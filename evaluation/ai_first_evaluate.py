"""Evaluate the Gemini-first pipeline on synthetic fixtures.

Profiles
  --profile local   No semantic AI (AXA_GEMINI=0): rules + static URL checks only.
  --profile live    Real Gemini calls (needs GEMINI_API_KEY). Use --record to save the raw
                    structured responses so the run can be re-scored without new calls.
  --profile replay  Re-score a recording made with --record (no network). Results are labelled
                    "replay" and are only as valid as the recorded live run.

Examples
  python evaluation/ai_first_evaluate.py --profile local --cases evaluation/forensics/release_holdout.json --output /tmp/local.json
  GEMINI_API_KEY=... python evaluation/ai_first_evaluate.py --profile live \
      --cases evaluation/forensics/release_holdout.json --record /tmp/rec.json --output /tmp/live.json

Alert = an estimated risk >= 35. Critical credential recall counts the "critical" label on cases
marked credential=true. All fixtures are synthetic; results do not measure real-world accuracy.
"""
import argparse
import json
import math
import os
import statistics
import sys
import tempfile
from collections import Counter
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Mechanism families used by the fixtures. Several AXA categories map onto one family.
FAMILY = {
    "credential_phishing": "credential_harvesting", "otp_or_authentication_theft": "credential_harvesting",
    "card_data_theft": "credential_harvesting", "identity_document_theft": "credential_harvesting",
    "advance_fee": "advance_payment", "reward_or_lottery": "advance_payment", "investment_fraud": "advance_payment",
    "job_scam": "advance_payment", "marketplace_scam": "advance_payment",
    "family_impersonation": "family_impersonation", "romance_or_trust": "family_impersonation",
    "institution_impersonation": "institutional_impersonation", "delivery_scam": "institutional_impersonation",
    "payment_redirection": "institutional_impersonation", "malicious_link": "institutional_impersonation",
    "account_takeover": "software_or_account_abuse", "malicious_authorization": "software_or_account_abuse",
    "remote_access": "software_or_account_abuse",
}
FAMILIES = sorted(set(FAMILY.values()))


def ratio(n, of):
    return {"n": n, "of": of, "rate": round(n / of, 4) if of else None}


def latency(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"median": round(statistics.median(ordered), 1), "p95": round(ordered[math.ceil(0.95 * len(ordered)) - 1], 1)}


def metrics(rows):
    scams = [r for r in rows if r["truth"] == "scam"]
    other = [r for r in rows if r["truth"] != "scam"]
    alerts = [r for r in rows if r["alert"]]
    ai = [r for r in rows if r["ai_status"] != "not_configured"]
    out = {
        "cases": len(rows),
        "scam_recall": ratio(sum(r["alert"] for r in scams), len(scams)),
        "scam_precision": ratio(sum(r["truth"] == "scam" for r in alerts), len(alerts)),
        "critical_credential_recall": ratio(sum(r["label"] == "critical" for r in rows if r["credential"]),
                                            sum(r["credential"] for r in rows)),
        "non_scam_false_alerts": ratio(sum(r["alert"] for r in other), len(other)),
        "protective_false_alerts": ratio(sum(r["alert"] for r in rows if r["protective"]), sum(r["protective"] for r in rows)),
        "normal_finance_false_alerts": ratio(sum(r["alert"] for r in rows if r["mechanism"] == "normal_finance"),
                                             sum(r["mechanism"] == "normal_finance" for r in rows)),
        "commercial_false_alerts": ratio(sum(r["alert"] for r in rows if r["truth"] == "commercial"),
                                         sum(r["truth"] == "commercial" for r in rows)),
        "inconclusive": ratio(sum(r["label"] == "inconclusive" for r in rows), len(rows)),
        "unestimated": ratio(sum(r["estimate"] is None for r in rows), len(rows)),
        "gemini_success": ratio(sum(r["ai_status"] == "completed" for r in ai), len(ai)),
        "gemini_failures": dict(Counter(r["ai_failure"] for r in ai if r["ai_failure"])),
        "request_ms": latency([r["ms"] for r in rows]),
        "gemini_ms": latency([r["ai_ms"] for r in ai if r["ai_ms"] is not None]),
        "mechanisms": {},
    }
    for family in FAMILIES:
        expected = [r for r in rows if r["mechanism"] == family]
        predicted = [r for r in rows if r["family"] == family]
        out["mechanisms"][family] = {"recall": ratio(sum(r["mechanism"] == family for r in predicted), len(expected)),
                                     "precision": ratio(sum(r["mechanism"] == family for r in predicted), len(predicted))}
    return out


