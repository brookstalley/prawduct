# Issue #951 — telemetry: record `found_by` on bugs so review escapes are measurable: Design

`status: draft · stage: design · area: governance/telemetry · added: 2026-10-17 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/951 · requirements:
documentation/issues/951-requirements.md (rev 2)`

Answers the four open questions in the requirements and turns R1–R5 into buildable chunks. Where an
answer needs the owner it is a numbered **Decision** at the end. Build waits on the owner's phase-2
call (requirements, Non-goals).

## Shape in one paragraph

Two facts are captured at two different moments and joined only at read time. `found_by` is captured
**at filing**, on the backlog item. `introduced_in` is captured **at fix time**, by a new
`prawduct-hook attribute-bug` subcommand that proposes a commit by blame, resolves it to a recorded
review, and appends one **`bug-attribution` evidence fact** carrying everything `stats` needs. `stats`
then reads the evidence store only, exactly as it does today. The backlog item keeps `found_by` and
`introduced_in` for humans; the evidence fact is the measurement copy. No provider call, no backlog
cache read, no new source for `stats`.

## Q4 — backlog encoding, and how `stats` sees bug fields

The requirements asked whether `found_by` / `introduced_in` fit the additive block and whether `stats`
can read bug items without a live provider call.

- **Encoding: they fit.** Block fields are additive-only-forever; `Block.fields` is a free key map
  (`plugin/lib/backlog/encode.py`, `Block`, `_parse_block_fields`), and an item without a key decodes
  to the default. Add `found_by` and `introduced_in` as block keys, projected by the item decoder next
  to `affected` / `working_branch` (`encode.py` ~1093) so a write is confirmable from its own
  response. A missing `found_by` projects as `unknown`, never an error (R1).
- **Validation lives on the write path.** `issuefmt.py` already branches on `kind == "bug"` (`:348`,
  `:361`); `found_by` validation goes there: closed vocabulary `review|test|user|session|unknown`,
  rejected on any other kind with a message naming the valid set. Changing a non-`unknown` value
  requires `--force-found-by`.
- **`stats` does not read the backlog.** The cache (`backlog/cache.py`, `cachequery.py`) is
  freshness-gated and can be absent or stale; `stats` today has one source and no network. Making
  `stats` depend on the cache would make the report's answer vary with sync state. So the measurement
  copy is written to the evidence store at fix time (below), and `stats` stays single-source.
- **Consequence to accept:** a bug that is never fixed through the attribution step is invisible to
  B5 beyond a count. That is the right behaviour for an escape metric (an unfixed, unattributed bug is
  `unattributed` by definition) and is reported as such (see "What `stats` reports").

## Q2 — where `introduced_in` is proposed

**A `prawduct-hook attribute-bug <issue-ref>` subcommand, invoked from the `/prawduct:backlog` close
path for a `kind:bug`.** Not the PR flow, not a gate.

Why this site: the fixer has just finished and knows the cause; the fix commit(s) exist; and
`/prawduct:backlog` close is the one place that already touches the item's lifecycle. The PR flow is
rejected because a bug's fix often ships without its own PR review step being the natural moment to ask
(the fixer may be closing a bug fixed three commits ago). A gate is rejected by R3: the proposal is
advisory and "nothing blocks a fix on it".

Behaviour, in order:

1. Read the item's `found_by` (from the cache if fresh, else `--found-by`); the subcommand never
   requires a provider call to proceed.
2. `git blame -w -M -C` over the **removed/changed lines of the fix range** (`<fix-base>..<fix-head>`,
   default: commits referencing the issue number). Candidate set = commits blamed for those lines,
   excluding the fix commits themselves and any commit older than the oldest `review` fact in the store
   (nothing earlier can have been reviewed; it is `unreviewed-origin` without a lookup).
3. **Unambiguous rule (R3).** One candidate, or several where exactly one is the latest *and* the
   others are ancestors of it touching the same hunks → propose it. Otherwise → write
   `introduced_in: unknown`, reason `ambiguous`. A fix that only **adds** lines yields no removed lines
   → `unknown`, reason `add-only` (Acceptance: "no proposal and no false escape").
4. Show the proposal and ask the fixer to confirm / override / mark unknown. Non-interactive runs
   (scheduled sessions) record the proposal as `introduced_in: <sha>` with `method: blame` and
   `confirmed: false`; an interactive confirm sets `method: fixer`. `confirmed` is carried into the
   fact so the report can show how many escapes are unconfirmed.
