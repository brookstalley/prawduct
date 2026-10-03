# Governance Telemetry

Visible Costs (Principle 9) applied to the framework itself: every independent
review appends one event to an append-only ledger, and `prawduct-hook
review-stats` aggregates that history into the numbers proportionality
decisions need. Telemetry is **pulled, not pushed** — no hook nags about it;
`/prawduct:janitor` reads it during maintenance.

## The event ledger

`.prawduct/.governance-ledger.jsonl` (gitignored) — one JSON event per line,
written ONLY by `lib.ledger` — `prawduct-hook ledger-append` for review events,
the Stop hook and `critic-consolidate` in-process for `learning.*` (agents never
hand-author JSONL; the one append validates the record and computes the envelope).

Every event shares the **envelope**; the kind-specific payload nests beneath a
kind-named key (`review` for `review.*`):

```json
{"schema_version": 1,
 "event": "review.critic",
 "ts": "2026-06-10T16:20:00Z",
 "duration_seconds": 720,
 "project": "my-product",
 "scope": "my-feature",
 "chunk": "02",
 "actor": {"role": "critic", "model": "claude-opus-4-8[1m]"},
 "git": {"head": "<sha>", "base": "origin/develop"},
 "review": { ...the full .critic-findings.json record... }}
```

- `schema_version` is **per line** — a long-lived ledger can mix versions.
- `scope` is the build-plan feature key (derived by `critic-begin` from the branch name, or passed explicitly as an override;
  the `active_build_plan` pointer is only the fallback).
- `duration_seconds` and `actor.model` are nullable — recorded, never invented.
  `duration_seconds` is the reviewing model's **own estimate**, never a clock. The clock is the
  optional `dispatched_at` key, written only when the review's dispatch was marked before the
  reviewer was spawned; its interval ends at `ts` (at `review_written_at` on a `review.pr` that
  carries it). An absent key means *not measured*, never zero. `lib/review_dispatch.py` owns the
  interval, and every reader goes through it.
- `review.critic` (the Critic, after writing its findings file) and
  `review.pr` (the `/prawduct:pr` skill after the PR review, via
  `--findings <evidence-path>` — required for `review.pr`, rejected for
  `review.critic`, whose only trusted source is the canonical
  `.critic-findings.json`).
- `learning.written`, `learning.fired` and `learning.compacted` — the learning loop, below.
- **Consumers skip unknown event kinds and unknown fields** — that contract is
  what lets producers grow without migrating the ledger.

## The learning-loop events

Measure the loop or do not claim it. Three kinds record what the rules corpus
actually does, so an audit reads a number instead of sampling transcripts:

| kind | `actor.role` | emitted by | means |
|---|---|---|---|
| `learning.written` | `builder` | the Stop hook, after the learnings budget check | a rule unit that is new since this session's base revision, **committed work included** |
| `learning.fired` | `critic` | `critic-consolidate`, after the `review.critic` anchor | a consolidated finding quoted a rule's opening words |
| `learning.compacted` | `builder` | `learnings-compact --apply` | a rule was rewritten or merged: `from_hash` is the unit it was, `unit_hash` the unit it became. `review-stats` reads citations and authorship through it, and the Stop hook does not count the new unit as written |

All three nest under a `learning` key, under the same envelope:

```json
{"schema_version": 1,
 "event": "learning.fired",
 "ts": "2026-09-02T18:40:00Z",
 "duration_seconds": null,
 "project": "my-product",
 "scope": "my-feature",
 "chunk": null,
 "actor": {"role": "critic", "model": null},
 "git": {"head": "<sha>", "base": "origin/develop"},
 "learning": {"file": ".claude/rules/learnings/core.md",
              "unit_hash": "45f9c4da0a95f423",
              "session": "2026-09-02T17:02:11Z",
              "review_id": "rev-9f21c0"}}
```

- **A rule unit** is a `##`/`###` heading below a rules file's title, or a
  top-level `- ` bullet (`lib/learnings_files.rule_units` — the one
  definition both emitters use). `unit_hash` is sha256 of the unit lowercased,
  whitespace-collapsed and stripped of trailing punctuation, first 16 hex.
  **Rewording a rule mints a new hash on purpose**: a rule whose text changed is
  a different rule to a reader, so "never fired" must not be answered from text
  the corpus no longer carries.
- **A citation** is a unit's opening eight words (the whole unit when shorter),
  matched against a finding's `summary` + `recommendation` after the same
  normalization. A unit of fewer than three words — a section banner such as
  `## Unsorted` — is **uncitable**: it can be written, it just cannot fire, or a
  single stray word would report a rule as exercised by a review that never read
  it.
