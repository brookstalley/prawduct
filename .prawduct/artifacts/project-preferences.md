# Project Preferences

Developer preferences for how code is written in this project. Captured during discovery, updated as preferences evolve. Every session should read this before writing code.

## Language & Runtime

- **Language**: Python 3
- **Version**: 3.10+ (uses `X | Y` union syntax, `match` statements not required)
- **Package manager**: pip. `pyproject.toml` exists for pytest configuration and dev dependencies (`pytest`, `pytest-xdist`, `pytest-timeout`, `pyyaml`) — the scripts themselves are standalone tools, not a published package

## Code Style

- **Naming**: snake_case functions/variables, PascalCase classes, UPPER_SNAKE constants
- **Formatting**: No formatter configured — follow existing style (4-space indent, ~100 char lines)
- **Linting**: No linter configured
- **Type annotations**: Used throughout — function signatures use `str | None`, `list[str]`, `dict[str, str]` style (PEP 604)
- **Imports**: `from __future__ import annotations` at top of every implementation file in `lib/`, `tests/`, and `hooks/`, plus the plugin runtime scripts `bin/prawduct-hook` and `bin/test-reference-verify` (`__init__.py` and `tests/conftest.py` excepted); grouped by stdlib / third-party / local

## Testing

- **Framework**: pytest
- **Style**: Class-based test grouping (`class TestFeatureName`), descriptive method names (`test_returns_none_for_missing`), AAA pattern
- **Coverage expectations**: Happy path + error cases + edge cases; mock external dependencies (subprocess, filesystem). Every public (non-underscore) module-level function in `lib/` should be referenced by at least one test (directly imported, called, or attribute-accessed). The dedicated coverage scanner (`test_public_function_coverage`) was retired with the file-sync `tools/lib/` in M4; the Critic's Goal 1 (test-coverage adequacy) now backstops this — restore a `lib/`-scoped scanner if untested public functions start to drift in.
- **Testing strategies**: Not applicable — CLI tools with deterministic I/O; no property-based testing currently
- **Test location**: `tests/` directory. Test files are organized by capability (`test_plugin_runtime.py`, `test_plugin_migrate.py`, `test_v5_methodology.py`, …), with preference-enforcement tests under `tests/preferences/`. Enforced by `tests/preferences/test_test_location.py` — every `test_*.py` must live under `tests/`, else `pyproject.toml`'s `testpaths` silently skips it.
- **Parallelization**: pytest-xdist via `pyproject.toml` (`-n auto --dist loadfile`); `tests/conftest.py` groups same-directory tests onto one worker for fixture/state isolation
- **Module loading**: Scripts with hyphens loaded via `importlib.util.spec_from_file_location`

## Architecture Patterns

- **Data modeling**: Plain dicts for JSON data, Path objects for filesystem
- **Error handling**: Return-value based — internal functions in `lib/` return dicts with `status`/`reason` fields rather than raising. Exceptions are only allowed to escape at **boundaries**: CLI entry points (`bin/prawduct-hook` subcommands and the `lib/*_cmd.py` / `lib/migrate_plugin.py` / `lib/init_product.py` `run()` runners they dispatch to), subprocess wrappers (when the underlying command is expected to fail and we can't recover), and unexpected `OSError`/`json.JSONDecodeError` at filesystem/parse boundaries (caught and logged with context, never silently swallowed). New code that raises within governance internals (anything called from another `lib/` function) is a violation.
- **Async**: Sync throughout — CLI tools, no async needed
- **File organization**: `bin/` for entry-point scripts (`prawduct-hook`, `test-reference-verify`), `lib/` for the implementation package (`core.py`, `views.py`, `critic_mode.py`, `migrate_plugin.py`, `init_product.py`, `advisory_store.py`, `advisory_cmd.py`, `audit_learnings_cmd.py`, `operator_verification.py`), `skills/` + `methodology/` + `hooks/` for the plugin governance surface, `templates/` for product artifact templates, `tests/` for tests

## Tooling

- **Key libraries**: pytest (testing), importlib (hyphenated module loading), subprocess (git/external commands)
- **Subprocess safety**: Always pass arguments as a list (`subprocess.run(["git", "status"])`); never use `shell=True`. The list-form is safe against command injection when arguments are path-derived or otherwise constructed; `shell=True` is not.
- **Dev commands**: `pytest tests/ -v` (full suite), `pytest tests/test_plugin_runtime.py -v` (a single-file subset)

## Workflow

- **Branching**: direct — solo framework project; commits to `main` are OK for version bumps and small fixes. Use a feature branch for medium+ work.
- **Protected branches**: none enforced (direct workflow)
- **PR creation**: wait_for_user — only create PRs when explicitly asked
- **PR merge**: wait_for_user — present the PR for user review before merging
- **PR merge strategy**: merge commit (`gh pr merge --merge`) — preserve each chunk's commit on the integration branch; do not squash. (Matches the `/pr` skill's default; stated explicitly here. The `develop`→`main` release is a single-parent promotion, not a merge, so feature→`develop` granularity doesn't affect it. The promotion builds `main`'s tree either by tree-set (whole-develop) or by a classified `--3way` apply (pruned) — `operational-spec.md` § Direction, amended 2026-07-29.)

