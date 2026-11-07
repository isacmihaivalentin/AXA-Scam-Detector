"""v2.1 regression and paired tests.

Semantic inputs are MOCKS of Gemini output; everything downstream (validation, grounding,
URL forensics, catalog, rules, decision, presentation) is the real code. Each paired test
puts a legitimate message and a malicious one on the two sides of the same boundary.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import engine
import gemini_client
import semantic_gemini
from url_analysis import analyze_single_url, extract_url_spans

KEEP, GIVE = "recipient_keeps_control", "to_sender_or_message_destination"
ALERTS = {"critical", "suspicious"}


def R(action, obj, sens, quote, stance="requested", handover=GIVE, dest=None):
    return {"action": action, "object": obj, "sensitivity": sens, "recipient": None, "stance": stance,
            "handover": handover, "destination": dest, "quote": quote}


def M(overall, mech="none", sender=None, stype="none", reqs=(), tac=(), thr=(), pro=(), dep=None, prot=()):
    return {"message_language": "ro", "claim_summary": "Rezumat.", "wants_summary": "Cere ceva.",
            "claimed_sender": {"name": sender, "type": stype, "quote": None},
            "requests": list(reqs), "promises": [{"kind": k, "quote": q} for k, q in pro],
            "threats": [{"kind": k, "quote": q} for k, q in thr],
            "dependency": {"present": bool(dep), "description": None, "quote": dep},
            "tactics": [{"tactic": t, "quote": q} for t, q in tac],
            "protective_context": [{"kind": k, "quote": q} for k, q in prot],
            "mechanism": {"category": mech, "description": "Descriere."}, "overall": overall, "uncertainties": []}


class Base(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory) / "t.sqlite3"
        self.enterContext(patch.dict(os.environ, {"AXA_SQLITE_PATH": str(path)}))
        for key in ("GEMINI_API_KEY", "AXA_WEB_RISK_API_KEY", "AXA_DATABASE_URL"):
            os.environ.pop(key, None)
        database.initialize_sqlite(path)

    def run_ai(self, text, response):
        raw = json.dumps(response, ensure_ascii=False)
        interpret = lambda t, k: semantic_gemini.interpret(t, k, generate=lambda *a, **kw: raw)  # noqa: E731
        return engine.analyze_text(text, "test-key", interpret=interpret)

    def assess(self, text, response):
        return self.run_ai(text, response)["analysis"]["assessment"]

    def assertNotAlert(self, assessment):
        self.assertNotIn(assessment["label"], ALERTS, assessment)

    def assertAlert(self, assessment, label=None):
        self.assertIn(assessment["label"], ALERTS if label is None else {label}, assessment)


# --------------------------------------------------------------- the seven reported messages
SEVEN = {c["id"]: c["text"] for c in json.loads(
    (Path(__file__).parent / "evaluation/audit/seven_cases.json").read_text(encoding="utf-8"))}


class ReportedFalsePositives(Base):
    """The user's seven legitimate messages, with the reading a competent model gives AND with
    the error modes reconstructed from the live scores (over-suspicious, own sign-in as a secret)."""

    def readings(self):
        return {
            "A-visa-gpay": M("ordinary_or_legitimate", sender="Visa", stype="bank", reqs=[
                R("call_number", "apel", "low", "contacteaza-ne la *2000", stance="hypothetical", dest="*2000")]),
            "B-fan-coordination": M("ordinary_or_legitimate", sender="FAN Courier", stype="courier", reqs=[
                R("call_number", "apel", "low", "Va rugam sa ne contactati la tel 0725724911", dest="0725724911")]),
            "C-orange-promo-1": M("marketing_or_spam", sender="My Orange", stype="telecom_or_utility", reqs=[
                R("click_link", "joc", "low", "Hai in Pinata Party aici"),
                R("change_settings", "preferințe", "low", "modifica preferintele de prelucrare a datelor personale", handover=KEEP)],
                pro=[("money_or_prize", "poti castiga prin tragere la sorti")]),
            "D-cargus-pickup": M("ordinary_or_legitimate", sender="Cargus", stype="courier", reqs=[
                R("other", "PIN", "secret_credential", "PIN 3168", stance="provided_to_recipient", handover=KEEP),
                R("click_link", "detalii", "low", "Vezi detalii")]),
            "E-orange-promo-2": M("marketing_or_spam", sender="Orange", stype="telecom_or_utility", reqs=[
                R("click_link", "joc", "low", "Intra in Pinata Party aici")],
                pro=[("money_or_prize", "intri in tragerea la sorti")]),
            "F-cargus-delivery": M("ordinary_or_legitimate", sender="Cargus", stype="courier", reqs=[
                R("other", "PIN", "secret_credential", "PIN 5499", stance="provided_to_recipient", handover=KEEP),
                R("click_link", "detalii", "low", "Vezi detalii si optiuni")]),
            "G-tursib-portal": M("ordinary_or_legitimate", sender="Tursib", stype="other_organization", reqs=[
                R("sign_in", "autentificare", "secret_credential", "Va rugam sa va autentificati in Portal", handover=KEEP)]),
        }

    def test_faithful_readings_are_not_alerts(self):
        for case, reading in self.readings().items():
            with self.subTest(case):
                a = self.assess(SEVEN[case], reading)
                self.assertNotAlert(a)
                self.assertIsNotNone(a["risk_estimate"])

    def test_live_observed_over_suspicious_reading_is_not_an_alert(self):
        """Reconstruction: A, B, D, F scored 40 because Gemini said "suspicious"."""
        for case, reading in self.readings().items():
            reading["overall"] = "suspicious"
            reading["mechanism"]["category"] = "delivery_scam"
            with self.subTest(case):
                self.assertNotAlert(self.assess(SEVEN[case], reading))

    def test_live_observed_sign_in_as_secret_is_not_critical(self):
        """Reconstruction: G scored 82 from a requested secret_credential sign-in, whatever the reading."""
        for overall in ("ordinary_or_legitimate", "suspicious"):
            reading = M(overall, "credential_phishing" if overall == "suspicious" else "none", sender="Tursib", reqs=[
                R("sign_in", "autentificare", "secret_credential", "Va rugam sa va autentificati in Portal")])
            with self.subTest(overall):
                self.assertNotAlert(self.assess(SEVEN["G-tursib-portal"], reading))

    def test_supplied_pin_misread_as_request_is_never_critical(self):
        reading = M("ordinary_or_legitimate", sender="Cargus", reqs=[
            R("share_otp_or_code", "PIN", "secret_credential", "PIN 3168")])
        r = self.run_ai(SEVEN["D-cargus-pickup"], reading)
        a = r["analysis"]["assessment"]
        self.assertNotAlert(a)
        self.assertTrue(any(e["status"] == "contradicted" for e in r["analysis"]["evidence"]))

    def test_no_phantom_link_from_missing_space(self):
        self.assertEqual(list(extract_url_spans(SEVEN["B-fan-coordination"])), [])

    def test_orange_deep_link_is_third_party_not_lookalike(self):
        report = analyze_single_url("https://orange.onelink.me/JgKP/8rrjf5o2")
        self.assertFalse(report["typosquatting"]["is_typosquatting"])
        self.assertTrue(report["typosquatting"]["brand_on_third_party"])
        self.assertLess(report["risk_points"], 35)
        r = self.run_ai(SEVEN["E-orange-promo-2"], self.readings()["E-orange-promo-2"])
        statuses = {d["status"] for c in r["analysis"]["domain_assessment"] for d in c["destinations"]}
        self.assertIn("brand_on_third_party_host", statuses)
        self.assertNotIn("lookalike_outside_catalog", statuses)
        self.assertIsNone(r["analysis"]["scenario"])

    def test_identity_does_not_depend_on_sender_spelling(self):
        scores = set()
        for name in ("Orange", "My Orange", "Orange Romania"):
            reading = self.readings()["E-orange-promo-2"]
            reading["claimed_sender"]["name"] = name
            scores.add(self.assess(SEVEN["E-orange-promo-2"], reading)["risk_estimate"])
        self.assertEqual(len(scores), 1)

    def test_local_fallback_does_not_flag_orange_promotion(self):
        for case in ("C-orange-promo-1", "E-orange-promo-2"):
            with self.subTest(case):
                a = engine.analyze_text(SEVEN[case], "")["analysis"]["assessment"]
                self.assertNotIn(a["label"], ALERTS)


# --------------------------------------------------------------- paired boundaries
class PairedBoundaries(Base):
    def test_code_supplied_vs_code_requested(self):
        benign = "Sameday: Coletul te asteapta in easybox. Codul de deschidere este 553201. Valabil 48 ore."
        scam = "Sameday: Pentru eliberarea coletului trimite-ne prin SMS codul de deschidere primit."
        self.assertNotAlert(self.assess(benign, M("ordinary_or_legitimate", sender="Sameday", reqs=[
            R("other", "cod", "secret_credential", "Codul de deschidere este 553201", stance="provided_to_recipient", handover=KEEP)])))
        self.assertAlert(self.assess(scam, M("likely_scam", "otp_or_authentication_theft", sender="Sameday", reqs=[
            R("share_otp_or_code", "cod", "secret_credential", "trimite-ne prin SMS codul de deschidere primit")])), "critical")

    def test_own_sign_in_vs_sign_in_on_deceptive_or_unverified_link(self):
        own = "BCR: Ai un document nou. Autentifica-te in aplicatia George ca sa il vezi."
        self.assertNotAlert(self.assess(own, M("ordinary_or_legitimate", sender="BCR", stype="bank", reqs=[
            R("sign_in", "autentificare", "secret_credential", "Autentifica-te in aplicatia George", handover=KEEP)])))
        lookalike = "BCR: Contul este suspendat. Autentifica-te aici: https://bcr-verificare.top/login"
        self.assertAlert(self.assess(lookalike, M("ordinary_or_legitimate", sender="BCR", stype="bank", reqs=[
            R("sign_in", "autentificare", "secret_credential", "Autentifica-te aici", dest="https://bcr-verificare.top/login")])),
            "critical")  # technical deception is not cancelled by a benign reading
        unknown = "Portalul tau: Contul va fi sters azi. Autentifica-te aici: https://acces-portal.top/login"
        scam = M("likely_scam", "credential_phishing", reqs=[
            R("sign_in", "autentificare", "secret_credential", "Autentifica-te aici", dest="https://acces-portal.top/login")],
            thr=[("account_block", "Contul va fi sters azi")])
        self.assertAlert(self.assess(unknown, scam), "critical")
        scam["overall"], scam["threats"] = "ordinary_or_legitimate", []
        self.assertNotAlert(self.assess(unknown, scam))  # an unverified login link alone is a cue

    def test_promotion_vs_advance_fee_prize(self):
        promo = "Vodafone: Participa la tragerea la sorti pentru un telefon nou din aplicatia My Vodafone: https://vodafone.app.link/joc"
        self.assertNotAlert(self.assess(promo, M("marketing_or_spam", sender="Vodafone", reqs=[
            R("click_link", "joc", "low", "Participa la tragerea la sorti")], pro=[("money_or_prize", "un telefon nou")])))
        fee = "Vodafone: Ai castigat un telefon! Pentru livrare achita taxa de 9,99 lei aici: https://vodafone-castig.top/p"
        self.assertAlert(self.assess(fee, M("likely_scam", "advance_fee", sender="Vodafone", reqs=[
            R("pay_fee", "taxa", "financial_asset", "achita taxa de 9,99 lei", dest="https://vodafone-castig.top/p")],
            dep="Pentru livrare achita taxa de 9,99 lei", pro=[("money_or_prize", "Ai castigat un telefon")])), "critical")

    def test_family_message_vs_family_payment_redirection(self):
        self.assertNotAlert(self.assess("Mama, am ajuns acasa. Iti dau inapoi banii luni.", M("ordinary_or_legitimate", stype="family_or_friend")))
        scam = "Mama, sunt eu de pe numarul unui coleg. Trimite-mi 900 lei in contul lui RO49AAAA1B31007593840000, urgent."
        self.assertAlert(self.assess(scam, M("likely_scam", "family_impersonation", stype="family_or_friend", reqs=[
            R("transfer_money", "900 lei", "financial_asset", "Trimite-mi 900 lei in contul lui", dest="RO49AAAA1B31007593840000")],
            tac=[("family_impersonation", "sunt eu de pe numarul unui coleg")])), "critical")

    def test_routine_approval_vs_approval_for_caller(self):
        own = "Revolut: Ai cerut conectarea pe un dispozitiv nou? Daca da, confirma in aplicatie."
        self.assertNotAlert(self.assess(own, M("ordinary_or_legitimate", sender="Revolut", reqs=[
            R("approve_authorization", "confirmare", "device_or_account_control", "Daca da, confirma in aplicatie",
              stance="hypothetical", handover=KEEP)])))
        caller = "Revolut: Un agent te suna acum. Cand apare notificarea, apasa Aproba ca sa anulam plata."
        reading = M("likely_scam", "malicious_authorization", sender="Revolut", reqs=[
            R("approve_authorization", "aprobare", "device_or_account_control", "apasa Aproba ca sa anulam plata", handover=KEEP)])
        self.assertAlert(self.assess(caller, reading), "critical")  # approvals are never discounted by "keeps control"

    def test_protective_warning_vs_active_request(self):
        warning = "Nu trimite parola nimanui, nici celor care spun ca sunt de la banca."
        # The model wrongly calls it a request and quotes the text without the "Nu".
        a = self.assess(warning, M("likely_scam", "credential_phishing", reqs=[
            R("share_password", "parola", "secret_credential", "trimite parola nimanui")]))
        self.assertNotEqual(a["label"], "critical")
        mixed = "Nu trimite parola nimanui. Trimite parola aici operatorului nostru."
        r = self.run_ai(mixed, M("likely_scam", "credential_phishing", reqs=[
            R("share_password", "parola", "secret_credential", "trimite parola"),
            R("share_password", "parola", "secret_credential", "Nu trimite parola nimanui", stance="discouraged", handover=KEEP)]))
        self.assertEqual(r["analysis"]["assessment"]["label"], "critical")
        live = [h for h in r["analysis"]["highlights"] if h["severity"] == "alarm"]
        self.assertTrue(live and all(h["start"] > 20 for h in live))  # the live occurrence, not the protective one

    def test_official_domain_vs_hyphen_continued_official_hostname(self):
        official = "OLX: Ai un mesaj nou de la cumparator. Vezi in aplicatie sau pe https://www.olx.ro/myaccount"
        self.assertNotAlert(self.assess(official, M("ordinary_or_legitimate", sender="OLX", reqs=[
            R("click_link", "mesaje", "low", "Vezi in aplicatie", stance="hypothetical", handover=KEEP)])))
        fake = "OLX: Ca sa primesti banii, completeaza datele cardului aici: https://olx.ro-livrare.com/primire"
        self.assertAlert(self.assess(fake, M("ordinary_or_legitimate", sender="OLX", reqs=[
            R("share_card_data", "card", "secret_credential", "completeaza datele cardului aici", dest="https://olx.ro-livrare.com/primire")])),
            "critical")

    def test_unverified_platform_vs_reputation_match(self):
        text = "eMAG: Spune-ne parerea ta despre livrare: https://emag.page.link/feedback"
        reading = M("ordinary_or_legitimate", sender="eMAG", reqs=[R("click_link", "sondaj", "low", "Spune-ne parerea ta")])
        self.assertNotAlert(self.assess(text, reading))
        listed = {"provider": "google_web_risk", "status": "threat_match", "types": ["SOCIAL_ENGINEERING"]}
        with patch("engine.add_reputation", side_effect=lambda reports: [r.__setitem__("reputation", listed) for r in reports] and "threat_match"):
            self.assertAlert(self.assess(text, reading), "critical")  # no AI reading cancels a listed threat

    def test_known_payee_vs_payee_supplied_by_the_message(self):
        self.assertNotAlert(self.assess("Factura Digi de 52 lei e emisa. O poti plati din aplicatia Digi.", M(
            "ordinary_or_legitimate", sender="Digi", reqs=[R("pay_fee", "factura", "financial_asset", "O poti plati din aplicatia Digi", handover=KEEP)])))
        a = self.assess("Digi: plata facturii nu a fost inregistrata. Achita 52 lei in noul cont RO12BACX0000001234567890 azi.", M(
            "likely_scam", "payment_redirection", sender="Digi", reqs=[
                R("transfer_money", "52 lei", "financial_asset", "Achita 52 lei in noul cont", handover=KEEP, dest="RO12BACX0000001234567890")]))
        self.assertAlert(a)

    def test_unfamiliar_mechanism_is_still_caught(self):
        text = "Te-am trecut beneficiar la o mostenire. Notarul vrea doar o poza cu buletinul pe WhatsApp la 0755 111 222."
        self.assertAlert(self.assess(text, M("likely_scam", "other_suspicious_mechanism", reqs=[
            R("send_documents_or_photos", "buletin", "identity_document", "o poza cu buletinul pe WhatsApp", dest="0755 111 222")],
            pro=[("money_or_prize", "beneficiar la o mostenire")])), "critical")
        # Reading only, nothing itemised: an alert if the text sends the reader somewhere, never a reassuring low.
        a = self.assess(text, M("likely_scam", "other_suspicious_mechanism", pro=[("money_or_prize", "beneficiar la o mostenire")]))
        self.assertAlert(a)

    def test_ai_scam_claim_without_any_grounded_element_is_unresolved_not_low(self):
        a = self.assess("Salut, ce mai faci?", M("likely_scam", "other_suspicious_mechanism"))
        self.assertEqual(a["label"], "inconclusive")
        self.assertIsNone(a["risk_estimate"])


class Metamorphic(Base):
    def test_diacritics_order_and_language_do_not_change_the_verdict(self):
        variants = [
            ("Trimite-mi codul primit prin SMS, e urgent.", "Trimite-mi codul primit prin SMS"),
            ("Trimite-mi codul primit prin SMS, e urgent.".replace("Trimite", "Trimite"), "Trimite-mi codul primit prin SMS"),
            ("E urgent. Trimite-mi codul primit prin SMS.", "Trimite-mi codul primit prin SMS"),
            ("Trimite-mi codul primit prin SMS, e urgent.".translate(str.maketrans("ăâîșț", "aaist")), "Trimite-mi codul primit prin SMS"),
            ("Send me the code you got by SMS, it's urgent.", "Send me the code you got by SMS"),
        ]
        labels = {self.assess(text, M("likely_scam", "otp_or_authentication_theft", reqs=[
            R("share_otp_or_code", "cod", "secret_credential", quote)]))["label"] for text, quote in variants}
        self.assertEqual(labels, {"critical"})

    def test_brand_swap_keeps_third_party_and_lookalike_distinct(self):
        for brand, official in (("emag", "emag.ro"), ("olx", "olx.ro"), ("cargus", "cargus.ro")):
            with self.subTest(brand):
                third = analyze_single_url(f"https://{brand}.app.link/x")["typosquatting"]
                look = analyze_single_url(f"https://{brand}-livrare.top/x")["typosquatting"]
                self.assertTrue(third["brand_on_third_party"] and not third["is_typosquatting"])
                self.assertTrue(look["is_typosquatting"])


# --------------------------------------------------------------- deterministic layers
class UrlForensics(unittest.TestCase):
    def test_sentence_boundaries_are_not_links(self):
        for text in ("detaliile livrarii.FAN Courier", "exped.INGI12178247 azi", "Multumim.Echipa Tursib"):
            self.assertEqual(list(extract_url_spans(text)), [], text)
        for text, url in (("vezi Emag.ro", "Emag.ro"), ("WWW.BCR.RO", "WWW.BCR.RO"), ("pe anaf.ro azi", "anaf.ro"),
                          ("x www.Bcr.Ro y", "www.Bcr.Ro"), ("salt.bank", "salt.bank"), ("bcr[.]ro", "bcr[.]ro")):
            self.assertEqual([u for u, _, _ in extract_url_spans(text)], [url], text)

    def test_third_party_hosts_and_service_terms(self):
        plain = analyze_single_url("https://emag.page.link/x")
        dressed = analyze_single_url("https://bcr.secure-login.com/x")
        self.assertEqual((plain["risk_points"], dressed["risk_points"]), (15, 30))
        self.assertFalse(dressed["typosquatting"]["is_typosquatting"])

    def test_shared_platform_tenants(self):
        exact = analyze_single_url("https://emag.web.app/x")["typosquatting"]
        dressed = analyze_single_url("https://digi-ro.web.app/plata")["typosquatting"]
        self.assertTrue(exact["brand_on_third_party"])
        self.assertTrue(dressed["is_typosquatting"])

    def test_deceptive_structures_are_preserved(self):
        for url in ("https://bcr.ro.login-check.example", "https://olx.ro-livrare.com/p", "https://bcr-verificare.top",
                    "https://xn--bcr-verific-k6a.top", "https://bcrr.ro"):
            with self.subTest(url):
                report = analyze_single_url(url)
                if report["typosquatting"].get("target"):
                    self.assertTrue(report["typosquatting"]["is_typosquatting"])
        self.assertGreaterEqual(analyze_single_url("https://www.bcr.ro@unrelated.example/p")["risk_points"], 35)
        self.assertTrue(analyze_single_url("https://x.test/a#https://dosare.alun-medical.example/i")["embedded_destination_hint"])


class Validation(unittest.TestCase):
    def test_negation_left_of_quote(self):
        text = "Nu trimite parola nimanui."
        out = semantic_gemini.validate(json.dumps(M("likely_scam", reqs=[
            R("share_password", "p", "secret_credential", "trimite parola nimanui")])), text)
        self.assertEqual(out["requests"][0]["consistency"], "negation_conflict")
        text = "Nu uita să îmi trimiți codul din SMS."
        out = semantic_gemini.validate(json.dumps(M("likely_scam", reqs=[
            R("share_otp_or_code", "c", "secret_credential", "să îmi trimiți codul din SMS")])), text)
        self.assertEqual(out["requests"][0]["consistency"], "consistent")  # case 24 stays a request

    def test_supplied_value_and_destination_grounding(self):
        text = "Codul tau Glovo este 5521. Detalii: https://glovoapp.com/x"
        out = semantic_gemini.validate(json.dumps(M("ordinary_or_legitimate", reqs=[
            R("share_otp_or_code", "c", "secret_credential", "Codul tau Glovo este 5521", dest="https://glovoapp.com/x"),
            R("click_link", "l", "low", "Detalii", dest="https://nu-exista.example")])), text)
        self.assertEqual(out["requests"][0]["consistency"], "supplied_value")
        self.assertEqual(out["requests"][0]["destination_status"], "grounded")
        self.assertEqual(out["requests"][1]["destination_status"], "ungrounded")

    def test_older_recordings_without_new_fields_still_validate(self):
        item = {"action": "share_password", "object": "p", "sensitivity": "secret_credential", "recipient": None,
                "stance": "requested", "quote": "Trimite parola"}
        out = semantic_gemini.validate(json.dumps(M("likely_scam", reqs=[item])), "Trimite parola.")
        self.assertEqual(out["requests"][0]["handover"], "unclear")


class ProviderContract(unittest.TestCase):
    ALLOWED = {"type", "enum", "nullable", "properties", "required", "items"}

    def walk(self, node, path="$"):
        if isinstance(node, dict):
            if "type" in node:
                self.assertLessEqual(set(node) - {"type"}, self.ALLOWED, path)
            for key, value in node.items():
                if key == "properties":
                    for name, child in value.items():
                        self.walk(child, f"{path}.{name}")
                elif isinstance(value, (dict, list)):
                    self.walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for child in node:
                self.walk(child, path)

    def test_schema_uses_only_supported_keywords(self):
        self.walk(semantic_gemini.RESPONSE_SCHEMA)
        self.assertNotIn("maxItems", json.dumps(semantic_gemini.RESPONSE_SCHEMA))
        request = semantic_gemini.RESPONSE_SCHEMA["properties"]["requests"]["items"]
        self.assertIn("handover", request["required"])
        self.assertIn("sign_in", request["properties"]["action"]["enum"])

    def test_request_body_and_settings_unchanged(self):
        captured = {}

        def post(url, body, key, timeout):
            captured.update(json.loads(body), url=url)
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        gemini_client.generate_json("k", [{"text": "x"}], "sys", semantic_gemini.RESPONSE_SCHEMA, post=post)
        config = captured["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["temperature"], 0.1)
        self.assertTrue(captured["url"].endswith(":generateContent"))


class Presentation(Base):
    def test_simulator_never_presents_an_official_domain_as_the_trap(self):
        r = self.run_ai("Detalii pe https://www.bcr.ro. Trimite-mi codul primit prin SMS.", M(
            "likely_scam", "otp_or_authentication_theft", reqs=[
                R("share_otp_or_code", "cod", "secret_credential", "Trimite-mi codul primit prin SMS")]))
        scenario = r["analysis"]["scenario"]
        self.assertNotIn("bcr.ro", json.dumps(scenario, ensure_ascii=False))
        self.assertNotIn("adresă din mesaj", json.dumps(scenario, ensure_ascii=False))

    def test_benign_result_shows_no_scam_stages_and_cues_as_notes(self):
        r = self.run_ai(SEVEN["E-orange-promo-2"], ReportedFalsePositives.readings(None)["E-orange-promo-2"])
        a = r["analysis"]
        self.assertFalse(any(stage["on"] for stage in a["stages"]))
        self.assertTrue(a["reasons"] and all(x["level"] in {"info", "protective"} for x in a["reasons"]))

    def test_database_outage_does_not_flip_the_verdict(self):
        text = "BCR: Afla noutatile pe pagina noastra: https://www.facebook.com/bcr"
        reading = M("ordinary_or_legitimate", sender="BCR", stype="bank", reqs=[R("click_link", "pagina", "low", "Afla noutatile")])
        up = self.assess(text, reading)
        os.environ["AXA_SQLITE_PATH"] = "/nonexistent/axa.sqlite3"
        down = self.run_ai(text, reading)["analysis"]
        self.assertEqual(down["checks"]["database"], "unavailable_static_fallback")
        self.assertEqual(up["label"], down["assessment"]["label"])

    def test_rules_never_override_the_structured_reading(self):
        """RH-039-like: lexical rules see a credential request; Gemini reads an own password change."""
        text = "Din profil deschizi Schimba parola, completezi parola veche si pe cea noua in casetele din cont."
        a = self.assess(text, M("suspicious", "credential_phishing", reqs=[
            R("sign_in", "parola", "secret_credential", "completezi parola veche si pe cea noua in casetele din cont", handover=KEEP)]))
        self.assertNotEqual(a["label"], "critical")


if __name__ == "__main__":
    unittest.main()