- **The span is the session's work, not its uncommitted work.** The Stop hook
  reaches `learning.written` off `gates.session_work_span`, which diffs the
  session's base tree against the working tree — so a rule written and
  committed in one turn is still counted at that turn's Stop. Without the
  marker there is no base to diff, and then nothing is recorded and the Stop
  hook says so on stderr; that one missing state is also why the budget check
  reports itself unchecked.
- **`session`** is the `.session-start` marker's mtime as UTC ISO
  (`evidence._session_epoch`) — nullable, never invented.
- **`review_id`** is the review fact's id on `learning.fired`, and `null` on
  `learning.written`.
- **Idempotence key: `(kind, session, file, unit_hash, review_id)`.** The Stop
  hook runs every turn, so a rule written once is re-observed as new on every
  turn until the session ends; re-consolidating a review re-reads its findings.
  The key is what keeps each at one line. It is also why `session` is in the
  payload rather than derived at read time: the same rule written in two
  sessions must count twice.
- **Machine-emitted only.** `ledger-append --event learning.*` exits 1 with a
  reason. The fields are derived — a unit hash from the corpus, a session from
  disk — so a hand-typed event measures nothing.
- **Best-effort at both call sites.** A failure to record is one `NOTE:` on
  stderr naming the consequence; the Stop gate's exit code and the
  consolidation's exit code are unaffected. A measurement never changes a
  verdict.

### The questions these answer

The format is lock-in, so the queries came before the fields:

1. **How many rules were written** per session / scope / repo / window —
   count `learning.written` by `learning.session`, `scope`, `project`, `ts`.
   The count is of rules the session wrote, committed or not. It is short for a session
   that ran with no base-tree marker, and it is HIGH under rewording: an edited rule mints
   a new unit hash and is counted as written, so merge-and-reword curation inflates it —
   read Q1 as writes-or-rewrites, and use Q3 for the corpus.
2. **Which rules fire, how often, and in which review** — count
   `learning.fired` by `learning.unit_hash`, read `learning.review_id`.
3. **Which rules never fire** — join the corpus's units (hash each with
   `rule_units` + `unit_hash`) against the `learning.fired` hashes. This is the
   question the corpus cannot answer about itself, and the reason `unit_hash`
   is a content hash rather than a heading string or a line number. **Read it
   as a floor, not a census:** a rule fires only when a reviewer QUOTES it, so
   a rule that shaped a finding without being quoted reads here as never fired.
   The instruction to quote lives with the reviewers (`agents/critic-reviewer.md`,
   and `cross-checks.md` for the cross-check), but nothing enforces it — so this
   answer under-counts by however often reviewers paraphrase.
4. **All of the above across a fleet** — key by the envelope's `project`.

`prawduct-hook review-stats` reads them: its `learning` block (below) reports
all four counts, and its human rendering closes with the number question 3
asks for.

## Control firings and sessions (evidence store)

Two facts outside the ledger feed the friction side of the picture. Both live in
the clone-shared evidence store, because the ledger is per worktree and
worktrees get deleted.

- **A Stop-hook block** appends one `guard-refusal` fact per gate that blocked,
  with `guard` = `stop-gate:<gate id>`. It uses the same sink as every other
  control firing, so `prawduct-hook evidence list --kind guard-refusal` lists
  them beside guard refusals. A deferred gate did not block and records nothing.
- **A session boundary** (startup or `/clear`) appends one `session-start` fact,
  the denominator for per-session rates.

Their writers are `lib/evidence.py`'s `append_stop_block` and
`append_session_start`. Neither is read by any gate. A failed append prints a `NOTE:` and changes
nothing else.

## `prawduct-hook review-stats [--json] [--since <stamp>] [--until <stamp>]`

Aggregates `review.*` events and tallies `learning.*` ones; skips corrupt
lines, kinds it aggregates neither of, and unusable payloads **with counts**
(never silently). A `learning.*` event carrying no `unit_hash` is an
`invalid_payload`, not a skip nobody names — it can answer none of the four
questions. A `learning.` kind this report has no column for counts
under `unknown_kinds`. Missing ledger → "no
review history", exit 0. Exit 1 only on bad arguments — **including a window bound this reader
cannot interpret**, which is refused rather than filtered on as a bare string: a bound silently
meaning something other than what was typed moves events between the halves of a before/after
comparison, and the difference is then attributed to whatever change was under test.

