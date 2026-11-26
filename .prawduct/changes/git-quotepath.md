---
schema: 1
type: fix
scope: git-quotepath
date: 2026-11-26
title: Readers of git's file names decode its quoting, so a non-ASCII or quote-bearing name is no longer missed
closes: [brookstalley/prawduct#1257]
---
git C-quotes a path name holding a non-ASCII byte, a double quote, a backslash or a control
character (`core.quotepath`, on by default): `skills/café.md` prints as `"skills/caf\303\251.md"`.
Readers that compared that text with names on disk missed the file, usually failing open. A
non-ASCII doc read as a judgeable file (its quoted name ends in `.md"`). A fragment's name went to
`git show` and named nothing. A `.prawduct/` change read as a source file.

### One decoder (Chunk 01)
`lib/gitstate.py` gains `unquote_git_path`, the one decoder of git's quoting. It is exact:
escapes become their bytes, read as UTF-8 with `surrogateescape`. Text that is not one whole
quoted token is returned unchanged. `git_path_lines` splits output on git's newline and decodes
each name. `parse_porcelain_line` now decodes both sides of a rename. It splits on ` -> ` only
when the status says rename, because an ordinary name may hold that text and git does not quote
it. Output read with `-z` is never quoted and is unchanged.

The readers whose answer is a governance verdict now route through it: `critic_mode`
(the extension-deferral span, the committed delta, the uncommitted code files), `coverage`
(the changed-file set, the doc-only PR check, the change-record probe, the working-tree paths),
`native_review` (whether the tree moved), `change_fragments` (the branch's record),
`plan_status` (the commits' files) and `buildplan_refs` (files changed on the branch).
`tests/test_git_path_names.py` reads git's own quoting of real files and holds each reader to
the real names.

### The remaining readers, and a lint (Chunk 02)
`risk` (the review scope's paths), `late_requirements` (the scan, in the working tree and at a
tree, where git quotes the name after its `<tree>:` prefix), `record_lint` (an artifact found by
name, and the added lines of a diff, whose `diff --git` header `gitstate.diff_header_path` now
decodes), `learnings_files` (the rules corpus at a tree), `learnings_compact` (the undo refusal
now shows real names) and `prawduct-hook`'s flake judgment route through the decoder.
`bin/test-reference-verify`, which imports nothing from `lib/`, reads with `-z` instead. The three
sites that set `core.quotepath=false` drop it: it covered non-ASCII only, and the decoder covers
every case it did and more. A file whose header cannot be read is still dropped, never attached
to the previous file. `gitstate.worktree_records` is left as it is: git prints a worktree path raw
there.

`tests/test_git_path_read_lint.py` scans every git argument list that prints names, in every
Python source the plugin ships (`conftest.plugin_python_sources`, hooks included). Each must pass `-z`, sit in a function that uses the decoder, or
be listed with the reason it needs neither: an emptiness or exit-code check, a fixed ASCII
pathspec, or git printing the name raw.

## Consumer note
A file whose name holds a non-ASCII character, a quote or a backslash is now seen by the review,
coverage, doc-only and change-record checks under its real name. A doc-only branch with such a
doc now reads as doc-only.
