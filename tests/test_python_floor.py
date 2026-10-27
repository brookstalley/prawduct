"""The Python floor: entry points find a qualifying interpreter or fail loudly.

Every entry point is started by a bare ``python3`` that each consumer machine
resolves on its own, and a hook that crashes is a non-blocking error in Claude
Code — so an interpreter below the floor would silence governance rather than
stop it. ``plugin/bin/_python_floor.py`` re-executes the entry point under an
interpreter that qualifies, or reports the gap where the caller will see it.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
_FLOOR_PATH = _PLUGIN / "bin" / "_python_floor.py"

_spec = importlib.util.spec_from_file_location("python_floor_under_test", _FLOOR_PATH)
floor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(floor)

#: Every file an interpreter is pointed at directly. Each must parse on the
#: oldest `python3` a consumer still resolves, or it raises SyntaxError before
#: its floor check can run.
ENTRY_POINTS = [
    _PLUGIN / "bin" / "prawduct-hook",
    _PLUGIN / "bin" / "test-reference-verify",
    _PLUGIN / "hooks" / "banner.py",
    _PLUGIN / "hooks" / "digest.py",
]

#: macOS still ships 3.9 as /usr/bin/python3.
OLDEST_PARSER = (3, 9)


def _write_python(path: Path, exit_code: int) -> Path:
    """A stand-in interpreter: a script that answers the version probe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    path.chmod(0o755)
    return path


class TestEntryPointsParseOnOldInterpreters:
    @pytest.mark.parametrize("path", ENTRY_POINTS + [_FLOOR_PATH], ids=lambda p: p.name)
    def test_it_parses_at_the_oldest_feature_version(self, path):
        ast.parse(path.read_text(), filename=str(path), feature_version=OLDEST_PARSER)

    @pytest.mark.parametrize("newer", [
        "match x:\n    case 1:\n        pass\n",
        "type X = int\n",
        "def f[T](x: T): pass\n",
        "try:\n    pass\nexcept* E:\n    pass\n",
        "try:\n    pass\nexcept A, B:\n    pass\n",
        'x = t"hi"\n',
    ], ids=["match", "type-stmt", "generic-def", "except-star", "except-no-parens", "t-string"])
    def test_the_parser_check_can_fail(self, newer):
        """Positive control: `feature_version` refuses these, so the check above
        is not vacuous for them. It is best-effort and does NOT refuse every
        newer form — same-quote nested f-strings (3.12) and parenthesised
        `with` (3.10) pass it — which is why the real-interpreter check below
        exists."""
        ast.parse(newer)
        with pytest.raises(SyntaxError):
            ast.parse(newer, feature_version=OLDEST_PARSER)

    @pytest.mark.parametrize("path", ENTRY_POINTS + [_FLOOR_PATH], ids=lambda p: p.name)
    def test_a_real_older_interpreter_parses_it(self, path):
        """The exact check `feature_version` approximates: the older interpreter's
        own parser. Runs wherever one exists (macOS's 3.9, a CI image's system
        `python3`)."""
        old = _older_python3()
        if old is None:
            pytest.skip("no python3 below 3.14 on this machine")
        res = subprocess.run(
            [old, "-c", "import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])", str(path)],
            capture_output=True, text=True,
        )
        assert res.returncode == 0, res.stderr

    @pytest.mark.parametrize("path", ENTRY_POINTS, ids=lambda p: p.name)
    def test_the_check_runs_before_any_other_import(self, path):
        """Only the floor's own imports may precede the check: anything else
        imported first could need a newer interpreter and crash before it."""
        allowed = {"__future__", "os", "sys", "_python_floor"}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.If) and "_python_floor.ensure" in ast.unparse(node):
                assert "__name__" in ast.unparse(node.test)
                return
            if isinstance(node, ast.Import):
                assert {a.name for a in node.names} <= allowed, ast.unparse(node)
            if isinstance(node, ast.ImportFrom):
                assert node.module in allowed, ast.unparse(node)
        pytest.fail(f"{path.name} never calls _python_floor.ensure under __main__")


