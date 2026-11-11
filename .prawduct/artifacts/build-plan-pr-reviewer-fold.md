---
artifact: build-plan
version: 2
scope: pr-reviewer-fold
branch: feature/pr-reviewer-fold
base: develop
working-branches: []
partition: "01-04 delegated to four Opus-class builders in isolated worktrees, disjoint by file except three seams the coordinator owns at integration (the dispatcher's usage line and command sets in the hook, api-contract.md, and the PR skill's two steps that call Chunk 01's commands); the coordinator integrates, runs the suite once, writes Chunk 05 and governs"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; one reviewer run leaves every PR boundary, so run-count and unit-cost both fall, and the Stop hook loses a network probe"
      - "proportionality ratchets both ways → conforms; this is the ratchet's removal (583 PR reviews measured 2026-11-10, no blocking finding), and the two commands it adds name the yield they expect and record each refusal as a fact"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file's growth rule changes"
      - "review rigor is stage-keyed → amendment proposed; the statement names the PR review as a boundary-stage review, and the owner's ruling of 2026-11-10 (\"yes fold PR reviewer in\") retires it. Recorded beneath the clause with the owner's words; the statement is not edited"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; a reviewer is removed and none gains a write"
      - "authority fails closed; advice fails soft → conforms; a result that refuses the PR exits non-zero, a check that could not run exits 3 and never reads as a pass, and the warnings are advice"
      - "local-first → conforms; the PR template is read from the working tree and backlog status from the local store"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the scaffold stops creating the PR-review evidence directory and nothing new is written"
      - "written in Python, never specific to Python → conforms; credential shapes, template headings and backlog ids read no language, and no debug-statement check is written"
      - "guides and reviews, never implements → exception; a credential-shape check on a PR's added lines overlaps what a secret scanner owns. The owner confirmed it on 2026-11-11 as a bounded exception (`.prawduct/owner-rulings.md`): it reuses the denylist the plugin already keeps, reads no language, and guards the one PR mistake that cannot be undone. A debug-code check is not written at all: it is a linter's rule, and the interim rule forbids a new duplicate"
      - "goals and verification bind, method is advice → conforms"
      - "every fact has one home → conforms; the credential denylist stays in the one module that has it, the closure list is read through the change record's own reader, and the template locations live in one function"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning → conforms; no subcommand gains a version of its own"
      - "exit codes are the contract → conforms; the two new commands use the documented scheme and attribute every failure"
      - "additive-first evolution, deprecation signalled, removal deferred to a major → exception; this removes `pr-review-dispatch`, `pr-review-payload`, `ledger-append --event review.pr`, `learnings-files --for-diff` and the cache queries `affecting` and `created-since` outside a major. The owner ruled the removals (2026-11-10) and, asked on 2026-11-11 whether each goes outright or stays callable and inert, ruled outright (`.prawduct/owner-rulings.md`), on the precedent of #303: the norm's why is protecting a caller across versions, the callers ship in the same plugin at the same version, and an inert payload command would hand a stale session's reviewer nothing to review"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; the PR gate becomes composed review coverage alone, and a model-written evidence file stops being a gate input"
      - "facts immutable and append-only → conforms; recorded `review.pr` ledger events are kept and still read"
      - "derived views never authoritative → conforms"
      - "a newer-schema fact is surfaced, never dropped → inapplicable because no fact schema changes"
      - "two stores, two lifetimes → conforms; the ledger keeps its history, and the per-clone PR-review evidence and dispatch mark stop being written"
      - "backlog_service_repo selects the authoritative backlog store → conforms; the closure check routes on it"
      - "backlog issues conform to the title rules → inapplicable because no write path changes"
      - "a governance document reaches a terminal state and is never deleted → inapplicable because no plan or record is deleted; the retired protocol and agent definition are plugin source"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms; a PR template's headings and checklist are compared and filled, and backlog titles are quoted, neither followed as instruction"
      - "a destructive operation needs owner approval at the operation level → conforms; nothing in a governed repo is deleted, and evidence files left over in a clone are named in the change record and left where they are"
      - "a product's content leaves its repo only through a pinned, approved surface → inapplicable because the PR body goes where it goes today, to the repo's own remote"