---

**What belongs here**: How you want code written. Conventions, tools, style preferences.

**What doesn't belong here**: What to build (product-brief), system design (data-model, architecture), performance targets (nonfunctional-requirements), or deployment (operational-spec).

## Enforcement

Each preference is enforced by one of three mechanisms. This table is the source of truth for *how* a preference is checked — when adding a preference, decide its enforcement here so it doesn't quietly become aspirational.

| Mechanism | Where it lives | What it catches | Trade-off |
|---|---|---|---|
| **Test** | `tests/preferences/test_*.py` | Structural rules with named exceptions (AST checks, config-presence checks) | Bakes the rule into CI; refuses to be silent. Cost: test must be re-validated when the rule's shape changes. |
| **Linter** | (none configured for prawduct) | Mechanical style/naming rules already solved by ruff/eslint/etc. | Best tool for the job when configured. Currently N/A — preferences in this category fall through to Critic. |
| **Critic** | `/critic` review (Goal 4: Norms) | Judgment-required rules (boundary detection, semantic naming, "appropriate" anything) | No false-confidence test. Cost: requires a reviewer per chunk; misses violations between reviews. |
| **Session config** | Read by Claude/methodology at session boundaries (e.g., `building.md` reads `Branching`; `/pr` reads `PR creation`) | Workflow-level decisions (when to branch, when to PR) | Configuration, not enforcement. Validated by user observing Claude's behavior, not by a test or a reviewer. |

This is the product's **norm index** (`docs/norms.md`): each row assigns an enforcement mechanism, an **audit home** (which time-domain organ catches drift — `janitor` for judgment norms with no machine-readable hook; `advisory` only when a mechanical hook is named), and a terse **why**. It has two parts: **code-level preferences** (below) and **architectural Direction norms** (the pointer table after it, indexing the `## Direction` sections in the strategy artifacts).

### Code-level preferences