Per grouping — overall, `actor.role` × `actor.model` × review mode,
per-`scope`, and per review `stage` — it reports: review count; duration led by the **clocked**
population (reviews whose dispatch was marked) and then the **unclocked** reviews' self-reported
estimate, labelled as one — two disjoint populations, never pooled; findings by severity, **actionable rate** (share of reviews with ≥1
blocking/warning), and findings-per-review. Plus a findings-by-file rollup
from per-finding `files` attribution (top paths by actionable findings,
capped at 10 with the total attributed count alongside).

### The `--json` contract

The machine shape is the seam cross-project aggregation builds on.
Top-level keys, in order:

```
schema_version   report schema (bumped on any key change — pinned by
                 tests/test_review_stats.py)
project          the repo's identity: product_identity.name, else the push
                 remote's repository name, else the main checkout's directory
generated_at     ISO-8601 UTC
window           {since, until} — the bounds in force, stated even when both
                 are null so a slice is never mistaken for the whole corpus
events_total     reportable review.* events
skipped          {corrupt_lines, unknown_kinds, invalid_payloads}
overall          one stat block (below)
by_role_model_mode  [{role, model, mode, ...stat block}]
by_scope         [{scope, ...stat block}]
by_stage         [{stage, ...stat block}] — `inner` / `boundary` / null
top_files        [{path, actionable_findings, findings}]
files_attributed_total  count behind the top_files cap
learning         {written, fired, units_written, units_fired, units_uncited}
```

