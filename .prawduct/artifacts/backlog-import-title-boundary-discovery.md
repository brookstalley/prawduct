---
artifact: discovery
scope: backlog-import-title-boundary
source: incoming-bugs/backlog-import-aborts-whole-run-on-one-oversized-title.md (discodon, 2026-08-06)
last_validated: 2026-08-06
---

# Backlog import: the title boundary, and the two guardrails that should have contained it

## 1. The problem, observed

A 396-item markdown→Issues migration in **discodon** created 27 issues in 55 seconds and then
died at item 28 with a GitHub **422**, and **no amount of resuming advances it** — the failure is
deterministic and position-ordered. The run is permanently pinned at 7%.

Two layers, and the loud one is not the real defect:

- **Layer 1 (the blocker).** GitHub caps issue titles at 256 characters. The importer passes
  titles through unbounded and treats a per-item 422 as fatal for the *entire* migration.
- **Layer 2 (the cause).** `legacy._parse_title_line` has **no title boundary at all**. It strips
  `~~` and `**` and returns the whole bullet line. Where a product authors title and body prose on
  one line, the "title" is title + provenance + areas + the entire body paragraph.

## 2. What the numbers actually say — measured, not inferred

> **Re-derive, do not cite.** `tools/measure-backlog-titles.py <backlog.md> …` prints every figure
> in this section. The tables below are a 2026-08-06 reading and will drift as either corpus
> grows; the discodon corpus is not in this repo, so nothing here re-checks itself. Where a figure
> matters to a decision, run the command.

The report could not characterise 342 of 396 lines and explicitly warned against trusting its
regex. Re-derived here against both real corpora:

| | pending | titles >256 | max title | median |
|---|---|---|---|---|
| discodon | 401 | **55** | **2319** | 148 |
| prawduct (this repo) | 197 | **6** | 336 | 155 |

**This repo has the same defect latent** — 6 of its own items would be rejected by GitHub today.

**But this repo's long titles are genuine.** `MET-4P9C`'s 336 characters are one authored
statement, not prose bleeding in. discodon's are not. There is therefore **no single
authored-title boundary across products**, and any rule that truncates on length alone would
damage the working shape to fix the broken one.

## 3. The boundary rule, derived from the data

discodon's line shape is:

```
- **[CI-L0SB]** (orig #980, pr-reviewer 2026-05-10) Move activity token-generation into
  `activity/package.json` build script. [areas: ci, frontend, deploy] The v2.1.0 ranch deploy…
```

The title ends at the **`[areas: …]` marker**. The rule is: strip the leading `[ID]`, strip a
leading `(orig …)` / `(from …)` provenance parenthetical, and cut at an inline `[areas:|tags: …]`
marker if one is present. Otherwise leave the line alone.

Measured effect:

| | >256 before | >256 after | max before | max after |
|---|---|---|---|---|
| discodon | 55 | **1** | 2319 | 260 |
| prawduct | 6 | 6 | 336 | 325 |

`CI-L0SB` — the exact item that killed the run — goes **1055 → 73 characters**:
`Move activity token-generation into `activity/package.json` build script.` That matches the
authored title the reporter measured at 72.

**The rule repairs the shape that carries the marker and does not touch the shape that does
not**, which is the property that makes it safe to ship to a fleet whose authoring conventions
differ. `[areas:` appears on 100 of discodon's 401 items and **0** of prawduct's.

## 4. The correctness question that gates the whole fix — resolved

Changing a title changes the *record*, so the first question is whether it changes the
**idempotency key** and turns a resumed import into a duplicating one.

`ImportRecord.key_label()` (`migrate.py:559-567`) answers it:

- An item **with a PFX** keys on `ids.alias_label(self.pfx)` — the `id:PFX` label.
  **Title-independent.** Fixing the title cannot change the key.
- An item **without a PFX** falls back to `import-key:<sha256(title + body)>` —
  **title-dependent.** For those, fixing the parser would silently mint a new key and duplicate.

**Measured: 0 of 401 discodon items and 0 of 197 prawduct items lack a PFX.** The duplicate
hazard is real in the schema and **absent from the live data**, so the fix is safe to ship — but
it must be guarded by a test rather than left to luck, because a PFX-less item is legal.

`_find_by_key` searches `state="all"` (`migrate.py:1048-1054`), so the **27 already-created,
now-closed** issues *are* matched. That answers the report's worry about a silent 27-item
coverage gap: they will be skipped, not duplicated — which is exactly what makes the owner's
recorded ruling (**retitle-in-place on skip**) the repair path for their polluted titles, without
needing the delete permission the operator structurally cannot hold on a user-owned repo.

