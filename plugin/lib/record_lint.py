"""Deterministic record-lint — the checks a reviewer should never re-derive.

On 2026-07-29, 57% of the day's Critic findings targeted hand-authored
governance *records* rather than shipped behavior: a dangling ``file:line``
citation, a backlog id that no longer exists, a ``governed_by:`` block that
disposed of one of an artifact's three norms, a test-count claim corrected three
times. Each correction is a commit, each commit extends HEAD, and that is how a
record defect buys a review round.

None of those need judgment. This module answers them in code, at dispatch
time, and :func:`lint_records` results ride the Critic's dispatch manifest so
the review protocol can tell reviewers the answers are already known.

**Advice, not authority.** Findings here are advisory: they enter the manifest
for the builder to fix or disposition, and they never gate. What they must never
do is *silently pass* — a check that cannot read its inputs reports itself
``unchecked`` with a reason (the same posture the per-language dispatch norm
requires of the compliance canary), because an unrun check and a clean one are
otherwise indistinguishable at the output.

**Cost is proportional to the diff, never the repo.** Consumers are ~20x this
repo's size, so every line-scoped check reads only the lines a change *added*
(``git diff --unified=0``) rather than re-scanning whole files. That is also why
the tripwire below does not drown in history: ``.prawduct/change-log.md`` holds
years of suite-total claims, and linting the added lines of a changed record
sees only the entry just written.

**Yield is observable** (``nonfunctional-requirements.md`` § Direction —
proportionality ratchets both ways; a control born after 2026-07-29 emits its
yield at birth). This control does not print-and-forget: its per-check counts
land in the dispatch manifest, and ``critic_consolidate`` carries them into the
review **fact**, so "how often did record-lint fire, and on what" is a query
over the evidence store rather than an argument. The yield *query* is the
janitor's Norm Health sweep, deliberately not here.

**Records are markdown, plus the governance state under ``.prawduct/``.** Prose
is where most hand-authored claims live, so ``.md`` anywhere in the repo is a
record. But it is not where they *all* live, and the gap was not hypothetical:
this module's suite-total tripwire swept the plugin's markdown clean while ten
governed products carried a hand-maintained test count in
``.prawduct/project-state.yaml`` — one of them on a single line of roughly 52 KB
— and markdown-only could not see any of it. So a YAML file **directly under a
``.prawduct/`` directory** is a record too: that file is hand-authored, it is
asserted as a product's source of truth, and it is exactly as prone to a claim
that drifts. Classification stays by path and suffix — no content is read and no
language is classified (``architecture.md`` § Direction: Python-implemented,
never Python-specific).

**Scoped to governance state, never to YAML generally.** A product's CI config,
its lockfiles and its own app config are its data, not governance records;
linting them would put this control in the business of grading product content.
The three markdown-specific checks are unaffected because each already selects
its own inputs — ``learnings-entry-shape`` by filename, ``governed-by-gap`` by
build-plan name (``.md$``) — rather than trusting the record set to be markdown;
tests pin that, so widening the set here cannot silently widen them.

Archived history is excluded whatever its suffix: it is not being asserted any
more.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import buildplan_refs, evidence, learnings_files
from .core import resolve_build_plan_path

#: Every check this module can run, in manifest order. Named so a consumer can
#: tell "ran and found nothing" from "never ran" (see ``unchecked`` below).
CHECKS = (
    "chunk-ref-missing",
    "governed-by-gap",
    "suite-total-claim",
    "learnings-entry-shape",
    "learnings-over-budget",
    "learnings-budget-unreasoned",
)

# Two checks were built, measured, and REMOVED before this shipped — recorded
# here because the removal is the norm working, not an omission to be helpfully
# restored (`nonfunctional-requirements.md` § Direction: a control that fires
# and catches nothing is removed by default).
#
# - **dangling-ref** (every backticked `file`/`file:line` citation in a changed
#   record resolves). On the 40-file branch that introduced it: 3 findings, 0
#   true positives. Every hit was prose that is path-SHAPED and not a path —
#   `backlog.md:307/311/315`, `parents/exist_ok` — because a multi-line citation
#   keeps its slashes past `_ref_path_part`, which strips only a trailing `:N`.
#   Chunk deliverables, the citations that actually gate anything, are covered
#   by `chunk-ref-missing` below.
# - **unknown-backlog-id** (ids cited in a record exist). 0 findings, and on the
#   Issues backend it could only ever report `unchecked`.
#
# Re-adding either needs evidence that the class costs review rounds — which the
# `record_lint` counts now in every review fact can supply, and argument cannot.

#: History, not live assertion — an archived record is excluded from every check.
_ARCHIVE_MARKERS = ("/archive/", "archive/")


#: A suite-total test claim in durable prose — the subtraction's tripwire. The
#: evidence store already records pass/fail per tree (``test-evidence record``),
#: so a number here is a hand-maintained copy of a machine-held fact, and it
#: drifts. Deliberately narrow: 3+ digits, or an explicit "full suite"/"total"
#: framing. A two-digit count is nearly always a scoped or delta count
#: (``+14 tests``, ``28 tests``), which is a different claim and not this one's
#: business. A leading ``+``/``-``/``.``/``/`` blocks the first arm so a delta or
#: a version fragment never reads as a total. The second arm exists only for a
#: two-digit suite claim ("full suite 99 passing"), which the first arm's digit
#: floor would miss; a bare "total" was deliberately dropped from it, because
#: "a total of 25 backlog items" is not a test claim, and a tripwire that fires
#: on prose like that gets ignored — which costs more than the claim it catches.
_SUITE_TOTAL_RE = re.compile(
    r"(?<![\w.+/-])\d{3,6}\s*(?:tests?|passing|green|pass(?:ed|es|ing)?)\b"
    r"|(?:(?:full|whole|entire) suite|suite total)\W{0,12}\d{2,6}",
    re.IGNORECASE,
)

# --- YAML frontmatter `governed_by:` shape (line-based; this codebase carries no
# YAML dependency — `core.read_str_yaml_key` is the same posture). ------------
_FRONTMATTER_FENCE = "---"
_GOVERNED_BY_RE = re.compile(r"^governed_by:\s*$")
_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][\w-]*:")
_ARTIFACT_ENTRY_RE = re.compile(r"^(\s*)-\s+artifact:\s*(\S+)\s*$")
_DISPOSITIONS_KEY_RE = re.compile(r"^(\s*)dispositions:\s*$")
_LIST_ITEM_RE = re.compile(r"^(\s*)-\s+\S")

#: A markdown heading, level + text. Local rather than imported: ``norm_probes``
#: owns the same grammar but answers a different question (every logical *line*
#: inside a Direction section, for its ``Why:``/``Status:`` scans) and pulls in
#: the advisory-store, backlog and coverage-probe stack, which is far too heavy
#: for the ``critic-begin`` dispatch path. If the grammar ever changes, both
#: matchers change — they are the same six characters of markdown.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

#: A build plan by filename. The `governed_by:` check reads plans only. Two
#: conventions are live and `core.resolve_build_plan_path` documents both: the
#: `build-plan-<scope>.md` prefix form, and the scope-named `<scope>-plan.md`
#: suffix form (`artifacts/v1.6.0-foo-plan.md`). Matching only the prefix form
#: would skip a scope-named plan silently — and silently is the whole problem,
#: since a plan that is never read reports zero gaps exactly like a complete one.
_BUILD_PLAN_RE = re.compile(r"(^|/)(?:build-plan[^/]*|[^/]*-plan)\.md$")


# ---------------------------------------------------------------------------
# Record classification
# ---------------------------------------------------------------------------


#: Governance state files: YAML sitting directly inside a ``.prawduct/`` dir.
#: Anchored on the directory rather than on the name so a product that adds a
#: second state file is covered, while a YAML one level deeper — under
#: ``.prawduct/artifacts/`` or a product's own tree — is not: nesting is how
#: this stays a check on a repo's declared state rather than on its data.
_STATE_RECORD_RE = re.compile(r"(^|/)\.prawduct/[^/]+\.ya?ml$")


def is_record(path: str) -> bool:
    """True when ``path`` is a governance record this module lints.

    Markdown anywhere, or YAML directly under a ``.prawduct/`` directory; never
    archived. Path and suffix only by design: no content is read to decide, and
    no language is classified.
    """
    if not (path.endswith(".md") or _STATE_RECORD_RE.search(path)):
        return False
    return not any(marker in f"/{path}" for marker in _ARCHIVE_MARKERS)


def records_in(paths: "list[str] | None") -> list[str]:
    """The record subset of ``paths`` (order preserved, None-safe)."""
    return [p for p in (paths or []) if is_record(p)]


# ---------------------------------------------------------------------------
# Added-line extraction — the cost boundary
# ---------------------------------------------------------------------------


_DIFF_HEADER_RE = re.compile(r"^diff --git a/(?:.*) b/(.+)$")
_HUNK_RE = re.compile(r"^@@+ .*?\+(\d+)(?:,\d+)? @@")


def _added_lines(
    project_dir: Path, base_tree: str, head_tree: str, paths: list[str]
) -> "dict[str, list[tuple[int, str]]] | None":
    """``{path: [(line_num, text), ...]}`` for the lines each path ADDED between
    two trees.

    ``None`` when the diff cannot be computed — the caller reports the check
    ``unchecked`` rather than treating an unreadable diff as an empty one.
    ``--unified=0`` means no context lines, so inside a hunk every ``+`` line is
    genuinely added and the hunk header carries its new-file line number.

    **One git call for every path, not one per path.** At consumer scale a
    change can touch hundreds of records, and a subprocess each would make this
    control's cost scale with the number of files rather than with the diff —
    the exact shape the language-agnosticism norms were written to prevent
    (`architecture.md` § Direction).

    A path absent from the result changed in a way this parser saw no added
    lines for (a pure deletion, a mode change); the caller reads a missing key
    as "nothing added", which is correct and distinct from the ``None`` above.
    """
    rc, out, _err = evidence.run_git(
        project_dir,
        # `core.quotepath` defaults on, so git C-quotes any non-ASCII pathname in
        # the `diff --git` header (`"a/caf\303\251.md"`). The header parser would
        # then miss it and attach that file's added lines to the PREVIOUS file —
        # wrong attribution, silently. Turning it off is a one-flag fix and keeps
        # this working for any repo whose records aren't named in ASCII.
        "-c", "core.quotepath=false",
        "diff",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        base_tree,
        head_tree,
        "--",
        *paths,
    )
    if rc != 0:
        return None
    return _parse_diff(out)


def _parse_diff(out: str) -> "dict[str, list[tuple[int, str]]]":
    """The `git diff --unified=0` parser, split from its subprocess so the
    header edge cases can be exercised as text — a pathname holding `"` cannot
    be committed on every platform this test suite runs on."""
    by_path: dict[str, list[tuple[int, str]]] = {}
    current: "list[tuple[int, str]] | None" = None
    in_hunk = False
    line_num = 0
    for raw in out.splitlines():
        header = _DIFF_HEADER_RE.match(raw)
        if header:
            current = by_path.setdefault(header.group(1), [])
            in_hunk = False
            continue
        if raw.startswith("diff --git "):
            # A header the regex could not parse. `core.quotepath=false` above
            # covers non-ASCII names, but git still C-quotes a pathname holding
            # `"` or `\`, and that quoting is not disableable. Dropping the file
            # loses one file's findings; leaving `current` alone would attach its
            # added lines to the PREVIOUS file, and a finding naming a record
            # that never contained the text is indistinguishable from a true one.
            # Silence beats a confident lie. (Content lines cannot reach here —
            # inside a hunk every line carries a `+`/`-`/space prefix.)
            current = None
            in_hunk = False
            continue
        hunk = _HUNK_RE.match(raw)
        if hunk:
            in_hunk = True
            line_num = int(hunk.group(1))
            continue
        # Everything before the first hunk is file metadata (`--- a/x`,
        # `+++ b/x`, `new file mode …`). Gating on `in_hunk` rather than
        # prefix-matching `+++` is what keeps a genuinely added line whose text
        # begins with `++` from being mistaken for a header.
        if not in_hunk or current is None:
            continue
        if raw.startswith("+"):
            current.append((line_num, raw[1:]))
            line_num += 1
    return by_path


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _finding(check: str, path: str, line: "int | None", detail: str) -> dict:
    return {"check": check, "path": path, "line": line, "detail": detail}


def _check_suite_totals(path: str, added: "list[tuple[int, str]]") -> list[dict]:
    """Suite-total test claims on added lines — the subtraction's tripwire.

    The claim is not wrong, it is *unmaintainable*: the number is true the day
    it is written and drifts the next, and nothing consumes it, because the
    evidence store records pass/fail per tree.
    """
    findings: list[dict] = []
    for line_num, text in added:
        match = _SUITE_TOTAL_RE.search(text)
        if match is None:
            continue
        findings.append(
            _finding(
                "suite-total-claim",
                path,
                line_num,
                f"suite-total test claim {match.group(0).strip()!r} — the evidence "
                "store records pass/fail per tree; a prose copy drifts and nothing "
                "reads it",
            )
        )
    return findings


#: `learnings.md` holds the RULE; `learnings-detail.md` holds the narrative.
#: A rule longer than this is carrying its evidence, which belongs in detail.
#: Set so a rule carrying its evidence trips it and an ordinary rule does not:
#: at the 2026-07-30 compaction, 16 of 156 headings were above the line.
#: **No percentile relation is claimed here, deliberately.** Four successive
#: attempts to state one shipped a wrong number — each while correcting the
#: last — because the statistic moves with every entry edited while the
#: sentence does not. Recompute the distribution if you need it:
#:   python3 -c "import re,statistics as s;h=[len(x[3:].strip()) for x in re.findall(r'^## .*$',open('.prawduct/learnings.md').read(),re.M)];print(s.median(h),sorted(h)[int(.9*len(h))])"
_LEARNINGS_RULE_MAX = 400

_LEARNINGS_REL = "learnings.md"


def _first_heading_line(text: "str | None") -> int:
    """1-indexed line of the first ``## `` entry, or 0 if there is none.

    Everything above it is the file's own preamble — prose by design, and not a
    finding. Without this the check reports the header paragraph that explains
    the format as a violation of the format.
    """
    if not text:
        return 0
    for i, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            return i
    return 0


def _follows_heading(text: "str | None", line_num: int) -> bool:
    """Is the 1-indexed line inside the FIRST body block under a ``## `` heading?

    Block, not line: a rule hard-wrapped at terminal width becomes a heading plus
    several body lines, and every one of them is part of the same continuation.
    Checking only the immediate predecessor would guard line 2 and hand line 3
    the destructive "move it" instruction — in the same report, on the same
    sentence. So this walks back over the whole contiguous non-blank run and asks
    whether that run starts under a heading.

    A blank line ends the continuation only once body prose precedes it. A
    paragraph separated from its heading by nothing but blank lines is still the
    first block and still gets the guarded message — a rule may be written with a
    blank line under the heading, so that position cannot be assumed safe. The
    bare move instruction therefore fires only after at least one non-blank body
    line, which is the one position where a continuation cannot be.

    Returns False when the file text is unavailable, so an unreadable file yields
    the conservative branch rather than a confident instruction derived from
    nothing.
    """
    if not text:
        return False
    lines = text.splitlines()
    i = line_num - 2  # 0-indexed predecessor of a 1-indexed line
    if i >= len(lines):
        return False
    # Back to the start of this contiguous block (a heading also terminates it).
    while i >= 0 and lines[i].strip() and not lines[i].startswith("## "):
        i -= 1
    if i >= 0 and lines[i].startswith("## "):
        return True  # block runs flush under the heading
    while i >= 0 and not lines[i].strip():
        i -= 1
    return i >= 0 and lines[i].startswith("## ")


def _check_learnings_shape(
    path: str, added: "list[tuple[int, str]]", text: "str | None" = None
) -> list[dict]:
    """Keep `learnings.md` a rule index rather than a second detail file.

    **Why this exists at all.** Compaction ran twice (2026-06-10, 2026-07-17) and
    the file regrew past its starting size both times, because a sweep is a
    one-time subtraction against a continuous addition. The 2026-07-30 pass took
    it 121KB -> 34KB; without something that fires per entry, the third sweep is
    already scheduled.

    **Why it checks the heading and not just the body.** The rule has always been
    "keep the rule here, move the narrative to detail" — so narrative migrated
    into the `##` heading, where the sweep never looked. On the eve of this pass
    the longest "rule" was 1,921 characters, a paragraph wearing a heading. A
    control that watches one channel relocates the content it was meant to stop.

    Added lines only, so existing entries are grandfathered and the check costs
    nothing until someone writes a new learning — which is the moment the
    guidance is actually actionable.
    """
    findings: list[dict] = []
    preamble_end = _first_heading_line(text)
    for line_num, line in added:
        if preamble_end and line_num < preamble_end:
            continue  # the file's own header prose, not an entry body
        stripped = line.strip()
        if stripped.startswith("## "):
            rule = stripped[3:].strip()
            if len(rule) > _LEARNINGS_RULE_MAX:
                findings.append(
                    _finding(
                        "learnings-entry-shape",
                        path,
                        line_num,
                        f"learnings rule is {len(rule)} chars (>{_LEARNINGS_RULE_MAX}) — "
                        "the heading carries the When-X-do-Y-because-Z rule; move the "
                        "evidence to learnings-detail.md under the same heading",
                    )
                )
        elif stripped and not stripped.startswith(("#", "---", "<!--", "[[")):
            # Body lines get one of two OPPOSITE remedies, and picking wrong in
            # one direction destroys data: telling an author to move a sentence
            # *continuation* to detail truncates the rule, and the loss is silent
            # because the heading still parses, still renders, and still reads as
            # a rule right up to the dangling word. Three rules were lost exactly
            # that way and repaired on 2026-07-31.
            #
            # Nothing here can classify reliably — a continuation may resume with
            # a backtick or a proper noun, and a narrative paragraph's first line
            # sits in the same position as a continuation. So position decides
            # which ADVICE is safe rather than which label is true: a line
            # adjacent to the heading is offered both remedies with the guard
            # clause attached, and the bare "move it" instruction is issued only
            # where a continuation cannot be (after intervening body prose).
            # Deliberately no case test — it is wrong for backtick-initial
            # continuations and meaningless in caseless scripts.
            if _follows_heading(text, line_num):
                findings.append(
                    _finding(
                        "learnings-entry-shape",
                        path,
                        line_num,
                        "body line directly under a `## ` heading — if it "
                        "CONTINUES the rule sentence, join it onto the heading "
                        "as one physical line; if it is evidence, move it to "
                        "learnings-detail.md under the same heading. Either way "
                        "the heading must still read as a complete rule "
                        "afterwards — moving a continuation truncates it "
                        "mid-sentence, and nothing downstream will notice",
                    )
                )
            else:
                findings.append(
                    _finding(
                        "learnings-entry-shape",
                        path,
                        line_num,
                        "narrative body added to learnings.md — this file is the "
                        "rule index; the body belongs in learnings-detail.md "
                        "under the same heading (a move, never a deletion)",
                    )
                )
    return findings


def _read_text(path: Path) -> "str | None":
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _scope_declared_in_change_log(prawduct_dir: Path, scope: "str | None") -> bool:
    """Does any change-log entry declare ``scope``?

    This is the discriminator between the two shapes that both reach
    "the dispatch names a scope no build plan declares":

    - a **typo'd or stale** scope, which names nothing anywhere. Grading must
      not proceed and must not go quiet — a deliverable check that silently
      skipped is indistinguishable from one that passed, which is the whole
      reason the `unchecked` prefix blocks.
    - a **real, deliberately plan-less** scope — the ordinary shape of a
      framework-only fix, which prawduct's own methodology says needs no build
      plan (`building.md`: small = build + verify, no plan). There is no
      deliverable set to grade, no `--chunk` that could supply one, and no edit
      to the diff that clears it. Blocking that is a false blocker with no
      remedy, and the only exits left to a builder are inventing a retroactive
      plan or departing from the rule silently. Three consecutive reviews took
      the second.

    The change-log is the witness because a code-changing branch cannot open a
    PR without ADDING an entry (`check-change-log-entry`, enforced at the PR
    boundary), and the `scope=` tag on that entry is what the release flow
    reads to enumerate what is still unshipped. So the declaration already
    exists by the time any review runs, and it lives in a durable, reviewed,
    release-tracked record.

    Be precise about the strength of that: the PR probe requires the entry, not
    the tag, so a builder who writes `scope=` is still declaring something
    rather than having it forced out of them. What this buys over the
    alternatives — a `--scope-has-no-plan` dispatch flag, or an allowlist key —
    is not unforgeability, it is that the declaration is durable, is read by
    the release flow for an unrelated purpose, and is visible in the diff a
    reviewer reads. A transient flag on one dispatch is none of those. A typo'd
    scope, meanwhile, is declared nowhere by construction, which is the case
    this branch actually has to separate.
    """
    if not scope or not scope.strip():
        return False
    text = _read_text(prawduct_dir / "change-log.md")
    if text is None:
        return False  # unreadable witness proves nothing — keep the block
    from . import change_log  # noqa: PLC0415 — lazy; mirrors the module's import posture

    try:
        entries = change_log.parse_change_log(text)
    except Exception:  # prawduct:allow prawduct/broad-except -- a malformed change-log must not decide severity; fail closed to the blocking read
        return False
    return any(e.tags.get("scope") == scope.strip() for e in entries)


def _norm_field_re():
    """What a norm entry IS, imported from its one home in ``norm_probes``:
    ``(field marker, blockquote prefix)``.

    #568 was two definitions of a norm entry disagreeing; closing it with a
    second *copy* of the marker would have re-created the same defect in a
    slower-acting form — the copies agree today and drift on the first edit
    (`architecture.md` § Direction: every fact has one home). Imported lazily
    because ``norm_probes`` pulls the advisory-store and backlog readers, and
    this module's top level is on the record-lint path.

    **The blockquote prefix is part of the definition, not a detail of the other
    module's parsing.** Importing only the marker is what let the two drift when
    blockquote tolerance landed: ``norm_probes`` strips ``>`` inside
    ``_direction_lines`` before matching, this module walks raw text, and the
    identical regex then answered differently on identical input. Sharing both
    halves is what makes "cannot drift apart on an edit" true rather than
    merely intended.
    """
    from .norm_probes import (  # noqa: PLC0415 — lazy; heavy deps
        _BLOCKQUOTE_PREFIX_RE,
        _FIELD_MARKER_RE,
    )

    return _FIELD_MARKER_RE, _BLOCKQUOTE_PREFIX_RE


def direction_norm_count(text: str) -> "int | None":
    """Number of norm entries in a document's ``## Direction`` section, or
    ``None`` when it has no such section.

    A norm is a top-level list bullet **that carries a norm FIELD** — the same
    definition :func:`lib.norm_probes._has_direction_entry` uses, and the one
    ``docs/norms.md`` § Anatomy states ("a norm captured without its why is
    unenforceable at the edges and immortal at the center"; ``Why`` is required,
    ``Status`` optional). The section opens at a heading whose text is exactly
    ``Direction`` and closes at the next heading of equal-or-higher level, so
    prose that merely mentions ``## Direction`` never opens one.

    **Counting bare bullets was a second, incompatible definition of the same
    thing.** The two disagreed exactly in the roadmap case — a ``## Direction``
    section holding a prioritised list of undone work — where the probes
    correctly saw no norms and this counted one per bullet, so the
    ``governed_by`` under-disposition lint demanded dispositions for items that
    are not norms. One fact, one home: the marker is imported from
    :mod:`lib.norm_probes` rather than restated here, so a norm entry is a
    field-bearing entry everywhere and the two cannot drift apart on an edit.
    """
    field_re, blockquote_re = _norm_field_re()
    in_section = False
    section_level = 0
    count: "int | None" = None
    pending_bullet = False
    for raw in text.splitlines():
        # Strip blockquote markers exactly as `norm_probes._direction_lines`
        # does. Sharing the field REGEX is not enough to share the DEFINITION:
        # that function feeds the probes de-quoted lines, while this walks the
        # raw text, so a `> **Why:** ...` registry counted N entries there and 0
        # here — #568 reopening in the blockquote case, silently skipping the
        # `governed_by` lint for exactly the products the strip was added for.
        line = blockquote_re.sub("", raw)
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            if heading.group(2).strip() == "Direction":
                in_section, section_level = True, level
                count = 0 if count is None else count
            elif in_section and level <= section_level:
                in_section = False
            pending_bullet = False
            continue
        if not in_section:
            continue
        if re.match(r"^[-*]\s+\S", line):
            # A new top-level bullet: whatever the previous one was, it is
            # settled — it counted when its Why arrived, or never.
            pending_bullet = True
            continue
        if pending_bullet and field_re.match(line):
            count = (count or 0) + 1
            pending_bullet = False
    return count


def _parse_governed_by(text: str) -> list[dict]:
    """``[{"artifact", "dispositions", "line"}]`` from a plan's frontmatter.

    Line-based: this codebase carries no YAML dependency, and the block's shape
    is fixed by the build-plan template. A disposition is a list item nested
    under ``dispositions:``; a soft-wrapped continuation does not start with
    ``- `` and so is not miscounted.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return []
    entries: list[dict] = []
    in_block = False
    entry_indent = -1
    disp_indent = -1
    for idx, line in enumerate(lines[1:], start=2):
        if line.strip() == _FRONTMATTER_FENCE:
            break
        if not in_block:
            if _GOVERNED_BY_RE.match(line):
                in_block = True
            continue
        if _TOP_LEVEL_KEY_RE.match(line):
            break  # a new top-level key closes the block
        artifact = _ARTIFACT_ENTRY_RE.match(line)
        if artifact:
            entry_indent = len(artifact.group(1))
            disp_indent = -1
            entries.append(
                {"artifact": artifact.group(2), "dispositions": 0, "line": idx}
            )
            continue
        if not entries:
            continue
        key = _DISPOSITIONS_KEY_RE.match(line)
        if key and len(key.group(1)) > entry_indent:
            disp_indent = len(key.group(1))
            continue
        item = _LIST_ITEM_RE.match(line)
        if item and disp_indent >= 0 and len(item.group(1)) > disp_indent:
            entries[-1]["dispositions"] += 1
    return entries


