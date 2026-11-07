"""Bounded Romanian action/object rules. All offsets refer to the original message."""
import re

from semantic_analysis import observe, trimmed_span, utf16_offset

ROMANIAN = str.maketrans("ăâîșşțţ", "aaisstt")
CLAUSE_BREAK = re.compile(r"[\n;!?]+|(?<!\bdvs)(?<!\bdna)(?<!\bdl)\.(?=\s|$)|\b(?:dar|insa|ci|totusi)\b")
QUOTED = re.compile(r'"[^"\n]+"|„[^”\n]+”|«[^»\n]+»|“[^”\n]+”|(?<!\w)\'[^\'\n]+\'(?!\w)')
REPORTED = re.compile(
    r"\b(?:exemplu(?:l)?|ipotetic|simulare|citat|am primit|am vazut|training\s+example|example\s+of\s+(?:a\s+)?(?:scam|fraud)|"
    r"mi-(?:a|au)\s+(?:aparut|venit|afisat)|mi\s+s-a\s+afisat|"
    r"care\s+(?:zice|spune|afirma|cere|solicita)\b|"
    r"am analizat|mesajul fals|(?:la|in) curs|(?:atentie|avertisment)\s+(?:la|despre)|"
    r"mesaj(?:ul|ele)?\s+(?:suspect\s+)?care|"
    r"daca\s+(?:(?:un\s+mesaj|mesajul|acest\s+mesaj)\b|(?:ti|vi)\s+se\s+(?:cere|solicita|pretinde)\b|(?:primesti|primiti|cineva)\b))"
)
CONTINUED_REPORT = re.compile(r"^\s*(?:si|and)\s+(?:cere|solicita|pretinde|zice|spune|afirma)\b")
ACTIONS = re.compile(
    r"\b(?P<disclose>trimit(?:e(?:ti)?|i)|comunic(?:a(?:ti)?|i)|divulg(?:a(?:ti)?|i)|"
    r"dezvalu(?:ie|iti)|furniz(?:eaza|ati|ezi)|transmit(?:e(?:ti)?|i)|spun(?:e(?:ti)?|i)|"
    r"introduc(?:e(?:ti)?|i)|introdu|tasteaz(?:a|i)|tastati|dict(?:eaza|ati|ezi)|"
    r"solicit(?:a|am|ati)|cer(?:e|em)|am\s+nevoie\s+(?:(?:urgent|acum|repede)\s+)?de|vreau|da(?:ti|i)?(?=\s|[-])|"
    r"ofer(?:a|iti|i)|scrie(?:ti)?-mi)"
    r"\b|\b(?P<pay>plat(?:este|iti|esti|este-mi)|achit(?:a(?:ti)?|i)|"
    r"transfer(?:a(?:ti)?|i)|depun(?:e(?:ti)?|i)|vir(?:a(?:ti)?|ezi))\b"
    r"|\b(?P<upload>atas(?:eaza|ati|ezi)|incarc(?:a(?:ti)?|i)|uploadeaz(?:a|i))\b"
    r"|\b(?P<purchase>cumpar(?:a(?:ti)?|i)|achizition(?:eaza|ati|ezi))\b"
    r"|\b(?P<interact>complet(?:eaza|ati|ezi)|confirm(?:a(?:ti)?|i)|valid(?:eaza|ati|ezi)|"
    r"verific(?:a(?:ti)?|i)|actualiz(?:eaza|ati|ezi)|acceseaz(?:a|i)|accesati|apas(?:a(?:ti)?|i)|"
    r"intr(?:a(?:ti)?|i)|deschid(?:e(?:ti)?|i)|click)\b"
)
SENSITIVE = re.compile(
    r"\b(?P<password>parol(?:a|ele|e|ei)|password)\b"
    r"|\b(?P<pin>(?:(?:cod(?:ul|urile)?)(?:\s+de)?\s+)?pin(?:-ul)?)\b"
    r"|\b(?P<otp>(?:(?:cod(?:ul|urile)?)(?:\s+(?:de\s+)?autentificare)?\s+)?"
    r"otp(?:-ul)?|cod(?:ul|urile)?\s+(?:(?:de\s+)?(?:autentificare|verificare|securitate)|"
    r"(?:primit(?:e)?\s+)?(?:prin|din)\s+sms))\b"
    r"|\b(?P<card>cvv(?:2|-ul)?|cvc(?:2|-ul)?|date(?:le)?\s+(?:de\s+pe\s+)?card(?:ului)?|"
    r"numar(?:ul)?\s+card(?:ului)?)\b"
    r"|\b(?P<identity>cnp(?:-ul)?|date(?:le)?\s+personale|"
    r"copi(?:e|a)\s+(?:de\s+pe\s+)?buletin(?:ului)?)\b"
)
MONEY = re.compile(
    r"\b(?:bani(?:i)?|sum(?:a|ei|e|ele)|transfer(?:ul|uri)?|virament(?:ul)?|plata|tax(?:a|e|ele)|comision(?:ul)?|depozit(?:ul)?|"
    r"avans(?:ul)?|factur(?:a|ii)|\d[\d., ]*\s*(?:de\s+)?(?:lei|ron|eur|euro))\b"
)
ACCOUNT = re.compile(r"\b(?:date(?:le)?|identitate(?:a)?|cont(?:ul(?:ui)?)?|formular(?:ul)?|link(?:ul)?|adresa|profil(?:ul)?)\b")
EXCEPTION = re.compile(r"\b(?:cu\s+exceptia|in\s+afara\s+de|(?:(?:doar|numai)\s+(?:catre\s+)?(?:operator|agent|consilier|echipa)))")
PRESSURE = re.compile(
    r"\b(?:urgent(?:a)?|imediat(?:a)?|in\s+maxim\s+\d+\s*(?:de\s+)?(?:ore|zile|h)|"
    r"ultima\s+notificare|expira\s+astazi|suspendat(?:a)?(?:\s+temporar)?|"
    r"cont(?:ul)?\s+(?:va fi|este)\s+blocat)\b"
)
DELIVERY = re.compile(r"\b(?:colet(?:ul)?|livrare\s+esuata|adresa\s+incompleta|reexpediere|taxa\s+vamala)\b")
FAMILY = re.compile(r"\b(?:mama|tata|mami|tati|bunic[ao]|bunicule|fiul tau|fiica ta|sunt eu)\b")
NUMBER_CHANGE = re.compile(r"\b(?:numar(?:ul)?\s+(?:meu\s+)?(?:nou|temporar|provizoriu)|schimbat\s+numar(?:ul)?|(?:noul|un alt)\s+(?:meu\s+)?numar)\b")
AVOID_CALL = re.compile(r"\bnu\s+(?:ma\s+suna|pot\s+(?:sa\s+)?vorb(?:i|esc)|(?:pot\s+)?raspund(?:e)?(?:\s+la\s+apel)?)\b")
PROMISE = re.compile(
    r"\b(?:(?:ai|aveti|ai avea)\s+de\s+primit|(?:banii|suma|fondurile)\s+(?:vor|va)\s+(?:intra|fi virat[eai]?)|ai\s+castigat|ati\s+castigat|castig(?:ul)?|premiu(?:l)?|mostenire(?:a)?|rambursare(?:a)?|restituire(?:a)?|"
    r"(?:vei|veti|poti|puteti|sa)\s+(?:primi(?:ti)?|incasa(?:ti)?|debloca(?:ti)?)|"
    r"investitie\s+garantata|profit\s+(?:zilnic|garantat))\b"
)
FEE = re.compile(r"\b(?:tax(?:a|e|ele)|comision(?:ul)?|depozit(?:ul)?|avans(?:ul)?|garanti(?:e|a)|tarif(?:ul)?)\b")
META_COMMAND = re.compile(
    r"\b(?:ignora(?:ti)?|returneaza|seteaza|ignore|output|respond|raspunde)\b"
    r".{0,100}\b(?:instructiun|scor|verdict|risk_score|system prompt|gemini)"
)
NEGATION = re.compile(r"\b(?:nu|niciodata|fara)(?:\s+[\w-]+){0,4}\s*$")
POSITIVE_AFTER_NU = re.compile(r"\bnu\s+(?:uita|uitati|ezita|ezitati|trebuie\s+decat|e\s+nevoie\s+decat)\b")
MANDATORY = re.compile(r"\bnu\s+(?:ai|aveti|exista)\s+.{0,55}\b(?:decat|trebuie)\b")
DESCRIPTIVE = re.compile(r"\b(?:va|vor|vei|veti|voi|vom)\s*$")