## 4b. Owner directive 2026-08-06 — the norm binds on every path

`[NORM BIRTH: issue titles must conform to the standard's §1 budget and shape on EVERY write path
— migrated, created, or modified. The agent rewrites where a source title does not conform; a
non-conforming title is not imported. | owner: "we need to enforce on migration. fine if the agent
has to rewrite. They must be EXCELLENT issue titles, always, whether migrated or created new or
modified" | owner ruled 2026-08-06]`

**Lifecycle capture** (`docs/norms.md` requires statement + why + scope + status + enforcement +
retroactivity; the quote above is only the statement):

- **Why:** an issue title is the handle every later reader triages by. A backlog whose titles are
  run-on prose cannot be scanned, and the 401-item corpus that motivated this proves the failure is
  silent — only the items breaching GitHub's 256 cap announced themselves; the rest simply read
  badly forever.
- **Scope:** every write path of the backlog adapter — `file`, `update`, `import`. Not the markdown
  backend's hand-authored bullets, which are the *source* the scrub rewrites.
- **Status:** **in-transition.** Enforcement is designed (§4b) and **not built**; three paths are
  non-conforming today and this branch changes none of them.
- **Retroactivity: existing corpora are NOT retro-conformed by this branch, and that is a decision,
  not an oversight.** Re-derive the counts with the command in §2 — a large majority of both
  corpora exceed the 72-char budget. Retro-conformance is the scrub pre-pass's job at migration
  time, and §4c's altitude constraint says it must not run before the shared-root-cause check
  exists, or it entrenches an over-split backlog.
- **Enforcement home:** `issuefmt._lint_title` already implements all four checks; what is missing
  is that `file`/`update` treat them as advisory and `import` never calls them. **Tracked as #614.**
- **Collision with standard §4 — RULED 2026-08-06 (owner), not left open.** §4 ratified these lints
  as *"WARN only, never blocks"*, which this directive contradicts. Owner ruled the directive
  supersedes: **§4 is amended so the four §1 TITLE checks block on all three write paths, while
  every body lint stays WARN-only.** The narrowing is deliberate — a title is the handle every
  reader triages by and is cheap to rewrite; a body budget blocking an edit to an unrelated field
  is the confirmation-fatigue shape `security-model.md`'s approval norm already rejects. The
  amendment is recorded in §4 itself, where a reader meets the rule.
- **Tracking ref for `Status: in-transition`:** **#614** (enforcement on all three paths + the
  co-shipping shared-root-cause check). #612 (import guardrails) and #613 (retitle-in-place on
  skip) carry the other deferred scope items.

**This strengthens the existing standard rather than inventing one.**
`documentation/backlog-service-issue-standard.md` §1 already specifies the budget (≤72, aim 50–70),
the shape (`area: specific summary` — a noun phrase saying *what failed + where*, or *what to do*),
atomicity (one problem; a `—`/`;` join usually means two), and the ❌ set (vague, non-specific,
em-dash chains). `issuefmt._lint_title` already implements all four checks
(`title-too-long` / `-too-short` / `-placeholder` / `-non-atomic`).

**What changes is enforcement, on three paths:**

| Path | Today | Required |
|---|---|---|
| `file` (create) | lint runs, **advisory** — a `body-too-long` warning shipped an issue on 2026-08-06 | conform or refuse |
| `update` (modify) | not verified to run the title lint at all | conform or refuse |
| `import` (migrate) | **no lint at all** — raw bullets went to GitHub, which is the whole defect | conform or refuse |

**The migration design that satisfies both this directive and "no model in the data plane":**
§5's LLM scrub pre-pass stays where it is — *before* the deterministic import. The importer does
not call a model; it **validates** and refuses. So a non-conforming corpus fails **pre-flight, in
the first second, with the full list** — which is also the report's fix #1 — and the agent then
runs the scrub to rewrite the named items, preserving originals verbatim in `original_title:` per
§5.2. The owner still approves in aggregate. The importer never writes a title the standard
rejects, and never needs a model to guarantee that.

Note this makes the report's Layer-1 guardrails *cheaper*, not redundant: pre-flight refusal means
a 422 for over-length becomes unreachable, but per-item isolation still matters for every other
422 cause.

## 4c. Owner directive 2026-08-06 — atomicity has two failure directions, not one

