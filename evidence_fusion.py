"""Ground semantic observations in the input and score mechanisms once."""
import re
from bisect import bisect_left
from dataclasses import dataclass

from action_context import (
    ACCESS_INTENTS, CHANNEL, DELIVERY_ACTION, HARMFUL_ACTIONS, INDICATORS, OWN_ACTION, PAYOUT,
    REFERENCE, REPORT_CUE, REQUEST, TRANSFER, VALUE, extract_frames, object_labels, overlaps,
    rule_slice, scope_reason,
)
from database import brand_key
from semantic_analysis import Observation, observe, utf16_offset
from text_analysis import (
    ACCOUNT, CARD, CODE_CLUE, DEPENDENCY, DOCUMENT, FAMILY, FEE,
    KEEP_SECRET, MONEY, NUMBER_CHANGE, PHOTO, PROMISE, PROMO, REPORTED, REWARD,
    SENSITIVE, VERIFY,
)

SENSITIVE_INTENTS = {"request_credentials", "request_card_photo", "request_sensitive_documents"}
REQUEST_INTENTS = HARMFUL_ACTIONS
PROTECTIVE_INTENTS = {"protective_warning", "educational_example"}
OFFER_INTENTS = {"commercial_solicitation", "reward_offer"}
PAYOUT_CUE = re.compile(r"\b(?:primi\w*|incas\w*|debloca\w*|credita\w*|ramburs\w*|despagub\w*|intra\s+(?:bani\w*|in\s+cont)|viram)\b")
PAYMENT_CUE = re.compile(r"\b(?:plat\w*|achit\w*|vira\w*|virament\w*|transfer\w*|depun\w*)\b")
NEGATIVE_CUE = re.compile(r"\b(?:nu|fara|niciun\w*|niciodata)\b")
ACTION_TO_OTHER = re.compile(
    r"\b(?:imi|mi|ne|noua|aici|chat|raspunde\w*|spune\w*|citest\w*|"
    r"trimit\w*|furniz\w*|transmit\w*|atasa\w*|incarca\w*|divulg\w*|"
    r"comunic\w*|scrie\w*|arata\w*|da-mi|introdu\w*|tastea\w*|sharing)\b"
)
PROMO_ACTION = re.compile(r"\b(?:cumpar\w*|achizition\w*|ofert\w*|vind\w*|comand\w*|livrar\w*|produs\w*)\b")
ASK_HINT = re.compile(r"\b(?:te\s+rog|va\s+rugam|poti|puteti|trebuie|astept\w*|am\s+nevoie|solicit\w*)\b")
IMPLIED_REQUEST = re.compile(r"\b(?:necesar\w*|este\s+nevoie\s+de|am\s+avea\s+nevoie|fa\s+o\s+copie|ar\s+ajuta|lasa\w*|pune\w*)\b")
VERIFICATION_CUE = re.compile(r"\b(?:direct|oficial\w*|din aplicati\w*)\b")
PRESSURE_CUE = re.compile(r"\b(?:urgent\w*|imediat\w*|acum|repede|termen\w*|blocat\w*|suspendat\w*|expir\w*|astazi|azi)\b")
MONEY_PAYOUT = re.compile(r"\b(?:sum\w*|bani\w*|fond\w*|premi\w*|mostenir\w*|ramburs\w*|restitu\w*|\d+\s*(?:de\s+)?(?:lei|ron|euro|eur))\b")


def is_protected(language, start, end):
    return any(overlaps(span, start, end) for span in language["protected"])


@dataclass(frozen=True)
class EvidenceReview:
    observation: Observation
    status: str
    reason: str
    unresolved: bool = False

    def public(self, text):
        return {**self.observation.public(text), "status": self.status, "reason": self.reason,
                "unresolved": self.unresolved}


