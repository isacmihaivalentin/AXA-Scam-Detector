"""Small evidence primitives for direction, recipient, target and scope."""
import re
from bisect import bisect_left
from dataclasses import dataclass

from text_analysis import ACCOUNT, CARD, CODE_CLUE, DEPENDENCY, DOCUMENT, FEE, MONEY, PHOTO, SENSITIVE, VERIFY

SECRET_FORM = re.compile(
    r"\b(?:pin|otp|cvv|cvc)(?:-?ul?)?\b|\b(?:pass(?:word|code)|recovery\s+(?:key|code)|"
    r"one[- ]time\s+(?:code|password)|(?:cod\w*|chei\w*)\s+(?:de\s+)?(?:rezerva|recuperare)|"
    r"fraza\s+de\s+recuperare|seed\s+phrase|private\s+key|chei\w*\s+privat\w*|"
    r"(?:cookie\w*|token\w*)\s+(?:de\s+sesiune|of\s+session)|session\s+(?:cookie|token)|__host-session)\b"
)
DIGIT_CODE = re.compile(r"\b(?:cifr\w*|digits|cod\w*|code)\b")
AUTH_ORIGIN = re.compile(r"\b(?:sms|2fa|otp|authenticator|autentific\w*|verification|verific\w*|mesaj\w*|notification|telefon\w*|plata|payment)\b")
NON_PAYMENT_CARD = re.compile(r"\b(?:card\w*\s+(?:cadou|de\s+(?:membru|fidelitate))|(?:membership|loyalty)\s+card)\b")
VALUE = re.compile(
    r"\b(?:btc|eth|usdt|cripto\w*|crypto\w*|token\w*|voucher\w*|gift\s+card|prepaid\s+card|"
    r"portofel\w*|wallet|funds|payout|balance|dollars?|usd|ramburs\w*|despagub\w*)\b"
)
TRANSFER = re.compile(r"\b(?:plat(?:este|iti|esti)|achit(?:a(?:ti)?|i)|transfer(?:a(?:ti)?|i)?|vir(?:a(?:ti)?|ezi)|"
                      r"trimit(?:e(?:ti)?|i)|depun(?:e(?:ti)?|i)|aliment(?:a(?:ti)?|eaza|ezi)|cumpar(?:a(?:ti)?|i)|"
                      r"pay|send|deposit|top\s+up|purchase)\b")
PAYOUT = re.compile(r"\b(?:payout|withdraw\w*|refund\w*|releas\w*|claim|receive|castig\w*|retrag\w*|ramburs\w*|despagub\w*|premi\w*|benefici\w*)\b")
LOGIN = re.compile(r"\b(?:logar\w*|login|sign[- ]in|autentific\w*|conectar\w*)\b")
APPROVAL = re.compile(r"\b(?:aprob\w*|approve|accept\w*|allow|autoriza\w*)\b")
DEVICE = re.compile(r"\b(?:calculator\w*|ecran\w*|computer\w*|device\w*|dispozitiv\w*|telefon\w*|phone|desktop)\b")
REMOTE = re.compile(r"\b(?:remote\s+(?:access|control|support)|(?:acces|control|asistenta)\s+de\s+la\s+distanta|"
                    r"acces\s+de\s+control|control\s+complet|(?:sa\s+)?(?:preiau|controlez|accesez)\s+\w*|screen\s+sharing|partaj\w*\s+ecran\w*)\b")
INSTALL = re.compile(r"\b(?:instal\w*|install|download|descarc\w*|permite\w*|allow|grant)\b")
SOFTWARE_PERMISSION = re.compile(r"\b(?:surse\s+necunoscute|unknown\s+sources|accessibility|accesibilitate|permissions|permisiun\w*|remote\s+control)\b")
PACKAGE_FILE = re.compile(r"\b(?:apk|installer|instalator|executabil|browser\s+extension|extensi\w*\s+de\s+browser)\b")

