---
artifact: build-plan
version: 2
scope: git-quotepath
branch: fix/git-quotepath
base: develop
working-branches: []
last_validated: 2026-11-26
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because this changes how git output is parsed, not who may write review state"
      - "authority fails closed; advice fails soft → conforms, and is the reason for the fix: a C-quoted name today makes coverage, judgeable-path and risk readers miss a file, which fails OPEN (a gate sees no judgeable file, a risk surface sees no match). Decoding the name makes those verdicts see the real path; an undecodable escape keeps the raw text, so a reader can only see more, never less"
      - "local-first, no network, no third-party dependency → conforms: stdlib decoding of output git already produces"
      - "the plugin writes nothing into a governed repo but its own state → conforms: read-side parsing only"
      - "never specific to Python → conforms: file names of any language are decoded alike; no language dispatch changes"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: the bound is the acceptance below (each reader class sees a non-ASCII and a quote-bearing name, seen red first); the per-site edits are a forecast"
      - "every fact has one home → conforms, and is the design: git's quoting rule is decoded in one function in `lib/gitstate.py`; every reader calls it, and a lint keeps new reads on it"
partition: serial — chunk 02 edits callers of the owner chunk 01 adds, and both touch `gitstate.py`
---

## Goals

**Response taken:** Proceed, citing #1257 (stage ready; filed 2026-11-26 as #1232's raw-name class).
The owner ordered it after the two stale branches (`.prawduct/owner-rulings.md`, 2026-11-26 evening).

**Product:** Governance readers compare the file names git prints against plan deliverables, risk
globs, judgeable-path rules and review spans. git C-quotes any name holding a non-ASCII byte, a
double quote, a backslash or a control character (`"skills/caf\303\251.md"`), so today such a file is
silently missed, usually failing open: it is not judgeable, matches no risk surface, credits no
deliverable. Success: every reader that uses a name sees the name as it is on disk.

**Architecture:** one owner, `lib/gitstate.py`:
- `unquote_git_path(text)` decodes git's C-quoting exactly (`\"`, `\\`, `\a\b\t\n\v\f\r`, `\ooo`
  bytes, UTF-8 with `surrogateescape`). Unquoted text is returned unchanged.
- `git_path_lines(stdout)` splits output into lines and decodes each.
- `parse_porcelain_line` decodes both sides of a rename with it. Its docstring's accepted caveat (octal
  escapes kept, "classification only") is false for its callers that match names exactly; it goes.

Sites already passing `-z` stay as they are; `-z` output is never quoted.

**Decisions (inferred, mine, open for the owner at the boundary review):**
- *Decode, not `-z` everywhere.* git's quoting is complete and reversible, and C-quoted output is
  line-safe (a newline in a name prints as `\n`). Decoding fixes the formats with no `-z` (`worktree
  list --porcelain` below git 2.36, `diff --git` headers) with the same function, and each site keeps
  its line parsing, so the diff per site is one call.
- *Not process-wide `core.quotepath=false`* through git's environment config: the hook starts the
  product's own test suite as a child, which would inherit it. It would also leave quotes,
  backslashes and control characters quoted.
- *Emptiness-only and exit-code-only reads are left alone*: they read no name. The lint
  lists them with that reason.
- *Display-only reads:* `learnings_compact.undo_refusals` is decoded, because the owner reads those
  names to act on them. `learnings_migrate.dirty_legacy_files` is left raw (decided mid-build): its
  pathspec names only the fixed ASCII legacy files, so git never quotes what it prints.

**Decisions made mid-build (inferred, mine, open for the owner at the boundary review):**
- *`gitstate.worktree_records` is not decoded.* Measured on git 2.54: `worktree list --porcelain`
  prints a path raw, never C-quoted (non-ASCII, quote, backslash, tab, even a newline), so decoding
  would rewrite a path that really starts and ends with `"`. The classification's "quoted when
  unusual" was wrong. Only `-z` (git 2.36+) carries a newline there; not taken, since no git floor is
  declared and a newline in a worktree path is pathological. The lint lists it with that reason.
- *`bin/test-reference-verify` reads with `-z`* rather than decoding: it imports nothing from `lib/`,
  and a second copy of the decoder there would be a second home for git's quoting rule.
- *`git grep -l` at a tree* prints `<tree>:<name>` with the name alone quoted, so
  `late_requirements.scan` strips the prefix before decoding (seen in the test, not assumed).
- *`record_lint._parse_diff` now attributes a quoted header's lines to its real name*, through a new
  `gitstate.diff_header_path`. Its test that pinned "a quoted header drops its file" is renegotiated
  in the open: the quoted case now names its file, and the invariant that an unreadable header drops
  its file (never the previous file) keeps its own test. `core.quotepath=false` comes off the three
  sites that set it, since the decoder covers every case it did and more.
- *The lint reads every Python source the plugin ships* (`conftest.plugin_python_sources`, which a
  repo guard requires of any plugin scan), not `lib` and `bin` alone, and so reached a site the
  classification did not: `hooks/banner.py`'s porcelain v2 read, a dirty flag only, listed.
