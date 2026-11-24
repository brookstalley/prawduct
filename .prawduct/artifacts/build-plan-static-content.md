---
artifact: build-plan
version: 2
scope: static-content
branch: feature/static-content
base: develop
working-branches: []
last_validated: 2026-11-24
depends_on:
  - artifact: architecture
  - artifact: nonfunctional-requirements
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: the change removes two of the three costs #1239 measured (a whole-suite run, and a three-reviewer roster) for declared static content, and adds no run"
      - "proportionality ratchets both ways: a new control names its yield → inapplicable because this adds no control; it narrows when an existing escalator fires"
      - "review rigor is stage-keyed → conforms: no stage's blocking set changes, and the boundary review still runs over every static file"
      - "state-file growth is an advisory → inapplicable because no state file grows"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms: a declaration the reader cannot read whole makes nothing static, so a typo costs suite runs and reviewers, never a relaxed gate"
      - "every fact has one home → conforms: the predicate lives in `coverage_algebra`, the key reader in `core`, and the roster rule's home stays `skills/critic/review-cycle.md`"
      - "never specific to Python → conforms: the declaration is paths, any language"
      - "the plugin writes nothing into a governed repo but its own state → conforms: it reads one optional key and writes nothing"
      - "goals and verification bind; prescribed method is advice → conforms: the chunk routes are forecasts; the Constraints bind"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer behaviour changes"
      - "local-first → conforms: no network, no new dependency"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
partition: serial — both chunks edit `coverage_algebra.py`, and Chunk 02's roster discount calls Chunk 01's predicate
---

## Goals

**Response taken:** Proceed, citing #1239 and the owner's ruling of 2026-11-24 (`.prawduct/owner-rulings.md`): declared static documents get a lighter review at the PR boundary, not the doc-only route that skips review.

**Product:** A branch made of static documents (stylesheets, static HTML pages, a JSON file of design values) paid the whole code path at the PR boundary: about 25 minutes, with a whole-suite run (about 6.5 minutes) and a three-reviewer boundary review (about 7 minutes), though nothing executes or parses those files. The review still found real defects (a value that contradicted a ruling, accessibility faults in the markup), so it must keep running. The goal is that such a branch reaches an open PR in a few minutes, with one independent review and the hygiene check.

**Architecture:**
- A repo declares `static_content_prefixes:` in `project-state.yaml`: path prefixes whose files nothing executes or parses. A file is **static content** when it is under a declared prefix, is not under a `suite_coupled_prefixes` entry, is not in `TEST_COUPLED_STATE`, and is not governance-protected prose. One predicate in `coverage_algebra` answers it.
- Static content stays **judgeable**: `is_judgeable_path` does not change. Review coverage is still owed, the doc-only fast path still refuses, and the change-record probe still asks for a fragment.
- Static content does **not affect the test outcome** (`affects_test_outcome`), so suite evidence recorded before a static-only change stays tree-valid. It is **not executable** (`is_executable_path`), so the coverage floor demands no test reference for it.
- Static content does **not count toward the coordinator roster's volume escalator** (`judgeable >= 12`). A risk surface still escalates, whatever the file is.
- Must stay possible: a repo that declares nothing behaves exactly as before.

