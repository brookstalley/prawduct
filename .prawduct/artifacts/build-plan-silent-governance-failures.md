---
artifact: build-plan
version: 2
scope: silent-governance-failures
branch: fix/silent-governance-failures
depends_on:
  - artifact: architecture
  - artifact: api-contract
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; Chunk 03 adds a read-only diagnostic at dispatch and opens no new mutation site"
      - "authority fails closed; advice fails soft → conforms; Chunk 02 withholds retirement when a sentinel cannot be graded (authority, closed), Chunk 03's signal is advisory and never gates"
      - "local-first; no third-party runtime dependencies → conforms; stdlib subprocess only, no new dependency"
      - "the plugin writes nothing into a governed repo except its own state → conforms; no new write target"
      - "prawduct is written in Python and must never be specific to Python → RESTORES CONFORMANCE; `run_sentinel` is a previously uninventoried LNG-5W8R violation, remedied by declaration per the `release_verification.py` precedent. No toolchain default survives the fix: an undeclared sentinel is reported unchecked per the norm's own fail-visible clause, because a pytest fallback would be the same violation wearing a default's clothes"
      - "prawduct guides and reviews; it never implements → conforms; the product declares its sentinel invocation, prawduct does not learn its toolchain"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "every fact has one home → conforms; the sentinel invocation's home is project-state.yaml beside `test_command:`, not a second copy in lib/"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; CLI subcommand surface internal → conforms; a project-state key is not the CLI surface and needs no per-subcommand version"
      - "exit codes are the contract; errors attributed → conforms; Chunk 03 reuses the existing prefix vocabulary and changes no exit code"
      - "additive-first evolution; keys never repurposed; deprecation signalled, never silent → conforms WITH A DEPARTURE TO RECORD. `sentinel_command:` and `unevaluated_reason` are additive, and `passed: null` becomes reachable in production where it was a test seam only, its meaning (not graded) unchanged. But removing the implicit pytest runner withdraws working behaviour rather than adding to it. Ruled in-bounds here because the withdrawal fails CLOSED — an ungraded sentinel withholds a retirement, destroying nothing — where the norm's Why is protecting callers from breakage; and it is signalled per the clause, by a stderr notice naming the knob rather than a silent unchecked. The alternative, an inert-retention window keeping the pytest default alive, would retain the very Python-specificity the architecture norm forbids, so the two norms are answered together rather than traded off"
partition: serial — the three chunks are independent, but delegation is off for this session, and one reviewer's attention over a single small diff is the binding constraint regardless
last_validated: 2026-08-26
---

## Requirements Confidence

**Level:** High

**Why:** All three chunks are repairs to mechanisms whose current behaviour was read
directly in the source this session, not inferred. Chunk 02's one genuine design fork —
that `test_command:` is a whole-suite invocation and cannot express "run this one file" —
was surfaced and ruled by the owner before any code was written. Chunk 03's two remainder
routes were each located at a specific line rather than taken from the issue's prose.

**Open assumptions / unknowns:** [ASSUMPTION: `{sentinel}` is the right placeholder spelling,
by symmetry with the established `{junit_xml}` | LOW impact | user can override]

**What would raise confidence:** N/A

## Status

- [ ] Chunk 01: Backlog and incoming-report triage
- [ ] Chunk 02: A sentinel runs under the product's own toolchain, or reports unchecked
- [ ] Chunk 03: A plan whose deliverable check cannot run says so at dispatch
Context: Plan written 2026-08-26 on a clean branch off `develop`; nothing built yet.
Baseline suite green (`test-status` exit 0, tree-valid). Next: Chunk 01.

## Verification Strategy

Chunk 01 is bookkeeping — verified by re-reading the backlog state it wrote and by the
`report-bug` advisory going quiet. Chunks 02 and 03 are both "a mechanism that failed
silently now speaks", so each is verified by constructing the failing input and reading
the actual output, not only by unit assertions: a non-Python sentinel fixture for 02, and
a scope-less plan plus a list-item plan for 03.

## Build Chunks

### Chunk 01: Backlog and incoming-report triage

- **Description:** Clear the accumulated triage debt found this session: three items whose
  recorded state is now wrong, two upstream reports sitting untriaged, and five issues
  carrying no metadata at all. This is what makes the backlog's own ranking trustworthy —
  #602 scored high enough to be picked while already being fixed.
