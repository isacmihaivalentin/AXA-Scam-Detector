"""Evidence-based assessment policy (v2.1). Documented in POLICY.md.

`assess` turns (a) the validated Gemini interpretation, (b) deterministic URL / catalog /
reputation findings and (c) the local rules engine into one assessment.

Principles
- Mechanisms, not labels. Risk comes from what would actually happen: which asset
  (secret, control, documents, money, personal data) goes where (to the sender or a
  destination the message supplies, or stays with the recipient), and whether that
  destination is official, unverified or structurally deceptive. A holistic "suspicious"
  reading or an ordinary call to action is a cue, never alert-level evidence on its own.
- Evidence hierarchy: verified technical threats and grounded harmful mechanisms can
  alert on their own; cues (pressure, an unverified third-party link, an AI hunch) cannot.
  Cues from independent families can converge to a low-confidence "suspicious".
- Families, not sums: the message text (Gemini + rules), the link/identity analysis and
  external reputation are separate families. The strongest family sets the level; other
  families reinforce by at most +10. Correlated items inside a family never add up.
- Grounding: quotes that cannot be located are tentative and cannot reach critical.
  A quote negated in the text, or one that only states a supplied code value, cannot
  support a "requested" reading: the item is kept as contradicted and visible.
- No blanket trust: an official domain never cancels a secret handed to the sender; no AI
  reading cancels a lookalike or a reputation match.
- Honest uncertainty: the estimate is null when evidence is insufficient or conflicting.
"""

import re

ALERT = 35
CRITICAL = 70
CUE_FLOOR = 25          # a family must reach this to reinforce or to converge
CONVERGENCE = 38        # independent cues that converge on an action through the message's own channel

MECHANISM_LABELS = {
    "credential_phishing": "Furt de date de autentificare (phishing)",
    "otp_or_authentication_theft": "Furt de coduri de autentificare",
    "card_data_theft": "Furt de date de card",
    "identity_document_theft": "Furt de acte de identitate",
    "advance_fee": "Plată în avans pentru un beneficiu promis",
    "family_impersonation": "Impersonarea unei rude sau a unui prieten",
    "institution_impersonation": "Impersonarea unei instituții sau firme",
    "payment_redirection": "Redirecționarea unei plăți",
    "account_takeover": "Preluarea unui cont",
    "malicious_authorization": "Aprobare sau autorizare frauduloasă",
    "remote_access": "Acces de la distanță la dispozitiv",
    "delivery_scam": "Pretext de livrare sau taxă de colet",
    "reward_or_lottery": "Premiu sau câștig fals",
    "investment_fraud": "Investiție falsă",
    "job_scam": "Job fals",
    "marketplace_scam": "Fraudă la vânzare sau cumpărare online",
    "romance_or_trust": "Exploatarea încrederii",
    "extortion_or_threat": "Șantaj sau amenințare",
    "other_suspicious_mechanism": "Mecanism suspect neobișnuit",
    "malicious_link": "Link raportat sau înșelător",
}
LEGACY_MECHANISMS = {
    "credential_disclosure": "credential_phishing", "sensitive_documents": "identity_document_theft",
    "advance_fee": "advance_fee", "family_impersonation": "family_impersonation",
    "organization_lookalike": "institution_impersonation", "delivery_pretext": "delivery_scam",
    "account_or_device_abuse": "account_takeover", "listed_url_threat": "malicious_link",
}
ACTION_MECHANISM = {
    "share_password": "credential_phishing", "share_otp_or_code": "otp_or_authentication_theft",
    "share_card_data": "card_data_theft", "send_documents_or_photos": "identity_document_theft",
    "approve_authorization": "malicious_authorization", "install_or_grant_access": "remote_access",
    "change_payment_details": "payment_redirection", "pay_fee": "advance_fee", "transfer_money": "advance_fee",
}
SENSITIVITY_TIER = {"secret_credential": 82, "device_or_account_control": 80, "identity_document": 72}
ACTION_RO = {
    "transfer_money": "să transferi bani", "pay_fee": "să plătești o taxă", "share_password": "să dai o parolă",
    "share_otp_or_code": "să dai un cod de autentificare", "share_card_data": "să dai datele cardului",
    "send_documents_or_photos": "să trimiți documente sau fotografii", "approve_authorization": "să aprobi o autorizare",
    "install_or_grant_access": "să instalezi o aplicație sau să dai acces",
    "change_payment_details": "să schimbi datele unei plăți", "click_link": "să deschizi un link",
    "call_number": "să suni la un număr", "reply_or_contact": "să răspunzi sau să contactezi pe cineva",
    "move_to_other_channel": "să continui pe alt canal", "open_attachment_or_scan_qr": "să deschizi un fișier sau un cod QR",
    "provide_personal_data": "să dai date personale", "buy_or_subscribe": "să cumperi sau să te abonezi",
    "sign_in": "să te autentifici", "change_settings": "să schimbi o setare", "other": "o altă acțiune",
}
TACTIC_RO = {
    "fear": ("Frică", "Te sperie ca să acționezi fără să verifici."),
    "urgency": ("Grabă", "Te grăbește ca să nu ai timp să verifici."),
    "authority": ("Autoritate", "Invocă o autoritate ca să pară de încredere."),
    "scarcity": ("Ofertă limitată", "Sugerează că pierzi ocazia dacă nu acționezi acum."),
    "trust_exploitation": ("Încredere exploatată", "Se bazează pe încrederea ta într-o persoană sau firmă."),
    "family_impersonation": ("Se dă drept o rudă", "Folosește apropierea de familie ca să ceară ceva."),
    "reward_bait": ("Momeală", "Promite un câștig ca să te atragă."),
    "social_pressure": ("Presiune socială", "Te face să crezi că alții așteaptă după tine."),
    "secrecy": ("Secret", "Îți cere să nu spui nimănui, ca să nu afli că e o înșelătorie."),
    "channel_switch": ("Schimbă canalul", "Te mută pe un canal unde verificarea e mai grea."),
}
PROTECTIVE_RO = {
    "security_warning": "Avertisment de securitate", "educational_example": "Exemplu educativ",
    "news_report": "Relatare sau știre", "quoted_scam": "Înșelătorie citată",
    "account_security_instruction": "Instrucțiune obișnuită de securitate",
}
PROMISE_RO = {"money_or_prize": "Promite bani sau un premiu", "refund_or_compensation": "Promite o rambursare",
              "job_income": "Promite un venit din muncă", "investment_return": "Promite un profit",
              "delivery_or_goods": "Promite o livrare", "account_restore": "Promite deblocarea contului",
              "other": "Promite un beneficiu"}
