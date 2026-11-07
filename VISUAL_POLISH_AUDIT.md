# Visual polish audit: AXA 2.1 Evidence Desk → "Evidence Desk, alive"

**Scope.** This audit covers the current release (`ad39af1`), rendered in Chromium through `tools/ui_fixture_server.py`: the real pipeline with **mock** Gemini readings.

**Screens reviewed:**
- `docs/ui-audit/after/*.jpg`;
- a fresh quick sweep (`tools/ui_check.js --quick`);
- `docs/visual-polish/type-*.png`.

Items marked *(unverified)* are judgements that were not measured.

## What the current release gets right (keep)
- **Action first.** The verdict and the safest action appear in the first phone screen in every state (action ≤ 560 px from the result top).
- **Truthful states.** Words + shapes for the verdict, the neutral "unknown", the honest partial-analysis note, and no fake progress.
- **Accessibility.** Zero overflow at 320 px / 200% text, zero contrast failures, focus moved to the result, and recovery in every result.
- **Evidence anchors** that work without JS, a URL anatomy where the real domain dominates, and the three provenance zones.

## Findings

| # | Lens | Finding | Evidence |
|---|---|---|---|
| 1 | Hierarchy / length | **Everything is expanded at once.** On a 390 px phone the result is **3,146 px** (benign) to **5,208 px** (critical). Evidence, notes, link anatomy, three provenance panels, eight recovery rows and two disclosures all render by default. A benign result carries the same weight of technical sections as a scam. | sweep `resultHeight` |
| 2 | Typography | **Lora + Inter reads academic and corporate.** Lora's bookish, high-contrast serif on every verdict and heading makes the verdict feel like an essay title. Inter, used everywhere else, is the generic SaaS default. The pairing has no warmth or energy. Inter's `ss02` changed little in this build: `I`/`l`/`1` are still near-identical (`type-glyphs.png`). | `type-directions.png`, `type-glyphs.png` |
| 3 | Personality | **The visual energy has drained away.** The decorative orange slash, the dark input desk and the green→red bar (the old UI's most recognisable element) were removed. What remains is beige paper, thin borders and one navy strip. The home page is a text column and a white box. | `home-light-1440.jpg`, `critical-light-1440.jpg` |
| 4 | Verdict | **Categorical-only reads flat.** There is nothing at a glance that places the message on a scale. The magnifier icon is clever but quiet. Colour appears only as a thin top border. | `benign-light-390.jpg` |
| 5 | Motion | **Abrupt.** Disclosures snap open, the result appears with one 8 px rise, and evidence selection is an instant outline. There is no submit→result continuity beyond dimming, no feedback on buttons beyond a 1 px press, and theme changes snap. | source + render |
| 6 | Repetition | **The domain appears four times** (URL card heading, anatomy, facts, technical rail), and the AI summary is repeated in the rail. Recovery sits both in the result and as a full page section directly below. | critical render |
| 7 | Layout craft | **Desktop balance is off.** The sticky rail is taller than the column beside it on short results, and there are large empty right-hand areas on benign results. The recovery list is a tall stack of identical rows. The section bands (help, signs, privacy) look the same as each other, so the page has no rhythm. | 1440 renders |
| 8 | Interaction | Disclosure controls are small "+" glyphs with no summary of what is inside. There is no drag-and-drop for screenshots, and once an image has been read there is no way to remove or replace it other than clearing the box. *(unverified for touch comfort)* | source |
| 9 | Anti-slop | The previous pass removed slop correctly but overshot into "beige document". No severity-3 issues; this is personality and attention debt, not a trust defect. | — |

## Direction

**Keep:** the truth model, action-first order, recovery entry, anchors, URL anatomy, the three provenance zones, the tokens for danger, caution, clear and unknown, and all accessibility behaviours.

**Amplify**
- The AXA slash: the logo's orange stroke becomes the single graphic motif. It appears as the hero composition, the spectrum marker, the section dividers and the selection accent.
- The cream/navy contrast: the input desk becomes deep navy again.

**Rework**
- Typography (below).
- The verdict into a **"verdict card"**: big type, the **restored green→amber→red spectrum** with a slash-shaped marker, one reason, the action and recovery.
- The home hero, with an expressive headline whose accent word is in orange.

**Simplify (progressive disclosure)**
- The default result is the verdict, spectrum, reason, action, a single "Am făcut deja ceva" trigger, and a strip of up to three question-shaped disclosures:
  - **„De ce am ajuns aici?”**: message + evidence.
  - **„Ce știm despre link?”**: its summary line already names the real domain and the verdict on it.
  - **„Ce am verificat și ce nu”**: the provenance zones.
- Then an advanced row: the hypothetical scenario and the technical details.
- Each trigger states its content in plain words.
- Alerts open "De ce" by default; benign results keep everything closed.

**Remove**
- The duplicate domain mentions, the duplicate AI summary in the rail, the rail layout (replaced by disclosures), and the always-expanded recovery list (it becomes one expandable trigger in the result).

## Typography decision (from rendered comparisons, `docs/visual-polish/type-directions.png`)

| Direction | Verdict |
|---|---|
| Current: Lora + Inter | Literary and corporate. Rejected. |
| **A: Bricolage Grotesque Bold (display) + Work Sans 400/700 (text)** | **Chosen.** Bricolage has warm ink-trap details and confident proportions: personality without whimsy, and it holds up at verdict size. Work Sans has wide, open forms, comfortable at 18–19 px, and a **tailed `l`**, so `I`, `l` and `1` are distinct by default. Both have full Romanian comma-below glyphs and OFL licences without reserved names (subset legally). |
| B: Young Serif + Work Sans | Friendly but retro; the chunky serif drifts toward "café menu". |
| C: National Park + Instrument Sans | Clean signage, but generic, and Instrument Sans draws `I` = `l`. |

URLs and codes keep the system monospace stack.

## Spectrum rules (truth constraints)

- **Zones** match the policy thresholds exactly:
  - 0–34 *Fără indicii clare*;
  - 35–69 *Suspect*;
  - 70–100 *Indicii puternice*.
- The **marker** is placed at `risk_estimate`.
- **No marker when:**
  - the estimate is null (*Neestimat*): a neutral hatched track and the words "nu putem poziționa mesajul";
  - the AI did not run and the result is in the green zone, so a missing interpretation is never shown as reassurance.
- The number is shown only as a small muted "indicator orientativ X/100, nu e o probabilitate".
- An alert produced by local rules alone still places its marker, because a warning backed by evidence is never hidden.
- Positions come from a tested presentation adapter (`analysis.ui.spectrum`), never computed ad hoc in the browser.

## Motion plan

| Tier | Duration | Used for |
|---|---|---|
| Feedback | 90–120 ms | Press / hover / focus |
| Local | 180–240 ms | Disclosure height, evidence selection, panel open |
| Major | 320 ms | Result reveal |
| Marker glide | 650 ms | Single ease-out, no overshoot |

- The result reveal is one transform + opacity.
- The submit button morphs into a calm busy state (spinner + seconds + Cancel).
- Drag-over state on the input desk.
- A short theme cross-fade.
- **All of it is disabled under reduced motion.** The marker then appears in place, with nothing that conveys meaning lost.