`[DECISION: atomicity is a property of the FIX, not of the sentence — the test is "would a single
change close all of these?". Over-splitting (a family of near-identical titles one fix would
close) is a first-class failure alongside under-splitting, and the standard must name both |
owner: "we don't get issues like 'personas crash on emoji' and 'on unicode' and 'on UTF-16' when
the correct thing is to uplevel to 'personas crash on character encoding'" | owner ruled
2026-08-06]`

Standard §1 amended. Two consequences that are **not** yet built:

1. **No per-title lint can catch over-splitting**, because it is a fact *between* issues. The
   detection surface is the dedup/merge sweep, which today groups by "title-keyword + body
   overlap" — a *duplicate* test, not a *shared-root-cause* test. Two issues can share a root cause
   with almost no keyword overlap (`crash on emoji` / `crash on UTF-16`). The sweep needs the
   altitude question added, and it is the only place it can live.
2. **The migration scrub must work across the corpus, not item-by-item.** A pre-pass that rewrites
   400 titles one at a time cannot see that 3 of them are one defect — and rewriting each to a
   *tighter* ≤72 title actively entrenches the over-split, because a sharper symptom title reads
   more like a well-formed issue. Enforcing §1's budget without §1's altitude test would make this
   corpus worse in exactly the way the owner is guarding against.

**Sequencing consequence:** the enforcement work in §4b must not ship the length/shape half alone.
Shipping "conform to ≤72" first, and the altitude test later, uses the intervening window to
produce a large, tidy, over-split backlog that then has to be merged back by hand.

## 5. Scope

**In scope**, in dependency order:

1. **The boundary rule** in `legacy.py` — the actual repair. Must not change `BacklogItem.title`'s
   meaning for existing consumers without checking them; prefer a derived value the import path
   reads, so the briefing's display string is a separate decision.
2. **A length cap with overflow to the body** — 1 discodon item and 6 prawduct items still exceed
   256 after the boundary fix. Truncation must move the remainder into the issue body, never
   discard it.
3. **Pre-flight validation** — report every over-length item *before* the first write, so a bad
   corpus fails in the first second with a list rather than 7% in with issues already created.
4. **Per-item failure isolation** — a 422 records that item and continues. One malformed row must
   never end a 396-row migration.
5. **Retitle-in-place on skip** (owner ruling) — repairs issues already written with polluted
   titles, including closed ones.

**Delivery status of the five, recorded so nothing is silently dropped (Principle 2).** This
branch delivers **1 and 2 only**. Items **3, 4 and 5 are DEFERRED, not descoped** — they remain
required, and the reporter's second failure mode (one bad row ending a 396-row run) survives until
item 4 lands. Their tracked home is `.prawduct/.handoff-notes.md` plus this section; they must be
filed to the backlog before this branch merges, because a handoff note is consumed at `/clear` and
is not a tracker. The same applies to §4b's three-path enforcement table and §4c's two named
consequences.

**Out of scope, recorded not forgotten:**

- The rollback/run-manifest design from the report's companion defect (`import --rollback`,
  digest-key release, permission pre-check). Real, and a separate decision — it changes the
  import's data model.
- The three smaller observations in the report (progress counter disagreeing with item count,
  unexplained `1 collision(s)`, the stale advisory count frozen at first-seen).

## 5b. Why `BacklogItem.title` changed rather than a derived value (§5.1 departure)

§5.1 preferred a derived value the import path reads, so the briefing's display string stayed a
separate decision. The implementation changed the shared parser value instead. **Recorded as a
departure with its reason rather than left as drift:** the run-on title is wrong for *every*
consumer, not only the importer — the briefing displaying 1055 characters of body prose as an item
title is the same defect wearing a different hat, and a derived value would have fixed the import
while leaving every reader looking at the polluted string.

Consumers swept before the change: `briefing.py:891`, `norm_probes.py:252,519`,
`release_readiness.py:169`, `backlog_probes.py`, `migrate.py`. All consume the title as display or
as a search haystack; none parses it or keys on it. The one place identity is keyed —
`ImportRecord.key_label` — uses the `id:PFX` alias for PFX items and is title-independent (§4).

## 6. Open assumptions

- `[areas:` / `[tags:` is the only inline end-of-title marker in the fleet. Verified against two
  corpora; **not** verified against the other ~24 sibling repos. A third corpus should be sampled
  before this is called general.
- The single remaining discodon title at 260 characters is assumed to be a genuinely long
  authored title rather than a second unhandled shape. Not individually inspected.
