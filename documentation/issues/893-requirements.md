# Issue #893 — tests: flag new literal-in-file pins the base file already satisfies: Requirements

`status: draft · stage: requirements · area: tests · added: 2026-10-01 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/893`

Related: #200 (parent class — vacuous tests in general; out of scope here), #187 (regex pins; out
of scope, same comparison could extend later).

## Problem

A test of the shape `assert "<literal>" in <text read from a file>` cannot fail if the file on the
merge-base already contained the literal. A branch that adds such a pin looks covered, the suite
stays green, and deleting the behaviour the pin was written for would not turn it red.

Instance (issue evidence, Critic O-1 on `rev-20260923T014216Z-8b015adf`): commit `40dad089` added
`assert "path-scoped" in body` to `tests/test_pr_reviewer_agent.py`; at merge-base `18c1d846`,
`plugin/agents/pr-reviewer.md` already said "`Write` is not path-scoped". The pin was green before
any change. The Critic caught it; nothing mechanical did.

## Grounding facts

Measured against `develop` on 2026-10-01 (re-derive with the commands in the last section):

- **Most literal-in-X asserts are not about files.** Of the single-line `assert "<lit>" in <name>`
  shapes under `tests/`, the dominant targets are subprocess/CLI output (`err`, `out`,
  `result.stderr`, `result.stdout`, `proc.stdout` — together roughly 60% of the top dozen shapes).
  Those have no merge-base counterpart and must never be flagged.
- **File-text targets are a minority and are reached through a variable**, not inline: `text`,
  `content`, `body`, `self.content`, `section`. Only 17 asserts read the file inline
  (`... in X.read_text()`). The #893 instance is itself indirect: `body = AGENT_DEF.read_text().split("---\n", 2)[2]`
  — a *derived slice* of the file, with `AGENT_DEF` a module-level `Path` constant.
- **So the hard part is resolution, not comparison.** Mapping an assertion's right-hand name to
  "the file (and slice) it came from" is a small dataflow problem. The merge-base comparison
  itself is cheap (`git show <mb>:<path>`).
- **Prior art for the pieces exists.** `plugin/lib/record_lint.py` already reads only the lines a
  change *added* (`git diff --unified=0`), is advisory by design (findings "never gate"), reports
  `unchecked` with a reason rather than passing silently, and rides the Critic dispatch manifest.
  `buildplan_refs.py` already computes merge-base-relative changed-file sets and returns `None`
  to distinguish "could not look" from "nothing changed".
- **record-lint's stated scope is records** (markdown and `.prawduct/*.yaml`), classified by path
  and suffix, "no language classified". A check over `tests/*.py` source is a new input class for
  it and must be justified against that scope (see D-1).

## Requirements

- **R-1 Detect added pins.** From the branch diff (merge-base → HEAD, plus working tree as
  `buildplan_refs` measures it), identify literal-in-text assertions *added* in test files: the
  `assert "<lit>" in <expr>` and `assert "<lit>" not in …` forms. Only added lines are examined
  (cost proportional to the diff).
- **R-2 Resolve to a file, or say it cannot.** For each added pin, resolve the right-hand
  expression to a source file when this is statically determinable within the same test module
  (a local assigned from `<PATH>.read_text()` with optional `.split(...)[n]` / slicing; a
  module-level `Path` constant; a helper that returns such text). Otherwise the pin is
  `unresolved` and reported as such — never silently treated as clean or as flagged.
- **R-3 Compare at the merge-base.** For a resolved pin, test whether the literal is a substring
  of that file's text at the merge-base. If the pin reads a *slice*, the comparison uses the same
  slice of the base text where it can be reproduced, else the whole file with the result marked
  `whole-file` (weaker, so the finding says so).
- **R-4 Flag only the already-satisfied positive pins.** Flag `assert lit in X` when the base
  already satisfies it. A new file (absent at the merge-base) is never flagged. `assert lit not in X`
  is a different property (the base satisfying a *negative* is not the defect described) and is out
  of scope for v1.
- **R-5 Never touch non-file targets.** Output of subprocesses, return values and any name not
  resolvable to a repo file produce no finding and no `unchecked` noise beyond a count.
- **R-6 Advisory wording.** A finding states: "this assertion was already true at the merge-base;
  if it protects existing text, say so; otherwise pin the new sentence." A flagged pin is not
  necessarily wrong (issue text: it may protect existing text).
