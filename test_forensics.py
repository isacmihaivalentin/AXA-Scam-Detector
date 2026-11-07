"""Metamorphic, uncertainty and provider safety checks for the forensics upgrade."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import database
import engine
import reputation
from action_context import extract_frames
from database import BrandDomain
from semantic_analysis import LocalResult, ModelStrength, observe
from text_analysis import analyze_language
from url_analysis import analyze_single_url, extract_url_spans


class MechanismTests(unittest.TestCase):
    def analyze(self, message, observations=()):
        with patch.object(engine.local_model, "analyze", return_value=LocalResult("completed", tuple(observations))):
            return engine.rules_analysis(message)

    def test_sensitive_direction_and_original_span_under_transformations(self):
        examples = (
            "Please read the six digits from the SMS to me.",
            "Parola contului, pune-o aici în răspuns.",
            "Îmi dai PINu aici pe chat?",
        )
        for text in examples:
            with self.subTest(text=text):
                result = self.analyze(text)
                self.assertGreaterEqual(result["risk_score"], 70)
                self.assertTrue(result["action_frames"])
        for text in ("Do not share your recovery code with me.", "Nu trimiteți CVV-ul în chat.",
                     "Training example: «Trimite-mi PIN-ul în chat.»"):
            with self.subTest(text=text):
                self.assertLess(self.analyze(text)["risk_score"], 35)

    def test_value_order_critical_distinction(self):
        request = "Transferul pentru câștig se eliberează după ce alimentați portofelul cu 80 EUR."
        inverted = "Veți primi suma integral. Achitați comisionul doar după ce primiți banii."
        self.assertIn("advance_fee", [m["id"] for m in self.analyze(request)["assessment"]["mechanisms"]])
        self.assertLess(self.analyze(inverted)["risk_score"], 35)

    def test_unresolved_local_observation_is_audited_and_unestimated(self):
        text = "Acel lucru despre care am vorbit pune-l în răspunsul pentru mine."
        proposed = observe(text, "request_credentials", "local_nli", (0, len(text)), "clause",
                           strength=ModelStrength(entailment=.96, neutral=.02, contradiction=.02))
        result = self.analyze(text, [proposed])
        self.assertEqual(result["risk_score"], 0)  # Legacy observed indicator subtotal.
        self.assertIsNone(result["assessment"]["risk_estimate"])
        self.assertEqual(result["assessment"]["risk_status"], "unestimated")
        record = result["evidence_review"][0]
        self.assertEqual((record["status"], record["reason"]), ("tentative", "target_not_grounded"))
        self.assertEqual(record["evidence_text"], text)

    def test_contradiction_protected(self):
        text = "Do not send me your password, even for technical support."
        candidate = observe(text, "request_credentials", "local_nli", (0, len(text)), "clause")
        result = self.analyze(text, [candidate])
        self.assertEqual(result["risk_score"], 0)
        self.assertEqual(result["evidence_review"][0]["status"], "contradictory")

    def test_routine_conversation_and_invoice_stay_below_threshold(self):
        for message in ("Hei, ne vedem la masă?", "Achitați 200 lei pentru factura curentă.",
                        "Puteți vedea factura la www.facturi.example."):
            with self.subTest(message=message):
                result = self.analyze(message)
                self.assertLess(result["risk_score"], 35)

    def test_reported_narration_and_first_person_storage_do_not_request_credentials(self):
        for text in (
            "Pe panou e un text care spune «Intră aici» și cere parola contului. Este o fraudă, nu-l urma.",
            "Mi-a apărut o notificare: «Trimite-mi parola și PIN-ul». Am închis-o și am raportat incidentul.",
            "Noua parolă o lăsăm în plicul sigilat din birou.",
        ):
            with self.subTest(text=text):
                self.assertLess(self.analyze(text)["risk_score"], 35)

    def test_unverified_hostname_reference_requires_an_active_destination(self):
        text = ("Aster Public: Adresa de pe chitanță este aster.public.example. "
                "Accesați https://aster.public.example.formulare.test/validare pentru actualizarea contului.")
        result = self.analyze(text)
        self.assertEqual(result["risk_label"], "suspicious")
        self.assertEqual(result["domain_reference_conflict"]["registrable_domain"], "formulare.test")
        self.assertEqual(result["domain_assessment"][0]["catalog_status"], "unknown_brand")

    def test_original_and_swapped_brands_use_the_same_mechanism(self):
        scores = []
        for brand, domain in (("BCR", "bcr.ro"), ("ING", "ing.ro")):
            lookalike = f"https://{domain}.client-reset.example/verify"
            result = self.analyze(f"{brand}: Confirmați contul la {lookalike}.")
            self.assertTrue(any(m["id"] == "organization_lookalike" for m in result["assessment"]["mechanisms"]))
            scores.append(result["risk_score"])
            direct = self.analyze(f"Spune-mi codul OTP aici. Detalii https://{domain}.")
            self.assertGreaterEqual(direct["risk_score"], 70)
        self.assertEqual(scores[0], scores[1])

    def test_irregular_format_and_repetition_do_not_create_new_risk(self):
        text = "Va rog sa imi trimiteti codul OTP in chat."
        score = self.analyze(text)["risk_score"]
        self.assertEqual(self.analyze("VĂ ROG să îmi trimiteți codul OTP în chat!")["risk_score"], score)
        self.assertEqual(self.analyze(" ".join([text] * 14))["risk_score"], score)


class AddressTests(unittest.TestCase):
    def test_explicit_unspecified_and_defanged_protocol(self):
        for text, protocol, has_https, source in (
            ("www.example.com", None, None, "unspecified"),
            ("//www.example.com", None, None, "unspecified"),
            ("hxxps://example[.]com/login", "https", None, "defanged"),
            ("https://example.com", "https", True, "explicit"),
        ):
            with self.subTest(text=text):
                links = list(extract_url_spans(f"Vezi ({text})."))
                self.assertEqual(links[0][0], text)
                u = analyze_single_url(text)
                self.assertEqual((u["protocol"], u["has_https"], u["protocol_source"]), (protocol, has_https, source))
                self.assertEqual(u["registrable_domain"], "example.com")

    def test_unfamiliar_catalog_structures_and_short_token_precision(self):
        catalog = (BrandDomain("Aurevia", "fictional", "aurevia.com", "fixture", "2026-11-06"),)
        for host, method in (("aureiva.example", "adjacent_transposition"), ("au-revia.example", "split_brand"),
                             ("aureviapay.example", "concatenated_service_token"),
                             ("aurevia.com.login.example", "embedded_official_hostname")):
            with self.subTest(host=host):
                report = analyze_single_url(f"https://{host}", catalog)
                self.assertEqual(report["typosquatting"]["method"], method)
                self.assertFalse(report["typosquatting"]["verified_match"])
        self.assertFalse(analyze_single_url("https://parking.example")["typosquatting"]["is_typosquatting"])
        self.assertEqual(analyze_single_url("https://api.user.github.io")["registrable_domain"], "user.github.io")

    def test_unknown_claim_and_embedded_url_do_not_prove_ownership_or_redirects(self):
        text = "Echipa VelaNova: Verifică identitatea la https://site.example/?redirect=https%3A%2F%2Fvelanova.example."
        with patch.object(engine.local_model, "analyze", return_value=LocalResult("disabled")):
            result = engine.analyze_text(text, "")
        claim = result["analysis"]["domain_assessment"][0]
        self.assertEqual(claim["catalog_status"], "unknown_brand")
        self.assertEqual(claim["destinations"][0]["status"], "verification_incomplete")
        u = result["url_reports"][0]
        self.assertTrue(u["embedded_destination_hint"])
        self.assertIsNone(u["redirect_count"])

    def test_alias_optional_and_does_not_change_catalog_tuple_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "axa.sqlite3"
            database.initialize_sqlite(path)
            with sqlite3.connect(path) as conn:
                conn.execute("""INSERT INTO brand_aliases
                    SELECT id, 'Retail Alias', 'retailalias', 'review fixture', '2026-11-06'
                    FROM brands WHERE normalized_name='emag'""")
            with patch.dict(os.environ, {"AXA_SQLITE_PATH": str(path), "AXA_DATABASE_URL": ""}):
                entries, status = database.load_catalog()
                self.assertEqual(status, "sqlite")
                self.assertIn("Retail Alias", next(e for e in entries if e.name == "eMAG").aliases)
                with sqlite3.connect(path) as conn:
                    conn.execute("DROP TABLE brand_aliases")
                entries, status = database.load_catalog()
                self.assertEqual(status, "sqlite")
                self.assertFalse(next(e for e in entries if e.name == "eMAG").aliases)


class ReputationTests(unittest.TestCase):
    def test_provider_uses_fixed_destination_and_is_separate_from_static(self):
        report = analyze_single_url("https://www.iana.org/test")
        with patch.dict(os.environ, {"AXA_WEB_RISK_API_KEY": "test-key"}), patch.object(
            reputation, "provider_response", return_value={"threat": {
                "threatTypes": ["SOCIAL_ENGINEERING"], "expireTime": "2099-01-01T12:00:00Z",
            }},
        ) as transport:
            status = reputation.add_reputation([report])
        req = transport.call_args.args[0]
        dest = urlsplit(req.full_url)
        self.assertEqual(dest.hostname, "webrisk.googleapis.com")
        self.assertEqual(parse_qs(dest.query)["uri"], ["https://www.iana.org/test"])
        self.assertNotIn("test-key", req.full_url)
        self.assertEqual(status, "threat_match")
        self.assertEqual(report["risk_points"], 0)
        self.assertIsNone(reputation.NoRedirect().redirect_request(None, None, 302, "", None, "http://127.0.0.1"))

    def test_privacy_skip_rate_limit_and_no_match(self):
        reports = [analyze_single_url(url) for url in ("www.iana.org", "https://www.iana.org/?token=x",
                                                      "https://169.254.169.254/", "https://www.iana.org/")]
        with patch.dict(os.environ, {"AXA_WEB_RISK_API_KEY": "test"}), patch.object(
            reputation, "provider_response", return_value={},
        ) as transport:
            self.assertEqual(reputation.add_reputation(reports), "partial")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(reports[-1]["reputation"]["status"], "no_known_match")
        with patch.object(reputation, "provider_response", side_effect=HTTPError("https://example.com", 429, "", None, None)):
            self.assertEqual(reputation.lookup("https://www.iana.org/", "test")["status"], "rate_limited")


if __name__ == "__main__":
    unittest.main()
