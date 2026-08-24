"""Tests for machine-level plugin install detection (`lib/plugin_install.py`).

The defect these guard is `#710`: a repo scaffolded with a perfect committed
install reference, on a machine where `installed_plugins.json` has no entry for
its path, gets NO governance at all — and nothing in prawduct could see it,
because every check read the repo's `.claude/settings.json` and none read the
registry that actually binds plugin resolution.

Two properties matter more than the mechanics and are pinned deliberately:

* **Fail toward alarming** — an ancestor-directory entry must NOT read as
  covering. Whether Claude Code matches `projectPath` exactly or by prefix could
  not be verified, and the two error directions cost very different things.
* **"Could not ask" is not "fine"** — an unreadable or malformed registry answers
  `unchecked`, never `absent` and never `installed`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.plugin_install import (  # noqa: E402
    PLUGIN_KEY,
    config_home,
    install_status,
    installed_plugins_path,
    remedy_for,
)

HOOK = ROOT / "bin" / "prawduct-hook"


# =============================================================================
# Helpers
# =============================================================================


def write_registry(config_dir: Path, entries: list[dict] | None, *, raw: str | None = None) -> Path:
    """Write a fake `installed_plugins.json` under `config_dir`."""
    path = config_dir / "plugins" / "installed_plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
        return path
    payload = {"version": 1, "plugins": {}}
    if entries is not None:
        payload["plugins"][PLUGIN_KEY] = entries
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated `CLAUDE_CONFIG_DIR` for the duration of one test."""
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    return cfg


# =============================================================================
# Path resolution
# =============================================================================


def test_config_home_honors_claude_config_dir(config_dir: Path):
    assert config_home() == config_dir
    assert installed_plugins_path() == config_dir / "plugins" / "installed_plugins.json"


