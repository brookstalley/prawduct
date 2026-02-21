"""Path resolution for governance hooks.

Single implementation of the context resolution that was previously duplicated
across governance-gate.sh, governance-tracker.sh, governance-stop.sh, and
critic-gate.sh. Resolves framework root, prawduct dir, and repo root.

Active-products registry: In cross-repo sessions (framework hooks managing
separate product repos), gate/track register each product in an
`.active-products/` directory keyed by hash of the product's realpath.
This allows multiple products to be tracked concurrently from the same
CLAUDE_PROJECT_DIR without clobbering. Stop enumerates all registered
products to check governance debt across all active products. Registrations
include a timestamp; entries older than 12h are considered stale.

Advisory lock: A `.session.lock` file in each product's `.prawduct/`
detects concurrent sessions on the same product. The lock is refreshed on
each gate/track invocation. If a fresh lock (< 1h) exists when a new
session activates, a warning is emitted. This is advisory only — sessions
proceed with last-writer-wins semantics.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Context:
    """Resolved governance paths (session-level)."""

    framework_root: str
    prawduct_dir: str
    repo_root: str

    @property
    def session_file(self) -> str:
        return os.path.join(self.prawduct_dir, ".session-governance.json")

    @property
    def activation_marker(self) -> str:
        return os.path.join(self.prawduct_dir, ".orchestrator-activated")

    @property
    def trace_file(self) -> str:
        return os.path.join(self.prawduct_dir, ".session-trace.jsonl")

    @property
    def critic_pending(self) -> str:
        return os.path.join(self.prawduct_dir, ".critic-pending")

    @property
    def critic_findings(self) -> str:
        return os.path.join(self.prawduct_dir, ".critic-findings.json")


def _git_toplevel() -> str:
    """Get the git repo root, or empty string if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


# --- Constants ---

# Stale product registration threshold (12 hours)
REGISTRATION_MAX_AGE = 12 * 60 * 60

# Concurrent session detection threshold (1 hour)
SESSION_LOCK_FRESHNESS = 60 * 60


# --- Product registry ---


def _product_hash(product_root: str) -> str:
    """Deterministic hash of a product's realpath. SHA256[:12]."""
    real = os.path.realpath(product_root)
    return hashlib.sha256(real.encode()).hexdigest()[:12]


def _active_products_dir(prawduct_dir: str) -> str:
    """Path to the .active-products/ directory."""
    return os.path.join(prawduct_dir, ".active-products")


def register_active_product(
    session_prawduct_dir: str, product_prawduct_dir: str
) -> None:
    """Register a product in the active-products directory.

    Creates `<session_prawduct_dir>/.active-products/<hash>` containing
    the product path and a timestamp. Same product always maps to the
    same file (idempotent). Different products create different files
    (no clobbering).

    Args:
        session_prawduct_dir: The session-level .prawduct/ (from CLAUDE_PROJECT_DIR).
        product_prawduct_dir: The resolved product's .prawduct/.
    """
    products_dir = _active_products_dir(session_prawduct_dir)
    try:
        os.makedirs(products_dir, exist_ok=True)
        h = _product_hash(product_prawduct_dir)
        entry_path = os.path.join(products_dir, h)
        with open(entry_path, "w") as f:
            f.write(f"{os.path.realpath(product_prawduct_dir)}\n{time.time()}\n")
    except OSError:
        pass  # Best effort — never block on registration failure


def enumerate_active_products(
    session_prawduct_dir: str,
    min_timestamp: float = 0.0,
) -> list[str]:
    """Return paths of all active (non-stale) registered products.

    Reads all entries from `.active-products/`, filters out stale (>12h)
    and nonexistent directories.

    Args:
        session_prawduct_dir: The session-level .prawduct/.
        min_timestamp: If > 0, skip products registered before this time.
            Used by stop hook to filter out products from prior conversations.

    Returns:
        List of product .prawduct/ directory paths.
    """
    products_dir = _active_products_dir(session_prawduct_dir)
    if not os.path.isdir(products_dir):
        return []

    now = time.time()
    result = []
    try:
        for entry_name in os.listdir(products_dir):
            entry_path = os.path.join(products_dir, entry_name)
            if not os.path.isfile(entry_path):
                continue
            try:
                with open(entry_path) as f:
                    lines = f.read().strip().split("\n")
                if len(lines) < 2:
                    continue
                product_path = lines[0].strip()
                ts = float(lines[1].strip())
                if now - ts > REGISTRATION_MAX_AGE:
                    continue  # Stale (>12h)
                if min_timestamp > 0 and ts < min_timestamp:
                    continue  # Registered before session boundary
                if not os.path.isdir(product_path):
                    continue  # Directory gone
                result.append(product_path)
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return result


def cleanup_active_products(session_prawduct_dir: str) -> None:
    """Remove the .active-products/ directory and all entries.

    Args:
        session_prawduct_dir: The session-level .prawduct/.
    """
    import shutil

    products_dir = _active_products_dir(session_prawduct_dir)
    try:
        if os.path.isdir(products_dir):
            shutil.rmtree(products_dir)
    except OSError:
        pass


# --- Advisory lock ---


def check_session_lock(prawduct_dir: str) -> Optional[str]:
    """Check if another session appears active on this product.

    Args:
        prawduct_dir: Product's .prawduct/ directory.

    Returns:
        Warning message if a fresh lock exists, None otherwise.
    """
    lock_path = os.path.join(prawduct_dir, ".session.lock")
    if not os.path.isfile(lock_path):
        return None
    try:
        age = time.time() - os.path.getmtime(lock_path)
        if age < SESSION_LOCK_FRESHNESS:
            return (
                f"Another session appears active on this product "
                f"(lock age: {int(age)}s). Proceeding with last-writer-wins semantics."
            )
    except OSError:
        pass
    return None


