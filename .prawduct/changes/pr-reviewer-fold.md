---
schema: 1
type: feature
scope: pr-reviewer-fold
date: 2026-11-11
title: The PR boundary has one reviewer, and the PR gate answers by code
closes: [brookstalley/prawduct#1129]
---
The owner ruled on 2026-11-10: "yes fold PR reviewer in", reversing the 2026-07 decision to keep
two boundary reviewers. Measured that day from the governance ledgers of the governed products
active in the previous 60 days (`python3 tools/pr-review-yield.py` re-derives it per repo): 583 PR
reviews and no blocking finding. `/prawduct:pr` now dispatches no agent. Its gate is the composed
Critic coverage it already required, plus two commands.

### The PR gate's two commands (Chunk 01)

`prawduct-hook check-pr-hygiene` answers over merge-base…HEAD and names each result:
`credential-shape` refuses the PR when a line the branch adds matches the plugin's credential
denylist and carries no `prawduct:allow prawduct/credential-shape -- reason` waiver, naming file,
line and the shape's class and never the text; `closes-unresolved` and `closes-still-open` warn
when the change record's `closes:` list names an id the backlog does not know, or, on a markdown
backlog, one still open; `close-owed-at-merge`, `chunks-open` and `review-tree-changed` are
information the PR description carries. A result it could not read says `unchecked`.

`prawduct-hook check-pr-body [<file>] [--template <path>]` finds the repo's PR template where
GitHub looks for one (`pull_request_template` in the root, `docs/` or `.github/`, any case, or a
`PULL_REQUEST_TEMPLATE/` directory there) and refuses a description that lacks one of the
template's headings or checklist items. Several templates with none chosen is a refusal that lists
them. With no file it prints what the description must follow, a `CONTRIBUTING` file included.
This is new: nothing in the plugin read a PR template before, and the owner asked on 2026-11-11
that the flow honour "repo standards like PR templates".

Each refusal is a `guard-refusal` fact (`pr-hygiene`, `pr-body-template`), so how often either
fires is `prawduct-hook evidence list --kind guard-refusal`.

The credential check is a bounded exception to `architecture.md` § Direction ("prawduct never
re-implements what a product's own tooling already does"), confirmed by the owner on 2026-11-11
and recorded in that norm's Rulings. No debug-code check is written: that is a linter's rule.

### `/prawduct:pr` dispatches no reviewer, and the reviewer's machinery is gone (Chunk 02)

The Create flow's review gate is `check-cumulative-critic` alone; `check-pr-hygiene` runs where
the reviewer was dispatched; the description is drafted to `.prawduct/.pr-body.md`, checked by
`check-pr-body`, passed to `gh pr create --body-file` and removed. Update re-runs the coverage
gate and the hygiene check on every update. Merge checks coverage where it checked for an evidence
file. "The branch moved after the review" is answered by the coverage gate, which composes over
trees at HEAD.

Removed: the `pr-reviewer` agent, `skills/pr/review-protocol.md`, `lib/pr_payload.py`, the
commands `pr-review-payload` and `pr-review-dispatch`, the `review.pr` dispatch mark, the
`review.pr` writer in `ledger-append`, the Stop hook's PR-evidence gate with its `gh pr list`
probe and its `gates.json` entry, the scaffolded `.prawduct/.pr-reviews/` directory, and the
ignore-list entries for it and the dispatch mark. The dispatcher answers each retired command by
name with a non-zero exit and what to do. A `pr` key in a `.gates-waived` file is reported as
retired and waives nothing. Recorded `review.pr` ledger events are still read by `review-stats`
and `tools/pr-review-yield.py`.

The removal is outright, outside a major version, on the owner's ruling of 2026-11-11, recorded
in `api-contract.md` § Deprecation & Compatibility beside #303's.

### Where each former PR-review check went

| Former check | Now |
|---|---|
| The bundle is one change and matches its stated work; each capability traces to a requirement | The Critic: Goal 3 and Goal 5's `scope-trace:` question |
| The change record's prose describes all the diff ships; a consumer note is honest; the commits read as one story | Dropped |
| Change-record keys are the ones the gates read | Code already: `check-change-log-entry`, record-lint `change-fragment` |
| A legacy single-file entry with a placeholder `release=` value | Dropped |
| Version bump, tag and entry agree | Dropped at the PR; the release checklist |
| A chunk this bundle delivers still reads open | Code: `check-pr-hygiene` `chunks-open` |
| A chunk reads done or dropped against what the bundle did | Dropped as its own check; the Critic's Goal 2 |
| A plan claiming a branch that does not exist, or none | Code already: the binding advisories |
| A norm amended to bless the bundle's own code | The Critic, which blocks it |
| Test evidence covers what ships | Code already: `test-status` |
| An item the diff happens to resolve is still open | Dropped |
| The branch claims a closure the backlog contradicts | Code: `check-pr-hygiene` `closes-unresolved`, `closes-still-open` |
| A raise of `core.md`'s cap without the owner's approval | Code already: record-lint `learnings-core-raise-unapproved` |
| A review consolidated over a tree that changed during it | Code: `check-pr-hygiene` `review-tree-changed`, carried into the PR description |
| Secrets or credentials in the diff | Code: `check-pr-hygiene` `credential-shape` |
| Debug code, commented-out experiments, TODOs and placeholders | Dropped at the PR gate; the product's linter, and the Critic's Goal 7 |
| Unintended files | Dropped; the Critic's Goal 3 |
| Migration or rollback notes for a changed persisted format | Dropped as its own check; the Critic's Goals 4 and 5 |
| Bundle-level simplification | Dropped |
| A rule that exists and nothing enforces is filed once | The Critic's reviewer contract |
| A closing keyword is not a close | The PR flow's create and merge steps |
| The description follows the repo's PR template | Code, new: `check-pr-body` |

### The prose and the norms (Chunk 03)

Every live guide, skill, template and artifact that said a PR reviewer runs now says the PR
boundary has one review. Seven amendments sit beneath their clauses with the owner's words and
the statements unedited: in `nonfunctional-requirements.md` the wall-clock norm, the stage-keyed
rigor norm, the PR-boundary target and the recorded keep of the `pr` mode; in `data-model.md` the
Critic-data-plane norm and the dispatch-mark clauses; in `project-preferences.md` the
reviewer-model row.

### Three operations with no reader are removed (Chunk 04)

`learnings-files --for-diff` and the backlog cache queries `affecting` and `created-since` are
removed on the owner's ruling of 2026-11-10; each is refused as an unknown flag or query, naming
what remains. The claim that a reviewer walks the backlog cache is gone from the code and the
cache spec. The cache's path index is no longer written; its empty table stays in the schema until
another change bumps the version (#1143), since a bump alone costs each repo a full re-fetch.

## Consumer note
`/prawduct:pr` no longer runs a PR reviewer. A PR opens when Critic reviews cover the branch, and
two commands run in the flow: `check-pr-hygiene`, which stops the PR on a credential-shaped line
the branch adds (a fixture or documented example takes a `prawduct:allow prawduct/credential-shape
-- reason` comment) and warns when the change record closes an item the backlog does not know; and
`check-pr-body`, which holds the PR description to your repo's PR template when it has one. The
Stop hook no longer asks for PR-review evidence, and no longer calls `gh` at the end of a turn.
Files left in `.prawduct/.pr-reviews/` are unused and safe to delete. A session that was already
open when the plugin updated must be restarted before it can open a PR: its loaded skill text
calls commands that were removed, and they say so. `learnings-files --for-diff` and the cache
queries `affecting` and `created-since` are gone.
