"""What the plugin distributes — the boundary between prawduct and its consumers.

The marketplace copies a *source directory* into every consumer's plugin cache. There is no
exclusion mechanism in the plugin system — no ``exclude``/``files`` field, no ``.claudeignore`` —
so the only lever is which directory ``marketplace.json`` points at. Before v3.1.1 that was ``"./"``,
which meant the whole repo shipped: prawduct's own backlog, learnings, change-log, build plans,
test suite and internal requirements docs all landed in the cache of every product using prawduct.

That is not a tidiness problem. A model working in a *consuming* repo reads
``${CLAUDE_PLUGIN_ROOT}`` legitimately — skills instruct it to — and a broad glob there returns
another product's requirements as though they were relevant. Confidently wrong context is the
failure mode this whole framework exists to prevent.

The fix is ``plugin/``: a curated plugin root of relative symlinks, which the installer dereferences
into real content. These tests pin that boundary in both directions, because the failure is silent
either way — a leak ships someone else's documentation, and an omission breaks governance for every
consumer at once with no recall.

Deliberately asserted against **git-tracked** state rather than the working tree: a git-sourced
install (what consumers get) sees only tracked files. A *local-path* install additionally copies
untracked working-tree files, which is how 132 stray ``.pyc`` files were caught during the v3.1.1
packaging work — see ``test_no_bytecode_in_tracked_package``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO / "plugin"

# Reachable from the curated root, and required. Each entry is load-bearing:
# a consumer missing any of these has broken governance, not degraded governance.
REQUIRED = [
    ".claude-plugin/plugin.json",  # identity + the auto-update cache key
    "VERSION",                     # read at runtime by lib/core.py and lib/evidence.py
    "CHANGELOG.md",                # the version-delta banner reads this, not .prawduct/change-log.md
    "bin/prawduct-hook",
    "hooks/hooks.json",
    "hooks/gates.json",
    "hooks/banner.py",
    "hooks/digest.py",
    "lib/core.py",
    "methodology/building.md",
    "skills/runbook/SKILL.md",
    "templates/runbook.md",
    "docs/runbook-authoring.md",
]

# Must NEVER reach a consumer's plugin cache. These are prawduct's own product state and
# development surface — not secret, but actively confusing in someone else's repo.
FORBIDDEN = [
    ".prawduct",                        # backlog, learnings, change-log, every build/release plan
    "tests",                            # prawduct's own suite (including this file)
    "documentation",                    # prawduct's own internal requirements/specs
    "CLAUDE.md",                        # prawduct's own operating instructions
    "pyproject.toml",
    ".claude",                          # repo-local harness config
    ".gitignore",
    "plugin",                           # the curated root must not nest inside itself
    ".claude-plugin/marketplace.json",  # marketplace-level, not plugin-level
    "incoming-bugs",
]


def _tracked(pathspec: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", pathspec],
        capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def _shipped_paths() -> set[str]:
    """Repo-relative tracked paths that land in the cache, keyed by their path *inside* the plugin.

    Mirrors what the installer does: walk the curated root, follow each symlink to its target,
    and take the git-tracked files under it.
    """
    shipped: set[str] = set()
    for entry in sorted(PLUGIN_ROOT.rglob("*")):
        rel_in_plugin = entry.relative_to(PLUGIN_ROOT).as_posix()
        if entry.is_symlink():
            target = entry.resolve()
            if target.is_dir():
                base = target.relative_to(REPO).as_posix()
                for t in _tracked(base):
                    shipped.add(f"{rel_in_plugin}/{t[len(base) + 1:]}")
            elif target.is_file():
                shipped.add(rel_in_plugin)
        elif entry.is_file():
            # A REAL tracked file committed under plugin/ ships too. Missing this made both the
            # required-present and forbidden-absent directions blind to anything not symlinked --
            # and plugin/.claude-plugin/ is already a real directory, so the gap was live.
            if _tracked(entry.relative_to(REPO).as_posix()):
                shipped.add(rel_in_plugin)
    return shipped


@pytest.fixture(scope="module")
def shipped() -> set[str]:
    return _shipped_paths()


def test_marketplace_points_at_the_curated_root():
    """``source`` must be the curated root, never the repo root.

    A regression here reverts silently — nothing fails, the plugin still works, and every
    consumer quietly starts receiving prawduct's internal state again.
    """
    manifest = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    sources = [p.get("source") for p in manifest["plugins"]]
    assert sources == ["./plugin"], (
        f"marketplace source is {sources!r}; expected ['./plugin']. "
        "'./' ships the entire repository — see GOV-4H7T."
    )


@pytest.mark.parametrize("rel", REQUIRED)
def test_required_component_ships(rel: str, shipped: set[str]):
    assert rel in shipped, (
        f"{rel} is missing from the distributed plugin. Governance breaks for every consumer "
        "at their next session start, and a release cannot be recalled."
    )


@pytest.mark.parametrize("rel", FORBIDDEN)
def test_forbidden_path_does_not_ship(rel: str, shipped: set[str]):
    leaked = sorted(p for p in shipped if p == rel or p.startswith(f"{rel}/"))
    assert not leaked, (
        f"{rel} reaches consumer plugin caches ({len(leaked)} file(s), e.g. {leaked[:3]}). "
        "This is prawduct's own state; a model in a consuming repo would read it as that "
        "project's own context."
    )


def test_this_test_file_does_not_ship(shipped: set[str]):
    """The packaging test is itself development surface — it must not be distributed."""
    me = Path(__file__).resolve().relative_to(REPO).as_posix()
    assert not any(p == me or p.endswith("test_plugin_packaging.py") for p in shipped), (
        "the packaging test ships to consumers, which is exactly what it exists to prevent"
    )


def test_no_dead_symlinks_in_the_curated_root():
    """A dead link installs as nothing. The plugin loads, the component is silently absent."""
    dead = [
        p.relative_to(REPO).as_posix()
        for p in PLUGIN_ROOT.rglob("*")
        if p.is_symlink() and not p.exists()
    ]
    assert not dead, f"dead symlinks in the curated plugin root: {dead}"


def test_curated_root_uses_relative_symlinks():
    """Absolute symlinks resolve to the author's machine and break on every other clone."""
    absolute = [
        f"{p.relative_to(REPO).as_posix()} -> {p.readlink()}"
        for p in PLUGIN_ROOT.rglob("*")
        if p.is_symlink() and p.readlink().is_absolute()
    ]
    assert not absolute, f"absolute symlinks in the curated plugin root: {absolute}"


