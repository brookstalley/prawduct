"""Tests for the upstream-dependency-policy advisory probe.

The contract is deliberately smaller than every other migration nudge: fire when
no intake policy is recorded, suppress when one is — and consult **nothing else**.
The trigger is universal (every product either incorporates upstream code or
records in one line that it does not), so there is no detector to gate on, and
the absence of one is a design property this file pins rather than an omission a
later reader should close. Registry isolation mirrors ``test_upstream_probes.py``
(autouse ``clear_registry``).
"""

from __future__ import annotations

import re

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    make_codebase,
    run_all_probes,
)
from lib import dependency_policy_probes as dp


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(tmp_path):
    return Codebase(root=tmp_path)


def _probe(tmp_path, state=None):
    return dp.probe_dependency_policy_undeclared(ProjectState(state or {}), _cb(tmp_path))


# --- firing -------------------------------------------------------------------


def test_fires_when_the_fact_is_unset(tmp_path):
    out = _probe(tmp_path)
    assert len(out) == 1
    assert out[0].type == "dependency-policy"
    assert out[0].priority == "info"


def test_fires_on_an_empty_repo(tmp_path):
    """No source, no manifests, nothing to detect — and it still fires.

    This is the whole design in one case: a repo the api-versioning-style scan
    would read as "nothing here to ask about" still owes an answer, because
    "we incorporate no upstream code" is itself an answer someone has to record.
    """
    assert len(_probe(tmp_path)) == 1


# --- suppression --------------------------------------------------------------


def test_suppressed_when_the_fact_is_set(tmp_path):
    assert _probe(tmp_path, {"upstream_dependency_policy_decided": "7d-cooldown"}) == []


def test_suppressed_when_recorded_as_none(tmp_path):
    """"We incorporate no upstream code" is a recorded decision, not an absence.

    Force the decision, don't mandate the answer: the product that answers "none"
    is as settled as the one that answers with terms, and the nudge must not keep
    asking it.
    """
    assert _probe(tmp_path, {"upstream_dependency_policy_decided": "none-no-upstream-code"}) == []


def test_suppressed_when_recorded_as_a_deferral(tmp_path):
    assert _probe(tmp_path, {"upstream_dependency_policy_decided": "deferred:pre-launch"}) == []


def test_an_unrelated_recorded_answer_does_not_suppress(tmp_path):
    """The api-versioning fact is a different question; it must not silence this one."""
    assert len(_probe(tmp_path, {"api_versioning_decided": "semver"})) == 1


def test_a_filled_decision_block_alone_does_not_suppress(tmp_path):
    """Read through the real loader, against a real state file, because this is the
    one behaviour a hand-built ``ProjectState`` cannot express.

    The answer store is a column-0 scan: everything nested under ``design_decisions``
    is invisible to it, so a product that fills the decision block and never sets
    the flat mirror keeps getting nudged. That is the documented contract — setting
    the flat fact is the resolution step named wherever the decision is asked for —
    and not something to route around by teaching the probe to guess at nested
    state. ``/prawduct:doctor`` Health Check #15 is the surface that can read both
    and is told to report exactly this pair.
    """
    from lib.advisory_store import load_project_state

    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir()
    (prawduct / "project-state.yaml").write_text(
        "schema_version: 6\n"
        "design_decisions:\n"
        "  upstream_dependency_policy:\n"
        "    status: active\n"
        "    new_dependency_intake: reviewed\n",
        encoding="utf-8",
    )
    state = load_project_state(tmp_path)
    assert state.get("upstream_dependency_policy_decided") is None
    assert len(dp.probe_dependency_policy_undeclared(state, _cb(tmp_path))) == 1

    # ...and the one-line mirror is what actually silences it.
    (prawduct / "project-state.yaml").write_text(
        "schema_version: 6\n"
        "upstream_dependency_policy_decided: active\n"
        "design_decisions:\n"
        "  upstream_dependency_policy:\n"
        "    status: active\n",
        encoding="utf-8",
    )
    assert dp.probe_dependency_policy_undeclared(load_project_state(tmp_path), _cb(tmp_path)) == []


# --- the absent scan, pinned --------------------------------------------------


class _ExplodingCodebase:
    """A ``Codebase`` stand-in where every attribute access is a test failure.

    ``__getattr__`` fires for anything not found normally, and this class defines
    nothing — so ``root``, ``has_imports``, ``has_source_matching`` and any future
    scan primitive all land here.
    """

    def __getattr__(self, name):
        raise AssertionError(
            f"the probe consulted codebase.{name} — it must read the recorded fact "
            "and nothing else; see the module docstring for why a detector here "
            "would re-introduce the allowlist the policy exists to reject"
        )


def test_the_probe_consults_no_codebase_scan_when_firing():
    """Called directly, not through ``run_all_probes``, which swallows exceptions
    from a probe — routing this through the roster would turn a violated design
    property into a silently-absent advisory instead of a red test."""
    assert len(dp.probe_dependency_policy_undeclared(ProjectState({}), _ExplodingCodebase())) == 1


def test_the_probe_consults_no_codebase_scan_when_suppressed():
    state = ProjectState({"upstream_dependency_policy_decided": "7d-cooldown"})
    assert dp.probe_dependency_policy_undeclared(state, _ExplodingCodebase()) == []


