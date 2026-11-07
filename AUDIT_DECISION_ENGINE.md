# AXA 2.0 — Decision-engine audit

Audit of the complete detection path of AXA 2.0 (as received, commit `917acf1`), done before any change to the detection code.

## 0. Evidence types used in this audit

| Kind | What it is | Where |
|---|---|---|
| **Real, deterministic** | URL extraction, PSL parsing, catalog, rules engine and decision code, run on the actual messages | `evaluation/audit/results/baseline-local-*.json`, probes below |
| **Reconstructed** | No Gemini key or Google network was available in the audit sandbox. For each of the 7 reported messages, a grid of plausible structured readings was run through the *real* v2.0 pipeline. A reading that reproduces the user's exact score is a candidate explanation. This is **not** a live Gemini response. | `evaluation/audit/reconstruct_seven.py`, `results/reconstruction-v2.0.json` |
| **Mocked** | Faithful hand-written Gemini readings for 105 holdout messages plus the 7 reported ones, frozen before any v2.1 code (`mocks.sha256`). Each is scored faithful and under 6 realistic model-error modes. They measure the **policy's** behaviour, not Gemini's accuracy. | `evaluation/audit/mock_interpretations.py`, `policy_eval.py`, `results/policy-v2.0-baseline.json` |

No live Gemini output exists in the repository for v2.0. The only recorded provider calls (`evaluation/forensics/results/provider/`) are from v1.3 and include a 401.

## 1. Actual execution path

```
POST /api/analyze ─ main.py ─ engine.analyze_text(text)
 1 database.load_catalog()            reviewed rows (SQLite/PG) + STATIC_CATALOG hints; outage → static only
 2 url_analysis.extract_url_spans()   regex over raw text (scheme, //, or bare "label.label")
 3 analyze_single_url() ×≤10          PSL split, IDNA, userinfo/IP/port/shortener, detect_typosquatting → risk_points
 4 reputation.add_reputation()        optional Web Risk (explicit http(s), no query/fragment, ≤2 lookups)
 5 engine._rules()                    text_analysis (regex clauses) → action_context frames → evidence_fusion.fuse
                                      → legacy additive score (language + URL points + combos)
 6 semantic_gemini.interpret()        JSON-schema call → pydantic → enum fallback → ground() every quote
 7 claims = domain_claim_assessment() claimed names: rules header/"de la X" + Gemini sender name (if in text)
 8 decision.assess()                  ledger of tiered items → family collapse → max + ≤10 reinforcement → label
 9 presentation.*                     headline, reasons, highlights, profile, stages, recommendations, scenario
10 frontend app.js                    renders label/estimate/meter, ledger, URL tags, stages, simulator
OCR: /api/analyze-image → Gemini transcription → the same analyze_text (from_ocr=True). Consistent by construction.
```

### Authoritative source per evidence type

| Evidence | Authority (v2.0) | Problem found |
|---|---|---|
| Meaning, stance, requested object | Gemini | No field for *where an item goes*; holistic `overall` label leaks into request tiers |
| Requested vs. supplied | Gemini `stance` | No value for "the message gives you this code" |
| Registrable domain | PSL (`psl.py`) | Private-section suffixes (`page.link`, `web.app`) make a tenant look like "the brand on another TLD" |
| Brand ownership | Catalog (reviewed > static) | Third-party subdomains labelled "typosquatting"; reviewed-only domains drive identity verdicts, so a DB outage changes them |
| Claimed identity | Rules header regex + Gemini name | Exact-string brand match: "Orange" → 75, "My Orange" → 30 for the same message |
| Final risk | `decision.assess` | Tiers keyed on labels, not mechanisms (§3) |

## 2. Interaction matrix (Gemini ↔ validation ↔ URL ↔ scoring ↔ frontend)

