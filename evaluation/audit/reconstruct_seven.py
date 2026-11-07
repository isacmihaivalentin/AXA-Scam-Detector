"""Reconstruct which Gemini interpretations reproduce the scores the user observed.

NOT live Gemini output. No API key or network was available in the audit sandbox.
For each case we enumerate plausible structured readings (overall reading x request
shape x claimed sender x tactics) and run them through the REAL v2.0 pipeline
(semantic_gemini.validate -> engine -> decision.assess). A combination that yields the
exact reported score is a candidate explanation; the decisive evidence item is listed.
"""
import itertools, json, os, sys, tempfile
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["AXA_SQLITE_PATH"] = tempfile.mktemp(suffix=".sqlite3")
for k in ("GEMINI_API_KEY", "AXA_WEB_RISK_API_KEY", "AXA_DATABASE_URL"):
    os.environ.pop(k, None)
import database, engine, semantic_gemini  # noqa: E402
database.initialize_sqlite(os.environ["AXA_SQLITE_PATH"])


def req(action, obj, sens, quote, stance="requested"):
    return {"action": action, "object": obj, "sensitivity": sens, "recipient": None, "stance": stance, "quote": quote}


OPTIONS = {
    "A-visa-gpay": dict(
        mech="otp_or_authentication_theft", senders=[None, "Visa", "Google Pay"],
        requests={"call_req": [req("call_number", "apel la *2000", "low", "contacteaza-ne la *2000")],
                  "call_hyp": [req("call_number", "apel la *2000", "low", "contacteaza-ne la *2000", "hypothetical")],
                  "none": []},
        tactics={"none": [], "urgency": [{"tactic": "urgency", "quote": "poate fi utilizat imediat"}]}),
    "B-fan-coordination": dict(
        mech="delivery_scam", senders=[None, "FAN Courier"],
        requests={"call_req": [req("call_number", "apel la 0725724911", "low", "Va rugam sa ne contactati la tel 0725724911")],
                  "none": []},
        tactics={"none": []}),
    "C-orange-promo-1": dict(
        mech="reward_or_lottery", senders=[None, "Orange", "My Orange"],
        requests={"click": [req("click_link", "link Pinata Party", "low", "Hai in Pinata Party aici")],
                  "click+pay": [req("click_link", "link Pinata Party", "low", "Hai in Pinata Party aici"),
                                req("pay_fee", "plata facturilor", "financial_asset", "platesti facturi")],
                  "other": [req("other", "participare la joc", "low", "Sparge Pinata")]},
        tactics={"none": [], "reward": [{"tactic": "reward_bait", "quote": "Castiga super premii"}]}),
    "D-cargus-pickup": dict(
        mech="delivery_scam", senders=[None, "Cargus"],
        requests={"click": [req("click_link", "detalii colet", "low", "Vezi detalii")],
                  "click+pin_req": [req("click_link", "detalii colet", "low", "Vezi detalii"),
                                    req("share_otp_or_code", "PIN 3168", "secret_credential", "PIN 3168")],
                  "click+pin_self": [req("click_link", "detalii colet", "low", "Vezi detalii"),
                                     req("share_otp_or_code", "PIN 3168", "secret_credential", "PIN 3168", "self_initiated")]},
        tactics={"none": [], "urgency": [{"tactic": "urgency", "quote": "pana la ora 20:00"}]}),
    "E-orange-promo-2": dict(
        mech="reward_or_lottery", senders=[None, "Orange", "My Orange"],
        requests={"click": [req("click_link", "link Pinata Party", "low", "Intra in Pinata Party aici")],
                  "click+pay": [req("click_link", "link Pinata Party", "low", "Intra in Pinata Party aici"),
                                req("pay_fee", "plati", "financial_asset", "Aduna puncte pentru plati")]},
        tactics={"none": [], "reward": [{"tactic": "reward_bait", "quote": "intri in tragerea la sorti"}]}),
    "F-cargus-delivery": dict(
        mech="delivery_scam", senders=[None, "Cargus"],
        requests={"click": [req("click_link", "detalii", "low", "Vezi detalii si optiuni")],
                  "click+pin_req": [req("click_link", "detalii", "low", "Vezi detalii si optiuni"),
                                    req("share_otp_or_code", "PIN 5499", "secret_credential", "PIN 5499")]},
        tactics={"none": []}),
    "G-tursib-portal": dict(
        mech="credential_phishing", senders=[None, "Tursib"],
        requests={"login_secret": [req("share_password", "autentificare in portal", "secret_credential", "Va rugam sa va autentificati in Portal")],
                  "login_personal": [req("other", "autentificare in portal", "personal_data", "Va rugam sa va autentificati in Portal")],
                  "login_low": [req("other", "autentificare in portal", "low", "Va rugam sa va autentificati in Portal")]},
        tactics={"none": [], "authority": [{"tactic": "authority", "quote": "Echipa Tursib"}]}),
}
OVERALL = ["ordinary_or_legitimate", "marketing_or_spam", "suspicious", "likely_scam"]


def run(text, interp):
    raw = json.dumps(interp, ensure_ascii=False)
    out = engine.analyze_text(text, "k", interpret=lambda t, k: semantic_gemini.interpret(t, k, generate=lambda *a, **kw: raw))
    return out["analysis"]


def main():
    cases = json.loads((ROOT / "evaluation/audit/seven_cases.json").read_text(encoding="utf-8"))
    report = {}
    for case in cases:
        opt = OPTIONS[case["id"]]
        hits, all_scores = [], Counter()
        for overall, (rname, reqs), sender, (tname, tactics) in itertools.product(
                OVERALL, opt["requests"].items(), opt["senders"], opt["tactics"].items()):
            mech = opt["mech"] if overall in {"suspicious", "likely_scam"} else "none"
            interp = {"message_language": "ro", "claim_summary": "-", "wants_summary": "-",
                      "claimed_sender": {"name": sender, "type": "other_organization" if sender else "none", "quote": sender},
                      "requests": reqs, "promises": [], "threats": [],
                      "dependency": {"present": False, "description": None, "quote": None},
                      "tactics": tactics, "protective_context": [],
                      "mechanism": {"category": mech, "description": "-"}, "overall": overall, "uncertainties": []}
            a = run(case["text"], interp)
            s = a["assessment"]
            score = s["risk_estimate"]
            all_scores[score] += 1
            top = s["policy"]["strongest"]
            top_item = next((e for e in a["evidence"] if top and e["id"] == top["id"]), {})
            row = {"overall": overall, "requests": rname, "sender": sender, "tactics": tname, "score": score,
                   "label": s["label"], "decisive": top and f"{top['category']}:{top['tier']} ({top_item.get('reason', '')[:90]})",
                   "reinforcement": s["policy"]["reinforcement"]}
            if score == case["reported"]:
                hits.append(row)
        report[case["id"]] = {"reported": case["reported"], "reproductions": hits,
                              "score_distribution": {str(k): v for k, v in sorted(all_scores.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))}}
    return report


if __name__ == "__main__":
    result = main()
    out = ROOT / "evaluation/audit/results/reconstruction-v2.0.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for cid, r in result.items():
        print(f"== {cid} reported={r['reported']} dist={r['score_distribution']}")
        seen = set()
        for h in r["reproductions"]:
            key = (h["overall"], h["requests"], h["decisive"])
            if key in seen:
                continue
            seen.add(key)
            print("   ", h["overall"], "|", h["requests"], "| sender:", h["sender"], "| tactics:", h["tactics"], "|", h["decisive"], "+", h["reinforcement"])
