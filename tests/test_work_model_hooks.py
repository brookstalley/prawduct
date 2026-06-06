"""Tests for the work-model hook wiring (Chunk 2) — `bin/prawduct-hook`
``build-index`` and ``user-prompt-submit``.

These pin the runtime contract of the external enforcement surface:
  * the index is built from the repo's governing artifacts into per-repo state
    (``.prawduct/.work-model-index.json`` — NOT plugin-bundled state);
  * UserPromptSubmit injects a nudge (the exact ``additionalContext`` JSON shape)
    only when the prompt has orphan terms, and is silent when clean;
  * every failure path is fail-soft — a hook error must NEVER block the user's
    prompt (the hardest invariant), and the hook stays silent in non-prawduct repos.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"

# Governing artifact: headings + bold define the covered vocabulary.
SPEC = """# Spec
## Continuity
The **judge** checks the **world** **model** **facts** for a **continuity**
defect against each **entity** and **scene**.
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".prawduct" / "artifacts").mkdir(parents=True)
    (tmp_path / ".prawduct" / "artifacts" / "spec.md").write_text(SPEC, encoding="utf-8")
    return tmp_path


def _run(command: str, project_dir: Path, stdin: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(HOOK), command],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def test_build_index_writes_per_repo_state(repo: Path):
    res = _run("build-index", repo)
    assert res.returncode == 0
    index_path = repo / ".prawduct" / ".work-model-index.json"
    assert index_path.exists(), "index must be written under .prawduct/ (per-repo state)"
    vocab = json.loads(index_path.read_text())["vocab"]
    assert {"continuity", "judge", "fact", "entity", "scene"} <= set(vocab)


def test_user_prompt_submit_nudges_on_orphan_terms(repo: Path):
    _run("build-index", repo)
    res = _run("user-prompt-submit", repo, '{"prompt":"model character belief and sincerity"}')
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "belief" in ctx and "sincerity" in ctx
    assert "tripwire #1" in ctx


def test_user_prompt_submit_silent_when_fully_covered(repo: Path):
    _run("build-index", repo)
    res = _run(
        "user-prompt-submit",
        repo,
        '{"prompt":"the judge and the world model facts for each entity and scene"}',
    )
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"expected silence, got: {res.stdout!r}"


def test_user_prompt_submit_lazy_builds_index_when_missing(repo: Path):
    # No prior build-index call: the hook must build on demand and still fire.
    assert not (repo / ".prawduct" / ".work-model-index.json").exists()
    res = _run("user-prompt-submit", repo, '{"prompt":"introduce doxastic sincerity"}')
    assert res.returncode == 0
    assert "sincerity" in res.stdout
    assert (repo / ".prawduct" / ".work-model-index.json").exists()


def test_user_prompt_submit_silent_in_non_prawduct_repo(tmp_path: Path):
    res = _run("user-prompt-submit", tmp_path, '{"prompt":"belief sincerity canonical"}')
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_user_prompt_submit_failsoft_on_malformed_stdin(repo: Path):
    res = _run("user-prompt-submit", repo, "not json {{{")
    assert res.returncode == 0  # NEVER block the prompt
    assert res.stdout.strip() == ""


def test_user_prompt_submit_failsoft_on_empty_stdin(repo: Path):
    res = _run("user-prompt-submit", repo, "")
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_index_rebuilds_when_an_artifact_is_newer(repo: Path):
    """Staleness: an artifact modified after the index forces a rebuild, so new
    vocabulary is picked up without a manual build-index."""
    _run("build-index", repo)
    index_path = repo / ".prawduct" / ".work-model-index.json"
    # "provenance" is not yet covered -> currently an orphan.
    assert "provenance" in _run("user-prompt-submit", repo, '{"prompt":"the provenance"}').stdout
    # Add it to a governing artifact and age the index so the artifact is newer.
    (repo / ".prawduct" / "artifacts" / "spec.md").write_text(
        SPEC + "\n## Provenance\nThe **provenance** of each claim.\n", encoding="utf-8"
    )
    old = index_path.stat().st_mtime - 100
    os.utime(index_path, (old, old))
    # The rebuilt index now covers it -> silent.
    res = _run("user-prompt-submit", repo, '{"prompt":"the provenance"}')
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"expected silence after rebuild, got {res.stdout!r}"


def test_corrupt_index_recovers_by_rebuilding(repo: Path):
    """A corrupt index file is transparently rebuilt from artifacts, not fatal."""
    _run("build-index", repo)
    index_path = repo / ".prawduct" / ".work-model-index.json"
    index_path.write_text("}{ not json", encoding="utf-8")
    res = _run("user-prompt-submit", repo, '{"prompt":"the sincerity"}')
    assert res.returncode == 0
    assert "sincerity" in res.stdout  # rebuilt index still detects the orphan
    json.loads(index_path.read_text())  # corrupt file was replaced with valid JSON


def test_index_is_gitignored():
    gitignore = (ROOT / ".gitignore").read_text()
    assert ".prawduct/.work-model-index.json" in gitignore
