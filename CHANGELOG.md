# Changelog

## 2.1.3: AXA for Education preview (`/education`)

- New static "în curând" page with a two-track conceptual preview (fraud / misinformation & bots), fictional examples only, no API calls. See `EDUCATION_PAGE.md`.
- Header: fourth link "AXA for Education"; below 70em the links move into the Afișare panel, whose button then reads "Meniu".
- `tools/education_check.js` and `test_education_page.py`.

## 2.1.2: GDPR information and consent

- New "Protecția datelor personale (GDPR)" section at the bottom of the main page, with consent status and withdrawal.
- Consent dialog before the first check on `/` and `/chat` (shared record). Refusing, Escape or "read first" sends nothing and stops the check; the text stays on the device.
- `tools/consent_check.js` (18 checks). Limits and next steps in `GDPR_CONSENT.md`.

## 2.1.1: Interface polish ("Evidence Desk, alive")

Presentation only; detection, thresholds and endpoints are unchanged. Details in `VISUAL_POLISH_CHANGELOG.md`.
- Restored the green → amber → red risk scale in the verdict card, driven by the new additive `analysis.ui.spectrum` (zones = `ALERT`/`CRITICAL`; no marker when unestimated or when an AI-less result would be green).
- Typography: Bricolage Grotesque + Work Sans (OFL, self-hosted subsets) replace Lora + Inter.
- Expressive hero and navy input desk with drag-and-drop, paste and a remove/replace chip for screenshots; the AXA slash as the single motif.
- A tiered motion system (110/210/320/650 ms) with interruptible disclosures and full reduced-motion fallbacks.
- Shorter default results: question-shaped disclosures, one recovery trigger with tiles; result height on a phone roughly halved for benign and inconclusive messages.

## 2.1.0: Mechanism-based decisions (audit-driven)

The audit is in `AUDIT_DECISION_ENGINE.md`; the measurements are in `EVALUATION_v2.1.md`.

### Root causes fixed
- **A holistic "suspicious" label became request evidence.** Any call or click scored 40, and that one policy line produced the four 40-point false positives. Low-impact actions are now context. The overall reading counts only when grounded deception backs it; otherwise it is a cue below the alert line.
- **Sensitivity was scored without direction.** An own-portal sign-in scored 82. Requests now carry `handover` and `destination`. Python resolves the destination against URL forensics, and the tier follows asset × handover × destination × reading. A sign-in with no message-controlled destination is the recipient's own login.
- **Third-party branded hosts were treated as lookalikes.** `orange.onelink.me` and `emag.page.link` became 75-point "impersonation". They are now `brand_on_third_party_host`: an unverified association and a weak cue, raised to 30 when the registrable domain carries login, payment or account terms. Exact brand tenants on PSL private suffixes are handled the same way.
- **Sentence boundaries were extracted as links.** `livrarii.FAN` and `exped.INGI…` are no longer read as links.
- **Negation was checked only inside the quote.** "Nu | trimite parola" could score critical 82. The left context is now checked, a requested item prefers a non-negated occurrence of its quote, and a quote that only states a code value ("PIN 3168") contradicts a "requested" reading.
- **A DB outage flipped verdicts.** The same message scored 55 with the DB and 4 without it. A claim/link mismatch is now a graded cue: 30 for reviewed domains, 22 for static hints.
- **Rules could override Gemini.** The lexical rules no longer decide over a structured reading that found no harmful request. Disagreement now gives a null estimate.
- **The fallback mixed two combination policies.** It now uses one family-based policy: the rules' linguistic points plus the shared link ledger. URL points are no longer counted twice.
- **The presentation contradicted the decision.** The simulator could show an official domain as the trap, and benign messages lit "partial scam pattern" stages. Both are fixed. Sub-alert cues are shown as "Notă", and ordinary requests are no longer labelled "Protector".

### Gemini contract
- **Added:** the actions `sign_in` and `change_settings`, the stance `provided_to_recipient`, and the request fields `handover` (enum, required) and `destination` (nullable).
- **Prompt:** defines `suspicious`, `likely_scam` and directionality, and lists ordinary patterns that are not red flags.
- **Unchanged:** the REST client, model, timeout, retries and concurrency.
- **Schema:** still only `type/enum/nullable/properties/required/items`, and `maxItems` is still stripped (enforced by a test).
- **Older recordings:** responses without `handover` still validate, with the handover set to `unclear`.

### URL and identity
- **New detections:** a hyphen-continued official hostname (`olx.ro-livrare.com` → 45), embedded addresses in the URL fragment, and PSL private-section awareness.
- **Brand matching:** a claimed sender now matches catalog brands by whole words, so "My Orange" and "Orange Romania" both resolve to Orange.
- **New claim statuses:** `brand_on_third_party_host` and `outside_known_domains` (with `known_basis`). The frontend tags them.

