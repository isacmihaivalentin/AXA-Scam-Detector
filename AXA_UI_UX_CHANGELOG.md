# AXA UI/UX changelog: v2.1 "Evidence Desk"

- **Audit:** `AXA_UI_UX_AUDIT.md`.
- **System:** `DESIGN_SYSTEM.md`.
- **Screenshots:** `docs/ui-audit/before`, `docs/ui-audit/after`, `docs/ui-audit/compare-*.jpg`.

**About the evidence.** All renders use the real frontend and the real analysis pipeline. Gemini is replaced by deterministic **mock** readings (`tools/ui_fixture_server.py`). No live provider was reachable from the build sandbox. The research report named in the brief was **not supplied**. The direction comes from the brief's own restatement of it.

## Preserved
- **Backend.** The detection engine, Gemini integration, URL forensics, OCR pipeline, database, endpoints and **every existing response field**.
  - The redesign changes no label, score or threshold.
  - The 90 detection and regression tests are unchanged and still pass.
- **Brand DNA.** Cream/sand, deep ink, restrained orange-red, and the AXA logo, now drawn in a single SVG with the wordmark.
- **Privacy safeguards.**
  - Escaping of every server and user string.
  - Submitted links are never clickable.
  - Privacy-safe share text.
  - Opt-in history that never stores message text.
  - The keys stay on the server.
- **Features.** OCR upload, transcript review, evidence highlighting, URL facts, the hypothetical scenario, the evidence ledger, theme and text-size controls, read-aloud, copy and share, and the guide and privacy sections.

## Refined
- **Verdict.** It is now categorical, in words and shape, mapped by a new **additive** adapter `analysis.ui` (`presentation.ui`, tested in `test_ui_contract.py`). The adapter supplies a one-sentence reason, a mechanism-aware action and the recovery situations suggested for the result.
  - **Strong:** "Indicii puternice de tentativă de fraudă".
  - **Suspect:** "Mesaj suspect".
  - **No clear signs:** "Nu am găsit indicii clare de fraudă", drawn as a magnifier, not a ✓.
  - **Unable:** "Nu putem evalua suficient mesajul".
- **Primary action.** It moved directly under the verdict, in an ink strip. Share and other utilities are secondary, and "Avertizează pe cineva" is no longer the most prominent button.
- **Provider failure.** It is now a neutral "Analiză parțială" note inside the verdict, not an amber banner above it.
- **Evidence.**
  - Numbered underlines are real anchors, linked one-to-one to their notes and usable by mouse, keyboard, touch and without JS.
  - Overlapping spans are listed, not dropped.
  - Underline styles differ (solid, dotted, dashed, double).
- **URL anatomy.**
  - The registrable domain is dominant.
  - Userinfo is struck through and explained.
  - Paths are middle-truncated, with the full defanged address available.
  - Third-party, official, deceptive and unknown relationships are each worded and coloured distinctly.
- **Provenance.** AI interpretation, technical observation and unverified items now sit in three visibly different zones.
- **Input.**
  - Privacy now sits beside the action, and the AI disclosure is set from `/api/status`.
  - An honest busy state shows elapsed seconds and offers **Cancel**.
  - Errors appear in an actionable summary that receives focus, with "Încearcă din nou" and "Mergi la casetă", and the text is always kept.
  - Example chips no longer require reading a 4.9rem slogan first.
- **Recovery.** Branching, stigma-free help for eight situations (opened, password, code/approval, card, paid, installed, documents, called). It is reachable from **every** result and from the header link "Am pățit deja ceva".
- **OCR.** The note now states plainly that the result is for the transcribed text, and that re-checking after a correction re-runs the analysis.
- **Typography.**
  - Lora and Inter with `ss02` disambiguation are self-hosted, and the Google Fonts request was removed. The CSP is now `font-src 'self'`.
  - The minimum text size is 14 px; body text is 18 px.
- **Header.** "Am pățit deja ceva" is always visible, and the text-size and theme controls moved into "Afișare" (Escape closes it). The header is sticky only on wide screens.
- **Accessibility.**
  - Focus moves to the result heading.
  - A short polite announcement replaces the old `aria-live` on the whole report.
  - The result is an `<article>` and the rail is an `<aside>`.
  - Table captions are present.
  - The form posts, so the message never lands in a URL even without JS.

## Removed (with rationale)

| Removed | Why |
|---|---|
| Giant animated 0–100 number, count-up, tri-colour meter and sliding pin | False precision (POLICY.md says the score is not a probability). It made benign results look like a "verified safe" pass. The number survives only inside "Detalii tehnice", worded "nu este o probabilitate". |
| Scanning beam over the input | It invented "AI activity". It was replaced by honest elapsed time and Cancel. |
| Auto-playing scenario with a range slider | Motion nobody asked for and a distraction above the evidence. It is now an opt-in disclosure, static and keyboard-native, with "ipotetic" on every step. |
| "Profilul indiciilor" and "Cum te prinde mesajul" cards | Low-information duplicates of the reasons, with jargon ("Canal controlat"). |
| Checkbox to-do list of recommendations | Fake interaction: the state meant nothing and was lost. The single action plus recovery replaces it. |
| Inert `<button>` evidence items | Buttons that did nothing. They became list items linked to anchors. |
| Chip badges on every reason ("Alarmă/Atenție/Notă…"), the 5 fact chips, and the "AI semantic: completat" green chip | Badge noise, and a coverage item styled like a pass. They were replaced by the provenance zones. |
| Decorative full-height skewed orange stripe; 2.2rem/999px radii | Shape noise. A three-step radius scale replaced it. |
| "Avertisment" example chip | The example set now covers the common cases (6). The protective case is still tested. |

