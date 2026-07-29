---
artifact: build-plan
version: 2
scope: record-mechanization
depends_on:
  - artifact: change-log-ledger-design      # Chunk 05's subject — the proposal this plan spikes, not implements
  - artifact: kernel-v3-evidence-design     # the facts-not-prose precedent every chunk extends
  - artifact: data-model                    # kernel norms the new fact kind must satisfy
  - artifact: api-contract                  # CLI surface conventions for the new subcommands
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts from facts, no model in a fact's write path → conforms — disposition facts are appended by `prawduct-hook disposition`, which validates the (review_id, fid) join and severity rules in code before writing; the model supplies content exactly as it does for resolutions today"
      - "facts immutable and append-only → conforms — a changed disposition is a newer fact, never an edit; the census renderer resolves last-fact-wins"
      - "derived views never authoritative, no gate reads a view → conforms — the rendered census is display prose; gates keep composing over facts, and record-lint reads sources, never views"
      - "newer-schema facts block loudly → conforms — disposition facts carry the store's existing `schema` field and inherit its SCHEMA-AHEAD behavior"
      - "two stores, two lifetimes → conforms — dispositions are shared committed answers in the evidence store; any lint cache stays per-clone and gitignored"
      - "backlog_service_repo selects the authoritative backlog store → conforms — record-lint's backlog-id existence check routes on the scalar: markdown backend reads backlog.md, Issues backend states the gap (the 3.2.0 reconciliation posture) rather than reading frozen history"
  - artifact: architecture
    dispositions:
      - "independent reviewer never mutates the reviewed session → conforms — record-lint runs inside critic-begin (kernel code); reviewers gain no new write surface"
      - "authority fails closed, advice fails soft → conforms — existing gate semantics are untouched; lint results enter the manifest as findings for the builder to disposition, and a lint that cannot read its inputs errors rather than passing"
      - "local-first, no network/daemon/third-party deps → conforms — every new check is file and git reads"
      - "plugin writes only its own .prawduct/ state, the evidence store, and reconciled config → conforms — new facts go to the evidence store; the renderer writes nothing unasked"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0, run-count is the lever → conforms — this plan is that norm's implementation arm: fewer record-triggered rounds, thinner payloads, fewer coordinator dispatches"
      - "state-file growth is an advisory, never a hard block → conforms — disposition facts ride evidence.jsonl, which already carries the growth-advisory posture"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms — lint verifies record contents against reality; nothing in a record directs behavior"
      - "destructive ops need operation-level owner approval → inapplicable because the plan only appends facts and reads state; the subtraction edits are ordinary reviewed commits"
      - "no cross-owner content egress → inapplicable because no network surface is touched"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary, stdout/stderr channel split → conforms — new subcommands adopt both"
      - "the ledger has a single writer → conforms — the ledger is untouched; consolidation remains its writer"
      - "no prawduct-internal identifiers in product-emitted text → conforms — rendered censuses land in .prawduct records and PR bodies, the non-emitted side, matching where finding ids already live; the `disposition` CLI's stdout confirmations also name a review id and fid, and those are the product's OWN governance identifiers (the same ones `evidence list` prints and resolution facts join on), not prawduct-internal ones, addressed to the builder who just typed them"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data independently schema-versioned → conforms — new subcommands ride the plugin version; disposition facts use the store's schema versioning"
      - "exit codes are the contract; errors attributed, never stack traces → conforms — new subcommands document exit codes on the existing scheme"
      - "additive-first evolution → conforms — new subcommands and flags only; no existing flag, exit code, or --json key is repurposed"
last_validated: 2026-07-29
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem is measured, not inferred: on 2026-07-29, 57% of the day's 151 Critic findings
targeted hand-authored governance records rather than shipped behavior; test-count arithmetic alone
consumed three review rounds in one product repo; the census in one change-log entry was corrected
three times, each correction re-entering review. The retrospective (this plan's requirement source,
requested by the owner) and the evidence store agree. What is unconfirmed is design detail, not
diagnosis: the disposition-fact schema is a persisted-format lock-in whose consumer queries must be
enumerated before fields are designed (Chunk 01 step 0), and two tuning values are inferred.

