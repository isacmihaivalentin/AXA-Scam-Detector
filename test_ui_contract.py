"""UI contract tests (v2.1 interface): the additive `analysis.ui` adapter, response-shape
stability, and static-asset / privacy guarantees the redesigned frontend relies on.
Semantic inputs are MOCK Gemini readings; the pipeline below them is real."""
import json
import re
import unittest
from pathlib import Path

import engine
from test_v21 import KEEP, M, R, SEVEN, Base

ROOT = Path(__file__).parent
# Every key the v2.1 API returned before the redesign; the redesign may only ADD keys.
BASELINE_ANALYSIS_KEYS = {
    "risk_score", "risk_label", "verdict", "summary", "headline", "assessment", "interpretation", "reasons",
    "highlights", "evidence", "profile", "stages", "recommendations", "scenario", "share_text", "domain_assessment",
    "rules", "checks", "uncertainties", "engine_used", "timings_ms",
}
POSITIVE_SAFETY = re.compile(r"\b(sigur|verificat|în siguranță|legitim|safe|garantat)\b", re.IGNORECASE)


class UiAdapter(Base):
    def ui(self, text, reading):
        return self.run_ai(text, reading)["analysis"]

    def test_states_map_existing_labels_without_changing_them(self):
        cases = [
            (SEVEN["D-cargus-pickup"], M("ordinary_or_legitimate", sender="Cargus", reqs=[
                R("click_link", "detalii", "low", "Vezi detalii")]), "low", "no_clear_signs"),
            (SEVEN["E-orange-promo-2"], M("marketing_or_spam", sender="Orange", reqs=[
                R("click_link", "joc", "low", "Intra in Pinata Party aici")]), "marketing", "no_clear_signs"),
            ("Trimite-mi codul primit prin SMS acum.", M("likely_scam", "otp_or_authentication_theft", reqs=[
                R("share_otp_or_code", "cod", "secret_credential", "Trimite-mi codul primit prin SMS")]), "critical", "strong"),
            ("Salut, ce mai faci?", M("likely_scam", "other_suspicious_mechanism"), "inconclusive", "unable"),
            ("Nu comunica nimanui parola.", M("protective_or_educational", reqs=[
                R("share_password", "parola", "secret_credential", "Nu comunica nimanui parola", stance="discouraged", handover=KEEP)]),
             "protective", "no_clear_signs"),
        ]
        for text, reading, label, state in cases:
            with self.subTest(label):
                a = self.ui(text, reading)
                self.assertEqual(a["assessment"]["label"], label)
                self.assertEqual(a["ui"]["state"], state)
                self.assertTrue(a["ui"]["title"] and a["ui"]["reason"] and a["ui"]["action"])

    def test_benign_and_unknown_never_claim_safety(self):
        for text, reading in ((SEVEN["G-tursib-portal"], M("ordinary_or_legitimate", reqs=[
                R("sign_in", "autentificare", "secret_credential", "Va rugam sa va autentificati in Portal", handover=KEEP)])),
                              ("Salut, ce mai faci?", M("likely_scam", "other_suspicious_mechanism"))):
            u = self.ui(text, reading)["ui"]
            for field in ("title", "reason", "action"):
                self.assertIsNone(POSITIVE_SAFETY.search(u[field]), (field, u[field]))
            self.assertIn("nu", u["action_detail"].lower())  # always qualifies what remains unconfirmed

    def test_partial_analysis_is_flagged(self):
        a = engine.analyze_text(SEVEN["D-cargus-pickup"], "")["analysis"]
        self.assertTrue(a["ui"]["partial"])
        self.assertIn("AI", a["ui"]["partial_note"])

    def test_action_follows_what_the_message_asks(self):
        call = self.ui("DPD: Sunati urgent la 0900 123 456 (tarif special) in 2 ore, altfel coletul va fi distrus.", M(
            "likely_scam", "delivery_scam", reqs=[R("call_number", "apel", "financial_asset", "Sunati urgent la 0900 123 456", dest="0900 123 456")],
            thr=[("loss_of_goods_or_money", "altfel coletul va fi distrus")]))["ui"]
        self.assertIn("numărul", call["action"])
        self.assertNotIn("linkul", call["action"])
        self.assertIn("called", call["recovery_suggested"])
        fam = self.ui("Mama, sunt eu de pe numarul unui coleg. Trimite-mi 900 lei in contul lui RO49AAAA1B31007593840000.", M(
            "likely_scam", "family_impersonation", stype="family_or_friend", reqs=[
                R("transfer_money", "900 lei", "financial_asset", "Trimite-mi 900 lei in contul lui", dest="RO49AAAA1B31007593840000")],
            tac=[("family_impersonation", "sunt eu de pe numarul unui coleg")]))["ui"]
        self.assertIn("numărul ei vechi", fam["action"])
        self.assertEqual(fam["recovery_suggested"], ["paid"])

    def test_response_shape_is_a_superset_of_the_previous_contract(self):
        a = self.ui(SEVEN["D-cargus-pickup"], M("ordinary_or_legitimate"))
        self.assertLessEqual(BASELINE_ANALYSIS_KEYS, set(a))
        self.assertEqual(set(a) - BASELINE_ANALYSIS_KEYS, {"ui"})


