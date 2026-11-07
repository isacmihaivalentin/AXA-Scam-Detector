"""User-facing text derived from the assessment: verdict copy, reasons, highlights,
qualitative risk profile, safe actions and the hypothetical scenario.

Everything here is built from validated evidence. Nothing here adds findings.
"""
from decision import ACTION_RO, ALERT, CRITICAL, MECHANISM_LABELS, mechanism_group

HEADLINES = {
    "critical": ("Probabil înșelătorie: nu acționa pe baza mesajului", "Nu răspunde, nu deschide linkul și nu trimite nimic."),
    "suspicious": ("Mesaj suspect: verifică înainte să faci ceva", "Verifică pe un canal oficial, deschis de tine, nu din mesaj."),
    "inconclusive": ("Nu putem estima riscul", "Nu acționa pe baza mesajului până nu verifici expeditorul pe un canal cunoscut."),
    "low": ("Nu am găsit semne clare de înșelătorie", "Asta nu confirmă cine a trimis mesajul. Dacă cere ceva neașteptat, verifică separat."),
    "protective": ("Pare un avertisment sau o informare", "Mesajul nu îți cere date secrete. Identitatea expeditorului rămâne neverificată."),
    "marketing": ("Pare un mesaj comercial obișnuit", "Oferta și expeditorul rămân neverificate. Nu da date de card din linkuri primite."),
}

RECOMMENDATIONS = {
    "secrets": [
        "Nu trimite și nu introduce parole, coduri primite prin SMS, PIN, CVV sau poze cu cardul ori actele.",
        "Deschide singur aplicația sau site-ul oficial, tastând adresa, dacă vrei să verifici contul.",
        "Dacă ai trimis deja ceva: sună banca la numărul de pe spatele cardului și blochează cardul.",
        "Schimbă parola contului afectat de pe un dispozitiv în care ai încredere.",
    ],
    "access": [
        "Nu instala aplicații de control de la distanță și nu aproba autentificări, plăți sau permisiuni pe care nu le-ai cerut tu.",
        "Dacă ai aprobat deja: deconectează sesiunile sau dispozitivele necunoscute și sună banca.",
        "Schimbă parolele de pe un alt dispozitiv și verifică redirecționările de apeluri la operator.",
    ],
    "pay_first": [
        "Nu plăti nicio taxă, avans sau garanție ca să primești bani, un premiu, un împrumut sau un job.",
        "Verifică firma independent, în registre oficiale, nu cu datele din mesaj.",
        "Dacă ai plătit deja: anunță imediat banca și păstrează dovezile plății.",
    ],
    "family": [
        "Sună persoana pe numărul vechi, cunoscut, înainte să trimiți bani.",
        "Întreabă ceva ce doar ea ar ști. Un escroc evită apelurile.",
        "Nu face niciun transfer și nu cumpăra carduri cadou sau reîncărcări până nu confirmi.",
    ],
    "redirect": [
        "Nu modifica datele de plată pe baza mesajului.",
        "Confirmă noul cont sunând la un număr deja cunoscut, nu la cel din mesaj.",
        "Dacă ai plătit deja în noul cont, anunță imediat banca.",
    ],
    "link": [
        "Nu deschide linkul. Intră singur în aplicația sau pe site-ul oficial.",
        "Dacă ai deschis deja linkul, nu introduce nimic acolo și închide pagina.",
        "Nu plăti taxe de livrare sau de deblocare din linkuri primite prin mesaj.",
    ],
    "threat": [
        "Nu plăti și nu răspunde la amenințări primite prin mesaj.",
        "Verifică orice presupusă amendă sau datorie direct la instituție, pe canalele ei oficiale.",
    ],
    "generic": [
        "Nu acționa pe baza mesajului. Verifică expeditorul pe un canal pe care îl cunoști deja.",
        "Nu trimite bani, coduri sau documente până nu confirmi cererea.",
    ],
}


def _grounded(item):
    span = item.get("span")
    return span and span.get("status") in {"exact", "normalized"}