`learning` counts the learning-loop events: `written`/`fired` are events,
`units_*` are distinct `unit_hash` values. `units_uncited` is the SET of written
units minus the set of fired ones (never a subtraction of the two counts — the sets
are not nested, and on a repo whose corpus predates the telemetry they are disjoint): the
rules no review has ever cited among those WRITTEN since the telemetry shipped — a floor under
question 3 (whose full answer is the corpus's units minus the fired set), reported rather than
by hand. They are **not** in `events_total`, which counts reviews.

Stat block: `reviews`, `duration_total_seconds`, `duration_median_seconds`
(the reviewing models' **estimates** over every review that carried one, clocked reviews
included; null when no event carried one — kept because a published key is never dropped or
repurposed, and not what the human headline shows), `duration_measured` /
`duration_self_reported` (each `{reviews, total_seconds, median_seconds}` —
a clock read either side of dispatch, and the estimate of the reviews that have NO clock:
two disjoint populations, because a median over the mixture measures
neither; schema 6 added them — the human line leads with the first and labels the second an
estimate), `findings`
(`{blocking, warning, note, other}`), `remedies` (below), `findings_per_review`,
`actionable_rate` (0–1), `observations` (items an inner-stage pass demoted —
never counted in `findings`), `reviews_recording_observations`
(reviews whose event carried the array; events written before it existed are
excluded, so `observations: 0` over `0` recording reviews means *not measured*,
not *nothing demoted*). Schema 4 added the last two keys.

`remedies` reports, per severity (`blocking`/`warning`/`note`/`other`), whether a finding ships a
fix plan: `{findings, with_remedy, blank_remedy, no_remedy_field, rate, median_words}`. The severity
label says what a finding is worth and the remedy beside it is what makes it read as work, so the two
can disagree — a NOTE carrying a finished fix plan is indistinguishable from a WARNING at the moment
the builder decides what to do. Three outcomes are counted, not two: **absent** (no `recommendation`
key at all) is a different claim from **blank**, because the PR reviewer's findings carry
`{goal, severity, file, line, summary}` and have no remedy field in their schema. `rate` is over
findings whose schema HAS the field, and is `null` when none does — reporting 0% there would be a
claim about a population's behaviour that its schema cannot support. Schema 7 added the key.

### Windowing (`--since` / `--until`)

Both bounds are **inclusive**, and a bound shorter than a full timestamp names a **period** rather
than an instant: `2026` is a year, `2026-09` the whole of September, `2026-09-01` that whole day.
Compared as bare strings every one of those excludes its own period, which silently shortens
whichever window the bound closes — and the window a before/after comparison closes is the one the
conclusion is read from. A full timestamp is parsed, so a zone offset means what it says.

**The window scopes the read, not the result.** Reviews, skips and the `learning` tallies all
describe the windowed population, so two adjacent windows partition the corpus and a `--json`
consumer summing them double-counts nothing. A human report carries a `WINDOW:` banner when either
bound is set.

The predicates live in `lib/timewindow.py` and are shared with `tools/pr-review-yield.py`, so the two
instruments grade a before/after split identically.

`by_stage` groups on the record's `stage` — `inner` (`chunk`, `final`, `verify-resolutions`) or
`boundary` (`cumulative`), stamped by `critic-begin` and carried through the fact and the findings
cache onto `review.critic` events. It is **read, never derived from the mode**: an event written
before the field existed groups under `null` (rendered "(unrecorded)"), and so does a `review.pr`
event, which carries no stage yet. Schema 5 added the key. This is the yield-by-stage query the
stage-keyed rigor norm (`nonfunctional-requirements.md` § Direction) was drawn to answer.

Mode keys are the short tokens (`chunk` / `final` / `cumulative` /
`verify-resolutions`), derived from the persisted verbose strings. PR-review
events carry `pr` (release-readiness scope — code soundness is certified by
the composition gate before the reviewer is dispatched).

Model keys are **folded to a family label** (`opus` / `sonnet` / `haiku` /
`fable`): one model is recorded under several id strings (`opus`,
`claude-opus-4-8`, `claude-opus-4-8[1m]` are all `opus`), so the aggregation
key collapses the aliases — otherwise the reviewer-model dimension fragments
into noise. An unfamiliar id passes through verbatim (never bucketed
under a known family). This folds **values, not keys**, so `schema_version`
holds; the raw id stays in each ledger line untouched, so the fold is a
read-time view, not a rewrite.

## `prawduct-hook stats [--json] [--since <stamp>] [--until <stamp>]`

What governance cost and what it caught, **per plugin version** (`major.minor`).
It reads the clone-shared evidence store, not the ledger. Every fact there
carries the plugin version that wrote it, and nothing is lost when a worktree is
deleted. `review-stats` answers a different question: what a review costs, by
mode and model, in this worktree. Exit 0 with a report (an empty store is an
answer); exit 1 on bad arguments or a store that cannot be read. `--since` and
`--until` scope facts by their `ts`, and take the same bounds `review-stats`
does. A finding's outcome is read from every fact, whatever its date, so a
finding raised inside the window and fixed after it counts as fixed.

The definitions (their one home):

**Cost**
- **rounds per scope**: reviews per work unit (a review's `scope`, else its
  branch), as median, p90 (nearest rank) and max. A unit whose reviews span a
  version bump counts once in each version.
- **review time**: measured only where the review's dispatch was clocked
  (`dispatched_at` to the fact's `ts`), as median per review and per scope.
  Reviews carrying only the reviewer's self-estimate are counted separately and
  never summed into the measured total, because the estimate runs high.
- **empty verify rounds**: `verify-resolutions` reviews that confirmed no
  resolution and raised no blocking or warning finding.
- **re-reviews**:
  - *same interval*: a review of exactly the (base, head) tree pair an earlier
    review covered.
  - *same head tree*: a review of a head tree already reviewed, whatever its
    base.
  - "Already reviewed" reads the whole store, so under `--since` a review of a
    tree reviewed before the window still counts.
- **stop blocks**:
  - Stops blocked, and stops blocked per recorded session. Only sessions with a
    `session-start` fact are counted, and only blocks from those sessions are
    divided by them, so a version whose early sessions predate the fact is not
    inflated.
  - Blocks by gate.
  - *loops*: (session, gate) pairs where one gate blocked three or more times in
    a session. A Stop that passes records nothing, so "consecutive" cannot be
    measured.
- **guard refusals**: control firings other than Stop blocks, per recorded
  session (the same rule) and by guard. A base-advance transfer grant shares
  their sink, but it is a pass, so it is counted under Benefit instead.

**Benefit**
- **findings**: per severity, raised, then what became of each one.
  - Each finding's state comes from the same rule `render-dispositions` uses
    (`dispositions.finding_state`), so the two reports never disagree about a
    finding.
  - A resolution outranks any disposition; among dispositions, the newest
    wins.
  - Outcomes are fixed (a verify pass confirmed it), fixed_unreviewed (recorded
    fixed with no review), filed, accepted, waived and undispositioned. Anything
    else lands in `other`, including a state a later plugin adds or a malformed
    finding.
  - *acted on* = (fixed + fixed_unreviewed + filed) / (those + accepted +
    waived). Undispositioned findings are left out of the rate and reported
    beside it. The denominator is exported as `answered`.
- **blocking fixed by goal**, and **blocking and warnings fixed per scope**.
  Both kinds of fixed count.
- **red suite runs**: recorded suite runs with a failure.
- **transfer grants**: base-advance transfers that granted, each a review round
  the transfer saved, per recorded session.

Rates with no denominator print as `-` (`null` in `--json`), never as zero.
`--json` carries `schema_version`, `project`, `generated_at`, `window`,
`schema_ahead` (facts a newer plugin wrote, not counted) and `by_version`, keyed
by `major.minor` (`unknown` when a fact names no version).
