"""Prawduct's Python floor, enforced before an entry point reads anything newer.

Every hook and CLI entry point is started by a bare ``python3`` (``hooks.json``,
the skills' ``python3 plugin/bin/prawduct-hook`` fallbacks, the shebang), and each
consumer machine resolves that name on its own: a pyenv shim, the system
interpreter, Homebrew. Claude Code treats a crashing hook as a non-blocking error,
so an interpreter below the floor would not stop governance — it would silence it.

So each entry point calls :func:`ensure` before any other import. Below the floor
it looks for an interpreter that qualifies and re-executes the same command under
it; when there is none it fails loudly, in the way the entry point's caller will
actually see.

This file, and the top of every entry point up to the :func:`ensure` call, must
parse under the oldest ``python3`` a consumer machine still resolves (macOS ships
3.9). ``tests/test_python_floor.py`` pins that with ``ast.parse(...,
feature_version=...)``: newer syntax here would raise ``SyntaxError`` before the
check could run, which is the silent failure this module exists to prevent.
"""

import os
import subprocess
import sys

FLOOR = (3, 14)

#: Set on the re-executed process to the interpreter it was first started under.
#: Seeing it under an interpreter still below the floor means discovery lied about
#: a candidate, so fail rather than re-execute again.
REEXEC_ENV = "PRAWDUCT_PYTHON_REEXEC"

#: In a re-executed process, the interpreter the caller originally invoked —
#: the project's own `python3`, which is what a pytest fallback must run under,
#: since the qualifying interpreter found here may not have the project's
#: packages, or pytest at all. ``None`` when no re-exec happened.
REEXECUTED_FROM = None

#: How many minor versions above the floor to look for by name (``python3.14``…).
_NAMED_MINORS = 6

_PROBE = "import sys; sys.exit(0 if sys.version_info[:2] >= (%d, %d) else 1)" % FLOOR

_INSTALL_HINT = (
    "Install Python {floor} so that `python{floor}` is on PATH (for example "
    "`brew install python@{floor}`, `uv python install {floor}`, or "
    "`pyenv install {floor}`), then restart Claude Code."
)


def floor_text():
    return "%d.%d" % FLOOR


def _named_candidates(environ):
    """Every ``python3.N`` (N from the floor up) on PATH, in PATH order per name.

    Every PATH entry, not only the first: a pyenv shim named ``python3.14``
    exists wherever any installed pyenv version provides it, and fails when the
    version selected for this directory does not — the next entry may serve."""
    names = ["python3.%d" % m for m in range(FLOOR[1], FLOOR[1] + _NAMED_MINORS)]
    dirs = [d for d in environ.get("PATH", "").split(os.pathsep) if d]
    for name in names:
        for d in dirs:
            path = os.path.join(d, name)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                yield path


def _uv_candidate(environ, run):
    """``uv python find`` for the floor, when uv is installed. It only finds — it
    never downloads — so it costs one process and changes nothing."""
    for d in environ.get("PATH", "").split(os.pathsep):
        uv = os.path.join(d, "uv") if d else ""
        if uv and os.path.isfile(uv) and os.access(uv, os.X_OK):
            break
    else:
        return None
    try:
        found = run(
            [uv, "python", "find", ">=%s" % floor_text()],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = found.stdout.strip() if found.returncode == 0 else ""
    return path or None


def qualifies(path, run=subprocess.run):
    """Run the candidate once: a name says nothing about what a shim will serve."""
    try:
        return run([path, "-c", _PROBE], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_interpreter(environ=None, run=subprocess.run):
    """The first interpreter at or above the floor, or ``None``."""
    environ = os.environ if environ is None else environ
    seen = set()
    for path in _named_candidates(environ):
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        if qualifies(path, run):
            return path
    path = _uv_candidate(environ, run)
    if path and os.path.realpath(path) not in seen and qualifies(path, run):
        return path
    return None


def role_of(entry, argv):
    """How a failure must surface for this entry point's caller.

    ``banner``: SessionStart stdout reaches the model, so the notice goes there.
    ``quiet``: the other SessionStart hooks — the banner speaks for the session.
    ``gate``: Stop and SubagentStop — never exit 2, which would ask the agent to
    fix what only the user can, every turn.
    ``cli``: everything a person or skill runs."""
    name = os.path.basename(entry)
    sub = argv[1] if len(argv) > 1 else ""
    if name == "banner.py":
        return "banner"
    if name == "digest.py" or (name == "prawduct-hook" and sub == "clear"):
        return "quiet"
    if name == "prawduct-hook" and sub in ("stop", "subagent-stop"):
        return "gate"
    return "cli"


def _found_text(version_info, executable):
    return "Python %d.%d (%s)" % (version_info[0], version_info[1], executable or "unknown path")


def fail(role, version_info, executable, out, err, looped=False):
    """Report the missing interpreter for ``role``; return the exit code."""
    found = _found_text(version_info, executable)
    hint = _INSTALL_HINT.format(floor=floor_text())
    if looped:
        why = "re-executed under %s, which is still below the floor" % found
    else:
        why = "the hooks found only %s and no python%s" % (found, floor_text())
    if role == "banner":
        out.write(
            "PRAWDUCT GOVERNANCE IS OFF THIS SESSION: prawduct needs Python %s or newer; "
            "%s. No gate, review or briefing will run. Tell the user this before anything "
            "else. %s\n" % (floor_text(), why, hint)
        )
        return 0
    err.write("ERROR: prawduct needs Python %s or newer; %s. %s\n" % (floor_text(), why, hint))
    return 0 if role == "quiet" else 1


def ensure(entry, argv=None, environ=None, version_info=None, executable=None,
           run=subprocess.run, execve=os.execve, out=None, err=None):
    """Return when this interpreter meets the floor; otherwise re-execute
    ``entry`` under one that does, or exit with :func:`fail`'s code.

    Call it only when the entry point runs as a program: a test importing the
    module must never have its process replaced."""
    version_info = sys.version_info if version_info is None else version_info
    if tuple(version_info[:2]) >= FLOOR:
        # The guard has done its job. A child this process starts may be another
        # entry point under an older `python3`; it must look for an interpreter
        # again, not read the inherited flag as its own loop.
        if environ is None:
            global REEXECUTED_FROM
            REEXECUTED_FROM = os.environ.pop(REEXEC_ENV, None) or None
        return
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    executable = sys.executable if executable is None else executable
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    role = role_of(entry, argv)
    if environ.get(REEXEC_ENV):
        sys.exit(fail(role, version_info, executable, out, err, looped=True))
    target = find_interpreter(environ, run)
    if target is None:
        sys.exit(fail(role, version_info, executable, out, err))
    env = dict(environ)
    env[REEXEC_ENV] = executable or "unknown"
    out.flush()
    err.flush()
    execve(target, [target, entry] + list(argv[1:]), env)
