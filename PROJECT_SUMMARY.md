# AXA Scam Detector: everything done in this engagement (final build 2.1.3)

This file summarises every step from the AXA 2.0 code as received to this build, in order, and gives the final verification status. The detailed documents are linked from each step.

## 1. The steps

| # | Step | What changed | Details |
|---|---|---|---|
| 1 | **Detection audit** | Reconstructed why AXA 2.0 flagged 7 legitimate messages (Cargus, Orange, Tursib…) as fraud. **Root cause:** risk came from labels and AI hunches, not from what the message actually asks for. | [AUDIT_DECISION_ENGINE.md](AUDIT_DECISION_ENGINE.md) |
| 2 | **Decision engine v2.1** | Risk is now decided by **mechanism**: which asset (code, password, card, money, access), handed to whom, on what kind of destination (official, unverified or deceptive link, or nowhere). Every AI quote must be found in the text. Protective messages ("nu dați codul") are recognised. "Unestimated" is honest: no number is invented. Gemini's `maxItems` fix is kept, and the offline fallback still works. | [POLICY.md](POLICY.md), [CHANGELOG.md](CHANGELOG.md) |
| 3 | **Evaluation** | Before/after on 105 development messages and a sealed 24-message holdout, using frozen mock readings and 7 error modes (no live Gemini was available). Benign false alerts went from **5/46 to 0/46** with faithful readings and from **32/46 to 0/46** with over-suspicious ones. Scam recall stays 59/59. | [EVALUATION_v2.1.md](EVALUATION_v2.1.md) |
| 4 | **UI audit + "Evidence Desk" redesign** | The verdict comes first, then the action. Recovery steps are offered for every result. Evidence is underlined in the message. Links are shown as a domain anatomy, and three zones separate what the AI understood, what was checked and what was not. | [AXA_UI_UX_AUDIT.md](AXA_UI_UX_AUDIT.md), [AXA_UI_UX_CHANGELOG.md](AXA_UI_UX_CHANGELOG.md) |
| 5 | **Visual polish 2.1.1 ("alive")** | The green → amber → red **scale** is restored and placed only from backend data. Fonts are now Bricolage Grotesque + Work Sans (OFL, self-hosted). The AXA slash is the visual motif. There is a motion system with reduced-motion support. Results on a phone are about half as long. | [VISUAL_POLISH_AUDIT.md](VISUAL_POLISH_AUDIT.md), [VISUAL_POLISH_CHANGELOG.md](VISUAL_POLISH_CHANGELOG.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) |
| 6 | **"AXA în chat" (`/chat`)** | A messaging-style simulation using the same engine, with a 3-lamp **semaphore**, the scale and every result section reachable as quick replies. It is additive: the main interface is untouched. | [CHAT_CONCEPT.md](CHAT_CONCEPT.md) |
| 7 | **Product idea: AXA Radar** | Anonymous campaign early-warning from verifications. Proposed only, **not built**; kept as a separate roadmap item, as in the pitch. | answer in conversation; pitch §6 |
| 8 | **Pitch strategy review** | Removed the 2 €/month subscription row, which contradicted "AXA Free" and "we don't promise B2C pricing". | [docs/pitch/](docs/pitch/AXA_Free_AXA_Edu_Strategie_Si_Pitch.md) |
| 9 | **GDPR** | An information section at the bottom of the main page, and a **consent dialog before the first check** on `/` and `/chat`. Refusing sends nothing; consent can be withdrawn. | [GDPR_CONSENT.md](GDPR_CONSENT.md) |
| 10 | **AXA for Education (`/education`)** | A "coming soon" preview with a two-track conceptual lesson (fraud / misinformation & bots), fictional examples only and no API calls. It adds a fourth nav link, and the links move into a "Meniu" panel on narrow screens. | [EDUCATION_PAGE.md](EDUCATION_PAGE.md) |

## 2. Final verification (run on this exact build)

**Environment.** Headless Chromium (Playwright) against `tools/ui_fixture_server.py`, which runs the **real pipeline with mock Gemini readings**. Python 3.13. FastAPI is not installed in the sandbox, so `main.py` itself was not run; it serves the same files and routes.

| Check | Result |
|---|---|
| `python -m unittest discover -p 'test_*.py'` | **112 tests OK** (1 skipped: FastAPI route test) |
| `evaluation/audit/policy_eval.py` (mocked policy, 105 messages, 8 reading modes) | Identical to EVALUATION_v2.1.md: recall 59/59; benign false alerts 0/46 in 7 of 8 modes (9/46 in the deliberately over-scam mode) |
| `tools/ui_check.js`, main page | **65 runs:** 10 states, 320–1920 px, both themes, expanded views, 200% text. 0 overflow, 0 contrast failures, 0 text under 14 px, 0 unnamed controls, 0 errors |
| `tools/chat_check.js`, `/chat` | **34 runs** clean. Lamps match the backend zone, and no lamp is lit when the risk is not estimated. Error keeps the text; retry works |
| `tools/consent_check.js`, GDPR | **18/18:** nothing reaches `/api/analyze*` before "da"; refusal and Escape stop the check; withdrawal works; consent is shared between pages |
| `tools/education_check.js`, `/education` | **30 renders** at 1440–320 px, both themes, both tracks, 200% text: clean. **33/33** behaviour and navigation checks. 0 API calls |
| Detection code since v2.1 | Unchanged. The only engine change after v2.1 is the additive `ui` field in the response |

## 3. What is still open before a public launch
1. **Live Gemini has never been measured.** Run `evaluation/ai_first_evaluate.py --profile live` with a key, ideally on new real messages.
2. **GDPR.** Fill in the controller's identity and contact, set log retention, and get a legal review of the text. Optionally make the server enforce and log consent (version + time, no text), so consent can be proven.
3. **Real devices.** Safari/iOS, Firefox and Android phones, and screen readers by ear (VoiceOver, TalkBack, NVDA). None were tested here.
4. **Run `main.py` itself** once with FastAPI installed (`pip install -r requirements.txt`) and smoke-test `/`, `/chat`, `/education`.
5. **User testing**, especially with older adults, and the AXA Edu pilot from the pitch.

## 4. Run it
```bash
pip install -r requirements.txt
GEMINI_API_KEY=...  python -m uvicorn main:app --port 8000   # without a key: local fallback
# open http://127.0.0.1:8000/  ·  /chat  ·  /education

# Without a key, with mock readings (test-only, never deploy):
python -m uvicorn tools.ui_fixture_server:app --port 8765
NODE_PATH=$(npm root -g) node tools/ui_check.js /tmp/shots   # and chat_check / consent_check / education_check
```
