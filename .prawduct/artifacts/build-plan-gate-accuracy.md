---
artifact: build-plan
version: 2
scope: gate-accuracy
branch: fix/gate-accuracy
depends_on:
  - artifact: architecture
  - artifact: data-model
governed_by:
  - artifact: architecture
    dispositions:
      - "goals and verification bind; prescribed method is advice → conforms, and Chunk 02 is where this plan's own prescribed method was WRONG: its Description named a `diff ⊆ scope` mechanism that does not exist, and the build corrected the plan rather than conforming to it."
      - "authority fails closed; advice fails soft → conforms, and it is the norm that picks the direction of Chunk 01. `test-status` is an AUTHORITY (the PR flow and the Stop gates read its verdict), so the only safe error is toward `stale`. The change adds paths to the suite-coupled set and never removes one, so every verdict it changes moves from `current` to `stale` — a suite run, never a skipped one."
      - "local-first: governance coordination is process-spawn + files + git, no network → conforms; nothing here reaches the network. The tempting fix for the observed incident — a session-start probe asking GitHub whether the integration branch is red — is REFUSED by this norm, and that refusal is why Chunk 01 fixes the local predicate instead. Recorded because the rejected design is the more obvious one."
      - "every fact has one home → conforms, and Chunk 02 is where it was nearly broken. `affects_test_outcome` remains the single answer to *can this path change what the suite says*; the WHICH-paths half moves to `project-state.yaml`, which is the only place a repo's own layout can live. Chunk 02 originally restated an internal rule it had read from a comment rather than the handler — a second home for a fact that turned out not to exist — and now states only the dispatcher's observable behaviour."
      - "goals and verification bind; prescribed method is advice → conforms; the Deliverables below name call sites read from the code, not guessed."
      - "prawduct guides and reviews; it never implements → inapplicable; both chunks change prawduct's own governance runtime, which is this repo's product."
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes: shared committed answers vs per-clone gitignored nags → conforms; the evidence record this changes the freshness of is already per-clone and gitignored, and neither chunk moves a fact between stores."
partition: serial — Chunk 02 is prose about a mechanism Chunk 01 does not touch, but it rides the same review and the same PR, so there is no reason to parallelize two edits one reviewer reads together. **Both chunks are reviewed by ONE cumulative pass rather than the per-chunk review each `Done when` names** — the combined diff is ~5 files and well under the roster's 12-file bound, and two dispatches over one small bundle buys a second round without a second reader's worth of attention. Recorded as a deviation from this plan's own prescribed method, which `architecture.md` § Direction permits and asks be written down.
last_validated: 2026-09-09
---

## Requirements Confidence

**Level:** High

**Why:** Both defects were reproduced in this session against the live repo rather than reasoned
about: the red base was inherited and diagnosed to two named tests that predate it by two weeks,
and the verify-resolutions refusal was read from the dispatcher's own printed block. **Chunk 02's
first draft then over-read that**, inferring a subset mechanism from a code comment; the Critic
caught it and the chunk now claims only what the dispatcher observably does. Confidence is High for
what shipped, not for that first reading.
Problem, success and scope are each one sentence.

**Open assumptions / unknowns:** none material. The plan-time assumption — that a blanket `.md`
rule would be proportionate — was **resolved during the build and against the plan**: three existing
pins record the wider exclusions as priced decisions, and the Critic then showed a hardcoded root set
is inert in every product repo besides. The built design is a repo-declared prefix list read from
`project-state.yaml`, defaulting to empty. Recorded here rather than quietly replaced, because the
abandoned design is the one a reader reaches for first.

**What would raise confidence:** N/A

## Status

- [x] Chunk 01: `affects_test_outcome` stops calling docs untestable
- [x] Chunk 02: `/prawduct:pr` Step 2's dirty-tree rule states its else-branch
Context: Plan written 2026-09-09, immediately after PR #769 merged. Both chunks come from that PR's
own reflection, and the first one's diagnosis was WRONG on the first pass — the session reflection
blamed the doc-only fast-path (`check-pr-doc-only`), and the actual cause is one predicate over, in
`affects_test_outcome`. The commits that landed red (`99c02309`, `97265bc4`) were pushed **directly
to `develop`** with no PR at all, so no `/prawduct:pr` gate was ever reached; CI ran on both pushes
and failed on both, and nothing read the result. Recorded here because the wrong diagnosis is the
more natural one and the next reader will reach for it too.

**Out of scope, and it is the stronger fix:** `develop` has no branch protection, so a direct push
lands and a red run blocks nothing (5 of the last 50 `develop` runs failed, all in the past week).
That is a repo setting and an owner decision, not a code change, and it is named here so that
choosing not to make it stays a choice rather than an oversight.

## Scaffolding

Not applicable — an existing, scaffolded project. `python3 -m pytest tests/ --junit-xml={junit_xml} -q`
is the declared suite; record through `prawduct-hook test-evidence record`.

## Chunks

