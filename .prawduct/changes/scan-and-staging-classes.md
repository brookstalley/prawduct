---
schema: 1
type: fix
scope: scan-and-staging-classes
date: 2026-11-23
title: the findings cache stages under its own temp-suffixed name, and plugin source scans reach the hook
closes: []
---
Two observations accepted at the #1229 boundary, fixed as the classes they belong to.

**Rename-into-place staging.** The branch findings cache writer staged its validated candidate as
`.prawduct/.critic-findings.json.derived` and renamed it into place. That name is outside
`core.TEMP_SUFFIX`, so a crash between the write and the rename left an untracked file that neither the
ignore contract nor the session-file exemption covers. The candidate is now a per-writer `mkstemp` name,
`.critic-findings.json.derived.<random>.prawduct.tmp`. Because the name is per writer, two sessions
deriving in one checkout at once cannot truncate each other's validated candidate before its rename. A
`finally` removes the candidate on every path that doesn't rename it.
`tests/test_temp_suffix.py` swept temp names ending in `.tmp`, so it could not see a staging file with
another name. A second sweep keys on the act instead:
- what it matches: `os.replace`, `os.rename`, `shutil.move`, a bare `replace`/`rename` imported from
  `os`, and any one-argument `.replace`/`.rename`;
- what it requires: a source built with `temp_sibling` or `TEMP_SUFFIX`, directly or through local names
  every binding of which carries it.

The archive move in `_archive_leftovers` moves a finished file rather than staging one, so it is exempted
by name, and the exemption fails if that function is gone. A source passed in as a parameter slips the
sweep. The writer's invalid-candidate branch and the two-writer case now have tests.

**Source scans that skip the hook.** Eight structural tests globbed `plugin/**/*.py` or `plugin/lib/*.py`
and passed over the extensionless `plugin/bin/prawduct-hook`, which holds the hook's whole CLI. One of
them was the AST pin that only `branch_review_chain` calls `review_chain`, and another was the one-home pin
on the blast-radius sentence. A defect in the hook stayed green under each of them.
The source set now has one owner, `conftest.plugin_python_sources`. It takes every `*.py` under
`plugin/` plus the extensionless executables with a Python interpreter line, and the three helpers that
duplicated it read it too. `tests/test_source_scans_reach_the_hook.py` fails a `*.py` glob (recursive or
flat, in a function or at module level) on a plugin path unless that scan brings the hook in. It counts
the hook as brought in when the glob's own statement names the hook or the owner, or when a statement
names one while using what the glob filled. Three scans leave the hook out on purpose and are exempted by
name with their reasons. A receiver whose root the AST cannot see slips the rule. Widening the eight scans
to the hook found no existing offender.

## Consumer note
No action needed. A crash while the findings cache was being rewritten no longer leaves an untracked
`.prawduct/.critic-findings.json.derived`; the staging file is ignored now. If an old one is already in
your tree, delete it.
