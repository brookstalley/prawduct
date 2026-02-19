"""File classification for governance decisions.

Single implementation replacing the duplicated classification logic in
governance-gate.sh and governance-tracker.sh.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .context import Context

# Files that require Orchestrator governance (framework files)
FRAMEWORK_PATTERNS = (
    "CLAUDE.md",
    "README.md",
    "skills/",
    "templates/",
    "docs/",
    "scripts/",
    "tools/",
    ".claude/settings.json",
    ".prawduct/framework-observations/README.md",
    ".prawduct/framework-observations/schema.yaml",
    ".prawduct/artifacts/",
)

# Governance-sensitive files — define what the framework *is*.
# Edits require PFR. Docs/templates/config are NOT governance-sensitive.
GOVERNANCE_SENSITIVE_PREFIXES = (
    "skills/",
    "tools/",
    "scripts/",
)

# Skill/template files gated for Read operations
READ_GATED_PREFIXES = (
    "skills/",
    "templates/",
)

# Always readable without activation
READ_WHITELIST = (
    "skills/orchestrator/SKILL.md",
)


@dataclass(frozen=True)
class FileClass:
    """Classification result for a file."""

    is_framework: bool
    is_product: bool
    is_governance_sensitive: bool
    is_read_gated: bool
    rel_path: str  # Relative to repo root
    fw_rel_path: str  # Relative to framework root (for cross-repo reads)


def _get_product_dir(session_file: str) -> str:
    """Read product_dir from session governance file."""
    try:
        import json

        with open(session_file) as f:
            data = json.load(f)
        return data.get("product_dir", "")
    except (OSError, ValueError, KeyError):
        return ""


def _normalize_path(file_path: str) -> str:
    """Normalize a file path for comparison."""
    try:
        dir_part = os.path.dirname(file_path)
        base_part = os.path.basename(file_path)
        if os.path.isdir(dir_part):
            return os.path.join(os.path.realpath(dir_part), base_part)
    except OSError:
        pass
    return file_path


def classify(file_path: str, ctx: Context) -> FileClass:
    """Classify a file for governance purposes.

    Args:
        file_path: Absolute path to the file.
        ctx: Resolved governance context.

    Returns:
        FileClass with classification flags.
    """
    rel_path = ""
    if ctx.repo_root and file_path.startswith(ctx.repo_root + "/"):
        rel_path = file_path[len(ctx.repo_root) + 1 :]

    fw_rel_path = ""
    if file_path.startswith(ctx.framework_root + "/"):
        fw_rel_path = file_path[len(ctx.framework_root) + 1 :]

    # Framework file: in the framework repo and matches a governed pattern
    is_framework = False
    check_path = rel_path if (ctx.repo_root and ctx.repo_root == ctx.framework_root) else ""
    if check_path:
        for pattern in FRAMEWORK_PATTERNS:
            if check_path == pattern or check_path.startswith(pattern):
                is_framework = True
                break

    # Product file: inside an active product build directory
    is_product = False
    if os.path.isfile(ctx.session_file):
        product_dir = _get_product_dir(ctx.session_file)
        if product_dir:
            norm_file = _normalize_path(file_path)
            if norm_file.startswith(product_dir):
                is_product = True

    # Governance-sensitive: framework file matching sensitive prefixes
    is_governance_sensitive = False
    if is_framework and rel_path:
        for prefix in GOVERNANCE_SENSITIVE_PREFIXES:
            if rel_path.startswith(prefix):
                is_governance_sensitive = True
                break

    # Read-gated: skill/template files (local or cross-repo)
    is_read_gated = False
    for prefix in READ_GATED_PREFIXES:
        if (rel_path and rel_path.startswith(prefix)) or (
            fw_rel_path and fw_rel_path.startswith(prefix)
        ):
            is_read_gated = True
            break
    # Whitelist overrides
    if rel_path in READ_WHITELIST or fw_rel_path in READ_WHITELIST:
        is_read_gated = False

    return FileClass(
        is_framework=is_framework,
        is_product=is_product,
        is_governance_sensitive=is_governance_sensitive,
        is_read_gated=is_read_gated,
        rel_path=rel_path,
        fw_rel_path=fw_rel_path,
    )
