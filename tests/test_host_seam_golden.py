"""The hook entry points' exact output, recorded before the host seam moved them.

#1037 moves every host payload read, every ``CLAUDE_*`` root read and every
structured hook response into one module. Claude's behaviour must not move with them
(#928 R-3), and "it still looks right" is not a check, so this file runs the real
entry points as the harness does, one subprocess per case, and compares stdout,
stderr and the exit code byte for byte against goldens recorded from the code
before the refactor.

Each case runs in a sealed environment: a fresh git repo, ``HOME`` and the
config home in the case's temp dir, git's global and system config off. What
the machine running the suite has installed or configured cannot reach the
output, so a golden recorded on one machine holds on another.

**Normalizations — the only ones.** Each replaces one exact string that is a
fact of the run, never a pattern over the output:

- the case's temp directory, as ``<TMP>`` (also in its resolved spelling);
- this checkout's plugin root, as ``<PLUGIN>``;
- the plugin version from ``plugin.json``, as ``<VERSION>``, so a release bump
  does not rewrite every golden;
- the checkout's ``<ref>@<sha>`` (and ``+dirty``) in the banner's provenance
  segment, as ``<REF>@<SHA>``, which moves with every commit and edit;
- the bundled session digest's text, as ``<DIGEST>``, so the digest's own
  edits do not rewrite the SessionStart golden (its JSON envelope is the shape
  under test).

Timestamps would be a sixth; no case's output carries one today, and the test
fails on an unnormalized difference rather than guessing at one.

To re-record after an intended output change, run with
``PRAWDUCT_UPDATE_GOLDENS=1`` and review the diff of
``tests/fixtures/host_seam_golden/`` like code. A golden that changed during a
refactor is a regression, not an update.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import SHAPED_REFLECTION  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / "plugin"
HOOK = PLUGIN / "bin" / "prawduct-hook"
GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "host_seam_golden"
UPDATE = os.environ.get("PRAWDUCT_UPDATE_GOLDENS") == "1"

# A standing block the Stop gate's verdict readers parse (see
# `lib/gates.turn_declares_in_flight`).
_RUNNING_TURN = (
    "Dispatched the review.\n\n---\n\n`STATE` — one file changed.\n\n"
    "`RUNNING` — the Critic review; if it never lands, re-run it.\n\n"
    "`DO NOT CLEAR` — a review is in flight."
)
_COMPLETE_TURN = (
    "Done.\n\n---\n\n`STATE` — one file changed.\n\n`COMPLETE`\n\n"
    "`SAFE TO CLEAR` — nothing is outstanding."
)
_TASKS = [{"type": "workflow", "name": "review-changes", "id": "wf_abc123"}]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=30, check=True,
        env=_sealed_env(repo.parent),
    ).stdout.strip()


def _sealed_env(tmp: Path) -> dict[str, str]:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _hook_env(tmp: Path, repo: Path | None, **extra: str) -> dict[str, str]:
    env = _sealed_env(tmp)
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN)
    if repo is not None:
        env["CLAUDE_PROJECT_DIR"] = str(repo)
    env.update(extra)
    return env


# --- fixture repos -----------------------------------------------------------


def _repo(tmp: Path) -> Path:
    """A governed repo with one commit and a captured session baseline."""
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    (prawduct / ".session-git-baseline").write_text(_git(repo, "status", "--porcelain"))
    (prawduct / ".session-base-tree").write_text(_git(repo, "rev-parse", "HEAD^{tree}"))
    return repo


#: An uncommitted broad except: the compliance canary reads the session's
#: uncommitted changes, so this is what makes it report.
_BROAD_EXCEPT = "try:\n    x = 3\nexcept Exception:\n    pass\n"


def _change_code(repo: Path) -> None:
    (repo / "code.py").write_text("x = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2")


def _plan_repo(tmp: Path, *, reflected: bool = True) -> Path:
    """Judgeable code changed on a branch a build plan claims, and the Critic
    waived. Reflected, the Stop gate passes at exit 0 and the missing forward
    note is its advisory; unreflected, the same advisory rides the block."""
    repo = _repo(tmp)
    _git(repo, "checkout", "-q", "-b", "feature/x")
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir()
    (artifacts / "build-plan-x.md").write_text(
        "---\nartifact: build-plan\nversion: 2\nscope: x\nbranch: feature/x\n"
        "base: main\n---\n\n# Plan\n\n### Chunk 01: Do x\n\n- **Description:** x\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "plan")
    prawduct = repo / ".prawduct"
    (prawduct / ".session-git-baseline").write_text(_git(repo, "status", "--porcelain"))
    (prawduct / ".session-base-tree").write_text(_git(repo, "rev-parse", "HEAD^{tree}"))
    _change_code(repo)
    if reflected:
        (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (prawduct / ".gates-waived").write_text(json.dumps({"critic": "golden fixture"}))
    return repo


# --- running and normalizing -------------------------------------------------


def _run(argv: list[str], env: dict[str, str], cwd: Path, stdin: str = "") -> dict:
    proc = subprocess.run(
        [sys.executable, *argv], input=stdin, capture_output=True, text=True,
        env=env, cwd=str(cwd), timeout=120,
    )
    return {"exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _digest_text() -> str:
    return (PLUGIN / "methodology" / "session-digest.md").read_text(encoding="utf-8").strip()


def _plugin_version() -> str:
    data = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return str(data["version"])


def _checkout_ref_sha() -> str | None:
    """The banner's provenance string for this checkout, derived from git here
    rather than from `banner.py`, whose output is what is under test.

    `+dirty` is part of it: tracked edits anywhere in the checkout set it, so
    without it every golden run during development would fail on the banner."""
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(PLUGIN), *args], capture_output=True, text=True, timeout=15
        ).stdout.strip()

    sha = git("rev-parse", "HEAD")[:7]
    if not sha:
        return None
    ref = git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = "+dirty" if git("status", "--porcelain", "--untracked-files=no") else ""
    return f"{ref if ref and ref != 'HEAD' else 'detached'}@{sha}{dirty}"


def _normalize(text: str, tmp: Path) -> str:
    # JSON-escaped forms first: the digest is embedded in a JSON string.
    digest = _digest_text()
    text = text.replace(json.dumps(digest)[1:-1], "<DIGEST>").replace(digest, "<DIGEST>")
    for spelling in {str(tmp.resolve()), str(tmp)}:
        text = text.replace(spelling, "<TMP>")
    text = text.replace(str(PLUGIN), "<PLUGIN>")
    ref_sha = _checkout_ref_sha()
    if ref_sha:
        text = text.replace(ref_sha, "<REF>@<SHA>")
    return text.replace(_plugin_version(), "<VERSION>")


def _check(name: str, result: dict, tmp: Path) -> None:
    observed = {k: (_normalize(v, tmp) if isinstance(v, str) else v) for k, v in result.items()}
    path = GOLDEN_DIR / f"{name}.json"
    if UPDATE:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(observed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    assert path.is_file(), f"no golden for {name}: record it with PRAWDUCT_UPDATE_GOLDENS=1"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert observed == expected, f"{name}: output differs from its golden ({path.name})"


# --- SessionStart ------------------------------------------------------------


class TestSessionStart:
    def test_banner(self, tmp_path):
        repo = _repo(tmp_path)
        result = _run([str(PLUGIN / "hooks" / "banner.py")], _hook_env(tmp_path, repo), repo)
        _check("banner", result, tmp_path)

    def test_banner_managed_install_under_config_dir(self, tmp_path):
        """`CLAUDE_CONFIG_DIR` locates the managed plugin home: a plugin root
        under it is a managed install, and the banner drops its provenance."""
        repo = _repo(tmp_path)
        config = tmp_path / "config"
        config.mkdir()
        (config / "plugins").symlink_to(REPO_ROOT, target_is_directory=True)
        env = _hook_env(tmp_path, repo, CLAUDE_CONFIG_DIR=str(config))
        result = _run([str(PLUGIN / "hooks" / "banner.py")], env, repo)
        _check("banner_managed", result, tmp_path)

    def test_banner_without_project_dir(self, tmp_path):
        repo = _repo(tmp_path)
        result = _run([str(PLUGIN / "hooks" / "banner.py")], _hook_env(tmp_path, None), repo)
        _check("banner_no_project", result, tmp_path)

    def test_digest(self, tmp_path):
        repo = _repo(tmp_path)
        result = _run([str(PLUGIN / "hooks" / "digest.py")], _hook_env(tmp_path, repo), repo)
        _check("digest", result, tmp_path)

    def test_digest_outside_a_governed_repo(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        result = _run([str(PLUGIN / "hooks" / "digest.py")], _hook_env(tmp_path, plain), plain)
        _check("digest_ungoverned", result, tmp_path)

    def test_clear_session_start(self, tmp_path):
        repo = _repo(tmp_path)
        result = _run([str(HOOK), "clear", "--session-start"], _hook_env(tmp_path, repo), repo)
        _check("clear_session_start", result, tmp_path)

    def test_clear_reads_transcripts_under_the_config_home(self, tmp_path):
        """`CLAUDE_CONFIG_DIR` is where the briefing's worktree scan looks for
        session transcripts: a fresh one for a sibling worktree reads as an
        agent active there. Control: the same repo without the variable has no
        such line, so the line is the config home's doing."""
        repo = _repo(tmp_path)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "state")
        worktree = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
        # Its reflog would read as fresh activity on its own; backdate it so the
        # transcript is the only recent signal.
        month_ago = time.time() - 30 * 86400
        os.utime(repo / ".git" / "worktrees" / "wt" / "logs" / "HEAD", (month_ago, month_ago))
        encoded ="".join(c if c.isalnum() else "-" for c in str(worktree.resolve()))
        transcripts = tmp_path / "config" / "projects" / encoded
        transcripts.mkdir(parents=True)
        (transcripts / "session.jsonl").write_text("{}\n")
        control = _run(
            [str(HOOK), "clear", "--session-start", "--brief-only"], _hook_env(tmp_path, repo), repo
        )
        assert "agent active" not in control["stdout"]
        assert "1 idle" in control["stdout"]
        env = _hook_env(tmp_path, repo, CLAUDE_CONFIG_DIR=str(tmp_path / "config"))
        result = _run([str(HOOK), "clear", "--session-start", "--brief-only"], env, repo)
        assert "agent active" in result["stdout"]
        _check("clear_brief_only_config_home", result, tmp_path)

    def test_clear_session_start_brief_only(self, tmp_path):
        repo = _repo(tmp_path)
        result = _run(
            [str(HOOK), "clear", "--session-start", "--brief-only"], _hook_env(tmp_path, repo), repo
        )
        _check("clear_brief_only", result, tmp_path)


