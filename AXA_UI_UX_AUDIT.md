# AXA 2.1 — UI/UX audit (before redesign)

This audit covers the frontend at commit `8bf4972`. No frontend file had been modified when it was written.

## 0. Method, sources and limits

**How the UI was rendered**
- The real `index.html`, `assets/axa.css` and `assets/app.js` ran in headless Chromium (Playwright).
- They ran against the **real analysis pipeline** through `tools/ui_fixture_server.py`.
- Gemini was replaced by **deterministic mock readings**. No live provider was reachable from this sandbox.

**What was swept** (`tools/ui_check.js`, 53 runs; raw data in `docs/ui-audit/before/report.json`, screenshots in `docs/ui-audit/before/`)
- **Viewports:** 320, 390, 768, 1440 and 1920 px.
- **Themes:** light and dark (OS preference).
- **Reduced motion.**
- **Large text:** 200% text.
- **States:**
  - results: benign, marketing, suspicious, critical (long deceptive URL with userinfo), family, inconclusive, protective, malformed URL;
  - failures: AI timeout, AI not configured, server error, OCR failure;
  - OCR success, and the busy state.

**What each run measured**
- horizontal overflow;
- text contrast (WCAG formula on computed colours);
- text under 14 px;
- controls under 44 px;
- unnamed controls;
- heading skips;
- infinite animations;
- the vertical position of the verdict and the action;
- whether the input is preserved after an error;
- the keyboard tab order.

**Limits**
- No screen reader was run, and no automated axe pass (axe-core is not installable here).
- Google Fonts could not load in the sandbox, so renders use the fallback font. That is itself a finding: §4, fragility.
- No real users were tested.

**The research report.** *UI/UX Research and Anti-AI-Slop Design Direction* was **not attached** to the task and is not in the project. This audit uses the research direction as **restated in the task brief**:
- the Evidence Desk language;
- the four verdict wordings;
- the 0–3 rubric;
- the motion bands;
- the four signature interactions;
- the accessibility targets.

Anything the full report adds is not reflected here.

## 1. Current experience map

```
Header (logo · nav · A− A+ Temă · mobile "Meniu")
Hero: 4.9rem H1 · lead · 3-step list · dark "desk" (textarea · Încarcă captură · Șterge · Verifică · AI pill · privacy) · 7 example chips (auto-run)
Result (#out, aria-live=polite, whole report injected):
  [AI-failure banner, amber]  →  dark verdict card:
     icon + "Seamănă cu…" + headline · BIG animated 0–100 number · summary · tri-colour meter with sliding pin
     action box · "Ce vrea mesajul (AI)" · reasons with chips (Alarmă/Atenție/Notă/Protector/Conflict)
     5 fact chips · 5 buttons (WhatsApp, SMS, voice, copy, new)
  "Ce să faci acum" (checkbox checklist) → scenario simulator (auto-plays on scroll, 1.6 s steps, range slider)
  "Radiografia mesajului" (AI view + marks + inert <button> list) → "Profilul indiciilor" + "Cum te prinde mesajul"
  "Linkuri" (URL anatomy) → "Ce am verificat și ce nu" (collapsed) → "Jurnalul dovezilor" (collapsed)
Guide (5 cards + golden rule) · Recovery "Ai căzut în plasă?" · History (opt-in) · Privacy · Footer
```

On mobile the critical result page is **≈15,000 px tall** (`critical-light-1440-full.jpg`; 390 px run in `report.json`).

## 2. Highest-severity issues (ranked)

**Severity scale:** 3 = trust/safety defect; 2 = UX debt; 1 = cosmetic.

