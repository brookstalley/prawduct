---
artifact: build-plan
version: 2
scope: escape-rerun
branch: chore/987-escape-rerun
base: develop
working-branches: []
partition: serial, because it is one script, its test and two paragraphs of prose
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms; the scorer fails closed on duplicated input"
      - "local-first → conforms; the scorer reads one local file"
      - "the plugin writes nothing into a governed repo except its own state → inapplicable because nothing ships in the plugin"
      - "written in Python, never specific to Python → inapplicable because this is study tooling, not a gate"
      - "guides and reviews, never implements → inapplicable because no product code is written"
      - "goals and verification bind, method is advice → conforms; #987's acceptance is the known-answer test"
      - "every fact has one home → conforms; the metric is imported from stats.py, not restated"
depends_on:
  - documentation/issues/987-requirements.md
  - .prawduct/artifacts/governance-roi-study-2026-10.md
last_validated: 2026-11-10
---

## Goals

**Response taken:** Proceed, citing #987 and `documentation/issues/987-requirements.md`. The owner
said yes on 2026-11-10. The issue decided fail-over-skip for duplicates (R2.2) and fixed the
procedure.

**Product:** The owner can score the post-cutoff re-run with one command, and a miswired input
fails loudly.

**Architecture:** One script beside `stats.py` that imports the study's mode, cutoff and window,
so the instrument itself does not change (scope-out in #987).

**Not in this plan:** running it. Its inputs are private and stay on the owner's machine. The
study's dated `## Escape re-run` section and the #984/#989 updates follow the owner's run.

**Level:** High.

## Build Chunks

### Chunk 01: rerun.py and its known-answer test

- **Description:** The scorer, its test, and the Re-deriving step in the study.
- **Depends on:** none
- **Deliverables:** new `.prawduct/research/escape-2026-10/rerun.py`; new
  `.prawduct/research/escape-2026-10/test_rerun.sh`; step 8 in the study's Re-deriving section.
- **Tests:** a known-answer shell test with synthetic rows covering scope, window-open, a
  zero-source landing, the 24h gap rule, all three groups, and the duplicate refusal.
- **Acceptance criteria:** `test_rerun.sh` passes, and it fails with the duplicate guard removed
  (#987 acceptance 1); `test_escape.sh` still passes.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