def _resolve_artifact(project_dir: Path, prawduct_dir: Path, name: str) -> "Path | None":
    """Locate the artifact a ``governed_by:`` entry names, or ``None``.

    ``.prawduct/artifacts/<name>.md`` is the canonical home and is tried first.
    It is not the only one: this repo keeps several governing artifacts under
    ``documentation/``, and a product may put them anywhere it likes. Rather
    than hardcode a second directory — which would be a guess about layout, the
    thing ``buildplan_refs._ref_root`` is explicit about never doing — fall back
    to asking git for a tracked file with that basename. One extra call, only on
    the non-canonical path, and it is layout- and language-neutral.
    """
    canonical = prawduct_dir / "artifacts" / f"{name}.md"
    if canonical.is_file():
        return canonical
    rc, out, _err = evidence.run_git(
        project_dir, "ls-files", "--", f"{name}.md", f"*/{name}.md"
    )
    if rc != 0:
        return None
    for line in out.splitlines():
        candidate = project_dir / line.strip()
        if line.strip() and candidate.is_file():
            return candidate
    return None


def _check_governed_by(
    project_dir: Path, prawduct_dir: Path, plan_rel: str, text: str
) -> list[dict]:
    """A plan's ``governed_by:`` block against each cited artifact's actual
    ``## Direction`` norm count — the GOV-8C3W mechanical enumeration.

    Fires only on **under**-disposition. Disposing of more entries than the
    artifact has norms is legitimate (a plan may split a norm's limbs); leaving
    a norm unaddressed is the defect, and "inapplicable, because —" is a
    perfectly good disposition, so there is never a reason to be short.

    A ``governed_by:`` entry naming an artifact that does not exist is reported
    here rather than treated as somebody else's problem: the name is a bare
    token, not a backticked path, so nothing that scans for path-shaped text
    would ever see it — and a plan claiming governance by a file nobody can read
    is the worse defect, because it reads as *more* governed than an omission.
    """
    findings: list[dict] = []
    for entry in _parse_governed_by(text):
        artifact = entry["artifact"]
        resolved = _resolve_artifact(project_dir, prawduct_dir, artifact)
        artifact_text = _read_text(resolved) if resolved is not None else None
        if artifact_text is None:
            findings.append(
                _finding(
                    "governed-by-gap",
                    plan_rel,
                    entry["line"],
                    f"`governed_by:` cites {artifact!r}, but no readable "
                    f"{artifact}.md exists in the repo — the plan claims "
                    "governance by a file no reader can check",
                )
            )
            continue
        norms = direction_norm_count(artifact_text)
        if not norms:
            continue  # no ratified norms to dispose of
        if entry["dispositions"] < norms:
            findings.append(
                _finding(
                    "governed-by-gap",
                    plan_rel,
                    entry["line"],
                    f"{artifact} carries {norms} `## Direction` norm(s) but this "
                    f"plan disposes of {entry['dispositions']} — each norm needs a "
                    "recorded disposition, and \"inapplicable, because —\" is one",
                )
            )
    return findings


