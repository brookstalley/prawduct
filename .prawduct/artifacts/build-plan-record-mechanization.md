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
      - "Python-implemented, never Python-specific; per-file dispatch; unpopulated language reported unchecked (born 2026-07-29) → conforms — record-lint reads records (markdown, YAML, JSON) and backlog ids, not product source, so it classifies no language and encodes no grammar. Chunk 02's `verify-chunk-refs` work touches file *paths* only. If a later chunk needs to decide whether a referenced path is source, it must route through the shared classifier rather than growing a private suffix list."
      - "prawduct guides and reviews, never implements; never re-implements a rule an ecosystem's tooling owns (born 2026-07-29) → conforms — record-lint checks prawduct's OWN governance records for internal consistency, which no linter models and no ecosystem tool owns; it emits findings for the builder rather than editing anything, and writes no product code, config or tooling"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 — BOTH levers, run-count and per-mode payload (amended 2026-07-29) → conforms — this plan is that norm's implementation arm on both arms: Chunk 02 cuts record-triggered round *count*, Chunk 03 cuts per-mode reviewer *payload*. The disposition previously read 'run-count is the lever' and was updated with the amendment, not around it."
      - "proportionality ratchets both ways; new controls emit yield observably (born 2026-07-29) → conforms, by a **ruling recorded 2026-07-30** that took neither branch the chunk offered. Record-lint's per-check counts and findings ride the dispatch manifest into the review **fact** (`critic_consolidate.build_fact_body` copies `record_lint` verbatim), so \"how often did this control fire and on what\" is a query over the evidence store — the same store the review yield it is measured against already lives in. A ledger fact per lint finding was rejected on the observability-strategy norm: the ledger has a **single writer** (consolidation), and a second writer would trade one norm for another. Exemption was rejected outright — this control is born inside the boundary. Yield emitted at birth; the yield *query* remains the janitor's Norm Health sweep, deliberately not here."
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
- [~~ASSUMPTION: the coordinator threshold moves from 5 changed files to 12 *judgeable* files~~ — **FALSIFIED 2026-07-30** by the validation it called for. Judgeable-count keying demotes 54% of historical blocking findings; the shipped rule is risk-surface-first with judgeable ≥ 12 as a secondary escalator, and repos declaring no risk surfaces keep the 5-file rule unchanged. See Chunk 04.]
- [ASSUMPTION: suite-total test counts in durable prose are deleted outright, not lint-verified — nothing consumes them; the evidence store already holds pass/fail per tree | MED impact | user can override] — **resolved 2026-07-30, and the premise was half wrong.** The deletion set on the plugin surface was **empty**: `grep -rnE '[0-9]{3,6} *(tests?|passing|green)' plugin --include='*.md'` returned nothing before the sweep, and no template, methodology step or skill instruction ever *demanded* a count. The habit lives in agents, not in an instruction, so there was nothing to delete and the whole value is in the tripwire. Both halves are now pinned by `tests/preferences/test_no_suite_total_claims.py` (exhibit side and demand side, each mutation-proved).
- [ASSUMPTION: the change-log ledger is spiked here and implemented in a follow-on plan, since it is a plugin-wide breaking change needing its own migrate path and release | HIGH impact | user can override — pulling implementation into this plan roughly doubles it]

**What would raise confidence:** Chunk 01 step 0 (consumer-query enumeration) resolves the schema
unknown; Chunk 04's review-stats measurement resolves the threshold.

## Status

