"""File classification for governance decisions.

Single implementation replacing the duplicated classification logic in
governance-gate.sh and governance-tracker.sh.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from .context import Context

# Cache for git root lookups: directory -> git root (or None if not in a repo)
_git_root_cache: Dict[str, Optional[str]] = {}

# Files that require Orchestrator governance (framework files)
FRAMEWORK_PATTERNS = (
    "CLAUDE.md",
    "README.md",
    "skills/",
    "agents/",
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
    "agents/",
    "tools/",
    "scripts/",
)

# Skill/template files gated for Read operations
READ_GATED_PREFIXES = (
    "skills/",
    "agents/",
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
    is_external_repo: bool  # In a git repo that is neither framework nor active product
    external_repo_root: str  # Git root of the external repo (empty if not external)
    rel_path: str  # Relative to repo root
    fw_rel_path: str  # Relative to framework root (for cross-repo reads)


def _find_git_root(file_path: str) -> Optional[str]:
    """Find the git repository root for a file by walking up directories.

    Handles both regular repos (.git is a directory) and worktrees/submodules
    (.git is a file containing 'gitdir: <path>').

    Results are cached by directory to avoid repeated filesystem walks.
    """
    d = os.path.dirname(os.path.abspath(file_path))

    # Check cache — walk up to find a cached ancestor
    check_dir = d
    uncached = []
    while check_dir != os.path.dirname(check_dir):
        if check_dir in _git_root_cache:
            # Found a cached entry — propagate to uncached descendants
            root = _git_root_cache[check_dir]
            for uc in uncached:
                _git_root_cache[uc] = root
            return root
        uncached.append(check_dir)
        check_dir = os.path.dirname(check_dir)

    # No cache hit — walk from the file upward
    check_dir = d
    while check_dir != os.path.dirname(check_dir):
        git_path = os.path.join(check_dir, ".git")
        # .git can be a directory (normal repo) or a file (worktree/submodule)
        if os.path.isdir(git_path) or os.path.isfile(git_path):
            # Cache all directories from file up to (and including) the root
            walk = d
            while walk != check_dir:
                _git_root_cache[walk] = check_dir
                walk = os.path.dirname(walk)
            _git_root_cache[check_dir] = check_dir
            return check_dir
        check_dir = os.path.dirname(check_dir)

    # Not in a git repo — cache that too
    walk = d
    while walk != os.path.dirname(walk):
        _git_root_cache[walk] = None
        walk = os.path.dirname(walk)
    return None


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

    # Bootstrap fallback: file's git root has .prawduct/ but session file
    # doesn't exist yet. Covers the window between Orchestrator step 3 and step 4.
    if not is_product:
        git_root = _find_git_root(file_path)
        if git_root:
            candidate = os.path.join(git_root, ".prawduct")
            if os.path.isdir(candidate):
                norm_file = _normalize_path(file_path)
                if norm_file.startswith(git_root + os.sep) or norm_file == git_root:
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

    # External repo: file is in a git repo that is neither the framework
    # nor the active product. This catches cross-repo governance escapes
    # (e.g., editing ../worldground/ without onboarding it).
    # git_root is already set by the bootstrap fallback above (both blocks
    # share the same `not is_product` precondition).
    is_external_repo = False
    external_repo_root = ""
    if not is_framework and not is_product:
        if git_root is not None:
            # Normalize framework_root for comparison
            fw_root_real = os.path.realpath(ctx.framework_root)
            git_root_real = os.path.realpath(git_root)
            if git_root_real != fw_root_real:
                is_external_repo = True
                external_repo_root = git_root

    return FileClass(
        is_framework=is_framework,
        is_product=is_product,
        is_governance_sensitive=is_governance_sensitive,
        is_read_gated=is_read_gated,
        is_external_repo=is_external_repo,
        external_repo_root=external_repo_root,
        rel_path=rel_path,
        fw_rel_path=fw_rel_path,
    )
