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
- **Imports**: `from __future__ import annotations` at top of every implementation file in `tools/` and `tests/` (backward-compat shims and `tests/conftest.py` excepted); grouped by stdlib / third-party / local

## Testing

- **Framework**: pytest
- **Style**: Class-based test grouping (`class TestFeatureName`), descriptive method names (`test_returns_none_for_missing`), AAA pattern
- **Coverage expectations**: Happy path + error cases + edge cases; mock external dependencies (subprocess, filesystem). Every public (non-underscore) module-level function in `tools/lib/` should be referenced by at least one test (directly imported, called, or attribute-accessed). Functions exercised only transitively (called from a tested entry point but never imported by a test) are tracked in the test's exemption list with a resolution path.
- **Testing strategies**: Not applicable — CLI tools with deterministic I/O; no property-based testing currently
- **Test location**: `tests/` directory. Test files are organized by capability (`test_prawduct_sync.py`, `test_prawduct_init.py`, `test_prawduct_migrate.py`, `test_prawduct_validate.py`); each loads from the consolidated `tools/prawduct-setup.py` entry point
- **Parallelization**: pytest-xdist via `pyproject.toml` (`-n auto --dist loadfile`); `tests/conftest.py` groups same-directory tests onto one worker for fixture/state isolation
- **Module loading**: Scripts with hyphens loaded via `importlib.util.spec_from_file_location`

## Architecture Patterns

- **Data modeling**: Plain dicts for JSON data, Path objects for filesystem
- **Error handling**: Return-value based — internal functions in `tools/lib/` return dicts with `status`/`reason` fields rather than raising. Exceptions are only allowed to escape at **boundaries**: CLI entry points (`tools/prawduct-setup.py` argparse handlers, `tools/product-hook` subcommands), subprocess wrappers (when the underlying command is expected to fail and we can't recover), and unexpected `OSError`/`json.JSONDecodeError` at filesystem/parse boundaries (caught and logged with context, never silently swallowed). New code that raises within tool internals (anything called from another `tools/lib/` function) is a violation.
- **Async**: Sync throughout — CLI tools, no async needed
- **File organization**: `tools/` for entry-point scripts (`prawduct-setup.py` plus backward-compat shims), `tools/lib/` for the implementation subpackage (`core.py`, `init_cmd.py`, `migrate_cmd.py`, `sync_cmd.py`, `validate_cmd.py`), `templates/` for product templates, `tests/` for tests

## Tooling

- **Key libraries**: pytest (testing), importlib (hyphenated module loading), subprocess (git/external commands)
- **Subprocess safety**: Always pass arguments as a list (`subprocess.run(["git", "status"])`); never use `shell=True`. The list-form is safe against command injection when arguments are path-derived or otherwise constructed; `shell=True` is not.
- **Dev commands**: `pytest tests/ -v` (full suite), `pytest tests/test_prawduct_sync.py -v` (sync subset)

## Workflow

- **Branching**: direct — solo framework project; commits to `main` are OK for version bumps and small fixes. Use a feature branch for medium+ work.
- **Protected branches**: none enforced (direct workflow)
- **PR creation**: wait_for_user — only create PRs when explicitly asked
- **PR merge**: wait_for_user — present the PR for user review before merging

---

**What belongs here**: How you want code written. Conventions, tools, style preferences.

**What doesn't belong here**: What to build (product-brief), system design (data-model, architecture), performance targets (nonfunctional-requirements), or deployment (operational-spec).

## Enforcement

Each preference is enforced by one of three mechanisms. This table is the source of truth for *how* a preference is checked — when adding a preference, decide its enforcement here so it doesn't quietly become aspirational.

| Mechanism | Where it lives | What it catches | Trade-off |
|---|---|---|---|
| **Test** | `tests/preferences/test_*.py` | Structural rules with named exceptions (AST checks, config-presence checks) | Bakes the rule into CI; refuses to be silent. Cost: test must be re-validated when the rule's shape changes. |
| **Linter** | (none configured for prawduct) | Mechanical style/naming rules already solved by ruff/eslint/etc. | Best tool for the job when configured. Currently N/A — preferences in this category fall through to Critic. |
| **Critic** | `/critic` review (Goal 4: Project Preferences) | Judgment-required rules (boundary detection, semantic naming, "appropriate" anything) | No false-confidence test. Cost: requires a reviewer per chunk; misses violations between reviews. |
| **Session config** | Read by Claude/methodology at session boundaries (e.g., `building.md` reads `Branching`; `/pr` reads `PR creation`) | Workflow-level decisions (when to branch, when to PR) | Configuration, not enforcement. Validated by user observing Claude's behavior, not by a test or a reviewer. |

| Preference | Mechanism | Enforcement artifact |
|---|---|---|
| `from __future__ import annotations` (Imports) | Test | `tests/preferences/test_future_annotations.py` |
| pytest-xdist parallelization config | Test | `tests/preferences/test_parallelization_config.py` |
| Sync-only architecture (no `async def`, no `asyncio`) | Test | `tests/preferences/test_sync_only_architecture.py` |
| Subprocess safety (no `shell=True`) | Test | `tests/preferences/test_subprocess_safety.py` |
| Test location (`test_*.py` only under `tests/`) | Test | `tests/preferences/test_test_location.py` |
| Public functions in `tools/lib/` referenced in tests | Test | `tests/preferences/test_public_function_coverage.py` (presence check only — see test docstring; Critic Goal 1 backstops for real coverage adequacy) |
| Naming (snake_case / PascalCase / UPPER_SNAKE) | Critic *(would be linter; no linter configured — see "Linting" above)* | Reviewer reads diff against this preference |
| Error handling (return-value based; exceptions at boundaries) | Critic | Reviewer judges what counts as a "boundary" per the definition above |
| Class-based test grouping (allows scenario-based class names) | Critic | Reviewer judges whether grouping is sensible — strict `Test<FuncName>` would over-enforce |
| Branching / PR creation / PR merge (Workflow) | Session config | Read by `building.md`, `/pr`, etc. at decision points |
| All others (Language, Version, Style, Type annotations, Testing strategy, File organization) | Critic | Reviewer reads diff against this preference |

**Rule for adding a new preference:** assign a mechanism. If the preference can be expressed as "every file/function/config matches pattern X with named exceptions" → write a test. If it requires understanding intent → assign to Critic. Never leave a preference unassigned — that's how preferences silently become aspirational.
