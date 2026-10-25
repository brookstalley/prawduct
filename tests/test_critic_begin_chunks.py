"""``critic-begin --chunks a,b`` — what the hook PASSES to ``begin_review`` (ST8, #1051).

The consolidator's handling of ``chunks`` (manifest, fact body, proposal
warning) is ``critic_consolidate``'s and pinned in ``test_critic_consolidate``.
This file pins the CLI half only: the flag's parse, its ``--chunk`` alias, and
the exact keyword the hook hands over. ``begin_review`` is replaced by a
recorder, so the test reads the call, not a downstream effect that could come
from somewhere else.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_loader = importlib.machinery.SourceFileLoader("prawduct_hook_critic_begin_chunks", str(HOOK))
_hook = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("prawduct_hook_critic_begin_chunks", _loader)
)
_loader.exec_module(_hook)


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    """A repo the dispatch guards accept, with ``begin_review`` recording its
    kwargs and answering a plain error, so the CLI returns right after the call."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(repo), check=True, timeout=10)
    (repo / ".prawduct").mkdir()
    monkeypatch.chdir(repo)
    calls: list[dict] = []
    consolidate = _hook._critic_consolidate()

    def fake_begin_review(project_dir, **kwargs):
        calls.append(kwargs)
        return {"status": "error", "reason": "recorded"}

    monkeypatch.setattr(consolidate, "begin_review", fake_begin_review)
    return repo.resolve(), calls


@pytest.mark.parametrize(
    "argv, chunks",
    [
        (["--chunks", "01,03"], ["01", "03"]),
        (["--chunks", " 01 , 03 "], ["01", "03"]),
        (["--chunks", "01", "--chunks", "03,01", "--chunk", "04"], ["01", "03", "04"]),
        (["--chunk", "02"], ["02"]),
    ],
)
def test_the_chunks_reach_begin_review_as_a_list(recorded, argv, chunks):
    repo, calls = recorded
    rc = _hook.cmd_critic_begin(repo, ["--mode", "chunk", *argv])
    assert rc == 1  # the recorder's error, so the call happened and returned
    assert len(calls) == 1
    assert calls[0]["chunks"] == chunks
    assert "chunk" not in calls[0]
    assert calls[0]["mode_token"] == "chunk"


def test_no_chunk_flag_passes_no_chunks_keyword(recorded):
    """Omitted, not ``chunks=[]``: an empty list would be a declaration that the
    review names no chunk, and the consolidator's default is what holds."""
    repo, calls = recorded
    assert _hook.cmd_critic_begin(repo, ["--mode", "final"]) == 1
    assert len(calls) == 1
    assert "chunks" not in calls[0] and "chunk" not in calls[0]


@pytest.mark.parametrize(
    "argv",
    [["--chunks", "01,,03"], ["--chunks", ","], ["--chunk", " "], ["--chunks"]],
)
def test_an_empty_or_missing_id_is_refused_before_dispatch(recorded, argv, capsys):
    repo, calls = recorded
    rc = _hook.cmd_critic_begin(repo, ["--mode", "chunk", *argv])
    assert rc == 1
    assert calls == []
    err = capsys.readouterr().err
    assert "critic-begin:" in err and ("empty chunk id" in err or "requires a value" in err)
