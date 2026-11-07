# AXA "Evidence Desk, alive": design system (v2.1.1 UI)

**Design thesis.** A warm desk where a message is examined, with one confident mark — the slash from the AXA logo — and a clear answer first.
- **Cream paper** holds what you read: your message and the plain explanations.
- **Deep navy** holds the input desk and the action you should take.
- **AXA orange** is the brand, the primary button and the slash motif.
- **The scale** (green → amber → red) places a message *only* when the backend estimated it.
- **"Unknown"** is a neutral slate with dashed or hatched edges. It is never placed between safe and dangerous.

All tokens live in `assets/axa.css` under `:root` (light) and the two dark-theme blocks (system preference and the explicit "Întunecată" choice).

## Colour roles

Measured with the sweep (`docs/visual-polish/after/report.json`): every visible text pair meets AA in both themes.

| Role | Token | Light | Dark | Used for |
|---|---|---|---|---|
| Page | `--paper` | `#F5ECDD` | `#121920` | Page background |
| Reading surface | `--paper-2` | `#FCF8F1` | `#1A232D` | Verdict card, disclosures, textarea |
| Quiet fill | `--sand` / `--sand-2` | `#EADCC4` / `#E2CFAF` | `#222D39` / `#2A3644` | Signs band, benign action panel, hovers |
| Hairline | `--line` | `#D9C6A6` | `#344252` | Decorative borders only |
| Field edge | `--field` | `#8A775B` | `#7C8A9A` | Scale outline (4.1:1) |
| Text | `--ink` | `#1D2833` (12.8:1) | `#F0E6D4` (14.3:1) | Body, headings |
| Secondary text | `--muted` | `#584C40` (7.1:1) | `#BDB3A4` (8.6:1) | Explanations |
| Navy desk | `--desk` / `--desk-2` | `#1D2833` / `#26344A` | `#243142` / `#2E3D51` | Input desk, "Ce faci acum", help band, recovery tiles |
| Text on navy | `--desk-text` / `--desk-muted` | `#FCF8F1` (14.1:1) / `#C9D0D8` | `#F0E6D4` (10.7:1) / `#A9B3BE` | |
| Brand | `--brand` | `#E4572E` | `#F27149` | Logo, slash motif, focus ring. Not body text. |
| Primary button | `--cta` / `--on-cta` | `#EE6A43` / ink (4.8:1, 19 px bold) | `#F27149` / `#121920` (6.1:1) | "Verifică mesajul", retry |
| Link | `--link` | `#AE3A12` (5.3:1) | `#F58A68` | Links, "potrivit aici" on light surfaces |
| On-navy accent | `--fit-on-dark` | `#FFB59C` (7.4:1 on navy) | same | "potrivit aici" on navy tiles |
| Danger / Caution / Clear / Unknown | `--danger` `--caution` `--clear` `--unknown` (+ `-tint`) | `#A3191F` `#7A4E00` `#25624A` `#46566A` | `#FF968C` `#F0C46B` `#86D1B2` `#AEBBC9` | Verdict edges, pills, marks, evidence kinds |
| Scale | `--sp-green` `--sp-amber` `--sp-red` | `#2E8B5E` `#E2A12B` `#D2412A` | `#4DB585` `#F0B84A` `#FF7A5C` | The risk scale only |

**Colour is never the only carrier of meaning.**

| Verdict | Shape | Pill | Edge |
|---|---|---|---|
| strong | octagon "!" | Alertă | solid danger |
| suspect | triangle "!" | Atenție | solid caution |
| no clear signs | magnifier (examined; deliberately not a check mark) | Rezultat | solid clear |
| unable | dashed square "?" | Fără verdict | dashed slate |

Evidence underlines differ by **line style**: Îngrijorător solid · De reținut dotted · Informativ dashed · Protector double.

## The risk scale

| Element | Rule |
|---|---|
| Zones | 0–34 *Fără indicii clare*, 35–69 *Suspect*, 70–100 *Indicii puternice* — exactly `decision.ALERT` / `decision.CRITICAL` (tested). Physical 3 px gaps mark 35 and 70. |
| Source | `analysis.ui.spectrum` from `presentation.spectrum()`. The browser never derives a position. |
| `placed` | Slash marker at `position`; current zone name bold with a slash; muted line "Indicator orientativ: N din 100, nu o probabilitate." |
| `unestimated` | Hatched slate track, no marker, no zone emphasised, the adapter's note. |
| `partial_unplaced` | AI missing and the local result is green: same neutral presentation, "Fără interpretarea AI nu poziționăm mesajul în zona verde." |
| Screen readers | One sentence from the adapter (`label`), e.g. "Pe scala de risc, mesajul este în zona „Suspect” (indicator orientativ 60 din 100, nu o probabilitate)." Visual parts are `aria-hidden`. |
| Marker contrast | Ink body with a paper outline: one of the two layers is ≥3:1 against every segment in both themes. |
| Narrow / large text | A container query turns the zone names into a short wrapped list under the bar. |

Never written: "X% șanse", "probabilitate de fraudă" as a figure, or a green marker for an analysis without AI.

## Typography

| Role | Face | Why |
|---|---|---|
| Display: hero, verdict, section heads, action line, disclosure questions | **Bricolage Grotesque Bold** | Warm ink traps and confident proportions; holds up from 20 px to 70 px. |
| Text: everything else | **Work Sans** 400 / 700 | Open, wide letterforms at 18 px; tailed `l` keeps `I l 1` distinct; clear `0`/`O`. |
| URLs, codes, domain anatomy | system `ui-monospace` stack | Character-by-character inspection only. Nothing shipped. |

