#!/usr/bin/env python3
"""
prawduct-init.py — Generate self-contained product repos.

Creates the .prawduct/ structure, copies templates with variable substitution,
sets up hooks, and configures .gitignore. Product repos have no runtime
dependency on the framework — everything needed to build is generated here.

Idempotent: running twice produces no changes on the second run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"

# Session files that should be gitignored in product repos
GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-findings.json",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
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
    content = src.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)

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


def merge_settings(dst: Path, template_path: Path) -> bool:
    """Create or merge .claude/settings.json. Preserves user hooks.
    Returns True if file was written."""
    template = json.loads(template_path.read_text())

    if not dst.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(template, indent=2) + "\n")
        return True

    try:
        existing = json.loads(dst.read_text())
    except json.JSONDecodeError:
        log(f"  ! Could not parse {dst.name} — skipping merge")
        return False

    # Already matches?
    if json.dumps(existing, sort_keys=True) == json.dumps(template, sort_keys=True):
        return False

    # Collect prawduct hook commands from template
    our_commands: set[str] = set()
    template_hooks = template.get("hooks", {})
    for entries in template_hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    our_commands.add(hook["command"])

    # Merge: start with template hooks, add non-prawduct user hooks
    merged_hooks: dict = dict(template_hooks)
    for event, entries in existing.get("hooks", {}).items():
        if event not in merged_hooks:
            merged_hooks[event] = entries
            continue

        user_entries = []
        for entry in entries:
            is_ours = any(
                hook.get("command") in our_commands
                for hook in entry.get("hooks", [])
                if hook.get("type") == "command"
            )
            if not is_ours:
                user_entries.append(entry)

        if user_entries:
            merged_hooks[event] = merged_hooks[event] + user_entries

    # Preserve other settings keys (companyAnnouncements, etc.)
    merged = dict(existing)
    merged["hooks"] = merged_hooks

    if json.dumps(merged, sort_keys=True) == json.dumps(existing, sort_keys=True):
        return False

    dst.write_text(json.dumps(merged, indent=2) + "\n")
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

    # 2. CLAUDE.md
    if write_template(TEMPLATES_DIR / "product-claude.md", target / "CLAUDE.md", subs):
        actions.append("Created CLAUDE.md")

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

    # 5. Learnings starter
    learnings = target / ".prawduct" / "learnings.md"
    if not learnings.is_file():
        learnings.write_text(
            "# Learnings\n\nAccumulated wisdom from building this product.\n"
        )
        actions.append("Created .prawduct/learnings.md")

    # 6. Product hook
    if copy_hook(
        FRAMEWORK_DIR / "tools" / "product-hook",
        target / "tools" / "product-hook",
    ):
        actions.append("Created tools/product-hook")

    # 7. Settings.json
    if merge_settings(
        target / ".claude" / "settings.json",
        TEMPLATES_DIR / "product-settings.json",
    ):
        actions.append("Created/updated .claude/settings.json")

    # 8. .gitignore
    if update_gitignore(target):
        actions.append("Updated .gitignore")

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
        log("Run prawduct-migrate.py to upgrade to v3:")
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
