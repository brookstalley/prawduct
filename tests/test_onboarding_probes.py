"""Tests for the never-onboarded post-sync advisory probe.

The failure this probe exists for is a repo where the plugin is *enabled* but
``/prawduct:onboard`` never ran. Enabling the plugin starts the hooks, and the
hooks fill ``.prawduct/`` with session state, so the directory populates, the
banner reports a version, and advisories appear — every visible signal reads as
"installed and working" while nothing an onboard writes is there.

**The two negatives are the load-bearing tests.** A probe that fires on a healthy
repo is worse than no probe, so a fully-onboarded repo and an
onboarded-but-drifted repo are each asserted silent — the drifted case
exhaustively, one surviving marker at a time, because a repair prescribed for a
repo that needs an install is the mistake this probe must not make. The firing
case is asserted against a repo carrying the *full* hook runtime state, which is
what made the field case invisible.

Registry isolation mirrors ``test_install_reference_probes.py`` (autouse
``clear_registry``); fixture repos are synthesised under ``tmp_path`` the way the
sibling probe tests do.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the plugin root first (mirrors tests/test_coverage_probes.py).
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.advisory_store import (  # noqa: E402
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    run_all_probes,
)
from lib import core  # noqa: E402
from lib import onboarding_probes as op  # noqa: E402
from lib.migrate_plugin import (  # noqa: E402
    ANCHOR_SENTINEL,
    DISTRIBUTION_KEY,
    DISTRIBUTION_VALUE,
    STATIC_ANCHOR,
    SYNC_MANIFEST,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(root) -> Codebase:
    return Codebase(root=Path(root))


def _probe(root):
    return op.probe_never_onboarded(ProjectState({}), _cb(root))


# --- fixture repos ------------------------------------------------------------

# The exact hook runtime state an enabled plugin writes into `.prawduct/` before
# anyone onboards. This is the noise the probe has to see through: it is what
# made the field repo look installed for weeks.
_RUNTIME_STATE = (
    ".prawduct/.session-start",
    ".prawduct/.session-base-tree",
    ".prawduct/.session-git-baseline",
    ".prawduct/.advisories.json",
    ".prawduct/.work-model-index.json",
    ".prawduct/.prawduct-version",
)

# The bare project-state.yaml stub the field repo carried: present, parseable,
# and recording nothing — including no `distribution:` key.
_STUB_STATE = (
    "product_name: null\n"
    "current_phase: null\n"
    "active_build_plan: null\n"
    "last_updated: null\n"
)


def _write(root: Path, rel: str, body: str = "") -> None:
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _enabled_never_onboarded(tmp_path) -> Path:
    """A repo the plugin has been running in, that nobody onboarded."""
    for rel in _RUNTIME_STATE:
        _write(tmp_path, rel, "runtime\n")
    _write(tmp_path, ".prawduct/project-state.yaml", _STUB_STATE)
    # The repo's own pre-prawduct CLAUDE.md — untouched by any onboard.
    _write(tmp_path, "CLAUDE.md", "# CLAUDE.md\n\nHouse rules for this codebase.\n")
    _write(tmp_path, "app.py", "print('hello')\n")
    return tmp_path


def _onboarded(tmp_path) -> Path:
    """A repo `/prawduct:onboard` scaffolded: anchor + `distribution: plugin`."""
    _enabled_never_onboarded(tmp_path)
    _write(tmp_path, "CLAUDE.md", f"# CLAUDE.md\n\n{STATIC_ANCHOR}\n")
    _write(
        tmp_path,
        ".prawduct/project-state.yaml",
        _STUB_STATE + f"{DISTRIBUTION_KEY}: {DISTRIBUTION_VALUE}\n",
    )
    return tmp_path


# --- the firing case ----------------------------------------------------------


def test_fires_when_plugin_enabled_but_never_onboarded(tmp_path):
    out = _probe(_enabled_never_onboarded(tmp_path))
    assert len(out) == 1
    assert out[0].type == "never-onboarded"


def test_fires_on_a_bare_directory(tmp_path):
    # No CLAUDE.md, no .prawduct/ at all — the first session in a fresh repo.
    # Firing immediately is the point: the user learns before building, not after.
    assert len(_probe(tmp_path)) == 1


def test_runtime_state_alone_never_reads_as_onboarded(tmp_path):
    # The defect, pinned: every file the hooks write, and nothing else. If any of
    # these ever counts as evidence of an onboard, the probe goes blind exactly
    # where it is needed.
    for rel in _RUNTIME_STATE:
        _write(tmp_path, rel, "runtime\n")
    assert len(_probe(tmp_path)) == 1


def test_advisory_names_the_cause_and_the_remedy(tmp_path):
    advisory = _probe(_enabled_never_onboarded(tmp_path))[0]
    assert advisory.recommended_action == "/prawduct:onboard"
    assert "/prawduct:onboard" in advisory.trigger_summary
    # It must read as a cause, not as one more symptom.
    assert "onboard" in advisory.trigger_summary.lower()
    # Repair is the wrong prescription for a repo that needs an install, so the
    # advisory must not offer one as an alternative route.
    assert "/prawduct:doctor" not in advisory.trigger_summary
    assert advisory.alternative_actions == ()


def test_priority_outranks_the_consequence_advisories(tmp_path):
    # The briefing sorts urgent → warn → info and ties break on triggered_at,
    # which is identical for everything one sync produces. `urgent` is the only
    # priority that guarantees the cause renders above its consequences.
    advisory = _probe(_enabled_never_onboarded(tmp_path))[0]
    assert advisory.priority == "urgent"


def test_advisory_says_the_other_advisories_are_downstream(tmp_path):
    # The probe sits alongside the consequence advisories rather than suppressing
    # them, so it carries the ranking in words as well as in priority.
    advisory = _probe(_enabled_never_onboarded(tmp_path))[0]
    assert "consequence" in advisory.trigger_summary.lower()


def test_identity_is_repo_independent(tmp_path):
    # Evidence is hashed into the advisory id, so it must carry no path, count or
    # other per-repo detail — two un-onboarded repos get the same id, and the id
    # survives every session until someone onboards.
    other = tmp_path / "other"
    other.mkdir()
    first = _probe(_enabled_never_onboarded(tmp_path))[0]
    second = _probe(other)[0]
    assert first.evidence == second.evidence
    assert compute_id(op.FEATURE, first.type, op.PROBE_VERSION, first.evidence) == compute_id(
        op.FEATURE, second.type, op.PROBE_VERSION, second.evidence
    )


# --- the load-bearing negatives ----------------------------------------------


def test_silent_for_a_fully_onboarded_repo(tmp_path):
    assert _probe(_onboarded(tmp_path)) == []


@pytest.mark.parametrize(
    "surviving_marker",
    [
        "anchor",
        "distribution",
        "legacy-block",
        "sync-manifest",
    ],
)
def test_silent_for_an_onboarded_repo_that_drifted(tmp_path, surviving_marker):
    """Drift removes onboarding's traces one at a time; it never removes them all.

    Each parameter is a repo that was onboarded and has since lost every marker
    but one. All four must stay silent: they need a *repair*, and prescribing an
    install for them is the inverse of the mistake this probe prevents.
    """
    _enabled_never_onboarded(tmp_path)
    if surviving_marker == "anchor":
        _write(tmp_path, "CLAUDE.md", f"# CLAUDE.md\n\n{ANCHOR_SENTINEL} kept\n")
    elif surviving_marker == "distribution":
        _write(
            tmp_path,
            ".prawduct/project-state.yaml",
            f"{DISTRIBUTION_KEY}: {DISTRIBUTION_VALUE}\n",
        )
    elif surviving_marker == "legacy-block":
        _write(tmp_path, "CLAUDE.md", f"# CLAUDE.md\n\n{core.BLOCK_BEGIN}\nrules\n")
    elif surviving_marker == "sync-manifest":
        _write(tmp_path, SYNC_MANIFEST, "{}\n")
    assert _probe(tmp_path) == []


def test_silent_for_a_pre_2_0_file_sync_repo(tmp_path):
    # A file-sync repo has neither the anchor nor `distribution: plugin`, but it
    # WAS onboarded — to the previous model. Its route is /prawduct:migrate, and
    # `/prawduct:onboard` sends it there; telling it "you never onboarded" is
    # wrong on the facts.
    _enabled_never_onboarded(tmp_path)
    _write(
        tmp_path,
        "CLAUDE.md",
        f"# CLAUDE.md\n\n{core.BLOCK_BEGIN}\ngovernance\n{core.BLOCK_END}\n",
    )
    _write(tmp_path, SYNC_MANIFEST, '{"files": {}}\n')
    assert _probe(tmp_path) == []


def test_silent_for_this_repo():
    # The acceptance criterion: prawduct's own checkout records
    # `distribution: plugin`, so the probe must say nothing here. Note its
    # CLAUDE.md deliberately carries no anchor — it IS the framework — which is
    # why any single marker has to be sufficient on its own.
    assert _probe(_REPO_ROOT) == []


def test_hook_nudged_files_are_not_onboarding_markers(tmp_path):
    """A file the *runtime* asks a session to create cannot vouch for an onboard.

    The session-start hook prints a CRITICAL telling the agent to create
    ``project-preferences.md`` when product code exists, the reflection loop
    writes rules into ``.claude/rules/learnings/core.md``, and
    ``/prawduct:backlog`` creates ``backlog.md`` — all reachable without ever
    onboarding. Counting them would silence the probe on exactly the trajectory
    the field repo was on.
    """
    _enabled_never_onboarded(tmp_path)
    for rel in (
        ".claude/rules/learnings/core.md",
        ".prawduct/backlog.md",
        ".prawduct/change-log.md",
        ".prawduct/artifacts/project-preferences.md",
        ".prawduct/artifacts/boundary-patterns.md",
    ):
        _write(tmp_path, rel, "# authored by a session, not by an onboard\n")
    assert len(_probe(tmp_path)) == 1


# --- fail-soft ----------------------------------------------------------------


def test_undecodable_claude_md_does_not_raise(tmp_path):
    _enabled_never_onboarded(tmp_path)
    (tmp_path / "CLAUDE.md").write_bytes(b"\xff\xfe\x00binary")
    # Unreadable is not evidence of an onboard, so the probe still fires — and,
    # above all, it does not raise inside the session-start sync.
    assert len(_probe(tmp_path)) == 1


def test_claude_md_as_a_directory_does_not_raise(tmp_path):
    _enabled_never_onboarded(tmp_path)
    (tmp_path / "CLAUDE.md").unlink()
    (tmp_path / "CLAUDE.md").mkdir()
    assert len(_probe(tmp_path)) == 1


# --- markers helper -----------------------------------------------------------


def test_markers_reports_which_traces_survive(tmp_path):
    assert op.onboarding_markers(_enabled_never_onboarded(tmp_path)) == []
    markers = op.onboarding_markers(_onboarded(tmp_path))
    assert len(markers) == 2
    assert any(DISTRIBUTION_KEY in m for m in markers)
    assert any(ANCHOR_SENTINEL in m for m in markers)


def test_never_onboarded_is_the_negation_of_the_markers(tmp_path):
    assert op.never_onboarded(_enabled_never_onboarded(tmp_path)) is True
    assert op.never_onboarded(_onboarded(tmp_path)) is False


# --- wiring -------------------------------------------------------------------


def test_fires_through_register_all(tmp_path):
    """The probe must reach production through ``probe_families.register_all()``.

    Testing only its own ``register()`` would stay green with the roster line
    deleted and the probe dead in production — the incident ``probe_families.py``
    exists to prevent.
    """
    from lib.probe_families import register_all

    register_all()
    candidates = run_all_probes(ProjectState({}), _cb(_enabled_never_onboarded(tmp_path)))
    mine = [c for c in candidates if c.feature == op.FEATURE]
    assert len(mine) == 1
    assert mine[0].type == "never-onboarded"
    assert mine[0].probe_version == op.PROBE_VERSION


def test_register_all_stays_silent_on_this_repo():
    from lib.probe_families import register_all

    register_all()
    candidates = run_all_probes(ProjectState({}), _cb(_REPO_ROOT))
    assert [c for c in candidates if c.feature == op.FEATURE] == []