- **Depends on:** none
- **Artifacts consumed:** `incoming-bugs/*.md`
- **Deliverables:** #602 closed as shipped; the base-sync report folded into `brookstalley/prawduct#672`
  as a second field instance and archived under `incoming-bugs/archive/`; the learnings-pairing
  report triaged into a new backlog item and archived; `#664`, `#607`, `#574`, `#573`, `#541`
  given `effort:`/`impact:`/`area:`/`stage:`; #642 re-scoped to its two live remainders; a new
  item filed for the gap this plan surfaced — `project-state.yaml` keys are a consumer-authored
  contract that `api-contract.md` classifies nowhere, so a chunk adding one has no honest
  `Exposed API:` name to declare
- **Tests:** none — no code changes. Verified by reading back the written state.
- **Acceptance criteria:** `incoming-bugs/` holds no untriaged report; the `report-bug`
  advisory no longer fires; no open issue this session identified as stale remains open
- **Type:** trivial
- **Trivial because:** backlog bookkeeping and file moves only; no behaviour change, no code
- **Done when:**
  1. Acceptance criteria met
  2. Committed and chunk marked `[x]` in Status

### Chunk 02: A sentinel runs under the product's own toolchain, or reports unchecked

- **Description:** `run_sentinel` hardcodes `sys.executable -m pytest`, so in any non-Python
  product the learnings sentinel mechanism is inert *and* reports a green test as failing —
  which then argues for retiring a rule that is still enforced. The remedy is the norm's own
  two clauses: the product declares how to run one of its test files, and a sentinel prawduct
  cannot grade is reported unchecked rather than failed. **No toolchain default survives** —
  prawduct states the requirement ("grade this sentinel") and the consuming repo decides how,
  so an undeclared sentinel is unchecked rather than attempted under a guessed runner.
- **Depends on:** none
- **Artifacts consumed:** `architecture.md` § Direction (the Python-agnosticism norm and its
  LNG-5W8R inventory), `api-contract.md` § Direction (additive-first, deprecation signalled)
- **Deliverables:** `sentinel_command:` read in `plugin/lib/audit_learnings_cmd.py`;
  `run_sentinel` returning a tri-state verdict with an `unevaluated_reason`; the pytest
  invocation deleted; the false `errors[]` entry withdrawn for the ungradeable case; a stderr
  notice naming the knob when a sentinel goes unchecked for want of it; `sentinel_command:`
  declared in this repo's own `project-state.yaml` and carried in the project-state template
- **Tests:** unit — a declared `sentinel_command:` is shlex-split and `{sentinel}` substituted;
  an absent knob yields `passed=None` with a reason and NO `errors[]` entry; a declared
  command missing `{sentinel}` is refused with an attributed message; a non-zero exit grades
  the sentinel failed while a launch failure grades it unchecked (the two must not collapse).
  Integration — a fixture product declaring a non-pytest command grades a sentinel through
  `audit-learnings --json`, and this repo's own sentinels still grade under its declaration
- **Acceptance criteria:** the reported vitest repro (`sentinel_command: npx vitest run {sentinel}`)
  grades a passing sentinel as passed; with no knob, output carries `passed: null` plus a
  reason naming the knob, and the retirement is withheld without accusing the test; no
  Python-specific literal remains in the sentinel path
- **Type:** bugfix
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: A plan whose deliverable check cannot run says so at dispatch

- **Description:** Two routes still disable the chunk deliverable check without a loud word,
  and #642 stayed open for exactly these. Route 1: a plan declaring no frontmatter `scope:`
  reaches `chunk-ref-missing unchecked — …`, which is real but buried in the dispatch manifest
  where `unchecked` reads as a pass. Route 2: chunks written as list items under `## Chunks`
  match no heading pattern, so `_chunk_ref_findings` returns `[], None, None, None` and emits
  nothing at all. Both should be named by `critic-begin`, where the fix is three lines of plan
  frontmatter, rather than at release time.
- **Depends on:** none
- **Artifacts consumed:** `architecture.md` § Direction (authority fails closed, advice fails soft)
- **Deliverables:** a dispatch-time check in `plugin/lib/critic_consolidate.py::begin_review`
  naming a resolved plan that declares no `scope:` or exposes no parseable chunk heading;
  the silent `return [], None, None, None` in `plugin/lib/record_lint.py` replaced with a
  reported gap; surfaced through `cmd_critic_begin`'s existing diagnostic channel
- **Tests:** unit — a plan with no frontmatter `scope:` produces the named signal; a plan whose
  chunks are `- Chunk 01: …` list items under `## Chunks` produces it too; a well-formed plan
  produces none (the no-false-positive case); the signal is advisory and changes no exit code
- **Acceptance criteria:** both plan shapes from #642's repro produce a signal at `critic-begin`
  that names the plan and the specific defect; a template-conforming plan is silent
- **Type:** cumulative-final
  <!-- Last chunk: its review is the one `/prawduct:critic cumulative` over the whole branch. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
