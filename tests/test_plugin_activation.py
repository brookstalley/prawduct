"""Tests for the plugin-activation check.

The failure this check exists for is a repo that looks fully onboarded —
scaffolded ``.prawduct/``, a CLAUDE.md promising enforcement, a correct install
reference in ``.claude/settings.json`` — while the plugin never loads, because
the harness's ``installed_plugins.json`` holds no record for that path. Nothing
inside such a repo can detect it: the probes and the doctor skill that would
report it are delivered by the plugin that did not load.

**The degradation tests are the load-bearing ones.** ``installed_plugins.json``
is a harness-internal file, so every way of failing to read it must yield
``unknown``, never ``inactive`` — reporting "not installed" off a file that
could not be parsed sends an operator to reinstall something that was never
broken. Each degradation path is asserted separately rather than as a group,
because they are separate code paths and a single grouped assertion would pass
while one of them regressed to ``inactive``.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the plugin root first (mirrors tests/test_onboarding_probes.py).
_PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent / "plugin")
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from lib import plugin_activation as pa  # noqa: E402


def _manifest(tmp_path: Path, payload) -> Path:
    path = tmp_path / "installed_plugins.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _record(project_path, *, scope="project", version="3.4.1"):
    return {
        "scope": scope,
        "projectPath": str(project_path),
        "installPath": "/somewhere/cache/prawduct",
        "version": version,
    }


# --------------------------------------------------------------------------
# Active
# --------------------------------------------------------------------------

def test_record_for_this_project_is_active(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [_record(repo)]},
    })

    result = pa.plugin_activation_status(repo, plugins_file=manifest)

    assert result["status"] == pa.ACTIVE
    assert result["matched_scope"] == "project"


def test_user_scope_record_covers_every_project(tmp_path):
    """A user-scope install governs the target without naming its path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [{"scope": "user", "version": "3.4.1"}]},
    })

    result = pa.plugin_activation_status(repo, plugins_file=manifest)

    assert result["status"] == pa.ACTIVE
    assert result["matched_scope"] == "user"


def test_trailing_slash_and_symlink_spellings_still_match(tmp_path):
    """The comparison is on resolved paths, not on string equality."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [_record(str(real) + "/")]},
    })

    assert pa.plugin_activation_status(link, plugins_file=manifest)["status"] == pa.ACTIVE


def test_matching_record_among_many_is_found(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [_record(other), _record(repo)]},
    })

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.ACTIVE


# --------------------------------------------------------------------------
# Inactive — the real defect, reported only from a manifest that read cleanly
# --------------------------------------------------------------------------

def test_records_for_other_paths_only_is_inactive_and_names_them(tmp_path):
    """The field case: entries for two unrelated repos, none for this one.

    The other paths are part of the report because they are what let the
    operator recognise what happened.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [_record(a), _record(b)]},
    })

    result = pa.plugin_activation_status(repo, plugins_file=manifest)

    assert result["status"] == pa.INACTIVE
    assert set(result["other_paths"]) == {str(a), str(b)}


def test_plugin_absent_from_a_readable_manifest_is_inactive(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {"something-else@elsewhere": [_record(repo)]},
    })

    result = pa.plugin_activation_status(repo, plugins_file=manifest)

    assert result["status"] == pa.INACTIVE
    assert result["other_paths"] == []


def test_empty_record_list_is_inactive(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {"version": 2, "plugins": {pa.PLUGIN_ID: []}})

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.INACTIVE


# --------------------------------------------------------------------------
# Unknown — every degradation, asserted one path at a time
# --------------------------------------------------------------------------

def test_missing_manifest_is_unknown_not_inactive(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = pa.plugin_activation_status(repo, plugins_file=tmp_path / "absent.json")

    assert result["status"] == pa.UNKNOWN


def test_undecodable_json_is_unknown_not_inactive(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = tmp_path / "installed_plugins.json"
    path.write_text("{not json", encoding="utf-8")

    assert pa.plugin_activation_status(repo, plugins_file=path)["status"] == pa.UNKNOWN


def test_manifest_that_is_not_an_object_is_unknown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, ["not", "an", "object"])

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.UNKNOWN


def test_manifest_without_a_plugins_object_is_unknown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {"version": 2})

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.UNKNOWN


def test_entry_that_is_not_a_list_is_unknown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: {"scope": "project"}},
    })

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.UNKNOWN


