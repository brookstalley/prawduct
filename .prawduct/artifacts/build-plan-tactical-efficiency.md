---
artifact: build-plan
version: 2
scope: tactical-efficiency
branch: feat/tactical-efficiency-pass
depends_on:
  - artifact: tactical-efficiency-analysis-2026-08-13
  - artifact: kernel-v3-evidence-design
governed_by:
  - artifact: architecture
    dispositions:
      - "independent reviewer never mutates the session it reviews → conforms (no reviewer write path changes)"
      - "authority fails closed; advice fails soft → conforms, and it is the design spine of Chunk 01: any git failure, missing object, or condition miss denies the transfer and the uncovered verdict stands"
      - "local-first, no network/daemon → conforms (git plumbing and files only)"
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state, the evidence store, and the named reconcile files → [DECISION: the merge-attribute chunk is advisory-only — the advisory and doctor both RECOMMEND the .gitattributes line and print it verbatim, never writing it, because .gitattributes is not in the permitted write set | engages the norm's why: unexpected framework writes are the trust breach | user can override by amending the norm to add .gitattributes to the reconcile set]"
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
- [x] Chunk 04: Prose findings priced honestly — severity ceilings, deletion-first remedies, no archaeology
- [x] Chunk 05: Verify-resolutions golden path at every point of action
- [x] Chunk 06: The plan declares its branch — active-plan resolution goes branch-scoped
- [ ] Chunk 07: Advisory recommends union-merge for the append-only change-log
Context: Plan authored 2026-08-13 by the Fable analysis session (Chunks 06–07 added same day
after owner feedback: doctor is rarely run → advisory surface; active plan is branch state →
Chunk 06). Chunks 01–04 built and committed; 05–07 outstanding. Executes on Opus. Parent evidence:
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
emits no yield signal, against the standing control-observability norm). **Both were then built by
a worktree subagent at the owner's request and merged into this branch (`243c7761`), so they ship
here rather than later** — the Stop gate transfers on its merge-base fallback span only, and a
grant records its yield through a span-keyed `guard-refusal` fact that repeated polls do not
duplicate.

Chunk 04 landed 2026-08-13 (`a02aa1c6` + `8e7d8781`; review `rev-20260813T203202Z-87a90058` and
two verify passes, final state 0 findings). Its blocking finding was a plan citation that resolved
from neither ref root; its most valuable was the **floor clause** — a severity ceiling stated with
only an upward exit silently outranks every rule that promotes a finding, so Goal 4's
actively-misleading-README BLOCKING would have come down to a WARNING. The second verify pass
caught the chunk violating its own provenance ban inside the test that pins that ban.

**Retroactivity of the archaeology rule: contain, do not sweep.** The rule is new, so the repo
carries a latent set of pre-existing review ids and chunk anchors in comments (the verify pass
counted several in `tests/test_v5_methodology.py` alone). Those are not load-bearing, so under this
chunk's own ceiling they are NOTEs, and sweeping them is exactly the wording churn the chunk exists
to stop. The rule binds new and edited comments; existing ones are corrected only when their file is
being touched anyway. Not backlog work — a decision, recorded here so it is not re-opened.