### Chunk 01: `affects_test_outcome` stops calling docs untestable

- **Description:** `affects_test_outcome(path)` answers *can a change to this path change what the
  test suite says*, and it currently answers **no** for every non-governance-protected `.md`. That is
  false in this repo and false in general: `tests/test_pr_evidence_contract.py::TestClosingKeywordClaims`
  sweeps `documentation/`, `tests/test_path_reference_resolution.py::test_no_governance_prose_cites_a_flow_step_by_NUMBER`
  sweeps governance prose, and the learnings/change-log lints read `.prawduct/*.md`. The consequence
  is not theoretical — it is the incident this plan exists for: a base sync brought two red
  `documentation/issues/*.md` files, `_test_evidence_tree_valid` classified them as
  "only non-judgeable paths changed", and `test-status` reported day-old evidence as `current` over a
  tree whose suite was red.
  **The repo already holds the correct reasoning and this predicate contradicts it.**
  `.github/workflows/`'s header refuses path filters in as many words — *"a docs-and-state change
  really can turn the suite red. A filter that calls those paths untestable would hide exactly that
  class of break."* `affects_test_outcome` is that filter.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction (authority fails closed;
  every fact has one home; gates never assume the governed product's shape)
- **Design decisions, recorded here rather than inside Deliverables** (these cite existing files;
  they do not produce them):
  - **Why not blanket `.md`.** Three existing pins record the wider exclusions as DELIBERATE:
    `test_the_held_out_bookkeeping_files_are_recorded_as_a_residual` holds `.prawduct/change-log.md`,
    `learnings.md`, `backlog.md` and a live build plan out **on cost**, saying so in its docstring,
    <!-- prawduct:allow prawduct/chunk-ref-missing -- a fixture path asserted inside that pin, quoted to name the exclusion this scope does not touch; a string in a test, not a file this repo carries -->
    and `test_ordinary_metadata_is_still_free_of_both` holds `README.md` and `docs/notes.md` out.
    Flipping those is an owner cost decision someone already made, not a defect to fix in passing —
    so the scope is chosen for **all three pins to stay green unedited.**
  - **Why the prefixes are a parameter and not a default.** The doc-only PR gate
    (`coverage.check_pr_doc_only`) also consults `suite_coupled_files`, so widening the predicate's
    DEFAULT would make a documentation-only PR buy a full cumulative Critic and PR review — a review
    cost nothing priced. Freshness callers pass the declaration; review callers do not.
- **Deliverables:**
  - `plugin/lib/coverage_algebra.py` — `affects_test_outcome` gains one clause: markdown under the
    **instruction roots** the repo declares is suite-coupled.
    **Scoped, not blanket, and the scope is not a guess** — the roots are the ones
    `instruction_surfaces()` scans in `tests/test_pr_evidence_contract.py`, whose docstring says why
    `documentation/` belongs: it *"carries runbooks and requirements that instruct exactly as
    plugin/ does."* **Not identical to that sweep, and the difference is deliberate:** it also skips
    <!-- prawduct:allow prawduct/chunk-ref-missing -- names a path COMPONENT that instruction_surfaces() skips, not a directory; none exists under the instruction roots and none is created -->
    record filenames and any `archive/` component, which a prefix test does not. Both skips would
    only ever move a verdict toward `stale`, which is the safe direction for an authority, so they
    buy nothing here and are not reimplemented — one predicate stays one predicate.
    The roots are **declared by the repo**, not carried by the framework: `plugin/` exists in no
    product repo, so a hardcoded root is inert everywhere it ships while taxing any product that
    happens to match. `core.suite_coupled_prefixes` reads them from `project-state.yaml` and the
    default is empty, so an undeclaring repo is byte-for-byte unchanged.
  - The same function's docstring — it currently explains the `is_judgeable_path` split using
    COV-4H7N (a state-only PR that skipped the suite and read its stale evidence as current). This
    chunk adds the sibling that just recurred one boundary over, in the present tense, with no
    finding id and no chunk number, and names the residual so the next reader meets it as a decision
    rather than as a gap.
  - **`is_judgeable_path` is NOT touched, and that is the point of the split.** Review coverage must
    not widen: the batch-fix directive promises builders that `.prawduct/` and doc writes are free
    mid-review, and this chunk keeps that promise true. Only the suite question moves.
- **Tests:** `tests/test_coverage_algebra.py` (or the existing home for these predicates — resolve
  by reading, not by assuming the filename). Cases, each asserting the subject is REACHED rather than
  that nothing fired: a `documentation/issues/*.md` path is suite-coupled and NOT judgeable (the two
  predicates must disagree, which is the whole design); `.prawduct/learnings.md` and
  `.prawduct/change-log.md` are **NOT** suite-coupled, which is the priced exclusion holding; a governance-protected `.md` stays both; a `.py` stays
  both; **and a regression pin that reconstructs the incident** — `_test_evidence_tree_valid` over a
  recorded tree and a target tree differing only by a `documentation/**.md` file returns *not valid*.
  That last one is the test whose absence let this ship, so it carries a positive control: it must
  fail against the pre-change predicate. (Verified by restoring the old predicate and watching all
  three new pins go red.)