REQUEST = re.compile(
    r"\b(?:te\s+rog|va\s+rugam|poti|puteti|ai\s+putea|ati\s+putea|trebuie|necesar\w*|"
    r"ne-ar\s+(?:ajuta|trebui)|astept\w*|ne\s+trebuie|please|kindly|could\s+you|"
    r"we\s+(?:need|require)|you\s+(?:must|need\s+to))\b"
)
DELIVERY_ACTION = re.compile(
    r"\b(?:trimite\w*|transmit\w*|spun\w*|scri\w*|dict\w*|cit\w*|incarc\w*|atas\w*|"
    r"arata\w*|ofer\w*|pun\w*|da(?:i|ti)?|introdu\w*|las(?:a(?:ti)?|i)|copi\w*|lip\w*|urc\w*|"
    r"send|share|upload|enter|read|forward|attach|reply|provide|paste|copy|export|show|give)\b"
)
CHANNEL = re.compile(
    r"\b(?:in\s+(?:(?:acest(?:a|e)?|urmatorul)\s+)?(?:raspuns\w*|chat|conversati\w*|formular\w*)|"
    r"in\s+camp\w*|pe\s+(?:chat|whatsapp|link\w*)|aici|(?:catre|pentru)\s+noi|"
    r"(?:imi|mi|ne)\s+(?:trimit\w*|spun\w*|dict\w*|dai|dati|arat\w*|scri\w*|poti|puteti)|"
    r"(?:trimite|spune|scrie|da|arat[aă])-(?:mi|ne)|"
    r"reply\s+(?:here|with)|(?:to|for)\s+(?:us|me)|in\s+(?:the\s+)?(?:chat|reply|form))\b"
)
REPORT_CUE = re.compile(
    r"\b(?:educat\w*|didactic\w*|training|workshop|role[- ]play|simula\w*|"
    r"(?:exempl\w*|example)\s+(?:de|of|pentru)|mesaj\w*\s+(?:care|cum)|"
    r"(?:the|a)\s+(?:scam|fraudster)\s+(?:said|asks?))\b"
)
PROHIBITION = re.compile(
    r"\b(?:nu\s+(?:iti\s+|vi\s+|va\s+|mi\s+|ne\s+|il\s+|le\s+|sa\s+|trebuie\s+sa\s+|"
    r"este\s+necesar\s+sa\s+)?(?:comunic\w*|trim\w*|spun\w*|plat\w*|achit\w*|vir\w*|"
    r"divulg\w*|incarc\w*|atas\w*|dai|dati|aprob\w*|accept\w*|instal\w*|autoriza\w*)|"
    r"(?:never|do\s+not|don't)\s+(?:share|send|read|give|approve|accept|install|pay|upload|forward)|"
    r"pastr\w*\s+.{0,65}\bpentru\s+(?:tine|dumneavoastra)|keep\s+.{0,65}\bto\s+yourself)\b"
)
# A person protecting the approvals they themselves initiated is distinct from a caller requesting approval.
OWN_ACTION = re.compile(
    r"\b(?:(?:pe\s+care|daca)\s+(?:le-ai|l-ai|ai|le-ati|ati)\s+(?:initiat\w*|pornit\w*)|"
    r"(?:you|yourself)\s+(?:initiated|started)|(?:direct|doar)\s+in\s+aplicati\w*\s+(?:ta|propri\w*))\b"
)
CONTRAST = re.compile(r"[,;]\s*|\b(?:but|however|except|totusi|insa|dar)\b")
REFERENCE = re.compile(r"\b(?:it|them|acel(?:a|e)?|acest(?:a|ea)?|acel\s+lucru|(?:il|le)\s+|(?:pune|trimite|lasa)-(?:l|o|le))\b")
INDICATORS = {
    "request_credentials": "authentication_secret", "request_card_photo": "card_information",
    "request_sensitive_documents": "identity_document", "request_money": "monetary_value",
    "advance_fee_condition": "monetary_value", "account_verification_request": "account",
    "request_login_approval": "login_approval", "request_remote_access": "device_access",
}
HARMFUL_ACTIONS = frozenset(INDICATORS)
ACCESS_INTENTS = frozenset({"request_login_approval", "request_remote_access"})


def rule_slice(language, start, end):
    offsets = language["offsets"]
    return language["active"][bisect_left(offsets, start):bisect_left(offsets, end)]


