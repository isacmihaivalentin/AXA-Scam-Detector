# AXA 2.1.1 UI — "Evidence Desk, alive"

The audit and the reasoning behind each decision are in [VISUAL_POLISH_AUDIT.md](VISUAL_POLISH_AUDIT.md); the tokens and components are in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md). Screens: `docs/visual-polish/` (`before/`, `after/`, and the side-by-side `compare-*.jpg` sheets).

**Nothing in the detection pipeline changed.** The decision engine, thresholds (`ALERT=35`, `CRITICAL=70`), labels, endpoints, Gemini client and its `maxItems` stripping, URL forensics, the database, reputation and OCR are as they were in 2.1.0. The only backend change is additive: `analysis.ui.spectrum`, a tested presentation adapter.

## What changed

### 1. The green → amber → red risk scale is back
- It sits inside the verdict card, directly under the verdict and qualifier, above the one-line reason. The verdict and the action still lead.
- **Zones are the policy thresholds**: 0–34 *Fără indicii clare*, 35–69 *Suspect*, 70–100 *Indicii puternice*. A test pins them to `decision.ALERT` / `decision.CRITICAL`.
- **The marker position comes only from `analysis.ui.spectrum`** (`presentation.spectrum()`), never from browser arithmetic. A test checks that `risk_estimate` is not used to draw anything.
- **No position is invented.**
  - `risk_estimate = null` → `status: "unestimated"`: a hatched neutral track, no marker, no zone highlighted, and the words "Nu putem poziționa mesajul pe scală…".
  - AI did not run and the local result would land in green → `status: "partial_unplaced"`: no green marker, "Fără interpretarea AI nu poziționăm mesajul în zona verde." A rules-only *warning* is still placed, because evidence of danger is never hidden.
- The number is de-emphasised to one muted line: "Indicator orientativ: 87 din 100, nu o probabilitate." There is no "X% șanse" anywhere.
- **Not colour-only.** The current zone name is bold and carries the slash mark; the screen-reader text states the zone and that the indicator is not a probability; the zone ticks are physical gaps in the bar.
- The marker is the AXA slash (ink parallelogram with a paper outline). It glides in once, 650 ms ease-out, from the left end; no bounce, no repeat. Under reduced motion it is simply drawn in place.
- At very narrow widths or very large text the zone names reflow into a short list under the bar (container query) instead of breaking words.

### 2. Typography: Lora + Inter → Bricolage Grotesque + Work Sans
- **Bricolage Grotesque Bold** for display (hero, verdict, section heads, action line, disclosure questions). Warm ink-trap details; personality without whimsy.
- **Work Sans 400/700** for everything else. Open, wide forms at 18 px; a tailed `l`, so `I`, `l`, `1` are distinct without feature flags.
- Monospace (system stack, nothing shipped) only for URLs, codes and the domain anatomy.
- No tracked all-caps labels remain; the logo wordmark is the only uppercase.
- Chosen from rendered comparisons of three directions (`docs/visual-polish/type-directions.png`, `type-glyphs.png`), including Romanian uppercase `ĂÂÎȘȚ` and the I/l/1, 0/O pairs.
- **Licensing:** both are SIL OFL 1.1 with **no Reserved Font Names**, so subsetting is permitted. Licences ship next to the files: `assets/fonts/BricolageGrotesque-OFL.txt`, `assets/fonts/WorkSans-OFL.txt`.
- **Files:** `bricolage-bold.woff` (29 KB), `worksans-regular.woff` (28 KB), `worksans-bold.woff` (30 KB); subset to Basic Latin, Latin-1, Latin Extended-A, Romanian comma-below `Șș Țț`, and common punctuation (`„”`, `–—`, `…`, `€`, arrows). Total font payload 317 KB → 87 KB.
- Self-hosted through the existing allow-listed `/assets/fonts/{name}` route; CSP stays `font-src 'self'`. No Google Fonts request.

