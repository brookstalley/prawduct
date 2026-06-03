"""
Core utilities and constants shared across the plugin's governance modules.

After the file-sync engine was retired in M4 (``MIG-M4-REMOVE``), the only
consumers of this module are the plugin-native governance commands — chiefly
``migrate_plugin`` (which derives its file-sync→plugin REMOVE set from the
``MANAGED_FILES`` / ``MANAGED_DIRS`` path registry) and ``init_product`` (which
renders the place-once product-state templates and seeds ``.gitignore``). The
sync/init/validate command layer that once lived in ``tools/lib/`` — and the
helper functions here that only served it (manifest building, settings merge,
template/skill placement, framework-dir resolution, vN gitignore migration) —
is gone.
"""

from __future__ import annotations

import sys
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"


# =============================================================================
# Constants
# =============================================================================

try:
    PRAWDUCT_VERSION = (FRAMEWORK_DIR / "VERSION").read_text().strip()
except FileNotFoundError:
    PRAWDUCT_VERSION = "dev"

BLOCK_BEGIN = "<!-- PRAWDUCT:BEGIN -->"
BLOCK_END = "<!-- PRAWDUCT:END -->"

# The framework-managed file path registry. These are the file-sync framework
# files a *consuming* repo carries; ``migrate_plugin`` derives the cutover
# REMOVE / edit-in-place set from this registry (CLAUDE.md + .claude/settings.json
# are edited, the rest are removed), and ``update_gitignore`` un-ignores them so
# they stay committed. The plugin never *places* these — it ships governance from
# its own ``skills/`` + ``methodology/`` — so only the paths matter; the file-sync
# template/strategy metadata retired with the engine.
MANAGED_FILES: frozenset[str] = frozenset({
    "CLAUDE.md",
    ".prawduct/critic-review.md",
    ".prawduct/pr-review.md",
    ".prawduct/build-governance.md",
    ".claude/skills/pr/SKILL.md",
    ".claude/skills/janitor/SKILL.md",
    ".claude/skills/prawduct-doctor/SKILL.md",
    ".claude/skills/learnings/SKILL.md",
    ".claude/skills/prawduct-advisory/SKILL.md",
    ".claude/skills/backlog/SKILL.md",
    ".claude/skills/critic/SKILL.md",
    "tools/product-hook",
    ".claude/settings.json",
})

# Managed directories: every matching file is framework-owned. The sole consumer
# is ``migrate_plugin``, which globs the *consumer's* ``tools/lib`` so it removes
# that repo's full (possibly older) module set during the cutover onto the plugin.
MANAGED_DIRS: dict[str, dict] = {
    "tools/lib": {
        "glob": "*.py",
    },
}

# Session files that should be gitignored in product repos
GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-findings.json",
    ".prawduct/.test-evidence.json",
    ".prawduct/.pr-reviews/",
    ".prawduct/.session-git-baseline",
    ".prawduct/.session-handoff.md",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    ".prawduct/.subagent-briefing.md",
    ".prawduct/.gates-waived",
    ".prawduct/.advisories.json",
    ".prawduct/reflections.md",
    ".prawduct/artifacts/build-plan.md",
    "__pycache__/",
]


# =============================================================================
# Core utilities
# =============================================================================


def log(msg: str) -> None:
    """Print status to stderr."""
    print(msg, file=sys.stderr)


# Optional project-state pointer naming the active build plan (relative to the
# `.prawduct/` dir). When unset, tooling uses the conventional default below, so
# repos that don't set it keep their existing behavior.
BUILD_PLAN_POINTER_KEY = "active_build_plan"
DEFAULT_BUILD_PLAN_REL = "artifacts/build-plan.md"


def read_str_yaml_key(state_path: Path, key: str) -> str | None:
    """Value of a top-level (column-0) ``key: value`` scalar, or None.

    Mirrors the column-0 idiom used by ``is_views_enabled`` and product-hook's
    ``_read_bool_yaml_key`` — no PyYAML dependency, fail-soft to None on a
    missing/unreadable file or absent key. Surrounding quotes and inline ``#``
    comments are stripped; an empty value reads as None.
    """
    try:
        content = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    needle = f"{key}:"
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        value = line.split(":", 1)[1].strip().strip("\"'")
        return value or None
    return None