### Tests and evaluation
- **`test_v21.py`:** 34 tests, covering the seven reported messages (faithful and the reconstructed live error modes), paired benign/malicious boundaries, metamorphic variants, URL forensics, validation, the provider contract and presentation.
- **`evaluation/audit/`:**
  - the reconstruction of the live scores;
  - frozen mocks and the policy harness with 8 error modes;
  - a scenario-paired development holdout (36 cases);
  - a sealed holdout (24 cases);
  - all results.

### Known remaining weaknesses
- **No live Gemini measurement.** The real model's behaviour on the new fields (`handover`, `provided_to_recipient`) is unverified.
- **Alphanumeric supplied codes.** A code such as `4F7KQ`, misread by the model as requested, can still score critical. The supplied-value check only recognises digits. This was found by the sealed holdout and left unfixed there.
- **The verdict still follows the model when it calls a benign message an outright scam** and grounded bait or an outward action exists (mocked: 9/46 benign false alerts; v2.0: 32/46).
- **A sign-in on an unverified page reaches critical only with a scam reading.** A hedged reading gives `suspicious`.
- **The local fallback remains the v1.3 rule engine.** Its recall is low, and its lexical credential rule still flags own password changes (RH-039 → 70 without AI).
- **Third-party relationships cannot be verified yet.** There is no reviewed brand→provider mapping (for example Orange→`orange.onelink.me`), so such links stay "relationship unverified" rather than "verified". The catalog schema is unchanged.

## 2.0.0: Gemini-first fusion

### Detection architecture
- **Gemini is now the primary semantic interpreter.** When a key is configured, every message is interpreted. There is no escalation gate (`ai_escalation.py` was removed).
- **New structured interpretation** (`semantic_gemini.py`). It covers:
  - the claimed sender;
  - requests (action, object, sensitivity, recipient and stance);
  - promises, threats and pay-first dependency;
  - tactics and protective context;
  - an open mechanism category with `other_suspicious_mechanism`, an overall reading, and Romanian summaries and uncertainties.
- **Every Gemini quote is located in the original text,** first exactly, then ignoring diacritics and whitespace. Ungrounded items stay tentative and are never highlighted. A "request" whose own quote starts with a negation is rejected.
- **New central decision policy** (`decision.py`, documented in `POLICY.md`):
  - tier-based scoring;
  - evidence families that cannot be double-counted;
  - technical findings that Gemini cannot cancel;
  - an official domain never cancels a request for a secret;
  - a null estimate when evidence is insufficient or contradictory.
- **The Romanian rules engine is kept unchanged** as a deterministic cross-check and as the offline fallback (`engine.rules_analysis`). Its lexical validators no longer filter Gemini output.
- **mDeBERTa is now opt-in** (`AXA_LOCAL_MODEL=1`). The default app needs no model weights.

### Infrastructure
- **Gemini is called over REST using the standard library** (`gemini_client.py`), replacing the optional `google-genai` SDK:
  - fixed endpoint, key in a header;
  - no redirects followed;
  - bounded response size, retries, deadline and concurrency;
  - errors reduced to categories.
- **`tldextract` was replaced** by a vendored Public Suffix List and a small matcher (`psl.py`). Results on all three fixture sets match v1.3 exactly.
- **`main.py` is now a thin FastAPI layer;** the pipeline is in `engine.py`. Added `GET /api/status`, an allow-listed asset route, and security headers (CSP, nosniff, frame-deny, no-referrer).
- **OCR** uses the same client, with a transcript review step in the UI.

### Frontend
- **The teammates' design (v3 HTML) is rebuilt as the real UI** (`index.html`, `assets/axa.css`, `assets/app.js`), connected to `/api/analyze` and `/api/analyze-image`. Their JavaScript regex detector was removed.
- **Results are ordered for the reader:** verdict, why, what the message wants, then what to do. Further panels:
  - message autopsy with validated spans, and an "explain fragments" toggle that keeps the original text;
  - link panel with the registrable domain highlighted and explicit relationship and reputation statuses;
  - coverage ("ce am verificat și ce nu");
  - the evidence ledger.
- **"Neestimat" replaces a reassuring zero.** Confidence and coverage are shown separately. The risk profile uses qualitative levels instead of percentage bars.
- **The simulator** is now "Cum ar putea evolua această înșelătorie". It is hypothetical and labelled as such, has no fabricated timings, and appears only when an alert-level mechanism is established.
- **Sharing is privacy-safe:** no message text, links, numbers or codes. History is opt-in and never stores message content.
- **Privacy copy is accurate:** the message is processed by the server, and by Gemini when enabled.
- **Mobile menu, persistent theme and text size,** reduced-motion support, and keyboard-accessible highlights.

### Tests and evaluation
- `test_ai_first.py` adds 24 tests: grounding, policy cases, provider failure categories, prompt-as-data, privacy of the share text, and OCR.
- The existing rules, URL and database tests were adapted to the new structure.
- `evaluation/ai_first_evaluate.py` runs `local`, `live` (with `--record`) and `replay` profiles.
- Added a fresh 30-case holdout, sealed with SHA-256.
