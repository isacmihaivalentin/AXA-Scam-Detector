# AXA for Education: the "în curând" preview page (`/education`)

## What it is
A landing page for a **future** educational product. It is an honest preview: it shows what AXA for Education *could* teach, using fixed, fictional examples. Nothing on the page analyses anything, calls the API or collects data. **AXA Scam Detector (`/`) and the chat concept (`/chat`) are unchanged in behaviour.**

Open it at `http://127.0.0.1:8000/education` (`python -m uvicorn main:app`). Without a Gemini key, the test fixture server serves it too, at `http://127.0.0.1:8765/education`:
```
python -m uvicorn tools.ui_fixture_server:app --port 8765
```

## Files
| File | Change |
|---|---|
| `education.html` | **New.** The page: same header/footer as AXA, hero, two-track preview, three moves, prepared modules, closing. |
| `assets/education.css` | **New.** All rules scoped under `body.edu` (a test enforces this). It reuses the tokens, header, buttons and footer from `axa.css`. |
| `assets/education.js` | **New.** Afișare/Meniu (same `axa_theme`/`axa_zoom` keys as the main page), tabs, the lesson sequence and replay. No network calls. |
| `main.py` | `GET /education`; `education.css`/`education.js` added to the existing `ASSETS` allow-list. CSP unchanged. |
| `index.html` | Fourth nav link **AXA for Education** after *Confidențialitate*; the same four links in the Meniu panel on narrower screens; footer link. |
| `assets/axa.css` | Inline nav from 70em (it was 56.25em, but four links did not fit there). Below 70em the *Afișare* button reads **Meniu** and its panel also lists the links. `aria-current` style. |
| `assets/app.js` | One line: a menu link closes the panel. |
| `tools/ui_fixture_server.py` | Test-only: the same route and allow-list. |
| `tools/education_check.js`, `test_education_page.py` | **New** checks. `test_chat_page.py`: the allow-list assertion follows the new `ASSETS` line. |

## What the page shows
- **Hero:**
  - "AXA for Education" with the **În curând** status;
  - the headline "Învață să recunoști capcanele digitale.";
  - one paragraph and the central promise;
  - the shared method *Observi afirmația → Recunoști semnalele → Verifici independent*.
- **"Previzualizare conceptuală"**: two real tabs (`role="tablist"`, arrow keys, Home/End).
  - **Fraude online.** A fictional SMS ("COLET-INFO, expeditor fictiv"). Three numbered cues: *Presiune artificială*, *Date sensibile*, *Cale sigură*. Its framing is "ce cere mesajul și pe ce cale".
  - **Dezinformare & boți.** A fictional post ("@exemplu_viral · cont fictiv"). Four cues: *Limbaj emoțional*, *Popularitate ≠ adevăr*, *Sursă neclară*, *Ce verifici?*. A small diagram is labelled "Simulare … nu arată boți și nu dovedește o campanie coordonată". The panel also says "Lecția nu spune că afirmația e falsă. Te învață cum o verifici." Its framing is "de unde vine afirmația și ce o susține".
  - **Motion.** When the preview scrolls into view, the lesson plays **once**: each phrase highlights, then its explanation appears, about 1.1 s per step, under 5 s in total. After that everything stays visible.
  - **Switching.** Changing tabs resets the other track completely and replays. **Reia lecția** replays the current one.
- **Cum vei învăța:** *Explorezi → Investighezi → Decizi informat*. Connected numbered moves on desktop, a compact list on phones.
- **Ce pregătim:**
  - three proposed modules, labelled "încă în lucru, nu sunt disponibile acum";
  - who it is for (individual learning, classroom activities, workshops);
  - an explicit **"Ce nu face încă"**.
- **Closing:** "Siguranța digitală se învață.", **Încearcă AXA Scam Detector** (`/#verifica`) and **Vezi semnele de fraudă** (`/#semne`). There is no signup, waitlist, form or email capture.

## What it intentionally does not do
- No fact-checking or verification of news.
- No bot, deepfake or coordination detection.
- No courses, classes, accounts, progress tracking, analytics or backend storage.
- No calls to `/api/*`, Gemini or third parties (checked in the browser).
- All examples are fictional. There are no real people, brands, parties or news claims, and no truth scores.

## Mobile decisions
- **Header.** It stays one row, 65 px, from 320 px up: logo, *Ajutor*, **Meniu**. Meniu opens the same panel as Afișare, with the four links first, then text size and theme.
- **Hero:**
  - The display type is capped, so the headline takes two or three lines.
  - On phones, the "observi → recunoști → verifici" path moves **below** the preview as its takeaway, so the preview starts on the first screen:
    - 390×844: tabs at 479 px, message at 609 px;
    - 320×640: tabs at 586 px.
- **The preview shows one track at a time**, with tabs.
- **Lower sections are compact:**
  - the moves become a three-row list;
  - the modules become short cards;
  - the audiences become chips.
- **Page length:**

| Viewport | Page height | Screens |
|---|---|---|
| 390 px | 3,228 px | about 3.8 (at 844 px) |
| 320 px | 3,913 px | about 6 (at 640 px) |
| 768 px | 2,654 px | |
| 1440 px | 2,217 px | |

## Accessibility and motion
- **Structure:** semantic header, nav, main, sections and footer; a skip link; one h1; no heading skips.
- **Contrast:** AA in both themes (measured).
- **Targets:** 44 px+ (radio buttons sit inside 44 px labels).
- **Tabs:** the tablist, the panels' `aria-labelledby`, and focusable panels.
- **Menu:** `aria-expanded`; Escape closes it and returns focus; `aria-current="page"` marks the current page.
- **No JavaScript:** the tabs are hidden and both lessons are shown in full, with all 7 explanations.
- **Reduced motion:** every highlight and explanation is shown at once, with no sequence and no transitions.
- **Off screen:** if the preview leaves the viewport mid-lesson, the lesson stops and shows everything.
- **No loops, autoplay, flashing or parallax.** Motion uses opacity and transform plus a background fill, within the existing 110/210/320 ms tiers.

## Verification actually run (headless Chromium, fixture server)
- **`tools/education_check.js`: 30 audited renders, 33/33 behaviour checks pass.**
  - Renders: 1440, 1280, 1024, 768, 430, 390, 375, 360 and 320 px light; 1440, 768, 390 and 320 px dark; both tracks; 200% text and the largest A+ setting at 390 px.
  - Results: zero horizontal overflow, contrast failures, text under 14 px, unnamed controls, heading skips, console errors or API calls.
  - Behaviour covered: tabs (click and keyboard), the reset on switching, the once-only sequence and replay, no-JS rendering, the menu and Escape, theme, every navigation smoke test from the brief, and the main header at 320–1280 px.
- **Regression:**
  - `tools/ui_check.js`: 65 runs clean.
  - `tools/chat_check.js`: 34 runs clean.
  - `tools/consent_check.js`: 18/18.
  - `python -m unittest discover -p 'test_*.py'`: **112 tests OK** (1 skipped: FastAPI is not installed in this sandbox, so `main.py` itself was not run; the fixture server serves the same files).
- **Not done:** real devices, Safari/Firefox, screen readers by ear, user testing.
