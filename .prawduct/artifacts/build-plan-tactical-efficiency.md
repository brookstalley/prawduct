---
artifact: build-plan
version: 2
scope: tactical-efficiency
depends_on:
  - artifact: tactical-efficiency-analysis-2026-08-13
  - artifact: kernel-v3-evidence-design
governed_by:
  - artifact: architecture
    dispositions:
      - "independent reviewer never mutates the session it reviews → conforms (no reviewer write path changes)"
      - "authority fails closed; advice fails soft → conforms, and it is the design spine of Chunk 01: any git failure, missing object, or condition miss denies the transfer and the uncovered verdict stands"
      - "local-first, no network/daemon → conforms (git plumbing and files only)"
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state, the evidence store, and the named reconcile files → [DECISION: Chunk 06 is advisory-only — doctor RECOMMENDS the .gitattributes line and prints it verbatim, never writes it, because .gitattributes is not in the permitted write set | engages the norm's why: unexpected framework writes are the trust breach | user can override by amending the norm to add .gitattributes to the reconcile set]"
      - "prawduct is Python but never Python-specific → conforms (all changes are git-level or prose)"
      - "prawduct guides and reviews; it never implements product code → conforms"
      - "goals and verification bind; prescribed method is advice → conforms; chunk Deliverables below are the author's best guess and a builder finding a better route records why"
      - "every fact has one home → conforms: the transfer verdict is computed, never stored; the cache is a keyed memo, not a second home for any fact"
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, never from mutable model-written state → conforms; no model output enters any new write path"
      - "facts are immutable and append-only → conforms (no new fact kinds; nothing edited in place)"
      - "derived views are disposable and never authoritative — no gate reads a view to reach a verdict → [DECISION: Chunk 02's cache is memoization of the pure verdict function, keyed on a content hash covering EVERY input (base tree, head tree, evidence-store content); a key miss or unreadable cache recomputes from the store, so the cache can never substitute for it | engages the norm's why: a stale view must not decide a gate | user can veto the cache entirely]"
      - "newer-schema facts surface as a loud block → conforms (schema-ahead precheck untouched, and it runs before any cache read)"
      - "two stores, two lifetimes → conforms: the cache lives with the per-clone gitignored nags-and-caches, never in committed state"
      - "a governance document reaches a terminal state, never deleted; live outranks archived → engaged at plan close, not by any chunk: this plan is archived with `archive-plan --state completed` in the closing PR (Governance Checkpoints). Chunk 06 additionally strengthens the live-outranks-archived half — an archived plan's `branch:` frontmatter is ignored by the resolver, so moving a plan under `archive/` ends its claim"
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules on every write path → conforms; enforced rather than asserted: all backlog writes here go through `/prawduct:backlog`, whose adapter refused a 95-char title on the #654 filing and rewrote it before writing"
      - "`backlog_service_repo` selects the authoritative backlog store; once set, `.prawduct/backlog.md` is frozen history → conforms: every backlog touch in this plan (#565, #283, and the items filed from review findings) routes through the skill, which reads the scalar; nothing in this plan reads or writes the markdown file"
last_validated: 2026-08-13
---

## Requirements Confidence

**Level:** High

**Why:** The problem is measured, not inferred — `tactical-efficiency-analysis-2026-08-13.md`
quantifies each pain (12.4 h reviewer wall-clock / 4 days in the busiest consumer; >90% of
findings non-blocking; 2 of 3 cumulatives on one branch caused purely by base movement; gate
calls timing out at 120 s). Success criteria and scope-outs are stated per chunk. The mechanism
was read before planning (coverage_algebra, gates, coverage, critic_consolidate, both review
protocols); no fast-moving or post-cutoff dependency exists.

**Open assumptions / unknowns:**

- [ASSUMPTION: Chunk 01 requires current test evidence (`tests_are_current`) as a transfer
  condition, so the suite vouches for semantic interaction with the advanced base | MED impact |
  user can override to drop or weaken the condition]
- [ASSUMPTION: Chunk 04's severity ceiling for non-load-bearing prose applies in `chunk`,
  `final`, and `cumulative` modes alike (verify mode is already blocking-only) | MED impact |
  user can restrict it to cumulative-only]
- [ASSUMPTION: Chunk 07 stays advisory-only per the architecture write-set norm (see governed_by
  DECISION) | LOW impact | user can amend the norm to allow the write]
- [ASSUMPTION: Chunk 06 keeps the `active_build_plan` scalar as a working fallback rather than
  deprecating it in this pass — consumer migration is a follow-on | MED impact | user can widen
  to full scalar retirement]

**What would raise confidence:** Nothing pending — the veto window on the assumptions above is
the remaining input.

## Status

- [x] Chunk 01: Base-advance coverage transfer — a clean base sync no longer voids review coverage
- [x] Chunk 02: Coverage-verdict memo — the PR gate answers in constant time
- [x] Chunk 03: Disposition-aware reviews — accepted findings stop being re-litigated
- [ ] Chunk 04: Prose findings priced honestly — severity ceilings, deletion-first remedies, no archaeology
- [ ] Chunk 05: Verify-resolutions golden path at every point of action
- [ ] Chunk 06: The plan declares its branch — active-plan resolution goes branch-scoped
- [ ] Chunk 07: Advisory recommends union-merge for the append-only change-log
Context: Plan authored 2026-08-13 by the Fable analysis session (Chunks 06–07 added same day
after owner feedback: doctor is rarely run → advisory surface; active plan is branch state →
Chunk 06). Nothing built yet. Executes on Opus. Parent evidence:
`tactical-efficiency-analysis-2026-08-13.md` — read it before Chunk 01; each chunk cites its
finding (F1–F7). Backlog: #565 is closed by Chunk 01 (shipped), #283 by Chunk 06 (archive in the
closing PR, not after). Branch: build on `feat/tactical-efficiency-pass` off `develop`;
`active_build_plan` points here (Chunk 06 is what makes that scalar legacy; this plan opts into
`branch:` frontmatter once Chunk 06 lands).