CARD = re.compile(r"\b(?:card(?:ul(?:ui)?|uri(?:le|lor)?)?|cvv|cvc)\b")
PHOTO = re.compile(r"\b(?:poz(?:a|e|ele)|fotografi(?:e|a|i|ile)|imagin(?:e|ea|i|ile)|captur(?:a|i)|screenshot(?:-ul)?|scan(?:are|ul))\b")
DOCUMENT = re.compile(r"\b(?:cnp(?:-ul)?|buletin(?:ul|ului)?|pasaport(?:ul|ului)?|(?:act(?:ul|ului)?|cart(?:e|ea|ii))\s+de\s+identitate)\b")
CODE_CLUE = re.compile(r"\b(?:cod(?:ul|urile)?|cifrele|cifr(?:e|a))\b.{0,100}\b(?:sms|autentificare|verificare|confirmare|banca|telefon)\b")
VERIFY = re.compile(r"\b(?:verific\w*|confirm\w*|valid\w*|reactiv\w*|debloc\w*)\b")
REWARD = re.compile(r"\b(?:gratuit(?:a|e)?|gratis|cadou(?:l)?|voucher(?:ul)?|recompens(?:a|e))\b")
PROMO = re.compile(r"\b(?:ofert(?:a|e|ele)|reclam(?:a|e)|reducer(?:e|i)|promoti(?:e|a))\b")
KEEP_SECRET = re.compile(r"\b(?:numai|doar)\s+pentru\s+tine\b|\bnu\s+(?:divulga\w*|dezvalui\w*|comunic\w*|da\w*|trimite\w*|incarca\w*|atasa\w*)\b")
DEPENDENCY = re.compile(
    r"\b(?P<purpose>ca\s+sa|pentru\s+a|inainte\s+de|mai\s+intai|in\s+prealabil|conditi[eo]n\w*|"
    r"before|in\s+order\s+to|first)\b|\b(?P<after>(?:numai\s+|doar\s+)?dupa\s+ce|odata\s+ce|imediat\s+ce|after|once)\b"
)
HARM_ANCHOR = re.compile(r"\b(?:telefon(?:ul)?|transfer(?:ul)?|verific\w*|confirm\w*|inregistr\w*)\b")
LINK_ACTION = ("acces", "intr", "apas", "click", "deschid")
ACCOUNT_CHANGES = ("complet", "confirm", "valid", "actualiz")