| From → To | Contract | Defect |
|---|---|---|
| Gemini `overall` → decision request tiers | `overall=="suspicious"` turns **any** requested action (call, click) into tier 40; `likely_scam` into 50 | A holistic hunch becomes "request evidence" (D1) |
| Gemini `sensitivity` → decision | `secret_credential` → 82 regardless of reading, recipient or destination | Own sign-in = credential theft (D2) |
| Gemini `action` enum → decision | No "change settings" or "sign in" values; `change_payment_details` → 70 | Model forced into a severe bucket (D3) |
| Validation → decision | Negation is only checked inside the quote; first occurrence used | Protective text can score 82 (D4, D5) |
| URL `is_typosquatting` → claims → decision | `subdomain_brand_label` counts as typosquatting → `lookalike_outside_catalog` → 60/75 | Branded deep links become "impersonation" (D6) |
| URL extraction → everything downstream | `livrarii.FAN` is a link to `livrarii.fan` | Phantom link in coverage, unestimated rule, simulator (D7) |
| Catalog status → identity tier | Reviewed brand + any other domain → 55; static brand → nothing | DB outage flips 55 → 4 (D8) |
| Rules legacy score → fallback | `score = max(tier score, additive legacy score)` | Two incompatible combination policies; C local 42 (D9) |
| Decision → presentation | Simulator uses the first URL; stages light "trap" for any link | Official domain shown as the trap; benign messages "partially match a scam" (D10) |
| Claims → frontend | `verification_incomplete` rendered as "unknown organisation" for static-list brands | Wrong coverage statement (D10) |

## 3. Reproduction of the seven reported false positives

Deterministic parts are real. The Gemini part is reconstructed (§0): "unique path" means that no other enumerated reading produces that score.

| Case | Reported | Deterministic facts (real) | Reconstructed decisive path | Root cause |
|---|---:|---|---|---|
| A Visa/Google Pay | 40 | No URL; rules 0 | `overall=suspicious` + requested `call_number` (low) → **tier 40** (unique path) | D1 |
| B FAN Courier | 40 | **`livrarii.FAN` → `livrarii.fan` (`.fan` is a real gTLD)**; rules 0 | `suspicious` + `call_number` → 40 (unique) | D1, D7 |
| C Orange promo | 70 | `orange.onelink.me` → 30 pts `subdomain_brand_label`, `is_typosquatting=True`; `www.orange.ro` static official; rules local **42** | Only reachable via `change_payment_details` + `suspicious` → tier 70, plausibly the model forcing "modifica preferințele…" into the only "change" action. **Unconfirmed.** With sender "Orange" and a click, every reading gives 75–80. | D3, D6, D1 |
| D Cargus pickup | 40 | `my.cargus.ro` = static official; rules 0 | `suspicious` + click → 40 (unique). PIN was **not** read as requested (that path gives 82). | D1 |
| E Orange promo 2 | 75 | As C | Sender "Orange" + click → identity `lookalike_outside_catalog` **75, even when Gemini reads it as ordinary marketing** | D6 |
| F Cargus delivery | 40 | As D | `suspicious` + click → 40 (unique) | D1 |
| G Tursib portal | 82 | No URL; claim "Tursib" (unknown brand) | requested sign-in with `secret_credential` → **82 under every `overall`, including "ordinary"** | D2 |

The prior hypotheses were verified as follows:
- **"40-point floor" — confirmed, with a refinement.** It is not a floor for all requests. It is the `suspicious` label converted into tier 40 through a mundane action (`decision.py:190,193`).
- **"82 for sign-in" — confirmed** (`decision.py:168`).
- **`orange.onelink.me` as impersonation — confirmed** (`url_analysis.py:116,319`).
- **Branded third-party link upgraded to an identity conflict — confirmed** (`decision.py:263`).
- **`livrarii.FAN` misparsed — confirmed** (`url_analysis.py:20`).

**What legitimately remains unverified in all seven:** sender identity (SMS text cannot prove it), phone-number ownership (`*2000`, `0725…`), and the owner of `onelink.me` deep links. A message with the same text but a different link still needs analysis.

