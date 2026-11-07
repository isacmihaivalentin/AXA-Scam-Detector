# AXA în chat: messaging-style concept (`/chat`)

This is a concept page that shows the AXA checker as an assistant in a chat. The look is inspired by WhatsApp: a teal bar, a patterned wallpaper, bubbles, ticks, quick replies and a round send button. It is a **simulation of an interface**. It is not a WhatsApp integration and it is not an official account. It uses no WhatsApp logos or marks, and the page says so in a visible system note.

**Additive only.** The main interface (`index.html`, `assets/app.js`, `assets/axa.css`), the existing routes, the API and the decision engine are unchanged.

Added:
- `chat.html`, `assets/chat.css`, `assets/chat.js`;
- two routes in `main.py`: `GET /chat` and `GET /chat-assets/{name}` (allow-listed);
- the same two routes in the test fixture server;
- `tools/chat_check.js` and `test_chat_page.py`.

## How it works
1. You paste a message, or attach, drag in or paste a screenshot. It is sent to the **same** endpoints as the main page (`/api/analyze`, `/api/analyze-image`). The typing indicator only appears while a real request is running, and you can cancel the request.
2. AXA replies with:
   - **the verdict bubble**:
     - a **semaphore** of three lamps;
     - the pill (Alertă / Atenție / Rezultat / Fără verdict);
     - the verdict;
     - the "Seamănă cu" qualifier;
     - **the green → amber → red scale**, with the slash marker that glides in;
     - the reason and the partial-analysis note.
   - **the "Ce faci acum" bubble**.

   Your own bubble is re-rendered with the evidence underlines, numbered and tappable. For screenshots, the underlines go on the OCR text bubble instead.
3. Quick replies reach **all the data the main page shows**, one question at a time:

| Chip | Answer |
|---|---|
| De ce? | Numbered explanations. Tapping one highlights the phrase in the message, and tapping a phrase highlights its explanation. |
| Ce e cu linkul? | The real domain, the address anatomy, plain facts, the defanged full address, and a copy button. Nothing is clickable. |
| Ce ai verificat? | What the AI understood, what was checked technically, and what could not be checked. |
| Am apăsat deja… | The 8 situations, with the relevant ones first ("potrivit aici"). Choosing one shows its steps and the "În orice situație" line. The steps are **read from the main page's `#recovery`**, so both pages stay identical. |
| Cum ar continua? | The hypothetical scenario (alerts only), labelled "ipotetic". |
| Detalii tehnice | The indicator ("nu este o probabilitate"), confidence, mechanism, limits and evidence ledger. |
| Avertizează pe cineva / Copiază rezumatul | The share text, which contains no message text, links, numbers or codes. |
| Corectez textul citit | Puts the OCR text back in the box for correction (screenshots only). |
| Verifică alt mesaj | Starts a new check. |

## Semaphore and scale rules (the same truth constraints as the main page)
- **What drives the display:**
  - The lit lamp and the marker come **only** from `analysis.ui.spectrum`.
  - `placed` lights exactly one lamp, the one for the backend zone (0–34 green, 35–69 amber, 70–100 red).
  - `unestimated` and `partial_unplaced` light **no lamp**: the housing is hatched and the track is neutral, with the adapter's explanation.
- **Not colour-only:** the pill, the bold zone name, the screen-reader sentence and the lamp position all carry the meaning.
- There is no "X% chance" wording anywhere.

## Privacy and safety
- Same recipients as the main page. The system note says so: the AXA server, plus Google Gemini when AI is on.
- No message text is stored.
- The page only *reads* the main page's theme and text-size preferences.
- Every string is escaped, and there are no inline styles, so it works under the existing CSP.
- Submitted links are never rendered as links.

## Verification actually run (headless Chromium, mock Gemini readings via the fixture server)
- **`tools/chat_check.js`: 34 runs**, with zero overflow, contrast failures, text under 14 px, unnamed controls or console errors.
  - Sizes: 320, 390, 768 and 1440 px light; 390 and 1440 px dark.
  - States: critical, suspicious, benign, inconclusive, AI not configured and AI timeout, before and after tapping the chips.
- **Lamps observed:**
  - critical: red;
  - suspicious: amber;
  - benign: green;
  - AI timeout (rules-only warning): red;
  - inconclusive and AI-not-configured: none.
- **Behaviour:**
  - On a server error, the typed text goes back into the box, and "Încearcă din nou" works.
  - Enter sends, and focus lands on the verdict.
  - Nothing is written to `localStorage`.
  - The marker glides from 0 to 246 px with motion on.
  - The screenshot flow shows the image bubble, then the OCR text bubble, then the verdict, and the "Corectez textul citit" chip refills the box.
- **Unit tests:** `python -m unittest discover -p 'test_*.py'`: 107 tests OK (1 skipped: FastAPI not installed in this sandbox). This includes `test_chat_page.py`.
- **Main page regression:** `tools/ui_check.js --quick` is still clean.

**Not done:** real phones, Safari, screen readers by ear, or user testing.

## Run
```bash
python -m uvicorn main:app --port 8000       # open http://127.0.0.1:8000/chat
# without a Gemini key (test-only, mock readings):
python -m uvicorn tools.ui_fixture_server:app --port 8765   # open http://127.0.0.1:8765/chat
```

The main page does not link to `/chat` yet, because the existing interface was left untouched on purpose. Adding the link takes one line in `index.html`.
