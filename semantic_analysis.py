"""Optional offline multilingual NLI and the shared, grounded observation schema."""
import argparse
import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
MODEL_REVISION = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"
MODEL_FILES = (
    "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
    "special_tokens_map.json", "added_tokens.json", "spm.model",
)
MAX_CLAUSES = 6
MAX_TOKENS = 256
MAX_MODEL_CHARS = 2400
MIN_ENTAILMENT = 0.82
AMBIGUOUS_ENTAILMENT = 0.55
ROMANIAN_COMMA = str.maketrans("ŞşŢţ", "ȘșȚț")
LOG = logging.getLogger("axa")

Intent = Literal[
    "request_money", "request_credentials", "request_sensitive_documents", "request_card_photo",
    "promise_payout", "advance_fee_condition", "family_impersonation", "organization_impersonation_claim",
    "account_verification_request", "request_login_approval", "request_remote_access",
    "urgency_or_pressure", "protective_warning", "educational_example",
    "commercial_solicitation", "reward_offer", "unavailable_for_call", "unknown",
]
Source = Literal["rules", "local_nli", "gemini"]
Span = tuple[int, int]
INTENTS = get_args(Intent)

HYPOTHESES = {
    "request_money": "Expeditorul îi cere destinatarului să trimită bani sau să facă o plată.",
    "request_credentials": "Destinatarul trebuie să îi dezvăluie expeditorului datele de autentificare.",
    "request_sensitive_documents": "Expeditorul cere să i se trimită o copie a unui act personal de identitate.",
    "request_card_photo": "Expeditorul cere o fotografie sau o captură cu informațiile de pe cardul bancar al destinatarului.",
    "promise_payout": "Mesajul îi promite destinatarului că va primi bani.",
    "advance_fee_condition": "Destinatarul trebuie să transfere bani sau un obiect de valoare înainte de a primi un beneficiu promis.",
    "family_impersonation": "Expeditorul pretinde că este o rudă care scrie de la un număr nou.",
    "organization_impersonation_claim": "Expeditorul se prezintă ca reprezentantul unei firme sau instituții.",
    "account_verification_request": "Expeditorul cere destinatarului să verifice activitatea contului sau să își confirme contul.",
    "request_login_approval": "Expeditorul cere destinatarului să aprobe o autentificare în cont.",
    "urgency_or_pressure": "Expeditorul cere destinatarului să acționeze urgent sau într-un termen scurt.",
    "protective_warning": "Expeditorul îi spune destinatarului să nu divulge parole, coduri secrete sau date bancare.",
    "educational_example": "Textul prezintă un exemplu de fraudă cu scop ilustrativ sau educativ.",
    "commercial_solicitation": "Expeditorul face reclamă unui produs sau serviciu și cere destinatarului să îl cumpere.",
    "reward_offer": "Expeditorul îi oferă destinatarului un cadou gratuit sau o recompensă.",
    "unavailable_for_call": "Expeditorul spune că nu poate vorbi la telefon.",
}
OTP_HYPOTHESIS = "Destinatarul este rugat să îi spună expeditorului codul de verificare primit prin SMS."
OTP_CONTEXT = re.compile(r"\b(?:otp|sms|cod\w*|cifr\w*)\b", re.IGNORECASE)
CLAUSE_INTENTS = (
    "request_money", "request_credentials", "request_sensitive_documents", "request_card_photo",
    "account_verification_request", "protective_warning", "educational_example",
)
FIELDS = {
    "request_money": ("pay", "money", "requested"),
    "request_credentials": ("disclose", "credentials", "requested"),
    "request_sensitive_documents": ("upload", "identity_document", "requested"),
    "request_card_photo": ("upload_photo", "card_information", "requested"),
    "promise_payout": ("receive", "money", "promised"),
    "advance_fee_condition": ("pay", "money", "conditional"),
    "family_impersonation": ("claim", "family_identity_and_new_number", "claimed"),
    "organization_impersonation_claim": ("claim", "organization_identity", "claimed"),
    "account_verification_request": ("verify", "account", "requested"),
    "request_login_approval": ("authorize", "login_approval", "requested"),
    "request_remote_access": ("grant_access", "device_access", "requested"),
    "urgency_or_pressure": ("act_quickly", None, "requested"),
    "protective_warning": ("avoid_disclosure", "sensitive_information", "discouraged"),
    "educational_example": ("report", "scam_example", "reported"),
    "commercial_solicitation": ("purchase", "product_or_service", "requested"),
    "reward_offer": ("receive", "reward", "promised"),
    "unavailable_for_call": ("avoid_call", "sender_contact", "claimed"),
    "unknown": (None, None, "unclear"),
}


class ModelStrength(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    entailment: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)
    contradiction: float = Field(ge=0, le=1)


