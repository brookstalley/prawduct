#!/usr/bin/env python3
"""
prawduct-sync.py — Sync product repos with framework template updates.

Reads .prawduct/sync-manifest.json to determine which files are framework-managed,
compares hashes to detect user edits, and updates files whose templates have changed.

Strategies:
  - template: update if user hasn't edited (hash comparison); skip with note if edited
  - always_update: always overwrite (hooks must stay current)
  - merge_settings: merge hooks + banner from template, preserve user settings

Usage:
  python3 tools/prawduct-sync.py <product_dir> [--framework-dir <dir>]

The framework dir is resolved in order:
  1. --framework-dir CLI argument
  2. PRAWDUCT_FRAMEWORK_DIR environment variable
  3. framework_source from the manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


BLOCK_BEGIN = "<!-- PRAWDUCT:BEGIN -->"
BLOCK_END = "<!-- PRAWDUCT:END -->"


def log(msg: str) -> None:
    """Print status to stderr."""
    print(msg, file=sys.stderr)


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


def compute_block_hash(content: str) -> str | None:
    """SHA-256 of just the block content between markers. None if no markers."""
    block, _, _ = extract_block(content)
    if block is None:
        return None
    return hashlib.sha256(block.encode()).hexdigest()


def compute_hash(path: Path) -> str | None:
    """Compute SHA-256 hex digest of a file's contents. Returns None if file missing."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_template(template_path: Path, subs: dict[str, str]) -> str:
    """Read a template file and apply variable substitutions."""
    content = template_path.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)
    return content