def test_unreadable_record_with_no_match_is_unknown_not_inactive(tmp_path):
    """A record this check could not read might have been the matching one.

    Reporting `inactive` here would be a confident answer derived from a set
    that was not fully read — the exact shape of the bug this module exists to
    prevent, one level down.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [_record(other), {"scope": "project"}]},
    })

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.UNKNOWN


def test_unreadable_record_does_not_mask_a_real_match(tmp_path):
    """A malformed sibling must not downgrade a genuine `active`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [{"scope": "project"}, _record(repo)]},
    })

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.ACTIVE


def test_no_degradation_path_ever_returns_inactive(tmp_path):
    """The invariant the individual tests above each cover one case of.

    Stated once as a whole so a NEW degradation path added later without its own
    test still cannot silently return the accusing answer.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    bad = tmp_path / "bad.json"

    broken_inputs = [
        None,                                        # missing file
        "{not json",                                 # undecodable
        json.dumps(["not", "an", "object"]),         # wrong root type
        json.dumps({"version": 2}),                  # no plugins object
        json.dumps({"version": 2, "plugins": []}),   # plugins not a mapping
        json.dumps({"version": 2, "plugins": {pa.PLUGIN_ID: 7}}),   # entry not a list
        json.dumps({"version": 99, "plugins": {pa.PLUGIN_ID: [{}]}}),  # unreadable record
    ]
    for payload in broken_inputs:
        if payload is None:
            path = tmp_path / "absent.json"
        else:
            bad.write_text(payload, encoding="utf-8")
            path = bad
        result = pa.plugin_activation_status(repo, plugins_file=path)
        assert result["status"] != pa.INACTIVE, payload


# --------------------------------------------------------------------------
# Shape and reporting
# --------------------------------------------------------------------------

@pytest.mark.parametrize("payload,expected", [
    ({"version": 2, "plugins": {pa.PLUGIN_ID: []}}, pa.INACTIVE),
    ({"version": 2, "plugins": {}}, pa.INACTIVE),
    ({"version": 2}, pa.UNKNOWN),
])
def test_every_result_carries_the_same_keys(tmp_path, payload, expected):
    """A caller must not have to know which branch produced its result."""
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, payload)

    result = pa.plugin_activation_status(repo, plugins_file=manifest)

    assert result["status"] == expected
    assert set(result) == {
        "status", "reason", "plugin_id", "project_path", "plugins_file",
        "matched_scope", "manifest_version", "other_paths",
    }


def test_a_shape_change_is_read_structurally_not_by_version(tmp_path):
    """An unrecognised `version` with a readable shape still answers.

    Version-gating would report `unknown` for a harness release that merely
    bumped the number, degrading the check to useless at the first upgrade.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 9999,
        "plugins": {pa.PLUGIN_ID: [_record(repo)]},
    })

    assert pa.plugin_activation_status(repo, plugins_file=manifest)["status"] == pa.ACTIVE


def test_inactive_report_carries_the_consequence_and_the_fix(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    manifest = _manifest(tmp_path, {
        "version": 2,
        "plugins": {pa.PLUGIN_ID: [_record(other)]},
    })

    text = "\n".join(pa.report_lines(
        pa.plugin_activation_status(repo, plugins_file=manifest)
    ))

    assert "NO governance" in text
    assert "claude plugin install" in text
    assert str(other) in text


def test_unknown_report_refuses_to_read_as_a_clean_bill(tmp_path):
    """Advice fails soft, but a degraded advisory must name its consequence."""
    repo = tmp_path / "repo"
    repo.mkdir()

    text = "\n".join(pa.report_lines(
        pa.plugin_activation_status(repo, plugins_file=tmp_path / "absent.json")
    ))

    assert "could not verify" in text
    assert "NOT a clean bill" in text


def test_remediation_command_names_the_target_repo(tmp_path):
    assert str(tmp_path) in pa.remediation_command(tmp_path)
    assert pa.PLUGIN_ID in pa.remediation_command(tmp_path)


def test_config_dir_env_var_is_honoured(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))

    assert pa.default_plugins_file() == tmp_path / "cfg" / "plugins" / "installed_plugins.json"


def test_default_plugins_file_is_resolved_at_call_time(monkeypatch):
    """Import ordering must not defeat a caller that sets the environment."""
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    before = pa.default_plugins_file()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/elsewhere")

    assert pa.default_plugins_file() != before


# --------------------------------------------------------------------------
# The CLI wrapper.
#
# The three-way exit contract is what `api-contract.md` publishes, so it is
# tested against the CLI rather than inferred from the library: a caller binds
# to the exit code, and nothing above this line would notice if the mapping
# regressed. `unknown` -> 3 is the one that matters most — folded to 0 it would
# report a clean bill off a check that never ran, which is the class this whole
# command exists to close.
# --------------------------------------------------------------------------

