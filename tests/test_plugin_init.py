"""Tests for plugin-native new-product scaffolding (Chunk 14).

The scaffolder lives in the plugin's ``lib/init_product.py`` and is driven through
``bin/prawduct-hook init-product``. These tests invoke it as a subprocess
(CLAUDE_PLUGIN_ROOT set), the established plugin-test pattern (mirrors
``test_plugin_migrate.py``), so they exercise the real CLI + plugin-root path
resolution. The scaffolder reads ``templates/`` and ``VERSION`` via ``core``'s
``TEMPLATES_DIR`` / ``PRAWDUCT_VERSION``; their ``FRAMEWORK_DIR`` depth was
fixed in review-fixes Chunk 1 (the prior ``parent.parent.parent`` was a
file-sync parity holdover that resolved one level ABOVE the plugin root and
silently read version ``"dev"`` — ``TestCoreResolution`` pins the fix).

The contract: scaffold creates ONLY the design-§3 "what STAYS in the repo" set
(product-owned ``.prawduct/`` state + the thin CLAUDE.md anchor + the committed
install reference) and NONE of the file-sync machinery.

The learnings corpus is the one piece of that set living outside ``.prawduct/``:
it is scaffolded as ``.claude/rules/learnings/core.md`` so the *harness* loads it
(``lib/learnings_files``), which is why the expected-file list names a path under
``.claude/``.
"""

from __future__ import annotations

import re
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _writes_no_base_branch_key(text: str) -> bool:
    """No *uncommented* `base_branch:` key in the rendered state file.

    A bare `"base_branch" not in text` substring test is wrong here: the
    template carries a COMMENTED-OUT `# base_branch: develop` hint, and a hint
    is not a written key. (An uncommented placeholder would be a real defect --
    it suppresses the write, and if the branch it names does not resolve every
    diff-base gate fails closed -- so the commented form is deliberate.) What
    these negative controls actually assert is that onboarding recorded nothing.
    """
    return not any(
        re.match(r"\s*base_branch\s*:", line)
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )


ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

