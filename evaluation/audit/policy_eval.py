"""Score the CURRENT decision pipeline on frozen mock interpretations, faithful and perturbed.

MOCKED evaluation: the semantic layer is a hand-written stand-in for Gemini (see
mock_interpretations.py). Everything downstream is the real code: validation and
grounding, URL forensics, catalog, rules, decision policy and presentation.

    python evaluation/audit/policy_eval.py --tag v2.0 --output evaluation/audit/results/policy-v2.0.json
"""
import argparse
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation/audit"))
for key in ("GEMINI_API_KEY", "AXA_WEB_RISK_API_KEY", "AXA_DATABASE_URL"):
    os.environ.pop(key, None)
os.environ["AXA_LOCAL_MODEL"] = "0"
os.environ["AXA_SQLITE_PATH"] = str(Path(tempfile.mkdtemp()) / "eval.sqlite3")

import database  # noqa: E402
import engine  # noqa: E402
import semantic_gemini  # noqa: E402
from mock_interpretations import MODES as FROZEN_MODES, MOCKS, perturb as frozen_perturb  # noqa: E402

# Added after the freeze (applies to every policy alike): the harshest observed-direction error,
# a benign message read as an outright scam. It shows how much the verdict still rests on the model.
MODES = (*FROZEN_MODES, "over_scam")


def perturb(mock, mode, truth):
    if mode != "over_scam":
        return frozen_perturb(mock, mode, truth)
    m = frozen_perturb(mock, "over_suspicious", truth)
    if truth != "scam" and m["overall"] == "suspicious":
        m["overall"] = "likely_scam"
    return m

database.initialize_sqlite(os.environ["AXA_SQLITE_PATH"])
SETS = {
    "seven": "evaluation/audit/seven_cases.json",
    "release": "evaluation/forensics/release_holdout.json",
    "fresh20": "evaluation/ai_first/fresh_holdout.json",
    "fresh21": "evaluation/audit/fresh_holdout_v21.json",
}


def load(name):
    cases = json.loads((ROOT / SETS[name]).read_text(encoding="utf-8"))
    for c in cases:
        c.setdefault("label", "benign")  # the seven reported messages are legitimate
        c["credential"] = bool(c.get("credential") or c.get("mechanism") == "credential_harvesting")
    return cases


def run(text, interp):
    raw = json.dumps(interp, ensure_ascii=False)
    out = engine.analyze_text(text, "mock", interpret=lambda t, k: semantic_gemini.interpret(
        t, k, generate=lambda *a, **kw: raw))
    return out["analysis"]


def metrics(rows):
    scams = [r for r in rows if r["truth"] == "scam"]
    other = [r for r in rows if r["truth"] != "scam"]
    cred = [r for r in rows if r["credential"]]
    return {
        "cases": len(rows),
        "scam_recall": [sum(r["alert"] for r in scams), len(scams)],
        "precision": [sum(r["alert"] for r in scams), sum(r["alert"] for r in rows)],
        "benign_false_alerts": [sum(r["alert"] for r in other), len(other)],
        "critical_credential_recall": [sum(r["label"] == "critical" for r in cred), len(cred)],
        "benign_critical": [sum(r["label"] == "critical" for r in other), len(other)],
        "inconclusive": [sum(r["estimate"] is None for r in rows), len(rows)],
        "missed_scams": [r["id"] for r in scams if not r["alert"]],
        "false_alerts": [f"{r['id']}:{r['estimate']}" for r in other if r["alert"]],
    }


def main(args):
    if args.sealed:
        # Sealed set: scored once per version, after tuning ended (see sealed_v21b.sha256).
        from sealed_mocks_v21b import SEALED
        MOCKS.update(SEALED)
        SETS.clear()
        SETS["sealed"] = "evaluation/audit/sealed_holdout_v21b.json"
    report = {"tag": args.tag, "note": "MOCKED semantic layer; deterministic layers are real.", "modes": {}}
    for mode in MODES:
        rows_by_set = defaultdict(list)
        for name in SETS:
            for case in load(name):
                interp = perturb(MOCKS[case["id"]], mode, case["label"])
                a = run(case["text"], interp)
                s = a["assessment"]
                est = s["risk_estimate"]
                rows_by_set[name].append({
                    "id": case["id"], "truth": case["label"], "credential": case["credential"],
                    "label": s["label"], "estimate": est, "alert": est is not None and est >= 35,
                    "strongest": (s["policy"]["strongest"] or {}).get("category"),
                })
        all_rows = [r for name, rows in rows_by_set.items() if name != "seven" for r in rows]
        report["modes"][mode] = {
            "holdouts_combined": metrics(all_rows),
            **{name: metrics(rows) for name, rows in rows_by_set.items()},
            "seven_scores": {r["id"]: r["estimate"] for r in rows_by_set.get("seven", [])},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    f = lambda p: f"{p[0]}/{p[1]}"  # noqa: E731
    print(f"{'mode':18} {'recall':>7} {'benignFA':>9} {'critCred':>9} {'benCrit':>8} {'inconc':>7}  seven")
    for mode, r in report["modes"].items():
        m = r["holdouts_combined"]
        print(f"{mode:18} {f(m['scam_recall']):>7} {f(m['benign_false_alerts']):>9} {f(m['critical_credential_recall']):>9} "
              f"{f(m['benign_critical']):>8} {f(m['inconclusive']):>7}  {list(r['seven_scores'].values())}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--tag", required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--sealed", action="store_true", help="score the sealed v2.1b holdout only")
    main(cli.parse_args())
