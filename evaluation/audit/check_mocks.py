"""Fail loudly if any mock quote is not an exact substring of its message."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "evaluation/audit"))
from mock_interpretations import MOCKS

def texts():
    out = {}
    for f in ("evaluation/audit/seven_cases.json", "evaluation/forensics/release_holdout.json",
              "evaluation/ai_first/fresh_holdout.json", "evaluation/audit/fresh_holdout_v21.json"):
        for c in json.loads((ROOT / f).read_text(encoding="utf-8")):
            out[c["id"]] = c.get("text") or c.get("message")
    return out

if __name__ == "__main__":
    t, bad = texts(), []
    for cid, m in MOCKS.items():
        text = t[cid]
        quotes = [r["quote"] for r in m["requests"]] + [x["quote"] for k in ("tactics", "promises", "threats", "protective_context") for x in m[k]]
        quotes += [q for q in (m["dependency"]["quote"], m["claimed_sender"]["quote"]) if q]
        quotes += [r["destination"] for r in m["requests"] if r["destination"]]
        bad += [(cid, q) for q in quotes if q not in text]
    missing = sorted(set(t) - set(MOCKS))
    print("mocks:", len(MOCKS), "missing:", missing, "bad quotes:", len(bad))
    for b in bad: print("  ", b)
    sys.exit(1 if bad or missing else 0)