- **Acceptance criteria:** suite green via the declared command. `test-status` reports `stale` for a
  tree whose only change since the run is a `documentation/**.md` edit, and still reports `current`
  for a priced-exclusion edit — verified by making both and reading the verdict, not by reasoning
  about it.
  **Verify it against evidence that PREDATES the session.** `tests_are_current` is a disjunction
  whose first clause is session-freshness, so evidence recorded in the same session passes on clause
  1 alone and the tree-validity clause is never consulted — a check run against fresh evidence
  reports `current` either way and proves nothing. That is also why the incident needed a day-old
  record to happen at all.
- **Residual, named rather than closed:** `_governance_prose()` in
  `tests/test_path_reference_resolution.py` sweeps EVERY tracked non-record `.md`, which is wider
  than the instruction roots — so `README.md`, `docs/*.md` and a **live build plan** can still flip
  the suite while this predicate calls them free. That exposure survives this chunk deliberately:
  closing it means overturning the two pins above, whose exclusions were priced and recorded. Raised
  to the owner as a cost question, not decided here.
- **Visible Costs:** in a repo that DECLARES prefixes, a doc-only edit under one of them stales test
  evidence and buys a suite run (~4 min here). **No other product pays anything until it declares** —
  the default is empty, so this is a cost this repo chose for itself rather than one the framework
  imposes. The trade is deliberate: the alternative is a gate that reports green over a red tree, and
  CI already pays the same cost on every push by explicit choice.
- **Critic mode:** chunk
- **Done when:** tests pass, acceptance criteria verified, `/prawduct:critic` run and blocking
  findings resolved, Status ticked.

### Chunk 02: `/prawduct:pr` Step 2's dirty-tree rule states its else-branch

- **Description:** Step 2 tells the builder *"Run the pass on the dirty tree, then commit it whole,
  and there is one round instead of two."* Followed literally in this session, it cost the round it
  promised to save: `verify-resolutions` refused with exit 3, reported that it had graded committed
  HEAD rather than the working tree, and named the uncommitted judgeable file as NOT REVIEWED. The
  guidance is not wrong — it is **unconditional about a conditional outcome.**

  **The plan's first draft named a mechanism that does not exist**, and the Critic caught it: there
  is no `diff ⊆ scope` refusal in `begin_review`'s verify arm — `_scope_widened` is pure cardinality
  (`delta > 2 * prior + 5`), which one unseen file never trips — and the symbol it cited was
  misspelled besides (`_rule_verify_resolutions_fires` is the real one, and it only picks a
  *recommended* mode). That draft was written from a code comment rather than from the handler,
  which is the failure this repo's learnings already name. Recorded rather than quietly replaced,
  because the wrong mechanism is the one a reader reaches for first.

  What is actually true is narrower and observable: the pass may anchor on a prior review and grade
  **committed HEAD** rather than the working tree, in which case it refuses (exit 3) and names the
  uncommitted judgeable files as NOT REVIEWED. The remedy is to commit and re-run over the delta —
  which the refusal itself says.
- **Depends on:** none — prose about a mechanism Chunk 01 does not change.
- **Artifacts consumed:** `plugin/skills/critic/review-cycle.md` § Verify-resolutions anchoring and
  demotion (the derivation Step 2 already cites)
- **Deliverables:**
  - `plugin/skills/pr/SKILL.md` Step 2 — the dirty-tree sentence gains its else-branch: the pass may
    instead anchor on a prior review and grade committed HEAD, refusing and naming the uncommitted
    judgeable files, and there the reader commits first and re-runs over the delta. It tells the
    reader **not to predict which case they are in** — dispatch is seconds and its own answer is
    authoritative. **It cites no internal rule at all**, which is the honest scope of what was
    verified, and no line number — this repo has paid three times for durable prose riding a
    position that renumbers, and `test_no_governance_prose_cites_a_flow_step_by_NUMBER` exists
    because of it.
  - **No new rule is invented.** The mechanism already behaves correctly and announces itself; only
    the instruction was incomplete. Nothing in `critic_mode.py` or `critic_consolidate.py` changes.
- **Tests:** the governance-prose contract tests already sweep `plugin/skills/` and must stay green
  (no line-number citation, no closing keyword without its condition). No new test: the claim being
  fixed is an instruction's completeness, and pinning prose against its own paraphrase buys a
  tautology — the mechanism it describes is already pinned by
  `tests/test_critic_mode_inference.py`. Recorded as a deliberate decision rather than an omission.
- **Acceptance criteria:** suite green. A reader of Step 2 who touches a file outside the prior
  review's surface is told, before dispatching, that they must commit first.
- **Critic mode:** chunk
- **Done when:** acceptance criteria verified, `/prawduct:critic` run and blocking findings resolved,
  Status ticked.
