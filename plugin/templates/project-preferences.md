# Project Preferences

Developer preferences for how code is written in this project. Captured during discovery, updated as preferences evolve. Every session should read this before writing code.

## Language & Runtime

- **Language**:
- **Version**:
- **Package manager**:

## Code Style

- **Naming**: (e.g., snake_case functions, PascalCase classes)
- **Formatting**: (e.g., black, prettier, gofmt)
- **Linting**: (e.g., ruff, eslint)
- **Type annotations**: (e.g., required, preferred, not used)
- **Imports**: (e.g., absolute, grouped by stdlib/third-party/local)

## Testing

- **Framework**: (e.g., pytest, vitest, go test)
- **Style**: (e.g., descriptive names, AAA pattern, table-driven)
- **Coverage expectations**: (e.g., happy path + error cases, comprehensive edge cases)
- **Testing strategies**: (e.g., property-based (hypothesis), property-based (proptest), contract testing, not applicable)
- **Test location**: (e.g., tests/ mirror of src/, colocated, __tests__/)
- **Parallelization**: (e.g., pytest-xdist with --dist loadgroup, vitest threads)

## Architecture Patterns

- **Data modeling**: (e.g., Pydantic v2, TypeScript interfaces, Go structs)
- **Error handling**: (e.g., exceptions, Result types, error codes)
- **Async**: (e.g., async/await throughout, sync unless needed)
- **File organization**: (e.g., feature folders, layer folders, flat)

## Tooling

- **Key libraries**: (list anything non-obvious that new sessions should know about)
- **Dev commands**: (e.g., `pytest tests/`, `npm run dev`, `cargo test`)

## Workflow

- **Branching**: feature-branches (default: feature-branches — create a branch for medium+ work, direct commits to protected branches only for trivial fixes; set to "direct" for solo projects where committing to main is OK)
- **Protected branches**: main, develop (branches that should not receive direct commits unless branching is "direct")
- **PR creation**: wait_for_user (default: wait_for_user — only create PRs when explicitly asked; set to "automatic" to create PRs after Critic review passes)
- **PR merge**: wait_for_user (default: wait_for_user — present the PR for user review before merging; set to "automatic" to merge after CI passes and review is clean)
- **PR merge strategy**: merge commit (default: merge commit — `gh pr merge --merge`; preserves each commit's identity so a reused branch's merge-base stays correct and the review/PR gates don't re-review already-merged work; set to "squash" for one linear commit per PR, or "rebase" — with either, branches are single-use: delete after merge and never reuse, because the rewritten history strands a reused branch's merge-base)
- **Commit attribution**: none (default: none — no `Co-Authored-By`, `Signed-off-by`, or "Generated with …" trailers on commits or PR bodies; set to "co-authored" to add a Claude `Co-Authored-By` trailer)
- **Delegation**: (unset — `/prawduct:methodology delegation` states the default and anything written here overrides it. Say in prose how much this project wants fanned out to subagents and what it is worth fanning out for. `off` is a complete answer: it means no delegation at all, it is honoured without ceremony, and nothing nags a repo that has said it.)
- **Delegate verification**: (unset — what a delegate here may run to prove its own change, and what it must leave to the coordinator's integration run. In this project's own words: prawduct does not know this project's test regime and will not invent a vocabulary for it. `/prawduct:doctor` will propose a starting point from what this repo already encodes about running part of its suite.)
- **Delegation approval**: ask-on-reason (default: ask-on-reason — a plan that will delegate discloses it and proceeds, asking for approval only on one of the enumerated reasons in `methodology/planning.md` "Partition: Serial or Delegated"; set to "pre-approved" once you have seen it work here, and the ask stops returning with every plan)

---

**What belongs here**: How you want code written. Conventions, tools, style preferences, workflow preferences.

**What doesn't belong here**: What to build (product-brief), system design (data-model, architecture), performance targets (nonfunctional-requirements), or deployment (operational-spec).

## Enforcement

Each preference above should be enforced by one of three mechanisms — assign the mechanism when you add the preference so it doesn't quietly become aspirational.

| Mechanism | Where it lives | What it catches | Trade-off |
|---|---|---|---|
| **Linter** | Project's configured linter (ruff, eslint, swiftlint, etc.) | Mechanical style/naming rules | Best tool when configured. If no linter, preferences in this category fall through to Critic. |
| **Test** | `tests/preferences/test_*.py` (or equivalent) | Structural rules with named exceptions (AST checks, config-presence checks) | Bakes the rule into CI; refuses to be silent. Cost: re-validate when the rule's shape changes. |
| **Critic** | `/critic` review (Goal 4: Norms) | Judgment-required rules (semantic naming, "appropriate" anything, what counts as a "boundary") | No false-confidence test. Cost: requires reviewer per chunk; misses violations between reviews. |

This per-preference table is the product's **norm index** (`/prawduct:methodology norms`): each row assigns a norm its **mechanism** (linter / test / Critic) and its **audit home** — `janitor` (only the deep sweep sees it) or `advisory` (a mechanical probe fires on it). A row may be a **pointer** to a `## Direction` section instead of restating the norm, and every norm carries its **why** (a whyless norm is unenforceable at its edges).

**Every populated row here *is* a homed norm** — the `norm-health-sweep-overdue` advisory reads
these rows to decide whether this product has norms worth auditing, so never leave an example or
placeholder row in the table: it would claim a norm registry that has not been ratified. Two row
shapes go in — an ordinary row naming the convention, its mechanism, its enforcement artifact, its
audit home (`janitor` or `advisory`) and its why; and a **pointer** row whose first cell reads
`norm lives in <artifact> § Direction`, whose enforcement artifact is `—`, and whose why lives in
the Direction entry it points at.

| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |
|---|---|---|---|---|

**A filled `Delegation` / `Delegate verification` row states a norm, and it takes `Critic`** — a policy stated in prose is judgment-required by construction, so no linter or test can grade it; audit home `janitor`, and the why is the sentence the owner gave for it. One row covers the policy the two state together. `Delegation approval` is a setting like `PR creation`, not a norm. The row is written when the policy is **ratified** (`/prawduct:doctor` proposes, the owner confirms), never shipped here, because this table ships empty.

**Rule for adding a new preference:** assign a mechanism. If the preference can be expressed as "every file/function/config matches pattern X with named exceptions" → write a test. If a linter rule already exists for it → configure the linter. If it requires understanding intent → assign to Critic. Never leave a preference unassigned.

**False-confidence guardrail:** if a generated test would pass on conforming code but couldn't reliably catch a real violation (e.g., greppy heuristics for semantic rules), prefer Critic over a weak test. A green test that doesn't actually check the rule is worse than no test.
