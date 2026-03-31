"""
Sync command for prawduct product repos.

Syncs product repo files with framework template updates, handling
manifests, renames, version migrations, and place-once files.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    BLOCK_BEGIN,
    BLOCK_END,
    FILE_RENAMES,
    MANAGED_FILES,
    PRAWDUCT_VERSION,
    _resolve_framework_dir,
    _try_pull_framework,
    compute_block_hash,
    compute_hash,
    extract_block,
    load_json,
    merge_settings,
    render_template,
    update_gitignore,
)
from .migrate_cmd import (
    migrate_backlog,
    migrate_change_log,
    migrate_project_state_v5,
    split_learnings_v5,
)


def _bootstrap_manifest(product: Path, fw_dir: Path) -> dict:
    """Create initial sync manifest for a prawduct repo that doesn't have one.

    Computes hashes of existing managed files so sync can track future changes.
    Files that don't exist get None (triggers creation on first sync).
    For files at old rename paths, uses the old path's content for hash computation
    so the rename + sync flow works correctly.
    """
    from .core import create_manifest

    # Infer product name from project-state.yaml or directory name
    product_name = product.name
    state_path = product / ".prawduct" / "project-state.yaml"
    if state_path.is_file():
        for line in state_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("product_name:"):
                val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if val:
                    product_name = val
                break

    file_hashes: dict[str, str | None] = {}
    for rel_path, config in MANAGED_FILES.items():
        strategy = config.get("strategy", "template")
        file_path = product / rel_path

        # If file doesn't exist at new path, check old rename paths
        if not file_path.is_file():
            for old_rel, new_rel in FILE_RENAMES.items():
                if new_rel == rel_path and (product / old_rel).is_file():
                    file_path = product / old_rel
                    break

        if strategy == "block_template":
            if file_path.is_file():
                file_hashes[rel_path] = compute_block_hash(file_path.read_text())
            else:
                file_hashes[rel_path] = None
        elif strategy == "merge_settings":
            file_hashes[rel_path] = None  # merge_settings doesn't use hash
        else:
            file_hashes[rel_path] = compute_hash(file_path)

    return create_manifest(product, fw_dir, product_name, file_hashes)


def apply_renames(
    product: Path,
    manifest: dict,
    actions: list[str],
) -> None:
    """Apply file renames from FILE_RENAMES. Mutates manifest['files'] in place."""
    files = manifest.get("files", {})

    for old_rel, new_rel in FILE_RENAMES.items():
        old_path = product / old_rel
        new_path = product / new_rel

        old_in_manifest = old_rel in files

        if old_path.is_file() and new_path.is_file():
            # Both exist — delete old (it's a leftover)
            old_path.unlink()
            if old_in_manifest:
                del files[old_rel]
            # Ensure new path uses canonical config if available
            if new_rel in MANAGED_FILES and new_rel in files:
                saved_hash = files[new_rel].get("generated_hash")
                files[new_rel] = dict(MANAGED_FILES[new_rel])
                files[new_rel]["generated_hash"] = saved_hash
            actions.append(f"Removed leftover: {old_rel}")
        elif old_path.is_file():
            # Normal rename: move file, transfer manifest entry
            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)
            if old_in_manifest:
                old_entry = files.pop(old_rel)
                # Use canonical config if available (fixes stale template paths),
                # otherwise transfer the old entry as-is
                if new_rel in MANAGED_FILES:
                    files[new_rel] = dict(MANAGED_FILES[new_rel])
                    files[new_rel]["generated_hash"] = compute_hash(new_path)
                else:
                    files[new_rel] = old_entry
            actions.append(f"Moved: {old_rel} → {new_rel}")
        elif old_in_manifest and not old_path.is_file():
            # Stale manifest entry (file already deleted/moved)
            del files[old_rel]
            actions.append(f"Cleaned stale manifest entry: {old_rel}")
        # else: neither exists — nothing to do

    # Clean up empty parent directories of old paths
    seen_parents: set[Path] = set()
    for old_rel in FILE_RENAMES:
        parent = product / Path(old_rel).parent
        if parent not in seen_parents and parent.is_dir() and parent != product:
            seen_parents.add(parent)
            try:
                parent.rmdir()  # Only succeeds if empty
                actions.append(f"Removed empty directory: {Path(old_rel).parent}")
            except OSError:
                pass  # Not empty — that's fine


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
        manifest = load_json(manifest_path)
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

    bootstrapped = False

    if not manifest_path.is_file():
        if not (product / ".prawduct").is_dir():
            return {
                "product_dir": str(product),
                "synced": False,
                "reason": "not a prawduct repo",
                "actions": [],
                "notes": [],
            }
        # Bootstrap: create manifest for prawduct repo that doesn't have one
        fw_dir = _resolve_framework_dir({}, framework_dir, product)
        if fw_dir is None:
            return {
                "product_dir": str(product),
                "synced": False,
                "reason": "framework not found",
                "actions": [],
                "notes": [],
            }
        manifest = _bootstrap_manifest(product, fw_dir)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        bootstrapped = True
    else:
        try:
            manifest = load_json(manifest_path)
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
    previous_version = manifest.get("framework_version", "")
    subs = {"{{PRODUCT_NAME}}": product_name, "{{PRAWDUCT_VERSION}}": PRAWDUCT_VERSION}
    actions: list[str] = []
    notes: list[str] = list(pull_notes)

    if bootstrapped:
        actions.append("Bootstrapped sync manifest (first framework sync for this repo)")

    # V4→V5 migration (if needed)
    v5_actions = migrate_v4_to_v5(product)
    actions.extend(v5_actions)
    if v5_actions:
        # Re-read manifest since migration updated it
        manifest = load_json(manifest_path)

    # Migrate change_log from project-state.yaml to change-log.md
    actions.extend(migrate_change_log(product))

    # Migrate remaining_work/future_work/backlog from project-state.yaml to backlog.md
    actions.extend(migrate_backlog(product))

    files = manifest.get("files", {})

    # Renames: move files from old paths to new paths (e.g., commands → skills)
    if FILE_RENAMES:
        apply_renames(product, manifest, actions)

    # Backfill: add any managed files missing from the manifest (added after init)
    # Also repair stale config (e.g., old template paths from renamed entries)
    for rel_path, config in MANAGED_FILES.items():
        if rel_path not in files:
            files[rel_path] = dict(config)
            files[rel_path]["generated_hash"] = None  # Forces creation on first sync
            desc = config.get("description", "")
            if desc:
                actions.append(f"New: {rel_path} — {desc}")
            else:
                actions.append(f"New: {rel_path}")
        else:
            # Repair stale config: if template/source/strategy differs from
            # canonical MANAGED_FILES, update it (preserving generated_hash)
            existing = files[rel_path]
            canonical = config
            stale = False
            for key in ("template", "source", "strategy"):
                if key in canonical and existing.get(key) != canonical.get(key):
                    stale = True
                    break
            if stale:
                saved_hash = existing.get("generated_hash")
                files[rel_path] = dict(canonical)
                files[rel_path]["generated_hash"] = saved_hash
                actions.append(f"Repaired manifest config for {rel_path}")

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
                        notes.append(f"Updated {rel_path} — re-read to pick up changes")
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
                notes.append(f"Updated {rel_path} — re-read to pick up changes")

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
                notes.append(f"Created {rel_path} — re-read to pick up changes")
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
                    notes.append(f"Updated {rel_path} — re-read to pick up changes")
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
            notes.append(f"Updated {rel_path} — re-read to pick up changes")

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
                notes.append(f"Updated {rel_path} — re-read to pick up changes")

    # Place-once files: create if missing, never tracked for ongoing sync
    place_once = {
        ".prawduct/artifacts/project-preferences.md": "templates/project-preferences.md",
        ".prawduct/artifacts/boundary-patterns.md": "templates/boundary-patterns.md",
        ".prawduct/change-log.md": "templates/change-log.md",
        ".prawduct/backlog.md": "templates/backlog.md",
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

    # Ensure gitignore stays current
    gi_result = update_gitignore(product)
    if gi_result["modified"]:
        actions.append("Updated .gitignore")
    for path in gi_result["unignored"]:
        notes.append(
            f"Removed {path} from .gitignore — it should be committed. "
            f"Run: git add {path}"
        )

    # Update manifest
    if actions:
        manifest["files"] = updated_files
        manifest["framework_version"] = PRAWDUCT_VERSION
        manifest["last_sync"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Include version change info so callers can surface upgrade notices
    version_info: dict[str, str] = {"new_version": PRAWDUCT_VERSION}
    if previous_version and previous_version != PRAWDUCT_VERSION:
        version_info["previous_version"] = previous_version

    return {
        "product_dir": str(product),
        "synced": bool(actions),
        "reason": "ok" if actions else "no updates needed",
        "actions": actions,
        "notes": notes,
        "version": version_info,
    }
