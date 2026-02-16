#!/usr/bin/env python3
"""
prawduct-init.py — Mechanical prawduct integration setup and repair.

Detects the current state of prawduct infrastructure in a target directory,
creates missing components, repairs stale paths, and merges settings.json
hooks without destroying user configuration.

Designed to be idempotent: running twice produces no changes on the second run.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent

# Hook scripts that identify a hook entry as prawduct's.
# Used for detection during settings.json merging.
PRAWDUCT_HOOK_SCRIPTS = [
    "governance-gate.sh",
    "governance-tracker.sh",
    "governance-prompt.sh",
    "governance-stop.sh",
    "critic-gate.sh",
    "compact-governance-reinject.sh",
]

# The canonical hook configuration for product repos.
# Commands use absolute paths to the framework's hook directory.
# The SessionStart/clear hook uses $CLAUDE_PROJECT_DIR because it
# operates on the product repo's own .claude/ directory.
def get_prawduct_hooks(framework_hooks_dir: str) -> dict:
    """Return the canonical prawduct hook configuration with absolute paths."""
    return {
        "SessionStart": [
            {
                "matcher": "clear|startup",
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            'rm -f "$CLAUDE_PROJECT_DIR"/.claude/.orchestrator-activated '
                            '"$CLAUDE_PROJECT_DIR"/.claude/.session-governance.json '
                            '"$CLAUDE_PROJECT_DIR"/.claude/.session-edits.json '
                            '"$CLAUDE_PROJECT_DIR"/.claude/.product-session.json'
                        ),
                    }
                ],
            },
            {
                "matcher": "compact",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{framework_hooks_dir}/compact-governance-reinject.sh"',
                    }
                ],
            },
        ],
        "UserPromptSubmit": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{framework_hooks_dir}/governance-prompt.sh"',
                    }
                ],
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{framework_hooks_dir}/critic-gate.sh"',
                    }
                ],
            },
            {
                "matcher": "Edit|Write|Read",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{framework_hooks_dir}/governance-gate.sh"',
                    }
                ],
            },
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{framework_hooks_dir}/governance-tracker.sh"',
                    }
                ],
            }
        ],
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{framework_hooks_dir}/governance-stop.sh"',
                    }
                ],
            }
        ],
    }


CLAUDE_MD_BOOTSTRAP = """\
<!-- prawduct-bootstrap -->
## Prawduct Framework

This project uses the Prawduct framework.
Framework location: read `.prawduct/framework-path` for the absolute path.

