"""The unloaded-plugin tripwire: a project SessionStart hook that says when
prawduct is not loaded (``plugin/lib/unloaded_tripwire.py``).

Three layers, each pinned where it can break:

- **The command itself**, run through a real shell against fixture
  ``installed_plugins.json`` files — loud only on a clean read that lacks a
  record for this repo, silent when the plugin is installed, and a
  could-not-verify line (never "not active") for every other case, a missing
  ``python3`` included. Its verdict is checked against
  ``plugin_activation.plugin_activation_status`` on the same fixtures, because
  the hook is an inlined copy of that rule and a copy is what drifts.
- **The writers**: ``ensure_tripwire`` merges idempotently, and every path that
  writes a product's settings (``transform_settings`` → ``init-product`` and
  ``/prawduct:migrate``, and ``prawduct-hook install-tripwire``) puts it there.
- **The nudge**: the ``tripwire-missing`` probe fires on an onboarded repo that
  lacks it, and through the composition root.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib import plugin_activation as pa  # noqa: E402
from lib import unloaded_tripwire as tw  # noqa: E402
from lib import install_reference_probes as irp  # noqa: E402
from lib.advisory_store import (  # noqa: E402
    Codebase,
    ProjectState,
    clear_registry,
    make_codebase,
    run_all_probes,
)
from lib.migrate_plugin import INSTALL_REFERENCE, transform_settings  # noqa: E402

_HOOK = _PLUGIN_ROOT / "bin" / "prawduct-hook"
_LOUD = "PRAWDUCT GOVERNANCE IS NOT ACTIVE"
_SOFT = "PRAWDUCT: could not verify"


# --- running the command -----------------------------------------------------


@pytest.fixture
def world(tmp_path):
    """A repo, another repo, a config dir, a home outside the repo, and a bin
    directory whose only ``python3`` is the interpreter running these tests."""
    repo = tmp_path / "repo"
    other = tmp_path / "other"
    config = tmp_path / "config"
    home = tmp_path / "home"
    bindir = tmp_path / "bin"
    for d in (repo, other, config / "plugins", home, bindir):
        d.mkdir(parents=True)
    (bindir / "python3").symlink_to(sys.executable)
    return {"repo": repo, "other": other, "config": config, "home": home, "bin": bindir}


def _manifest(world, content) -> Path:
    path = world["config"] / "plugins" / "installed_plugins.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def _run_hook(world, *, shell="/bin/sh", path=None, config=True, project=None):
    env = {
        "PATH": path if path is not None else f"{world['bin']}:/usr/bin:/bin",
        "HOME": str(world["home"]),
        "CLAUDE_PROJECT_DIR": str(project or world["repo"]),
    }
    if config:
        env["CLAUDE_CONFIG_DIR"] = str(world["config"])
    proc = subprocess.run(
        [shell, "-c", tw.TRIPWIRE_COMMAND], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _record(path) -> dict:
    return {"scope": "project", "projectPath": str(path), "version": "3.7.2"}


def test_empty_plugins_is_the_loud_line(world):
    """The field case (#1078): a fresh profile whose manifest is `{"plugins": {}}`."""
    _manifest(world, {"version": 2, "plugins": {}})
    out = _run_hook(world)
    assert out.startswith(_LOUD)
    assert "claude plugin install prawduct@prawduct" in out
    assert "--plugin-dir" in out
    assert str(world["config"]) in out


def test_user_scope_record_is_silent(world):
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "user"}]}})
    assert _run_hook(world) == ""


def test_project_record_for_this_repo_is_silent(world):
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [_record(world["repo"])]}})
    assert _run_hook(world) == ""


def test_project_record_through_a_symlink_is_silent(world, tmp_path):
    """The record and CLAUDE_PROJECT_DIR spell the same repo differently."""
    link = tmp_path / "link"
    link.symlink_to(world["repo"])
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [_record(link)]}})
    assert _run_hook(world) == ""


def test_project_dir_through_a_symlink_is_silent(world, tmp_path):
    """The other direction: the session started through a symlink to the repo."""
    link = tmp_path / "link"
    link.symlink_to(world["repo"])
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [_record(world["repo"].resolve())]}})
    assert _run_hook(world, project=link) == ""


