"""Static address parsing and bounded catalog matching. No submitted-host I/O."""
import ipaddress
import re
import unicodedata
from urllib.parse import unquote, urlsplit

import idna

from database import STATIC_CATALOG, brand_key
from psl import PSL

MAX_URLS = 10
MAX_URL_LENGTH = 4096
RESERVED_SUFFIXES = {"example", "test", "invalid"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "rb.gy", "is.gd", "cutt.ly", "shorturl.at", "tiny.cc"}
NON_WEB_SCHEME = r"(?:javascript|data|mailto|tel|file):"
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://|" + NON_WEB_SCHEME, re.IGNORECASE)
DOT = r"(?:[.。．｡]|\[\.\]|\(\.\)|\[dot\])"
TEXTUAL_DOT = re.compile(r"\[\.\]|\(\.\)|\[dot\]", re.IGNORECASE)
URL_PATTERN = re.compile(
    r"(?<![\w@./-])(?:(?:[a-z][a-z0-9+.-]*://|//|" + NON_WEB_SCHEME + r")[^\s<>\"'„”«»]*"
    r"|(?:[\w-]+"
    + DOT + r")+[^\W\d_][\w-]*(?::\d+)?(?:[/?#][^\s<>\"'„”«»]*)?(?![\w@-]))",
    re.IGNORECASE,
)
LEET = str.maketrans("013458", "oleasb")
CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "в": "b",
    "і": "i", "ј": "j", "ѕ": "s", "у": "y", "ӏ": "l", "ԁ": "d", "һ": "h", "м": "m",
    "α": "a", "ο": "o", "ρ": "p", "χ": "x", "ι": "i", "κ": "k", "ν": "v",
})
SERVICE_TOKENS = {
    "account", "auth", "billing", "care", "client", "clients", "confirm", "cont", "help",
    "login", "online", "pay", "payment", "plata", "profile", "secure", "security", "service",
    "signin", "support", "update", "verify", "verification", "verificare", "web",
}
PATH_LINK = re.compile(r"(?:https?://|(?://)(?:[\w-]+\.)+[\w-]+)", re.IGNORECASE)


def sentence_boundary(url):
    """A scheme-less "word.Word" is a missing space after a full stop ("livrarii.FAN Courier",
    "exped.INGI1217"), not a hostname: the label after the last dot switches from lower to upper
    case. Real bare hostnames keep one case ("emag.ro", "WWW.BCR.RO") or carry "www."/a path."""
    if SCHEME.match(url) or url.startswith("//") or url.casefold().startswith("www.") or re.search(r"[/?#]", url):
        return False
    labels = re.split(r"[.。．｡]", url.split(":")[0])
    return len(labels) >= 2 and labels[-1][:1].isupper() and labels[-2][-1:].islower()


def extract_url_spans(text):
    for match in URL_PATTERN.finditer(text):
        url = match.group().rstrip(".,;:!?…")
        for close, opening in ((")", "("), ("]", "["), ("}", "{")):
            while url.endswith(close) and url.count(close) > url.count(opening):
                url = url[:-1]
        url = url.rstrip(".,;:!?…")
        if url and not sentence_boundary(url):
            yield url, match.start(), match.start() + len(url)


def extract_urls(text):
    return list(dict.fromkeys(url for url, _, _ in extract_url_spans(text)))[:MAX_URLS]


def normalize_hostname(hostname):
    try:
        return idna.encode(hostname, uts46=True, std3_rules=True).decode("ascii").removesuffix(".")
    except (UnicodeError, ValueError):
        return ""


def domain_parts(hostname):
    parts = PSL(hostname)
    labels = hostname.split(".")
    if parts.suffix:
        return parts.domain, parts.suffix, parts.top_domain_under_public_suffix
    return (labels[-2] if len(labels) > 1 else ""), labels[-1], ".".join(labels[-2:])


def damerau_distance(left, right):
    """Optimal string alignment distance, including one adjacent swap."""
    before = None
    row = list(range(len(right) + 1))
    for i, char in enumerate(left, 1):
        current = [i]
        for j, other in enumerate(right, 1):
            distance = min(row[j] + 1, current[j - 1] + 1, row[j - 1] + (char != other))
            if before is not None and j > 1 and char == right[j - 2] and left[i - 2] == other:
                distance = min(distance, before[j - 2] + 1)
            current.append(distance)
        before, row = row, current
    return row[-1]


