---
artifact: build-plan
version: 2
scope: testament-onboarding
branch: feature/testament-onboarding
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: the point of the change is moving the suite's wall clock off the developer's machine; no review step is added"
      - "proportionality ratchets both ways; new controls emit their yield → inapplicable because no control is added"
      - "state-file growth is advisory only → inapplicable because no state file is touched"
      - "review rigor is stage-keyed → inapplicable because no review mechanism is touched"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable because no reviewer is touched"
      - "authority fails closed; advice fails soft → conforms: a pool run is not recorded as evidence until it can be ingested honestly (testament#52); the recorder stays the authority"
      - "the plugin writes nothing into a governed repo but its own state → inapplicable because nothing in plugin/ changes"
      - "local-first governance, no third-party governance dependencies → conforms: Testament is an optional test runner for this repo's own suite; governance never depends on it, and without it `pytest` runs as before"
      - "prawduct guides and reviews; it never implements → inapplicable because no product code is touched"
      - "never specific to Python → inapplicable because this configures this repo's own (Python) test lane, not the plugin"
      - "goals and verification bind; prescribed method is advice → conforms: acceptance is a pool run matching the local pass/fail set"
      - "every fact has one home → conforms: the suite's selection lives in `.testament.toml`; the marker's meaning in pyproject's marker registration"
partition: serial — one chunk; config, one marker, one doc block
last_validated: 2026-10-17
---

# Build Plan: run prawduct's suite on the Testament pool (#1016)

## Goals

**Response taken:** Proceed, citing #1016. The owner asked on 2026-10-17 to onboard prawduct to
Testament (`../testrouter`) before the suite-runtime work (#1015, blocked_by #1016), and chose the
container executor and "Testament writes JUnit" (filed as brookstalley/testament#52) when asked.

**Product.** The full suite takes 9-10 min on the developer's machine. Testament spreads it over the
pool (three runners, 30 slots on 2026-10-17). Onboarding follows `testament guide project`.

**Inferred decisions (for the boundary):**
- *Inferred:* the pool's suite is CI's suite minus tests marked `requires_history`. Measured on
  2026-10-17 by running the full suite in a history-less single-commit copy of the tree: exactly
  one test failed (`test_norm_index_scaffold.py::...test_scaffold_rows_match_the_shipped_history`,
  which searches history by content and fails rather than skips without it, on purpose). It is
  marked, not changed; local runs and CI still run it.
- *Inferred:* `[git] tags = ["v[0-9]*"]` so `test_anchor_repair`'s release-tag pin runs on the pool
  rather than skipping. Two other tests skip on a fresh checkout for machine-local reasons (a
  gitignored backlog cache; a branch-derived plan lookup); accepted, since local and CI cover them.
- *Inferred:* the AGENTS.md block is Testament's, verbatim, plus one paragraph saying evidence
  stays with `prawduct-hook test-evidence record` until testament#52 ships JUnit output.

## Chunk 01 — onboard

**Delivers:** `.testament.toml`; `docker/testament.Dockerfile`; AGENTS.md "Running tests"; the
`requires_history` marker (pyproject) on the one history-dependent test.

**Acceptance:** (a) `testament onboard --check` all ok (devcontainer n/a); (b) after the owner allows
the project, `testament run --json` runs the full selection on the pool, `report.missing` empty,
with the same pass/fail set as a local run of the same selection; (c) suite green locally.

**Done when:** acceptance passes, Critic clean of blocking.

## Status

- [ ] Chunk 01 — onboard
