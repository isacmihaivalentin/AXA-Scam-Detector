"""Optional passive Google Cloud Web Risk lookup. Submitted hosts are data only."""
import ipaddress
import json
import os
from datetime import datetime, timezone
from threading import BoundedSemaphore
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ENDPOINT = "https://webrisk.googleapis.com/v1/uris:search"
PROVIDER = "google_web_risk"
THREAT_TYPES = ("SOCIAL_ENGINEERING", "MALWARE", "UNWANTED_SOFTWARE")
LOOKUP_LIMIT = 2
SLOTS = BoundedSemaphore(2)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider_response(request):
    # Credentials and submitted text never leave the fixed provider via redirects.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=2.5) as response:
        payload = response.read(16_385)
    if len(payload) > 16_384:
        raise ValueError("oversize provider response")
    return json.loads(payload)


def eligible_uri(report):
    scheme, host = report["protocol"], report["domain"]
    if (report["inspection_status"] != "passive_only" or report["protocol_source"] != "explicit"
            or scheme not in {"https", "http"} or not host or report["defanged"]
            or report["registered_domain_basis"] != "public_suffix_list"
            or report["userinfo_present"] or report["query_present"] or report["fragment_present"]
            or report["port"] not in {None, 80 if scheme == "http" else 443}
            or host in {"example.com", "example.org", "example.net"}
            or report["registrable_domain"] in {"example.com", "example.org", "example.net"}):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        path = quote(report["path"] or "/", safe="/:@!$&'()*+,;=-._~%")
        authority = f"{host}:{report['port']}" if report["port"] else host
        return urlunsplit((scheme, authority, path, "", ""))


def lookup(uri, api_key):
    data = {"provider": PROVIDER, "status": "provider_unavailable"}
    if not SLOTS.acquire(blocking=False):
        return {**data, "status": "not_checked", "reason": "provider_busy"}
    try:
        params = [("uri", uri), *(("threatTypes", item) for item in THREAT_TYPES)]
        request = Request(ENDPOINT + "?" + urlencode(params), headers={
            "X-Goog-Api-Key": api_key, "Accept": "application/json",
        })
        result = provider_response(request)
        checked = datetime.now(timezone.utc)
        if result == {}:
            return {**data, "status": "no_known_match", "checked_at": checked.isoformat()}
        threat = result.get("threat") if isinstance(result, dict) else None
        if not isinstance(threat, dict):
            raise ValueError("invalid provider response")
        types = threat.get("threatTypes")
        if not isinstance(types, list) or not types or any(item not in THREAT_TYPES for item in types):
            raise ValueError("invalid threat types")
        expiration = datetime.fromisoformat(threat["expireTime"].replace("Z", "+00:00"))
        if expiration <= checked:
            raise ValueError("expired result")
        return {**data, "status": "threat_match", "types": sorted(set(types)),
                "checked_at": checked.isoformat(), "expires_at": expiration.isoformat()}
    except HTTPError as error:
        return {**data, "status": "rate_limited" if error.code == 429 else
                "invalid_or_unsupported" if error.code == 400 else "provider_unavailable"}
    except (URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError):
        return data
    finally:
        SLOTS.release()


def add_reputation(reports):
    api_key = os.environ.get("AXA_WEB_RISK_API_KEY", "").strip()
    cache = {}  # Only per request. No submitted URLs or responses are stored.
    for report in reports:
        status = {"provider": PROVIDER, "status": "not_configured"}
        if api_key:
            uri = eligible_uri(report)
            if not uri:
                status = {**status, "status": "invalid_or_unsupported", "reason": "lookup_scope_or_privacy"}
            elif uri in cache:
                status = cache[uri]
            elif len(cache) >= LOOKUP_LIMIT:
                status = {**status, "status": "not_checked", "reason": "lookup_limit"}
            else:
                status = cache[uri] = lookup(uri, api_key)
        report["reputation"] = status
    statuses = {report["reputation"]["status"] for report in reports}
    if not statuses:
        return "not_checked"
    if len(statuses) == 1:
        return next(iter(statuses))
    return "threat_match" if "threat_match" in statuses else "partial"