def skeleton(label):
    if label.startswith("xn--"):
        label = idna.decode(label)
    folded = unicodedata.normalize("NFKD", label.casefold()).translate(CONFUSABLES)
    return "".join(c for c in folded if not unicodedata.combining(c)).translate(LEET)


def brand_forms(entry, official_label):
    # The domain label is authoritative for resemblance. Aliases are optional
    # reviewed references and are never sufficient for an ownership match.
    aliases = getattr(entry, "aliases", ())
    return {skeleton(official_label), *(skeleton(brand_key(alias)) for alias in aliases if brand_key(alias))}


# A brand name on somebody else's registrable domain (a deep-link, survey, hosting or
# marketing platform, or an attacker's domain) is an UNVERIFIED ASSOCIATION, not a
# lookalike of the brand's own domain. It is reported separately and scored as a weak
# cue; it is stronger when the registrable domain itself is dressed up with
# account/login/payment terms ("bcr.secure-login.com").
THIRD_PARTY_METHODS = {"brand_on_third_party_host", "brand_on_third_party_host_service_terms"}


def resemblance(hostname, official, root, subs, brand, tenant=False):
    if len(brand) < 3:
        return None
    normalized = skeleton(root)
    tokens = tuple(part for part in normalized.split("-") if part)
    compact = "".join(tokens)
    if f".{official}." in f".{hostname}." or re.search(r"(?:^|\.)" + re.escape(official) + r"-", hostname):
        # "bcr.ro.login-check.example" or "olx.ro-livrare.com": the official name is shown, the owner is not.
        return 45, 95, "embedded_official_hostname"
    service_terms = any(token in SERVICE_TOKENS for token in tokens)
    if tenant and normalized == brand:
        # Exact brand tenant on a shared platform (PSL private suffix, e.g. "emag.web.app").
        return 15, 90, "brand_on_third_party_host"
    if normalized == brand:
        return 45, 96, "same_label_other_suffix" if root == brand else "confusable_or_leetspeak"
    if brand in tokens:
        return 45, 93, "brand_token"
    if len(brand) >= 4 and len(tokens) >= 2 and compact == brand:
        return 42, 93, "split_brand"
    if len(brand) >= 5 and any(compact in {brand + token, token + brand} for token in SERVICE_TOKENS):
        return 41, 91, "concatenated_service_token"
    if brand in subs or any(brand in label.split("-") for label in subs):
        return (30, 88, "brand_on_third_party_host_service_terms") if service_terms else (15, 88, "brand_on_third_party_host")
    if len(brand) >= 5 and abs(len(compact) - len(brand)) <= 1 and damerau_distance(compact, brand) == 1:
        changes = [i for i, (a, b) in enumerate(zip(compact, brand)) if a != b]
        swap = len(compact) == len(brand) and len(changes) == 2
        return 38, round(100 * (1 - 1 / max(len(compact), len(brand)))), (
            "adjacent_transposition" if swap else "single_edit"
        )
    return None