depends_on:
  - plugin/skills/pr/SKILL.md
  - plugin/skills/critic/review-protocol.md
  - plugin/lib/record_lint.py
  - plugin/lib/backlog/transport.py
  - .prawduct/artifacts/api-contract.md
  - .prawduct/owner-rulings.md
last_validated: 2026-11-11
---

## Goals

**Response taken:** Proceed, citing it. #1129 (`stage:ready`) carries the requirement, and the
owner's rulings in `.prawduct/owner-rulings.md` are its authority: "yes fold PR reviewer in"
(2026-11-10), the removal of `learnings-files --for-diff` and the cache queries `affecting` and
`created-since` with this item (2026-11-10), and the constraint stated while this plan was being
drawn (2026-11-11): "my one concern with 1129 is making sure it honors repo standards like PR
templates -- or, if the boundary agent doesn't do that, SOMETHING does it". Two questions the
governing norms raise were put to the owner on 2026-11-11, who answered "yes to both of your
recommendations"; both are recorded below.

**Product:** `/prawduct:pr create` opens a PR with no reviewer agent. Its gate is the composed
Critic coverage it already requires, plus two commands that answer by code what a reviewer was
asked to notice: whether the branch is clean to open, and whether the PR description follows the
repo's own PR template. A governed product loses a second boundary reviewer that measured 583
reviews without a blocking finding, and keeps its PR standards honoured by something that cannot
forget them.

**Architecture:**
- The PR boundary has one reviewer, the cumulative Critic. Nothing the `/prawduct:pr` flow needs
  is a model's file: coverage is composed over trees at HEAD, so "the branch moved under the
  review" is answered by the coverage gate rather than by a `commit_reviewed` field.
- Two new gate commands, both read-only. `check-pr-hygiene` answers over merge-base…HEAD;
  `check-pr-body` answers for a drafted description. Each names its results, says `unchecked` with a
  reason where it could not look, and records a refusal as a `guard-refusal` fact so its yield is a
  query.
- The Stop hook's PR-evidence gate goes with the evidence it read. Composed coverage is already the
  Stop hook's Critic gate.
- Recorded `review.pr` ledger events stay readable by `stats` and `review-stats`; nothing writes a
  new one.

**Constraints:**
- No prose, template or test names the PR reviewer as a live mechanism when the plan is done.
  History (archives, release notes, change-log archive, reflections, old plans) is not rewritten.
- Norm statements are not edited to fit this work. An amendment is recorded beneath its clause with
  the owner's words and date, in the form `docs/norms.md` § Amendment gives.
- No new nag. A check that finds nothing prints one line; a repo with no PR template is told so
  once per PR, in the gate's own output, and nothing else.
- `plugin/methodology/session-digest.md` has a hard character wall; anything changed there is paid
  for in place.
- GitHub's rules for PR templates were read from GitHub's documentation on 2026-11-11 (the two
  pages under "Using templates to encourage useful issues and pull requests"): one template named
  `pull_request_template` in the repository root, `docs/` or `.github/`; the filename is not case
  sensitive and takes an extension such as `.md` or `.txt`; several templates live in a
  `PULL_REQUEST_TEMPLATE/` subdirectory of any of those and one is chosen by a `template` query
  parameter; templates take effect from the default branch. Precedence between locations is not
  stated there, so more than one candidate is reported as ambiguous rather than resolved by a guess.

**Tradeoffs accepted:**
- The reviewer's judgment checks on prawduct's own records are dropped, not moved: whether the
  change record's prose describes everything the diff ships, whether a consumer note is honest,
  whether the commits read as one story. They produced 145 warnings and 277 notes in the measured
  window and no blocking finding. Worth revisiting if a release note is found to have omitted
  shipped work; the lever is a check derived from the diff, not a reader.
- Bundle-level simplification is dropped here, per #1129; generic simplification belongs to the
  native-review comparison in #1130.
- A stale session, one whose plugin text loaded before the installed plugin advanced, cannot open a
  PR until it is restarted: its old skill text calls commands that no longer exist. That is the
  safe direction, and the dispatcher names the retired command and the remedy.
- `check-pr-body` reads the template from the branch's working tree, while GitHub applies the
  default branch's. A branch that changes the template is checked against its own version.