## 4. Confirmed defects

Ranked by detection impact. Each one follows *cause → affected components → consequence → correction → regression risk*.

**D1. A holistic label is laundered into request evidence.** (`decision.py:183-194, 226-232`)
- **Cause:** a requested low-sensitivity action gets tier 40 when `overall=suspicious`, or 50 when `likely_scam`. The "reading" item needs only *any* grounded item as support, and a click counts.
- **Affects:** Gemini prompt (`suspicious` is undefined), decision, presentation.
- **Consequence:** A, B, D and F score 40. In the mocks, *over-suspicious* readings produce **32/46 benign false alerts**.
- **Correction:** score mechanisms, not labels. A reading counts only when it is backed by grounded deception elements (threat, bait, dependency, fear/urgency/secrecy tactic, consequential request). A `suspicious` reading alone is a sub-alert cue.
- **Regression risk:** unfamiliar scams that Gemini only describes holistically. Mitigated by keeping `likely_scam` with grounded deception support as an alert-level item (tested in mode *reading_only*).

**D2. Sensitivity without direction.** (`decision.py:56,167-172`; prompt `semantic_gemini.py:115-117`)
- **Cause:** `secret_credential`, `device_or_account_control` and `identity_document` map to 82/80/72 whatever the recipient or destination. The schema cannot say "you use it in your own account".
- **Consequence:** G = 82. RH-039, N03 and N17 (own sign-ins) = 82, and RH-025 (*disable* call forwarding) = 80, **with faithful readings**.
- **Correction:** add `handover` (to sender or message destination / recipient keeps control / unclear) and `destination` (an exact substring). Python resolves the destination against URL forensics, and the tier follows asset × handover × destination × reading. A sign-in with no message-controlled location is the recipient's own login.
- **Regression risk:** the model mislabels a real exfiltration as "keeps control". This is mitigated by never discounting approvals, remote access, payment changes or money. An "unclear" handover stays at alert level, and the mode *handover_lenient* tests it.

**D3. Enum gaps force severe buckets.** (`semantic_gemini.py:20-25`, `decision.py:173-175`)
- **Cause:** there is no `sign_in`, no `change_settings`, and no "provided to recipient" stance. `change_payment_details` → 70 with no check that money or a payee is involved.
- **Consequence:** the only reconstruction of C's 70.
- **Correction:** add the three values. `change_payment_details` scores as redirection only with `financial_asset` sensitivity and a scam or suspicious reading.
- **Regression risk:** low.

**D4. Negation checked only inside the quote.** (`semantic_gemini.py:268`)
- **Probe:** "Nu trimite parola nimanui…", with the quote "trimite parola nimanui" → **critical 82**.
- **Correction:** check the grounded span's left context in the original text. Treat a quote that only states a supplied code value ("PIN 3168") as contradicting a "requested" stance.
- **Regression risk:** "Nu uita să trimiți…" (case 24). The existing `POSITIVE_AFTER_NU` idioms are reused.

**D5. Grounding picks the first occurrence.** (`semantic_gemini.py:225`)
- **Probe:** "Nu trimite codul. Trimite codul aici" → the highlight lands on the protective sentence.
- **Correction:** for requested items, prefer an occurrence that is not negated.

**D6. Third-party branded subdomains are treated as lookalikes.** (`url_analysis.py:115-116,316-320`; `decision.py:263-266`; `app.js:142`)
- **Cause:** a brand label anywhere in the subdomains gives `is_typosquatting=True`. The claims step then upgrades a matching sender to `lookalike_outside_catalog` → 60/75. PSL private suffixes add another path: `emag.page.link` is "eMAG on another suffix" → 45 + 75.
- **Consequence:** C and E score 75 under a correct marketing reading, N07 (an eMAG survey on `page.link`) scores 75, and the result depends on the exact sender string.
- **Correction:** report a brand label in the subdomain of an unrelated registrable domain, or an exact brand tenant on a shared platform, as `brand_on_third_party_host`. It is an *unverified association*, a weak cue, never a lookalike. It is stronger (30) when the registrable domain carries service or login terms.
- **Preserve:** `bcr.ro.login-check.example`, `bcr-verificare.top`, homographs, userinfo decoys, and brand tokens in tenant labels (`digi-ro.web.app`).
- **New detection:** an official hostname continued by a hyphen (`olx.ro-livrare.com`), currently only 30 pts.