def test_record_for_a_different_repo_only_is_the_loud_line(world):
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [_record(world["other"])]}})
    assert _run_hook(world).startswith(_LOUD)


@pytest.mark.parametrize(
    "content, reason",
    [
        ("{not json", "unreadable"),
        ({"version": 2, "plugins": []}, "unreadable"),
        ({"version": 2, "plugins": {pa.PLUGIN_ID: {"scope": "user"}}}, "unreadable"),
        # One record this check cannot read might have been the matching one.
        ({"version": 2, "plugins": {pa.PLUGIN_ID: ["x", _record("/elsewhere")]}}, "unreadable"),
    ],
)
def test_an_unreadable_manifest_never_claims_not_installed(world, content, reason):
    _manifest(world, content)
    out = _run_hook(world)
    assert out.startswith(_SOFT)
    assert f"({reason}:" in out
    assert _LOUD not in out


def test_a_missing_manifest_is_could_not_verify(world):
    """The module's rule: a missing file is ``unknown``, not ``inactive``."""
    out = _run_hook(world)
    assert out.startswith(_SOFT)
    assert "(missing:" in out


def test_a_missing_python3_is_still_visible(world):
    """No interpreter must not mean no output — the hook's sh half speaks."""
    _manifest(world, {"version": 2, "plugins": {}})
    empty = world["home"] / "nobin"
    empty.mkdir()
    out = _run_hook(world, path=str(empty))
    assert out.startswith(_SOFT)
    assert "python3 could not be run" in out


def test_a_python3_that_fails_to_run_is_still_visible(world):
    """The macOS `/usr/bin/python3` shim exists and exits non-zero."""
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "user"}]}})
    shim = world["home"] / "shimbin"
    shim.mkdir()
    (shim / "python3").write_text("#!/bin/sh\necho 'xcrun: error' >&2\nexit 1\n")
    (shim / "python3").chmod(0o755)
    out = _run_hook(world, path=f"{shim}:/usr/bin:/bin")
    assert "python3 could not be run" in out


def test_default_config_dir_is_home_dot_claude(world):
    (world["home"] / ".claude" / "plugins").mkdir(parents=True)
    (world["home"] / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {}})
    )
    assert _run_hook(world, config=False).startswith(_LOUD)


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/bash"])
def test_runs_the_same_under_sh_and_bash(world, shell):
    """Claude Code runs a command hook through `sh -c` or bash by default."""
    if not Path(shell).exists():
        pytest.skip(f"{shell} not present")
    _manifest(world, {"version": 2, "plugins": {}})
    assert _run_hook(world, shell=shell).startswith(_LOUD)
    _manifest(world, {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "user"}]}})
    assert _run_hook(world, shell=shell) == ""


@pytest.mark.parametrize(
    "content",
    [
        {"version": 2, "plugins": {}},
        {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "user"}]}},
        {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "global"}]}},
        {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "local", "projectPath": "REPO"}]}},
        {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "local", "projectPath": "OTHER"}]}},
        {"version": 2, "plugins": {pa.PLUGIN_ID: [{"scope": "project"}]}},
        {"version": 2, "plugins": {pa.PLUGIN_ID: "nope"}},
        {"version": 2},
        [],
        "{broken",
    ],
)
def test_verdict_agrees_with_plugin_activation(world, content):
    """The hook inlines ``plugin_activation``'s rule; the two must agree."""
    if isinstance(content, dict):
        content = json.loads(
            json.dumps(content).replace('"REPO"', json.dumps(str(world["repo"])))
            .replace('"OTHER"', json.dumps(str(world["other"])))
        )
    path = _manifest(world, content)
    expected = pa.plugin_activation_status(world["repo"], plugins_file=path)["status"]
    out = _run_hook(world)
    got = "active" if out == "" else "inactive" if out.startswith(_LOUD) else "unknown"
    assert got == expected, out


def test_the_python_half_survives_sh_single_quoting():
    """The verdict is wrapped in sh single quotes, which nothing can escape."""
    assert "'" not in tw._VERDICT_PY
    assert tw.TRIPWIRE_COMMAND.startswith(tw.TRIPWIRE_TAG + "\n")


# --- the merge ---------------------------------------------------------------