def write_session_lock(prawduct_dir: str) -> None:
    """Write the advisory session lock file.

    Args:
        prawduct_dir: Product's .prawduct/ directory.
    """
    lock_path = os.path.join(prawduct_dir, ".session.lock")
    try:
        cpd = os.environ.get("CLAUDE_PROJECT_DIR", "")
        with open(lock_path, "w") as f:
            f.write(f"{time.time()}\n{cpd}\n")
    except OSError:
        pass


def touch_session_lock(prawduct_dir: str) -> None:
    """Update the advisory lock's mtime (heartbeat).

    Args:
        prawduct_dir: Product's .prawduct/ directory.
    """
    lock_path = os.path.join(prawduct_dir, ".session.lock")
    try:
        if os.path.isfile(lock_path):
            os.utime(lock_path, None)  # Update to current time
    except OSError:
        pass


def resolve_product_for_file(file_path: str, fallback_prawduct_dir: str) -> str:
    """Resolve the product .prawduct/ directory for a specific file path.

    Derives the product from the file's git root rather than a global
    pointer. If the file's git root contains .prawduct/, use that.
    Otherwise fall back to the session-level prawduct_dir.

    Args:
        file_path: Absolute path to the file being operated on.
        fallback_prawduct_dir: Session-level .prawduct/ (from Context).

    Returns:
        The prawduct_dir string for the resolved product.
    """
    from .classify import _find_git_root

    if file_path:
        git_root = _find_git_root(file_path)
        if git_root:
            candidate = os.path.join(git_root, ".prawduct")
            if os.path.isdir(candidate):
                return candidate
    return fallback_prawduct_dir


def update_product_context(
    file_path: str, ctx: Context, register: bool = True
) -> Context:
    """Resolve product from file path and update context if needed.

    If the file belongs to a different product than ctx currently points to,
    optionally registers the product in the active-products directory and
    returns a NEW Context with the updated prawduct_dir.

    Args:
        file_path: Absolute path to the file being operated on.
        ctx: Current resolved governance context.
        register: Whether to register the product for stop-hook validation.
            True for Edit/Write (mutations), False for Read (passive).

    Returns:
        Context — either the original (if no change) or a new one pointing
        to the resolved product.
    """
    product_prawduct_dir = resolve_product_for_file(file_path, ctx.prawduct_dir)

    if os.path.realpath(product_prawduct_dir) == os.path.realpath(ctx.prawduct_dir):
        return ctx  # No change

    # Cross-repo: optionally register product and return updated context.
    # The registry lives in the session-level .prawduct/ (from CLAUDE_PROJECT_DIR).
    # Read operations resolve context (for correct classification) but don't
    # register — reading a file shouldn't cause the stop hook to validate
    # that repo's governance debt.
    if register:
        session_prawduct_dir = os.path.join(
            os.environ.get("CLAUDE_PROJECT_DIR", ctx.framework_root), ".prawduct"
        )
        register_active_product(session_prawduct_dir, product_prawduct_dir)

    return Context(
        framework_root=ctx.framework_root,
        prawduct_dir=product_prawduct_dir,
        repo_root=ctx.repo_root,
    )


def resolve(
    framework_root: Optional[str] = None,
    follow_pointer: bool = True,
) -> Context:
    """Resolve all governance paths from environment.

    After computing the initial prawduct_dir from CLAUDE_PROJECT_DIR,
    optionally checks the active-products registry to redirect to
    a cross-repo product (most recently registered entry).

    Args:
        framework_root: Explicit framework root. If None, derived from
            GOVERNANCE_FRAMEWORK_ROOT env var (set by hook shims).
        follow_pointer: Whether to follow the active-products registry.
            True for gate/track (need product context for the file being
            edited). False for stop/commit/prompt — stop enumerates all
            products separately; commit/prompt operate session-level only.

    Returns:
        Context with all resolved paths.
    """
    if framework_root is None:
        framework_root = os.environ.get("GOVERNANCE_FRAMEWORK_ROOT", "")
    if not framework_root:
        raise ValueError(
            "framework_root must be provided or GOVERNANCE_FRAMEWORK_ROOT must be set"
        )

    repo_root = _git_toplevel()
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")

    if claude_project_dir:
        prawduct_dir = os.path.join(claude_project_dir, ".prawduct")
    elif repo_root:
        prawduct_dir = os.path.join(repo_root, ".prawduct")
    else:
        prawduct_dir = os.path.join(framework_root, ".prawduct")

    # Follow active-products registry if requested.
    # Gate/track follow the pointer to resolve per-file product context.
    # Stop enumerates all products separately via enumerate_active_products().
    # Commit/prompt operate session-level only.
    if follow_pointer:
        products = enumerate_active_products(prawduct_dir)
        if products:
            # Use the most recently registered product
            # (entries are filtered for staleness already)
            best_path = None
            best_ts = 0.0
            products_dir = _active_products_dir(prawduct_dir)
            try:
                for entry_name in os.listdir(products_dir):
                    entry_path = os.path.join(products_dir, entry_name)
                    if not os.path.isfile(entry_path):
                        continue
                    try:
                        with open(entry_path) as f:
                            lines = f.read().strip().split("\n")
                        if len(lines) >= 2:
                            p = lines[0].strip()
                            ts = float(lines[1].strip())
                            if p in products and ts > best_ts:
                                best_ts = ts
                                best_path = p
                    except (OSError, ValueError):
                        continue
            except OSError:
                pass
            if best_path:
                prawduct_dir = best_path

    return Context(
        framework_root=framework_root,
        prawduct_dir=prawduct_dir,
        repo_root=repo_root,
    )