# --- Stop --------------------------------------------------------------------

_STOP_PAYLOADS = {
    "no_fields": {},
    "tasks": {"background_tasks": _TASKS},
    "empty_tasks": {"background_tasks": []},
    "running_turn": {"last_assistant_message": _RUNNING_TURN},
    "complete_turn": {"last_assistant_message": _COMPLETE_TURN},
    "null_message": {"last_assistant_message": None},
    "tasks_and_turn": {"background_tasks": _TASKS, "last_assistant_message": _COMPLETE_TURN},
}


def _stop(tmp: Path, repo: Path, payload: dict | str) -> dict:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return _run([str(HOOK), "stop"], _hook_env(tmp, repo), repo, stdin=stdin)


class TestStop:
    @pytest.mark.parametrize("payload", sorted(_STOP_PAYLOADS))
    def test_clean(self, tmp_path, payload):
        repo = _repo(tmp_path)
        _check(f"stop_clean_{payload}", _stop(tmp_path, repo, _STOP_PAYLOADS[payload]), tmp_path)

    @pytest.mark.parametrize("payload", sorted(_STOP_PAYLOADS))
    def test_blocking(self, tmp_path, payload):
        repo = _repo(tmp_path)
        _change_code(repo)
        _check(f"stop_block_{payload}", _stop(tmp_path, repo, _STOP_PAYLOADS[payload]), tmp_path)

    @pytest.mark.parametrize("payload", sorted(_STOP_PAYLOADS))
    def test_advisory_at_exit_zero(self, tmp_path, payload):
        repo = _plan_repo(tmp_path)
        _check(f"stop_advisory_{payload}", _stop(tmp_path, repo, _STOP_PAYLOADS[payload]), tmp_path)

    def test_a_block_carries_its_advisories_and_canary(self, tmp_path):
        """The block reason's later sections, in order: the advisories (here
        the missing forward note) and the compliance canary (a broad except)."""
        repo = _plan_repo(tmp_path, reflected=False)
        (repo / "code.py").write_text(_BROAD_EXCEPT)
        result = _stop(tmp_path, repo, {})
        assert result["exit"] == 2
        assert "ADVISORIES (not blocking):" in result["stderr"]
        assert "COMPLIANCE CANARY (address if possible):" in result["stderr"]
        _check("stop_block_advisory_canary", result, tmp_path)

    def test_a_clean_stop_reports_its_canary(self, tmp_path):
        repo = _plan_repo(tmp_path)
        (repo / "code.py").write_text(_BROAD_EXCEPT)
        result = _stop(tmp_path, repo, {})
        assert result["exit"] == 0
        assert "COMPLIANCE CANARY (informational):" in result["stderr"]
        _check("stop_advisory_canary", result, tmp_path)

    def test_garbage_stdin_reads_as_no_payload(self, tmp_path):
        repo = _repo(tmp_path)
        _change_code(repo)
        _check("stop_block_garbage", _stop(tmp_path, repo, "not json"), tmp_path)

    def test_redirected_into_a_worktree(self, tmp_path):
        """The hook follows cwd into a worktree of the launch repo and says so."""
        repo = _repo(tmp_path)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "state")
        worktree = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
        result = _run([str(HOOK), "stop"], _hook_env(tmp_path, repo), worktree, stdin="{}")
        _check("stop_worktree_redirect", result, tmp_path)


# --- SubagentStop ------------------------------------------------------------


class TestSubagentStop:
    @pytest.mark.parametrize(
        "name,payload",
        [
            ("reviewer", {"agent_type": "prawduct:critic-reviewer"}),
            ("non_reviewer", {"agent_type": "general-purpose"}),
            ("non_string_agent_type", {"agent_type": 7}),
            ("no_fields", {}),
        ],
    )
    def test_agent_type(self, tmp_path, name, payload):
        repo = _repo(tmp_path)
        payload = {**payload, "cwd": str(repo)}
        result = _run(
            [str(HOOK), "subagent-stop"], _hook_env(tmp_path, repo), repo, stdin=json.dumps(payload)
        )
        _check(f"subagent_stop_{name}", result, tmp_path)