def review_observations(text, language, local, gemini, frames):
    reviews = []
    for item in (*local.observations, *local.tentative, *gemini):
        label, start, end = item.label, item.start, item.end
        if not (0 <= start < end <= len(text)) or text[start:end] != item.evidence_text:
            # Never echo a quotation whose claimed offsets fail.
            reviews.append(EvidenceReview(item, "rejected", "invalid_original_span"))
            continue
        snippet = rule_slice(language, start, end)
        related = [frame for frame in frames if frame.label == label and overlaps((frame.start, frame.end), start, end)]
        requested = any(frame.direction == "requested" for frame in related)
        blocked = scope_reason(language, start, end, snippet)
        weak = item in local.tentative
        if label in REQUEST_INTENTS and (blocked or (OWN_ACTION.search(snippet) and label in ACCESS_INTENTS)):
            mixed_scope = item.scope == "whole_message" and requested
            reviews.append(EvidenceReview(item, "tentative" if mixed_scope else "contradictory",
                                          "mixed_scope_needs_localization" if mixed_scope else blocked or "self_initiated_action",
                                          mixed_scope and not weak))
            continue

        targets = object_labels(snippet)
        scoped = item.scope != "whole_message"
        action = bool(ACTION_TO_OTHER.search(snippet) or REQUEST.search(snippet) or IMPLIED_REQUEST.search(snippet)
                      or (CHANNEL.search(snippet) and DELIVERY_ACTION.search(snippet)))
        supported = False
        unresolved = False
        reason = "insufficient_context"

        if label in SENSITIVE_INTENTS:
            # Reuse the exact quote's target and direction together, including when
            # the target occurs before the action. A nearby protected target
            # does not establish the object of an otherwise ambiguous request.
            preceding_targets = {frame.label for frame in frames if frame.label in SENSITIVE_INTENTS
                                 and frame.direction != "discouraged_or_reported" and 0 <= start - frame.end <= 95}
            referent = scoped and action and REFERENCE.search(snippet) and preceding_targets == {label}
            target = label in targets or (scoped and requested) or bool(referent)
            supported = scoped and target and (requested or action)
            reason = "whole_message_needs_localization" if not scoped else (
                "target_not_grounded" if not target else "recipient_or_action_unclear")
            unresolved = not weak and not supported and (scoped or bool(targets) or action)
        elif label in ACCESS_INTENTS:
            supported = scoped and label in targets and requested
            reason = "authorization_target_or_direction_unclear"
            unresolved = not weak and not supported and (scoped or bool(targets))
        elif label == "request_money":
            supported = label in targets and (action or TRANSFER.search(snippet) or requested)
            reason = "payment_target_or_direction_unclear"
            unresolved = not weak and not supported and (requested or bool(targets and action))
        elif label == "advance_fee_condition":
            supported = (bool(targets & {"request_money"}) and
                         bool((FEE.search(snippet) or VALUE.search(snippet)) and
                              (DEPENDENCY.search(snippet) or PAYOUT.search(snippet))))
            reason = "value_or_dependency_unclear"
            unresolved = not weak and not supported and bool(targets or PAYOUT.search(snippet))
        elif label == "account_verification_request":
            supported = label in targets and not VERIFICATION_CUE.search(snippet)
            reason = "account_target_or_direction_unclear"
            unresolved = not weak and not supported and scoped and bool(VERIFY.search(snippet))
        else:
            supported = bool({
                "promise_payout": lambda: (PROMISE.search(snippet) or PAYOUT_CUE.search(snippet) or PAYOUT.search(snippet))
                and (MONEY_PAYOUT.search(snippet) or VALUE.search(snippet)),
                "family_impersonation": lambda: FAMILY.search(snippet) or NUMBER_CHANGE.search(snippet),
                "organization_impersonation_claim": lambda: item.claimed_identity
                or re.search(r"\b(?:sunt\w*\s+de\s+la|reprezint\w*|departament\w*|echipa)\b", snippet),
                "urgency_or_pressure": lambda: PRESSURE_CUE.search(snippet) and not NEGATIVE_CUE.search(snippet),
                "unavailable_for_call": lambda: NEGATIVE_CUE.search(snippet)
                and re.search(r"\b(?:apel\w*|telefon\w*|vorb\w*|suna\w*)\b", snippet),
                "protective_warning": lambda: KEEP_SECRET.search(snippet) or (blocked and bool(targets)),
                "educational_example": lambda: REPORTED.search(snippet) or REPORT_CUE.search(snippet) or is_protected(language, start, end),
                "commercial_solicitation": lambda: PROMO_ACTION.search(snippet) or PROMO.search(snippet),
                "reward_offer": lambda: REWARD.search(snippet) or PROMISE.search(snippet),
            }.get(label, lambda: False)())
        if weak:
            reviews.append(EvidenceReview(item, "tentative", "model_entailment_ambiguous",
                                          label in REQUEST_INTENTS and requested))
        elif supported:
            reviews.append(EvidenceReview(item, "supported", "scoped_context_corroborated"))
        elif label in REQUEST_INTENTS:
            reviews.append(EvidenceReview(item, "tentative", reason, unresolved))
        else:
            reviews.append(EvidenceReview(item, "rejected", reason))
    return tuple(reviews)