**D7. Bare-domain extraction across a missing space.** (`url_analysis.py:20-25`)
- **Cause:** `livrarii.FAN` and `exped.INGI12178247` look like hosts.
- **Consequence:** a phantom link in coverage and in the "insufficient information + links" unestimated rule, and the simulator would say "you're asked to open livrarii.fan".
- **Correction:** reject a scheme-less candidate whose last label switches from lower to upper case right after the dot (a sentence boundary), unless it has `www.` or a path.
- **Regression risk:** "Emag.ro" and "WWW.BCR.RO" are still accepted (tests).

**D8. Identity verdicts depend on DB availability, not evidence.** (`url_analysis.py:308,320`; `decision.py:267-271`)
- **Cause:** only *reviewed* domains count, and any other host is an "identity conflict" of 55.
- **Probe:** "BCR: … https://www.facebook.com/bcr" → **55 with the DB, 4 without it**.
- **Correction:** use graded provenance (reviewed > static hint). A mismatch is a sub-alert cue (30 reviewed, 22 static) that needs an independent harmful element to reach alert. The coverage text shows the provenance.

**D9. Two combination policies in fallback.** (`decision.py:349`, `evidence_fusion.py:336-349`)
- **Cause:** the legacy score adds language and URL points, while the decision engine takes the strongest tier.
- **Consequence:** C local-only = 42 (12 payment + 30 subdomain).
- **Correction:** in fallback, feed only the rules' *linguistic* points as the text family, so URL and identity come from the shared ledger once.
- **Regression risk:** fallback recall, measured on the three holdouts (must stay 3/21, 11/24, 5/20 or better).

**D10. Presentation contradicts the decision.** (`presentation.py:187,290`; `app.js:146`)
- The simulator personalises with the first URL, even an official one ("Ți se cere cod printr-o adresă din mesaj" when the code goes by reply).
- The "trap" stage lights for any link, so a benign Cargus notice reads as "Am recunoscut doar o parte din tiparul unei înșelătorii".
- A static-list brand is shown as "Organizație necunoscută în catalog".
- **Correction:** take the scenario host only from decisive non-official link evidence; show stages only for alert or inconclusive results; add explicit statuses for static and third-party hosts.

**D11. The prompt does not define the labels the policy depends on.** (`semantic_gemini.py:128`)
- **Cause:** `suspicious` has no definition, and nothing says that unknown senders, links, delivery PINs, promotions and sign-in prompts are normal.
- **Correction:** define `suspicious` as concrete grounded red flags with no clear harmful step, and explain directionality. Prompt wording alone is **not** relied on: the policy must hold under the *over_suspicious* perturbation.

**Lower-impact findings (documented, not all changed)**
- `PATH_LINK` ignores the fragment, so `https://x.test/a#https://official…` is not flagged as embedding another address (RH-035). Fixed together with D6.
- Web Risk eligibility excludes any URL with a query, so many phishing links are "not checked". This is correctly reported, and left unchanged (privacy choice).
- Gemini free text (`claim_summary`, `uncertainties`) is shown to the user. A prompt injection can affect wording but not score. It is labelled "AI:". Residual risk.
- Local fallback without the NLI model labels most benign messages `inconclusive`. This is honest, kept.
- The rules engine flags "completezi parola… în casetele din cont" as a credential request (RH-039 local → 70). It is a lexical limit of the fallback, documented and not patched with more regex.

