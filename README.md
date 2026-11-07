# AXA Scam Detector 2.1 (Gemini-first, mechanism-based decisions)

> **Start here:** [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) lists every step of this build (2.1.3), the final verification and what is still open before launch.

AXA is a Romanian-first assistant for checking suspicious SMS, WhatsApp, email, links and screenshots. It explains:
- what a message claims;
- what it wants you to do;
- which parts are suspicious, protective or ambiguous;
- which mechanism may be at work;
- what the links really point to;
- what was verified and what is still unknown;
- what to do next.

```
text / screenshot ──> FastAPI (main.py)
                       └─ engine.analyze_text()
                           ├─ Gemini structured interpretation ── validated + every quote located in the text
                           ├─ URL forensics (PSL, lookalikes, userinfo, IPs) ── catalog DB ── optional Web Risk
                           ├─ Romanian rules engine (cross-check, and offline fallback)
                           └─ decision.assess() ── POLICY.md ──> presentation ──> UI (index.html + assets/)
```

- **Gemini is the primary semantic interpreter.** When a key is configured, every message goes to it. It returns meaning only: no scores and no technical claims.
- **Python handles parsing, the catalog, reputation, grounding and the final decision.** See [POLICY.md](POLICY.md).
- **Risk comes from mechanisms, not labels.** Risk follows which asset would go where: to the sender, to an official, unverified or deceptive link, or nowhere (the recipient keeps control). An AI hunch or an ordinary call to action is a cue, not an alert. See the audit ([AUDIT_DECISION_ENGINE.md](AUDIT_DECISION_ENGINE.md)) and the measurements ([EVALUATION_v2.1.md](EVALUATION_v2.1.md)).
- **Without Gemini the app still works.** It falls back to the local rules and static URL checks, and says so on screen.

## Run on macOS (Python 3.12)

From this folder:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python database.py                       # creates ./axa.sqlite3 with the reviewed catalog
cp .env.example .env                     # then put your GEMINI_API_KEY in .env
set -a; source .env; set +a
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The privacy line beside the "Verifică mesajul" button says whether the text also goes to Gemini (from `GET /api/status`, which exposes no secrets). Use a single Uvicorn worker for the demo. No model weights are needed.

For a quick test, paste one of the example chips. With no key, the result shows a banner: *"Analiza semantică AI nu este configurată…"*.

### Interface (v2.1.1 "Evidence Desk, alive")

- **Design documents:** [VISUAL_POLISH_AUDIT.md](VISUAL_POLISH_AUDIT.md) and [VISUAL_POLISH_CHANGELOG.md](VISUAL_POLISH_CHANGELOG.md) (2.1.1), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), and the 2.1.0 [AXA_UI_UX_AUDIT.md](AXA_UI_UX_AUDIT.md) / [AXA_UI_UX_CHANGELOG.md](AXA_UI_UX_CHANGELOG.md).
- **Risk scale:** the green → amber → red scale is drawn from `analysis.ui.spectrum` (additive field). Its zones are the policy thresholds; unestimated results, and AI-less results that would land in green, are shown without a marker.
- **AXA for Education:** `/education` is a "coming soon" preview with fictional teaching examples; it calls no API. See [EDUCATION_PAGE.md](EDUCATION_PAGE.md).
- **GDPR:** an information section at the bottom of the page and a consent dialog before the first check; nothing is sent without "da". See [GDPR_CONSENT.md](GDPR_CONSENT.md).
- **Chat concept:** `/chat` shows the same checks as a messaging-style assistant (semaphore, scale and all result data). See [CHAT_CONCEPT.md](CHAT_CONCEPT.md).
- **Fonts:** Bricolage Grotesque (display) and Work Sans (text), self-hosted WOFF subsets in `assets/fonts` with their OFL licences. No external font request is made.
- **Checking the UI without a Gemini key** (test-only; mock readings, real pipeline; needs Node + Playwright for the sweep):

```bash
python -m uvicorn tools.ui_fixture_server:app --port 8765     # never deploy this
node tools/ui_check.js /tmp/ui-shots                          # screenshots + measured checks
```

## Configuration

