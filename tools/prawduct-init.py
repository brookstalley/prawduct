#!/usr/bin/env python3
"""
prawduct-init.py — Generate self-contained product repos.

Creates the .prawduct/ structure, copies templates with variable substitution,
sets up hooks, generates a sync manifest, and configures .gitignore. Product
repos work standalone; the sync manifest enables automatic framework updates.

Idempotent: running twice produces no changes on the second run.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import stat
import sys
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"

# Import shared helpers from prawduct-sync.py
_sync_path = FRAMEWORK_DIR / "tools" / "prawduct-sync.py"
_sync_spec = importlib.util.spec_from_file_location("prawduct_sync", _sync_path)
_sync_mod = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(_sync_mod)

compute_hash = _sync_mod.compute_hash
compute_block_hash = _sync_mod.compute_block_hash
render_template = _sync_mod.render_template
merge_settings = _sync_mod.merge_settings
create_manifest = _sync_mod.create_manifest
BLOCK_BEGIN = _sync_mod.BLOCK_BEGIN

# Session files that should be gitignored in product repos
GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-findings.json",
    ".prawduct/.pr-reviews/",
    ".prawduct/.session-git-baseline",
    ".prawduct/.session-handoff.md",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    ".prawduct/.subagent-briefing.md",
    ".prawduct/reflections.md",
    ".prawduct/sync-manifest.json",
    "__pycache__/",
]


def is_v1_repo(target_dir: str) -> bool:
    """Check if target is a v1 Prawduct repo (has .prawduct/framework-path)."""
    return Path(target_dir, ".prawduct", "framework-path").is_file()


def log(msg: str) -> None:
    """Print status to stderr."""
    print(msg, file=sys.stderr)


def ensure_dir(path: Path) -> bool:
    """Create directory if missing. Returns True if created."""
    if path.is_dir():
        return False
    path.mkdir(parents=True, exist_ok=True)
    return True


def write_template(src: Path, dst: Path, subs: dict[str, str]) -> bool:
    """Copy a template with variable substitution. Skips if dst exists.
    Returns True if file was written."""
    content = render_template(src, subs)

    if dst.is_file():
        if dst.read_text() == content:
            return False  # Already up to date
        return False  # Exists with different content — don't overwrite user edits

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


def copy_hook(src: Path, dst: Path) -> bool:
    """Copy a hook script and make it executable. Updates if content changed.
    Returns True if file was written."""
    src_bytes = src.read_bytes()

    if dst.is_file():
        if dst.read_bytes() == src_bytes:
            return False  # Already up to date
        # Hook content changed — update it (hooks should stay current)
        dst.write_bytes(src_bytes)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def update_gitignore(target: Path) -> bool:
    """Add prawduct entries to .gitignore. Returns True if modified."""
    gitignore = target / ".gitignore"

    if gitignore.is_file():
        content = gitignore.read_text()
        existing_lines = set(content.splitlines())
    else:
        content = ""
        existing_lines = set()

    missing = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    if not missing:
        return False

    parts = []
    if content and not content.endswith("\n"):
        parts.append("\n")
    if content.strip():
        parts.append("\n")
    parts.append("# Prawduct session files\n")
    for entry in missing:
        parts.append(entry + "\n")

    gitignore.write_text(content + "".join(parts))
    return True


def run_init(target_dir: str, product_name: str) -> dict:
    """Initialize a product repo. Returns a summary of actions taken."""
    target = Path(target_dir).resolve()
    actions: list[str] = []

    subs = {
        "{{PRODUCT_NAME}}": product_name,
    }

    # 1. .prawduct/ structure
    for subdir in [".prawduct", ".prawduct/artifacts"]:
        path = target / subdir
        if ensure_dir(path):
            actions.append(f"Created {subdir}/")

    # 2. CLAUDE.md — three-way handling for existing repos
    claude_dst = target / "CLAUDE.md"
    if not claude_dst.is_file():
        # New file — write full template
        if write_template(TEMPLATES_DIR / "product-claude.md", claude_dst, subs):
            actions.append("Created CLAUDE.md")
    elif BLOCK_BEGIN not in claude_dst.read_text():
        # Existing file without markers — merge: template + user content below
        existing_content = claude_dst.read_text()
        template_content = render_template(TEMPLATES_DIR / "product-claude.md", subs)
        merged = template_content.rstrip("\n") + "\n\n" + existing_content
        claude_dst.write_text(merged)
        actions.append("Merged framework content into existing CLAUDE.md")
    # else: already has markers — skip (sync handles updates)

    # 3. Critic review instructions
    if write_template(
        TEMPLATES_DIR / "critic-review.md",
        target / ".prawduct" / "critic-review.md",
        subs,
    ):
        actions.append("Created .prawduct/critic-review.md")

    # 4. Project state
    if write_template(
        TEMPLATES_DIR / "project-state.yaml",
        target / ".prawduct" / "project-state.yaml",
        subs,
    ):
        actions.append("Created .prawduct/project-state.yaml")

    # 5. Project preferences template
    if write_template(
        TEMPLATES_DIR / "project-preferences.md",
        target / ".prawduct" / "artifacts" / "project-preferences.md",
        subs,
    ):
        actions.append("Created .prawduct/artifacts/project-preferences.md")

    # 6. Boundary patterns template
    if write_template(
        TEMPLATES_DIR / "boundary-patterns.md",
        target / ".prawduct" / "artifacts" / "boundary-patterns.md",
        subs,
    ):
        actions.append("Created .prawduct/artifacts/boundary-patterns.md")

    # 6.5. PR review instructions
    if write_template(
        TEMPLATES_DIR / "pr-review.md",
        target / ".prawduct" / "pr-review.md",
        subs,
    ):
        actions.append("Created .prawduct/pr-review.md")

    # 6.6. PR slash command
    commands_dir = target / ".claude" / "commands"
    if ensure_dir(commands_dir):
        actions.append("Created .claude/commands/")
    pr_cmd_src = TEMPLATES_DIR / "commands-pr.md"
    pr_cmd_dst = commands_dir / "pr.md"
    if pr_cmd_src.is_file() and write_template(pr_cmd_src, pr_cmd_dst, subs):
        actions.append("Created .claude/commands/pr.md")

    # 7. Test infrastructure (conftest.py with parallel test support)
    tests_dir = target / "tests"
    if ensure_dir(tests_dir):
        actions.append("Created tests/")
    conftest_dst = tests_dir / "conftest.py"
    if not conftest_dst.is_file():
        shutil.copy2(TEMPLATES_DIR / "conftest.py", conftest_dst)
        actions.append("Created tests/conftest.py (parallel test support)")

    # 8. Learnings starter
    learnings = target / ".prawduct" / "learnings.md"
    if not learnings.is_file():
        learnings.write_text(
            "# Learnings\n\nAccumulated wisdom from building this product.\n"
        )
        actions.append("Created .prawduct/learnings.md")

    # 9. Product hook
    if copy_hook(
        FRAMEWORK_DIR / "tools" / "product-hook",
        target / "tools" / "product-hook",
    ):
        actions.append("Created tools/product-hook")

    # 10. Settings.json (with subs for banner)
    if merge_settings(
        target / ".claude" / "settings.json",
        TEMPLATES_DIR / "product-settings.json",
        subs,
    ):
        actions.append("Created/updated .claude/settings.json")

    # 11. .gitignore
    if update_gitignore(target):
        actions.append("Updated .gitignore")

    # 12. Sync manifest
    manifest_path = target / ".prawduct" / "sync-manifest.json"
    if not manifest_path.is_file():
        claude_content = (target / "CLAUDE.md").read_text()
        file_hashes = {
            "CLAUDE.md": compute_block_hash(claude_content),
            ".prawduct/critic-review.md": compute_hash(
                target / ".prawduct" / "critic-review.md"
            ),
            ".prawduct/pr-review.md": compute_hash(
                target / ".prawduct" / "pr-review.md"
            ),
            ".claude/commands/pr.md": compute_hash(
                target / ".claude" / "commands" / "pr.md"
            ),
            "tools/product-hook": compute_hash(target / "tools" / "product-hook"),
            ".claude/settings.json": None,  # merge_settings doesn't use hash
        }
        manifest = create_manifest(target, FRAMEWORK_DIR, product_name, file_hashes)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        actions.append("Created .prawduct/sync-manifest.json")

    return {
        "target": str(target),
        "product_name": product_name,
        "actions": actions,
        "files_written": len(actions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained Prawduct product repo.",
    )
    parser.add_argument(
        "target_dir",
        help="Target directory for the product repo",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Product name",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="JSON output only",
    )
    args = parser.parse_args()

    target = os.path.abspath(args.target_dir)
    if not os.path.isdir(target):
        os.makedirs(target, exist_ok=True)

    if is_v1_repo(target):
        log("This looks like a v1 Prawduct repo.")
        log("Run prawduct-migrate.py to upgrade:")
        log(f"  python3 {FRAMEWORK_DIR / 'tools' / 'prawduct-migrate.py'} {target}")
        return 1

    result = run_init(target, args.name)

    if args.json_mode:
        print(json.dumps(result, indent=2))
    else:
        log(f"Initialized Prawduct product: {args.name}")
        log(f"  Directory: {result['target']}")
        if result["actions"]:
            for action in result["actions"]:
                log(f"  + {action}")
        else:
            log("  (no changes — already initialized)")
        log("")
        log("Next: Open this directory in Claude Code to start discovery.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