# The design-§3 product-owned set a scaffolded repo must carry.
EXPECTED_FILES = [
    ".prawduct/project-state.yaml",
    ".claude/rules/learnings/core.md",
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


class TestCoreResolution:
    """``lib/core.py`` resolves the plugin root from ``lib/`` (review-fixes
    Chunk 1). Regression guard for the ``parent.parent.parent`` depth bug:
    ``FRAMEWORK_DIR`` pointed one level ABOVE the repo, ``TEMPLATES_DIR`` at a
    nonexistent path, and ``PRAWDUCT_VERSION`` silently fell back to ``"dev"``."""

    def test_framework_dir_is_plugin_root(self):
        from lib import core
        assert core.FRAMEWORK_DIR == ROOT

    def test_templates_dir_exists(self):
        from lib import core
        assert core.TEMPLATES_DIR.is_dir()
        assert (core.TEMPLATES_DIR / "project-state.yaml").is_file()

    def test_version_is_real_not_dev_fallback(self):
        from lib import core
        assert core.PRAWDUCT_VERSION == (ROOT / "VERSION").read_text().strip()
        assert core.PRAWDUCT_VERSION != "dev"


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


def test_learnings_scaffolded_as_a_harness_rules_file(scaffolded: Path):
    """The corpus a new product receives is a `.claude/rules/` file, not a
    `.prawduct/` one — so the harness loads it and no prawduct code is on the
    read path. The starter carries the descent obligation, which is the whole
    reason the header is scaffolded rather than left empty."""
    from lib import learnings_files  # noqa: PLC0415

    core = scaffolded / learnings_files.RULES_DIR_REL / learnings_files.CORE_NAME
    assert core.read_text(encoding="utf-8") == learnings_files.CORE_HEADER
    assert "Reading a rule is not applying it" in core.read_text(encoding="utf-8")
    # No pre-cutover corpus: a new product must never be born unmigrated.
    assert not (scaffolded / learnings_files.LEGACY_REL).exists()
    assert learnings_files.resolve(scaffolded).state == learnings_files.STATE_NEW


def test_static_anchor_present(scaffolded: Path):
    text = (scaffolded / "CLAUDE.md").read_text()
    assert "PRAWDUCT:ANCHOR" in text
    assert "/prawduct:methodology building" in text  # the anchor points at the build cycle


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


# =============================================================================
# --backlog-repo — day-one GitHub Issues adoption (ONB-3F9P)
# =============================================================================


def test_backlog_repo_recorded_on_apply(tmp_path: Path):
    target = tmp_path / "issuesprod"
    result = run_init(target, "Issues Prod", "--backlog-repo", "acme/widgets", "--apply")
    assert result["backlog_service_repo"] == "acme/widgets"
    state = (target / ".prawduct" / "project-state.yaml").read_text()
    assert "backlog_service_repo: acme/widgets" in state
    # Coexists with the distribution marker on the same file.
    assert "distribution: plugin" in state


def test_backlog_repo_dry_run_reports_without_writing(tmp_path: Path):
    target = tmp_path / "issuesprod"
    result = run_init(target, "Issues Prod", "--backlog-repo=acme/widgets")  # no --apply
    assert result["applied"] is False
    assert result["backlog_service_repo"] == "acme/widgets"  # would record
    assert not target.exists(), "dry run must not write anything"


def test_no_backlog_repo_leaves_scalar_unset(scaffolded: Path):
    # The normal markdown-first path: no --backlog-repo → no backend recorded.
    state = (scaffolded / ".prawduct" / "project-state.yaml").read_text()
    assert "backlog_service_repo" not in state


def test_value_flags_do_not_swallow_the_next_flag():
    """A value-taking flag must not consume a following ``-``-prefixed token.

    The pre-fix parser took the next token unconditionally, which did double
    damage: it invented a nonsense value AND dropped the flag it ate. Both
    halves are pinned here because the second is the dangerous one — with
    ``--json`` swallowed, a machine caller got an unparseable result, and with
    ``--apply`` swallowed a run that was meant to write silently became a
    dry run (or, worse, the reverse once only one of the two was eaten).
    """
    from lib.init_product import _parse_argv

    # `--name` with its value forgotten: the name is empty (caught by run()'s
    # usage check) and BOTH following flags survive.
    target, name, backlog_repo, apply, as_json, unknown = _parse_argv(
        ["/t", "--name", "--json", "--apply"]
    )
    assert (name, backlog_repo) == ("", None)
    assert apply is True and as_json is True, "a swallowed flag silently changes the run"
    assert unknown == [], "every token here is recognized; none should be reported"

    # Valueless must stay distinguishable from absent: `--backlog-repo` with no
    # value is a shape error (loud), while omitting it is the markdown-first
    # path (silent, correct). Collapsing both to None forfeits the one-shot
    # day-one Issues window with no diagnostic.
    assert _parse_argv(["/t", "--name", "P", "--apply", "--backlog-repo"])[2] == ""
    assert _parse_argv(["/t", "--name", "P", "--apply"])[2] is None


def test_invalid_backlog_repo_is_usage_error(tmp_path: Path):
    target = tmp_path / "p"
    proc = subprocess.run(
        [sys.executable, str(HOOK), "init-product", str(target),
         "--name", "P", "--backlog-repo", "a/b/c", "--apply", "--json"],
        capture_output=True, text=True, env=_env(target), timeout=30,
    )
    assert proc.returncode == 1
    assert "backlog-repo" in json.loads(proc.stdout)["error"]
    assert not (target / ".prawduct").exists(), "a bad target must not scaffold a half-repo"


def test_init_product_guards_bad_backlog_repo_directly(tmp_path: Path):
    # The library guard behind run()'s CLI validation: a direct caller passing a
    # malformed backlog_repo gets a warning and NO recorded scalar — never a junk
    # write. (run() rejects it earlier with exit 1; this pins the belt-and-braces.)
    from lib import init_product as ip

    target = tmp_path / "direct"
    result = ip.init_product(target, "Direct", backlog_repo="a/b/c", apply=True)
    assert result["backlog_service_repo"] is None
    assert any("--backlog-repo" in w for w in result["warnings"])
    assert "backlog_service_repo" not in (
        target / ".prawduct" / "project-state.yaml"
    ).read_text()


def test_backlog_repo_ignored_on_reapply(scaffolded: Path):
    # Re-running an already-scaffolded repo with --backlog-repo is a no-op that
    # does NOT record the backend — that would be a cutover (/prawduct:backlog
    # scrub), not a re-scaffold.
    again = run_init(scaffolded, "Acme Widgets", "--backlog-repo", "acme/widgets", "--apply")
    assert again["already_scaffolded"] is True
    assert again["backlog_service_repo"] is None
    assert any("--backlog-repo ignored" in w for w in again["warnings"])
    assert "backlog_service_repo" not in (
        scaffolded / ".prawduct" / "project-state.yaml"
    ).read_text()


def test_an_unrecognized_token_refuses_before_scaffolding(tmp_path):
    """`init-product` WRITES a repo under `--apply`, and its parser's final
    branch accepts only a bare positional — so an unrecognized flag used to fall
    off the chain and vanish. `--apply --dry-run` then scaffolded while the
    caller believed they had asked for a preview: the reported `update-gitignore`
    defect, in the command that creates repositories.
    """
    from lib.init_product import _parse_argv, run

    assert _parse_argv(["/t", "--name", "P", "--dry-run"])[5] == ["--dry-run"]
    # A second positional is unclaimed too — the first wins and the rest vanished.
    assert _parse_argv(["/t", "/other", "--name", "P"])[5] == ["/other"]

    target = tmp_path / "newrepo"
    rc = run([str(target), "--name", "P", "--apply", "--dry-run"])
    assert rc == 2, "a misread invocation must not scaffold"
    assert not target.exists(), "nothing may be written when nothing ran"


# =============================================================================
# base_branch — the gitflow knob, written at onboard (#254)
# =============================================================================
#
# `coverage._resolve_base_branch` consults `origin/HEAD` when no `base_branch:`
# is recorded, but that fallback cannot see the repo whose remote default is
# `main` while its integration branch is `develop` — only the written knob can,
# and onboarding is the moment it is cheap to write. What is under test is the
# discrimination, not the write: a key that appears in every ordinary repo is
# noise, and a key naming a branch that does not exist fails every gate CLOSED.


def _git(repo: Path, *args: str) -> str:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True, parents=True)
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
        env={
            "HOME": str(home),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
            "GIT_CONFIG_SYSTEM": str(home / "gitconfig-system"),
            "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def make_git_repo(root: Path, remote_default: str | None, *, dangling: bool = False) -> Path:
    """A git repo whose ``origin/HEAD`` names ``remote_default`` (or has none).

    ``dangling`` writes the symref WITHOUT creating the branch it names — what a
    stale ``origin/HEAD`` or a partial fetch leaves behind. ``symbolic-ref``
    never checks its target, so this state is reachable in the field.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", ".")
    _git(root, "commit", "--allow-empty", "-q", "-m", "seed")
    if remote_default is not None:
        if not dangling:
            _git(root, "update-ref", f"refs/remotes/origin/{remote_default}",
                 _git(root, "rev-parse", "HEAD"))
        _git(root, "symbolic-ref", "refs/remotes/origin/HEAD",
             f"refs/remotes/origin/{remote_default}")
    return root


@pytest.mark.parametrize("remote_default,expected", [
    ("develop", "develop"),   # the gitflow repo the knob exists for
    ("trunk", "trunk"),       # any non-main-family name, not a develop allowlist
    ("main", None),           # NEGATIVE CONTROL — the resolver already answers main
    ("master", None),         # ...and master, the other half of the family
])
def test_base_branch_written_only_for_a_non_main_family_remote_default(
    tmp_path: Path, remote_default: str, expected: "str | None"
):
    """One parametrization, both directions: the same scaffold over the same
    fixture must write the key for `develop`/`trunk` and NOT write it for
    `main`/`master`. Split across two tests, a writer that always writes (or
    never does) still passes one of them."""
    target = make_git_repo(tmp_path / "prod", remote_default)
    result = run_init(target, "Prod", "--apply")
    state = (target / ".prawduct" / "project-state.yaml").read_text()

    assert result["base_branch"] == expected
    if expected is None:
        assert _writes_no_base_branch_key(state), (
            "a trunk repo got a key that only restates the resolver's default — "
            "noise in every ordinary repo"
        )
    else:
        assert f"base_branch: {expected}\n" in state
        # And it is a bare branch name: the resolver prefixes `origin/` itself,
        # so `origin/develop` here would resolve to `origin/origin/develop`.
        assert "base_branch: origin/" not in state


def test_the_written_knob_is_what_the_resolver_then_reads(tmp_path: Path):
    """End to end past the write: the scaffolded repo's gates must actually
    anchor on the recorded branch. The write is only worth having if the
    resolver agrees with it."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from lib import coverage

    target = make_git_repo(tmp_path / "prod", "develop")
    run_init(target, "Prod", "--apply")

    base, _reason = coverage._resolve_base_branch(target)
    assert base == "origin/develop"


def test_a_repo_with_no_origin_head_scaffolds_normally(tmp_path: Path):
    """Fresh ``init``, no remote — the overwhelmingly common new-product case.
    Detection must degrade to silence, not to a failed onboard."""
    target = make_git_repo(tmp_path / "prod", None)
    result = run_init(target, "Prod", "--apply")

    assert result["base_branch"] is None
    for rel in EXPECTED_FILES:
        assert (target / rel).is_file(), f"onboarding lost {rel}"
    assert _writes_no_base_branch_key(
        (target / ".prawduct" / "project-state.yaml").read_text()
    )


def test_a_non_git_directory_scaffolds_normally(tmp_path: Path):
    """`init-product` creates the target if it does not exist, and a repo need
    not be a git repo at all to be scaffolded — every git probe here is
    best-effort."""
    target = tmp_path / "notarepo"
    result = run_init(target, "Prod", "--apply")

    assert result["base_branch"] is None
    assert (target / ".prawduct" / "project-state.yaml").is_file()


def test_a_dangling_origin_head_is_not_recorded(tmp_path: Path):
    """``origin/HEAD`` can name a branch that was never fetched. Recording it
    would be worse than recording nothing: a configured-but-unresolvable
    `base_branch:` fails EVERY diff-base gate closed, so an unverified name
    turns a working repo into a broken one."""
    target = make_git_repo(tmp_path / "prod", "develop", dangling=True)
    result = run_init(target, "Prod", "--apply")

    assert result["base_branch"] is None
    assert _writes_no_base_branch_key(
        (target / ".prawduct" / "project-state.yaml").read_text()
    )


def test_dry_run_previews_the_base_branch_without_writing(tmp_path: Path):
    """The operator's single confirmation is given against the preview, and this
    key changes what every gate measures — so it has to appear there."""
    target = make_git_repo(tmp_path / "prod", "develop")
    result = run_init(target, "Prod")  # no --apply

    assert result["base_branch"] == "develop"
    assert not (target / ".prawduct").exists(), "dry run wrote state"


def test_an_operator_set_base_branch_is_never_clobbered(tmp_path: Path):
    """Onboarding an existing repo that already recorded its own integration
    base: the remote's default is a guess, the operator's value is a decision."""
    target = make_git_repo(tmp_path / "prod", "develop")
    (target / ".prawduct").mkdir()
    (target / ".prawduct" / "project-state.yaml").write_text(
        "# Project State\nbase_branch: release\n"
    )
    result = run_init(target, "Prod", "--apply")

    state = (target / ".prawduct" / "project-state.yaml").read_text()
    assert "base_branch: release" in state
    assert "base_branch: develop" not in state
    assert result["base_branch"] == "release", "reported a branch the file does not hold"


def test_human_output_names_the_recorded_base_branch(tmp_path: Path):
    """--json is not the only reader: the skill runs the plain form too, and a
    silent change to the gates' anchor is exactly the kind of thing an operator
    must be told about."""
    target = make_git_repo(tmp_path / "prod", "develop")
    proc = subprocess.run(
        [sys.executable, str(HOOK), "init-product", str(target),
         "--name", "Prod", "--apply"],
        capture_output=True, text=True, env=_env(target), timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "base_branch: develop" in proc.stdout