def test_no_bytecode_in_tracked_package(shipped: set[str]):
    """No compiled bytecode in the distributed set.

    Caught for real during v3.1.1: a *local-path* install copies untracked working-tree files, and
    132 ``.pyc`` files (3.1 MB) landed in the cache — including ``lib/backlog/__pycache__``, i.e.
    compiled bytecode of the very modules that release deliberately withheld. Git-sourced installs
    are clean because the files are untracked; this test pins the tracked set so a committed
    ``.pyc`` could never make it universal.
    """
    bytecode = sorted(p for p in shipped if p.endswith((".pyc", ".pyo")) or "__pycache__" in p)
    assert not bytecode, f"compiled bytecode in the distributed plugin: {bytecode[:5]}"


# Top-level tracked directories that are deliberately NOT distributed. Anything tracked at the
# repo root that is neither shipped nor listed here fails the reachability test below — so a new
# component directory cannot be added without an explicit decision either way.
NOT_DISTRIBUTED_DIRS = {".claude", ".claude-plugin", ".prawduct", "documentation", "plugin", "tests"}


def test_every_top_level_directory_is_shipped_or_explicitly_excluded(shipped: set[str]):
    """Every tracked top-level dir must be either symlinked into ``plugin/`` or explicitly excluded.

    Adding a new component directory (say ``commands/``) without symlinking it works locally via
    ``--plugin-dir`` on the repo root and is simply absent for everyone else.

    Phrased as a partition rather than a hardcoded list of the eight dirs that already ship: an
    earlier version iterated only those eight, so it could not fail for the very scenario its
    docstring described. (Critic, 2026-07-21.)
    """
    top_level = {p.split("/", 1)[0] for p in _tracked(".") if "/" in p}
    for d in sorted(top_level):
        if d in NOT_DISTRIBUTED_DIRS:
            continue
        assert any(p.startswith(f"{d}/") for p in shipped), (
            f"{d}/ is tracked at the repo root but nothing under it ships. Either symlink it into "
            f"plugin/, or add it to NOT_DISTRIBUTED_DIRS to record that the exclusion is deliberate."
        )


def test_no_shipped_file_points_at_an_unshipped_plugin_root_path():
    """A shipped doc must not send a model to ``${CLAUDE_PLUGIN_ROOT}/<path>`` that does not ship.

    This is the generalised form of a real defect: ``docs/runbook-authoring.md`` — which
    ``skills/runbook/SKILL.md`` instructs models to read — pointed at
    ``${CLAUDE_PLUGIN_ROOT}/.prawduct/research/.../CHECKPOINT.md``. Under the old ``source: "./"``
    that resolved; curating the root broke it, and nothing caught it because the path is
    git-tracked and the reference is prose. The failure is a model told to read a file that is not
    there — the exact confidently-wrong state the packaging change exists to prevent.
    """
    import re

    pattern = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_.@/-]+)")
    shipped_tops = {p.name for p in PLUGIN_ROOT.iterdir()} | {".claude-plugin"}
    offenders: list[str] = []
    for rel in _tracked("."):
        top = rel.split("/", 1)[0]
        if top in NOT_DISTRIBUTED_DIRS:
            continue
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for ref in pattern.findall(text):
            if ref.split("/", 1)[0] not in shipped_tops:
                offenders.append(f"{rel} -> ${{CLAUDE_PLUGIN_ROOT}}/{ref}")
    assert not offenders, (
        "shipped files reference plugin-root paths that are not distributed:\n  "
        + "\n  ".join(sorted(offenders))
    )