def _check_chunk_refs(
    project_dir: Path,
    prawduct_dir: Path,
    chunk_id: "str | None",
    scope: "str | None" = None,
) -> "tuple[list[dict], str | None, str | None, str | None]":
    """The reviewed chunk's declared deliverables, existence-checked.

    Delegates wholly to ``buildplan_refs`` — the same parse and the same
    resolution ``verify-chunk-refs`` performs, computed here so it rides the
    manifest instead of being an instruction a reviewer executes. A plan or
    chunk section that cannot be located is the ``cannot-verify:`` case and
    returns an ``unchecked`` reason, never an empty pass.

    Unlike the suite-total tripwire this runs whether or not the plan changed:
    a chunk's deliverables must exist by the time its review runs, whether or
    not the plan file moved in the same diff.

    **Whose chunk.** ``chunk_id`` comes from the dispatch manifest. Falling back
    to the build plan's Status is a last resort and is *reported as an
    assumption*, because Status resolves "current" to the first unchecked box —
    so the instant a chunk is marked ``[x]``, "current" is the next, unbuilt
    chunk, and grading it produces a confident answer about the wrong subject.

    **Whose plan.** ``scope`` comes from the same manifest and selects the plan,
    via :func:`buildplan_refs.resolve_reviewed_plan`. Without it the plan came
    from ``active_build_plan`` while the chunk came from the dispatch, and
    nothing checked the two agreed: a review of one branch's chunk 03 graded a
    different plan's chunk 03 and reported zero missing deliverables over a diff
    that cited a path no longer present. A scope naming no plan is the
    unchecked case — falling back to the pointer there is that same silent grade.

    Returns ``(findings, gap, chunk_graded, plan_graded)``. The last two name the
    subject, so a zero count reads as an answer about a named chunk of a named
    plan rather than an answer about nothing.
    """
    plan = buildplan_refs.resolve_reviewed_plan(project_dir, prawduct_dir, scope)
    if plan.path is None and plan.gap:
        if _scope_declared_in_change_log(prawduct_dir, scope):
            return [], (
                f"chunk-ref-missing no-subject — {plan.gap}; the change-log "
                f"declares scope {scope!r}, so the scope is real and carries no "
                "plan — there is no declared deliverable set to grade"
            ), None, None
        return [], f"chunk-ref-missing unchecked — {plan.gap}", None, None

    assumed = False
    if chunk_id is None:
        chunk_id = buildplan_refs._current_chunk_id_from_status(project_dir, plan.path)
        assumed = chunk_id is not None
    if chunk_id is None:
        # "No chunk in scope" has two causes that look identical here and are
        # not alike. A plan whose chunks are all ticked genuinely has nothing to
        # grade, and silence is right. A plan exposing no `### Chunk NN:`
        # heading has nothing to grade EITHER — but because no chunk section can
        # be located at all, which disables this check for the plan's whole life
        # while reporting a null count that reads exactly like the healthy case.
        # That is the wholly-silent route: unlike the other failures here it
        # emits no `unchecked` line, so nothing downstream has a word to carry.
        # Both conditions, and the second is what keeps a FINISHED plan quiet.
        # "No current chunk" is also what a plan whose boxes are all ticked
        # reports, and that is a healthy end state — grading is over, not
        # disabled. A Status roster is the evidence that chunks were locatable
        # at all, so only a plan with neither a roster NOR a heading is
        # structurally ungradeable rather than simply done.
        total, _complete = buildplan_refs._count_build_plan_chunks(
            prawduct_dir, plan.path
        )
        if total == 0 and buildplan_refs.plan_has_parseable_chunk_heading(
            plan.path
        ) is False:
            return [], (
                f"chunk-ref-missing unchecked — {plan.rel} exposes no parseable "
                "chunk heading (`### Chunk NN: Name`), so no chunk section can "
                "be located and the deliverable check graded nothing. List items "
                "under a `## Chunks` section match no heading pattern"
            ), None, None
        return [], None, None, None  # no chunk in scope — nothing declared to check
    refs = buildplan_refs._parse_build_plan_chunk_refs(
        prawduct_dir, chunk_id, plan.path
    )
    if refs["error"]:
        # Name the plan. "chunk '03' not found in build-plan" is the same
        # sentence whether the chunk is missing or the wrong file was opened,
        # and those are very different problems for whoever reads it.
        return [], (
            f"chunk-ref-missing unchecked — {refs['error']} ({plan.rel}); chunk "
            f"{chunk_id}'s deliverable check did not run"
        ), None, None
    missing = buildplan_refs._verify_chunk_refs(project_dir, refs)
    findings = [
        _finding(
            "chunk-ref-missing",
            f"chunk {chunk_id}",
            entry.get("line_num"),
            f"declared deliverable `{entry['ref']}` {entry['reason']}",
        )
        for entry in missing
    ]
    # An assumption about EITHER half — which chunk, or which plan — reads the
    # same way to the reviewer and carries the same severity, so they share one
    # line rather than emitting two the reader has to join up.
    assumptions = []
    if assumed:
        assumptions.append(
            f"chunk {chunk_id} was inferred from build-plan Status because the "
            "dispatch carried no chunk — Status names the first UNCHECKED chunk, "
            "so this may be the next chunk rather than the reviewed one"
        )
    if plan.source == buildplan_refs.SOURCE_ACTIVE_PLAN and plan.gap:
        assumptions.append(plan.gap)
    gap = None
    if assumptions:
        gap = (
            f"chunk-ref-missing graded chunk {chunk_id} of {plan.rel}: "
            + "; ".join(assumptions)
        )
    return findings, gap, chunk_id, plan.rel