def fold(text):
    # Avoid length-changing Unicode case mappings so evidence offsets stay exact.
    return "".join(char.lower() if len(char.lower()) == 1 else char for char in text).translate(ROMANIAN)


def mask(text, spans):
    chars = list(text)
    for start, end in spans:
        chars[start:end] = [char if char in "\r\n" else " " for char in chars[start:end]]
    return "".join(chars)


def clause_spans(text):
    start = 0
    for match in CLAUSE_BREAK.finditer(text):
        yield start, match.start()
        start = match.end()
    yield start, len(text)


def is_negated(clause, action):
    # Strip pronoun hyphens before checking the short left scope.
    prefix = re.split(r"[:,]|\bsi\b", clause[:action.start()])[-1]
    negation = NEGATION.search(prefix.replace("-", " "))
    return bool(negation and not POSITIVE_AFTER_NU.search(negation[0]) and not MANDATORY.search(prefix))


def rule_view(original, url_spans):
    """Fold Romanian marks for rules while mapping every boundary to the original."""
    chars, offsets = [], [0]
    for i, char in enumerate(mask(original, url_spans)):
        # Decomposed Romanian breve/circumflex/comma/cedilla.
        if chars and ((char in "\u0302\u0306" and chars[-1] in "ai")
                      or (char in "\u0326\u0327" and chars[-1] in "st")):
            offsets[-1] = i + 1
        else:
            chars.append(fold(char))
            offsets.append(i + 1)
    return "".join(chars), offsets


