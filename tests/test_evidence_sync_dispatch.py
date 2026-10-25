"""``prawduct-hook evidence sync|configure`` reach ``lib.evidence_sync`` (#1052).

One router (R-6): the hook's ``cmd_evidence`` hands every op to
``lib.evidence.evidence_cmd``, which dispatches ``sync`` and ``configure`` to
``evidence_sync.cmd_evidence_sync`` and ``evidence_sync.cmd_evidence_configure``
— ``(project_dir, args) -> int``, exit 0 ok, 1 a reported failure naming the
step, 2 usage — importing that module only for those two ops. These pin only
the wiring: every op passes through the lib router, each of the two routes to
its function with the op's own arguments, the function's exit code is the
command's, and a lib that cannot provide the function fails closed (exit 1,
nothing claimed). The module is stubbed through ``sys.modules`` (and the
``lib`` package attribute the router's ``from . import`` reads), so what is
tested is the wiring, not the transport, which ``tests/test_evidence_sync.py``
owns. The guards' classification of both ops is pinned in
``test_ephemeral_worktree.py`` and ``test_binary_skew_guard.py``.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lib  # noqa: E402
from lib import evidence  # noqa: E402


def _load_hook():
    loader = importlib.machinery.SourceFileLoader("prawduct_hook_evidence_sync_dispatch", str(HOOK))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def stub(monkeypatch):
    """A stand-in ``lib.evidence_sync`` recording each call, returning ``rc``."""
    module = types.ModuleType("lib.evidence_sync")
    module.calls = []
    module.rc = 0

    def make(name):
        def fn(project_dir, args):
            module.calls.append((name, project_dir, list(args)))
            return module.rc
        return fn

    module.cmd_evidence_sync = make("sync")
    module.cmd_evidence_configure = make("configure")
    monkeypatch.setitem(sys.modules, "lib.evidence_sync", module)
    monkeypatch.setattr(lib, "evidence_sync", module, raising=False)
    return module


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["sync"], ("sync", [])),
        (["sync", "--no-push", "--json"], ("sync", ["--no-push", "--json"])),
        (["configure"], ("configure", [])),
        (["configure", "--apply", "--json"], ("configure", ["--apply", "--json"])),
    ],
)
def test_each_op_reaches_its_function_with_its_own_arguments(tmp_path, stub, argv, expected):
    hook = _load_hook()
    assert hook.cmd_evidence(tmp_path, argv) == 0
    assert stub.calls == [(expected[0], tmp_path, expected[1])]


@pytest.mark.parametrize("op", ["sync", "configure"])
def test_the_lib_router_itself_reaches_the_function(tmp_path, stub, op):
    """R-6: the lib's router dispatches the two ops (it printed a usage and
    exited 1 for them while the hook routed them around it)."""
    assert evidence.evidence_cmd(tmp_path, [op, "--json"]) == 0
    assert stub.calls == [(op, tmp_path, ["--json"])]


@pytest.mark.parametrize("argv", [[], ["status"], ["list", "-n", "1"], ["ingest"], ["sync"],
                                  ["configure", "--apply"], ["no-such-op"]])
def test_the_hook_hands_every_op_to_the_one_lib_router(tmp_path, monkeypatch, argv):
    """R-6: the hook is a thin call. Every op — reads, writes, an unknown one —
    reaches ``lib.evidence.evidence_cmd`` with the argv as given, and its exit
    code is the command's."""
    seen = []

    def router(project_dir, given):
        seen.append((project_dir, list(given)))
        return 7

    monkeypatch.setattr(evidence, "evidence_cmd", router)
    assert _load_hook().cmd_evidence(tmp_path, list(argv)) == 7
    assert seen == [(tmp_path, list(argv))]


@pytest.mark.parametrize("rc", [0, 1, 2])
@pytest.mark.parametrize("op", ["sync", "configure"])
def test_the_functions_exit_code_is_the_commands(tmp_path, stub, op, rc):
    stub.rc = rc
    assert _load_hook().cmd_evidence(tmp_path, [op]) == rc


def test_the_reads_do_not_reach_the_sync_module(tmp_path, stub, capsys):
    """Control: `status` still goes to the store reader, never to sync."""
    _load_hook().cmd_evidence(tmp_path, ["status"])
    assert stub.calls == []


@pytest.mark.parametrize("op", ["sync", "configure"])
def test_a_lib_without_the_function_fails_closed(tmp_path, monkeypatch, capsys, op):
    """A lib/ whose transport module is missing the function (a broken
    install) must not read as a sync that ran: exit 1, and the reason names
    the missing piece."""
    empty = types.ModuleType("lib.evidence_sync")
    monkeypatch.setitem(sys.modules, "lib.evidence_sync", empty)
    monkeypatch.setattr(lib, "evidence_sync", empty, raising=False)
    assert _load_hook().cmd_evidence(tmp_path, [op]) == 1
    err = capsys.readouterr().err
    assert f"evidence {op} unavailable" in err
    assert "nothing was" in err