def fee_dependency(language, payments, payout, proposed):
    """Find positive payment-before-payout linkage, including across nearby clauses."""
    if not payments or not payout:
        return None
    offsets = language["offsets"]
    text = language["active"]
    benefit = lambda chunk: PAYOUT_CUE.search(chunk) or PAYOUT.search(chunk)
    opposite_order = False
    for payment in payments:
        left, right = bisect_left(offsets, payment[0]), bisect_left(offsets, payment[1])
        # The action clause is a much safer anchor than a fee word elsewhere.
        lower = max(0, left - 130)
        upper = min(len(text), right + 150)
        window = text[lower:upper]
        for connector in DEPENDENCY.finditer(window):
            pos = lower + connector.start()
            following = text[lower + connector.end():upper]
            preceding = text[lower:pos]
            if connector.lastgroup == "after":
                if pos < left and benefit(preceding) and left - pos < 100:
                    return offsets[pos], payment[1]
                if pos >= left and benefit(following):
                    opposite_order = True
            elif connector[0] in {"mai intai", "in prealabil", "first"} and abs(pos - left) < 75:
                return min(payment[0], offsets[pos]), max(payment[1], offsets[lower + connector.end()])
            elif pos >= left and (trigger := benefit(following)) and not NEGATIVE_CUE.search(following[:65]):
                return payment[0], offsets[min(upper, lower + connector.end() + trigger.end())]
            elif pos < left and benefit(text[lower + connector.end():left]) and left - pos < 100:
                return offsets[pos], payment[1]
        if (FEE.search(window) or VALUE.search(window)) and proposed and (PAYMENT_CUE.search(window) or TRANSFER.search(window)) and not opposite_order:
            # The model contributes the dependency. An actual payment and payout are still required.
            return proposed.start, proposed.end
    return None


def linked_bank_link(language, reports, links, verifications):
    claim_keys = {brand_key(name) for name in language["context"]["claimed_entities"]}
    if not claim_keys:
        return None
    for report in reports:
        typo = report["typosquatting"]
        if not typo.get("is_typosquatting") or brand_key(typo.get("brand", "")) not in claim_keys:
            continue
        for url, left, right in links:
            if url != report["original_url"] or is_protected(language, left, right):
                continue
            same_clause = next((span for span in language["clauses"] if overlaps(span, left, right)), None)
            if not same_clause:
                continue
            explicit_link_action = same_clause in language["link_actions"]
            context = rule_slice(language, *same_clause)
            if (any(overlaps(same_clause, *verify) for verify in verifications)
                    or (explicit_link_action and VERIFY.search(context))
                    or (explicit_link_action and any(0 <= left - verify[1] < 115 for verify in verifications))):
                return report
    return None


def linked_domain_reference(language, reports, links):
    """A quoted-looking hostname embedded in another active destination is a clue, not ownership."""
    reference_hosts = {u["domain"] for u in reports if u.get("protocol") is None and u["registrable_domain"]}
    for report in reports:
        host = report["domain"]
        if not host or not report["registrable_domain"]:
            continue
        for ref in sorted(reference_hosts):
            if ref == report["registrable_domain"] or not host.startswith(ref + "."):
                continue
            if any(url == report["original_url"] and not is_protected(language, left, right)
                   and any(overlaps(span, left, right) for span in language["link_actions"])
                   for url, left, right in links):
                return {"reference_in_message": ref, "actual_hostname": host,
                        "registrable_domain": report["registrable_domain"], "source": "static_url"}
    return None