def highlights(text, evidence):
    out = []
    for item in evidence:
        if not _grounded(item) or item["status"] in {"contradicted"}:
            continue
        span = item["span"]
        kind = item["kind"]
        if kind == "request":
            requested = item["stance"] == "requested"
            severity = "alarm" if requested and item["tier"] >= ALERT else "note" if requested else "protective"
            title = ("Cere " + ACTION_RO.get(item["action"], "o acțiune")) if requested else "Cerere relatată sau descurajată"
            meaning = f"Ce vrea de fapt: {item['object']}" if requested else item["reason"]
        elif kind == "tactic":
            severity, title, meaning = "attention", item["label"], item["reason"]
        elif kind in {"promise", "threat"}:
            severity, title, meaning = "attention", item["label"], item["reason"]
        elif kind == "dependency":
            severity, title, meaning = "alarm", "Plătești întâi, primești (poate) apoi", item["reason"]
        elif kind == "protective":
            severity, title, meaning = "protective", item["label"], item["reason"]
        else:
            continue
        out.append({"start": span["start_utf16"], "end": span["end_utf16"], "text": span["quote"],
                    "severity": severity, "title": title, "meaning": meaning, "source": item["source"],
                    "evidence_id": item["id"], "match": span["status"]})
    rank = {"alarm": 0, "attention": 1, "note": 2, "protective": 3}
    out.sort(key=lambda h: (h["start"], rank[h["severity"]]))
    merged = {}
    for h in out:  # one mark per identical span, several explanations
        key = (h["start"], h["end"])
        if key in merged:
            merged[key]["notes"].append({"title": h["title"], "meaning": h["meaning"]})
        else:
            merged[key] = {**h, "notes": [{"title": h["title"], "meaning": h["meaning"]}]}
    return list(merged.values())


def legacy_highlights(legacy):
    severity = {"Solicitare de date sensibile": "alarm"}
    return [{"start": h["start"], "end": h["end"], "text": h["phrase"], "severity": severity.get(h["category"], "attention"),
             "title": h["category"], "meaning": h["explanation"], "source": "rules", "evidence_id": None, "match": "exact",
             "notes": [{"title": h["category"], "meaning": h["explanation"]}]}
            for h in legacy.get("highlights", [])]


def reasons(assessment, interp, legacy):
    out = []
    evidence = sorted((i for i in assessment["evidence"] if i["status"] in {"supported", "tentative"} and i["tier"] >= 12),
                      key=lambda i: i["tier"], reverse=True)
    seen = set()
    identity_hosts = {i.get("host") for i in evidence if i["kind"] == "identity"}
    for item in evidence:
        if item["kind"] == "url" and item["tier"] < ALERT and item.get("host") in identity_hosts:
            continue  # the identity note already explains this link
        text = item["reason"]
        if item["kind"] == "request":
            text = f"Îți cere {ACTION_RO.get(item['action'], 'o acțiune')}: {item['object']}. {item['reason']}"
        if text in seen:
            continue
        seen.add(text)
        # Sub-alert cues are shown as notes so that a weak clue never reads like an alarm.
        level = "alarm" if item["tier"] >= CRITICAL else "attention" if item["tier"] >= ALERT else "info"
        out.append({"level": level, "text": text, "source": item["source"], "tentative": item["status"] == "tentative"})
    if interp:
        for item in assessment["evidence"]:
            if item["kind"] == "tactic" and item["status"] == "supported" and len(out) < 5:
                out.append({"level": "attention", "text": f"{item['label']}: {item['reason']}", "source": "gemini",
                            "tentative": False})
        if assessment["label"] in {"protective", "low", "marketing"}:
            for item in assessment["evidence"]:
                if item["kind"] in {"protective", "request"} and item.get("status") == "context" and len(out) < 4:
                    # Only warnings and reported/discouraged requests are "protective"; an ordinary request
                    # explained as harmless is a note, not reassurance about the sender.
                    protective = item["kind"] == "protective" or item.get("stance") in {"discouraged", "reported_or_quoted"}
                    text = item["reason"]
                    if item["kind"] == "request" and item.get("stance") == "requested":
                        text = f"Îți cere {ACTION_RO.get(item['action'], 'o acțiune')}: {item['object']}. {item['reason']}"
                    out.append({"level": "protective" if protective else "info", "text": text, "source": "gemini", "tentative": False})
    elif legacy:
        for tactic in legacy.get("tactics_detected", [])[:3]:
            if not any(tactic in r["text"] for r in out):
                out.append({"level": "attention", "text": tactic, "source": "rules", "tentative": False})
    for item in assessment["evidence"]:
        if item["status"] == "contradicted" and len(out) < 6:
            out.append({"level": "conflict", "text": item["reason"], "source": item["source"], "tentative": True})
    return out[:6]