def test_ensure_adds_to_fresh_settings():
    data: dict = {}
    assert tw.ensure_tripwire(data) is True
    assert data["hooks"]["SessionStart"] == [tw.TRIPWIRE_GROUP]
    assert tw.tripwire_state(data) == tw.PRESENT


def test_ensure_keeps_other_hooks_and_a_second_run_changes_nothing():
    mine = {"matcher": "startup", "hooks": [{"type": "command", "command": "echo hi"}]}
    data = {
        "permissions": {"allow": ["Bash(ls)"]},
        "hooks": {"SessionStart": [mine], "Stop": [{"hooks": [{"type": "command", "command": "x"}]}]},
    }
    assert tw.ensure_tripwire(data) is True
    snapshot = json.dumps(data, sort_keys=True)
    assert tw.ensure_tripwire(data) is False
    assert json.dumps(data, sort_keys=True) == snapshot
    assert data["hooks"]["SessionStart"] == [mine, tw.TRIPWIRE_GROUP]
    assert data["hooks"]["Stop"] and data["permissions"] == {"allow": ["Bash(ls)"]}


def test_ensure_replaces_a_stale_copy_rather_than_adding_a_second():
    old = {"type": "command", "command": ": prawduct-unloaded-tripwire v0\necho old"}
    mine = {"type": "command", "command": "echo mine"}
    data = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [mine, old]}]}}
    assert tw.tripwire_state(data) == tw.STALE
    assert tw.ensure_tripwire(data) is True
    groups = data["hooks"]["SessionStart"]
    assert groups == [{"matcher": "startup", "hooks": [mine]}, tw.TRIPWIRE_GROUP]


def test_replacing_a_stale_copy_alone_in_its_group_drops_the_empty_group():
    old = {"matcher": "startup", "hooks": [
        {"type": "command", "command": ": prawduct-unloaded-tripwire v0\necho old"}
    ]}
    data = {"hooks": {"SessionStart": [old]}}
    assert tw.ensure_tripwire(data) is True
    assert data["hooks"]["SessionStart"] == [tw.TRIPWIRE_GROUP]


def test_ensure_leaves_a_malformed_hooks_shape_alone():
    data = {"hooks": {"SessionStart": {"not": "a list"}}}
    assert tw.tripwire_state(data) == tw.MALFORMED
    assert tw.ensure_tripwire(data) is False
    assert data == {"hooks": {"SessionStart": {"not": "a list"}}}


def test_transform_settings_writes_it_once_and_keeps_it(tmp_path):
    """The migrate/init writer strips legacy `product-hook` wiring; the tripwire
    must not look like it, and a re-run must not add a second copy."""
    (tmp_path / ".claude").mkdir()
    settings = tmp_path / ".claude" / "settings.json"
    settings.write_text(json.dumps({
        "hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "python3 tools/product-hook clear"}]},
            {"hooks": [{"type": "command", "command": "echo mine"}]},
        ]}
    }))
    assert transform_settings(tmp_path) is True
    assert transform_settings(tmp_path) is False
    data = json.loads(settings.read_text())
    commands = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
    assert commands == ["echo mine", tw.TRIPWIRE_COMMAND]
    assert data["enabledPlugins"] == INSTALL_REFERENCE["enabledPlugins"]


def test_init_product_writes_it(tmp_path):
    from lib.init_product import init_product

    repo = tmp_path / "product"
    repo.mkdir()
    result = init_product(repo, "Product", apply=True)
    assert ".claude/settings.json" in result["created"]
    data = json.loads((repo / ".claude" / "settings.json").read_text())
    assert tw.tripwire_state(data) == tw.PRESENT


def test_init_product_adds_it_to_settings_that_carry_only_the_reference(tmp_path):
    """A repo whose settings already match the install reference still lacks the
    hook, so init-product must not report the file as already done."""
    from lib.init_product import init_product

    repo = tmp_path / "product"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(json.dumps(INSTALL_REFERENCE))
    result = init_product(repo, "Product", apply=True)
    assert ".claude/settings.json" in result["edited"]
    data = json.loads((repo / ".claude" / "settings.json").read_text())
    assert tw.tripwire_state(data) == tw.PRESENT


# --- the CLI writer ----------------------------------------------------------


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK), "install-tripwire", *args],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "CLAUDE_PLUGIN_ROOT": str(_PLUGIN_ROOT),
            "CLAUDE_PROJECT_DIR": str(root),
        },
    )


