"""The in-process hook runner (`tests/_hook_inproc.py`) gives a test what a fresh `python3
prawduct-hook` child gave it.

Two kinds of check. The inventories are derived from the code, so a memo or an environment
switch added to production fails here until the runner says what to do with it. The behaviour
checks call `run_hook` and observe, from inside the hook's own first step, what the call ran
under: its argv, environment, cwd, pid and library state.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import _hook_inproc
from _hook_inproc import EXITED_PID, HOOK, PLUGIN_ROOT, run_hook

_CACHE_DECORATORS = {"cache", "lru_cache", "functools.cache", "functools.lru_cache"}
_MUTATORS = {
    "append", "add", "update", "setdefault", "pop", "popitem", "clear", "extend", "insert",
    "remove", "discard",
}


def _production_files() -> list[tuple[str, Path]]:
    """`(module name, path)` for every production Python module the hook can load."""
    files = [
        (".".join(path.relative_to(PLUGIN_ROOT).with_suffix("").parts).removesuffix(".__init__"),
         path)
        for path in sorted((PLUGIN_ROOT / "lib").rglob("*.py"))
    ]
    files += [(path.stem, path) for path in sorted((PLUGIN_ROOT / "bin").glob("*.py"))]
    files.append(("prawduct-hook", HOOK))
    return files


def _process_state_in(tree: ast.Module) -> set[str]:
    """Module-level names a function rebinds (`global`) or mutates in place, plus functions a
    per-process cache decorates: what a long-lived process carries from one call to the next."""
    module_names = set()
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        module_names.update(t.id for t in targets if isinstance(t, ast.Name))
    found = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in fn.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if ast.unparse(target) in _CACHE_DECORATORS:
                found.add(fn.name)
        for node in ast.walk(fn):
            if isinstance(node, ast.Global):
                found.update(node.names)
            elif isinstance(node, (ast.Assign, ast.AugAssign, ast.Delete)):
                targets = node.targets if not isinstance(node, ast.AugAssign) else [node.target]
                found.update(
                    t.value.id for t in targets
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                    and t.value.id in module_names
                )
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr in _MUTATORS and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in module_names):
                found.add(node.func.value.id)
    return found


def _production_process_state() -> set[tuple[str, str]]:
    found = set()
    for module_name, path in _production_files():
        for name in _process_state_in(ast.parse(path.read_text(encoding="utf-8"))):
            found.add((module_name, name))
    return found


class TestInventories:
    def test_every_value_production_keeps_across_calls_is_reset_or_declared_constant(self):
        """A memo the runner neither resets nor declares would carry one test's repository
        into the next test's hook. The hook script's own globals are exempt: each call
        executes a fresh copy of it."""
        found = {entry for entry in _production_process_state() if entry[0] != "prawduct-hook"}
        assert ("lib.tree_key_memo", "_MEMOS") in found, "the scan found nothing: it is broken"
        assert ("lib.record_progress", "this_machine") in found, "decorated caches not scanned"
        reset = {(module, attr) for module, attr, _fresh in _hook_inproc.PROCESS_STATE}
        constant = set(_hook_inproc.PROCESS_CONSTANTS)
        assert not reset & constant, reset & constant
        assert found - reset - constant == set(), (
            "module state the in-process runner does not handle: add it to PROCESS_STATE "
            "(reset per call) or PROCESS_CONSTANTS (with why a fresh process computes the same)"
        )
        assert (reset | constant) - found == set(), "entries that no longer name process state"

    def test_the_scan_sees_each_shape_of_process_state(self):
        """The scan's own control: each shape it must catch, and a constant table it must not."""
        source = (
            "import functools\n"
            "TABLE = {'a': 1}\n_MEMO = {}\n_SEEN = set()\n_ONCE = None\n_ROWS = []\n"
            "def lookup(k):\n    return TABLE[k]\n"
            "def remember(k, v):\n    _MEMO[k] = v\n"
            "def note(x):\n    _SEEN.add(x)\n"
            "def once():\n    global _ONCE\n    _ONCE = 1\n"
            "def row(x):\n    _ROWS.append(x)\n"
            "@functools.lru_cache(maxsize=4)\ndef pure(x):\n    return x\n"
        )
        assert _process_state_in(ast.parse(source)) == {"_MEMO", "_SEEN", "_ONCE", "_ROWS", "pure"}

    def test_every_switch_production_reads_from_the_environment_is_classified(self):
        """The helpers this runner replaced gave the hook a scratch environment, so no host or
        CI variable reached it. A new switch production reads must be stripped (the caller's
        session or CI job would otherwise steer the hook) or named as not an environment read."""
        literal = re.compile(r"""["']((?:CLAUDE|PRAWDUCT|TESTAMENT|GITHUB)_[A-Z0-9_]+)["']""")
        names = set()
        for _module, path in _production_files():
            names.update(literal.findall(path.read_text(encoding="utf-8")))
        assert "CLAUDE_CONFIG_DIR" in names, "the scan found nothing: it is broken"
        # Names that must reach the hook, or are no environment read at all. A test seam a
        # fixture sets (a clock, say) belongs here: stripping it would hand the hook the real one.
        passed_through = {
            "PRAWDUCT_VERSION",  # `lib/__init__`'s export table names the constant
            "PRAWDUCT_TEST_ONLY_FROZEN_NOW",  # the suite's one clock (`lib/clock.py`), set by conftest
            "PRAWDUCT_TEST_ONLY_ENTROPY_SEED",  # the suite's id tokens (`lib/entropy.py`), set by conftest
        }
        assert names - _hook_inproc.STRIPPED_ENV - passed_through == set()
        assert _hook_inproc.STRIPPED_ENV - names == set(), "stripped names production never reads"