THREAT_RO = {"account_block": "Amenință cu blocarea contului", "legal_or_fine": "Amenință cu amenzi sau urmări",
             "loss_of_goods_or_money": "Amenință cu o pierdere", "harm_to_someone": "Amenință că cineva are de suferit",
             "deadline": "Impune un termen", "other": "Amenință cu o consecință"}


def mechanism_group(category):
    if category in {"credential_phishing", "otp_or_authentication_theft", "card_data_theft", "identity_document_theft"}:
        return "secrets"
    if category in {"advance_fee", "reward_or_lottery", "investment_fraud", "job_scam", "marketplace_scam"}:
        return "pay_first"
    if category in {"malicious_authorization", "remote_access", "account_takeover"}:
        return "access"
    if category in {"family_impersonation", "romance_or_trust"}:
        return "family"
    if category == "payment_redirection":
        return "redirect"
    if category in {"institution_impersonation", "delivery_scam", "malicious_link"}:
        return "link"
    if category == "extortion_or_threat":
        return "threat"
    return "generic"



HIGH_TIER = {"secret_credential": 82, "device_or_account_control": 80, "identity_document": 72}
HIGH = set(HIGH_TIER)
# Never discounted because the model said "recipient keeps control": these always act for someone else.
NO_DISCOUNT = {"approve_authorization", "install_or_grant_access", "change_payment_details"}
MONEY_ACTIONS = {"transfer_money", "pay_fee", "buy_or_subscribe"}
STRONG_TACTICS = {"fear", "urgency", "secrecy", "family_impersonation", "reward_bait", "channel_switch",
                  "trust_exploitation", "social_pressure", "authority"}
FAMILY_OF = {"semantic_request": "message", "semantic_reading": "message", "rules": "message",
             "url_technical": "link", "identity_conflict": "link", "identity_cue": "link",
             "reputation": "reputation"}


def _span(grounding):
    if not grounding or grounding.get("status") == "ungrounded":
        return None
    return grounding["start"], grounding["end"]


class Ledger:
    def __init__(self):
        self.items = []

    def add(self, **item):
        item.setdefault("status", "supported")
        item.setdefault("tier", 0)
        item["id"] = f"e{len(self.items) + 1}"
        self.items.append(item)
        return item

    def active(self):
        return [i for i in self.items if i["status"] in {"supported", "tentative"} and i["tier"] > 0]


# ------------------------------------------------------------ destinations --

