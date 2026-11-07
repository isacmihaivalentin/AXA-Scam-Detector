# AXA assessment policy (v2.1)

Implemented in `decision.py`. Gemini interprets meaning; Python validates the evidence, resolves technical facts and makes the final decision. The audit behind this design is in `AUDIT_DECISION_ENGINE.md`.

## 1. Evidence sources

| Source | What it can establish | What it cannot establish |
|---|---|---|
| Gemini (`semantic_gemini.py`) | What the message claims and asks. For each request: the action, the object, the sensitivity, the **stance** (requested, provided to the recipient, discouraged, reported, self-initiated or hypothetical), the **handover** (to the sender or a destination the message supplies / the recipient keeps control / unclear) and the **destination** text. Also tactics, promises, threats, dependency, mechanism and an overall reading. Every item carries a quote. | Domain ownership, reputation, sender identity, page content, a probability. Whether a destination is official is never taken from the model. |
| Static URL analysis (`url_analysis.py`, `psl.py`) | Registrable domain (PSL, including the private section), lookalikes of catalog domains, an official hostname embedded or continued by a hyphen, a brand name on a third-party host, userinfo, IP hosts, shorteners and embedded addresses (path, query, fragment). | Redirects, content, certificates, WHOIS. No submitted URL is fetched. |
| Catalog (`database.py`) | Whether a host is on a reviewed or static-hint official domain, and which domains a claimed organisation is known to use. | Who owns a domain outside the catalog. |
| Google Web Risk (optional) | A listed threat. | Safety. "No match" never lowers risk. |
| Local rules | A cross-check, and the offline fallback. | They never override a structured reading (see §6). |

## 2. Validation and grounding

- **Quote matching.** Every quote is located in the original text, exactly first, then ignoring case, diacritics, quote style and whitespace.
  - When a quote occurs more than once, a *requested* item uses an occurrence that is not negated.
  - An item whose quote cannot be found is **tentative**: never highlighted, capped at 40.
- **Negated request.** A requested item whose span is negated is **contradicted** (score 0, shown). The negation can open the quote, or sit just before it in the text ("Nu | trimite parola"). Idioms such as "nu uita să…" are not negations.
- **Supplied code.** A requested secret whose quote only *states* a code value ("PIN 3168", "Codul tău este 482 913") is contradicted: the message supplies the code, it does not ask for it.
- **Destination.** The destination text is grounded the same way. Python then resolves it against the parsed links:
  - `link_official`: a reviewed or static catalog domain;
  - `link_deceptive`: a lookalike, an embedded or hyphen-continued official hostname, a userinfo decoy, an embedded address, an IP host, or a Web Risk match;
  - `link_unverified`: any other link;
  - `contact`: the sender, a reply, a phone, e-mail, IBAN or handle;
  - `own`: the recipient keeps control;
  - `unclear`.

  If the model names no destination but the message carries a **non-official** link, the riskiest link is assumed. An official link is never assumed, because that inference may only raise concern.
- **Handover overrides.**
  - A `sign_in` with no message-controlled destination is the recipient's own login, whatever handover the model gave.
  - "Recipient keeps control" is ignored for approvals, remote access and payment-detail changes.
  - "Recipient keeps control" is also ignored for payments to a payee the message itself supplies.

## 3. Evidence classes

- **Technical** (Web Risk, structural lookalikes) and **mechanism** items can raise an alert on their own.
- **Cues** stay below the alert line (35). Examples: an AI hunch, an unverified third-party link, a claim/link mismatch, a sign-in on an unverified page with no scam reading, rules-only pressure wording.

### Requests (stance `requested`, grounded, not contradicted)

**Secret, control or identity documents.** The base tiers are 82 for a secret, 80 for control and 72 for identity documents. The reading is the model's overall reading: `scam` = `likely_scam` with a mechanism.

| Where the item goes | `scam` reading | `suspicious` reading | Other readings |
|---|---|---|---|
| `contact` (sender, reply, person, phone, e-mail) | base | base | base |
| `link_deceptive` | base | base | base |
| `link_unverified`: card data, OTP, password value | base | 70 | 50 |
| `link_unverified`: other items | base | 60 | 50 |
| `link_unverified`: `sign_in` | base | 45 | 25 (cue) |
| `link_official` | 50 | 12 (cue) | 12 (cue) |
| `own` | 0, or 15 for an OTP (cue) | same | same |
| `unclear` | base | 60 (55 for identity documents) | 60 (55 for identity documents) |

**Money.**

