"""Run `plugin/bin/prawduct-hook` inside the test process, as a fresh child would run it.

Why in-process at all: testament vouches for a git child run under the suite's isolated
environment, and for nothing else a test spawns, so a test that runs the hook as a `python3`
child can never have its result reused. Calling `main()` here keeps the hook's own git children
the only subprocesses, and those are the vouched kind.

What a fresh `python3 prawduct-hook <args>` child gave a test, and how :func:`run_hook` gives
the same:

- **argv dispatch and exit code.** `main()` reads `sys.argv` and returns the exit code, so argv
  is swapped for the call. A command that raises `SystemExit` is read the way the interpreter
  reads it: `None` is 0, an int is itself, anything else is printed to stderr and is 1.
- **stdout and stderr, at the file descriptors.** Fds 1 and 2 are pointed at temporary files for
  the call, and `sys.stdout`/`sys.stderr` write to them, so output from a child the hook starts
  without capturing lands in the same stream, in order, as it did through a pipe. stdin is empty,
  as a closed pipe is.
- **cwd and environment.** The caller's `cwd` (or the process's, as `subprocess.run` without
  `cwd` inherited it) and its environment overlay are applied for the call and restored after,
  over the suite's environment rather than in place of it, so `conftest.TEST_ENV` (git's
  isolation and the suite's one clock) and any seam a fixture sets reach the hook's git children
  and its code. What a scratch child environment used
  to keep out is stripped instead: :data:`STRIPPED_ENV` (the host's and CI's variables, which a
  developer's session or a CI job sets ambiently) and git's repository-locating variables.
- **process state.** Each call executes a fresh copy of the hook's module, so the hook's own
  globals start new. The library modules are shared with the test process, so every module-level
  value production mutates is listed in :data:`PROCESS_STATE`: emptied or reset before the call,
  restored after, so neither a previous call nor the test's own in-process use leaks into the
  hook, and the hook leaks nothing back. :data:`PROCESS_CONSTANTS` lists the memos left alone
  because a fresh process computes the same value (the running plugin's own build and code
  identity among them). `tests/test_hook_inproc.py` derives both from
  the code, so a new memo cannot be missed by forgetting to list it.
- **exit handlers.** The tree-key memo saves itself from an `atexit` handler; the call runs that
  save before it returns, as a child's exit did.
- **a process that is gone afterwards.** A child's pid named no live process once it exited, and
  the test-evidence recorder stamps its pid into an `in_progress` record that `test-status` later
  probes. So for the call `lib.record_progress` reads its pid as :data:`EXITED_PID`, which no
  process can hold, and a stamp the call leaves behind reads as interrupted, as the child's did.
  Only that module's view changes: anything else that writes or probes its own pid during the
  call (a temp-file name, a lock) sees a live process, as the child saw itself.

What it cannot give: a timeout (nothing can stop a call in this process), and a different
interpreter. A test whose subject is the process boundary itself (the entry point parsing on an
old interpreter, the exit status the OS reports) runs a real child and says so with
`@pytest.mark.uncacheable`.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import types
from contextlib import ExitStack, contextmanager
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = PLUGIN_ROOT / "bin" / "prawduct-hook"

#: Variables a fresh child never saw, because the helpers built its environment from scratch: the
#: host's and the plugin's own switches, and the CI context the backlog's write guards read. A
#: developer's Claude Code session or a GitHub Actions job sets these ambiently, and the hook
#: would act on them (`CLAUDE_CONFIG_DIR` points it at the real configuration home,
#: `GITHUB_ACTIONS` makes it an unattended actor). An overlay naming one sets it for the call.
#: `tests/test_hook_inproc.py` checks this against the names production reads.
STRIPPED_ENV = frozenset({
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PROJECT_DIR",
    "GITHUB_ACTIONS",
    "GITHUB_EVENT_NAME",
    "GITHUB_HEAD_REF",
    "GITHUB_REPOSITORY",
    "GITHUB_WORKFLOW",
    "PRAWDUCT_ACTOR_AUTHORIZED",
    "PRAWDUCT_ALLOW_EPHEMERAL_WRITES",
    "PRAWDUCT_GIT_TIMEOUT",
    "PRAWDUCT_HOST",
    "PRAWDUCT_PR_HEAD_REPO",
    "PRAWDUCT_PYTHON_REEXEC",
    "PRAWDUCT_UNATTENDED",
    "PRAWDUCT_VERIFY_CHUNK_ID",
    "PRAWDUCT_WORKER",
    "TESTAMENT_HOME",
})

#: Module-level values production changes while it runs, as `(module, attribute, fresh value)`.
#: A container is emptied in place (other modules may hold the same object); anything else is
#: rebound to the fresh value.
PROCESS_STATE = (
    ("lib.advisory_store", "_REGISTRY", dict),
    ("lib.buildplan_refs", "_GIT_REF_NAMES_CACHE", dict),
    ("lib.buildplan_refs", "_GIT_REMOTE_SLUGS_CACHE", dict),
    ("lib.critic_marker", "LAST_ROSTER_ERROR", None),
    ("lib.evidence", "_ATTRIBUTED_BAD_TIMEOUTS", set),
    ("lib.evidence", "_ATTRIBUTED_BAD_TREES", set),
    ("lib.record_progress", "_PROBED", dict),
    ("lib.tree_key_memo", "_MEMOS", dict),
    ("_python_floor", "REEXECUTED_FROM", None),
)

#: Per-process memos deliberately NOT reset, with why a fresh process would compute the same.
#: The first three describe the running plugin, which is this checkout's: production memoises
#: them because the code that runs cannot change under a running process, and the code the hook
#: runs here is the test process's own. Resetting them would make every call probe this
#: checkout's repository, a live-state read no fixture controls.
PROCESS_CONSTANTS = {
    ("lib.evidence", "_build_memo"): "the running plugin's build, its checkout's commit",
    ("lib.verdict_cache", "_CODE_IDENTITY"): "the running plugin's code identity",
    ("lib.verdict_cache", "_MODULE_DIGEST"): "the bytes of the running plugin's identity modules",
    ("lib.learnings_files", "glob_to_regex"): "a pure function of its argument",
    ("lib.record_progress", "this_machine"): "this machine's boot identity, the same in any process",
}

#: One above the largest pid Linux can allocate (`pid_max` is at most 2**22), and far above
#: macOS's 99,998, so no process holds it and a liveness probe of it reads "exited".
EXITED_PID = 2**22 + 1

_code: types.CodeType | None = None


def _hook_code() -> types.CodeType:
    """The hook's compiled code, compiled once per process: compiling it is most of a load."""
    global _code
    if _code is None:
        _code = compile(HOOK.read_text(encoding="utf-8"), str(HOOK), "exec")
    return _code


