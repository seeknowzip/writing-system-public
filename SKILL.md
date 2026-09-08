---
name: writing-system
description: Rewrites, writes, and reviews natural, distinctive Korean customer-facing text. Given existing text, preserves facts, intent, and the writer's voice while replacing AI-sounding, assembled, translated, or over-simplified wording with words and sentences a person in that field would actually write — marketing copy, landing pages, social and LinkedIn posts, product/UI copy, guides, FAQs, notices, press releases. Given only a brief, drafts from the brief and genre-specific information roles. Use for any request to polish, "make it read naturally / without the AI feel", rewrite, or write text a customer will read. Voice (honorific level, persona, banned terms) stays owned by the consuming project. Not for personal literary writing, pure translation, or spelling-only proofreading.
user-invocable: true
---
# Writing System

Rewriting is the default job: keep the content, facts, intent, and the writer's voice, and
replace what only a model would write with what a person in that field would write. Structure
is a diagnostic tool, not a template — change it only where reading actually fails, or when the
user asks for a redesign. Natural Korean and factual safety are separate requirements; neither
compensates for the other.

## 1. Path decision

| path | condition | contract |
|---|---|---|
| `rewrite` | the user supplies existing text (polish, 워싱, 윤문, "AI 티 없이", "자연스럽게") | [`references/rewrite-contract.md`](references/rewrite-contract.md) |
| `draft` | no source text; write from a brief | §3 |
| `fragment` | buttons, labels, errors, one- or two-sentence UI text | confirm only product context and next action; [`references/micro-corpus.md`](references/micro-corpus.md) when short role-specific phrasing helps |

`high-stakes` (money, contracts, legal, safety, security, outages, policy changes, apologies) is an
overlay on any path: lock the fact ledger and required items first, prevent misunderstanding before
persuading, and mark for human review. Never escalate on length alone. Follow the user's path if they
name one.

Priorities, fixed on every path: preserve facts, figures, conditions, causality, proper nouns, quotes,
and the writer's stance → rewrite words, phrases, sentences → repair paragraph flow → repair a section's
structure only when a P3 gate in `rewrite-contract.md` fires → redesign the whole piece only on
`draft` or explicit request.

## 2. `rewrite`

Follow `rewrite-contract.md` end to end. It defines the minimal input (`source_text`, optional `voice`,
`protected_strings`, `facts`, `audience_familiarity`, `adapter`), the seven steps, the P3 gates, and the
four-part result. Do not request a full brief, `genre`, `channel`, `positioning`, or packets.

Read for step 3–4:

- [`references/failure-taxonomy.md`](references/failure-taxonomy.md) — diagnose only the 2–4 dominant
  failures; `FT12`–`FT17` are the sentence-level ones.
- [`references/surface-tells.md`](references/surface-tells.md) — the removal checklist for spans you
  touch.
- [`references/register-restoration.md`](references/register-restoration.md) — what to put back:
  common terms, collocations, verbs and agents, attribution, concreteness, and prohibited
  meaning or register changes (§8).
- [`references/copy-quality.md`](references/copy-quality.md) §3 — the swap, judgment, scene, speech,
  and memory tests, for diagnosis only.

Rewrite only diagnosed spans. When removal and restoration both apply to a span, restoration wins;
when restoration would need a fact outside the preservation list, remove only and return the gap as a
confirmation item. If an `adapter` is given, its term table beats `surface-tells.md` for that channel.

## 3. `draft`

Secure the input contract in [`references/brief-contract.md`](references/brief-contract.md) — for
complex or verified work, store it as JSON and run:

```bash
python3 scripts/validate_brief.py path/to/brief.json
```

Load evidence: [`references/common-decisions.md`](references/common-decisions.md), then exactly one
genre file — `landing-marketing.md`, `guides-faq.md`, `notices-press.md`, `editorial-social.md`, or
`product-ui.md`. For persuasive genres also read `copy-quality.md` §1–2. References supplied by the user are optional. Read their relevant portions only when authorized and
available. Apply the genre file alone when no reference is supplied; do not require external corpus
access. Learn information roles rather than wording. Never import a reference's facts, figures,
product names, distinctive wording, metaphor, or voice into the brief's fact ledger.

