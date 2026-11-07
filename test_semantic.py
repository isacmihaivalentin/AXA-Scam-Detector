"""Focused tests for the optional model, exact evidence and mechanism fusion."""
import os
import tempfile
import unittest
import unicodedata
from pathlib import Path
from threading import Event
from unittest.mock import patch

import engine
from semantic_analysis import LocalResult, LocalSemanticModel, observe


class FusionTests(unittest.TestCase):
    def analyze(self, text, observations=(), status="completed"):
        with patch.object(engine.local_model, "analyze", return_value=LocalResult(status, tuple(observations))):
            return engine.rules_analysis(text)

    def test_inferred_card_request_can_add_risk_with_exact_clause(self):
        text = "Salut! 📷 O imagine cu spatele cardului este necesară pentru a continua."
        start = text.index("📷")
        observation = observe(text, "request_card_photo", "local_nli", (start, len(text)), "clause")
        analysis = self.analyze(text, [observation])
        self.assertEqual(analysis["risk_label"], "suspicious")
        self.assertEqual(analysis["highlights"], [])
        evidence = next(item for item in analysis["semantic_evidence"] if item["source"] == "local_nli")
        raw = text.encode("utf-16-le")[evidence["start"] * 2:evidence["end"] * 2]
        self.assertEqual(raw.decode("utf-16-le"), text[start:])

    def test_protective_scope_outweighs_inferred_request(self):
        text = "Nu încărca o poză cu datele cardului, nici măcar la cerere."
        item = observe(text, "request_card_photo", "local_nli", (0, len(text)), "clause")
        analysis = self.analyze(text, [item])
        self.assertEqual(analysis["risk_score"], 0)
        self.assertEqual(analysis["checks"]["rule_model_agreement"], "disagreement")

    def test_wrong_advance_fee_model_signal_without_dependency_is_bounded(self):
        text = "Factură de internet emisă. Achitați soldul de 80 lei prin aplicația furnizorului."
        items = [observe(text, label, "local_nli", (0, len(text)), "whole_message")
                 for label in ("request_money", "advance_fee_condition", "promise_payout")]
        analysis = self.analyze(text, items)
        self.assertLess(analysis["risk_score"], 35)
        self.assertNotIn("advance_fee", [m["id"] for m in analysis["assessment"]["mechanisms"]])

    def test_reported_request_inside_warning_is_not_active(self):
        text = "Nu publica poza cu datele cardului, chiar daca ti se solicita PIN-ul."
        self.assertEqual(self.analyze(text)["risk_score"], 0)

    def test_model_cannot_turn_a_publication_into_a_document_request(self):
        text = "Buletin informativ de securitate."
        item = observe(text, "request_sensitive_documents", "local_nli", (0, len(text)), "clause")
        self.assertEqual(self.analyze(text, [item])["risk_score"], 0)

    def test_an_off_brand_url_must_be_linked_to_the_same_claim_and_action(self):
        standalone = self.analyze("https://bcr.ro.login-check.example")
        connected = self.analyze("BCR: Verificați activitatea contului. Accesați https://bcr.ro.login-check.example pentru validare.")
        unrelated = self.analyze("ING: Verificați activitatea contului. Accesați https://bcr.ro.login-check.example pentru validare.")
        self.assertEqual(standalone["risk_score"], 45)
        self.assertGreaterEqual(connected["risk_score"], 70)
        self.assertEqual(unrelated["score_breakdown"]["linked_identity_action"], 0)

    def test_decomposed_romanian_and_original_unicode_offsets(self):
        text = "  🛡️ " + unicodedata.normalize("NFD", "Vă rugăm să atașați o poză cu datele cardului.") + "  "
        with patch.object(engine.local_model, "analyze", return_value=LocalResult("disabled")):
            payload = engine.analyze_text(text, "")
        self.assertEqual(payload["text"], text)
        self.assertEqual(payload["analysis"]["risk_label"], "critical")
        item = payload["analysis"]["highlights"][0]
        raw = text.encode("utf-16-le")[item["start"] * 2:item["end"] * 2]
        self.assertEqual(raw.decode("utf-16-le"), item["text"])
        self.assertIn("s\u0326", item["text"])


class WorkerTests(unittest.TestCase):
    def create_worker(self, timeout):
        path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for name in ("model.safetensors", "config.json", "tokenizer.json"):
            (path / name).touch()
        self.enterContext(patch.dict(os.environ, {"AXA_LOCAL_MODEL": "1", "AXA_MODEL_DIR": str(path)}))
        worker = LocalSemanticModel(timeout=timeout)
        self.addCleanup(worker.executor.shutdown)
        return worker

    def test_load_once_and_missing_dependency_fallback(self):
        worker = self.create_worker(1)
        with patch("semantic_analysis.NLIRunner") as factory:
            factory.return_value.analyze.return_value = LocalResult("completed")
            for _ in range(2):
                self.assertEqual(worker.analyze("Un mesaj.", ((0, 9),), ()).status, "completed")
            factory.assert_called_once()
        worker = self.create_worker(1)
        with patch("semantic_analysis.NLIRunner", side_effect=ModuleNotFoundError) as factory:
            for _ in range(2):
                self.assertEqual(worker.analyze("Un mesaj.", ((0, 9),), ()).status, "dependency_missing")
            factory.assert_called_once()

    def test_model_timeout_does_not_queue_more_work(self):
        worker = self.create_worker(0.04)
        release = Event()
        self.addCleanup(release.set)
        with patch("semantic_analysis.NLIRunner") as factory:
            factory.return_value.analyze.side_effect = lambda *_: release.wait(2)
            self.assertEqual(worker.analyze("Mesaj.", ((0, 6),), ()).status, "timeout")
            self.assertEqual(worker.analyze("Alt mesaj.", ((0, 10),), ()).status, "busy")

    def test_missing_weights_and_inference_error(self):
        with patch.dict(os.environ, {"AXA_LOCAL_MODEL": "1", "AXA_MODEL_DIR": "/no-model-here"}):
            self.assertEqual(engine.local_model.analyze("Mesaj.", ((0, 6),), ()).status, "model_missing")
        worker = self.create_worker(1)
        with patch("semantic_analysis.NLIRunner") as factory:
            factory.return_value.analyze.side_effect = RuntimeError
            self.assertEqual(worker.analyze("Mesaj.", ((0, 6),), ()).status, "inference_failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