@pytest.fixture
def seen(monkeypatch, tmp_path):
    """Record what the hook ran under, from its first act: `get_project_dir` asks the host seam
    for the launch-dir hint before any command runs."""
    run_hook("version", cwd=tmp_path)  # loads the host seam into this process
    host = sys.modules["prawduct_host"]
    record: dict = {}
    real_hint = host.project_dir_hint

    def probe():
        from lib import buildplan_refs, critic_marker, record_progress  # noqa: PLC0415

        record.update(
            argv=list(sys.argv), cwd=os.getcwd(), pid=os.getpid(), env=dict(os.environ),
            recorder_pid=record_progress.stamp("probe", "2026-01-01T12:00:00Z")["pid"],
            ref_cache=dict(buildplan_refs._GIT_REF_NAMES_CACHE),
            roster_error=critic_marker.LAST_ROSTER_ERROR,
        )
        if "raise" in record:
            raise record["raise"]
        return real_hint()

    monkeypatch.setattr(host, "project_dir_hint", probe)
    return record


class TestWhatTheCallRunsUnder:
    def test_argv_cwd_and_pid_are_a_childs_and_are_restored(self, seen, tmp_path):
        before = (list(sys.argv), os.getcwd(), os.getpid())
        result = run_hook("resolve-base", cwd=tmp_path)
        assert seen["argv"] == [str(HOOK), "resolve-base"]
        assert Path(seen["cwd"]).resolve() == tmp_path.resolve()
        # The recorder's stamp names a gone process; the process itself keeps its pid.
        assert seen["recorder_pid"] == EXITED_PID
        assert seen["pid"] == os.getpid()
        assert (list(sys.argv), os.getcwd(), os.getpid()) == before
        assert result.args == [str(HOOK), "resolve-base"]

    def test_the_environment_is_overlaid_stripped_and_restored(self, seen, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "real-config"))
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GIT_DIR", str(tmp_path / "another" / ".git"))
        monkeypatch.setenv("PRAWDUCT_TEST_SEAM_PROBE", "set by a fixture")
        before = dict(os.environ)
        run_hook("resolve-base", cwd=tmp_path, env={"HOME": str(tmp_path / "home")})
        env = seen["env"]
        assert env["HOME"] == str(tmp_path / "home")
        assert env["PRAWDUCT_TEST_SEAM_PROBE"] == "set by a fixture"
        assert env["GIT_AUTHOR_NAME"] == os.environ["GIT_AUTHOR_NAME"]  # the suite's git env
        for stripped in ("CLAUDE_CONFIG_DIR", "GITHUB_ACTIONS", "GIT_DIR"):
            assert stripped not in env, stripped
        assert dict(os.environ) == before

    def test_an_overlay_may_set_a_stripped_variable(self, seen, tmp_path):
        run_hook("resolve-base", cwd=tmp_path, env={"CLAUDE_PROJECT_DIR": str(tmp_path)})
        assert seen["env"]["CLAUDE_PROJECT_DIR"] == str(tmp_path)

    def test_library_state_starts_fresh_and_the_tests_own_comes_back(self, seen, tmp_path):
        from lib import buildplan_refs, critic_marker  # noqa: PLC0415

        buildplan_refs._GIT_REF_NAMES_CACHE["/elsewhere"] = frozenset({"main"})
        critic_marker.LAST_ROSTER_ERROR = "left by an earlier call"
        before = dict(buildplan_refs._GIT_REF_NAMES_CACHE)  # an earlier test may add its own
        try:
            run_hook("resolve-base", cwd=tmp_path)
            assert seen["ref_cache"] == {}
            assert seen["roster_error"] is None
            assert buildplan_refs._GIT_REF_NAMES_CACHE == before
            assert critic_marker.LAST_ROSTER_ERROR == "left by an earlier call"
        finally:
            buildplan_refs._GIT_REF_NAMES_CACHE.pop("/elsewhere", None)
            critic_marker.LAST_ROSTER_ERROR = None