def _report_class(report):
    """Deterministic classification of one link, from URL forensics and reputation only."""
    typo = report.get("typosquatting") or {}
    if (report.get("reputation") or {}).get("status") == "threat_match":
        return "deceptive"
    if typo.get("is_official"):
        return "official"
    if (typo.get("is_typosquatting") or report.get("userinfo_present") or report.get("embedded_destination_hint")
            or (report.get("domain") and re.fullmatch(r"[\d.:a-f]+", report["domain"]) and report["domain"].count(".") >= 3)):
        return "deceptive"
    if report.get("inspection_status") != "passive_only":
        return "unverified"
    return "unverified"


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def resolve_destination(request, url_reports):
    """Where the requested item or action goes. Returns (kind, report|None).

    kind: link_official | link_unverified | link_deceptive | contact | own | unclear.
    Python resolves the model's `destination` text against the parsed links; the model never
    decides whether a domain is official."""
    destination = request.get("destination")
    report = None
    if destination:
        compact = _norm(destination)
        for r in url_reports:
            if not r.get("domain"):
                continue
            if _norm(r["original_url"]) and (_norm(r["original_url"]) in compact or compact in _norm(r["original_url"])
                                             or _norm(r["domain"]) in compact):
                report = r
                break
    action, handover = request["action"], request["handover"]
    links = [r for r in url_reports if r.get("domain")]
    if report is None and destination is None and handover != "recipient_keeps_control" and links and action in {
            "sign_in", "click_link", "share_password", "share_otp_or_code", "share_card_data", "provide_personal_data",
            "pay_fee", "approve_authorization", "install_or_grant_access", "open_attachment_or_scan_qr"}:
        # The model named no destination but the message carries links: assume the riskiest one.
        # This inference may only RAISE concern: an official link is never assumed to be the
        # destination (a secret sent by reply next to "details on www.bank.ro" stays a handover).
        order = {"deceptive": 0, "unverified": 1, "official": 2}
        riskiest = min(links, key=lambda r: order[_report_class(r)])
        report = riskiest if _report_class(riskiest) != "official" else None
    if report is not None:
        return "link_" + _report_class(report), report
    if action == "sign_in":
        # Signing in can only leak credentials to a place the message controls. With no link
        # (or with a destination that is not a link) the recipient signs in where they choose.
        return ("contact", None) if destination and handover == "to_sender_or_message_destination" else ("own", None)
    if handover == "recipient_keeps_control":
        if action in NO_DISCOUNT:
            return "unclear", None
        if action in MONEY_ACTIONS and destination:
            # Paying a payee the MESSAGE supplies (an IBAN, a number, a handle) is not "your own channel".
            return "contact", None
        return "own", None
    if handover == "to_sender_or_message_destination" or destination:
        return "contact", None
    return "unclear", None


# ------------------------------------------------------------- semantic part --