def profile(assessment, interp, url_reports, reputation_status):
    evidence = assessment["evidence"]
    live = [i for i in evidence if i["status"] in {"supported", "tentative"}]

    def strongest(kinds):
        return max((i["tier"] for i in live if i["kind"] in kinds), default=0)

    request_tier = strongest({"request", "rules"})
    requested_low = any(i["kind"] == "request" and i.get("stance") == "requested" for i in live)
    tactics = [i for i in live if i["kind"] in {"tactic", "threat", "promise"}]
    identity = strongest({"identity"})
    claimed = interp and interp["claimed_sender"]["type"] not in {"none", "unknown_person"}
    url_tier = max((r["risk_points"] for r in url_reports), default=0)

    def level(value):
        return "strong" if value >= CRITICAL else "moderate" if value >= ALERT else "weak" if value > 0 else "none"

    reputation_level = {"threat_match": "strong", "no_known_match": "no_match"}.get(
        reputation_status, "not_checked" if url_reports else "not_applicable")
    return [
        {"key": "request", "label": "Ce ți se cere", "level": level(request_tier) if request_tier else "weak" if requested_low else "none",
         "note": "Cereri de date secrete, bani, acces sau documente."},
        {"key": "identity", "label": "Identitate pretinsă", "level": level(identity) if identity else
         ("weak" if claimed else "none" if interp else "not_checked"),
         "note": "Compararea organizației invocate cu destinația linkurilor."},
        {"key": "pressure", "label": "Presiune și manipulare",
         "level": "strong" if len(tactics) >= 3 else "moderate" if len(tactics) == 2 else "weak" if tactics else
         ("none" if interp else "not_checked"), "note": "Frică, grabă, secret, momeli."},
        {"key": "link", "label": "Link și domeniu", "level": (level(url_tier) if url_tier else "none") if url_reports else "not_applicable",
         "note": "Analiză statică: linkurile nu au fost deschise."},
        {"key": "reputation", "label": "Reputație externă", "level": reputation_level,
         "note": "Google Web Risk, dacă este configurat."},
        {"key": "protective", "label": "Context protector",
         "level": "present" if any(i["kind"] == "protective" for i in live) or any(
             i["kind"] == "request" and i["status"] == "context" for i in evidence) else ("none" if interp else "not_checked"),
         "note": "Avertismente, exemple, instrucțiuni obișnuite."},
    ]


def stages(assessment, interp, url_reports):
    """The classic scam pattern. Only mapped when the result is an alert or unresolved: for a
    low/marketing/protective result a promotion with a link must not read as "part of a scam"."""
    known = interp is not None
    if assessment["label"] not in {"critical", "suspicious", "inconclusive"}:
        return [{"key": k, "label": label, "on": False, "known": known if k in {"bait", "pressure"} else True}
                for k, label in (("bait", "Momeală"), ("pressure", "Presiune"), ("request", "Cerere"), ("trap", "Canal controlat"))]
    evidence = assessment["evidence"]
    live = [i for i in evidence if i["status"] in {"supported", "tentative"}]
    bait = any(i["kind"] in {"promise", "threat"} for i in live) or any(i.get("tactic") == "reward_bait" for i in live)
    pressure = any(i["kind"] == "tactic" for i in live)
    request = any(i["kind"] in {"request", "rules"} and i["tier"] >= ALERT for i in live)
    trap = any(i.get("tactic") == "channel_switch" for i in live) or any(
        i["kind"] == "request" and i.get("stance") == "requested"
        and i.get("destination_kind") in {"contact", "link_unverified", "link_deceptive"} for i in evidence) or (
        not known and any(r["risk_points"] >= ALERT for r in url_reports))
    return [{"key": "bait", "label": "Momeală", "on": bait, "known": known},
            {"key": "pressure", "label": "Presiune", "on": pressure, "known": known},
            {"key": "request", "label": "Cerere", "on": request, "known": True},
            {"key": "trap", "label": "Canal controlat", "on": trap, "known": True}]


