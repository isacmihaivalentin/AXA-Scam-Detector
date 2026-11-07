"""Rules regressions, domain parsing, storage, offline guarantees and FastAPI routes.

Route tests need FastAPI + httpx (requirements-dev.txt); they are skipped otherwise.
"""
import asyncio
import json
import os
import socket
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import database
import engine
from url_analysis import analyze_single_url, detect_typosquatting, extract_urls

try:
    import httpx
    import main
except ImportError:  # pragma: no cover - depends on the environment
    httpx = main = None

ROOT = Path(__file__).resolve().parent
CASES = json.loads((ROOT / "regression_cases.json").read_text(encoding="utf-8"))


class Store(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "test.sqlite3"
        self.enterContext(patch.dict(os.environ, {"AXA_SQLITE_PATH": str(self.path)}, clear=False))
        for key in ("GEMINI_API_KEY", "AXA_DATABASE_URL", "AXA_WEB_RISK_API_KEY"):
            os.environ.pop(key, None)
        database.initialize_sqlite(self.path)


class RulesEngineTests(Store):
    """The deterministic engine is the offline fallback; its reviewed behaviour must not regress."""

    def test_reviewed_regressions(self):
        reviewed = database.load_reviewed_examples()
        self.assertEqual(len(reviewed), len(CASES))
        for message, expected, scenario in reviewed:
            with self.subTest(scenario=scenario):
                fixture = next(case for case in CASES if case["id"] == scenario)
                report = engine.rules_analysis(message)
                urls = report["url_reports"]
                self.assertEqual(report["risk_label"], expected)
                self.assertIn(report["risk_score"], range(101))
                if "intent" in fixture:
                    self.assertEqual(report["context"]["sensitive_data_intent"], fixture["intent"])
                if "tactic" in fixture:
                    self.assertIn(fixture["tactic"], report["tactics_detected"])
                if "official" in fixture:
                    self.assertEqual(any(url["typosquatting"].get("is_official") for url in urls), fixture["official"])
                if "typo" in fixture:
                    self.assertEqual(any(url["typosquatting"].get("is_typosquatting") for url in urls), fixture["typo"])
                if "url_status" in fixture:
                    self.assertEqual(urls[0]["inspection_status"], fixture["url_status"])
                for highlight in report["highlights"]:
                    snippet = message.encode("utf-16-le")[2 * highlight["start"]:2 * highlight["end"]]
                    self.assertEqual(snippet.decode("utf-16-le"), highlight["phrase"])
                if scenario == "01-bcr-awareness":
                    self.assertEqual(report["risk_score"], 0)
                    self.assertEqual(report["highlights"], [])
                    self.assertIn("BCR", report["context"]["brand_mentions"])
                if scenario == "20-embedded-model-instructions":
                    self.assertIn("embedded_analysis_instruction", report["context"]["context_notes"])
                if scenario == "28-warning-then-request":
                    self.assertEqual(report["highlights"][0]["phrase"], "trimite parola")

    def test_scoring_invariants(self):
        def score(message):
            return engine.rules_analysis(message)["risk_score"]

        warning = "Nu divulga parola sau codul PIN."
        request = "Trimite-mi parola."
        bad_url = "https://bcr.ro.login-check.example"
        base = score(request)
        self.assertGreaterEqual(base, 70)
        self.assertEqual(score(warning), score("BCR. " + " ".join([warning] * 30)))
        self.assertEqual(score(" ".join([request] * 40) + " Trimite-mi codul PIN. Trimite-mi codul OTP."), base)
        self.assertEqual(score(request + " " + warning + " https://www.bcr.ro"), base)
        self.assertEqual(score(bad_url), score(bad_url + " " + bad_url + "/2 https://www.bcr.ro"))
        self.assertEqual(score("http://regular.top"), score("https://regular.example"))
        report = engine.analyze_text(" ".join(f"https://regular.example/{i}" for i in range(12)), "")["analysis"]
        self.assertEqual((report["checks"]["urls_detected"], report["checks"]["urls_analyzed"]), (12, 10))
        self.assertTrue(any("primele 10" in note for note in report["uncertainties"]))

    def test_database_unavailable(self):
        with patch.dict(os.environ, {"AXA_SQLITE_PATH": str(self.path) + ".missing"}):
            payload = engine.analyze_text("Trimite-mi codul OTP. https://info.bcr.ro", "")
            report = payload["analysis"]
            self.assertEqual(report["risk_label"], "critical")
            self.assertEqual(report["checks"]["database"], "unavailable_static_fallback")
            self.assertEqual(payload["url_reports"][0]["typosquatting"]["source"], "static_catalog")
            self.assertFalse(Path(os.environ["AXA_SQLITE_PATH"]).exists())

    def test_database_records_and_idempotent_seed(self):
        database.initialize_sqlite(self.path)
        self.assertEqual(len(database.load_reviewed_examples()), len(CASES))
        with closing(sqlite3.connect(self.path)) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO brands (name, normalized_name, category) VALUES (?, ?, ?)", ("Demo", "demo", "retail")
            )
            conn.execute(
                "INSERT INTO official_domains (brand_id, domain, verification_source, verified_at) VALUES (?, ?, ?, ?)",
                (cursor.lastrowid, "demo-company.com", "fixture://local", "2026-11-06"),
            )
            conn.execute("INSERT INTO scam_examples (message_text, expected_label, scenario_type) VALUES (?, ?, ?)",
                         ("Excluded fixture", "uncertain", "unreviewed"))
        payload = engine.analyze_text("https://eu.demo-company.com", "")
        typo = payload["url_reports"][0]["typosquatting"]
        self.assertTrue(typo["is_official"])
        self.assertEqual(typo["source"], "verified_database")
        self.assertEqual(typo["verification_source"], "fixture://local")
        self.assertEqual(len(database.load_reviewed_examples()), len(CASES))

    def test_no_submitted_url_network_access(self):
        blocked = AssertionError("unexpected network access")
        with (
            patch.object(socket, "getaddrinfo", side_effect=blocked),
            patch.object(socket.socket, "connect", side_effect=blocked),
        ):
            message = ("https://bcr.ro.login-check.example https://bit.ly/sample http://127.0.0.1/private "
                       "http://169.254.169.254/latest/meta-data http://[::1]:8080/ "
                       "http://2130706433/private ftp://host.example/file javascript:alert(1)")
            payload = engine.analyze_text(message, "")
        reports = payload["url_reports"]
        self.assertEqual(len(reports), 8)
        self.assertTrue(reports[1]["is_shortened"])
        self.assertTrue(all(u["redirect_count"] is None and u["page_title"] is None for u in reports))
        self.assertIn("nepublică", " ".join(reports[3]["flags"]))
        self.assertIn("8080", " ".join(reports[4]["flags"]))
        self.assertIn("numerică", " ".join(reports[5]["flags"]))
        self.assertTrue(all(u["inspection_status"] == "unsupported_scheme" for u in reports[6:]))


