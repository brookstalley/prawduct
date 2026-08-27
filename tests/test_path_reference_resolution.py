"""Intra-repo path references must RESOLVE — the complement to pinning where files may live.

``test_plugin_packaging.py`` pins *location*: which files are allowed to exist where, and which
reach a consumer's plugin cache. It is blind to a reference pointing at a path that no longer
exists. The ``plugin/`` relocation shipped ``bin/prawduct-hook`` in five skills' instruction prose
**and in their ``allowed-tools:`` permission grants**, with the full suite green throughout, because
no test executes skill front-matter. The documented command could not run and the grant did not
cover the one that would.

That is the third recurrence of *relocating a source file: sweep every READER of the old path*,
which is what promotes the rule to a mechanism.

**Extraction is by reference FORM, and that is the whole design.** The naive extractor — every
backticked path token — cannot distinguish a path a reader is told to *use* from one the prose is
*talking about*. Measured across this repo's artifacts it produced two orders of magnitude more
"failures", nearly all of them in completed build plans that correctly describe the pre-``plugin/``
tree layout, and it flagged the very build plan that specified this test (which quotes broken paths
as examples of the problem). An allowlist absorbing that is longer than the check's catch, and
``docs/norms.md`` warns that a probe which misfires trains its reader to ignore the one real catch.
(The census figures have one home: the ``2026-08-02`` change-log entry for this work. They are a
historical measurement, not a live quantity, and restating them here would be a third copy of a
number — the defect class this batch exists to remove.)

``test_no_shipped_file_points_at_an_unshipped_plugin_root_path`` named the fix: it keys on
``${CLAUDE_PLUGIN_ROOT}/…``, a form that unambiguously means *go read this*. The same idea gives
three high-signal forms, in the sweep order of how silently each fails:

1. ``allowed-tools:`` front-matter grants — a grant naming a path that does not exist is a
   permission that cannot cover the command it was written for. Fails most silently of all: nothing
   executes front-matter.
2. **Command position** — a backticked span whose first token is an executable. The path is an
   argument to something a reader will run.
3. **Markdown links** — ``[text](path)``. An unambiguous pointer.

A bare backticked path inside a sentence is a *citation* and is deliberately not extracted.

Relative targets resolve against the **containing file**, not the repo root. Getting that wrong
over-reported twenty non-defects during the census.

**The record exemption is container-scoped; its rationale is role-scoped, and the two do not
line up.** ``_is_record`` exempts whole files, but the reason it gives — *narrates defects, quoting
the paths they occurred at* — is a claim about a reference's role. It holds for
``learnings-detail.md``, which quotes stale invocations as evidence. It does not hold for every
reference inside ``learnings.md``: that file also carries live instructions (one rule tells the
reader to invoke ``python3 plugin/bin/prawduct-hook``, and ``/prawduct:learnings`` serves it as
current guidance), so a future relocation strands them with the suite green — the exact defect
class this test exists for. Scoping the exemption per reference rather than per file is not worth
building for one known instance; leaving the gap unnamed is what is not acceptable, since an
exemption nobody has examined reads as one somebody has.
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _tracked() -> list[str]:
    """Git-tracked paths. Asserted against tracked state so an untracked leftover cannot vouch
    for itself — the same reasoning as the packaging tests."""
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return out.split("\n") if out else []


_TRACKED = [p for p in _tracked() if p]
_TRACKED_SET = set(_TRACKED)
_TRACKED_DIRS = {
    "/".join(p.split("/")[:i]) for p in _TRACKED for i in range(1, len(p.split("/")))
}

# RECORDS vs INSTRUCTIONS — the distinction that keeps the allowlist from swallowing the check.
#
# A file whose job is to say *what happened* legitimately names the tree as it stood at the time:
# the change-log entry that ran ``tools/product-hook`` was correct when written, and rewriting it to
# satisfy a resolver falsifies the record. A file whose job is to *instruct* has no such licence —
# a reader follows it against today's tree.
#
# This is a predicate on the file's ROLE, not a list of awkward cases, which is why it does not
# grow: six historical plans naming the pre-v2 CLI cost zero entries.
_RECORD_FILES = frozenset(
    {
        ".prawduct/change-log.md",       # append-only: what changed, when
        ".prawduct/backlog.md",          # frozen by the GitHub Issues cutover
        ".prawduct/learnings.md",        # narrates defects, quoting the paths they occurred at
        ".prawduct/learnings-detail.md",
        ".prawduct/reflections.md",
        ".prawduct/operator-verification.md",
    }
)
_RECORD_PREFIXES = (".prawduct/archive/",)
# An archived build plan is a record of what was built, and its instructions were
# true when written — `tools/product-hook` really was the entry point before the
# plugin distribution. Grading one as a live instruction file demands editing
# history to keep a suite green, which is the opposite of what an archive is for.
#
# Matched as an `archive/` path COMPONENT rather than a fixed prefix, because a
# plan is archived *beside itself*: a repo organizing plans as
# `artifacts/plans/<id>/build-plan.md` archives to `artifacts/plans/<id>/archive/`,
# and a top-level-only rule would exempt the flat layout while grading the nested
# one. That is the same "any depth" rule the plan scanners prune on, and the two
# must agree or a plan can be invisible to one and live to the other.
_ARCHIVE_COMPONENT = re.compile(r"^\.prawduct/(?:.*/)?archive/")
# ``v1``/``v2``-named artifacts are the PRE-V3 plan convention, retired when plans became
# ``build-plan-<scope>.md``. The naming convention itself marks them as shipped-era, so no status
# lookup is needed.
#
# Deliberately NOT extended to ``release-plan-v3.*``: those are the *current* convention, the v3.2.3
# one is still pending, and skipping them would silently exempt live instruction files. An earlier
# cut of this pattern matched any version-shaped name and excluded all four v3.2.x release plans —
# contradicting the pre-v3 rationale written directly above it. Narrowing cost nothing: zero
# offenders either way, so the wider pattern bought no green and gave up real coverage.
_HISTORICAL_ARTIFACT = re.compile(r"^\.prawduct/(?:archive/)?artifacts/v[12]\d*[.-]")


def _is_record(rel: str) -> bool:
    return (
        rel in _RECORD_FILES
        or rel.startswith(_RECORD_PREFIXES)
        or bool(_ARCHIVE_COMPONENT.match(rel))
        or bool(_HISTORICAL_ARTIFACT.match(rel))
    )


# Named exceptions that are neither records nor fixable. Kept tiny and reasoned on purpose.
ALLOWLISTED_FILES = {
    "documentation/prompt-management-requirements.md": (
        "requirements doc describing a config file that does not exist yet — a forward reference to "
        "a planned surface, not a stale reference to a removed one"
    ),
}

# Executables whose arguments are paths a reader will actually run against this tree.
_COMMAND_HEAD = re.compile(
    r"^(?:\$\s+)?(?:python3?|prawduct-hook|pytest|bash|sh|cat|less|grep|rg|ls|chmod)\b"
)
_PATH_SHAPED = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+$")
_HAS_EXTENSION = re.compile(r"\.(?:py|md|sh|json|yaml|yml|toml|jsonl)$")

# Directory vocabulary of this repo's source tree, INCLUDING directories that no longer exist
# (``tools/``, ``agents/``, and a repo-root ``bin/``). Deliberately explicit rather than derived
# from the current tree: a derived set can only name directories that still exist, and the defect
# class this test was built for is a reference to one that was REMOVED. ``bin/prawduct-hook`` — the
# original five-skill breakage — is extensionless and lives under a root ``bin/`` that is now
# ``plugin/bin/``, so neither the extension rule nor a derived-directory rule would see it.
_SOURCE_DIR_SEGMENTS = frozenset(
    {
        "plugin", "bin", "lib", "tests", "docs", "skills", "methodology",
        "templates", "hooks", "documentation", "tools", "agents",
        ".prawduct", ".claude", ".claude-plugin",
    }
)


#: A skill reads the plugin through its own directory: `${CLAUDE_SKILL_DIR}` expands
#: at skill load, and the plugin root is one directory pair above it. That form
#: replaced `${CLAUDE_PLUGIN_ROOT}`, which does not expand in prose — and in doing so
#: the reads fell out of BOTH checks that could see them: the packaging test matches
#: the retired sigil, and `_PATH_SHAPED` rejects any token holding `$`, `{` or `}`.
#: Five cross-plugin reads were therefore checked by nothing, and could be stranded
#: by any relocation with the suite green — the third-recurrence class this file
#: exists to mechanize. Normalizing the prefix hands them to the resolver that
#: already owns path references, so present and future ones share one owner.
_SKILL_DIR_PREFIX = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/(?:\.\./)+")


def _normalize_skill_relative(token: str) -> str:
    """Rewrite a skill-dir-relative read as the repo path it names."""
    return _SKILL_DIR_PREFIX.sub("plugin/", token)


def _is_repo_path(token: str) -> bool:
    """Path-shaped and plausibly naming something in this tree.

    The extension branch catches ``tools/prawduct-sync.py``; the directory branch catches
    extensionless ``plugin/bin/prawduct-hook``. Together they exclude ``owner/repo`` arguments,
    which are path-shaped, appear in command position after ``--repo``, and name nothing on disk.
    """
    token = _normalize_skill_relative(token)
    if not _PATH_SHAPED.match(token):
        return False
    return bool(_HAS_EXTENSION.search(_strip_ref(token))) or (
        token.split("/", 1)[0] in _SOURCE_DIR_SEGMENTS
    )
_BACKTICKED = re.compile(r"`([^`\n]{3,300})`")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
# Forms that INVOKE a path rather than name it. The plugin/ root fallback is denied to these.
_INVOCATION_FORMS = frozenset({"command", "allowed-tools"})
_ALLOWED_TOOLS = re.compile(r"^allowed-tools:(.*)$", re.M)


def _strip_ref(raw: str) -> str:
    """Trim trailing prose punctuation, a line-number suffix, and an anchor."""
    ref = _normalize_skill_relative(raw).rstrip(".,;:)`").rstrip("/")
    ref = ref.split("#", 1)[0]
    ref = re.sub(r":\d+(?:[,-]\d+)*$", "", ref)  # foo.py:182 and foo.md:58-60
    return ref


def _resolves(containing: str, raw: str, form: str) -> bool:
    """True if ``raw``, referenced from ``containing``, names something in the tracked tree.

    Three roots are tried, and each earns its place:
    - the repo root, for ordinary repo-relative references;
    - the containing file's own directory, for ``./`` and ``../`` targets;
    - ``plugin/`` — but only for files entitled to it (see below).

    **The ``plugin/`` fallback is scoped by BOTH file and form, and the form half is what makes the
    motivating defect visible.** Applied everywhere, it resolves ``bin/prawduct-hook`` against
    ``plugin/bin/prawduct-hook`` and hides the exact relocation this test exists to catch.

    The fallback earns its place for **naming a file**: docs under ``plugin/`` refer to siblings the
    way the plugin ships them (``skills/critic/review-cycle.md``, ``methodology/building.md``,
    ``lib/backlog_probes.py`` — dozens of them), and build plans under ``.prawduct/artifacts/`` do
    the same under this repo's *declared* ``build_plan_ref_root: plugin``. A declared second root,
    not a sniffed one.

    It earns nothing for **running one**. A reader executing a command runs it from a working
    directory, and in this repo that means ``plugin/bin/prawduct-hook`` — which is what all fifteen
    invocations in the shipped plugin say. So the fallback is denied to the two invocation forms,
    ``command`` and ``allowed-tools``, and a skill reverting to a bare ``bin/prawduct-hook`` in
    either is caught.

    ``form`` has no default on purpose. It defaulted to ``md-link`` — the one form the ``plugin/``
    fallback is *granted* to — so an omitted argument silently bought the most permissive behaviour
    at exactly the call sites least likely to have thought about it.

    Scoping by file alone was not enough and shipped as if it were: the motivating breakage was in
    five *skills'* prose and grants, and skills live under ``plugin/`` — inside the retained scope.
    Two of the three covered forms, on the exact files, of the exact class, still resolved. The form
    half closes it.
    """
    ref = _strip_ref(raw)
    if not ref:
        return True
    candidates = []
    if ref.startswith(("./", "../")):
        candidates.append(posixpath.normpath(posixpath.join(posixpath.dirname(containing), ref)))
    else:
        candidates.append(ref.lstrip("/"))
        entitled = containing.startswith("plugin/") or containing.startswith(".prawduct/artifacts/")
        if entitled and form not in _INVOCATION_FORMS:
            candidates.append(f"plugin/{ref.lstrip('/')}")
    return any(c in _TRACKED_SET or c in _TRACKED_DIRS for c in candidates)


def _fenced_command_lines(text: str) -> list[str]:
    """Lines inside fenced blocks that begin with a known executable.

    #193 names *fenced and inline* commands; a shell block is command position just as much as an
    inline span, and it is where multi-line setup instructions live.
    """
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and _COMMAND_HEAD.match(line.strip()):
            lines.append(line.strip())
    return lines


def _strip_code(text: str) -> str:
    """Remove fenced blocks and inline code spans.

    A markdown link *inside backticks* is being quoted, not offered — this batch's own build plan
    quotes the broken ``[learnings file](../.prawduct/learnings.md)`` as evidence, and an extractor
    that follows it reddens on the document specifying it. Same citation-versus-reference rule as
    for bare paths, applied to the link form.
    """
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", " ", text)


def _references(rel: str, text: str) -> list[tuple[str, str]]:
    """Every instruction-bearing path reference in ``text``, as ``(form, raw_ref)``."""
    found: list[tuple[str, str]] = []

    fm = _FRONT_MATTER.match(text)
    if fm:
        for grant_line in _ALLOWED_TOOLS.findall(fm.group(1)):
            for token in re.findall(r"[A-Za-z0-9_./-]+", grant_line):
                # Same predicate as command position, and for the same reason ``_is_repo_path``
                # was written: ``owner/repo`` arguments are path-shaped and name nothing on disk.
                # Latent rather than live today — the only slash-bearing grant token in tracked
                # markdown is ``plugin/bin/prawduct-hook`` — but the moment a skill grants
                # ``Bash(gh issue list --repo owner/name *)`` the bare shape test reddens on a
                # non-defect, and the cheapest-looking fix is an allowlist entry spent on a bug
                # in this extractor.
                #
                # ``buildplan_refs._verify_chunk_refs`` answers the same shape the OPPOSITE way —
                # it reports the ambiguity and has the author disambiguate. Both are right on
                # their own blast radii: that check emits an advisory lint line a human reads,
                # while this one fails the suite outright, and a hard failure a reader cannot
                # disambiguate is one they silence with an allowlist entry.
                if _is_repo_path(token):
                    found.append(("allowed-tools", token))

    for span in list(_BACKTICKED.findall(text)) + _fenced_command_lines(text):
        span = span.strip()
        if not _COMMAND_HEAD.match(span):
            continue
        for token in span.split()[1:]:
            if _is_repo_path(token):
                found.append(("command", token))

    for target in _MD_LINK.findall(_strip_code(text)):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not _HAS_EXTENSION.search(target.split("#", 1)[0]):
            continue  # section links and bare anchors are not file references
        found.append(("md-link", target))

    return found


def _scan() -> tuple[list[str], list[tuple[str, str, str]]]:
    """Return (offenders, checked_references) across tracked markdown.

    ``checked`` deliberately excludes references skipped as records or allowlisted: it is the
    quantity the non-vacuity floor guards, and counting *extracted* references instead would let
    the check go fully dark — widen the record predicate far enough and every reference is skipped
    while the floor still sees them all.
    """
    offenders: list[str] = []
    checked: list[tuple[str, str, str]] = []
    for rel in _TRACKED:
        if not rel.endswith(".md"):
            continue
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if rel in ALLOWLISTED_FILES or _is_record(rel):
            continue
        for form, raw in _references(rel, text):
            checked.append((rel, form, raw))
            if not _resolves(rel, raw, form):
                offenders.append(f"{rel} [{form}] -> {raw}")
    return offenders, checked


def test_every_instruction_bearing_path_reference_resolves():
    """The check itself: no tracked markdown sends a reader to a path that is not there.

    Caught on its first run: ``plugin/docs/principles.md`` linked to ``../.prawduct/learnings.md``,
    which from ``plugin/docs/`` resolves to ``plugin/.prawduct/learnings.md`` — absent here and
    equally absent in a consumer's plugin cache, where the reader wants the *product's* learnings
    file. The same class the ``${CLAUDE_PLUGIN_ROOT}`` guard catches, in the one form it cannot see.
    """
    offenders, _ = _scan()
    assert not offenders, (
        "markdown references a path that does not resolve. Fix the reference, or — only if the "
        "file is historical or aspirational by construction — add the FILE to ALLOWLISTED_FILES "
        "with a reason:\n  " + "\n  ".join(sorted(offenders))
    )


def test_the_scan_is_not_vacuous():
    """An extractor that silently stops matching passes forever.

    The floors guard references **actually checked**, not references extracted. That distinction is
    the whole point: the two escape hatches are asymmetric — ``ALLOWLISTED_FILES`` is bounded at
    four and demands a reason per entry, while the record predicate is unbounded and unasserted, so
    it is the cheapest door through which a future red could be quietly greened. A floor on
    extracted references would not notice, because a skipped reference is still an extracted one.

    Precedent for the shape: ``assert len(scanned) > 50`` in ``test_plugin_packaging.py``.

    **The floor moved once, and this is the record of why.** It was ``> 90`` until the
    archive backfill moved 73 shipped build plans under ``artifacts/archive/`` and
    ``_is_record`` grew ``_ARCHIVE_COMPONENT`` to match, which is the record predicate
    widening — precisely what the sentence above warns is the cheapest door to a quiet
    green. It is allowed here because the widening is *by construction* rather than by
    enumeration: it exempts a container whose whole meaning is "this is history", the
    same rule ``.prawduct/archive/`` already carried, and every file it newly exempts is
    one that stopped being an instruction the moment it was archived. Both floors here are reset
    to the population that remains rather than to the number observed, and the companion
    assertion below is what stops the next widening from passing unremarked: it requires
    the LIVE artifacts tree to keep contributing, so exempting the archive cannot shade
    into exempting artifacts.
    """
    files = [p for p in _TRACKED if p.endswith(".md")]
    _, checked = _scan()
    assert len(files) > 150, f"expected to scan the tracked markdown tree, got {len(files)} files"
    assert len(checked) > 65, (
        f"only {len(checked)} path references are actually being checked — either the extractor "
        "stopped matching a form, or the record predicate has widened until the check is dark"
    )
    live_artifacts = {
        rel
        for rel, _, _ in checked
        if rel.startswith(".prawduct/artifacts/") and "/archive/" not in rel
    }
    assert live_artifacts, (
        "no LIVE .prawduct/artifacts/ file contributes a checked reference — the archive "
        "exemption has widened past the archive and is now darkening the artifacts tree "
        "itself, which is the failure the record-predicate warning names"
    )
    # Reset with the reference floor above and for the same reason — 73 of the files
    # that used to contribute are now archived records.
    assert len({rel for rel, _, _ in checked}) > 25, (
        f"only {len({rel for rel, _, _ in checked})} files contribute a checked reference"
    )
    forms = {form for _, form, _ in checked}
    assert forms == {"allowed-tools", "command", "md-link"}, (
        f"a covered form checks nothing: {sorted(forms)}. An uncovered form is an unguarded "
        "surface, not a clean one."
    )


def test_the_allowlist_stays_small_and_reasoned():
    """A probe whose allowlist outgrows its catch trains its reader to ignore it.

    Bound stated in the plan and defended here rather than left to drift. Entries are FILES, so the
    bound does not move when a record file gains another historical reference.
    """
    assert len(ALLOWLISTED_FILES) <= 4, (
        f"{len(ALLOWLISTED_FILES)} allowlisted files. Adding a fifth is a decision to record, not "
        "a step in fixing a red test — the check stops being worth reading somewhere around here."
    )
    for path, reason in ALLOWLISTED_FILES.items():
        assert path in _TRACKED_SET, f"allowlisted file is not tracked: {path} (stale entry?)"
        assert len(reason) > 40, f"allowlist entry for {path} needs a real reason, got: {reason!r}"


@pytest.mark.parametrize(
    "form,text",
    [
        (
            "allowed-tools",
            "---\nallowed-tools: Read, Bash(python3 plugin/bin/does-not-exist run *)\n---\nbody\n",
        ),
        ("command", "Run `python3 plugin/bin/does-not-exist --json` to check.\n"),
        ("md-link", "See the [guide](../plugin/docs/does-not-exist.md) for details.\n"),
    ],
)
def test_a_broken_reference_is_caught_in_each_covered_form(form: str, text: str):
    """Red-verified per form. A form with no failing case is not actually covered.

    Synthetic rather than by mutating a real file: mutating the tree to prove a test works leaves
    the proof nowhere, and this keeps each form's failure independently visible.
    """
    refs = _references("docs/example.md", text)
    assert refs, f"the {form} extractor matched nothing in its own fixture"
    assert any(f == form for f, _ in refs), f"expected a {form} reference, got {refs}"
    assert any(not _resolves("docs/example.md", raw, form) for f, raw in refs if f == form), (
        f"the {form} fixture references a nonexistent path but was reported as resolving"
    )


def test_a_grant_token_naming_a_repository_is_not_a_path_reference():
    """``owner/name`` is path-shaped, names nothing on disk, and must not redden the suite.

    Pins the narrowing rather than assuming it: the shared allowed-tools fixture grants
    ``plugin/bin/does-not-exist``, which the bare shape test and ``_is_repo_path`` BOTH extract, so
    reverting grant extraction to ``_PATH_SHAPED.match(token) and "/" in token`` leaves every other
    case in this file green. Latent today — ``plugin/bin/prawduct-hook`` is the only slash-bearing
    grant token in tracked markdown — which is exactly why it needs a test rather than a comment.
    """
    grant = "---\nallowed-tools: Read, Bash(gh issue list --repo owner/name *)\n---\nbody\n"
    assert not [f for f, _ in _references("docs/example.md", grant) if f == "allowed-tools"], (
        "a repository argument was extracted as a path reference, which reddens the suite on a "
        "non-defect and invites an allowlist entry spent on a bug in this extractor"
    )
    # The same line still yields the real path beside it — narrowing, not disabling.
    both = "---\nallowed-tools: Bash(gh issue list --repo owner/name *), Bash(python3 plugin/bin/prawduct-hook *)\n---\nbody\n"
    assert [raw for f, raw in _references("docs/example.md", both) if f == "allowed-tools"] == [
        "plugin/bin/prawduct-hook"
    ]


def test_a_citation_is_not_a_reference():
    """Prose that mentions a path in order to discuss it must not redden.

    Every string here is real: the first three are quoted in this batch's own build plan (a worked
    example, and two descriptions of the pre-``plugin/`` layout), the rest are runtime-generated or
    product-side paths that legitimately do not exist in this tree. A check that fails on its own
    specification is a check nobody will keep.
    """
    citations = [
        "The forward-reference rule uses `skills/foo/bar.md` as its example.",
        "Completed plans name `tools/lib/core.py`, which was accurate when written.",
        "The v1.5 plan refers to `agents/critic/SKILL.md` throughout.",
        "The default is `.prawduct/artifacts/build-plan.md` in a product repo.",
        "Forward notes live in `.prawduct/.handoff-notes.md`.",
        "The dispatcher writes `.prawduct/.critic-partials/reviewer.json`.",
        # A markdown link QUOTED inside a code span. Pinned synthetically rather than relying on
        # the build plan that quotes the real one: a guard that lives in a document scheduled for
        # deletion is a guard with an expiry date, and this is precisely the "branch that depends
        # on a file which happens to exist" shape.
        "It links to `[learnings file](../.prawduct/learnings.md)`, which does not resolve.",
        "```\nsee [a guide](../nowhere/absent.md)\n```",
    ]
    for text in citations:
        assert not _references("docs/example.md", text), (
            f"a citation was extracted as an instruction-bearing reference: {text!r}"
        )


def test_the_plugin_fallback_is_denied_to_invocation_forms():
    """A plugin doc may NAME a sibling the way the plugin ships it; it may not INVOKE one that way.

    This is the assertion that makes the motivating defect visible. Scoping the fallback by file
    alone leaves skills inside the entitled scope — and skills' prose and grants are exactly where
    the five-skill breakage lived, so two of three forms on the exact files of the exact class still
    resolved. Without this test the property is incidental to how ``_resolves`` happens to be
    written; with it, restoring the wider fallback reddens.
    """
    skill = "plugin/skills/backlog/SKILL.md"
    # NAMING a sibling file the way the plugin ships it — legitimate, still resolves.
    assert _resolves(skill, "methodology/building.md", "md-link")
    assert _resolves(skill, "lib/backlog_probes.py", "md-link")
    # INVOKING the pre-relocation path — the motivating defect, in both invocation forms.
    assert not _resolves(skill, "bin/prawduct-hook", "command")
    assert not _resolves(skill, "bin/prawduct-hook", "allowed-tools")
    # The corrected form resolves from anywhere, which is why all fifteen uses in the shipped
    # plugin say it. "In the shipped plugin", not "in-tree": tree-wide the literal appears in
    # tracked markdown well over a hundred times, and a reviewer re-measuring the wider scope
    # would read this load-bearing count as fabricated.
    assert _resolves(skill, "plugin/bin/prawduct-hook", "command")
    # Build plans hold the same declared entitlement, and the same denial.
    plan = ".prawduct/artifacts/build-plan-drift-burndown.md"
    assert _resolves(plan, "lib/gates.py", "md-link")
    assert not _resolves(plan, "bin/prawduct-hook", "command")


def test_relative_targets_resolve_against_the_containing_file():
    """``./`` and ``../`` are relative to the file, not the repo root.

    Resolving them at the repo root over-reported twenty non-defects during the census — a whole
    cluster of ``documentation/work-model*.md`` cross-links that are perfectly correct. A resolver
    that is wrong in this direction sends the builder to 'fix' working links.
    """
    # ``form`` is never consulted on a ``./``/``../`` ref — the relative branch returns before the
    # fallback that reads it — but it is passed explicitly because the parameter is required, and
    # ``md-link`` is the form these actually appear in.
    assert _resolves("plugin/docs/principles.md", "./doctor-vs-janitor.md", "md-link")
    assert _resolves("plugin/skills/critic/SKILL.md", "../../methodology/building.md", "md-link")
    assert not _resolves("plugin/docs/principles.md", "../.prawduct/learnings.md", "md-link")
    # The same target from a file one level up DOES resolve — proving the base is the containing
    # file rather than a constant.
    assert _resolves("plugin/principles.md", "../.prawduct/learnings.md", "md-link")


# ---------------------------------------------------------------------------
# Which interpolation a shipped instruction may use
#
# Claude Code substitutes ``${CLAUDE_PLUGIN_ROOT}`` into hook commands declared in
# ``hooks/hooks.json``, and exports it into the environment of the process those
# commands start. It does NOT substitute it into skill prose, and the Bash tool the
# agent runs does not carry it either — so a prose instruction spelled that way
# reaches the reader as the literal seven-token string and names nothing.
# ``${CLAUDE_SKILL_DIR}`` *is* substituted when a skill loads, which makes
# ``${CLAUDE_SKILL_DIR}/../../<path>`` the form that resolves from a skill to
# anything else the plugin ships.
#
# The failure is silent and it is worse than a missing file: the reader that cannot
# open the path does not stop. Doctor's install-reference check, told to read the
# install contract out of the plugin, falls back to the illustrative list printed
# beside the instruction — a list its own text forbids grading against, and one that
# has already gone stale once. So the check reports a verdict, and the verdict is
# whatever the stale list says.
#
# The trees below are the ones whose markdown is READ AS INSTRUCTIONS: skill prose,
# the docs skills route readers into, the methodology guides, and the templates a
# product copies. ``plugin/CHANGELOG.md`` sits outside them because it is a record —
# it narrates the packaging change that curated the plugin root, and naming the
# variable is the subject of the sentence rather than a path anyone follows.
#: `plugin/agents/` is here for a reason worth stating: `critic-reviewer.md` ships in
#: the plugin and is read verbatim as a subagent's system prompt, and it is the one
#: tree where the remedy does NOT apply — `${CLAUDE_SKILL_DIR}` is not defined for an
#: agent, so an agent file must name its paths in prose. It is clean today, which is
#: exactly why omitting it was invisible: the next agent definition would reopen the
#: defect with CI green, in the one instruction surface the guard could not see.
_INSTRUCTION_TREES = (
    "plugin/skills/", "plugin/docs/", "plugin/methodology/",
    "plugin/templates/", "plugin/agents/",
)

#: The INTERPOLATION, not the name. Prose is free to discuss `CLAUDE_PLUGIN_ROOT`
#: as a variable — that reads as documentation. `${...}` reads as a path to follow,
#: and in these trees it is always a path that will not resolve. Keeping the rule on
#: the sigil is what lets it stay absolute instead of growing an exemption list.
_PLUGIN_ROOT_INTERPOLATION = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}")
_SKILL_DIR_INTERPOLATION = re.compile(r"\$\{CLAUDE_SKILL_DIR\}")


def _instruction_markdown() -> list[str]:
    return [
        p for p in _TRACKED
        if p.endswith(".md") and p.startswith(_INSTRUCTION_TREES)
    ]


def test_no_shipped_instruction_interpolates_the_plugin_root():
    """Skill prose and the docs it routes to must not spell a path they cannot resolve."""
    offenders = []
    for rel in _instruction_markdown():
        for lineno, line in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), 1):
            if _PLUGIN_ROOT_INTERPOLATION.search(line):
                offenders.append(f"{rel}:{lineno}")
    assert not offenders, (
        "${CLAUDE_PLUGIN_ROOT} does not expand outside a hooks.json command, so these "
        "instructions hand their reader a literal that names nothing. Use "
        "${CLAUDE_SKILL_DIR}/../../<path> from a skill; from a doc, which is read as "
        "plain content and interpolates nothing at all, describe the location instead:"
        "\n  " + "\n  ".join(offenders)
    )


def test_the_resolving_interpolation_is_the_one_in_use():
    """The rule above is assert-absent, and deleting every path would satisfy it.

    This is the other half: skills really do have to reach across the plugin, and
    they reach with the form that expands. If this goes quiet, the reads were not
    repointed — they were removed, or the substitution contract changed under them.
    """
    users = {
        rel for rel in _instruction_markdown()
        if _SKILL_DIR_INTERPOLATION.search((REPO / rel).read_text(encoding="utf-8"))
    }
    assert len(users) >= 4, (
        f"only {len(users)} shipped instruction files reach across the plugin with "
        "${CLAUDE_SKILL_DIR} — either the cross-plugin reads are gone, or they are "
        "being written some other way that this check no longer sees"
    )


def test_the_interpolation_sweep_has_subjects():
    """An assert-absent check over an empty file list is green and worthless."""
    assert len(_instruction_markdown()) > 20, (
        f"only {len(_instruction_markdown())} instruction-bearing markdown files found "
        f"under {_INSTRUCTION_TREES} — the trees moved and the sweep is dark"
    )
