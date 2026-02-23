#!/usr/bin/env python3
"""
prawduct-migrate.py — Migrate v1 product repos to v3 (self-contained).

V1 repos depend on an external framework directory via .prawduct/framework-path.
V3 repos are fully self-contained. This script makes any repo v3-shaped:
overwrites the bootstrap CLAUDE.md, replaces hooks, copies product-hook,
archives historical v1 directories, and cleans up v1-only files.

Idempotent: running on an already-v3 repo produces zero changes.
Running twice on a v1 repo produces changes on first run, zero on second.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"

# V3 gitignore entries (same as prawduct-init.py)
V3_GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-findings.json",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    "__pycache__/",
]

# V1-specific gitignore entries to remove
V1_GITIGNORE_ENTRIES = [
    ".prawduct/traces/",
    ".prawduct/framework-observations/",
    ".prawduct/.cross-repo-edits",
    ".prawduct/.session-governance.json",
    ".prawduct/.orchestrator-activated",
]

# V1 transient session files
V1_SESSION_FILES = [
    ".prawduct/.session-governance.json",
    ".prawduct/.orchestrator-activated",
    ".prawduct/.skill-context.json",
    ".prawduct/.active-skill",
]


def log(msg: str) -> None:
    """Print status to stderr."""
    print(msg, file=sys.stderr)


def detect_version(target: Path) -> str:
    """Detect repo version. Returns 'v1', 'v3', 'partial', or 'unknown'."""
    has_framework_path = (target / ".prawduct" / "framework-path").is_file()
    has_product_hook = (target / "tools" / "product-hook").is_file()

    if has_framework_path and not has_product_hook:
        return "v1"
    if has_product_hook and not has_framework_path:
        return "v3"
    if has_framework_path and has_product_hook:
        return "partial"
    return "unknown"


def infer_product_name(target: Path) -> str | None:
    """Read product_identity.name from project-state.yaml via regex.

    No PyYAML dependency — scans line by line for the name field under
    product_identity. Returns None if the file is missing, the field is
    absent, or the value is a template placeholder.
    """
    state_file = target / ".prawduct" / "project-state.yaml"
    if not state_file.is_file():
        return None

    in_product_identity = False
    for line in state_file.read_text().splitlines():
        stripped = line.strip()

        # Track when we're inside product_identity block
        if stripped == "product_identity:" or stripped.startswith("product_identity:"):
            in_product_identity = True
            continue

        # Exit block on unindented line (new top-level key)
        if in_product_identity and line and not line[0].isspace():
            in_product_identity = False
            continue

        if in_product_identity:
            match = re.match(r'\s*name:\s*["\']?([^"\'#\n]+?)["\']?\s*$', line)
            if match:
                name = match.group(1).strip()
                if name and "{{" not in name and name != "null":
                    return name

    return None


def write_template_overwrite(src: Path, dst: Path, subs: dict[str, str]) -> bool:
    """Copy a template with variable substitution, overwriting existing content.
    Idempotent via content comparison. Returns True if file was written."""
    content = src.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)

    if dst.is_file():
        if dst.read_text() == content:
            return False  # Already up to date

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


def write_template_if_missing(src: Path, dst: Path, subs: dict[str, str]) -> bool:
    """Copy a template only if dst doesn't exist. Returns True if file was written."""
    if dst.is_file():
        return False

    content = src.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