### 3. Energy, with restraint
- **One motif:** the orange slash from the AXA logo. It appears as the hero composition (three parallel bars behind the input desk, desktop only), the scale marker, the section-heading marks, the "Ce faci acum" mark and the selected-evidence edge. Nothing else is decorative.
- **Hero:** "Nu apăsa încă. *Verifică* mai întâi mesajul." with the accent word in brand orange; the input desk is deep navy again, with a cream writing surface and a single vivid orange "Verifică mesajul" button (full-width on phones).
- **Verdict card:** a coloured left edge (dashed for "no verdict"), shape mark + short pill (Alertă / Atenție / Rezultat / Fără verdict), large verdict, the scale, the reason. The action sits beside it on desktop and directly under it on phones, on a navy panel for alerts and on sand for benign results, so a benign result stays light.
- **Section rhythm:** a navy help band, a sand band with five numbered sign cards and the golden-rule panel, then the privacy section on paper.
- **Tactile controls:** buttons lift 1 px on hover and press down on click (110 ms); chips, tiles and cards respond the same way.
- **Evidence highlights:** underlines keep their four line styles; on hover or selection the tint fills upward under the phrase, the numbered tag turns orange, and the matching note slides 4 px and gains a slanted orange edge, both on the same 210 ms timing.

### 4. Motion system
| Tier | Token | Used for |
|---|---|---|
| Feedback | `--d-fb` 110 ms | press, hover, focus, chip/tile response |
| Local | `--d-local` 210 ms (JS 220 ms) | disclosure height, evidence selection, recovery panel, display panel, step swap |
| Major | `--d-major` 320 ms | result reveal (card rises 14 px + fades; disclosures follow 80 ms later), theme cross-fade |
| Marker | `--d-marker` 650 ms | one glide of the scale marker |

- Easing is `cubic-bezier(.22,1,.36,1)` (ease-out, no overshoot) everywhere.
- **Submit → result continuity:** the button turns into a spinner + "Se verifică…", the status line shows real elapsed seconds and **Anulează**, the old result dims to 40%, then the new card rises in and the page scrolls to it (smooth only when motion is allowed). Focus moves to the verdict heading.
- **Disclosures** animate height with the Web Animations API and are **interruptible**: a second press mid-animation reverses from the current height. Under reduced motion they toggle natively.
- **Screenshot input:** drag-over highlights the desk with a dashed orange edge; while reading, a chip says which file is being read; afterwards the chip offers **Înlocuiește** and **Elimină captura**. Pasting an image into the box also works. Failures keep whatever was in the box and offer *Încearcă din nou / Alege altă captură / Lipește textul manual*.
- **Not used:** fake progress, scanner beams, shimmer, blinking, parallax, staggered cascades, overshoot. The only looping animation is the spinner inside the busy button, and only while a request is actually running.
- **`prefers-reduced-motion: reduce`:** every transition and animation is cut to ~0 ms, the spinner stops, smooth scrolling is off, the marker is drawn in place, disclosures toggle natively. No information depends on motion.

### 5. Shorter default results (progressive disclosure)
Visible first: verdict + scale, one-line reason, the action, and one recovery trigger. Then question-shaped disclosures, each with a one-line summary of what is inside:
- **„De ce am ajuns la această concluzie?”** — the message with highlights and the numbered explanations side by side on desktop. Open by default for alerts, closed for everything else.
- **„Ce știm despre link?”** — its summary already names the real domain and its status (e.g. "Duce pe **secure-george-verificare.example** · structură înșelătoare").
- **„Ce am verificat și ce nu”** — the three provenance zones; summary like "Interpretare AI · 3 verificări tehnice · 4 lucruri neverificate".
- **„Cum ar putea continua?”** — the hypothetical scenario, alerts only, opt-in, labelled *ipotetic* on every step.
- **„Detalii tehnice”** — indicator, confidence, limits, evidence ledger.

Removed repetition: the domain is printed once large (facts now say "acest domeniu"), the anatomy row only appears when it adds something, the AI claim summary is no longer repeated, and the eight-row recovery list in the result became **one button** that opens tiles (mechanism-relevant situations first, marked "potrivit aici") with the chosen steps shown below. The full recovery section remains on the page and works without JS.

**Measured result height on a 390 px phone (light, all disclosures in their default state):**

