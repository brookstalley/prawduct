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
- `scope` is the build-plan feature key (passed explicitly by the reviewer;
  the `active_build_plan` pointer is only the fallback).
- `duration_seconds` and `actor.model` are nullable — recorded, never invented.
- v1 emits `review.critic` (the Critic, after writing its findings file) and
  `review.pr` (the `/prawduct:pr` skill after the PR review, via
  `--findings <evidence-path>` — required for `review.pr`, rejected for
  `review.critic`, whose only trusted source is the canonical
  `.critic-findings.json`). `build.chunk` / `plan.authored` /
  `discovery.session` are accommodated by the envelope and deliberately not
  yet produced.
- **Consumers skip unknown event kinds and unknown fields** — that contract is
  what lets producers grow without migrating the ledger.

## `prawduct-hook review-stats [--json]`

Aggregates `review.*` events; skips corrupt lines, non-`review.*` kinds, and
unusable payloads **with counts** (never silently). Missing ledger → "no
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
events carry `pr-scoped` (the Critic record survived the audit and was
consumed) or `pr-full` (record voided or absent — full code-soundness pass),
so scoped and full runs aggregate as distinct modes.