class TestWhatTheCallReturns:
    @pytest.mark.parametrize(("code", "returncode"), [(None, 0), (0, 0), (3, 3), ("why", 1)])
    def test_a_system_exit_is_read_as_the_interpreter_reads_it(self, seen, tmp_path, code, returncode):
        seen["raise"] = SystemExit(code)
        result = run_hook("resolve-base", cwd=tmp_path)
        assert result.returncode == returncode
        assert ("why" in result.stderr) == (code == "why")

    def test_the_exit_code_is_mains(self, tmp_path):
        assert run_hook("version", cwd=tmp_path).returncode == 0
        unknown = run_hook("no-such-command", cwd=tmp_path)
        assert unknown.returncode == 1
        assert "Usage" in unknown.stderr or "usage" in unknown.stderr, unknown.stderr
        assert unknown.stdout == ""

    def test_output_written_to_the_descriptors_is_captured_in_order(self, monkeypatch, tmp_path):
        """A child the hook starts without capturing writes to fd 1 and 2, not to
        `sys.stdout`; both must land in the call's streams, interleaved as written."""
        def probe_writes():
            print("from print")
            os.write(1, b"from the descriptor\n")
            print("to stderr", file=sys.stderr)
            os.write(2, b"stderr descriptor\n")
            raise SystemExit(0)

        run_hook("version", cwd=tmp_path)  # loads the host seam into this process
        monkeypatch.setattr(sys.modules["prawduct_host"], "project_dir_hint", probe_writes)
        result = run_hook("resolve-base", cwd=tmp_path)
        assert result.stdout == "from print\nfrom the descriptor\n"
        assert result.stderr == "to stderr\nstderr descriptor\n"

    def test_the_exit_handler_runs_inside_the_call(self, monkeypatch, tmp_path):
        from lib import tree_key_memo  # noqa: PLC0415

        calls = []

        def flush_all():
            calls.append(1)
            print("NOTE: flushed", file=sys.stderr)

        monkeypatch.setattr(tree_key_memo, "flush_all", flush_all)
        result = run_hook("version", cwd=tmp_path)
        assert calls == [1]
        assert "NOTE: flushed" in result.stderr

    def test_stderr_escapes_what_it_cannot_encode_as_the_interpreters_does(self):
        """Before `main` reconfigures the streams (the hook module's own load, an exit
        message after it), the call's stderr is the runner's, so it must escape as the
        interpreter's stderr does rather than raise."""
        with _hook_inproc._captured_fds("") as captured:
            print("path-\udcff", file=sys.stderr)
        assert captured["stderr"] == b"path-\\udcff\n"

    def test_the_calls_pid_names_no_process(self):
        """What the recorder's liveness probe asks first. End to end, a recorder stamp a call
        leaves reads `stale (interrupted)` (`test_plugin_runtime.py`'s
        `_assert_only_the_attempts_stub`), as a dead child's did."""
        with pytest.raises(ProcessLookupError):
            os.kill(EXITED_PID, 0)
        os.kill(os.getpid(), 0)  # control: the live process answers