def analyze_language(text, url_spans, catalog):
    rule_text, offsets = rule_view(text, url_spans)
    reported_quotes = []
    for quote in QUOTED.finditer(rule_text):
        before = rule_text[max(0, quote.start() - 220):quote.start()]
        last = re.split(r"[\n!?;]", before)[-1]
        after = rule_text[quote.end():quote.end() + 100]
        if REPORTED.search(last) or re.match(r"\s*(?:este|e|reprezinta)\s+(?:un\s+)?(?:exemplu|mesaj\s+suspect)", after):
            reported_quotes.append(quote.span())
    active = mask(rule_text, reported_quotes)
    highlights, risks, actions, observations = {}, {}, [], []
    protected_spans, clauses, verification, link_actions = list(reported_quotes), [], [], []
    contextual = {"educational"} if reported_quotes else set()
    referenced = list(dict.fromkeys(m.lastgroup for m in SENSITIVE.finditer(rule_text)))

    def original_span(span):
        return trimmed_span(text, offsets[span[0]], offsets[span[1]])

    def fact(label, span, identity=None):
        start, end = original_span(span)
        if 0 < end - start <= 2400 and len(observations) < 36:
            observations.append(observe(text, label, "rules", (start, end), "rule_span", identity=identity))

    for span in reported_quotes:
        fact("educational_example", span)

    def evidence(span, category, explanation, points):
        start, end = original_span(span)
        if start == end or points <= risks.get(category, 0):
            return
        risks[category] = points
        highlights[category] = {"phrase": text[start:end], "category": category, "explanation": explanation,
                                "start": utf16_offset(text, start), "end": utf16_offset(text, end), "source": "rules"}

    def add_action(kind, intent, span):
        start, end = original_span(span)
        item = {"kind": kind, "intent": intent, "phrase": text[start:end].strip()}
        if len(actions) < 12 and item not in actions:
            actions.append(item)

    claimed, brand_mentions = [], []
    for name in dict.fromkeys(entry.name for entry in catalog):
        aliases = list(dict.fromkeys([fold(name), *(fold(alias) for entry in catalog if entry.name == name
                                                   for alias in getattr(entry, "aliases", ())) ]))
        if name == "Banca Transilvania":
            aliases.append("bt")
        pattern = r"\b(?:" + "|".join(re.escape(alias) for alias in aliases) + r")\b"
        for match in re.finditer(pattern, active):
            if name not in brand_mentions:
                brand_mentions.append(name)
            before = active[max(0, match.start() - 75):match.start()]
            after = active[match.end():match.end() + 3]
            header = re.fullmatch(r"\s*(?:(?:alerta|informare(?: de securitate)?|notificare|mesaj(?: de la)?)\s+)?", before)
            if (header and re.match(r"\s*:", after)) or re.search(
                r"\b(?:sunt(?:em)?(?:\s+(?:de la|din partea))?|reprezint|echipa|din partea|de la)\s*$", before,
            ):
                claimed.append(name)
                fact("organization_impersonation_claim", match.span(), name)
                break

    interacted = contradiction = False
    pressure = delivery = promise = fee = number_change = family = avoid_call = None
    payment_spans, payout_spans = [], []
    for start, end in clause_spans(active):
        clause = active[start:end]
        semantic_end = end
        while semantic_end < len(active) and active[semantic_end] in ".!?;":
            semantic_end += 1
        original_clause = original_span((start, semantic_end))
        if original_clause[0] < original_clause[1]:
            clauses.append(original_clause)
        report = REPORTED.search(clause)
        report_end = None
        if report:
            separator = clause.find(",", report.end())
            quote_ends = [b - start for a, b in reported_quotes if start + report.end() <= a < b <= end]
            quote_ends = [boundary for boundary in quote_ends if not CONTINUED_REPORT.match(clause[boundary:])]
            report_end = min([len(clause), *quote_ends, *([separator] if separator >= 0 else [])])
            reported_span = start + report.start(), start + report_end
            protected_spans.append(reported_span)
            if SENSITIVE.search(clause[report.start():report_end]) or MONEY.search(clause[report.start():report_end]):
                contextual.add("educational")
                fact("educational_example", reported_span)
        scan_start = report_end if report_end is not None else 0
        eligible = clause[scan_start:]

        def clue(pattern):
            match = pattern.search(eligible)
            return (start + scan_start + match.start(), start + scan_start + match.end()) if match else None

        pressure = pressure or clue(PRESSURE)
        delivery = delivery or clue(DELIVERY)
        current_payout = clue(PROMISE)
        if current_payout:
            payout_spans.append(current_payout)
        promise = promise or current_payout
        fee = fee or clue(FEE)
        number_change = number_change or clue(NUMBER_CHANGE)
        family = family or clue(FAMILY)
        avoid_call = avoid_call or clue(AVOID_CALL)
        reward = clue(REWARD)
        if reward and re.search(r"\b(?:primi\w*|ofer\w*|castig\w*|revendic\w*|obtin\w*|cadou)\b", eligible):
            if not KEEP_SECRET.search(eligible):
                fact("reward_offer", (start + scan_start, end))

        matches = list(ACTIONS.finditer(clause))
        for i, action in enumerate(matches):
            if report and report.start() <= action.start() < report_end:
                continue
            if DESCRIPTIVE.search(clause[:action.start()]):
                continue
            following = matches[i + 1].start() if i + 1 < len(matches) else len(clause)
            stop = min(following, action.end() + 150)
            tail = clause[action.end():stop]
            sensitive = list(SENSITIVE.finditer(tail))
            money = MONEY.search(tail)
            account = ACCOUNT.search(tail)
            left_money = MONEY.search(clause[max(scan_start, action.start() - 45):action.start()])
            negated = is_negated(clause, action) or bool(re.match(r"\s+niciodata\b", tail))
            if action.lastgroup == "pay" or (action.lastgroup == "disclose" and (money or left_money) and not sensitive):
                span = start + action.start(), start + action.end() + (money.end() if money else 0)
                if negated:
                    protected_spans.append((start + scan_start, start + stop))
                else:
                    payment_spans.append(span)
                    add_action("payment", "requested", span)
                    fact("request_money", span)
                    evidence(span, "Solicitare de plata", "Mesajul cere o plata sau un transfer.", 12)
                continue
            if action.lastgroup == "purchase":
                if not negated:
                    fact("commercial_solicitation", (start + action.start(), start + stop))
                continue
            if action.lastgroup == "interact" and action[0].startswith(LINK_ACTION) and not negated:
                if any(original_clause[0] <= left < original_clause[1] for left, _ in url_spans):
                    link_actions.append(original_clause)

            photo = PHOTO.search(tail)
            card = CARD.search(tail)
            doc = DOCUMENT.search(tail)
            is_photo = bool(photo and card and action.lastgroup in {"upload", "disclose"})
            is_document = bool(doc and action.lastgroup == "upload")
            if (sensitive or is_photo or is_document) and action.lastgroup in {"disclose", "interact", "upload"}:
                exception = EXCEPTION.search(tail) if negated else None
                if action.lastgroup == "interact" and action[0].startswith(("verific", *LINK_ACTION)):
                    continue
                objects = [*sensitive, *(m for m in (photo, card) if m and is_photo), *(m for m in (doc,) if m and is_document)]
                span = start + action.start(), start + action.end() + max(m.end() for m in objects)
                if negated and not exception:
                    contextual.add("protective")
                    protected_spans.append((start + scan_start, start + stop))
                    fact("protective_warning", (start + scan_start, span[1]))
                    add_action("sensitive_data", "discouraged", (start, span[1]))
                    continue
                contradiction |= bool(exception)
                secrets = {m.lastgroup for m in sensitive}
                label = "request_card_photo" if is_photo else "request_credentials" if secrets - {"identity"} else "request_sensitive_documents"
                points = 52 if label == "request_sensitive_documents" else 70
                if exception:
                    span = start, start + stop
                    explanation = "Interdictia initiala are o exceptie care permite divulgarea datelor."
                else:
                    explanation = "Actiunea cere comunicarea sau incarcarea unor date sensibile."
                fact(label, span)
                add_action("sensitive_data", "requested", span)
                evidence(span, "Solicitare de date sensibile", explanation, points)
                continue
            if action.lastgroup == "interact" and not negated and (
                account or (url_spans and re.search(r"\b(?:aici|pe\s+link)\b", tail))
            ):
                if action[0].startswith("verific") and re.search(r"\b(?:direct|aplicatia|oficial)\b", tail):
                    continue
                interacted = True
                span = start + action.start(), start + action.end() + (account.end() if account else 0)
                add_action("account_or_link", "requested", span)
                if VERIFY.search(action[0]):
                    verification.append(original_span(span))
                    fact("account_verification_request", span)
                if action[0].startswith(ACCOUNT_CHANGES):
                    evidence(span, "Actiune asupra contului sau formularului",
                             "Mesajul cere completarea unui formular sau modificarea unor date.", 18)

    if promise:
        fact("promise_payout", promise)
        if re.search(r"\b(?:profit\s+garantat|investitie\s+garantata)\b", active):
            evidence(promise, "Promisiune financiara", "Mesajul promite un castig garantat.", 20)
    if family and number_change:
        fact("family_impersonation", number_change, "Persoana apropiata (pretinsa)")
    if avoid_call:
        fact("unavailable_for_call", avoid_call)
    if delivery and (payment_spans or interacted) and (url_spans or fee):
        evidence(delivery, "Pretext de livrare", "Un colet este invocat impreuna cu o cerere de plata sau de actiune.", 25)
    if pressure:
        fact("urgency_or_pressure", pressure)
        if payment_spans or interacted or "Solicitare de date sensibile" in risks:
            evidence(pressure, "Presiune de timp sau consecinte", "Mesajul asociaza actiunea ceruta cu urgenta sau blocarea contului.", 10)

    asked = "Solicitare de date sensibile" in risks
    contradiction |= asked and "protective" in contextual
    intent = ("mixed" if contradiction else "requested" if asked else
              "discouraged" if "protective" in contextual else
              "educational" if "educational" in contextual else "mentioned" if referenced else "absent")
    if META_COMMAND.search(active):
        contextual.add("embedded_analysis_instruction")
    pressure_key = "Presiune de timp sau consecinte"
    return {
        "base_points": max((p for k, p in risks.items() if k != pressure_key), default=0),
        "pressure_points": risks.get(pressure_key, 0), "highlights": list(highlights.values()), "tactics": list(risks),
        "observations": tuple(observations), "clauses": tuple(clauses),
        "protected": tuple(original_span(span) for span in protected_spans),
        "active": active, "offsets": offsets,
        "payment_spans": tuple(original_span(span) for span in payment_spans),
        "payout_spans": tuple(original_span(span) for span in payout_spans),
        "verification": tuple(verification), "link_actions": tuple(link_actions),
        "context": {
            "claimed_entities": list(dict.fromkeys(claimed)) + (["Persoana apropiata (posibil)"] if family and number_change else []),
            "brand_mentions": brand_mentions, "requested_actions": actions,
            "sensitive_data_types": referenced, "sensitive_data_intent": intent,
            "manipulation_indicators": [key for key in risks if key not in {
                "Solicitare de plata", "Actiune asupra contului sau formularului",
            }],
            "financial_indicators": [highlights[key]["phrase"] for key in ("Solicitare de plata", "Promisiune financiara") if key in highlights],
            "contradictions": ["Avertismentul coexista cu o solicitare de date."] if contradiction else [],
            "context_notes": sorted(contextual),
        },
    }
