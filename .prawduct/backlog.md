# Backlog — prawduct

<!-- Structured backlog (format v2). Managed via the /backlog skill.
     Each item: an ID line + a backticked metadata bar + optional free-form body.
     Sections: ## Open (pickable) · ## Promoted (in an active build plan) · ## Archive (shipped/dropped).
     Items move between sections only via explicit `/backlog update` calls. -->

## Open


- **[TEL-7A4X]** Cross-project review-telemetry aggregation — aggregate and review review-cost/value stats across all Prawduct-governed products
  `effort: M · impact: L · area: governance/telemetry · source: user · added: 2026-06-10 · status: open · stage: requirements · refs: build-plan-review-proportionality.md`

  Builds on the per-project foundation in `build-plan-review-proportionality.md` (chunk 02 ledger
  `.prawduct/.critic-reviews.jsonl` with schema_version/model fields; chunk 03 `prawduct-hook
  review-stats --json` stable machine shape with top-level schema_version/project/generated_at —
  that JSON contract is the integration point). Fix-shape sketch (requirements still open): an
  aggregator that scans known product directories (the same discovery the "reviewing product
  feedback" CLAUDE.md route uses for learnings.md), collects each repo's `review-stats --json`, and
  renders a cross-project view: review wall-clock and actionable-finding rate by mode/model/project,
  so proportionality tuning (e.g. which products' chunk reviews yield nothing, where escalation
  pays) is evidence-driven framework-wide. Open requirements: where the aggregate view lives (skill
  vs doc vs janitor section), product opt-in/privacy posture (ledgers are gitignored local state),
  and whether product plugin versions skew comparability. **Blocked until review-proportionality
  chunks 02–03 ship.** User request 2026-06-10 ("grab a backlog to enable telemetry aggregation and
  review across projects"). (user)

- **[CRT-7Q2T]** Critic's no-test-execution rule is not structurally enforced for coordinator-dispatched subagents
  `effort: M · impact: M · area: governance/critic · source: reflection · added: 2026-06-10 · status: open · stage: design · related: CRT-3X9D, CRT-8D2W · refs: skills/critic/SKILL.md (Structural Constraints), bin/prawduct-hook (critic-begin/critic-end)`

  During the 2026-06-10 gate-soundness cumulative review, a coordinator-pattern subagent ran the
  affected test files directly (217 passed, reported in the review summary) despite the SKILL prose
  instruction and the pure-allow tool list — which doesn't bind Agent-dispatched subagents. Same gap
  class as CRT-3X9D, whose critic-begin marker guards only `prawduct-hook clear`. The review
  conclusion was unaffected, but the boundary exists so reviews can't mutate or depend on session
  state. Fix-shape: extend the critic-active marker enforcement (or subagent tool restriction) to
  test/build execution, or have the coordinator pass an enforced `allowed-tools` to Agent
  dispatches. Priority P2. (reflection)

- **[TST-3E8V]** `cmd_test_evidence` catches only FileNotFoundError for a declared test_command — widen to OSError
  `effort: S · impact: S · area: tests/runtime · source: critic · added: 2026-06-10 · status: open · stage: ready · refs: bin/prawduct-hook (cmd_test_evidence), tests/test_plugin_runtime.py (TestTestEvidenceKnobs)`

  `cmd_test_evidence` wraps the declared `test_command` launch in `except FileNotFoundError` only,
  so a *missing* executable gets the clean exit-2 path but a *non-executable* target raises
  PermissionError and tracebacks instead. Fix-shape: widen the except to `OSError`
  (FileNotFoundError and PermissionError are both subclasses) so any OS-level launch failure takes
  the same clean exit-2 path; add a non-executable-target case alongside the existing
  `TestTestEvidenceKnobs` coverage. Filed from the cumulative Critic NOTE on the gate-soundness
  bundle, 2026-06-10. (critic)
- **[STH-5P2W]** Loud guard when a set active_build_plan pointer resolves to no file
  `effort: S · impact: M · area: stop-hook · source: critic · added: 2026-06-09 · status: open · stage: ready · related: REL-4T8N · refs: lib/core.py, bin/prawduct-hook`

  From review-fixes Chunk 1 Critic (2026-06-09). The active_build_plan pointer is
  .prawduct/-relative; a repo-relative value (the natural way to write it) mis-resolves and the
  resolvers (lib/core.py resolve_build_plan_path + the hook's inline mirror) silently fall back to
  the default plan path — disabling the Critic gate, plan-aware mode inference, and
  verify-chunk-refs with no signal. Happened live: the review-fixes planning commit shipped the
  mis-resolving form and the gates were blind for one work cycle until the Critic caught it.
  Fix-shape: when the pointer is SET but resolves to a nonexistent file, warn loudly in the session
  briefing (and/or accept repo-relative forms by stripping a leading .prawduct/) + test.
  Escape-hatches-create-silent-failures shape. (critic)

- **[CRT-5Q8W]** Skill prose clarity micro-fixes from the 2026-06-09 review (critic protocol wording, designer-handoff note, backlog pick defaults, framework-checks example)
  `effort: S · impact: S · area: critic · source: builder · added: 2026-06-09 · status: open · stage: ready · related: PR-3J6W, CRT-6F2N · refs: skills/critic/review-protocol.md, skills/critic/review-cycle.md, skills/critic/framework-checks.md, skills/critic/SKILL.md, skills/backlog/SKILL.md`

  Batch of small wording fixes from the skills review agent, none changing behavior: (1) critic
  review-protocol.md 'Decide checks from signals below' is vague — state that the resolved MODE
  determines which goals apply, with a pointer to review-cycle.md. (2) critic SKILL.md Getting
  Started: add a one-line note that Type: designer-handoff chunks exit early without a findings
  file, so an agent that skips the protocol read still knows the special case. (3) review-cycle.md
  learnings cross-check: note that if a later learning revokes/softens the original, the latest
  learning wins (currently assumes learnings are infallible). (4) framework-checks.md Check 7: add
  a concrete avoid/prefer example for 'strengthening the dynamic generation system'. (5) backlog
  SKILL pick: document the combined effect of missing effort/impact defaults (2/2 = 1.0 score)
  explicitly; drop the stale Q6 label. (builder)

- **[MET-6W3J]** learnings.md compaction: restore When-X-do-Y-because-Z brevity, move narrative to learnings-detail.md, add a size nudge
  `effort: M · impact: M · area: methodology · source: builder · added: 2026-06-09 · status: open · related: MET-5C2H, MET-7R4J · refs: .prawduct/learnings.md, .prawduct/learnings-detail.md`

  From the 2026-06-09 framework review. learnings.md is ~28k tokens for 23 entries — individual
  entries run 300-600 words, drifting from the file's own stated format (rule in learnings.md, full
  context in learnings-detail.md). Every /prawduct:learnings lookup and Critic learnings cross-check
  pays this. Fix-shape: (1) compact each entry to the When/do/because rule plus a pointer into
  learnings-detail.md (move the narrative there — never delete it); (2) add a mechanical size check
  per this repo's own 'growing files need structural nudges to prune' learning (e.g. session-start
  warn when learnings.md exceeds a threshold, like the existing project-state.yaml 40KB warning).
  (builder)

- **[PR-3J6W]** PR skill control-flow clarity: pre-flight guard placement, named retry entry points, Step 1b addressee, evidence retention
  `effort: S · impact: M · area: pr · source: builder · added: 2026-06-09 · status: open · related: PR-5K8D, PR-2H8N · refs: skills/pr/SKILL.md, skills/pr/review-protocol.md`

  From the 2026-06-09 framework review (skills agent). (1) The release-promotion guard sits
  mid-prose after the Context Detection heading but must fire before routing — extract it as an
  explicit Pre-flight section before the routing table. (2) The three sequential STOPs (steps 2,
  2b, 3) never name their retry entry point; an agent may re-run Step 1 after fixing a Step 3
  block — add 'fix, re-run THIS gate, continue' to each. (3) Step 1b's doc-only fast-path
  instruction reads as if addressed to the Critic; rephrase as imperative to the skill executor.
  (4) Decide evidence-file retention: 'delete the evidence file with the branch' loses the audit
  trail if a PR is reverted — archive to .prawduct/.pr-reviews-archive/ or document why deletion
  is intended. Note: the doc-only fileset bug itself (skills/ treated as docs) is PR-5K8D,
  promoted into the review-fixes plan Chunk 3 — this item is the prose/control-flow cleanup only.
  (builder)

- **[STH-4F7C]** Extract the duplicated Critic-freshness gate (cmd_stop vs briefing) to lib/gates.py — copies have already diverged
  `effort: S · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: open · stage: ready · related: STH-9V4K, STH-6B4R, STH-2K8R · refs: bin/prawduct-hook, lib/briefing.py, lib/gates.py`

  From the 2026-06-09 framework review. The mtime-vs-session-start freshness check is duplicated
  nearly verbatim (including the same STH-6B4R comment block) in cmd_stop (bin/prawduct-hook) and
  briefing._check_previous_session_gates (lib/briefing.py). Unlike the hook's intentional inline
  mirrors, this pair has no parity test and has already diverged: cmd_stop gained the
  verify-resolutions scope check; the briefing copy did not. The briefing copy lives in lib/
  already, so the import-light hot-path rationale does not apply — extract to lib/gates.py and add
  a parity/regression test. (builder)

- **[STH-8M3V]** Atomic writes for .prawduct state files + guard unguarded hot-path I/O in cmd_clear
  `effort: S · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: open · stage: ready · related: STH-6Q9D, ADV-9K2T · refs: bin/prawduct-hook, lib/advisory_store.py, lib/gitstate.py`

  From the 2026-06-09 framework review. Only .test-evidence.json gets tmp + os.replace;
  .advisories.json (lib/advisory_store.py), .work-model-index.json, .session-start,
  .session-git-baseline, and .session-handoff.md are plain write_text — two concurrent sessions on
  the same repo (worktrees) can tear them. Readers fail open, so blast radius is a misfired gate,
  not a crash — still worth one shared atomic_write_text helper. Same pass: three unguarded I/O
  sites in cmd_clear (session-file unlink loop, .session-start write, baseline write) can traceback
  the SessionStart hook on an OSError, unlike the meticulously best-effort code around them;
  gitstate's _get_session_changed_files also lacks the (UnicodeDecodeError, OSError) guard its
  siblings have. (builder)

- **[STH-6Q9D]** Batch git subprocess fan-out on SessionStart/Stop hot paths
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: open · stage: ready · refs: bin/prawduct-hook, lib/gitstate.py`

  From the 2026-06-09 framework review. cmd_clear runs ~20+ serial subprocesses (~940ms here; 5-10s
  risk on monorepos): _untrack_session_files issues 1 + up to 14 git ls-files --error-unmatch calls
  every session start (replace with one batched 'git ls-files -- <paths>'); 'git status --porcelain'
  is re-run 4-5x per clear and >=3x per stop (capture once per invocation and pass down);
  _has_product_code (lib/gitstate.py) walks the full tree via rglob including node_modules/.git
  before filtering (use pruned os.walk or git ls-files). (builder)

- **[REL-6C3W]** Flag a code-changing branch that merges with no change-log entry
  `effort: M · impact: M · area: release/change-log · source: reflection · added: 2026-06-08 · status: open · related: REL-2N8K · refs: docs/release-process.md`

  A non-doc-only feature branch can merge to develop with NO `.prawduct/change-log.md` entry at all,
  and nothing flags it — CRT-7B4M (#82) did exactly this, and it only surfaced at the v2.0.16
  release-prep, where the entry had to be reconstructed from the build plan to ship release-notes /
  flip the plan's Status / clear the pointer. This is a worse sibling of REL-2N8K (statusless entries
  silently dropped at release): there the entry exists but lacks a status; here there's no entry.
  Candidate fix: a PR/merge gate (parallel to check-pr-doc-only/trivial) or a release-prep probe that
  flags when `merge-base...HEAD` is not doc-only/trivial yet adds no new change-log entry. Filed from
  the v2.0.16 release (2026-06-08). (reflection)

- **[CRT-3D9K]** `bin/prawduct-hook` stop-gate chunk resolution has the same views-branch blindness CRT-7B4M fixed in inference
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-08 · status: open · stage: requirements · related: CRT-7B4M, STH-2K8R`

  CRT-7B4M fixed `lib/critic_mode.py` so Critic-mode inference derives the current chunk from git
  on a `views_enabled` feature branch (where the build-plan Status checkboxes are a derived view
  that never flips until release). But `bin/prawduct-hook`'s stop-gate still resolves the current
  chunk via the non-git-aware `_current_chunk_id_from_status` mirror (for chunk-`Type:` detection —
  e.g. the trivial-rationale gate), so on a feature branch it reads Chunk 01's `Type:`, not the
  chunk actually in progress. This was an explicit, user-vetoable scope boundary in the
  critic-mode-branch-fix build plan (ASSUMPTION 2); it fails safe (worst case: the gate checks the
  wrong chunk's Type, defaulting toward stricter review), so it's filed rather than fixed in that
  PR. Fix-shape: give the hook's chunk resolver the same git-aware path (or — per STH-2K8R —
  consolidate the mirrored helpers into `lib/` and have both the hook and inference consume one
  implementation, which would close this by construction). Surfaced by the CRT-7B4M cumulative
  Critic (2026-06-08). (critic)

- **[MET-5C2H]** Holistic context/token-budget audit — manage what fills the context window, don't dodge ceilings
  `effort: M · impact: L · area: methodology · source: user · added: 2026-06-08 · status: open · stage: research`

  The per-file token-budget tests (`building.md` <4850, critic `review-protocol.md` <3120) are proxies for
  context-window cost, but they (a) don't measure the *whole* always-loaded surface (session digest +
  product CLAUDE.md anchor + whatever methodology gets read on demand per work cycle), and (b) invite a
  "we hit a ceiling, put the tokens in a file with headroom" reflex that optimizes the wrong thing —
  content lands in a less-natural home to dodge a budget instead of asking whether the budget should rise.
  Surfaced during backlog-rework Chunk 05 (placing C-B checks in `review-cycle.md`): there the file *was*
  the natural home, but the heuristic itself is a smell. **Research-stage** — investigate before designing:
  enumerate every always-on / per-cycle context surface and its size; estimate per-token ROI (is every
  existing token earning its place?); decide whether budgets should be holistic (a total always-on ceiling)
  rather than per-file; and only raise a per-file budget when every existing token is high-ROI. Output: a
  recommendation + (likely) a revised budget model. Then it can advance to `design`/`ready`. (user)

