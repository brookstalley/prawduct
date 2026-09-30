"""Telemetry names a governed repo by its identity, never by the directory a
session happens to run in.

A devcontainer mounts every workspace at one fixed path — discodon's at
`/opt/venv` — so every ledger event it wrote read `project: "venv"` (#933). A
worktree's directory names the worktree. The label resolves, in order: the
committed `product_identity.name`, the origin remote's repository name, the
main checkout's directory, and only then the directory itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import gitstate  # noqa: E402

HOOK = ROOT / "bin" / "prawduct-hook"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _repo(path: Path, origin: str | None = None) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    (path / "app.py").write_text("x = 1\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "init")
    if origin:
        _git(path, "remote", "add", "origin", origin)
    (path / ".prawduct").mkdir()
    return path


def _declare(repo: Path, name: str) -> None:
    (repo / ".prawduct" / "project-state.yaml").write_text(
        f"product_identity:\n  name: \"{name}\"\n"
    )


@pytest.mark.parametrize(
    "origin",
    [
        "git@github.com:pacepace/discodon.git",
        "https://github.com/pacepace/discodon.git",
        "https://github.com/pacepace/discodon/",
        "ssh://git@host:2222/team/discodon",
    ],
)
def test_a_container_mount_is_labelled_by_its_origin(tmp_path, origin):
    repo = _repo(tmp_path / "opt" / "venv", origin)
    assert gitstate.project_label(repo) == "discodon"


def test_a_declared_product_name_wins_as_a_slug(tmp_path):
    repo = _repo(tmp_path / "venv", "git@github.com:x/other.git")
    _declare(repo, "Acme Widgets")
    assert gitstate.project_label(repo) == "acme-widgets"


def test_a_placeholder_name_declares_nothing(tmp_path):
    repo = _repo(tmp_path / "checkout", "git@github.com:x/real.git")
    _declare(repo, "{{product_name}}")
    assert gitstate.project_label(repo) == "real"


def test_a_worktree_without_a_remote_takes_the_main_checkout_name(tmp_path):
    main = _repo(tmp_path / "discodon")
    worktree = tmp_path / "wt-discodon-kairo"
    _git(main, "worktree", "add", "-q", str(worktree), "-b", "kairo")
    assert gitstate.project_label(worktree) == "discodon"


def test_outside_git_the_directory_is_all_there_is(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert gitstate.project_label(plain) == "plain"


def test_the_ledger_records_the_label_not_the_mount_path(tmp_path):
    """At the layer the defect was reported at: an appended ledger event."""
    repo = _repo(tmp_path / "opt" / "venv", "git@github.com:pacepace/discodon.git")
    head = _git(repo, "rev-parse", "HEAD")
    (repo / ".prawduct" / ".critic-findings.json").write_text(json.dumps({
        "timestamp": "2026-09-30T00:00:00Z", "duration_seconds": 60,
        "mode": "final (full review, ready for push)",
        "commit_reviewed": head, "files_reviewed": ["app.py"],
        "findings": [], "summary": "No issues found.",
    }))
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    r = subprocess.run(
        [sys.executable, str(HOOK), "ledger-append", "--event", "review.critic"],
        cwd=str(repo), capture_output=True, text=True, timeout=60, env=env,
    )
    assert r.returncode == 0, r.stderr
    lines = (repo / ".prawduct" / ".governance-ledger.jsonl").read_text().splitlines()
    assert [json.loads(line)["project"] for line in lines] == ["discodon"]


def test_the_briefing_still_reads_the_declared_name_verbatim(tmp_path):
    from lib import briefing
    repo = _repo(tmp_path / "r")
    _declare(repo, "Acme Widgets")
    assert briefing._get_product_name(repo / ".prawduct") == "Acme Widgets"


def test_review_stats_reports_the_label_not_the_mount_path(tmp_path):
    """The report header, the other place the directory name used to leak."""
    repo = _repo(tmp_path / "opt" / "venv", "git@github.com:pacepace/discodon.git")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    r = subprocess.run(
        [sys.executable, str(HOOK), "review-stats", "--json"],
        cwd=str(repo), capture_output=True, text=True, timeout=60, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["project"] == "discodon"


def test_a_lone_remote_not_called_origin_still_names_the_repo(tmp_path):
    repo = _repo(tmp_path / "opt" / "venv")
    _git(repo, "remote", "add", "upstream", "git@github.com:pacepace/discodon.git")
    assert gitstate.project_label(repo) == "discodon"
