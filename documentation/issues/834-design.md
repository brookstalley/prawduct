# Issue #834 — Governance: Derive the Change-Log Entry at Merge, Not by Hand: Design

`status: draft · stage: design · area: governance · added: 2026-09-21 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/834`

Builds on `documentation/issues/834-requirements.md` (CLG1–CLG9, Decisions 1–6). This document
resolves the two design questions requirements left open (Decision 1 / CLG8's reconciliation
mechanism, and CLG5's exact issue-linkage plumbing) and turns the result into a concrete build. One
requirements-doc framing is corrected below before design proceeds, because it changes where the
work actually lands.

Related: #830 (severity → channel — unrelated surface, no shared code); #712 / #843 (the
branch-landing and finished-branch probes — cited only as the nearest examples of this repo's
"reuse the existing primitive, don't fork a classifier" convention, which this design follows too).

## Correction to the requirements doc's framing

**"Derive the entry at merge" cannot be literal — this repo has an explicit, load-bearing rule
against it, and the requirements doc already cites the mechanism that rule depends on without
naming the conflict.**

`plugin/skills/pr/SKILL.md` Step 1d states, as a hard rule with its own rationale: *"Nothing about
this branch's work may require a post-merge commit on the integration branch. Protected bases take
commits only by PR, and a dedicated bookkeeping-only PR is ceremony, not governance — so every
release tag, archive, and Status tick rides IN this branch, atomic with the merge (an abandoned PR
then abandons its bookkeeping too — state can't drift)."* A change-log entry written *after*
`gh pr merge` succeeds is exactly the post-merge commit this rule forbids — there is no PR left to
carry it, and `develop`/`main` take commits only by PR under this repo's own gitflow (Step 1d, and
Merge Flow's *"Confirm the bookkeeping merged WITH the PR"* step).

The issue's phrasing ("derive the entry at merge... from the PR body... the merge commit... the
closed issues") is describing which **data** becomes available late, not literally a post-merge
write. The data borrowed from "the merge commit" is actually the branch's `scope:` resolution
(Requirements Decision 2, unaffected by this correction); the data borrowed from "the PR body" is
available the moment the PR description is *drafted*, which happens at Create Step 5 — **before**
push, before `gh pr create`, and certainly before merge. **This design derives the entry at Create
Step 5, as part of the same commit set that rides into the PR**, which is the only point that is
both late enough to have the narrative and early enough to still be a commit the PR carries.

This does not reopen any numbered requirement — CLG1 ("no hand-authoring... beyond writing the PR
description") and Decision 5 ("the narrative body is lifted from the PR's own description") both
already presuppose the description exists before the entry does. It corrects only the load-bearing
*when*, which requirements left as "a design question" (CLG8).

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-21), beyond what requirements already
grounded:

- **`.prawduct/change-log.md` is never judgeable, at any point in the flow — this is what makes
  Step 5 timing safe.** `coverage_algebra.is_judgeable_path` (`plugin/lib/coverage_algebra.py:73-104`)
  checks `gitstate.METADATA_PREFIXES` first and returns `False` immediately for any path starting
  `.prawduct/` (`plugin/lib/gitstate.py:656-659`) — before the `.md` / governance-protected check
  even runs. The module's own commentary states the consequence by name for this exact file:
  *"a change-log entry is written LATE by construction because the PR gate demands one — so
  suite-coupling them would tax every PR with a re-run after the bookkeeping"*
  (`coverage_algebra.py:184-187`). Concretely: committing the derived entry **after** Step 2's
  cumulative-Critic review has already run does not reopen `check-cumulative-critic` — the same
  reasoning Step 1d already relies on for the Build-plan Status tick (*"A checkbox lives under
  `.prawduct/`, which is non-judgeable, so it needs no new review coverage either way"*,
  `pr/SKILL.md:89`) and the change-log `release=` tag it adds in the same step. Deriving the entry
  at Step 5 — after Steps 2–4 — costs no extra review round.
- **`check_change_log_entry` (`plugin/lib/coverage.py:1020-1166`) is a presence probe over a diff,
  not a content check.** It answers one question — did this branch's `merge-base...HEAD` diff add a
  new `## ` header to the change log — via a `git diff --name-only` plus a targeted
  `git diff -- <path>` for the `+## ` line (`:1061-1076`, `:1139-1155`). Nothing about its logic
  assumes *when* in the flow it runs; it only needs the branch's commits to exist. This makes it
  reusable unmodified as both the pre-check ("is an entry needed at all") and the post-check ("did
  deriving one work") this design calls for — no second, differently-tuned presence classifier.
- **`pr_payload.py` already has the two primitives this item's issue-linkage requirement (CLG5)
  needs, one of them private with exactly one existing caller.** `cited_backlog_citations(commit_text,
  change_log_text)` (`plugin/lib/pr_payload.py:434-483`) is already exported and already does what
  CLG5 asks for — extracts backlog ids from free text and tags each with whether a closing keyword
  (`closes`/`fixes`/`resolves`/`closed-by`) actually **claims** the closure, as opposed to merely
  mentioning the id. `_commit_bodies(project_dir, base)` (`:206-224`) is the one-line `git log
  --format=%B <base>..HEAD` call that supplies the commit half of that scan; it is module-private
  with a docstring explaining *why* full bodies matter (69 of 84 backlog citations on this repo's own
  integration branch live in commit bodies, not subjects) but has exactly one caller
  (`assemble`, `:639` via `:678-681`). A second caller needs it public, not re-implemented — this
  design promotes it rather than duplicating three lines of `git log`.
- **The PR body itself does not exist as a file at Create Step 5 today — `gh pr create` is invoked
  with the description composed inline, not via `--body-file`.** `pr/SKILL.md` Step 5
  (`:207`) reads *"Draft the title and description here... Create via `gh pr create`"* with no
  `--body-file` flag named. For this design's title/body to be **the same bytes** in both the
  derived entry and the created PR (Decision 5's "not a second, separately-worded narrative"), the
  flow needs one file both commands read — `gh pr create` already accepts `--body-file` as a
  standard flag, so routing through one avoids composing the description twice from two different
  in-context drafts.
- **The Workflow section of `project-preferences.md` is exactly the established home for a setting
  of this shape.** Six existing rows there (`PR creation`, `PR merge`, `PR merge strategy`, `Commit
  attribution`, `Upstream filing`, `Delegation approval`) share one form: a named default, and a
  parenthetical explaining what the non-default value changes (`plugin/templates/project-
  preferences.md:41-48`). The Merge Flow already reads one of these at runtime by having the
  *agent* consult the file's prose (*"Check `project-preferences.md` for `PR merge` setting"*,
  `pr/SKILL.md:220`) — there is no code that parses this table; every existing consumer is the
  skill's own instructions telling the agent what to look for. This item's adoption gate (Decision 1
  below) is the same kind of setting and needs no new code to be read, only new skill prose.
- **No existing `## Direction` norm or ratified rule blocks a skill from writing to
  `.prawduct/change-log.md` on the author's behalf.** Searched `architecture.md` § Direction for
  anything naming the change log's authorship boundary: the two norms nearest in spirit ("Prawduct
  guides and reviews; it never implements" and the Python-specificity norm, both cited in the 774
  design doc) are about *product* code, not about prawduct's own governance bookkeeping — the same
  distinction that already lets `archive-change-log`, `archive-plan`, and the `release=` tag write
  to this exact file autonomously today.

## Decisions

**1. Derivation runs at Create Step 5, as a new sub-step between drafting the PR description and
pushing — never after `gh pr merge`.** Settles the Correction above as the concrete mechanism. The
derived entry rides in the same commit set as the rest of the branch's work, preserving Step 1d's
atomicity rule (an abandoned PR abandons its change-log entry too, exactly like every other piece of
Step 1d bookkeeping) and costing no extra review round (Grounding facts: the file is never
judgeable).

**2. Adoption is gated by a new `project-preferences.md` Workflow-section row, `Change-log
derivation`, default `manual`.** Mirrors the existing six-row convention exactly (Grounding facts).
Default `manual` means **zero behavior change** for every repo that has not opted in — Step 1c and
Step 5 run exactly as they do today. Set to `automatic`, Step 1c is superseded (below) and Step 5
gains the derivation sub-step. This is the CLG8 reconciliation requirements left open: the two
checks never coexist live on the same PR, because exactly one of them is wired in for a given
product at a given time.

**3. `check_change_log_entry` is reused unmodified, at two different points, as both the pre-check
and the post-check — no second presence classifier.** In `automatic` mode, Step 5 runs it *before*
attempting derivation (its existing `doc-only` / `empty-diff` / `entry-present` exits mean no
derivation is needed — a doc-only branch, or one where an entry already exists from an Update-flow
re-run, gets no second entry); only its `no-entry` exit triggers a derivation attempt. After
deriving, Step 5 runs it again to confirm the write actually landed a `+## ` header — the same
belt-and-suspenders pattern Step 5 already applies to the push (`check-branch-pushed` verifying the
push actually landed, `pr/SKILL.md:207`) rather than trusting the preceding command's exit code
alone. This is why Decision 1 places derivation *at* Step 5 rather than folding it into Step 1c: at
Step 1c the PR title/description do not exist yet, so an early failure could not be repaired by
deriving anyway (Correction, above) — running the same check twice at the point where its failure is
actually actionable is one classifier, two calls, not two classifiers.

**4. Idempotency is the existing release-pending-scope read, not a new marker.** Before writing, the
deriver checks whether this branch's resolved `scope` already appears in
`release_readiness.release_pending_scopes(entries)` (Requirements Decision 2's same resolution
feeding a function that already exists for exactly this "is this scope already accounted for"
question). If so, it refuses rather than adding a duplicate entry for the same scope — the case an
Update-flow re-run through Step 5 produces. No new "have I already derived this" flag; reusing the
release gate's own accounting keeps there being one definition of "this scope already has a pending
entry."

**5. Issue linkage: promote `pr_payload._commit_bodies` to a public `pr_payload.commit_bodies`, and
call the existing `cited_backlog_citations` over commit bodies + the drafted PR description — not a
second extraction.** Directly resolves CLG5's literal text ("using the same resolution
`pr-review-payload` already performs") rather than approximating it. Citations where
`claims_closure` is `True` render as one prose line in the derived entry, `**Closes:** #123,
PFX-4567` — prose, not a new tag key (CLG9). This line is documentation of intent only; it does
**not** itself close anything (GitHub's keyword is inert on this repo's branch model, Requirements
Grounding facts) — the actual close still runs through the existing backend-aware
`/prawduct:backlog update ... closed-by=<scope>` call at Step 1d (markdown backend) or Merge Flow
step 6 (Issues backend), unchanged by this item. Same source of ids, one existing call each — not a
second closing mechanism.

**6. `release=` is never written by the deriver (Requirements Decision 3, carried forward
unmodified) — this item's write path only ever produces a release-pending entry.** The existing
trunk-base `release=vX.Y.Z` stamp at Step 1d, and the `develop→main` release runbook's stamp, are
both untouched: neither reads or writes anything this design adds.

## What ships

1. **`plugin/lib/change_log.py`** — two new pure functions, no change to existing ones:
   - `render_entry(title: str, *, scope: str, body: str, today: str | None = None) -> str` —
     formats `## {today}: {title}\n\n<!-- prawduct: scope={scope} -->\n\n{body}\n`. `today` defaults
     to `date.today().isoformat()`; accepting it as a parameter (rather than calling `date.today()`
     inline) is what makes the formatter itself pure and testable without freezing the clock.
   - `prepend_entry(content: str, entry_text: str) -> str` — inserts `entry_text` immediately before
     the first entry `parse_change_log(content)` finds (i.e., at the top, matching the template's own
     "Append new entries at the top" instruction), or at end-of-file when the log has no entries yet.
     Uses `parse_change_log`'s own line-number boundary — the same technique
     `change_log_archive.split` already uses one module over — rather than a second header regex, so
     insertion and parsing can never disagree about where an entry starts.
2. **`plugin/lib/pr_payload.py`** — `_commit_bodies` renamed to public `commit_bodies` (one-line
   rename plus its one existing call site at `:678-681`); no behavior change.
3. **New module `plugin/lib/change_log_derive.py`** — `derive_entry(project_dir, prawduct_dir, *,
   title, body) -> tuple[str | None, str | None]` (see below).
4. **`plugin/bin/prawduct-hook`** — new `cmd_derive_change_log_entry(project_dir, argv)`, CLI
   dispatch entry `derive-change-log-entry`, usage-string and `_NO_ARGUMENT_COMMANDS`/allowlist
   updates as needed (this command *does* take arguments — `--title`/`--body-file` — so it is not
   added to `_NO_ARGUMENT_COMMANDS`, matching commands like `ledger-append`).
5. **`plugin/templates/project-preferences.md`** and **`.prawduct/artifacts/project-
   preferences.md`** — one new Workflow-section row, `Change-log derivation` (Decision 2).
6. **`plugin/skills/pr/SKILL.md`** — Step 1c gains a one-paragraph preference check and supersession
   note (Decision 2/3); Step 5 gains the derivation sub-step (Decision 1/3); the `allowed-tools`
   frontmatter gains `Bash(prawduct-hook derive-change-log-entry*)`.
7. **`plugin/skills/pr/review-protocol.md`** — no change. The PR reviewer's R-2 backlog check already
   reads whatever citations exist in the change-log entry it is handed (`pr_payload._section_change_log`
   scans the entry body for citations exactly as before); this item does not touch that path.
8. **Tests** — `tests/test_change_log.py` (new cases for `render_entry`/`prepend_entry`),
   `tests/test_change_log_derive.py` (new), `tests/test_pr_payload.py` (rename coverage for
   `commit_bodies`).

## `change_log_derive.derive_entry`

```python
# plugin/lib/change_log_derive.py
"""Deriving a change-log entry from data this flow already produced (issue #834).

Runs at PR-create time (Create Step 5), never post-merge — `.prawduct/change-log.md`
is never judgeable (`coverage_algebra.is_judgeable_path`, gated on `gitstate.
METADATA_PREFIXES`), so landing this write after the cumulative-Critic review has
already run costs no extra review round; a post-merge commit to the integration
branch would violate `pr/SKILL.md` Step 1d's atomicity rule, which is why this is
NOT triggered by `gh pr merge`.

Fails closed toward hand-authoring, never toward writing something wrong: an
unresolved scope, or a scope already release-pending, refuses rather than guessing
or duplicating (both readable by `check_change_log_entry`'s `no-entry` exit as
"still needs an entry" — the caller falls back to the pre-existing manual flow).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def derive_entry(
    project_dir: Path,
    prawduct_dir: Path,
    *,
    title: str,
    body: str,
) -> tuple[str | None, str | None]:
    """Write a derived entry to the live change log. Returns ``(scope, refusal)``.

    Exactly one of the two is set. ``scope`` on success is the resolved scope the
    entry was tagged with — useful to the caller for logging, not required to act
    on. ``refusal`` is a sentence naming why nothing was written; every refusal
    here is recoverable by the existing hand-authoring flow, so none of them are
    hard failures of the PR itself.
    """
    from . import buildplan_refs, change_log, release_readiness  # noqa: PLC0415

    reviewed = buildplan_refs.resolve_branch_plan(project_dir, prawduct_dir)
    scope = reviewed.scope
    if not scope:
        return None, (
            "no build-plan scope resolved for this branch "
            f"({reviewed.gap or 'no claiming plan'}) — derivation needs the "
            "existing scope-to-plan resolution and will not guess a scope from "
            "commit text. Write the change-log entry by hand."
        )

    log_path = prawduct_dir / "change-log.md"
    try:
        content = log_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"could not read {log_path}: {exc}. Write the entry by hand."

    entries = change_log.parse_change_log(content)
    if scope in release_readiness.release_pending_scopes(entries):
        return None, (
            f"a release-pending entry already tags scope={scope!r} — not adding "
            "a duplicate. Edit that entry by hand if its narrative needs updating."
        )

    entry_text = change_log.render_entry(
        title, scope=scope, body=body, today=date.today().isoformat()
    )
    new_content = change_log.prepend_entry(content, entry_text)
    try:
        log_path.write_text(new_content, encoding="utf-8", newline="")
    except OSError as exc:
        return None, f"could not write {log_path}: {exc}. Write the entry by hand."
    return scope, None
```

`--title`/`--body-file` at the CLI layer (`cmd_derive_change_log_entry`) additionally appends the
`**Closes:**` line (Decision 5) before calling `derive_entry`, using `pr_payload.commit_bodies` and
`pr_payload.cited_backlog_citations` — kept out of `derive_entry` itself so the pure write path has
one job and the citation scan (which needs `base`, resolved separately) stays where
`buildplan_refs`/`pr_payload` already resolve it:

```python
# plugin/bin/prawduct-hook, cmd_derive_change_log_entry (sketch)
def cmd_derive_change_log_entry(project_dir: Path, argv: list[str]) -> int:
    """``derive-change-log-entry --title T --body-file F``. Issue #834.

    Always exits 0 or 1 with a NAMED reason — never a bare failure — because
    every refusal here has a working fallback (hand-author the entry) and the
    caller (Create Step 5, in `automatic` mode) must be able to tell "nothing
    written, do it by hand this once" apart from a real usage error.
    """
    title, body_file = _parse_title_body_flags("derive-change-log-entry", argv)
    if title is None:  # usage error already printed
        return 2
    try:
        body = Path(body_file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"derive-change-log-entry: could not read {body_file}: {exc}", file=sys.stderr)
        return 1

    lib_root = _plugin_root()
    if lib_root not in sys.path:
        sys.path.insert(0, lib_root)
    try:
        from lib import buildplan_refs, change_log_derive, gitstate, pr_payload
    except ImportError as exc:
        print(f"derive-change-log-entry unavailable ({exc}); write the entry by hand.", file=sys.stderr)
        return 1

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    reviewed = buildplan_refs.resolve_branch_plan(project_dir, prawduct_dir)
    base, base_reason = _resolve_base_for_citations(project_dir)  # existing resolve-base call
    closes_line = ""
    if base:
        claimed = [
            c.id for c in pr_payload.cited_backlog_citations(
                pr_payload.commit_bodies(project_dir, base), body
            ) if c.claims_closure
        ]
        if claimed:
            closes_line = f"\n\n**Closes:** {', '.join(claimed)}"

    scope, refusal = change_log_derive.derive_entry(
        project_dir, prawduct_dir, title=title, body=body + closes_line
    )
    if refusal:
        print(f"derive-refused: {refusal}", file=sys.stderr)
        return 1
    print(f"derived: change-log entry added, scope={scope}.")
    return 0
```

## `pr/SKILL.md` changes

**Step 1c**, prepended:

> **First, check `project-preferences.md` for `Change-log derivation`.** If `automatic`: print a
> NOTE — *"Change-log derivation: automatic — presence is verified at Step 5, after the PR
> description is drafted, not here."* — and proceed directly to Step 1d. Do not run
> `check-change-log-entry` at this step in `automatic` mode: the PR title and description do not
> exist yet, so a `no-entry` result here could not be repaired until Step 5 anyway, and running it
> twice for no actionable reason is only cost. If `manual` (the default) or unset, proceed exactly as
> below — nothing changes for a product that has not opted in.

**Step 5**, inserted between drafting the title/description and "Push branch with `-u`":

> **In `automatic` mode only:** write the drafted description to a file (the same file `gh pr create
> --body-file` will read below — one narrative, one file, never two drafts of the same text). Run
> `prawduct-hook check-change-log-entry`. `doc-only` / `empty-diff` / `entry-present`: no derivation
> needed, continue. `no-entry`: run `prawduct-hook derive-change-log-entry --title "<title>"
> --body-file <path>`; on `derive-refused:`, tell the user why and write the entry by hand this once
> (the refusal names the reason and is always recoverable — Change-log Derive Decisions 4/6), then
> continue as `manual` mode does. On success, re-run `prawduct-hook check-change-log-entry` as
> confirmation — it must now report `entry-present`; if it does not, treat it exactly as a `no-entry`
> failure and stop rather than push an unconfirmed state. `entry-edited-not-added` / `no-base` /
> `git-failed`: fall back to the existing manual remedy (check by hand, note it in the PR
> description) — these are the same exceptional git-evaluation failures Step 1c already names, not
> new cases this item introduces.

## Test plan

**`tests/test_change_log.py` additions:**
1. `render_entry` produces exactly `## {date}: {title}\n\n<!-- prawduct: scope={scope} -->\n\n{body}\n`
   for a representative title/scope/body — no `release=` ever appears (pins CLG3).
2. `prepend_entry` on a log with existing entries inserts before the first one, preamble untouched
   (pins the template's "append at the top" convention).
3. `prepend_entry` on a log with **no** entries (preamble-only, or empty file) appends at end —
   round-trips through `parse_change_log` afterward, recovering exactly one entry.
4. Round-trip: `parse_change_log(prepend_entry(content, render_entry(...)))` finds the new entry with
   the exact `scope=` tag and no `tag_conflicts`/`unconsumed_tag_lines` — pins that the writer and
   the existing reader agree about the format, the actual risk `validate_change_log_tags`'s own
   docstring warns about for any change-log writer.

**`tests/test_change_log_derive.py` (new):**
5. `derive_entry` on a fixture branch whose plan declares `scope: demo` writes a new top entry
   tagged `scope=demo`, no `release=`; `(scope, refusal)` returns `("demo", None)`.
6. No claiming plan (`resolve_branch_plan` returns `scope=None`) → refuses, log file untouched
   (assert file bytes unchanged) — pins Decision fail-closed-toward-hand-authoring.
7. A fixture where `release_pending_scopes` already contains the resolved scope → refuses with the
   duplicate-scope message, log file untouched — pins Decision 4 (idempotency via reuse, not a new
   marker).
8. Unreadable/unwritable log path (permission-denied fixture) → refuses with the OSError detail,
   never raises — matches every other refusal-shaped command in this codebase.
9. `check_change_log_entry` run against a fixture branch **after** a successful `derive_entry` call
   reports `entry-present` — the cross-module contract Decision 3 depends on (the same predicate
   used as pre-check and post-check must actually see the derived write as a `+## ` addition).

**`tests/test_pr_payload.py` additions:**
10. `commit_bodies` (renamed, public) — same assertions the current private-function test already
    makes, confirming the rename changed no behavior.
11. `cited_backlog_citations` called with a drafted PR-description string as its second argument
    (rather than a change-log entry body) still detects a `closes: #N` claim in it — pins that the
    function's existing contract ("full text, not a rendering of it") holds for this new caller,
    which was not exercised by any existing test.

**`prawduct-hook` CLI test additions** (existing subcommand-test file):
12. `derive-change-log-entry --title T --body-file F` on a fixture repo with a resolvable scope →
    exit 0, `derived: ... scope=<x>`, log file grew by one entry.
13. Same, but the fixture branch's commits contain `Closes #42` → the written entry's body ends with
    `**Closes:** #42`. That derived line records intent and closes nothing: GitHub fires a closing
    keyword only for a PR merged into the repository's **default** branch, so on this repo's
    gitflow base it is inert and the real close stays with the backend-aware call (Decision 5).
14. `derive-change-log-entry` with no claiming plan → exit 1, `derive-refused:` naming the reason.
15. Missing `--title` or `--body-file` → exit 2 (usage error), matching this repo's documented
    exit-code scheme.

## Scope-out (this item)

- **Literal post-merge derivation.** Explicitly ruled out by the Correction above — the requirements
  doc's own Decision 1 already anticipated needing to pick one of "a project-preference flag the
  gate reads, or the gate retired"; this design picks neither literally but the preference-flag shape
  Decision 1 named, applied to *where derivation runs* rather than to the presence gate's own logic.
- **A new tag key for `**Closes:**` citations.** Ships as prose (Decision 5), per CLG9's SHOULD.
- **Changing what the PR reviewer's R-2 check reads.** `pr_payload._section_change_log` already scans
  whatever body the entry carries; this item changes who writes that body, not how it is read.
- **Any change to `release=` stamping, the `develop→main` release runbook, or
  `check-releasability`'s logic** — Requirements Decision 3/CLG3/CLG6, unmodified, carried forward.
- **A markdown-backend-specific or Issues-backend-specific code path.** The deriver produces prose;
  the actual backlog-close call is unchanged and already backend-aware (Decision 5).
- **Retiring `check_change_log_entry` for `manual`-mode products, or removing Step 1c's existing text
  wholesale.** It stays exactly as it is today for the default (`manual`) case — Decision 2's whole
  point is that opting in costs the adopter nothing extra and costs everyone else nothing at all.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] A PR created through `/prawduct:pr` in `automatic` mode produces a change-log entry with no
      hand-authored tag line, per CLG1/CLG2 — `derive_entry` (What ships §3) called from Step 5.
- [ ] The derived entry's `scope=` matches the governing build plan and carries no `release=`, per
      CLG2/CLG3 — `render_entry`/`derive_entry`, pinned by test-plan cases 1, 5.
- [ ] `check-releasability` and the scope→plan warnings pass on a derived entry exactly as on a
      hand-authored one, per CLG6/CLG7 — unmodified reuse (What ships, Decisions 3–4), pinned by
      case 9's cross-module check.
- [ ] The pre-merge presence gate and derivation never disagree on the same PR, per CLG8 — Decision
      2's adoption gate plus Decision 3's reuse of one classifier at two points, pinned by case 9.
- [ ] Issue links route through the existing backend-aware close call, never `Closes #N`, per CLG5 —
      Decision 5's `**Closes:**` prose is documentation of intent only, because GitHub fires a
      closing keyword only for a PR merged into the repository's **default** branch and this base
      is not it; the actual close is the pre-existing Step 1d / Merge Flow *"Close the backlog
      items this PR resolves"* call, unmodified.

## Evidence / references

- `documentation/issues/834-requirements.md` — CLG1–CLG9, Decisions 1–6, and the grounding this
  design builds on (the tag grammar, `check_releasability`'s reads, the scope→plan machinery, the
  presence gate, the PR-body-as-only-narrative-source fact).
- `plugin/skills/pr/SKILL.md:79-91` (Step 1d, the atomicity rule the Correction is built on), `:69-77`
  (Step 1c, the presence gate this design supersedes conditionally), `:206-208` (Step 5, where
  derivation is inserted), `:218-249` (Merge Flow, unaffected — confirms no post-merge write is
  needed or wanted).
- `plugin/lib/coverage_algebra.py:73-104` (`is_judgeable_path`), `:184-187` (the comment naming
  change-log entries as written late "by construction") — the fact that makes Step 5 timing free of
  extra review cost.
- `plugin/lib/gitstate.py:656-659` (`METADATA_PREFIXES`) — confirms `.prawduct/` is never judgeable,
  the mechanism behind the above.
- `plugin/lib/coverage.py:1020-1166` (`check_change_log_entry`) — reused unmodified as both pre- and
  post-check (Decision 3).
- `plugin/lib/pr_payload.py:206-224` (`_commit_bodies`, promoted), `:434-483`
  (`cited_backlog_citations`, reused), `:639-683` (`assemble`, its one existing caller, updated for
  the rename only).
- `plugin/lib/change_log_archive.py:92-112` (`split`) — the line-number-boundary technique
  `prepend_entry` follows rather than a second header regex.
- `plugin/lib/release_readiness.py:138-160` (`release_pending_scopes`) — reused for idempotency
  (Decision 4).
- `plugin/lib/buildplan_refs.py:616-632` (`resolve_branch_plan`) — reused for scope resolution
  (Requirements Decision 2, unchanged here).
- `plugin/templates/project-preferences.md:41-48` (the six-row Workflow-section convention the new
  `Change-log derivation` row follows) and `pr/SKILL.md:220` (`PR merge`'s read-by-the-agent pattern,
  the precedent for how `automatic`/`manual` gets consulted with no new code).
- `.prawduct/artifacts/architecture.md` § Direction — searched for a norm bounding this item's
  autonomous write to the change log; none found (Grounding facts), and the existing
  `archive-change-log`/`archive-plan`/`release=`-stamp precedents already write to this file without
  human transcription.