def main(args):
    os.environ.pop("AXA_DATABASE_URL", None)
    os.environ.pop("AXA_WEB_RISK_API_KEY", None)
    os.environ["AXA_LOCAL_MODEL"] = "0"
    import database
    import engine
    import semantic_gemini

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    recording = {}
    if args.profile == "replay":
        recording = json.loads(args.replay.read_text(encoding="utf-8"))
    key = ""
    if args.profile == "live":
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise SystemExit("GEMINI_API_KEY is required for --profile live")
    captured = {}

    def interpret(text, api_key):
        if args.profile == "local":
            return semantic_gemini.interpret(text, "")
        if args.profile == "replay":
            item = recording.get(text)
            if item is None or item["raw"] is None:
                return None, {"provider": "gemini", "model": "replay", "status": "failed",
                              "failure": (item or {}).get("failure", "not_recorded"), "truncated": False, "elapsed_ms": None}
            return semantic_gemini.interpret(text, "replay", generate=lambda *a, **k: item["raw"])

        raw_holder = {}

        def recording_generate(*a, **k):
            raw_holder["raw"] = semantic_gemini.gemini_client.generate_json(*a, **k)
            return raw_holder["raw"]
        result, status = semantic_gemini.interpret(text, key, generate=recording_generate)
        captured[text] = {"raw": raw_holder.get("raw"), "failure": status.get("failure"), "model": status.get("model")}
        return result, status

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AXA_SQLITE_PATH"] = str(Path(tmp) / "eval.sqlite3")
        database.initialize_sqlite(os.environ["AXA_SQLITE_PATH"])
        for case in cases:
            started = perf_counter()
            payload = engine.analyze_text(case["text"], key or ("replay" if args.profile == "replay" else ""), interpret=interpret)
            elapsed = (perf_counter() - started) * 1000
            a = payload["analysis"]
            s, ai = a["assessment"], a["checks"]["semantic_ai"]
            estimate = s["risk_estimate"]
            mechanism = (s.get("mechanism") or {}).get("category")
            rows.append({
                "id": case["id"], "truth": case["label"], "mechanism": case.get("mechanism"),
                "credential": bool(case.get("credential")), "protective": bool(case.get("protective")),
                "label": s["label"], "estimate": estimate, "indicator_score": s["indicator_score"],
                "alert": estimate is not None and estimate >= 35, "confidence": s["confidence"],
                "predicted_mechanism": mechanism, "family": FAMILY.get(mechanism),
                "ai_status": ai["status"], "ai_failure": ai.get("failure"), "ai_ms": ai.get("elapsed_ms"),
                "ai_overall": (a["interpretation"] or {}).get("overall"),
                "strongest": s["policy"]["strongest"], "ms": round(elapsed, 1),
            })
            print(f"{case['id']:8} {case['label']:10} -> {s['label']:12} {str(estimate):>5} {ai['status']}", flush=True)
    result = {"profile": args.profile, "cases_file": str(args.cases), "metrics": metrics(rows), "rows": rows}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if args.record and captured:
        args.record.write_text(json.dumps(captured, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    m = result["metrics"]
    fmt = lambda d: f"{d['n']}/{d['of']}"  # noqa: E731
    print(json.dumps({k: fmt(m[k]) for k in ("scam_recall", "scam_precision", "critical_credential_recall",
                                              "non_scam_false_alerts", "protective_false_alerts",
                                              "normal_finance_false_alerts", "commercial_false_alerts",
                                              "inconclusive", "gemini_success")}, ensure_ascii=False))


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--profile", choices=("local", "live", "replay"), default="local")
    cli.add_argument("--cases", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--record", type=Path)
    cli.add_argument("--replay", type=Path)
    main(cli.parse_args())