- **R-7 Yield is observable.** Per-check counts (`examined`, `resolved`, `unresolved`, `flagged`)
  land where record-lint's other yields do, so precision/recall is a query, not an argument
  (record-lint and NFR proportionality norm: a control emits its yield at birth).
- **R-8 Fails visible.** If the base ref or merge-base cannot be resolved, the check reports
  `unchecked: <reason>`, not clean.

## Acceptance criteria

- [ ] **Positive control (from the issue):** replaying `40dad089` against `18c1d846` flags
      `"path-scoped"` in `tests/test_pr_reviewer_agent.py` (resolved to
      `plugin/agents/pr-reviewer.md`, slice = body). Fixture is a synthetic two-commit repo that
      reproduces the shape, plus one test that runs against the real commit pair when it is
      reachable (skipped with an explicit reason, not silently, where history is shallow).
- [ ] **Negative control (from the issue):** a literal absent at the merge-base and added to the
      file on the branch is not flagged.
- [ ] **Non-file control:** `assert "x" in result.stderr` is not flagged and not counted as
      `unresolved` noise.
- [ ] **Unresolvable control:** a pin whose RHS cannot be resolved is reported `unresolved`.
- [ ] **New-file control:** a pin against a file created on the branch is not flagged.
- [ ] **Instance-vs-class (learnings rule on guards):** the fixtures vary the *resolution shape*
      (inline `read_text()`, local variable, split-slice, module constant, class attribute
      `self.content`), not only the one in the issue — otherwise the check is pinned to its example.
- [ ] A decision on block-vs-advise and on where it runs is recorded (D-1, D-2).

## Decisions for the owner

- **D-1 — where it runs.** Options: (a) a record-lint check (advisory, rides the dispatch
  manifest, diff-cost, reaches the Critic and so the author at the point the defect has been
  costing a round); (b) a test-time guard in the suite (blocking, but a test that needs
  git history is not hermetic and breaks on shallow clones); (c) the Critic payload only.
  **Recommendation: (a)**, with the scope note that record-lint gains one new input class
  (`tests/*.py` added lines) — path-classified like its others, content parsed only for the
  assertion shape, not language-classified. Rationale: the defect is an authoring slip the author
  can resolve in one edit, which matches record-lint's "advice, not authority" posture; and (b)
  would make the suite depend on repository history.
- **D-2 — block or advise.** **Recommendation: advise.** A flagged pin can be correct (it guards
  existing text on purpose), so a block needs an escape that is itself a recorded artifact; the
  false-positive rate is unmeasured until R-7 yields data. Revisit promotion to blocking after
  the yield is observed (promotion changes what a false positive costs).
- **D-3 — slice fidelity (R-3).** When the slice cannot be reproduced, comparing the whole base
  file can false-positive (the literal exists elsewhere in the base file, outside the slice the
  test reads). Choose: report it labelled `whole-file` (weaker evidence), or leave such pins
  `unresolved`. **Recommendation: label and report**, then let the R-7 yield decide.

## Risks and open questions

- **Direction of the whole-file fallback.** It can only over-flag, never miss a satisfied pin;
  design should size how many real pins fall in each bucket (see D-3).
- **Parsing cost and brittleness.** Resolution via the `ast` module over the changed test file
  only is the expected mechanism; a regex over added lines cannot resolve a variable. Design
  decides; requirements only demand R-2's "resolve or say so".
- **Pins on rendered output** (a test that renders a skill and asserts a literal in the render)
  read no repo file directly; they are `unresolved`/ignored in v1.

## Out of scope

Vacuous tests in general (#200); regex pins (#187); negative (`not in`) pins; asserting that a
test goes red under mutation (a different, stronger instrument); a repo-wide audit of existing
pins (the check is about what a branch *adds*).

## Re-deriving the grounding numbers

```
grep -rhoE '^\s+assert (not )?"[^"]+" in [A-Za-z_.()]+' tests | sed -E 's/"[^"]+"/L/' | sort | uniq -c | sort -rn | head
grep -rhoE 'assert (not )?"[^"]+" in .*read_text\(\)' tests | wc -l
git show 40dad089 -- tests/test_pr_reviewer_agent.py
```

## Next step

Design: the resolver (ast-based, scope-limited to the changed test module), where the check slots
into `record_lint.lint_records`, and a measurement pass over the last N merged branches to size
the `resolved`/`unresolved` split before committing to a mechanism.