- [x] Chunk 01: Disposition facts and the census renderer
- [x] Chunk 02: Subtraction sweep and deterministic record-lint
- [x] Chunk 03: Per-mode reviewer payload
- [x] Chunk 04: Coordinator roster keyed to risk surface
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
chunk changes roster *selection* on the same two files. That fix also exposed a ledger double-anchor:
`review_event_exists` now closes the replay path and narrows the overlap window, but there is no lock,
so it is not "exactly once" — and concurrent dispatch made overlap more reachable. `critic_consolidate`
additionally grew an advisory duplicate-finding grouping path (CRT-R4Z2's reporting half) that Chunk
04/05 authors will meet in the same file.

**Chunk 02 built 2026-07-30** (checkbox stays `[ ]` — `views_enabled: true`, so Status is a derived
view that `regen-views` regenerates from the change-log tag at release). `record_lint.py` +
`verify-records`, wired into `critic-begin`'s manifest and carried into the review fact.

**Three checks shipped in this chunk, two were built then deleted, and a fourth
(`learnings-entry-shape`) was added later on this branch outside every chunk's scope.** `dangling-ref` and `unknown-backlog-id`
measured **0 true positives** on the 40-file branch that introduced them — `dangling-ref`'s only
three hits were prose that is path-shaped and not a path. Removing them is the proportionality norm
working as designed rather than an omission, and the reason is recorded at the mechanism
(`record_lint.CHECKS`) so a future author argues with the measurement. What survives:
`chunk-ref-missing` (a *move* — a reviewer instruction deleted, net-negative cost),
`governed-by-gap` (the demonstrated yield: **22 gaps across 8 plans**, where GOV-8C3W estimated "a
four-line sweep"), and `suite-total-claim` (the subtraction's tripwire).

Two spec corrections, both recorded above: the subtraction's deletion set was **empty**, and the
observable-yield obligation was ruled into the *fact*, not the ledger.

**Chunk 04's author should know the protocol surface moved:** `verify-chunk-refs` is no longer a
reviewer instruction (it runs at dispatch and rides `record_lint`), its `allowed-tools` grant is
retired with a test pinning the retirement, and the review-protocol token budget was **held at 3620
rather than bumped** — headroom is 5 tokens, so Chunk 03's payload work has none to spend there.
The `cumulative` review of the first cut (`rev-20260730T111810Z-8d2cf430`) is where the trim came
from; it also caught the check grading the *wrong chunk* (Status names the first unchecked box, so a
finished chunk's review graded the next one) and an unguarded decode that would have aborted every
review dispatch on one non-UTF-8 `.md`. Next: Chunk 03 (per-mode reviewer payload).

**Chunk 03 built 2026-07-30.** `plugin/skills/critic/goals-1-3.md` + `SKILL.md` step 2 routing;
payload for `chunk`/`verify-resolutions` drops ~10,500 → ~1,875 tokens (83%, bar was 50%). Three
things Chunk 04's author should know, all on files that chunk also edits:

- **`review-protocol.md` now serves `final`/`cumulative` only**, and its chunk-mode restatements are
  gone. Headroom went 5 → 48 tokens, so there is room there now — but the trim-or-relocate rule stands.
- **Goals 1-3 live in two files, bound by a directional test** (`TestCriticGoals13.
  test_no_check_from_goals_1_3_was_dropped`): adding a check to the protocol's goals 1-3 without
  adding it to `goals-1-3.md` fails the suite. Editing either copy means editing both.
- **The `≤80 lines` target was missed at 125**, deliberately — self-containment required inlining four
  former pointer-chases, and trimming to 80 would have deleted checks. The real acceptance criterion
  (halve the payload, no follow-the-pointer reads) is met and guardrailed.
- **The guardrails landed in `tests/test_v5_methodology.py`, not the declared `tests/preferences/`.**
  They sit beside `review-protocol.md`'s own `test_token_budget`, so the budget rules for both halves
  of the same protocol are read and edited together; splitting them across directories is how one gets
  raised without the other. Deliverable met, path changed, recorded here because the review rightly
  asked why this divergence was the one not written down.

**The acceptance criterion is proved on disk and by guardrail, NOT yet in a live review.** The first
cut of the routing was inert: `SKILL.md`'s header ordered `review-protocol.md` "(read this first)"
twenty-six lines above step 2, so a reviewer obeyed the header and loaded the full 10,519-token
predecessor payload before reaching the instruction telling it not to. A review caught this by doing
it and reporting its own token spend. Every guardrail stayed green — **all of them measured file
sizes; none read the instructions in the order an agent reads them.** Three instruction-order
guardrails now exist. But the reviewer that verified the fix was itself running on a cached pre-fix
skill body, so **the first `chunk`/`verify-resolutions` review in a fresh session is the measurement**
— take it before treating the wall-clock baseline above as re-measurable.

**Observed, not built — for Chunk 04's roster work.** The coordinator's **correctness** reviewer runs
exactly goals 1-3 and still reads the full `review-protocol.md` (its agent definition points there).
Pointing it at `goals-1-3.md` would extend this chunk's saving to the coordinator path, but this
chunk's spec scopes `final`/`cumulative` to the full protocol, so it was left alone rather than taken
quietly. It belongs with roster selection, which is Chunk 04's subject.

**Third amendment outside every chunk's scope, 2026-07-30:** `plugin/methodology/session-digest.md`
gains one line — prefer an invariant to a tally, and where a number is essential compute it at write
time and let a mechanism own it. Owner-requested, on the observation that `learnings.md` is
project-scoped so an onboarded product inherits none of its rules. Recorded here because the
change-log's compaction entry had, one commit earlier, stated the opposite decision; both now stand,
with the reversal noted at the entry.

**Second amendment outside every chunk's scope, 2026-07-30:** the architecture-staleness probe in
`plugin/lib/briefing.py` now skips git-ignored directories, via a new batched
`gitstate.git_paths_ignored`. Declared in the commit and the change-log, and recorded here because
`gitstate.py` is the subject of its own live plan (`build-plan-hot-path-git-batching.md`) whose
author now meets a subprocess-batching helper that plan does not mention. Neither Chunk 03 nor 04
touches either file.

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

### Chunk 04: Coordinator roster keyed to risk surface

**Descoped 2026-07-30 by the validation step this chunk's own spec required.** The original spec —
"key the roster rule to *judgeable* changed files and raise the threshold to 12 … validated against
review-stats history before locking — if the data says a different knee, use it and record why" —
was falsified by that validation. The replay is recorded below; the rule that ships is the one the
data supports.

**[DECISION: judgeable-count keying rejected]** Replaying all 82 `final`/`cumulative` review facts in
the evidence store (35 blocking, 505 warning findings), scoring each candidate rule by the historical
blocking findings it would have sent to a single reviewer:

| rule | coordinator share | blockers demoted |
|---|---|---|
| current: total ≥ 5 | 80% | 2 (6%) |
| **spec as written: judgeable ≥ 12** | 40% | **19 (54%)** |
| judgeable ≥ 5 (count fix only) | 56% | 19 (54%) |
| **risk-surface OR judgeable ≥ 12** | 78% | 1 (3%) |
| gate-kernel OR judgeable ≥ 12 | 52% | 8 (23%) |

**Recomputable — and the table is a dated snapshot, not a standing fact.** `python3
tests/spikes/roster_rule_replay.py` regenerates every row from this clone's evidence store. The
figures above were taken 2026-07-30 over 82 `final`/`cumulative` facts carrying 35 blocking
findings; the store is append-only, so every later review shifts them (this chunk's own reviews
already did). **The invariant the decision rests on is the ordering of the rows, which no
single review changes — read the script's output for current values, never these.**

*"Demoted" scores every rule identically — blocking findings in reviews the rule would send
single-pass — which is what makes the rows comparable. It is an upper bound on loss: a single
reviewer still covers all 7 goals and may have found the same defect. It is the right risk proxy
because deeper per-goal coverage is the only thing the roster choice buys.*

**The actual change is smaller than R3's row suggests.** Measured as reviews that *ran* coordinator
and would now run single-pass: **8 reviews, carrying 0 blocking and 27 warning findings.** R3's one
scored blocker sits in a review that already ran single-pass and found it anyway — so the shipped
rule demotes no review that a coordinator's depth is known to have been needed for.

**Why the premise was wrong.** The spec assumed record files inflate the count, so a record-heavy
diff is a small diff paying triple. The slice it targeted — total ≥ 5, judgeable < 5 — is **20
reviews carrying 17 blocking findings, 13 of which point at code rather than records**. Those are not
record-padded trivia; they are small, high-consequence governance diffs. The sharpest case is the AST
free-edge relaxation (3 judgeable files, 5 total), where the coordinator returned **10 blocking
findings**, including *"the gate can now relax itself with no way to detect it."* Every
judgeable-count rule sends that review single-pass.

The conflation underneath: `coverage_algebra.is_judgeable_path` answers *"does this change need
review coverage"* — a gate question, and the reason it is THE predicate there. It does not answer
*"how much review depth does this change deserve."* A record-heavy diff **is** a governance diff, and
governance diffs are where the blockers are: reviews touching the gate kernel yield 0.96 blocking per
review against 0.22 for everything else, a 4.4× discriminator. No size cut comes close — blocker-
bearing and clean reviews overlap across 0–206 and 0–60 judgeable files respectively.

**What the data does support.** One band is safely demotable: 5–11 judgeable files is 13 coordinator
reviews with **zero** blocking findings. Keying to risk surface with that band as the only demotion
is the rule that ships. It is deliberately a small saving (8 of 82 dispatches, median 420s each) —
recorded as such rather than dressed up, because the honest finding is that **this repo's coordinator
dispatch rate is approximately correct** and the review-cost lever is not roster selection. The
levers that did pay are Chunk 03's payload cut and the round policy filed as CRT-3W6P.

- **Depends on:** Chunk 03
- **Artifacts consumed:** `nonfunctional-requirements.md`
- **Deliverables:** re-anchored risk surfaces in `plugin/lib/risk.py` (see below), roster derivation
  edit in `plugin/lib/critic_consolidate.py` (`_derive_roster`), edits to `review-protocol.md` and
  `review-cycle.md` tables, tests
- **Tests:** unit — roster selection across the boundary, risk-surface intersection, judgeable-count
  escalator; regression — `chunk`/`verify-resolutions` single-pass path unchanged; the risk-surface
  anchoring regression pinned
- **Acceptance criteria:** in a repo that declares `risk_surfaces:`, a diff touching no risk surface
  with 5–11 judgeable files reviews single-pass (an undeclared repo keeps the 5-file rule); a diff touching `plugin/lib/gates.py` reviews coordinator at any size; replayed
  history reproduces the R3 row above

**The prerequisite bug this chunk had to fix first.** `risk.py`'s derived-default surfaces
(`skills/`, `lib/gates*`, `bin/*hook*`) were never re-anchored when the plugin moved into `plugin/`
at `c6b8131` (2026-07-21). None of the three matches a `plugin/`-prefixed path and no
`risk_surfaces:` key is declared, so the invariant since the restructure is that **a diff carrying no
pre-restructure root-layout path cannot classify `escalate`**, gate-kernel changes included. The last
`escalate`, `rev-20260721T143005Z-975cbd6f`, matched only because the restructure was still in flight
and its diff listed the root paths being deleted; every review after it went `standard` — 95
consecutive, 24 of them `final`/`cumulative`, ending only when this chunk's fix landed. It went unnoticed because the
2026-07-14 `reviewer-session-model` patch (user directive: prawduct was escalating to fable far too
often) removed the verdict's only consumer; the tier has been telemetry-only since, so nothing
downstream was watching when it broke. Blast radius today is nil, which is exactly why it survived.

**A consequence for any future restore of tiering (REL-5K8M).** Re-anchored, the derived surfaces
match 77% of this repo's reviews — and near-100% before the restructure. That breadth is the same
root cause as the over-escalation the July directive was reacting to. It is harmless here because
the roster is not model selection, but a tiering restore that reconnects this verdict to model
choice reproduces the original complaint unless the surface list is narrowed first. Recorded at the
mechanism in `risk.py`.
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
  review now lands near its 1–2 minute target. **The spot-check must come from a genuinely new Claude
  Code invocation** — not merely a new fork. On 2026-07-30, *every* fork launched *after* the
  fix still received the pre-fix `SKILL.md` body and followed the old routing, so the stale skill
  payload survives a fresh fork within a session. A same-session reading proves nothing about the new
  routing. Re-run the population query below and compare the `chunk` and
  `verify-resolutions` medians; the durations recorded on 2026-07-30 after Chunk 03 shipped are all
  pre-fix reads and must be excluded from the comparison.

  **Baseline recorded 2026-07-30, and RESTATED the same day over the full population.** The first
  cut hand-picked seven recent rows; a review then asked which population they came from, and the
  answer was "no rule" — so the query is now stated and the whole store answers it.

  **Population: every review fact in `<git-common-dir>/prawduct/evidence.jsonl` carrying a
  `duration_seconds` — 267 facts, all scopes, no date or scope filter.** Re-run exactly that after
  Chunk 03; the per-mode medians below are the comparison.

  | mode | n | median | target | over target | r(files changed, seconds) |
  |---|---|---|---|---|---|
  | `chunk` | 30 | 300s | 1–2 min | **30/30 (100%)** | +0.25 |
  | `verify-resolutions` | 155 | 300s | 1–2 min | **148/155 (95%)** | +0.51 |
  | `final` | 33 | 360s | 4–10 min | 5/33 (15%) | +0.37 |
  | `cumulative` | 49 | 900s | 4–10 min | 34/49 (69%) | +0.31 |

  **The two modes Chunk 03 targets miss their target essentially always** — `chunk` in every single
  recorded run, `verify-resolutions` in 95% of 155 — while `final`, which loads the same protocol for
  more than twice the goals, sits *inside* its target 85% of the time. A payload that is roughly
  right for seven goals is roughly 3× too expensive for three.

  **One claim from the first cut is withdrawn.** It read "file count barely predicts it," inferred
  from a 3-file pass at 460s next to an 8-file pass at 330s. Across 155 facts r = **+0.51** — a
  moderate relationship, not a null one, and the ≤5-file runs (n=96, median 240s) really are faster
  than the ≥12-file ones (n=16, median 420s). Two adjacent rows were never evidence for a
  correlation; the full population is, and it says diff size matters.

  **The conclusion survives the correction, on a better statistic — the floor.** Those 96
  smallest verify-resolutions reviews, with five or fewer changed files and often a one-line fix to
  confirm, still take a **median 240s against a 60–120s target**. That floor cannot be diff size,
  because there is barely any diff; it is what the reviewer loads before reading a single changed
  line. Distillation attacks exactly that, which is why Chunk 03 is the lever and run-count (already
  cut by Chunk 02) is not.
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

Closed by this plan's work: **CRT-2W8J** (coordinator roster counts non-judgeable files) — archived
`status: shipped · closed-by: record-mechanization` on 2026-07-30. Chunk 04 **falsified** it: the
82-review replay showed its proposed fix (key the roster to judgeable count) would demote 54% of
historical blocking findings, so the diagnosis was right and the prescription harmful. It is recorded
as closed rather than open precisely so nobody implements it; the item's own archive note carries the
replay evidence and the `is_judgeable_path` coverage-vs-depth conflation to avoid re-introducing. One
residue stays unanswered and is called out there: its secondary ask about `critic_mode._rule_final_fires`'
no-plan `>= 5` heuristic, which this plan did not touch and the roster replay does not answer.
