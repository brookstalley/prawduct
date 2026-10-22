"""Post-sync advisory probe for the change-log's merge attribute.

One probe, two directions, decided by which change record the repo keeps.

In a repo still on the single-file log, it recommends ``merge=union`` for
``.prawduct/change-log.md`` when the committed log has no such gitattribute. Every
branch writes its entry at the TOP of that file, so two branches always edit the
same first lines and merging an advanced base conflicts there every single time —
in both observed forced base syncs on a consumer repo, prawduct's own record
files were 100% of the conflicts and the change-log led them. Git's ``union``
merge driver keeps both sides' lines instead of raising a conflict, which is the
shape an append-only entry log wants.

In a repo that records changes as fragments (``.prawduct/changes/``), no branch
prepends to the log, so it recommends REMOVING the attribute once no legacy entry
is release-pending (:func:`_retire_union_candidates` says why). Everything below
about advice, self-resolution and failing soft holds for both directions.

**Advisory-only, and that is a norm, not a convenience.** The plugin writes
nothing into a governed repo beyond its own ``.prawduct/`` state, the evidence
store and the named reconcile files; ``.gitattributes`` is not among them,
because unexpected framework writes to a repo's committed configuration are the
trust breach the write-set exists to prevent. So this probe RECOMMENDS the exact
line and never writes it — unlike ``gitignore_probes``, whose remedy is a
prawduct command precisely because ``.gitignore`` *is* in the reconcile set.

**Union merge is right here and is not free — say so.** The driver never
conflicts, so a genuine two-sided edit to the *same* entry survives as both
versions of the line rather than as a conflict to resolve: stamping ``release=``
on one side while the other side edits the same tag line yields two tag lines.
What it does NOT do is duplicate the entry: identical hunks are not conflicting,
so an entry that lands on both sides is kept once.

**Both halves are measured, and measuring them corrected this paragraph**
(``tests/test_gitattributes_probes.py``). It used to claim the two-tag-line shape
was surfaced downstream by ``change_log.validate_change_log_tags``. It was not:
the driver concatenates whole HUNKS, so the second version lands *after* the
first version's prose, and entry parsing stops its tag block at the first prose
line — the second version was metadata to nobody and no validator ever saw it. A
``release=`` could vanish in a merge under a caveat asserting it was caught.
Parsing now counts tag lines past the prose (``ChangeLogEntry.unconsumed_tag_lines``)
and the validator warns that they are read by nothing, which is what makes the
sentence above true rather than reassuring.

For a log whose normal traffic is "each branch prepends its own entry," that
trade is worth taking: two branches prepending tagged entries merge with each
entry's tag line still under its own header. A file with genuine concurrent
in-place edits would not want this attribute at all.

**Self-resolving, and resolution reads git's own answer.** The trigger and the
resolution are the same observable state — ``git check-attr merge`` — so adding
the line and committing it makes the probe return ``[]`` on the next sync and
``reconcile`` flips the advisory to ``resolved``. This mirrors
``gitignore_probes`` / ``upstream_probes`` (trigger and resolution are one
state), and it asks what git will actually DO in this working copy rather than
parsing ``.gitattributes``: a per-clone ``.git/info/attributes`` override
genuinely protects that clone, and the advisory store is per-clone too, so each
clone answering for itself is the honest scope.

**Fail soft, never fail silent.** Three states, not two: the attribute is
``union``, the attribute is something else, or **git could not be asked**. The
third is not evidence of the second, so it raises no advisory, returns ``None``
(could not look — an open advisory stays open rather than resolving) *and* — when the
log is committed, which is when the harm is live — prints a ``NOTE:`` naming
what went unchecked. A degraded advisory path that says nothing manufactures the
false success it exists to prevent. When git cannot be asked at all (no repo, no
git) the probe stays fully quiet: nothing there can be committed, and nothing
that cannot merge can conflict.

Registered at the composition root (``lib/probe_families.register_all``), not at
import time — the same pattern as the sibling probe modules.
"""

from __future__ import annotations

from . import gitstate
from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .change_fragments import FRAGMENT_DIR_REL
from .change_log import CHANGE_LOG_REL_PATH
from .core import log

FEATURE = "gitattributes"
PROBE_VERSION = 1

#: The line the advisory recommends, verbatim — what the operator adds to
#: ``.gitattributes``. Named once so the recommendation and its test cannot
#: drift into recommending two different lines.
UNION_MERGE_LINE = f"{CHANGE_LOG_REL_PATH} merge=union"