# ---------------------------------------------------------------------------
# The learnings budget — over AND grown blocks the next addition
# ---------------------------------------------------------------------------


#: Default ceiling for one learnings rules file, in KB. Every session pays for
#: ``core.md`` at launch and for an area file the moment a matching path is read,
#: so the cost of a rule is paid by every session that follows it, forever. The
#: number is a *curation* trigger, not a storage limit: the two prior compactions
#: (2026-06-10, 2026-07-17) were one-time subtractions against a continuous
#: addition, and the file regrew past its starting size both times. A ceiling
#: that fires per addition is the standing form of the same sweep.
_LEARNINGS_BUDGET_DEFAULT_KB = 16

#: ``project-state.yaml`` key holding a per-file override, ``{kb, reason}``.
_LEARNINGS_BUDGETS_KEY = "learnings_budgets"

#: The two findings the budget check emits. Named as a pair because a budget
#: declaration this reader cannot parse compromises both of them at once — the
#: ceiling it states and the reason it gives for it.
_BUDGET_CHECKS = ("learnings-over-budget", "learnings-budget-unreasoned")

#: The repo-relative record the override lives in — named in every finding, so a
#: reader is told where to go rather than which knob abstractly exists.
_STATE_REL = ".prawduct/project-state.yaml"


def _split_unquoted(text: str, separators: str) -> list[str]:
    """Split ``text`` on any character in ``separators``, ignoring quoted runs.

    A budget's ``reason`` is prose: it holds commas and it may hold a ``#``, and
    both are the separators this file's other readers split on. Splitting inside
    the quotes truncates the operator's stated reason and then reports the
    truncation as "no reason given" — a BLOCKING finding manufactured out of
    punctuation. Quote-awareness is the whole reason this does not reuse
    ``core.read_yaml_block``'s comment stripping.
    """
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in text:
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            current.append(char)
            continue
        if char in separators:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def _budget_block(text: str) -> "list[str] | None":
    """The raw indented lines under the column-0 ``learnings_budgets:`` key.

    Indentation is *preserved*, unlike ``core.read_yaml_block``, because this
    block is the one nested mapping the governance state carries and the nesting
    is what tells an entry name from its fields. ``None`` means the key is
    absent, which is the ordinary case and not a defect.
    """
    lines = text.splitlines()
    needle = f"{_LEARNINGS_BUDGETS_KEY}:"
    for index, raw in enumerate(lines):
        if raw[:1] in (" ", "\t"):
            continue
        if not raw.split("#", 1)[0].rstrip().startswith(needle):
            continue
        body: list[str] = []
        for follow in lines[index + 1:]:
            if not _split_unquoted(follow, "#")[0].strip():
                continue  # blank or comment-only — inert at any indent
            if follow[:1] not in (" ", "\t"):
                break  # the next column-0 key ends the block
            body.append(_split_unquoted(follow, "#")[0].rstrip())
        return body
    return None


