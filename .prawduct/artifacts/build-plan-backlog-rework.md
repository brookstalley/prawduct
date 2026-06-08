<!-- Build Plan — Backlog rework (v0.3). Source of truth for WHAT to build.
     For HOW (governance, Critic, handoff), read /prawduct:building before starting. -->
---
artifact: build-plan
version: 2
# Namespaces this plan's chunk numbering so its shipped `chunks=N` change-log
# entries flip only THIS plan's Status (not a same-numbered chunk in another
# scope). Matches the change-log `scope=backlog-rework` tag.
scope: backlog-rework
depends_on:
  - artifact: backlog-system-requirements   # documentation/backlog-system-requirements.md v0.3
last_validated: null
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem, the five observed failures, and the four root causes are well understood (from `../scriob` usage + the v0.3 spec). What's inferred rather than confirmed: the exact `stage:` vocabulary words, how forcefully `pick` should route an early-stage item (suggest vs. refuse), and the precise chunk boundaries. None block the architecture; each is cheap to adjust early.

**Open assumptions / unknowns:**
- `[ASSUMPTION: stage vocabulary is exactly idea→research→requirements→design→ready (5 words) | MED impact | user can correct — collapsing research∪requirements or adding "arch" is a one-line change to the spec + skill]`
- `[ASSUMPTION: pick ROUTES (suggests discovery) for early-stage items but does not REFUSE to let a user override and build anyway | MED impact | user can override — refusing would be a harder gate, contrary to D13 route-not-gate]`
- `[ASSUMPTION: accepted-by actor identity is a free-form @handle the caller supplies; the framework does not validate or enumerate actors | LOW impact | user can correct]`
- `[ASSUMPTION: the C-B1–C-B4 Critic checks + R-1/R-2 PR checks are protocol PROSE (the review agent reads diff+backlog and reasons), not new executable code | MED impact | user can correct — if they want deterministic code checks instead, that enlarges Chunk 05]`
- `[ASSUMPTION: 10 chunks is the right granularity; chunks 5/9 are the cascade-heavy ones | LOW impact | user can request a re-split before build starts]`

