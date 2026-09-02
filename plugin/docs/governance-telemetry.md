# Governance Telemetry

Visible Costs (Principle 9) applied to the framework itself: every independent
review appends one event to an append-only ledger, and `prawduct-hook
review-stats` aggregates that history into the numbers proportionality
decisions need. Telemetry is **pulled, not pushed** — no hook nags about it;
`/prawduct:janitor` reads it during maintenance.

## The event ledger

`.prawduct/.governance-ledger.jsonl` (gitignored) — one JSON event per line,
written ONLY by `prawduct-hook ledger-append` (agents never hand-author
JSONL; the helper validates the findings record and computes the envelope).

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
- `review.critic` (the Critic, after writing its findings file) and
  `review.pr` (the `/prawduct:pr` skill after the PR review, via
  `--findings <evidence-path>` — required for `review.pr`, rejected for
  `review.critic`, whose only trusted source is the canonical
  `.critic-findings.json`). `build.chunk` / `plan.authored` /
  `discovery.session` are accommodated by the envelope and deliberately not
  yet produced.
- `learning.written` and `learning.fired` — the learning loop, below.
- **Consumers skip unknown event kinds and unknown fields** — that contract is
  what lets producers grow without migrating the ledger.

## The learning-loop events

Measure the loop or do not claim it. Two kinds record what the rules corpus
actually does, so an audit reads a number instead of sampling transcripts:

| kind | `actor.role` | emitted by | means |
|---|---|---|---|
| `learning.written` | `builder` | the Stop hook, after the learnings budget check | a rule unit that is new since this session's base revision |
| `learning.fired` | `critic` | `critic-consolidate`, after the `review.critic` anchor | a consolidated finding quoted a rule's opening words |

Both nest under a `learning` key, under the same envelope:

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
2. **Which rules fire, how often, and in which review** — count
   `learning.fired` by `learning.unit_hash`, read `learning.review_id`.
3. **Which rules never fire** — join the corpus's units (hash each with
   `rule_units` + `unit_hash`) against the `learning.fired` hashes. This is the
   question the corpus cannot answer about itself, and the reason `unit_hash`
   is a content hash rather than a heading string or a line number.
4. **All of the above across a fleet** — key by the envelope's `project`.

Nothing in the plugin reads these yet; `review-stats` counts them under
`skipped.unknown_kinds` (below), which is v1's documented contract for a kind a
consumer does not aggregate.

## `prawduct-hook review-stats [--json]`

Aggregates `review.*` events; skips corrupt lines, non-`review.*` kinds, and
unusable payloads **with counts** (never silently). The `learning.*` kinds land
in `skipped.unknown_kinds` — "unknown to this report", which is what the key has
always meant. The key is documented rather than renamed: a JSON key is never
repurposed, and `--json` consumers pin it. Missing ledger → "no
review history", exit 0. Exit 1 only on bad arguments.

Per grouping — overall, `actor.role` × `actor.model` × review mode, and
per-`scope` — it reports: review count, total/median `duration_seconds`,
findings by severity, **actionable rate** (share of reviews with ≥1
blocking/warning), and findings-per-review. Plus a findings-by-file rollup
from per-finding `files` attribution (top paths by actionable findings,
capped at 10 with the total attributed count alongside).

### The `--json` contract

The machine shape is the seam cross-project aggregation (TEL-7A4X) builds on.
Top-level keys, in order:

```
schema_version   report schema (bumped on any key change — pinned by
                 tests/test_review_stats.py)
project          repo directory name
generated_at     ISO-8601 UTC
events_total     reportable review.* events
skipped          {corrupt_lines, unknown_kinds, invalid_payloads}
overall          one stat block (below)
by_role_model_mode  [{role, model, mode, ...stat block}]
by_scope         [{scope, ...stat block}]
top_files        [{path, actionable_findings, findings}]
files_attributed_total  count behind the top_files cap
```

Stat block: `reviews`, `duration_total_seconds`, `duration_median_seconds`
(null when no event carried a duration), `findings`
(`{blocking, warning, note, other}`), `findings_per_review`,
`actionable_rate` (0–1).

Mode keys are the short tokens (`chunk` / `final` / `cumulative` /
`verify-resolutions`), derived from the persisted verbose strings. PR-review
events carry `pr` (release-readiness scope — code soundness is certified by
the composition gate before the reviewer is dispatched).

Model keys are **folded to a family label** (`opus` / `sonnet` / `haiku` /
`fable`): one model is recorded under several id strings (`opus`,
`claude-opus-4-8`, `claude-opus-4-8[1m]` are all `opus`), so the aggregation
key collapses the aliases — otherwise the reviewer-model dimension fragments
into noise (TEL-4M9X). An unfamiliar id passes through verbatim (never bucketed
under a known family). This folds **values, not keys**, so `schema_version`
holds; the raw id stays in each ledger line untouched, so the fold is a
read-time view, not a rewrite.