def fuse(text, language, reports, links, local, gemini=()):
    """Keep legacy scores and fields while deriving evidence-based mechanisms."""
    original_rules = language["observations"]
    frames = extract_frames(language)
    reviews = review_observations(text, language, local, gemini, frames)
    inferred = [review.observation for review in reviews if review.status == "supported"]
    deterministic = [
        observe(text, frame.label, "rules", (frame.start, frame.end), "clause")
        for frame in frames if frame.explicit and frame.end - frame.start <= 650
        and not any(item.label == frame.label and overlaps((item.start, item.end), frame.start, frame.end)
                    for item in original_rules)
    ]
    rules = (*original_rules, *deterministic)
    all_observations = [*rules, *inferred]
    by_label = {}
    for item in all_observations:
        by_label.setdefault(item.label, []).append(item)
    context = {**language["context"], "requested_actions": list(language["context"]["requested_actions"]),
               "contradictions": list(language["context"]["contradictions"])}
    tactics, highlights, mechanisms = list(language["tactics"]), list(language["highlights"]), []
    base, pressure = language["base_points"], language["pressure_points"]
    contextual_finance = list(context["financial_indicators"])
    direct = any(item.label in SENSITIVE_INTENTS for item in rules)

    def mark(mechanism, label, points, sources):
        nonlocal base
        base = max(base, points)
        if label not in tactics:
            tactics.append(label)
        mechanisms.append({"id": mechanism, "label": label, "sources": sorted(set(sources))})

    secret = [item for item in inferred if item.label in SENSITIVE_INTENTS]
    if direct or secret:
        grounded = [item for item in rules if item.label in SENSITIVE_INTENTS] + secret
        card_photo = any(item.label == "request_card_photo" for item in grounded)
        credential = any(item.label == "request_credentials" for item in grounded)
        if direct:
            extra = 70 if card_photo or credential else 52
        elif any(item.source == "local_nli" and item.label in {"request_credentials", "request_card_photo"}
                 and CHANNEL.search(rule_slice(language, item.start, item.end)) for item in secret):
            extra = 70
        else:
            # External model interpretation can add concern. It cannot establish a critical request alone.
            extra = 54 if card_photo or credential else 45
        mark("credential_disclosure" if card_photo or credential else "sensitive_documents",
             "Solicitare de date sensibile", extra, [item.source for item in grounded])
        mixed = context["sensitive_data_intent"] in {"discouraged", "mixed"} or any(
            warning.scope != "whole_message" and not any(overlaps((warning.start, warning.end), item.start, item.end)
                                                         for item in grounded)
            for warning in by_label.get("protective_warning", [])
        )
        context["sensitive_data_intent"] = "mixed" if mixed else "requested"
        if mixed and not context["contradictions"]:
            context["contradictions"].append("Avertismentul coexista cu o posibila solicitare de date.")

    for label in sorted(ACCESS_INTENTS):
        access = by_label.get(label, [])
        if access:
            mark("account_or_device_abuse", "Solicitare de aprobare a autentificării" if label == "request_login_approval"
                 else "Solicitare de acces la distanță", 58, [item.source for item in access])

    existing_actions = {(item["kind"], item["intent"]) for item in context["requested_actions"]}
    action_kinds = {"request_money": "payment", "account_verification_request": "account_or_link",
                    **dict.fromkeys(ACCESS_INTENTS, "account_or_device_access"),
                    **dict.fromkeys(SENSITIVE_INTENTS, "sensitive_data")}
    for item in sorted([*deterministic, *inferred], key=lambda item: item.scope == "whole_message"):
        kind = action_kinds.get(item.label)
        if not kind or (kind, "requested") in existing_actions or len(context["requested_actions"]) >= 12:
            continue
        if item.label in SENSITIVE_INTENTS and item.source != "rules" and item not in secret:
            continue
        context["requested_actions"].append({"kind": kind, "intent": "requested",
                                              "phrase": item.evidence_text, "source": item.source})
        existing_actions.add((kind, "requested"))

    payment_items = by_label.get("request_money", [])
    payments = list(dict.fromkeys([
        *language["payment_spans"], *((item.start, item.end) for item in payment_items if item.scope != "whole_message"),
        *((frame.action_start, frame.end) for frame in frames
          if frame.label == "request_money" and frame.direction == "requested" and frame.action_start is not None),
    ]))
    paid = bool(payments or (payment_items and not language["protected"]))
    if paid:
        base = max(base, 12)
    payout = by_label.get("promise_payout", [])
    if not payout:
        payout = [observe(text, "promise_payout", "rules", (start, end), "clause")
                  for start, end in language["clauses"] if end - start <= 650
                  and PAYOUT.search(rule_slice(language, start, end))
                  and (MONEY_PAYOUT.search(rule_slice(language, start, end)) or VALUE.search(rule_slice(language, start, end)))
                  and not scope_reason(language, start, end, rule_slice(language, start, end))]
    fee_claim = next((item for item in inferred if item.label == "advance_fee_condition"), None)
    dependency = fee_dependency(language, payments, payout, fee_claim)
    if dependency:
        support = {item.source for item in payment_items + payout}
        if fee_claim and (fee_claim.start, fee_claim.end) == dependency:
            support.add(fee_claim.source)
        else:
            support.add("rules")
            start, end = dependency
            if 0 < end - start <= 2400:
                all_observations.append(observe(text, "advance_fee_condition", "rules", dependency, "rule_span"))
        mark("advance_fee", "Posibila frauda cu plata in avans", 58, support)
        contextual_finance.append(text[dependency[0]:dependency[1]])

    family = by_label.get("family_impersonation", [])
    pressured = by_label.get("urgency_or_pressure", [])
    avoid_call = by_label.get("unavailable_for_call", [])
    if family and paid and (avoid_call or pressured):
        mark("family_impersonation", "Posibila impersonare a unei persoane apropiate", 48,
             [item.source for item in family + payment_items + avoid_call + pressured])
    if pressured and (paid or secret or mechanisms) and not pressure:
        pressure = 10
        tactics.append("Presiune de timp sau consecinte")

    verify_items = by_label.get("account_verification_request", [])
    verifications = [*language["verification"], *((i.start, i.end) for i in verify_items if i.scope != "whole_message")]
    bank_link = linked_bank_link(language, reports, links, verifications)
    reference_conflict = linked_domain_reference(language, reports, links)
    url_points = max((u["risk_points"] for u in reports), default=0)
    language_points = min(85, base + pressure)
    combo = max(0, 72 - language_points - url_points) if bank_link else 0
    if reference_conflict and not bank_link:
        combo = max(0, 54 - language_points - url_points)
        mark("organization_lookalike", "Referință de domeniu încorporată într-o altă destinație", 0, ["static_url", "rules"])
    if bank_link:
        mark("organization_lookalike", "Identitate pretinsa si link de verificare asemanator", 0,
             ["static_url", "rules", *(i.source for i in verify_items)])
    elif url_points >= 35 and "Pretext de livrare" in tactics:
        mark("delivery_pretext", "Pretext de livrare", 0, ["rules", "static_url"])
    threat_points = 90 if any(u.get("reputation", {}).get("status") == "threat_match" for u in reports) else None
    if threat_points:
        mark("listed_url_threat", "Adresă raportată de Google Web Risk", 0, ["google_web_risk"])
    score = max(min(100, language_points + url_points + combo), threat_points or 0)

    safety = any(label in by_label for label in PROTECTIVE_INTENTS)
    commercial = "commercial_solicitation" in by_label
    reward = "reward_offer" in by_label
    overlap = {i.label for i in rules} & {i.label for i in inferred if i.source == "local_nli"}
    disagreements = {review.observation.label for review in reviews
                     if review.observation.source == "local_nli" and review.status == "contradictory"}
    unresolved = [review for review in reviews if review.unresolved
                  and not any(item.label == review.observation.label
                              and overlaps((item.start, item.end), review.observation.start, review.observation.end)
                              for item in all_observations)]
    if unresolved and not disagreements and not overlap:
        disagreements = {review.observation.label for review in unresolved}
    agreement = ("mixed" if overlap else "disagreement") if disagreements else (
        "agreement" if overlap else "no_shared_findings"
    )
    if local.status not in {"completed", "partial"}:
        agreement = "not_compared"

    if score >= 70:
        risk_label, verdict = "critical", "RISC RIDICAT · INDICII PUTERNICE DE FRAUDĂ"
    elif score >= 35:
        risk_label, verdict = "suspicious", "MESAJ SUSPECT · VERIFICĂ SURSA"
    elif commercial:
        risk_label, verdict = "uncertain", "SOLICITARE COMERCIALĂ · VERIFICĂ OFERTA"
    elif safety or reward or local.status == "completed":
        risk_label, verdict = "uncertain", "INDICII LIMITATE · VERIFICĂ SURSA"
    else:
        risk_label, verdict = "uncertain", "ANALIZĂ NECONCLUDENTĂ · VERIFICĂ SURSA"
    assessment_label = (risk_label if risk_label != "uncertain" else "commercial_solicitation" if commercial
                        else "limited_indicators" if safety or reward or local.status == "completed" else "inconclusive")
    message_type = (mechanisms[0]["id"] if mechanisms else "commercial_solicitation" if commercial else
                    "reward_offer" if reward else "protective_or_educational" if safety else
                    "suspicious_link" if url_points >= 35 else "undetermined")
    if bank_link:
        summary = (f"Mesajul invocă {bank_link['typosquatting']['brand']} și cere verificarea. "
                   f"Domeniul înregistrabil al linkului este {bank_link['registrable_domain']}.")
    elif mechanisms:
        summary = "Indicii observate includ " + ", ".join(item["label"] for item in mechanisms) + "."
    elif url_points:
        strongest = max(reports, key=lambda u: u["risk_points"])
        summary = f"Adresa {strongest['domain']} prezintă indicii tehnice care merită verificate."
    elif commercial:
        summary = "Mesajul promovează un produs sau serviciu. Oferta și caracterul nesolicitat rămân neconfirmate."
    elif reward:
        summary = "Mesajul promite un beneficiu. Oferta rămâne neconfirmată."
    elif safety:
        summary = "Textul conține un avertisment de securitate sau un exemplu relatat."
    else:
        summary = "Verificările disponibile au găsit indicii limitate."
    summary += " Identitatea expeditorului rămâne neverificată."
    recommendations = ["Verifică expeditorul separat, folosind aplicația sau datele de contact oficiale."]
    if score >= 35:
        recommendations.append("Evită linkurile din mesaj și păstrează datele secrete sau bancare private.")
    if paid:
        recommendations.append("Confirmă beneficiarul și solicitarea de plată printr-un canal cunoscut.")

    context["corroboration"] = [
        {"domain": u["domain"], "target": u["typosquatting"]["target"],
         "brand": u["typosquatting"]["brand"], "source": u["typosquatting"]["source"],
         "matches_claimed_entity": u["typosquatting"]["brand"] in context["claimed_entities"]}
        for u in reports if u["typosquatting"].get("is_official")
    ]
    context["financial_indicators"] = list(dict.fromkeys(contextual_finance))
    context["manipulation_indicators"] = [t for t in tactics if t not in {
        "Solicitare de plata", "Actiune asupra contului sau formularului",
    }]
    context["semantic_intents"] = list(dict.fromkeys(item.label for item in all_observations)) or ["unknown"]
    # Keep a clause only in the evidence panel, never style it as a precise keyword highlight.
    return {
        "risk_score": score, "risk_label": risk_label, "verdict": verdict, "summary": summary,
        "tactics_detected": tactics, "highlights": highlights, "recommendations": recommendations,
        "score_breakdown": {"linguistic_behavior": language_points, "url_domain": url_points,
                            "linked_identity_action": combo, "verified_threat_intelligence": threat_points},
        "assessment": {"label": assessment_label, "message_type": message_type, "mechanisms": mechanisms},
        "context": context, "semantic_evidence": [item.public(text) for item in all_observations[:48]],
        "domain_reference_conflict": reference_conflict,
        "evidence_review": [{**review.public(text), "unresolved": review in unresolved}
                            if review.reason != "invalid_original_span" else
                            {"label": review.observation.label, "source": review.observation.source,
                             "status": review.status, "reason": review.reason, "unresolved": False}
                            for review in reviews],
        "action_frames": [{"intent": frame.label, "actor": "message_recipient", "target": INDICATORS[frame.label],
                           "direction": frame.direction, "recipient": frame.recipient, "source": "rules",
                           "start": utf16_offset(text, frame.start), "end": utf16_offset(text, frame.end),
                           "text": text[frame.start:frame.end]}
                          for frame in frames if frame.end - frame.start <= 650],

    }, {
        "direct": direct, "safety": safety, "paid": paid, "agreement": agreement,
        "unresolved": unresolved, "frames": frames, "inferred": inferred, "bank_link": bool(bank_link),
    }