**What would raise confidence:** One pass from the user over the chunk list + the stage vocabulary (a 5-minute read of this plan's Build Chunks). Chunk 01 (the parser) also de-risks by proving the format→parse→surface path before any capability builds on it.

## Status

- [ ] Chunk 01: Parser substrate (`lib/backlog.py`) + briefing rewire (thin vertical slice)
- [ ] Chunk 02: `accepted-by` claim field  <!-- done 9fc5dd3+: SKILL.md pick/list exclude claimed, update set/clear + auto-clear on ship/drop; template doc. Critic 0-blocking. Doc-only (parser support landed ch.01). -->
<!-- Inference wrinkle to file (Chunk 10): on a feature branch with views_enabled, plan checkboxes never flip (derived), so infer-critic-mode always treats Chunk 01 as current → passing explicit Critic mode per chunk for the rest of the run. -->
- [ ] Chunk 03: `stage` field + requirements-precede-code routing (keystone)  <!-- done: SKILL.md stage field + Stage-aware routing (early→discovery, design→planning, none→not-ready); template; discovery.md + planning.md hooks. Critic final 0-blocking, 2 notes (is_implementable descoped+recorded; refs doc forward-pulled). -->
- [ ] Chunk 04: `refs` field + `/backlog dedup` + triage-method guidance  <!-- done: SKILL.md refs field + dedup subcommand + Triage method section + menu/derived-count note. Skill prose (no lib code — dedup is agent reasoning, not a Python call site; lib dedup-helper descoped like is_implementable). Critic 0-blocking. -->
- [ ] Chunk 05: Review-agent backlog checks — Critic C-B1–C-B4 + PR reviewer R-1/R-2  <!-- done: C-B1–4 in review-cycle.md Backlog Reconciliation (review-protocol.md untouched — at 3112/3120 ceiling); R-1/R-2 under PR Merge Hygiene (not a new goal). Presence-assertion tests added (resolved Critic WARNING). Filed MET-5C2H (holistic context-budget audit, stage=research) per user. Critic final 0-blocking after fix. -->
- [ ] Chunk 06: Advisory probes (external-backlog / legacy-section / overdue-grooming)  <!-- done: new lib/backlog_probes.py (3 probes, pure ProbeFn, derive-on-read counts, in-probe now for grooming since ProbeFn has no clock); registered in cmd_clear composition root (advisory_store stays feature-agnostic); SKILL.md list/pick stamp backlog_last_groomed_at. tests/test_backlog_probes.py (16). Critic final 0-blocking; NOTE2 (double-cite heading) fixed. 1003 tests. -->
- [ ] Chunk 07: Archive discipline + strikeout cleanup + archive-split + janitor Step 2.5  <!-- done: backlog SKILL.md archive discipline (done=archive, never strikethrough) + migrate strikeout-cleanup sweep (4b) + archive-split operation (>200 → backlog-archive.md, skill-performed, janitor-surfaced); janitor Step 2.5 Backlog Health + Step 7 reworded to /prawduct:backlog (D4). DESCOPED: lib archive-split helper (the split is a skill Write, no Python consumer — same rationale as is_implementable/dedup-helper; recorded per Principle 2). Skill prose. Critic final: 0 blocking after recording. -->
- [ ] Chunk 08: `/backlog import` + prawduct-doctor external-file report  <!-- done: SKILL.md import subcommand (structure-infer items, source=user, stage inferred, confirm, record backlog_external_imports) + menu; doctor Health Check #7 (external files → /backlog import, report-only). Probe docstring documents the bare-name substring resolution contract (NOTE 1). Tests descoped (skill prose; probe + fact already tested) — recorded. Critic final: 0 blocking. -->
- [ ] Chunk 09: Workflow wiring (methodology + session-digest + build-plan template)  <!-- done: digest backlog-discipline rule (universal carrier); building.md chunk-close routes to /prawduct:backlog (token-neutral, 4845/4850); reflection.md /backlog add; build-plan template backlog-hygiene Done-when note. planning/discovery already wired in ch.03. Presence tests added (digest + building). Critic final 0-blocking; NOTE1 (comment split) fixed. 1005 tests. -->
- [ ] Chunk 10: Reconciliation + cumulative review (requirements status, change-log, deferred-item reconcile)
Context: **Chunk 01 done** (Critic final: 0 blocking, 1 NOTE — fixed in-chunk: body code-fence truncation). `lib/backlog.py` parser + `lib/briefing.py` rewired to it (count parity verified: old & new both = 41 on live backlog, 91 items parsed losslessly). `tests/test_backlog_parser.py` (23 cases). Spec gained D14 (never persist derived counts). 985 tests pass. Checkboxes stay `[ ]` until release (derived view); one change-log entry with `chunks=1..10` is written at Chunk 10 (ships as ONE PR, like work-model). **Next: Chunk 02 (`accepted-by` claim field).** Stage vocabulary locked = 5-stage (idea→research→requirements→design→ready) for Chunk 03. Branch `feature/backlog-rework` off develop.

## Scaffolding

Repo is already scaffolded (this is the prawduct framework repo). No project init. Test runner: `python -m pytest -q` (config in `pyproject.toml`; `-n auto`, 30s timeout). New test files live in `tests/` (the structural suite enforces canonical test location). Record evidence with `prawduct-hook test-evidence record -- -q` at chunk close.

### Verification Strategy

Per chunk: run the targeted test module, then the full suite at chunk close. Beyond tests, exercise the real surfaces: invoke `/prawduct:backlog` (pick/list/add/update) against this repo's own backlog and confirm the new fields/filters behave; run `prawduct-hook regen-views --check`, the briefing (`prawduct-hook` SessionStart path), and the probes against the live `.prawduct/`. The framework self-hosts, so the flagship product IS the test product.

## Build Chunks

> **Cross-cutting test guardrails.** Chunks touching `methodology/*.md` and `skills/critic/`, `skills/pr/` carry token-budget assertions (`tests/test_*` — e.g. `test_token_budget`, methodology-digest budgets). Per `methodology/planning.md` "enumerate the surfaces," chunks 03/05/09 add prose to budgeted files; each plans its trim in-chunk rather than discovering the budget at close.

### Chunk 01: Parser substrate (`lib/backlog.py`) + briefing rewire

- **Description:** The enabling foundation and the thin vertical slice. A structured backlog parser mirroring `lib/views.py` (the change-log parser), then rewire `lib/briefing.py`'s textual line-count to consume it — proving format→parse→surface end-to-end before any capability builds on it.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-system-requirements.md` (§0.1 parser, §4.1 item shape incl. v0.3 fields)
- **Deliverables:**
  - new `lib/backlog.py` — parse the file into items: `[PFX-XXXX]` ID, the dot-separated metadata bar (all keys incl. v0.3 `accepted-by`/`stage`/`refs`), the three sections (`## Open`/`## Promoted`/`## Archive`), free-form body. Legacy/unstructured items tolerated (no metadata bar → `area:untagged`, etc.). Mirror `lib/views.py`'s pure-function style: parse + small query helpers (`open_items`, `is_claimed`, `items_by_area`), no I/O coupling.
  - `lib/briefing.py` — replace the hand-rolled Open-count scan with `lib/backlog.py`; preserve the exact briefing output line (assert-absent on the old behavior per the renderer-leak learning).
  - new `tests/test_backlog_parser.py` — item parse, metadata-bar parse, section assignment, legacy tolerance, strikethrough handling, the v0.3 fields.
- **Tests:** parser unit tests; briefing-count tests updated to go through the parser (existing `tests/test_briefing_functions.py` count cases must still pass with identical output).
- **Acceptance criteria:** full suite green; `lib/backlog.py` parses this repo's real `.prawduct/backlog.md` (incl. its legacy items) without loss; briefing line byte-identical to before.
- **Critic mode:** final
  <!-- Override forward to final: architectural keystone — every later chunk imports this parser, so its coherence must be reviewed before they build on it (planning.md "override forward to final"). -->
- **Type:** code
- **Done when:** 1. Acceptance criteria met and tests pass · 2. `/prawduct:critic final` run and blocking findings resolved · 3. Committed and chunk marked `[x]`

### Chunk 02: `accepted-by` claim field

- **Description:** The soft, durable (non-expiring) claim. Parser already carries the field (ch.01); this chunk makes the skill honor it and documents it.
- **Depends on:** Chunk 01
- **Artifacts consumed:** spec §0.1 (claim), §3 D10, §4.1 (`accepted-by`)
- **Deliverables:**
  - `skills/backlog/SKILL.md` — `pick`/`list` exclude items with a non-empty `accepted-by:` by default (a `--include-claimed` override surfaces them); `update … accepted-by=@actor` sets it, `accepted-by=` (empty) clears it; `status=shipped|dropped` auto-clears it. State the honest limit (eventually-consistent, not a mutex) in the skill prose.
  - `templates/backlog.md` — document `accepted-by` in the item-shape comment.
  - `lib/backlog.py::is_claimed` consumed by the skill's filter logic; add tests.
- **Tests:** parser `is_claimed`; a skill-contract test if one exists for filter behavior (else covered by parser tests).
- **Acceptance criteria:** claimed items excluded from `pick`/`list` by default; clearing works; status-transition auto-clear documented; suite green.
- **Type:** code
- **Done when:** 1. tests pass · 2. `/prawduct:critic` (chunk inferred) blocking resolved · 3. committed + `[x]`

### Chunk 03: `stage` field + requirements-precede-code routing (KEYSTONE)

- **Description:** The governance keystone (§5a). Adds the `stage:` field and makes `/backlog pick` route early-/unspecified-stage items to discovery/planning instead of defaulting to code — closing the requirements-precede-code hole for backlog work.
- **Depends on:** Chunk 01
- **Surfaces (enumerated — cascade chunk):**
  1. `skills/backlog/SKILL.md` — `pick` surfaces `stage:`; early-stage (`idea`/`research`/`requirements`) → route to `/prawduct:discovery`; `design` → `/prawduct:planning`; **no `stage:` ⇒ treat as not-ready, prompt clarity first**; `ready` → buildable. `update … stage=` advances it.
  2. `templates/backlog.md` — document `stage:` + the vocabulary.
  3. `methodology/planning.md` — a line: an early-`stage:` pick is a discovery/planning task, not a build task.
  4. `methodology/discovery.md` — reconciliation entry-point note: discovery can be entered *from* a backlog item; on completion, update the item's `stage:` + add `refs:`.
  5. `lib/backlog.py` — `stage` accessor (already shipped in Chunk 01). **DESCOPED:** the planned `is_implementable(item)` helper was *not* built — it would be unused code, because `/prawduct:backlog` is LLM-interpreted prose and the readiness/routing decision lives there (reading `item.stage`), not in a Python call site. Recorded per Principle 2 (no silent descope); re-add if a future Python consumer needs it. `refs:` documentation landed in `templates/backlog.md` here (forward-pull, closes the discovery.md `refs` mention) — Chunk 04 should not re-document it in the template.
  6. tests: parser stage cases + any methodology token-budget guardrails (plan the trim).
- **Depends-on note:** the full methodology wiring (building/reflection/digest) is Chunk 09; this chunk lands only the *pick-routing* behavior + the minimal planning/discovery hooks it needs.
- **Tests:** parser `stage`/`is_implementable`; budget guardrails on touched methodology files.
- **Acceptance criteria:** `pick` demonstrably routes a stageless / `idea` item to discovery rather than presenting it as buildable; a `ready` item is unaffected; suite green incl. budgets.
- **Critic mode:** final
  <!-- Override forward to final: this is the requirements-precede-code keystone; coherence across the skill + methodology surfaces matters before later chunks lean on stage. -->
- **Type:** code
- **Done when:** 1. tests pass · 2. `/prawduct:critic final` blocking resolved · 3. committed + `[x]`

### Chunk 04: `refs` field + `/backlog dedup` + triage-method guidance

- **Description:** Doc-linking + the dedup sweep + a codified triage method (root cause D, §0.2). Promotes BKL-3R8P (dedup).
- **Depends on:** Chunk 01
- **Deliverables:**
  - `skills/backlog/SKILL.md` — `refs:` field handling; new `dedup` subcommand (group by area, surface title/body-overlap candidates, propose merges, never destructive); a **Triage method** section codifying the GREAT rules (converge duplicates, link `related:`/`refs:`, staleness review, stage backfill).
  - `templates/backlog.md` — document `refs:`.
  - `lib/backlog.py` — dedup-candidate helper (area + keyword overlap); tests.
- **Tests:** dedup-candidate helper; refs parse.
- **Acceptance criteria:** `dedup` surfaces real overlaps on this repo's backlog; `refs:` parsed; triage section present; suite green.
- **Type:** code
- **Done when:** standard 3 steps.

### Chunk 05: Review-agent backlog checks — Critic C-B1–C-B4 + PR reviewer R-1/R-2

- **Description:** Stale-completion detection at the review boundaries (§7, §7a), respecting D4 (flag, never infer/auto-update). Promotes CRT-3K9P; adds the new PR-reviewer reconciliation.
- **Depends on:** Chunk 01
- **Surfaces (enumerated — cascade chunk):**
  1. `skills/critic/review-protocol.md` + `skills/critic/review-cycle.md` — C-B1 (missing metadata), C-B2 (no-dedup-evidence), C-B3 (missing hygiene step at chunk close), C-B4 (dangling ID ref); all NOTE-level (D1).
  2. `skills/pr/review-protocol.md` — R-1 (resolution-candidate NOTE), R-2 (closes/closed-by-disagreement WARNING).
  3. tests: token-budget guardrails on the critic + pr protocol files (plan the trim — these files are near-ceiling); plus assert-present on the new check text.
- **Tests:** protocol budget tests; presence assertions for C-B1–4 / R-1–2.
- **Acceptance criteria:** the four Critic checks + two PR checks are specified in the protocols; budgets pass after planned trim; suite green.
- **Type:** doc-only
  <!-- Protocol prose, no executable code — but it edits skills/, so NOT trivial. Critic still reviews prose coverage. -->
- **Done when:** standard 3 steps.

### Chunk 06: Advisory probes (external-backlog / legacy-section / overdue-grooming)

- **Description:** The three remaining §8.2 probes, registered against the advisory infra via `lib/advisory_store.register_probe`, consuming `lib/backlog.py`. Promotes BKL-2F7K.
- **Depends on:** Chunk 01
- **Deliverables:**
  - new `lib/backlog_probes.py` (or a probes section in `lib/backlog.py`) — `external-backlog-detected` (root/`.github/` TODO/BACKLOG/ROADMAP/IDEAS), `legacy-section-schema` (old `## Active`/`## Queue` headings), `backlog-overdue-grooming` (>20 open items AND no groom in >90d).
  - `bin/prawduct-hook` — register the probes where the roster runs (the `cmd_clear`→`run_sync_advisories` path, per the advisory-rehome learning).
  - `skills/backlog/SKILL.md` — `list`/`pick` write `backlog_last_groomed_at` to project-state (the grooming-probe resolution fact).
  - tests for each probe's trigger + resolution.
- **Tests:** probe trigger/resolution unit tests; project-state fact write.
- **Acceptance criteria:** probes fire on synthetic fixtures and resolve on the recorded fact; suite green.
- **Type:** code
- **Done when:** standard 3 steps.

### Chunk 07: Archive discipline + strikeout cleanup + archive-split + janitor Step 2.5

- **Description:** §5b archive discipline + the Q2 archive-split + janitor triage. Promotes JNT-7T1W. Resolves observed failure #3 (token growth from strikethrough).
- **Depends on:** Chunk 01, 04 (triage method)
- **Deliverables:**
  - `skills/backlog/SKILL.md` — `migrate` gains a strikeout-cleanup sweep (convert struck/done items in `## Open` → `status=shipped` archived, bodies preserved); archive-split to `backlog-archive.md` past threshold (`find` spans both files — already noted in SKILL.md).
  - `skills/janitor/SKILL.md` — formalize Step 2.5 Backlog Triage (group-by-area, dedup candidates, stale flag, neglected-hygiene surface, unstructured count) emitting a `Backlog Health` block.
  - `lib/backlog.py` — archive-split helper; tests.
- **Tests:** cleanup sweep idempotence + non-destructiveness; split threshold; janitor triage findings shape.
- **Acceptance criteria:** strikethrough items convert cleanly; split works and `find` spans both; janitor produces a Backlog Health block; suite green.
- **Type:** code
- **Done when:** standard 3 steps.

### Chunk 08: `/backlog import` + prawduct-doctor external-file report

- **Description:** Onboarding existing projects with an external backlog (§8.3/§8.4). Promotes BKL-5H9M + BKL-1V8J.
- **Depends on:** Chunk 01, 06 (external-backlog probe resolution fact)
- **Deliverables:**
  - `skills/backlog/SKILL.md` — `import <path>` (heuristic bullet→item, `source:user`, inferred area, always confirm; writes `backlog_external_imports`).
  - `skills/doctor/SKILL.md` — setup-time report of external `TODO.md`/`BACKLOG.md` candidates (report-only, no auto-import).
  - tests.
- **Tests:** import heuristic on a fixture; doctor report detection.
- **Acceptance criteria:** import converts a sample TODO.md with confirmation; doctor lists candidates; external-backlog probe resolves after import; suite green.
- **Type:** code
- **Done when:** standard 3 steps.

### Chunk 09: Workflow wiring (methodology + session-digest + build-plan template)

- **Description:** Root cause A, cross-cutting. Route agents to the skill rather than hand-editing; make the backlog-hygiene step (BKL-6L3Q) a documented standard. Route + flag, not gate (D13).
- **Depends on:** Chunks 02–08 (so the methodology references real, shipped behavior)
- **Surfaces (enumerated — the big cascade; budget-bound):**
  1. `methodology/building.md` — chunk-close: update affected items via `/backlog update` (not hand-edit); the backlog-hygiene step.
  2. `methodology/reflection.md` — capture deferred work via `/backlog add`.
  3. `methodology/planning.md` / `methodology/discovery.md` — select via `/backlog pick`; early-`stage:` pick routes to discovery (reinforces ch.03).
  4. `methodology/session-digest.md` — the ONLY surface every already-onboarded repo re-reads (per learning "framework-level default behavior"): a concise line that backlog edits go through `/prawduct:backlog`, done = archived (never strikethrough).
  5. `templates/build-plan.md` — the backlog-hygiene Done-when guidance (BKL-6L3Q).
  6. `CLAUDE.md` — backlog references if any need updating.
  7. tests: token-budget guardrails on every touched methodology file + digest (`test_token_budget`, methodology-digest budgets) — **plan the trim up front** (planning.md cascade warning); assert-present on the new routing text + assert-absent on stale "hand-edit" phrasing.
- **Tests:** budget guardrails (post-trim); presence/absence assertions across all surfaces.
- **Acceptance criteria:** every surface routes to the skill consistently; budgets pass; suite green.
- **Critic mode:** final
- **Type:** doc-only
- **Done when:** standard 3 steps.

### Chunk 10: Reconciliation + cumulative review

- **Description:** Coherent-artifacts close-out + the PR gate. Flip the spec to "v0.3 shipped," write the change-log entry, and reconcile the deferred backlog items this release subsumes.
- **Depends on:** Chunks 01–09
- **Deliverables:**
  - `documentation/backlog-system-requirements.md` — status → "v0.3 built/shipped"; deferred-list updated.
  - `.prawduct/change-log.md` — entry tagged `scope=backlog-rework` (statusless on the branch; flipped at release per the v2.0.14 learning).
  - `.prawduct/backlog.md` — reconcile via `/backlog update`: BKL-2F7K/BKL-3R8P/BKL-5H9M/BKL-1V8J/BKL-4N6X/BKL-6L3Q, CRT-3K9P, JNT-7T1W → `shipped` (or `dropped` if superseded), with `closed-by`. The new REL-2N8K/CRT-6F2N are unaffected.
  - `CLAUDE.md` — any backlog-doc references.
- **Tests:** full suite; `regen-views --check` clean.
- **Acceptance criteria:** spec/change-log/backlog all coherent; deferred items reconciled; suite green.
- **Type:** cumulative-final
  <!-- Triggers /prawduct:critic cumulative against merge-base...HEAD in addition to this chunk's final review — the /prawduct:pr create gate. -->
- **Done when:** 1. acceptance + tests · 2. `/prawduct:critic final` blocking resolved · 3. committed + `[x]` · 4. `/prawduct:critic cumulative` against `merge-base...HEAD` blocking resolved (the `/prawduct:pr create` gate)

## Early Feedback Milestone

**Milestone chunk:** Chunk 03 — the first user-felt behavior change (`pick` routing a vague item to discovery instead of code). Chunk 01 proves the architecture (parser→briefing); Chunk 03 is where the governance fix becomes observable.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` passes; the whole plan ships as ONE PR to `develop` after Chunk 10's `final` + `cumulative` pass (then batched into a release per `docs/release-process.md`).

- After Chunk 01: architecture validation — is the parser the right substrate shape before 9 chunks import it?
- After Chunk 05: midpoint — do the review-agent checks + the field set cohere, or is the format carrying too much?
- After Chunk 10: cumulative review (the PR gate).
