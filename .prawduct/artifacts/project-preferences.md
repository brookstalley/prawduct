# Project Preferences

Developer preferences for how code is written in this project. Captured during discovery, updated as preferences evolve. Every session should read this before writing code.

## Language & Runtime

- **Language**: Python 3
- **Version**: 3.10+ (uses `X | Y` union syntax, `match` statements not required)
- **Package manager**: pip (no pyproject.toml — scripts are standalone tools, not a package)

## Code Style

- **Naming**: snake_case functions/variables, PascalCase classes, UPPER_SNAKE constants
- **Formatting**: No formatter configured — follow existing style (4-space indent, ~100 char lines)
- **Linting**: No linter configured
- **Type annotations**: Used throughout — function signatures use `str | None`, `list[str]`, `dict[str, str]` style (PEP 604)
- **Imports**: `from __future__ import annotations` at top of every file; grouped by stdlib / third-party / local

## Testing

- **Framework**: pytest
- **Style**: Class-based test grouping (`class TestFeatureName`), descriptive method names (`test_returns_none_for_missing`), AAA pattern
- **Coverage expectations**: Happy path + error cases + edge cases; mock external dependencies (subprocess, filesystem)
- **Test location**: `tests/` directory, files mirror tool names (`test_prawduct_sync.py` for `prawduct-sync.py`)
- **Module loading**: Scripts with hyphens loaded via `importlib.util.spec_from_file_location`

## Architecture Patterns

- **Data modeling**: Plain dicts for JSON data, Path objects for filesystem
- **Error handling**: Return-value based (functions return dicts with status/reason fields); exceptions caught at boundaries
- **Async**: Sync throughout — CLI tools, no async needed
- **File organization**: `tools/` for executable scripts, `templates/` for product templates, `tests/` for tests

## Tooling

- **Key libraries**: pytest (testing), importlib (hyphenated module loading), subprocess (git/external commands)
- **Dev commands**: `pytest tests/ -v` (full suite), `pytest tests/test_prawduct_sync.py -v` (sync tests)

---

**What belongs here**: How you want code written. Conventions, tools, style preferences.

**What doesn't belong here**: What to build (product-brief), system design (data-model, architecture), performance targets (nonfunctional-requirements), or deployment (operational-spec).