5. Resolve the commit to a review (Q1 below) and append the fact.

A hook subcommand rather than skill prose, per `core.md` ("a rule you must RECALL is its weakest
form"): the skill invokes the command; the logic is testable code.

## Q1 — which key survives a squash merge

A commit SHA is not a stable identity (squash and rebase rewrite it), and the fact store keys on
**trees** (`base_tree` → `head_tree`, D3). A squash-merged tree equals the reviewed `head_tree` only
when the base did not advance in files the branch touched, so tree-equality alone silently
under-attributes on a busy base.

**Chosen key: per-path blob identity.** The introducing commit `C` changed a set of paths
`P = diff(C^, C)`. A review fact `R` *covers* `C` when, for **every** path in `P`, the blob at that
path in `R.head_tree` equals the blob in `C`. In words: the content the bug lives in is byte-identical
to content a reviewer saw at the end of a reviewed interval. Implementation uses
`evidence.tree_entries` (already used for tree comparison, `evidence.py:1185`) and the persisted
per-tree memo (`tree_key_memo.py`) so each tree costs once per clone.

- **Verbatim and rebase merges:** the whole tree matches; per-path match is a superset of the existing
  tree-equality rule, so nothing regresses.
- **Squash with advanced base:** whole-tree equality fails, per-path equality still holds for files the
  base did not touch. If the base *did* touch one of `P` in the meantime, the squash result is content
  no reviewer saw; that is genuinely `unreviewed-origin` (the review did not cover the merged content),
  not an attribution failure.
- **Several covering reviews:** attribute to the **earliest** covering fact. Rationale: the escape is
  charged to the first review that saw the buggy content and let it pass, and attributing to the latest
  would credit a version that merely re-reviewed it. (Decision 3.)
- **Verdict:** `covered` requires the covering review to have been a *passing* review of that content,
  i.e. no unresolved blocking finding in it on the bug's file path. A review that raised a blocking
  finding on the very hunk the bug later came from is a *caught-then-regressed* case, not an escape;
  it is counted in its own `caught_then_regressed` bucket so it cannot inflate escapes. (Decision 4.)

Must be verified against a real squash-merged branch before build is called done (a fixture built with
`git merge --squash` onto an advanced base — Acceptance).

## The `bug-attribution` fact

One new evidence kind, additive to `KNOWN_KINDS` (an older plugin ignores it by the store's own
unknown-kind rule: "can never satisfy a gate, only coexist"). Body:

```
{ "issue": "owner/repo#N", "found_by": "...", "introduced_in": "<sha>|unknown",
  "method": "blame|fixer|none", "confirmed": bool, "reason": "ambiguous|add-only|...",
  "verdict": "escape|unreviewed-origin|unattributed|caught-then-regressed",
  "review_fact": "<fact id>|null", "review_plugin": "<major.minor>|null" }
```

`verdict` is **derived and stored** here, which looks like it contradicts requirements R2 ("derived,
not stored: storing it is a second, forgeable copy"). It does not: R2's concern is a stored verdict
that outlives its inputs. The fact is an append-only record of *what was true when attributed*, and the
verdict is recomputed by `stats` from `introduced_in` + the store at read time. The stored `verdict` is
an informational convenience for `evidence list`; `stats` ignores it. This avoids a second source of
truth: if the two ever disagree, `stats` wins and a test asserts they agree on fixtures.
`review_plugin` comes from the covering fact's `actor.plugin`, the key `stats._bucket` already uses
(`version_bucket`), so B5 lands in the same per-version buckets as wave-1 cost and yield.

Re-attribution (the fixer corrects a wrong proposal) appends a **new** fact; `stats` takes the latest
per `issue`. Append-only, no edit path.

## What `stats` reports (R5)

A new `bugs` block per version bucket, from the `bug-attribution` facts in the window (by fact `ts`):

| Field | Meaning |
|---|---|
| `fixed` | distinct bugs with an attribution fact |
| `escape` / `unreviewed_origin` / `unattributed` / `caught_then_regressed` | the four verdicts; sum to `fixed` |
| `by_found_by` | the same split per `found_by`; `unknown` is its own row, never merged |
| `attribution_rate` | (`escape` + `unreviewed_origin` + `caught_then_regressed`) ÷ `fixed` |
| `escapes_per_100_reviews` | `escape` ÷ that version's passing `review` facts × 100 |

The bucket is the **review's** version for `escape` / `caught_then_regressed`, and the **fixing
session's** version (the fact's own `actor.plugin`) for the rest, since there is no review to name.
The human render prints `attribution_rate` on the same line as every escape number, and prints
"clone-local" beside it (R4: a review run in another clone reads `unreviewed-origin`, a known
undercount). `REPORT_SCHEMA_VERSION` 1 → 2 and `plugin/docs/governance-telemetry.md` update in the
same chunk, per the existing contract.

**A bug filed but never fixed** appears nowhere in B5. `stats` has no way to know, and inventing a
count would need the cache. The report footer says "bugs without an attribution fact are not counted".

## Q3 — non-framework products

Not a blocker (requirements agree). Design consequence: `attribute-bug` degrades to
`unreviewed-origin` / `unattributed` when the store is empty, and `stats` prints the attribution rate,
which is exactly the signal that a product lacks history. No product-specific code path.

## Build plan

Chunks in dependency order; each ends in a Critic run per the usual rule.

1. **Backlog fields (R1).** `found_by` / `introduced_in` block keys, bug-only validation, decode
   default `unknown`, update-once rule. Tests: each vocabulary value; invalid value; non-bug rejected;
   missing decodes `unknown`; an item written by an older plugin round-trips the new keys untouched.
2. **Resolver (Q1).** Pure function `commit → covering review fact | None` over the store, per-path
   blob identity, earliest-covering, caught-then-regressed. Tests are the falsifying fixtures: verbatim,
   rebase, squash on an advanced base (file untouched → covered), squash where base touched the file →
   `unreviewed-origin`, no review at all, two covering reviews → earliest.
3. **`attribute-bug` subcommand (Q2).** Blame proposal, ambiguity rule, add-only, non-interactive
   `confirmed: false`, fact append. Tests: single candidate, ambiguous candidates → `unknown`,
   add-only → `unknown`, fix commits excluded from candidates.
4. **`stats` block (R5).** Aggregation, schema bump 1→2, `governance-telemetry.md`, human render with
   attribution rate adjacent. Test that the three-to-four verdicts sum to `fixed`, and that
   `unknown` never merges into another `found_by` row.
5. **Skill wiring.** `/prawduct:backlog` close path invokes `attribute-bug` for `kind:bug`; docs
   sweep for every sentence describing the old "no escape record" state (`core.md`: a mechanism change
   is done when every artifact describing it agrees).

Per `core.md`, "a check never seen to return non-zero proves nothing": chunk 2's tests must include a
case the resolver must classify as an escape *and* one it must refuse, and each is red-verified by
breaking the resolver first.

## Producer / consumer ledger

`core.md`: a channel produced and never consumed is a defect. Producers → consumers: `found_by`,
`introduced_in` → `attribute-bug` (reads them) and humans; `bug-attribution` fact → `stats` (sole
consumer) and `evidence list`. Nothing here is gate-read; B5 is measurement only (Non-goals).

## Risks

- **Blame is wrong more often than it looks** for refactors that move code (`-M -C` mitigates, does not
  fix). Mitigation is structural: an ambiguous or add-only case becomes `unattributed`, and
  `confirmed: false` is surfaced. The failure mode is under-counting escapes, never over-counting.
- **Small-n.** Early windows will have few bugs per version; the report shows `fixed` beside every rate
  so a rate on n=3 reads as such. No significance machinery is proposed.
- **Fixer honesty** (the confirmation step relies on the fixer reporting their own prior work). The
  proposal is shown first so the default is the blame result, not the fixer's memory; only an explicit
  override changes it, and `method: fixer` records that it did.

## Decisions for the owner

1. **Approve the evidence-fact copy** (the `bug-attribution` kind) as the way B5 reaches `stats`,
   instead of making `stats` read the backlog cache. Cost: one new fact kind. Alternative: add a cache
   read to `stats` and accept a report whose numbers depend on sync freshness.
2. **Approve invoking `attribute-bug` from `/prawduct:backlog` close**, rather than a PR-flow hook.
3. **Earliest vs latest covering review** when several qualify (recommend earliest).
4. **Add the `caught_then_regressed` bucket**, or fold it into `escape`. Recommend the separate bucket:
   folding makes a review look worse for a defect it flagged.
5. **Phase-2 go/no-go.** Build is held until the owner schedules phase 2 (2026-10-02 decision).

## Not designed here

Contribution and collection of B5 (#949, #950); backfilling existing bugs; any use of escape data to
change gates or severity.