def _request_tier(request, where, reading, ctx):
    """Tier, reason, mechanism and class for one grounded, live request."""
    sensitivity, action = request["sensitivity"], request["action"]
    scam, suspicious = reading == "scam", reading == "suspicious"
    if sensitivity in HIGH:
        base = HIGH_TIER[sensitivity]
        mech = ACTION_MECHANISM.get(action)
        mech = mech if mech and mechanism_group(mech) in {"secrets", "access"} else (
            "remote_access" if sensitivity == "device_or_account_control" else
            "identity_document_theft" if sensitivity == "identity_document" else "credential_phishing")
        login = action == "sign_in" and sensitivity == "secret_credential"
        if where == "own":
            if action == "share_otp_or_code":
                return 15, "Codul se folosește în aplicația ta; introdu-l doar pentru operațiuni începute de tine.", None, "cue"
            return 0, "Folosești singur datele, în contul sau aplicația ta: nu sunt trimise nimănui.", None, "context"
        if where == "contact":
            return base, "Ți se cere să predai direct ceva ce permite accesul la bani, conturi sau identitate.", mech, "mechanism"
        if where == "link_deceptive":
            return base, "Ți se cere să introduci date sensibile pe o adresă care imită o organizație sau își ascunde destinația.", mech, "mechanism"
        if where == "link_official":
            if scam:
                return 50, "Date sensibile cerute într-un mesaj citit ca înșelătorie, deși linkul e pe un domeniu cunoscut.", mech, "mechanism"
            return 12, "Linkul e pe un domeniu oficial cunoscut. Introdu date doar dacă ai deschis singur aplicația sau site-ul.", None, "cue"
        if where == "link_unverified":
            if scam:
                return base, "Date sensibile cerute pe o adresă al cărei proprietar nu e confirmat, într-un mesaj citit ca înșelătorie.", mech, "mechanism"
            if login:
                return (45 if suspicious else 25), ("Ți se cere să te autentifici pe o adresă al cărei proprietar nu este confirmat. "
                                                    "Intră singur în aplicația sau site-ul oficial."), mech, ("mechanism" if suspicious else "cue")
            # Card data or one-time codes typed into an unconfirmed page is the core phishing step.
            entry = action in {"share_card_data", "share_otp_or_code", "share_password"}
            return (70 if suspicious and entry else 60 if suspicious else 50), (
                "Ți se cer date sensibile pe o adresă al cărei proprietar nu este confirmat."), mech, "mechanism"
        # unclear handover
        if scam:
            return base, "Ți se cere ceva ce permite accesul la bani, conturi sau identitate; destinația nu e clară.", mech, "mechanism"
        return (60 if sensitivity != "identity_document" else 55), (
            "Ți se cere ceva sensibil, dar nu e clar cui ajunge. Verifică pe un canal cunoscut."), mech, "mechanism"

    if action == "change_payment_details":
        if sensitivity == "financial_asset" and (scam or suspicious):
            return 70, "Cere ca plata să meargă în alt cont decât cel cunoscut.", "payment_redirection", "mechanism"
        return 25, "Menționează schimbarea unor date de plată sau setări; confirmă pe un canal cunoscut.", None, "cue"

    if sensitivity == "financial_asset":
        if ctx["dependency"]:
            return 74, "Plata este cerută înainte de un beneficiu promis.", "advance_fee", "mechanism"
        if ctx["family"]:
            return 74, "O persoană care se prezintă drept apropiată cere bani.", "family_impersonation", "mechanism"
        if where == "own":
            return 6, "Plată către un beneficiar sau canal pe care îl cunoști deja.", None, "context"
        if scam:
            return 60, "Cerere de bani într-un mesaj interpretat ca înșelătorie.", ACTION_MECHANISM.get(action), "mechanism"
        if suspicious:
            return (35 if where in {"contact", "link_unverified", "link_deceptive"} else 25), (
                "Cerere de bani către o destinație din mesaj, într-un context suspect."), None, (
                "mechanism" if where in {"contact", "link_unverified", "link_deceptive"} else "cue")
        return (18 if where in {"link_unverified", "link_deceptive"} else 10), "Cerere de plată fără alte semne de înșelătorie.", None, "cue"

    if sensitivity == "personal_data":
        if where == "own":
            return 0, "Datele rămân în contul sau canalul tău.", None, "context"
        outward = where in {"contact", "link_unverified", "link_deceptive"}
        if scam:
            return (50 if outward else 45), "Cere date personale.", None, "mechanism"
        if suspicious and outward:
            return 35, "Cere date personale către o destinație din mesaj, într-un context suspect.", None, "mechanism"
        return (25 if suspicious else 8), "Cere date personale.", None, "cue"

    # Low-impact actions (open a link, call, reply) are context: the risk lies in what follows,
    # which the link, identity and reading checks evaluate separately.
    return 0, "Acțiunea în sine nu predă nimic sensibil; riscul ar ține de destinație, verificată separat.", None, "context"


