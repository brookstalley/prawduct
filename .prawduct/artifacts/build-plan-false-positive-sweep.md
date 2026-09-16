---
artifact: build-plan
version: 2
scope: false-positive-sweep
# branch: fix/false-positive-sweep   <- uncomment when the branch is created
partition: "01 serial first; 02–04 delegable to isolated worktrees after 01 lands — disjoint modules (plan_archive / change-log template / stop-hook trivial gate), each proven by its own tests"
program: consumer-overhead-program-2026-09.md (WS7)
related_issues:
  - "brookstalley/prawduct#809 — archive-plan refuses `lifecycle: active` (Chunk 01)"
  - "brookstalley/prawduct#813 — api-versioning advisory says no decision while a nested one exists (Chunk 01)"
  - "brookstalley/prawduct#765 — version-shaped scope= example trips the release gate (Chunk 02)"
  - "brookstalley/prawduct#301 — trivial gate: patch or retire (Chunk 03)"
  - "brookstalley/prawduct#818 — dead-why re-fires after owner re-affirmation (Chunk 04, design-first)"
  - "brookstalley/prawduct#811 — accept-operator-verification reads no entries (Chunk 05, design-first)"
  - "brookstalley/prawduct#762 — wholesale .prawduct/ ignore defeats the gitignore contract (Chunk 06, detection only)"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "a control that fires repeatedly with no yield stops being read → ENGAGED: every chunk removes a no-action firing"
      - "warnings are effectively blocking; never demote a severity to fix a false positive, fix the classification → ENGAGED: no chunk lowers a severity; each corrects what the detector reads or says"
  - artifact: architecture
    dispositions:
      - "advice fails soft, not silent → conforms; Chunks 05–06 add NOTEs where a check currently passes silently"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → ENGAGED in Chunk 06: detection only, never a `.gitignore` rewrite"
last_validated: 2026-09-16
---

# Build plan — false-positive sweep

## Requirements Confidence

**Level:** Medium

**Why:** Chunks 01–02 are confirmed in source by their triage comments, with fixes named. Chunk
03's direction is an owner decision. Chunks 04–06 carry open design questions and each starts with
that step.

**Open assumptions / unknowns:**
- `[ASSUMPTION: #301 retires the trivial gate (program decision 6) | HIGH impact | user can choose patch; Chunk 03 is then re-drawn]`
- `[ASSUMPTION: #811 ships options (b)+(c), not (a) (program decision 7) | MED impact | user can override]`
- `[ASSUMPTION: #762 ships detection only (program decision 8) | MED impact | user can override]`
- #818 open question: retire the advisory on a dated re-affirmation marker, or tell a Why that rests
  on the item apart from a history mention? Chunk 04 answers it.

**What would raise confidence:** owner answers on program decisions 6–8.

## Status