**Asked of the owner on 2026-11-11 and confirmed as recommended ("yes to both of your
recommendations", `.prawduct/owner-rulings.md`):**
- *The secrets check and the architecture norm.* #1129's acceptance asks that "a secrets-or-debug-code
  check still runs at the PR gate, mechanically". `architecture.md` § Direction says prawduct never
  re-implements what a product's own tooling does, and its interim rule forbids a new check that
  duplicates an existing linter rule. *Confirmed:* a small credential-shape check over the PR's
  added lines, reusing the denylist the plugin already keeps for its own output, as a bounded
  exception; no debug-code check, because that is squarely a linter's rule.
- *How the retired commands leave.* `api-contract.md` § Direction defers removal of anything a
  person or a skill can call to a major version, and its own case law says a ruling to delete does
  not settle that. *Confirmed:* outright removal, as #303 did by owner ruling, with the
  dispatcher answering each retired name with what replaced it. An inert exit-0 `pr-review-payload`
  would hand a stale session's reviewer an empty payload to review, which is worse than a refusal.

**Inferred, for the owner to see at the boundary** (each former PR-review check and where it went;
the same table goes in the change record):

| Former check | Where it goes |
|---|---|
| The bundle is one change and matches its stated work; each capability traces to a requirement | The boundary Critic: Goal 3 ("no extra functionality beyond what was planned") and Goal 5's `scope-trace:` question, both already there |
| The change record's prose describes all the diff ships; a consumer note is honest; the commits read as one story; an unfamiliar reader can follow | Dropped |
| Change-record keys are the ones the gates read | Already code: `check-change-log-entry` (retired keys, fragment schema) and record-lint's `change-fragment` |
| A legacy single-file entry carrying a placeholder `release=` value | Dropped; fragments carry no `release` and the single-file log is on its way out |
| Version bump, tag and entry agree | Dropped at the PR; the release checklist owns version coherence |
| A chunk this bundle delivers still reads open | `check-pr-hygiene` lists the bound plan's open chunks |
| A chunk reads done or dropped against what the bundle did | Dropped as a separate check; the Critic's Goal 2 already blocks a silently dropped requirement |
| A plan claiming a branch that does not exist; a live plan claiming none | Already code: the binding advisories |
| A norm amended to bless the bundle's own code | The boundary Critic, which already blocks it |
| Test evidence covers what ships | Already code: `test-status` at the flow's first step |
| An item the diff happens to resolve is still open (R-1) | Dropped |
| The branch claims a closure the backlog contradicts (R-2) | `check-pr-hygiene`, read from the change record's `closes:` list |
| A raise of `core.md`'s cap without the owner's approval | Already code: record-lint's `learnings-core-raise-unapproved` |
| A review consolidated over a tree that changed mid-review, on the builder's word | `check-pr-hygiene` prints each one for the PR description, where the PR's human reader is the independent reader |
| Secrets or credentials in the diff | `check-pr-hygiene`, as a bounded exception the owner confirmed |
| Debug code, commented-out experiments, TODOs and placeholders | Dropped at the PR gate; a linter's rules, and the Critic's Goal 7 covers dead code |
| Unintended files (lock files, IDE configuration, unrelated formatting) | Dropped; the Critic's Goal 3 covers unlisted dependencies and unplanned work |
| Migration or rollback notes for a changed persisted format | Dropped as a separate check; the Critic's Goals 4 and 5 judge undocumented decisions and drift |
| Bundle-level simplification | Dropped, per #1129 |
| A rule that exists and nothing enforces is filed once | The Critic's reviewer contract carries the same instruction |
| A closing keyword is not a close | Stays where the builder reads it, in the flow's create and merge steps |
| The description follows the repo's PR template | New: `check-pr-body` (owner, 2026-11-11) |

Also inferred: "repo standards like PR templates" is read as the PR template, enforced, plus the
contribution guide, surfaced: `check-pr-body` names a `CONTRIBUTING` file where one exists and the
flow reads its section on pull requests before drafting. Nothing checks adherence to that guide by
code. Code owners and required reviewers are the host's to apply.

**Decisions made mid-build:** *(appended while building)*
- The closure check reads the branch's record through `change_fragments.branch_change_record`, the
  reader built for merge-base…HEAD, and a branch that records its change only in the single-file
  log is `unchecked` for closure rather than clean. Settled by "every fact has one home" and by
  the rule that a check which could not look never reads as a pass.
- The cloud-token placeholder the denylist scrubs is not reported as a credential, and a private
  key is recognised by its header line; a key body added without its header is not caught. Settled
  by the exception's scope: a floor for the irreversible, not a scanner.
- A credential waiver counts on the line or the line above, as `docs/waivers.md` already defines
  for every waiver.
- The description file is the literal `.prawduct/.pr-body.md`, written after the coverage gate
  passes and removed after `gh pr create`. No managed ignore entry fits it, and a new entry would
  raise the ignore-drift advisory in every governed repo. Settled by the constraint "no new nag".
- A doc-only PR skips the review gates and still runs `check-pr-hygiene`: a credential can sit in
  prose. Not settled by the goals; chosen as the direction that fails closed.
- The Update flow re-runs the coverage gate and the hygiene check on every update instead of
  judging which deltas are judgeable; both take seconds and the coverage gate already decides that.
  Settled by the architecture goal that nothing the flow needs is judged by eye.
- A retired command exits 1 with one line on stderr, from one table, checked before argument
  parsing. A `pr` key in `.gates-waived` is reported as retired with no effect.
- This repo's own `.gitignore` keeps its `.prawduct/.pr-reviews/` line: clones hold leftover
  evidence files, and the managed list (what `update-gitignore` adds) is what shrank.
- `learnings_change_set`, `files_for_paths` and `encode.affected_matches` went with the operations
  that were their only callers.
- The cache's path index stops being written, and its table stays in the schema: a version bump
  makes every cache read answer `unavailable` until a sync that discards the cursor and re-fetches
  the whole backlog. Filed as #1143 to ride the next schema change. Stakes were not high enough to
  stop for; the goals do not settle whether the item-level `affected` field should still exist,
  and that question is on #1143 for the owner.
- No `Retires:` line accompanies the amendments: each retired phrase survives either in a norm
  statement that is deliberately unedited or in dated artifacts outside `archive/`, so the check
  the line feeds would warn on text nobody may edit.
- The credential exception is recorded as a ruling in the architecture norm's `Rulings:` field,
  not as a temporary exception with a clock: the owner confirmed it without a term, and
  `docs/norms.md` puts the clock on temporary exceptions only.

**Level:** Medium. The removal is well understood and its sites are enumerable by query. What would
raise it: one real `/prawduct:pr create` run through the rewritten flow
in a fresh session after the installed plugin advances, which this plan queues rather than claims.

## Verification Strategy

Each new command's tests are red first at the behaviour the chunk adds, and each names the input
that must trip it. The removal chunks return falsifying queries with their reports: a search, in
more than one phrasing, for every name and claim the chunk retires, over `plugin/`, `tests/`,
`tools/`, `documentation/` and the live artifacts, returning nothing but history. The acceptance
line "`stats` and `review-stats` still read old `review.pr` events" is a kept test over the real
fixture, not a reading of the code. The full suite runs once, on the integrated branch. A live
`/prawduct:pr create` through the new flow cannot be observed in the session that edits the skill
(the harness serves the copy it loaded), so it is queued for the first fresh session after the
installed plugin advances.

## Build Chunks

### Chunk 01: The PR gate answers by code what the reviewer was asked to notice

- **Description:** Two read-only commands and the module behind them.
  `check-pr-hygiene [--json]` answers over merge-base…HEAD of the checked-out branch, the base
  taken from the one resolver `resolve-base` uses. It reports named results:
  `credential-shape` (refuses; an added line matches the plugin's credential denylist and carries no
  `prawduct:allow prawduct/credential-shape -- reason` waiver; the output names file, line and the
  shape's class, never the matched text); `closes-unresolved` (warning; an id in the branch's change
  record `closes:` list that the backlog does not resolve); `closes-still-open` (warning; markdown
  backend only, where the archive rides the branch); `close-owed-at-merge` (information; Issues
  backend, the ids the PR description must carry); `chunks-open` (information; the bound plan's open
  chunks); `review-tree-changed` (information; reviews on the composed coverage path that were
  consolidated over a changed tree, for the PR description). Exit 0 when nothing refuses, 1 when
  something does, 3 when it could not answer at all; a single result that could not be read says
  `unchecked` with its reason and never reads as clean.
  `check-pr-body [<body file>] [--template <path>] [--json]` finds the repo's PR template at the
  locations in this plan's Constraints. With no file it prints what the description must follow: the
  template path or paths, and a `CONTRIBUTING` file where one exists. With a file it checks that
  every heading and every checklist item of the template appears in the body: exit 0 followed or no
  template (naming where it looked), exit 1 naming each missing line or listing the candidates when
  more than one template exists and none was chosen, exit 3 when the body cannot be read. A refusal
  from either command is recorded through `evidence.append_guard_refusal`. Expected yield, stated
  for the ratchet: the closure results inherit R-2's history; a template refusal has no history,
  being the first control of its kind; a credential refusal is expected to be near zero.
- **Depends on:** none
- **Exposed API:** `prawduct-hook` CLI
- **Foreign API:** GitHub pull request templates
- **Deliverables:** new `plugin/lib/pr_gate.py`; the two commands registered in
  `plugin/bin/prawduct-hook` with their usage and read-only classification; new
  `tests/test_pr_gate.py`; the commands' entries in `.prawduct/artifacts/api-contract.md`
  (§ Operations and the surface inventory).
- **Tests:** Red first. Hygiene: an added line carrying a credential shape refuses and the output
  does not contain the credential; the same line with a waiver passes; a credential on a line the
  branch did not add is not reported; a `closes:` id the backlog does not know warns; on a markdown
  backend a `closes:` id still open warns and on an Issues backend it is listed as owed at merge;
  an unresolvable base exits 3. Body: a body missing one template heading exits 1 naming it; a body
  with every heading and checklist item exits 0; no template exits 0 and names the locations
  searched; a template in each of the three locations is found, with a differently cased filename
  and a `.txt` extension; two candidates with no `--template` exit 1 and list both; `--template`
  resolves it. Each refusal lands a `guard-refusal` fact.
- **Acceptance criteria:** on a branch whose change record closes an item the backlog contradicts,
  whose description omits a section of the repo's PR template, or which adds a credential-shaped
  line, the flow's commands say so by name with a non-zero exit where the result refuses; on a clean
  branch each prints one line.
- **Done when:**
  0. verify-api: GitHub's template rules read from its documentation (recorded in Constraints,
     2026-11-11); the fake template layouts in the tests are built from those rules
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: `/prawduct:pr` opens a PR with no reviewer, and the reviewer's machinery exits