def test_the_verdict_is_identical_across_wildly_different_trees(tmp_path, tmp_path_factory):
    """Same answer for an empty repo and one stuffed with intake surfaces — the
    readable form of the property above, and the one that would catch a detector
    added through a helper rather than through ``codebase``."""
    empty = _probe(tmp_path)
    stuffed = tmp_path_factory.mktemp("stuffed")
    (stuffed / "manifest.toml").write_text("[deps]\nsomething = '1.0'\n")
    (stuffed / "vendor").mkdir()
    (stuffed / ".github").mkdir()
    (stuffed / ".github" / "ci.yml").write_text("jobs: {build: {uses: someone/else@v4}}\n")
    busy = dp.probe_dependency_policy_undeclared(ProjectState({}), _cb(stuffed))
    assert [c.evidence for c in empty] == [c.evidence for c in busy]
    assert [c.trigger_summary for c in empty] == [c.trigger_summary for c in busy]


# --- what the reader is told --------------------------------------------------


def test_the_nudge_routes_to_both_recording_and_the_health_check(tmp_path):
    """Deliverable of the check/advisory pairing: the reader can either record the
    decision or go see what their repo actually does. ``recommended_action`` is the
    field that carries it because it is the one the briefing renders —
    ``alternative_actions`` is stored and displayed nowhere."""
    action = _probe(tmp_path)[0].recommended_action
    assert "/prawduct:methodology discovery" in action
    assert "/prawduct:doctor" in action and "#15" in action


def test_the_id_is_stable_across_repos(tmp_path, tmp_path_factory):
    """One universal trigger means one advisory id everywhere — which is what makes
    a dismissal stick instead of returning under a new hash on the next sync."""
    other = tmp_path_factory.mktemp("other")
    (other / "README.md").write_text("# unrelated\n")
    here = compute_id(dp.FEATURE, dp.PROBE_TYPE, dp.PROBE_VERSION, _probe(tmp_path)[0].evidence)
    there = compute_id(
        dp.FEATURE,
        dp.PROBE_TYPE,
        dp.PROBE_VERSION,
        dp.probe_dependency_policy_undeclared(ProjectState({}), _cb(other))[0].evidence,
    )
    assert here == there


def test_the_nudge_states_no_terms_of_its_own(tmp_path):
    """The clauses have one home. A nudge that restated an interval would be a
    second copy in the surface read most often — every session briefing.

    ``test_v5_templates.py``'s policy-surface sweep scans this whole module for
    the same property and so overlaps here, deliberately: that sweep guards the
    *file*, this guards the *emitted strings* — the subset a product owner
    actually reads — and it keeps holding if the roster entry is ever dropped.
    """
    cand = _probe(tmp_path)[0]
    emitted = " ".join(
        (*cand.evidence, cand.trigger_summary, cand.recommended_action)
    )
    hit = re.search(r"\d+\s*days?\b", emitted)
    assert not hit, f"the advisory text states an interval ({hit.group(0)!r}); the spec owns it"


# --- registration -------------------------------------------------------------


def test_probe_is_wired_into_the_composition_root(tmp_path):
    """Must fire through ``register_all()``, not merely through its own
    ``register()``. A probe whose own ``register()`` is tested but whose
    composition-root line was never added is dead in production and green in the
    suite — the incident ``probe_families.py``'s docstring records."""
    from lib.probe_families import register_all

    register_all()
    fired = [
        c
        for c in run_all_probes(ProjectState({}), make_codebase(tmp_path))
        if c.feature == dp.FEATURE and c.type == dp.PROBE_TYPE
    ]
    assert len(fired) == 1
    assert fired[0].probe_version == dp.PROBE_VERSION


#: The prose surfaces that name this advisory to a reader and route them to it.
#: The pairing is meant to hold in BOTH directions — the probe points at the
#: health check, and these point back — but only the probe's half is expressed in
#: code. Each of these carries the type as a bare literal, so a rename or a
#: version bump would leave all three routing readers to an advisory that no
#: longer exists, with the suite green. These asserts are the coupling.
_SURFACES_NAMING_THE_ADVISORY = (
    "skills/doctor/SKILL.md",
    "skills/janitor/SKILL.md",
    "docs/doctor-vs-janitor.md",
)


@pytest.mark.parametrize("rel_path", _SURFACES_NAMING_THE_ADVISORY)
def test_the_surfaces_that_name_the_advisory_use_its_real_type(rel_path):
    from pathlib import Path

    plugin_root = Path(__file__).resolve().parents[1] / "plugin"
    text = (plugin_root / rel_path).read_text(encoding="utf-8")
    assert f"`{dp.PROBE_TYPE}`" in text, (
        f"{rel_path} routes a reader to this advisory but does not name "
        f"{dp.PROBE_TYPE!r} — either the surface drifted or the probe's type did, "
        "and the reader is being sent to an advisory that does not exist"
    )


def test_direct_register_is_idempotent_and_fires(tmp_path):
    dp.register()
    dp.register()  # idempotent — register_probe overwrites
    fired = [c for c in run_all_probes(ProjectState({}), make_codebase(tmp_path))
             if c.type == dp.PROBE_TYPE]
    assert len(fired) == 1
    assert fired[0].feature == "upstream-dependency-policy"
