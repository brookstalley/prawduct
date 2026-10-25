---
artifact: build-plan
version: 2
scope: chunk-status
branch: feature/1051-chunk-status
base: develop
working-branches: []
partition: >-
  01 and 06 serial (coordinator, 01 built by one delegate in an isolated worktree against the
  signature below and reviewed `final` before anyone else is briefed). 02–05 delegated after 01
  commits, isolated worktrees, disjoint ownership — A: plugin/lib/critic_consolidate.py,
  evidence.py, critic_mode.py, coverage.py; B: plugin/bin/prawduct-hook and
  plugin/skills/doctor/SKILL.md; C: plugin/lib/gates.py, briefing.py, pr_payload.py,
  plan_archive.py, plan_backfill.py, record_lint.py, lifecycle_repair.py; D: prose (methodology,
  templates, the other skills, data-model.md, cross-cutting-concerns.md, session-digest.md) and the
  tests that READ those files. The coordinator owns plan_status.py, buildplan_refs.py,
  plan_index.py, the walker pin test and integration.
governed_by:
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
depends_on:
  - documentation/issues/1050-requirements.md
  - documentation/issues/1050-design.md
  - .prawduct/artifacts/build-plan-work-unit-binding.md
last_validated: 2026-10-25
---

## Goals

**Response taken:** Proceed, citing #1051 (`stage: design`, child of #1050) and
`documentation/issues/1050-design.md` § 3, the Wave-2 half of § 7, § 8 and MG2. The owner ruled
D1, D6 and D-ST8 on 2026-10-24 and recorded them in the design; Wave 1 (`work-unit-binding`,
PR #1053) merged to develop on 2026-10-25, which this wave requires. Delegation for the #1050
waves was approved by the owner on 2026-10-24 (handoff), so no approval ask is made here.

**Product:** "Is chunk N done" and "is this plan finished" each have one answer, derived from the
review and resolution facts the Critic already writes, never from a hand-ticked box or a commit.
The Stop gate stays armed until governance of the last chunk is complete and disarms with no
ceremony. A reader still sees progress in the plan, the briefing and the handoff, rendered from
the same answer. Parallel delegation lands several chunks per review and the fact names all of
them. This closes the other half of #1050; #1051 is this wave's item.

**Architecture:** `plan_status.chunk_states / is_finished / current_chunks` is the only walker of
chunk progress; every consumer takes its answer and none re-derives it (`architecture.md`: one
home; the #541 pin extends to it). Verdicts come from the fact ledger (`data-model.md`: no model in
a fact's write path; derived views never feed a gate — `plan status` is a view, `chunk_states` is
a computation). Authority fails closed: an unreadable `dropped:` or an unreadable fact leaves the
chunk `open`, which keeps every gate armed; the sweep's refusal reads `is_finished` and nothing
softer. Additive-first on the CLI and the fact schema: `--chunk` stays as a one-element alias for
one release, the fact keeps `chunk` = first element for old readers, `chunks` and the
`chunk-imported` kind are added, no `--json` key is repurposed (`api-contract.md`).

**Constraints and tradeoffs accepted:**
- *Self-governing build.* This plan is governed by the machinery it replaces until Chunk 06
  lands, so Chunks 01–05 keep ticking `## Status` under the old rule, and 06 runs the MG2 import
  on this very plan as its live verification (gates.md: run the changed detection against this
  repo first — a wrong signal silently disables the gate enforcing this session).
- *Facts written before this wave carry `chunk: null`* (measured 2026-10-25: `--chunk` is
  optional and most reviews omit it). They complete nothing. Live plans are carried by the in-memory
  import of their boxes until migrated (MG1); nothing is reinterpreted.
- *`built` is render-only and off the hot path.* It needs a git walk; `chunk_states` does not
  compute it (NF1: every Stop calls this). Only `plan status` and the built-but-not-done advisory
  ask for it, through a separate function, and no gate reads it (pinned by test).
- *Debt taken knowingly:* the review-fact `chunks` set is declared at dispatch and confirmed by
  the coordinator (D-ST8), so a model-confirmed field sits upstream of `is_finished`, which the
  #634 sweep refusal and the Stop hook's designer-handoff `Type:` exemption read. Mitigation in
  Chunk 02: the manifest and the fact also record `chunks_proposed` (the code-derived set), and
  `critic-begin` warns when the declared set leaves the proposal — the edit is visible on the
  record, never silent. *Inferred, owner can veto:* record both rather than refuse the edit.
- *Debt taken knowingly, revisit at #1052:* facts are per-clone until Wave 3 ships transport. A
  plan whose block MG2 removed in clone X answers "all open" in clone Y, which today's box reading
  did not. **Decision (inferred, owner can veto):** `doctor`'s import writes the facts in every
  repo but removes the block only with `--remove-block`, which the skill offers once #1052 has
  shipped; this repo passes it now to dogfood the full migration. Until then the in-memory import
  keeps answering in every clone, and no release sweep refuses a migrated plan it cannot see facts
  for. Revisit when #1052 merges: flip the default and retire the flag.
- *Scope not taken:* archived plans are untouched (their boxes render as history); git-notes
  transport is #1052; Q3 (fragment-only units binding a branch) stays at its default.

**Decisions made mid-build:** (appended while building)
- Level item (2), read 2026-10-25 before Chunk 01 was briefed: `evidence.py` states that a newer
  minor may add kinds and "an unknown kind can never satisfy a gate, only coexist"; `read_facts`
  keeps an unknown-kind line in the verdict digest and files only `schema > SCHEMA_VERSION` as
  `schema_ahead`; `append_fact` refuses a kind outside `KNOWN_KINDS` at the writer. So
  `chunk-imported` is a `KNOWN_KINDS` append (and an `OBSERVATIONAL_KINDS` member — it spans no
  trees), not a schema bump; an older reader in the `-live` worktree coexists with it. Settled by
  the api-contract norm (additive-first).
- Level item (1), read 2026-10-25: `cmd_test_evidence` holds both writes — the per-worktree
  `.test-evidence.json` and `append_test_run` — and `_check_ephemeral_worktree` runs before
  dispatch, outside the command. DG2 is therefore: admit `test-evidence record` through the guard
  from a scratch tree, and inside the command skip the JSON write and append the fact with
  `narrowed: true` and the ceiling. One guarded branch; no fork of the command. Settled by § 7.
- Chunk 01's open call, settled by the coordinator 2026-10-25: the plan's NF1 wording "no git
  call" conflicted with § 3's reachability rule. Resolution: `chunk_states` makes no git WALK
  (no log/diff/rev-list, never calls `built_chunks`); it runs at most one memoized
  `merge-base --is-ancestor` per fact that would otherwise certify an open chunk, and zero
  subprocesses when no such fact exists — the NF1 test asserts that by call. The anchor is
  `head_commit or dispatch_commit` (a dirty-tree review records `head_commit` null, per
  `critic_consolidate`), so a pre-commit chunk review certifies once its dispatch commit is in the
  branch's history; that the reviewed TREE was committed is carried by the Stop gate's coverage
  verdict, which `chunk_states` does not duplicate. Settled by the Architecture goal (one home per
  fact; coverage owns tree identity).
- Chunk 01 as built (delegate, 2026-10-25), accepted by the coordinator: precedence follows cost —
  `chunk-imported` fact, then a ticked box, then `dropped:`, then review facts for chunks still
  open (so a chunk both ticked and reviewed reads `done, imported`, citing no fact; the probe runs
  only where it can change the answer). `dropped:` is a block sequence of `- <id>: <reason>`;
  the reason is required, and a flow list, a mapping item, a bare dash or an empty reason leaves
  the chunk `open` with the cause in `reason` (fail closed; an unquoted ` #` in a reason is a YAML
  comment — the template legend says so). Fail-closed shapes the literal "no chunks is finished"
  would miss: an unreadable plan returns one open entry keyed `?`; a chunk heading the parser
  rejects is an open chunk keyed `?L<line>`; a plan declaring no `branch:` is certified by imports
  and `dropped:` only, never by review facts (no history to anchor to). Additive signature
  surfaces for 02–05: `fact_chunks(body)` (the one home of the `chunks`/`chunk` reader rule),
  `deliverable_paths(content, chunk_id)`, `propose_chunks(..., *, repo_dir=None)`, constants
  `UNREADABLE_PLAN`, `DROPPED_KEY`, `IMPORTED_KIND`; `ChunkState.reason` is set on `open` too. A
  Deliverables directory token matches files beneath it only at two or more path segments (a bare
  `.prawduct/` in prose had claimed every governance write as Chunk 03's). Box import applies to
  any plan path passed in, so an archived plan renders its boxes as history. `KNOWN_KINDS` is
  untouched here (Chunk 02 adds the kind; 01's fixtures write store lines directly). Red was shown
  by a 28-mutant sweep with one intended survivor, return codes asserted.
- Chunk 01 verified live, 2026-10-25 (delegate's worktree at b12e072d, re-run by the coordinator
  at c29024a9 with identical output): `python3 plugin/bin/prawduct-hook plan status
  .prawduct/artifacts/build-plan-chunk-status.md` → exit 0, `6 of 6 open`, rows 01–06 all
  `open`, `imported` on none, `built` on 06 alone (the plan commit created 06's deliverable, the
  fragment stub — the rule working as stated). Acceptance met. Chunk 01's `final` review
  `rev-20261025T125704Z-02fa9efd`: 0 blocking, 0 warning, 3 record notes, 17 observations —
  ten fixed on the delegate's branch (O-1/O-11 silent `dropped:` rejection, O-7 sentinel keys
  reaching `current_chunks`, O-2, O-3, O-4, O-8, O-10, O-15, O-16), three answered by this record
  (O-5/O-14 this line, O-12 the signature block above), four accepted with reasons on the record.
- Chunk 02's open call, settled by the coordinator 2026-10-25 (delegate A): the #167 extension
  deferral's trigger was "the reviewed chunk is still the first UNTICKED one" — under fact-derived
  status a clean review certifies the chunk at once, so that trigger is dead on every plan that
  declares `branch:`. Settled for the observable form over the stored one (hook-surface.md): the
  deferral fires when every chunk the review chain names was certified by a fact ON the chain (not
  an import or box) AND the pending, uncovered work touches no open chunk's Deliverables
  (`propose_chunks` in `chunk` mode over the uncovered paths is empty). Fail-open named: a chunk
  declaring no path-shaped Deliverables lets new-chunk work read as a fix — the cost is a wider
  interval at the next review, never lost coverage (the later review starts at the frontier).
  Rejected: the literal port (kills #167 on bound plans, one verify-resolutions round per mid-plan
  warning fix — against review-run count, the owner's P0). `later_review_owed` on the extension
  path becomes ">=1 open after the reviewed set"; `_mid_plan_start` keeps ">=2 open".
- Chunk 03's seam, found by delegate B before integration and closed in Chunk 04 (delegate C):
  `gates._store_run_vouching` treats every `test-run` fact with a tree as a candidate, so a DG2
  narrowed fact whose tree matched after the coordinator's merge would have vouched a 3-file run
  for the whole suite (fail open). A narrowed fact is attribution only — skipped in that loop,
  neither vouching nor denying; a refusal would have made the newest narrowed fact deny, the wrong
  direction. Red-first test with the un-narrowed control.
- Chunk 04 as built (delegate C, 2026-10-25, merged aadcb174), four behaviour changes accepted by
  the coordinator: (1) a finished bound plan stays visible as active work with `Resume: finished`
  instead of falling back to project-state WIP — ST5 implies it; it reverses SCN-4H9T, and the
  test was renamed and inverted in the open; (2) a plan with no chunks is finished everywhere
  (design § 3): the sweep archives it with no unbuilt stamp and the missing-branch warning stays
  silent; a heading the parser rejects is refused and stamped; (3) `staleness_scan`'s check 5
  ("project-state.yaml has a completed build plan") is retired — it read `chunks[].status` (ST7);
  (4) lifecycle-repair names built-but-not-done chunks as `Chunk <id>`; an open chunk with
  nothing built is no longer reported. `unbuilt_at_archive(plan_path, *, repo_dir, facts=None)`
  replaces the content-taking form (one hook line in `cmd_archive_plan` followed). Carried to
  Chunk 06: the chunk-table renderer exists twice (`briefing.chunk_table_lines` and the hook's
  `_cmd_plan_status`) — move it into `plan_status` as the one home and call it from both;
  `_count_build_plan_chunks`'s docstring lists three callers (the function dies in 06). Red shown
  by swapping each owned module back to its pre-chunk version: 29 tests red, return codes read.
- Chunk 05 as built (delegate D, 2026-10-25, merged 58b90eaf). NF3 measured, cited from the
  budget tests: `session-digest.md` 1911→1883 tokens (9494→9423 chars; wall 10,000);
  `templates/build-plan.md` 2605→2394 tokens; injected footprint framework 3108→3080, product
  2226→2198; ceilings lowered with the trims (building 5316→5294, critic SKILL 3113→3096,
  review-cycle 7702→7699, cross-checks 3391→3387, footprint 3109/2227→3081/2199). One declared
  increase: `planning.md` +75 tokens, now the rule's only home and a read-on-demand file. The
  `test_a_status_tick_has_one_pinned_meaning` pin became
  `test_chunk_state_has_one_home_and_the_others_point_at_it` (five mutants red, one intended
  survivor). Calls accepted: the template keeps its cadence paragraph minus the tick clause; the
  commit-subject guidance went with the `## Status` block; `data-model.md` gained two small
  amendments beyond the brief, both witnessed by D1 (the derived-views ruling no longer calls the
  block hand-authored state; "can never satisfy 'all boxes ticked'" → "whose work stopped can
  never be finished"), with the 2026-08-11 ruling kept verbatim and tagged "Carrier amended
  2026-10-24, below". Four stale `doctor/SKILL.md` lines outside D's grant (~37, ~72, ~101, ~105)
  routed to B. The C/D phrase seam (`inferred as the plan's first open chunk`) closed at merge:
  the two-surface test passes on the integrated tree. D's ten forward-true sentences are the
  checklist Chunk 06 verifies at integration before the cumulative.
- Chunk 03 as built (delegate B, 2026-10-25, merged fd4ce72d), accepted: the hook passes
  `chunks=[ids in order, de-duplicated]` to `begin_review` when `--chunks`/`--chunk` is given (they
  mix and repeat) and omits the keyword otherwise — never `None`/`[]`, never `chunk=`.
  `import-status` picks what to write from `chunk_states` (done, imported, no fact yet), so it
  holds no box-reading code; it writes every fact first and removes the block only after all
  succeed, and every block refusal precedes any write. Refusal codes recorded in api-contract.md
  at Chunk 06: `import-status` 1 `refused: archived-plan | no-scope | store-unreadable |
  status-block-ambiguous | status-block-undelimited | status-block-trailing-comment |
  fact-append-failed | plan-write-failed`, 2 usage/not-a-plan; `check-claims` 0/1/3 (git cannot
  list branches)/2; `critic-begin` 1 on an empty chunk id; `test-evidence record` from a scratch
  tree refuses `--no-rerun` and `--from-counts` with 2 (neither records a fact). `test-status`
  prints the verdict first, then one line per scratch worktree's newest narrowed run (≤10), exit
  unchanged. Two intended mutation survivors named: `dg2-degraded` (no test drives a degraded
  narrowed run) and the write-side `newline=""` (inert on POSIX; read side killed). Carried to
  06: `check-claims` reads the private `work_unit._live_declarations` — give it a public name;
  the check's first live run found both retained plans (`work-unit-binding`, `build-plan.md`)
  claiming deleted branches, which is D-BR5's retention working, so B adds a third outcome
  `release-pending` (branch gone AND the scope's fragment pending → not a miss, exit 0) before
  integration. Done 2026-10-25 (merged 5fff485b): the pending set comes from
  `release_readiness.pending_scopes`; JSON claims gain `outcome: exists|release-pending|missing`;
  a fragment that fails validation stays a miss with a stderr note. Live: both retained plans
  print the release-pending line, exit 0.
- Chunk 02 as built (delegate A, 2026-10-25, merged 515e4d48), accepted: `begin_review(...,
  chunks: list[str] | None = None)` appended last; declared ids normalised to the plan's spelling
  and kept in plan order; an undeclared id refuses before the tree capture as `unknown-chunk`
  (hook exit 1; recorded in api-contract.md at 06); a declared id outside the proposal records
  with a `WARNING:` note; no plan → `chunks == chunks_proposed == []`, `chunk` None;
  `validate_manifest` requires `chunk == chunks[0]` and a pre-`chunks` manifest still yields a
  fact with the bare `chunk`. `binding_progress` returns `PlanProgress` from one `chunk_states`
  walk, keeping `total`/`complete`; "final" = exactly one real open chunk and nothing synthetic
  open. Beyond the brief, accepted: legacy (no-`branch:`) plans keep the old #167 trigger, since
  facts can never certify there; the reviewed set is the NEWEST chunk-naming fact on the chain,
  not the chain's union (an earlier, since-ticked chunk would otherwise kill the deferral);
  `boundary_cumulative_still_owed` computed directly. The #167 fail-open was demonstrated by test:
  a chunk with no path-shaped Deliverables defers, and the next review's interval starts at the
  reviewed commit and covers both the fix and the new file — wider interval, nothing uncovered.
  An older installed reader (3.7.2-dev.4 `evidence.py`) read a store holding a `chunk-imported`
  fact with `status: ok`, `schema_ahead: []` — Level item (2) verified live. Three gaps found by
  A, sent back as one round: box-free short plans never infer the boundary `cumulative` (settled:
  the short-plan last-chunk rule may read `built_chunks`, the one place inference may, bounded to
  plans within `SHORT_PLAN_MAX_CHUNKS`, because § 3 names `built` as exactly that state and mode
  choice is not a gate verdict; `short_plan_next_step` says "commit", never "tick");
  `verify-resolutions` naming a chunk always warned (settled: that mode's proposal is the anchored
  review's recorded `chunks`); Stop read the store up to twice more (settled: one `read_facts`
  per `infer_mode`, threaded).

**Level:** High for § 3's reader and the Stop/inference callers (every site is enumerated below
from a 2026-10-25 inventory, with its callers). Medium for two things, each raised by one read
before the delegate is briefed: (1) DG2 — how `evidence.append_test_run` and the per-worktree
`.test-evidence.json` writer split today, so "shared store only" is one guarded branch and not a
fork of `cmd_test_evidence` (read `_check_ephemeral_worktree` and `cmd_test_evidence`'s write
sites before briefing B); (2) whether a `chunk-imported` fact, a new kind, is a "newer schema"
to an older reader (`evidence.KNOWN_KINDS` and the forward-incompatibility block at
`data-model.md` § Direction) — this repo runs the `-live` plugin beside the repo-local binary, so
an older reader meets the new kind here first (read `evidence.read_facts`'s unknown-kind path
before Chunk 02 is briefed; if it blocks, the kind is added in a schema bump, not a list append).

### Norm reconciliation (`governed_by`)

- `data-model.md` "verdicts computed from the fact ledger, no model in a fact's write path" —
  **conforms**; the fact's verdict content is code-written; `chunks` is a declaration like
  `--chunk` today, now with its code-derived proposal recorded beside it (above).
- `data-model.md` "derived views never feed a gate" — **conforms**; `plan status` renders,
  `chunk_states` computes, `built` reaches no gate (pinned).
- `data-model.md` Ruling "the `## Status` block is hand-authored state" (DV3) — **amendment,
  owner-ruled D1 2026-10-24, recorded in Chunk 05**: the governance event's fact is the carrier;
  DV3's why (a commit ends coding, not governance) is preserved verbatim; the block becomes a
  rendered view and leaves the template.
- `data-model.md` #634 ruling "checkbox state IS a precondition of the mechanical sweep" —
  **amendment of the carrier, not the substance**: the precondition becomes `is_finished`; an
  explicit `archive-plan <path>` still has no such precondition. Recorded with D1 in Chunk 05.
- `data-model.md` "newer schema → loud block, never dropped" — **conforms once Level item (2) is
  read**; the answer decides whether `chunk-imported` is a kind or a schema bump.
- `data-model.md` "two stores, two lifetimes" — **conforms**; `chunk-imported` facts are shared
  committed answers; nothing new is per-clone except what already is.
- `architecture.md` "authority fails closed; advice fails soft" — **conforms**; unreadable
  `dropped:`/fact → `open` (armed); rendering degrades to a named cause.
- `architecture.md` "every fact has one home" — **conforms**; `plan_status` is the home; § 8's
  deletions are the proof, counted in Chunk 06.
- `architecture.md` "an independent reviewer never mutates the session it reviews" —
  **conforms**; the Critic writes facts, never the plan.
- `api-contract.md` additive-first; exit codes are the contract — **conforms**; new subcommand
  `plan status`, new flags `--chunks`, `--remove-block`, new keys; `critic-begin` refuses an
  unknown chunk id with a documented code; nothing repurposed.

## Status

<!-- Governed by the OLD rule until Chunk 06: tick when the chunk is built, committed and reviewed
     on the branch. 06's import converts these boxes to `chunk-imported` facts and removes this
     block — that conversion is the chunk's live verification. -->

- [x] Chunk 01: `plan_status` — the one walker, and `plan status` renders it
- [ ] Chunk 02: review facts name their chunks (ST8); inference reads `current_chunks`
- [ ] Chunk 03: hook — gate arms on binding (ST2/ST7), doctor import (MG2), BR3 check, DG2 admission
- [ ] Chunk 04: lib readers take `plan_status`; the `repo_rel` fix
- [ ] Chunk 05: one home for the rule — prose, template, digest, DV3 amendment
- [ ] Chunk 06: integration — delete the walkers, extend the pin, migrate this plan, measure NF3, cumulative review

## Build Chunks

Fact shape every chunk reads or writes (fixed here so no delegate guesses it; Chunk 01 reads it,
Chunk 02 writes it):

- `review` fact body gains `chunks: list[str]` (plan order, may be empty) and
  `chunks_proposed: list[str]`; `chunk` stays and equals `chunks[0]` or `null`. A reader takes
  `chunks` when present, else `[chunk]` when `chunk` is non-null, else `[]`.
- New kind `chunk-imported`: body `{scope, chunk, source: "status-box", imported_at}`.
  Observational for coverage (it spans no trees); `chunk_states` counts it as `done`, tagged
  `imported`.
- `plan_status` signature (final — Chunk 01 reviewed 2026-10-25; this block is what 02–05 are
  briefed from, and a field added later re-briefs four delegates):
  `chunk_states(plan_path, facts, *, repo_dir) -> dict[str, ChunkState]` where `ChunkState` has
  `state` (`open|done|dropped`), `fact_id`, `date`, `imported: bool`, `reason` (the `dropped:`
  reason, or on an `open` chunk why something that looked like an answer was not one — an
  unreadable `dropped:` entry, a fact whose anchor is not in the branch's history);
  `is_finished(...) -> bool`; `current_chunks(...) -> list[str]` (open chunks in plan order —
  never the `?`/`?L<n>` sentinel keys an unreadable plan or heading produces, which surface only
  through `chunk_states`); `built_chunks(plan_path, repo_dir) -> set[str]` (render-only,
  git-walking, separate); `propose_chunks(plan_path, facts, diff_paths, mode, *, repo_dir=None)
  -> list[str]`; `fact_chunks(body) -> list[str]` (the one home of the reader rule above — Chunk
  02 reuses it, never re-derives it); `deliverable_paths(content, chunk_id)`; constants
  `UNREADABLE_PLAN`, `DROPPED_KEY`, `IMPORTED_KIND`. `chunk_states` walks no git history and
  never calls `built_chunks`; its only subprocess is a memoized `merge-base --is-ancestor`, run
  only for a fact that would otherwise certify an open chunk.

### Chunk 01: `plan_status` — the one walker, and `plan status` renders it

- **Description:** New module `plugin/lib/plan_status.py` exactly as `1050-design.md` § 3 states,
  with the in-memory import of a live plan's `## Status` boxes (same code path as MG2's facts,
  nothing written) and `dropped:` frontmatter. A thin `prawduct-hook plan status [<path>] [--json]`
  renders the chunk table (id, state, certifying fact id, date, `imported`/`built` tags) so the
  walker is exercised end to end before any caller moves. `built` comes from `_committed_chunk_ids`'
  rule (subject names `Chunk <id>`) or a diff touching the chunk's Deliverables paths, computed
  only by `built_chunks`.
- **Depends on:** none
- **Artifacts consumed:** `1050-design.md` § 3; `plugin/lib/plan_index.py`
  (`iter_status_section_items`, chunk id walkers — read-only here); `plugin/lib/evidence.py`
  (`read_facts`, `facts_of_kind`); `plugin/lib/dispositions.py` (`census`, which owns "every
  blocking finding has a passing resolution"); `plugin/lib/work_unit.py` (`resolve`, `repo_rel`);
  `plugin/lib/critic_mode.py` `extension_deferral_owed` (the precedent that reads a fact's chunk).
- **Deliverables:** new `plugin/lib/plan_status.py`; `plan status` in `plugin/bin/prawduct-hook`
  (`_cmd_plan_status`, `_PLAN_HELP`, the read-only ops table so it runs in a scratch worktree);
  new `tests/test_plan_status.py` covering, red first: a review fact `chunks: [01, 03]` with zero
  blocking completes 01 and 03 and leaves 02 `open`; a fact with an unresolved blocking finding
  completes nothing, and a `resolution` fact with a passing disposition then completes it; a
  fact whose `head_commit` is not reachable from the integration or a declared working branch
  completes nothing; a short plan's one boundary fact naming every chunk finishes the plan; a
  `dropped:` chunk with a reason finishes a plan and an undeclared unbuilt one does not; a plan with
  no chunks is finished; a ticked box in a live plan with a `## Status` block reads as `done,
  imported` with no fact written (assert the store is byte-identical after); an unreadable
  `dropped:` entry leaves the chunk `open`; `built_chunks` is not called by `chunk_states` (spy);
  `plan status --json` key set, and the human table on a fixture plan.
- **Tests:** the module above, plus `tests/test_plan_hook_cmd.py` gains the `plan status` cases.
- **Acceptance criteria:** every listed shape has a red-first test; `chunk_states` makes no git
  walk and no network call, and no subprocess at all when no fact would certify an open chunk
  (NF1; assert by spy, by call, not by timing); `is_finished` is the only
  function answering "finished" in the module; `plan status` on this repo's own live plan prints
  six `open` rows with `imported` on none.
- **Critic mode:** final
  <!-- Keystone: four delegates build on this signature. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status — then 02–05 are briefed with the signature above

### Chunk 02: review facts name their chunks (ST8); inference reads `current_chunks`

- **Description:** `critic_consolidate.begin_review` takes `chunks` (list); the manifest carries
  `chunks` and `chunks_proposed` (`validate_manifest` allows both); `build_fact_body` writes
  `chunks`, `chunks_proposed` and `chunk = chunks[0] or None`. `propose_chunks` (in
  `plan_status`, Chunk 01's signature; this chunk implements its callers) gives: for `chunk`
  mode, the open chunks whose Deliverables paths intersect the dispatch diff; for
  `final`/`cumulative`, every open chunk. `begin_review` warns (stderr prefix vocabulary) when the
  declared set is not a subset of the proposal and refuses (documented exit code) an id the plan
  does not declare. `evidence.KNOWN_KINDS` gains `chunk-imported` (or the schema bump Level item
  (2) decides). `critic_mode.infer_mode` and its helpers (`binding_progress`,
  `short_plan_deferral`, `_rule_final_fires`, `later_review_owed`, `_critic_mode_for_chunk`,
  `_unticked_labels`, `declares_boundary_cumulative`, `_declared_chunk_modes`) read
  `plan_status.current_chunks` / `chunk_states` instead of box counts; `extension_deferral_owed`
  compares against `chunks`; `coverage._extension_reason` follows. The short-plan rule keeps its
  constant and its meaning: "last chunk" = exactly one chunk not done or dropped.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 3 "ST8"; `plugin/lib/critic_consolidate.py`
  (`begin_review`, `validate_manifest`, `build_fact_body`, `_plan_owes_a_later_review`);
  `plugin/lib/critic_mode.py`; `plugin/lib/evidence.py`; `plugin/lib/coverage.py`.
- **Deliverables:** the changes above; `tests/test_critic_consolidate.py` and
  `tests/test_critic_mode_inference.py` renegotiated in the open (tests.md: rename to the new
  contract, never silently relax) — a fact names `chunks: [01, 03]` and `chunk: "01"`; a declared
  id outside the proposal warns and still records; an undeclared id refuses; #208's shape still
  answers `none`; a plan with two chunks not done infers `chunk`, with one infers `final` (or the
  short plan's `cumulative`); `TestBranchProgressCRT7B4M` ported to `chunk_states`.
- **Tests:** as above; `tests/test_evidence*.py` gains the new kind's read/append case.
- **Acceptance criteria:** no function in the owned files reads a `[x]`/`[ ]` box or imports a
  `buildplan_refs` progress reader (grep is the check); the `-live` plugin's reader on this repo
  does not block on a `chunk-imported` fact (Level item (2), verified live).
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass (the delegate's ceiling)
  2. Handed back; the coordinator merges, reviews with 03–05 (cadence below)
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: hook — gate arms on binding (ST2/ST7), doctor import (MG2), BR3 check, DG2 admission

- **Description:** In `plugin/bin/prawduct-hook`: `cmd_stop`'s `has_build_plan` becomes
  "binding is `bound` (or `broken`) and the plan is live" — `_has_build_plan_in_state` and the
  unticked count are no longer consulted (deleted in Chunk 04/06), the `project-state.yaml`
  `chunks[].status` arm goes (ST7), and `briefing._check_previous_session_gates`' copy of the
  arming logic is reconciled by C in Chunk 04 against the same predicate (name it in B's brief).
  The designer-handoff `Type:` exemption and `cmd_verify_chunk_refs` take `current_chunks()` (an
  empty list grades no chunk, as today's unbound case does). `critic-begin --chunks a,b`
  (repeatable; `--chunk` kept as a one-element alias, documented one release) and the re-dispatch
  pass-through. New `plan import-status <path> [--apply] [--remove-block]`: for each ticked box
  appends one `chunk-imported` fact, code-written from the box; `--remove-block` deletes the
  `## Status` block (the writer must delimit the block it deletes — hook-surface.md: a reporting
  scanner reused in an editor inverts its safety); without `--apply` it previews. New
  `plan check-claims`: every live plan declaring `branch:` or `working-branches:` names a branch
  that exists locally or on a remote; reports each miss distinctly (BR3). DG2: the ephemeral guard
  admits `test-evidence record` from a scratch worktree into the shared store only — the
  `test-run` fact is appended with `narrowed: true` and the delegate's ceiling, the per-worktree
  JSON is not written; `test-status` lists delegate runs by tree. `doctor/SKILL.md` gains checks
  #23 (import-status offer, with the cross-clone caveat stated until #1052) and #24
  (check-claims), each with its `allowed-tools` grant.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 3 "The gate", "Migration", § 7 second bullet;
  `plugin/bin/prawduct-hook` (`cmd_stop`, `cmd_critic_begin`, `cmd_verify_chunk_refs`,
  `cmd_test_evidence`, `_check_ephemeral_worktree`, `_ephemeral_command_writes`, the read-only ops
  table, `cmd_plan`); `plugin/skills/doctor/SKILL.md`; `plugin/lib/plan_index.py`
  (`branch_claiming_plans`, `status_section_bounds`); `plugin/lib/gitstate.py`.
- **Deliverables:** the changes above; `tests/test_session_critic_gate.py`,
  `tests/test_critic_gate_fallthrough.py`, `tests/test_short_plan_deferral.py::TestStopGateOnShortPlans`
  renegotiated: the gate arms on a bound branch with every box unticked AND with every box ticked
  (the tick no longer disarms), does not arm on an unbound branch, arms on `broken`; a repo whose
  `project-state.yaml` lists unfinished chunks and whose branch is unbound arms nothing (ST7
  red-first); new `tests/test_plan_import_status.py` (preview writes nothing; `--apply` writes N
  facts for N ticked boxes and leaves the block; `--remove-block` removes exactly the block and
  nothing else — CRLF and header-comment cases); new `tests/test_plan_check_claims.py`; the DG2
  cases in the ephemeral-guard tests (scratch tree: fact appended with `narrowed`, JSON absent;
  any other `.prawduct/` write still refused).
- **Tests:** as above.
- **Acceptance criteria:** `grep -n '\[x\]\|\[ \]\|chunks\[\]\.status\|_has_build_plan_in_state\|_count_build_plan_chunks' plugin/bin/prawduct-hook` returns only the import-status writer; on this
  branch, `prawduct-hook stop` (dry) arms the Critic gate with this plan's boxes in any state; in a
  scratch worktree forked from this branch it arms nothing and `test-evidence record` appends one
  narrowed fact.
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass
  2. Handed back; merged and reviewed with 02, 04, 05
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: lib readers take `plan_status`; the `repo_rel` fix

- **Description:** Every reader outside A's and the coordinator's files takes `plan_status`'
  answer: `gates._has_active_build_plan_file` (arming; becomes a thin "plan is live" predicate or
  goes), `gates._critic_session_satisfies_gate` (the nudge becomes "every chunk done or dropped and
  the latest fact is not final/cumulative"), `briefing.staleness_scan` (the branch-claim warning
  filter, "all chunks complete" lines), `briefing._get_active_work` / `_get_work_in_progress`
  (`Resume:` line from `current_chunks`), `briefing.render_session_handoff` (`**Current chunk**`
  from the same), `briefing._check_previous_session_gates` (the arming copy, same predicate as
  Chunk 03's), `pr_payload._section_build_plan` (renders the `plan status` table instead of its
  own scan), `plan_archive.unbuilt_at_archive` (stamped from `chunk_states`),
  `plan_backfill._incompleteness_refusal` (#634 precondition = `not is_finished`),
  `record_lint._check_chunk_refs` (the "first unchecked" fallback becomes `current_chunks`; an
  unbound checkout grades nothing, as Wave 1 settled), `lifecycle_repair.stale_status_reports`
  (built-but-not-done from `chunk_states` + `built_chunks`). Fix `record_lint._plans_to_check`'s
  hand-rolled relative path with `work_unit.repo_rel` (inherited from Wave 1's cumulative).
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 3 "The gate", "Rendering"; the 2026-10-25 inventory
  (readers A.5, A.12, B, E, J, K in the coordinator's notes — each site's callers are named there);
  `plugin/lib/gates.py`, `briefing.py`, `pr_payload.py`, `plan_archive.py`, `plan_backfill.py`,
  `record_lint.py`, `lifecycle_repair.py`.
- **Deliverables:** the changes above; `tests/test_briefing_functions.py`, `tests/test_plan_archive.py`,
  `tests/test_plan_backfill*.py`, `tests/test_record_lint.py`, `tests/test_lifecycle_repair.py`,
  `tests/test_pr_review_payload.py` renegotiated — red-first for: the nudge fires on a finished
  plan whose latest fact is `chunk` and not after a `cumulative`; the sweep refuses an unfinished
  plan and archives a finished one with a `dropped:` chunk; `unbuilt_at_archive` lists open
  chunks; the briefing's `Resume:` names the first open chunk and says `finished` when none; the
  payload section renders from `plan status`; `_plans_to_check` returns a POSIX repo-relative path
  on a symlinked tmp root (the `repo_rel` case).
- **Tests:** as above.
- **Acceptance criteria:** no owned file imports `has_unfinished_chunk`, `build_plan_is_complete`,
  `incompleteness_reason`, `_count_build_plan_chunks`, `resolve_chunk_progress`,
  `committed_chunk_progress`, `_parse_build_plan_status`, `_current_chunk_id_from_status` or
  `unticked_chunk_items` (grep is the check — these die in Chunk 06); no owned file parses a box.
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass
  2. Handed back; merged and reviewed with 02, 03, 05
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: one home for the rule — prose, template, digest, DV3 amendment

- **Description:** The rule is stated once, in `planning.md` ("a chunk is done when a review fact
  names it with no unresolved blocking finding; `prawduct-hook plan status` renders it; a dropped
  chunk is a `dropped:` line with a reason"), and every other surface references it. Delete the
  tick-timing prose the inventory lists (17 files): `planning.md:56,66,156`,
  `building.md:122` (chunk-close step 5 deleted; steps renumbered), `:126`, `:230`;
  `delegation.md:45` (the "ticked a Status box" tell drops) and `:23/:73` take the one sentence
  "a scratch worktree is unbound; it builds, you govern"; `reflection.md:74`;
  `session-digest.md:30-32` (the tick paragraph goes; one sentence names `plan status`);
  `templates/build-plan.md` (the `## Status` block `:82-99`, the three "chunk marked `[x]`"
  Done-when lines, the cadence line `:228`, `unbuilt_at_archive` comment `:58` reworded; add
  `dropped:` to the frontmatter legend); `critic/SKILL.md:42` (`--chunks`, the proposal, the
  confirm-or-edit step), `critic/review-cycle.md:18,27,28,304`, `critic/goals-1-3.md:64`,
  `critic/cross-checks.md:151`; `pr/SKILL.md:80,89,209` (Status ticks and the "LAST box" exception
  leave Step 1d), `pr/review-protocol.md:19,87`; `janitor/themes.md:117`;
  `doctor/SKILL.md:74-76,112` (B owns the new checks; D owns these lines — brief the seam).
  Record D1 in `data-model.md` Rulings (dated, citing the design and requirements; DV3's why kept
  verbatim) and the #634 carrier change; update `cross-cutting-concerns.md:47`. Delete superseded
  sentences; never add beside them (core.md). Budget tests: `LAST_MEASURED_TOKENS` for each edited
  file, the digest headroom test, `INJECTED_FOOTPRINT_CEILINGS` — record before/after (NF3 is
  measured here and cited in Chunk 06).
- **Depends on:** Chunk 01 (the command name and table it documents)
- **Artifacts consumed:** `1050-design.md` § 3 "Rendering", § 7 first bullet, § 8; the inventory's
  file list; `plugin/methodology/*.md`, `plugin/templates/build-plan.md`, `plugin/skills/**`,
  `plugin/methodology/session-digest.md`, `.prawduct/artifacts/data-model.md`,
  `.prawduct/cross-cutting-concerns.md`.
- **Deliverables:** the edits above; the tests that READ the owned files, found by
  `grep -ln <each owned file> tests/` before the first edit (Wave 1's lesson: known today —
  `test_v5_methodology.py` (`:4358` Status-comment pin, `LAST_MEASURED_TOKENS`),
  `test_plugin_methodology_digest.py`, `test_v5_templates.py::TestBuildPlanTemplate`,
  `test_short_plan_deferral.py::TestProseCarriesTheConstant`,
  `preferences/test_critic_skill_structure.py`, `tests/test_pr_reviewer.py`) renegotiated, with
  a new pin that `planning.md` carries the rule and `building.md`, the digest and the template
  reference it without restating.
- **Tests:** as above.
- **Acceptance criteria:** `grep -rn 'tick\|\[x\]\|Status box\|disarm' plugin/methodology plugin/skills plugin/templates plugin/methodology/session-digest.md` returns only the one rule and
  references to it, plus the import-status migration text; digest and template token counts are
  lower than the recorded before-values (NF3) and the tests pin the new values.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass
  2. Handed back; merged and reviewed with 02–04
  3. Committed and chunk marked `[x]` in Status

### Chunk 06: integration — delete the walkers, extend the pin, migrate this plan, measure NF3, cumulative review

- **Description:** Merge 02–05; close any seam (the shared `plan_status` signature and the fact
  shape are fixed, so a seam here is a brief defect — record it). Delete, now unreferenced:
  `buildplan_refs.unticked_chunk_items`, `has_build_plan_shape`'s box dependence,
  `status_chunk_ids`, `incompleteness_reason`, `_count_build_plan_chunks`, `_committed_chunk_ids`
  (moved into `plan_status.built_chunks` in 01 — delete the original here), `resolve_chunk_progress`,
  `committed_chunk_progress`, `_resolve_chunk_progress_from`, `unticked_committed_chunk_notice`
  (its token is replaced by the built-but-not-done notice from Chunk 04), `_parse_build_plan_status`
  and its private scan, `build_plan_is_complete`, `_completed_chunk_ids`,
  `_current_chunk_id_from_status`, the `_iter_status_section_*` re-exports;
  `gates._has_build_plan_in_state`; `plan_index.has_unfinished_chunk`. `plan_index`'s walker
  stays as `plan_status`' and the importer's one input. Extend
  `TestOneCurrentChunkImplementation.test_no_consumer_walks_the_status_section_itself` to the
  real population: every `plugin/lib/**/*.py` and the hook, excluding `plan_status.py`,
  `plan_index.py` and the import-status writer, has no box regex and no `iter_status_section_*`
  call — and the test asserts the scanned set is non-empty and names the three exclusions.
  Retire the `TestCountChunksCallerEnumeration` pin with its subject. Run the suite through
  `test-evidence record`. Then the dogfood: `plan import-status
  .prawduct/artifacts/build-plan-chunk-status.md --apply --remove-block` on this branch, confirm
  `plan status` shows 01–05 `done imported` and 06 `open`, confirm `prawduct-hook stop` (dry)
  still arms, commit. Measure NF3: digest and template token counts before (develop) and after,
  cited from the tests. Then the `cumulative`.
- **Depends on:** Chunks 02, 03, 04, 05
- **Artifacts consumed:** everything above; `tests/test_handoff_parser_correctness.py`,
  `tests/test_buildplan_walkers.py`, `tests/preferences/test_build_plan_decoding.py`.
- **Deliverables:** the deletions, the pin, this plan migrated, `.prawduct/changes/chunk-status.md`
  written (narrative, consumer note naming: `--chunks`, `chunk`'s one-release alias, the
  `chunk-imported` kind, `plan status`, `plan import-status` and its `--remove-block` caveat,
  `plan check-claims`, the ST7 arm's removal, the DG2 admission, the retired `unticked-committed-chunk`
  token; `closes: [brookstalley/prawduct#1051, brookstalley/prawduct#1050]`).
- **Tests:** the suite, green, recorded.
- **Acceptance criteria:** `git grep -n 'has_unfinished_chunk\|build_plan_is_complete\|incompleteness_reason\|_has_build_plan_in_state\|_count_build_plan_chunks\|_parse_build_plan_status\|_current_chunk_id_from_status\|unticked_committed_chunk_notice' plugin/` is empty; the
  extended pin is red when a box regex is planted in `gates.py` (mutate, watch, restore the way
  you mutated); § 8's list is accounted for name by name in the fragment; this plan has no
  `## Status` block and `is_finished` is false until 06's own fact lands.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met, suite green and recorded
  2. Committed; `/prawduct:critic cumulative` run, blocking findings resolved, verify-resolutions
     recorded
  3. `/prawduct:pr create` — one PR to `develop`; #1051 and #1050 close at merge (Issues backend)

## Verification Strategy

Beyond tests, on this repo: after Chunk 01, `prawduct-hook plan status` on this plan prints six
`open` rows; after Chunk 03 and 04 merge, a scratch worktree forked from this branch arms no gate
and `test-evidence record` there appends a `narrowed` fact the coordinator's `test-status` lists;
`prawduct-hook stop` (dry) on this branch arms with every box of this plan ticked, which the old
rule would have disarmed. After Chunk 06, the migration of this plan is the live MG2 run, and
`plan check-claims` on this repo reports the finished `review-stats-dispositions` plan's claim
state. Record each result, dated, in Decisions — the record is the answer the command gave, read
from its output, not the command (hook-surface.md).

## Governance Checkpoints

**Commit & PR cadence:** 01 is built by one delegate in an isolated worktree, merged, reviewed
`final`, committed. 02–05 are briefed together with the signature and fact shape above, each in an
isolated worktree running only its own test modules; the coordinator merges all four, closes seams,
and reviews them in one `chunk` pass naming `--chunks 02,03,04,05` (this wave's own ST8, used as
soon as 02 lands it — the fact names four chunks). 06 commits first, then its `cumulative` is the
PR gate. One PR, to `develop`, via `/prawduct:pr`.

- After Chunk 01: the `plan_status` signature and the fact shape are final before any delegate is
  briefed. Read Level items (1) and (2) before briefing B and A respectively; record the answers.
- Before briefing 02–05: re-check the partition against the machine (four worktrees; each brief
  names its file ownership, its test ceiling found by grep, the signature, and the seam partner
  for shared surfaces — B/C on the arming predicate, B/D on `doctor/SKILL.md`).
- After the four merge, before the `chunk` review: suite green; every seam recorded in Decisions.
- After Chunk 06 (cumulative): the dogfood migration, the NF3 measurement and the scratch-worktree
  gate verified live, not from the tests alone, and recorded dated in Decisions.
