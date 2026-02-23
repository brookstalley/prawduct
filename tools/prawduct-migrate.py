#!/usr/bin/env python3
"""
prawduct-migrate.py — Migrate product repos to the latest version.

Handles:
  v1 → v4: Full migration from framework-dependent repos
  v3 → v4: Add sync manifest, Python hook, banner
  v4 → v4: Idempotent (no changes)

V1 repos depend on an external framework directory via .prawduct/framework-path.
V3 repos are self-contained with a bash product-hook.
V4 repos add sync manifest, Python hook, and banner.

Idempotent: running on an already-current repo produces zero changes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
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
extract_block = _sync_mod.extract_block
render_template = _sync_mod.render_template
merge_settings = _sync_mod.merge_settings
create_manifest = _sync_mod.create_manifest
BLOCK_BEGIN = _sync_mod.BLOCK_BEGIN
BLOCK_END = _sync_mod.BLOCK_END

# V4 gitignore entries
V4_GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.critic-findings.json",
    ".prawduct/.session-git-baseline",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    ".prawduct/sync-manifest.json",
    "__pycache__/",
]

# V3 gitignore entries (subset of V4 — used to detect already-present entries)
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
    """Detect repo version. Returns 'v1', 'v3', 'v4', 'partial', or 'unknown'."""
    has_framework_path = (target / ".prawduct" / "framework-path").is_file()
    has_product_hook = (target / "tools" / "product-hook").is_file()
    has_sync_manifest = (target / ".prawduct" / "sync-manifest.json").is_file()

    if has_framework_path and not has_product_hook:
        return "v1"
    if has_framework_path and has_product_hook:
        return "partial"
    if has_product_hook and has_sync_manifest:
        return "v4"
    if has_product_hook and not has_framework_path:
        return "v3"
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
    content = render_template(src, subs)

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

    content = render_template(src, subs)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


def replace_settings(dst: Path, template_path: Path, subs: dict[str, str] | None = None) -> bool:
    """Replace v1/v3 hooks with v4 hooks in .claude/settings.json.

    Identifies v1 hooks by checking if command contains 'framework-path',
    'governance-hook', or 'prawduct-statusline'. Identifies v3 hooks by
    checking for product-hook without python3 prefix. Removes v1 statusLine
    if it references prawduct. Adds banner from template. Preserves
    non-prawduct hooks and other settings keys. Returns True if file was written.
    """
    template_text = template_path.read_text()
    if subs:
        for key, value in subs.items():
            template_text = template_text.replace(key, value)
    template = json.loads(template_text)

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

    # Collect v4 hook commands from template
    v4_commands: set[str] = set()
    template_hooks = template.get("hooks", {})
    for entries in template_hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    v4_commands.add(hook["command"])

    def is_old_prawduct_hook(entry: dict) -> bool:
        """Check if this is a v1 or v3 (pre-python3) prawduct hook."""
        if is_v1_hook_entry(entry):
            return True
        # v3 bash hooks: product-hook without python3 prefix
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if "product-hook" in cmd and not cmd.startswith("python3 "):
                return True
        return False

    # Build merged hooks: start with template hooks, add non-prawduct user hooks
    merged_hooks: dict = dict(template_hooks)
    for event, entries in existing.get("hooks", {}).items():
        if event not in merged_hooks:
            user_entries = [e for e in entries if not is_old_prawduct_hook(e)]
            if user_entries:
                merged_hooks[event] = user_entries
            continue

        user_entries = []
        for entry in entries:
            if is_old_prawduct_hook(entry):
                continue
            is_v4 = any(
                hook.get("command") in v4_commands
                for hook in entry.get("hooks", [])
                if hook.get("type") == "command"
            )
            if not is_v4:
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

    # Always update banner from template (framework-managed)
    if "companyAnnouncements" in template:
        merged["companyAnnouncements"] = template["companyAnnouncements"]

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
    """Remove v1-specific entries, add v4 entries. Returns True if modified."""
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

    # Add missing v4 entries
    existing_set = set(l.strip() for l in filtered)
    missing = [e for e in V4_GITIGNORE_ENTRIES if e not in existing_set]

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


def generate_sync_manifest(target: Path, product_name: str) -> bool:
    """Generate sync manifest for the product repo. Returns True if created."""
    manifest_path = target / ".prawduct" / "sync-manifest.json"
    if manifest_path.is_file():
        return False

    claude_path = target / "CLAUDE.md"
    if claude_path.is_file():
        claude_hash = compute_block_hash(claude_path.read_text())
        if claude_hash is None:
            claude_hash = compute_hash(claude_path)
    else:
        claude_hash = None

    file_hashes = {
        "CLAUDE.md": claude_hash,
        ".prawduct/critic-review.md": compute_hash(
            target / ".prawduct" / "critic-review.md"
        ),
        "tools/product-hook": compute_hash(target / "tools" / "product-hook"),
        ".claude/settings.json": None,
    }
    manifest = create_manifest(target, FRAMEWORK_DIR, product_name, file_hashes)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return True


def add_block_markers(target: Path, subs: dict[str, str]) -> bool:
    """Add PRAWDUCT block markers to CLAUDE.md if missing.

    - If already has markers → no-op.
    - Otherwise → wrap the body (everything from the first ## heading onward)
      in markers.

    For V1 repos, CLAUDE.md was already overwritten by write_template_overwrite
    with the current marked template, so this is a no-op. For V3/V4 repos
    without markers, the existing content is preserved and wrapped.

    Returns True if the file was modified.
    """
    claude_path = target / "CLAUDE.md"
    if not claude_path.is_file():
        return False

    content = claude_path.read_text()

    # Already has markers — no-op
    if BLOCK_BEGIN in content and BLOCK_END in content:
        return False

    # Wrap everything from the first ## heading onward in markers
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            body_start = i
            break
    else:
        # No section headers found — wrap everything after first non-empty lines
        body_start = min(2, len(lines))

    before_lines = lines[:body_start]
    body_lines = lines[body_start:]

    # Build new content
    before = "\n".join(before_lines)
    if before and not before.endswith("\n"):
        before += "\n"
    before += "\n"

    body = "\n".join(body_lines)
    if body and not body.endswith("\n"):
        body += "\n"

    new_content = before + BLOCK_BEGIN + "\n\n" + body + "\n" + BLOCK_END + "\n"
    claude_path.write_text(new_content)
    return True


def upgrade_manifest_strategy(target: Path) -> bool:
    """Upgrade manifest CLAUDE.md strategy from 'template' to 'block_template'.

    Recomputes the hash as a block hash. Returns True if modified.
    """
    manifest_path = target / ".prawduct" / "sync-manifest.json"
    if not manifest_path.is_file():
        return False

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return False

    files = manifest.get("files", {})
    claude_config = files.get("CLAUDE.md")
    if claude_config is None:
        return False

    if claude_config.get("strategy") == "block_template":
        return False  # Already upgraded

    # Change strategy
    claude_config["strategy"] = "block_template"

    # Recompute hash as block hash
    claude_path = target / "CLAUDE.md"
    if claude_path.is_file():
        content = claude_path.read_text()
        claude_config["generated_hash"] = compute_block_hash(content)

    manifest["files"]["CLAUDE.md"] = claude_config
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return True


def run_migrate(target_dir: str, product_name: str | None = None) -> dict:
    """Migrate a product repo to v4. Returns a summary of actions taken."""
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

    # === V1-specific steps (v1 and partial) ===
    if version in ("v1", "partial"):
        # 1. Overwrite CLAUDE.md with current template
        if write_template_overwrite(
            TEMPLATES_DIR / "product-claude.md", target / "CLAUDE.md", subs
        ):
            actions.append("Overwrote CLAUDE.md with current template")

        # 2. Delete v1 marker files
        deleted = delete_v1_files(target)
        for f in deleted:
            actions.append(f"Deleted {f}")

        # 3. Archive v1 directories
        archived = archive_v1_dirs(target)
        for d in archived:
            actions.append(f"Archived {d} → .prawduct/archive/")

        # 4. Clean v1 session files
        cleaned = clean_v1_session_files(target)
        for f in cleaned:
            actions.append(f"Deleted session file {f}")

    # === Steps for all non-v4 repos (v1, v3, partial) ===

    # Replace hooks in settings.json (handles v1, v3 bash, and adds banner)
    if replace_settings(
        target / ".claude" / "settings.json",
        TEMPLATES_DIR / "product-settings.json",
        subs,
    ):
        actions.append("Updated .claude/settings.json (hooks + banner)")

    # Copy product-hook (Python version)
    if copy_hook(
        FRAMEWORK_DIR / "tools" / "product-hook",
        target / "tools" / "product-hook",
    ):
        actions.append("Installed tools/product-hook (Python)")

    # Create critic-review.md if missing
    if write_template_if_missing(
        TEMPLATES_DIR / "critic-review.md",
        target / ".prawduct" / "critic-review.md",
        subs,
    ):
        actions.append("Created .prawduct/critic-review.md")

    # Create learnings.md if missing
    learnings = target / ".prawduct" / "learnings.md"
    if not learnings.is_file():
        learnings.parent.mkdir(parents=True, exist_ok=True)
        learnings.write_text(
            "# Learnings\n\nAccumulated wisdom from building this product.\n"
        )
        actions.append("Created .prawduct/learnings.md")

    # Generate sync manifest
    if generate_sync_manifest(target, product_name):
        actions.append("Created .prawduct/sync-manifest.json")

    # Clean gitignore
    if clean_gitignore(target):
        actions.append("Updated .gitignore")

    # Add block markers to CLAUDE.md if missing
    if add_block_markers(target, subs):
        actions.append("Added block markers to CLAUDE.md")

    # Upgrade manifest strategy from template to block_template
    if upgrade_manifest_strategy(target):
        actions.append("Upgraded CLAUDE.md sync strategy to block_template")

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
        description="Migrate a Prawduct product repo to the latest version.",
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
            log("  (no changes — already up to date)")
        log("")
        if result["version_after"] == "v4":
            log("Migration complete. Product repo is now self-contained with sync support.")
        else:
            log(f"Note: version detected as '{result['version_after']}' — review manually.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