def recommendations(assessment):
    label = assessment["label"]
    mechanism = assessment.get("mechanism")
    if label in {"critical", "suspicious"}:
        group = mechanism_group(mechanism["category"]) if mechanism else "generic"
        steps = list(RECOMMENDATIONS[group])
        if group != "link" and any(i["kind"] == "url" and i["tier"] >= ALERT for i in assessment["evidence"]):
            steps.insert(1, RECOMMENDATIONS["link"][0])
        steps.append("Raportează încercarea la DNSC, la numărul 1911, și apoi șterge mesajul." if label == "critical"
                     else "Dacă se confirmă că e o înșelătorie, o poți raporta la DNSC (1911).")
        steps.append("Avertizează o persoană apropiată: mesajele de acest fel vin des în valuri.")
        return steps
    if label == "inconclusive":
        return ["Nu trimite bani, coduri sau documente pe baza acestui mesaj.",
                "Verifică expeditorul pe un canal pe care îl cunoști deja (aplicația oficială, numărul de pe card sau de pe site).",
                "Poți relua analiza mai târziu, când verificarea semantică este disponibilă."]
    if label == "protective":
        return ["Mesajul pare informativ. Nu e nevoie să răspunzi.",
                "Dacă totuși cere o acțiune, fă-o doar din aplicația sau site-ul oficial, deschis de tine."]
    steps = ["Nu am găsit semne clare de înșelătorie, dar asta nu confirmă expeditorul.",
             "Dacă mesajul îți cere ceva neașteptat, verifică printr-un canal pe care îl cunoști deja."]
    if any(i["kind"] in {"identity", "url"} and 0 < i["tier"] < ALERT for i in assessment["evidence"]):
        steps.append("Linkul nu este pe un domeniu cunoscut al organizației. Dacă ai dubii, intră direct din aplicația "
                     "sau de pe site-ul oficial, nu din link.")
    return steps


SCENARIOS = {
    "secrets": [
        ("Momeala", "Mesajul creează un motiv să acționezi: un cont blocat, un colet, o plată de primit."),
        ("Cererea", "Ți se cere {object}{where}."),
        ("Ce poate face escrocul", "Cu astfel de date, un escroc poate încerca să intre în cont sau să confirme plăți în numele tău."),
        ("Consecința tipică", "Banii pot pleca rapid, iar recuperarea devine dificilă dacă nu anunți banca imediat."),
    ],
    "access": [
        ("Pretextul", "Ți se spune că trebuie rezolvată o problemă tehnică sau de securitate."),
        ("Cererea", "Ți se cere {object}{where}."),
        ("Ce poate face escrocul", "Cu acces sau cu o aprobare dată de tine, poate vedea ecranul, intra în conturi sau confirma operațiuni."),
        ("Consecința tipică", "Operațiunile pot părea făcute chiar de tine, ceea ce îngreunează contestarea."),
    ],
    "pay_first": [
        ("Promisiunea", "Ți se promite un beneficiu: bani, un premiu, un împrumut, un job sau un produs."),
        ("Condiția", "Înainte de beneficiu, ți se cere {object}."),
        ("Escaladarea", "În scheme de acest tip, după prima plată apar de obicei alte taxe „obligatorii”."),
        ("Consecința tipică", "Beneficiul nu sosește, iar sumele plătite se recuperează greu."),
    ],
    "family": [
        ("Contactul", "Cineva se prezintă drept o persoană apropiată, adesea de pe un număr nou."),
        ("Cererea", "Ți se cere {object}, de obicei urgent și uneori cu rugămintea să nu spui nimănui."),
        ("Transferul", "Banii trimiși ajung într-un cont controlat de escroc și sunt mutați repede."),
        ("Repetarea", "Dacă prima cerere reușește, de multe ori urmează alta."),
    ],
    "redirect": [
        ("Pretextul", "Ți se spune că s-au schimbat datele de plată ale unui furnizor sau ale unei persoane cunoscute."),
        ("Cererea", "Ți se cere {object}."),
        ("Plata", "Plata ajunge într-un cont controlat de escroc, nu la destinatarul real."),
        ("Consecința tipică", "Diferența se observă târziu, când destinatarul real cere banii."),
    ],
    "link": [
        ("Momeala", "Mesajul invocă o firmă sau o instituție și un motiv de acțiune: livrare, cont, plată."),
        ("Linkul", "Ți se cere să deschizi {domain}."),
        ("Ce urmează de obicei", "Pagini de acest tip cer de obicei date de card, parole sau coduri, sub pretextul unei verificări sau taxe."),
        ("Consecința tipică", "Datele introduse ajung la escroc și pot fi folosite imediat."),
    ],
    "threat": [
        ("Amenințarea", "Mesajul invocă o consecință gravă: amendă, dosar, expunere."),
        ("Cererea", "Ți se cere {object}."),
        ("Presiunea", "Termenul scurt are rolul să te împiedice să verifici."),
        ("Consecința tipică", "Plata nu oprește nimic; de obicei urmează alte cereri."),
    ],
    "generic": [
        ("Momeala", "Mesajul creează un motiv ca să acționezi repede."),
        ("Cererea", "Ți se cere o acțiune: un link, o plată, un cod sau un răspuns."),
        ("Canalul controlat", "Discuția este mutată acolo unde escrocul controlează informația."),
        ("Consecința tipică", "Datele sau banii ajung la escroc."),
    ],
}
REAL = {
    "secrets": "O bancă sau o firmă reală nu îți cere prin mesaj parola, PIN-ul, CVV-ul sau codurile primite prin SMS.",
    "access": "Nicio bancă sau firmă nu îți cere să instalezi programe de control de la distanță sau să aprobi operațiuni pe care nu le-ai început tu.",
    "pay_first": "Un câștig, un împrumut sau un job real nu cere taxe plătite în avans prin transfer, carduri cadou sau cripto.",
    "family": "O rudă adevărată nu se supără dacă o suni pe numărul vechi ca să verifici.",
    "redirect": "Schimbarea datelor de plată se confirmă întotdeauna pe un canal cunoscut dinainte.",
    "link": "Firmele reale te lasă să verifici în aplicația sau pe site-ul lor oficial, deschis de tine.",
    "threat": "Instituțiile comunică amenzile și datoriile prin canale oficiale, verificabile, nu prin presiune în mesaje.",
    "generic": "Un mesaj legitim te lasă să verifici în ritmul tău, pe canale oficiale.",
}


