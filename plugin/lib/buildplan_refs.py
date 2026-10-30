"""Build-plan reference parsing + governance-protected path bounds for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 3) — the build-plan
parsing cluster: it reads the active build plan's per-chunk sections (file-path
refs, ``Type:`` declaration) and owns the governance-protected path bounds
(``protected_path_violation``). Parsing + path inspection, plus read-only git
queries (refs, the branch's diff) — no git mutation, no network. Which chunks
are done, and which is current, is ``plan_status``' answer (#1051); nothing here
reads a ``## Status`` box.

Depends on its lib siblings ``gitstate`` (git and ``.prawduct`` lookups), ``core``
(``read_str_yaml_key``), ``work_unit`` (which plan governs this checkout),
``coverage`` (``_resolve_base_branch``) and ``plan_index`` (the canonical
frontmatter ``scope:`` reader) plus the stdlib. A reader here that is asked
about "the active plan" (``plan_path=None``) asks ``work_unit.resolve`` and reads
the bound plan, or none — there is one resolver, and no reader walks a route of
its own.

**Dependencies point downward.** ``core`` never imports this module, and
``work_unit`` imports only ``core``, ``gitstate`` and ``plan_index``, so this
module imports it at module scope at no extra cost.

Every read of the plan — here and in every other module that reads it — is
explicitly UTF-8, and every guarded read catches ``UnicodeDecodeError`` beside
``OSError``. Both axes are pinned by
``tests/preferences/test_build_plan_decoding.py``. The
plan is markdown authored by a model or a human (em dashes, arrows,
box-drawing), and which of its readers can decode it must not depend on the
operator's locale. The divergence this rule exists to prevent is not a decode
failure but a DISAGREEMENT: readers of the same file on different codecs, with
different except-sets, answering differently about whether it parses. It was
found three review rounds running — first six of seven reads in this module,
then two more outside it, one of them inside a function that reads the plan
twice — which is why the rule is now a pin rather than a convention.

The hook calls these lazily via ``_buildplan_refs()``, keeping its top level
lib-free.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

from . import core, gitstate, plan_index, waivers, work_unit
from .core import read_str_yaml_key
from .coverage import _resolve_base_branch

# `plan_index` is imported at MODULE scope, deliberately, where its predecessor
# `lib.views` had to be lazy. This module IS the hot path — `briefing` and
# `gates` both import it at module scope, so it is billed at every SessionStart
# and every Stop — and a lazy import inside the function is a cost of its own
# once the callee is cheap. Measured marginal cost on top of this module's own
# imports: `plan_index` 0.29ms, against 7.39ms for the module it replaced (now
# deleted, so that figure is history rather than a comparison anyone can re-run).
# `plan_index` shares `pathlib` and `collections.abc` with this module and pulls
# nothing else, which is the property that has to hold, not the number:
# `tests/test_lib_lazy_imports.py` asserts it structurally, against a positive
# control that proves the probe can fail. Re-measure with
# `python3 -c "import lib.buildplan_refs, time; ..."`, do not trust these
# figures on a different tree.
#
# This replaces a "deliberately no millisecond figure here" note that used to sit
# on `_scope_plan_map`, and the reversal is narrower than it looks: that note
# governed the SCAN cost, which is a property of each consumer's artifacts/ tree
# and therefore drifts the moment it is written down. These are IMPORT costs — a
# property of this code, identical in every checkout of a given version — and what
# binds is the structural test, not the numbers.


def _bound_plan_path(project_dir: Path) -> "Path | None":
    """The plan the checkout's work-unit binding names, or ``None``.

    What every reader here means by "the active plan" when its caller passes
    ``plan_path=None``. ``None`` for an unbound checkout (no plan is borrowed)
    and for a broken one (no claimant is chosen by precedence) — so a caller
    holding ``binding.plan_path`` may pass it straight through, ``None``
    included, and be answered about the same plan, never another route's.
    """
    binding = work_unit.resolve(project_dir)
    return binding.plan_path if binding.state == "bound" else None


# The Status section's bounds live in `plan_index` (#657). This alias stays for
# `lifecycle_repair`, which reads it through this module. Nothing here walks the
# section or reads a box: which chunks are done is `plan_status`' answer (#1051).
status_section_bounds = plan_index.status_section_bounds


# Build-plan chunk id extraction — the two supported forms:
#   "### Chunk 02: Name"            (H3, colon — the template default)
#   "## Chunk 2 (RES-K3QP) — Name"  (H2, optional "(ID)", en/em dash — research plans)
# The id is the first whitespace-delimited word after "Chunk", and it MUST be
# followed by a separator (``: — – - (``) or end-of-line — so a notes heading
# like "### Chunk 2 build-session decisions" is NOT mistaken for chunk 2's
# deliverable heading. Leading zeros are tolerated downstream ("2" matches
# "### Chunk 02:"). Previously only the colon form parsed, so an em-dash heading
# silently disabled Goal-2 ref verification and per-chunk mode scoping for the
# whole plan.
# `**` closes a bolded label (`**Chunk A** — Name`) and so terminates the id
# exactly as `:` or an em-dash does. It is in the SEPARATOR set, and `_CHUNK_BOLD`
# allows the opening `**`. The bold form is accepted because plans in the wild
# write it, and because this matcher once had a Status-line twin in the derived-
# view machinery that accepted it while this one did not. That disagreement cost
# more than either matcher's gap alone: the checkbox flipped (the twin matched)
# while `_chunk_id_from_item_text` returned None (this matcher did not), so the
# plan read as having NO current chunk and `verify-chunk-refs` exited 0 having
# verified nothing. The twin is gone and this is the sole matcher, so the
# disagreement cannot recur — but the widening stays, because the plans that
# provoked it are still on disk. A one-sided widening of a shared contract is not a partial
# fix, it is a new defect.
#
# Two more authoring forms are accepted for the same reason: plans in the wild
# write them, and neither errors when it fails to parse.
#   * A **dotted id** (`Chunk 1.2`) — sub-chunk numbering. `(\w+)` stopped at the
#     `1`, and `.` is not a separator, so the whole heading fell through.
#   * A **leading checkbox** (`### [ ] Chunk 7:`, `- [x]` bullet included) — plans
#     that carry the roster's tick marks into the body headings. The checkbox
#     occupies the position the matcher expected `Chunk` in.
# The dotted id is `\w+(?:\.\w+)*` rather than `[\w.]+`, so a heading ending in a
# sentence period (`### Chunk 1. Name`) still fails to match instead of yielding
# the id `1.` — that form did not parse before and gains nothing by parsing as a
# chunk nobody's Status roster names.
# Both widenings land on BOTH matchers, which is the rule the paragraph above
# records: the heading form and the Status-item form are one authoring
# vocabulary read by two regexes, and a form accepted by one alone reproduces
# the split-brain exactly — the section resolves while the roster entry returns
# None, so completeness "cannot be told", every forward-ref exemption is kept,
# and the check passes having verified nothing.
# `_CHUNK_ITEM_RE`'s callers hand it Status-item text with the `- [ ] ` prefix
# already stripped, so the checkbox alternative is unreachable on today's paths;
# it is there so that a caller passing a raw Status LINE gets the same answer as
# the heading matcher does, rather than a second silent gap to discover later.
_CHUNK_ID_SEP = r"\s*(?:[:—–(-]|\*\*|$)"
_CHUNK_BOLD = r"(?:\*\*\s*)?"
_CHUNK_CHECKBOX = r"(?:(?:[-*+]\s+)?\[[ xX]\]\s+)?"
_CHUNK_ID = r"(\w+(?:\.\w+)*)"
#: Strips a leading ``Chunk`` label so the flag accepts what the heading prints.
_CHUNK_LABEL_PREFIX_RE = re.compile(r"^[Cc]hunk\s+")
_CHUNK_HEADING_RE = re.compile(
    r"^#{2,3}\s+" + _CHUNK_CHECKBOX + _CHUNK_BOLD + r"Chunk\s+" + _CHUNK_ID + _CHUNK_ID_SEP
)
_CHUNK_ITEM_RE = re.compile(
    r"^" + _CHUNK_CHECKBOX + _CHUNK_BOLD + r"Chunk\s+" + _CHUNK_ID + _CHUNK_ID_SEP
)

# A heading line that ANNOUNCES a chunk without parsing as one — deliberately
# looser than `_CHUNK_HEADING_RE` on every axis it can afford to be: any heading
# depth (`#### Chunk 01:` is the classic silent defeat), any short run of
# punctuation between the hashes and the word, any dotted id, and any separator
# after it. What it will not accept is the two shapes that make a heading prose
# rather than an announcement:
#   * a WORD after the id — `### Chunk 1 build-session decisions` is a notes
#     sub-heading living inside chunk 1's body, and treating it as a boundary is
#     a defect this module already fixed once;
#   * an APOSTROPHE after the id — `## Chunk 01's review` is possessive prose.
# It is used only to explain a failure, never to locate a section: nothing is
# parsed out of it, so being loose costs a sentence and never a wrong id.
_CHUNK_ANNOUNCE_RE = re.compile(
    r"^#{1,6}\s+[^A-Za-z0-9]{0,8}Chunk\s+[\w.]+\s*(?:[^\w\s'’]|$)"
)


def has_build_plan_shape(content: str) -> bool:
    """Whether ``content`` is a build plan on POSITIVE evidence rather than by default.

    ``plan_index.is_build_plan`` answers the same question from frontmatter and
    fails safe toward *yes*: a document declaring no ``artifact:`` counts,
    because at least one real plan declares none. That direction is sound where
    a declared ``scope:`` is already evidence, and useless without it — over
    this repo's live ``artifacts/`` it admits 22 documents of which 20 are
    release plans, spikes, audits and ``project-preferences.md``.

    So this asks for evidence instead, in the three forms a build plan in the
    wild actually carries. Any one is enough, and each is load-bearing on its
    own — one plan in this repo's own corpus is reachable by that signal and no
    other, which is why the union is not redundancy:

    * it DECLARES the type — ``v1.5-critic-proportionality-plan.md``;
    * it has a ``## Status`` section — ``waiver-pragma-plan.md``, whose chunks
      are list items no heading matcher parses. The section's presence is the
      signal, never its boxes: what a box says is ``plan_status``' to read, and
      over this repo's 250 artifacts (2026-10-25) the presence test admits
      exactly the documents the old roster-item test did;
    * it ANNOUNCES a chunk — ``build-plan-coverage-perf.md``, which has chunks
      and no Status section at all. Matched with :data:`_CHUNK_ANNOUNCE_RE`, not
      the stricter :data:`_CHUNK_HEADING_RE`: the strict one exists to parse an
      *id* out of a heading, and a heading it cannot parse is exactly the plan
      most in need of being named here — ``#### Chunk 01:`` is the classic
      silent defeat. This asks only "does this document announce chunks", which
      is the loose matcher's stated job. The two agree on all 138 documents in
      this repo, so the widening costs nothing today and covers the shape that
      would otherwise escape.

    Measured 2026-08-20 over the 91 known-real build plans in this repo (90
    archived plus the live scoped one): the three signals score 90, 90 and 91,
    their union 91, and against the 22 scope-less live candidates the union
    names exactly the 2 that are genuinely plans.
    ``tests/test_unscoped_plan_fact.py`` re-measures both halves against the
    real corpus rather than restating these numbers, so they cannot quietly rot.

    This lives here and not in ``plan_index`` because two of the three signals
    are build-plan STRUCTURE, which is this module's subject; ``plan_index``
    reads frontmatter, imports nothing heavy, and runs at every session boundary.
    """
    if plan_index.declared_artifact_type(content) == plan_index.BUILD_PLAN_TYPE:
        return True
    if plan_index.status_section_bounds(content.splitlines()) is not None:
        return True
    return any(_CHUNK_ANNOUNCE_RE.match(line) for line in content.splitlines())


def plans_missing_scope(artifacts_dir: Path) -> list[Path]:
    """Live build plans invisible to the scope walk because they declare no ``scope:``.

    The published fact consumers call: ``plan_index.unscoped_candidates`` owns
    the walk and the frontmatter half, this supplies the
    :func:`has_build_plan_shape` evidence that walk refuses to guess at.

    **Every reader of ``iter_scoped_plan_candidates`` reports over a set these
    plans are missing from**, so any of them that states coverage asks this
    beside it — that is the rule, rather than a list of today's callers that
    goes stale as the next one is added. Asking turns an implied-complete
    figure into a stated one, and at the release gate it turns a false sentence
    into a caveated one: an unscoped plan there produced "work is shipping with
    no plan describing it" about a plan sitting in the same directory.
    """
    return plan_index.unscoped_candidates(
        artifacts_dir, looks_like_plan=has_build_plan_shape
    )


def _chunk_id_from_item_text(text: str) -> str | None:
    """``"Chunk 02: name"`` / ``"Chunk 2 (ID) — name"`` → ``"02"`` / ``"2"``;
    ``None`` for non-chunk items. Accepts the colon (``### Chunk N:``) and the
    em/en-dash + optional ``(ID)`` (``## Chunk N (ID) — name``) forms."""
    m = _CHUNK_ITEM_RE.match(text)
    return m.group(1) if m else None


def _commits_ahead_of_base(project_dir: Path, base: str) -> int:
    """Number of commits on HEAD since merge-base with ``base``. ``-1`` on failure."""
    proc = subprocess.run(
        ["git", "rev-list", "--count", f"{base}..HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return -1
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return -1


class ReviewedPlan(NamedTuple):
    """Which build plan a review is actually about, and how that was decided.

    ``path`` is ``None`` when no plan could be resolved at all. ``gap`` carries a
    reason when the resolution is an assumption or a failure, so a caller can
    report it rather than grade a subject it only guessed at; it is ``None`` when
    the answer is grounded.

    The distinction this type exists for: **a chunk id from the dispatch and a
    plan from ``active_build_plan`` are two halves of one question resolved from
    different places, with nothing checking they agree.** When they disagree the
    deliverable check grades a chunk of a plan the diff has nothing to do with,
    and answers zero — which is the shape of a clean result.
    """

    path: Path | None
    rel: str | None
    scope: str | None
    gap: str | None


def _scope_plan_map(prawduct_dir: Path) -> dict[str, Path]:
    """``{frontmatter scope: plan path}`` over this repo's artifacts directory.

    Asked by :func:`resolve_reviewed_plan` when a dispatch names a scope, and by
    :func:`unresolved_scope_cause` when explaining why none resolved — not by
    "which plan governs this checkout", which is ``work_unit.resolve``'s walk.

    **Nothing memoizes the scan across calls.** The recursive walk of
    ``artifacts/`` and its per-file frontmatter parse happen every time; a
    caller asking twice passes the map it built (``known=``). What bounds the
    walk as plans accumulate is :mod:`lib.plan_index` pruning the archive at
    directory level.
    """
    return plan_index.build_scope_to_plan_map(prawduct_dir / "artifacts")


def _declares_scope(plan_path: Path) -> bool:
    """Whether the plan's frontmatter names a scope, whether or not the scope map kept it.

    The map keeps one plan per scope, so a plan whose scope duplicates another's
    is absent from it while still declaring one — telling it to "add" a scope
    would be wrong advice.
    """
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return bool(plan_index.parse_build_plan_frontmatter_scope(content)[1])


def _changed_on_branch(project_dir: Path, pathspec: Path) -> "set[Path] | None":
    """Files under ``pathspec`` this branch created or edited since it left the base.

    Tracked changes are measured from the merge-base to the working tree, so
    committed and uncommitted edits both count; untracked files count too,
    because a file git has never seen was written here rather than inherited.
    Resolved absolute paths. ``None`` when it cannot be shown — no base, no
    merge-base, a git error — so a caller can tell "nothing changed" from
    "could not look".
    """
    base, _ = _resolve_base_branch(project_dir)
    if not base:
        return None
    try:
        mb = subprocess.run(
            ["git", "merge-base", base, "HEAD"],
            cwd=str(project_dir), capture_output=True, text=True, timeout=10,
        )
        if mb.returncode != 0 or not mb.stdout.strip():
            return None
        diff = subprocess.run(
            ["git", "diff", "--name-only", "--relative", mb.stdout.strip(), "--", str(pathspec)],
            cwd=str(project_dir), capture_output=True, text=True, timeout=10,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", str(pathspec)],
            cwd=str(project_dir), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if diff.returncode != 0 or untracked.returncode != 0:
        return None
    names = diff.stdout.splitlines() + untracked.stdout.splitlines()
    return {(project_dir / n).resolve() for n in names if n.strip()}


def unresolved_scope_cause(
    project_dir: Path, prawduct_dir: Path
) -> "tuple[str, str] | None":
    """Why an unbound checkout's review found no scope here: ``(code, sentence)``.

    Advice for the dispatcher of a review whose scope did not resolve — the
    review then records no scope, and every control keyed on one (the round
    budget first) cannot see it. Without this the only trace was a parenthetical
    on the record-lint line, and the commonest causes are one-line edits to a
    plan, so naming the plan and the edit is most of the fix.

    ``None`` when there is nothing to fix: a detached HEAD, or the integration
    branch, where no plan should claim the branch and a note would fire on every
    review with nothing to act on. The codes, first match wins:

    - ``claim-no-scope`` — a plan claims this branch in frontmatter and declares
      no ``scope:``, so the claim has no scope to hand back.
    - ``body-branch`` — a plan names this branch on a ``branch:`` line below its
      frontmatter, where :func:`plan_index.branch_claiming_plans` never looks.
    - ``pointer-claims-other`` — the fallback plan (the pointer, else the
      conventional ``build-plan.md``) claims a different branch, so it does not
      govern this one (``work_unit.resolve`` never serves a plan that declares
      some branch to another).
    - ``no-claim`` — a live plan this branch created or edited does not claim
      it. That edit is the evidence the branch has a plan at all; a branch that
      touched no plan is doing plan-less work (a chore, a small fix), where
      "add ``branch:`` to your plan" is advice with nothing to act on, so it
      gets ``None`` rather than a note on every review. A branch binds by its
      plan's claim alone — its name is never matched against a ``scope:``.

    Call it only when resolution has already failed; it re-derives nothing the
    resolver decided and would name a cause for a scope that did resolve.
    """
    branch = gitstate.current_branch(project_dir)
    if not branch:
        return None
    base, _ = _resolve_base_branch(project_dir)
    if base and branch == base.removeprefix("origin/"):
        return None

    artifacts_dir = prawduct_dir / "artifacts"
    known = _scope_plan_map(prawduct_dir)
    scoped = set(known.values())

    def rel(path: Path) -> str:
        return work_unit.repo_rel(path, prawduct_dir.parent)

    for path, claimed in plan_index.branch_claiming_plans(artifacts_dir):
        if (
            claimed == branch
            and path not in scoped
            and not _declares_scope(path)
        ):
            return (
                "claim-no-scope",
                f"{rel(path)} claims branch {branch!r} but declares no `scope:` in "
                "its frontmatter, so the claim has no scope to record — add one",
            )

    body = plan_index.plans_naming_branch_in_body(artifacts_dir, branch)
    if body:
        path = body[0]
        missing_scope = "" if path in scoped else ", together with a `scope:`"
        return (
            "body-branch",
            f"{rel(path)} names branch {branch!r} below its frontmatter, where "
            f"nothing reads it — move `branch: {branch}` into the `---` block at "
            f"the top of the file{missing_scope}",
        )

    # One statement of "the fallback claims another branch", shared with
    # nothing that resolves — the refusal itself is `work_unit.resolve`'s.
    foreign = core.foreign_fallback_claim(prawduct_dir)
    if foreign is not None:
        refused, other = foreign
        return (
            "pointer-claims-other",
            f"the fallback plan {rel(refused)} claims branch {other!r}, not "
            f"{branch!r}, so it does not govern this branch — correct its "
            "`branch:` if this is its work, or pass `--scope`",
        )

    changed = _changed_on_branch(project_dir, artifacts_dir) or set()
    edited = [p for p in plan_index.iter_live_plan_files(artifacts_dir) if p.resolve() in changed]
    if not edited:
        return None
    return (
        "no-claim",
        f"{rel(edited[0])} was edited on this branch but no live plan declares "
        f"`branch: {branch}` in its frontmatter — if that is this work's plan, "
        f"bind it (`{work_unit.BIND_COMMAND} <plan> --branch {branch}`); "
        "otherwise pass `--scope`",
    )


def resolve_reviewed_plan(
    project_dir: Path,
    prawduct_dir: Path,
    scope: "str | None",
    known: "dict[str, Path] | None" = None,
) -> ReviewedPlan:
    """Resolve the build plan a review is about: the reviewed SCOPE's plan when
    the dispatch names one, else the checkout's work-unit binding.

    ``known`` is a prebuilt scope→plan map, so a caller that already walked
    ``artifacts/`` pays no second walk. Omitted, it builds its own.

    Outcomes:

    - **scope names a plan** → that plan, ``gap=None``; ``rel`` names the file
      that was graded.
    - **scope names no plan** → ``path=None`` and a ``gap``. Falling back here is
      precisely the silent grade of an unrelated plan, so the caller must report
      instead of answering.
    - **no scope** → the binding (``work_unit.resolve``). A plan that claims
      this branch has ``gap=None`` — the claim is the grounding — unless it
      declares no ``scope:``, which the gap says. A legacy-window plan's gap
      carries the binding's reason, on every repo: it was once silent where
      only one plan declared a scope (#1007(a)), which left a fallback answer
      looking exactly like a grounded one. An unbound or broken checkout is
      ``path=None`` with the binding's reason as the gap — no plan is borrowed
      and none is chosen. How the binding was reached is the binding's
      ``case``; this answer does not restate it.
    """
    if scope and scope.strip():
        scope = scope.strip()
        match = (known if known is not None else _scope_plan_map(prawduct_dir)).get(scope)
        if match is None:
            return ReviewedPlan(
                None,
                None,
                scope,
                f"the dispatch names scope {scope!r} but no build plan under "
                "artifacts/ declares it — grading this repo's active plan "
                "would grade a different subject",
            )
        return ReviewedPlan(match, work_unit.repo_rel(match, project_dir), scope, None)

    binding = work_unit.resolve(project_dir)
    if binding.state != "bound" or binding.plan_path is None:
        return ReviewedPlan(None, None, None, binding.reason)
    return ReviewedPlan(
        binding.plan_path,
        work_unit.repo_rel(binding.plan_path, project_dir),
        binding.scope,
        binding.reason,
    )


def _plan_description_fallback(plan_path: Path, content: str) -> str:
    """Name the plan when it carries no ``# Build Plan`` H1.

    The frontmatter-style plans this repo writes open with a ``---`` block and a
    ``## Goals`` heading (older plans: ``## Requirements Confidence``) — no H1 at all. Requiring one made
    ``description`` empty, and an empty description is not a cosmetic loss: it
    is the sole key gating the handoff's Work In Progress section, so the whole
    section vanished from a live four-chunk plan's handoff. Fall back to the
    frontmatter ``scope:``, then to the filename with the conventional
    ``build-plan-`` prefix stripped, so the section can never silently vanish.
    """
    _present, scope = plan_index.parse_build_plan_frontmatter_scope(content)
    if scope:
        return scope
    return plan_path.stem.removeprefix("build-plan-") or plan_path.stem


_BUILD_PLAN_PATH_RE = re.compile(r"`([^`\s]+)`")
_BUILD_PLAN_NEW_QUALIFIER_RE = re.compile(r"\bnew\s+`([^`\s]+)`")
# The mirror of `new`: a deliverable declared as a REMOVAL is satisfied by the
# file's absence, not falsified by it.
#
# Without this the ref check is structurally unable to pass a retirement chunk.
# It asserts existence for every backticked deliverable ref, so a chunk whose
# job is deleting `x.py` reports `missing-ref: x.py` **because it succeeded** —
# and the check is rated BLOCKING, so the work cannot be closed honestly. The
# tempting workaround is to reword the plan until the parser stops seeing the
# path, which satisfies the checker by making the plan describe its own deletion
# less clearly. That is fixing the symptom at the cost of the artifact.
#
# Deliberately an EXPLICIT qualifier rather than a heuristic over removal verbs
# near a path. A fuzzy rule would exempt real deliverables sitting in a sentence
# that happens to mention a deletion, and an exemption that fires by accident is
# worse than no exemption — it fails open on exactly the input the gate exists
# to judge. Both orders are accepted because both read naturally in a
# Deliverables line (``deleted `x.py` `` and ``` `x.py` deleted ```), but the
# verb must be ADJACENT to the path, so the binding is visible to a reader.
#
# No expiry, where `new` has one. `new` expires when the chunk completes because
# a promised file that still does not exist is a real miss; a removal is the
# opposite — before completion the file is still there and resolves on its own,
# and after completion its absence IS the delivery.
_REMOVAL_VERBS = r"(?:deleted|removed|retired)"
_BUILD_PLAN_GONE_QUALIFIER_RE = re.compile(
    rf"\b{_REMOVAL_VERBS}\s+`([^`\s]+)`|`([^`\s]+)`\s+(?:is\s+|are\s+)?{_REMOVAL_VERBS}\b"
)
# #224(b): `new` is also an ordinary English adjective. Narrative prose ABOUT a
# file — a `Context:` paragraph recording that a chunk "added new `x.py`" — is
# not a declaration that THIS chunk creates it, but the qualifier matched any
# `new` before any backticked token anywhere in the section, so one such
# sentence silently exempted a real path from verification for the whole chunk.
#
# **The item prescribed scoping to a Deliverables list item; that is too narrow
# and this departs from it deliberately.** Real plans in this repo declare
# creations outside Deliverables as a matter of course —
# `build-plan-api-design.md:177` names a new test file in `- **Tests:**` and
# `:109` names one in acceptance criteria. Honouring the qualifier only inside
# Deliverables would turn every one of those into a false missing-ref, which is
# the failure the exemption exists to prevent. The distinction that actually
# separates the two cases is STRUCTURAL rather than positional: a declaration is
# a list item (`- new \`x\``, `1. new \`x\``), while the adjectival use that
# motivated the item lives in running paragraphs. Scoping to list items excludes
# the prose without breaking the fields plans really use, and #224(a) — the
# expiry below — is what actually catches a file the chunk promised and skipped.
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s)")
# A list item does not end at its first newline. This repo's plans wrap
# deliverable bullets across several lines, and the `new `path`` declaration
# routinely lands on a CONTINUATION line rather than the one carrying the
# bullet marker. Matching per-line therefore dropped the exemption for the
# dominant declaration form and would have produced BLOCKING `missing-ref:`
# findings on open chunks — a worse failure than the one #224(b) set out to fix.
# A continuation is a non-blank line that starts no new item and is not a
# column-0 field; a blank line or a column-0 non-list line closes the block.
_PLAN_FIELD_RE = re.compile(r"^\S")
# A trailing `:<line>`, `:<line>:<col>`, or `:<line>-<line>` on a backticked
# token is a code-location citation (`lib/critic_mode.py:452`, `lib/foo.py:5-8`,
# the editor-style `lib/foo.py:12:34`), not part of the filename.
_BUILD_PLAN_LINE_SUFFIX_RE = re.compile(r":\d+(?::\d+)?(?:-\d+)?$")
# ---------------------------------------------------------------------------
# The shared grammar of a build-plan chunk FIELD (`**Type:**`, `**Critic
# mode:**`, …). Every chunk field is written the same way and misread the same
# way, so the shapes live here once and each reader keeps only what genuinely
# differs — what it does with a value it cannot honour. `critic_mode` builds its
# own patterns from these factories; two hand-copied delimiter classes is how
# they came to disagree about `<br>`.
# ---------------------------------------------------------------------------


def field_token_re(label: str) -> "re.Pattern[str]":
    """The one-word VALUE of a ``**<label>:**`` field, wherever it sits.

    Hyphen-aware, so ``doc-only`` and ``verify-resolutions`` are captured whole.
    The opening backtick is optional — authors backtick values. And the token
    must END at a delimiter: read up to the first non-word character instead,
    ``n/a (verification only)`` reports the value ``'n'``, a string that appears
    nowhere in the author's plan.

    Unanchored on purpose, because the field is not reliably the first thing on
    its line — authors compose chunk headers (``**Depends on:** — · **Type:**
    code · **Critic mode:** chunk``). Apply it through
    :func:`iter_field_declarations`, never with a bare ``.search``: the marker
    appears in PROSE too, and a sentence discussing a field must not be read as
    declaring it.
    """
    return re.compile(
        rf"\*\*{re.escape(label)}:\*\*\s*`?([A-Za-z][\w\-]*)(?=[\s`.,;)<·|]|$)"
    )


def field_value_re(label: str) -> "re.Pattern[str]":
    """Everything after a ``**<label>:**`` that OPENS its line, verbatim.

    Field position — the line starts with the field, modulo list and bold
    markers — is what earns a value the right to be reported back to its author
    when no token can be read out of it. A value further along a line does not:
    see :func:`iter_field_declarations` for why position is a heuristic there,
    and a heuristic must not be the thing that fails someone's chunk.

    Blank matches nothing, deliberately: a field with nothing after it carries
    no intent to contradict.
    """
    return re.compile(rf"^[\s\-\*]*\*\*{re.escape(label)}:\*\*\s*(\S.*?)\s*$")


#: How much of an unreadable value a report quotes. Fields take a one-word
#: token, so anything past this is prose that will not help the author find
#: their own line any faster.
FIELD_VALUE_QUOTE_LIMIT = 60

#: What a field declaration may FOLLOW on its line, and the whole of what
#: separates a declaration from a mention. A field opens the line (modulo list,
#: bold and backtick markers), follows a composition separator, or opens a new
#: sentence — those three are how every composed chunk header in this repo is
#: written. Anything else in front of the marker is a sentence *about* the
#: field: `- **Notes:** the old reader took **Type:** anything as a value`.
#: A period after an abbreviation that never ends a sentence (`e.g.`, `i.e.`,
#: `cf.`, `viz.`) opens nothing: `(e.g. **Type:** designer-handoff)` is prose
#: quoting the field, and binding it would switch review off (#778). `etc.` is
#: left out on purpose — it does end sentences, and a composed field after one
#: must still bind.
_FIELD_DECLARATION_PREFIX_RE = re.compile(
    r"(?:^[\s\-\*`]*|[·•|]\s*"
    r"|(?<!\b[eE]\.g)(?<!\b[iI]\.e)(?<!\b[cC]f)(?<!\b[vV]iz)\.\s+)$"
)


def iter_field_declarations(
    line: str, token_re: "re.Pattern[str]"
) -> "Iterator[re.Match[str]]":
    """Yield the matches of ``token_re`` on ``line`` that DECLARE the field.

    Searching for a field mid-line is what makes composed headers readable, and
    the cost is that a line merely discussing the field reads as declaring it.
    That cost is not payable: a chunk field decides how much review the chunk
    gets, and `Type: designer-handoff` skips it entirely — so a sentence
    mentioning a field would switch the gate off in every governed product, with
    nothing said. Position is what separates the two, and
    ``_FIELD_DECLARATION_PREFIX_RE`` is the whole of that rule.

    It is a heuristic, and it is used only to BIND — the readers report an
    unhonourable value only from field position, where the judgement is not a
    heuristic at all.
    """
    for match in token_re.finditer(line):
        if _FIELD_DECLARATION_PREFIX_RE.search(line[: match.start()]):
            yield match


# Per-chunk Type declaration (v1.4 F6 — proportional Critic via chunk type).
# Two passes over the section, and their order is what keeps prose out of a
# gate: a value in FIELD POSITION is read first and is final, typo included;
# only a section declaring nothing there is searched at large, where an ALLOWED
# type at a declaration position is the only thing that can bind.
_BUILD_PLAN_TYPE_RE = field_token_re("Type")
_BUILD_PLAN_TYPE_VALUE_RE = field_value_re("Type")
# `trivial` is in the allowed set; it changes only the Critic's protocol (Goal
# 3 judges its `**Trivial because:**` rationale against the diff). Its stop-hook
# file-set + rationale gate was retired (#301) — a file set enforces nothing
# about triviality.
_BUILD_PLAN_ALLOWED_TYPES = frozenset(
    {"code", "doc-only", "cleanup", "designer-handoff", "cumulative-final", "trivial"}
)
#: The work types `building.md` scales governance by, and the change-log's
#: `type=` vocabulary shares two of them, so authors write them in a chunk's
#: `Type:` field meaning "this is code work". Each reads as `code`, the full
#: protocol, so an alias can never lighten a review. Rejecting them reported an
#: error on a chunk that ran as `code` anyway.
_BUILD_PLAN_TYPE_ALIASES = {
    "feature": "code",
    "bugfix": "code",
    "refactor": "code",
    "optimization": "code",
    "hotfix": "code",
    "debt-paydown": "code",
}
# Git branch/ref names (`feature/backlog-service-relayout`, `origin/develop`) are
# backticked identifiers that contain `/` but name a branch, not a file — the same
# "contains `/`, isn't a path" family as the slash-command / URL carveouts in
# `_looks_like_file_path`. A token whose first segment is one of these prefixes and
# whose final segment carries no extension is a ref to skip, not a missing file.
# `refs` is the ref NAMESPACE rather than a branch prefix — `refs/tags/v3.2.1`,
# `refs/heads/develop`, `refs/remotes/origin/main` — and a release plan backticks
# it for exactly the same reason it backticks a branch. It belongs to this set on
# the same test: it names something in git, not on disk. A repo-root directory
# literally called `refs/` would be shadowed, which is why the extension guard
# below still applies (`refs/foo.py` stays checked).
#
# #333: the original set covered git-flow only, so every consumer on
# Conventional-Commits branch naming (`feat/…`, `chore/…`) or with a dependency
# bot got a spurious BLOCKING `missing-ref:` for a branch named in plan prose —
# `missing-ref:` is BLOCKING in `skills/critic/review-protocol.md`, so this
# failed a review on the branch name itself.
#
# **The shape-rule alternative was evaluated and rejected**, though the item and
# the plan both proposed it as the better route. "A token is a path only if its
# final segment carries an extension-shaped suffix" would drop the guessing
# entirely — but it also stops verifying real extensionless paths, and this
# repo's single most-cited path is one: `plugin/bin/prawduct-hook`. Trading a
# spurious-finding class for a missed-finding class on the most-referenced file
# in the tree is the wrong direction, so the allowlist stays.
#
# **#537: it stays but stops growing.** Every entry above was a guess about
# another team's branch naming, and the set can never finish — `epic/`, `spike/`,
# `deps/`, `PROJ-123/` are all real conventions and none is here. So the primary
# question is now put to the repo instead (`_names_a_live_git_ref`), and a token
# git confirms as a ref is skipped whatever its prefix. This set is kept for the
# one case git cannot answer: a branch that has since been DELETED, which is
# every archived plan naming the branch it shipped on. That is also why a
# NEGATIVE from git is not evidence and does not narrow this set — treating
# "git has never heard of it" as "it must be a file" would redden the whole
# archive. Do not add prefixes here for a live convention; the repo answers that
# now. The remaining entries are load-bearing only for history.
_GIT_REF_PREFIXES = frozenset(
    {
        # git-flow
        "feature", "fix", "hotfix", "release", "bugfix", "support",
        # remotes and raw refs
        "origin", "upstream", "refs",
        # Conventional-Commits branch naming, as enumerated by #333. Deliberately
        # NOT `docs`, `test`, `build` or `style`: those are plausible top-level
        # DIRECTORY names, and every prefix added here stops an extensionless
        # token under it from being verified (`docs/requirements` would go
        # unchecked). The set is entries whose collision risk with a real
        # directory is near zero — `ci` and `perf` are the weakest two and are
        # here because the item named them.
        "feat", "chore", "refactor", "perf", "ci", "wip",
        # dependency bots
        "dependabot", "renovate",
    }
)

# "Carries an extension" is not "contains a dot". A version-numbered branch —
# `release/v3.2.0`, `feature/v3.2.0-c02-adapter-safety` — contains dots and is
# still a ref, so a dot-presence test makes the carveout above inert for exactly
# the branches a release cuts, and `verify-chunk-refs` then emits a BLOCKING
# `missing-ref:` for a branch named in plan prose. A file extension is short and
# alphabetic (`py`, `md`, `tsx`); the trailing dot-part of a version is not
# (`v3.2.0` -> `0`, `v3.2.0-c02-adapter-safety` -> `0-c02-adapter-safety`). Test
# the SUFFIX SHAPE so `feature/foo.py` stays checked while `release/v3.2.0` does not.
_FILE_EXTENSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,7}$")


def _has_file_extension(segment: str) -> bool:
    """True when ``segment`` ends in something shaped like a file extension.

    Requires a non-empty stem, so a dotfile (``.hidden``) is not an extension,
    and an extension-shaped suffix, so ``v3.2.0`` is not one either.
    """
    stem, dot, suffix = segment.rpartition(".")
    return bool(dot) and bool(stem) and bool(_FILE_EXTENSION_RE.match(suffix))


#: Per-repo cache of ``git for-each-ref``. **One subprocess per repo, not one
#: per token** — the classifier below is called for every backticked token in
#: every chunk of every plan a gate reads, and a `git rev-parse` per token would
#: turn one gate into hundreds of process spawns. Asking once for the whole ref
#: namespace and answering from a set is the same trade `_TRACKED_SET` makes in
#: the path-resolution test.
#:
#: Keyed by the repo path as a string, because :class:`Path` hashes by value and
#: two callers can hold different spellings of one checkout.
#:
#: Never invalidated, and that is correct for its consumers: `prawduct-hook` is a
#: short-lived CLI process, so the ref namespace cannot meaningfully change under
#: one run. A long-lived embedding that creates branches mid-process would want
#: to clear it — the tests do, which is also what makes the one-call-per-repo
#: property assertable.
_GIT_REF_NAMES_CACHE: "dict[str, frozenset[str] | None]" = {}


def _git_ref_names(project_dir: Path) -> "frozenset[str] | None":
    """Every ref name in ``project_dir``, in both spellings, or ``None``.

    ``None`` means **could not ask** — not a git checkout, git missing, or the
    call failed — and every caller must read it as "fall back to the shape
    rule", never as "there are no refs". The two are opposite verdicts about a
    token that looks like a branch, and collapsing them would make an
    unavailable git silently reclassify every branch name in every plan as a
    missing file. An empty repo genuinely with no refs returns an empty set,
    which is a real answer.

    Both ``%(refname)`` and ``%(refname:short)`` are collected because a plan
    backticks either: ``refs/tags/v3.2.1`` and ``origin/develop`` are the same
    ref written two ways, and a classifier that knew only one spelling would
    answer differently about one object.
    """
    key = str(project_dir)
    if key in _GIT_REF_NAMES_CACHE:
        return _GIT_REF_NAMES_CACHE[key]
    names: "frozenset[str] | None"
    try:
        proc = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)%09%(refname:short)"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        names = (
            frozenset(
                field
                for line in proc.stdout.splitlines()
                for field in line.split("\t")
                if field
            )
            if proc.returncode == 0
            else None
        )
    except (OSError, subprocess.SubprocessError):
        names = None
    _GIT_REF_NAMES_CACHE[key] = names
    return names


def _names_a_live_git_ref(token: str, project_dir: "Path | None") -> bool:
    """Does git say ``token`` names a ref that exists in this checkout?

    ``False`` whenever the question could not be asked — no ``project_dir``, no
    git, not a checkout — so the shape rule below stays the sole authority on
    those paths rather than a git outage changing verdicts.
    """
    if project_dir is None:
        return False
    names = _git_ref_names(project_dir)
    return names is not None and token in names


#: Per-repo cache of the ``owner/repo`` slugs this checkout's remotes point at,
#: casefolded. One subprocess per repo for the same reason as the ref cache
#: above, and never invalidated for the same reason.
_GIT_REMOTE_SLUGS_CACHE: "dict[str, frozenset[str]]" = {}


def _git_remote_slugs(project_dir: Path) -> "frozenset[str]":
    """The GitHub ``owner/repo`` of every configured remote, casefolded.

    Empty when git cannot answer. Unlike :func:`_git_ref_names` there is no
    third state to keep: the only use is to EXCUSE a token, so "could not ask"
    and "no remote" both mean "keep checking it", which is the direction this
    module fails in. A non-GitHub remote yields no slug for the same reason —
    ``parse_remote_url`` is the one parser of remote URLs, and a remote it
    cannot read leaves the token checked rather than guessed at.
    """
    key = str(project_dir)
    if key in _GIT_REMOTE_SLUGS_CACHE:
        return _GIT_REMOTE_SLUGS_CACHE[key]
    from .backlog.upstream import parse_remote_url  # noqa: PLC0415 — lazy; only a slug-shaped token pays for it

    slugs: "frozenset[str]" = frozenset()
    try:
        proc = subprocess.run(
            ["git", "config", "--get-regexp", r"^remote\..*\.url$"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            slugs = frozenset(
                slug.casefold()
                for line in proc.stdout.splitlines()
                if (slug := parse_remote_url(line.partition(" ")[2]))
            )
    except (OSError, subprocess.SubprocessError):
        pass  # empty: the token stays checked, which is this cache's fail direction
    _GIT_REMOTE_SLUGS_CACHE[key] = slugs
    return slugs


def _names_a_configured_remote(token: str, project_dir: "Path | None") -> bool:
    """Is ``token`` the ``owner/repo`` of one of this checkout's remotes?

    Asked of git rather than decided by shape: ``docs/api`` and
    ``brookstalley/prawduct`` are the same shape, and only one is a path.
    """
    if project_dir is None or token.count("/") != 1:
        return False
    return token.casefold() in _git_remote_slugs(project_dir)


def _looks_like_file_path(token: str, project_dir: "Path | None" = None) -> bool:
    """A backticked token is a precise file-path reference only when it
    contains ``/`` — i.e. the chunk author wrote a specific relative path.
    Bare filenames in prose (e.g. ``backlog.md``, ``SKILL.md``) are usually
    conceptual references whose actual location varies, so they're not
    verifiable in a useful way.

    A token anchored anywhere but the repo root is not a deliverable this
    verifier can check: an absolute path (``/usr/local/bin/lane-status``, on a
    host the plan describes), a home path (``~/testruns``), or a slash-command
    (``/prawduct:pr``), which is the same leading-``/`` shape. Resolving one
    against the repo asks about a file nobody claimed lives there.

    Glob patterns written in prose (e.g. ``docs/requirements/*.md`` in a Tests
    bullet) also contain ``/`` but name a *set*, not a literal file — a literal
    source path never contains the shell-glob metacharacters ``*``, ``?``, or
    ``[``, so a token carrying one is a glob to skip rather than a missing file
    to flag (BLD-2R9X). Sibling of the ``path::symbol`` carveout the chunk-ref
    parser applies before calling this.

    Write-target templates with angle-bracket placeholders (e.g.
    ``<target-repo>/<kebab-slug>.md``) and URLs (e.g. ``https://example.com/x``) also
    contain ``/`` but are not literal on-disk paths — a token carrying ``<``,
    ``>``, or ``://`` is a placeholder/URL to skip, not a missing file to flag
    (BLD-4K7P; same form-family as the glob carveout above).

    Issue references and anchors (e.g. ``owner/repo#12``, ``docs/api#usage``)
    contain ``/`` but the ``#`` names a location in a *tracker or document*,
    not a file — no source file this verifier could be asked about carries one.
    Excluding them is a property of the token's shape, so it belongs here
    rather than at a caller, and it is correct for every consumer: a contract
    surface with a ``#`` in it is not a path either. Sibling of the URL and
    placeholder carveouts above.

    Tokens that interpolate a variable (``${CLAUDE_SKILL_DIR}/../..``,
    ``$HOME/notes``) contain ``/`` but resolve against whatever the variable
    holds at run time, so no repo-relative answer exists for them. A literal
    source path carries no ``$``, ``{`` or ``}``. Same form-family as the
    placeholder carveout above.

    Git branch/ref names (e.g. ``feature/backlog-service-relayout``,
    ``origin/develop``, ``release/v3.2.0``) also contain ``/`` but name a branch,
    not a file — a build/release plan legitimately backticks them in prose.

    **Two answers, asked in that order (#537).** First the repo itself: when
    ``project_dir`` is given, a token that ``git for-each-ref`` reports as a
    live ref is a ref, whatever its prefix. That is the authoritative answer and
    it costs one subprocess per repo (:func:`_git_ref_names`). It is what makes
    ``epic/…``, ``spike/…``, ``deps/…`` and ``PROJ-123/…`` stop drawing a
    BLOCKING ``missing-ref:`` — none of them is in the allowlist, and no
    allowlist ever finishes, because branch-naming conventions are a property of
    the consuming team rather than of prawduct.

    Then the shape rule, as the **deleted-branch fallback**: a token whose first
    segment is in :data:`_GIT_REF_PREFIXES` and whose final segment carries no
    extension-shaped suffix (:func:`_has_file_extension`) is a ref to skip. It
    has to stay, and not only for repos with no git: an archived plan names the
    branch it was built on, that branch was merged and deleted years ago, and
    git will never confirm it again. Asking git first and *narrowing* the
    allowlist on a negative answer would therefore redden every historical plan
    in the tree — so a negative from git is not evidence, and the fallback runs
    unchanged.

    A real path keeps its extension (``feature/foo.py`` stays checked), so
    neither arm blinds the verifier to genuine missing files. Version-numbered
    branches are the case a dot-presence test gets wrong — see the note on
    ``_FILE_EXTENSION_RE``.

    A repo slug (``brookstalley/prawduct``) is path-shaped too, and is excused
    the same way a live ref is: only when git confirms it, here as the
    ``owner/repo`` of a configured remote (:func:`_names_a_configured_remote`).
    Any other slug stays checked, so ``docs/api`` is never skipped for its shape.

    ``project_dir`` is optional because :mod:`lib.risk` shares this predicate to
    classify tokens in a diff, where there is no plan and no repo question to
    ask; omitting it skips both git questions."""
    if "/" not in token:
        return False
    if token.startswith(("/", "~")):
        return False
    if any(ch in token for ch in "*?["):
        return False
    if "<" in token or ">" in token:
        return False
    if any(ch in token for ch in "${}"):
        return False
    if "://" in token:
        return False
    if "#" in token:
        return False
    if _names_a_live_git_ref(token, project_dir):
        return False
    if _names_a_configured_remote(token, project_dir):
        return False
    first, _, rest = token.partition("/")
    if first in _GIT_REF_PREFIXES and not _has_file_extension(rest.rsplit("/", 1)[-1]):
        return False
    return True


# =============================================================================
# Instruction-bearing reference FORMS (#552)
# =============================================================================
#
# Extraction by SHAPE — every backticked token that looks like a path — cannot
# tell a path a reader is told to *use* from one the prose is *talking about*.
# The three forms below can, because each one unambiguously means "go read /
# run / follow this":
#
#   1. ``allowed-tools:`` front-matter grants — a grant naming a path that does
#      not exist is a permission that cannot cover the command it was written
#      for, and it fails most silently of all: nothing executes front-matter.
#   2. Command position — a backticked span, or a fenced line, whose first token
#      is an executable. The path is an argument to something a reader runs.
#   3. Markdown links — ``[text](path)``. An unambiguous pointer.
#
# **This lived only in `tests/test_path_reference_resolution.py` until #552.**
# That module shipped the form vocabulary and measured it (form-based extraction
# cut one corpus from 195 apparent failures to 6 real ones), while
# `_parse_build_plan_chunk_refs` — the extractor wired to a BLOCKING gate — kept
# reading by shape. Two extractors disagreeing about one tree, with the naive one
# holding the veto. The definition is homed here, in the library, and the test
# module imports it: the same "share the matcher AND the reader that feeds it"
# rule the norm parser had to learn one module over.

#: A skill reads the plugin through its own directory: ``${CLAUDE_SKILL_DIR}``
#: expands at skill load and the plugin root is one directory pair above it.
#: That form replaced ``${CLAUDE_PLUGIN_ROOT}``, which does not expand in prose,
#: and in doing so the reads fell out of every check that could see them.
#: Normalizing the prefix hands them to the resolver that owns path references.
_SKILL_DIR_PREFIX_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/(?:\.\./)+")

#: Executables whose arguments are paths a reader will run against this tree.
_COMMAND_HEAD_RE = re.compile(
    r"^(?:\$\s+)?(?:python3?|prawduct-hook|pytest|bash|sh|cat|less|grep|rg|ls|chmod)\b"
)
_REF_PATH_SHAPED_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+$")
_REF_HAS_EXTENSION_RE = re.compile(r"\.(?:py|md|sh|json|yaml|yml|toml|jsonl)$")
_BACKTICKED_SPAN_RE = re.compile(r"`([^`\n]{3,300})`")
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---", re.S)
_ALLOWED_TOOLS_RE = re.compile(r"^allowed-tools:(.*)$", re.M)

#: Forms that INVOKE a path rather than name it. A reader executing a command
#: runs it from a working directory, so the ``plugin/`` root fallback a *naming*
#: reference is entitled to is denied to these — that fallback is what hides a
#: ``bin/prawduct-hook`` relocation behind ``plugin/bin/prawduct-hook``.
INVOCATION_FORMS = frozenset({"command", "allowed-tools"})

#: Directory vocabulary of a prawduct-shaped source tree, INCLUDING directories
#: that no longer exist (``tools/``, ``agents/``, a repo-root ``bin/``).
#: Deliberately explicit rather than derived from the current tree: a derived set
#: can only name directories that still exist, and the defect class this catches
#: is a reference to one that was REMOVED. ``bin/prawduct-hook`` is
#: extensionless and lives under a root ``bin/`` that is now ``plugin/bin/``, so
#: neither the extension rule nor a derived-directory rule would see it.
_SOURCE_DIR_SEGMENTS = frozenset(
    {
        "plugin", "bin", "lib", "tests", "docs", "skills", "methodology",
        "templates", "hooks", "documentation", "tools", "agents",
        ".prawduct", ".claude", ".claude-plugin",
    }
)


def normalize_skill_relative(token: str) -> str:
    """Rewrite a skill-dir-relative read as the repo path it names."""
    return _SKILL_DIR_PREFIX_RE.sub("plugin/", token)


def strip_reference(raw: str) -> str:
    """Trim trailing prose punctuation, a line-number suffix, and an anchor."""
    ref = normalize_skill_relative(raw).rstrip(".,;:)`").rstrip("/")
    ref = ref.split("#", 1)[0]
    return re.sub(r":\d+(?:[,-]\d+)*$", "", ref)  # foo.py:182 and foo.md:58-60


def is_repo_path_token(token: str) -> bool:
    """Path-shaped and plausibly naming something in a prawduct-shaped tree.

    The extension branch catches ``tools/prawduct-sync.py``; the directory
    branch catches extensionless ``plugin/bin/prawduct-hook``. Together they
    exclude ``owner/repo`` arguments, which are path-shaped, appear in command
    position after ``--repo``, and name nothing on disk.
    """
    token = normalize_skill_relative(token)
    if not _REF_PATH_SHAPED_RE.match(token):
        return False
    return bool(_REF_HAS_EXTENSION_RE.search(strip_reference(token))) or (
        token.split("/", 1)[0] in _SOURCE_DIR_SEGMENTS
    )


def _fenced_command_lines(text: str) -> list[str]:
    """Lines inside fenced blocks that begin with a known executable.

    A shell block is command position just as much as an inline span, and it is
    where multi-line setup instructions live.
    """
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and _COMMAND_HEAD_RE.match(line.strip()):
            lines.append(line.strip())
    return lines


def _strip_code(text: str) -> str:
    """Remove fenced blocks and inline code spans.

    A markdown link *inside backticks* is being quoted, not offered — a plan
    that quotes a broken ``[the rules](../.claude/rules/learnings/core.md)`` as
    evidence would redden on the document specifying it. Same
    citation-versus-reference rule as for bare paths, applied to the link form.
    """
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", " ", text)


def instruction_references(text: str) -> list[tuple[str, str]]:
    """Every instruction-bearing path reference in ``text``, as ``(form, raw)``.

    A bare backticked path inside a sentence is a *citation* and is deliberately
    not returned. That omission is the whole point of the function: it is what
    separates "the reader is told to use this" from "the prose is discussing
    this", and no amount of allowlisting recovers the distinction after the fact.
    """
    found: list[tuple[str, str]] = []

    front_matter = _FRONT_MATTER_RE.match(text)
    if front_matter:
        for grant_line in _ALLOWED_TOOLS_RE.findall(front_matter.group(1)):
            for token in re.findall(r"[A-Za-z0-9_./-]+", grant_line):
                # Same predicate as command position, and for the same reason
                # `is_repo_path_token` was written: `owner/repo` arguments are
                # path-shaped and name nothing on disk.
                if is_repo_path_token(token):
                    found.append(("allowed-tools", token))

    for span in list(_BACKTICKED_SPAN_RE.findall(text)) + _fenced_command_lines(text):
        span = span.strip()
        if not _COMMAND_HEAD_RE.match(span):
            continue
        for token in span.split()[1:]:
            if is_repo_path_token(token):
                found.append(("command", token))

    for target in _MD_LINK_RE.findall(_strip_code(text)):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not _REF_HAS_EXTENSION_RE.search(target.split("#", 1)[0]):
            continue  # section links and bare anchors are not file references
        found.append(("md-link", target))

    return found


def _ref_path_part(token: str) -> str:
    """Reduce a backticked ref token to the file path that gets existence-checked.

    Two suffix forms name a location *inside* a file rather than a different
    file, so both are stripped before the check:

    - ``path::symbol`` (e.g. ``lib/plan_index.py::build_scope_to_plan_map``) —
      verified by its file half; symbol verification stays deferred.
    - ``path:line`` / ``path:line-range`` (e.g. ``lib/critic_mode.py:452``,
      ``lib/foo.py:5-8``) — a code-location citation. Without this the whole
      ``path:line`` string is existence-checked literally and a present file
      reports as a missing ref.

    Order matters: the ``::`` split runs first, so a symbol that happens to end
    in digits (``lib/foo.py::rule42``) is discarded with the rest of the symbol
    half rather than being mistaken for a line number.
    """
    path_part = token.split("::", 1)[0]
    return _BUILD_PLAN_LINE_SUFFIX_RE.sub("", path_part)


class ChunkSection(NamedTuple):
    """The result of one chunk-section walk — THREE states, not two.

    ``found`` / ``lines`` are the answer; ``unparsed`` is why an answer may be
    worth nothing. A two-state return is what let this walk fail silently: an
    unparseable heading yields ``found=False`` with an empty ``lines``, which is
    the same shape a plan that simply has no such chunk produces, and empty
    reads downstream as "nothing to check."

    ``unparsed`` names every heading-position chunk announcement in the WHOLE
    plan that :data:`_CHUNK_HEADING_RE` rejected, as ``[(line_num, text), ...]``
    — not only the ones near the requested chunk, because the damage is not
    local. A heading that does not match also does not TERMINATE the preceding
    section, so the chunk before it absorbs its body and answers a deliverable
    check with a confident, non-empty, wrong set. That failure lands on a
    different, perfectly parseable chunk than the malformed one, so a signal
    raised only at the malformed chunk's own lookup would never reach it.

    Hence the plan-level rule, the same one ``plan_status.chunk_states``
    applies (a rejected heading is an open entry of its own): a plan whose
    chunk boundaries cannot all be read is not evidence about any of its
    chunks. A plan with no chunk headings at all leaves ``unparsed`` empty
    and stays quiet — that is an absence, not a check that failed, and the two
    must not collapse into one signal.
    """

    found: bool
    lines: list[tuple[int, str]]
    unparsed: list[tuple[int, str]]


#: The marker :func:`unparsed_chunk_heading_reason` stamps on its prose so a
#: consumer can recognize it without matching a sentence. The reason text is
#: long, narrative and rewritten whenever the parser's advice improves; a reader
#: that greps a phrase out of it goes silently dead on the first reword, and the
#: only session-end surfacing of an unparseable plan heading is what goes quiet.
#: Producer-owned by construction: the string a consumer tests for is the string
#: this module writes, so the two cannot drift apart.
UNPARSED_HEADING_MARKER = "unparseable-chunk-heading"


#: The prefix :func:`chunk_type` stamps on an unrecognized ``Type:`` value. Same
#: rule, same reason, and it is a constant for the same one: the sentence after
#: it names the allowed values and will grow as they do.
UNKNOWN_TYPE_PREFIX = "unknown type:"


def is_unparsed_heading_error(reason: str | None) -> bool:
    """Whether ``reason`` is :func:`unparsed_chunk_heading_reason`'s output.

    The predicate rather than the marker is the export callers should reach for:
    it keeps *how* the reason is recognized on this side of the boundary, so a
    future change of mechanism (a marker, a prefix, a structured error) touches
    one function instead of every consumer.
    """
    return bool(reason) and UNPARSED_HEADING_MARKER in reason


def is_reportable_type_error(reason: str | None) -> bool:
    """Whether a ``Type:`` read's error is one a session-end surface should show.

    Both members of the class in one predicate, because they are one question —
    *did the plan's own text defeat the parser in a way an author can fix?* — and
    a caller asking it twice is a caller that can come to answer it once.
    """
    return bool(reason) and (
        reason.startswith(UNKNOWN_TYPE_PREFIX) or is_unparsed_heading_error(reason)
    )


def unparsed_chunk_heading_reason(section: ChunkSection) -> str | None:
    """Prose for a caller to report ``section``'s unparseable headings, or
    ``None`` when every chunk heading in the plan parsed.

    The reason names lines, because the remedy is an edit to one of them and a
    reader who cannot find the offending heading cannot make it. Callers append
    this to their own "could not verify" message rather than replacing it: which
    chunk was asked for is still the first thing to say.
    """
    if not section.unparsed:
        return None
    shown = "; ".join(f"line {num}: {text!r}" for num, text in section.unparsed[:3])
    if len(section.unparsed) > 3:
        shown += f"; …and {len(section.unparsed) - 3} more"
    return (
        f"{UNPARSED_HEADING_MARKER}: {len(section.unparsed)} chunk heading(s) in this "
        f"plan announce a chunk but do not parse as one ({shown}) — an unparseable "
        "heading also fails to close the section before it, so no chunk boundary in "
        "this plan can be trusted"
    )


def chunk_section_gap(chunk_id: str, section: ChunkSection) -> str | None:
    """Why ``section`` cannot answer about ``chunk_id``, or ``None`` when it can.

    **The one gate every consumer of the walk goes through**, so that a reader
    added later inherits the refusal instead of having to remember it. Three
    outcomes, and the first two must not share a sentence:

    - **Not located, plan reads cleanly** → the plan genuinely has no such
      chunk. That is the plan's answer, and it names no line to go fix.
    - **Not located, plan has unreadable headings** → the chunk may well be
      there, under a heading nothing can parse. The remedy is an edit to a named
      line, so the reason names it.
    - **Located, plan has unreadable headings** → refused anyway, and this is
      the case worth the words. A heading that does not parse does not close the
      section before it either, so the section that *did* resolve runs on
      through its neighbour's body and answers with a confident, non-empty,
      wrong set — a deliverable check that verifies another chunk's files and
      passes, a ``Type:`` read off a declaration written
      for different work.
    """
    unparsed = unparsed_chunk_heading_reason(section)
    if not section.found:
        base = f"chunk {chunk_id!r} not found in build-plan"
        return f"{base} — {unparsed}" if unparsed else base
    if unparsed:
        return (
            f"chunk {chunk_id!r} resolved, but its boundaries are not trustworthy: "
            f"{unparsed}"
        )
    return None


def plan_has_parseable_chunk_heading(plan_path: "Path | None") -> "bool | None":
    """Whether ``plan_path`` exposes at least one ``### Chunk NN:`` heading.

    ``None`` when the plan is absent or unreadable — a third answer, and it
    earns its keep: "has no headings" and "could not look" prescribe different
    things, and a caller collapsing them reports a confident structural verdict
    about a file it never opened.

    Chunk sections are located BY heading, so a plan exposing none has nothing
    for the deliverable check to grade — and that check answers with a null
    count rather than a complaint, which is why two independent readers ask this
    question and why it lives here rather than in either of them.
    """
    if plan_path is None or not plan_path.is_file():
        return None
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return any(_CHUNK_HEADING_RE.match(line.strip()) for line in content.splitlines())


def _plan_gaps(plan_path: Path, artifacts_dir: Path) -> list[str]:
    """The gap sentences for one plan file. See :func:`deliverable_check_gaps`.

    An unreadable plan is REPORTED, not swallowed. An earlier version returned
    ``[]`` for it on the reasoning that ``plan_index.unreadable_candidates``
    already covers the case — which is true of the doctor (its only caller,
    ``lifecycle_repair``) and false of this channel: nothing on the dispatch
    path calls it, so an undecodable plan under ``artifacts/`` was reported to
    the operator by no one at all. Reporting the *fault* is not the same as
    guessing at the structure of content never read; the sentence claims only
    that the file could not be opened.

    Paths are rendered by :func:`plan_index.display_path`, never ``Path.name``:
    recursive discovery makes ``build-plan.md`` a near-certain collision across
    ``plans/<id>/`` directories, and naming two of them identically tells an
    operator nothing about which to fix.
    """

    if not plan_path.is_file():
        return []
    shown = plan_index.display_path(plan_path, artifacts_dir)
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [
            f"{shown} could not be read ({exc.__class__.__name__}), so no review "
            "can resolve it and the chunk deliverable check cannot grade it. "
            "Nothing else on the dispatch path reports this"
        ]

    gaps: list[str] = []
    declared, _value = plan_index.parse_build_plan_frontmatter_scope(content)
    if not declared:
        gaps.append(
            f"{shown} declares no frontmatter `scope:`, so no review can "
            "resolve it by scope and the chunk deliverable check reports "
            "`unchecked` for the life of the plan — which reads as a pass. Add "
            "`scope: <change-log scope tag>` to its frontmatter"
        )
    if not any(
        _CHUNK_HEADING_RE.match(line.strip()) for line in content.splitlines()
    ):  # same predicate as `plan_has_parseable_chunk_heading`, on content already read
        gaps.append(
            f"{shown} exposes no parseable chunk heading, so there is "
            "nothing for the deliverable check to grade and it reports NOTHING "
            "— not even `unchecked`. Chunks must be `### Chunk NN: Name` "
            "headings; list items under a `## Chunks` section match no heading "
            "pattern and are invisible to every plan reader"
        )
    return gaps


def deliverable_check_gaps(
    prawduct_dir: Path, resolved_plan: "Path | None"
) -> list[str]:
    """Why the chunk deliverable check will not grade this review's plan.

    **Asked at DISPATCH, answered before a review runs.** Two conditions disable
    the check for the whole life of a plan, and neither is visible where it
    happens: a missing frontmatter ``scope:`` surfaces as
    ``chunk-ref-missing unchecked — …`` buried in the dispatch manifest, where
    ``unchecked`` reads as a pass to anyone who does not also read the caveat;
    chunks written as list items surface as nothing at all, because such a plan
    yields no offending line to name. The only existing signal is
    ``check-releasability``'s "release-pending scope has no build-plan file",
    which fires at RELEASE — long after authoring, and long after the reviews
    that ran blind.

    **Falls back to scanning when nothing resolved, and that is the main case.**
    Asking the resolver for the plan and checking only what comes back misses the
    defect entirely: a plan declaring neither ``scope:`` nor ``branch:`` does not
    resolve *because of* the very gap being reported, so the resolver returns
    ``None`` and the check goes quiet exactly where it is needed. When no plan
    resolved, every live plan file is examined instead and its gaps reported with
    the file named — an unresolved plan that is also unparseable is the whole of
    #642's first route, and it must not depend on being found first.

    Returned as finished sentences rather than flags: the caller prints them, and
    the remedy is three lines of plan frontmatter either way. Empty list = the
    check has a subject, or there is no plan at all (an absence the resolver
    already reports, and this must not complain about twice).
    """
    if resolved_plan is not None:
        return _plan_gaps(resolved_plan, prawduct_dir / "artifacts")
    # Discovery goes through `plan_index`, which owns the rule — recursive, and
    # never descending an `archive` subtree. A flat glob of `artifacts/*.md` was
    # wrong on both axes for a repo laying plans out as
    # `artifacts/plans/<id>/build-plan.md`, and wrong on the path this function's
    # own docstring calls the main case. `iter_live_plan_files`, not
    # `iter_scoped_plan_candidates`: the latter yields plans that DECLARE a
    # scope, which is exactly what a plan missing one cannot do.
    #
    # UNIONED with :func:`plans_missing_scope`, because the two answer "is this a
    # plan" differently: `iter_live_plan_files` goes by declared type or the
    # `build-plan` filename, while `has_build_plan_shape` also counts a `## Status`
    # section or a chunk announcement. A plan only the second recognizes — a
    # roster-only `waiver-pragma-plan.md` — is exactly the scope-less plan this
    # channel is the dispatch-time home for, and every other surface names it.
    gaps: list[str] = []
    artifacts = prawduct_dir / "artifacts"
    candidates = {
        path.resolve(): path
        for path in (
            *plan_index.iter_live_plan_files(artifacts),
            *plans_missing_scope(artifacts),
        )
    }
    for candidate in sorted(candidates.values()):
        gaps.extend(_plan_gaps(candidate, artifacts))
    return gaps


def _unparsed_chunk_headings(content: str) -> list[tuple[int, str]]:
    """Heading lines that announce a chunk but that the chunk matcher rejects.

    Fenced spans are skipped: a plan that documents the heading forms in a
    ``text`` block is describing them, not declaring chunks, and such a line
    cannot bleed anyway — the walk drops fenced lines from every section body.
    """
    found: list[tuple[int, str]] = []
    in_fence = False
    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _CHUNK_ANNOUNCE_RE.match(stripped) and not _CHUNK_HEADING_RE.match(stripped):
            found.append((line_num, stripped))
    return found


def _chunk_section_lines(content: str, chunk_id: str) -> ChunkSection:
    """Locate the ``Chunk <chunk_id>`` section and return its body lines.

    The one canonical chunk-section walk: name-anchored with leading-zero
    tolerance (``"02"`` matches ``### Chunk 2:`` and vice versa), matches every
    supported heading form (``### Chunk NN: Name``, ``## Chunk N (ID) — Name``,
    ``### **Chunk A** — Name``, dotted ids and a leading checkbox — see
    ``_CHUNK_HEADING_RE``), stops at the next sibling chunk heading or a
    non-chunk ``## `` heading, and drops fenced code blocks (project-structure
    diagrams aren't load-bearing prose). Line numbers in the returned
    :class:`ChunkSection` are 1-based into ``content``. This skeleton was
    previously copied in the three chunk-field parsers below and
    ``lib.critic_mode``'s ``**Critic mode:**`` reader; all four now fold onto it.

    Returns a :class:`ChunkSection`, whose docstring carries the contract every
    caller owes the third field.
    """
    target = _normalize_chunk_id(chunk_id)
    in_section = False
    in_fence = False
    section_lines: list[tuple[int, str]] = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        heading = _CHUNK_HEADING_RE.match(stripped)
        if heading:
            head_norm = _normalize_chunk_id(heading.group(1))
            if in_section:
                # Entered a sibling chunk; stop accumulating.
                break
            if head_norm == target:
                in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("## "):
            # Left the Build Chunks section entirely (a non-chunk H2).
            break
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        section_lines.append((line_num, line))
    return ChunkSection(in_section, section_lines, _unparsed_chunk_headings(content))


def _normalize_chunk_id(chunk_id: str) -> str:
    """Chunk id reduced to its comparable form — label stripped, zeros trimmed.

    Accepts the string a plan's own heading prints (``Chunk 01``) as well as the
    bare id the matchers capture. That widening lived inline in the section walk
    for one commit, which left the completed-chunk join (now `_chunk_is_done`) comparing a label
    against bare ids: the membership test could never be true, so a completed
    chunk's forward-ref exemption never expired and the deliverable check
    reported zero refs while claiming it ran.

    **The only chunk-id normalizer in the tree.** A stronger one — casefolding
    and unifying ``_``/``-`` — lived in the derived-view module and went with it,
    which settles a difference this docstring used to have to warn about: the two
    disagreed on ``Chunk_A`` vs ``Chunk-A``, contained only because each was
    applied to both sides of a comparison within its own module. Nothing here
    grew to cover the retired one's extra folding, because nothing asked for it;
    if a caller ever needs case- or separator-insensitive matching, widen this
    one rather than adding a second.

    **Total on the dotted grammar, which it was not when that grammar widened.**
    ``lstrip("0")`` reads the id as one token, so ``"0.2"`` lost the leading zero
    of its FIRST component and returned ``".2"`` — truthy, so the ``or "0"`` guard
    could not fire — and the numeric sort a since-retired notice keyed on it
    evaluated ``int("")`` and raised past an except-set that did not catch it. The trim is per COMPONENT because
    that is what the grammar makes it: a normalizer written against the old
    grammar keeps typechecking against the new one and answers wrongly, which is
    why this is fixed here rather than guarded at the sort.
    """
    bare = _CHUNK_LABEL_PREFIX_RE.sub("", chunk_id.strip())
    return ".".join(part.lstrip("0") or "0" for part in bare.split("."))


#: A chunk field label: ``- **Deliverables:**``, ``**Description:**``,
#: ``1. **Done when:**``. Bounded length so a bolded sentence in prose
#: (``**This is the design point.**``) is not mistaken for one — a label is a
#: short noun phrase, and the colon is what makes it a field rather than emphasis.
_CHUNK_FIELD_LABEL_RE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?\*\*([^*:]{1,48}):\*\*|^\s*(?:[-*+]\s+|\d+[.)]\s+)?\*\*([^*:]{1,48})\*\*:"
)

#: Chunk fields whose body is narrative ABOUT the work — the citation positions.
#:
#: **This is the form-vs-shape switch (#552).** A chunk does not only DECLARE
#: paths; it also DISCUSSES them, and to a backtick scan the two are identical.
#: The reported case: a plan that enumerates broken paths *by name* as its
#: adversarial evidence was reported as eight missing deliverables — against a
#: record that is right precisely BECAUSE those paths are absent. The check is
#: mapped BLOCKING, so the only exits were to launder the record or to record a
#: deliberate departure, and a reviewer chose the second.
#:
#: A DENYLIST of prose labels rather than an allowlist of declaration labels,
#: and the corpus is why: across this repo's 97 plans the declaration labels are
#: open-ended (``Deliverables``, ``Tests``, ``Artifacts consumed``, ``Done
#: when``, ``Acceptance criteria``, and a long tail — ``Surfaces this touches``,
#: ``Delivers``, ``Deliverable files``, ``Scope — delete``), while the prose
#: labels are a small closed set dominated by ``Description``. An allowlist
#: would silently stop checking every ad-hoc declaration label an author
#: invents, which is the failure mode that matters: over-firing is visible and
#: annoying, under-firing is invisible and is what a gate exists to prevent.
#:
#: Deliberately NOT the narrower "scope extraction to Deliverables" rule an
#: earlier reading proposed and ``_LIST_ITEM_RE`` already argues against: plans
#: name load-bearing paths in Tests, Done-when, acceptance criteria and
#: Artifacts-consumed as a matter of course, and all four stay checked.
_PROSE_CHUNK_FIELDS = frozenset(
    {
        "description", "why", "context", "problem", "background", "rationale",
        "notes", "note", "the defect", "evidence", "trivial because",
        "what the user can do", "open assumptions", "risk",
    }
)


def _chunk_field_label(line: str) -> "str | None":
    """The field label this line OPENS, lowercased and de-punctuated, or ``None``."""
    match = _CHUNK_FIELD_LABEL_RE.match(line)
    if not match:
        return None
    return (match.group(1) or match.group(2)).strip().rstrip(".").lower()


def _declaration_scope_lines(
    section_lines: list[tuple[int, str]],
) -> Iterator[tuple[int, str]]:
    """A chunk's DECLARATION lines — where a backticked path names a deliverable.

    Two exclusions, and each one is a class the corpus measures:

    - **Narrative paragraphs**, i.e. anything outside a list item. This is the
      same scope :func:`_qualifier_scope_lines` applies to the ``new``
      qualifier, and for the same reason: a plan's running prose talks about
      paths, its bullets declare them.
    - **Prose-labelled fields** (:data:`_PROSE_CHUNK_FIELDS`), whose body is a
      list item and so survives the first rule. ``- **Description:**`` is where
      a chunk explains itself, quotes the defect it is fixing, and names the
      grep that found it.

    A field's scope runs from its label line to the next label line at the same
    or shallower indent, or to the end of the item — so a ``Description``
    bullet's wrapped continuations stay excluded and the ``Deliverables``
    bullet after it comes back in.
    """
    in_item = False
    prose_field = False
    for line_num, line in section_lines:
        if _LIST_ITEM_RE.match(line):
            in_item = True
            label = _chunk_field_label(line)
            if label is not None:
                prose_field = label in _PROSE_CHUNK_FIELDS
        elif not line.strip() or _PLAN_FIELD_RE.match(line):
            # A blank line, or a line starting in column 0 — either closes the
            # item. Column-0 prose is a narrative paragraph, not a wrap.
            in_item = False
            prose_field = False
        elif _chunk_field_label(line) is not None:
            # An unbulleted `**Label:**` on a continuation line still opens a field.
            prose_field = _chunk_field_label(line) in _PROSE_CHUNK_FIELDS
        if in_item and not prose_field:
            yield line_num, line


def _command_position_refs(
    section_lines: list[tuple[int, str]],
) -> dict[int, list[str]]:
    """``line -> paths`` the chunk names in COMMAND POSITION, wherever they sit.

    :func:`_declaration_scope_lines` drops a chunk's prose, which is right for
    the citations that motivated #552 and wrong for the one thing prose
    legitimately instructs with: a command a reader is told to run.
    ``- **Description:** confirm with `grep -rn installed_plugins plugin/lib/x.py``
    names a real path in a real invocation, and a relocation that stranded it
    would be a live defect the position rule alone would now miss.

    So form GRANTS what position denies — the form-vs-shape switch, in the
    direction that ADDS coverage rather than removing it.

    This is also the only place chunk-ref extraction sees a *multi-token*
    backticked span at all. ``_BUILD_PLAN_PATH_RE`` requires a whitespace-free
    span, so every path that was ever an argument to a command was invisible to
    the shape scan; making the grant a re-admission of what shape already found
    would therefore have been inert. Line numbers come from this walk rather
    than from :func:`instruction_references`, which returns none — a finding a
    reader cannot locate is barely a finding.

    Fenced blocks are walked here rather than delegated for the same reason:
    fence state is a property of the line sequence, and the shared extractor
    takes a text blob. The token predicate itself IS delegated
    (:func:`is_repo_path_token`), so the two surfaces cannot disagree about what
    counts as a path — which is the half of #552 that was actually load-bearing.

    Markdown links are deliberately NOT admitted, though
    :func:`instruction_references` yields them: every build plan under
    ``.prawduct/artifacts/`` is already swept for broken md-links by
    ``tests/test_path_reference_resolution.py``. A second owner for a covered
    form buys nothing and gives the two a way to disagree.
    """
    out: dict[int, list[str]] = {}
    in_fence = False
    for line_num, line in section_lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        spans = [stripped] if in_fence else _BACKTICKED_SPAN_RE.findall(line)
        for span in spans:
            span = span.strip()
            if not _COMMAND_HEAD_RE.match(span):
                continue
            for token in span.split()[1:]:
                if is_repo_path_token(token):
                    out.setdefault(line_num, []).append(
                        _ref_path_part(strip_reference(token))
                    )
    return out


def _qualifier_scope_lines(
    section_lines: list[tuple[int, str]],
) -> Iterator[tuple[int, str]]:
    """A chunk's LIST-ITEM lines, **wrapped continuations included** — where a
    ``new `path`` declaration counts.

    See ``_LIST_ITEM_RE`` for why this is list items rather than the
    Deliverables block the item prescribed, and why a per-line test is wrong.
    Narrative paragraphs are excluded, which is where the adjectival ``new``
    that motivated #224(b) lives.
    """
    in_item = False
    for line_num, line in section_lines:
        if _LIST_ITEM_RE.match(line):
            in_item = True
        elif not line.strip() or _PLAN_FIELD_RE.match(line):
            # A blank line, or a line starting in column 0 — either closes the
            # item. Column-0 prose is a narrative paragraph, not a wrap: this
            # repo indents continuations.
            in_item = False
        if in_item:
            yield line_num, line


def _chunk_is_done(
    plan_path: Path, chunk_id: str, project_dir: Path, facts: "dict | None"
) -> bool:
    """Whether ``plan_status.chunk_states`` reads ``chunk_id`` of this plan ``done``.

    ``facts`` is an ``evidence.read_facts`` result the caller already holds, or
    ``None`` to read the store here. Imported lazily: ``plan_status`` imports
    this module.
    """
    from . import evidence, plan_status  # noqa: PLC0415 — plan_status imports this module

    if facts is None:
        facts = evidence.read_facts(project_dir)
    target = _normalize_chunk_id(chunk_id)
    states = plan_status.chunk_states(plan_path, facts, repo_dir=project_dir)
    return any(
        st.state == "done" and not st.synthetic and _normalize_chunk_id(cid) == target
        for cid, st in states.items()
    )


def _parse_build_plan_chunk_refs(
    prawduct_dir: Path,
    chunk_id: str,
    plan_path: "Path | None" = None,
    *,
    facts: "dict | None" = None,
) -> dict:
    """Extract a chunk's DECLARED file-path references from its section
    in ``.prawduct/artifacts/build-plan.md``.

    **Declared, not merely mentioned (#552).** A chunk does not only name the
    paths it is responsible for; it also *discusses* paths — the defect it is
    fixing, the grep that found it, a fixture string, a path that is broken and
    whose brokenness is the point being recorded. To a backtick scan those are
    indistinguishable, and this extractor used to treat them alike: one plan
    that enumerated broken paths by name as its adversarial evidence drew eight
    BLOCKING ``chunk-ref-missing`` findings against a record that was correct.
    The only exits were to launder the record or to record a departure.

    Position decides, and form overrides:

    - :func:`_declaration_scope_lines` yields the declaration positions — list
      items outside a prose-labelled field. A chunk's ``Deliverables``,
      ``Tests``, ``Artifacts consumed``, ``Done when`` and ``Acceptance
      criteria`` bullets all stay checked; its ``Description`` bullet and its
      running paragraphs do not.
    - :func:`_command_position_refs` admits anything the chunk puts in
      *command position* wherever it sits, because that is prose instructing
      rather than prose discussing. That arm ADDS coverage: a multi-token
      backticked span was invisible to the shape scan, so a path passed as a
      command argument had never been checked at all.

    That switch is the same one ``tests/test_path_reference_resolution.py``
    makes repo-wide, and the extractor it makes it with now lives in this
    module (:func:`instruction_references`) rather than in that test — two
    extractors disagreeing about one tree, with the naive one wired to the
    BLOCKING gate, is what #552 reported.

    ``plan_path`` names the plan to read; it defaults to this repo's active
    build plan, which is right for ``verify-chunk-refs`` (a repo-level question)
    and wrong for a review (a question about the plan the DISPATCH named). The
    review path passes :func:`resolve_reviewed_plan`'s answer.

    The section is located by ``_chunk_section_lines`` (both the ``### Chunk NN:``
    and ``## Chunk N (ID) — Name`` heading forms, leading zeros tolerant), and
    parsing stops at the next sibling chunk heading or a non-chunk ``## `` heading
    — sibling chunks' refs are NOT returned. Fenced code blocks (```...```)
    are skipped because project-structure diagrams aren't load-bearing prose.
    A path declared with the ``new`` qualifier anywhere in the chunk is skipped
    for the whole section — it's a file the chunk creates rather than modifies,
    and re-naming it in a later Done-when step doesn't make it exist yet — until
    the chunk is ``done`` (``plan_status``; ``facts`` is the store the caller
    already read, else it is read here).

    Returns ``{"file_paths": [{"line_num": int, "ref": str}, ...],
    "error": str | None}``. The stored ``ref`` is the path half of the token as
    reduced by ``_ref_path_part`` — any ``::symbol`` or ``:line`` suffix is
    dropped, so a missing-ref message names the file rather than the citation.
    Symbol and backlog-ID verification remain deferred.

    A line carrying ``prawduct:allow prawduct/chunk-ref-missing -- <reason>``
    (or the same pragma on the line above) contributes no refs. It was the only
    escape for prose that *discusses* a path rather than declaring it; the
    position rule above now handles that case structurally, so the waiver is
    left for the residue — a citation inside a declaration bullet, where no
    positional rule can help and a human reason is the honest answer. It needs
    that reason like every other waiver, and the Critic checks it is legitimate.
    """
    result: dict = {"file_paths": [], "error": None}
    if plan_path is None:
        plan_path = _bound_plan_path(prawduct_dir.parent)
    if plan_path is None:
        result["error"] = "missing build-plan: no build plan governs this branch"
        return result
    if not plan_path.is_file():
        result["error"] = f"missing build-plan: {plan_path}"
        return result
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        result["error"] = f"unreadable build-plan: {exc}"
        return result

    # The repo the plan lives in, for the git-ref classifier (#537). Derived
    # rather than passed: every caller already hands this function the
    # `.prawduct` dir, and threading a second, redundant argument through three
    # call sites to say the same thing twice is how the two get to disagree.
    project_dir = prawduct_dir.parent

    section = _chunk_section_lines(content, chunk_id)
    gap = chunk_section_gap(chunk_id, section)
    if gap:
        result["error"] = gap
        return result
    section_lines = section.lines

    # A path the chunk declares with the `new ` qualifier is a forward reference
    # for the WHOLE chunk section, not just the occurrence carrying the word.
    # Chunks routinely declare `new `path`` on Deliverables and then name the
    # same path again in a Done-when step; keying the exemption to that one
    # occurrence made every re-reference a false missing-ref. Normalized the same
    # way as the tokens below so a `new `path`` declaration also exempts a later
    # `path:42` citation of it.
    #
    # Scoped to list items (#224b) — see `_LIST_ITEM_RE` for why not Deliverables.
    forward_refs: set[str] = {
        _ref_path_part(m.group(1))
        for _, section_line in _qualifier_scope_lines(section_lines)
        for m in _BUILD_PLAN_NEW_QUALIFIER_RE.finditer(section_line)
    }
    # #224(a): the exemption EXPIRES when the chunk completes. `new `path`` says
    # "this chunk will create it" — once the chunk is done, a file that still
    # does not exist is a real missing ref, and the un-expiring exemption meant a
    # chunk could claim to create a file, not create it, and never be caught.
    #
    # Done is `plan_status.chunk_states`' answer (#1051), never a box read here.
    # What it cannot read it leaves `open`, which keeps every exemption —
    # failing TOWARD the exemption, because a false missing-ref fires on every
    # review of an in-progress chunk while a missed one surfaces at the next
    # verify. A `dropped` chunk keeps its exemptions too: it created nothing.
    if _chunk_is_done(plan_path, chunk_id, project_dir, facts):
        forward_refs = set()

    # Paths this chunk declares it REMOVES — satisfied by absence. Same list-item
    # scoping as `new` above and for the same reason: the declaration routinely
    # lands on a wrapped continuation line. See `_BUILD_PLAN_GONE_QUALIFIER_RE`
    # for why this is an explicit qualifier and why it never expires.
    gone_refs: set[str] = {
        _ref_path_part(m.group(1) or m.group(2))
        for _, section_line in _qualifier_scope_lines(section_lines)
        for m in _BUILD_PLAN_GONE_QUALIFIER_RE.finditer(section_line)
    }

    # The declaration positions, plus what command position grants back.
    # `granted` is computed over the WHOLE section (prose included) because that
    # is exactly the text position dropped and form is entitled to recover.
    declaration_lines = {line_num for line_num, _ in _declaration_scope_lines(section_lines)}
    granted = _command_position_refs(section_lines)

    seen: set[tuple[str, int]] = set()
    # Waiver lookup needs the line ABOVE as well as the line itself (both
    # placements are supported — `waivers.waives`), and a plan puts the pragma
    # above far more often than beside: the path usually sits mid-sentence in
    # wrapped prose, where a trailing comment would land on whichever line the
    # wrap happened to end on.
    section_texts = [text for _, text in section_lines]
    for index, (line_num, line) in enumerate(section_lines):
        # A chunk body does not only DECLARE paths — it also DISCUSSES them, and
        # the two are indistinguishable to a backtick scan. The case that forced
        # this: a carried-in review observation naming the path a past defect was
        # about (`plugin/tests`, a scan root that never existed on any branch).
        # The prose is correct precisely BECAUSE the path is missing, so the
        # check fires forever and the only ways out are to launder the record to
        # satisfy the linter or to leave a permanent blocking finding.
        #
        # The exemption is the repo's ordinary waiver pragma (`docs/waivers.md`)
        # rather than a new rule of its own: it demands a reason, it is visible
        # to the next reader at the line it applies to, the Critic verifies each
        # one is legitimate, and a reason-less waiver still fires. Deliberately
        # NOT solved by scoping extraction to `**Deliverables:**` — a chunk names
        # load-bearing paths in Tests, Done-when and Artifacts-consumed too, and
        # narrowing the scan would stop checking them to silence prose.
        if waivers.waives(section_texts, index, "prawduct/chunk-ref-missing"):
            continue
        # Two admission routes, one dedupe. Shape locates a declaration; form
        # locates an invocation. A path admitted by either is checked once.
        candidates = list(granted.get(line_num, ()))
        if line_num in declaration_lines:
            candidates += [
                _ref_path_part(match.group(1))
                for match in _BUILD_PLAN_PATH_RE.finditer(line)
            ]
        for path_part in candidates:
            if not _looks_like_file_path(path_part, project_dir):
                continue
            if path_part in forward_refs or path_part in gone_refs:
                continue
            key = (path_part, line_num)
            if key in seen:
                continue
            seen.add(key)
            result["file_paths"].append({"line_num": line_num, "ref": path_part})
    return result


def _parse_build_plan_chunk_type(
    prawduct_dir: Path, chunk_id: str, plan_path: "Path | None" = None
) -> tuple[str | None, str | None]:
    """Extract the `Type:` declaration from a chunk's build-plan section.

    ``plan_path`` names the plan to read, defaulting to this repo's active
    build plan. It exists so a caller that has already resolved *which plan* — via
    :func:`resolve_reviewed_plan` — reads this chunk field from the same file it
    read the others from. Two chunk-level fields resolving from two different
    plans is the same "one question, two answers" defect one field over.

    Returns ``(chunk_type, error)``. ``chunk_type`` is one of
    ``code | doc-only | cleanup | designer-handoff | cumulative-final | trivial``.
    Default (field absent) is ``code`` — fail-closed so a missing declaration
    runs the full Critic protocol rather than silently triggering a carveout
    (learnings: "escape hatches in classification create silent failures").
    Unknown values surface as ``(None, "unknown type: <value>")`` so the
    author fixes the typo instead of getting silent fall-through — but only
    from a field in FIELD POSITION. A type binds from further along its line
    too, backticked or sharing the line with the other chunk fields, provided
    it sits at a DECLARATION position (:func:`iter_field_declarations`); a
    sentence mentioning the field binds nothing and reports nothing, because
    it can neither be trusted to fail a chunk nor to lighten one.

    Section discovery is the shared ``_chunk_section_lines`` walker —
    name-anchored on ``### Chunk <chunk_id>:`` with leading-zero tolerance;
    fenced code blocks are skipped.
    """
    if plan_path is None:
        plan_path = _bound_plan_path(prawduct_dir.parent)
    if plan_path is None:
        return None, "missing build-plan: no build plan governs this branch"
    if not plan_path.is_file():
        return None, f"missing build-plan: {plan_path}"
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable build-plan: {exc}"

    # Fail-closed here means REPORTING the gap, not falling back to the `code`
    # default: that default exists for a field nobody wrote, and this is a field
    # nobody can attribute.
    section = _chunk_section_lines(content, chunk_id)
    gap = chunk_section_gap(chunk_id, section)
    if gap:
        return None, gap

    # Pass one: a value in FIELD POSITION, and its answer is final. A token no
    # type can be read out of is REPORTED here rather than defaulted — the
    # author declared an intent, and silence would spend their chunk's review
    # depth on their typo. The verbatim value is what carries: quoting the
    # readable prefix of `n/a (docs only)` names a value appearing nowhere in
    # their plan.
    declared: str | None = None
    for _line_num, line in section.lines:
        value = _BUILD_PLAN_TYPE_VALUE_RE.search(line)
        if value is None:
            continue
        # Through the predicate here too, though the line is already known to
        # open with the field: a second marker further along it —
        # `- **Type:** n/a (unlike a **Type:** doc-only chunk)` — is prose, and
        # a bare search would take it as this chunk's type.
        token = next(iter_field_declarations(line, _BUILD_PLAN_TYPE_RE), None)
        declared = (
            token.group(1)
            if token
            else value.group(1)[:FIELD_VALUE_QUOTE_LIMIT]
        )
        break

    # Pass two runs only when the section declares nothing there, and reads the
    # composed-header form (`**Depends on:** — · **Type:** code · …`). Two
    # bounds, and this field needs both: only an ALLOWED type binds, and only
    # from a DECLARATION position. Position is a heuristic, so it is spent only
    # on binding — an unreadable value out here takes the `code` default in
    # silence, exactly what it took before the field was searchable at all.
    # Without the position bound a Description sentence naming
    # `**Type:** designer-handoff` would switch the chunk's Critic gate off.
    if declared is None:
        for _line_num, line in section.lines:
            for match in iter_field_declarations(line, _BUILD_PLAN_TYPE_RE):
                if match.group(1) in _BUILD_PLAN_ALLOWED_TYPES:
                    declared = match.group(1)
                    break
            if declared is not None:
                break

    if declared is None:
        return "code", None  # fail-closed default
    declared = _BUILD_PLAN_TYPE_ALIASES.get(declared, declared)
    if declared not in _BUILD_PLAN_ALLOWED_TYPES:
        allowed = ", ".join(sorted(_BUILD_PLAN_ALLOWED_TYPES)) + (
            "; read as code: " + ", ".join(sorted(_BUILD_PLAN_TYPE_ALIASES))
        )
        return None, f"{UNKNOWN_TYPE_PREFIX} {declared!r} (allowed: {allowed})"
    return declared, None


# STH-1W5N — single source of truth for the governance-protected path bounds.
# Each entry is ``(path, is_exact, reason_label)``: a change touching ``path``
# (segment match unless ``is_exact``) edits the framework's own governance, so it
# is judgeable even when it is pure ``.md`` and may never ride a doc-only fast
# path, and a match is reported as ``"<reason_label>: <path>"``. Kept as data so
# every consumer of ``protected_path_violation`` shares one provably-identical
# list and the bound set is testable as data. (It began as the ``Type: trivial``
# file-set bound; that gate was retired, #301, and the list outlived it.)
#   skills/       — the critic/pr/etc. SKILL definitions + bundled protocols ARE
#                   the governance; editing one changes the framework itself.
#   methodology/  — the build/discovery/planning/reflection guides Claude reads
#                   as operating instructions.
#   templates/    — the artifact templates every product's specs are generated
#                   from; a silent change propagates to all downstream output.
#   agents/       — a subagent's own system prompt IS its behaviour, by exactly
#                   the argument ``skills/`` makes for fork-skill prose. The
#                   sharp case is the reviewer's: ``agents/critic-reviewer.md``
#                   decides what an independent review looks at and how hard,
#                   so an unreviewed edit there can quietly narrow every review
#                   that follows — the one file where "free to edit" compounds.
#   CLAUDE.md     — the project's top-level operating contract (exact match —
#                   a nested ``foo/CLAUDE.md`` is ordinary product doc).
#   AGENTS.md     — the same contract for every agent host: it carries the
#                   governance anchor, and CLAUDE.md imports it, so an unreviewed
#                   edit here changes what every session is told (exact match).
_GOVERNANCE_PROTECTED_PATHS: frozenset[tuple[str, bool, str]] = frozenset({
    ("skills/", False, "skill-file-edited"),
    ("methodology/", False, "methodology-edited"),
    ("templates/", False, "template-edited"),
    ("agents/", False, "agent-file-edited"),
    ("CLAUDE.md", True, "claude-md-edited"),
    ("AGENTS.md", True, "agents-md-edited"),
})


def protected_path_violation(path: str) -> str | None:
    """Return the violation label (``"<reason_label>: <path>"``) when *path*
    falls under a governance-protected bound (``skills/``, ``methodology/``,
    ``templates/``, ``agents/``, root ``CLAUDE.md`` or ``AGENTS.md``), else ``None``.

    Read through ``coverage_algebra.is_judgeable_path`` by the session doc-only
    classification and the PR-boundary doc-only gate (``lib/coverage.py``,
    PR-5K8D): fork-skill prose is behavioral logic in this framework, so a
    ``skills/*.md`` change must never ride a doc-only fast path past the
    reviewers.

    **Directory bounds match the path SEGMENT, not a root anchor.** They were
    root-anchored, which silently stopped matching the moment a repo kept its
    skills anywhere but the top level: every ``plugin/skills/**.md`` edit read
    as non-judgeable, so a skills-only session was classified doc-only and
    skipped the reviewers entirely — the precise inverse of what this function
    exists to guarantee, and invisible because the failure is silence.

    A segment match over-includes rather than under-includes (a product's own
    ``src/skills/`` is caught too). That is the deliberate direction: this is
    authority, and authority fails closed. The cost of a false positive is one
    session that reviews when it need not; the cost of the false negative was
    governance-protected prose shipping unreviewed. The leading ``/`` in the
    containment test keeps ``myskills/`` from matching ``skills/``."""
    for protected, is_exact, reason_label in _GOVERNANCE_PROTECTED_PATHS:
        if is_exact:
            matched = path == protected
        else:
            matched = path.startswith(protected) or f"/{protected}" in path
        if matched:
            return f"{reason_label}: {path}"
    return None


REF_ROOT_KEY = "build_plan_ref_root"


def _ref_root(project_dir: Path) -> Path | None:
    """A second root that this repo's plan refs may be written relative to,
    declared by the repo — or ``None``, which is the default everywhere.

    Some repos write plan refs relative to a subdirectory rather than the repo
    root, because that is how the paths read from inside the thing being built:
    a repo that *ships* a plugin names ``lib/gates.py`` and
    ``skills/backlog/SKILL.md``, which resolve from nowhere at the root. Those
    would otherwise report as missing deliverables.

    **The repo declares this; the verifier never infers it.** Sniffing for a
    subdirectory that "looks like" such a root — by name, or by a marker file
    inside it — silently weakens the gate for every repo whose layout happens
    to match: a genuinely missing deliverable gets resolved against an
    unrelated directory and never reported. A product that ships a plugin, an
    extension, or a bundled vendor tree is an ordinary layout, not a signal of
    intent. So the affordance is opt-in and available to any repo that wants
    it, and an absent key means the root is the only root, which is both the
    prior behaviour and the fail-closed one.

    A declared root that escapes the repo, does not exist, or is not a
    directory is ignored rather than honoured — the same fail-closed posture.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    declared = read_str_yaml_key(prawduct_dir / "project-state.yaml", REF_ROOT_KEY)
    if not declared:
        return None
    root = project_dir / declared
    try:
        root.resolve().relative_to(project_dir.resolve())
    except (ValueError, OSError):
        return None
    return root if root.is_dir() else None


def _verify_chunk_refs(project_dir: Path, refs: dict) -> list[dict]:
    """Verify each file-path ref names something that exists.

    Returns a list of ``{"kind", "ref", "line_num", "reason"}`` for missing
    entries. Empty list = all refs resolved.

    A ref resolves at the repo root or, when the repo declares one, under its
    additional ref root (:func:`_ref_root`). Anything else is
    reported. **Ambiguity is reported, not excused**: a token that is
    path-shaped but resolves nowhere gets named, even when it looks like it
    might be prose (a repo slug, a placeholder). A gate that guesses "probably
    not a file" fails open on exactly the input it exists to judge; the author
    disambiguates in the plan instead — placeholders as ``<owner>/<repo>``,
    other repositories unbackticked or as URLs, both of which this module
    already declines to treat as paths. This repo's own remotes need neither:
    git confirms those, so :func:`_looks_like_file_path` excuses them.
    """
    missing: list[dict] = []
    ref_root = _ref_root(project_dir)
    for entry in refs.get("file_paths", []):
        ref = entry["ref"]
        target = project_dir / ref
        if not target.exists():
            if ref_root is not None and (ref_root / ref).exists():
                continue
            if gitstate.git_path_is_ignored(project_dir, ref):
                # BLD-4K7P: an intentionally-gitignored managed path (e.g.
                # `.prawduct/.test-evidence.json`) is a generated/managed file,
                # legitimately absent from a fresh checkout — not a missing
                # deliverable. Skip rather than cry wolf.
                continue
            # #147: `Path.exists()` follows the link and reports False for a
            # BROKEN one, while `is_symlink()` stays True. A review dispatched
            # into a linked worktree whose `.prawduct/artifacts` is symlinked
            # back at the primary checkout hits exactly that, and "file does
            # not exist" sends the reader hunting for a deliverable that was
            # written — the path is reachable, just not from here. Same
            # verdict (it IS missing at this ref), different diagnosis.
            reason = (
                "symlink escapes the worktree"
                if target.is_symlink()
                else "file does not exist"
            )
            missing.append({
                "kind": "file_path",
                "ref": ref,
                "line_num": entry["line_num"],
                "reason": reason,
            })
    return missing
