# Issue #1154 — a plan's mid-build decision retires the phrasing it overturns: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-11-15 · source: boundary review
rev-20261112T041348Z-76de58b6, finding R-4 (#890) · issue:
https://github.com/brookstalley/prawduct/issues/1154`

Related: #136 (closed; built `retired-claim-survives` for Direction norms and project-state
decisions), #641 (deleting a mechanism leaves stale assertions undetected), the learnings rule
"Recording a scope narrowing is a CASCADE" (`.claude/rules/learnings/authoring.md`). The norm this
item extends is `plugin/docs/norms.md` § Anatomy, "Retires", and the plan field it attaches to is
`plugin/methodology/planning.md` "Goals", "Decisions made mid-build".

## Problem

A build plan is written before the build and corrected during it. The correction lands as an
entry under **Decisions made mid-build**. The sections the entry overturns (chunk bodies,
acceptance criteria, the falsifier, the design document the plan depends on) keep instructing
against the old fact, and a later chunk or a cold session builds to them. The learnings rule
names this and relies on the author opening every section. #136 established that an author's
sweep does not hold, and built a check so the literal part is mechanical.

That check does not reach a plan. Read on develop at `6f3d232f`, `retired_claims` takes
declarations from two places only: a `Retires:` field on a line of a `## Direction` section in
`.prawduct/artifacts/*.md`, and a `retires:` list on a `technical_decisions` or
`design_decisions` entry in `project-state.yaml`. A `Retires:` line written in a plan's `## Goals`
is dropped without a finding (`_artifact_declarations` skips any field that is not a Direction
line), so an author who tries the obvious thing gets silence that reads as a clean result.

The #890 boundary review found five survivors in one plan and its design document after
mid-build corrections: a falsifier figure ("~1% measured") that the re-derivation had moved to
about 6%, "rides as oracle" after the bundle became context, `coverage.boundary_frontier` after
the function was placed in `gates`, the sweep still described as built, and a "NOT to be built"
status. The issue records all five as superseded phrasing, literal, and all five
were in files the plan itself names. The Critic's Goal 4 read caught them; the price was a
finding and its round at the merge boundary, the most expensive place to learn it.

Two things make a plan different from a norm, and they are why this is not a one-line widening
of the existing reader:

- **Scope.** A norm's retired wording is wrong everywhere, so the existing search covers every
  tracked file and open issue. A plan's superseded phrasing is local: "~1% measured" or "rides as
  oracle" is true or harmless elsewhere in the repo. Searched repo-wide it would report copies
  that are not survivors.
- **The entry quotes what it overturns.** A mid-build entry says "X, not Y", across several
  wrapped lines and often nested bullets. The existing exemption covers the `Retires:` field's
  own lines, not the prose of the entry that carries it.

## Goals

- G1. When a mid-build decision overturns wording, the wording's literal survivors in the plan
  and the files the plan depends on are found by the check, before the boundary review.
- G2. One `Retires:` convention. An author who knows the norm form writes the plan form without
  learning a second grammar, and the check has one phrase parser and one matcher.
- G3. A declaration the check does not read is reported where it is written, never dropped.
- G4. The control is priced: its findings are countable apart from the norm-scoped ones, and the
  five #890 survivors are its replay set, each seen red before the change.

## Non-goals

- Paraphrase. A restatement is still Critic Goal 4's to read, as the existing docstring says.
- A general `depends_on` graph, its validation, or `artifact_manifest`. #136 scoped that out
  because nothing maintains it. This item reads one plan's own list and nothing transitive.
- Requiring a `Retires:` on every mid-build entry. Most decide something new and overturn
  nothing. Whether an entry that does overturn wording *must* carry one is question 4.
- Scope narrowing beyond wording. A cut chunk whose dependents were never re-planned is a
  planning defect; this check finds only the phrases the author names.
- Rewriting archived plans, or changing how Direction and project-state declarations behave.

## Requirements

**Declaration**

- R1. An entry under a plan's **Decisions made mid-build** may carry a `Retires:` field. Its
  value has the grammar the norm field has: each retired phrasing a double-quoted string, prose
  around the quotes ignored, soft-wrapped like any field. Matching is the existing matcher's:
  literal words, case-insensitive, wrap-tolerant. No pattern syntax is added.
- R2. The field is read on every entry shape the plans in this repo use today: a single line
  after the heading, a top-level bullet, a nested bullet under a dated group, and the
  `[DECISION: … | …]` form. Design names the rule that bounds one entry and pins each shape
  with a fixture drawn from a live plan.
- R3. A plan is any `build-plan*.md` the existing declaration walk already visits. An archived
  plan declares nothing, as an archived norm document declares nothing today.
- R4. `Retires:` written where it is not read is a finding at that line: inline after an entry's
  text, in a plan section other than the mid-build decisions, or under `## Goals` outside an
  entry. This closes the silent drop described above and applies the existing "inline form is
  not read" finding to plans.
- R5. The existing defects in a declaration keep their findings in a plan: a field that quotes
  nothing, and a phrase too short to search.

**Scope of the search**

- R6. A plan-declared phrase is searched in the plan itself and in each file its front matter
  `depends_on:` names, and nowhere else. It is not searched repo-wide and not in the backlog.
- R7. Both `depends_on` entry forms resolve: a path, and `artifact: <name>`. An entry that
  resolves to no readable file is reported `unchecked` with the entry named. It is never
  skipped into a clean result.
- R8. A plan with a `Retires:` declaration and no `depends_on` list is searched alone, and the
  result says the search covered the plan only.
- R9. Files the current change edits are not exempt, as in the existing check.

**What is not a survivor**

- R10. The declaring entry's whole text is exempt, not only its `Retires:` lines. The entry is
  the record of the overturn and has to be able to quote it.