@unittest.skipIf(main is None, "FastAPI/httpx not installed (pip install -r requirements-dev.txt)")
class RouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory) / "test.sqlite3"
        self.enterContext(patch.dict(os.environ, {"AXA_SQLITE_PATH": str(path)}, clear=False))
        os.environ.pop("GEMINI_API_KEY", None)
        database.initialize_sqlite(path)

    async def asyncSetUp(self):
        self.client = await self.enterAsyncContext(
            httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")
        )

    async def test_routes_and_size_limits(self):
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AXA Scam Detector", response.text)
        self.assertIn("/assets/axa.css", response.text)
        self.assertIn("/assets/app.js", response.text)
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])
        self.assertEqual((await self.client.get("/assets/app.js")).status_code, 200)
        self.assertEqual((await self.client.get("/assets/..%2Fmain.py")).status_code, 404)
        self.assertEqual((await self.client.get("/api/status")).json()["semantic_ai"], "not_configured")
        self.assertNotIn("cdn.tailwindcss", response.text)
        css = await self.client.get("/assets/axa.css")
        self.assertEqual(css.status_code, 200)
        self.assertTrue(css.headers["content-type"].startswith("text/css"))
        self.assertEqual((await self.client.post("/api/analyze", json={"text": " \n "})).status_code, 400)
        self.assertEqual((await self.client.post("/api/analyze", json={"text": "a" * 20001})).status_code, 422)
        self.assertEqual((await self.client.post("/api/analyze", content=b"x" * 300000)).status_code, 413)

        async def chunks():
            for _ in range(6):
                await asyncio.sleep(0)
                yield b"x" * 65536

        too_large = await self.client.post("/api/analyze", content=chunks(), headers={"content-type": "application/json"})
        self.assertEqual(too_large.status_code, 413)
        response = await self.client.post("/api/analyze-image", files={"file": ("x.png", b"pretend", "image/png")})
        self.assertEqual(response.status_code, 503)
        response = await self.client.post("/api/analyze", json={"text": "Buna ziua."})
        report = response.json()["analysis"]
        self.assertEqual((report["risk_label"], report["checks"]["semantic_ai"]["status"]), ("uncertain", "not_configured"))


class DomainTests(unittest.TestCase):
    def test_url_parsing_boundaries(self):
        self.assertTrue(detect_typosquatting("info.bcr.ro")["is_official"])
        self.assertTrue(detect_typosquatting("WWW.BCR.RO.")["is_official"])
        self.assertTrue(detect_typosquatting("o1x-plata-sigura.example")["is_typosquatting"])
        self.assertFalse(detect_typosquatting("shopping.com")["is_typosquatting"])
        self.assertEqual(extract_urls("Vezi (https://www.emag.ro/a(b)), acum."), ["https://www.emag.ro/a(b)"])
        self.assertEqual(extract_urls("contact la x@sub.bcr.ro; link bcr.ro.login-check.example."),
                         ["bcr.ro.login-check.example"])
        for url in ("https://[bad", "https://example.com:99999", "https://[::1]fake.example",
                    "https://www.bcr.ro\\@outside.example", "https://invalid_host.example"):
            with self.subTest(url=url):
                self.assertEqual(analyze_single_url(url)["inspection_status"], "invalid_url")
        for url in ("https://оlх.example/", "https://xn--l-0tbw.example/"):
            self.assertTrue(analyze_single_url(url)["typosquatting"]["is_typosquatting"])
        self.assertEqual(analyze_single_url("https://a.b.co.uk")["registrable_domain"], "b.co.uk")
        self.assertEqual(analyze_single_url("https://a.project.github.io")["registrable_domain"], "project.github.io")
        test_catalog = (database.BrandDomain("Hosting", "test", "github.io", "fixture://local", "2026-11-06"),)
        self.assertFalse(detect_typosquatting("project.github.io", test_catalog)["is_official"])
        self.assertFalse(analyze_single_url("https://bcr.ro@unrelated.example")["typosquatting"]["is_official"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