def _onboarded(root: Path, **extra) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    path = root / ".claude" / "settings.json"
    path.write_text(json.dumps({**json.loads(json.dumps(INSTALL_REFERENCE)), **extra}, indent=2))
    return path


def test_cli_dry_run_reports_absent_and_writes_nothing(tmp_path):
    path = _onboarded(tmp_path)
    before = path.read_bytes()
    proc = _cli(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "install-tripwire (dry-run): absent" in proc.stdout
    assert "--apply to write it" in proc.stdout
    assert path.read_bytes() == before


def test_cli_apply_writes_and_is_idempotent(tmp_path):
    path = _onboarded(tmp_path, permissions={"allow": ["Bash(ls)"]})
    proc = _cli(tmp_path, "--apply")
    assert proc.returncode == 0, proc.stderr
    assert "Wrote" in proc.stdout
    data = json.loads(path.read_text())
    assert tw.tripwire_state(data) == tw.PRESENT
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    assert data["enabledPlugins"] == INSTALL_REFERENCE["enabledPlugins"]
    after = path.read_bytes()
    again = _cli(tmp_path, "--apply", "--json")
    assert again.returncode == 0
    assert json.loads(again.stdout) == {"status": "present", "applied": False, "path": str(path)}
    assert path.read_bytes() == after


def test_cli_refuses_a_malformed_file_and_writes_nothing(tmp_path):
    (tmp_path / ".claude").mkdir()
    path = tmp_path / ".claude" / "settings.json"
    path.write_text("{ not json")
    proc = _cli(tmp_path, "--apply")
    assert proc.returncode == 1
    assert "malformed" in proc.stdout
    assert path.read_text() == "{ not json"


def test_cli_rejects_unknown_flags(tmp_path):
    assert _cli(tmp_path, "--force").returncode == 2


# --- the nudge ---------------------------------------------------------------


@pytest.fixture
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def test_probe_fires_on_an_onboarded_repo_without_it(tmp_path):
    _onboarded(tmp_path)
    out = irp.probe_tripwire_missing(ProjectState({}), Codebase(root=tmp_path))
    assert [c.type for c in out] == ["tripwire-missing"]
    assert out[0].recommended_action == "/prawduct:doctor"
    assert "has no unloaded-plugin tripwire hook" in out[0].trigger_summary


def test_probe_fires_on_a_stale_copy(tmp_path):
    _onboarded(tmp_path, hooks={"SessionStart": [{"hooks": [
        {"type": "command", "command": ": prawduct-unloaded-tripwire v0\necho old"}
    ]}]})
    out = irp.probe_tripwire_missing(ProjectState({}), Codebase(root=tmp_path))
    assert "older copy" in out[0].trigger_summary


def test_probe_is_inert_once_the_doctor_repair_ran(tmp_path):
    """Following the advisory's route clears it: the repair is the resolution."""
    _onboarded(tmp_path)
    assert irp.probe_tripwire_missing(ProjectState({}), Codebase(root=tmp_path))
    assert _cli(tmp_path, "--apply").returncode == 0
    assert irp.probe_tripwire_missing(ProjectState({}), Codebase(root=tmp_path)) == []


def test_probe_is_inert_on_a_repo_that_never_onboarded(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    assert irp.probe_tripwire_missing(ProjectState({}), Codebase(root=tmp_path)) == []
    assert irp.probe_tripwire_missing(ProjectState({}), Codebase(root=tmp_path / "x")) == []


def test_the_contract_drift_probe_accepts_settings_carrying_the_tripwire(tmp_path):
    path = _onboarded(tmp_path)
    data = json.loads(path.read_text())
    tw.ensure_tripwire(data)
    path.write_text(json.dumps(data))
    assert irp.probe_install_reference_drift(ProjectState({}), Codebase(root=tmp_path)) == []


def test_probe_is_wired_into_the_composition_root(tmp_path, _isolated_registry):
    from lib.probe_families import register_all

    _onboarded(tmp_path)
    register_all()
    fired = [
        c for c in run_all_probes(ProjectState({}), make_codebase(tmp_path))
        if c.feature == irp.FEATURE and c.type == "tripwire-missing"
    ]
    assert len(fired) == 1
