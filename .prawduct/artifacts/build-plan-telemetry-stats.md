---
artifact: build-plan
version: 1
scope: telemetry-stats
branch: feature/telemetry-stats
partition: serial — chunk 02's report reads the facts chunk 01 starts writing, and both touch prawduct-hook's dispatch table
depends_on:
  - artifact: roi-audit-2026-10-02
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways; a control emits its yield observably → conforms: this plan is that norm's instrument. Stop-gate blocks become countable facts, and `stats` reports yield by plugin version so a control can be retired on evidence"
      - "review wall-clock is P0 → conforms: no review is added; `stats` reports only measured time as time and labels self-estimates as estimates"
      - "state-file growth is advisory → conforms: one fact per Stop block and one per session boundary, both observational; no new state file"
      - "review rigor is stage-keyed → inapplicable, because no review stage or severity rule changes"
  - artifact: data-model
    dispositions:
      - "verdicts come from append-only facts; no model in a fact's write path → conforms: the Stop hook and SessionStart write the facts from code; no model writes them"
      - "facts immutable and append-only → conforms"
      - "derived views never authoritative → conforms: `stats` is a report; no gate reads it"
      - "a fact from a newer schema is a loud block → conforms: no schema version moves. The new `session-start` kind is additive under schema 1, and older readers keep unknown kinds without letting them satisfy a gate (evidence.py's forward-compat rule)"
      - "two stores, two lifetimes → conforms: both facts go to the clone-shared evidence store, which outlives worktrees"
      - "a governance document reaches a terminal state, never deleted → conforms: this plan is archived at merge like any other"
      - "every backlog write conforms to the issue title standard → inapplicable, because this plan writes no backlog item"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable, because no backlog read or write changes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; no per-subcommand version; persisted data schema-versioned → conforms: `stats --json` carries its own `schema_version`, like `review-stats --json`"
      - "exit codes are the contract → conforms: `stats` exits 0 on a report (an empty store included) and 1 on bad arguments or an unreadable store, matching review-stats"
      - "additive-first evolution → conforms: new subcommand; nothing repurposed"
  - artifact: architecture
    dispositions:
      - "local-first, two admitted network surfaces → conforms: wave 1 opens no socket. Wave 2's upload is a third surface, and owner confirmation of that amendment is a wave-2 entry condition, not this plan's"
      - "the plugin writes nothing into a governed repo but its own state and the shared store → conforms"
      - "authority fails closed; advice fails soft → conforms: recording a block is advice. A failed append is attributed on stderr and never changes the Stop exit code or delays session start"
      - "every fact has one home → conforms: metric definitions live in governance-telemetry.md; the audit artifact cites them"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "written in Python, never specific to Python → conforms: the metrics read language-neutral facts; nothing dispatches by language"
      - "prawduct guides and reviews, it never implements → conforms: the report measures governance; it writes no product code"
      - "goals and verification bind; prescribed method is advice → conforms: Done-when states what must be true; the file lists are forecasts"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use the severity-prefix vocabulary and the stdout/stderr split → conforms: a failed append is a `NOTE:` on stderr"
      - "the ledger has one writer → inapplicable, because nothing new is written to the ledger"
      - "emitted text names no internal identifier → conforms: `stats` output names metrics in plain language"
---

# Build Plan: telemetry stats, wave 1 (local metrics)

## Problem

Nobody can answer "did prawduct version N cost more or protect more than N-1?" without a one-off
audit, and the 2026-10-02 audit (`roi-audit-2026-10-02.md`) had to mine Claude Code transcripts
for Stop-hook blocks because prawduct records none. Transcripts are kept for about six weeks.

## Success

- Every Stop-hook block appends one fact per blocking gate to the evidence store, and every
  session boundary appends a `session-start` fact.
- `prawduct-hook stats [--json] [--since] [--until]` reports the audit's metric set per plugin
  `major.minor` from this clone's evidence store. Run against the sibling stores, it reproduces
  the audit's review numbers, which is the cross-check that it is right.

## Out of scope