def _fresh_hook() -> types.ModuleType:
    """A new module executing the hook's code. Not named `__main__`, so the Python floor check
    (a re-exec on an old interpreter) and the script's own `sys.exit(main())` do not run."""
    module = types.ModuleType("prawduct_hook_inproc")
    module.__file__ = str(HOOK)
    exec(_hook_code(), module.__dict__)
    return module


def _repo_locating_env() -> frozenset[str]:
    from lib import gitstate  # noqa: PLC0415 — conftest seeds the plugin on sys.path

    return gitstate.REPO_LOCATING_ENV


@contextmanager
def _environment(overlay: dict[str, str]):
    saved = dict(os.environ)
    try:
        for name in STRIPPED_ENV | _repo_locating_env():
            os.environ.pop(name, None)
        os.environ.update(overlay)
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


@contextmanager
def _cwd(cwd: Path | str | None):
    if cwd is None:
        yield
        return
    saved = os.getcwd()
    os.chdir(cwd)
    try:
        yield
    finally:
        os.chdir(saved)


class _OsWithAnExitedPid:
    """`os`, as `lib.record_progress` sees it for a call: its own pid is :data:`EXITED_PID`."""

    @staticmethod
    def getpid() -> int:
        return EXITED_PID

    def __getattr__(self, name: str):
        return getattr(os, name)


@contextmanager
def _exited_pid():
    """The recorder's stamp names a process that is gone, and only the stamp: the rest of the
    process (a temp-file name, a lock, the test's own liveness probes) keeps its real pid."""
    from lib import record_progress  # noqa: PLC0415 — the module the hook's lazy import reaches

    saved = record_progress.os
    record_progress.os = _OsWithAnExitedPid()
    try:
        yield
    finally:
        record_progress.os = saved


@contextmanager
def _argv(argv: list[str]):
    saved = sys.argv
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = saved


def _reset(module: types.ModuleType, attr: str, fresh) -> None:
    current = getattr(module, attr)
    if isinstance(current, (dict, set, list)):
        current.clear()
    else:
        setattr(module, attr, fresh)