def _parse_budget_fields(pairs: "list[str]", entry: dict) -> bool:
    """Fold ``k: v`` strings into ``entry``. False on anything unrecognised."""
    for pair in pairs:
        if not pair.strip():
            continue
        key, sep, value = pair.partition(":")
        key = key.strip().strip("\"'")
        if not sep or key not in ("kb", "reason"):
            return False
        if key == "kb":
            try:
                entry["kb"] = int(_unquote(value))
            except ValueError:
                return False
        else:
            entry["reason"] = _unquote(value)
    return True


def parse_learnings_budgets(text: str) -> "tuple[dict[str, dict], list[str]]":
    """``learnings_budgets:`` as ``({name: {kb, reason}}, malformed_names)``.

    Both the block form and the flow form the template documents::

        learnings_budgets:
          core.md: {kb: 24, reason: "the fleet's rules, and the sweep is done"}
          critic.md:
            kb: 20
            reason: "…"

    An entry this reader cannot parse lands in ``malformed`` and NOT in the
    budgets: a half-read declaration silently applies the 16KB default while the
    operator believes their override is in force, and the difference surfaces as
    a blocking finding they cannot explain. The caller reports it ``unchecked``,
    which is this module's standing answer for "did not run" (never a pass).
    """
    body = _budget_block(text)
    if not body:
        return {}, []
    indents = [len(line) - len(line.lstrip()) for line in body]
    top = min(indents)
    budgets: dict[str, dict] = {}
    malformed: list[str] = []
    current: "str | None" = None
    for line, indent in zip(body, indents):
        key, sep, value = line.strip().partition(":")
        name = _unquote(key)
        if indent == top:
            current = None
            if not sep or not name:
                malformed.append(line.strip())
                continue
            entry: dict = {"kb": None, "reason": None}
            value = value.strip()
            if value.startswith("{") and value.endswith("}"):
                if not _parse_budget_fields(
                    _split_unquoted(value[1:-1], ","), entry
                ):
                    malformed.append(name)
                    continue
            elif value:
                malformed.append(name)  # a scalar where a mapping belongs
                continue
            budgets[name] = entry
            current = name
        elif current is None:
            malformed.append(line.strip())
        elif not _parse_budget_fields([line.strip()], budgets[current]):
            malformed.append(current)
            budgets.pop(current, None)
            current = None
    return budgets, malformed