def scenario(assessment, interp, url_reports):
    """Educational, hypothetical. Only built when an alert-level mechanism is established."""
    mechanism = assessment.get("mechanism")
    if assessment["label"] not in {"critical", "suspicious"} or not mechanism:
        return None
    established = mechanism["established"] and mechanism["category"] != "other_suspicious_mechanism"
    group = mechanism_group(mechanism["category"]) if established else "generic"
    requested = next((i for i in sorted(assessment["evidence"], key=lambda i: -i["tier"])
                      if i["kind"] == "request" and i["status"] == "supported" and i.get("stance") == "requested"), None)
    # Personalise only with a link the evidence actually implicates; never present an
    # official (catalog) domain as the trap.
    ranked = sorted(assessment["evidence"], key=lambda i: -i["tier"])
    host = next((i.get("destination_host") for i in ranked if i["kind"] == "request" and i.get("stance") == "requested"
                 and i.get("destination_kind") in {"link_unverified", "link_deceptive"} and i.get("destination_host")), None)
    if host is None:
        flagged = {i.get("host") for i in ranked if i["kind"] in {"url", "identity", "reputation"} and i["tier"] > 0}
        host = next((r["registrable_domain"] or r["domain"] for r in url_reports if r["domain"] in flagged), None)
    obj = requested["object"] if requested else "o acțiune"
    if group == "link" and not host:
        group = "generic"
    where = " printr-o adresă din mesaj" if requested and requested.get("destination_kind", "").startswith("link") else ""
    fill = {"object": obj, "where": where, "domain":
            f"adresa {host} (AXA nu a deschis-o)" if host else "o adresă din mesaj"}
    return {
        "mode": "mechanism_based" if established else "generic_example",
        "title": "Cum ar putea evolua această înșelătorie" if established else "Exemplu general: cum evoluează de obicei o înșelătorie",
        "mechanism": mechanism["label"] if established else None,
        "steps": [{"title": t, "text": s.format(**fill)} for t, s in SCENARIOS[group]],
        "real_world": REAL[group],
        "disclaimer": ("Scenariu educativ, ipotetic. AXA nu a deschis linkurile, nu a văzut nicio pagină și nu poate "
                       "prezice ce ar face un anumit escroc." if established else
                       "Exemplu general, nu o reconstituire a acestui mesaj. Mecanismul exact nu a putut fi stabilit."),
        "personalized_from": [x for x in (("cerere validată" if requested else None), ("domeniu analizat static" if host else None)) if x],
    }