Everything is set through environment variables. See [.env.example](.env.example).

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Enables semantic analysis and screenshot OCR. Stays on the server. |
| `GEMINI_MODEL` | Model ID. Default `gemini-3.5-flash-lite`. |
| `AXA_GEMINI_TIMEOUT_MS`, `AXA_GEMINI_RETRIES`, `AXA_GEMINI_CONCURRENCY` | Deadline (default 20 s), bounded retries for 429/5xx/timeouts (default 1), and concurrent calls (default 4). |
| `AXA_GEMINI=0` | Forces local-only mode. |
| `AXA_WEB_RISK_API_KEY` | Optional Google Cloud Web Risk Lookup. Without it, links show *Reputație: neverificată*. |
| `AXA_SQLITE_PATH` / `AXA_DATABASE_URL` | SQLite path, or a PostgreSQL/Supabase DSN (read-only role; `pip install "psycopg[binary]>=3.2,<4"`). |
| `AXA_LOCAL_MODEL=1` | Optional experimental mDeBERTa pass (`pip install -r requirements-ml.txt`, then `python semantic_analysis.py --prepare`). Off by default. |

Gemini is called through its REST `generateContent` endpoint using the standard library:
- fixed host, key sent in a header;
- no redirects followed;
- size-bounded responses;
- JSON-schema output, validated with Pydantic.

Provider errors are logged as a category only (`timeout`, `rate_limited`, `authentication_or_access` and so on), never as payloads.

## Database

The database interface is unchanged:
- `database.load_catalog()` returns `(entries, status)`;
- `load_reviewed_examples()` returns the curated test cases;
- the `brand_aliases` table stays optional;
- `schema.postgres.sql` is the migration for PostgreSQL/Supabase.

If the database is unavailable, the app uses the static list and reports `unavailable_static_fallback`. Submitted messages are never stored. Gemini never writes queries.

For Supabase, grant the runtime role read access:

```sql
GRANT USAGE ON SCHEMA axa TO axa_reader;
GRANT SELECT ON axa.brands, axa.official_domains, axa.scam_examples, axa.brand_aliases TO axa_reader;
```

## API

- `POST /api/analyze` with `{"text": "...", "ocr_reviewed": null|true|false}`
- `POST /api/analyze-image` with multipart `file` (PNG, JPEG or WebP, up to 5 MB). Gemini transcribes the image, then the transcript goes through the same pipeline. Returns 503 when Gemini is not configured.
- `GET /api/status`

Key fields of `analysis`:

| Field | Meaning |
| --- | --- |
| `assessment.label` | `critical`, `suspicious`, `inconclusive`, `low`, `protective` or `marketing` |
| `assessment.policy` | `version` (2.1), strongest item, `families`, `reinforcement`, `converged` |
| `assessment.risk_estimate` | 0–100, or **null** when evidence is insufficient or contradictory ("Neestimat"). Not a probability. |
| `assessment.confidence` | Interpretation confidence, separate from risk |
| `assessment.mechanism` | Category, Romanian label, description and source |
| `checks` | Coverage: `semantic_ai`, `threat_intelligence`, `database`, `sender_authentication: not_checked` and so on |
| `interpretation` | Gemini's claim and want summaries, claimed sender (`claimed_not_authenticated`) and overall reading |
| `highlights` | Validated spans in UTF-16 offsets, with explanations |
| `evidence` | The full ledger: source, status (supported, tentative, contradicted, context, corroborating), tier, `evidence_class` (technical, mechanism, cue, context) and quote. Requests add `handover`, `destination`, `destination_kind` and `destination_host`. |
| `profile`, `stages` | Qualitative levels per evidence category (no percentages) |
| `ui` | **v2.1, additive.** Interface verdict: `state` (strong, suspect, no_clear_signs, unable), `title`, `reason`, `action`, `action_detail`, `recovery_suggested`, `partial`. It is derived from `assessment` only and changes no decision. |
| `scenario` | Hypothetical, educational simulator. `null` unless an alert-level mechanism is established. |
| `share_text` | Privacy-safe summary with no message text, numbers, codes or links |
| `risk_score`, `risk_label`, `verdict` | Kept for existing callers |
| `rules` | The local rules engine's own result |

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m unittest -v           # 97 tests (1 skipped without FastAPI)
```

Gemini is always mocked in the unit tests. They test validation and policy, not live model quality.

## Evaluation

```bash
# Local fallback (no network):
python evaluation/ai_first_evaluate.py --profile local --cases evaluation/forensics/release_holdout.json --output /tmp/local.json
# Live Gemini-first. Records raw responses so the run can be re-scored offline:
python evaluation/ai_first_evaluate.py --profile live --cases evaluation/forensics/release_holdout.json \
    --record /tmp/release-rec.json --output /tmp/release-live.json