def _base_size(project_dir: Path, base_tree: str, rel: str) -> "int | None":
    """Bytes this path held in ``base_tree``; 0 when it was not there.

    Absent-at-base counts as **grown** — a file that did not exist before is all
    addition, and exempting the first commit of an area file would let a repo
    ship a 40KB one and then be told it may never touch it again.

    ``None`` means git answered in a shape this cannot read, which the caller
    reports ``unchecked``. The base tree itself is validated by the caller, so a
    nonzero exit here is genuinely "no such object in that tree".
    """
    rc, out, _err = evidence.run_git(
        project_dir, "cat-file", "-s", f"{base_tree}:{rel}"
    )
    if rc != 0:
        return 0
    try:
        return int(out.strip())
    except ValueError:
        return None


def _check_learnings_budget(
    project_dir: Path, prawduct_dir: Path, base_tree: str
) -> "tuple[list[dict], list[str], set[str]]":
    """The curation gate: a rules file over budget **and grown this interval**.

    Returns ``(findings, unchecked, no_answer)``.

    **Over-and-grew, never over alone.** A repo arriving with a 40KB corpus is
    not asked to stop the world and compact it — that is a one-time sweep, and
    the two this project ran both regrew. What it is asked is to pay for the
    *next* addition, which is the moment the trade is live and the duplicate is
    in front of the author. So an over-budget file that shrank, or held still,
    passes: the direction of travel is the finding, not the size.

    **Legacy layouts are silent.** ``resolve`` reports no files for a repo that
    has not migrated, so nothing here fires — the unmigrated state is the
    migration directive's business (R4), and two controls naming the same state
    teach a reader to skip both.
    """
    findings: list[dict] = []
    unchecked: list[str] = []
    no_answer: set[str] = set()

    state_text = _read_text(prawduct_dir / "project-state.yaml") or ""
    budgets, malformed = parse_learnings_budgets(state_text)
    if malformed:
        unchecked.append(
            f"{_BUDGET_CHECKS[0]}, {_BUDGET_CHECKS[1]} unchecked — "
            f"`{_LEARNINGS_BUDGETS_KEY}` in {_STATE_REL} declares "
            + ", ".join(repr(name) for name in malformed)
            + " in a shape this reader does not parse; the declared budget was "
            "NOT applied and the default stands"
        )
        no_answer.update(_BUDGET_CHECKS)

    for name in sorted(budgets):
        if not budgets[name].get("reason"):
            findings.append(
                _finding(
                    "learnings-budget-unreasoned",
                    _STATE_REL,
                    None,
                    f"`{_LEARNINGS_BUDGETS_KEY}.{name}` raises a budget with no "
                    "`reason:` — an unreasoned ceiling only ever rises, and the "
                    "next author reads a number with no argument behind it. Say "
                    "what this file earns the extra room for",
                )
            )

    layout = learnings_files.resolve(project_dir)
    if not layout.files:
        return findings, unchecked, no_answer

    rc, _out, err = evidence.run_git(
        project_dir, "rev-parse", "--verify", "--quiet", f"{base_tree}^{{tree}}"
    )
    if rc != 0:
        # Validate the tree ONCE rather than reading a per-file failure as
        # "absent at base". An unresolvable base tree makes every file look new,
        # and every rules file would be reported grown-from-nothing — a wall of
        # blocking findings caused by the interval, not by the corpus.
        unchecked.append(
            f"{_BUDGET_CHECKS[0]} unchecked — git could not resolve the base "
            f"tree {base_tree[:12]} ({err.strip() or 'no such tree'}); a growth "
            "comparison needs both sides"
        )
        no_answer.add(_BUDGET_CHECKS[0])
        return findings, unchecked, no_answer

    for path in layout.files:
        try:
            rel = path.relative_to(project_dir).as_posix()
            now = path.stat().st_size
        except (ValueError, OSError) as exc:
            unchecked.append(
                f"{_BUDGET_CHECKS[0]} unchecked on {path.name} — "
                f"{type(exc).__name__}: {exc}"
            )
            no_answer.add(_BUDGET_CHECKS[0])
            continue
        base = _base_size(project_dir, base_tree, rel)
        if base is None:
            unchecked.append(
                f"{_BUDGET_CHECKS[0]} unchecked on {rel} — git reported an "
                "unreadable size for the base revision of this file"
            )
            no_answer.add(_BUDGET_CHECKS[0])
            continue
        declared = budgets.get(path.name, {}).get("kb")
        kb = declared if isinstance(declared, int) and declared > 0 else (
            _LEARNINGS_BUDGET_DEFAULT_KB
        )
        budget = kb * 1024
        if now > budget and now > base:
            findings.append(
                _finding(
                    "learnings-over-budget",
                    rel,
                    None,
                    f"{now}B, over its {budget}B budget and grown from {base}B "
                    "at the base tree — pay from genuine duplication (merge or "
                    f"delete in this commit), or raise `{_LEARNINGS_BUDGETS_KEY}"
                    f".{path.name}` in project-state.yaml with a reason — never "
                    "trim a rule to fit",
                )
            )
    return findings, unchecked, no_answer


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def lint_records(
    project_dir: Path,
    prawduct_dir: Path,
    paths: "list[str] | None",
    base_tree: str,
    head_tree: str,
    chunk_id: "str | None" = None,
    scope: "str | None" = None,
) -> dict:
    """Run every check over the record subset of ``paths``.

    Returns ``{"records", "chunk_graded", "plan_graded", "findings",
    "unchecked", "counts"}``. ``findings`` is advisory — it never gates.
    ``unchecked`` names each check that could not run and why, so an unrun check
    is never mistaken for a clean one; ``chunk_graded`` and ``plan_graded`` name
    whose deliverables were checked, so a zero count is never mistaken for an
    answer about a different chunk or a different plan.

    ``chunk_id`` should be the reviewed chunk from the dispatch manifest. It is
    NOT inferred by default, because the build-plan Status resolves "current" to
    the first *unchecked* box — which, the moment a chunk is marked ``[x]``, is
    the NEXT chunk. A review of chunk 02 was silently graded against chunk 03's
    unbuilt deliverables exactly that way.

    ``scope`` is the other half of the same manifest and selects the PLAN — see
    :func:`_check_chunk_refs`. The two used to come from different places with
    nothing checking they agreed.
    """
    records = records_in(paths)
    findings: list[dict] = []
    unchecked: list[str] = []
    # Checks that produced no answer. Their counter is `None`, never `0` — a
    # tally gets quoted far more often than the caveat beside it, so the number
    # has to carry the distinction rather than the prose next to it.
    no_answer: set[str] = set()

    # Chunk deliverables are checked whether or not a RECORD changed — a
    # code-only diff still has a reviewed chunk whose declared outputs must
    # exist by review time.
    chunk_findings, chunk_gap, chunk_graded, plan_graded = _check_chunk_refs(
        project_dir, prawduct_dir, chunk_id, scope
    )
    findings.extend(chunk_findings)
    if chunk_gap:
        unchecked.append(chunk_gap)
    if chunk_graded is None:
        # Agrees with `chunk_graded` by construction: `review-cycle.md` already
        # reads a null subject as "nothing was checked at all", and the counter
        # said 0 in the same breath.
        no_answer.add("chunk-ref-missing")

    added_by_path: dict = {}
    if records:
        diffed = _added_lines(project_dir, base_tree, head_tree, records)
        if diffed is None:
            unchecked.append(
                "suite-total-claim, learnings-entry-shape unchecked — git could "
                f"not read the diff {base_tree[:12]}..{head_tree[:12]} over the "
                "changed records"
            )
            no_answer.update({"suite-total-claim", "learnings-entry-shape"})
        else:
            added_by_path = diffed
    for rel in records:
        added = added_by_path.get(rel)
        if added:
            findings.extend(_check_suite_totals(rel, added))
            # The rule index is the ROOT record only. A `learnings.md` nested
            # elsewhere (a migration fixture under tests/, a vendored product
            # sample) is data, not this repo's index, and grading its shape
            # reports thirty findings about a file nobody maintains as an index.
            if Path(rel).name == _LEARNINGS_REL and Path(rel).parent == Path(".prawduct"):
                findings.extend(
                    _check_learnings_shape(
                        rel, added, _read_text(project_dir / rel)
                    )
                )

    for rel in _plans_to_check(prawduct_dir, records):
        text = _read_text(project_dir / rel)
        if text is None:
            unchecked.append(f"governed-by-gap unchecked on {rel} — unreadable")
            no_answer.add("governed-by-gap")
            continue
        findings.extend(_check_governed_by(project_dir, prawduct_dir, rel, text))

    # Not record-scoped: the rules corpus grows on a commit that changed nothing
    # else, and the budget is about the file's size rather than its added lines.
    budget_findings, budget_gaps, budget_no_answer = _check_learnings_budget(
        project_dir, prawduct_dir, base_tree
    )
    findings.extend(budget_findings)
    unchecked.extend(budget_gaps)
    no_answer.update(budget_no_answer)

    return {
        "records": records,
        "chunk_graded": chunk_graded,
        "plan_graded": plan_graded,
        "findings": findings,
        "unchecked": unchecked,
        "counts": _count(findings, no_answer),
    }


