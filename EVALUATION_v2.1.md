# AXA 2.1 — before/after evaluation

## What was measured, and what was not

| Kind | Status |
|---|---|
| **Live Gemini** | **Not measured.** There was no API key and no Google network in the build sandbox. No number below comes from a live model. |
| **Mocked semantic layer** | Hand-written "faithful" Gemini readings, frozen by SHA-256 *before* the v2.1 code existed, plus 7 realistic error modes. Everything downstream is the real code: validation, grounding, URL/PSL, catalog, rules, decision and presentation. This measures the **policy**, not Gemini. Same harness, same mocks, v2.0 run from the untouched commit `e6e6064`. |
| **Local fallback (no AI)** | Real, deterministic, on every fixture set. |
| **Seven reported messages** | Deterministic parts are real. Gemini's part was reconstructed in the audit (§3) and mocked here. |

All fixtures are synthetic or user-reported. The development sets (release, fresh v2.0, fresh v2.1 and the seven) were **seen during tuning**, so they are development data. The **sealed** set (24 cases) was written after tuning ended, hashed (`evaluation/audit/sealed_v21b.sha256`) and scored once per version. Its mocks were written by the same author as the policy, so it is less biased, not independent.

Reproduce:

```bash
python evaluation/audit/policy_eval.py --tag v2.1 --output /tmp/p.json            # development sets, 8 modes
python evaluation/audit/policy_eval.py --sealed --tag v2.1 --output /tmp/s.json   # sealed set
python evaluation/ai_first_evaluate.py --profile local --cases <set>.json --output /tmp/l.json
```

## 1. Mocked policy evaluation — development sets (105 messages: 59 scam, 46 non-scam)

An alert means an estimate of at least 35. The error modes are:
- **over_suspicious**: benign → `suspicious`. This was observed live (A, B, D, F).
- **direction_errors**: an own sign-in or a supplied code read as a request to the sender. Observed live (G).
- **under_suspicious**: scam → `suspicious`.
- **handover_lenient**: the scam's handover set to `unclear`.
- **ungrounded**: every quote paraphrased.
- **reading_only**: the scam is recognised but no consequential item is listed.
- **over_scam**: benign → `likely_scam`. Added after the freeze and applied to both versions.

| Mode | Version | Scam recall | Precision | Benign false alerts | Critical credential | Benign critical | Unestimated |
|---|---|---:|---:|---:|---:|---:|---:|
| faithful | v2.0 | 59/59 | 59/64 | 5/46 | 24/24 | 5/46 | 0/105 |
| | **v2.1** | 59/59 | **59/59** | **0/46** | 24/24 | **0/46** | 1/105 |
| over_suspicious | v2.0 | 59/59 | 59/91 | **32/46** | 24/24 | 5/46 | 0/105 |
| | **v2.1** | 59/59 | 59/59 | **0/46** | 24/24 | 0/46 | 1/105 |
| direction_errors | v2.0 | 59/59 | 59/70 | 11/46 | 24/24 | 11/46 | 0/105 |
| | **v2.1** | 59/59 | 59/59 | **0/46** | 24/24 | 0/46 | 6/105 |
| under_suspicious | v2.0 | 59/59 | 59/64 | 5/46 | 24/24 | 5/46 | 0/105 |
| | **v2.1** | 59/59 | 59/59 | 0/46 | **23/24** | 0/46 | 1/105 |
| handover_lenient | v2.0 | 59/59 | — | 5/46 | 24/24 | 5/46 | 0/105 |
| | **v2.1** | 59/59 | — | 0/46 | 24/24 | 0/46 | 1/105 |
| ungrounded | v2.0 | 59/59 | — | 5/46 | 14/24 | 1/46 | 0/105 |
| | **v2.1** | 59/59 | — | 0/46 | 14/24 | 0/46 | 2/105 |
| reading_only | v2.0 | 56/59 | 56/61 | 5/46 | 1/24 | 5/46 | 0/105 |
| | **v2.1** | 56/59 | 56/56 | 0/46 | 1/24 | 0/46 | 4/105 |
| over_scam | v2.0 | 59/59 | 59/91 | 32/46 | 24/24 | 5/46 | 0/105 |
| | **v2.1** | 59/59 | 59/68 | **9/46** | 24/24 | 1/46 | 25/105 |

### The seven reported messages (estimate; `None` = "Neestimat")

| Reading | Version | A | B | C | D | E | F | G |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| faithful | v2.0 | 0 | 4 | **75** | 4 | **75** | 4 | **82** |
| | v2.1 | 0 | 0 | 20 | 0 | 20 | 0 | 0 |
| over_suspicious (≈ live) | v2.0 | 38 | 40 | 80 | 40 | 80 | 40 | 82 |
| | v2.1 | 15 | 15 | 20 | 15 | 20 | 15 | 15 |
| direction_errors (≈ live G) | v2.0 | 0 | 4 | 75 | 82 | 75 | 82 | 82 |
| | v2.1 | 0 | 0 | 20 | None | 20 | None | 0 |
| **user-reported (live, v2.0)** | | 40 | 40 | 70 | 40 | 75 | 40 | 82 |

Under v2.1 all seven fall below the alert line in every mode except `over_scam`, where B scores 40 and C and E score 50. In that mode the model calls the message a scam outright, and the policy then follows the model when grounded bait or an outward action exists.