def overlaps(span, start, end):
    return span[0] < end and start < span[1]


def scope_reason(language, start, end, snippet):
    if any(overlaps(span, start, end) for span in language["protected"]):
        return "protected_or_reported_scope"
    if REPORT_CUE.search(snippet):
        return "reported_context"
    if PROHIBITION.search(snippet):
        return "prohibited_action"
    return None


def object_labels(snippet):
    labels = set()
    secrets = SENSITIVE.search(snippet)
    if (SECRET_FORM.search(snippet) or CODE_CLUE.search(snippet)
            or (DIGIT_CODE.search(snippet) and AUTH_ORIGIN.search(snippet))
            or (secrets and secrets.lastgroup != "identity")):
        labels.add("request_credentials")
    if CARD.search(snippet) and PHOTO.search(snippet) and not NON_PAYMENT_CARD.search(snippet):
        labels.add("request_card_photo")
    if DOCUMENT.search(snippet) or (secrets and secrets.lastgroup == "identity"):
        labels.add("request_sensitive_documents")
    if MONEY.search(snippet) or VALUE.search(snippet) or FEE.search(snippet):
        labels.add("request_money")
    if ACCOUNT.search(snippet) and VERIFY.search(snippet):
        labels.add("account_verification_request")
    if LOGIN.search(snippet) and APPROVAL.search(snippet):
        labels.add("request_login_approval")
    if (REMOTE.search(snippet) and (DEVICE.search(snippet) or CHANNEL.search(snippet) or SOFTWARE_PERMISSION.search(snippet))
            or (INSTALL.search(snippet) and SOFTWARE_PERMISSION.search(snippet))):
        labels.add("request_remote_access")
    return labels


@dataclass(frozen=True)
class ActionFrame:
    label: str
    start: int
    end: int
    direction: str
    recipient: str
    explicit: bool
    action_start: int | None = None


def extract_frames(language):
    """Use the same role and object checks for unfamiliar nouns and word orders."""
    frames = []
    prior = None
    for left, right in language["clauses"]:
        snippet = rule_slice(language, left, right)
        blocked = scope_reason(language, left, right, snippet)
        if not blocked and OWN_ACTION.search(snippet):
            blocked = "self_initiated_action"
        delivery, channel, ask = DELIVERY_ACTION.search(snippet), CHANNEL.search(snippet), REQUEST.search(snippet)
        transfer = TRANSFER.search(snippet)
        targets = object_labels(snippet)
        if (not blocked and prior and left - prior[1] <= 75 and DIGIT_CODE.search(snippet)
                and delivery and channel and prior[2]):
            targets.add("request_credentials")
        prior = (left, right, not blocked and bool(DIGIT_CODE.search(snippet) and AUTH_ORIGIN.search(snippet)))
        for label in sorted(targets):
            directed = (
                bool(delivery and (channel or ask) or (label == "request_card_photo" and channel and ask)) if label in {
                    "request_credentials", "request_card_photo", "request_sensitive_documents",
                } else bool(transfer and (ask or channel or DEPENDENCY.search(snippet))) if label == "request_money"
                else bool(APPROVAL.search(snippet) and (ask or channel)) if label == "request_login_approval"
                else bool(INSTALL.search(snippet) or ask) if label == "request_remote_access"
                else bool(ask or VERIFY.search(snippet))
            )
            direction = "discouraged_or_reported" if blocked else "requested" if directed else "unclear"
            # A channel alone is weak. For authentication, both the object and a
            # directed act are necessary. A question about where a secret is kept
            # does not by itself request its value.
            explicit = direction == "requested" and (
                bool(channel and (delivery or (label == "request_card_photo" and ask))) if label in {
                    "request_credentials", "request_card_photo", "request_sensitive_documents",
                } else label in ACCESS_INTENTS
            )
            verb = transfer if label == "request_money" else delivery
            action_start = language["offsets"][bisect_left(language["offsets"], left) + verb.start()] if verb else None
            frames.append(ActionFrame(label, left, right, direction, "specified_channel" if channel else "unspecified",
                                      explicit, action_start))
    return tuple(frames[:40])