Draft: pick only the facts this document needs; for persuasive genres write the private four-line
direction from `copy-quality.md` first and record a gap instead of filling it with a generic promise;
outline from the genre’s information roles as `reader question → required answer → next action`; write
independently so a concrete situation or judgment carries the text; give title, lead, and CTA distinct
roles; invent no superlatives, results, urgency, social proof, discounts, periods, conditions, quotes, or
emotions.

The draft is not the deliverable. Run §2 on it as if it were source text — the same diagnosis, removal,
and restoration — before checks.

## 4. Diagnosis rules shared by both paths

Diagnose before rewriting; never rewrite during diagnosis. `AI-like`, `generic`, `flat` are symptoms;
map them to `FT12`–`FT17` with an evidence span. When `FT02` looks possible in a landing or marketing
hierarchy, record the four-part role comparison in `failure-taxonomy.md` before repairing. If `FT12`
shows the proposition itself is generic, discard that direction and rewrite the affected title, lead,
or persuasive section — local polish cannot fix it. Read only the relevant failure IDs in
[`references/repair-playbook.md`](references/repair-playbook.md).

When the harness offers a general-purpose subagent, call it once with `brief or preservation list +
text + failure-taxonomy` (plus `copy-quality.md` for persuasive genres) and have it return 2–4 problems
and a preservation list, not rewritten copy. Pass only the current writing task and relevant diagnostic references.

## 5. Checks

With a brief JSON (`draft`) run after the draft and again after the final:

```bash
python3 scripts/validate_copy.py --brief path/to/brief.json --copy path/to/draft.md
python3 scripts/validate_copy.py --brief path/to/brief.json --copy path/to/final.md --before path/to/draft.md
```

On `rewrite`, follow [`references/rewrite-validation.md`](references/rewrite-validation.md) for
source-bound diagnostics and the deterministic check, then `rewrite-contract.md` step 7 for semantic
comparison. Two or more paragraphs, or any `high-stakes` text, require that independent comparison
when a subagent is available. Report unavailable independent review explicitly. A lone reviewer's
condition or confidence concern remains unresolved until checked; agreement is not a substitute for
resolving the span. Touch rate describes scope and is not a quality gate.

A deterministic failure blocks delivery. Naturalness, distinction, and human specificity are judged
with [`references/rewrite-rubric.md`](references/rewrite-rubric.md) on `rewrite` and
[`references/evaluation-rubric.md`](references/evaluation-rubric.md) on `draft`; an unresolved quality
failure also blocks delivery, and an automatic score is never evidence of quality. With any
`compliance_triggers`, read [`references/compliance-gates.md`](references/compliance-gates.md); without
an approved `compliance_source` the copy is not publishable.

## 6. Exit boundary

This skill does not auto-invoke `humanize-korean`. Removal and restoration on every touched span happen
here; `humanize-korean` remains an optional later pass that re-scans its whole taxonomy and must receive
`restored_terms` and `protected_strings` so it does not undo restored terms. It never turns a failed
draft into a verified one. Voice and topic adapters stay in the consuming project. Optional user-authored samples follow
[`references/personalization.md`](references/personalization.md); no samples are required.

## 7. Result

1. the final text
2. touched spans with their reason IDs, `restored_terms[]`, and — on `draft` — 2–4 significant copy
   decisions and the information structure applied
3. facts, conditions, term candidates, structural suggestions, and human-review items still to confirm
4. verification results

If the user asked for copy only, return 1 — but never hide unconfirmed facts or failed checks. On
`high-stakes`, or while `human_review` or unverified items remain, return the `release-status.json`
from [`references/release-contract.md`](references/release-contract.md) separately and validate it:

```bash
python3 scripts/validate_release.py --brief path/to/brief.json --copy path/to/final.md --status path/to/release-status.json
```

Record each real use in `local/usage-log.md` with the route, `restored_terms`, any collocation lookups, and
what the person reverted.

## Maintenance

This public snapshot excludes private source corpora and historical model evaluations. Do not report
its synthetic regression tests as evidence of human preference or general writing superiority.
Reproduce the targeted behavior before changing a rule; preserve unrelated wording and user intent.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