_HOOK = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"


def _run(args, *, config_dir=None, cwd=None):
    env = dict(os.environ)
    if config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    return subprocess.run(
        [sys.executable, str(_HOOK), "check-plugin-active", *args],
        capture_output=True, text=True, env=env,
        cwd=str(cwd) if cwd else None,
    )


@pytest.fixture
def config_dir(tmp_path):
    """A CLAUDE_CONFIG_DIR whose manifest the test writes."""
    d = tmp_path / "cfg"
    (d / "plugins").mkdir(parents=True)

    def write(payload):
        (d / "plugins" / "installed_plugins.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return d
    write.dir = d
    return write


def test_cli_exits_0_when_active(tmp_path, config_dir):
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(repo)]}})

    proc = _run(["--path", str(repo)], config_dir=cfg)

    assert proc.returncode == 0
    assert "active:" in proc.stdout


def test_cli_exits_1_when_inactive(tmp_path, config_dir):
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(other)]}})

    proc = _run(["--path", str(repo)], config_dir=cfg)

    assert proc.returncode == 1


def test_cli_exits_3_when_unknown_not_0_and_not_1(tmp_path, config_dir):
    """The load-bearing exit. Both foldings are wrong and both are asserted."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = config_dir.dir
    (cfg / "plugins" / "installed_plugins.json").write_text("{not json", encoding="utf-8")

    proc = _run(["--path", str(repo)], config_dir=cfg)

    assert proc.returncode == 3, proc.stderr
    assert proc.returncode != 0
    assert proc.returncode != 1


def test_cli_routes_active_to_stdout_and_problems_to_stderr(tmp_path, config_dir):
    """stdout is the agent-facing channel; a problem belongs on stderr."""
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(repo)]}})
    ok = _run(["--path", str(repo)], config_dir=cfg)
    assert ok.stdout.strip() and not ok.stderr.strip()

    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(other)]}})
    bad = _run(["--path", str(repo)], config_dir=cfg)
    assert bad.stderr.strip() and not bad.stdout.strip()


def test_cli_json_carries_the_three_way_status(tmp_path, config_dir):
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(repo)]}})

    proc = _run(["--path", str(repo), "--json"], config_dir=cfg)

    assert json.loads(proc.stdout)["status"] == pa.ACTIVE


def test_cli_path_defaults_to_the_current_project(tmp_path, config_dir):
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(repo)]}})

    assert _run(["--json"], config_dir=cfg, cwd=repo).returncode == 0


@pytest.mark.parametrize("args", [["--path"], ["--context"]])
def test_cli_flag_without_a_value_is_a_usage_error(args, config_dir):
    proc = _run(args, config_dir=config_dir.dir)

    assert proc.returncode == 2
    assert "needs a value" in proc.stderr


def test_cli_rejects_an_unknown_context(tmp_path, config_dir):
    proc = _run(["--context", "sideways"], config_dir=config_dir.dir)

    assert proc.returncode == 2
    assert "unknown --context" in proc.stderr


def test_cli_rejects_an_unknown_flag(config_dir):
    proc = _run(["--bogus"], config_dir=config_dir.dir)

    assert proc.returncode == 2
    assert "unknown argument" in proc.stderr


def test_cli_doctor_context_does_not_accuse_the_repo_of_being_ungoverned(
    tmp_path, config_dir
):
    """The false-accusation direction, guarded at the call site that reintroduced it.

    From doctor the plugin demonstrably loaded, so relaying onboard's "NO
    governance" would send an operator to reinstall a working install. The
    verdict is the same; only the consequence differs.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    cfg = config_dir({"version": 2, "plugins": {pa.PLUGIN_ID: [_record(other)]}})

    onboard = _run(["--path", str(repo)], config_dir=cfg)
    doctor = _run(["--path", str(repo), "--context", "doctor"], config_dir=cfg)

    assert onboard.returncode == doctor.returncode == 1
    assert "NO governance" in onboard.stderr
    assert "NO governance" not in doctor.stderr
    assert "stale install record" in doctor.stderr


def test_remediation_command_survives_a_path_with_a_space(tmp_path):
    """`tmp_path` never contains a space, so this needs its own fixture."""
    spaced = tmp_path / "my repo"
    spaced.mkdir()

    command = pa.remediation_command(spaced)

    # The `cd` argument must survive word-splitting as ONE token.
    cd_arg = shlex.split(command)[1]
    assert cd_arg == str(spaced)