**Constraints:**
- Paths classify, contents don't (`coverage_algebra.is_judgeable_path` docstring; `spike-tree-validated-test-evidence.md` §4). No extension table either: the docstring of `is_executable_path` records that a second suffix table is the divergence CRT-5D8Q removed, so the declaration is the whole claim.
- Roster depth is a risk question, not a judgeability one (#370's closing note). The discount is framed as the repo's declaration that these paths carry no risk the third reviewer would find; it does not reuse the judgeability predicate to choose depth.
- `suite_coupled_prefixes` wins any overlap: a path a test reads as data is never static.

**Tradeoffs accepted:**
- SUPERSEDED 2026-11-24 by the boundary review's decision below: *Inferred:* the declaration is read from the working tree, as `risk_surfaces` and `suite_coupled_prefixes` are. A branch can therefore declare its own static paths, as it can already remove a risk surface. Bounded because the files are still reviewed and the declaration is visible in `project-state.yaml`. Revisit if a declaration is ever seen widening on the same branch as code under it.
- *Owner-ruled (2026-11-24):* one reviewer instead of three for static-heavy diffs. #370's replay has no data on static content, so how many blockers a third reviewer would have found there is not measurable; the owner accepts that.
- *Inferred:* the suite is not re-run for a static-only change. A test that does read a declared file is the case `suite_coupled_prefixes` exists for, and it wins.
- Out of scope: the paired native review, which runs only on development builds (`native_review.py`) and so is not a consumer cost; and `critic_mode`'s mode inference, a different axis from the roster (#370).

**Decisions made mid-build:**
- Chunk 01: the block reader already refuses an empty entry (`- ''`) as unparseable, so an empty prefix can never make every path static; a filter added for it was dead and removed. Settled by "authority fails closed".
- Chunk 01: `is_static_content` carries no `TEST_COUPLED_STATE` clause. Those paths are metadata, so never judgeable and never static, and a mutation sweep showed the clause could not change an answer.
- Chunk 01: `coverage.explain_uncovered` (the PR gate's `CAUSE:` line) also asks the freshness question on its `head` target, so it takes the static declaration; its review-side `working` target still names static files. Settled by "every fact has one home": the explanation must agree with the gate it explains.
- Chunk 01 review (rev-20261124T191600Z-8ec5426d, paired native review): the freshness check read the declaration from the working tree while comparing two committed trees, so an uncommitted declaration relaxed a comparison neither tree supported. The declaration in force is now the one the judged tree carries: the recorded run's tree at the freshness check, `HEAD` at the coverage floor. The JUnit ingest and the `CAUSE:` explanation stay on the working tree, because an uncommitted declaration changes `project-state.yaml`, which is test-coupled and stales them first. **Chunk 02 must follow the same rule**: the roster reads the declaration from the reviewed head tree. Settled by "authority fails closed".
- Chunk 01: the scaffolded state file has a size ceiling (`test_plugin_init.py`) and sat 7 bytes under it. Paid in place, with no raise: the deprecated `active_build_plan` hint is one line (the guard requires every documented key to stay hinted, and its explanation lives in the keys reference), and the new hint is one short comment line.
- Chunk 02: the tree-reading helper gained a second consumer (the roster), so it left `gates.py`. It now lives in `coverage.suite_declarations` (next line).
- Boundary review (rev-20261124T194049Z-03e0ff55, three reviewers plus the paired native review): (1) the coupling declaration that overrides the static one was still read from the working tree, so an uncommitted coupling removal relaxed a committed comparison, the same class Chunk 01 fixed for the static key; (2) the branch that adds a declaration got the lighter path for its own suite runs, coverage floor and boundary review, against the core rule that a governance change cannot supply its own authority; (3) a refused declaration was silent. One owner now answers all three, `coverage.suite_declarations(project_dir, tree)`: coupling is the union of the working tree, the judged tree and the merge-base; static is the judged tree's declaration intersected with the merge-base's; a refused or not-yet-integrated declaration comes back as a note that the `test-status` reason and the roster rationale print. Every reader goes through it, including the JUnit ingest and the `CAUSE:` line. `is_static_content` takes the coupling declaration as a required argument. Declarations are read only when something judgeable is left to classify. Settled by "authority fails closed" and core.md's governance-authority rule.
- Chunk 02: `review-cycle.md` sat 1 token under its ceiling. Paid in place, not raised: the derived default risk surfaces now point at `lib/risk.py`, which owns the list, instead of restating it; the ceiling was lowered with the reading. `building.md` is net zero.

**Level:** High. Every consumer of the three predicates is enumerated below, and each change narrows an existing rule for declared paths only.

## Build Chunks

### Chunk 01: Declared static content keeps suite evidence current and needs no test reference

- **Description:** a repo can declare `static_content_prefixes:`, and a change confined to static content leaves recorded suite evidence tree-valid and asks the coverage floor for nothing.
- **Depends on:** none
- **Deliverables:** `core.static_content_prefixes()` (block sequence of strings; absent, `[]`, or unreadable means nothing is static); `coverage_algebra.is_static_content()`; `affects_test_outcome`, `suite_coupled_files` and `is_executable_path` take the declaration; every caller that passes `suite_coupled_prefixes` (`gates.py`, `coverage.py`, `evidence.py`) also passes it, and the coverage floor in `gates.py` does; a `static_content_prefixes` section in `plugin/docs/project-state-keys.md`; a commented example in `plugin/templates/project-state.yaml`
- **Tests:** unit — the predicate: under a prefix; a coupled prefix wins; `TEST_COUPLED_STATE` wins; governance-protected prose is never static; prefixes match as written, so a prefix with a trailing slash does not reach a longer sibling directory name; an unreadable declaration makes nothing static. Integration — on a temp repo with recorded evidence, a static-only change reads `current (tree-valid)`, a change to a non-declared file or to a coupled path under the prefix reads stale, and a repo with no declaration behaves as before (control). `check-pr-doc-only` still refuses a static-only branch.
- **Acceptance criteria:** #1239's shape (Markdown plus static `.css`/`.html`/`.json` under one declared prefix) needs no suite re-run, and the same shape undeclared still does
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed

### Chunk 02: Declared static content does not buy the three-reviewer roster

- **Description:** `_derive_roster` counts judgeable files outside declared static content toward the coordinator threshold, and its rationale says how many it discounted.
- **Depends on:** Chunk 01
- **Deliverables:** the discount in `critic_consolidate._derive_roster`, with the rationale naming the declaration; the roster rule restated in its home, `plugin/skills/critic/review-cycle.md` (the Execution row and the paragraph under it), and the two references to it in `plugin/methodology/building.md` ("Session Scope Discipline") and `.prawduct/artifacts/architecture.md`; a `## Consumer note` in the change fragment saying what to declare
- **Tests:** unit — 45 static files and 5 Markdown files under a declared prefix choose single-pass; the same files undeclared choose the coordinator (control); a static file on a risk surface still chooses the coordinator; 12 non-static judgeable files beside static ones still choose the coordinator.
- **Acceptance criteria:** #1239's branch shape, declared, dispatches one reviewer at `cumulative`; undeclared, three
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then one `/prawduct:critic cumulative`

## Verification strategy

Reproduce #1239's branch on a temp repo, declared and undeclared, through the real commands (`test-status`, `check-pr-doc-only`, and the roster `critic-begin` derives), not only through the predicates. Then dogfood: this repo declares no static content, so its own behaviour must not move, and the suite proves that.