### Failures and costs (v2.1), not hidden by the aggregates
- **Critical-credential recall under `under_suspicious`: 23/24.** N04 (sign-in on `george-bcr.secure-acces.com`) is `suspicious` 50, not critical, when the model only says "suspicious". A sign-in on an unverified page needs a scam reading to become critical. This is deliberate: it is the boundary of the Tursib fix.
- **reading_only: 3 misses** (RH-029, FH-15, FH-19). They are `inconclusive`, never `low`. v2.0 also missed 3 here.
- **over_scam: 9 benign false alerts.**
  - Six are at 50, from a grounded promise or a payment under a model "scam" reading.
  - Three are at 40: a scam reading plus an outward click or call.
  - RH-039 sits at 70: the rules agree with a model "scam" reading.

  This is the remaining dependence on the model. It is 9/46, against 32/46 in v2.0.
- **More unestimated results** (1 → 25 in over_scam, 0 → 6 in direction_errors). These are cases where the model and the text, or the model and the rules, disagree. They show "Neestimat" instead of a confident false alarm.
- **RH-039 under a faithful reading → `inconclusive`.** The lexical rules still see "completezi parola…" as a credential request. v2.0 said critical 82.
- **Mocked faithful scams at `suspicious` rather than `critical`:** RH-010, RH-028, FH-12, FH-14, N10. These are money or personal data sent to a message-supplied destination under a scam reading (60/50). They were `suspicious` in v2.0 too.

## 2. Sealed holdout (24 messages: 12 scam, 12 non-scam), scored once

| Mode | v2.0 recall | v2.1 recall | v2.0 benign FA | v2.1 benign FA | v2.0 crit. cred. | v2.1 crit. cred. |
|---|---:|---:|---:|---:|---:|---:|
| faithful | 12/12 | 12/12 | 1/12 (S03 Netflix TV code → 82) | **0/12** | 4/4 | 4/4 |
| over_suspicious | 12/12 | 12/12 | 7/12 | **0/12** | 4/4 | 4/4 |
| direction_errors | 12/12 | 12/12 | 2/12 | **1/12** | 4/4 | 4/4 |
| under_suspicious | 12/12 | 12/12 | 1/12 | 0/12 | 4/4 | 4/4 |
| ungrounded | 12/12 | 12/12 | 1/12 | 0/12 | 3/4 | 3/4 |
| reading_only | 12/12 | 12/12 | 1/12 | 0/12 | 1/4 | 1/4 |
| over_scam | 12/12 | 12/12 | 7/12 | **1/12** (S09 newsletter click, 40) | 4/4 | 4/4 |

**The sealed set revealed one weakness, which was left unfixed** so that the measurement stays clean:
- S11, Steam Guard's code `4F7KQ`, is alphanumeric.
- When the model misreads it as requested, the supplied-value check misses it, because it only recognises numeric codes. The case scores 82.

## 3. Local fallback (no AI), real

Scam recall, non-scam false alerts and critical credential recall are **identical to v2.0 on every set**:

| Set | Recall | Non-scam false alerts | Critical credential |
|---|---|---|---|
| release | 3/21 | 1/18 | 3/8 |
| fresh v2.0 | 5/20 | 0/10 | 4/6 |
| first | 10/16 | 0/14 | 5/8 |
| holdout | 13/15 | 0/13 | 7/7 |
| fresh v2.1 | 10/18 | **1/18 → 0/18** | 7/10 |
| sealed | 3/12 | 0/12 | 3/4 |

Two things change:
- **Benign false alerts.** The N07 eMAG survey on `page.link` went from 75 to unestimated, and the seven-case C (the Orange promotion) went from 42 to unestimated.
- **Scores.** Several scam scores moved within their label, because the additive v2.0 fallback double-counted URL points (for example 100 → 70–80).

The fallback stays weak by design. It is the v1.3 rule engine, and it labels most messages "Neestimat".

## 4. Technical findings (real, deterministic)

| Input | v2.0 | v2.1 |
|---|---|---|
| `livrarii.FAN` in the FAN message | link to `livrarii.fan` | no link |
| `orange.onelink.me`, `emag.page.link` | typosquatting, 30 → identity 75 | brand on a third-party host, 15; identity cue 20 |
| `olx.ro-livrare.com` | 30 (subdomain label) | 45, embedded official hostname |
| `https://x.test/a#https://official…` | no flag | embedded address flagged; credential entry there → critical |
| `bcr.secure-login.com` | 30, typosquatting | 30, third-party host with service terms (not a lookalike) |
| Lookalikes such as `bcr-verificare.top`, `bcr.ro.login-check.example`, `digi-ro.web.app`, confusables, userinfo decoys | caught | unchanged |

## 5. Other measurements

- **Gemini calls:** still exactly 1 per message. The system prompt grew from about 4.2k to about 5.6k characters (roughly +400 tokens). The provider settings, timeout and retries are unchanged, and `maxItems` is still stripped. A test enforces the allowed schema keywords.
- **Pipeline latency, excluding the provider:** median 1.7 ms, p95 3.8 ms over 105 messages. v2.0: 1.7 / 3.6 ms.
- **Gemini success or failure rate:** not measurable here (no live calls).
- **Tests:** 90 pass, 1 is skipped (FastAPI route tests need FastAPI and httpx, which are not installable here). Previously 56 passed and the same 1 was skipped.
- **UI:** the real `index.html`/`app.js` was driven in headless Chromium against the real pipeline, with the frozen mocks for the seven messages, through a test-only Starlette shim. All seven render as "Fără semne clare" or "Comercial". There is no scam-stage legend and no simulator, the third-party tag is amber, cues are shown as "Notă", and there were no JS errors besides the blocked Google Fonts.
