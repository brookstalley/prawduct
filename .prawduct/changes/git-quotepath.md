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

`tests/test_git_path_read_lint.py` reads every Python source the plugin ships
(`conftest.plugin_python_sources`, hooks included) for git argument lists in the forms that print
names (`--name-only`, `--name-status`, `ls-files`, `ls-tree`, `diff-tree`, `grep -l` and its
spellings, `--porcelain`). It holds four rules:
- A function makes no more such reads without `-z` than it uses decoders, or it is listed with the
  reason its reads use no name: an emptiness or exit-code check, a fixed ASCII pathspec, or git
  printing the name raw.
- No name read goes through a runner that trims git's output (`evidence.run_git` without
  `strip=False`, `gitstate._git_text`, and the module helpers that trim). Trimming takes the
  status column's leading space off the first porcelain line, and a leading space off a first name.
- Every function that parses `diff --git` headers reads them through `gitstate.diff_header_path`.
- Every reader of `gitstate.git_status_output`'s text decodes, or is listed with why it needs no
  name.

A companion test holds that every git call whose arguments hold no literal is a wrapper forwarding
its caller's arguments, builds its arguments as a literal the scan reads, or is listed.

### Found and fixed by the boundary review
- `evidence.run_git` trims by default, so its name reads, `-z` ones included, lost a leading
  space from their first name. `critic_consolidate.no_judgeable_wip` misread an unstaged first line
  (` M .prawduct/x.py` became `prawduct/x.py`, a judgeable file). Each now passes `strip=False`.
- A `diff --git a/X b/X` header is read at its midpoint, because X may hold ` b/` and git does not
  quote a space. `record_lint`'s diff pins `--src-prefix=a/ --dst-prefix=b/` against a user's
  `diff.noprefix`.
- Porcelain readers split on git's newline only, as `git_path_lines` does, and skip the empty last
  line. `late_requirements.scan` sorts the decoded names, not git's quoted text.



## Consumer note
A file whose name holds a non-ASCII character, a quote or a backslash is now seen by the review,
coverage, doc-only and change-record checks under its real name. A doc-only branch with such a
doc now reads as doc-only.