Chunk 02 landed 2026-08-13 (`65b37539`; review `rev-20260813T161546Z-20da8706` + verify pass,
final state 0 findings). Profiled before building: the entire 29–120 s gate cost is
`coverage_verdict`'s free-edge search keying every tree the store mentions (17.4 s cold / 0.01 s
warm here), so the memo targets exactly that. Measured 20.0 s → 0.35 s on this repo. The Critic
caught that the memo's stated soundness precondition was not the one the call site established;
`read_facts` now hands back the fingerprint of the bytes it parsed, which makes the pairing
structural instead of documented. Five prose corrections from the verify pass are owed and
recorded in `.prawduct/.handoff-notes.md` — they are deferred only because a concurrent worktree
agent (#654/#655) holds those files.

Chunk 05 landed 2026-08-13 (review `rev-20260813T212253Z-9a675b4c` + one verify pass, final state
0 findings, 0 blocking throughout). Its warning was a **fail-open in its own new rule**:
`cost-of-commit` with no arguments — or a directory — prices the *working* tree, which at that
point in the PR Update flow is clean because the delta is already pushed, so it returns an empty
`judgeable` list having read none of the delta and the agent skips the independent PR review. The
step now passes explicit paths and requires a non-empty priced set; unknown is never free. The
chunk also reached one surface beyond its three: `critic-consolidate`'s dirty-tree note prescribed
the same superfluous round the new remedy removes. **Its `gates.py` twin is carried into Chunk 06**
— see the carry note under Chunk 05.

Dogfooded end to end: the verify pass delivered its observations pre-priced (the chunk's own new
instruction, on its first live run), and Chunk 05 closed by committing the vouched-for tree
verbatim rather than fixing the two demoted observations and buying a round — which is the golden
path the chunk installs, taken by the chunk itself.

Chunk 06 landed 2026-08-13 (review `rev-20260813T224220Z-535e6351` + two verify passes, final state
0 findings). It also discharged Chunk 05's two carried items. **Both its blocking findings were one
defect, found independently by two reviewers: the fail-closed refusal failing OPEN at the Stop
hook.** `main()` rendered every refusal as exit 1, but `stop` is a harness hook whose recorded error
model gives it two outcomes — 0 clean, 2 block — so a repo with two plans claiming one branch would
have ended its session CLEAN with no gate having run. `cmd_stop` now probes resolution once, before
any gate and before the background-work deferral (which returns 0, and which nothing about
background work could ever clear). Guarding the individual call sites was tried first and only moved
which line raised: three resolve independently, which is the finding's own point.

The second verify pass caught the fix's own fix untested — the one-line `_has_unfinished_chunk`
filter that silences the new advisory across the gitflow retention window, where all six sibling
tests used an unfinished plan and so passed with it deleted.

Two departures from this plan's prescribed method, both recorded inline under the chunk: there was
no resolver "pair" to change (the hook's mirror had no caller and was deleted), and the resolver
alone did not satisfy the acceptance criterion — `infer_scope_from_branch` had to consult the
`branch:` declaration too, because `critic-begin`'s ledger scope is derived from the branch NAME.

Note Chunks 03–05 all edit the Critic/PR protocol prose, and every one of those files sits within
~30 tokens of a guardrail ceiling; `goals-1-3.md` now has 7. Chunk 06 touched none of them.

Next: Chunk 07, which is independent of everything before it. One accepted debt rides its commit —
R-17's relational sweep of the ~dozen `active_build_plan pointer` narratives this chunk falsified
but did not edit; the list is in `.prawduct/.handoff-notes.md`.

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
     drift" + `plugin/skills/pr/review-protocol.md` severity notes): comment/docstring/doc wording, counts, and
     phrasing are **NOTE** unless load-bearing — referenced by a test or a gate, or the reviewer
     names the concrete wrong action a maintainer takes because of it (the existing WARNING bar,
     now applied to prose explicitly). The ceiling never lowers a severity another rule assigns
     explicitly.
     <!-- Amended 2026-08-13: the floor clause was added during the chunk's review. Stated with
          only its upward exit, a rule that suppresses findings silently outranks every rule that
          promotes one — Goal 4's actively-misleading-README BLOCKING among them. -->

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
     non-judgeable paths and/or a base-sync merge does not re-run the PR reviewer.
     **Closes half of the observed 520-second re-review, not all of it** — the `.prawduct`
     records are non-judgeable, but a CI workflow file is config, so `is_judgeable_path` calls
     a comment-only edit to it judgeable and the reviewer still re-runs. The content-equivalence
     exception that would close the other half was built and reverted as unsound (COV-3M8Q),
     so the rule states its own limit rather than overreaching to meet the evidence.
  Explicitly **not** built (analysis "What was deliberately not proposed"): a sincerity flag, and
  refusing verify dispatch when the delta is "only fixes" — the fixes live in judgeable files, so
  refusal would strand the gate uncovered.
- **Depends on:** Chunk 04 (shares `goals-1-3.md`)
- **Artifacts consumed:** `tactical-efficiency-analysis-2026-08-13.md` §F5
- **Deliverables:** `plugin/lib/gates.py` (`blocking_remedy_lines` + its tests),
  `plugin/skills/critic/goals-1-3.md`, `plugin/skills/pr/SKILL.md`,
  `plugin/lib/critic_consolidate.py` (the dirty-tree dispatch note prescribed the same superfluous
  round the new remedy removes — added during the build, reason in the change-log)
- **Tests:** `blocking_remedy_lines` unit tests updated to the new wording (both callers render
  it — the one-home rule holds); prose guards as in Chunk 04, in
  `tests/test_verify_golden_path.py`
- **Acceptance criteria:** gate stderr on a blocking verdict prescribes the batch golden path;
  verify-mode report template carries the pricing line; suite green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

**Carried into Chunk 06's commit — two items, deliberately not fixed in Chunk 05's.** Both are
judgeable-file edits, and Chunk 05's closing commit is the verbatim commit of a tree a verify pass
already vouched for; editing them in would have forfeited that and bought exactly the round this
chunk exists to remove. Riding a commit Chunk 06 is making anyway buys none. **Do them there:**

1. `plugin/lib/gates.py` — the `uncovered` remedy's last clause still tells a builder whose verify
   fact anchored the WORKING tree to "commit (or stash) the WIP and **re-run**". Same defect as the
   consolidate note this chunk corrected, and this one's reader is the builder: committing the WIP
   *verbatim* ends the fact at the tree the gate targets, so no re-run is owed. Name the real
   exception instead — a selective or further-edited commit.
2. `tests/test_critic_consolidate.py` — the corrected half of the dirty-tree note ("Commit this
   tree VERBATIM and no further pass is needed") has no pin; the existing assertion covers only
   "vouches for the WORKING tree", which survived the edit unchanged. By this chunk's own logic, a
   restated rule is what a later trim deletes first.

### Chunk 06: The plan declares its branch — active-plan resolution goes branch-scoped (analysis F7; closes #283)

- **Description:** `active_build_plan` is branch state stored in a product-level scalar — two
  concurrent branches guarantee a same-line conflict, and after the merge one plan is invisible
  to every pointer-resolved surface. Invert the pointer: build plans gain optional frontmatter
  `branch: <name>`, and the resolver pair (`core.resolve_build_plan_path` + the parity-tested
  `bin/prawduct-hook` mirror — change BOTH, the parity test pins them) resolves in precedence
  <!-- Amended during the build 2026-08-13: there is no pair. The hook's mirror had NO caller —
       `staleness_scan` was its last one and was rewritten onto `core.resolve_build_plan_path`
       when it moved into `lib/briefing.py`, leaving only its own parity test to invoke it, and
       voiding the import-light claim (that path reaches the resolver via `lib.briefing` and
       loads `core` regardless). Extending it meant duplicating a directory walk and a git
       subprocess into unreachable code on its fourth rework, so it was DELETED instead
       (Principle 25; "goals and verification bind, prescribed method is advice"). The scalar
       reader beside it stays — four live callers — and its parity cases are unchanged. The
       parity test now pins the deletion, so the duplicate cannot quietly return. -->
  <!-- Also added during the build, and NOT in the plan: `infer_scope_from_branch` consults the
       `branch:` declaration before its name-matching rules. Without it the acceptance criterion's
       first named consumer stays broken — the resolver alone does not fix `critic-begin`'s ledger
       scope, which is derived from the branch NAME, not from the resolved plan. -->
  <!-- Two more in-build departures, recorded to the same standard as the two above.
       (1) `gitstate.current_branch` gained a HEAD-file fast path with the subprocess kept as
       fallback. Not scope creep but its opposite: the branch probe made the session briefing
       197 ms -> 494 ms (measured), which an efficiency pass does not get to ship. It reads
       215 ms now, and the fast path is worktree-aware because reading the shared common dir
       would report the primary checkout's branch to every gate, silently.
       (2) `cmd_stop` probes resolution once, up front, and renders a refusal as a BLOCKED
       report at exit 2. Found by the chunk's own review: `main`'s wrapper renders every
       refusal as exit 1, which the harness-hook row of `api-contract.md` treats as neither
       clean nor blocking, so the session ended CLEAN with no gate having run — the fail-OPEN
       inverse of the posture, on the one state this chunk invents. -->
  order: (1) the live (non-archived) plan under `.prawduct/artifacts/` whose `branch:` matches
  `git branch --show-current`; (2) the `active_build_plan` scalar; (3) the conventional default.
  Existing repos behave unchanged until a plan opts in. **Two live plans claiming the current
  branch is a loud error** surfaced by the resolver's callers, never a silent pick (authority
  fails closed). Detached HEAD or a non-matching `branch:` falls through to (2)/(3); the session
  briefing names a live plan whose `branch:` matches no existing branch (advice, fails soft).
  Archive keeps working with less ceremony: moving a plan under `.prawduct/artifacts/archive/`
  ends its claim, so `archive-plan`'s pointer-clearing becomes unnecessary for
  frontmatter-resolved plans (keep it
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
- **Acceptance criteria:** on this branch with the frontmatter added, every pointer-resolved
  surface (briefing, `infer-critic-mode`, stop-hook gate trigger) resolves THIS plan by its
  `branch:` **without consulting the scalar** — demonstrate precedence by pointing the scalar at a
  DIFFERENT live plan for the check, not by relying on its incumbent value; on develop nothing
  changes; suite green.
  <!-- Amended 2026-08-13: the original said "the scalar left pointing at the purpose-and-cession
       plan". This branch repointed it at THIS plan when the build session opened, so that form
       would now pass vacuously — both routes would agree and precedence would go untested. -->
  **Also verify the two consumers this pass found empirically:** `critic-begin` could not resolve
  the plan from the branch name (`feat/tactical-efficiency-pass` does not match scope
  `tactical-efficiency`) and fell back to the scalar with ledger scope `(none)`, and Chunk 03's
  `prior_dispositions` work-scope filter is inert until a dispatch resolves a scope. Both should
  start working when this chunk lands; if they do not, the chunk is not done.
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
  (register in `lib/probe_families.py::register_all`, same pattern as
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