class TestDiscovery:
    def test_a_failing_shim_is_skipped_for_a_later_path_entry(self, tmp_path):
        shim = _write_python(tmp_path / "shims" / "python3.14", 1)
        real = _write_python(tmp_path / "brew" / "python3.14", 0)
        environ = {"PATH": os.pathsep.join([str(shim.parent), str(real.parent)])}
        assert floor.find_interpreter(environ) == str(real)

    def test_a_newer_named_minor_qualifies(self, tmp_path):
        newer = _write_python(tmp_path / "bin" / "python3.16", 0)
        assert floor.find_interpreter({"PATH": str(newer.parent)}) == str(newer)

    def test_uv_is_asked_when_no_name_qualifies(self, tmp_path):
        found = _write_python(tmp_path / "uvpy" / "python", 0)
        uv = tmp_path / "bin" / "uv"
        uv.parent.mkdir()
        uv.write_text(f"#!/bin/sh\necho {found}\n")
        uv.chmod(0o755)
        assert floor.find_interpreter({"PATH": str(uv.parent)}) == str(found)

    def test_nothing_qualifying_is_none(self, tmp_path):
        _write_python(tmp_path / "bin" / "python3.14", 1)
        assert floor.find_interpreter({"PATH": str(tmp_path / "bin")}) is None


def _ensure(entry, argv, environ, version=(3, 9, 6)):
    """Run `ensure` below the floor with every effect captured."""
    calls: list[tuple] = []
    out, err = io.StringIO(), io.StringIO()
    code = None
    try:
        floor.ensure(
            entry, argv=argv, environ=environ, version_info=version,
            executable="/usr/bin/python3", out=out, err=err,
            execve=lambda *a: calls.append(a),
        )
    except SystemExit as exc:
        code = exc.code
    return code, calls, out.getvalue(), err.getvalue()


class TestEnsure:
    def test_at_the_floor_it_returns_and_clears_an_inherited_flag(self, monkeypatch):
        monkeypatch.setenv(floor.REEXEC_ENV, "/usr/bin/python3")
        monkeypatch.setattr(floor, "REEXECUTED_FROM", None)
        calls: list[tuple] = []
        floor.ensure("prawduct-hook", version_info=(3, 14, 0), execve=lambda *a: calls.append(a))
        assert calls == []
        assert floor.REEXEC_ENV not in os.environ
        assert floor.REEXECUTED_FROM == "/usr/bin/python3"

    def test_below_it_reexecutes_the_same_command(self, tmp_path):
        target = _write_python(tmp_path / "bin" / "python3.14", 0)
        environ = {"PATH": str(target.parent), "KEEP": "me"}
        code, calls, _out, _err = _ensure(
            "/plugin/bin/prawduct-hook", ["prawduct-hook", "stop", "--x"], environ
        )
        assert code is None
        assert len(calls) == 1
        path, argv, env = calls[0]
        assert path == str(target)
        assert argv == [str(target), "/plugin/bin/prawduct-hook", "stop", "--x"]
        assert env[floor.REEXEC_ENV] == "/usr/bin/python3", "carries the invoked interpreter"
        assert env["KEEP"] == "me"

    def test_a_reexecuted_process_still_below_it_fails_instead_of_looping(self, tmp_path):
        target = _write_python(tmp_path / "bin" / "python3.14", 0)
        environ = {"PATH": str(target.parent), floor.REEXEC_ENV: "1"}
        code, calls, _out, err = _ensure("prawduct-hook", ["prawduct-hook", "test-status"], environ)
        assert calls == []
        assert code == 1
        assert err.startswith("ERROR:") and "re-executed" in err


class TestFailureSurfacesWhereTheCallerLooks:
    @staticmethod
    def _none(tmp_path):
        return {"PATH": str(tmp_path / "empty")}

    def test_the_banner_tells_the_model_on_stdout(self, tmp_path):
        code, calls, out, err = _ensure("/p/hooks/banner.py", ["banner.py"], self._none(tmp_path))
        assert (code, calls, err) == (0, [], "")
        assert out.startswith("PRAWDUCT GOVERNANCE IS OFF THIS SESSION")
        assert "Tell the user" in out and "python3.14" in out and "Python 3.9" in out

    @pytest.mark.parametrize("entry,argv", [
        ("/p/hooks/digest.py", ["digest.py"]),
        ("/p/bin/prawduct-hook", ["prawduct-hook", "clear", "--session-start"]),
    ])
    def test_the_other_session_start_hooks_stay_quiet(self, tmp_path, entry, argv):
        code, _calls, out, err = _ensure(entry, argv, self._none(tmp_path))
        assert code == 0 and out == ""
        assert err.startswith("ERROR:")

    @pytest.mark.parametrize("sub", ["stop", "subagent-stop"])
    def test_a_stop_gate_never_exits_two(self, tmp_path, sub):
        """Exit 2 at Stop blocks the turn and hands the agent a problem only the
        user can fix, every turn. Exit 1 is shown to the user and blocks nothing."""
        code, _calls, out, err = _ensure("/p/bin/prawduct-hook", ["prawduct-hook", sub], self._none(tmp_path))
        assert code == 1 and out == ""
        assert err.startswith("ERROR: prawduct needs Python 3.14")

    def test_a_candidate_that_would_not_run_is_named(self, tmp_path):
        """The pyenv case: `python3.14` is on PATH as a shim for a version this
        directory does not select. The user can see it, so "none found" alone
        would contradict them; the message names it and the pyenv step that
        makes it selectable."""
        shim = _write_python(tmp_path / "shims" / "python3.14", 1)
        code, _calls, _out, err = _ensure(
            "/p/bin/prawduct-hook", ["prawduct-hook", "test-status"], {"PATH": str(shim.parent)}
        )
        assert code == 1
        assert f"found but would not run: {shim}" in err
        assert "pyenv local <current> 3.14" in err

    def test_the_cli_names_the_interpreter_and_the_fix(self, tmp_path):
        code, _calls, _out, err = _ensure(
            "/p/bin/test-reference-verify", ["test-reference-verify"], self._none(tmp_path)
        )
        assert code == 1
        assert "/usr/bin/python3" in err and "brew install python@3.14" in err