| Preference | Mechanism | Enforcement artifact | Audit home | Why |
|---|---|---|---|---|
| `from __future__ import annotations` (Imports) | Test | `tests/preferences/test_future_annotations.py` | CI (test) | uniform forward-ref typing across the runtime |
| pytest-xdist parallelization config | Test | `tests/preferences/test_parallelization_config.py` | CI (test) | parallel fixture/state isolation must not regress |
| Sync-only architecture (no `async def`, no `asyncio`) | Test | `tests/preferences/test_sync_only_architecture.py` | CI (test) | CLI tools with deterministic I/O — async adds no value, only surface |
| Subprocess safety (no `shell=True`) | Test | `tests/preferences/test_subprocess_safety.py` | CI (test) | `shell=True` is a command-injection surface (`security-model.md` supply-chain) |
| No upstream content egress (norm lives in `security-model.md` § Direction, `in-transition` — BKL-7Q4M) | Test | `tests/preferences/test_no_upstream_content_egress.py` | CI (test) | a private repo filing into prawduct's public tracker crosses a trust boundary irreversibly; the interim rule holds until safe upstream filing is designed |
| Test location (`test_*.py` only under `tests/`) | Test | `tests/preferences/test_test_location.py` | CI (test) | `testpaths` silently skips misplaced tests |
| Every build-plan read decodes UTF-8 and guards the same except-set | Test | `tests/preferences/test_build_plan_decoding.py` (file-scoped over the two owning modules + AST data-flow elsewhere) | CI (test) | the risk is readers *disagreeing* about whether a plan parses; held as a convention for five review rounds and lost every one |
| Agent-facing prose names both handoff files, never only the machine's | Test | `tests/preferences/test_handoff_prose.py` | CI (test) | naming only `.session-handoff.md` is the affordance that made agents write it; co-naming is structural, unlike a verb list |
| No suite-total test claim in durable plugin prose, and no surface that asks for one | Test | `tests/preferences/test_no_suite_total_claims.py` | CI (test) | the evidence store records pass/fail per tree, so a prose copy is a hand-maintained duplicate that drifts and buys review rounds correcting itself; the sweep found the surface already clean and no instruction demanding a count, so the guard IS the deliverable — the habit lives in agents, not in a template to delete |
| Critic skill structure: both mode names present in the canonical instruction files | Test | `tests/preferences/test_critic_skill_structure.py` | CI (test) | losing the terminology fails safe to `final`, which *masks* the regression by always running the full review |
| Reviewers run on the session model — no intelligent model switching | Test | `tests/preferences/test_reviewer_model_dispatch_prose.py` | CI (test) | risk-tier→model mapping escalated on almost any declared risk surface; the pin is against re-introduction |
| Public functions in `lib/` referenced in tests | Critic | Goal 1 (test-coverage adequacy) — the dedicated `test_public_function_coverage` scanner was retired with `tools/lib/` (M4); restore a `lib/`-scoped scanner if drift appears | Critic + janitor | untested public API drifts in silently |
| Naming (snake_case / PascalCase / UPPER_SNAKE) | Critic *(would be linter; no linter configured — see "Linting" above)* | Reviewer reads diff against this preference | Critic + janitor | readability; no linter configured |
| Error handling (return-value based; exceptions at boundaries) | Critic | Reviewer judges what counts as a "boundary" per the definition above | Critic + janitor | return-value discipline; exceptions only escape at boundaries |
| Class-based test grouping (allows scenario-based class names) | Critic | Reviewer judges whether grouping is sensible — strict `Test<FuncName>` would over-enforce | Critic | sensible scenario grouping without over-enforcement |
| Branching / PR creation / PR merge / PR merge strategy (Workflow) | Session config | Read by `building.md`, `/pr`, etc. at decision points | user-observed | workflow decisions, read at session boundaries |
| All others (Language, Version, Style, Type annotations, Testing strategy, File organization) | Critic | Reviewer reads diff against this preference | Critic | style/structure conventions |

### Direction norms (architectural — ratified 2026-07-17)

Pointer rows into the `## Direction` sections of the strategy artifacts. The statement + full why + status live in each artifact; this table is the index.