- **Description:** Rewrite the PR skill's Create, Update and Merge flows so no agent is dispatched.
  Create: the coverage gate is the gate; the step that waited on the reviewer becomes
  `check-pr-hygiene`; the evidence-file verification and its ledger append go; the description is
  drafted to a file, following what `check-pr-body` names, checked by `check-pr-body <file>`, and
  created with `gh pr create --body-file`; the description carries the closes lines, the
  owed-at-merge line and any `review-tree-changed` lines the hygiene command printed. Update: a
  judgeable delta re-runs the coverage gate and `check-pr-hygiene`, and an edited description
  re-runs `check-pr-body`. Merge: the evidence check becomes the coverage gate where the branch is
  checked out, and the evidence-file deletion goes. Remove, as one exit: the `pr-reviewer` agent,
  the PR review protocol, the payload builder and its command, the `pr-review-dispatch` command and
  the `review.pr` dispatch mark, the `review.pr` writer in `ledger-append` (readers stay), the Stop
  hook's PR-evidence gate with its `gh pr list` probe and its `gates.json` entry, the scaffolded
  `.prawduct/.pr-reviews/` directory and the ignore-list entries for it and the dispatch mark, and
  every test and fixture that exists only for them. A `pr` key in an existing `.gates-waived` file
  is tolerated and waives nothing. The dispatcher answers each retired command name with what
  replaced it and a non-zero exit. `tools/pr-review-yield.py` is kept as the derivation of the
  numbers #1129 cites, described as a reader of history.