def probe_change_log_union_merge(state: ProjectState, codebase: Codebase):
    """Fire when the committed change-log resolves no ``merge=union`` attribute.

    Inert when the attribute is already in force (the resolved steady state),
    when the log is absent or untracked (nothing committed can conflict), and
    when git cannot answer.

    Ordered so the steady state is cheapest: an on-disk check that costs no
    subprocess, then the attribute lookup that ends it for every already-fixed
    repo, and only then the tracked check — which is needed just to tell a
    genuinely untracked log from a committed one. That is ONE git subprocess on
    the session-start hot path for a repo that has taken the advice (measured at
    ~25 ms here, which is what *any* git invocation costs — ``git rev-parse
    HEAD`` measures ~23 ms on the same clone); a firing repo pays a second, and
    is about to stop firing. Asking git is the price of not re-implementing
    attribute precedence, which is the one thing that could make this answer
    confidently wrong.
    """
    if not (codebase.root / CHANGE_LOG_REL_PATH).is_file():
        return []
    if (codebase.root / FRAGMENT_DIR_REL).is_dir():
        # A repo that records changes as fragments prepends nothing to the
        # live log, so the reason for union is gone and only its harm is left.
        return _retire_union_candidates(codebase)

    attr = gitstate.git_merge_attribute(codebase.root, CHANGE_LOG_REL_PATH)
    if attr == "union":
        return []

    tracked = gitstate.git_path_is_tracked(codebase.root, CHANGE_LOG_REL_PATH)
    if tracked is not True:
        return []

    if attr is None:
        log(
            f"NOTE: {CHANGE_LOG_REL_PATH} is committed, but git could not be asked "
            "which merge driver applies to it — this session did not check whether "
            "the log is protected against merge conflicts."
        )
        return None  # could not look — not "nothing to report" (#917)

    return [
        AdvisoryCandidate(
            type="change-log-union-merge",
            # Count- and value-independent: hashed into the advisory id, so the
            # id must not move when the log grows or when someone sets a
            # different merge driver on the way to fixing this.
            evidence=(
                f"{CHANGE_LOG_REL_PATH} is committed and git resolves no "
                "merge=union attribute for it",
            ),
            trigger_summary=(
                f"{CHANGE_LOG_REL_PATH} has no `merge=union` gitattribute — every "
                "branch prepends its entry to the same first lines, so merging an "
                "advanced base conflicts there every time; union-merge keeps both "
                "sides' entries instead"
            ),
            # Addressed to the owner because it is genuinely theirs: `.gitattributes`
            # is outside the plugin's write set, and that exclusion is part of what
            # makes running prawduct a safe trust decision. So the concrete line
            # lives here rather than in an agent field that can never act on it.
            owner_action=(
                f"Add the line `{UNION_MERGE_LINE}` to `.gitattributes` and commit it. It "
                "is one line, and it changes nothing the log says — it only stops every "
                "branch's entry from colliding on the same first lines at merge time. "
                "Prawduct never writes that file itself, which is why this one is yours."
            ),
            # Empty, deliberately. This field means "the command the runtime
            # executes", and there is none — the repair is a file edit the plugin
            # is not allowed to make. It previously held the prose above, which the
            # briefing rendered behind a literal "Run" prefix, instructing nobody.
            recommended_action="",
            alternative_actions=("/prawduct:doctor",),
            priority="info",
        )
    ]


def _retire_union_candidates(codebase: Codebase) -> list:
    """Advise removing ``merge=union`` from a log no branch prepends to any more.

    In a fragments repo the live log holds shipped history that only the size
    archive edits, by deleting blocks. Union merges deletions badly: a branch
    that moved entries out and one that did not merge back into a log holding
    them again, which is how archived entries came back with no conflict raised
    (#857). The advice waits until no legacy entry is still release-pending,
    because until then a branch may still be editing one, and it is advice only:
    ``.gitattributes`` is the owner's file, here as in the opposite direction.
    """
    attr = gitstate.git_merge_attribute(codebase.root, CHANGE_LOG_REL_PATH)
    if attr is None and gitstate.git_path_is_tracked(codebase.root, CHANGE_LOG_REL_PATH) is True:
        log(
            f"NOTE: {CHANGE_LOG_REL_PATH} is committed, but git could not be asked "
            "which merge driver applies to it — this session did not check whether "
            "a leftover merge=union could bring archived entries back."
        )
    if attr != "union":
        return []
    from . import change_log  # noqa: PLC0415 — lazy; only a fragments repo with union set gets here
    from . import release_readiness  # noqa: PLC0415 — lazy, for the same reason

    try:
        text = (codebase.root / CHANGE_LOG_REL_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if release_readiness.release_pending_scopes(change_log.parse_change_log(text)):
        return []
    return [
        AdvisoryCandidate(
            type="change-log-union-merge-retire",
            evidence=(
                f"{FRAGMENT_DIR_REL}/ records this repo's changes, no {CHANGE_LOG_REL_PATH} "
                "entry is release-pending, and git still resolves merge=union for it",
            ),
            trigger_summary=(
                f"{CHANGE_LOG_REL_PATH} still has a `merge=union` gitattribute, but this "
                "repo records changes as fragments, so no branch prepends to it any more; "
                "union now only lets merges bring archived entries back"
            ),
            owner_action=(
                f"Remove the line `{UNION_MERGE_LINE}` from `.gitattributes` and commit it. "
                "It was there because every branch prepended to the log; fragments ended "
                "that, and the archive moves that still edit the log are exactly what union "
                "merges wrongly. Prawduct never writes that file itself, which is why this "
                "one is yours."
            ),
            recommended_action="",
            alternative_actions=("/prawduct:doctor",),
            priority="info",
        )
    ]


def register() -> None:
    """Register the change-log merge-attribute probe. Idempotent (register_probe overwrites)."""
    register_probe(
        FEATURE, "change-log-union-merge", PROBE_VERSION, probe_change_log_union_merge
    )