def lint_records_safe(
    project_dir: Path,
    prawduct_dir: Path,
    paths: "list[str] | None",
    base_tree: str,
    head_tree: str,
    chunk_id: "str | None" = None,
    scope: "str | None" = None,
) -> dict:
    """:func:`lint_records`, but a crash degrades to a reported ``unchecked``
    instead of taking the caller down with it.

    **This is the only form the review-dispatch path may call.** Record-lint is
    *advice*, and `architecture.md` § Direction says advice fails soft — but
    ``critic-begin`` had no handler between this module and ``main()``, so a
    single unreadable byte in one changed ``.md`` would abort every review
    dispatch in every consuming repo with a raw traceback. That inverts two
    recorded dispositions at once (advice fails soft; errors are attributed,
    never stack traces across the boundary), and it fails in the worst
    direction: an advisory check taking out the authority path it advises.

    The failure is *reported*, never swallowed — the reason lands in
    ``unchecked``, which is the same "this did not run" channel every other
    non-answer uses.
    """
    try:
        return lint_records(
            project_dir, prawduct_dir, paths, base_tree, head_tree, chunk_id, scope
        )
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- advice must never abort review dispatch; reported as unchecked, never swallowed
        return {
            "records": records_in(paths),
            # NOT `chunk_id`: nothing was graded, and the contract says a null
            # `chunk_graded` means exactly that. Echoing the requested chunk here
            # would pair a named subject with zero counts — the shape a clean
            # result has.
            "chunk_graded": None,
            "plan_graded": None,
            "findings": [],
            # The `chunk-ref-missing unchecked` prefix is load-bearing:
            # `review-cycle.md` grades that string BLOCKING, inheriting the
            # retired `cannot-verify:` bar. A crash takes the deliverable check
            # down with everything else, so it must reach the reviewer at the
            # deliverable check's severity — not as a generic NOTE, which is the
            # BLD-5J8N habituation arriving by a new route.
            "unchecked": [
                f"chunk-ref-missing unchecked — record-lint did not run at all "
                f"({type(exc).__name__}: {exc}). The review proceeds; NO record "
                "check was performed, including the deliverable check."
            ],
            # Nothing ran, so nothing counted. Zeros here would be the crash
            # reporting itself in the shape of a clean check.
            "counts": _count([], set(CHECKS)),
        }