@contextmanager
def _fresh_process_state():
    """Every :data:`PROCESS_STATE` value as a new process has it, for the call; restored after.

    Only modules already imported hold state; one the call imports starts fresh by itself, and is
    reset again afterwards so the call's values do not reach the test's own use of it."""
    restore = []
    for module_name, attr, fresh in PROCESS_STATE:
        module = sys.modules.get(module_name)
        if module is None:
            restore.append((module_name, attr, fresh, None))
            continue
        current = getattr(module, attr)
        saved = current.copy() if isinstance(current, (dict, set, list)) else current
        _reset(module, attr, fresh)
        restore.append((module_name, attr, fresh, (saved,)))
    try:
        yield
    finally:
        for module_name, attr, fresh, saved in reversed(restore):
            module = sys.modules.get(module_name)
            if module is None:
                continue
            _reset(module, attr, fresh)
            if saved is None:
                continue
            (value,) = saved
            current = getattr(module, attr)
            if isinstance(current, list):
                current.extend(value)
            elif isinstance(current, (dict, set)):
                current.update(value)
            else:
                setattr(module, attr, value)


@contextmanager
def _captured_fds(stdin: str):
    """Point fds 1 and 2 (and `sys.stdout`/`sys.stderr`) at temp files and `sys.stdin` at
    ``stdin``; yield a dict holding their bytes once the call is over."""
    out_file = tempfile.TemporaryFile()
    err_file = tempfile.TemporaryFile()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError):
            pass
    saved_fds = (os.dup(1), os.dup(2))
    saved_streams = (sys.stdout, sys.stderr, sys.stdin)
    os.dup2(out_file.fileno(), 1)
    os.dup2(err_file.fileno(), 2)
    # Unbuffered byte writes through to the fds, so the hook's prints and its children's
    # uncaptured output interleave as they did through a pipe.
    sys.stdout = io.TextIOWrapper(
        open(os.dup(1), "wb", buffering=0), encoding="utf-8", write_through=True
    )
    # The interpreter's own stderr escapes what it cannot encode (a surrogate from a
    # non-UTF-8 path) rather than raising; its stdout is strict.
    sys.stderr = io.TextIOWrapper(
        open(os.dup(2), "wb", buffering=0), encoding="utf-8", errors="backslashreplace",
        write_through=True,
    )
    sys.stdin = io.StringIO(stdin)
    result: dict[str, bytes] = {}
    try:
        yield result
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
                stream.close()
            except (OSError, ValueError):
                pass
        sys.stdout, sys.stderr, sys.stdin = saved_streams
        os.dup2(saved_fds[0], 1)
        os.dup2(saved_fds[1], 2)
        os.close(saved_fds[0])
        os.close(saved_fds[1])
        for key, handle in (("stdout", out_file), ("stderr", err_file)):
            handle.seek(0)
            result[key] = handle.read()
            handle.close()


def _text(data: bytes) -> str:
    """Decode as `subprocess.run(text=True)` does: UTF-8, universal newlines."""
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace").read()


def _exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)
    return 1


def run_hook(
    *args: str,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    """Run `prawduct-hook <args>` in this process; return what `subprocess.run(...,
    capture_output=True, text=True)` of a fresh child would have.

    ``env`` is overlaid on the suite's environment (after :data:`STRIPPED_ENV` and git's
    repository-locating variables are removed) for the call only. ``cwd`` is entered for the
    call; ``None`` keeps the current one, as `subprocess.run` without `cwd` did. ``input`` is
    what the hook reads from stdin, as `subprocess.run(input=...)`; ``None`` is an empty stdin.
    """
    argv = [str(HOOK), *args]
    with ExitStack() as stack:
        stack.enter_context(_environment(env or {}))
        stack.enter_context(_cwd(cwd))
        stack.enter_context(_argv(argv))
        stack.enter_context(_exited_pid())
        stack.enter_context(_fresh_process_state())
        captured = stack.enter_context(_captured_fds(input or ""))
        try:
            returncode = _fresh_hook().main()
        except SystemExit as exc:
            returncode = _exit_code(exc)
        finally:
            # A child's exit ran this `atexit` handler; its NOTE belongs to the call's stderr.
            memo = sys.modules.get("lib.tree_key_memo")
            if memo is not None:
                memo.flush_all()
    return subprocess.CompletedProcess(
        argv, returncode, _text(captured["stdout"]), _text(captured["stderr"])
    )