class Observation(BaseModel):
    """Internally uses Python code-point offsets. The JSON API exposes UTF-16 offsets."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: Intent
    source: Source
    scope: Literal["whole_message", "clause", "exact_quote", "rule_span"]
    evidence_text: str = Field(min_length=1, max_length=2400)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    direction: Literal["requested", "discouraged", "reported", "claimed", "promised", "conditional", "unclear"]
    action: str | None = None
    object: str | None = None
    claimed_identity: str | None = None
    promise: Literal["payout", "reward"] | None = None
    condition: Literal["payment_before_payout"] | None = None
    pressure: Literal["time_pressure", "cannot_call"] | None = None
    model_strength: ModelStrength | None = None
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_span(self):
        if self.end - self.start != len(self.evidence_text):
            raise ValueError("evidence length does not match its span")
        return self

    def public(self, original):
        item = self.model_dump(mode="json")
        item.update(start=utf16_offset(original, self.start), end=utf16_offset(original, self.end))
        return item


def utf16_offset(text, offset):
    return len(text[:offset].encode("utf-16-le")) // 2


def trimmed_span(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def observe(text, label, source, span, scope, *, strength=None, identity=None):
    start, end = trimmed_span(text, *span)
    action, target, direction = FIELDS[label]
    return Observation(
        label=label, source=source, scope=scope, evidence_text=text[start:end], start=start, end=end,
        direction=direction, action=action, object=target, claimed_identity=identity,
        promise={"promise_payout": "payout", "reward_offer": "reward"}.get(label),
        condition="payment_before_payout" if label == "advance_fee_condition" else None,
        pressure={"urgency_or_pressure": "time_pressure", "unavailable_for_call": "cannot_call"}.get(label),
        model_strength=strength,
        limitations=("inferred_intent", "whole_message_scope") if scope == "whole_message"
        else ("inferred_intent",) if source != "rules" else (),
    )


def normalized_model_text(original, span, url_spans):
    start, end = span
    chunks, position = [], start
    for left, right in url_spans:
        if right <= position:
            continue
        if left >= end:
            break
        chunks.extend((original[position:max(position, left)], " [link] "))
        position = min(right, end)
    chunks.append(original[position:end])
    return unicodedata.normalize("NFC", "".join(chunks)).translate(ROMANIAN_COMMA)


@dataclass(frozen=True)
class LocalResult:
    status: str
    observations: tuple[Observation, ...] = ()
    ambiguous: tuple[str, ...] = ()
    elapsed_ms: float | None = None
    clauses_examined: int = 0
    tentative: tuple[Observation, ...] = ()
    coverage_limits: tuple[str, ...] = ()


def model_dir():
    configured = os.environ.get("AXA_MODEL_DIR", "").strip()
    return Path(configured).expanduser() if configured else Path(__file__).with_name(".models") / "mdeberta"


class NLIRunner:
    def __init__(self, path):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.set_num_threads(4)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True, trust_remote_code=False, use_safetensors=True,
        ).to("cpu").eval()
        ids = {key.casefold(): value for key, value in self.model.config.label2id.items()}
        self.label_ids = [ids[name] for name in ("entailment", "neutral", "contradiction")]

    def classify(self, texts, labels, *, add_otp_hypothesis=False):
        # Independent NLI per hypothesis, like zero-shot multi-label classification,
        # while retaining neutral rather than normalizing it out.
        pairs = [(index, premise, label, HYPOTHESES[label]) for index, premise in enumerate(texts) for label in labels]
        if add_otp_hypothesis:
            pairs.extend((index, premise, "request_credentials", OTP_HYPOTHESIS)
                         for index, premise in enumerate(texts) if OTP_CONTEXT.search(premise))
        predictions = []
        for offset in range(0, len(pairs), 16):
            batch = pairs[offset:offset + 16]
            inputs = self.tokenizer(
                [premise for _, premise, _, _ in batch], [hypothesis for _, _, _, hypothesis in batch],
                padding=True, truncation="only_first", max_length=MAX_TOKENS, return_tensors="pt",
            )
            with self.torch.inference_mode():
                values = self.model(**inputs).logits.softmax(dim=-1)[:, self.label_ids].tolist()
            predictions.extend((index, label, ModelStrength(entailment=e, neutral=n, contradiction=c))
                               for (index, _, label, _), (e, n, c) in zip(batch, values))
        strongest = {}
        for index, label, strength in predictions:
            key = index, label
            if key not in strongest or strength.entailment > strongest[key].entailment:
                strongest[key] = strength
        return [(index, label, strength) for (index, label), strength in strongest.items()]

    def analyze(self, original, spans, url_spans):
        started = perf_counter()
        full_span = trimmed_span(original, 0, min(len(original), MAX_MODEL_CHARS))
        whole = normalized_model_text(original, full_span, url_spans)
        if not re.search(r"[^\W\d_]", whole.replace("[link]", "")):
            return LocalResult("not_applicable")
        clauses = [(span, normalized_model_text(original, span, url_spans)) for span in spans if span[1] - span[0] <= 650]
        clauses = [(span, text) for span, text in clauses if re.search(r"[^\W\d_]", text.replace("[link]", ""))]
        selected = [(span, text) for span, text in clauses[:MAX_CLAUSES]
                    if len(self.tokenizer(text, add_special_tokens=False, verbose=False)["input_ids"]) <= MAX_TOKENS - 48]
        token_count = len(self.tokenizer(whole, add_special_tokens=False, verbose=False)["input_ids"])
        whole_complete = len(original) <= MAX_MODEL_CHARS and token_count <= MAX_TOKENS - 48
        partial = (not whole_complete or len(selected) < len(clauses)
                   or any(end - start > 650 for start, end in spans))

        observations, ambiguous, tentative = [], set(), []

        def record(label, strength, span, scope):
            if strength.entailment >= MIN_ENTAILMENT:
                observations.append(observe(original, label, "local_nli", span, scope, strength=strength))
            elif strength.entailment >= AMBIGUOUS_ENTAILMENT:
                ambiguous.add(label)
                tentative.append(observe(original, label, "local_nli", span, scope, strength=strength))

        identical_clause = whole_complete and len(selected) == 1 and selected[0][0] == full_span
        if not identical_clause:
            for index, label, strength in self.classify([text for _, text in selected], CLAUSE_INTENTS, add_otp_hypothesis=True):
                record(label, strength, selected[index][0], "clause")
        if whole_complete:
            for _, label, strength in self.classify([whole], HYPOTHESES, add_otp_hypothesis=identical_clause):
                scope = "clause" if identical_clause and label in CLAUSE_INTENTS else "whole_message"
                record(label, strength, full_span, scope)
        limits = tuple(name for active, name in (
            (not whole_complete, "whole_message_limit"),
            (len(selected) < len(clauses) or any(end - start > 650 for start, end in spans), "clause_limit"),
        ) if active)
        tentative.sort(key=lambda item: item.model_strength.entailment, reverse=True)
        return LocalResult("partial" if partial else "completed", tuple(observations), tuple(sorted(ambiguous)),
                           round((perf_counter() - started) * 1000, 1), len(selected), tuple(tentative), limits)


class LocalSemanticModel:
    """One model, one running job. Busy requests fall back instead of queuing."""
    def __init__(self, timeout=8.0):
        self.timeout = timeout
        self.slot = Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="axa-nli")
        self.runner = None
        self.load_failure = None

    def _run(self, path, original, spans, url_spans):
        if self.load_failure:
            return LocalResult(self.load_failure)
        if self.runner is None:
            try:
                self.runner = NLIRunner(path)
            except Exception as error:
                self.load_failure = "dependency_missing" if isinstance(error, ImportError) else "load_failed"
                LOG.warning("Local NLI initialization failed (%s)", type(error).__name__)
                return LocalResult(self.load_failure)
        try:
            return self.runner.analyze(original, spans, url_spans)
        except Exception as error:
            LOG.warning("Local NLI inference failed (%s)", type(error).__name__)
            return LocalResult("inference_failed")

    def analyze(self, original, spans, url_spans):
        # Opt-in since 2.0: the Gemini-first app must not need local weights.
        if os.environ.get("AXA_LOCAL_MODEL", "0").lower() not in {"1", "on", "true"}:
            return LocalResult("disabled")
        path = model_dir()
        if not all((path / name).is_file() for name in ("model.safetensors", "config.json", "tokenizer.json")):
            return LocalResult("model_missing")
        premise = normalized_model_text(original, (0, min(len(original), MAX_MODEL_CHARS)), url_spans)
        if not re.search(r"[^\W\d_]", premise.replace("[link]", "")):
            return LocalResult("not_applicable")
        if not self.slot.acquire(blocking=False):
            return LocalResult("busy")
        try:
            job = self.executor.submit(self._run, path, original, spans, url_spans)
        except RuntimeError:
            self.slot.release()
            return LocalResult("inference_failed")
        job.add_done_callback(lambda _: self.slot.release())
        try:
            return job.result(timeout=self.timeout)
        except TimeoutError:
            return LocalResult("timeout")


local_model = LocalSemanticModel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare the pinned offline AXA model before the demo.")
    parser.add_argument("--prepare", action="store_true", required=True)
    args = parser.parse_args()
    from huggingface_hub import snapshot_download

    location = snapshot_download(
        MODEL_ID, revision=MODEL_REVISION, allow_patterns=MODEL_FILES, local_dir=model_dir(), token=False,
    )
    print(f"Model available at {location}")