## Anti-slop rubric (0–3), after implementation

| Component | Truth | Priority | States | Separation | Interaction | Visual | A11y | Copy | Worst |
|---|---|---|---|---|---|---|---|---|---|
| Intro + input | 0 | 0 | 0 | – | 1 (examples run immediately) | 0 | 0 | 0 | 1 |
| Verdict sheet | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Action + recovery | 0 | 0 | 0 | – | 0 | 0 | 0 | 0 | 0 |
| Partial / provider failure | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Evidence exhibit | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 (AI-written note text) | 1 |
| URL anatomy | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Provenance rail | 1 (AI summaries shown verbatim, labelled) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| Scenario | 0 | 0 | 0 | 0 | 0 | 1 (generic templates) | 0 | 0 | 1 |
| Busy / errors | 0 | 0 | 0 | – | 0 | 0 | 0 | 0 | 0 |

**No severity-3 or severity-2 items remain.**

## Verification (measured with `tools/ui_check.js`; 53 runs per version)

The runs cover:
- viewports of 320, 390, 768, 1440 and 1920 px;
- light and dark themes;
- reduced motion;
- 200% text;
- states: benign, marketing, suspicious, critical, family, inconclusive, protective, malformed URL, AI timeout, AI off, server error, OCR failure and OCR success.

| Metric | Before | After |
|---|---:|---:|
| Runs with horizontal overflow | 16 (max 538 px) | **0** |
| Low-contrast text instances (WCAG ratio, computed colours) | 156 | **0** |
| Text under 14 px | 50 | **0** |
| Controls under 44 px (average per run) | 1.8 | **0** |
| Unnamed controls / console errors / infinite animations | 0 / 0 / 0 (the beam was a pseudo-element, not counted) | 0 / 0 / 0 |
| Recovery entry present in phone results | 0 / 23 | **23 / 23** |
| Worst-case distance from result top to the primary action on a phone | 1,168 px | 560 px (inside a 320×700 screen) |
| Critical result page height at 390 px | 14,993 px | 10,174 px (all disclosures closed except recovery) |

**Scripted keyboard journey** (`tools/ui_check.js` plus a separate script), all passing:
- skip link → textarea → submit;
- focus lands on the result heading, with a polite announcement;
- 13 Tab stops to the first evidence mark;
- Enter selects it and focuses its note;
- recovery opens by keyboard;
- Escape closes "Afișare" and returns focus;
- Cancel during a slow analysis keeps the text and re-enables the button.

**Input is preserved** after a server error and after an OCR failure; in both cases focus moves to the error summary.

**Tests:** `python -m unittest` → **97 pass, 1 skipped** (FastAPI route tests need FastAPI and httpx, which are not installable here). `test_ui_contract.py` adds 7 tests:
- the four verdict states map existing labels without changing them;
- benign and unknown states never claim safety;
- partial analysis is flagged;
- the action follows the requested act;
- the response shape is a superset;
- fonts are self-hosted with licences and the CSP is tight;
- the JS never stores message text and never links submitted URLs.

## Known gaps (not validated)
- No screen-reader session was run (NVDA, VoiceOver, TalkBack). Only semantics, focus and announcements were checked programmatically.
- No real-device or low-power phone testing. Rendering is Chromium only: no Safari or Firefox, and no Windows ClearType check.
- **No live Gemini.** Real AI summaries may be long or oddly worded; the rail shows them verbatim (labelled "Interpretare automată… nu este o verificare").
- Lora ships as an unmodified 212 KB TTF. Serving it with compression (or as WOFF2 converted with the licence respected) would cut the weight. Inter is subset WOFF; brotli was unavailable here, so it is not WOFF2.
- The FastAPI font route in `main.py` was added but not executed here (no FastAPI). The Starlette fixture server mirrors it and was exercised.
- No users, older adults included, took part in any test. **No comprehension outcomes are claimed.**

## Proposed (not run) 5-second and task test protocol

**Participants:** 8–10 people, at least half aged 60 or over, with mixed technical confidence. Use their own phone where possible, at their usual text size.

1. **5-second test.** Show each result screen for 5 s (critical, suspect, no clear signs, unable, partial). Then ask:
   - "Ce ți-a spus AXA?"
   - "Ce ar trebui să faci acum?"
   - "E mesajul sigur?"

   **Success:**
   - the participant names the action;
   - for "no clear signs", does **not** answer "da, e sigur";
   - for "unable", says it is neither safe nor dangerous.
2. **Task: submit.** "Verifică acest SMS" (the participant pastes it, or uploads a screenshot). Measure time to the first submit and any hesitation at the privacy line.
3. **Task: recovery.** "Ai apăsat deja pe link și ai scris parola. Ce faci?" Success: they reach the password steps without searching.
4. **Task: domain.** "Pe ce site te-ar duce linkul?" Success: they name the registrable domain, not `www.bcr.ro@…`.
5. **Task: provenance.** "Ce a verificat AXA și ce nu?" Success: they mention that sender identity is unverified.

**Record:** success, time, errors, quotes. Report counts, not percentages, for n < 20.
