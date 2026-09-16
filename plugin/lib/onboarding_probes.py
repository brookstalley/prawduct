"""Post-sync advisory probe for a repo the plugin runs in but nobody onboarded.

One probe. Enabling the prawduct plugin starts its hooks immediately, and the
hooks write session state into ``.prawduct/`` — ``.session-start``,
``.session-base-tree``, ``.advisories.json``, ``.prawduct-version`` and the rest.
So the directory fills, the session banner reports a version, and advisories
appear, all before anyone has run ``/prawduct:onboard``. **Every visible signal
says installed and working**, which is why a repo can sit in this state for weeks:
there is nothing to notice.

What makes it worse than silence is that the downstream probes *do* fire there.
An un-onboarded repo trips the gitignore-contract, external-backlog and
discovery-not-captured nudges — each true, each a *consequence* of never having
onboarded, and none of them containing the word "onboard". Prawduct detects three
symptoms and never names the cause, while the visible activity reinforces the
belief that setup succeeded. This probe names the cause.

**Never onboarded vs. onboarded and drifted.** These need opposite prescriptions —
an install versus a repair — and prescribing the repair for a repo that needs the
install is the mistake this exists to stop, so the detection must not fire on
drift. The rule is **unanimous absence**: fire only when *no* trace of an
onboarding remains. Drift removes traces one at a time; it does not remove them
all at once, so a single surviving marker is proof an onboard once ran and the
repo's problem is repair (``/prawduct:doctor``), not installation.

The markers are chosen by one test — **is this written ONLY by an onboarding
path?** — which rules out most of what an onboarded repo contains:

- ``.claude/rules/learnings/core.md``, ``.prawduct/backlog.md``,
  ``change-log.md``, ``artifacts/project-preferences.md`` are all things the
  *runtime* independently asks for. The session-start hook prints a CRITICAL
  telling the agent to author ``project-preferences.md`` whenever product code
  exists; the reflection loop writes rules into ``core.md``; ``/prawduct:backlog``
  creates ``backlog.md``. All of that happens without an onboard, so counting
  their existence would blind the probe on exactly the trajectory it is built
  for.
- The committed install reference in ``.claude/settings.json`` is excluded for the
  same reason from the other direction: adding the marketplace entry and enabling
  the plugin is the *install* step the reporter performed, and it is precisely the
  state being detected — treating it as onboarding evidence would silence the
  probe on its own subject.

What survives the test is written by ``lib.init_product`` / ``lib.migrate_plugin``
and by nothing else: the ``CLAUDE.md`` governance marker (either generation), the
``distribution: plugin`` key, and the pre-2.0 sync manifest. Each is read through
the owning module's own constant rather than transcribed, so a rename tracks.

**Why it sits alongside the consequence advisories instead of suppressing them.**
Suppression was the alternative — the downstream advisories are misleading while
the cause stands — and it is rejected for three reasons. (1) The registry is
deliberately feature-agnostic and its probes are independent of one another and of
registration order (``lib.advisory_store``); a cross-family filter would introduce
exactly the coupling that design excludes, and every future probe family would
have to be audited against it. (2) The framework already has an idiom for "one
nudge at a time" — ``lib.coverage_probes`` stages layer 1 behind layer 0 by having
both evaluate a shared predicate *inside* the probes, within one family. There is
no precedent for one family silencing another, and inventing one for a nudge is
out of proportion. (3) Suppression trades a misleading briefing now for a
surprising one later: a repo that onboards would see three advisories appear at
the moment it fixed something. Ranking answers the real complaint at no structural
cost — ``urgent`` sorts this above every consequence in the briefing
(``lib.briefing`` orders urgent → warn → info), and the summary says in words that
what follows is downstream. The reader gets the cause first and the symptoms as
corroboration.

``urgent`` is this probe's own justification, not a habit: ties in the briefing's
sort break on ``triggered_at``, which is identical for everything one sync
produces, so ``warn`` could not guarantee this renders above the
``warn``-priority discovery nudge that fires beside it in the same repo. It is
also the one advisory whose subject is that governance is not installed at all —
every other nudge presumes it is — and it stops firing after a single command.

Registered at the composition root (``lib/probe_families.py``), like every sibling
probe family. Read-only and fail-soft: it executes nothing, never blocks session
start, and an unreadable file reads as "no marker" (fire), because unreadable is
not evidence that an onboard happened.
"""

from __future__ import annotations

from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import BLOCK_BEGIN, read_str_yaml_key
from .migrate_plugin import (
    ANCHOR_SENTINEL,
    DISTRIBUTION_KEY,
    DISTRIBUTION_VALUE,
    SYNC_MANIFEST,
)

FEATURE = "onboarding"
PROBE_VERSION = 1

_STATE_REL = (".prawduct", "project-state.yaml")