| # | Sev | Issue | Evidence | Why it harms users |
|---|---|---|---|---|
| 1 | **3** | **No recovery entry in any result.** "Ai căzut în plasă?" exists only as a page section about 11,000 px below a mobile result, and its nav link is hidden behind "Meniu" on phones. Nothing branches by what the person did. | full-page screenshot; `index.html` `#ajutor` | A person who already clicked or paid, the most urgent user, has to search. |
| 2 | **3** | **An uncalibrated 0–100 number is the visual centrepiece.** It is a 7rem animated count-up with a sliding pin over a green-amber-red meter. A benign result shows a **green ✓ and a green "0/100"**, which reads as "verified safe". | `benign-light-390.jpg`; `app.js` `render()` `.big`, `.meter`, `.pin` | False precision. "No indicators found" becomes "safe". The number dominates the action. |
| 3 | **3** | **AI interpretation, technical facts and unknowns share one visual language.** Reasons mix AI tactics ("Grabă"), URL facts ("Adresa conține @") and catalog cues under the same chips. "AI semantic: completat" is a green chip beside "Expeditor: neverificat". | `critical-light-1440.jpg` | An AI opinion looks as authoritative as a parsed fact, and a coverage item looks like a pass. |
| 4 | **3** | **A provider failure is shown as a warning.** An amber banner sits above the verdict and pushes it 308 px down (390 px viewport). The result still shows a confident number. | `ai_timeout-light-390.jpg`; `report.json` firstScreen | A lack of information is styled as danger, and the partial nature of the check is visually detached from the verdict. |
| 5 | 2 | **The primary action sits below the first mobile screen** in failure states: 945 px from the result top at 390×844, and 508–690 px in normal states, below a 7rem number and a meter. **The most prominent button in an alert is "Avertizează pe cineva" (WhatsApp share)**, not the safety step. | `report.json` firstScreen; `app.js` `.acts` | It fails "what do I do now?" within seconds. |
| 6 | 2 | **Horizontal overflow at 320 px in every state** (34 px from the header controls). A long URL overflows by 131–203 px at 390/320 px, and by **538 px at 200% text**. | `report.json` overflowX; `text200-critical-390.jpg` | It breaks reflow (WCAG 1.4.10) and hides content. |
| 7 | 2 | **Fake activity and theatre:** an infinite orange "scan beam" over the input while waiting, a count-up number and a sliding pin, and a scenario that **auto-plays** when scrolled into view. | `axa.css` `.desk.scan::after`; `app.js` IntersectionObserver | Motion invents "AI working" and steals attention. |
| 8 | 2 | **Inert or fake controls:** the evidence list items are `<button>`s that do nothing; recommendations are checkboxes whose state means nothing and is lost; marks only change on hover or focus. Touch users get no explanation when tapping a mark. | `app.js` `marked()`, `.todo` | Interaction reality: controls promise behaviour they don't have. |
| 9 | 2 | **The whole report is injected into an `aria-live="polite"` region**, so a screen reader may read the entire report. Focus is not moved to the result. | `index.html` `#out` | It is noisy for screen-reader users and gives no predictable landing point. |
| 10 | 2 | **OCR runs the analysis before the person reviews the transcript.** "Am verificat transcrierea" only affects a later re-run. | `ocr-done-390.jpg` | The verify step is decorative. A misread URL is analysed as if confirmed. |
| 11 | 2 | **Low-information containers:** "Profilul indiciilor" (qualitative bars) and "Cum te prinde mesajul" (4 skewed stages) repeat the reasons. | full-page screenshot | They lengthen the page and add jargon ("Canal controlat"). |
| 12 | 2 | **Contrast failures:** "Notă" tag 1.75:1 (added in v2.1); orange buttons with dark text 4.11:1; level and tag chips 4.33:1; 156 low-contrast text instances across 53 runs. | `report.json` lowContrast | Text is unreadable for low-vision users. |
| 13 | 2 | **First screen on a phone:** a 4.9rem H1 and a 3-step list push the textarea to about 590 px. At 320×700 the field starts near the fold, and the "Verifică" button is below it. | `home-light-320.jpg`, `home-light-390.jpg` | The primary task is delayed by a slogan. |
| 14 | 2 | **Remote font fragility:** Plus Jakarta Sans loads from Google Fonts, a third-party request. In Plus Jakarta, `I` and `l` are near-identical; the fallback was used in every render here. | `index.html` `<link>`; CSP | Offline or blocked loads change the layout. Character ambiguity matters when reading URLs and codes. |
| 15 | 1 | **Shape and type noise:** radii of 2.2, 2, 1.6, 1.2 and 999 rem; pills everywhere; uppercase letter-spaced micro-labels; an 8.6 px "SCAM DETECTOR" logo label (the only text under 14 px); a decorative full-height skewed orange stripe behind the page. | `axa.css` | Weak hierarchy, with generic "rounded SaaS" cues diluting the identity. |
| 16 | 1 | **Jargon:** "Analiză AI activă (gemini-3.5-flash-lite)", "Radiografia", "Canal controlat", "Jurnalul dovezilor", "potrivire fără diacritice/spații", "Copiază adresa „stricată”". | various | These are not everyday Romanian for the target audience. |

**What was not broken:**
- Input survives server errors and OCR failures (both verified).
- Errors use `role="alert"`.
- Escaping is consistent (`esc()`).
- Links in the message are never made clickable.
- The share text is privacy-safe.
- History is opt-in and stores no message text.
- Reduced motion disables the beam and the count-up.
- The keyboard order is logical, and the skip link works.
- Dark theme contrast was mostly acceptable.

## 3. Anti-slop rubric (0–3) by component, before

The criteria are truthfulness, priority, state completeness, evidence separation, interaction reality, visual specificity, accessibility and copy specificity.

| Component | Truth | Priority | States | Separation | Interaction | Visual | A11y | Copy | Worst |
|---|---|---|---|---|---|---|---|---|---|
| Hero + input | 1 | 2 | 1 | – | 1 | 1 | 2 | 1 | 2 |
| Verdict card (number/meter) | **3** | **3** | 2 | **3** | 2 | 2 | 2 | 1 | **3** |
| Action + share row | 1 | 2 | 1 | – | 1 | 1 | 2 | 1 | 2 |
| Failure banner / partial | **3** | 2 | 2 | 2 | 1 | 1 | 1 | 1 | **3** |
| Recovery | 2 | **3** | 2 | – | 1 | 1 | 1 | 1 | **3** |
| Scenario simulator | 1 | 2 | 1 | 1 | 2 | 2 | 2 | 1 | 2 |
| Message "Radiografia" | 1 | 1 | 1 | 2 | 2 | 1 | 2 | 2 | 2 |
| Profile + stages cards | 1 | 2 | 1 | 1 | 1 | 2 | 1 | 2 | 2 |
| URL anatomy | 2 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 2 |
| Coverage + ledger | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 2 | 2 |
| Busy state | 2 | 1 | 2 | – | 1 | 2 | 1 | 1 | 2 |