def merge_settings(dst: Path, template_path: Path, subs: dict[str, str] | None = None) -> bool:
    """Create or merge .claude/settings.json.

    Merges hooks and companyAnnouncements from template into existing settings.
    Preserves user hooks and other settings keys. Applies subs to template before
    parsing (for banner {{PRODUCT_NAME}} substitution).

    Returns True if file was written.
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
        log(f"  ! Could not parse {dst.name} — skipping merge")
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

    # Preserve other settings keys, but always update banner from template
    merged = dict(existing)
    merged["hooks"] = merged_hooks

    # Always update companyAnnouncements from template (framework-managed)
    if "companyAnnouncements" in template:
        merged["companyAnnouncements"] = template["companyAnnouncements"]

    if json.dumps(merged, sort_keys=True) == json.dumps(existing, sort_keys=True):
        return False

    dst.write_text(json.dumps(merged, indent=2) + "\n")
    return True


def create_manifest(
    product_dir: Path,
    framework_dir: Path,
    product_name: str,
    file_hashes: dict[str, str | None],
) -> dict:
    """Build a sync manifest from the given file hashes.

    file_hashes maps relative file paths to their SHA-256 hex digests (or None).
    """
    files: dict[str, dict] = {}

    # Define the managed file configs
    file_configs = {
        "CLAUDE.md": {
            "template": "templates/product-claude.md",
            "strategy": "block_template",
        },
        ".prawduct/critic-review.md": {
            "template": "templates/critic-review.md",
            "strategy": "template",
        },
        ".prawduct/pr-review.md": {
            "template": "templates/pr-review.md",
            "strategy": "template",
        },
        ".claude/commands/pr.md": {
            "template": "templates/commands-pr.md",
            "strategy": "template",
        },
        "tools/product-hook": {
            "source": "tools/product-hook",
            "strategy": "always_update",
        },
        ".claude/settings.json": {
            "template": "templates/product-settings.json",
            "strategy": "merge_settings",
        },
    }

    for rel_path, config in file_configs.items():
        entry = dict(config)
        entry["generated_hash"] = file_hashes.get(rel_path)
        files[rel_path] = entry

    return {
        "format_version": 2,
        "framework_source": str(framework_dir),
        "product_name": product_name,
        "auto_pull": True,
        "last_sync": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": files,
    }


def _resolve_framework_dir(
    manifest: dict, cli_framework_dir: str | None, product_dir: Path | None = None
) -> Path | None:
    """Resolve the framework directory from CLI arg, env var, manifest, or sibling.

    Resolution order:
      1. --framework-dir CLI argument (explicit override; fail if invalid)
      2. PRAWDUCT_FRAMEWORK_DIR env var (explicit override; fail if invalid)
      3. framework_source from manifest (recorded at init; fall through if stale)
      4. Sibling ../prawduct relative to product dir (convention-based discovery)
    """
    # 1. CLI argument
    if cli_framework_dir:
        p = Path(cli_framework_dir).resolve()
        if p.is_dir():
            return p
        return None

    # 2. Environment variable
    env_dir = os.environ.get("PRAWDUCT_FRAMEWORK_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
        if p.is_dir():
            return p
        return None

    # 3. Manifest value
    source = manifest.get("framework_source", "")
    if source:
        p = Path(source).resolve()
        if p.is_dir():
            return p

    # 4. Sibling ../prawduct relative to product dir
    if product_dir:
        sibling = (product_dir.parent / "prawduct").resolve()
        if sibling.is_dir():
            return sibling

    return None


def _try_pull_framework(fw_dir: Path, auto_pull: bool) -> list[str]:
    """Best-effort git pull/fetch of the framework repo before syncing.

    When auto_pull is True: runs ``git pull --ff-only`` (safe fast-forward).
    When auto_pull is False: runs ``git fetch`` and reports if behind upstream.

    Returns a list of human-readable notes (may be empty). Never raises.
    """
    notes: list[str] = []
    try:
        # Verify fw_dir is inside a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=str(fw_dir),
            timeout=30,
        )
        if result.returncode != 0:
            return notes  # Not a git repo — silently skip

        if auto_pull:
            # Check for dirty working tree
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=str(fw_dir),
                timeout=30,
            )
            if status.returncode == 0 and status.stdout.strip():
                notes.append("Framework has uncommitted changes — skipping pull")
                return notes

            # Fast-forward pull
            pull = subprocess.run(
                ["git", "pull", "--ff-only"],
                capture_output=True,
                text=True,
                cwd=str(fw_dir),
                timeout=30,
            )
            if pull.returncode == 0:
                if "Already up to date" not in pull.stdout:
                    notes.append("Framework updated via git pull")
            else:
                stderr = pull.stderr.strip()
                if "Not possible to fast-forward" in stderr or "fatal" in stderr:
                    notes.append("Framework pull failed (not fast-forwardable) — run git pull manually")
                else:
                    notes.append("Framework pull failed — run git pull manually")
        else:
            # Advisory mode: fetch + check if behind
            fetch = subprocess.run(
                ["git", "fetch", "--quiet"],
                capture_output=True,
                text=True,
                cwd=str(fw_dir),
                timeout=30,
            )
            if fetch.returncode != 0:
                return notes  # Fetch failed — silently skip

            behind = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..@{upstream}"],
                capture_output=True,
                text=True,
                cwd=str(fw_dir),
                timeout=30,
            )
            if behind.returncode == 0:
                count = behind.stdout.strip()
                if count and int(count) > 0:
                    notes.append(f"Framework is {count} commit(s) behind upstream — consider running git pull")

    except FileNotFoundError:
        pass  # git not on PATH
    except subprocess.TimeoutExpired:
        notes.append("Framework git operation timed out")
    except Exception:  # prawduct:ok-broad-except — sync helper must never block session start
        pass

    return notes


def split_learnings_v5(product_dir: Path) -> list[str]:
    """Create learnings-detail.md as reference backup of learnings.md.

    Part of v4→v5 migration. If learnings.md exists with meaningful content
    and learnings-detail.md doesn't exist yet, copies the content.
    Idempotent: skips if detail file already exists.

    Returns list of actions taken.
    """
    actions: list[str] = []
    learnings = product_dir / ".prawduct" / "learnings.md"
    detail = product_dir / ".prawduct" / "learnings-detail.md"

    if not learnings.is_file():
        return actions
    if detail.is_file():
        return actions  # Already split

    content = learnings.read_text()
    # Only split if there's meaningful content beyond the header
    lines = [l for l in content.strip().splitlines()
             if l.strip() and not l.startswith("#")]
    if not lines:
        return actions

    detail.write_text(content)
    actions.append("Created .prawduct/learnings-detail.md (reference backup)")
    return actions


def migrate_project_state_v5(product_dir: Path) -> list[str]:
    """Add v5 sections to project-state.yaml, remove v4-only fields.

    Adds work_in_progress and health_check sections if missing.
    Removes current_phase if present. Idempotent.

    Returns list of actions taken.
    """
    actions: list[str] = []
    state_path = product_dir / ".prawduct" / "project-state.yaml"

    if not state_path.is_file():
        return actions

    content = state_path.read_text()
    original = content

    # Remove current_phase field (v4 artifact) — top-level key, single line
    if "\ncurrent_phase:" in content or content.startswith("current_phase:"):
        lines = content.split("\n")
        new_lines = [l for l in lines if not l.startswith("current_phase:")]
        content = "\n".join(new_lines)

    # Add work_in_progress section if missing
    if "work_in_progress:" not in content:
        content = content.rstrip("\n") + "\n\n" + (
            "# =============================================================================\n"
            "# WORK IN PROGRESS\n"
            "# =============================================================================\n"
            "# Tracks what's being done now and at what governance level.\n"
            "\n"
            "work_in_progress:\n"
            "  description: null\n"
            "  size: null\n"
            "  type: null\n"
        )

    # Add health_check section if missing
    if "health_check:" not in content:
        content = content.rstrip("\n") + "\n\n" + (
            "# =============================================================================\n"
            "# HEALTH CHECK\n"
            "# =============================================================================\n"
            "# Tracks periodic health check state.\n"
            "\n"
            "health_check:\n"
            "  last_full_check: null\n"
            "  last_check_findings: null\n"
        )

    if content != original:
        state_path.write_text(content)
        actions.append("Updated .prawduct/project-state.yaml for v5")

    return actions


def migrate_v4_to_v5(product_dir: Path) -> list[str]:
    """Migrate a v4 product to v5 structure. Called from run_sync().

    Checks manifest format_version; skips if already v5.
    Runs learnings split, project-state update, and version bump.
    Idempotent.

    Returns list of actions taken.
    """
    actions: list[str] = []
    manifest_path = product_dir / ".prawduct" / "sync-manifest.json"

    if not manifest_path.is_file():
        return actions

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return actions

    if manifest.get("format_version", 1) >= 2:
        return actions  # Already v5

    # 1. Split learnings
    actions.extend(split_learnings_v5(product_dir))

    # 2. Update project-state.yaml
    actions.extend(migrate_project_state_v5(product_dir))

    # 3. Bump manifest version
    manifest["format_version"] = 2
    manifest["last_sync"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    actions.append("Bumped manifest to format_version 2 (v5)")

    return actions


def run_sync(product_dir: str, framework_dir: str | None = None, *, no_pull: bool = False, force: bool = False) -> dict:
    """Run the sync algorithm on a product directory.

    Returns a summary dict with actions taken, notes, and any warnings.
    """
    product = Path(product_dir).resolve()
    manifest_path = product / ".prawduct" / "sync-manifest.json"

    if not manifest_path.is_file():
        return {
            "product_dir": str(product),
            "synced": False,
            "reason": "no manifest",
            "actions": [],
            "notes": [],
        }

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return {
            "product_dir": str(product),
            "synced": False,
            "reason": "invalid manifest JSON",
            "actions": [],
            "notes": [],
        }

    fw_dir = _resolve_framework_dir(manifest, framework_dir, product)
    if fw_dir is None:
        return {
            "product_dir": str(product),
            "synced": False,
            "reason": "framework not found",
            "actions": [],
            "notes": [],
        }

    # Best-effort framework pull before syncing templates
    if not no_pull:
        auto_pull = manifest.get("auto_pull", True)
        pull_notes = _try_pull_framework(fw_dir, auto_pull)
    else:
        pull_notes = []

    product_name = manifest.get("product_name", product.name)
    subs = {"{{PRODUCT_NAME}}": product_name}
    actions: list[str] = []
    notes: list[str] = list(pull_notes)

    # V4→V5 migration (if needed)
    v5_actions = migrate_v4_to_v5(product)
    actions.extend(v5_actions)
    if v5_actions:
        # Re-read manifest since migration updated it
        manifest = json.loads(manifest_path.read_text())

    files = manifest.get("files", {})
    updated_files = dict(files)

    for rel_path, config in files.items():
        strategy = config.get("strategy", "template")
        dst = product / rel_path

        if strategy == "template":
            template_rel = config.get("template", "")
            template_path = fw_dir / template_rel
            if not template_path.is_file():
                notes.append(f"Template missing: {template_rel}")
                continue

            # Render current template
            rendered = render_template(template_path, subs)
            rendered_hash = hashlib.sha256(rendered.encode()).hexdigest()

            # Check if template has changed since last sync
            stored_hash = config.get("generated_hash")
            if stored_hash == rendered_hash:
                continue  # Template hasn't changed

            # Template changed — check if user edited the file
            current_hash = compute_hash(dst)
            if current_hash is not None and current_hash != stored_hash:
                if force:
                    dst.write_text(rendered)
                    new_hash = compute_hash(dst)
                    updated_files[rel_path] = dict(config)
                    updated_files[rel_path]["generated_hash"] = new_hash
                    actions.append(f"Force-updated {rel_path} (local edits overwritten)")
                    if rel_path in ("CLAUDE.md",):
                        notes.append(f"Updated {rel_path} — restart session for full effect")
                else:
                    notes.append(
                        f"Skipped {rel_path} — new template available but file has local edits (re-run with --force to overwrite)"
                    )
                continue

            # Safe to update
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(rendered)
            new_hash = compute_hash(dst)
            updated_files[rel_path] = dict(config)
            updated_files[rel_path]["generated_hash"] = new_hash
            actions.append(f"Updated {rel_path}")
            # CLAUDE.md and settings.json are pre-loaded — flag for restart
            if rel_path in ("CLAUDE.md",):
                notes.append(f"Updated {rel_path} — restart session for full effect")

        elif strategy == "block_template":
            template_rel = config.get("template", "")
            template_path = fw_dir / template_rel
            if not template_path.is_file():
                notes.append(f"Template missing: {template_rel}")
                continue

            # Render current template and extract block
            rendered = render_template(template_path, subs)
            rendered_block, _, _ = extract_block(rendered)
            if rendered_block is None:
                notes.append(f"Template {template_rel} has no markers — skipping block sync")
                continue

            rendered_block_hash = hashlib.sha256(rendered_block.encode()).hexdigest()

            # Check if template block has changed since last sync
            stored_hash = config.get("generated_hash")
            if stored_hash == rendered_block_hash:
                # Template hasn't changed — but check if product drifted
                if dst.is_file():
                    product_content = dst.read_text()
                    product_block, _, _ = extract_block(product_content)
                    if product_block is not None:
                        product_block_hash = hashlib.sha256(product_block.encode()).hexdigest()
                        if product_block_hash != stored_hash:
                            # Product drifted from last sync — re-apply
                            before_idx = product_content.find(BLOCK_BEGIN)
                            end_idx = product_content.find(BLOCK_END)
                            before = product_content[:before_idx]
                            after = product_content[end_idx + len(BLOCK_END):]
                            new_content = before + rendered_block + after
                            dst.write_text(new_content)
                            actions.append(f"Restored {rel_path}")
                            notes.append(f"Restored {rel_path} — block had drifted from synced version")
                continue

            # Template changed — check product file
            if not dst.is_file():
                # Product file missing — create from full template
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(rendered)
                updated_files[rel_path] = dict(config)
                updated_files[rel_path]["generated_hash"] = rendered_block_hash
                actions.append(f"Created {rel_path}")
                notes.append(f"Created {rel_path} — restart session for full effect")
                continue

            product_content = dst.read_text()
            product_block, before, after = extract_block(product_content)

            if product_block is None:
                notes.append(
                    f"Skipped {rel_path} — no markers (add markers to enable sync)"
                )
                continue

            # Check if user edited the block
            product_block_hash = hashlib.sha256(product_block.encode()).hexdigest()
            if product_block_hash != stored_hash:
                if force:
                    new_content = before + rendered_block + after
                    dst.write_text(new_content)
                    updated_files[rel_path] = dict(config)
                    updated_files[rel_path]["generated_hash"] = rendered_block_hash
                    actions.append(f"Force-updated {rel_path} block (local edits overwritten)")
                    notes.append(f"Updated {rel_path} — restart session for full effect")
                else:
                    notes.append(
                        f"Skipped {rel_path} — new template available but block has local edits (re-run with --force to overwrite)"
                    )
                continue

            # Safe to replace block in-place, preserving before/after
            new_content = before + rendered_block + after
            dst.write_text(new_content)
            updated_files[rel_path] = dict(config)
            updated_files[rel_path]["generated_hash"] = rendered_block_hash
            actions.append(f"Updated {rel_path}")
            notes.append(f"Updated {rel_path} — restart session for full effect")

        elif strategy == "always_update":
            source_rel = config.get("source", "")
            source_path = fw_dir / source_rel
            if not source_path.is_file():
                notes.append(f"Source missing: {source_rel}")
                continue

            source_bytes = source_path.read_bytes()
            if dst.is_file() and dst.read_bytes() == source_bytes:
                continue  # Already up to date

            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(source_bytes)
            # Make executable
            import stat
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            new_hash = compute_hash(dst)
            updated_files[rel_path] = dict(config)
            updated_files[rel_path]["generated_hash"] = new_hash
            actions.append(f"Updated {rel_path}")

        elif strategy == "merge_settings":
            template_rel = config.get("template", "")
            template_path = fw_dir / template_rel
            if not template_path.is_file():
                notes.append(f"Template missing: {template_rel}")
                continue

            if merge_settings(dst, template_path, subs):
                actions.append(f"Merged {rel_path}")
                notes.append(f"Updated {rel_path} — restart session for full effect")

    # Place-once files: create if missing, never tracked for ongoing sync
    place_once = {
        ".prawduct/artifacts/project-preferences.md": "templates/project-preferences.md",
        ".prawduct/artifacts/boundary-patterns.md": "templates/boundary-patterns.md",
    }
    for rel_path, template_rel in place_once.items():
        dst = product / rel_path
        if dst.is_file():
            continue
        template_path = fw_dir / template_rel
        if not template_path.is_file():
            continue
        rendered = render_template(template_path, subs)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(rendered)
        actions.append(f"Created {rel_path}")

    # Place-once binary files: copy if missing (no template rendering)
    place_once_copy = {
        "tests/conftest.py": "templates/conftest.py",
    }
    for rel_path, template_rel in place_once_copy.items():
        dst = product / rel_path
        if dst.is_file():
            continue
        template_path = fw_dir / template_rel
        if not template_path.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_path, dst)
        actions.append(f"Created {rel_path}")

    # Update manifest
    if actions:
        manifest["files"] = updated_files
        manifest["last_sync"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return {
        "product_dir": str(product),
        "synced": bool(actions),
        "reason": "ok" if actions else "no updates needed",
        "actions": actions,
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync a Prawduct product repo with framework template updates.",
    )
    parser.add_argument(
        "product_dir",
        help="Product repo directory",
    )
    parser.add_argument(
        "--framework-dir",
        default=None,
        help="Framework directory (overrides manifest and env var)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="JSON output only",
    )
    parser.add_argument(
        "--no-pull",
        action="store_true",
        dest="no_pull",
        help="Skip git pull/fetch of the framework repo",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite locally-edited files with new template versions",
    )
    args = parser.parse_args()

    result = run_sync(args.product_dir, args.framework_dir, no_pull=args.no_pull, force=args.force)

    if args.json_mode:
        print(json.dumps(result, indent=2))
    else:
        if not result["synced"]:
            if result["reason"] not in ("no manifest", "framework not found", "no updates needed"):
                log(f"Sync skipped: {result['reason']}")
        else:
            log(f"Synced {result['product_dir']}")
            for action in result["actions"]:
                log(f"  + {action}")
        for note in result.get("notes", []):
            log(f"  * {note}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