**Open assumptions / unknowns:**
- [ASSUMPTION: disposition facts extend evidence.jsonl rather than a new store — same lifetime, same sharing, same schema machinery | HIGH impact | user can override]
- [ASSUMPTION: the coordinator threshold moves from 5 changed files to 12 *judgeable* files | MED impact | user can correct the number; Chunk 04 validates it against review-stats history before locking]
- [ASSUMPTION: suite-total test counts in durable prose are deleted outright, not lint-verified — nothing consumes them; the evidence store already holds pass/fail per tree | MED impact | user can override]
- [ASSUMPTION: the change-log ledger is spiked here and implemented in a follow-on plan, since it is a plugin-wide breaking change needing its own migrate path and release | HIGH impact | user can override — pulling implementation into this plan roughly doubles it]

**What would raise confidence:** Chunk 01 step 0 (consumer-query enumeration) resolves the schema
unknown; Chunk 04's review-stats measurement resolves the threshold.

## Status

- [ ] Chunk 01: Disposition facts and the census renderer
- [ ] Chunk 02: Subtraction sweep and deterministic record-lint
- [ ] Chunk 03: Per-mode reviewer payload
- [ ] Chunk 04: Coordinator roster keyed to judgeable files
- [ ] Chunk 05: Change-log ledger spike and go/no-go
Context: Plan authored 2026-07-29 from the ship-day retrospective (v3.2.0 + discodon). **Chunk 01
complete 2026-07-29** — `disposition` fact kind + `render-dispositions`; step 0's consumer-query
enumeration is recorded in the chunk's own section and is the schema-lock-in checkpoint's subject.
Reviewed at `rev-20260729T230420Z-71b7f129` (0 blocking, 9 warning, 16 note; 17 fixed, 8 accepted).
The three review-cost levers NOT in this plan, deliberately: converge-by-construction round policy
enforced in critic-begin (filed as CRT-3W6P, child of CRT-8N5V), learnings.md compaction (filed as
LRN-4K8T), and the backlog.md disease (own in-flight GitHub-Issues migration). **Also amended on this
branch, outside every chunk's scope:** the Critic's coordinator *dispatch* surfaces
(`review-protocol.md` step 2, `SKILL.md`'s roster bullet) now require the three reviewers to be
issued in one message, with a mutation-proved guardrail — Chunk 04 author please note, since that
chunk changes roster *selection* on the same two files. That fix also exposed and closed a
deterministic ledger double-anchor (`review_event_exists`). Next: Chunk 02 (subtraction sweep +
deterministic record-lint).

## Scaffolding

Existing plugin codebase — no scaffold. Tests: `python -m pytest tests/ -q` (pip + pyproject per
`project-preferences.md`). New code follows existing `plugin/lib/` module layout and the
`prawduct-hook` subcommand pattern.

### Verification Strategy

The framework's own repo is the test bed: every chunk's deliverable runs against the real
`evidence.jsonl` (254 reviews, 505 resolutions) and the real records that failed review on
2026-07-29. Chunk 03 additionally measures payload with the existing token-budget guardrail tests.
Plan-level success is measured by `prawduct-hook review-stats` on the next comparable working day:
record-class findings under 20% of total (from 57%), median rounds per logical change at or under
2, chunk/verify-resolutions wall-clock at or under 3 minutes.

## Build Chunks

### Chunk 01: Disposition facts and the census renderer

- **Description:** The keystone slice: dispositions become facts, and the census becomes a derived
  view. Today ACCEPT/FILE dispositions live only in hand-written change-log prose — which is why
  censuses drift and their corrections buy review rounds. New fact kind `disposition`
  (accept | file; fixed/waived stay with verify-resolutions) written by a new CLI:
  `prawduct-hook disposition <review-id> <fid> --accept <reason> | --file <backlog-id>`, validating
  the (review_id, fid) join against the store and refusing `--accept` on a BLOCKING finding without
  an explicit `--owner-ruling <text>` (review-cycle.md's severity rule, enforced in code). A
  renderer, `prawduct-hook render-dispositions [--review <id> | --scope <s>] [--json]`, derives the
  census table for change-log entries and PR bodies. `review-cycle.md`'s disposition section is
  updated: dispositions are recorded via the CLI and censuses are rendered, never authored.
- **Depends on:** none
- **Artifacts consumed:** `data-model.md` (kernel norms), `kernel-v3-evidence-design.md` (fact
  patterns), `api-contract.md` (CLI conventions)
- **Deliverables:** new `plugin/lib/dispositions.py`, subcommand wiring in `plugin/bin/prawduct-hook`,
  edits to `plugin/skills/critic/review-cycle.md`, new `tests/test_dispositions.py`
- **Tests:** unit — join validation, blocking-accept refusal, last-fact-wins on re-disposition;
  integration — render against a fixture store and against the real store's 2026-07-29 facts
- **Acceptance criteria:** a finding can be dispositioned in one command; `render-dispositions`
  reproduces the 2026-07-29 census that took three hand-written corrections, correctly, from facts
- **Exposed API:** prawduct-hook-cli
- **Critic mode:** final
- **Done when:**
  0. Consumer-query enumeration for the disposition fact (persisted-format rule,
     `methodology/planning.md`): read every prospective consumer — renderer, review-stats, gates
     (which must remain blocking-resolution-only), next-review context — and record the queries in
     this chunk's section before designing fields — **done 2026-07-29, below**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

#### Step 0 — consumer queries for the `disposition` fact (recorded 2026-07-29)

Every prospective consumer was read before fields were designed. The fact is a persisted format, so
reversal cost — not line count — set the rigor (`methodology/building.md` "Decision Research").

| # | Consumer | Query it must answer | Fields it needs |
|---|---|---|---|
| Q1 | `render-dispositions --review <id>` | For review R, every finding with its severity, title, and current disposition — `fixed`/`waived` (resolution facts), `accept`/`file` (disposition facts), or **none** | join `(review_id, fid)`; `action`; `reason`; `backlog_id`; `owner_ruling` |
| Q2 | `render-dispositions --scope <s>` | Same rolled up across every review of a scope | none new — `scope` already rides the review fact body |
| Q3 | Gates (`check-cumulative-critic`, Stop) | *Negative query:* does a disposition fact ever affect unresolved-blocking? Must be **no** | none — must stay unreadable to gates |
| Q4 | `review-stats` (future) | Accept-rate per reviewer role × model × mode — the honest "actionable yield" denominator | none new — `(review_id, fid, action)` joins to the review fact, which already carries roster/model/mode |
| Q5 | Next-review context (future) | Which findings of the prior review were accepted, so a reviewer is not re-raising a closed question | none new — `action` + `reason` |
| Q6 | Change-log entry / PR body | The census table as prose, plus a machine form | none new — `--json` renders the same query as Q1 |
| Q7 | Audit ("who accepted this, when, from where") | Provenance of the disposition | none — the envelope's `actor` + `ts` already answer it |
| Q8 | The blocking-accept rule | An `--accept` on a BLOCKING finding is refused without an explicit owner ruling | `owner_ruling`, persisted so the ruling survives as the record |
| Q9 | Completeness | Which findings of a review are **undispositioned** — the gap `review-cycle.md`'s "severity does not exempt" rule asserts but nothing measures | none new — absence is the answer |

**Resulting body** (the join shape deliberately mirrors the resolution fact's, so the two kinds read
alike):

```
{"finding": {"review_id": str, "fid": str},
 "action": "accept" | "file",
 "reason": str | None,          # required for accept
 "backlog_id": str | None,      # required for file
 "owner_ruling": str | None}    # required when the finding is BLOCKING
```

Deliberately **absent**: the finding's `severity` and `title` (Q1 joins to the review fact for
`title` anyway, so denormalizing buys nothing — review facts are immutable, so there is no staleness
argument for copying either); any `*_tree` key (see M4).

**Five mechanism findings that shaped the design** — each from reading the code, not inferring it
(Principle 24):

- **M1 — a re-disposition cannot reuse the fact id.** `evidence.read_facts` dedupes `(kind, id)`
  keeping the **first** occurrence, so an append under an existing id is silently discarded. The id
  therefore carries a per-finding sequence (`disp:<review_id>:<fid>:<n>`), and an unchanged
  re-disposition is caught by an explicit newest-fact comparison that reports a no-op — never by
  accidental dedupe. Last-fact-wins resolves by store order, which is append order.
- **M2 — "disposition" already names two other vocabularies.** Release scope carries
  `ships`/`withheld` (`release_readiness.py`) and resolution facts carry `fixed`/`waived`
  (`coverage_algebra._RESOLVING_DISPOSITIONS`). A third `body.disposition` would make one field name
  mean three things across the store, so this fact's field is **`action`**.
- **M3 — the gate invariant holds by construction, and a test pins it.** `resolution_index` filters
  `kind != "resolution"` before reading any body, so a `disposition` fact is structurally incapable
  of unblocking a BLOCKING finding (Q3). That is the load-bearing safety property of this chunk; it
  gets an explicit regression test rather than resting on the filter staying put.
- **M4 — no tree keys in the body.** `evidence.distinct_trees` scans `base_tree`/`head_tree` across
  *all* facts to drive the store-growth advisory. A disposition is an answer about a finding, not a
  coverage edge, so carrying a tree would both inflate that advisory and invite a reader to mistake
  it for one.
- **M5 — `review-stats` reads the governance ledger, not the evidence store.** Q4 is therefore a
  future join needing a reader change, not a field change. Recorded so Chunk 04's threshold
  measurement does not assume dispositions are already visible to it.

### Chunk 02: Subtraction sweep and deterministic record-lint

- **Description:** Subtraction first: durable records stop carrying machine-derivable numbers.
  Suite-total test counts are deleted from every surface that demands or exhibits them (methodology,
  templates, skill prose) — the evidence store already records pass/fail per tree via
  `test-evidence record`, and nothing consumes the prose copies. Then the checks that must remain
  become code: a `verify-records` pass run by `critic-begin`, whose results are embedded in the
  dispatch manifest as machine-verified items reviewers are told not to re-derive. Checks:
  backticked file and `file:line` references in judgeable records resolve; referenced backlog ids
  exist (routed on `backlog_service_repo`); a plan's `governed_by:` disposition count matches each
  cited artifact's actual `## Direction` norm count (the GOV-8C3W mechanical enumeration); flagged
  suite-total claims in judgeable records (the subtraction's tripwire).
- **Depends on:** Chunk 01
- **Artifacts consumed:** `data-model.md` (backlog-routing norm), retrospective finding classes
- **Deliverables:** new `plugin/lib/record_lint.py`, `critic-begin` wiring and manifest field,
  subtraction edits across `plugin/methodology/`, `plugin/templates/`, `plugin/skills/`, edits to
  `plugin/skills/critic/review-protocol.md` (checks moved from model text to manifest), new
  `tests/test_record_lint.py`
- **Tests:** unit — each check against fixtures including the real defects from 2026-07-29 (the
  drifted census, the GOV-8C3W one-of-three disposition gap); integration — manifest carries lint
  results; guardrail — no methodology/template surface still requests a test count
- **Acceptance criteria:** `critic-begin` on a branch with a dangling `file:line` ref or an
  incomplete `governed_by:` block reports it in the manifest in seconds, deterministically, without
  a reviewer
- **Exposed API:** prawduct-hook-cli
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Per-mode reviewer payload

- **Description:** A `chunk` or `verify-resolutions` reviewer currently loads the full 217-line
  protocol plus the 305-line review-cycle to run three goals for a target 1–2 minutes — and actual
  wall-clock ran 5–10 minutes all day on 2026-07-29. Distill goals 1–3 into a new
  `plugin/skills/critic/goals-1-3.md` (target ≤80 lines) that those modes load instead; `final` and
  `cumulative` keep the full protocol minus the check text Chunk 02 mechanized. Add a token-budget
  guardrail test for the new slice so it cannot regrow.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `nonfunctional-requirements.md` (wall-clock norm)
- **Deliverables:** new `plugin/skills/critic/goals-1-3.md`, edits to
  `plugin/skills/critic/SKILL.md`, `review-protocol.md`, `review-cycle.md`, budget test in
  `tests/preferences/`
- **Tests:** guardrail — payload budgets per mode; behavioral — mode-to-payload selection
- **Acceptance criteria:** measured payload for chunk/verify modes drops by at least half; protocol
  content for those modes is self-contained (no follow-the-pointer reads at review time)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Coordinator roster keyed to judgeable files

- **Description:** The coordinator pattern (three subagents) currently fires at 5+ changed files —
  counting non-judgeable record files, so routine medium diffs pay triple review. Key the roster
  rule to *judgeable* changed files and raise the threshold to 12 (validated against review-stats
  history before locking — if the data says a different knee, use it and record why). Manifest
  telemetry (`roster_chosen_by`) already exists to observe the change.
- **Depends on:** Chunk 03
- **Artifacts consumed:** `nonfunctional-requirements.md`
- **Deliverables:** roster derivation edit in `critic-begin` (`plugin/lib/` locus found at build
  time), edits to `review-protocol.md` and `review-cycle.md` tables, tests
- **Tests:** unit — roster selection across the boundary, judgeable-only counting; regression —
  single-pass path unchanged
- **Acceptance criteria:** a 10-file diff of which 6 are records reviews single-pass; review-stats
  shows the expected roster mix on replayed history
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Change-log ledger spike and go/no-go

- **Description:** The change-log is the largest remaining hand-authored record surface;
  `change-log-ledger-design.md` (proposed 2026-07-29) already designs its mechanization and names
  its own de-risking step. Execute exactly that: convert five real change-log entries end-to-end to
  the per-change fact format, render, and diff against `parse_change_log` output as the equivalence
  oracle; review the backlog-service overlap the design marks as a scheduling prerequisite (§6);
  record a go/no-go with scoping for a follow-on `change-log-ledger` build plan. Implementation is
  explicitly out of scope here — it is a plugin-wide breaking change deserving its own plan,
  migrate path, and release.
- **Depends on:** Chunk 01 (pattern), none of 02–04
- **Artifacts consumed:** `change-log-ledger-design.md` §§5–9
- **Deliverables:** spike artifacts under the scratch area, findings appended to
  `change-log-ledger-design.md` (status updated), go/no-go decision recorded
- **Tests:** the equivalence-oracle diff is the test
- **Acceptance criteria:** five entries round-trip with a byte-level accounting of any divergence;
  the design's Requirements Confidence moves off Medium in whichever direction the spike indicates
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook render-dispositions` against the real evidence store
and see the census that took three hand-written corrections on 2026-07-29 produced correctly from
facts in one command.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes; Chunk 05's cumulative
review makes the branch PR-ready.

- After Chunk 01: schema lock-in review — the disposition fact's consumer queries and fields are the
  plan's one irreversible decision; confirm before anything builds on it.
- After Chunk 03: measure — payload delta from guardrail tests, and a spot-check that a chunk-mode
  review now lands near its 1–2 minute target.
- After Chunk 05 (cumulative): full-bundle review; verify the success metrics section of
  Verification Strategy has its baseline recorded so the next working day can be compared.

## Related open backlog items

GOV-8C3W (mechanical `governed_by` enumeration — Chunk 02 implements it), DOC-5T8N (hand-edited
derived blocks — Chunk 05's subject absorbs it), COV-2P7F (`check-change-log-entry` routing —
converges with the ledger follow-on, not this plan), GOV-6D4Q (the 2026-07-02 simplification
diagnosis whose fix program never ran — this plan is a measured successor on the record layer),
BLD-5R7K (chunk-progress degradation — adjacent, not covered; stays open).

Opened or advanced by this plan's own work: CRT-8N5V (review-loop exit condition — its enforcement
leg is now CRT-3W6P, filed rather than absorbed because it changes the Critic *dispatch* path, not
the record layer), TEL-2B6K (ledger phase 2 — Chunk 01 landed the record half of its part (b); what
remains is the `gate.blocked`/`probe.fired` kinds plus the join that would let disposition facts
reach `review-stats`, which reads the ledger and not the evidence store), CRT-R4Z2 (coordinator
findings double-counted because the merge key cannot collide across disjoint goal sets), LRN-4K8T
(learnings.md compaction).