- [ ] Chunk 01: archive-plan accepts an active plan; api-versioning names the fact it read (#809, #813)
- [ ] Chunk 02: change-log examples use a work-named scope (#765)
- [ ] Chunk 03: Retire the trivial gate (#301)
- [ ] Chunk 04: dead-why honours an owner re-affirmation (#818)
- [ ] Chunk 05: operator-verification: an unparseable queue says so early, and the refusal names an action (#811)
- [ ] Chunk 06: gitignore contract sees a wholesale ignore (#762, detection)
Context: Drawn 2026-09-16. Nothing built. #818 still has no labels. Triage it first as
`kind:bug area:governance effort:S impact:S source:user stage:design`.

## Chunk 01: archive-plan accepts an active plan; api-versioning names the fact it read (#809, #813)

- **Description:** #809: the re-archive refusal in `plugin/lib/plan_archive.py` tests whether a
  `lifecycle:` key is present. It should test whether the value is in `TERMINAL_STATES`. The
  refusal message names the value it read and the values it refuses. #813: the
  `api_versioning_probes.py` trigger summary names the flat `api_versioning_decided` fact it reads
  and says a decision already under `design_decisions.api_versioning_approach` is resolved by
  setting that mirror. The `templates/project-state.yaml` stub for the flat fact moves next to the
  nested key. Detection is unchanged.
- **Tests:** `lifecycle: active` plan with all boxes ticked → archived and stamped; `completed` →
  still refused, and the message names `completed`; the probe message contains the flat key and the
  nested key; the probe still fires with no decision and stays silent with the flat fact set.
- **Done when:** tests pass; `/prawduct:critic`; tick; close #809 and #813.

## Chunk 02: change-log examples use a work-named scope (#765)

- **Type:** doc-only
- **Description:** Replace the version-shaped `scope=v1.4` examples in `plugin/templates/change-log.md`
  and the `plugin/lib/change_log.py` docstring with a work-named scope that resolves to a plan. Add
  one sentence where the key is documented: `scope=` names the work, `release=` names the version.
- **Tests:** a pin that no shipped `scope=` example matches a version pattern.
- **Done when:** pin passes; `/prawduct:critic`; tick; close #765.

## Chunk 03: Retire the trivial gate (#301)

- **Description:** Remove the trivial gate's hard-coded prawduct directory names from the Stop path.
  Keep the `Type: trivial` rationale requirement. Remove the gate's tests and every instruction
  surface that names its blast-radius bound (grep `skill-file-edited`, "catastrophic-blast-radius",
  `planning.md` "Choosing a Chunk Type"). Record the retirement the way #301's evidence names
  (third-rework deletion signal, MET-9W2P).
- **Tests:** a product repo editing `.claude/skills/foo/SKILL.md` in a `Type: trivial` chunk → no
  block; a trivial chunk with an empty rationale → still blocks.
- **Done when:** tests pass; methodology token-budget tests pass; `/prawduct:critic`; tick; close #301.

## Chunk 04: dead-why honours an owner re-affirmation (#818)

- **Description:** First confirm the root cause in `plugin/lib/norm_probes.py` (the report infers it
  and has not traced it). Then choose between: (i) a dated owner re-affirmation after the cited item
  closed retires the firing for that norm; (ii) only a Why whose reasoning cites the item counts, not
  a history mention. Record the choice as [DECISION] in the change-log entry. Proposed: (i). It is
  mechanical, and the owner's re-affirmation is exactly the signal the advisory asks for.
- **Tests:** a norm re-affirmed after the item shipped → silent; a norm whose Why still depends on a
  shipped item and has no re-affirmation → fires (positive control).
- **Done when:** tests pass; `/prawduct:critic`; tick; close #818.

## Chunk 05: operator-verification: an unparseable queue says so early, and the refusal names an action (#811)

- **Description:** With the requirement off, `check-operator-verification` prints a NOTE (never a block)
  when a non-empty queue parses 0 entries, naming the first rejected heading line. The accept-path
  refusal in `plugin/lib/operator_verification.py` names that line too, and replaces the
  "fix the format / don't reformat" pair with the action available to the caller: hand the decision
  to the operator, who owns the queue's format. The heading grammar is unchanged.
- **Tests:** bracketed-heading queue, requirement off → NOTE, exit 0; accept → refusal names the line
  and the operator hand-off; a well-formed queue → unchanged.
- **Done when:** tests pass; `/prawduct:critic`; tick; close #811.

## Chunk 06: gitignore contract sees a wholesale ignore (#762, detection)

- **Type:** cumulative-final
- **Description:** Route `core._contract_diff` membership through the batched `git check-ignore`
  helper already in `gitstate.py`, so a `.prawduct/` rule is seen to subsume the entries it covers.
  Report "a wholesale ignore of `.prawduct/` also ignores N files prawduct requires committed" as a
  finding. Never rewrite the user's rule. Fall back to today's literal check when git is
  unavailable, and say so.
- **Tests:** #762's reproduction (`.prawduct/` + `__pycache__/`): 0 false "missing" entries, and the
  required-committed files are reported; a literal per-entry gitignore → unchanged; git unavailable
  → the literal fallback plus a disclosure.
- **Done when:** commit; one `/prawduct:critic cumulative`; tick; close #762 (or narrow it to the
  remedy question).