def _count(findings: list[dict], no_answer: "set[str] | None" = None) -> dict:
    """Per-check tallies with every check present, so a zero is visibly a zero
    rather than a missing key a consumer has to interpret.

    A check in ``no_answer`` counts ``None``, not ``0``: it produced no answer,
    and the two are different facts that a bare integer cannot tell apart. Every
    consumer that renders these must read ``None`` as "did not run" — a
    ``0``-vs-``None`` slip reads as clean, which is the direction that loses
    governance.

    **``no_answer`` wins over findings, including a PARTIAL run.** A check can be
    both skipped and productive — ``governed-by-gap`` is added to ``no_answer``
    per unreadable plan while other, readable plans still contribute findings —
    and reporting the partial tally as a bare integer says "this check ran and
    found N", which is the whole confusion ``None`` exists to remove. Nothing is
    lost: every finding stays in ``findings`` and prints, and the ``unchecked``
    reason names what was skipped. Only the *tally* withholds, because a count
    over some of the inputs is not a count.
    """
    skipped = no_answer or set()
    counts: dict = {check: (None if check in skipped else 0) for check in CHECKS}
    for finding in findings:
        check = finding["check"]
        if check in skipped:
            continue
        counts[check] = (counts.get(check) or 0) + 1
    return counts


def _plans_to_check(prawduct_dir: Path, records: list[str]) -> list[str]:
    """Which build plans get the ``governed_by:`` enumeration this run.

    Every changed plan, plus — when a *governing artifact* changed — the active
    plan, because adding a norm to an artifact silently shortens the
    disposition block of a plan that did not itself change. That is the GOV-8C3W
    class rather than its instance, and it costs one extra file read.
    """
    plans = [rel for rel in records if _BUILD_PLAN_RE.search(rel)]
    governing_changed = any(
        rel.startswith(".prawduct/artifacts/") and not _BUILD_PLAN_RE.search(rel)
        for rel in records
    )
    if governing_changed:
        active = resolve_build_plan_path(prawduct_dir)
        try:
            rel_active = str(active.relative_to(prawduct_dir.parent))
        except ValueError:
            rel_active = ""
        if rel_active and active.is_file() and rel_active not in plans:
            plans.append(rel_active)
    return plans


def format_findings(result: dict) -> list[str]:
    """Human-readable lines for the CLI and the manifest's reader. One line per
    finding, then one per unchecked reason — an unrun check is reported, never
    silently absent."""
    out: list[str] = []
    for finding in result.get("findings") or []:
        where = finding["path"]
        if finding.get("line"):
            where = f"{where}:{finding['line']}"
        out.append(f"{finding['check']}: {where}: {finding['detail']}")
    for reason in result.get("unchecked") or []:
        out.append(f"unchecked: {reason}")
    return out