| Situation | Tier |
|---|---|
| Grounded pay-before-benefit dependency | 74 |
| Family impersonation | 74 |
| Via the recipient's own channel or a payee they already know | 6 |
| `scam` reading | 60 |
| `suspicious` reading, outward destination | 35 |
| `suspicious` reading, other destinations | 25 |
| Other readings | 10–18 |

`change_payment_details` scores 70 only with `financial_asset` and a `scam` or `suspicious` reading. Otherwise it is a cue of 25.

**Personal data.**

| Situation | Tier |
|---|---|
| `scam` reading, outward destination | 50 |
| `scam` reading, other destinations | 45 |
| `suspicious` reading, outward destination | 35 |
| `suspicious` reading, other destinations | 25 |
| Recipient's own channel | 0 |
| Otherwise | 8 |

**Low-impact actions** (open, call, reply) are context with tier 0. The risk lies in where they lead, which the link and identity checks score.

### Overall reading
The reading counts only when **grounded deception** backs it: a threat, a dependency, a strong tactic (fear, urgency, secrecy, family, bait, channel switch, authority, trust), a consequential request (≥ 25), or a promise (with a request, or under `likely_scam`).

| Reading | With grounded deception | Without it |
|---|---|---|
| `likely_scam` | 50 | 40 if a grounded action points outward. Otherwise 30, and the result is unresolved. |
| `suspicious` | 28 (cue) | 15 (cue) |

### Links and identity

| Finding | Tier |
|---|---|
| Web Risk match | 88 |
| Static URL structure | its points: lookalike 38–45, userinfo decoy 35, IP host 12–18, shortener 18, brand on a third-party host 15, or 30 when the registrable domain carries login, payment or account terms |
| Claimed organisation plus a lookalike of *its* domain | 75 with an action on that link, 60 without |
| Claimed organisation plus its name on a third-party host | cue: 20 with an action, 12 without |
| Claimed organisation plus another domain, organisation has reviewed domains | cue: 30 with an action, 18 without |
| Claimed organisation plus another domain, static-hint domains only | cue: 22 with an action, 12 without |

## 4. Combining

1. The evidence has three **families**:
   - the message text: Gemini requests, the reading and the rules;
   - the link: URL structure and the identity relationship;
   - reputation.

   Within a family only the strongest item counts.
2. The score is the strongest family score.
   - A tentative top item is capped at 40.
   - When the score is ≥ 35, each *other* family with a supported score ≥ 25 adds 5, up to +10. The total is capped at 97.
3. **Convergence.** The score is set to 38 (`suspicious`, low confidence) when all of these hold:
   - the score is below 35;
   - at least two families each hold a supported cue ≥ 25;
   - the message asks for an action toward a destination it controls.

## 5. Labels and the null estimate

| Score | Label |
|---|---|
| ≥ 70 | `critical` |
| 35–69 | `suspicious` |
| < 35 | `low`, `protective` or `marketing`, from Gemini's overall reading |

The estimate is **null** (label `inconclusive`, shown as "Neestimat") when the score is below 35 and any of the following holds:
- a rules/AI conflict (§6);
- a high-impact request is tentative or contradicted;
- `likely_scam` with nothing grounded behind it;
- `insufficient_information` while the message requests something consequential or contains links.

## 6. Rules vs. Gemini

The local rules are a deterministic cross-check:
- If they raise an alert-level request and Gemini's own items do not, and Gemini does not read the message as `likely_scam`, the rules item is **contradicted** and the estimate is withheld. A keyword match never decides over the structured reading.
- If both agree, confidence rises and the score does not.
- Without Gemini (the fallback), only the rules' *linguistic* points enter the message family, so link evidence is never counted twice. Rules-only pressure or verification wording is a cue of 25.

## 7. Guarantees (tested in `test_v21.py` and `test_ai_first.py`)

- A secret handed to the sender is critical even next to an official domain.
- No AI reading cancels a lookalike or a Web Risk match.
- A protective sentence never cancels a separate live request.
- A brand name on a third-party host is never reported as a lookalike.
- A database outage changes provenance labels, not the verdict class, for the tested cases.
- A misread supplied code, a negated quote or an own sign-in can never produce a critical result.

## 8. Confidence

Confidence is separate from risk.

| Confidence | When |
|---|---|
| `high` | The strongest evidence is grounded or technical, at tier ≥ 70 or corroborated by an independent family, with no conflict. |
| `low` | Null estimate, convergence of cues, tentative top evidence, or fallback without a direct request. |
| `medium` | Otherwise. Also when Gemini voiced concern that no mechanism backed. |

The 0–100 number is an indicator-strength scale, **not** a calibrated probability.