## 5. Mocked baseline (v2.0 policy, 105 holdout messages: 59 scam / 46 non-scam)

| Mode | Scam recall | Benign false alerts | Critical credential | Benign critical | Seven (A–G) |
|---|---:|---:|---:|---:|---|
| faithful | 59/59 | **5/46** | 24/24 | 5/46 | 0, 4, **75**, 4, **75**, 4, **82** |
| over_suspicious (live-observed) | 59/59 | **32/46** | 24/24 | 5/46 | 38, 40, 80, 40, 80, 40, 82 |
| direction_errors | 59/59 | 11/46 | 24/24 | 11/46 | 0, 4, 75, 82, 75, 82, 82 |
| under_suspicious | 59/59 | 5/46 | 24/24 | 5/46 | — |
| ungrounded quotes | 59/59 | 5/46 | 14/24 | 1/46 | — |
| reading_only | 56/59 | 5/46 | 1/24 | 5/46 | — |

**Real local fallback (no AI):**
- release: 3/21 recall, 1/18 false alerts (RH-039 → 70);
- fresh v2.0: 5/20 recall, 0/10 false alerts.

These match the README.

Reading: v2.0 recall is excellent *when the model is right or harsh*. But its false-positive control depends entirely on Gemini never saying `suspicious` for a legitimate message, and even a perfect reading leaves 5 structural false alerts. The fix must remove the amplification without touching recall under the faithful, under-suspicious and handover-lenient modes.

## 6. Protected behaviours (invariants to keep, with tests)

1. A secret handed to the sender, a person or a reply is critical, even next to an official domain (`test_secret_request_is_critical_even_with_official_domain`).
2. A protective sentence never cancels a separate live request (cases 12, 23, 28).
3. Web Risk matches and structural lookalikes (embedded official hostname, brand token, confusables, userinfo decoy) cannot be cancelled by any AI reading.
4. Ungrounded quotes never reach critical and are never highlighted.
5. A rules/AI conflict and an unresolved high-impact request give a null estimate, never a reassuring score.
6. No submitted URL is fetched. Web Risk uses a fixed endpoint, no redirects. Provider errors are logged as categories only.
7. The Gemini schema uses only `type/enum/nullable/properties/required/items`, and `maxItems` stays stripped.
8. Fallback recall on the three holdouts does not drop.
9. The API contract is kept (`risk_estimate` nullable, labels, evidence ledger, `checks`). Additions are additive.

## 7. Implementation priorities

| # | Change | Fixes | Effort | Regression risk | Modules that must change together |
|---|---|---|---|---|---|
| 1 | Schema: `handover`, `destination`, `sign_in`, `change_settings`, `provided_to_recipient`; prompt definitions | D2, D3, D11 | M | Provider schema rejection → keep allowed keywords only | semantic_gemini, decision, presentation, tests |
| 2 | Validation: negation context, occurrence choice, supplied-value check, destination resolution | D4, D5 | S | Over-rejecting real requests → contradicted (not dropped) → null estimate | semantic_gemini, decision |
| 3 | Decision: mechanism matrix (asset × handover × destination × reading); cues vs. mechanisms; graded identity cue; explicit convergence rule; fallback uses linguistic points only | D1, D2, D8, D9 | L | Recall → measured in 7 modes + local | decision, engine, presentation |
| 4 | URL: brand on third-party host, PSL private tenants, hyphen-continued official host, fragment embedding, sentence-boundary extraction, brand-name matching for claims | D6, D7, D10 | M | Lookalike recall → URL forensic tests | url_analysis, psl, engine, app.js |
| 5 | Presentation: scenario host, stages, claim statuses | D10 | S | — | presentation, app.js |

**How each is verified:**
- mocked policy evaluation in all 7 modes, before vs. after;
- real local-fallback evaluation on all holdouts;
- paired unit tests (§11 of the brief);
- the full existing suite;
- Gemini request-body schema check (no unsupported keywords);
- headless UI rendering of the seven cases.