def test_config_home_defaults_to_dot_claude(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert config_home() == Path.home() / ".claude"


def test_plugin_key_comes_from_the_install_contract():
    """Derived, never transcribed — so the key cannot drift from what onboard writes."""
    from lib.migrate_plugin import INSTALL_REFERENCE

    assert PLUGIN_KEY in INSTALL_REFERENCE["enabledPlugins"]


def test_remedy_carries_the_cd():
    """`--scope project` keys on the CURRENT directory, and the caller that needs
    this string most (`/prawduct:onboard <target>`) is running somewhere else."""
    remedy = remedy_for("/some/repo")
    assert remedy.startswith("cd /some/repo && ")
    assert "claude plugin install" in remedy
    assert "--scope project" in remedy


# =============================================================================
# Installed
# =============================================================================


def test_exact_project_path_is_installed(config_dir: Path, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_registry(config_dir, [{"scope": "project", "projectPath": str(repo), "version": "3.4.0"}])

    result = install_status(repo)

    assert result["status"] == "installed"
    assert result["scope"] == "project"
    assert result["remedy"] is None
    assert result["reason"]


def test_user_scope_covers_any_path(config_dir: Path, tmp_path: Path):
    """A machine-wide install needs no path entry — it loads everywhere."""
    write_registry(config_dir, [{"scope": "user", "version": "3.4.0"}])

    result = install_status(tmp_path / "never-mentioned")

    assert result["status"] == "installed"
    assert result["scope"] == "user"


def test_local_scope_at_the_exact_path_is_installed(config_dir: Path, tmp_path: Path):
    """`local` is path-keyed like `project`; it is a real install for that path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    write_registry(config_dir, [{"scope": "local", "projectPath": str(repo)}])

    assert install_status(repo)["status"] == "installed"


def test_symlinked_path_matches_through_resolution(config_dir: Path, tmp_path: Path):
    """Both sides are resolved, so `/tmp` vs `/private/tmp` cannot cause a false alarm."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    write_registry(config_dir, [{"scope": "project", "projectPath": str(real)}])

    assert install_status(link)["status"] == "installed"


def test_scans_past_non_matching_entries(config_dir: Path, tmp_path: Path):
    """The registry holds every project's entry; the match may not be first."""
    repo = tmp_path / "repo"
    repo.mkdir()
    write_registry(
        config_dir,
        [
            {"scope": "project", "projectPath": str(tmp_path / "other-a")},
            {"scope": "project", "projectPath": str(tmp_path / "other-b")},
            {"scope": "project", "projectPath": str(repo)},
        ],
    )

    assert install_status(repo)["status"] == "installed"


# =============================================================================
# Absent — the `#710` state
# =============================================================================


def test_sibling_projects_do_not_cover_this_one(config_dir: Path, tmp_path: Path):
    """The exact field report: entries for two unrelated repos, none for this one."""
    repo = tmp_path / "bl-eng-client-delivery"
    repo.mkdir()
    write_registry(
        config_dir,
        [
            {"scope": "project", "projectPath": str(tmp_path / "airflow-eng")},
            {"scope": "project", "projectPath": str(tmp_path / "ai-dipp")},
        ],
    )

    result = install_status(repo)

    assert result["status"] == "absent"
    assert result["scope"] is None
    assert result["remedy"] == remedy_for(repo)


def test_ancestor_directory_does_not_count_as_installed(config_dir: Path, tmp_path: Path):
    """Fail toward alarming.

    Prefix matching is unverified; if it turns out to be real, this answer costs a
    redundant (idempotent) install command. The opposite mistake — reading an
    ancestor entry as coverage that isn't there — is the silently-ungoverned repo
    `#710` reports, so it is the one direction that must not happen.
    """
    parent = tmp_path / "source"
    repo = parent / "repo"
    repo.mkdir(parents=True)
    write_registry(config_dir, [{"scope": "project", "projectPath": str(parent)}])

    assert install_status(repo)["status"] == "absent"


def test_missing_registry_is_absent_not_unchecked(config_dir: Path, tmp_path: Path):
    """A registry that was never written is a real answer: nothing is installed."""
    result = install_status(tmp_path / "repo")

    assert result["status"] == "absent"
    assert result["remedy"]


def test_other_plugins_installed_but_not_prawduct(config_dir: Path, tmp_path: Path):
    path = config_dir / "plugins" / "installed_plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"plugins": {"someone-else@market": [{"scope": "user"}]}}), encoding="utf-8"
    )

    assert install_status(tmp_path / "repo")["status"] == "absent"


def test_absent_reason_names_what_is_lost(config_dir: Path, tmp_path: Path):
    """The consequence, not just the condition — an operator reading only this
    line must learn what stops working, which is the whole point of `#710`."""
    write_registry(config_dir, [])
    reason = install_status(tmp_path / "repo")["reason"]

    assert "skills" in reason
    assert "gate" in reason or "hook" in reason


# =============================================================================
# Unchecked — "could not ask" is not "fine"
# =============================================================================


@pytest.mark.parametrize(
    "raw",
    [
        "{not json at all",
        '"a bare string"',
        "[]",
        '{"version": 1}',  # no `plugins` mapping
        '{"plugins": "not a mapping"}',
    ],
)
def test_unreadable_registry_is_unchecked(config_dir: Path, tmp_path: Path, raw: str):
    write_registry(config_dir, None, raw=raw)

    result = install_status(tmp_path / "repo")

    assert result["status"] == "unchecked", raw
    # Soft, but never silent: the degraded path still names its consequence.
    assert "silently inactive" in result["reason"]
    assert result["remedy"]


def test_malformed_entries_are_skipped_not_trusted(config_dir: Path, tmp_path: Path):
    """A junk entry must not be read as a match — and must not crash the read."""
    repo = tmp_path / "repo"
    repo.mkdir()
    write_registry(
        config_dir,
        ["a string, not a dict", {"scope": "project"}, {"projectPath": 42}],
    )

    assert install_status(repo)["status"] == "absent"


def test_entries_not_a_list_is_absent(config_dir: Path, tmp_path: Path):
    path = config_dir / "plugins" / "installed_plugins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plugins": {PLUGIN_KEY: {"scope": "user"}}}), encoding="utf-8")

    assert install_status(tmp_path / "repo")["status"] == "absent"


def test_every_answer_carries_a_reason_sentence(config_dir: Path, tmp_path: Path):
    """Including the good one — a caller rendering any branch has something honest
    to print, so no branch degrades into an empty string."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for entries in ([{"scope": "user"}], [], None):
        write_registry(config_dir, entries)
        result = install_status(repo)
        assert result["reason"].strip()
        assert result["registry"]


def test_nothing_is_written_to_the_config_home(config_dir: Path, tmp_path: Path):
    """Read-only, always — the plugin never writes into the operator's config."""
    write_registry(config_dir, [{"scope": "user"}])
    before = sorted(p.relative_to(config_dir) for p in config_dir.rglob("*"))

    install_status(tmp_path / "repo")

    assert sorted(p.relative_to(config_dir) for p in config_dir.rglob("*")) == before


# =============================================================================
# The `init-product` surface — both JSON and the human formatter
# =============================================================================


