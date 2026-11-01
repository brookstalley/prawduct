"""Tests for the change-record format advisory probe.

``change_record_probes.probe_change_log_fragments_available`` fires only on a
COMMITTED single-file change log in a repo with no ``.prawduct/changes/``,
**self-resolves** once the migration it routes to has run, and answers
``None`` (could not look) when git cannot be asked.

Registry isolation mirrors ``test_gitattributes_probes.py`` (autouse
``clear_registry``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lib import change_migrate
from lib import change_record_probes as crp
from lib import probe_families
from lib.advisory_store import ProjectState, clear_registry, make_codebase, run_all_probes
from lib.change_fragments import FRAGMENT_DIR_REL
from lib.change_log import CHANGE_LOG_REL_PATH


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _repo(tmp_path: Path, *, change_log: str = "committed", fragments: bool = False) -> Path:
    """A repo whose change log is committed, untracked or absent, optionally
    already carrying the fragment directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    if change_log != "absent":
        log_path = repo / CHANGE_LOG_REL_PATH
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("# Change Log\n\n## 2026-08-13: first\n")
    if fragments:
        keep = repo / FRAGMENT_DIR_REL / ".gitkeep"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("")
    _git(repo, "add", "-A")
    if change_log == "untracked":
        _git(repo, "reset", "-q", "--", CHANGE_LOG_REL_PATH)
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _pin(repo: Path, ref: str) -> None:
    """Commit an install reference pinning prawduct to ``ref``."""
    from lib.migrate_plugin import INSTALL_REFERENCE

    marketplace = next(iter(INSTALL_REFERENCE["extraKnownMarketplaces"]))
    settings = {"extraKnownMarketplaces": {marketplace: {"source": {"source": "github", "ref": ref}}}}
    path = repo / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings))


def _probe(repo: Path):
    return crp.probe_change_log_fragments_available(ProjectState({}), make_codebase(repo))


class TestProbe:
    def test_fires_on_a_committed_log_with_no_fragment_directory(self, tmp_path):
        out = _probe(_repo(tmp_path))
        assert len(out) == 1
        cand = out[0]
        assert cand.type == "change-log-fragments-available"
        assert cand.priority == "info"
        # Doctor check #22 owns the procedure; the advisory routes there.
        assert cand.recommended_action == "/prawduct:doctor"
        assert "dry run" in cand.owner_action
        assert "pin" not in cand.owner_action
        assert cand.prerequisite_of[0][0] == "gitattributes:change-log-union-merge"

    def test_inert_once_the_fragment_directory_exists(self, tmp_path):
        # Control: the same repo without the directory fires (previous test).
        assert _probe(_repo(tmp_path, fragments=True)) == []

    def test_inert_when_the_change_log_is_absent(self, tmp_path):
        assert _probe(_repo(tmp_path, change_log="absent")) == []

    def test_inert_when_the_change_log_is_untracked(self, tmp_path):
        # An untracked log cannot conflict at merge time — the cost being advised against.
        repo = _repo(tmp_path, change_log="untracked")
        assert (repo / CHANGE_LOG_REL_PATH).is_file()
        assert _probe(repo) == []

    def test_could_not_look_outside_a_repo(self, tmp_path):
        # "git could not be asked" is not "untracked": an open advisory stays open.
        not_a_repo = tmp_path / "bare"
        (not_a_repo / ".prawduct").mkdir(parents=True)
        (not_a_repo / CHANGE_LOG_REL_PATH).write_text("# Change Log\n")
        assert _probe(not_a_repo) is None

    def test_a_too_old_pin_leads_the_owner_action(self, tmp_path):
        repo = _repo(tmp_path)
        _pin(repo, "v3.6.0")
        cand = _probe(repo)[0]
        assert cand.owner_action.startswith("First move this repo's prawduct install pin from v3.6.0")
        # The id is hashed from evidence, so the pin state must not move it.
        _pin(repo, "main")
        unpinned = _probe(repo)[0]
        assert "pin" not in unpinned.owner_action
        assert unpinned.evidence == cand.evidence

    def test_following_the_advice_resolves_it(self, tmp_path):
        # Effect, not object: run the migration the advisory routes to and the
        # very next probe goes quiet.
        repo = _repo(tmp_path)
        assert len(_probe(repo)) == 1
        assert change_migrate.migrate_cmd(repo, ["--apply"]) == 0
        assert (repo / FRAGMENT_DIR_REL).is_dir()
        assert _probe(repo) == []


class TestRegistration:
    def test_the_composition_root_runs_it(self, tmp_path):
        repo = _repo(tmp_path)
        probe_families.register_all()
        types = {c.type for c in run_all_probes(ProjectState({}), make_codebase(repo))}
        assert "change-log-fragments-available" in types