def headline(assessment):
    title, action = HEADLINES[assessment["label"]]
    return title, action


def summary(assessment, interp, url_reports, ai_status):
    label = assessment["label"]
    parts = []
    if interp and interp["claim_summary"]:
        parts.append(interp["claim_summary"])
    mechanism = assessment.get("mechanism")
    if mechanism and label in {"critical", "suspicious"}:
        parts.append(f"Mecanism: {mechanism['label'].lower()}.")
    if label == "inconclusive":
        parts.append("Dovezile disponibile sunt insuficiente sau contradictorii, așa că nu afișăm un scor.")
    if not interp and ai_status.get("status") != "completed":
        parts.append("Interpretarea semantică AI nu a fost disponibilă; rezultatul se bazează pe verificări locale.")
    parts.append("Identitatea expeditorului rămâne neverificată.")
    return " ".join(parts)


def share_text(assessment, title):
    """Privacy-safe: no message text, numbers, codes or links."""
    mechanism = assessment.get("mechanism")
    lines = ["Am verificat un mesaj cu AXA Scam Detector.", f"Rezultat: {title}."]
    if mechanism and assessment["label"] in {"critical", "suspicious"}:
        lines.append(f"Seamănă cu: {mechanism['label'].lower()}.")
    lines.append("Dacă primești ceva asemănător, nu apăsa linkuri și nu trimite bani, coduri sau poze cu cardul ori actele. "
                 "Verifică direct la sursă, pe un canal cunoscut.")
    return "\n".join(lines)


# ------------------------------------------------------------------ v2.1 UI adapter --
# Additive, presentation-only. Maps the policy's existing labels to the four categorical
# verdicts shown in the interface. It never changes a label, a score or a threshold.
UI_TITLES = {
    "strong": "Indicii puternice de tentativă de fraudă",
    "suspect": "Mesaj suspect",
    "no_clear_signs": "Nu am găsit indicii clare de fraudă",
    "unable": "Nu putem evalua suficient mesajul",
}
UI_STATE = {"critical": "strong", "suspicious": "suspect", "low": "no_clear_signs", "marketing": "no_clear_signs",
            "protective": "no_clear_signs", "inconclusive": "unable"}
UI_QUALIFIER = {"marketing": "Pare un mesaj comercial.", "protective": "Pare un avertisment sau o informare."}
UI_ACTIONS = {
    "secrets": ("Nu trimite și nu introduce niciun cod, parolă, PIN sau date de card.",
                "Dacă vrei să verifici contul, deschide singur aplicația oficială."),
    "access": ("Nu instala nimic și nu aproba nicio cerere pe care n-ai pornit-o tu.",
               "Închide conversația. Sună instituția la un număr pe care îl știi deja."),
    "pay_first": ("Nu plăti nicio taxă ca să primești ceva.",
                  "Un câștig, un credit sau un job real nu cere bani în avans."),
    "family": ("Nu trimite bani până nu vorbești cu persoana la numărul ei vechi.",
               "Pune o întrebare la care doar ea ar ști răspunsul."),
    "redirect": ("Nu schimba contul în care plătești pe baza acestui mesaj.",
                 "Confirmă schimbarea sunând la un număr cunoscut dinainte."),
    "link": ("Nu deschide linkul din mesaj.",
             "Intră singur în aplicația sau pe site-ul oficial al organizației."),
    "threat": ("Nu plăti și nu răspunde la amenințare.",
               "Verifică direct la instituție, pe canalele ei oficiale."),
    "generic": ("Nu acționa pe baza mesajului.",
                "Verifică expeditorul pe un canal pe care îl cunoști deja."),
}
# Actions keyed by the decisive requested action, when it is more specific than the mechanism family.
UI_ACTION_BY_REQUEST = {
    "call_number": ("Nu suna la numărul din mesaj.",
                    "Dacă vrei să verifici, sună organizația la un număr de pe site-ul ei oficial sau de pe card."),
    "reply_or_contact": ("Nu răspunde la mesaj.", "Verifică expeditorul pe un canal pe care îl cunoști deja."),
    "move_to_other_channel": ("Nu continua discuția pe alt canal (WhatsApp, Telegram).",
                              "Verifică expeditorul pe un canal pe care îl cunoști deja."),
}
UI_RECOVERY = {"secrets": ["code", "password", "card"], "access": ["installed", "code"], "pay_first": ["paid"],
               "family": ["paid"], "redirect": ["paid"], "link": ["opened", "card", "password"],
               "threat": ["paid"], "generic": ["opened", "paid"]}
