---
artifact: build-plan
version: 2
scope: testament-cache-areas
branch: chore/testament-cache-areas
base: develop
working-branches: []
last_validated: 2026-11-23
partition: "delegated — 01 (Opus) owned tests/conftest.py, pyproject.toml's marker and the test files; 02 (Sonnet) owned .testament.toml. The files were disjoint and no seam was shared. The coordinator integrated both"
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer path changes"
      - "authority fails closed; advice fails soft → inapplicable because no gate or advice changes"
      - "local-first → conforms; the test environment points git at no network (GIT_ALLOW_PROTOCOL=file)"
      - "the plugin writes only its own state → inapplicable because only tests and test configuration change"
      - "written in Python, never specific to Python → inapplicable because no shipped code changes"
      - "guides and reviews, never implements → inapplicable because no shipped code changes"
      - "goals and verification bind, method is advice → conforms; the delegate chose an import-time environment over an autouse fixture so that session-scoped fixtures are covered too, and recorded why"
      - "every fact has one home → conforms; the isolating git environment is one dict, `GIT_TEST_ENV` in tests/conftest.py, which helpers that build their own env start from"
---

## Goals

**Response taken:** Proceed, citing it — owner ruling 2026-11-23 in `.prawduct/owner-rulings.md` (act on
testament's `cache` and `areas` advice), backlog items #1215 and #1216.

**Product:** the owner can see where test time goes, by area, and more of the suite is cacheable on
testament's pool, so repeated runs cost less wall clock.

**Constraints:** no production code changes. No assertion is weakened to absorb the fixed git dates.

**Decisions made mid-build:**
- Git dates are fixed in the past (2026-01-01). A future date broke the reflection and session-gate
  tests, whose history must come before the session. A past date broke two tests, which now date
  their own commits by the real clock.
- The next cacheability blockers are left for a follow-up item, because each needs a production
  change or a per-test decision. They are: production clock reads (`evidence._now_iso`), tests that
  run the hook as a `python3` child, `core._shared_ignore_matches` stripping every `GIT_*` variable,
  and tests that read this checkout's own history.

**Level:** High — owner-ruled, and measured by testament's own output.

## Build Chunks

### Chunk 01: Git children isolated and dated (#1215)

- **Deliverables:** `GIT_TEST_ENV` in `tests/conftest.py`, applied at import; helpers that build a
  fresh env start from it; the `uncacheable` marker registered and used where a test lifts the
  isolation on purpose; the two tests that need real-clock commits date their own
- **Acceptance criteria:** the default suite and the local-only selection both pass, and
  testament's cache fates show the uncacheable share down from its baseline (49.3%)
- **Done when:** covered by Chunk 02's `cumulative`

### Chunk 02: Test areas (#1216)

- **Deliverables:** `[areas]` in `.testament.toml`, with every test in an area (`testament areas check --strict`)
- **Type:** cumulative-final
- **Done when:** integrated, suite green, committed, then `/prawduct:critic cumulative` run and
  blocking findings resolved