Before taking any action, read the framework path from `.prawduct/framework-path`,
then read `{framework-path}/skills/orchestrator/SKILL.md` and follow its activation process.
<!-- /prawduct-bootstrap -->
"""

# Schema version detection signals
SCHEMA_SIGNALS = {
    "v0": ["product_shape", "shape"],
    "v0.5": ["concerns"],
    "v1_no_version": ["structural"],  # has structural but no schema_version
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str, json_mode: bool) -> None:
    """Print to stderr unless in JSON-only mode."""
    if not json_mode:
        print(msg, file=sys.stderr)


def git_commit_hash(repo_dir: str) -> str | None:
    """Get the current git commit hash, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def is_git_repo(target_dir: str) -> bool:
    """Check if target_dir is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "-C", target_dir, "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_framework_repo(target_dir: str) -> bool:
    """Check if target_dir is the prawduct framework repo itself."""
    return (Path(target_dir) / "skills" / "orchestrator" / "SKILL.md").is_file()


def detect_schema_version(project_state_path: Path) -> str | None:
    """Detect the schema version of a project-state.yaml file.

    Returns: "v0", "v0.5", "v1", "v2", or None if file doesn't exist.
    Does NOT use a YAML parser — relies on line-level text matching
    to avoid requiring PyYAML.
    """
    if not project_state_path.is_file():
        return None

    try:
        content = project_state_path.read_text()
    except OSError:
        return None

    lines = content.splitlines()

    # Check for explicit schema_version first
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("schema_version:"):
            val = stripped.split(":", 1)[1].strip()
            try:
                version = int(val)
                return f"v{version}"
            except ValueError:
                pass

    # No explicit version — check structural signals using TOP-LEVEL keys only
    # (column 0, no leading whitespace). Indented keys like classification.structural
    # are the current format, not old v1.
    has_top_level_structural = False
    for line in lines:
        # Skip comments and empty lines
        if not line or line[0] in ("#", "\n"):
            continue
        # Only check lines with no leading whitespace (top-level YAML keys)
        if line[0] in (" ", "\t"):
            continue
        # v0 signals
        for signal in SCHEMA_SIGNALS["v0"]:
            if line.startswith(f"{signal}:"):
                return "v0"
        # v0.5 signals
        if line.startswith("concerns:"):
            return "v0.5"
        # v1 signal (top-level structural: without schema_version)
        if line.startswith("structural:"):
            has_top_level_structural = True

    if has_top_level_structural:
        return "v1"

    # No version field and no old structural signals — assume current format
    # missing the schema_version field (e.g., framework's own project-state.yaml)
    return "current"


def scan_existing_docs(target_dir: str) -> list[str]:
    """Find markdown documentation files in the target directory."""
    docs = []
    target = Path(target_dir)

    # Check for root-level docs
    for name in ["README.md", "CHANGELOG.md", "CONTRIBUTING.md"]:
        if (target / name).is_file():
            docs.append(name)

    # Check docs/ directory
    docs_dir = target / "docs"
    if docs_dir.is_dir():
        for md in sorted(docs_dir.rglob("*.md")):
            docs.append(str(md.relative_to(target)))

    return docs


# Command patterns that identify a hook as prawduct's, even when not referencing
# a named hook script (e.g., the SessionStart cleanup command).
PRAWDUCT_COMMAND_PATTERNS = [
    ".orchestrator-activated",
    ".session-governance.json",
]


def is_prawduct_hook(command: str) -> bool:
    """Check if a hook command is a prawduct hook."""
    if any(script in command for script in PRAWDUCT_HOOK_SCRIPTS):
        return True
    if any(pattern in command for pattern in PRAWDUCT_COMMAND_PATTERNS):
        return True
    return False


def merge_settings_json(
    existing: dict, prawduct_hooks: dict, framework_hooks_dir: str
) -> tuple[dict, int, int]:
    """Merge prawduct hooks into existing settings.json.

    Returns (merged_settings, hooks_added, user_hooks_preserved).
    """
    merged = dict(existing)  # shallow copy of top-level keys
    existing_hooks = existing.get("hooks", {})
    merged_hooks = {}
    hooks_added = 0
    user_hooks_preserved = 0

    # Collect all event types from both sources
    all_events = set(list(existing_hooks.keys()) + list(prawduct_hooks.keys()))

    for event in all_events:
        existing_entries = existing_hooks.get(event, [])
        prawduct_entries = prawduct_hooks.get(event, [])

        # Separate existing entries into prawduct vs user
        user_entries = []
        existing_prawduct_matchers = {}  # matcher -> entry index
        for entry in existing_entries:
            entry_hooks = entry.get("hooks", [])
            is_prawduct = any(
                is_prawduct_hook(h.get("command", ""))
                for h in entry_hooks
                if h.get("type") == "command"
            )
            if is_prawduct:
                existing_prawduct_matchers[entry.get("matcher", "")] = entry
            else:
                user_entries.append(entry)
                user_hooks_preserved += 1

        # Build merged list for this event
        merged_entries = []

        # Governance hooks fire first for PreToolUse/UserPromptSubmit
        # User hooks fire first for PostToolUse/Stop (prawduct appended)
        fires_first = event in ("PreToolUse", "UserPromptSubmit", "SessionStart")

        if fires_first:
            # Add prawduct hooks first
            for pentry in prawduct_entries:
                matcher = pentry.get("matcher", "")
                if matcher in existing_prawduct_matchers:
                    # Update existing prawduct hook (path may have changed)
                    pass  # We'll use the new one
                else:
                    hooks_added += 1
                merged_entries.append(pentry)
            # Then user hooks
            merged_entries.extend(user_entries)
        else:
            # User hooks first
            merged_entries.extend(user_entries)
            # Then prawduct hooks
            for pentry in prawduct_entries:
                matcher = pentry.get("matcher", "")
                if matcher in existing_prawduct_matchers:
                    pass  # We'll use the new one
                else:
                    hooks_added += 1
                merged_entries.append(pentry)

        if merged_entries:
            merged_hooks[event] = merged_entries

    merged["hooks"] = merged_hooks
    return merged, hooks_added, user_hooks_preserved


# ---------------------------------------------------------------------------
# Check functions — each returns a check result dict
# ---------------------------------------------------------------------------

def check_prawduct_dir(target_dir: str, mode: str) -> dict:
    """Check/create .prawduct/ directory."""
    prawduct_dir = Path(target_dir) / ".prawduct"
    if prawduct_dir.is_dir():
        return {"name": "prawduct_dir", "status": "ok", "detail": str(prawduct_dir)}

    if mode == "fix":
        prawduct_dir.mkdir(parents=True, exist_ok=True)
        # Create subdirectories
        (prawduct_dir / "artifacts").mkdir(exist_ok=True)
        (prawduct_dir / "working-notes").mkdir(exist_ok=True)
        (prawduct_dir / "framework-observations").mkdir(exist_ok=True)
        return {"name": "prawduct_dir", "status": "created", "detail": str(prawduct_dir)}

    return {"name": "prawduct_dir", "status": "missing", "detail": str(prawduct_dir)}


def check_framework_path(target_dir: str, mode: str) -> dict:
    """Check/create .prawduct/framework-path file."""
    fp_file = Path(target_dir) / ".prawduct" / "framework-path"
    correct_path = str(FRAMEWORK_DIR)

    if fp_file.is_file():
        stored = fp_file.read_text().strip()
        if stored == correct_path:
            return {"name": "framework_path", "status": "ok", "detail": correct_path}
        # Stale path
        if mode == "fix":
            fp_file.write_text(correct_path)
            return {
                "name": "framework_path",
                "status": "updated",
                "detail": f"{stored} -> {correct_path}",
            }
        return {
            "name": "framework_path",
            "status": "stale",
            "detail": f"stored={stored}, correct={correct_path}",
        }

    if mode == "fix":
        fp_file.parent.mkdir(parents=True, exist_ok=True)
        fp_file.write_text(correct_path)
        return {"name": "framework_path", "status": "created", "detail": correct_path}

    return {"name": "framework_path", "status": "missing", "detail": correct_path}


def check_framework_version(target_dir: str, mode: str) -> dict:
    """Check/create .prawduct/framework-version file."""
    version_file = Path(target_dir) / ".prawduct" / "framework-version"
    current_hash = git_commit_hash(str(FRAMEWORK_DIR))

    if current_hash is None:
        return {
            "name": "framework_version",
            "status": "error",
            "detail": "Could not determine framework git commit",
        }

    result = {
        "name": "framework_version",
        "current": current_hash,
        "stored": None,
        "updated": False,
    }

    if version_file.is_file():
        stored = version_file.read_text().strip().split("\n")[0]  # first line is hash
        result["stored"] = stored
        if stored == current_hash:
            result["status"] = "ok"
            return result
        # Different version
        if mode == "fix":
            version_file.write_text(f"{current_hash}\n")
            result["status"] = "updated"
            result["updated"] = True
            return result
        result["status"] = "stale"
        return result

    if mode == "fix":
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(f"{current_hash}\n")
        result["status"] = "created"
        result["updated"] = True
        return result

    result["status"] = "missing"
    return result


def check_project_state(target_dir: str, mode: str) -> dict:
    """Check for project-state.yaml and detect its schema version."""
    prawduct_ps = Path(target_dir) / ".prawduct" / "project-state.yaml"
    root_ps = Path(target_dir) / "project-state.yaml"

    def version_to_int(version: str | None) -> int | None:
        if version is None:
            return None
        if version == "current":
            return 2  # Current format without explicit schema_version
        if version.startswith("v"):
            try:
                return int(version[1:])
            except ValueError:
                return None
        return None

    # Check .prawduct/ first, then root
    if prawduct_ps.is_file():
        version = detect_schema_version(prawduct_ps)
        return {
            "name": "project_state",
            "status": "ok",
            "detail": str(prawduct_ps),
            "schema_version": version_to_int(version),
            "location": ".prawduct/",
        }
    if root_ps.is_file():
        version = detect_schema_version(root_ps)
        return {
            "name": "project_state",
            "status": "ok",
            "detail": str(root_ps),
            "schema_version": version_to_int(version),
            "location": "root",
        }

    # No project-state.yaml — this is expected for fresh repos (onboarding creates it)
    return {
        "name": "project_state",
        "status": "missing",
        "detail": "No project-state.yaml found; onboarding will create it",
        "schema_version": None,
    }


def check_claude_md(target_dir: str, mode: str) -> dict:
    """Check/create CLAUDE.md with prawduct bootstrap section."""
    claude_md = Path(target_dir) / "CLAUDE.md"
    bootstrap_marker = "<!-- prawduct-bootstrap -->"
    bootstrap_end = "<!-- /prawduct-bootstrap -->"
    bootstrap_content = CLAUDE_MD_BOOTSTRAP.replace(
        "{framework-path}", str(FRAMEWORK_DIR)
    )

    if claude_md.is_file():
        existing = claude_md.read_text()
        if bootstrap_marker in existing:
            # Already has bootstrap — update it in case framework path changed
            start = existing.index(bootstrap_marker)
            end = existing.index(bootstrap_end) + len(bootstrap_end)
            current_bootstrap = existing[start : end]
            expected_bootstrap = bootstrap_content.strip()
            if current_bootstrap == expected_bootstrap:
                return {"name": "claude_md", "status": "ok", "detail": "Bootstrap section present"}
            if mode == "fix":
                updated = existing[:start] + expected_bootstrap + existing[end:]
                claude_md.write_text(updated)
                return {"name": "claude_md", "status": "updated", "detail": "Bootstrap section updated (framework path changed)"}
            return {"name": "claude_md", "status": "stale", "detail": "Bootstrap section has wrong framework path"}

        # Exists but no bootstrap — prepend
        if mode == "fix":
            claude_md.write_text(bootstrap_content + "\n" + existing)
            return {"name": "claude_md", "status": "merged", "detail": "Bootstrap prepended to existing CLAUDE.md"}
        return {"name": "claude_md", "status": "missing_bootstrap", "detail": "CLAUDE.md exists but lacks prawduct bootstrap"}

    # No CLAUDE.md at all
    if mode == "fix":
        claude_md.write_text(bootstrap_content)
        return {"name": "claude_md", "status": "created", "detail": "CLAUDE.md created with bootstrap"}
    return {"name": "claude_md", "status": "missing", "detail": "No CLAUDE.md"}


def check_settings_json(target_dir: str, mode: str) -> dict:
    """Check/create .claude/settings.json with prawduct hooks merged."""
    settings_path = Path(target_dir) / ".claude" / "settings.json"
    framework_hooks_dir = str(FRAMEWORK_DIR / ".claude" / "hooks")
    prawduct_hooks = get_prawduct_hooks(framework_hooks_dir)

    if settings_path.is_file():
        try:
            existing = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {
                "name": "settings_json",
                "status": "error",
                "detail": "Could not parse existing settings.json",
                "hooks_added": 0,
                "user_hooks_preserved": 0,
            }

        # Check if all prawduct hooks are present and correct
        merged, hooks_added, user_hooks_preserved = merge_settings_json(
            existing, prawduct_hooks, framework_hooks_dir
        )

        # Compare to see if anything changed
        if json.dumps(merged, sort_keys=True) == json.dumps(existing, sort_keys=True):
            return {
                "name": "settings_json",
                "status": "ok",
                "detail": "All prawduct hooks present",
                "hooks_added": 0,
                "user_hooks_preserved": user_hooks_preserved,
            }

        if mode == "fix":
            settings_path.write_text(json.dumps(merged, indent=2) + "\n")
            return {
                "name": "settings_json",
                "status": "merged",
                "detail": f"Added {hooks_added} hook(s), preserved {user_hooks_preserved} user hook(s)",
                "hooks_added": hooks_added,
                "user_hooks_preserved": user_hooks_preserved,
            }
        return {
            "name": "settings_json",
            "status": "needs_merge",
            "detail": f"Need to add {hooks_added} hook(s)",
            "hooks_added": hooks_added,
            "user_hooks_preserved": user_hooks_preserved,
        }

    # No settings.json — create with only prawduct hooks
    if mode == "fix":
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {"hooks": prawduct_hooks}
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        total_hooks = sum(len(entries) for entries in prawduct_hooks.values())
        return {
            "name": "settings_json",
            "status": "created",
            "detail": f"Created with {total_hooks} prawduct hooks",
            "hooks_added": total_hooks,
            "user_hooks_preserved": 0,
        }

    return {
        "name": "settings_json",
        "status": "missing",
        "detail": "No .claude/settings.json",
        "hooks_added": 0,
        "user_hooks_preserved": 0,
    }


def check_hook_accessibility(target_dir: str) -> list[str]:
    """Verify each hook script exists at the framework path."""
    hooks_dir = FRAMEWORK_DIR / ".claude" / "hooks"
    warnings = []
    for script in PRAWDUCT_HOOK_SCRIPTS:
        if not (hooks_dir / script).is_file():
            warnings.append(f"Hook script not found: {hooks_dir / script}")
    return warnings


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_init(target_dir: str, mode: str, json_mode: bool) -> dict:
    """Run all checks and return the result dict."""
    target = os.path.abspath(target_dir)
    checks = []
    warnings = []
    scenario = "healthy"
    self_hosted = False

    # 1. Target directory validation
    if not os.path.isdir(target):
        return {
            "status": "error",
            "target_dir": target,
            "framework_dir": str(FRAMEWORK_DIR),
            "scenario": "error",
            "checks": [],
            "next_action": "none",
            "warnings": [f"Target directory does not exist: {target}"],
        }

    # Self-hosted detection
    if is_framework_repo(target):
        log("Self-hosted framework repo detected. Reporting status only.", json_mode)
        mode = "check"  # Force check-only for framework repo
        self_hosted = True
        scenario = "self_hosted"

    if not self_hosted:
        # 2. .prawduct/ directory (product repos only)
        c = check_prawduct_dir(target, mode)
        checks.append(c)
        if c["status"] == "created":
            scenario = "fresh"

        # 3. framework-path (product repos only)
        c = check_framework_path(target, mode)
        checks.append(c)
        if c["status"] in ("created", "updated"):
            if scenario == "healthy":
                scenario = "repair"

        # 4. framework-version (product repos only)
        c = check_framework_version(target, mode)
        checks.append(c)

    # 5. project-state.yaml
    c = check_project_state(target, mode)
    checks.append(c)
    ps_check = c

    # Detect migration scenarios (not for self-hosted)
    if not self_hosted and c["status"] == "ok":
        sv = c.get("schema_version")
        if sv == 0:
            scenario = "migration_v0"
        elif sv == 1:
            if scenario == "healthy":
                scenario = "migration_v1"

    if not self_hosted:
        # 6. CLAUDE.md (product repos only)
        c = check_claude_md(target, mode)
        checks.append(c)

        # 7. .claude/settings.json (product repos only)
        c = check_settings_json(target, mode)
        checks.append(c)

    # 8. Existing documentation inventory
    existing_docs = scan_existing_docs(target)

    # 9. Hook accessibility
    hook_warnings = check_hook_accessibility(target)
    warnings.extend(hook_warnings)

    # Determine overall status and next_action
    statuses = [c["status"] for c in checks]
    has_created = "created" in statuses
    has_missing = any(
        s in statuses
        for s in ("missing", "stale", "needs_merge", "missing_bootstrap")
    )
    has_error = "error" in statuses

    if self_hosted:
        overall_status = "healthy"
    elif has_error:
        overall_status = "error"
    elif mode == "check" and has_missing:
        overall_status = "needs_repair"
    elif has_created or "merged" in statuses or "updated" in statuses:
        overall_status = "repaired"
    else:
        overall_status = "healthy"

    # Determine next action for the Orchestrator
    if self_hosted:
        next_action = "session_resumption"
    elif scenario == "fresh" and ps_check["status"] == "missing":
        next_action = "onboarding"
    elif scenario.startswith("migration"):
        next_action = "migration"
    elif overall_status in ("healthy", "repaired"):
        next_action = "session_resumption"
    else:
        next_action = "none"

    # Build framework_version info
    fv_check = next((c for c in checks if c["name"] == "framework_version"), None)
    framework_version = None
    if fv_check:
        framework_version = {
            "current": fv_check.get("current"),
            "stored": fv_check.get("stored"),
            "updated": fv_check.get("updated", False),
        }

    result = {
        "status": overall_status,
        "target_dir": target,
        "framework_dir": str(FRAMEWORK_DIR),
        "scenario": scenario,
        "framework_version": framework_version,
        "existing_docs": existing_docs,
        "checks": checks,
        "next_action": next_action,
        "warnings": warnings,
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Detect, create, and repair prawduct infrastructure in a target directory.",
    )
    parser.add_argument(
        "target_dir",
        nargs="?",
        default=os.getcwd(),
        help="Target directory (defaults to CWD)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report state without making changes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply all repairs (default)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="JSON-only output to stdout",
    )
    args = parser.parse_args()

    # Determine mode
    if args.check:
        mode = "check"
    elif args.dry_run:
        mode = "check"  # dry-run uses check mode but shows output
    else:
        mode = "fix"

    result = run_init(args.target_dir, mode, args.json_mode)

    # Output
    if args.json_mode:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output to stderr, JSON to stdout
        status = result["status"]
        scenario = result["scenario"]
        print(f"prawduct-init: {status} (scenario: {scenario})", file=sys.stderr)

        for check in result["checks"]:
            name = check["name"]
            cstatus = check["status"]
            detail = check.get("detail", "")
            print(f"  {name}: {cstatus} — {detail}", file=sys.stderr)

        if result["warnings"]:
            print("\nWarnings:", file=sys.stderr)
            for w in result["warnings"]:
                print(f"  ! {w}", file=sys.stderr)

        next_action = result["next_action"]
        if next_action != "none":
            print(f"\nNext action: {next_action}", file=sys.stderr)

        # Always output JSON to stdout for Orchestrator consumption
        print(json.dumps(result, indent=2))

    # Exit code
    if result["status"] == "error":
        sys.exit(1)
    if args.check and result["status"] == "needs_repair":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