def _semantic_evidence(ledger, interp, url_reports):
    overall = interp["overall"]
    mechanism = interp["mechanism"]["category"]
    reading = "scam" if overall == "likely_scam" and mechanism != "none" else (
        "suspicious" if overall in {"likely_scam", "suspicious"} else "benign")
    family = any(t["tactic"] == "family_impersonation" and _span(t["grounding"]) for t in interp["tactics"]) or (
        interp["claimed_sender"]["type"] == "family_or_friend" and mechanism == "family_impersonation")
    dependency = interp["dependency"]
    ctx = {"dependency": bool(dependency["present"] and (_span(dependency.get("grounding")) or reading == "scam")),
           "family": family}

    for request in interp["requests"]:
        grounding, stance = request["grounding"], request["stance"]
        span = _span(grounding)
        where, report = resolve_destination(request, url_reports)
        base = dict(source="gemini", category="semantic_request", kind="request", span=grounding,
                    action=request["action"], object=request["object"], sensitivity=request["sensitivity"],
                    stance=stance, recipient=request["recipient"], handover=request["handover"],
                    destination=request["destination"], destination_kind=where,
                    destination_host=report and (report["registrable_domain"] or report["domain"]))
        if stance != "requested":
            ledger.add(**base, status="context", tier=0,
                       reason={"discouraged": "Cererea apare ca sfat de a NU face acest lucru.",
                               "reported_or_quoted": "Cererea este relatată sau citată, nu adresată ție.",
                               "self_initiated": "Pas obișnuit într-un proces inițiat chiar de tine.",
                               "provided_to_recipient": "Mesajul îți oferă această informație; nu ți-o cere înapoi.",
                               "hypothetical": "Cererea este ipotetică sau condiționată."}[stance])
            continue
        if request["consistency"] == "negation_conflict":
            ledger.add(**base, status="contradicted", tier=0,
                       reason="În text, fragmentul citat este precedat de o negație; interpretarea „cerere” nu este susținută.")
            continue
        if request["consistency"] == "supplied_value":
            ledger.add(**base, status="contradicted", tier=0,
                       reason="Fragmentul citat doar comunică un cod sau un PIN; nu arată o cerere de a-l preda.")
            continue
        tier, reason, mech, klass = _request_tier(request, where, reading, ctx)
        status = "supported" if tier else "context"
        if tier and not span:
            status, tier = "tentative", min(tier, 40)
            reason += " Fragmentul citat nu a putut fi găsit exact în text."
        ledger.add(**base, status=status, tier=tier, reason=reason, mechanism=mech, evidence_class=klass)

    if dependency["present"]:
        span = _span(dependency.get("grounding"))
        ledger.add(source="gemini", category="semantic_dependency", kind="dependency", span=dependency.get("grounding"),
                   status="supported" if span else "tentative", tier=0,
                   reason=dependency.get("description") or "Beneficiul promis depinde de o acțiune făcută înainte.")
    for tactic in interp["tactics"]:
        label, explanation = TACTIC_RO[tactic["tactic"]]
        ledger.add(source="gemini", category="semantic_tactic", kind="tactic", tactic=tactic["tactic"], label=label,
                   span=tactic["grounding"], status="supported" if _span(tactic["grounding"]) else "tentative",
                   tier=0, reason=explanation)
    for promise in interp["promises"]:
        ledger.add(source="gemini", category="semantic_promise", kind="promise", label=PROMISE_RO[promise["kind"]],
                   span=promise["grounding"], status="supported" if _span(promise["grounding"]) else "tentative",
                   tier=0, reason="Beneficiul promis este folosit ca momeală dacă cere ceva în schimb.")
    for threat in interp["threats"]:
        ledger.add(source="gemini", category="semantic_threat", kind="threat", label=THREAT_RO[threat["kind"]],
                   span=threat["grounding"], status="supported" if _span(threat["grounding"]) else "tentative",
                   tier=0, reason="Consecința amenințată creează presiune.")
    for item in interp["protective_context"]:
        ledger.add(source="gemini", category="semantic_protective", kind="protective", label=PROTECTIVE_RO[item["kind"]],
                   span=item["grounding"], status="supported" if _span(item["grounding"]) else "tentative",
                   tier=0, reason="Context protector sau informativ.")

    # The holistic reading counts only when grounded text shows a deceptive element, not merely a
    # call to action. Otherwise it stays a visible cue (and, for "likely_scam", an unresolved concern).
    scam_claim = overall == "likely_scam"
    deception = [i for i in ledger.items if i["source"] == "gemini" and _span(i.get("span")) and i["status"] == "supported" and (
        i["kind"] in {"threat", "dependency"}
        or (i["kind"] == "tactic" and i["tactic"] in STRONG_TACTICS)
        # A promise is bait only when something is asked in return, or when the model itself
        # reads the message as a scam (unsolicited "you won / approved / recovered").
        or (i["kind"] == "promise" and (scam_claim or any(r["kind"] == "request" and r["tier"] > 0 for r in ledger.items)))
        or (i["kind"] == "request" and i["tier"] >= CUE_FLOOR and i["sensitivity"] != "low"))]
    outward = [i for i in ledger.items if i["kind"] == "request" and _span(i.get("span")) and i.get("stance") == "requested"
               and i["status"] in {"supported", "context"} and i.get("destination_kind") in {"contact", "link_unverified", "link_deceptive"}]
    unsupported = False
    if mechanism != "none" and overall in {"likely_scam", "suspicious"}:
        if scam_claim and deception:
            tier, klass = 50, "mechanism"
        elif scam_claim and outward:
            # The model calls it a scam and the text sends the reader somewhere the message controls.
            tier, klass = 40, "mechanism"
        elif scam_claim:
            tier, klass, unsupported = 30, "cue", True
        elif deception:
            tier, klass = 28, "cue"
        else:
            tier, klass = 15, "cue"
        ledger.add(source="gemini", category="semantic_reading", kind="reading", status="supported", tier=tier,
                   mechanism=mechanism, evidence_class=klass, support=[i["id"] for i in deception[:4]],
                   reason=(interp["mechanism"]["description"] or MECHANISM_LABELS.get(mechanism, "")) + (
                       "" if klass == "mechanism" else
                       " (Interpretare AI fără un element înșelător concret în text: indiciu, nu dovadă.)"))
    return unsupported