def resolve_build_plan_path(prawduct_dir: Path) -> Path:
    """Resolve the active build-plan path (supports standard + scope-named plans).

    Reads an optional ``active_build_plan:`` pointer (a path relative to the
    ``.prawduct/`` dir) from ``project-state.yaml``; when set, that file is the
    active plan, letting a project name its plan by scope
    (``artifacts/v1.6.0-foo-plan.md``). When the pointer is absent, falls back to
    the conventional ``artifacts/build-plan.md`` — so repos that don't set it
    behave exactly as before. The returned path may not exist; callers treat a
    missing plan as "no active build plan."

    Kept in sync with the inline mirror in ``bin/prawduct-hook``
    (``_resolve_build_plan_path``), which cannot import this module in product
    repos — a parity test pins the two together.
    """
    pointer = read_str_yaml_key(prawduct_dir / "project-state.yaml", BUILD_PLAN_POINTER_KEY)
    if pointer:
        return prawduct_dir / pointer
    return prawduct_dir / DEFAULT_BUILD_PLAN_REL


def extract_block(content: str) -> tuple[str | None, str, str]:
    """Extract content between PRAWDUCT markers.

    Returns (block, before, after) where before + block + after == content.
    Returns (None, content, "") if markers are missing or malformed
    (e.g. BEGIN without END, or END before BEGIN).
    """
    begin_idx = content.find(BLOCK_BEGIN)
    end_idx = content.find(BLOCK_END)

    if begin_idx == -1 or end_idx == -1 or end_idx <= begin_idx:
        return (None, content, "")

    before = content[:begin_idx]
    block = content[begin_idx : end_idx + len(BLOCK_END)]
    after = content[end_idx + len(BLOCK_END) :]

    return (block, before, after)


# =============================================================================
# Template / file operations
# =============================================================================


def render_template(template_path: Path, subs: dict[str, str]) -> str:
    """Read a template file and apply variable substitutions."""
    content = template_path.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)
    return content


def write_template(src: Path, dst: Path, subs: dict[str, str], *, overwrite: bool = False) -> bool:
    """Copy a template with variable substitution.

    Without overwrite: skips if dst exists.
    With overwrite: idempotent via content comparison.
    Returns True if file was written.
    """
    content = render_template(src, subs)

    if dst.is_file():
        if not overwrite:
            return False
        if dst.read_text() == content:
            return False  # Already up to date

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


def update_gitignore(target: Path) -> dict:
    """Add prawduct entries to .gitignore and remove incorrect ones.

    Managed files (MANAGED_FILES) should be committed, not gitignored.
    Session files (GITIGNORE_ENTRIES) should be gitignored.
    Returns dict with 'modified' bool and 'unignored' list of paths
    that were removed from .gitignore (caller should advise user to
    git-add these).
    """
    gitignore = target / ".gitignore"

    if gitignore.is_file():
        content = gitignore.read_text()
        existing_lines = set(content.splitlines())
    else:
        content = ""
        existing_lines = set()

    modified = False
    unignored: list[str] = []

    # Remove lines that gitignore managed files (they should be committed)
    incorrectly_ignored = set()
    for rel_path in MANAGED_FILES:
        if rel_path in existing_lines:
            incorrectly_ignored.add(rel_path)

    if incorrectly_ignored:
        lines = content.splitlines(keepends=True)
        filtered = [line for line in lines if line.rstrip("\n") not in incorrectly_ignored]
        content = "".join(filtered)
        existing_lines -= incorrectly_ignored
        unignored = sorted(incorrectly_ignored)
        modified = True

    # Add missing session file entries
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    if missing:
        parts = []
        if content and not content.endswith("\n"):
            parts.append("\n")
        if content.strip():
            parts.append("\n")
        parts.append("# Prawduct session files\n")
        for entry in missing:
            parts.append(entry + "\n")
        content += "".join(parts)
        modified = True

    if modified:
        gitignore.write_text(content)

    return {"modified": modified, "unignored": unignored}