python evaluation/ai_first_evaluate.py --profile live --cases evaluation/ai_first/fresh_holdout.json \
    --record /tmp/fresh-rec.json --output /tmp/fresh-live.json
```

Run the two live commands **once each, before changing the prompt or the policy**. See "Comparison" below for why.

## v2.1 policy evaluation

`evaluation/audit/policy_eval.py` scores the real pipeline on frozen *mock* Gemini readings, faithful and under 8 realistic model-error modes. `--sealed` scores the sealed holdout. The results and their limits are in [EVALUATION_v2.1.md](EVALUATION_v2.1.md). In short, with the semantic layer mocked:
- **Faithful readings:** scam recall is unchanged at 59/59, and benign false alerts fall from 5/46 to 0/46.
- **The live-observed over-suspicious error:** benign false alerts fall from 32/46 to 0/46.

Live Gemini quality is still unmeasured.

## Comparison with the previous implementation (v2.0 vs v1.3)

All numbers are from synthetic fixtures. An alert means an estimated risk of at least 35.

| Set | Profile | Scam recall | Precision | Critical credential | Non-scam false alerts | Protective FA |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Release holdout (39, independent author) | v1.3 rules (re-run here) | 3/21 | 3/4 | 3/8 | 1/18 | 0/7 |
| | v1.3 rules + mDeBERTa (from the audit) | 4/21 | 4/6 | 3/8 | 2/18 | 1/7 |
| | **v2.0 local fallback** | 3/21 | 3/4 | 3/8 | 1/18 | 0/7 |
| | **v2.0 Gemini-first** | **not yet measured** | | | | |
| First holdout (42, development data) | v1.3 rules (re-run here) | 11/24 | 11/11 | 6/9 | 0/18 | 0/7 |
| | **v2.0 local fallback** | 11/24 | 11/11 | 6/9 | 0/18 | 0/7 |
| Fresh holdout (30, written for v2.0) | v1.3 rules (re-run here) | 5/20 | 5/5 | 4/6 | 0/10 | 0/3 |
| | **v2.0 local fallback** | 5/20 | 5/5 | 4/6 | 0/10 | 0/3 |
| | **v2.0 Gemini-first** | **not yet measured** | | | | |

How to read this table:
- **The fallback is intentionally identical to v1.3 rules,** and the re-runs reproduce the audit's numbers.
- **The Gemini-first improvement has not been measured.** The build environment could not reach Google's API and had no key. Run the live commands above to measure it.
- **The release holdout is clean for the Gemini profile.** The prompt was written without reading its cases.
- **The fresh holdout is not independent.** It was written by the same author as the prompt, and sealed before any live run (`evaluation/ai_first/fresh_holdout.sha256`).
- **After a live run, both sets count as exposed.** If prompt or policy changes are made in response, treat them as development data and write new cases.

## Known limitations and unverified integrations

- **Not live-verified in this build:**
  - Gemini calls (text and OCR);
  - Google Web Risk with a real key;
  - PostgreSQL/Supabase;
  - the FastAPI route tests (`RouteTests`). They run where FastAPI is installed; the build sandbox had no FastAPI, so the pipeline was tested directly.
  - The UI was driven in headless Chromium against the real Python pipeline, with canned Gemini responses.
- **Gemini quality is unmeasured on real or held-out messages.** The policy limits damage from a bad interpretation: ungrounded quotes cannot reach critical, a rules/AI conflict gives a null estimate, and technical findings cannot be cancelled. A confidently wrong grounded reading can still mislead.
- **Privacy:** message text goes to Google when AI is enabled. The UI says so, and suggests removing codes or card numbers before submitting.
- **Domain checks are static.** The catalog is small, and owners of domains outside it are unknown. Redirects, content, certificates and domain age are not checked.
- **The Public Suffix List is vendored** (snapshot 2025-12-28, `data/public_suffix_list.dat`, MPL-2.0). Refresh it occasionally.
- **The simulator uses generic educational templates per mechanism family.** It personalises only with validated facts: the requested object, and the parsed domain, which is labelled as not visited.
- **The legacy evaluation scripts were removed;** they targeted the v1.3 escalation gate. Their results and sealed sets remain in `evaluation/`. The old `*.sha256` engine manifests describe v1.3 files.