WHERE_RO = {"contact": "direct expeditorului", "link_deceptive": "pe o adresă care imită o organizație",
            "link_unverified": "pe o adresă al cărei proprietar nu este confirmat",
            "link_official": "pe un domeniu cunoscut", "unclear": "", "own": ""}
AI_GAP = {"not_configured": "nu este configurată pe acest server", "failed": "nu a răspuns"}


def _first_sentence(text):
    text = (text or "").strip()
    for stop in (". ", "! ", "? "):
        if stop in text:
            return text[:text.index(stop) + 1]
    return text if text.endswith((".", "!", "?")) or not text else text + "."


def _decisive(assessment):
    top = (assessment.get("policy") or {}).get("strongest") or {}
    return next((i for i in assessment["evidence"] if i["id"] == top.get("id")), None)


def _alert_reason(assessment):
    if (assessment.get("policy") or {}).get("converged"):
        return "Mai multe indicii independente, fiecare slab, apar împreună și cer prudență."
    item = _decisive(assessment)
    if not item:
        return "Am găsit indicii care cer prudență."
    if item["kind"] == "request":
        where = WHERE_RO.get(item.get("destination_kind") or "", "")
        if item["action"] == "call_number" and item.get("destination_kind") == "contact":
            where = "dat chiar în mesaj"
        verb = ACTION_RO.get(item["action"], "o acțiune")
        obj = item.get("object") or ""
        detail = f" ({obj})" if obj and obj.lower() not in verb.lower() else ""
        return f"Mesajul îți cere {verb}{detail}{(' ' + where) if where else ''}."
    if item["kind"] == "rules":
        found = (item.get("reason") or "").replace("Regulile locale:", "").strip().rstrip(".").lower()
        return f"Verificările locale au găsit: {found}." if found else "Verificările locale au găsit indicii de fraudă."
    if item["kind"] == "reading":
        support = [i for i in assessment["evidence"] if i["id"] in set(item.get("support") or [])]
        cues = list(dict.fromkeys(i.get("label", "").lower() for i in support if i.get("label")))[:2]
        label = MECHANISM_LABELS.get(item.get("mechanism"), "înșelătorie").lower()
        joined = " și ".join(cues)
        return (f"Textul combină {joined}, ca într-o schemă de tip „{label}”." if cues else
                f"Textul urmează tiparul unei scheme de tip „{label}”.")
    return _first_sentence(item.get("reason"))


SPECTRUM_ZONES = (
    {"key": "clear", "label": "Fără indicii clare", "from": 0, "to": ALERT},
    {"key": "suspect", "label": "Suspect", "from": ALERT, "to": CRITICAL},
    {"key": "strong", "label": "Indicii puternice", "from": CRITICAL, "to": 100},
)


def spectrum(assessment, partial):
    """Green→amber→red scale for the interface. Zones use the policy's own thresholds
    (ALERT, CRITICAL), so the marker's zone always matches the verdict label.

    Never invents a position: no marker when the risk is unestimated, and no green marker
    when the AI interpretation did not run (a missing check is never shown as reassurance)."""
    estimate = assessment.get("risk_estimate")
    zones = [dict(z) for z in SPECTRUM_ZONES]
    if estimate is None:
        return {"zones": zones, "status": "unestimated", "position": None, "zone": None, "indicator": None,
                "note": "Nu putem poziționa mesajul pe scală: dovezile sunt insuficiente sau contradictorii.",
                "label": "Riscul nu a putut fi estimat, așa că mesajul nu este poziționat pe scală."}
    value = max(0, min(100, int(round(estimate))))
    zone = "strong" if value >= CRITICAL else "suspect" if value >= ALERT else "clear"
    if partial and zone == "clear":
        return {"zones": zones, "status": "partial_unplaced", "position": None, "zone": None, "indicator": None,
                "note": "Fără interpretarea AI nu poziționăm mesajul în zona verde.",
                "label": "Analiză parțială: verificările locale nu au găsit indicii, dar mesajul nu este poziționat pe scală."}
    name = next(z["label"] for z in zones if z["key"] == zone)
    return {"zones": zones, "status": "placed", "position": value, "zone": zone, "indicator": value,
            "note": None,
            "label": f"Pe scala de risc, mesajul este în zona „{name}” (indicator orientativ {value} din 100, nu o probabilitate)."}