- **[REL-2N8K]** Release-prep silently drops statusless change-log entries — step 3 only flips `status=merged`
  `effort: S · impact: M · area: methodology · source: builder · added: 2026-06-08 · status: open · related: REL-4T8N`

  `docs/release-process.md` step 3 instructs the release author to flip entries "from `status=merged`
  to `status=shipped`." But the documented two-state lifecycle (set `status=merged` at the
  feature→develop merge) is manual and the `/prawduct:pr` merge flow never applies it, so most entries
  arrive at release-prep **statusless**. A literal reading of step 3 flips only the `status=merged`
  entries and silently omits every statusless one — and since `regen-views` acts only on
  `status ∈ {shipped, merged}`, those scopes' build-plan `## Status` checkboxes never flip and they
  vanish from `release-notes.md` + `scope_rollups`, with no warning. At v2.0.14, 8 of 10 unreleased
  entries were statusless (hook-decomp ch.1–7 + critic-session-guard); the release was correct only
  because the author enumerated ALL entries above the prior `release=` boundary by hand. Two fix
  options: (a) reword step 3 to "flip every unreleased entry — statusless OR `status=merged` — to
  `status=shipped`," and/or (b) make the `/prawduct:pr` feature→develop merge reliably stamp
  `status=merged` on the merged entry so the lifecycle the learnings describe actually holds. Either
  closes the silent-omission hole. (builder, from the v2.0.14 release)

- **[CRT-3X9D]** Critic's no-execution constraint doesn't prevent session-mutating `prawduct-hook clear`
  `effort: S · impact: M · area: critic · source: builder · added: 2026-06-07 · status: in-progress (implementation complete) · branch: fix/critic-session-guard-CRT-3X9D · plan: build-plan-critic-session-guard.md · related: STH-9V4K`

  The Critic skill is documented (CLAUDE.md, review-protocol) to run with restricted `allowed-tools` so
  it "cannot run test suites, builds, or executables" — review is code-analysis only. During the
  STH-9V4K ch.7 `cumulative` review the Critic nonetheless ran `prawduct-hook clear` (as a "read-only
  smoke") AND `pytest` once against the real project dir. `clear` is NOT read-only: it archived +
  deleted the builder's `.session-reflected`, rewrote `.session-start` (making fresh test evidence read
  "stale"), and recaptured the git baseline — clobbering live session governance state mid-review. The
  builder had to restore the reflection and re-record evidence. Root cause: the tool restriction must
  not actually be enforced for `prawduct-hook <subcmd>` (and pytest) the way the docs imply, OR the
  Critic agent has Bash latitude it shouldn't. Fix options: tighten the Critic's `allowed-tools` so it
  genuinely cannot invoke `prawduct-hook`/`pytest`, or make the Critic's smoke run against a temp copy /
  with a guard env var that disables session-file mutation. Either way, an independent reviewer must
  never be able to mutate the session it's reviewing. (builder)