def detect_typosquatting(hostname, catalog=STATIC_CATALOG):
    hostname = normalize_hostname(hostname)
    clean = {"is_official": False, "verified_match": False, "is_typosquatting": False, "brand_on_third_party": False,
             "relationship": None, "target": None, "similarity": 0}
    if not hostname:
        return clean
    label, suffix, registrable = domain_parts(hostname)
    if not label:
        return clean
    targets = []
    for entry in catalog:
        official = normalize_hostname(entry.domain) if entry.domain else ""
        if not official:
            continue
        official_label, _, official_root = domain_parts(official)
        if not official_label or not PSL(official).suffix:
            continue
        if (hostname == official or hostname.endswith("." + official)) and registrable == official_root:
            reviewed = bool(entry.verified_at and entry.verification_source)
            return {**clean, "is_official": True, "verified_match": reviewed, "relationship": "official",
                    "target": official, "similarity": 100,
                    "brand": entry.name, "source": "verified_database" if reviewed else "static_catalog",
                    "verification_source": entry.verification_source, "verified_at": entry.verified_at}
        targets.append((entry, official, brand_forms(entry, official_label)))

    subs = {skeleton(part) for part in hostname[:-(len(suffix) + 1)].split(".")[:-1]}
    tenant = PSL(hostname).private_suffix
    best = None
    for entry, official, forms in targets:
        for form in forms:
            match = resemblance(hostname, official, label, subs, form, tenant)
            if match and (best is None or match[:2] > best[:2]):
                best = (*match, entry, official)
    if best is None:
        return clean
    points, similarity, method, entry, official = best
    third_party = method in THIRD_PARTY_METHODS
    return {**clean, "is_typosquatting": not third_party, "brand_on_third_party": third_party,
            "relationship": "third_party_host" if third_party else "lookalike",
            "target": official, "similarity": similarity,
            "brand": entry.name, "points": points, "method": method,
            "source": "verified_database" if entry.verified_at and entry.verification_source else "static_catalog",
            "verification_source": entry.verification_source, "verified_at": entry.verified_at,
            "reason": (f"Numele {entry.name} apare pe domeniul terț {registrable}. Relația cu {official} nu este verificată."
                       if third_party else f"Adresa seamănă cu {official} și se află în afara acelui domeniu.")}


def parse_address(url):
    """A scheme-relative placeholder is internal. It never changes the submitted URL."""
    prefix = SCHEME.match(url)
    explicit = bool(prefix)
    defanged_scheme = url.casefold().startswith(("hxxp://", "hxxps://"))
    candidate = ("http" + url[4:] if defanged_scheme else url)
    if not explicit and not candidate.startswith("//"):
        candidate = "//" + candidate
    authority_start = candidate.find("//") + 2 if "//" in candidate else len(candidate)
    end = re.search(r"[/?#]", candidate[authority_start:])
    authority_end = authority_start + end.start() if end else len(candidate)
    authority = candidate[authority_start:authority_end]
    normalized_authority = TEXTUAL_DOT.sub(".", authority)
    parsed = urlsplit(candidate[:authority_start] + normalized_authority + candidate[authority_end:])
    source = "defanged" if defanged_scheme else "explicit" if explicit else "unspecified"
    return parsed, source, defanged_scheme or authority != normalized_authority