def replace_settings(dst: Path, template_path: Path) -> bool:
    """Replace v1 hooks with v3 hooks in .claude/settings.json.

    Identifies v1 hooks by checking if command contains 'framework-path',
    'governance-hook', or 'prawduct-statusline'. Removes v1 statusLine
    if it references prawduct. Preserves non-prawduct hooks and other
    settings keys. Returns True if file was written.
    """
    template = json.loads(template_path.read_text())

    if not dst.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(template, indent=2) + "\n")
        return True

    try:
        existing = json.loads(dst.read_text())
    except json.JSONDecodeError:
        log(f"  ! Could not parse {dst.name} — skipping")
        return False

    v1_markers = ["framework-path", "governance-hook", "prawduct-statusline"]

    def is_v1_hook_entry(entry: dict) -> bool:
        """Check if a hook entry is a v1 prawduct hook."""
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if any(marker in cmd for marker in v1_markers):
                return True
        return False

    # Collect v3 hook commands from template
    v3_commands: set[str] = set()
    template_hooks = template.get("hooks", {})
    for entries in template_hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    v3_commands.add(hook["command"])

    # Build merged hooks: start with template hooks, add non-v1/non-v3 user hooks
    merged_hooks: dict = dict(template_hooks)
    for event, entries in existing.get("hooks", {}).items():
        if event not in merged_hooks:
            # Non-prawduct event — keep user entries, filtering out v1
            user_entries = [e for e in entries if not is_v1_hook_entry(e)]
            if user_entries:
                merged_hooks[event] = user_entries
            continue

        # Event exists in template — add non-prawduct, non-v1 user entries
        user_entries = []
        for entry in entries:
            if is_v1_hook_entry(entry):
                continue  # Drop v1 hook
            is_v3 = any(
                hook.get("command") in v3_commands
                for hook in entry.get("hooks", [])
                if hook.get("type") == "command"
            )
            if not is_v3:
                user_entries.append(entry)

        if user_entries:
            merged_hooks[event] = merged_hooks[event] + user_entries

    # Build merged settings: preserve all non-hook keys
    merged = dict(existing)
    merged["hooks"] = merged_hooks

    # Remove v1 statusLine if it references prawduct
    if "statusLine" in merged:
        status_line = merged["statusLine"]
        if isinstance(status_line, str) and "prawduct" in status_line.lower():
            del merged["statusLine"]
        elif isinstance(status_line, dict):
            cmd = status_line.get("command", "")
            if "prawduct" in cmd.lower():
                del merged["statusLine"]

    if json.dumps(merged, sort_keys=True) == json.dumps(existing, sort_keys=True):
        return False

    dst.write_text(json.dumps(merged, indent=2) + "\n")
    return True


def delete_v1_files(target: Path) -> list[str]:
    """Remove v1-only marker files. Returns list of deleted file names."""
    v1_files = [
        ".prawduct/framework-path",
        ".prawduct/framework-version",
        ".prawduct/.cross-repo-edits",
    ]
    deleted = []
    for rel in v1_files:
        path = target / rel
        if path.is_file():
            path.unlink()
            deleted.append(rel)
    return deleted


def archive_v1_dirs(target: Path) -> list[str]:
    """Move v1 directories to .prawduct/archive/. Returns list of archived dir names."""
    v1_dirs = [
        ".prawduct/framework-observations",
        ".prawduct/traces",
    ]
    archived = []
    for rel in v1_dirs:
        src = target / rel
        if not src.is_dir():
            continue
        archive_dir = target / ".prawduct" / "archive"
        dst = archive_dir / Path(rel).name
        if dst.exists():
            continue  # Already archived
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        archived.append(rel)
    return archived


def clean_v1_session_files(target: Path) -> list[str]:
    """Remove transient v1 session files. Returns list of deleted file names."""
    deleted = []
    for rel in V1_SESSION_FILES:
        path = target / rel
        if path.is_file():
            path.unlink()
            deleted.append(rel)
    return deleted


def clean_gitignore(target: Path) -> bool:
    """Remove v1-specific entries, add v3 entries. Returns True if modified."""
    gitignore = target / ".gitignore"
    changed = False

    if gitignore.is_file():
        content = gitignore.read_text()
        lines = content.splitlines()
    else:
        content = ""
        lines = []

    # Remove v1 entries
    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped in V1_GITIGNORE_ENTRIES:
            changed = True
            continue
        filtered.append(line)

    # Add missing v3 entries
    existing_set = set(l.strip() for l in filtered)
    missing = [e for e in V3_GITIGNORE_ENTRIES if e not in existing_set]

    if missing:
        changed = True
        if filtered and filtered[-1].strip():
            filtered.append("")
        filtered.append("# Prawduct session files")
        for entry in missing:
            filtered.append(entry)

    if not changed:
        return False

    gitignore.write_text("\n".join(filtered) + "\n")
    return True