class Spectrum(Base):
    """The restored green-amber-red scale: zones follow the policy thresholds, the marker
    follows risk_estimate, and nothing is placed that the backend did not estimate."""

    def run_case(self, text, reading):
        a = self.run_ai(text, reading)["analysis"]
        return a, a["ui"]["spectrum"]

    def test_zone_matches_label_and_marker_matches_estimate(self):
        cases = [
            (SEVEN["D-cargus-pickup"], M("ordinary_or_legitimate", sender="Cargus", reqs=[R("click_link", "d", "low", "Vezi detalii")])),
            ("DPD: Sunati urgent la 0900 123 456 (tarif special) in 2 ore, altfel coletul va fi distrus.", M(
                "likely_scam", "delivery_scam", reqs=[R("call_number", "apel", "financial_asset", "Sunati urgent la 0900 123 456", dest="0900 123 456")],
                thr=[("loss_of_goods_or_money", "altfel coletul va fi distrus")])),
            ("Trimite-mi codul primit prin SMS acum.", M("likely_scam", "otp_or_authentication_theft", reqs=[
                R("share_otp_or_code", "cod", "secret_credential", "Trimite-mi codul primit prin SMS")])),
        ]
        expected = {"no_clear_signs": "clear", "suspect": "suspect", "strong": "strong"}
        seen = set()
        for text, reading in cases:
            a, sp = self.run_case(text, reading)
            self.assertEqual(sp["status"], "placed")
            self.assertEqual(sp["position"], a["assessment"]["risk_estimate"])
            self.assertEqual(sp["zone"], expected[a["ui"]["state"]])
            zone = next(z for z in sp["zones"] if z["key"] == sp["zone"])
            self.assertTrue(zone["from"] <= sp["position"] < zone["to"] or (sp["position"] == 100 and zone["to"] == 100))
            self.assertIn("nu o probabilitate", sp["label"])
            seen.add(sp["zone"])
        self.assertEqual(seen, {"clear", "suspect", "strong"})

    def test_zone_boundaries_are_the_policy_thresholds(self):
        import decision
        import presentation
        self.assertEqual([(z["from"], z["to"]) for z in presentation.SPECTRUM_ZONES],
                         [(0, decision.ALERT), (decision.ALERT, decision.CRITICAL), (decision.CRITICAL, 100)])
        for score, zone in ((0, "clear"), (34, "clear"), (35, "suspect"), (69, "suspect"), (70, "strong"), (97, "strong")):
            sp = presentation.spectrum({"risk_estimate": score}, partial=False)
            self.assertEqual(sp["zone"], zone, score)

    def test_unestimated_never_gets_a_marker(self):
        a, sp = self.run_case("Salut, ce mai faci?", M("likely_scam", "other_suspicious_mechanism"))
        self.assertIsNone(a["assessment"]["risk_estimate"])
        self.assertEqual((sp["status"], sp["position"], sp["zone"]), ("unestimated", None, None))

    def test_no_ai_never_gets_a_green_marker(self):
        import presentation
        sp = presentation.spectrum({"risk_estimate": 10}, partial=True)
        self.assertEqual((sp["status"], sp["position"], sp["zone"]), ("partial_unplaced", None, None))
        warn = presentation.spectrum({"risk_estimate": 80}, partial=True)  # a rules-only warning is never hidden
        self.assertEqual((warn["status"], warn["zone"]), ("placed", "strong"))
        for text in (SEVEN[k] for k in SEVEN):
            sp = engine.analyze_text(text, "")["analysis"]["ui"]["spectrum"]
            self.assertFalse(sp["status"] == "placed" and sp["zone"] == "clear", text)


class StaticContract(unittest.TestCase):
    def test_fonts_are_self_hosted_with_licences_and_csp_is_tight(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("font-src 'self'", main)
        self.assertNotIn("googleapis", main)
        for name in re.findall(r'"([\w-]+\.(?:woff|ttf))"', main):
            self.assertTrue((ROOT / "assets/fonts" / name).exists(), name)
        for licence in ("BricolageGrotesque-OFL.txt", "WorkSans-OFL.txt"):
            self.assertTrue((ROOT / "assets/fonts" / licence).exists())
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("fonts.googleapis", html)

    def test_frontend_never_stores_message_text_and_never_links_submitted_urls(self):
        js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"setItem\([^)]*\btext\b")
        self.assertNotRegex(js, r"href=\"\$\{[^}]*original_url")
        self.assertIn("const esc", js)

    def test_frontend_draws_the_scale_only_from_the_adapter(self):
        js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
        # risk_estimate is only quoted as text in the technical details, never used to place the marker
        self.assertEqual(len(re.findall(r"risk_estimate", js)), 2, "risk_estimate must not drive presentation")
        self.assertIn("sp.status === 'placed'", js)
        self.assertNotRegex(js, r"style=\"")  # CSP style-src 'self': no inline style attributes
        eyebrows = re.search(r"const EYEBROW = \{([^}]*)\}", js).group(1)
        self.assertIsNone(POSITIVE_SAFETY.search(eyebrows), eyebrows)
        css = (ROOT / "assets/axa.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion:reduce", css)
        for token in ("--d-fb:110ms", "--d-local:210ms", "--d-major:320ms", "--d-marker:650ms"):
            self.assertIn(token, css)


if __name__ == "__main__":
    unittest.main()