class TestThePytestFallbackRunsTheInvokedInterpreter:
    """With no test command declared, `test-evidence record` falls back to
    `<python> -m pytest`. After a re-exec that must be the `python3` the caller
    invoked — the project's — not the qualifying one found for the hook."""

    @staticmethod
    def _hook():
        from importlib.machinery import SourceFileLoader

        loader = SourceFileLoader("prawduct_hook_floor_test", str(_PLUGIN / "bin" / "prawduct-hook"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def test_after_a_reexec_it_is_the_invoked_interpreter(self, monkeypatch):
        hook = self._hook()
        monkeypatch.setattr(hook._python_floor, "REEXECUTED_FROM", "/project/.venv/bin/python3")
        assert hook._fallback_pytest_python() == "/project/.venv/bin/python3"

    def test_without_one_it_is_this_interpreter(self, monkeypatch):
        hook = self._hook()
        monkeypatch.setattr(hook._python_floor, "REEXECUTED_FROM", None)
        assert hook._fallback_pytest_python() == sys.executable


def _older_python3() -> "str | None":
    for candidate in ("/usr/bin/python3", shutil.which("python3")):
        if not candidate:
            continue
        probe = subprocess.run(
            [candidate, "-c", "import sys; print(sys.version_info[:2] < (3, 14))"],
            capture_output=True, text=True,
        )
        if probe.returncode == 0 and probe.stdout.strip() == "True":
            return candidate
    return None


class TestThePythonFloorReport:
    """`prawduct-hook python-floor` is what `/prawduct:doctor` relays."""

    def test_a_direct_run_reports_no_reexec(self):
        hook = str(_PLUGIN / "bin" / "prawduct-hook")
        env = {k: v for k, v in os.environ.items() if k != floor.REEXEC_ENV}
        res = subprocess.run([sys.executable, hook, "python-floor"], capture_output=True, text=True, env=env)
        assert res.returncode == 0, res.stderr
        first, second = res.stdout.splitlines()
        assert first.startswith(f"python: {sys.executable} (") and first.endswith("meets the 3.14 floor")
        assert second == "invoked as: the interpreter above (no re-exec)"

    def test_a_reexecuted_run_names_where_it_started(self):
        old = _older_python3()
        if old is None or floor.find_interpreter() is None:
            pytest.skip("needs both a python3 below 3.14 and one at it on this machine")
        hook = str(_PLUGIN / "bin" / "prawduct-hook")
        env = {k: v for k, v in os.environ.items() if k != floor.REEXEC_ENV}
        res = subprocess.run([old, hook, "python-floor"], capture_output=True, text=True, env=env)
        assert res.returncode == 0, res.stderr
        assert "below the floor — re-executed under the interpreter above" in res.stdout.splitlines()[1]


class TestOnARealOlderInterpreter:
    def test_prawduct_hook_reexecutes_and_answers(self):
        old = _older_python3()
        if old is None or floor.find_interpreter() is None:
            pytest.skip("needs both a python3 below 3.14 and one at it on this machine")
        hook = str(_PLUGIN / "bin" / "prawduct-hook")
        env = {k: v for k, v in os.environ.items() if k != floor.REEXEC_ENV}
        under_old = subprocess.run([old, hook, "version"], capture_output=True, text=True, env=env)
        direct = subprocess.run([sys.executable, hook, "version"], capture_output=True, text=True, env=env)
        assert under_old.returncode == 0, under_old.stderr
        assert under_old.stdout == direct.stdout
