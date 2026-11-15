---
schema: 1
type: fix
scope: gitignore-contract-semantics
date: 2026-11-15
title: The gitignore check now asks git what is ignored, so a wholesale `.prawduct/` rule is neither a pile of "missing" entries nor invisible
closes: [brookstalley/prawduct#762]
---
Prawduct checks that a repo's `.gitignore` ignores its session files and does not ignore the files
that must be committed. It did that by comparing literal lines, so a single rule like `.prawduct/`,
which already covers every session entry, matched none of them. The check failed in both directions:
it called the session entries missing (and the repair would then have appended all of them again),
and it never noticed that the same rule hides files prawduct needs committed, such as
`.prawduct/pr-review.md` and the build plan. #762 reported it from a repo whose `.gitignore` was
exactly `.prawduct/` and `__pycache__/`.

**What changed.** `core._contract_diff` now asks `git check-ignore` which paths would be ignored,
instead of comparing strings. A session entry counts as covered when any rule in a `.gitignore`
ignores it, and a negated re-include (`!.prawduct/pr-review.md`) counts. Where there is no work tree
yet (onboarding a directory before `git init`), it asks git about a scratch repo holding only the
`.gitignore` text, so the answer is the same. Only `.gitignore` files count: a rule in
`.git/info/exclude` or your global excludes belongs to this machine, not to the next clone.

**It reports, and does not rewrite your rule.** When a rule of yours hides a file that must be
committed, `prawduct-hook update-gitignore` prints `cannot fix automatically:`, names the rule and
its line, and gives the exact lines to paste: delete the rule, or replace `.prawduct/` with
`.prawduct/*` followed by one `!` line per file to keep (a bare directory rule cannot be negated, so
it is replaced, not added to). The same sentence reaches the session advisory
(`contract-ignored-by-rule`, owner-only, cleared once the rule is narrowed), onboarding's output
(`ignored_by_rule`), and the doctor skill's gitignore check. The repair command still removes only
lines that literally name a managed file, and it adds no line a broader rule already covers, which
also stops onboarding from appending the version marker beside a wholesale rule.

**Boundary.** If git cannot be run at all, the check falls back to the old literal comparison, says
so (`basis: literal`, and a `note:` from `update-gitignore`), and cannot see a wholesale rule. Git
names only the last rule matching a path, so a file that both a literal line and a wholesale rule
hide can surface under the wholesale rule one run after the literal line is stripped.

`tests/test_gitignore_contract_semantics.py` uses the issue's own `.gitignore`, in a real repo and
in a directory with no repo, and covers both directions, negation, per-clone excludes, nested
`.gitignore` files, the no-git fallback, the probe, the command's output, onboarding, and that
following the printed advice clears the report. `tests/test_gitignore_management.py` keeps its
checks; one equality assertion now also names the two new result keys.

## Consumer note
If your `.gitignore` has a rule like `.prawduct/` or `.claude/`, you will now be told that it hides
files prawduct needs committed, with the lines to use instead. Nothing edits that rule for you.
Session entries that such a rule already covers are no longer reported missing or appended again.