Chunk 01 landed 2026-08-13 (review `rev-20260813T150910Z-86134e56` + two verify passes, final
state 0 findings). Two of its blocking findings were soundness holes in the per-file equality
check that only a hostile filename exposes — a glob-metacharacter path and a C-quoted non-ASCII
path — so `evidence.tree_diff` now sends `:(literal)` pathspecs and reads `-z` output. Two
findings were filed rather than built, both deliberate scope calls with their reasons on the
issues: **#654** (the Stop gate composes the same span and attempts no transfer, so a synced
branch passes the PR gate and is then blocked at session end) and **#655** (a transferred pass
emits no yield signal, against the standing control-observability norm).

Chunk 02 landed 2026-08-13 (`65b37539`; review `rev-20260813T161546Z-20da8706` + verify pass,
final state 0 findings). Profiled before building: the entire 29–120 s gate cost is
`coverage_verdict`'s free-edge search keying every tree the store mentions (17.4 s cold / 0.01 s
warm here), so the memo targets exactly that. Measured 20.0 s → 0.35 s on this repo. The Critic
caught that the memo's stated soundness precondition was not the one the call site established;
`read_facts` now hands back the fingerprint of the bytes it parsed, which makes the pairing
structural instead of documented. Five prose corrections from the verify pass are owed and
recorded in `.prawduct/.handoff-notes.md` — they are deferred only because a concurrent worktree
agent (#654/#655) holds those files.

Next: Chunk 03. Note Chunks 03–05 all edit the Critic/PR protocol prose, and every one of those
files sits within ~30 tokens of a guardrail ceiling.

## Scaffolding

Existing repo — no initialization. Suite: `python3 -m pytest tests/ -q` (the recorded
`test_command`); record evidence via `prawduct-hook test-evidence record`. Several governance
prose files carry token-budget guardrail tests — when a protocol edit trips one, **simplify or
deduplicate within the file first, raise the ceiling second, and never relocate text between
files to dodge a budget** (standing owner preference).

### Verification Strategy

Beyond unit tests: Chunks 01–02 are verified against throwaway fixture repos (temp git repos
exercising the real gate binary — the existing gate tests have this pattern; extend it, don't
invent a parallel one). Chunks 03–05 are verified by dispatching a real `/prawduct:critic` run in
this repo after the change and reading the manifest/report surfaces. Chunk 06 by running
`/prawduct:doctor` before/after.

## Build Chunks

### Chunk 01: Base-advance coverage transfer (analysis F1; closes #565)

- **Description:** When `check-cumulative-critic` would report `uncovered` after the base branch
  advanced, attempt a computed **transfer**: a previously covered span (base′ → head′, zero
  unresolved blocking on its path) transfers to the required span (base → HEAD) iff (1) the two
  spans' judgeable changed-file sets are identical; (2) for every such file `f`,
  `blob(HEAD,f) == blob(head′,f)` and `blob(base,f) == blob(base′,f)` — the branch's own diff is
  byte-identical and the advance touched none of its files; (3) `tests_are_current` holds for the
  merged tree. All three hold → the gate prints
  `satisfied (transferred across base advance <base′>→<base>; branch diff byte-identical; suite current)`
  and exits 0. Any condition unverifiable (missing object, git failure) → **no transfer, fail
  closed**, today's remedy block unchanged. Computed, never stored — the free-edge philosophy.
  **Soundness boundary (state it in the code where the check lives):** this is byte equality
  across contexts, NOT content equivalence within one — the 2026-07-29 ruling (#367) is
  untouched; any edit to a branch file, comments included, denies transfer.
- **Depends on:** none
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F1,
  `kernel-v3-evidence-design.md` (D4–D6 — the transfer must not weaken edge validity rules)
- **Deliverables:**
  - Transfer computation in `plugin/lib/coverage.py` (sibling to `diagnose_fix_churn` /
    `diagnose_stale_remote_base`), wired into `check_cumulative_critic` in `plugin/lib/gates.py`
    after the `uncovered` verdict and before the remedy block.
  - **Riders, same bundle:** `plugin/skills/pr/SKILL.md` — Step 1 gains the #565 ordering rule
    (if `merge-base(base, HEAD) != base` tip, sync base and resolve conflicts BEFORE Step 2, with
    the one-line why); Update flow states that a base-sync merge introducing no judgeable
    authored content does not re-run the PR reviewer, and that the transfer makes post-review
    syncs cheap. `plugin/skills/critic/review-cycle.md` PR-gate section documents the transfer in
    two sentences (cite the mechanism; don't restate the conditions — one home).
- **Tests:** fixture-repo tests for: clean transfer after conflict-free base merge; denial when a
  branch file was edited during the merge (byte inequality); denial when upstream touched a
  branch file (file-set overlap); denial when test evidence is stale; denial on missing git
  objects (fail closed); transfer after a rebase that preserves byte-identical diffs; and the
  existing `uncovered` behavior untouched when no prior covered span exists.
- **Acceptance criteria:** on a fixture branch reviewed-then-base-advanced with disjoint files,
  the gate exits 0 with the transfer message and dispatches nothing; on every denial fixture it
  exits 1 with today's remedy; full suite green.
- **Critic mode:** final
  <!-- Keystone override: this changes what a release gate accepts; coherence matters before
       later chunks build near it. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=tactical-efficiency`, no `release=`)
  3. `/prawduct:critic` run and blocking findings resolved
  4. `/prawduct:backlog update 565 status=shipped closed-by=tactical-efficiency`
  5. Committed and chunk marked `[x]` in Status

### Chunk 02: Coverage-verdict memo (analysis F2)

- **Description:** `check-cumulative-critic` costs 29–120 s per call and hit the 2-minute Bash
  ceiling twice in one consumer session. Memoize the composed verdict keyed on a content hash
  covering every input: (base tree, head tree, evidence-store content hash). Key hit → replay the
  stored verdict output; miss, unreadable, or any doubt → recompute from the store (see the
  governed_by DECISION — the cache may never decide what the store would not). Store under the
  per-clone gitignored cache area beside the evidence store. Transfer lookups from Chunk 01 are
  cacheable under the same key: git objects are content-addressed and immutable, so the key
  already covers them.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F2, `data-model.md`
  Direction (view-vs-verdict norm)
- **Deliverables:** memo layer in `plugin/lib/gates.py` (or a small sibling module if gates.py
  grows unwieldy), cache file management beside the evidence store
- **Tests:** hit replays identical output; store append invalidates; tree change invalidates;
  corrupted cache file recomputes without error; the schema-ahead precheck still runs before any
  cache read
- **Acceptance criteria:** second consecutive gate call on an unchanged repo completes in <2 s in
  the fixture; verdict output byte-identical to uncached; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: Disposition-aware reviews + real duplicate grouping (analysis F3)

- **Description:** Two changes that cut finding volume mechanically. (1) `critic-begin` joins
  ACCEPT/FILE disposition facts to their findings and writes a `prior_dispositions` block into
  the manifest (review id, fid, one-line title, disposition, reason). Both reviewer protocol
  files instruct: a dispositioned finding is not re-raised absent material change in its cited
  files — acknowledge it in one line under a `priors:` note instead (mirror of the existing
  `record_lint` "already answered — don't recount" pattern). (2) Strengthen
  `likely_duplicate_groups` in `plugin/lib/critic_consolidate.py` so three reviewers filing the
  same defect (observed: same file, same claim, `[]` groups) actually group — keep it advisory
  (the write-path-fuzzy-merge rejection stands), but have consolidation RENDER a group as one
  finding line with N attributions so the builder reads one defect, not three.
- **Depends on:** none (file overlap with Chunk 04 in the protocol files — build in order)
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F3
- **Deliverables:** manifest block in the `critic-begin` path (`plugin/bin/prawduct-hook` /
  `plugin/lib/critic_consolidate.py` wherever the manifest is assembled), grouping improvements
  in `critic_consolidate.py`, short protocol additions in `plugin/skills/critic/goals-1-3.md` and
  `plugin/skills/critic/review-protocol.md`
- **Tests:** manifest carries dispositions when facts exist and an empty block when none;
  malformed disposition facts are skipped loudly (fail toward inclusion of nothing, never a
  crash); the observed triplicate shape (three goals, overlapping files, same claim words) groups;
  disjoint genuine findings do not group; consolidation renders a group as one line
- **Acceptance criteria:** a live `/prawduct:critic cumulative` in this repo after an `--accept`
  shows the manifest block and the review does not re-raise the accepted finding; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 04: Prose priced honestly — severity ceilings, deletion-first remedies, no archaeology (analysis F4)

- **Description:** Protocol-and-policy edits, all prose, all in governance-protected files (this
  is a `code`-typed chunk — skill prose is behavioral logic here). Four rules, stated once each
  at the surface that owns them:
  1. **Severity ceiling** (`goals-1-3.md` Severity + `review-protocol.md` Goal 4 "Documentation
     drift" + `pr/review-protocol.md` severity notes): comment/docstring/doc wording, counts, and
     phrasing are **NOTE** unless load-bearing — referenced by a test or a gate, or the reviewer
     names the concrete wrong action a maintainer takes because of it (the existing WARNING bar,
     now applied to prose explicitly).
  2. **Remedy constraint** (same three surfaces, one sentence each citing the owner): for stale
     prose the permitted recommendations are **delete the claim, make it relational, or pin it
     with a test** — never "reword the narration," never "add a comment explaining the history."
  3. **Provenance ban** (`building.md` comment policy + one line in each protocol): review/finding
     IDs, chunk numbers, and review history never enter shipped comments; a comment narrating
     history is a deletion finding. ("Added because callers kept passing null" states a live
     constraint and stays legal; "previously this did X / Critic caught Y" does not.)
  4. **Builder-side sharpening** (`building.md`): history's one home is commits + change-log;
     extend the existing ephemeral-id rule with the archaeology line above.
  Expect token-budget guardrail tests on these files — trim by deduplication within the file
  (per Scaffolding note), and update any test that pins protocol wording ONLY where the pinned
  sentence itself changed (Tests Are Contracts — never weaken an assertion to make room).
- **Depends on:** Chunk 03 (same protocol files; sequencing avoids churn)
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F4
- **Deliverables:** edits to `plugin/skills/critic/goals-1-3.md`,
  `plugin/skills/critic/review-protocol.md`, `plugin/skills/pr/review-protocol.md`,
  `plugin/methodology/building.md`
- **Tests:** existing prose-guard tests updated where their pinned sentences changed; no test
  deleted or weakened without a change-log-recorded reason
- **Acceptance criteria:** the four rules each appear at their owning surface exactly once and
  read as one policy; token-budget guardrails green; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 05: Verify-resolutions golden path at every point of action (analysis F5)

- **Description:** The batch-fix discipline exists in `building.md` and consolidate output but
  not where agents act. Three point-of-action edits:
  1. `blocking_remedy_lines` (`plugin/lib/gates.py`) — the standard remedy becomes the golden
     path: fix ALL named findings in the working tree, do NOT commit between fixes, run ONE
     `/prawduct:critic verify-resolutions` (dirty-tree verify is sound), then commit the verified
     tree verbatim. Superseded-case variants keep their current routing.
  2. `goals-1-3.md` verify-mode Observations section — every observation is delivered pre-priced:
     ACCEPT is the default disposition; fixing any of these re-opens the gate and costs a round;
     batch survivors into an already-planned commit.
  3. `plugin/skills/pr/SKILL.md` Update flow — define "substantive": a delta that is only
     non-judgeable paths and/or a base-sync merge does not re-run the PR reviewer (closes the
     observed 520-second re-review of a CI comment + `.prawduct` records).
  Explicitly **not** built (analysis "What was deliberately not proposed"): a sincerity flag, and
  refusing verify dispatch when the delta is "only fixes" — the fixes live in judgeable files, so
  refusal would strand the gate uncovered.
- **Depends on:** Chunk 04 (shares `goals-1-3.md`)
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F5
- **Deliverables:** `plugin/lib/gates.py` (`blocking_remedy_lines` + its tests),
  `plugin/skills/critic/goals-1-3.md`, `plugin/skills/pr/SKILL.md`
- **Tests:** `blocking_remedy_lines` unit tests updated to the new wording (both callers render
  it — the one-home rule holds); prose guards as in Chunk 04
- **Acceptance criteria:** gate stderr on a blocking verdict prescribes the batch golden path;
  verify-mode report template carries the pricing line; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 06: The plan declares its branch — active-plan resolution goes branch-scoped (analysis F7; closes #283)

- **Description:** `active_build_plan` is branch state stored in a product-level scalar — two
  concurrent branches guarantee a same-line conflict, and after the merge one plan is invisible
  to every pointer-resolved surface. Invert the pointer: build plans gain optional frontmatter
  `branch: <name>`, and the resolver pair (`core.resolve_build_plan_path` + the parity-tested
  `bin/prawduct-hook` mirror — change BOTH, the parity test pins them) resolves in precedence
  order: (1) the live (non-archived) plan under `artifacts/` whose `branch:` matches
  `git branch --show-current`; (2) the `active_build_plan` scalar; (3) the conventional default.
  Existing repos behave unchanged until a plan opts in. **Two live plans claiming the current
  branch is a loud error** surfaced by the resolver's callers, never a silent pick (authority
  fails closed). Detached HEAD or a non-matching `branch:` falls through to (2)/(3); the session
  briefing names a live plan whose `branch:` matches no existing branch (advice, fails soft).
  Archive keeps working with less ceremony: moving a plan under `archive/` ends its claim, so
  `archive-plan`'s pointer-clearing becomes unnecessary for frontmatter-resolved plans (keep it
  for the scalar). NOT in scope: removing the scalar, migrating consumer repos, or touching the
  release-side scope enumeration (already pointer-free). Frontmatter scanning may open every
  live `artifacts/*.md` header — keep it cheap (first-KB reads) and note that Chunk 02's memo
  does not cover this path.
  Docs: `plugin/templates/build-plan.md` frontmatter gains `branch:` with a two-line comment;
  `plugin/methodology/planning.md` "Plan lifecycle" paragraph updated (the gitflow RETAIN story
  simplifies: a merged plan's `branch:` stops matching, so it reads live-but-inactive with no
  advisory to ignore); `plugin/skills/pr/SKILL.md` merge-flow pointer language updated.
- **Depends on:** none (touches `plugin/lib/core.py`, `plugin/bin/prawduct-hook`; independent of
  Chunks 01–05)
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F7
- **Tests:** branch-match wins over scalar; scalar still wins when no plan matches; default when
  neither; ambiguity (two live plans, same `branch:`) errors loudly; archived plan with matching
  `branch:` is ignored; detached HEAD falls through; parity test still pins resolver and mirror;
  this plan's own file gains `branch: feat/tactical-efficiency-pass` as the first opt-in
- **Acceptance criteria:** on this branch with the frontmatter added and the scalar left pointing
  at the purpose-and-cession plan, every pointer-resolved surface (briefing, `infer-critic-mode`,
  stop-hook gate trigger) resolves THIS plan; on develop nothing changes; suite green
- **Critic mode:** final
  <!-- Override: every governance surface resolves through this pair — coherence check before
       the last chunk rides on it. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. `/prawduct:backlog update 283 status=shipped closed-by=tactical-efficiency`
  5. Committed and chunk marked `[x]` in Status

### Chunk 07: Advisory recommends union-merge for the append-only change-log (analysis F6)

- **Description:** In both observed forced base syncs, 100% of merge conflicts were prawduct's
  own files, led by top-appended `.prawduct/change-log.md`. Add a **post-sync advisory probe**
  (register in `lib/probe_families.register_all`, same pattern as
  `stale_base_probes.probe_unpromoted_release_prep` — trigger and resolution read the same
  observable state) that fires when a committed `.prawduct/change-log.md` has no `merge=union`
  gitattribute, RECOMMENDS the exact line (`.prawduct/change-log.md merge=union`), and
  self-resolves once the attribute exists. The advisory surface is chosen because it runs in
  every session briefing — doctor is rarely run (owner, 2026-08-13); doctor may list the same
  check as a secondary surface if cheap. Advisory-only per the governed_by DECISION — recommend,
  never write. `test_count` churn is out of scope — #633 owns it.
- **Depends on:** none
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F6
- **Tests:** probe fires on a fixture repo without the attribute; returns `[]` when present, when
  change-log is absent/gitignored, and when `git check-attr` is unavailable (fail soft, say why);
  advisory id stable across firings
- **Acceptance criteria:** fixture briefing shows the advisory with the verbatim line; adding the
  line resolves it on next sync; suite green
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` over the branch —
       commit first, run once; that review is also the `/prawduct:pr create` gate. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** on any consumer worktree, merge an advanced `develop` into a reviewed
branch and watch `prawduct-hook check-cumulative-critic` stay `satisfied` instead of demanding a
fresh cumulative — the headline tax, gone, demonstrable in one command.

## Governance Checkpoints

**Commit & PR cadence:** feature branch `feat/tactical-efficiency-pass` off `develop`; commit per
chunk after its Critic review passes. Chunk 07's cumulative makes the branch PR-ready;
`/prawduct:pr create` when the user asks. All bookkeeping (backlog archives incl. #565 and #283,
change-log entries with `scope=tactical-efficiency` and no `release=`) rides in the branch.

- After Chunk 01 (`final` review): the keystone — confirm the transfer's fail-closed posture and
  the soundness boundary prose before anything builds near it.
- After Chunk 04: re-read the four prose rules end-to-end across the three protocol files for
  coherence (they were edited in two chunks; Principle 13).
- After Chunk 06 (`final` review): confirm every pointer-resolved surface behaves identically on
  a repo with no `branch:` opt-in — the fallback chain is the compatibility contract.
- After Chunk 07 (cumulative): full-bundle review; then re-measure a consumer branch's round
  count in a follow-up session — the analysis' cost baseline is the before-picture.
