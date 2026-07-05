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
    vocabulary is picked up without a manual build-index.

    Prompt is requirement-shaped ("add ...") since review-fixes Chunk 2: the
    firing threshold silences single-orphan non-imperative prompts, and this
    test pins staleness mechanics, not the threshold."""
    _run("build-index", repo)
    index_path = repo / ".prawduct" / ".work-model-index.json"
    # "provenance" is not yet covered -> currently an orphan.
    assert "provenance" in _run(
        "user-prompt-submit", repo, '{"prompt":"add provenance tracking"}'
    ).stdout
    # Add it to a governing artifact and age the index so the artifact is newer.
    (repo / ".prawduct" / "artifacts" / "spec.md").write_text(
        SPEC + "\n## Provenance\nThe **provenance** of each claim.\n", encoding="utf-8"
    )
    old = index_path.stat().st_mtime - 100
    os.utime(index_path, (old, old))
    # The rebuilt index now covers it -> silent.
    res = _run("user-prompt-submit", repo, '{"prompt":"add provenance tracking"}')
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"expected silence after rebuild, got {res.stdout!r}"


def test_corrupt_index_recovers_by_rebuilding(repo: Path):
    """A corrupt index file is transparently rebuilt from artifacts, not fatal.
    (Requirement-shaped prompt per the Chunk 2 firing threshold — this test
    pins corruption recovery, not the threshold.)"""
    _run("build-index", repo)
    index_path = repo / ".prawduct" / ".work-model-index.json"
    index_path.write_text("}{ not json", encoding="utf-8")
    res = _run("user-prompt-submit", repo, '{"prompt":"add doxastic sincerity"}')
    assert res.returncode == 0
    assert "sincerity" in res.stdout  # rebuilt index still detects the orphan
    json.loads(index_path.read_text())  # corrupt file was replaced with valid JSON


INDEX_RELPATH = ".prawduct/.work-model-index.json"


def test_index_is_gitignored():
    gitignore = (ROOT / ".gitignore").read_text()
    assert INDEX_RELPATH in gitignore


def test_index_is_in_gitignore_contract():
    """The runtime-generated index must be in the canonical contract list that
    propagates to product repos — not just this framework repo's hand-edited
    ``.gitignore``. Regression for the original ship: the SessionStart/
    UserPromptSubmit hooks generated the index in every governed repo, but
    ``update_gitignore`` never wrote an ignore line for it, so onboarded
    products carried it as permanent untracked noise. ``TestSessionGitignoreMirror``
    pins the hook's ``_SESSION_GITIGNORED_PATHS`` in sync, so asserting the
    core contract covers both lists."""
    sys.path.insert(0, str(ROOT))
    from lib.core import GITIGNORE_ENTRIES  # noqa: PLC0415

    assert INDEX_RELPATH in GITIGNORE_ENTRIES


def test_update_gitignore_writes_index_line(repo: Path):
    """End-to-end: a freshly reconciled product ``.gitignore`` ignores the index,
    so consuming repos self-heal on next session instead of accruing noise."""
    sys.path.insert(0, str(ROOT))
    from lib.core import update_gitignore  # noqa: PLC0415

    update_gitignore(repo)
    assert INDEX_RELPATH in (repo / ".gitignore").read_text()


# --- Corpus widening (review-fixes Chunk 2; recursive since gate-noise) ------
# CLAUDE.md, docs/, and methodology/ feed the index alongside
# .prawduct/artifacts/ — including doc SUBDIRECTORIES, so governing vocabulary
# nested under docs/<area>/ stops reading as orphans.


def test_index_covers_claude_md_docs_and_methodology(repo: Path):
    (repo / "CLAUDE.md").write_text("# Repo\n## Doxastic budgeting\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "notes.md").write_text("## Telemetry provenance\n", encoding="utf-8")
    (repo / "docs" / "design").mkdir()
    (repo / "docs" / "design" / "adr.md").write_text("## Attestation ledger\n", encoding="utf-8")
    (repo / "methodology").mkdir()
    (repo / "methodology" / "m.md").write_text("## Reflection cadence\n", encoding="utf-8")

    _run("build-index", repo)
    vocab = set(json.loads((repo / ".prawduct" / ".work-model-index.json").read_text())["vocab"])
    assert {"doxastic", "telemetry", "provenance", "cadence", "attestation", "ledger"} <= vocab

    # Covered by the widened corpus -> silent, even though requirement-shaped.
    res = _run("user-prompt-submit", repo, '{"prompt":"extend the telemetry provenance"}')
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"expected silence, got {res.stdout!r}"


def test_index_rebuilds_when_a_docs_file_is_newer(repo: Path):
    """Staleness must track the WIDENED corpus, not just .prawduct/artifacts/ —
    including a file nested in a docs subdirectory (recursive since gate-noise)."""
    (repo / "docs" / "design").mkdir(parents=True)
    docs_file = repo / "docs" / "design" / "notes.md"
    docs_file.write_text("## Notes\n", encoding="utf-8")
    _run("build-index", repo)
    index_path = repo / ".prawduct" / ".work-model-index.json"

    assert "attestation" in _run(
        "user-prompt-submit", repo, '{"prompt":"add attestation support"}'
    ).stdout
    docs_file.write_text("## Notes\n## Attestation\n", encoding="utf-8")
    old = index_path.stat().st_mtime - 100
    os.utime(index_path, (old, old))
    res = _run("user-prompt-submit", repo, '{"prompt":"add attestation support"}')
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"expected silence after docs rebuild, got {res.stdout!r}"