- **[STH-2K8R]** `lib/critic_mode` could consume `lib/buildplan_refs` directly instead of mirroring its build-plan helpers
  `effort: S · impact: S · area: refactor · source: builder · added: 2026-06-07 · status: open · related: STH-9V4K · reviewed: 2026-06-09`

  `lib/critic_mode.py` carries independent re-implementations of `_current_chunk_id_from_status`,
  the chunk-`Type:` parser, and `_is_metadata_path` (and references `_parse_build_plan_status`),
  whose stated rationale is "no dependency on `bin/prawduct-hook` — re-implemented to stay importable
  from the slash-command shim" (critic_mode.py docstring ~L46). STH-9V4K ch.2–3 moved those helpers
  into `lib/gitstate` + `lib/buildplan_refs`, which `critic_mode` *already* imports siblings from
  (`from .core import resolve_build_plan_path`). So the mirror's reason-to-exist is now gone:
  `critic_mode` could `from .buildplan_refs import _current_chunk_id_from_status` (etc.) and
  `from .gitstate import _is_metadata_path`, deleting the duplicate bodies + their manual-sync
  docstrings. Defer until the decomposition (ch.4–7) lands so the lib surface is stable. NOT a
  behavior-preserving move (it changes critic_mode's structure + collapses a parity relationship),
  so it needs its own tests + Critic pass — kept out of ch.3 for scope discipline. Filed from the
  ch.3 buildplan_refs extraction on 2026-06-07. (builder)

  Critic note (review-fixes Chunk 1, 2026-06-09): lib/critic_mode.py contains a third porcelain
  parser that near-duplicates the new shared gitstate.parse_porcelain_line (quoted paths, renames);
  fold it onto the shared helper when consolidating this item's lib/critic_mode mirrors.

- **[ADR-7X2M]** Adversarial review agent (4th review-agent role) — RFC: systematic edge-case / attack-surface generation
  `effort: L · impact: M · area: methodology · source: user · added: 2026-06-06 · status: open · related: CRT-9V4T, PRR-4M9T, JAN-4F7M`

  RFC for a FOURTH independent review agent alongside Critic / PR-reviewer / Janitor, with the
  opposite goal — make the code *break*, not work: systematic edge-case / attack-surface generation.
  **Opt-in per project (default disabled).** Defense-in-depth via THREE independent attack-surface
  identification points: (1) **Planning** — build-plan chunks declare an `attack_surfaces:` field (an
  empty list is a valid declaration; the field itself is required); (2) **Builder** — verifies the
  actual surfaces touched at chunk-end and prompts the user for an opt-in adversarial pass when the
  diff matches the surface taxonomy; (3) **Critic Goal 8** — independent diff inspection backstop
  (WARNING on an undeclared touched surface, or a declared-but-undispositioned surface). Plus a
  pre-release `/adversarial --sweep-since-last-release` sweep.

  **NOTE — needs rework, not a merge:** the original RFC targeted the pre-2.0 `agents/` +
  `templates/critic-review.md` layout (both since removed). A real implementation must be reworked
  onto the current plugin `skills/` architecture; treat as **new feature work**, not a merge. Full
  original design is preserved verbatim at git tag `rfc/adversarial-review` (commit `967b861`).
  Author: Jason-Vaughan. Type: feature/methodology, size: medium-large. (user)


- **[PR-2H8N]** Key the `/pr` release-promotion guard off `resolve-base` instead of hardcoded branch names
  `effort: S · impact: S · area: pr · source: critic · added: 2026-06-06 · status: open · related: REL-8K3M`

  REL-8K3M's release-promotion guard in `skills/pr/SKILL.md` hardcodes `develop`/`main`/`master` to
  recognize a release/integration context. The skill's own merge-flow (step 7) already distinguishes
  trunk-vs-gitflow generically via `prawduct-hook resolve-base`. A repo with a custom `base_branch`
  name (or an unusual release-surface name) would slip past the guard. Kept a NOTE during REL-8K3M
  because the guard is judgment-admitting prose an LLM can generalize, the doc reference is already
  present, and REL-8K3M targets prawduct's own gitflow case. Fix-shape: have the guard compare the
  current branch to `resolve-base`'s output (the integration base) and to the release surface, rather
  than a fixed name list. Filed from the REL-8K3M cumulative Critic NOTE on 2026-06-06. (critic)

- **[WMK-1P4Q]** Work-model parent-map injection (B2) + optional `vocabulary:` frontmatter convention
  `effort: M · impact: M · area: hooks · source: critic · added: 2026-06-06 · status: open · related: work-model`

  Deferred from the work-model build (confidence-gated). A SessionStart hook would inject a compact,
  capped "parent map" (governing docs + 1-line scope) as ambient awareness, complementing the shipped
  *active* UserPromptSubmit nudge. Deferred because its value over the active nudge is medium-confidence
  and it adds ambient per-session tokens (review NOTE-7) — earn with usage evidence (false-positive /
  miss data from the live nudge). Also document the optional `vocabulary:`/`governs:` frontmatter
  convention in artifact templates (the lib already supports it; auto-extract is the default). See
  `docs/work-model-spec.md` Part C and `docs/work-model-enforcement.md`.

- **[LRN-3F8K]** Reconcile the dangling sentinel on the "Framework ownership follows the write strategy" learning
  `effort: S · impact: S · area: learnings · source: critic · added: 2026-06-04 · status: open`

  `audit-learnings` reports an error: the learning "Framework ownership follows the write strategy,
  not just registry membership" carries `sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip`,
  but `tests/test_prawduct_sync.py` was deleted with the file-sync engine in M4 (v2.0.3) — so the
  sentinel is dangling and the audit flags it as a failing sentinel (which blocks the learning's
  retirement). Pre-existing (M4-era); surfaced by the rigor-and-stance cumulative Critic as outside
  that bundle, flagged rather than fixed inline (Scope Discipline). Fix-shape: decide whether the
  write-strategy-ownership contract still has a live equivalent test (repoint the sentinel to it), or
  the learning has outlived its mechanism (drop the sentinel annotation / retire the learning) — a
  one-line annotation fix once decided. Filed from the v2.0.7 release audit. (critic)

- **[STN-6K3D]** (Optional) Ship a non-forced `output-styles/` style power users can voluntarily select
  `effort: S · impact: S · area: agent-stance · source: builder · added: 2026-06-04 · status: open`

  rigor-and-stance Chunk 02 placed the agent stance in the always-on session digest because a
  `force-for-plugin` output style HARD-OVERRIDES (clobbers) a consumer's own output style and does not
  compose — disqualifying for unconditional, composable governance (verified against the Claude Code
  output-styles docs, 2026-06-04). A *non-forced* output style is a separate, safe nice-to-have: ship
  `output-styles/<name>.md` (no `force-for-plugin`) so power users can OPT IN to the prawduct voice via
  `/config` without clobbering their own style. Low priority — the digest already delivers the stance
  unconditionally; this is pure ergonomics. Filed from the rigor-and-stance cumulative Critic
  (Complete Delivery — the plan deferred this). (builder)

- **[STH-3W7F]** Stop gate blocks session end while a tracked background workflow/task is still producing the diff
  `effort: L · impact: M · area: stop-hook · source: user · added: 2026-06-04 · status: open · partial: floor+design shipped via #60 (code fix pending) · related: STH-7K2A`

  Filed by a Hallucinote session (`incoming-bugs/stop-gate-blocks-on-in-flight-background-work.md`) and
  **confirmed firsthand** in the roi-batch-2 session: the `critic-review` + `reflection` Stop gates fire
  on "tracked files changed, no Critic/reflection yet" with NO awareness of in-flight background work.
  While a background `Workflow`/`Task` is still generating the diff, ending the turn (the natural thing
  while awaiting an async run) trips the block, and every subsequent yield re-fires it until the job
  completes (roi-batch-2 absorbed ~15 block-loops over the ~12-min HOOK lane). The two available
  outcomes both misfit: SPIN (absorb a block every turn) or WAIVE — but `.gates-waived` means "cannot be
  satisfied THIS session" (`docs/waivers.md`), which is FALSE here (the gate WILL be satisfied minutes
  later), so waiving overloads the semantics and pollutes the archive with a "can't satisfy" reason for
  work that was satisfied. Distinct from [STH-7K2A] (a same-signature loop COUNTER that escalates/
  downgrades after N fires): this is about *deferral when a live tracked job exists*, not loop-counting —
  though a unified design could cover both. Remediation options (from the report): (1) background-aware
  deferral — before blocking, the Stop hook checks for a live tracked background job (workflow run dir /
  task registry) and DEFERS, re-running the gate on the next Stop after completion; (2) a first-class
  `.gates-deferred` state (reason + expected-completion) distinct from a waiver, so the archive records
  "deferred pending async run"; (3) minimal — sanction an in-flight-work waiver reason-prefix in
  `docs/waivers.md` to stop the semantic overload. Open design problem: the Stop hook is a subprocess and
  has no guaranteed handle on "is a Workflow still running" — the detection signal (a live workflow run
  dir under the session dir?) is harness-version-dependent and needs verification before (1) is viable;
  (3) is the cheap, safe floor. Filed 2026-06-04. (user)

  **DESIGN + safe floor shipped (evidence-deferral, 2026-06-04 — chunk 02).** Investigation
  corrected the framing: the report's option (3) "sanction an in-flight WAIVER" is actually WRONG —
  waiving the Critic gate while background work is in flight would SKIP the Critic the completed
  work still needs (the waiver persists the session, auto-clears next). So the agent is NOT forced
  to choose between two bad options: SPIN is the *correct* behavior (wait, then run the Critic when
  the job lands); the only real defect is the NOISE of repeated harmless blocks during a legitimate
  wait. Shipped floor: `methodology/building.md` Gate-waivers now states "in-flight background work
  is NOT a waiver case — wait, don't waive," so the semantic-overload temptation is removed.
  Detection finding (rules out option 1 for now): the Stop hook (`prawduct-hook stop`) does NOT read
  stdin, so it has no `transcript_path`/`session_id`; even if it did, inspecting
  `subagents/workflows/*/journal.jsonl` can't distinguish a LIVE run from a CRASHED one (`started >
  result` matches both; the journal persists after completion) — harness-version-dependent, unsafe
  to build. Recommended REAL fix (option 2, refined): a SELF-DECLARED `.prawduct/.gates-deferred`
  file (the AGENT knows it launched background work; the hook can't detect it) that the Stop hook
  honors to defer the gate EXACTLY ONCE, then auto-rearms (clears itself on the deferred fire) — so
  it quiets the wait WITHOUT ever permanently skipping the Critic (the next Stop re-checks normally;
  the harness's pending-background-work keeps the session alive across the deferred fire). Distinct
  archive semantics from a waiver ("deferred pending async run," not "unsatisfiable"). This needs a
  Stop-hook code change + a guard test that a deferred gate re-arms; deferred from the doc-floor
  chunk on proportionality. Could unify with [STH-7K2A] (both quiet a re-firing gate). (builder)

- **[STH-4D2X]** Decide whether the trivial/doc-only file-set gate should also protect a consumer's own `.claude/skills/`
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-06-03 · status: open`

  The waiver-pragma branch (W2-C1) fixed `_classify_trivial_change` to bound `skills/` (the framework
  repo's own skill definitions) instead of the deleted `agents/`. Open question it surfaced: in a
  CONSUMER repo, a product's own skills live at `.claude/skills/` (not top-level `skills/`), and
  `_is_metadata_path` no longer excuses them (M4 made `.claude/skills/` count as gated code). Should
  editing `.claude/skills/foo/SKILL.md` in a `Type: trivial`/doc-only chunk trip the catastrophic-
  blast-radius bound? A product skill is important but arguably not "governs all future work"
  catastrophic the way the framework's own `skills/`/`methodology/`/`templates/` are. Changing it
  affects every consumer, so it needs a deliberate decision + test, not a silent add. Filed from the
  2.0-rock-solid pass, 2026-06-03. (builder)

- **[CRT-SHADOW]** (Optional) Recreate an A/B "shadow Critic" as a plugin variant
  `effort: M · impact: S · area: critic · source: builder · added: 2026-06-02 · status: open · reviewed: 2026-06-02`

  Chunk 13 retired the `critic-test` shadow skill (owner decision 2026-06-02). It was a framework-only experimental twin of `/critic` that wrote to `.critic-test-findings.json` (non-gating) for A/B-testing review-strategy changes. It was deliberately never ported to the plugin (Chunk 3), it read the now-deleted `agents/` tree, and its comparison baseline — the production Critic — now lives in the plugin. If A/B review-strategy testing is wanted again, recreate it as a **plugin** skill (`skills/critic-test/`) that forks against the plugin's bundled `skills/critic/review-protocol.md`, rather than maintaining divergent copies of the protocol. Low priority — only build if a concrete review-strategy experiment needs it. (builder)

- **[CRT-9V4T]** Verify (or harden) interactive enforcement of the Critic fork-skill's `allowed-tools` cap
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-01 · status: open · reviewed: 2026-06-01`

  Surfaced during v2.0.0 Chunk 4 empirical verification. The Critic's structural "no pytest / read-only git" guarantee rests on a `context: fork` skill with a pure-allow `allowed-tools` list (pytest unmatchable). `test_critic_skill_metadata.py` pins the *list shape* (no allow pattern matches pytest), and CLAUDE.md calls the constraint "structural, not behavioral." But a Chunk-4 probe found that under headless `claude -p`, a fork-skill with `allowed-tools: Read, Bash(git status *)` still ran a NON-allow-listed `echo` (marker printed) — i.e. headless `-p` did not enforce the allow-list as a hard cap. This does NOT prove a hole: the real Critic runs **interactively** (forked from a `/critic` invocation), where the cap is designed to apply, and the probe couldn't exercise that path. But it means the interactive enforcement is **assumed, not hermetically verified**, and the "structural" claim is only as strong as that assumption. Pre-existing — affects today's file-sync Critic identically; Chunk 4 introduced no regression (frontmatter byte-identical). Relates to memory `feedback_critic_no_test_execution` and learning CRT-2M5P. Fix-shapes: (a) an interactive-mode verification (manual or scripted) that confirms a forked `/critic` is actually denied a non-allow-listed Bash command — establishes whether the cap is structural or merely prompt-suppression; (b) if (a) shows it's not a hard cap, add a belt-and-suspenders **PreToolUse guard hook** in the plugin `hooks/hooks.json` that blocks pytest/`git checkout`/tree-mutation specifically when the calling agent is the critic (needs the hook to be able to scope to the subagent — itself unverified); (c) at minimum, soften the "structural, not behavioral" wording in CLAUDE.md to match what's actually verified. Open question: does Claude Code treat skill `allowed-tools` as a hard deny-cap in interactive mode, or as a no-prompt allow-list with a separate ask-fallback for unlisted tools? Resolve (a) before relying further on the claim. Filed from Chunk 4 verification on 2026-06-01. (builder)

- **[STH-7K2A]** Stop-hook structural loop-detection counter (defense-in-depth on top of v1.5.2's discoverability fix)
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-23 · status: open · closes: v1.5.2 discoverability half · reviewed: 2026-05-29`

  v1.5.2 (2026-05-23) shipped the discoverability piece: all four blocker stderr messages now name `.gates-waived`, the JSON shape, and `build-governance.md` so agents stuck in unsatisfiable gate states can declare a waiver. The structural piece is still open. Pathology: even with the escape hatch named in the blocker text, an agent can in principle ignore it and continue re-firing the same gate. Defense-in-depth fix-shape: track stop-hook fire count per session in a new `.prawduct/.stop-fire-count` file recording `{count, blocker_signature, ts}`. On the Nth (e.g., 3rd) consecutive fire with the same signature and no progress (no new Critic findings, no new waiver, no diff change since last fire), either (a) escalate the blocker text to name the loop explicitly and force-surface the waiver mechanism above the existing prose, or (b) auto-downgrade to advisory (stderr-only) on the assumption that the agent has seen the gate and made an informed call. (a) is conservative; (b) is firmer about not burning tokens. Auto-clear on session start. Open design questions: per-blocker counter or session-wide? what counts as "progress" (any diff change or only changes that materially address the gate)? should the counter persist if the blocker signature changes mid-session? Filed from v1.5.2 release (2026-05-23) as the deferred structural half of the original infinite-loop bug; the original "discoverability" half is shipped and the backlog entry closes against v1.5.2's change-log entry. (reflection)

- **[CRT-1F7N]** Re-enable cumulative inference mid-build by recording per-HEAD cumulative records
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-22 · status: open · reviewed: 2026-05-29`

  Chunk 03's rule 2 (cumulative) added a clean-tree guard so it doesn't over-fire mid-chunk-N. Side effect: even after the user commits chunk N, rule 2 still doesn't fire because the helper has no record that cumulative was already run for THIS HEAD — but in practice cumulative IS expensive and the user typically only wants it pre-PR. The current behavior matches the proportionality intent, but loses some signal: if the user committed and is about to PR, inference doesn't surface "you should run cumulative" — it returns `chunk` (or `final` if last chunk). Fix-shape: when the working tree is clean AND ≥2 commits ahead, return `cumulative` even though it'd take 4-10 min — the cleanness is the signal the user has stopped editing and is about to merge. Risk: false-positives on chunk boundaries where the user clean-committed but isn't about to PR. Validate against a few real chunk boundaries before changing. Filed from Chunk 03 work on 2026-05-22. (builder)

- **[MIG-6B0R]** Recommend gitflow as the default git strategy + strip prawduct artifacts on deploy-to-main
  `effort: L · impact: M · area: migration · source: builder · added: 2026-05-19 · status: open · reviewed: 2026-05-29`

  Two coupled proposals:
  1. **Recommend gitflow** (`develop` for ongoing work, `main` as the deployed/released branch, feature/release/hotfix branches off `develop`) as the prawduct-recommended workflow. Captured in `project-preferences.md` (or a new `methodology/git-strategy.md`) with rationale: prawduct's session-artifacts churn pattern fits gitflow's "develop is mutable, main is immutable releases" split much better than trunk-based flow, where every session-edit lands on the deployable branch.
  2. **In gitflow repos, strip prawduct artifacts from `main` when promoting `develop` → `main`** (or when pushing directly to `main`). Filter scope:
     - **Strip:** `.prawduct/` contents — `backlog.md`, `build-plan.md`, `artifacts/`, `learnings.md`, `learnings-detail.md`, `change-log.md`, `.session-*`, `.critic-findings.json`, `.test-evidence.json`, etc. (governance bookkeeping, not deployment payload).
     - **Strip:** prawduct-owned hooks/skills — `bin/prawduct-hook`, `.claude/skills/{critic,pr,janitor,learnings,prawduct-doctor}/SKILL.md`, framework-managed `.claude/settings.json` hook entries.
     - **Keep:** `docs/` and `documentation/` (real product documentation, not governance artifacts).
     - **Keep:** project-owned skills/hooks (anything in `.claude/skills/` that's NOT in the prawduct-managed set — user-authored skills stay).
  Fix-shape: probably a `prawduct-doctor deploy-to-main` (or `prawduct-deploy`) subcommand that performs a filtered merge/squash — strips the listed paths from a temp index, commits the cleaned tree to `main`, leaves `develop` intact. Alternative: a git pre-receive hook recipe in `methodology/git-strategy.md` that products copy into their own remote. Need to decide which paths are framework-canonical (centralizable in `core.py`'s MANAGED_FILES + a new `DEPLOY_STRIP_PATHS` set) vs. project-configurable. Open question: does the filter run on every push to main, or only on explicit `prawduct-doctor deploy` invocations? Filed from user request on 2026-05-19. (builder)

- **[DOC-9J4B]** F8: add Foreign-API example to hallucinote product repo
  `effort: S · impact: S · area: docs · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  v1.4 Chunk 04 (F8) acceptance criterion called for "at least one product-repo example added (hallucinote's Ableton Live MCP work is the obvious reference)." The Ableton-MCP example was shipped as a worked illustration inside the framework (planning.md "Foreign API Verification" section + templates/build-plan.md inline example), satisfying the spirit but not the literal product-repo touch. Defer the hallucinote-side update — `**Foreign API:** ableton-live-mcp` on the relevant build-plan chunk + `verify-api` step in Done-when — to the next hallucinote session. Filed from /critic NOTE on 2026-05-18. (critic)

- **[BLD-5V8F]** F3: extend `verify-chunk-refs` beyond file paths
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  v1.4 Chunk 02 (F3) shipped file-path verification only; the original plan also called for symbol (function/class names) and backlog-ID verification. Deferred during build because (a) symbols in prose are often approximate (`parse_func` vs implementation's `_parse_func`) so strict grep produces false positives requiring fuzzy match; (b) this project's backlog has no formal IDs (bullet titles, not e.g. `BL-123`), so the check would be inert here and need per-project ID convention. Add when a project surfaces a concrete need: define matching rules (substring grep across configured source roots for symbols; project-preferences `backlog_id_pattern` regex for backlog refs) and extend `_parse_build_plan_chunk_refs` to return `symbols` and `backlog_refs` lists alongside `file_paths`. Note: this project now HAS formal backlog IDs (`[PFX-XXXX]`) post-migration, so the backlog-ID half is newly actionable. Filed from /critic NOTE on 2026-05-18. (critic)

- **[BLD-6Q1N]** Extract `_iter_status_section_items` shared parser for build-plan Status
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-08 · status: open · reviewed: 2026-05-29`

  `_count_build_plan_chunks` (bin/prawduct-hook lines ~2073-2113, added v1.3.13) duplicates the Status-section parsing skeleton of `_parse_build_plan_status` (lines ~1021-1099): same `## Status` detection, same HTML-comment skip, same exit on next `## ` heading. Two callers is borderline; if a third caller appears (e.g., a future stop-hook check that needs chunk metadata), extract to `_iter_status_section_items(prawduct_dir) -> Iterator[StatusItem]` and refactor both call sites. Filed from /critic NOTE on 2026-05-08. (critic)

- **[CRT-2H8K]** `.critic-findings.json` cumulative-state file
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-05 · status: open · reviewed: 2026-05-29`

  Would let `final` reviews focus on emergent cross-chunk concerns by remembering what each `chunk` review already covered. Useful but not necessary for proportionality MVP (v1.3.13). Revisit if `final` reviews still feel slow after live use. Filed during proportional-Critic build plan as out-of-scope. (builder)

- **[MET-9K4R]** Workflow-values schema/validator
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-01 · status: open · reviewed: 2026-05-29`

  Workflow preferences (`Branching: direct`, `PR creation: wait_for_user`, `PR merge: wait_for_user`) are read by `building.md` and `/pr` but have no allowed-vocabulary or shape check. A typo or unknown value would silently default. Candidate: small Critic checklist line ("Workflow values must be one of X / Y / Z") OR a tiny config-presence test. Low priority — current values are stable. (critic, 2026-05-01)

- **[MET-3P7B]** Lift "assign a mechanism per preference" pattern into methodology
  `effort: M · impact: M · area: methodology · source: critic · added: 2026-05-01 · status: open · reviewed: 2026-05-29`

  The Enforcement section added to `project-preferences.md` (and the template, 2026-05-01) encodes a methodology insight: every preference must be assigned to Linter / Test / Critic when it's captured, with a false-confidence guardrail that escalates weak tests to Critic. Currently lives only in the artifact + template. Candidate: weave into `methodology/discovery.md` (when capturing preferences) and `methodology/planning.md` (when designing test specs). Validate the pattern against 2-3 more preferences first before promoting. (critic)

- **[CRT-6T1V]** Critic check: test helpers duplicating production logic
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Cross-product reflection audit (Apr 16) surfaced a recurring drift hazard in discodon: test files re-implement production calculations (LogQL builders, SDK result parsing) rather than importing the shared helper, so tests keep passing while production drifts. Evidence: discodon/reflections.md §2026-04-14 "Pattern worth keeping". Candidate: extend Goal 1 or Goal 7 in skills/critic/review-protocol.md — when a test performs a calculation/parsing operation that exists in production, flag as WARNING unless the test is deliberately testing the helper itself. Needs design work on detection heuristic (string-matching is noisy; AST match is heavier). (reflection)

- **[CRT-1B6Q]** Critic check: stateful objects in shared_kwargs need lifecycle cleanup
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-15 · status: open · reviewed: 2026-05-29`

  Discodon's multi-tool coordinator pattern passes stateful objects (PendingVoiceSlot, prior voice_getter closures) via `shared_kwargs` to multiple tools. Critic caught lifecycle bugs (missed_intro false-positives when idle) only after complex state interactions emerged. Evidence: discodon/reflections.md §2026-04-15 V0.5-5. Candidate: extend Goal 6 (The System Can Be Understood) — when an object with enter/exit/close methods is shared across tools, verify owner tool's stop() drains/closes it. Generalizes beyond discodon's specific pattern to any DI/coordinator framework. (reflection)

- **[CRT-5N3F]** Critic false positives from fork-context limits
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Discodon archive (Feb–Apr 2026) has 4 confirmed cases where Critic misread code: Mar 24 shutdown event closure, Mar 25 eval doc merge (3 of 4 prior findings false), Mar 28 ARIA A1/A2 missed an existing `model_config = ConfigDict(str_strip_whitespace=False)` override, plus branch-switching confusion. Root cause: `context: fork` can't see overrides spanning files / inheritance / closures. Investigate whether Critic's research phase needs a wider read budget for inheritance chains, or whether prompt engineering can compensate. (reflection)

- **[CRT-8D2W]** Critic-in-worktree as structural fix for session-file conflicts
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-03-25 · status: open · reviewed: 2026-06-10 · related: CRT-3X9D`

  v1.3.3 gitignored build-plan.md and v1.3.4 added `_untrack_session_files()`, but the user explicitly suggested running Critic in a separate worktree to avoid touching session files in the active tree at all. Mar 25 discodon avatar_description session captured this when branch-switching during Critic review caused merge conflicts on `.session-handoff.md` and backlog. Worth designing as a follow-up to the gitignore approach. (reflection)

  **Premise partially obsoleted — reassessed 2026-06-10:** the original motivation rested in part on
  the build plan being a *gitignored* session file; gate-soundness ch.3 (feature/gate-soundness) made build
  plans **tracked**, so that half of the conflict surface is gone. The residual rationale is
  narrower: the remaining gitignored session files (`.session-handoff.md`, `.critic-findings.json`,
  `.session-reflected`, …) plus the broader isolation argument — an independent reviewer should not
  be able to mutate the session tree at all (the same invariant CRT-3X9D enforces at the mutation
  site via the critic-begin/critic-end guard). Before any design work, re-derive the requirement
  against the current tracked-build-plan + critic-session-guard reality; the worktree approach may
  now be redundant defense-in-depth rather than a structural fix. (critic, gate-soundness cumulative
  review note)

- **[SYN-6J0R]** WIP tracking goes stale when branches merge piecemeal
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-03-23 · status: open · reviewed: 2026-05-29`

  Mar 23 discodon doc audit found 3 WIP branches were already merged into develop via other PRs but project-state.yaml still listed them in-progress. No mechanism reflects branch completion back to project-state.yaml when PRs merge. Consider git-based detection (branch existence on remote) or a post-merge sync step. (reflection)

- **[STH-9V4K]** `bin/prawduct-hook` decomposition
  `effort: L · impact: M · area: stop-hook · source: janitor · added: 2026-04-16 · status: in-progress (implementation complete — release-pending) · plan: build-plan-hook-decomposition.md · reviewed: 2026-06-07`

  Split the hook monolith into logical modules. **Implementation complete (2026-06-07):** all 7 chunks built + Critic-clean, one module per PR in dependency order — ch.1 lazy `lib/__init__` (enabling), ch.2 `lib/gitstate` (#74), ch.3 `lib/buildplan_refs` (#75), ch.4 `lib/compliance` (#76), ch.5 `lib/coverage` (#77), ch.6 `lib/gates` (#78), ch.7 `lib/briefing` (the SessionStart surface — final). The hook went from **4,942 → 1,911 lines (−61%)** and is now a thin dispatcher (bootstrap + parity-pinned inline mirrors + lazy `lib` accessors + `cmd_*` wrappers + `cmd_clear`/`cmd_stop`/`main`). An AST call-graph drove the leaf-first order; the briefing↔gates↔coverage↔buildplan_refs cycle was broken by reassigning `_parse_build_plan_status` to buildplan_refs. **Remaining: the develop→main release** that flips the build-plan checkboxes `[x]` (`status=shipped` change-log tags + regen-views) — close this item then. Enabled follow-up still open: STH-2K8R (critic_mode mirror consolidation). (janitor)

- **[TST-4P8H]** Flaky tests under parallel execution (xdist)
  `effort: M · impact: M · area: tests · source: builder · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Re-validated 2026-06-03: 5 of the 6 originally-named tests were removed with the file-sync engine (M4) — only `TestStopPrReviewGate::test_stop_clean_without_pr` survives. The narrow open question is whether that surviving subprocess-heavy test (and peers) still flake under `-n10`. The depth_cap test creates 111 git subprocess commits in a loop — when 9 other xdist workers are simultaneously doing similar subprocess-heavy work, the system runs out of fork resources / hits IO contention and the test times out. Passes 100% of the time when run in isolation or with reduced parallelism. Root cause likely race conditions in the subprocess-based hook tests sharing process-level state or temp dir contention. (builder)

- **[STH-7B5N]** Session lock file for concurrent session detection
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Advisory lock file in product-hook clear/stop to warn when another Claude session is active on the same project. Agreed on non-blocking approach with staleness timeout (~4 hours). (builder)

<!-- v1.7.0 deferred scope — the backlog feature shipped its lean core (the /backlog skill + the single
     legacy-backlog-format probe). The items below are real requirements scope (backlog-system-requirements.md,
     post-sync-advisory-spec.md §8.2) held back on proportionality grounds: low-risk internal markdown tool,
     no current consumer. Add each when a real product needs it. Filed from the v1.7.0 release chunk (2026-05-29). -->

- **[BKL-4N6X]** `/backlog dismiss-advisory` per-feature alias
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: open`

  Requirements §8.2. A convenience alias that forwards to the existing unified `/prawduct-advisory dismiss`. The unified command already works, so this is pure ergonomics — deferred until the alias's discoverability is worth the extra surface. (builder)

- **[BLD-7W2J]** Single-slot `active_build_plan` vs parallel in-flight plans
  `effort: M · impact: M · area: governance/planning · source: critic · added: 2026-06-10 · status: open · stage: idea · related: REL-4T8N · refs: lib/core.py (resolve_build_plan_path), methodology/planning.md`

  Two concurrent feature branches (feature/review-fixes → `build-plan-review-fixes.md`,
  feature/gate-soundness → `build-plan-gate-soundness.md`) each set the one `active_build_plan`
  pointer in `project-state.yaml`, guaranteeing a same-line merge conflict on develop — after which
  one plan is invisible to pointer-resolved governance (stop hook, `infer-critic-mode`,
  `verify-chunk-refs`) until repointed. planning.md's new "Plan lifecycle on gitflow" paragraph
  covers only the *serial* release-pending case; gate-soundness ch.3 (tracked plans) + scope-named
  files make parallel plans more likely. Design work needed: model multi-plan state (e.g. a plan
  list, or per-branch resolution) or document the parallel-branch convention. Related: REL-4T8N
  solved the *release-side* multi-plan problem (regen-views enumerates change-log scopes instead of
  the pointer) but the in-flight pointer remains single-slot. Filed from fable test-reviewer NOTE on
  the gate-soundness bundle, 2026-06-10. (critic)

- **[MET-7R4J]** Methodology/CLAUDE.md redundancy and prompt-quality pass — hard rules stated 4-6x across always-loaded surfaces
  `effort: M · impact: M · area: methodology · source: builder · added: 2026-06-09 · status: open · related: MET-5C2H · refs: CLAUDE.md, docs/principles.md, methodology/building.md, methodology/planning.md, methodology/session-digest.md`

  From the 2026-06-09 framework review (methodology-as-prompts agent). For Opus/Fable-class models, restating a rule with varied phrasing creates interference, not reinforcement. (1) Consolidate to one canonical statement + cross-refs: Tests Are Contracts appears 6x (CLAUDE.md, principles.md, agent-stance.md, building.md 2x, session-digest.md); the mid-build-requirement rule has 8+ phrasings; the Critic mandate appears 6x with escalating emphasis. (2) Remove emphasis escalation: CLAUDE.md 'STOP. Read this before writing ANY code' caps — prompt-rot pattern that also misstates Critic timing (Critic runs after code). (3) Compress planning.md Foreign API Verification (~40 lines to ~15: rule + when-to-apply + one worked example; move match mechanics to the Critic protocol). (4) Add one sentence to building.md Before You Build: re-review the plan's Open assumptions as code reveals new facts (assumptions are recorded at plan time but never checkpointed mid-build). Note: digest-vs-CLAUDE.md duplication is handled separately by the review-fixes plan Chunk 4 (slim framework-repo digest); this item is the within-file redundancy pass. Token-budget guardrail tests on methodology files will need adjusting downward, not up. (builder)

- **[JNT-9R2K]** Janitor SKILL: move the investigation-theme taxonomy to a companion reference file; close the Step 2.5 to Step 7 backlog loop
  `effort: S · impact: S · area: janitor · source: builder · added: 2026-06-09 · status: open · refs: skills/janitor/SKILL.md`

  From the 2026-06-09 framework review (skills agent). (1) The nine investigation themes (~100 lines, ~50% of the skill) read once per janitor run — move theme details to a bundled companion file (the pattern the Critic already uses with review-protocol.md etc.) and keep SKILL.md as dispatcher + process. (2) Clarify that Step 2.5 Backlog Health emits read-only NOTE findings and Step 7 Reconcile is where those findings drive /prawduct:backlog update calls — the linkage is currently implicit. (3) Reframe the 'fresh eyes' line toward pattern-detection + infer-and-confirm, and say what to do when the user cannot confirm a preference divergence (file a backlog item rather than resolving unilaterally). (builder)

- **[WMK-7D3R]** Work-model index never rebuilds on artifact deletion — retired vocabulary lingers
  `effort: S · impact: S · area: work-model · source: builder · added: 2026-06-09 · status: open · related: WMK-1P4Q · refs: bin/prawduct-hook, lib/work_model_index.py`

  From the 2026-06-09 framework review. The staleness check (bin/prawduct-hook, build-index path) compares
  remaining artifact mtimes to the index mtime, so deleting an artifact never triggers a rebuild and its
  vocabulary lingers between sessions. Mostly masked by build-index force=True at SessionStart — decide
  whether to fix (include the artifact file-set in the staleness fingerprint) or document the SessionStart
  rebuild as the intended guarantee. Note: probe precision (false positives on common English) is separate,
  covered by the review-fixes plan Chunk 2. (builder)

- **[STH-5R2Q]** Flag-only `prawduct-hook` subcommands silently ignore unknown positional arguments
  `effort: S · impact: M · area: governance/cli · source: builder · added: 2026-06-10 · status: open · refs: bin/prawduct-hook · related: STH-9V4K`

  `prawduct-hook audit-learnings` (and any flag-only subcommand) silently ignores unknown positional
  arguments; this hid a test bug where `tmp_path` was passed positionally and the real repo was audited
  instead (found 2026-06-10 during review-proportionality ch.04). Tighten flag-only subcommand arg
  parsing to reject unknowns, matching ledger-append/review-stats/classify-diff-risk fail-closed arg
  handling. (builder)

## Promoted

- **[CRT-6F2N]** `critic-begin` runs before the designer-handoff skip, so a designer-handoff chunk leaves the marker set
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-08 · status: promoted · reviewed: 2026-06-09 · related: CRT-3X9D`

  Critic SKILL.md step 1 runs `prawduct-hook critic-begin` right after mode resolution, but a
  `Type: designer-handoff` chunk exits clean *before* step 8 (`critic-end`), so the
  `.prawduct/.critic-active` marker is left set on that path. Benign — the marker self-corrects
  three ways (30-min TTL, session-start sweep, explicit override) — and rare, but ideally
  `critic-begin` should run only after the designer-handoff skip is ruled out (move the
  `critic-begin` call below the skip, or pair the skip with a `critic-end`). Surfaced as a NOTE in
  the CRT-3X9D cumulative review. (critic, 2026-06-08)

- **[PR-5K8D]** check-pr-doc-only should exclude skills/ (and methodology/templates) — align with `_classify_trivial_change`'s bounds
  `effort: S · impact: M · area: pr/governance · source: reflection · added: 2026-06-08 · status: promoted · reviewed: 2026-06-09 · related: PR-9T4M · refs: skills/pr/SKILL.md, lib/buildplan_refs.py, lib/coverage.py`

  The two PR fast-path classifiers disagreed on skill files. On the backlog-legend-refresh PR (#83),
  `check-pr-doc-only` returned exit 0 (all 4 files `.md` → "gates may be skipped"), which per the
  `/pr` Step 1b instruction would skip the independent PR reviewer entirely — but `check-pr-trivial`
  correctly returned "not-trivial: skill-file-edited: skills/backlog/SKILL.md. Full review required."
  A fork-skill's SKILL.md IS behavior/logic (per the existing learning "when a feature's logic lives
  in a context:fork skill, lib/ holds DATA not LOGIC"), so an extension-only doc-only classification
  under-reads a behavioral skill change and can skip review.

  Re-anchored 2026-06-08 (branch fix/retire-pr-trivial-fast-path): `check-pr-trivial` /
  `_pr_diff_is_trivial` were DELETED when the PR-boundary trivial fast-path was retired (see
  PR-9T4M). The original fix-shape pointed at `check-pr-trivial` as the model to copy; that
  classifier is gone. The canonical exclusion bounds still live in `lib/buildplan_refs.py`
  (`_classify_trivial_change` / `_TRIVIAL_PROTECTED_PATHS` — `{skills/, methodology/, templates/,
  CLAUDE.md}`), now consumed only by the chunk-level `_is_trivial_fileset_eligible` gate
  (`lib/gates.py`). This item is now MORE relevant, not less: with the trivial fast-path retired,
  `check-pr-doc-only` (`lib/coverage.py`, hook `cmd_check_pr_doc_only`) is the ONLY remaining
  PR-boundary gate-skip path, and it still under-reads behavioral `skills/*.md` changes. Candidate
  fix (re-anchored): align `check-pr-doc-only`'s fileset bounds with `_classify_trivial_change` —
  exclude `skills/`, `methodology/`, `templates/`, and `CLAUDE.md` from the doc-only fast-path so a
  behavioral-prose change still gets the reviewer; consume the shared `_TRIVIAL_PROTECTED_PATHS`
  rather than re-listing the bounds. refs: skills/pr/SKILL.md (Step 1b/1c), lib/coverage.py
  (check_pr_doc_only), lib/buildplan_refs.py (_classify_trivial_change). Filed from the v2.0.16
  release (2026-06-08). (reflection)

- **[BLD-2R9X]** `verify-chunk-refs` over-matches glob paths (`*.md`) written as prose in a build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-06-05 · status: in-progress · branch: fix/verify-chunk-refs-globs · related: BLD-8F2Q, BLD-5V8F`

  **Resolved on branch.** `_looks_like_file_path` (`bin/prawduct-hook`, the single semantic gate the
  chunk-ref parser consults) now returns False for any backticked token carrying a shell-glob
  metacharacter (`*`, `?`, `[`) — a literal source path never contains one, so a glob written in prose
  (e.g. a Tests bullet's `docs/requirements/*.md`) is skipped instead of reported `missing-ref`. Same
  parser family as the shipped BLD-8F2Q (`path::symbol`); symbol/backlog-ref verification stays
  deferred (BLD-5V8F). 4 regression tests in
  `tests/test_build_plan_resolution.py::TestVerifyChunkRefsGlobPaths` (each glob char + the per-token
  case where a real path on the same line is still captured). Statusless change-log entry on-branch;
  flips to `merged` at develop-merge, `shipped` at release, then this item archives.

- **[REL-8K3M]** `/pr` cumulative-Critic gate false-positives (benign exit-1) on a develop→main RELEASE promotion
  `effort: S · impact: S · area: release · source: reflection · added: 2026-06-06 · status: in-progress · branch: fix/pr-release-redirect · related: CRT-7M2D`

  **Resolved on branch (fix-shape a+b, no gate-logic change).** `skills/pr/SKILL.md` gained a
  release-promotion guard (on `develop`/`main` → redirect to `docs/release-process.md`, don't run the
  feature-PR gates); `docs/release-process.md` gained a "`/prawduct:pr` is not the release vehicle"
  section explaining the benign `check-cumulative-critic` exit-1 is neither a gate to re-satisfy (the
  CRT-7M2D treadmill) nor a waiver case. Fix-shape (c) — broadening the CRT-7M2D allowance to version/
  derived-view files — was rejected (weakens a correct global gate to patch a context-misuse). 2 guard
  tests in `tests/test_pr_reviewer.py::TestPrReviewSkillContent`. Change-log entry is statusless
  on-branch (avoids the regen-views typo-guard); gains `status=merged` at feature→develop merge and
  `status=shipped` at the develop→main release, then this item archives.

  Original report: the `/prawduct:pr` Step 2 gate is feature→develop shaped and exit-1'd during the
  v2.0.13 release because release-prep touches non-`.md` version files (version strings +
  `regen-views`-regenerated `scope_rollups`) outside CRT-7M2D's docs-only allowance. (reflection)

## Archive


- **[CRT-4J8W]** P0 — review-phase wall clock: accept a cumulative + verify-resolutions CHAIN at the PR gate
  `effort: M · impact: L · area: governance/gates · source: user · added: 2026-06-10 · status: shipped · closed-by: gate-soundness ch.05 (commits 9618c2b + 78fadaf) · reviewed: 2026-06-10 · stage: ready · related: CRT-7M2D · refs: lib/gates.py (check_cumulative_critic), skills/critic/SKILL.md, skills/critic/review-protocol.md, tests/test_cumulative_gate.py`

  User escalation 2026-06-10: review phase ran 30+ min wall clock for ~5 min of work. Two cost
  drivers: unit cost per review (fixed same day — reviewers default to model opus, ~4x faster per
  the reviewer-model-ab-2026-06-10.md experiment) and the **re-review treadmill**: every non-.md fix
  after a cumulative review re-stales `check-cumulative-critic` and costs a FULL bundle re-review
  even when only 2 files changed. Structural fix (the option deferred in gate-soundness ch.4 as
  "build if it recurs" — it recurred the same session):
  1. When `/prawduct:critic verify-resolutions` runs while the existing `.critic-findings.json` is a
     clean cumulative record, embed an `extends_cumulative: {commit_reviewed: <X>}` anchor in the
     new record.
  2. `check_cumulative_critic` accepts EITHER a HEAD-covering cumulative record (today's rule) OR a
     chain: `mode=verify-resolutions`, 0 blocking, `commit_reviewed==HEAD`, `extends_cumulative`
     present, AND files changed in `X..HEAD` ⊆ the record's `files_reviewed` (fail closed on any
     gap, same as today).

  Soundness argument: cumulative@X vouches for the bundle; a clean delta review whose scope covers
  `X..HEAD` extends that vouching to HEAD — same shape as the existing doc-only allowance, with
  scope verification. Surfaces: `lib/gates.py` (`check_cumulative_critic` + findings schema optional
  field), `skills/critic/SKILL.md` + `review-protocol.md` (record the anchor),
  `tests/test_cumulative_gate.py` (chain accept/reject cases incl. scope-gap fail-closed),
  `methodology/building.md` + `skills/pr/SKILL.md` sequencing prose (update: the fix-after-cumulative
  path becomes a cheap delta review, not a full re-run). Priority P0. Related: CRT-7M2D (the
  coverage-not-mtime gate this extends — archived/shipped). (user)

  — Shipped 2026-06-10 — Built as gate-soundness chunk 05 (commits 9618c2b + 78fadaf). Dogfooded on
  its own PR bundle: the chain record satisfied `check-cumulative-critic` live.

- **[PR-9T4M]** Trivial PR fast-path treats `bin/` + `lib/` (core runtime) as fileset-eligible — a core-runtime change can skip cumulative-Critic + reviewer
  `effort: S · impact: M · area: pr · source: builder · added: 2026-06-06 · status: shipped · closed-by: retire-pr-trivial-fast-path · reviewed: 2026-06-08 · related: STH-1W5N, BLD-2R9X`

  `_TRIVIAL_PROTECTED_PATHS` (`bin/prawduct-hook`) bounds the `Type: trivial` / `check-pr-trivial`
  fast-path to `{skills/, methodology/, templates/, CLAUDE.md}` — the governance *content* surfaces.
  It does NOT include `bin/` or `lib/`, which hold the framework's executable runtime — including
  `bin/prawduct-hook` itself (the ~4,369-line hook that *implements every gate*) and the `lib/`
  modules. Consequence (observed firsthand merging BLD-2R9X, a `bin/prawduct-hook` bugfix):
  `check-pr-trivial` returned exit 0 (`all fileset-eligible`), so the `/prawduct:pr` fast-path would
  have skipped BOTH the cumulative-Critic gate AND the independent reviewer for a change to the core
  gate-runtime. I declined the fast-path manually and ran the full review, but the next contributor
  may not. A bug in `bin/prawduct-hook`/`lib/` can break gating itself, so it is arguably *more*
  catastrophic-blast-radius than a `templates/` edit, not less. Fix-shape: add `("bin/", False,
  "runtime-edited")` and `("lib/", False, "runtime-edited")` to `_TRIVIAL_PROTECTED_PATHS` (single
  source of truth — both the stop-hook `_is_trivial_fileset_eligible` and the PR-boundary
  `_pr_diff_is_trivial` consume it), with tests in `tests/test_trivial_fileset_gate.py`. Open
  question: is a doc/comment-only edit to a `bin/`/`lib/` file (no logic change) worth exempting, or
  keep the bound coarse (any `bin/`/`lib/` touch → full review)? Coarse is safer and simpler. Filed
  from the BLD-2R9X merge on 2026-06-06. (builder)

  — Resolved 2026-06-08 (branch fix/retire-pr-trivial-fast-path) — Closed by retiring the entire
  PR-boundary trivial fast-path (`check-pr-trivial` / `_pr_diff_is_trivial` removed) rather than the
  narrower proposed fix (adding `bin/`/`lib/` to `_TRIVIAL_PROTECTED_PATHS`). With the whole
  PR-boundary fast-path gone, there is no longer any path where fileset-eligibility skips BOTH review
  gates — retiring the unsound predicate supersedes the narrower patch. Note: the chunk-level
  `Type: trivial` fileset bounds still omit `bin/`/`lib/`, but `Type: trivial` does NOT skip the
  Critic gate at the chunk level, so no gate-skip risk remains there.

- **[CRT-7B4M]** infer-critic-mode pins to Chunk 01 on a feature branch with views_enabled (derived checkboxes never flip)
  `effort: S · impact: S · area: critic · source: builder · added: 2026-06-08 · status: shipped · closed-by: critic-mode-branch-fix · reviewed: 2026-06-08 · stage: requirements`

  On a feature branch with views_enabled, build-plan ## Status checkboxes are a derived view that only flips at release, so they stay [ ] for every chunk during branch development. prawduct-hook infer-critic-mode reads the first unchecked [ ] as the current chunk → always resolves to Chunk 01, so a multi-chunk plan's later chunks all inherit Chunk 01's declared Critic mode (final, in backlog-rework) regardless of the chunk's own declared mode. Observed across all 10 backlog-rework chunks: passing an explicit /prawduct:critic <mode> arg was the workaround. Not harmful (final is the safe direction) but it makes per-chunk Critic-mode declarations inert on a branch and the mode_chosen_by rationale misleading. Research-stage: investigate whether inference should consult git-committed-chunk-count or the plan's own chunk ordering rather than the derived checkboxes. Surfaced during backlog-rework (2026-06-08).

- **[BKL-2F7K]** Ship the three remaining §8.2 backlog probes (`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`)
  `effort: L · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 06) · reviewed: 2026-06-08`

  v1.7.0 shipped only `legacy-backlog-format` (the first production probe). The other three §8.2 probes are deferred — no product today has an external backlog file, an old-section-schema backlog, or a stale-grooming signal worth nagging. Build when one does. Each registers against the v1.6.0 advisory infrastructure via `register_probe("backlog", …)` in a new `lib/` probe module via `lib/advisory_store.register_probe` (the file-sync `tools/lib/backlog_probes.py` was deleted in M4) and resolves off a `project-state.yaml` fact: `external-backlog-detected` → `backlog_external_imports` (set by `/backlog import`); `legacy-section-schema` → reuse `backlog_format_version: 2` (migration folds the old `## Active`/`## Queue` headings); `backlog-overdue-grooming` → `backlog_last_groomed_at` + the 90-day window (spec §8.2). Tune the >5-item / >20-item / 90-day thresholds against a real product's backlog before shipping. (builder)

- **[BKL-3R8P]** `/backlog dedup` — surface and merge near-duplicate items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 04) · reviewed: 2026-06-08`

  Requirements §4.3. A subcommand that finds candidate duplicate items (title/area/keyword overlap) and proposes merges, preserving both bodies. Not on the path to the §1 user-facing test ("pick a high-value item in 30 min"), so deferred from lean core. The `add` subcommand already does inline dedup-on-create; this is the after-the-fact sweep. (builder)

- **[BKL-5H9M]** `/backlog import <path>` — convert an external TODO/BACKLOG file into structured items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 08) · reviewed: 2026-06-08`

  Requirements §4.3/§8.4. Resolves the `external-backlog-detected` probe ([BKL-2F7K]) by writing `backlog_external_imports` to `project-state.yaml`. Heuristically converts each bullet/list item in the named file into a `[PFX-XXXX]` entry (`source: user`, `status: open`, area inferred), always confirming before writing. Deferred with its probe — this repo has no external file to import. Build alongside [BKL-2F7K]'s `external-backlog-detected`. (builder)

- **[BKL-1V8J]** prawduct-doctor setup-time external-backlog report
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 08) · reviewed: 2026-06-08`

  Requirements/advisory-spec §8.3. At setup/health-check time, `prawduct-doctor` reports any external backlog files (`TODO.md`, `BACKLOG.md`) found in repo root + `.github/`. Redundant with the `external-backlog-detected` probe ([BKL-2F7K]); deferred with it — build both together or decide one supersedes the other. (builder)

- **[BKL-6L3Q]** Build-plan hygiene-step guidance in `templates/build-plan.md` + `methodology/building.md`
  `effort: S · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 09) · reviewed: 2026-06-08`

  Requirements §5.3, decision D9. Document the backlog-hygiene step (at chunk close, review open items in the chunk's area and update status explicitly — the framework never infers status from plans/change-logs, per D4) in the build-plan template's Done-when prose and in `methodology/building.md`. Cheap, but no probe or check depends on it in lean core, so filed rather than shipped. The v1.7.0 plan already dogfoods the step informally (chunk close-out includes "backlog hygiene"); this makes it a documented standard. (builder)

- **[CRT-3K9P]** The four backlog Critic checks C-B1–C-B4
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 05) · reviewed: 2026-06-08`

  Requirements §7. Four soft NOTE-level Critic checks for backlog hygiene (e.g. C-B3: a chunk touches an area with open backlog items but its Done-when has no backlog-hygiene step). Decision D1 made them NOTE-level; deferred because adding governance friction to *every* product's Critic run before there's evidence of need is the least proportional piece of the feature (success criterion S6 watches for fatigue). Build when backlog-hygiene drift actually shows up in reviews. (builder)

- **[JNT-7T1W]** Janitor Step 2.5 — Backlog Triage (incl. Q2 archive-split)
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 07) · reviewed: 2026-06-08`

  Requirements §6. Add a backlog-triage step to the janitor: flag stale `status: open` items (`reviewed`/`added` >90d), surface neglected `## Promoted` items whose owning chunk shipped, and — the Q2 decision — when `## Archive` exceeds ~200 entries, propose splitting it to `backlog-archive.md` (with `/backlog find` spanning both files). Deferred from lean core; build when a product's backlog is large enough that grooming friction is real. (builder)

- **[CRT-7M2D]** Cumulative-Critic gate judges commit-coverage, not mtime-recency
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-04 · status: shipped · closed-by: #65 (v2.0.9) · related: STH-6B4R`

  `check-cumulative-critic` now passes iff the cumulative record covers HEAD (`commit_reviewed == HEAD`,
  or only `.md` changed since), instead of judging mtime vs `.session-start` — closing the false-pass
  (a stale record passing over real code changes) AND the post-review re-run treadmill (inert doc fixes
  no longer force a full cumulative re-run). New `tests/test_cumulative_gate.py` (8 real-git tests; the
  gate previously had none); doc wording swept "fresh" → "HEAD-covering". Dogfooded on its own PR #65
  (doc-only post-review fixes stayed covered, no re-run). Shipped v2.0.9. (builder)

- **[REL-4T8N]** Release tooling: handle MULTIPLE release-pending plans (regen-views per scope) instead of a single `active_build_plan` pointer
  `effort: M · impact: M · area: release · source: builder · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  The release model assumed ~one release-pending plan between `develop→main` releases: `regen-views`
  resolved THE plan via the single `active_build_plan` pointer. Batched sub-releases stack up (v2.0.5
  shipped four scopes), so the release had to point the pointer at each plan in turn and `regen-views`
  per scope — 4× tedious, easy to miss one. It also surfaced a SECOND symptom: the derived
  `release-notes.md` rendered only one entry per `release=` tag, mis-aggregating all scopes of a
  release under one heading with a union'd chunk list.

  **Resolved #62 (v2.0.6):** Chunk 01 (REL-4T8N-A) — `regen-views` now enumerates every change-log
  `scope=` (status ∈ {shipped, merged}), resolves each to its build-plan file via frontmatter `scope:`
  (`build_scope_to_plan_map`), and regenerates every release-pending plan in one pass (per-plan scope
  re-detection → no cross-scope leakage; single-plan back-compat preserved; also fixed a latent
  can't-run exit-2 state). Chunk 02 (REL-4T8N-B) — `release-notes.md` renders each distinct scope as
  its own `### ` sub-section (group-by-scope; same-scope collapses; single sub-release stays flat). The
  open "scope→file" question was answered by the existing frontmatter parser. (builder)

- **[BLD-8F2Q]** `verify-chunk-refs` misreads `path::symbol` backtick tokens as missing file paths
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  The chunk-ref parser (`bin/prawduct-hook` `cmd_verify_chunk_refs` / `_parse_build_plan_chunk_refs`)
  captured a whole backtick token like `lib/views.py::is_views_enabled`, saw the `/`, and treated the
  entire `module.py::symbol` string as a (missing) file path → false-positive exit 1 even though the
  file exists. **Resolved #62 (v2.0.6):** the parser splits on `::` and existence-checks only the
  pre-`::` path (stored as the ref); symbol verification stays deferred (BLD-5V8F). The `new ` forward-
  ref exclusion still composes; 6 net-new tests. (critic)

- **[PR-7Q3M]** Condition PR-skill merge-flow step 7 (build-plan deletion) on whether the develop-merge is itself the release
  `effort: M · impact: M · area: pr · source: user · added: 2026-06-02 · status: shipped · closed-by: #62 (v2.0.6) · related: BLD-3X9M`

  Under the v2.0 gitflow batched-release model, release-bound work merges feature→develop ahead of the
  develop→main release, where the release runs `regen-views` ON the build plan. Deleting the plan +
  clearing `active_build_plan` at develop-merge time left the release nothing to regenerate; step 7 also
  hardcoded `artifacts/build-plan.md`. **Resolved #62 (v2.0.6):** step 7 branches on `prawduct-hook
  resolve-base` — base = release surface (`main` family) → delete the plan (resolved via the pointer,
  not a hardcoded path) + clear the pointer; base = `develop` (release-pending) → RETAIN both until the
  release. Dogfooded on this very PR's merge (base=develop → retained). (user)

- **[TST-9K4W]** Structural tests scan `.claude/worktrees/` — leftover/in-flight workflow worktrees fail the suite
  `effort: S · impact: S · area: tests · source: builder · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  `test_test_location::test_all_test_files_live_under_tests_directory` and
  `test_plugin_methodology_digest::test_source_is_one_canonical_copy` globbed the whole repo tree, so a
  worktree-isolated workflow's leftover `.claude/worktrees/wf_*/` checkout (duplicate test/methodology
  copies) failed both. **Resolved #62 (v2.0.6):** both collectors prune the `.claude/` path component
  (and take a `root` param for testability); regression tests via synthetic worktree trees + a real-tree
  simulation. Layer-2 `norecursedirs` was deliberately skipped (collection is already scoped by
  `testpaths=["tests"]`). (builder)

- **[BLD-7P3K]** Guard test: assert the active build plan's chunk headings parse (fail loud on heading-format drift)
  `effort: S · impact: M · area: build-plan · source: critic · added: 2026-06-04 · status: shipped · closed-by: #61 (v2.0.5) — shipped test-only; runtime-check-for-any-product variant not pursued · related: VWS-3K7P`

  Recommended by `learnings.md` ("Build-plan chunk headings must use `### Chunk N:` colon form") AND
  twice by the roi-batch-2 cumulative Critic after the build plan itself shipped with `#### Chunk NN:`
  (four-hash, under a `### Lane` grouping level) — which silently defeated the `### Chunk ` parsers
  (`verify-chunk-refs`, `_parse_build_plan_chunk_type`, `lib/critic_mode.py` plan-override) for the
  WHOLE plan. The degradation is silent: chunk-type fail-closes to `code`, refs stop verifying, and
  nothing errors. Fix-shape: a test (or a `regen-views`/stop-hook check) that resolves the active
  build plan via `resolve_build_plan_path` and asserts its `## Status` chunk IDs each map to a
  parseable `### Chunk <id>:` heading — so a depth/format mismatch fails LOUDLY instead of degrading.
  Open question: test-only (pins the framework's own plan) vs. a runtime check that fires for any
  product's active plan. Filed from roi-batch-2 Critic NOTE on 2026-06-04. (critic)

- **[SYN-9C4T]** Extract shared `read_bool_yaml_key(state_path, key)` from `lib/views.py::is_views_enabled` and `bin/prawduct-hook::_read_bool_yaml_key`
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-06-03`

  Both perform the same column-0 boolean scan against `project-state.yaml`, intentionally duplicated to keep the hook flat (one inline ~10-line helper vs. a new lib import). Move to `lib/core.py::read_bool_yaml_key(path, key) -> bool` and call from both sites. **Now more actionable (re-verified 2026-06-03):** the file-sync `product-hook` named in the original NOTE was deleted in M4; the duplicate survives in the plugin runtime as `bin/prawduct-hook::_read_bool_yaml_key` (line ~3331, comment says "kept parallel to is_views_enabled in lib/views.py") against `lib/views.py::is_views_enabled` (line ~651). The third caller the original NOTE said would tip this to extraction is already here — `_read_bool_yaml_key` now also reads `coverage_required` (bin/prawduct-hook ~3464). Filed from /critic chunk NOTE on 2026-05-19 (Chunk 09); paths refreshed post-M4. (critic)

- **[TST-5W1J]** Cache test-file contents in `bin/test-reference-verify` to drop O(N*T) re-reads
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-19 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  `_has_reference` re-opens every test file once per changed file. Sub-second on framework scale (~20 test files × small chunk diffs) but a stronger verifier or larger product would feel it. Fix-shape: discover_tests reads all test contents into a dict once, then `_has_reference` runs substring across the cached text. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 08). (critic)

- **[PRR-4M9T]** Trim PR-reviewer goals to remove Critic overlap
  `effort: S · impact: S · area: pr-reviewer · source: builder · added: 2026-05-05 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  PR reviewer Goals 1, 2, 4, 5, 6 in `skills/pr/review-protocol.md` overlap with Critic. Now that the layering is explicit (Critic-chunk = local; Critic-final = synthesis; PR reviewer = release readiness), PR reviewer goals could be trimmed to release-specific concerns (narrative, scope, merge hygiene, simplification). Filed during proportional-Critic build plan as out-of-scope. (builder)

- **[CRT-4W8M]** Critic check: byte-exact assertions for "no behavior change" refactors
  `effort: S · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  When a refactor's explicit bar is "no behavior change," substring-level test assertions are insufficient. Discodon graph_ops refactor (Apr 16) had two silent text drifts (double-prefix, error message wrapper) that substring assertions missed and Critic caught only by reading the code. Evidence: discodon/reflections.md §2026-04-16 graph_ops. Candidate: add to skills/critic/review-protocol.md for Refactor work type — "If the chunk claims no behavior change, are output assertions exact-match (not substring/contains)? If not, flag WARNING." (reflection)

- **[MET-7H2D]** Testing guidance: multi-hop edge-case tests
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-04-08 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  When a data structure or state machine's correctness depends on what happens on the NEXT invocation (accumulator, coordinator, cursor, stateful retry), tests that only check post-state miss multi-hop bugs. Discodon has repeatedly shipped bugs caught only by the next cycle (Apr 8 accumulator, Apr 15 V0.5-7a timestamp collision under prune). Evidence: discodon/reflections.md §2026-04-08 "What I'd do differently". Candidate: add a bullet to methodology/building.md §Test Discipline — "When tested behavior depends on subsequent invocations (next cycle, next call, next prune), exercise at least one additional step beyond the immediate post-state." Broadly applicable; no detection heuristic needed. (reflection)

- **[TST-6V2N]** test-evidence freshness gate reads `.test-evidence.json` but the plugin ships no command to WRITE it
  `effort: M · impact: M · area: tests · source: user · added: 2026-06-04 · status: shipped · closed-by: #60 (72c4081, develop) · related: TST-5W1J · reviewed: 2026-06-04`

  Filed by a Hallucinote session (`incoming-bugs/test-evidence-gate-reads-a-file-the-plugin-doesnt-write.md`)
  and **confirmed firsthand** in roi-batch-2: the plugin has a READER (`cmd_test_status` freshness check +
  the cumulative-Critic staleness flag + `cmd_validate_evidence` schema check) but NO command that RUNS the
  suite and PRODUCES `.test-evidence.json` (timestamp + `git_sha` + passed/failed/skipped/duration + the
  F4a fields). `bin/test-reference-verify` writes only the F4a half (`changes_referenced`/`coverage_level`)
  via `--merge-into`; nothing writes the pytest half. Under the retired file-sync model `product-hook`
  wrote it; post-plugin-migration it's a reader without a writer. roi-batch-2 had to hand-author the
  passed/failed/git_sha/timestamp JSON and manually merge F4a — exactly the friction the prior roi-batch
  handoff flagged ("no automated test-evidence writer is wired up"). Hallucinote improvises with a local
  `tools/stamp_evidence_sha.py` shim; every product repo reinvents this. Worse, the gate's `git_sha` check
  is satisfiable by a post-commit stamp over STALE counts — nothing ties the recorded counts to a real run.
  Fix-shape: add a `prawduct-hook test-evidence record [-- <pytest args>]` subcommand that runs (or wraps)
  the suite, captures real `passed/failed/skipped/duration`, stamps `git_sha = HEAD` + ISO timestamp, calls
  `test-reference-verify --merge-into` for the F4a half, and writes atomically — so the freshness gate
  judges output the plugin itself produced + ties counts to an actual run. Watch the pytest-count parse
  (no native JSON without a plugin; parse the summary line or use exit-code + `--json-report`). Until then,
  ship the sha-stamp+schema as a documented helper so repos don't each reinvent it. Filed 2026-06-04. (user)

- **[VWS-3K7P]** Validate change-log `status=` values + reconcile views.py docstring
  `effort: M · impact: M · area: views · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/views.py parse_tag_line accepts ANY status= string; only `status=shipped` flips checkboxes, so a typo (e.g. `status=shippd`) silently never flips and emits no warning — a real release-process footgun. Also the views.py module docstring (~line 19) lists status values as `shipped|in-progress|deferred` but the actual convention (docs/release-process.md, learnings.md, roi-batch entry) uses `merged` for the release-pending intermediate; in-progress/deferred are not emitted today. Fix-shape: add a pure `validate_status_values(entries) -> list[str]` helper in views.py recognizing {shipped, merged} (warn on others) and have bin/prawduct-hook cmd_regen_views print the warnings; sync the docstring to {shipped, merged}; never change the flip rule (only shipped flips). + tests. The DOC half (defining the enum in release-process.md) already shipped in a28ccaa; this is the code half. (janitor)

- **[STH-2J9F]** regen-views returns exit 0 on ImportError (silent degradation)
  `effort: S · impact: M · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  bin/prawduct-hook cmd_regen_views (~line 3673-3683) catches `from lib import views` ImportError, prints a NOTE, and returns 0 — but it is a state-mutating command, and other mutating commands (accept-operator-verification, verify-operator-verification) return 1 on ImportError per the honest-failure pattern. A user on a broken install sees exit 0 and assumes views regenerated. Fix-shape: return 1 for ImportError, keep 0 for the disabled-by-config path. + test. (janitor)

- **[STH-6B4R]** Gate freshness timestamp comparison is lexicographic / tie-ambiguous
  `effort: M · impact: M · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  The stop-hook Critic gate (bin/prawduct-hook ~2579-2594) and check-cumulative-critic (~3616-3627) compare ISO-8601 string mtimes (`.session-start` vs findings mtime). Same-second ties are ambiguous and the precision contract is undocumented/untested. Fix-shape: format both sides to identical %Y-%m-%dT%H:%M:%SZ precision and TEST the tie case (findings_mtime == session_start must be rejected as not-fresh), or switch to numeric epoch seconds. Document the tie-breaking rule. (janitor)

- **[TST-7Q3D]** Stop-gate regression coverage gaps (verify-resolutions, trivial-fileset, waiver unknown-key)
  `effort: M · impact: M · area: tests · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  TestPluginStopGate is missing three regression cases: (a) verify-resolutions mode out-of-scope file blocking — findings with files_reviewed=[a.py], diff modifies [a.py,b.py] -> assert exit 2 out-of-scope (bin/prawduct-hook ~2198); (b) Type: trivial chunk modifying files outside the allowed bounds -> assert exit 2 fileset reason (~2536-2564); (c) gate-waiver unknown key -> assert stderr diagnostic WITHOUT blocking (~2438-2447). All test-only, no runtime change. (janitor)

- **[TST-4H8M]** Unit coverage for migrate `_collapse_blank_runs` edge cases
  `effort: S · impact: S · area: tests · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/migrate_plugin.py _collapse_blank_runs (~264-273, added by MIG-8C3V) has no dedicated unit tests for 3/4/5/7+ consecutive newlines, only-newlines, empty string, or while-loop convergence (e.g. `a\n\n\nb\n\n\nc` -> `a\n\nb\n\nc`). Currently only covered indirectly via the end-to-end migrate test. Add a TestCollapseBlankRuns class. (janitor)

- **[VWS-8M2Q]** Harden lib/views.py tag/frontmatter parsers (quote-in-chunk-id, unclosed HTML comment)
  `effort: S · impact: S · area: views · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  Two low-impact parser corners in lib/views.py: (a) chunk IDs from parse_tag_line are quoted verbatim into scope_rollups YAML (~368-384) without escaping — a chunk id containing a quote (malformed tag) produces unparseable YAML; CHUNK_LINE_RE guards the build-plan file but not tag-line input. (b) _parse_build_plan_frontmatter_scope (~165-170) silently treats an UNCLOSED HTML comment block as missing frontmatter (returns (False,None)) rather than flagging it; the v1.5.1 R5 'explicit malformed-frontmatter test' was never added. Fix-shape: validate/escape chunk IDs (or yaml.safe_dump); raise or explicitly document unclosed-comment leniency + add the malformed-frontmatter test. (janitor)

- **[ADV-9K2T]** advisory_store read/write failures degrade silently (no corruption surfacing)
  `effort: M · impact: M · area: advisory · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/advisory_store.py best-effort read/write falls back to safe defaults on any failure, so a corrupted `.advisories.json` is silently reset with no signal — the user never learns their advisory state was lost. Fix-shape: on a parse/read failure, drop a `.advisories.json.corrupt` sentinel (or log) so corruption is surfaced on next session start for user-initiated recovery, instead of silently swallowed. (janitor)

- **[STH-1W5N]** Centralize the trivial-change protected-path bounds into a documented constant
  `effort: S · impact: S · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · related: STH-4D2X · reviewed: 2026-06-04`

  The Type: trivial / doc-only fileset bounds (skills/, methodology/, templates/, CLAUDE.md, test deletions, new files) are enforced inline in bin/prawduct-hook (~3120-3180) with no central spec. Extract to a documented module-level `_TRIVIAL_PROTECTED_PATHS` frozenset (lib/core.py or bin/prawduct-hook) with a rationale per path, referenced from all call sites. Relates to STH-4D2X (the `.claude/skills/` bound question). (janitor)

- **[TST-1D5W]** Tighten `_validate_evidence_schema` against bool-as-int
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-05 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  Python's `bool` is a subclass of `int`, so `{"passed": True}` slips through `isinstance(v, int)` in the test-evidence validator. No real test runner emits booleans for these fields, so impact is theoretical, but the loophole is real. If addressed: add `or isinstance(v, bool)` exclusion to the type check (with a comment), and add a `TestValidateEvidenceSchema::test_bool_rejected_for_int_field` case. Filed from /critic NOTE on 2026-05-05. (critic)

- **[CRT-3M8Q]** `/critic` ignores the build plan's per-chunk `Critic mode:` override — Skill-tool args don't thread to `$ARGUMENTS`, so a plan-mandated `final` silently runs as inferred `chunk`
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-06-01 · status: shipped · closed-by: #58 (befd69b, develop) · related: CRT-1F7N · reviewed: 2026-06-04`

  The `/critic` skill ignores the build plan's per-chunk `**Critic mode:**` field, and Skill-tool args don't thread to its `$ARGUMENTS`, so a plan-mandated `final` override silently runs as inferred `chunk` mode. Discovered in v2.0.0 Chunk 9 (a destructive cutover whose plan overrode the mode to `final`): the independent Critic ran clean goals 1-3 twice but goals 4-7 were never run by the agent (`mode_chosen_by: rule-4`, not `explicit-args`). The methodology already says the per-chunk `Critic mode:` should be a "successive override," but the skill doesn't read it and the Skill-tool args never reach the forked skill, so the override is inert. Fix-shape: (a) have the `/critic` skill read the active build plan's per-chunk `**Critic mode:**` field as an override (matching the methodology's "successive override" intent), and/or (b) fix Skill-tool args reaching the forked skill's `$ARGUMENTS`. Type: process/governance. Priority: medium. Filed from v2.0.0 Chunk 9 reflection on 2026-06-01. (reflection)

- **[BLD-4Q9X]** `scope: null` in build-plan frontmatter does not suppress change-log inference
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-23 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Surfaced by v1.5.1 Chunk 05 cumulative Critic. The template ships `scope: null` as the documented opt-out form, and `_parse_build_plan_frontmatter_scope` correctly returns `None` for null literals. But `_detect_active_scope` then treats "key present with null" identically to "key absent" — it falls through to change-log inference, picking up the most-recent `scope=` tag. Result: a product with a tagged release in change-log.md (e.g. `scope=v1.5`) plus a fresh `scope: null` build-plan with new chunks 01/02/03 will see `regen-views` flip those chunks to `[x]` because v1.5's tagged entries claim chunks 01/02/03. Author's explicit-null intent ("don't filter") is overridden silently. Fix-shape: distinguish "key absent" from "key present with null/empty" in `_parse_build_plan_frontmatter_scope` (return a sentinel or change to `tuple[bool, str | None]`); have `_detect_active_scope` skip inference when key was explicitly null. Doesn't bite the framework's own v1.5.1 plan (sets `scope: v1.5.1` explicitly). Filed from /critic cumulative WARNING on 2026-05-23 (v1.5.1 Chunk 05). (critic)

- **[TST-2R7H]** Add fixture coverage for `cumulative-final`/`cleanup` Type fall-through to default gate
  `effort: S · impact: M · area: tests · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Code analysis confirms only `designer-handoff` skips the Critic gate; the other Type values (`code`, `doc-only`, `cleanup`, `cumulative-final`) all fall through to the default gate path. But no dedicated test fixture pins this — `TestDesignerHandoffSkipsCriticGate` only covers the explicit skip branch. A refactor that accidentally broadens the skip list (e.g. `if chunk_type in {"designer-handoff", "doc-only"}`) would silently regress. Fix-shape: add a parametrized `TestNonHandoffTypesFallThroughToGate` covering the four fall-through Types. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MIG-8C3V]** migrate's CLAUDE.md transform leaves a double blank line at the top of the migrated file
  `effort: S · impact: S · area: migration · source: user · added: 2026-06-02 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  When `apply_claude_anchor` strips the framework generator comments via `_drop_generator_comments` (`lib/migrate_plugin.py`), it removes the comment lines but leaves the blank line that preceded them adjacent to the blank line that followed, producing two consecutive blank lines between the H1 title and the first product section. Cosmetic only (markdown collapses it on render), zero semantic impact, but it's a wart in a diff meant to be pristine. Found during the v2.0.0 1.x→2.x migration acceptance test against ../discodon (2026-06-02). Fix: collapse 3+ consecutive newlines to 2 in the assembled CLAUDE.md, or drop blank lines left adjacent to removed generator comments. Low priority / trivial. (user)

- **[MET-4K8Z]** 8-surface cascade pattern — anticipate token-budget pressure in chunk plans
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Chunk 05's source-of-truth guardrail threading touched 8 surfaces (product-claude / Critic SKILL / 2 critic-review / 2 pr-review / methodology / build-plan template). Same pattern Requirements Precede Code (v1.3.15) hit. When a chunk introduces a project-wide structural concept, the plan should enumerate the surface count up front so token-budget bumps (and the aggressive trim that precedes them) are anticipated, not discovered. Worth promoting to methodology after one more datapoint; until then, captured as observation. Filed from Chunk 05 reflection, 2026-05-18. (reflection)

- **[MET-1T5W]** Document the `new \`path\`` forward-ref convention in methodology prose
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `verify-chunk-refs` (F3) supports `new \`path/to/file\`` syntax to mark forward-references for not-yet-created files; this is implemented, tested, and documented inside `templates/build-plan.md`'s inline HTML comment, but not in `methodology/planning.md` prose. Authors who write plans without copying the template won't know the keyword exists and will get spurious BLOCKING ref-drift findings for chunks creating new files. Fix-shape: add a one-paragraph "Forward-references" note to planning.md near the build-plan-structure section. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-8N2C]** Tighten F8 worked-example numbering language for consistency
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `methodology/planning.md:118` describes the `verify-api` step as "the first item in its Done-when", while the worked example a few lines down uses "step 0" (`0. verify-api: ...`). Both true, but the terminology is inconsistent. Fix-shape: change line 118 to "prepended as step 0 in its Done-when (so existing step numbering is preserved across chunks with and without a foreign API)". One-line tweak. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-2D9K]** `methodology/planning.md` parallel section for the `Visual change:` build-plan field
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  F8 added a "Foreign API Verification" section to planning.md when introducing `**Foreign API:**`. F10 (Chunk 14) added `**Visual change:**` to the build-plan template with inline-comment guidance but no parallel planning.md section. The build-plan template's HTML comment is sufficient discoverability for v1.4.0; consider a v1.5 enhancement (~50 tokens) to align with the F8 precedent and pre-empt the asymmetry NOTE the Critic emitted. Filed from /critic Chunk 14 final review NOTE. (critic)

- **[DOC-2W9P]** Repoint stale `tools/lib/` example paths in `documentation/` design specs to plugin-native
  `effort: S · impact: S · area: docs · source: builder · added: 2026-06-03 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `documentation/post-sync-advisory-spec.md` (≈ lines 197/218/276/296/434/435) and
  `documentation/governance-tax-followups.md` §3 still illustrate the advisory/probe layout with
  retired file-sync paths (`tools/lib/probes/…`, `tools/product-hook`, `prawduct-setup.py`, `run_sync`).
  The spec is still the authoritative reference for `lib/advisory_store.py`, so the illustrative paths
  should point at `lib/advisory_store.py` / `hooks/hooks.json` / `bin/prawduct-hook`. Internal design
  archive, not user-facing — deferred from the 2.0-rock-solid pass Wave 2. (builder)

- **[ADV-3K7Q]** Namespace skill names in plugin advisory output (briefing recommended_action + dismiss hint)
  `effort: S · impact: S · area: advisory · source: critic · added: 2026-06-03 · status: shipped · closed-by: #53 (12e03b3, v2.0.3) · reviewed: 2026-06-03`

  Surfaced when the advisory-probe-at-SessionStart fix made post-sync advisories visible in plugin repos for the first time. The briefing rendered un-namespaced skill forms (`/backlog migrate`, `/prawduct-advisory dismiss`) where a plugin repo resolves `/prawduct:backlog` / `/prawduct:advisory`. info-priority/cosmetic; not a broken gate.

  **Shipped (#53 — `fix(plugin): namespace all agent-facing command forms in the plugin runtime`, commit `12e03b3`, in develop/v2.0.3):** the runtime gate-message + advisory-output sweep landed. `bin/prawduct-hook` now renders `/prawduct:advisory` (0 bare `/prawduct-advisory` remain) and `/prawduct:critic`/`/prawduct:pr` in every agent-facing gate; `lib/operator_verification.py`'s `/pr create` stragglers namespaced. Pinned by `TestPluginRuntimeNamespacing` (assert-absent source-scan) + strengthened stop-gate/divergence tests. The byte-parity-lock half (`backlog_probes` → `DIVERGED_MODULES`) is moot: `lib/backlog_probes.py` and its frozen `tools/lib/` twin were both deleted in M4 (v2.0.3, Chunk 3) along with the `legacy_backlog_format_probe`, so source #1 no longer exists. The stale standalone branch `origin/fix/advisory-namespace-backlog` (single commit, same title/SHA-content as #53) was superseded by the merged PR and can be deleted. (Triage 2026-06-03 — the "do not archive until merged" hold is satisfied: the work is in HEAD.)

- **[CRT-2M5P]** Critic skill `Bash(git *)` allowed-tools is too broad — permits state-mutating git verbs (checkout/stash/reset/branch)
  `effort: S · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Observed v1.5.1 Chunk 05 verify-resolutions: the Critic ran `git checkout d2b8af4` (mid-review!), corrupted the working tree to a detached HEAD state, and recovered via stash+pop. All my modified files survived but only because the Critic chose to restore them. The skill `allowed-tools` entry `Bash(git *)` permits every git subcommand including ones that mutate the working tree. Read-only verbs are sufficient for Critic's review purpose. Fix-shape: replace `Bash(git *)` with an explicit allow-list of read-only verbs — `Bash(git diff *)`, `Bash(git log *)`, `Bash(git status *)`, `Bash(git show *)`, `Bash(git ls-files *)`, `Bash(git rev-parse *)`, `Bash(git merge-base *)`, `Bash(git branch --show-current)`, `Bash(git for-each-ref *)`. Or, more concise, add a deny-list (subject to the same v1.5.1 Chunk 02 caveat that skill-frontmatter denies may not enforce). Filed from /critic verify-resolutions NOTE on 2026-05-23 (v1.5.1 Chunk 05). (critic)

  **Resolved (reduce-governance-tax Chunk E):** The Critic's `allowed-tools` now grants explicit read-only git verbs (diff/log/status/show/ls-files/rev-parse/merge-base/branch --show-current/for-each-ref) instead of the broad `Bash(git *)`, so a review can no longer run `git checkout`/`reset`/`stash` and corrupt the tree. Applied to `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`, and the `critic-test` shadow skill; pinned by `test_critic_skill_metadata.py::test_git_is_read_only`.

- **[CRT-8H3D]** v1.5.1 Chunk 02's `!Bash(pytest*)` deny patterns in skill `allowed-tools` do NOT structurally block pytest invocation
  `effort: M · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Confirmed by v1.5.1 Chunk 04 Critic WARNING: the Critic agent ran `python3 -m pytest` despite the four deny patterns in `.claude/skills/critic/SKILL.md` `allowed-tools`. The patterns appear to be documentation-only; Claude Code's skill `allowed-tools` field is allow-list semantics and the `!`-prefixed deny syntax is not honored there (or is overridden by project-level `settings.local.json` `permissions.allow: ["Bash(python3:*)"]`). Fix-shape options: (1) move deny patterns to `.claude/settings.json` `permissions.deny` (project-wide block — but would also block the *builder* from running pytest, which is wrong); (2) scope deny via a wrapper command or use a tool-namespace filter the harness actually enforces; (3) accept that the constraint is prose-and-allow-list only (the allow-list IS restrictive — `Bash(python3 tools/product-hook ...)` exact-strings shouldn't match pytest in pure-allow mode), and soften the v1.5.1 change-log / memory rule claim of "structurally enforced". Add a deliberate negative-path probe test before claiming structural enforcement. Filed from /critic chunk WARNING on 2026-05-23 (v1.5.1 Chunk 04). (critic)

  **Resolved (reduce-governance-tax Chunk E):** Structural enforcement is the PURE-ALLOW list (the `!Bash(...pytest*)` entries are documented as non-functional). Added the negative-path probe the item asked for: `test_critic_skill_metadata.py::test_no_allow_pattern_permits_pytest` asserts no allow pattern can match a pytest invocation. The skill comment already softens the 'structurally enforced' claim to name the allow-list as the real mechanism.

- **[SYN-2K9N]** Template drift advisory dismiss/acknowledge mechanism
  `effort: M · impact: M · area: sync · source: critic · added: 2026-04-16 · status: shipped · closed-by: reduce-governance-tax Chunk B · reviewed: 2026-05-30`

  **Resolved** by the template-drift fire-once fix (Chunk B of the governance-tax reduction): a drift advisory now surfaces exactly once per template change, then sync refreshes the stored template hash so it self-resolves — directly fixing the "nags every session" pathology. This is a cleaner fix than the proposed `dismissed_advisories` list / `/janitor dismiss` flow: place-once files are user-owned ("surface the change once, then it's yours"), so auto-resolving after one surfacing matches the semantics without new dismiss machinery. The user's place-once file is never overwritten. (critic)

- **[BLD-9R3K]** `infer-critic-mode` does not detect a build plan living in `.prawduct/artifacts/`
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-29 · status: shipped · closed-by: v1.6.0 Chunk 06 · reviewed: 2026-05-29`

  During v1.6.0 Chunk 02 the helper returned `rule-4 final: no active build plan ... fail-safe to thoroughness` even though `.prawduct/artifacts/v1.6.0-advisory-infrastructure-plan.md` is the active plan. **Resolved** by Chunk 06's `active_build_plan:` pointer (project-state.yaml) + the shared `core.resolve_build_plan_path` resolver, mirrored inline in product-hook and used by `infer-critic-mode`, `regen-views`, the stop-hook gates, `verify-chunk-refs`, and `check-pr-trivial`. The chosen shape is the explicit pointer (not the `*plan*.md` glob the original fix-shape proposed — a glob is ambiguous when multiple scope-named plans accumulate, which this repo demonstrates). Validated against both the framework repo (pointer → scope-named plan) and the back-compat default (no pointer → `build-plan.md`). Filed from /critic NOTE on 2026-05-29 (v1.6.0 Chunk 02); closed 2026-05-29 (v1.6.0 Chunk 06). (critic)

- **[JAN-4F7M]** Rewrite `skills/janitor/SKILL.md` "Template Currency" theme for plugin distribution
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-06-03 · status: resolved · reviewed: 2026-06-04`

  The janitor skill's **Template Currency** investigation theme (and its Step 1 framework-health
  pre-check + Step 7 hash-update guidance) still teaches the file-sync maintenance workflow:
  comparing the consumer's place-once artifacts against `framework_source/templates/*` via
  `.prawduct/sync-manifest.json` `place_once_templates` stored hashes. Under plugin distribution a
  consumer carries no sync-manifest (init never creates it; `/prawduct:migrate` removes it) and has
  no `framework_source` checkout, so the whole theme is inert for migrated/plugin-native repos.
  Surfaced during M4 Chunk 4: `test_v5_templates.py::TestJanitorSkillTemplateCurrency` (which pinned
  this content via the now-deleted `templates/skill-janitor.md`) was DELETED rather than retargeted,
  precisely to avoid pinning stale guidance. Resolve: rework the theme for plugin-era maintenance —
  what does "is this product's tooling current with the plugin?" mean when governance ships from the
  plugin and updates via `autoUpdate`? — and add fresh `skills/janitor/SKILL.md` structural coverage
  to replace the deleted mirror test. Candidate to fold into M4 Chunk 5 (docs/residue) if cheap, else
  a standalone janitor-skill pass. Filed from M4 Chunk 4 on 2026-06-03. (builder)

  **Resolved (v2.0.3 pre-promotion, 2026-06-04):** reworked the Template Currency theme for plugin
  distribution — it now compares the product's artifacts against the read-only plugin templates at
  `${CLAUDE_PLUGIN_ROOT}/templates/` (no `sync-manifest.json`, no `framework_source`, no place-once
  hash store). The Step 1 framework-health pre-check now confirms the plugin runtime is reachable
  (`${CLAUDE_PLUGIN_ROOT}/templates/` readable) instead of asserting a sync-manifest exists; Step 7
  records resolved drift in `.prawduct/change-log.md` rather than recomputing template hashes.
  Structural coverage restored via `test_plugin_runtime.py::TestJanitorSkillPluginEra` (asserts no
  `sync-manifest`/`framework_source`/`place_once` residue + the plugin-root target). The same pass
  also cleaned the file-sync-era `_METADATA_PREFIXES` entries (`.claude/skills/`, `tools/product-hook`)
  from both mirrors (`bin/prawduct-hook` + `lib/critic_mode.py`) — a product's own `.claude/skills/`
  skill now counts as gated code, not excused metadata (`TestMetadataPathClassification`). Surfaced by
  the develop→main release-readiness review; folded into v2.0.3 rather than deferred. 652 passing. (builder)

- **[DOC-7H2K]** Port `/prawduct:doctor`'s remaining file-sync-coupled flows to the plugin model (Chunk 13)
  `effort: L · impact: M · area: doctor · source: builder · added: 2026-06-02 · status: resolved · reviewed: 2026-06-02`

  Surfaced during v2.0.0 Chunk 11 (dogfood + self-containment audit). The plugin's `skills/doctor/SKILL.md` is a thin wrapper over `python3 <framework>/tools/prawduct-setup.py` for nearly every flow: Onboard (`setup`), Health Check (`validate`), Migrate feature opt-ins (`migrate --enable-coverage|--enable-settings-layout|--enable-operator-verification`), and Audit Learnings (`audit-learnings`). In a migrated consumer there is no framework checkout, so all of these break — only the **Verify** flow was ported this chunk (new `prawduct-hook verify-operator-verification`, which operates purely on the consumer's `.prawduct/`). The rest were deliberately NOT ported because (a) `setup`/`validate` ARE the file-sync engine, which design §5 / Chunk 5 deliberately excludes from the plugin runtime — bundling them would re-introduce exactly what the architecture removes; and (b) the plugin onboarding model is "install the plugin + `/prawduct:migrate`", not a `setup` script. Resolve as part of Chunk 13 (remove file-sync + its name): rework the doctor skill to the plugin model — Onboard → install + `/prawduct:migrate`; Health Check → a plugin-native `prawduct-hook` validate/health read of the consumer's own `.prawduct/` (no framework path); coverage / operator-verification opt-ins → plugin-native `project-state.yaml` flag flips (need no sync); decide whether `--enable-settings-layout` (pure file-sync settings normalization) and `audit-learnings` survive in the plugin world. Also: `lib/operator_verification.py::run_verify_entry`'s "no queue" error hint still names the legacy `prawduct-setup migrate --enable-operator-verification` path — repoint once the plugin-native enable exists. And the legacy `agents/` tree ships inside the plugin and the loader picks it up as frontmatter-less agents (`claude plugin validate` warnings) — Chunk 13's grep-sweep across `agents/` should drop it. Filed from Chunk 11 dogfood on 2026-06-02. (builder)

  **Resolved (Chunk 13, 2026-06-02):** all four flows reworked off file-sync — Onboard → install + `/prawduct:migrate`; Health-Check → plugin-native Read/Glob of the consumer's own `.prawduct/`; opt-ins (F4/F10) → `project-state.yaml` flag flips (F5 settings-layout dropped as file-sync-only); Audit-Learnings → new plugin-native `prawduct-hook audit-learnings` (port of `lib/audit_learnings_cmd.py`). Operator-verification hint repointed off `prawduct-setup migrate`. The legacy `agents/` tree dropped (clears the 6 `claude plugin validate` frontmatter warnings). `/prawduct:doctor` `allowed-tools` tightened (broad `Bash(python3 *)` removed). Confirmed by the Chunk-13 Critic (NOTE 2). (builder)

- **[MIG-M4-REMOVE]** Permanently delete the file-sync engine + payload + shims (post-2.0.0 milestone M4)
  `effort: L · impact: M · area: distribution · source: builder · added: 2026-06-02 · status: shipped · closed-by: M4 (v2.0.3) · reviewed: 2026-06-03`

  The terminal step of the file-sync→plugin transition, deliberately deferred out of 2.0.0. Chunk 13 removes file-sync only from THIS repo's active path; the engine stays a **live service** for un-migrated external repos, because `tools/product-hook` + `tools/lib/*` are `MANAGED_FILES` synced into products and a product's own `try_sync()` calls back to this framework's `tools/prawduct-setup.py sync` every session (fail-soft: missing script ⇒ no crash, the sibling keeps governing on its last-synced version). **Blocked on:** marketplace live (Chunk 2) AND every local sibling migrated to the plugin (`/prawduct:migrate`). Inventory is the owner's — manual, "only this one machine"; no consumer census / deprecation advisory is being added (owner decision 2026-06-02, keep 1.x frozen). When unblocked: delete `templates/`, the 7 `.claude/skills/*` sync sources, `tools/product-hook`, `tools/lib/*` (sync modules), `tools/prawduct-setup.py`, and the `prawduct-{init,sync,migrate}.py` shims; finish the deep name-sweep across the (now-removed) `templates/`+`tools/` — *you can only remove a mechanism's name from a path once the mechanism has left it.* After M4, a stale un-migrated sibling fails-soft (silent no-update), an acceptable terminal contract because it was warned during M3. See build-plan Chunk 13 "Permanent-removal path (M1–M4)". **Cleanup rider (Chunk 13 Critic NOTE 1, 2026-06-02):** the plugin `lib/audit_learnings_cmd.py` is byte-parity-locked to `tools/lib/audit_learnings_cmd.py`, so its `run_audit_learnings` docstring still names the legacy `prawduct-setup audit-learnings` path (correct for the file-sync copy, stale for the plugin). When `tools/lib/` is deleted here, the parity lock dissolves — repoint that docstring to `prawduct-hook audit-learnings`. (builder)

  **Resolved (M4, v2.0.3, 2026-06-03):** the owner directive (2026-06-03, "we DO NOT need backwards compatibility … remove ANY cruft that exists only for back compat to pre-2.0") lifted the consumer-census block — the inventory is "only this one machine," all local siblings migrated. M4 (5 chunks on `feat/retire-filesync-engine-m4`) executed the full removal: Chunk 2 deleted `tools/` (product-hook, prawduct-setup.py, the 3 shims, `tools/lib/`), Chunk 4 deleted the file-sync templates (`product-claude`/`critic-review`/`pr-review`/`build-governance`/`product-settings.json`/`conftest.py` + the 7 `skill-*.md` sources) and slimmed `lib/core.py`, Chunk 5 removed the committed `.prawduct/` protocol-doc residue + swept the deep name-sweep across kept code/docs/templates. The `run_audit_learnings` docstring rider was discharged (repointed to `prawduct-hook audit-learnings`, Chunk 5). Deferred fragment: `[JAN-4F7M]` (the janitor skill's file-sync Template Currency theme). (builder)

- **[BLD-3X9M]** Resolve `status=shipped` semantic — per-chunk merge vs. tagged release
  `effort: S · impact: M · area: build-plan · source: builder · added: 2026-05-18 · status: resolved · reviewed: 2026-06-02`

  Chunk 05 dogfooding raised an open question: does `status=shipped` on a change-log tag line mean "merged to mainline" (per-chunk timing — Status flips `[x]` when the chunk commits) or "in a tagged release" (wave timing — Status flips when a release entry covers it)? Current state: Chunk 05 left `[ ]` pending Wave 2 release entry. The Critic check (mismatch → WARNING) is symmetric, so either interpretation is internally consistent once chosen. Decide before Wave 2 release; document the chosen semantic in `templates/change-log.md` schema doc. Filed from Chunk 05 work, 2026-05-18. (builder)

  **Resolved (v2.0.0 Chunk 14, 2026-06-02):** decided as **tagged-release / wave timing** — `status=shipped` means "in a tagged release" and flips Status `[x]` only at the `develop → main` release; `status=merged` is the develop-phase intermediate that does NOT flip checkboxes. Documented in `docs/release-process.md` (release checklist + "Why the checkboxes stay `[ ]` during development") and the v2.0.0 build-plan "Checkbox model" note. (Schema-doc home moved from `templates/change-log.md` to `docs/release-process.md` under the plugin model.)

- **[DOC-4B2W]** Namespace bare command forms in plugin-bundled teaching prose (`skills/critic/*.md`, `methodology/*.md`)
  `effort: M · impact: M · area: docs/governance · source: builder · added: 2026-06-03 · status: shipped · closed-by: M4 Chunk 1 (v2.0.3) · reviewed: 2026-06-03`

  **Resolved (M4 Chunk 1, v2.0.3, 2026-06-03):** swept the 6 plugin-only prose files (`methodology/{building,planning,reflection}.md`, `skills/critic/{review-cycle,review-protocol}.md`, `skills/pr/review-protocol.md`) → `/prawduct:*`; pinned by `TestPluginDocsNamespacing` (assert-absent source-scan over the skill vocabulary). Decision (point 3): conceptual short-names ARE namespaced in the teaching prose, since a plugin repo resolves `/prawduct:*`. File-path carve-outs (`.prawduct/critic-review.md`) and the built-in `/clear` preserved; the file-sync `tools/` copies that carried duplicated prose were deleted outright in Chunk 2 rather than kept on bare forms. (builder)

  The runtime gate-message sweep (#53) namespaced `bin/prawduct-hook` + `lib/` agent-facing OUTPUT, but the plugin-bundled PROSE an agent reads via `/prawduct:*` still carries ~34+ bare command forms — `skills/critic/review-cycle.md`, `skills/critic/review-protocol.md`, and `methodology/{building,planning,reflection}.md` say "run /critic", "/pr create", "/critic cumulative" etc. where a plugin repo resolves `/prawduct:critic`, `/prawduct:pr`. Same leak class as #53, larger + lower-severity surface (teaching prose, not gates; agents can often infer the mapping, and the SessionStart briefing already lists namespaced forms). This is the "entire leak class as a build plan" follow-up.

  Scope notes for the build plan: (1) sweep the whole FORM-FAMILY per the new learning — bare `/cmd`, hyphenated `/prawduct-advisory`, legacy `prawduct-setup` — one grep per spelling; (2) preserve carve-outs: file paths (`.prawduct/critic-review.md`, `agents/critic/SKILL.md`), the Claude Code built-in `/clear`, and prose like "critic/pr skills"; (3) DECISION REQUIRED — whether to namespace conceptual short-names in teaching guides at all, or keep `/critic` as the canonical short name with a one-time namespacing note (judgment call, raise with owner); (4) the frozen `tools/` copies of any duplicated prose stay bare; (5) pin with an assert-absent source-scan like `TestPluginRuntimeNamespacing`, extended to the docs surface. (builder)

- **[SYN-3D8K]** Align `enable_v1_4_views` detector/mutator on inline-comment forms
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: dropped · reviewed: 2026-05-29`

  Same pattern Chunk 10 fixed in `enable_v1_4_coverage`: `is_views_enabled`-style detection strips inline comments via `split('#', 1)`, but `enable_v1_4_views`'s flip uses exact `line.strip() == "views_enabled: false"`. A user line like `views_enabled: false  # opt-out` is detected as present-and-off but never flipped → silent no-op (manifest flag still set, file unchanged). Edge case (templates emit bare values), but the asymmetry will keep biting until both helpers use the same shape-aware match. Apply the Chunk-10 fix-shape: iterate lines, skip indented, compare comment-stripped value, re-attach inline comment on rewrite. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 10) — the views variant was left alone in-chunk to keep diff scope tight. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the enable_v1_4_views mutator/flip lived in the deleted sync engine; only the is_views_enabled reader survives and it isn't the buggy path.

- **[BLD-0G6V]** Backfill Done-when blocks on Chunks 05-14 of v1.4 build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  Chunks 00-04 each carry a Done-when block; Chunks 05-14 do not. Not a chunk-close blocker (chunk-mode Critic still fires on declared `**Critic mode:**`), but worth backfilling for consistency before Chunk 06 starts. Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — backfilling Done-when on the long-shipped v1.4 plan has no consumer.

- **[BLD-7A2E]** Capture pre-commit-regen scope-shift in Wave 2 retrospective / change-log
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  F1 plan line 234 promises "pre-commit regen of build-plan Status from work-log"; Chunk 05 shipped on-demand `regen-views` plus methodology docs that tell users to invoke manually (Chunk 06 plan note confirms this is deliberate as "ad-hoc regen between commits"). The deliverable line was flagged "high level — to be expanded before chunk starts" so this is not silent, but the Wave-2 release entry / retrospective should record the explicit decision: pre-commit hook (deferred to Chunk 07's migration tooling or Wave-3) vs. on-demand `regen-views` (shipped now). Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the v1.4 Wave-2 retrospective window is closed; the decision shipped.

- **[DOC-6P3Q]** v1.4 release-readiness: document the new `/pr create` gate before tagging
  `effort: S · impact: M · area: docs · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  F2 ships hard enforcement: `check-cumulative-critic` blocks `/pr create` without a fresh cumulative-mode findings file. Product owners who sync v1.4 without reading the change-log will hit the gate cold and read it as a regression. Before tagging v1.4 (after all waves merge): add a change-log entry naming the new gate, a `prawduct-doctor` migration prompt if relevant, and a Compatibility-Strategy line in the release notes (the cumulative gate is new structural enforcement, not a behavior tweak). Filed from /critic cumulative NOTE on 2026-05-18. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the 'before tagging v1.4' window is closed; the /pr cumulative gate shipped and is live.

- **[SYN-7L0D]** Remove dead `if rel_path in ("CLAUDE.md",)` lines in sync_cmd.py `template`-strategy branch
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-08 · status: dropped · reviewed: 2026-05-29`

  Two pre-existing branches (`force=True` overwrite + `current_hash != stored_hash` skip) emit a "re-read CLAUDE.md" note guarded by `if rel_path in ("CLAUDE.md",)`. CLAUDE.md uses `block_template`, not `template`, so it can never reach these branches. Dead since the strategy split. Remove or document. Filed from /critic chunk on 2026-05-08 — flagged after the same dead pattern was caught in the new stale-clean branch (already removed there). Two-line cleanup; defer until next sync_cmd.py touch. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the dead CLAUDE.md branch lived in the deleted sync_cmd.py.

- **[SYN-3F6P]** Sync: skip-summary line counts + `--diff` preview flag
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-05-08 · status: dropped · reviewed: 2026-05-29`

  When sync skips a file as "local edits," it gives no signal about the size or shape of the divergence — the user must `--force` blind or manually diff. Add to the skip note: `+N lines / -M lines vs current template`. Add a `--diff` flag that prints the unified diff(s) of would-be skips (or all would-be changes) without writing anything. For `block_template`, also note that content outside markers won't change. Lets users decide whether to force without a separate investigation. (reflection)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — pure file-sync `sync` UX (--diff/--force/skip-summary); the sync engine is gone.

- **[TST-8B3X]** Audit public-function coverage exemptions in `tests/preferences/test_public_function_coverage.py`
  `effort: M · impact: S · area: tests · source: builder · added: 2026-05-05 · status: dropped · reviewed: 2026-05-29`

  Four functions in `tools/lib/` are exercised transitively but never directly referenced as a function call (under the tightened detection that requires `Attribute.attr` or `Name` in `Call.func`): `core.py::log`, `core.py::load_json`, `migrate_cmd.py::strip_test_tracking`, `migrate_cmd.py::generate_sync_manifest`. For each, decide: (a) add a direct unit test class, or (b) rename to `_<name>` (private-by-convention) and remove from the exemption list. Rationale captured inline in `EXEMPT_FROM_DIRECT_COVERAGE`. (builder)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — two of the four named functions were in the deleted tools/lib/migrate_cmd.py and the exemption list referenced the old tree (a fresh public-function-coverage audit against lib/ can be re-filed if wanted).

- **[SYN-5G2J]** Extract `_git_run` helper for fw-dir git lookups
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-01 · status: dropped · reviewed: 2026-05-29`

  `_get_framework_head_commit`, `_get_template_last_change` (sync_cmd.py), and the inline `git log -1` inside `_compute_framework_freshness` (product-hook) share the same try/except + subprocess.run + timeout=10 + broad-except + None-on-failure pattern. Three is the minimum-viable case for extraction. If a fourth fw-dir git lookup gets added, factor into `tools/lib/core.py` as `_git_run(fw_dir, args, timeout=10) -> str | None`. Currently small and well-commented; not urgent. (critic, 2026-05-01)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the three _git_run call sites were framework-dir freshness probes in the deleted sync_cmd.py/product-hook.

- **[SYN-3T7B]** run_sync() decomposition
  `effort: M · impact: M · area: sync · source: janitor · added: 2026-04-16 · status: dropped · reviewed: 2026-05-29`

  Extract per-strategy logic (template, block_template, always_update, merge_settings) from 337-line function in sync_cmd.py. (janitor)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — run_sync() was the deleted sync_cmd.py dispatcher; no 2.0 analog.

- **[TST-1M6V]** Pre-existing timeout flakes in test_product_hook.py
  `effort: M · impact: S · area: tests · source: builder · added: 2026-04-16 · status: dropped · reviewed: 2026-05-29`

  `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` intermittently hit the 15s timeout. May need investigation into why the product-hook subprocess hangs in certain test configurations. (builder)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** both named tests were removed with the file-sync engine in M4 — `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` (manifest = file-sync) no longer exist.