**Licensing and files.** Both are SIL Open Font License 1.1 without Reserved Font Names, subset with `pyftsubset` to WOFF. Licences: `assets/fonts/BricolageGrotesque-OFL.txt`, `assets/fonts/WorkSans-OFL.txt`. Coverage: Basic Latin, Latin-1, Latin Extended-A, `Șș Țț` (comma-below), typographic quotes and dashes, `…`, `€`, arrows. Payload 87 KB total. `font-display: swap`; the display face and the regular text face are preloaded. CSP `font-src 'self'`.

**Scale** (root 16 px; the "Afișare" control scales it 100–160%)

| Use | Size |
|---|---|
| Body | 1.125rem (18 px), line height 1.6 |
| Meta (minimum) | 0.875rem (14 px) |
| Lead / reason | 1.0625–1.3rem fluid |
| Disclosure question | 1.15–1.35rem fluid, display face |
| Verdict | `min(clamp(1.85rem, …, 2.85rem), 12.5vw)` |
| Hero | `min(clamp(2.2rem, …, 4.4rem), 13vw)` |

The `vw` cap only matters at very narrow widths with very large text, where it keeps words from breaking mid-letter. No tracked uppercase labels.

## Spacing, shape, elevation

| | Values |
|---|---|
| Space | `--s1` .25 · `--s2` .5 · `--s3` .75 · `--s4` 1 · `--s5` 1.5 · `--s6` 2 · `--s7` 3 · `--s8` 5 rem |
| Radius | `--r-sm` 8 px · `--r` 14 px (buttons, cards, fields, tiles) · `--r-lg` 22 px (verdict card, input desk); pills only for the verdict pill, example chips and the help link |
| Elevation | Soft, long shadows only on the input desk and verdict card; disclosures gain a shadow when open; buttons lift on hover. |

**Signature shape:** the AXA slash, a parallelogram skewed −20° to −24°. Used for: the hero composition (desktop), the scale marker, section-heading marks, the "Ce faci acum" mark, the selected evidence edge and the "regula de aur" panel. Nowhere else.

## Motion

| Tier | Token | Duration | Used for |
|---|---|---|---|
| Feedback | `--d-fb` | 110 ms | hover lift, press, chip/tile/border responses |
| Local | `--d-local` | 210 ms (JS 220 ms) | disclosure height, evidence selection (phrase and note together), recovery panel, display panel, step swap |
| Major | `--d-major` | 320 ms | result reveal (14 px rise + fade, disclosures 80 ms later), theme cross-fade |
| Marker | `--d-marker` | 650 ms | single glide of the scale marker from the left end |

- Easing: `--ease-out` `cubic-bezier(.22,1,.36,1)`; `--ease-io` only for the theme cross-fade. No overshoot or bounce.
- Disclosures and the recovery panel animate height via the Web Animations API (CSP-safe), are interruptible, and fall back to native toggling under reduced motion.
- Busy: spinner inside the button, real elapsed seconds, **Anulează**. No progress bar, no staged fake steps.
- **Reduced motion:** all transitions/animations ≈0 ms, spinner stopped, no smooth scroll, marker drawn in place.

## Components

| Component | Pattern |
|---|---|
| **Input desk** | Navy card, label in display face, cream textarea with an orange focus ring, orange primary button (full width on phones), "Încarcă o captură" outline button, drag-and-drop with a dashed orange drag state, paste-an-image, a file chip (reading → *Înlocuiește* / *Elimină captura*), the OCR check note, the honest privacy line from `/api/status`. |
| **Verdict card** | Left: mark + pill, verdict, qualifier ("Seamănă cu: …"), scale, one-sentence reason, partial-analysis note. Right (≥960 px) or below: **Ce faci acum** panel (navy for alerts and "no verdict", sand for benign) with the single safest step, one supporting sentence and the recovery trigger. Footer: check another, warn someone (alerts only), copy summary (no message text), read aloud. |
| **Recovery** | In the result: one button → tiles for eight situations, mechanism-relevant ones first and marked "potrivit aici" → the chosen steps and the "În orice situație" line. On the page: the same eight situations as native `<details>` in the navy help band, working without JS. |
| **Disclosure** | `<details class="disc">`: a question in the display face, a one-line summary of what is inside, a round chevron button that rotates. |
| **Evidence** | Message on the left (sticky on desktop), numbered explanations on the right. Each phrase is an in-page anchor (`#ev-n`) so it works without JS; selection is mirrored with `aria-current`. Overlapping spans are listed as "nemarcat separat", never dropped. |
| **Link card** | The real domain printed once, large and monospace, underlined in its relationship colour; the anatomy row only when there is a subdomain, userinfo or path; plain facts with icons; the full address defanged in a disclosure with a copy button. Nothing is ever a link. |
| **Provenance** | Three different zones: *Ce înțelege AI* (paper, orange top edge, "nu este o verificare"), *Ce am verificat tehnic* (navy), *Ce nu am putut verifica* (dashed slate). |
| **Advanced** | Hypothetical scenario (alerts only; disclaimer first; "ipotetic" on every step) and technical details (indicator "nu este o probabilitate", confidence, limits, evidence ledger). |

## Focus, targets, reflow

- Focus: `3px solid var(--focus)`, offset 3 px; the textarea uses an orange border + soft ring.
- Targets: primary 52 px; all other controls ≥44 px; radio/checkbox 20 px inside ≥44 px labels.
- Sticky header only at ≥56em, with `scroll-padding-top`.
- Measured: no horizontal scroll at 320–1920 px, at 200% text at 390 px, in both themes, with every disclosure open.