# ------------------------------------------------------------ technical part --

def _technical_evidence(ledger, url_reports, claims, interp):
    for report in url_reports:
        host = report["domain"] or report["original_url"]
        typo = report.get("typosquatting") or {}
        reputation = (report.get("reputation") or {}).get("status")
        if reputation == "threat_match":
            ledger.add(source="google_web_risk", category="reputation", kind="reputation", host=host, tier=88,
                       mechanism="malicious_link", evidence_class="technical",
                       reason="Adresa apare în lista Google Web Risk (" + ", ".join(report["reputation"].get("types", [])) + ").")
        if report["risk_points"] >= 10:
            third_party = typo.get("brand_on_third_party")
            ledger.add(source="static_url", category="url_technical", kind="url", host=host,
                       tier=min(55, report["risk_points"]), evidence_class="technical" if report["risk_points"] >= ALERT else "cue",
                       mechanism="institution_impersonation" if typo.get("is_typosquatting") else None,
                       reason=" ".join(report["flags"][:2]) or "Structură de adresă neobișnuită.",
                       relationship="third_party_host" if third_party else typo.get("relationship"))
        elif typo.get("is_official"):
            ledger.add(source="catalog", category="verified_relationship", kind="url", host=host, tier=0,
                       status="context", reason=(f"Gazda aparține domeniului {typo['target']} din "
                                                 + ("catalogul verificat." if typo.get("verified_match") else "lista statică.")
                                                 + " Asta nu confirmă expeditorul și nu anulează alte cereri."))
    link_hosts = set()
    if interp is None:
        link_hosts = {r["domain"] for r in url_reports}
    else:
        for r in interp["requests"]:
            if r["stance"] == "requested" and r["consistency"] == "consistent":
                where, report = resolve_destination(r, url_reports)
                if report is not None:
                    link_hosts.add(report["domain"])
    for claim in claims:
        for destination in claim["destinations"]:
            status, host = destination["status"], destination["host"]
            acted = host in link_hosts
            if status == "lookalike_outside_catalog":
                ledger.add(source="catalog", category="identity_conflict", kind="identity", host=host, evidence_class="technical",
                           claim=claim["claim"], tier=75 if acted else 60, mechanism="institution_impersonation",
                           reason=f"Mesajul invocă {claim['claim']}, iar linkul imită domeniul acestei organizații.")
            elif status == "brand_on_third_party_host":
                ledger.add(source="catalog", category="identity_cue", kind="identity", host=host, evidence_class="cue",
                           claim=claim["claim"], tier=20 if acted else 12,
                           reason=(f"Mesajul invocă {claim['claim']}, iar linkul e pe domeniul terț "
                                   f"{destination['registrable_domain'] or host}. Relația nu este verificată; poate fi un serviciu "
                                   "folosit de organizație sau o imitație."))
            elif status == "outside_known_domains":
                reviewed = destination.get("known_basis") == "reviewed"
                ledger.add(source="catalog", category="identity_cue", kind="identity", host=host, evidence_class="cue",
                           claim=claim["claim"], tier=(30 if reviewed else 22) if acted else (18 if reviewed else 12),
                           reason=(f"Mesajul invocă {claim['claim']}, dar linkul duce la {destination['registrable_domain'] or host}, "
                                   "în afara domeniilor " + ("verificate" if reviewed else "cunoscute (listă statică)")
                                   + " ale organizației. Proprietarul linkului nu este confirmat."))
            elif status in {"verified_domain_match", "static_catalog_match"}:
                ledger.add(source="catalog", category="verified_relationship", kind="identity", host=host,
                           claim=claim["claim"], status="context", tier=0,
                           reason=f"Linkul este pe un domeniu {'verificat' if status == 'verified_domain_match' else 'cunoscut (listă statică)'} "
                                  f"al {claim['claim']}. Expeditorul rămâne neverificat.")
        if claim["catalog_status"] == "unknown_brand" and claim["destinations"]:
            ledger.add(source="catalog", category="identity_unknown", kind="identity", claim=claim["claim"], status="context",
                       tier=0, reason=f"Nu avem o înregistrare pentru {claim['claim']}; domeniul oficial nu poate fi stabilit.")


