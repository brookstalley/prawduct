---
schema: 1
type: fix
scope: scan-and-staging-classes
date: 2026-11-23
title: the findings cache stages under the temp suffix, and every plugin source scan reaches the hook
closes: []
---
Two observations accepted at the #1229 boundary, fixed as the classes they belong to.

**Rename-into-place staging.** The branch findings cache writer staged its validated candidate as
`.prawduct/.critic-findings.json.derived` and renamed it into place. That name is outside
`core.TEMP_SUFFIX`, so a crash between the write and the rename left an untracked file that neither the
ignore contract nor the session-file exemption covers. The candidate is now
`.critic-findings.json.derived.prawduct.tmp`, written directly: it is itself the staging file, and a torn
one fails validation before it reaches the cache. `tests/test_temp_suffix.py` swept temp names ending in
`.tmp`, so it could not see a staging file with another name. A second sweep now keys on the act: every
`os.replace`/`os.rename`, and every one-argument `.replace`/`.rename`, must take a source built with
`temp_sibling` or `TEMP_SUFFIX`. The one rename that moves a finished file rather than staging one, the
archive move in `_archive_leftovers`, is exempted by name, and the exemption fails if that function is gone.
The writer's invalid-candidate branch, which had no test, now has one.

**Source scans that skip the hook.** Seven structural tests globbed `plugin/**/*.py` and passed over the
extensionless `plugin/bin/prawduct-hook`, which holds the hook's whole CLI. One of them was the AST pin
that only `branch_review_chain` calls `review_chain`. A defect in the hook stayed green under each of them.
The source set now has one owner, `conftest.plugin_python_sources`, and the three helpers that duplicated
it read it too. `tests/test_source_scans_reach_the_hook.py` fails any test function that globs `*.py` on a
plugin path without bringing the hook in. It follows the root's name through derivations and through
imports from sibling test modules. Widening the seven scans to the hook found no existing offender.

## Consumer note
No action needed. A crash while the findings cache was being rewritten no longer leaves an untracked
`.prawduct/.critic-findings.json.derived`; the staging file is ignored now. If an old one is already in your
tree, delete it.