- Any upload, payload schema or collector: waves 2 and 3.
- Escape attribution (B5): phase 2.
- Changing `review-stats` (its actionable rate stays severity-derived; #941 is answered by
  `stats`' disposition-based precision and is updated to say so, not closed by this plan).
- Doctor checks and the other #563 control classes.

## Requirements Confidence: Medium

The metric definitions are settled by the audit. Unconfirmed:

- [ASSUMPTION: a Stop block is recorded through the existing `guard-refusal` class sink (one fact
  per blocking gate, `guard: "stop-gate:<gate-id>"`), not through a new kind | MED impact | owner
  can override]
- [ASSUMPTION: a `session-start` fact per session boundary (startup and /clear, not resume) is an
  acceptable growth rate for the evidence store | LOW impact | owner can override]

`[DECISION: Stop-gate blocks ride the guard-refusal sink | #563's 2026-09-30 owner decision asks
for one "control fired" event shape and one sink for doctor checks, guards and gates, and names
`append_guard_refusal` as the starting point. Reusing it gives one shape now; it also means plugin
versions already in the field read the new facts as a kind they know, which keeps them
observational (out of their verdict-cache key) instead of an unknown kind that would evict every
cached verdict on each block. The kind name reads "guard"; the body's `guard` field is documented
as naming the control. | owner can veto]`

## Status

- [x] Chunk 01: Stop-block and session-start facts
- [ ] Chunk 02: `prawduct-hook stats`

## Chunk 01: Stop-block and session-start facts

**Files:** `plugin/lib/evidence.py` (`KNOWN_KINDS`, `OBSERVATIONAL_KINDS`, new `append_stop_block`,
new `append_session_start`), `plugin/bin/prawduct-hook` (the Stop path's final `return 2`; the
session-boundary stamp in `cmd_clear`), the `evidence list` renderer, tests, and
`plugin/docs/governance-telemetry.md`.

**Persisted-format questions the facts must answer:** how often each gate blocks per session and
per plugin version; whether one gate blocks repeatedly within a session (its facts grouped by
`actor.session`); which gates co-fire on one Stop; how many sessions ran per version. Body:
`{"guard": "stop-gate:<id>", "gate": "<id>", "stop": "<one id shared by the Stop's facts>",
"co_gates": [...]}`; `session-start` body `{}`: the envelope is the record, and no question here needs
the SessionStart payload's `source`.

**Done when:** a blocked Stop appends one fact per blocking gate and a clean Stop appends none; a
deferred gate appends nothing; a store failure prints a `NOTE:` and leaves the exit code at 2; a
session boundary appends one `session-start` and a continuation appends none; older-reader safety
is pinned (a `session-start` line is excluded from `coverage_fingerprint`); `evidence list` shows
both. The touched tests pass.

## Chunk 02: `prawduct-hook stats`

**Files:** new `plugin/lib/stats.py`, `plugin/bin/prawduct-hook` (dispatch + usage), new
`tests/test_stats.py`, `plugin/docs/governance-telemetry.md` (metric definitions — their one
home), `plugin/skills/janitor/SKILL.md` (instruction plus both grant forms), `plugin/CHANGELOG.md`.

**Metrics,** per plugin `major.minor`, windowed by `--since`/`--until` on fact `ts`:
C1 rounds per scope (median, p90); C2 measured review time per scope (`dispatched_at`→`ts` only,
estimates reported separately and labelled); C3 empty verify-resolutions rounds; C4
unchanged-tree re-reviews; C5 Stop blocks per recorded session and per gate, plus loops (one gate
blocking three or more times in a session — a passing Stop records nothing, so "consecutive" is not
measurable); C6 guard refusals per session; B1 blocking fixed per
scope by goal; B2 warnings fixed per scope; B3 acted-on rate per severity; B4 red recorded suite runs. **Descoped:** B6 (learnings fired per session). Ledger lines carry no
plugin version (#262 TEL1), so it cannot be bucketed by version.

**Done when:** each metric has a fixture test, including a falsifying case (an empty round that
verified a resolution is not empty; an estimated duration is never summed as measured); `--json`
carries `schema_version`; running it over the sibling stores reproduces the audit's
per-version blocking, fixed and verify-resolutions figures; the full suite passes.