def ui(assessment, interp, ai_status, url_reports):
    """Additive presentation contract for the interface (analysis.ui)."""
    label = assessment["label"]
    state = UI_STATE.get(label, "unable")
    mechanism = assessment.get("mechanism")
    group = mechanism_group(mechanism["category"]) if mechanism else "generic"
    partial = ai_status.get("status") != "completed"
    reasons = set(assessment.get("confidence_reasons") or [])
    if state in {"strong", "suspect"}:
        reason = _alert_reason(assessment)
        decisive = _decisive(assessment) or {}
        if group == "link" and not any(r.get("domain") for r in url_reports):
            group = "generic"  # a "link" family scheme with no link: advise on what the message actually asks
        action, detail = UI_ACTION_BY_REQUEST.get(decisive.get("action")) if decisive.get("kind") == "request" and \
            decisive.get("action") in UI_ACTION_BY_REQUEST else UI_ACTIONS[group]
        if group != "link" and any(i["kind"] in {"url", "identity", "reputation"} and i["tier"] >= ALERT
                                   for i in assessment["evidence"]):
            detail = "Nu deschide nici linkul din mesaj. " + detail
        recovery = list(UI_RECOVERY[group])
        if decisive.get("action") == "call_number":
            recovery = ["called", "paid"]
    elif state == "unable":
        if "rules_ai_conflict" in reasons:
            reason = "Interpretarea AI și regulile locale citesc mesajul diferit, așa că nu dăm un verdict."
        elif any(i["kind"] == "request" and i["status"] in {"tentative", "contradicted"} for i in assessment["evidence"]):
            reason = "O cerere sensibilă din mesaj nu a putut fi confirmată în textul lui."
        elif "ai_reading_without_grounded_mechanism" in reasons:
            reason = "Interpretarea AI are o suspiciune, dar nu a putut arăta în text elementul înșelător."
        elif any(r.get("inspection_status") == "invalid_url" for r in url_reports):
            reason = "Mesajul conține o adresă care nu poate fi interpretată, iar textul nu ajunge pentru o evaluare."
        elif partial:
            reason = "Fără interpretarea AI, verificările locale nu pot evalua acest mesaj."
        else:
            reason = "Dovezile sunt insuficiente sau contradictorii."
        action = "Nu trimite bani, coduri sau date până nu verifici expeditorul pe un canal cunoscut."
        detail = "Lipsa unui verdict nu înseamnă că mesajul e sigur sau periculos."
        recovery = ["opened", "code", "paid"]
    else:
        if label == "protective":
            reason = "Mesajul pare un avertisment sau o informare și nu îți cere nimic periculos."
            action, detail = "Nu e nevoie să faci nimic.", "Dacă totuși vrei să verifici ceva, deschide singur aplicația oficială."
        else:
            reason = ("Regulile locale nu au găsit indicii; interpretarea AI nu a fost disponibilă." if partial else
                      "În ce am putut verifica nu apare o cerere periculoasă și nici un link care imită o organizație.")
            action = ("Dacă te interesează oferta, intră direct din aplicația sau de pe site-ul oficial." if label == "marketing" else
                      "Dacă nu te așteptai la mesaj, verifică direct în aplicația sau pe site-ul oficial.")
            detail = "Asta nu confirmă cine a trimis mesajul."
        recovery = []
    return {
        "state": state, "title": UI_TITLES[state], "qualifier": UI_QUALIFIER.get(label),
        "mechanism": mechanism["label"] if mechanism and state in {"strong", "suspect"} else None,
        "reason": reason, "action": action, "action_detail": detail,
        "recovery_suggested": recovery,
        "partial": partial,
        "partial_note": (f"Interpretarea AI {AI_GAP.get(ai_status.get('status'), 'nu a fost disponibilă')}. "
                         "Rezultatul folosește doar verificările locale, care recunosc mai puține tipuri de înșelătorii.") if partial else None,
        "source_label": "Verdictul AXA, din politica de decizie (nu o probabilitate).",
        "spectrum": spectrum(assessment, partial),
    }