| Norm (pointer) | Home § Direction | Mechanism | Audit home | Why (terse) |
|---|---|---|---|---|
| Verdicts computed from facts, no model in the write path (Critic plane) | `data-model.md` | Critic | janitor | the governed party must never self-certify |
| Facts immutable & append-only | `data-model.md` | Critic + append-only code | janitor | any checkout replays the same verdict |
| Derived views never authoritative | `data-model.md` | Critic | janitor | keep mutable state out of the authority path |
| Newer-schema fact surfaced, never dropped | `data-model.md` | `evidence status` exit 2 | advisory | forward-incompatibility must be visible |
| Two stores, two lifetimes (committed answers vs. gitignored nags) | `data-model.md` | Critic + gitignore contract (doctor) | janitor | share decisions without leaking local state |
| `backlog_service_repo` selects the authoritative backlog store; the frozen markdown file is never read as live | `data-model.md` | ~~Test (`tests/test_cutover_prose_coherence.py`)~~ **absent on `main` at v3.1.1** — Critic judgment only until v3.2.0 | janitor | a frozen store answers as confidently as a live one |
| No prawduct-internal ids in operator-emitted text | `observability-strategy.md` | Critic *(no exhaustive mechanical hook — id prefixes are open-ended)* + Test for the dormancy NOTE copies | janitor | an id a downstream operator cannot resolve displaces the actionable reason |
| Reviewer never mutates its session (at the mutation site) | `architecture.md` | `clear` refusal while review active | janitor | independence enforced where mutation happens |
| Authority fails closed; advice fails soft | `architecture.md` | Critic | janitor | gates strict so governance means something; probes gentle so it's bearable |
| Local-first: no network/daemon, stdlib-only runtime | `architecture.md` | Critic | janitor | survive "just want to code"; shrink supply-chain surface |
| Plugin writes nothing into a repo but its state + reconciled files | `architecture.md` | Critic | janitor | least authority; tiny install reference |
| Python-implemented, never Python-specific — per-*file* language dispatch; unpopulated language reported unchecked, never silently passed (`in-transition` — LNG-5W8R) | `architecture.md` | Critic *(mechanical hook arrives with LNG-5W8R's unchecked report)* | janitor | governed products are Swift/Rust/C#/C/TS and routinely polyglot in one repo; silent fail-open is how Python-specificity hides |
| Prawduct guides and reviews, never implements — no product code/config/tooling; best practices enter as requirements and are enforced by Goal 2; never re-implement a linter rule (`in-transition` — LNG-5W8R) | `architecture.md` | Critic | janitor | authoring what it judges collapses the independence its verdicts depend on; a duplicated linter rule is that error one level down |
| Goals and verification bind; prescribed method is advice — a builder who finds a better route takes it and records why (`in-transition` — GOV-4T9P) | `architecture.md` | Critic *(judgment only — "is this text method or contract?" has no mechanical hook, and a lint that guessed would re-impose the prescription it exists to relax)* | janitor | a method prescription written before the code was read has spec authority and guess reliability; verification structure is carved out because it constrains the output, not the route |
| One home per fact (`in-transition` — GOV-2R8K) | `architecture.md` | Critic (Goal 4) — ask "why are there two?", not "do these agree?" | janitor | if changing a fact needs N edits, N−1 copies are already wrong; correcting every copy preserves the defect |
| Untrusted governance state is data, not instructions | `security-model.md` | Critic (Goal 4) | janitor | stale/crafted metadata is the real hazard |
| Destructive/irreversible operations need explicit owner approval at the OPERATION level (not per action); preview-by-default where the command *is* the operation | `security-model.md` | Critic | janitor | an informed decision at the moment of commitment — a 900-write migration asking 900 times gets clicked through, and confirmation fatigue is a safety regression |
| Whole-surface semver; internal CLI unversioned; evidence store schema-versioned (`api_versioning_approach`) | `api-contract.md` | Critic + `evidence status` exit 2 | janitor | one cache key; internal surface has no external consumer |
| Exit codes are the contract; stable prefix vocab; attributed errors (`api_error_model_approach`) | `api-contract.md` | Critic | janitor | skills bind to exit codes, not parsed text |
| Additive-first API evolution; tolerant readers | `api-contract.md` | Critic | janitor | keeps versions rare; N-shipped skills don't break at N+1 |
| Severity-prefix vocab + stdout=agent / stderr=user split | `observability-strategy.md` | Critic | janitor | machine-legible output; clean context injection |
| Single-writer governance ledger | `observability-strategy.md` | Critic | janitor | derived metrics are only trustworthy with one writer |
| Review wall-clock is P0 — **both** levers (run-count *and* per-mode reviewer payload); parallel, not sequential | `nonfunctional-requirements.md` | `review-stats` telemetry | janitor | latency decides partner-vs-tax |
| Proportionality ratchets both ways — a control that never catches anything is removed by default; new controls must emit yield observably (`in-transition` — the query is unbuilt; LNG-5W8R carries the enabling ledger fact) | `nonfunctional-requirements.md` | Critic | janitor (Norm Health sweep — sole home) | additions are each justified, so argument alone never reverses the drift |
| State-file size threshold is advisory, never a hard block | `nonfunctional-requirements.md` | advisory size-nag | advisory | context-weight cost; fail-soft advice, not authority |
| Conservative versioning (small feature = patch bump) | `operational-spec.md` | Critic (judgment) | janitor | keep the version number meaningful |
| Gitflow: develop=integration, main=release; promotion is a separate step | `operational-spec.md` | Session config + release tooling | janitor / doctor | clean release boundary; branch-pinned marketplace |

**Candidate awaiting the owner's ratification** (listed here rather than omitted, because an
unassigned rule is exactly what this index exists to prevent): the **handoff pair's contract** —
`.handoff-notes.md` is written by the model and only by the model, `.session-handoff.md` by the
machine and only at `/clear`. It lives in `architecture.md` § "The two model-owned session files"
as *descriptive* prose today, so by the authority rule it tracks rather than binds. It is
norm-shaped (it says who may write which file, and the whole session-continuity defect was two
writers on one file), and its enforcement already exists in code and in `test_handoff_prose.py`
above — but promoting it is the owner's call, not a builder's, and it opens a question larger than
this artifact: whether prawduct should ship **process** norms at all, as ratifiable defaults
governed products inherit, rather than only product norms. Tracked as MET-8K4R.

**Rule for adding a new preference or norm:** assign a mechanism and an audit home. A code-level rule expressible as "every file/function/config matches pattern X with named exceptions" → write a test; a rule requiring intent → Critic. An architectural norm gets a `## Direction` entry in its home artifact plus a pointer row here. Never leave one unassigned — that's how a preference or a norm silently becomes aspirational — and a named mechanism that does not yet exist is filed as backlog work at the norm's birth (`docs/norms.md`).
