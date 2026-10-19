# Retro-review rubric (blind)

Used for every sampled landing, whatever repo or governance mode it came from. The reviewer sees
the landing's diff and a copy of the tree. Governance files (`.prawduct/`, `.claude/`, `CLAUDE.md`,
change-logs), the repo name, the commit messages and the date are all removed. The reviewer does
not know why the item was chosen.

## What counts

A **defect** is code in this diff that, on a plausible input or state, produces wrong output, loses
or corrupts data, crashes, hangs, leaks or opens a security hole, or silently reports success for
something that failed. Each finding must give:

- `file:line` in the diff
- a concrete failure scenario: the inputs or state → what happens → what should happen
- severity:
  - **high** — silent wrong results, data loss or corruption, security, or a crash on a common path
  - **medium** — wrong behaviour on an edge case that a user or caller would plausibly hit

## What does not count

Style, naming, docs, refactoring opportunities, performance without a correctness effect,
speculative "might" findings without a scenario, and anything the diff did not introduce or
change. A **missing test** is recorded separately as `test_gap`. It is never a defect.

## Verification

A second, independent agent re-checks every defect against the same tree copy. It marks each one
**real** (the scenario reproduces by reading the code), **not real** (gives the line that
prevents it), or **uncertain**. Only **real** defects are counted.