def analyze_single_url(url, catalog=STATIC_CATALOG):
    result = {
        "original_url": url, "final_url": url, "domain": "", "registrable_domain": None, "subdomain": None,
        "registered_domain_basis": "unavailable", "protocol": None, "protocol_source": "unspecified",
        "port": None, "path": None, "userinfo_present": False, "defanged": False, "query_present": False,
        "fragment_present": False, "embedded_destination_hint": False, "redirect_count": None,
        "is_shortened": False, "suspicious_tld": False, "tld": "", "typosquatting": {},
        "domain_age_days": None, "has_https": None, "has_login_or_card_form": None, "page_title": None,
        "inspection_status": "passive_only", "risk_points": 0, "flags": [],
    }
    flags = result["flags"]
    try:
        if len(url) > MAX_URL_LENGTH or re.search(r"[\\\s\x00-\x1f\x7f]", url):
            raise ValueError("invalid URL characters or length")
        parsed, source, defanged = parse_address(url)
        scheme = parsed.scheme.lower() or None
        result.update(protocol=scheme, protocol_source=source, defanged=defanged)
        if scheme and scheme not in {"http", "https"}:
            result["inspection_status"] = "unsupported_scheme"
            flags.append("Schema nu este HTTP(S). Linkul nu a fost accesat.")
            return result
        authority = parsed.netloc.rsplit("@", 1)[-1]
        if authority.startswith("[") and not re.fullmatch(r"\[[^\]]+\](?::\d+)?", authority):
            raise ValueError("invalid bracketed authority")
        port = parsed.port
        raw_host = parsed.hostname or ""
        try:
            address = ipaddress.ip_address(raw_host)
        except ValueError:
            address = None
        hostname = str(address) if address is not None else normalize_hostname(raw_host)
        if not hostname or (address is None and ":" in raw_host):
            raise ValueError("invalid host")
    except (ValueError, UnicodeError):
        result["inspection_status"] = "invalid_url"
        flags.append("Linkul nu a putut fi interpretat. Destinația rămâne neverificată.")
        return result

    result.update(domain=hostname, port=port, path=parsed.path or "/", query_present=bool(parsed.query),
                  fragment_present=bool(parsed.fragment), userinfo_present="@" in parsed.netloc,
                  has_https=(scheme == "https" if source == "explicit" and scheme else None))
    obscurity = 0
    if result["userinfo_present"]:
        # Userinfo can be a legitimate URL feature. A catalog hostname placed
        # there to suggest a different owner is stronger evidence.
        presented = normalize_hostname(parsed.netloc.rsplit("@", 1)[0])
        decoy = any(entry.domain and (presented == entry.domain or presented.endswith("." + entry.domain))
                    for entry in catalog)
        obscurity = 35 if decoy else 28
        flags.append(f"Adresa conține informații înainte de @. Gazda interpretată este {hostname}.")
    if address is not None:
        obscurity = max(obscurity, 18 if not address.is_global else 12)
        flags.append("Destinație IP directă, cu adresă nepublică." if not address.is_global
                     else "Destinație IP directă. Proprietarul rămâne neverificat.")
    elif hostname == "localhost" or hostname.endswith(".localhost"):
        obscurity = max(obscurity, 18)
        flags.append("Destinație locală. Linkul nu a fost accesat.")
    elif re.fullmatch(r"(?:0x[\da-f]+|\d+)(?:\.(?:0x[\da-f]+|\d+)){0,3}", hostname):
        obscurity = max(obscurity, 18)
        flags.append("Gazdă numerică neobișnuită. Browserul o poate interpreta ca adresă IP.")
    if port is not None and port not in ({443} if scheme == "https" else {80} if scheme == "http" else {80, 443}):
        obscurity = max(obscurity, 8)
        flags.append(f"Adresa specifică portul neobișnuit {port}.")
    if address is None and "." in hostname:
        _, suffix, registrable = domain_parts(hostname)
        basis = "public_suffix_list" if PSL(hostname).suffix else "reserved_suffix" if suffix in RESERVED_SUFFIXES else "unknown_suffix"
        result.update(registered_domain_basis=basis, registrable_domain=registrable or None if basis != "unknown_suffix" else None,
                      subdomain=hostname[:-(len(registrable) + 1)] if registrable and hostname.endswith("." + registrable) and basis != "unknown_suffix" else None,
                      tld="." + suffix)
        if registrable in SHORTENERS:
            result["is_shortened"] = True
            obscurity = max(obscurity, 18)
            flags.append("Link scurtat. Destinația finală rămâne neverificată.")
        typo = detect_typosquatting(hostname, catalog)
        result["typosquatting"] = typo
        if typo["is_typosquatting"] or typo.get("brand_on_third_party"):
            flags.append(typo["reason"])
        elif typo["is_official"]:
            catalog_kind = "catalogul verificat" if typo["verified_match"] else "lista statică"
            flags.append(f"Gazda corespunde domeniului {typo['target']} din {catalog_kind}. Expeditorul rămâne neverificat.")
        if any(label.startswith("xn--") for label in hostname.split(".")):
            flags.append("Nume internaționalizat (IDNA). Unele caractere pot semăna între ele.")
    if PATH_LINK.search(unquote(parsed.path + "?" + parsed.query + "#" + parsed.fragment)):
        result["embedded_destination_hint"] = True
        flags.append("Adresa conține o altă adresă în cale sau parametri. Redirecționarea rămâne neverificată.")
    if defanged:
        flags.append("Adresa era scrisă în formă mascată. Normalizarea a fost folosită pentru interpretare.")
    if scheme is None:
        flags.append("Textul nu specifică un protocol. Conexiunea nu a fost verificată.")
    elif source == "explicit" and scheme == "http":
        flags.append("Textul indică HTTP. Suportul serverului pentru HTTPS rămâne neverificat.")
    result["risk_points"] = min(55, obscurity + result["typosquatting"].get("points", 0))
    return result

