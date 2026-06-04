"""Tests for plugin-native new-product scaffolding (Chunk 14).

The scaffolder lives in the plugin's ``lib/init_product.py`` and is driven through
``bin/prawduct-hook init-product``. These tests invoke it as a subprocess
(CLAUDE_PLUGIN_ROOT set), the established plugin-test pattern (mirrors
``test_plugin_migrate.py``), so they exercise the real CLI + plugin-root path
resolution — including that the scaffolder reads ``templates/`` from the plugin
root, not via ``core``'s parity-locked (and at this depth mis-resolving)
``FRAMEWORK_DIR``.

The contract: scaffold creates ONLY the design-§3 "what STAYS in the repo" set
(product-owned ``.prawduct/`` state + the thin CLAUDE.md anchor + the committed
install reference) and NONE of the file-sync machinery.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"

# The design-§3 product-owned set a scaffolded repo must carry.
EXPECTED_FILES = [
    ".prawduct/project-state.yaml",
    ".prawduct/learnings.md",
    ".prawduct/backlog.md",
    ".prawduct/change-log.md",
    ".prawduct/artifacts/project-preferences.md",
    ".prawduct/artifacts/boundary-patterns.md",
    "CLAUDE.md",
    ".claude/settings.json",
    ".gitignore",
]

# File-sync machinery a plugin repo must NEVER commit (the whole point of v2).
FORBIDDEN = [
    "tools/product-hook",
    "tools/lib",
    ".claude/skills",
    ".prawduct/sync-manifest.json",
    ".prawduct/critic-review.md",
    ".prawduct/pr-review.md",
    ".prawduct/build-governance.md",
]


def _env(target: Path) -> dict:
    home = target.parent / "_home"
    home.mkdir(exist_ok=True, parents=True)
    return {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(target),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run_init(target: Path, name: str, *flags: str) -> dict:
    """Invoke ``bin/prawduct-hook init-product <target> --name <name> [flags] --json``."""
    proc = subprocess.run(
        [sys.executable, str(HOOK), "init-product", str(target),
         "--name", name, *flags, "--json"],
        capture_output=True, text=True, env=_env(target), timeout=30,
    )
    assert proc.returncode == 0, f"init-product failed: {proc.stderr}\n{proc.stdout}"
    return json.loads(proc.stdout)


# =============================================================================
# Dry run (default — safe)
# =============================================================================


def test_dry_run_plans_without_writing(tmp_path: Path):
    target = tmp_path / "newprod"
    result = run_init(target, "NewProd")  # no --apply
    assert result["applied"] is False
    assert result["already_scaffolded"] is False
    assert ".prawduct/project-state.yaml" in result["created"]
    assert "CLAUDE.md" in result["created"]
    assert not target.exists(), "dry run must not write anything"


# =============================================================================
# Apply — creates the design-§3 product-owned set
# =============================================================================


@pytest.fixture
def scaffolded(tmp_path: Path) -> Path:
    target = tmp_path / "newprod"
    run_init(target, "Acme Widgets", "--apply")
    return target


@pytest.mark.parametrize("rel", EXPECTED_FILES)
def test_apply_creates_expected_file(scaffolded: Path, rel: str):
    assert (scaffolded / rel).is_file(), f"scaffold missing {rel}"


def test_apply_creates_pr_reviews_dir(scaffolded: Path):
    assert (scaffolded / ".prawduct" / ".pr-reviews").is_dir()


@pytest.mark.parametrize("bad", FORBIDDEN)
def test_no_filesync_machinery_created(scaffolded: Path, bad: str):
    assert not (scaffolded / bad).exists(), f"file-sync machinery leaked: {bad}"


def test_product_name_rendered(scaffolded: Path):
    state = (scaffolded / ".prawduct" / "project-state.yaml").read_text()
    assert 'name: "Acme Widgets"' in state
    assert "{{PRODUCT_NAME}}" not in state, "PRODUCT_NAME placeholder left unrendered"
    assert "{{PRAWDUCT_VERSION}}" not in state, "VERSION placeholder left unrendered"


def test_name_detectable_by_briefing(scaffolded: Path):
    # The "Project: Unknown" fix: the scaffolded project-state carries a
    # product_identity.name block, which is exactly what the SessionStart briefing's
    # product-name probe reads.
    state = (scaffolded / ".prawduct" / "project-state.yaml").read_text()
    assert "product_identity:" in state
    assert 'name: "Acme Widgets"' in state


def test_distribution_plugin_recorded(scaffolded: Path):
    assert "distribution: plugin" in (
        scaffolded / ".prawduct" / "project-state.yaml"
    ).read_text()


def test_static_anchor_present(scaffolded: Path):
    text = (scaffolded / "CLAUDE.md").read_text()
    assert "PRAWDUCT:ANCHOR" in text
    assert "/prawduct:building" in text  # the anchor points at the build cycle


def test_install_reference_committed(scaffolded: Path):
    settings = json.loads((scaffolded / ".claude" / "settings.json").read_text())
    assert settings["enabledPlugins"]["prawduct@prawduct"] is True
    src = settings["extraKnownMarketplaces"]["prawduct"]["source"]
    assert src["repo"] == "brookstalley/prawduct"
    assert src["ref"] == "main"
    assert settings["extraKnownMarketplaces"]["prawduct"]["autoUpdate"] is True


def test_session_files_and_marker_gitignored(scaffolded: Path):
    gi = (scaffolded / ".gitignore").read_text().splitlines()
    assert ".prawduct/.prawduct-version" in gi  # the version-banner marker
    assert ".prawduct/.session-reflected" in gi
    assert ".prawduct/.critic-findings.json" in gi


# =============================================================================
# Idempotency
# =============================================================================


def test_reapply_is_idempotent_noop(scaffolded: Path):
    again = run_init(scaffolded, "Acme Widgets", "--apply")
    assert again["already_scaffolded"] is True
    assert again["created"] == []
    assert again["edited"] == []
    assert again["created_dirs"] == []


# =============================================================================
# CLI surface
# =============================================================================


def test_usage_error_without_name(tmp_path: Path):
    target = tmp_path / "p"
    proc = subprocess.run(
        [sys.executable, str(HOOK), "init-product", str(target), "--json"],
        capture_output=True, text=True, env=_env(target), timeout=30,
    )
    assert proc.returncode == 1
    assert "error" in json.loads(proc.stdout)
    assert not target.exists()


def test_subcommand_registered():
    src = HOOK.read_text()
    assert 'command == "init-product"' in src
    assert "init-product <target> --name" in src  # usage string


def test_onboard_skill_invokes_init_product():
    # Onboarding was split out of `doctor` into its own `/prawduct:onboard` skill
    # (doctor = health-check/repair of an already-onboarded repo). The init-product
    # scaffold call now lives in the onboard skill.
    text = (ROOT / "skills" / "onboard" / "SKILL.md").read_text()
    assert "init-product" in text, "the onboard flow must use init-product"
    assert "Bash(prawduct-hook init-product" in text, "allowed-tools must permit init-product"


def test_doctor_skill_does_not_onboard():
    # Guard the split: doctor must NOT grant the scaffold capability (the
    # init-product tool), and must route setup to /prawduct:onboard. A prose
    # mention of init-product (explaining what onboard does) is fine — the
    # contract is the tool grant, not the word.
    text = (ROOT / "skills" / "doctor" / "SKILL.md").read_text()
    assert "Bash(prawduct-hook init-product" not in text, (
        "doctor must not grant init-product — scaffolding moved to /prawduct:onboard"
    )
    assert "/prawduct:onboard" in text, "doctor must route setup requests to /prawduct:onboard"