# ------------------------------------------------------------------ legacy ---

def _legacy_evidence(ledger, legacy, ai_done):
    """The rules engine as one text-family item. Only its LINGUISTIC points are used: URL and
    identity evidence already sit in the ledger, so they are never counted twice."""
    mechanisms = [m for m in legacy["assessment"]["mechanisms"] if m["id"] in LEGACY_MECHANISMS
                  and m["id"] not in {"organization_lookalike", "listed_url_threat"}]
    text_points = legacy["score_breakdown"]["linguistic_behavior"]
    if mechanisms and text_points >= ALERT:
        return ledger.add(source="rules", category="rules", kind="rules", tier=min(80, text_points),
                          mechanism=LEGACY_MECHANISMS[mechanisms[0]["id"]], evidence_class="mechanism",
                          reason="Regulile locale: " + ", ".join(m["label"] for m in mechanisms) + ".")
    if ai_done:
        return None
    # Offline fallback only: pressure or verification wording tied to an action is a text cue.
    cues = {i["label"] for i in legacy.get("semantic_evidence", [])} & {"urgency_or_pressure", "account_verification_request"}
    if text_points >= 10 or cues:
        return ledger.add(source="rules", category="rules", kind="rules", tier=max(min(34, text_points), 25 if cues else 0),
                          evidence_class="cue", mechanism=None,
                          reason="Regulile locale: " + (", ".join(legacy.get("tactics_detected", [])) or "formulare de presiune sau verificare") + ".")
    return None


# ------------------------------------------------------------------ assess ---

def _level(score):
    return "critical" if score >= CRITICAL else "suspicious" if score >= ALERT else "low"


