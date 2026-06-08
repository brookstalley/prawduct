"""Session-end compliance canary + its file classifiers for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 4) — the lightweight
failure-detection pass the Stop hook runs at session end: it inspects the
session's changed files for code-without-tests, dependency-without-manifest,
broad exception handling, and reason-less ``prawduct:allow`` waivers, returning
informational ``CANARY:`` findings. Best-effort by design — every probe fails
open (never crashes, never blocks session end).

Depends only on its lib sibling ``gitstate`` (for ``_get_session_changed_files``
and ``get_prawduct_dir``) and, lazily, ``waivers`` (the shared pragma
recognizer), plus the stdlib — a clean DAG node (``gitstate`` ← ``compliance``).
The hook calls ``compliance_canary`` lazily via ``_compliance()``, keeping its
top level lib-free; the ``cmd_stop`` call site wraps it in a broad catch so a
canary failure can never block session end.

The file classifiers (``_is_source_file`` / ``_is_test_file`` /
``_is_dependency_file``) move with the canary — it is their only caller.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import gitstate


def _is_source_file(filepath: str) -> bool:
    """Check if a filepath looks like a source code file (not test, not config)."""
    p = Path(filepath)
    suffix = p.suffix

    if suffix not in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb", ".swift", ".kt", ".c", ".cpp", ".h"):
        return False

    name = p.name
    if name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".test.ts", ".test.jsx", ".test.tsx", ".spec.js", ".spec.ts")):
        return False

    if filepath.startswith(".prawduct/"):
        return False

    return True


def _is_test_file(filepath: str) -> bool:
    """Check if a filepath looks like a test file."""
    name = Path(filepath).name
    return (
        (name.startswith("test_") and name.endswith(".py"))
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".test.jsx", ".test.tsx", ".spec.js", ".spec.ts"))
    )


def _is_dependency_file(filepath: str) -> bool:
    """Check if a filepath is a dependency declaration file."""
    name = Path(filepath).name
    return name in ("requirements.txt", "package.json", "Pipfile", "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile")


def _waivers_module():
    """Lazy-import the shared waiver recognizer (``lib/waivers.py``).

    Returns the module, or ``None`` if it can't be imported. The canary is
    best-effort and must never crash, so callers treat ``None`` as "recognizer
    unavailable" and fail open (emit no waiver-dependent finding).
    """
    try:
        from . import waivers  # noqa: PLC0415 — lazy keeps the canary best-effort
        return waivers
    except Exception:  # prawduct:allow prawduct/broad-except -- recognizer is best-effort; canary must not crash
        return None


def _check_broad_exceptions(project_dir: Path, source_files: list[str]) -> list[str]:
    """Check if changed source files contain broad exception patterns.

    Skips lines waived with ``prawduct/broad-except`` (intentional, reviewed),
    recognized via the shared ``lib.waivers`` recognizer — which honors both the
    ``prawduct:allow prawduct/broad-except`` form and the legacy
    ``prawduct:ok-broad-except`` spelling (see docs/waivers.md). For Python, also
    skips broad catches that re-raise or log within 3 lines.
    """
    waivers = _waivers_module()
    if waivers is None:
        return []  # recognizer unavailable — fail open (best-effort canary)
    # Language-specific patterns for overly broad exception handling
    patterns = {
        ".py": r"except\s+(?:Exception|BaseException)\s*(?::|,|as\b)",
        ".js": r"catch\s*\([^)]*\)\s*\{\s*\}",
        ".jsx": r"catch\s*\([^)]*\)\s*\{\s*\}",
        ".ts": r"catch\s*\([^)]*\)\s*\{\s*\}",
        ".tsx": r"catch\s*\([^)]*\)\s*\{\s*\}",
        ".go": r"_\s*=\s*\w+\.(?:\w+)\(",  # _ = foo.Bar() — ignored errors
    }
    flagged = []
    for filepath in source_files:
        full_path = project_dir / filepath
        if not full_path.is_file():
            continue
        suffix = Path(filepath).suffix
        pattern = patterns.get(suffix)
        if not pattern:
            continue
        try:
            content = full_path.read_text()
            lines = content.splitlines()
            has_unflagged = False
            for i, line in enumerate(lines):
                if not re.search(pattern, line):
                    continue
                # Skip if this line (or the line above) waives broad-except.
                if waivers.waives(lines, i, "prawduct/broad-except"):
                    continue
                # For Python: skip if the except block re-raises or logs
                if suffix == ".py":
                    # Check next 3 lines for raise or log/logger calls
                    following = "\n".join(lines[i + 1 : i + 4])
                    if re.search(r"\braise\b", following) or re.search(r"\blog(?:ger|ging)?\b", following, re.IGNORECASE):
                        continue
                has_unflagged = True
                break
            if has_unflagged:
                flagged.append(filepath)
        except Exception:  # prawduct:allow prawduct/broad-except -- canary must never crash on a single file
            pass
    return flagged


def _check_invalid_waivers(project_dir: Path, source_files: list[str]) -> list[str]:
    """Source files carrying a reason-less ``prawduct:allow`` waiver.

    The reason is mandatory (docs/waivers.md): a waiver without one is malformed
    and defeats the "reviewed and intentional" contract. Best-effort like the
    rest of the canary.
    """
    waivers = _waivers_module()
    if waivers is None:
        return []
    flagged = []
    for filepath in source_files:
        full_path = project_dir / filepath
        if not full_path.is_file():
            continue
        try:
            lines = full_path.read_text().splitlines()
            if waivers.invalid_waivers(lines):
                flagged.append(filepath)
        except Exception:  # prawduct:allow prawduct/broad-except -- canary must never crash on a single file
            pass
    return flagged


def compliance_canary(project_dir: Path) -> list[str]:
    """Lightweight compliance checks at session end. Returns informational findings."""
    findings: list[str] = []
    changed = gitstate._get_session_changed_files(project_dir)

    if not changed:
        return findings

    source_changed = [f for f in changed if _is_source_file(f)]
    test_changed = [f for f in changed if _is_test_file(f)]
    dep_changed = [f for f in changed if _is_dependency_file(f)]

    # 1. Code changed but no tests
    if source_changed and not test_changed:
        preview = ", ".join(source_changed[:3])
        findings.append(
            f"CANARY: {len(source_changed)} source file(s) changed but no test files modified. Changed: {preview}"
        )

    # 2. Dependency file changed without manifest update
    if dep_changed:
        prawduct_dir = gitstate.get_prawduct_dir(project_dir)
        manifest_path = prawduct_dir / "artifacts" / "dependency-manifest.md"
        dep_manifest_in_changes = any(f.endswith("dependency-manifest.md") for f in changed)
        if manifest_path.is_file() and not dep_manifest_in_changes:
            findings.append(
                f"CANARY: Dependency file(s) changed ({', '.join(dep_changed)}) "
                f"but dependency-manifest.md was not updated."
            )

    # 3. Broad exception handling in changed source files
    broad_except_files = _check_broad_exceptions(project_dir, source_changed)
    if broad_except_files:
        findings.append(
            f"CANARY: Broad exception handling detected in: {', '.join(broad_except_files)}. "
            f"Verify exceptions are specific and include logging/re-raising."
        )

    # 4. Reason-less prawduct:allow waivers (malformed — a waiver must say why)
    invalid_waiver_files = _check_invalid_waivers(project_dir, source_changed)
    if invalid_waiver_files:
        findings.append(
            f"CANARY: Reason-less prawduct:allow waiver in: {', '.join(invalid_waiver_files)}. "
            f"A waiver must state why it's intentional (see docs/waivers.md)."
        )

    return findings