def _run_init(target: Path, cfg: Path, *flags: str) -> subprocess.CompletedProcess:
    home = target.parent / "_home"
    home.mkdir(exist_ok=True, parents=True)
    return subprocess.run(
        [sys.executable, str(HOOK), "init-product", str(target), "--name", "Probe", *flags],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "HOME": str(home),
            "CLAUDE_CONFIG_DIR": str(cfg),
            "CLAUDE_PROJECT_DIR": str(target),
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


def test_json_result_carries_install_status(tmp_path: Path):
    cfg = tmp_path / "cfg"
    write_registry(cfg, [])
    proc = _run_init(tmp_path / "prod", cfg, "--json")

    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["install_status"]["status"] == "absent"
    assert result["install_status"]["remedy"]


def test_json_result_reports_installed_when_it_is(tmp_path: Path):
    cfg = tmp_path / "cfg"
    target = tmp_path / "prod"
    write_registry(cfg, [{"scope": "project", "projectPath": str(target)}])
    proc = _run_init(target, cfg, "--json")

    assert json.loads(proc.stdout)["install_status"]["status"] == "installed"


def test_human_output_prints_the_remedy(tmp_path: Path):
    """The human path is tested explicitly: `--json`-only tests never exercise the
    formatter, and this formatter is the entire user-facing value of the check."""
    cfg = tmp_path / "cfg"
    write_registry(cfg, [])
    proc = _run_init(tmp_path / "prod", cfg)

    assert "NOT INSTALLED" in proc.stdout
    assert "claude plugin install" in proc.stdout
    assert "--scope project" in proc.stdout


def test_human_output_does_not_promise_governance_when_absent(tmp_path: Path):
    """The defect in prose form: today's closing line asserts governance activates
    in the target, spoken with full confidence in the one state where it is false."""
    cfg = tmp_path / "cfg"
    write_registry(cfg, [])
    proc = _run_init(tmp_path / "prod", cfg, "--apply")

    assert proc.returncode == 0
    assert "hooks and briefing activate there" not in proc.stdout
    assert "do NOT rely on governance" in proc.stdout


def test_human_output_promises_governance_when_installed(tmp_path: Path):
    cfg = tmp_path / "cfg"
    target = tmp_path / "prod"
    write_registry(cfg, [{"scope": "user"}])
    proc = _run_init(target, cfg, "--apply")

    assert "hooks and briefing activate there" in proc.stdout
    assert "NOT INSTALLED" not in proc.stdout


def test_absent_install_does_not_fail_the_scaffold(tmp_path: Path):
    """Advice fails soft. The scaffold genuinely succeeded and its state is correct
    and portable; whether one machine has the plugin installed for one path is a
    separate fact, and conflating them would break every `--json` consumer."""
    cfg = tmp_path / "cfg"
    target = tmp_path / "prod"
    write_registry(cfg, [])
    proc = _run_init(target, cfg, "--apply")

    assert proc.returncode == 0
    assert (target / ".prawduct" / "project-state.yaml").is_file()
    assert (target / ".claude" / "settings.json").is_file()


def test_already_scaffolded_rerun_still_reports_install_state(tmp_path: Path):
    """Re-running onboard is how someone reaches for a diagnosis when a repo
    "looks onboarded but isn't working" — the no-op path must still answer."""
    cfg = tmp_path / "cfg"
    target = tmp_path / "prod"
    write_registry(cfg, [])
    assert _run_init(target, cfg, "--apply").returncode == 0

    proc = _run_init(target, cfg, "--json")
    result = json.loads(proc.stdout)

    assert result["already_scaffolded"] is True
    assert result["install_status"]["status"] == "absent"


def test_unchecked_registry_reaches_the_human_output(tmp_path: Path):
    cfg = tmp_path / "cfg"
    write_registry(cfg, None, raw="{broken")
    proc = _run_init(tmp_path / "prod", cfg)

    assert "NOT VERIFIED" in proc.stdout
    assert "claude plugin install" in proc.stdout


# =============================================================================
# The prose surfaces — the anchor and the two skills
# =============================================================================


def test_anchor_tells_a_cold_agent_what_a_missing_banner_means():
    """The one channel that survives the plugin not loading.

    In the `#710` state every other surface is unreachable — no skills, no hooks,
    no `/prawduct:ping` (a plugin skill cannot diagnose the plugin not loading).
    `CLAUDE.md` is read regardless, so the self-check has to live there or nowhere.
    """
    from lib.migrate_plugin import STATIC_ANCHOR

    lowered = STATIC_ANCHOR.lower()
    # Asserted as the four things the passage must convey, not as its wording —
    # the anchor is under a hard per-session token budget and gets re-trimmed.
    assert "banner" in lowered, "must tell the agent what to key off"
    assert "not installed" in lowered, "must name the cause, not just the symptom"
    assert "claude plugin install" in lowered, "must carry the actual fix"
    assert "restart" in lowered, "the fix is inert until the session restarts"


def test_anchor_stays_version_free():
    """Its standing contract: the active version is injected by the banner at
    session start, so nothing here may pin one."""
    import re

    from lib.migrate_plugin import STATIC_ANCHOR

    assert not re.search(r"\bv\d+\.\d+\.\d+", STATIC_ANCHOR)


def test_anchor_plugin_key_is_derived_not_typed():
    from lib.migrate_plugin import INSTALL_REFERENCE, STATIC_ANCHOR

    assert PLUGIN_KEY in INSTALL_REFERENCE["enabledPlugins"]
    assert PLUGIN_KEY in STATIC_ANCHOR


def test_onboard_skill_verifies_the_install():
    text = (ROOT / "skills" / "onboard" / "SKILL.md").read_text()

    assert "install_status" in text, "onboard must check the install, not just write the reference"
    assert "claude plugin install" in text, "onboard must hand over the exact remedy"
    assert "Bash(prawduct-hook install-status" in text, "allowed-tools must permit the check"


def test_onboard_skill_warns_off_the_false_positive_diagnostic():
    """`claude plugin list` reports other projects' entries with no `projectPath`
    qualifier, so it says "installed and enabled" in exactly the broken state — and
    it is the first thing a diagnosing agent reaches for."""
    text = (ROOT / "skills" / "onboard" / "SKILL.md").read_text()

    assert "claude plugin list" in text
    assert "Never diagnose this with `claude plugin list`" in text


def test_doctor_relays_the_machine_level_install():
    text = (ROOT / "skills" / "doctor" / "SKILL.md").read_text()

    assert "install-status" in text
    assert "Bash(prawduct-hook install-status" in text


def test_doctor_install_check_is_information_not_a_grade():
    """`--plugin-dir` self-hosting bypasses the registry by design, so grading on
    it would report a framework checkout broken. And the total failure is
    unreachable from doctor at all — a plugin skill cannot run when the plugin
    did not load — so a healthy answer here must not read as coverage."""
    text = (ROOT / "skills" / "doctor" / "SKILL.md").read_text()

    assert "information, not a grade" in text
    assert "never degraded" in text
    assert "--plugin-dir" in text


def test_install_status_subcommand_is_classified_read_only():
    """It mutates nothing; classifying it otherwise would make an informational
    read refuse to run wherever writes are refused."""
    text = (ROOT / "bin" / "prawduct-hook").read_text()

    assert '"install-status",' in text
    assert 'elif command == "install-status":' in text
    assert "install-status [--json]" in text


def test_probe_docstring_no_longer_describes_doctor_check_as_future():
    """`install_reference_probes` states the complementary-check obligation this
    work discharges; leaving it in the future tense is the doc drift the Critic
    checks bidirectionally."""
    text = (ROOT / "lib" / "install_reference_probes.py").read_text()

    assert "Doctor now takes that half up" in text
    assert "Health Check #19" in text


def test_unresolvable_home_is_unchecked_not_a_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The advice must never take down the operation it advises on.

    `Path.home()` raises when the home directory cannot be resolved, and this code
    runs inside a scaffold — an escaping exception would turn an unresolvable HOME
    into a failed `init-product`.
    """
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    # Patched on the MODULE's `Path` name, never on `pathlib.Path` itself. A
    # class-global patch raises in every thread of this xdist worker for the
    # duration of the test — including pytest's timeout timer and xdist's own
    # channel — which wedges the worker and hangs the whole parallel run. It
    # passes in isolation, so the cost lands only on the full suite.
    class _NoHome:
        """Constructs real `Path`s; only `home()` is replaced."""

        def __new__(cls, *args, **kwargs):
            return Path(*args, **kwargs)

        @staticmethod
        def home():
            raise RuntimeError("no home directory")

    monkeypatch.setattr("lib.plugin_install.Path", _NoHome)

    assert config_home() is None
    assert installed_plugins_path() is None

    result = install_status(tmp_path / "repo")
    assert result["status"] == "unchecked"
    assert result["registry"] is None
    assert result["remedy"]
