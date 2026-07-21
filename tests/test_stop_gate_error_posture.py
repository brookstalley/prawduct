"""The Stop-hook Critic gate fails closed AND loud on an internal crash (C3).

Kernel-v3 ch.06 review (sustainability note): ``cmd_stop`` wraps
``gates.session_review_verdict`` in a broad except so a gate bug can never
crash session end — but the old handler swallowed the exception into an
empty verdict, which rendered as the generic "no composed review coverage"
block: an internal error misreported as a coverage verdict, exactly the
attribution loss the C3 fail-loud invariant forbids. The handler now
carries the crash into an ``error``-status verdict and ``cmd_stop`` renders
a dedicated "gate error" block naming it.

Nothing in-tree currently raises through ``session_review_verdict`` (its
callees return error dicts by design), so the crash is injected by
monkeypatch — this pins the defense-in-depth rendering, not a reproducible
in-tree failure.

Deliberately narrow: only the CRASH path takes the new "gate error"
rendering (distinct ``gate-crash`` status). A verdict that *returns*
``status: "error"`` (capture/HEAD failures) keeps the legacy generic
rendering — its reasons are already attributed and remedy-bearing, and the
mock-git harnesses in ``test_stop_abandoned_critic.py`` /
``test_plugin_runtime.py`` pin that contract.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

sys.path.insert(0, str(_ROOT))
from lib import gates  # noqa: E402

# Load the extensionless plugin-runtime hook (SourceFileLoader — shebang
# script, no .py extension; module name is not "__main__" so the CLI
# dispatch does not run at import).
_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_gate_error", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_gate_error", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )


def _blocking_session(tmp_path: Path) -> Path:
    """A repo whose Stop would reach the Critic coverage gate: committed
    baseline, an uncommitted judgeable change, an active build plan, and a
    satisfied reflection gate (so the Critic gate is the only blocker)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    prawduct = repo / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "artifacts" / "build-plan.md").write_text(
        "# Build Plan\n\n## Status\n\n- [ ] Chunk 01: work\n"
    )
    (prawduct / ".session-reflected").write_text(
        "A sufficiently long session reflection so only the Critic gate can block here.\n"
    )
    (repo / "code.py").write_text("x = 2\n")  # judgeable session change
    return repo


class TestGateErrorFailsClosedAndLoud:
    def test_crash_renders_gate_error_not_a_coverage_verdict(
        self, tmp_path, monkeypatch, capsys
    ):
        repo = _blocking_session(tmp_path)
        monkeypatch.setattr(
            gates,
            "session_review_verdict",
            lambda project_dir: (_ for _ in ()).throw(RuntimeError("boom-XYZ")),
        )

        rc = _hook.cmd_stop(repo, {})
        err = capsys.readouterr().err

        assert rc == 2  # fail closed — the session does not end "clean"
        assert "CRITIC REVIEW (gate error)" in err
        assert "boom-XYZ" in err  # ...and loud: the actual crash is named
        # The crash must NOT be misreported as a coverage verdict.
        assert "no composed review coverage" not in err

    def test_real_uncovered_verdict_still_renders_coverage_block(
        self, tmp_path, capsys
    ):
        # Contrast pin: with no crash injected, the same session state
        # renders the genuine coverage blocker — the error branch did not
        # swallow the normal path.
        repo = _blocking_session(tmp_path)

        rc = _hook.cmd_stop(repo, {})
        err = capsys.readouterr().err

        assert rc == 2
        assert "no composed review coverage" in err
        assert "CRITIC REVIEW (gate error)" not in err