# Explicit attribution is evidence of a claim, not evidence of ownership.
EXPLICIT_IDENTITY = re.compile(
    r"\b(?:suntem\s+de\s+la|sunt\s+de\s+la|din\s+partea|echipa|reprezint|representing|"
    r"(?:i\s+am|we\s+are)\s+(?:calling\s+)?from|team\s+at)\s+"
    r"(?P<name>[^\W\d_][\w&-]{1,30}(?:\s+[^\W\d_][\w&-]{1,30}){0,3})(?=\s*[,.:!?\n]|$)",
    re.IGNORECASE,
)
IDENTITY_HEADER = re.compile(r"^\s*(?P<name>[^\W\d_][\w&-]{1,32}(?: +[^\W\d_][\w&-]{1,32}){0,2})\s*:")
NON_NAMES = {"alerta", "atentie", "hello", "informare", "mesaj", "notificare", "salut", "buna", "exemplu", "warning"}


def _words(name):
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", name.casefold()).encode("ascii", "ignore").decode())


def catalog_index(catalog):
    known = {}
    for entry in catalog:
        for name in (entry.name, *getattr(entry, "aliases", ())):
            known.setdefault(brand_key(name), []).append(entry)
    return known


def match_brand(name, catalog, known=None):
    """Catalog entries for a claimed name. Exact key first, then a catalog brand appearing as
    whole words inside the claim ("My Orange" -> Orange, "ING Securitate" -> ING), so the
    identity check does not depend on how the model spelled the sender."""
    known = known if known is not None else catalog_index(catalog)
    exact = known.get(brand_key(name))
    if exact:
        return exact
    words = _words(name)
    best = []
    for key, entries in known.items():
        brand_words = _words(entries[0].name)
        if not brand_words or len("".join(brand_words)) < 2:
            continue
        n = len(brand_words)
        if any(words[i:i + n] == brand_words for i in range(len(words) - n + 1)):
            if n > len(_words(best[0].name)) if best else True:
                best = entries
    return best


def domain_claim_assessment(text, context, reports, catalog):
    """Relate each claimed organisation to each link. Statuses, strongest first:
    lookalike_outside_catalog (structural imitation of the brand's own domain),
    brand_on_third_party_host (the brand name on someone else's domain: unverified association),
    outside_known_domains (any other domain; `known_basis` says whether the brand's domains are
    reviewed or only static hints), verified_domain_match / static_catalog_match,
    verification_incomplete (brand not in the catalog), unparsed."""
    claimed = [name for name in context["claimed_entities"] if not name.startswith("Persoana apropiata")]
    known = catalog_index(catalog)
    if not claimed:
        prefix = text[:280]
        match = EXPLICIT_IDENTITY.search(prefix) or IDENTITY_HEADER.match(prefix)
        if match:
            name = match["name"]
            key = brand_key(name)
            # Headers used for warnings and conversational greetings are not identities.
            if key not in NON_NAMES and (name[0].isupper() or key in known):
                claimed.append(name)
    assessments, seen = [], set()
    for name in claimed[:4]:
        entries = match_brand(name, catalog, known)
        canonical = entries[0].name if entries else name
        if brand_key(canonical) in seen:
            continue
        seen.add(brand_key(canonical))
        reviewed = sorted({e.domain for e in entries if e.domain and e.verified_at and e.verification_source})
        static = sorted({e.domain for e in entries if e.domain} - set(reviewed))
        item = {"claim": name, "canonical_name": canonical if entries else None,
                "source": "message_claim", "identity_status": "unverified",
                "catalog_status": "reviewed_domains" if reviewed else "static_or_unreviewed" if entries else "unknown_brand",
                "reviewed_domains": reviewed, "known_domains": reviewed or static,
                "known_basis": "reviewed" if reviewed else "static_hint" if static else None, "destinations": []}
        for report in reports:
            typo = report["typosquatting"]
            same = bool(entries) and brand_key(typo.get("brand", "")) == brand_key(canonical)
            status = ("unparsed" if not report["domain"] else
                      "verified_domain_match" if same and typo.get("verified_match") else
                      "static_catalog_match" if same and typo.get("is_official") else
                      "lookalike_outside_catalog" if same and typo.get("is_typosquatting") else
                      "brand_on_third_party_host" if same and typo.get("brand_on_third_party") else
                      "outside_known_domains" if entries and (reviewed or static) else "verification_incomplete")
            item["destinations"].append({"host": report["domain"], "registrable_domain": report["registrable_domain"],
                                         "status": status, "known_basis": item["known_basis"]})
        assessments.append(item)
    return assessments
