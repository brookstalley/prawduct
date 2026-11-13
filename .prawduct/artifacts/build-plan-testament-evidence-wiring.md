---
artifact: build-plan
version: 2
scope: testament-evidence-wiring
branch: feature/testament-evidence-wiring
base: develop
working-branches: []
depends_on:
  - plugin/bin/prawduct-hook
  - plugin/lib/probe_families.py
  - plugin/methodology/building.md
  - plugin/docs/project-state-keys.md
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no review path changes"
      - "authority fails closed; advice fails soft → conforms; the new check is an advisory, and the recorder's refusal is unchanged in what it refuses, only in what it says"
      - "local-first → conforms; the probe reads two files in the repo and runs nothing"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the advisory names the change and makes none"
      - "written in Python, never specific to Python → conforms; the check keys on testament's manifest and the declared command's words, not on a language"
      - "guides and reviews, never implements → conforms; the product's test_command is the owner's to change"
      - "goals and verification bind, method is advice → conforms"
      - "every fact has one home → conforms; one function answers whether a declared command runs testament. The recorder resolves the declaration and hands it to the refusal; the probe resolves it by the recorder's rules through lib, pinned to the recorder by a parity test that drives the real hook on every disputed shape, as the hook's other mirrored readers are pinned"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → inapplicable because no verdict changes"
      - "facts immutable and append-only → inapplicable because no fact is written"
      - "derived views never authoritative → inapplicable"
      - "a governance document reaches a terminal state → inapplicable"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes"
      - "a newer-schema fact is surfaced, never dropped → inapplicable"
      - "two stores, two lifetimes → conforms; the answer is the committed test_command, and dismissing the advisory is per-clone"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → inapplicable because no review changes"
      - "proportionality ratchets both ways → conforms; one dismissable advisory, no gate"
      - "state-file growth is advisory, never a hard block → inapplicable"
      - "review rigor is stage-keyed → inapplicable"
partition: "serial, one builder — one chunk whose recorder message and probe share one predicate"
last_validated: 2026-11-13
---

## Goals

**Response taken:** Proceed, citing it. #1167 carries the requirement. The owner approved this fix on
2026-11-13 ("yes build 2"), after a diagnosis of a downstream product's sessions.

**Product:** A repo whose tests run on testament records test evidence from that run. Today an
agent there verifies on the pool, cannot hand that run to the recorder, and runs the whole
suite a second time locally. Done means three things. An advisory tells the owner when the
declared command doesn't run testament, and names the one-line fix. The recorder's refusal of
`--from-counts` names the testament route that does work. `building.md` stops claiming that
`--from-counts` ingests when a command is declared.

**Architecture:**
- One module answers whether a repo's tests run on testament (`.testament.toml` at the root, the
  file testament itself reads to run the suite) and whether any declared `test_command` or
  `test_commands` entry runs `testament run`. The probe and the recorder both ask it.
- The probe is a sibling advisory family, registered at the composition root.
- The refusal's text picks its lead route from the same answer: the testament route leads
  where testament is present.

**Constraints:**
- Nothing writes `project-state.yaml`. The advisory names the change, and the owner (or the agent,
  with the owner's yes) makes it.
- The recorder refuses exactly what it refused before.
- prawduct's own repo, whose first `test_commands` entry runs testament, must not fire.

**Tradeoffs accepted:**
- A declared command that wraps testament in a script the probe can't see through reads as
  unwired and fires. The advisory is dismissable, and its evidence is the declared commands, so a
  dismissal holds until they change.
- The `doctor` and `onboard` defaults that the first proposal named are dropped. Neither skill
  reads or writes `test_command` today, and the session-start advisory reaches every governed
  repo, new or existing.

**Decisions made mid-build:** *(appended while building)*
- `building.md`'s corrected sentence names no testament example: the file sits at its token
  ceiling, and the example lives in `project-state-keys.md` and in the refusal itself, which is
  where an agent meets it. Settled by paying a prose ceiling in place, with the ceiling lowered to
  the new reading.
- The predicate, the probe and the refusal text share one module, `testament_evidence_probes.py`,
  which the hook imports lazily, as it does its other `lib` modules. Settled by "every fact has
  one home".
- Review round. The first cut gave the declaration a second reader that disagreed with the
  recorder's (an empty or doubly-declared `test_commands`). It also wrote texts that ignored the
  declaration's form and size: one testament report offered as the whole of a three-command
  suite, and a scalar fix for a list repo that the recorder would refuse. Now the recorder passes
  its resolved declaration into the refusal. The probe's reader is pinned to the recorder by a
  parity test, and every text is chosen from the key, the entry count and the `{junit_xml}`
  placeholder. Settled by the product goal (evidence must not be recorded from part of the
  suite) and by the recorder's existing mirror-plus-parity convention.
- Review round. The module was renamed `testament_evidence_probes.py` to match its feature,
  `testament-evidence`. `runs_testament` now also reads options before `run` and a quoted
  `sh -c` string. Settled by the advisory's cost of a false fire (telling the owner to change a
  command that already works).

**Level:** High. The defect was observed in three sessions, and the downstream session
confirmed the working route (`testament run --junit-xml`, then `--from-junit`).

## Verification Strategy

Tests first at both seams: the probe against fixture repos (testament present and unwired,
present and wired through `test_command`, through one `test_commands` entry, absent), and
the refusal's text in each of those states through the real hook. The positive control is
this repo: the probe must return nothing here. The full suite runs once, at the boundary.

## Build Chunks

### Chunk 01: The recorder and an advisory name testament's route to evidence

- **Description:** Add the predicate module and its advisory probe, register it, route the
  `--from-counts` refusal's text through it, and correct `building.md` and
  `project-state-keys.md`.
- **Depends on:** none
- **Deliverables:** new `plugin/lib/testament_evidence_probes.py` (the predicate, the probe and
  `register`); its registration in `plugin/lib/probe_families.py`; the refusal in
  `plugin/bin/prawduct-hook` leading with the testament route where testament is present;
  `plugin/methodology/building.md` and `plugin/docs/project-state-keys.md` stating what the
  recorder accepts; new `tests/test_testament_evidence_probes.py`; the change fragment.
- **Tests:** unit for the predicate (word-level matching, shlex failures, list and scalar
  declarations, no declaration); the probe's candidates and evidence; the refusal's text in
  each state through a subprocess run of the hook.
- **Acceptance criteria:** the advisory fires on a fixture shaped like the downstream repo
  and not on this one. The refusal names `testament run --junit-xml` and `--from-junit` there.
  No sentence in `plugin/` claims that `--from-counts` ingests alongside a declared command.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