- R11. The rest of the mid-build decisions list is not exempt by default. An earlier entry that
  still states the overturned fact instructs a cold reader as a chunk body does. See question 2.
- R12. The existing acknowledgement (`prawduct:allow prawduct/retired-claim-survives -- <reason>`)
  works on a plan-scoped hit unchanged, for a line that quotes the phrase as its subject.
- R13. A phrase declared by a plan never produces a finding outside the R6 set, and a phrase
  declared by a norm or a project-state decision keeps its repo-wide reach. One phrase declared
  by both is searched at the wider reach and reported once per site.

**Reporting**

- R14. Findings use the existing check id and severity (`retired-claim-survives`, warning), so
  the stage rule holds without new wiring: an observation at the inner stage, raised at the
  boundary. A finding names the surviving file and line and the plan entry that retired it.
- R15. Plan-scoped findings are countable apart from norm-scoped ones from what the finding
  already carries (the declaring record's path), with no stored category added.

**Prose and templates**

- R16. One home states the plan form: `plugin/docs/norms.md` § Anatomy "Retires" gains it, and
  `planning.md` "Decisions made mid-build", the build-plan template and the check's docstring
  reference that home. The check's docstring "read in two places" becomes three.
- R17. The learnings rule on scope-narrowing cascades keeps its instruction and points at the
  field for the literal part, within its one line.

## Non-functional

- NF1. A repo whose plans declare nothing pays no more than today: the declarations are read
  and no search runs. A plan-scoped search reads only the R6 files and adds no `git grep`.
- NF2. Advice fails soft and never reports a clean result it did not earn: an unreadable plan,
  an unparseable front matter or an unresolvable `depends_on` entry is `unchecked` with a reason.
- NF3. No second parser for `Retires:` values and no second matcher. The plan reader supplies
  declarations and a search set to the code that exists.
- NF4. Nothing is written. The check stays read-only and gates nothing.
- NF5. Reading the mid-build list is the first `plugin/lib` reader of a plan's `## Goals`
  content. `build-plan-critic-trim.md` records that no such reader existed and that its brief
  ruled out writing one for printing the list. This reader has a different purpose, and the
  design states the entry-boundary rule once so a later reader does not derive a second.

## Acceptance

- A1. Replay: the five #890 survivors are rebuilt as fixtures from the plan and design document
  as they stood before the review's fixes. Each is reported at its file and line once the
  overturning entry carries `Retires:`, and each test is seen red on develop first.
- A2. Scope: a fixture repo holding the same phrase in an unrelated tracked file and in an open
  backlog issue reports neither (R6, R13). The control case, the same phrase declared on a
  Direction norm, reports both.
- A3. Every R2 entry shape has a fixture; the declaring entry's own quotation is not reported
  (R10); an earlier entry's copy is reported or not according to the ruling on question 2.
- A4. Each misplaced form in R4 yields a finding at its line. A `depends_on` entry naming a
  missing file yields `unchecked`, and the run is not clean (R7, NF2).
- A5. Run over this repository's live plans with no `Retires:` added, the check's output is
  unchanged from develop. Then the falsifying query for R16: no sentence in `plugin/` or
  `tests/` still says the field is read in two places only.
- A6. Expected yield is stated in the build plan as the A1 set, and R15's count is shown to be
  derivable from one review's findings.

## Open questions for the owner

1. **Scope (R6).** Plan plus `depends_on` only, as the issue proposes? In this repo a plan's
   design is often `documentation/issues/<n>-design.md`, which the plan may link in prose and
   not list. Recommendation: `depends_on` only. The list is the declared set, a link in prose
   is not a dependency claim, and the fix for an unlisted design document is to list it.
2. **Earlier mid-build entries (R11).** Is the decisions list an instructing section or an
   append-only log? Recommendation: instructing, so an earlier entry's copy is reported and the
   author amends it in place with a pointer to the later entry. Treating the whole list as
   history is simpler and leaves a cold session reading an overturned decision as current.
3. **Code files in `depends_on`.** Plans list source files there (`plugin/lib/gates.py`). A
   retired field name surviving in code is a real survivor, and a retired figure in a comment
   is one too. Recommendation: search them; the acknowledgement covers a deliberate quotation.
4. **Obligation.** Should `planning.md` say an entry that overturns wording carries `Retires:`,
   as `norms.md` says of an amendment? Recommendation: yes, as prose with no check behind it.
   Nothing mechanical can tell an overturning entry from a new decision.
5. **Sizing.** The issue has no `impact` or `effort` label. Suggested: `impact:M`, `effort:M`.
   One review's evidence so far; the failure class is the one #136 measured at thirteen
   recurrences in a product repo.

## What was checked, and what was not

Read on develop at `6f3d232f`: `plugin/lib/retired_claims.py` in full (declaration readers,
matcher, history and exemption rules, the backlog leg), `plugin/docs/norms.md` § Anatomy and
§ Amendment, `planning.md` "Goals", the build-plan template's Goals block, issue #136, and the
mid-build decision blocks of the live plans in `.prawduct/artifacts/` for the entry shapes in
R2. Queried: no `plugin/` Python file reads `depends_on` (grep, zero hits outside templates and
`planning.md`), and no live plan carries a `Retires:` field today.

Not read: the review `rev-20261112T041348Z-76de58b6` itself. The five survivors are taken from
the issue body, and only the plan's later corrections were seen, so A1's fixtures need the
pre-fix text from git history. Not run: nothing here was executed against a fixture, including
the claim that a `Retires:` line in a plan's Goals is dropped without a finding, which is a
reading of `_artifact_declarations`. Not checked: how `norm_probes._direction_lines` treats a
plan that has both a `## Direction` and a `## Goals` section. Design starts by running both.
