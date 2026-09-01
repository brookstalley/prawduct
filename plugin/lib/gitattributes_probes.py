"""Post-sync advisory probe for the change-log's merge attribute.

One probe: it recommends ``merge=union`` for ``.prawduct/change-log.md`` when the
committed log has no such gitattribute. Every branch writes its entry at the TOP
of that file, so two branches always edit the same first lines and merging an
advanced base conflicts there every single time — in both observed forced base
syncs on a consumer repo, prawduct's own record files were 100% of the conflicts
and the change-log led them. Git's ``union`` merge driver keeps both sides'
lines instead of raising a conflict, which is the shape an append-only entry log
wants.

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
third is not evidence of the second, so it raises no advisory *and* — when the
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
        return []

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
            recommended_action=f"add `{UNION_MERGE_LINE}` to .gitattributes and commit it",
            alternative_actions=("/prawduct:doctor",),
            priority="info",
        )
    ]


def register() -> None:
    """Register the change-log merge-attribute probe. Idempotent (register_probe overwrites)."""
    register_probe(
        FEATURE, "change-log-union-merge", PROBE_VERSION, probe_change_log_union_merge
    )