- **Depends on:** Chunk 01 (the two commands' names and exits, as that chunk states them)
- **Exposed API:** `prawduct-hook` CLI
- **Deliverables:** `plugin/skills/pr/SKILL.md`; deleted `plugin/skills/pr/review-protocol.md`;
  deleted `plugin/agents/pr-reviewer.md`; deleted `plugin/lib/pr_payload.py`;
  `plugin/bin/prawduct-hook`; `plugin/lib/ledger.py`; `plugin/lib/review_dispatch.py`;
  `plugin/hooks/gates.json`; `plugin/lib/init_product.py`; `plugin/lib/core.py`;
  `plugin/lib/coverage.py`; `.gitignore`; the tests that pinned the removed machinery, deleted or
  rewritten to pin the new flow; `.prawduct/artifacts/api-contract.md` (the removed commands).
- **Tests:** Red first: the PR skill grants no `Agent` tool and names no reviewer dispatch; its
  grants cover exactly the commands its body runs, the two new ones included; a Stop with a PR open
  and no evidence file does not block and runs no `gh` probe; `ledger-append --event review.pr` is
  refused with a message naming why; each retired command name exits non-zero with its replacement
  named; `init-product` creates no `.pr-reviews` directory; `stats` and `review-stats` still read
  the recorded `review.pr` events in the real fixture; a `.gates-waived` file carrying `pr` raises
  no error.
- **Acceptance criteria:** `/prawduct:pr create` on a branch with composed coverage opens the PR
  with no agent dispatched; a secrets check and the template check run in that flow by command; the
  Stop hook neither blocks on nor probes for PR-review evidence; old `review.pr` events are still
  counted.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. The falsifying search for the retired names (`pr-reviewer`, `pr-review-payload`,
     `pr-review-dispatch`, `.pr-reviews`, `pr_payload`, `commit_reviewed`, and the phrases "PR
     reviewer" and "release-readiness review") over the files this chunk owns returns only readers
     of history
  3. Committed (reviewed at the plan boundary)

### Chunk 03: No prose or artifact names the PR reviewer as a live mechanism

- **Description:** Sweep by the claim, not by a list of files: every sentence outside Chunk 02's
  files saying that a PR reviewer runs, is dispatched, gates a PR, writes evidence, or shares the
  boundary with the Critic. That covers the methodology guides and the session digest, the Critic's
  own skill files where they describe the PR review beside them, the other skills, `plugin/docs/`,
  the templates and the product anchor they scaffold, `AGENTS.md`, `documentation/`, the tools'
  descriptions, and the live artifacts under `.prawduct/artifacts/` (not archives, discovery notes,
  investigations, old plans, release notes or the change-log archive). Sort what each sentence was
  doing before cutting it: a rule that died with the reviewer is deleted, a rule that still holds is
  rewritten for its new owner, and a rule whose reason was the reviewer is checked for having
  inverted. Record the amendments the reviewer's exit makes to binding norms beneath their clauses,
  with the owner's words of 2026-11-10 and the date, statements unedited:
  `nonfunctional-requirements.md` (the stage-keyed rigor norm, and the PR-boundary target's
  two-reviews-in-parallel sentence), `data-model.md` (the reserved `pr-review` fact kind and the
  dispatch-mark and evidence-file descriptions), `project-preferences.md` where a row names the PR
  dispatch. `plugin/CHANGELOG.md` is the release's to write, not this chunk's.
- **Depends on:** none (it writes against this plan's statement of the new flow)
- **Deliverables:** `plugin/methodology/building.md`; `plugin/methodology/delegation.md`;
  `plugin/methodology/session-digest.md`; `plugin/skills/critic/review-cycle.md`;
  `plugin/skills/critic/cross-checks.md`; `plugin/docs/norms.md`;
  `plugin/docs/governance-telemetry.md`; `AGENTS.md`; `documentation/project-structure.md`;
  `documentation/release-process.md`; `.prawduct/artifacts/nonfunctional-requirements.md`;
  `.prawduct/artifacts/data-model.md`; `.prawduct/artifacts/project-preferences.md`;
  `.prawduct/cross-cutting-concerns.md`; and every other file the claim search finds.
- **Tests:** the prose pins that read these files (token budgets, the digest's character wall, the
  cutover and methodology coherence tests) pass, with a ceiling lowered in the same commit where a
  cut lands under it. Where a deleted sentence was pinned by a test, the pin goes with it or is
  restated for the rule's new owner; no pin is weakened to pass.
- **Acceptance criteria:** a reader of any live guide, skill, template or artifact is told the PR
  boundary has one reviewer and that `/prawduct:pr` dispatches none; each amended norm carries the
  owner's words and its statement is unchanged.
- **Done when:**
  1. Acceptance criteria met and the prose pins pass
  2. The claim search, in more than one phrasing, over everything outside history returns nothing,
     and its output is in the builder's report
  3. Committed (reviewed at the plan boundary)

### Chunk 04: Three operations no reviewer reads are removed, and the claim that one walks the backlog

- **Description:** Remove `learnings-files --for-diff` (the bare command and `--json` stay), and the
  backlog cache queries `affecting` and `created-since`, with the functions only they called, their
  tests and their documentation. Sweep the claim that a reviewer walks or reads the backlog cache
  wherever it is stated; the sites known on 2026-11-10 were docstrings in `plugin/lib/briefing.py`,
  `plugin/lib/backlog/cli.py`, `plugin/lib/backlog/sync.py` and `plugin/lib/backlog/cachequery.py`
  and two passages in `documentation/backlog-service-cache-spec.md`, and the search is by the claim,
  not those names. Name who does read the cache now (the backlog skill, the janitor, the bug-report
  triage, and `check-pr-hygiene`'s closure check) where a sentence needs a reader. Remove the
  `critic-reviewer` agent's grants for commands its protocol no longer instructs, after checking
  each against the Critic's own files.
- **Depends on:** none
- **Exposed API:** `prawduct-hook` CLI
- **Deliverables:** `plugin/bin/prawduct-hook` (the `learnings-files` command);
  `plugin/lib/gates.py`; `plugin/lib/learnings_files.py`; `plugin/lib/backlog/cli.py`;
  `plugin/lib/backlog/cachequery.py`; `plugin/lib/backlog/sync.py`; `plugin/lib/briefing.py`;
  `plugin/skills/backlog/cache-reads.md`; `plugin/skills/backlog/adapter-mode.md`;
  `plugin/agents/critic-reviewer.md`; `documentation/backlog-service-cache-spec.md`;
  `.prawduct/artifacts/api-contract.md` (the `learnings-files` entry and the stable-tier sentence
  naming who binds it); the affected tests.
- **Tests:** Red first: `learnings-files --for-diff` is rejected as an unknown flag; `backlog
  cache-query affecting` and `created-since` are rejected as unknown queries with the usage naming
  the queries that remain; the remaining queries and the bare `learnings-files` answer as before.
- **Acceptance criteria:** the three operations are gone from the code, the usage text, the skills
  and the contract; no sentence says a reviewer walks the backlog.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. The falsifying searches (`for-diff`, `for_diff`, `created-since`, `created_since`,
     `affecting` as a query name, and the backlog-walk claim in more than one phrasing) return only
     history, and their output is in the builder's report
  3. Committed (reviewed at the plan boundary)

### Chunk 05: The record, the seams, and the boundary review

- **Type:** cumulative-final
- **Description:** The coordinator's chunk. Reconcile the PR skill's two steps that call Chunk 01's
  commands against the handlers as built. Write the change fragment, whose body lists each former
  PR-review check as moved to the Critic, moved to code (naming the check) or dropped, and whose
  consumer note says what a governed product sees: no reviewer at the PR, two commands in the flow,
  a description checked against its PR template, the Stop hook no longer asking for PR-review
  evidence, leftover `.prawduct/.pr-reviews/` files safe to delete. Record the owner's two answers
  where each landed. Run the full suite once on the integrated branch.
- **Depends on:** Chunks 01-04
- **Deliverables:** new `.prawduct/changes/pr-reviewer-fold.md`; this plan's Goals;
  `.prawduct/owner-rulings.md`.
- **Acceptance criteria:** #1129's five acceptance lines each hold and each is shown by a command
  or a test named in the change record.
- **Done when:**
  1. Acceptance criteria met; suite green on the integrated branch
  2. Committed, then one `/prawduct:critic cumulative`; its blocking findings resolved