class TestStubbedExecutables:
    """`stubs` answers a stubbed executable's `subprocess.run` as a child's would be read."""

    @staticmethod
    def _stub(argv, stdin):
        return (3 if "fail" in argv else 0), f"out {argv[1:]} {stdin}\n", "err\n"

    def test_a_captured_call_gets_the_answer_as_text_or_bytes(self):
        with _hook_inproc._stubbed_children({"git": self._stub}):
            text = subprocess.run(["git", "a"], capture_output=True, text=True, input="in")
            raw = subprocess.run(["/opt/x/git", "a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert (text.returncode, text.stdout, text.stderr) == (0, "out ['a'] in\n", "err\n")
        assert (raw.stdout, raw.stderr) == (b"out ['a'] None\n", b"err\n"), "any path to the name"

    def test_bytes_input_reaches_the_stub_and_comes_back_byte_for_byte(self):
        """A child gets ``input=`` bytes as they are, so the stub hands them on losslessly."""
        raw = b"\xff\xfe not utf-8"
        with _hook_inproc._stubbed_children({"git": lambda argv, stdin: (0, stdin, "")}):
            echoed = subprocess.run(["git"], input=raw, capture_output=True)
        assert echoed.stdout == raw

    @pytest.mark.parametrize("kwargs", [
        {"stdout": "FILE"}, {"stderr": "FILE"}, {"stdout": 1}, {"stdin": "FILE"},
    ])
    def test_a_stream_the_stub_cannot_model_is_refused_not_dropped(self, tmp_path, kwargs):
        """A file or descriptor target: a child would write or read there, and the stub cannot,
        so it refuses rather than return a result that looks like a run."""
        with open(tmp_path / "f", "w+") as handle:
            kwargs = {k: (handle if v == "FILE" else v) for k, v in kwargs.items()}
            with _hook_inproc._stubbed_children({"git": self._stub}):
                with pytest.raises(TypeError, match="stubbed executable"):
                    subprocess.run(["git", "a"], **kwargs)
            with _hook_inproc._stubbed_children({"gh": self._stub}):  # control: unstubbed git runs
                assert subprocess.run(["git", "--version"], **{**kwargs, "stdin": None}).returncode == 0

    def test_check_raises_on_a_non_zero_answer(self):
        with _hook_inproc._stubbed_children({"git": self._stub}):
            with pytest.raises(subprocess.CalledProcessError) as raised:
                subprocess.run(["git", "fail"], capture_output=True, text=True, check=True)
            unchecked = subprocess.run(["git", "fail"], capture_output=True, text=True)
        assert raised.value.returncode == 3
        assert unchecked.returncode == 3, "control: without check the code is returned"

    def test_stderr_to_stdout_merges_and_an_uncaptured_stream_reaches_the_descriptor(self):
        with _hook_inproc._captured_fds("") as captured:
            with _hook_inproc._stubbed_children({"git": self._stub}):
                merged = subprocess.run(["git", "m"], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                inherited = subprocess.run(["git", "i"])
                dropped = subprocess.run(["git", "d"], stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
        assert (merged.stdout, merged.stderr) == ("out ['m'] None\nerr\n", None)
        assert (inherited.stdout, inherited.stderr, dropped.stdout) == (None, None, None)
        assert captured["stdout"] == b"out ['i'] None\n"
        assert captured["stderr"] == b"err\n"

    def test_an_unstubbed_executable_still_starts_and_the_patch_is_gone_after(self, tmp_path):
        real = subprocess.run
        with _hook_inproc._stubbed_children({"gh": self._stub}):
            started = subprocess.run(["git", "--version"], capture_output=True, text=True,
                                     cwd=tmp_path)
        assert started.returncode == 0 and started.stdout.startswith("git version"), started
        assert subprocess.run is real

    def test_run_hook_answers_the_hooks_own_git_from_the_stub(self, tmp_path):
        """End to end: the hook's `git` reaches the stub, and nothing reaches it without one."""
        asked: list[list[str]] = []

        def git(argv, _stdin):
            asked.append(argv[1:])
            return 0, "stubbed-base\n", ""

        run_hook("resolve-base", cwd=tmp_path, stubs={"git": git})
        assert asked, "the hook's git calls never reached the stub"
        asked.clear()
        run_hook("resolve-base", cwd=tmp_path, stubs={"gh": git})
        assert asked == [], "control: a stub answers only the executable it is named for"


@pytest.mark.uncacheable(
    "its subject is the process boundary: a real python3 child of the entry point, compared "
    "with the in-process call"
)
class TestAChildAgrees:
    @pytest.mark.parametrize(("args", "pin"), [
        (("version",), None), (("no-such-command",), None), (("resolve-base",), None),
        # A path that is not UTF-8 reaches stderr as a surrogate, which both escape.
        (("contribute",), "not-utf8-\udcff"),
    ], ids=["version", "unknown", "resolve-base", "surrogate-on-stderr"])
    def test_a_real_child_and_the_in_process_call_answer_alike(self, tmp_path, args, pin):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        (repo / "f").write_text("x\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=repo, check=True)
        env = {"HOME": str(tmp_path / "home"), "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
               "PYTHONDONTWRITEBYTECODE": "1"}
        if pin is not None:
            env["CLAUDE_PROJECT_DIR"] = str(tmp_path / pin)
        child = subprocess.run(
            [sys.executable, str(HOOK), *args], cwd=repo, capture_output=True, text=True,
            env={**{k: v for k, v in os.environ.items()
                    if k not in _hook_inproc.STRIPPED_ENV}, **env},
            timeout=90,
        )
        inproc = run_hook(*args, cwd=repo, env=env)
        assert (inproc.returncode, inproc.stdout, inproc.stderr) == (
            child.returncode, child.stdout, child.stderr
        )
        if pin is not None:
            assert "not-utf8-\\udcff" in child.stderr, "precondition: the surrogate reached stderr"


# --- no hook child is started with a hand-built environment ---------------------------------
#
# `conftest.TEST_ENV` (git's isolation, the test identity and the suite's one clock) reaches a
# child through the environment it is given: the process's own (`os.environ`, or `run_hook`'s
# overlay on it) or `conftest.scrubbed_env`. A child of the hook given an environment written out
# key by key gets none of it, so the git it runs reads the machine's global config and the hook
# stamps the wall clock beside commits dated on the suite's. The shape is found by what it is,
# whatever the helper is called: a subprocess call whose argv names the hook and whose `env` is
# a dict built only from literal keys, directly or through a name assigned in the same function.

_SUBPROCESS_CALLS = {"run", "Popen", "check_output", "check_call", "call"}
_NAMES_THE_HOOK = re.compile(r"HOOK|prawduct-hook")


def _built_from_scratch(node: ast.AST) -> bool:
    """A dict display with no `**` spread, or `dict(...)` with keywords only."""
    if isinstance(node, ast.Dict):
        return all(key is not None for key in node.keys)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        return not node.args and all(kw.arg is not None for kw in node.keywords)
    return False


def _hand_built_hook_children(source: str, filename: str) -> list[str]:
    found = []
    tree = ast.parse(source, filename)
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        assigned = {
            node.targets[0].id: node.value
            for node in ast.walk(scope)
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        }
        for call in ast.walk(scope):
            if not isinstance(call, ast.Call) or not call.args:
                continue
            func = call.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            argv = call.args[0]
            if isinstance(argv, ast.Name):
                argv = assigned.get(argv.id, argv)
            if name not in _SUBPROCESS_CALLS or not _NAMES_THE_HOOK.search(ast.unparse(argv)):
                continue
            env = next((kw.value for kw in call.keywords if kw.arg == "env"), None)
            if isinstance(env, ast.Name):
                env = assigned.get(env.id)
            if env is not None and _built_from_scratch(env):
                found.append(f"{filename}:{call.lineno}")
    return sorted(set(found))


_A_HAND_BUILT_HOOK_CHILD = '''
import subprocess, sys
def _cli(root):
    return subprocess.run([sys.executable, str(_HOOK), "install-tripwire"],
                          env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(root)})
def _named(root):
    env = dict(PATH="/usr/bin:/bin")
    return subprocess.Popen([sys.executable, str(HOOK_PATH), "stop"], env=env)
def _argv_by_name(root):
    cmd = [sys.executable, str(REPO_ROOT / "bin" / "prawduct-hook"), "x"]
    return subprocess.run(cmd, env={"PATH": "/usr/bin:/bin"})
'''

_HOOK_CHILDREN_THAT_INHERIT = '''
import os, subprocess, sys
def _ok(root, home):
    subprocess.run([sys.executable, str(HOOK), "x"], env=scrubbed_env(home, A="1"))
    subprocess.run([sys.executable, str(HOOK), "x"], env={**os.environ, "A": "1"})
    subprocess.run([sys.executable, str(HOOK), "x"], env={**_git_env(root), "A": "1"})
    subprocess.run(["git", "status"], env={"PATH": "/usr/bin"})  # not the hook
'''


class TestNoHookChildIsStartedWithAHandBuiltEnvironment:
    def test_the_scan_flags_the_shape_and_passes_what_inherits(self):
        assert _hand_built_hook_children(_A_HAND_BUILT_HOOK_CHILD, "fixture.py") == [
            "fixture.py:11", "fixture.py:4", "fixture.py:8",
        ]
        assert _hand_built_hook_children(_HOOK_CHILDREN_THAT_INHERIT, "fixture.py") == []

    def test_no_test_starts_one(self):
        tests_dir = Path(__file__).resolve().parent
        found: list[str] = []
        hook_children = 0
        for path in sorted(tests_dir.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            rel = str(path.relative_to(tests_dir))
            found += _hand_built_hook_children(source, rel)
            hook_children += len(re.findall(r"str\(_?HOOK(?:_PATH)?\)", source))
        assert hook_children > 50, "the scan must have reached the suite's hook children"
        assert found == [], (
            "build the child's environment with conftest.scrubbed_env, or call run_hook:\n  "
            + "\n  ".join(found)
        )
