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

- **PR creation**: wait_for_user (default: wait_for_user — only create PRs when explicitly asked; set to "automatic" to create PRs after Critic review passes)

---

**What belongs here**: How you want code written. Conventions, tools, style preferences, workflow preferences.

**What doesn't belong here**: What to build (product-brief), system design (data-model, architecture), performance targets (nonfunctional-requirements), or deployment (operational-spec).
