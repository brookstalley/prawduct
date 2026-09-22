"""Tests for the risk-surfaces-undeclared post-sync advisory probe.

The condition this probe exists for is silent by design: a product that never
answered *where would a missed defect cost you most?* is reviewed at the depth its
diff size suggests, whatever the diff touches, and nothing ever fails or prompts.
The probe is the one prompt — asked once, dismissable, resolved by writing the
key.

**The silences are the load-bearing tests.** ``risk_surfaces: []`` is the
deliberate opt-out (``discovery.md``) and MUST silence the ask; a docs-only repo
has no code for a surface to name; a key in an unreadable shape was answered, and
is the doctor row's finding rather than this one's. Each silent fixture asserts
the precondition that puts it in front of the subject, so silence is measured at
the key and not at the gate.

Registry isolation mirrors ``test_onboarding_probes.py`` (autouse
``clear_registry``); fixture repos are synthesised under ``tmp_path`` the way the
sibling probe tests do.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the plugin root first (mirrors tests/test_onboarding_probes.py).
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.advisory_store import (  # noqa: E402
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    dismiss,
    read_store,
    run_all_probes,
    run_sync_advisories,
)
from lib import gitstate  # noqa: E402
from lib import risk_surface_probes as rsp  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DISCOVERY_MD = _PLUGIN_ROOT / "methodology" / "discovery.md"


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(root) -> Codebase:
    return Codebase(root=Path(root))


def _probe(root):
    return rsp.probe_risk_surfaces_undeclared(ProjectState({}), _cb(root))


# --- fixture repos ------------------------------------------------------------

# A parseable state file recording nothing about risk. The other keys are what a
# scaffolded repo carries; none of them is the one under test.
_STATE_NO_KEY = (
    "product_name: demo\n"
    "current_phase: null\n"
    "active_build_plan: null\n"
    "distribution: plugin\n"
)


def _write(root: Path, rel: str, body: str = "") -> None:
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _repo_with_code(tmp_path, state: str = _STATE_NO_KEY) -> Path:
    """An onboarded repo with source code and the given state file."""
    _write(tmp_path, ".prawduct/project-state.yaml", state)
    _write(tmp_path, "src/app.py", "def main():\n    ...\n")
    return tmp_path


def _mine(root: Path) -> list[dict]:
    """This probe's entries in the per-clone store, by the id prefix the store
    computes — retention COMPACTS a dismissed or resolved entry to its id and
    state, so `type` is not there to filter on after a second sync."""
    prefix = f"{rsp.FEATURE}-{rsp.PROBE_TYPE}-v{rsp.PROBE_VERSION}-"
    return [a for a in read_store(root)["advisories"] if a["id"].startswith(prefix)]


def _assert_owed(root: Path) -> None:
    """The fixture is in front of the subject: the gate is open, so whatever the
    probe says next is about the key and not about the work."""
    assert rsp.judgeable_work_present(root), "fixture never reached the key check"


# --- the firing case ----------------------------------------------------------


def test_fires_when_code_exists_and_the_key_is_absent(tmp_path):
    root = _repo_with_code(tmp_path)
    _assert_owed(root)
    assert rsp.risk_surfaces_status(root) == rsp.STATUS_UNDECLARED
    out = _probe(root)
    assert len(out) == 1
    assert out[0].type == rsp.PROBE_TYPE


def test_the_ask_is_in_the_products_terms_and_lands_on_discovery(tmp_path):
    advisory = _probe(_repo_with_code(tmp_path))[0]
    # The question, as discovery.md asks it, leads.
    assert "missed defect cost you most" in advisory.trigger_summary.lower()
    assert advisory.recommended_action == "/prawduct:methodology discovery"
    # The landing is a SECTION the reader can find — pinned against the real
    # guide, so a renamed heading breaks this rather than the reader.
    assert rsp.DISCOVERY_SECTION in advisory.trigger_summary
    assert f"## {rsp.DISCOVERY_SECTION}" in _DISCOVERY_MD.read_text(encoding="utf-8")
    # The opt-out is named as such, with its cost.
    assert f"{rsp.RISK_SURFACES_KEY}: []" in advisory.trigger_summary
    assert "opt-out" in advisory.trigger_summary
    # Two audiences, two actions: the owner's is a question, never a command.
    assert advisory.owner_action
    assert "prawduct-hook" not in advisory.owner_action
    assert "/" not in advisory.owner_action.split("?")[0]


def test_emitted_text_names_no_runner_and_no_internal_identifier(tmp_path):
    """Plan § Success: the diff reads the same for a Swift, C#, JS or Python
    product; observability norm: nothing emitted into a governed product names a
    prawduct-internal identifier."""
    advisory = _probe(_repo_with_code(tmp_path))[0]
    emitted = " ".join((advisory.trigger_summary, advisory.owner_action, *advisory.evidence)).lower()
    for banned in (
        "pytest", "jest", "xunit", "junit", "go test", "cargo", ".py", ".cs", ".swift",
        # internal surfaces the reader of a product briefing has no handle on
        "classify-diff-risk", "roster", "critic", "cumulative", "escalate", "tier",
    ):
        assert banned not in emitted, f"emitted text names {banned!r}"


def test_identity_is_repo_independent(tmp_path):
    # Evidence is hashed into the advisory id, so it must carry no path, count or
    # other per-repo detail — two undeclared repos get the same id, and the id
    # survives every session until the key is written.
    other = tmp_path / "other"
    other.mkdir()
    first = _probe(_repo_with_code(tmp_path))[0]
    second = _probe(_repo_with_code(other))[0]
    assert first.evidence == second.evidence
    assert compute_id(rsp.FEATURE, first.type, rsp.PROBE_VERSION, first.evidence) == compute_id(
        rsp.FEATURE, second.type, rsp.PROBE_VERSION, second.evidence
    )


def test_fires_once_across_syncs(tmp_path):
    """Two syncs, one advisory: the second refreshes the entry under the same id
    rather than opening a second one."""
    root = _repo_with_code(tmp_path)
    rsp.register()
    run_sync_advisories(root, now="2026-09-17T10:00:00Z")
    run_sync_advisories(root, now="2026-09-17T11:00:00Z")
    mine = _mine(root)
    assert len(mine) == 1
    assert mine[0]["state"] == "active"
    assert mine[0]["id"] == compute_id(rsp.FEATURE, rsp.PROBE_TYPE, rsp.PROBE_VERSION, mine[0]["evidence"])


def test_dismissed_stays_silent(tmp_path):
    """Dismissal is sticky under the stable id — the probe re-firing does not
    reopen it, and it does not come back under a fresh id."""
    root = _repo_with_code(tmp_path)
    rsp.register()
    run_sync_advisories(root, now="2026-09-17T10:00:00Z")
    (advisory,) = _mine(root)
    assert dismiss(root, advisory["id"], "we know", now="2026-09-17T10:30:00Z")["status"] == "ok"

    run_sync_advisories(root, now="2026-09-17T11:00:00Z")
    mine = _mine(root)
    assert [a["state"] for a in mine] == ["dismissed"]
    # The precondition, asserted after the second sync: the probe still fires on
    # this repo, so the silence is the dismissal's and not the probe's.
    assert len(_probe(root)) == 1


def test_writing_the_opt_out_resolves_it(tmp_path):
    """The recommendation's EFFECT, not only that it fires: following the advice
    with the opt-out clears the advisory on the next sync."""
    root = _repo_with_code(tmp_path)
    rsp.register()
    run_sync_advisories(root, now="2026-09-17T10:00:00Z")
    assert [a["state"] for a in _mine(root)] == ["active"]

    _write(root, ".prawduct/project-state.yaml", _STATE_NO_KEY + f"{rsp.RISK_SURFACES_KEY}: []\n")
    run_sync_advisories(root, now="2026-09-17T11:00:00Z")
    assert [a["state"] for a in _mine(root)] == ["resolved"]


# --- the load-bearing silences -------------------------------------------------


@pytest.mark.parametrize(
    ("declaration", "items"),
    [
        (f"{rsp.RISK_SURFACES_KEY}:\n  - src/auth/\n  - src/billing/*.py\n", 2),
        (f"{rsp.RISK_SURFACES_KEY}: []\n", 0),
        (f"{rsp.RISK_SURFACES_KEY}:\n", 0),
    ],
)
def test_silent_when_the_key_is_declared(tmp_path, declaration, items):
    """A present key is an answer — including the empty one, which discovery.md
    defines as the opt-out and which MUST silence the ask (the plan's own
    acceptance). `risk.has_product_risk_declaration` reads `[]` as no
    declaration; that predicate is deliberately not the one this probe uses."""
    root = _repo_with_code(tmp_path, _STATE_NO_KEY + declaration)
    _assert_owed(root)
    assert rsp.risk_surfaces_status(root) == rsp.STATUS_DECLARED
    from lib.risk import read_declared_surfaces  # noqa: PLC0415

    assert len(read_declared_surfaces(root / ".prawduct" / "project-state.yaml", rsp.RISK_SURFACES_KEY)[1]) == items
    assert _probe(root) == []


def test_silent_on_an_unparseable_key_which_is_the_doctor_rows_finding(tmp_path):
    """Flow style is a key the reader refuses. The question WAS answered, so the
    "please answer it" ask is wrong here; `coverage-status` grades this state
    degraded with the shape fix, and the Critic escalates on it out loud."""
    root = _repo_with_code(tmp_path, _STATE_NO_KEY + f"{rsp.RISK_SURFACES_KEY}: [src/auth/, src/billing/]\n")
    _assert_owed(root)
    assert rsp.risk_surfaces_status(root) == rsp.STATUS_UNPARSEABLE
    assert _probe(root) == []


def test_silent_for_a_docs_only_repo(tmp_path):
    """Product-DEFINITION work is not judgeable work: a spec-first repo owes
    discovery (the sibling nudge fires) but has no code for a risk surface to
    name, so this ask waits."""
    _write(tmp_path, ".prawduct/project-state.yaml", _STATE_NO_KEY)
    _write(tmp_path, "docs/design.md", "# Design\n")
    assert gitstate._has_product_definition_work(tmp_path), "fixture must be product work"
    assert not rsp.judgeable_work_present(tmp_path)
    assert rsp.risk_surfaces_status(tmp_path) == rsp.STATUS_NOT_OWED
    assert _probe(tmp_path) == []


def test_silent_for_a_freshly_scaffolded_empty_repo(tmp_path):
    _write(tmp_path, ".prawduct/project-state.yaml", _STATE_NO_KEY)
    assert rsp.risk_surfaces_status(tmp_path) == rsp.STATUS_NOT_OWED
    assert _probe(tmp_path) == []


def test_silent_with_no_state_file_to_record_the_answer_in(tmp_path):
    # Core-state breakage is a different check's finding; asking for a key in a
    # file that does not exist would prescribe the wrong repair.
    _write(tmp_path, "src/app.py", "print('hi')\n")
    assert gitstate._has_product_code(tmp_path)
    assert rsp.risk_surfaces_status(tmp_path) == rsp.STATUS_NOT_OWED
    assert _probe(tmp_path) == []


def test_silent_for_this_repo():
    # The acceptance criterion in the precedent's shape: prawduct's own checkout
    # declares `risk_surfaces:`, so the probe must say nothing here — and it is
    # in front of the subject, because this repo has code.
    assert rsp.judgeable_work_present(_REPO_ROOT)
    assert rsp.risk_surfaces_status(_REPO_ROOT) == rsp.STATUS_DECLARED
    assert _probe(_REPO_ROOT) == []


# --- fail-soft, never fail-silent ----------------------------------------------


def test_an_undecodable_state_file_fires_rather_than_vanishing(tmp_path):
    """The shared reader grades an unreadable file `absent`. That direction is
    the visible one: a state file nobody can read has declared nothing, and a
    nudge that appears is a nudge that can be dismissed, while one that vanishes
    on a broken file manufactures a clean bill."""
    root = _repo_with_code(tmp_path)
    (root / ".prawduct" / "project-state.yaml").write_bytes(b"\xff\xfe\x00binary")
    assert rsp.risk_surfaces_status(root) == rsp.STATUS_UNDECLARED
    assert len(_probe(root)) == 1


# --- wiring -------------------------------------------------------------------


def test_fires_through_register_all(tmp_path):
    """The probe must reach production through ``probe_families.register_all()``.

    Testing only its own ``register()`` would stay green with the roster line
    deleted and the probe dead in production — the incident ``probe_families.py``
    exists to prevent.
    """
    from lib.probe_families import register_all

    register_all()
    candidates = run_all_probes(ProjectState({}), _cb(_repo_with_code(tmp_path)))
    mine = [c for c in candidates if c.feature == rsp.FEATURE]
    assert len(mine) == 1
    assert mine[0].type == rsp.PROBE_TYPE
    assert mine[0].probe_version == rsp.PROBE_VERSION


def test_register_all_stays_silent_on_this_repo():
    from lib.probe_families import register_all

    register_all()
    candidates = run_all_probes(ProjectState({}), _cb(_REPO_ROOT))
    assert [c for c in candidates if c.feature == rsp.FEATURE] == []