- *The lint counts a decoder passed uncalled* (`map(parse_porcelain_line, …)`) as decoding, as the
  entropy inventory counts an API passed uncalled.

- *Boundary review fixes (rev-20261126T212656Z-f4781515):* `strip=False` on every name read through
  a trimming runner, found by a new lint rule rather than by listing the review's five sites (the
  class was wider than the sites it named); `diff_header_path` reads `a/X b/X` at its midpoint; `record_lint` pins the
  diff prefixes; porcelain readers split on `\n`; the lint gains per-read counting, a trim rule, a
  header-parser rule, a status-text rule and a companion for calls it cannot read; the decoder
  test gains a generated domain (every ASCII character but upper case, which a case-insensitive
  filesystem folds, plus awkward Unicode), since `hypothesis` is not a dependency.

**Level:** High. The site table below was built by reading each of the 66 grep hits plus a search
past the grep (2026-11-26); the fix per site is mechanical.

## The sites

Unsafe sites that use the names they read, by reader class (rows from the 2026-11-26 classification;
re-derive with the lint chunk 02 adds):

- name-only: `critic_mode._paths_since_tree`, `critic_mode._committed_files_since`,
  `buildplan_refs._changed_on_branch`, `native_review._tree_moved` (two reads),
  `coverage._coverage_changed_files`, `coverage._pr_diff_is_doc_only`, `coverage.check_change_log_entry`,
  `change_fragments.branch_change_record` (two reads), `risk._review_scope_paths`,
  `bin/test-reference-verify._changed_files`
- ls-files: `critic_mode._paths_since_tree`, `buildplan_refs._changed_on_branch`,
  `coverage._coverage_changed_files`, `record_lint._resolve_artifact`, `prawduct-hook _judge_flakes`,
  `bin/test-reference-verify._changed_files`
- porcelain: `critic_mode._get_uncommitted_code_files`, `coverage._working_tree_paths`,
  `gitstate.git_status_output`'s readers, `critic_consolidate.no_judgeable_wip` (all through
  `parse_porcelain_line`), `risk._review_scope_paths`, `learnings_compact.undo_refusals`;
  `learnings_migrate.dirty_legacy_files` left raw (Decisions)
- log --name-only: `plan_status._log_commits`
- ls-tree --name-only: `learnings_files.corpus_texts_at`
- worktree list --porcelain: `gitstate.worktree_records`, left raw (Decisions: git prints it raw)
- git grep -l: `late_requirements.scan`
- diff headers: `record_lint._added_lines` (drops a quoted name on purpose today)

## Build Chunks

### Chunk 01: One decoder, and the review and coverage readers

- **Description:** `unquote_git_path` and `git_path_lines` in `lib/gitstate.py`; `parse_porcelain_line`
  decodes. Route the readers whose answer is a governance verdict: `critic_mode`, `coverage`,
  `native_review`, `critic_consolidate`, `change_fragments`, `plan_status`, `buildplan_refs`.
- **Depends on:** none
- **Deliverables:** `plugin/lib/gitstate.py`; the seven modules above; `tests/test_gitstate_porcelain.py`
  and a new `tests/test_git_path_names.py`; `.prawduct/changes/git-quotepath.md` (closes #1257).
- **Tests:**
  - `unquote_git_path`: a property test that for any name (non-ASCII, `"`, `\`, tab, newline, space,
    invalid UTF-8 bytes) the decode of git's own quoting of it, read from a real `git ls-files` in a
    temp repo, is the name; plain names unchanged; an unterminated or malformed escape returns the text.
  - Per reader class (name-only, ls-files, porcelain, log --name-only): a real temp repo holding
    one file named with a non-ASCII character and one named with a double quote, and the reader's
    verdict names each file, seen red first.
- **Acceptance criteria:** each chunk-01 reader, given those two files, returns or classifies them
  by their real names.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic` run and blocking findings resolved

### Chunk 02: The remaining readers, and a lint that keeps new reads on the owner

- **Description:** route `risk`, `late_requirements`, `record_lint` (both reads), `learnings_files`,
  `learnings_compact`, `prawduct-hook _judge_flakes`
  and `bin/test-reference-verify`. Drop `risk`'s and the others' `-c core.quotepath=false` where the
  decode now covers it. Add the lint.
- **Depends on:** Chunk 01
- **Deliverables:** the modules above; `tests/test_git_path_names.py`; the lint test.
- **Tests:**
  - Per reader class (ls-tree, worktree list, git grep -l, diff headers): the same two-file fixture,
    seen red first. `record_lint._added_lines` keeps a quote-bearing file.
  - The lint: an AST scan of `plugin/lib` and `plugin/bin` for git argument lists carrying
    `--name-only`, `--name-status`, `--porcelain`, `ls-files`, `ls-tree`, `grep -l` or `diff` headers.
    Each must pass `-z`, or its function must call the owner, or it is listed with its reason
    (emptiness or exit code only). The scan's own control catches each spelling.
- **Acceptance criteria:** every reader in "The sites" sees both fixture names; the lint is green and
  its control red on an unlisted raw read.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