| State | Before (2.1.0) | After (2.1.1) |
|---|---|---|
| benign | 3,146 px | 1,572 px |
| marketing | 3,777 | 1,611 |
| protective | 2,409 | 1,439 |
| inconclusive | 2,765 | 1,450 |
| invalid URL | 3,586 | 1,601 |
| suspicious | 3,701 | 2,596 |
| family impersonation | 3,828 | 2,918 |
| critical | 5,208 | 3,588 (evidence open by default) |
| AI timeout (critical) | 5,087 | 3,451 |
| AI not configured | 3,769 | 1,765 |

The action line starts 416–460 px below the result top in every full-analysis state on a 390 px phone, and 610–626 px when the partial-analysis note is shown; all inside the first 844 px screen.

## Verification actually performed

All runs used `tools/ui_fixture_server.py`: the **real** pipeline with **mock** Gemini readings. Headless Chromium (Playwright) only.

- `tools/ui_check.js` full sweep: **65 runs** — 10 states × 320/390/768/1440/1920 (light), 390/1440 (dark), expanded views (every disclosure open, recovery tile chosen, evidence selected) for critical/benign/inconclusive at 390/1440 in both themes, 200% text at 390, server error, OCR failure, OCR success, keyboard order, busy state with motion. Result: **0** horizontal overflow, **0** contrast failures (text 4.5:1 / large 3:1, computed per element), **0** text under 14 px, **0** unnamed controls, **0** heading skips, **0** console errors, **0** infinite animations at rest; the only animation while busy is the spinner. Report: `docs/visual-polish/after/report.json`.
- Behaviour script (motion on and off): marker starts at 47 px and ends at 412 px = 87% of the track with motion, and is at 412 px immediately with reduced motion; keyboard Enter on a disclosure summary opens it with focus kept on the summary, a close-then-reopen mid-animation ends open with no leftover inline styles, a third press closes it; recovery button toggles `aria-expanded`, tiles show 3 steps; drag-enter adds the drag state, drop reads the screenshot and shows the chip, "Elimină captura" clears text/chip/result and focuses the box; an OCR failure keeps typed text and focuses the alert; "Încearcă din nou" succeeds once the fixture recovers.
- Spectrum states observed in the browser: benign 0 → placed in green; suspicious 60 → Suspect; critical (rules only, AI timeout) 85 → placed in red; inconclusive, invalid URL and **AI-not-configured benign** → no marker.
- Visual review of screenshots at 320, 390, 768, 1440, 1920, both themes, 200% text: home, benign, marketing, protective, suspicious, critical, family, inconclusive, invalid URL, AI timeout, AI not configured, errors, OCR.
- `python -m unittest discover -p 'test_*.py'`: **102 tests, OK** (1 skipped: FastAPI is not installed in this sandbox, so the route test is skipped). New: 4 spectrum tests and 1 static frontend contract test (scale drawn only from the adapter, no inline styles under the CSP, no safety words in the verdict pills, motion tokens and reduced-motion block present).

## Limitations (honest)
- **Not done:** hands-on user testing, testing with older adults, Safari/WebKit, Firefox, real phones or tablets, VoiceOver/TalkBack/NVDA. Screen-reader support was checked structurally (names, roles, live regions, focus order), not by listening.
- Contrast is measured on computed solid colours; text over the hero slashes was avoided by layout rather than measured.
- The scale's amber segment is 2.1:1 against the card (WCAG 1.4.11 asks 3:1 for meaningful graphics). The scale does not rely on it: the zone names, the gaps at 35/70, the bar's outline (4.1:1) and the marker (ink 3.2–6.7:1 against every segment in light mode; its dark outline 6.2–8.8:1 in dark mode) carry the information.
- The FastAPI app itself was not run here (not installable offline); the fixture server serves the same `index.html` and assets. `main.py` changes are limited to the font allow-list and are covered by the static tests.
- Bricolage/Work Sans subsets cover Romanian, Western European and Latin Extended-A. Other scripts fall back to system fonts.

## Run instructions
Unchanged from 2.1.0 (see README). To review the UI without a Gemini key:
```bash
python -m uvicorn tools.ui_fixture_server:app --port 8765     # test-only, never deploy
node tools/ui_check.js /tmp/ui-shots                          # needs Node + Playwright
```