def copy_hook(src: Path, dst: Path) -> bool:
    """Copy a hook script and make it executable. Updates if content changed.
    Returns True if file was written."""
    src_bytes = src.read_bytes()

    if dst.is_file():
        if dst.read_bytes() == src_bytes:
            return False
        dst.write_bytes(src_bytes)
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def run_migrate(target_dir: str, product_name: str | None = None) -> dict:
    """Migrate a product repo to v3. Returns a summary of actions taken."""
    target = Path(target_dir).resolve()
    actions: list[str] = []

    version = detect_version(target)

    # Safety: refuse to migrate directories that aren't Prawduct repos
    if version == "unknown":
        return {
            "target": str(target),
            "product_name": product_name or target.name,
            "version_before": version,
            "version_after": version,
            "actions": [],
            "files_changed": 0,
            "error": "Not a Prawduct repo (no .prawduct/framework-path or tools/product-hook found)",
        }

    # Infer product name if not provided
    if product_name is None:
        product_name = infer_product_name(target)
    if product_name is None:
        product_name = target.name

    subs = {"{{PRODUCT_NAME}}": product_name}

    # 1. Overwrite CLAUDE.md with v3 template
    if write_template_overwrite(
        TEMPLATES_DIR / "product-claude.md", target / "CLAUDE.md", subs
    ):
        actions.append("Overwrote CLAUDE.md with v3 template")

    # 2. Replace hooks in settings.json
    if replace_settings(
        target / ".claude" / "settings.json",
        TEMPLATES_DIR / "product-settings.json",
    ):
        actions.append("Replaced hooks in .claude/settings.json")

    # 3. Copy product-hook
    if copy_hook(
        FRAMEWORK_DIR / "tools" / "product-hook",
        target / "tools" / "product-hook",
    ):
        actions.append("Installed tools/product-hook")

    # 4. Create critic-review.md if missing
    if write_template_if_missing(
        TEMPLATES_DIR / "critic-review.md",
        target / ".prawduct" / "critic-review.md",
        subs,
    ):
        actions.append("Created .prawduct/critic-review.md")

    # 5. Create learnings.md if missing
    learnings = target / ".prawduct" / "learnings.md"
    if not learnings.is_file():
        learnings.parent.mkdir(parents=True, exist_ok=True)
        learnings.write_text(
            "# Learnings\n\nAccumulated wisdom from building this product.\n"
        )
        actions.append("Created .prawduct/learnings.md")

    # 6. Delete v1 marker files
    deleted = delete_v1_files(target)
    for f in deleted:
        actions.append(f"Deleted {f}")

    # 7. Archive v1 directories
    archived = archive_v1_dirs(target)
    for d in archived:
        actions.append(f"Archived {d} → .prawduct/archive/")

    # 8. Clean v1 session files
    cleaned = clean_v1_session_files(target)
    for f in cleaned:
        actions.append(f"Deleted session file {f}")

    # 9. Clean gitignore
    if clean_gitignore(target):
        actions.append("Updated .gitignore")

    return {
        "target": str(target),
        "product_name": product_name,
        "version_before": version,
        "version_after": detect_version(target),
        "actions": actions,
        "files_changed": len(actions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate a Prawduct product repo from v1 to v3 (self-contained).",
    )
    parser.add_argument(
        "target_dir",
        nargs="?",
        default=".",
        help="Target directory (default: current directory)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Product name (inferred from project-state.yaml if not provided)",
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
        log(f"Error: {target} is not a directory")
        return 1

    result = run_migrate(target, args.name)

    if "error" in result:
        if args.json_mode:
            print(json.dumps(result, indent=2))
        else:
            log(f"Error: {result['error']}")
            log(f"  Directory: {result['target']}")
            log("  Use prawduct-init.py to create a new product repo.")
        return 1

    if args.json_mode:
        print(json.dumps(result, indent=2))
    else:
        log(f"Migrated Prawduct product: {result['product_name']}")
        log(f"  Directory: {result['target']}")
        log(f"  Version: {result['version_before']} → {result['version_after']}")
        if result["actions"]:
            for action in result["actions"]:
                log(f"  + {action}")
        else:
            log("  (no changes — already v3)")
        log("")
        if result["version_after"] == "v3":
            log("Migration complete. Product repo is now self-contained.")
        else:
            log(f"Note: version detected as '{result['version_after']}' — review manually.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
