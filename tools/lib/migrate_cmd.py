"""
Migration operations for prawduct product repos.

Handles v1→v3→v4→v5 migrations, changelog/backlog extraction,
and sync manifest generation.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .core import (
    BLOCK_BEGIN,
    BLOCK_END,
    FRAMEWORK_DIR,
    PRAWDUCT_VERSION,
    TEMPLATES_DIR,
    V1_GITIGNORE_ENTRIES,
    V1_SESSION_FILES,
    V4_GITIGNORE_ENTRIES,
    compute_block_hash,
    compute_hash,
    copy_hook,
    create_manifest,
    detect_version,
    infer_product_name,
    load_json,
    merge_settings,
    render_template,
    write_template,
)


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


def add_block_markers(target: Path, subs: dict[str, str]) -> bool:
    """Add PRAWDUCT block markers to CLAUDE.md if missing.

    - If already has markers → no-op.
    - Otherwise → wrap the body (everything from the first ## heading onward)
      in markers.

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
        manifest = load_json(manifest_path)
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


def strip_test_tracking(product_dir: Path) -> list[str]:
    """Remove build_state.test_tracking from project-state.yaml.

    Test count is derived data — computed dynamically by the hook, never tracked
    as a static artifact. Idempotent: no-op if test_tracking is absent.

    Returns list of actions taken.
    """
    actions: list[str] = []
    state_path = product_dir / ".prawduct" / "project-state.yaml"
    if not state_path.is_file():
        return actions

    content = state_path.read_text()
    if "test_tracking:" not in content:
        return actions

    lines = content.split("\n")
    tt_start = None
    tt_end = None

    for i, line in enumerate(lines):
        if tt_start is None:
            stripped = line.strip()
            if stripped.startswith("test_tracking:") and line.startswith("  "):
                tt_start = i
        elif tt_start is not None:
            # End when we hit a non-blank/non-comment line at indent <= 2
            if line.strip() and not line.strip().startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent <= 2:
                    tt_end = i
                    break

    if tt_start is None:
        return actions
    if tt_end is None:
        tt_end = len(lines)

    new_lines = lines[:tt_start] + lines[tt_end:]
    cleaned = "\n".join(new_lines)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    state_path.write_text(cleaned)
    actions.append("Removed build_state.test_tracking from project-state.yaml")
    return actions


def migrate_project_state_v5(product_dir: Path) -> list[str]:
    """Add v5 sections to project-state.yaml, remove v4-only fields.

    Adds work_in_progress (backward compat for existing repos) and
    health_check sections if missing. Removes current_phase if present.
    Idempotent.

    Note: New repos (v6+) no longer include work_in_progress or build_plan
    in the template — build plan Status is the source of truth. This
    migration keeps adding work_in_progress so existing repos that read
    from it continue to work during the transition.

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
            "# WORK IN PROGRESS (branch-scoped)\n"
            "# =============================================================================\n"
            "# Each branch gets its own entry. See project-state.yaml template for format.\n"
            "\n"
            "work_in_progress: {}\n"
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


def migrate_change_log(product_dir: Path) -> list[str]:
    """Move change_log from project-state.yaml to .prawduct/change-log.md.

    Parses YAML change_log entries, converts to markdown sections, writes
    to change-log.md (appending if it exists), and removes the change_log
    section from project-state.yaml. Idempotent: skips if no change_log
    section exists in project-state.yaml.

    Returns list of actions taken.
    """
    actions: list[str] = []
    state_path = product_dir / ".prawduct" / "project-state.yaml"
    if not state_path.is_file():
        return actions

    content = state_path.read_text()

    # Check if change_log: exists with actual entries (not just [] or {})
    if "\nchange_log:" not in content and not content.startswith("change_log:"):
        return actions

    # Find the change_log section boundaries
    lines = content.split("\n")
    cl_start = None
    cl_end = None
    for i, line in enumerate(lines):
        if line.startswith("change_log:") or line.strip() == "change_log:":
            cl_start = i
        elif cl_start is not None and not line.startswith(" ") and not line.startswith("#") and line.strip() and not line.startswith("change_log"):
            # Hit next top-level key
            cl_end = i
            break
    if cl_start is None:
        return actions

    if cl_end is None:
        cl_end = len(lines)

    # Also capture any comment lines immediately before change_log:
    comment_start = cl_start
    while comment_start > 0 and (lines[comment_start - 1].startswith("#") or lines[comment_start - 1].strip() == ""):
        if lines[comment_start - 1].startswith("# ===") or "CHANGE LOG" in lines[comment_start - 1]:
            comment_start -= 1
        elif lines[comment_start - 1].strip() == "":
            comment_start -= 1
        elif lines[comment_start - 1].startswith("#"):
            comment_start -= 1
        else:
            break

    cl_section = lines[cl_start:cl_end]

    # Parse entries from the YAML section (lightweight, no PyYAML)
    entries: list[dict[str, str]] = []
    current_entry: dict[str, str] = {}
    current_key: str | None = None

    for line in cl_section:
        stripped = line.strip()
        if stripped.startswith("- what:") or stripped.startswith("- what :"):
            if current_entry:
                entries.append(current_entry)
            current_entry = {}
            current_key = "what"
            val = stripped.split(":", 1)[1].strip().strip("\"'")
            if val:
                current_entry["what"] = val
        elif stripped.startswith("why:") and current_entry is not None:
            current_key = "why"
            val = stripped.split(":", 1)[1].strip().strip("\"'")
            if val:
                current_entry["why"] = val
        elif stripped.startswith("blast_radius:") and current_entry is not None:
            current_key = "blast_radius"
            val = stripped.split(":", 1)[1].strip().strip("\"'")
            if val:
                current_entry["blast_radius"] = val
        elif stripped.startswith("classification:") and current_entry is not None:
            current_key = "classification"
            val = stripped.split(":", 1)[1].strip().strip("\"'")
            if val:
                current_entry["classification"] = val
        elif stripped.startswith("date:") and current_entry is not None:
            current_key = "date"
            val = stripped.split(":", 1)[1].strip().strip("\"'")
            if val:
                current_entry["date"] = val
        elif current_key and current_entry is not None and stripped and not stripped.startswith("#") and not stripped.startswith("- "):
            # Continuation line for multiline YAML value
            prev = current_entry.get(current_key, "")
            continuation = stripped.strip("\"'")
            if prev:
                current_entry[current_key] = prev + " " + continuation
            else:
                current_entry[current_key] = continuation

    if current_entry:
        entries.append(current_entry)

    if not entries:
        # change_log: exists but is empty ([] or no entries) — just remove the section
        new_lines = lines[:comment_start] + lines[cl_end:]
        # Clean up double blank lines
        cleaned = "\n".join(new_lines)
        while "\n\n\n" in cleaned:
            cleaned = cleaned.replace("\n\n\n", "\n\n")
        state_path.write_text(cleaned)
        actions.append("Removed empty change_log section from project-state.yaml")
        return actions

    # Convert entries to markdown
    md_entries: list[str] = []
    for entry in entries:
        date = entry.get("date", "unknown")
        what = entry.get("what", "Untitled change")
        md = f"## {date}: {what}"
        if entry.get("why"):
            md += f"\n\n**Why:** {entry['why']}"
        if entry.get("blast_radius"):
            md += f"\n\n**Blast radius:** {entry['blast_radius']}"
        if entry.get("classification"):
            md += f"\n\n**Classification:** {entry['classification']}"
        md_entries.append(md)

    # Write to change-log.md
    cl_path = product_dir / ".prawduct" / "change-log.md"
    product_name = product_dir.name
    if cl_path.is_file():
        existing = cl_path.read_text()
        # Append migrated entries at the end with a separator
        separator = "\n\n<!-- Migrated from project-state.yaml -->\n\n"
        cl_path.write_text(existing.rstrip("\n") + separator + "\n\n".join(md_entries) + "\n")
    else:
        header = f"# Change Log — {product_name}\n\n<!-- Append new entries at the top. -->\n\n"
        cl_path.write_text(header + "\n\n".join(md_entries) + "\n")

    actions.append(f"Migrated {len(entries)} change_log entries to .prawduct/change-log.md")

    # Remove change_log section from project-state.yaml
    # Replace with a pointer comment
    pointer = (
        "# =============================================================================\n"
        "# CHANGE LOG\n"
        "# =============================================================================\n"
        "# Change log moved to .prawduct/change-log.md (separate file for merge-friendliness).\n"
    )
    new_lines = lines[:comment_start] + pointer.split("\n") + lines[cl_end:]
    cleaned = "\n".join(new_lines)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    state_path.write_text(cleaned)
    actions.append("Removed change_log section from project-state.yaml (replaced with pointer)")

    return actions


def migrate_backlog(product_dir: Path) -> list[str]:
    """Move remaining_work/future_work/deferred_work from project-state.yaml to backlog.md.

    For remaining_work (under build_plan): parses item/description/phase fields,
    skips completed items, converts pending items to markdown bullets.
    For other sections (future_work, deferred_work, backlog): extracts raw YAML
    and wraps in a code block with cleanup marker.

    Idempotent: skips if no matching sections exist in project-state.yaml.
    Returns list of actions taken.
    """
    actions: list[str] = []
    state_path = product_dir / ".prawduct" / "project-state.yaml"
    if not state_path.is_file():
        return actions

    content = state_path.read_text()
    lines = content.split("\n")
    backlog_items: list[str] = []
    raw_sections: list[str] = []
    sections_removed: list[tuple[int, int, str]] = []  # (start, end, pointer)

    # --- remaining_work under build_plan ---
    rw_start = None
    rw_end = None
    rw_comment_start = None
    for i, line in enumerate(lines):
        if rw_start is None:
            # Match indented remaining_work: under build_plan
            stripped = line.strip()
            if stripped.startswith("remaining_work:") and line.startswith("  "):
                rw_start = i
                # Capture preceding comment lines at same or deeper indent
                rw_comment_start = i
                while rw_comment_start > 0:
                    prev = lines[rw_comment_start - 1]
                    if prev.strip().startswith("#") and prev.startswith("  "):
                        rw_comment_start -= 1
                    else:
                        break
        elif rw_start is not None and rw_end is None:
            # Find end: next line at same or lesser indentation (not blank/comment)
            if line.strip() and not line.strip().startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent <= 2:
                    rw_end = i
                    break

    if rw_start is not None:
        if rw_end is None:
            rw_end = len(lines)

        rw_section = lines[rw_start:rw_end]

        # Parse remaining_work entries
        entries: list[dict[str, str]] = []
        current_entry: dict[str, str] = {}
        current_key: str | None = None

        for line in rw_section:
            stripped = line.strip()
            if stripped.startswith("- item:"):
                if current_entry:
                    entries.append(current_entry)
                current_entry = {}
                current_key = "item"
                val = stripped.split(":", 1)[1].strip().strip("\"'")
                if val:
                    current_entry["item"] = val
            elif stripped.startswith("description:") and current_entry:
                current_key = "description"
                val = stripped.split(":", 1)[1].strip().strip("\"'")
                if val:
                    current_entry["description"] = val
            elif stripped.startswith("phase:") and current_entry:
                current_key = "phase"
                val = stripped.split(":", 1)[1].strip().strip("\"'")
                if val:
                    current_entry["phase"] = val
            elif current_key and current_entry and stripped and not stripped.startswith("#") and not stripped.startswith("- "):
                # Continuation line
                prev = current_entry.get(current_key, "")
                continuation = stripped.strip("\"'")
                if prev:
                    current_entry[current_key] = prev + " " + continuation
                else:
                    current_entry[current_key] = continuation

        if current_entry:
            entries.append(current_entry)

        # Convert non-completed entries to markdown
        for entry in entries:
            phase = entry.get("phase", "").lower()
            if phase == "completed":
                continue
            item = entry.get("item", "Untitled")
            desc = entry.get("description", "")
            bullet = f"- **{item}**"
            if desc:
                bullet += f" — {desc}"
            bullet += " (migrated)"
            backlog_items.append(bullet)

        # Mark for removal (use comment_start to capture preceding comments)
        pointer = "    # remaining_work: migrated to .prawduct/backlog.md\n"
        sections_removed.append((rw_comment_start, rw_end, pointer))

    # --- Top-level sections: future_work, deferred_work, backlog ---
    top_level_keys = ["future_work", "deferred_work", "backlog"]
    for key in top_level_keys:
        marker = f"{key}:"
        if f"\n{marker}" not in content and not content.startswith(marker):
            continue

        sec_start = None
        sec_end = None
        for i, line in enumerate(lines):
            if sec_start is None:
                if line.startswith(marker) or line.strip() == marker:
                    sec_start = i
            elif sec_start is not None:
                if line.strip() and not line.startswith(" ") and not line.startswith("#"):
                    sec_end = i
                    break

        if sec_start is None:
            continue
        if sec_end is None:
            sec_end = len(lines)

        # Capture preceding comments
        comment_start = sec_start
        while comment_start > 0:
            prev = lines[comment_start - 1]
            if prev.strip().startswith("#") or prev.strip() == "":
                comment_start -= 1
            else:
                break

        raw_yaml = "\n".join(lines[sec_start:sec_end]).rstrip()
        raw_sections.append(
            f"<!-- CLEANUP: Migrated from project-state.yaml ({key}).\n"
            f"     Review and convert to standard backlog items, then delete this block. -->\n"
            f"```yaml\n{raw_yaml}\n```"
        )

        pointer = f"# {key}: migrated to .prawduct/backlog.md\n"
        sections_removed.append((comment_start, sec_end, pointer))

    if not backlog_items and not raw_sections:
        return actions

    # Build backlog content
    md_parts: list[str] = []
    if backlog_items:
        md_parts.extend(backlog_items)
    if raw_sections:
        md_parts.extend(raw_sections)
    migrated_content = "\n".join(md_parts)

    # Write to backlog.md
    backlog_path = product_dir / ".prawduct" / "backlog.md"
    product_name = product_dir.name
    if backlog_path.is_file():
        existing = backlog_path.read_text()
        separator = "\n\n<!-- Migrated from project-state.yaml -->\n\n"
        backlog_path.write_text(existing.rstrip("\n") + separator + migrated_content + "\n")
    else:
        header = (
            f"# Backlog — {product_name}\n\n"
            "<!-- Work discovered during sessions but out of current scope.\n"
            "     Add items at the top. Each is a bullet with source marker:\n"
            "     (builder), (critic), (reflection), or (migrated).\n"
            "     Review with /janitor or when planning new work. -->\n\n"
        )
        backlog_path.write_text(header + migrated_content + "\n")

    item_count = len(backlog_items) + len(raw_sections)
    actions.append(f"Migrated {item_count} backlog item(s) to .prawduct/backlog.md")

    # Remove sections from project-state.yaml (process in reverse order to preserve indices)
    sections_removed.sort(key=lambda x: x[0], reverse=True)
    for start, end, pointer in sections_removed:
        lines[start:end] = pointer.split("\n")

    cleaned = "\n".join(lines)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    state_path.write_text(cleaned)
    actions.append("Removed migrated sections from project-state.yaml")

    return actions


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


def run_migrate(target_dir: str, product_name: str | None = None) -> dict:
    """Migrate a product repo to v5. Returns a summary of actions taken."""
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

    subs = {"{{PRODUCT_NAME}}": product_name, "{{PRAWDUCT_VERSION}}": PRAWDUCT_VERSION}

    # Deprecation notice for old versions
    if version == "v1":
        actions.append(
            "DEPRECATION: v1 repos are no longer supported. "
            "Migrating to v5 — review CLAUDE.md and .prawduct/ after migration."
        )
    elif version == "v3":
        actions.append(
            "DEPRECATION: v3 repos are no longer supported. "
            "Migrating to v5 — review CLAUDE.md and .prawduct/ after migration."
        )
    elif version == "partial":
        actions.append(
            "DEPRECATION: partial (v1→v3) repos are no longer supported. "
            "Migrating to v5 — review CLAUDE.md and .prawduct/ after migration."
        )

    # === V1-specific steps (v1 and partial) ===
    if version in ("v1", "partial"):
        # 1. Overwrite CLAUDE.md with current template
        if write_template(
            TEMPLATES_DIR / "product-claude.md", target / "CLAUDE.md", subs, overwrite=True
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
    if merge_settings(
        target / ".claude" / "settings.json",
        TEMPLATES_DIR / "product-settings.json",
        subs,
        legacy_cleanup=True,
    ):
        actions.append("Updated .claude/settings.json (hooks + banner)")

    # Copy product-hook (Python version)
    if copy_hook(
        FRAMEWORK_DIR / "tools" / "product-hook",
        target / "tools" / "product-hook",
    ):
        actions.append("Installed tools/product-hook (Python)")

    # Create critic-review.md if missing
    if write_template(
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

    # === V5 migration steps (idempotent, applies to all repos) ===

    # Remove stale test_tracking from project-state.yaml (test count is derived)
    actions.extend(strip_test_tracking(target))

    # Split learnings into active rules + reference detail
    actions.extend(split_learnings_v5(target))

    # Update project-state.yaml (add v5 sections, remove v4 fields)
    actions.extend(migrate_project_state_v5(target))

    # Place boundary-patterns.md if missing
    bp_src = TEMPLATES_DIR / "boundary-patterns.md"
    bp_dst = target / ".prawduct" / "artifacts" / "boundary-patterns.md"
    if bp_src.is_file() and not bp_dst.is_file():
        rendered = render_template(bp_src, subs)
        bp_dst.parent.mkdir(parents=True, exist_ok=True)
        bp_dst.write_text(rendered)
        actions.append("Created .prawduct/artifacts/boundary-patterns.md")

    # Bump manifest version to 2 if needed
    manifest_path = target / ".prawduct" / "sync-manifest.json"
    if manifest_path.is_file():
        try:
            mf = load_json(manifest_path)
            if mf.get("format_version", 1) < 2:
                mf["format_version"] = 2
                manifest_path.write_text(json.dumps(mf, indent=2) + "\n")
                actions.append("Bumped manifest to format_version 2 (v5)")
        except json.JSONDecodeError:
            pass

    return {
        "target": str(target),
        "product_name": product_name,
        "version_before": version,
        "version_after": detect_version(target),
        "actions": actions,
        "files_changed": len(actions),
    }
