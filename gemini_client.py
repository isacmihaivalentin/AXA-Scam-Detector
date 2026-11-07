"""Minimal Gemini REST client (standard library only).

Only the fixed generativelanguage.googleapis.com endpoint is contacted, with the
API key in a header, no redirects, bounded response size, explicit timeout and
bounded retries. Errors are reduced to a category so provider payloads (which
may echo submitted text) never reach the logs.
"""
import json
import os
import random
import time
from threading import BoundedSemaphore
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
MAX_RESPONSE_BYTES = 512 * 1024
RETRYABLE = {429, 500, 503, 504}


def _int_env(name, default, low, high):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        value = default
    return min(high, max(low, value))


def model_id():
    model = os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    # Model IDs are path segments; refuse anything that could alter the URL.
    if not all(c.isalnum() or c in "-._" for c in model):
        raise ProviderError("invalid_request", "invalid model id")
    return model


def timeout_s():
    return _int_env("AXA_GEMINI_TIMEOUT_MS", 20000, 3000, 60000) / 1000


def max_attempts():
    return 1 + _int_env("AXA_GEMINI_RETRIES", 1, 0, 2)


SLOTS = BoundedSemaphore(_int_env("AXA_GEMINI_CONCURRENCY", 4, 1, 16))


class ProviderError(Exception):
    """kind is one of: not_configured, busy, invalid_request, authentication_or_access,
    model_unavailable, rate_limited, timeout, provider_unavailable, invalid_output, blocked."""

    def __init__(self, kind, detail=""):
        super().__init__(kind)
        self.kind = kind
        self.detail = detail


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _kind_for_status(code):
    if code == 400:
        return "invalid_request"
    if code in {401, 403}:
        return "authentication_or_access"
    if code == 404:
        return "model_unavailable"
    if code == 429:
        return "rate_limited"
    if code in {408, 504}:
        return "timeout"
    return "provider_unavailable"


def _post(url, body, api_key, timeout):
    request = Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "x-goog-api-key": api_key, "Accept": "application/json",
    })
    opener = build_opener(_NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ProviderError("invalid_output", "oversize response")
    return json.loads(payload)


def extract_text(payload):
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not candidates:
        reason = (payload or {}).get("promptFeedback", {}).get("blockReason") if isinstance(payload, dict) else None
        raise ProviderError("blocked" if reason else "invalid_output", "no candidates")
    first = candidates[0] or {}
    if first.get("finishReason") in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"}:
        raise ProviderError("blocked", "candidate blocked")
    parts = (first.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict) and not part.get("thought"))
    if not text.strip():
        raise ProviderError("invalid_output", "empty response")
    return text


def generate_json(api_key, parts, system_instruction, schema, *, max_tokens=4096, timeout=None,
                  attempts=None, temperature=0.1, post=_post, sleep=time.sleep):
    """Return the model's JSON text. Raises ProviderError with a category."""
    if not api_key:
        raise ProviderError("not_configured")
    timeout = timeout or timeout_s()
    attempts = attempts or max_attempts()
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json", "responseSchema": schema,
            "maxOutputTokens": max_tokens, "temperature": temperature,
        },
    }, ensure_ascii=False).encode("utf-8")
    url = API_ROOT + quote(model_id(), safe="") + ":generateContent"
    if not SLOTS.acquire(timeout=min(10, timeout)):
        raise ProviderError("busy")
    try:
        deadline = time.monotonic() + timeout
        last = ProviderError("provider_unavailable")
        for attempt in range(attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 0.5:
                raise ProviderError("timeout")
            try:
                return extract_text(post(url, body, api_key, remaining))
            except HTTPError as error:
                last = ProviderError(_kind_for_status(error.code), f"http {error.code}")
                retry = error.code in RETRYABLE
            except TimeoutError:
                last, retry = ProviderError("timeout"), True
            except URLError as error:
                timed_out = isinstance(getattr(error, "reason", None), TimeoutError)
                last, retry = ProviderError("timeout" if timed_out else "provider_unavailable"), True
            except (ValueError, json.JSONDecodeError):
                last, retry = ProviderError("invalid_output"), False
            except OSError:
                last, retry = ProviderError("provider_unavailable"), True
            if not retry or attempt + 1 >= attempts:
                break
            sleep(min(1.5, 0.4 * (2 ** attempt) + random.random() * 0.2))
        raise last
    finally:
        SLOTS.release()
