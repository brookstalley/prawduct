"""The oversized-evidence-store advisory (#953).

The clone-shared ``evidence.jsonl`` is append-only and parsed whole on every gate
call. The probe reads one ``stat`` against a byte threshold, keeps a size-free
evidence so a dismissal survives appends, and stays silent wherever it cannot
measure. ``evidence status`` gains the per-kind byte split that says where the
growth is.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from lib import evidence, probe_families
from lib import evidence_size_probes as esp
from lib.advisory_store import ProjectState, clear_registry, compute_id, make_codebase, run_all_probes


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _repo(tmp_path: Path, threshold: str | None = "1") -> Path:
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    state = "project: demo\n"
    if threshold is not None:
        state += f"evidence_store_threshold_mb: {threshold}\n"
    (repo / ".prawduct" / "project-state.yaml").write_text(state, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _store(repo: Path, size: int) -> Path:
    path = evidence.store_path(repo)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def _probe(root: Path):
    return esp.probe_oversized_evidence_store(ProjectState({}), make_codebase(root))


class TestThreshold:
    def test_one_byte_over_fires_once_and_at_the_threshold_does_not(self, tmp_path):
        repo = _repo(tmp_path, "1")
        _store(repo, 1_000_000)
        assert _probe(repo) == []
        _store(repo, 1_000_001)
        found = _probe(repo)
        assert [c.type for c in found] == ["oversized-evidence-store"]
        assert found[0].recommended_action == "prawduct-hook evidence status"

    @pytest.mark.parametrize("raw", [None, "0", "-5", "abc"])
    def test_a_bad_or_absent_key_falls_back_to_fifty(self, tmp_path, raw):
        repo = _repo(tmp_path, raw)
        assert esp.evidence_store_threshold(repo / ".prawduct") == 50_000_000

    def test_a_positive_key_is_honoured(self, tmp_path):
        repo = _repo(tmp_path, "1")
        assert esp.evidence_store_threshold(repo / ".prawduct") == 1_000_000


class TestStableIdentity:
    def test_appending_keeps_the_advisory_id(self, tmp_path):
        repo = _repo(tmp_path, "1")
        path = _store(repo, 1_500_000)
        before = _probe(repo)[0]
        with path.open("ab") as handle:
            handle.write(b"y" * 700_000)
        after = _probe(repo)[0]
        assert before.trigger_summary != after.trigger_summary, "the size did move"
        ident = lambda c: compute_id(esp.FEATURE, c.type, esp.PROBE_VERSION, c.evidence)  # noqa: E731
        assert ident(before) == ident(after)


class TestSilentWhereItCannotMeasure:
    def test_missing_store(self, tmp_path):
        assert _probe(_repo(tmp_path, "1")) == []

    def test_outside_git(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _probe(plain) == []

    def test_unstatable_store(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path, "1")
        _store(repo, 2_000_000)
        real_stat = os.stat

        def _stat(path, *args, **kwargs):
            if str(path).endswith("evidence.jsonl"):
                raise PermissionError("denied")
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(esp.os, "stat", _stat)
        assert _probe(repo) == []

    def test_never_parses_the_store(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path, "1")
        _store(repo, 2_000_000)

        def _boom(*_a, **_k):
            raise AssertionError("read_facts must not run")

        monkeypatch.setattr(evidence, "read_facts", _boom)
        assert len(_probe(repo)) == 1


def test_registered_in_the_production_roster(tmp_path):
    repo = _repo(tmp_path, "1")
    _store(repo, 2_000_000)
    probe_families.register_all()
    found = [c for c in run_all_probes(ProjectState({}), make_codebase(repo)) if c.type == esp.PROBE_TYPE]
    assert len(found) == 1


class TestStatusSizeLine:
    def test_per_kind_bytes_sum_to_the_file_within_excluded_lines(self, tmp_path, capsys):
        repo = _repo(tmp_path, None)
        evidence.append_fact(repo, "review", "r-1", {"head_tree": "a" * 40, "pad": "p" * 3000})
        evidence.append_fact(repo, "resolution", "s-1", {"at_tree": "b" * 40})
        path = evidence.store_path(repo)
        junk = b"not json\n"
        with path.open("ab") as handle:
            handle.write(junk)
        line = evidence._store_size_line(path)
        assert line is not None
        total = path.stat().st_size
        assert line.startswith(f"size: {total / 1_000_000:.2f} MB, 3 lines; largest kinds: review ")
        # The split itself, measured at byte precision from the same rule.
        raw = path.read_bytes().splitlines(keepends=True)
        assert sum(len(r) for r in raw if r != junk) == total - len(junk)
        assert line.index("review") < line.index("resolution"), "largest first"

        assert evidence._cmd_status(repo) == 0
        assert "size: " in capsys.readouterr().out