def _claude_md_text(root: Path) -> str:
    """``CLAUDE.md``'s text, or empty when it is absent, a directory, or not UTF-8.

    Empty means "no marker found", which fires. That is the right direction: a
    file that cannot be read is not evidence an onboard wrote to it, and the cost
    of the wrong answer here is a dismissable nudge rather than a missed install.
    """
    try:
        return (root / "CLAUDE.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def onboarding_markers(project_dir) -> list[str]:
    """Every surviving trace that an onboarding once ran here, as reader-facing text.

    Returns the empty list only for a repo no onboarding path ever touched. Each
    entry names a file and the thing found in it, so a caller can report *why* it
    concluded the repo is set up.
    """
    root = Path(project_dir)
    markers: list[str] = []

    # `distribution: plugin` — written by migrate_plugin.record_distribution, from
    # /prawduct:onboard (init_product) and /prawduct:migrate only. It is also the
    # framework's OWN "already onboarded" test (init_product.already_scaffolded,
    # migrate_plugin.already_migrated), so its absence is exactly "an onboard here
    # would still do work". It is the only marker prawduct's own checkout carries:
    # that repo IS the framework, so its CLAUDE.md holds the full methodology
    # rather than the thin anchor — which is why one marker has to suffice alone.
    if read_str_yaml_key(root.joinpath(*_STATE_REL), DISTRIBUTION_KEY) == DISTRIBUTION_VALUE:
        markers.append(f"project-state.yaml records `{DISTRIBUTION_KEY}: {DISTRIBUTION_VALUE}`")

    # The CLAUDE.md governance marker, in either generation: the plugin-era static
    # anchor (migrate_plugin.apply_claude_anchor) or the pre-2.0 file-sync block.
    # The BEGIN marker is matched on its own rather than through core.extract_block
    # because a half-written block is still proof the generator ran — well-formedness
    # is the migrator's problem, not the question being asked here.
    claude_md = _claude_md_text(root)
    if ANCHOR_SENTINEL in claude_md:
        markers.append(f"CLAUDE.md carries the {ANCHOR_SENTINEL} governance anchor")
    elif BLOCK_BEGIN in claude_md:
        markers.append("CLAUDE.md carries a pre-2.0 PRAWDUCT governance block")

    # Pre-2.0 file-sync state. A file-sync repo predates both markers above but was
    # onboarded — to the previous model — and its route is /prawduct:migrate, which
    # /prawduct:onboard forwards it to. Telling it "you never onboarded" is wrong on
    # the facts. Named directly rather than through migrate_plugin.framework_files,
    # whose `tools/lib/*.py` glob would also match a product's own tooling.
    if (root / SYNC_MANIFEST).is_file():
        markers.append(f"{SYNC_MANIFEST} is present (pre-2.0 file-sync install)")

    return markers


def never_onboarded(project_dir) -> bool:
    """True when no onboarding path has ever run in this repo."""
    return not onboarding_markers(project_dir)


def probe_never_onboarded(state: ProjectState, codebase: Codebase):
    """Fire when the plugin is running here but onboarding never ran.

    Inert the moment any onboarding marker exists — including for a repo that was
    onboarded and has since drifted, which needs a repair rather than an install.
    Evidence is fixed text carrying no path or count, so the advisory keeps one
    identity across every repo and every session until someone onboards (evidence
    is hashed into the id — ``advisory_store.compute_id``).

    Deliberately ungated on whether the repo looks like a product. The sibling
    coverage probes hold their nudges until product work exists, because they ask
    for work proportional to what is being built; this one asks for the setup step
    that should precede all of it, and delaying it until code appears reintroduces
    the window in which the repo silently looks installed.
    """
    if not never_onboarded(codebase.root):
        return []
    return [
        AdvisoryCandidate(
            type="never-onboarded",
            evidence=(
                "no artifact that /prawduct:onboard or /prawduct:migrate writes exists in this "
                "repo: CLAUDE.md carries no prawduct governance marker, project-state.yaml does "
                f"not record `{DISTRIBUTION_KEY}: {DISTRIBUTION_VALUE}`, and there is no pre-2.0 "
                "sync manifest",
                "the plugin's hooks run from the moment it is enabled and write session state "
                "into .prawduct/, so the directory fills, the banner reports a version and "
                "advisories appear — every visible signal reads as installed and working",
                "any other advisory in this briefing is downstream of this one; they are "
                "consequences of an un-onboarded repo, not independent problems to repair",
            ),
            trigger_summary=(
                "PRAWDUCT IS NOT SET UP IN THIS REPO. The plugin is enabled and its hooks are "
                "running — that is what filled .prawduct/ and produced this advisory list — but "
                "onboarding never ran, so nothing it writes is here: no governance anchor in "
                "CLAUDE.md, no `distribution: plugin` in project-state.yaml. Governance is "
                "watching a product it has never been told about. Run /prawduct:onboard to set "
                "it up; every other advisory here is a consequence of this one, so fix the cause "
                "and re-check rather than repairing each symptom."
            ),
            # The one advisory whose owner action is a genuine yes/no rather than a
            # ratification: onboarding writes into CLAUDE.md and project-state.yaml
            # in a repo that never asked for it, and a repo may legitimately have
            # the plugin enabled without wanting to be governed by it.
            owner_action=(
                "Say go and I will set this repo up: it writes a governance anchor into "
                "CLAUDE.md and a few keys into project-state.yaml, both committed files you "
                "will see a diff for. Say no if this repo is deliberately not governed — the "
                "reminder stays, but nothing else here is worth fixing until you decide, "
                "because every other advisory in this list is downstream of this one."
            ),
            recommended_action="/prawduct:onboard",
            # No alternative action, deliberately. /prawduct:doctor is the obvious
            # candidate and is the wrong prescription: it health-checks and repairs
            # an *onboarded* repo, and offering it here is the confusion between
            # repair and install that this probe exists to end. /prawduct:migrate is
            # not offered either — /prawduct:onboard routes a pre-2.0 repo there
            # itself, and this probe stays silent on those repos anyway.
            alternative_actions=(),
            priority="urgent",
        )
    ]


def register() -> None:
    """Register the never-onboarded probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, "never-onboarded", PROBE_VERSION, probe_never_onboarded)