The verdict card, the failure banner and the missing recovery entry are **severity 3**, so they block release.

## 4. Theme, mobile, large-text, motion and accessibility findings

- **Light/dark.** The dark theme is a careful re-mapping, not an inversion, but the verdict card is always dark navy. In dark mode it becomes navy on navy with only a thin coloured edge. The amber banner is low-contrast in dark mode.
- **Mobile.** Everything is stacked, not recomposed. At 390 px the action appears after the score, the meter and the summary. The header controls overflow at 320 px.
- **Large text.** The app's own A+ goes to 160%, which is good. At 200% text the URL anatomy and the code element overflow by 538 px.
- **Motion.** Infinite scan beam; 1.1 s pin slide; count-up; auto-playing scenario (1.6 s per step); 0.5 s step fades. Reduced motion disables the beam and the count-up, but the scenario still jumps to its end without any user action.
- **Accessibility.**
  - Focus ring: 3 px orange, visible on cream, weak on orange buttons.
  - Live region too large.
  - No focus management on completion.
  - Marks are focusable but not operable by tap.
  - The switch "xr" relies on `aria-pressed` with only a visual label.
  - Headings are fine (no skips measured).
  - Unnamed controls: none found.

## 5. Top UX safety and truthfulness problems

1. A benign result is presented like a pass (green ✓, green 0/100).
2. The number and meter imply calibrated precision that POLICY.md explicitly denies.
3. AI opinion, parsed facts and unknowns are visually indistinguishable.
4. The recovery path is unreachable from the result.
5. A provider failure is shown as alarm while the verdict still looks complete.
6. OCR's "review" step comes after the analysis.

## 6. Design concept and implementation sequence

**Concept: "Masa de examinare" (Evidence Desk).** The result reads like a careful examiner's sheet, not an oracle's dial.

**The verdict band**
- A categorical verdict: shape + word + one reason. The four states are mapped from the backend's existing labels:
  - `critical` → **Indicii puternice de tentativă de fraudă**
  - `suspicious` → **Mesaj suspect**
  - `low` / `marketing` / `protective` → **Nu am găsit indicii clare de fraudă**, with a qualifier: notice, offer or warning
  - `inconclusive` → **Nu putem evalua suficient mesajul**
- Directly below it, an ink **action strip** with the single safest step, and a stigma-free **"Am apăsat deja / am trimis date / am plătit"** entry that opens branching recovery.

**The evidence**
- **The message "exhibit"** sits on cream paper with numbered evidence underlines, each linked one-to-one to its explanation (anchor links, so it works without JS).
- **Three visibly different provenance zones:**
  - *Ce înțelege AI* (cream, labelled interpretation);
  - *Observații tehnice* (ink, factual);
  - *Neverificat* (neutral dashed).
- **Domain anatomy:** the registrable domain is dominant, userinfo is struck out and explained, the path is folded, and nothing is clickable.
- **Advanced details** are opt-in: the scenario as a static, labelled hypothetical; the evidence ledger; and the internal indicator, shown as *"nu este o probabilitate"*.

**Visual system and motion**
- Cream/ink/orange DNA.
- A **separate danger red** and a **neutral slate for unknown**.
- Lora (editorial headings) with Inter `ss02` (disambiguated body), self-hosted.
- One radius scale.
- Borders over shadows.
- Motion only for feedback and continuity: 80–280 ms, interruptible, reduced-motion safe.

**Sequence**
1. Input and submission (privacy beside the action, honest busy state, cancel).
2. The result hierarchy (verdict, action, recovery).
3. Evidence, URL anatomy and provenance zones.
4. Failure, partial, OCR and reset states.
5. Guide, help and privacy sections.
6. Motion and theme polish.
7. The sweep, rerun with the same script, and the fixes.

## 7. What must remain untouched

**Untouched**
- Gemini, decision policy, URL forensics, OCR pipeline and database.
- Endpoints (`/api/analyze`, `/api/analyze-image`, `/api/status`) and every existing response field, including `risk_score`, `headline`, `verdict`, `assessment.*`, `scenario` and `share_text`.

**Allowed contract changes** (each additive or infrastructure-only, each tested)
- One **additive** presentation field (`analysis.ui`): the verdict state, title, one-sentence reason and mechanism-aware action, derived only from the existing assessment.
- The static-asset allow-list extended to self-hosted fonts.
- The CSP tightened to `font-src 'self'`, with Google Fonts dropped.