def assess(text, interp, ai_status, url_reports, claims, legacy, legacy_details, reputation_status):
    ledger = Ledger()
    unsupported_reading = False
    if interp:
        unsupported_reading = _semantic_evidence(ledger, interp, url_reports)
    _technical_evidence(ledger, url_reports, claims, interp)
    ai_done = interp is not None
    rules_item = _legacy_evidence(ledger, legacy, ai_done)

    conflict = False
    if ai_done and rules_item:
        semantic_alert = any(i["source"] == "gemini" and i["tier"] >= ALERT and i["status"] == "supported"
                             for i in ledger.items)
        if not semantic_alert and interp["overall"] != "likely_scam":
            # The lexical rules see an alert-level request that the structured reading did not find.
            # Rules corroborate Gemini; they never override it. The disagreement is shown and the
            # estimate is withheld instead of letting a keyword match decide.
            rules_item["status"] = "contradicted"
            rules_item["reason"] += " Interpretarea semantică nu găsește această cerere; conflictul rămâne nerezolvat."
            conflict = True
        elif semantic_alert:
            # Same text, two readers: corroboration raises confidence, not the score.
            rules_item["status"] = "corroborating"

    # ---- combine by evidence family ----------------------------------------
    active = [i for i in ledger.active() if i["status"] != "corroborating"]
    families = {}
    for item in active:
        family = FAMILY_OF.get(item["category"], item["category"])
        if item["tier"] > families.get(family, {"tier": -1})["tier"]:
            families[family] = item
    ranked = sorted(families.values(), key=lambda i: i["tier"], reverse=True)
    top = ranked[0] if ranked else None
    score = top["tier"] if top else 0
    if top and top["status"] == "tentative":
        score = min(score, 40)
    independent = [i for i in ranked[1:] if i["tier"] >= CUE_FLOOR and i["status"] == "supported"]
    reinforcement = min(10, 5 * len(independent)) if score >= ALERT else 0
    score = min(97, score + reinforcement)

    # Independent sub-alert cues converging on an action through the message's own channel.
    acted_outward = (not ai_done and bool(url_reports)) or any(
        i["kind"] == "request" and i["status"] in {"supported", "context"} and i.get("stance") == "requested"
        and i.get("destination_kind") in {"contact", "link_unverified", "link_deceptive"} for i in ledger.items)
    supported_cues = [i for i in ranked if i["tier"] >= CUE_FLOOR and i["status"] == "supported"]
    converged = score < ALERT and len(supported_cues) >= 2 and acted_outward
    if converged:
        score = CONVERGENCE

    unresolved_high = [i for i in ledger.items if i["source"] == "gemini" and i["kind"] == "request"
                       and i["status"] in {"tentative", "contradicted"} and i.get("sensitivity") in HIGH]

    # ---- labels ---------------------------------------------------------------
    if not ai_done:
        legacy_assessment = legacy["assessment"]
        unestimated = score < ALERT and (
            legacy_assessment.get("risk_status") == "unestimated" or legacy_assessment.get("label") == "inconclusive")
        label = "inconclusive" if unestimated else _level(score)
        if label == "low" and legacy_assessment.get("message_type") == "protective_or_educational":
            label = "protective"
    else:
        protective = interp["overall"] == "protective_or_educational"
        consequential = any(r["stance"] == "requested" and r["sensitivity"] != "low" for r in interp["requests"])
        unestimated = score < ALERT and (
            conflict or bool(unresolved_high) or unsupported_reading
            or (interp["overall"] == "insufficient_information" and (consequential or url_reports)))
        if unestimated:
            label = "inconclusive"
        elif score >= ALERT:
            label = _level(score)
        elif protective:
            label = "protective"
        elif interp["overall"] == "marketing_or_spam":
            label = "marketing"
        else:
            label = "low"

    # ---- mechanism ---------------------------------------------------------
    mechanism = None
    if label in {"critical", "suspicious"}:
        category = None
        decisive = top.get("mechanism") if top and not converged else None
        if ai_done and interp["mechanism"]["category"] != "none":
            category = interp["mechanism"]["category"]
        category = category or decisive or next((i.get("mechanism") for i in ranked if i.get("mechanism")), None)
        if not category and not ai_done:
            legacy_ids = [m["id"] for m in legacy["assessment"]["mechanisms"] if m["id"] in LEGACY_MECHANISMS]
            category = LEGACY_MECHANISMS[legacy_ids[0]] if legacy_ids else None
        category = category or "other_suspicious_mechanism"
        from_ai = ai_done and interp["mechanism"]["category"] == category
        mechanism = {"category": category, "label": MECHANISM_LABELS.get(category, category),
                     "description": interp["mechanism"]["description"] if from_ai else None,
                     "source": "gemini" if from_ai else ("rules" if not ai_done else (top or {}).get("source", "policy")),
                     "established": bool(top and not converged and top["status"] == "supported" and top["tier"] >= ALERT
                                         and top.get("evidence_class") in {"mechanism", "technical"})}

    # ---- confidence --------------------------------------------------------
    reasons = []
    corroborated = rules_item is not None and rules_item["status"] == "corroborating"
    if unestimated:
        confidence = "low"
        reasons.append("insufficient_or_conflicting_evidence")
    elif converged:
        confidence = "low"
        reasons.append("converging_weak_indicators")
    elif top and top["status"] == "tentative":
        confidence = "low"
        reasons.append("tentative_evidence")
    elif not ai_done:
        confidence = "high" if legacy_details.get("direct") and score >= CRITICAL else "medium" if score >= ALERT else "low"
        reasons.append("semantic_ai_unavailable")
    elif label in {"critical", "suspicious"} and top and (top["source"] in {"google_web_risk", "catalog", "static_url"}
                                                          or _span(top.get("span"))):
        confidence = "high" if (top["tier"] >= CRITICAL or corroborated or independent) and not conflict else "medium"
        reasons.append("grounded_strongest_evidence")
    elif label in {"low", "marketing", "protective"} and interp and interp["overall"] in {"suspicious", "likely_scam"}:
        confidence = "medium"
        reasons.append("ai_concern_not_backed_by_mechanism")
    else:
        confidence = "medium"
    if corroborated:
        reasons.append("rules_and_ai_agree")
    if independent and score >= ALERT:
        reasons.append("independent_evidence_categories")
    if conflict:
        reasons.append("rules_ai_conflict")
    if unsupported_reading:
        reasons.append("ai_reading_without_grounded_mechanism")
    if ai_status.get("truncated"):
        reasons.append("ai_saw_partial_text")

    estimate = None if unestimated else score
    return {
        "label": label, "risk_status": "unestimated" if unestimated else "estimated", "risk_estimate": estimate,
        "indicator_score": score, "confidence": confidence, "confidence_reasons": reasons,
        "mechanism": mechanism, "conflict": conflict,
        "policy": {"version": "2.1", "strongest": top and {k: top[k] for k in ("id", "category", "tier", "source")},
                   "reinforcement": reinforcement, "converged": converged,
                   "families": {FAMILY_OF.get(i["category"], i["category"]): i["tier"] for i in ranked},
                   "independent_categories": [i["category"] for i in independent]},
        "evidence": ledger.items,
    }
