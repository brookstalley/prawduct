"""Read-only git + repository-state probes for the prawduct runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 2) — the leaf of the hook
decomposition: every other extracted module depends on these probes, and this
module depends on nothing but the standard library. Pure inspection only — no
mutation of git state (the session-start ``git rm --cached`` untracking stays in
the hook). The hook imports this lazily inside the functions that use it
(``_gitstate()``), keeping the hook's top level lib-free; after the Chunk-1
``lib/__init__`` slim, ``from lib import gitstate`` loads only this module.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def get_prawduct_dir(project_dir: Path) -> Path:
    """``.prawduct/`` under the project dir. Local copy of the hook's bootstrap
    helper so this module stays self-contained (lib never imports from bin/)."""
    return project_dir / ".prawduct"


def git_status_output(project_dir: Path) -> str | None:
    """Return raw `git status --porcelain` output, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        return None


def git_has_changes(project_dir: Path) -> str:
    """Check if there are uncommitted changes. Returns first changed file or empty string."""
    output = git_status_output(project_dir)
    if output is None:
        return ""
    lines = output.strip().splitlines()
    return lines[0] if lines else ""


# Paths that are framework/session metadata — changes to these should
# never trigger reflection or Critic gates. Plugin-only: product-owned state
# and the committed install reference. The file-sync-era entries
# (``.claude/skills/`` for synced framework skills, ``tools/product-hook``)
# are intentionally absent — a plugin repo never carries them, and a
# product's *own* skill under ``.claude/skills/`` is product code that must
# be gated, not excused. The single canonical copy — ``lib/critic_mode.py``'s
# mirror was consolidated onto this one (STH-2K8R).
_METADATA_PREFIXES = (
    ".prawduct/",
    ".claude/settings.json",
)


def _is_metadata_path(filepath: str) -> bool:
    """Check if a file path is framework/session metadata (not user code)."""
    return any(filepath.startswith(p) for p in _METADATA_PREFIXES)


def parse_porcelain_line(line: str) -> tuple[str, str | None, str] | None:
    """Parse one ``git status --porcelain`` line into ``(status, src_path, path)``.

    Git QUOTES paths containing spaces or special characters (`` M "my doc.md"``)
    and renders renames as ``R  old -> new`` — a naive ``line.split()[-1]`` returns
    ``doc.md"`` for the quoted form, which made the doc-only classification fail on
    the trailing quote and falsely block doc-only sessions at the Critic/reflection
    gates (review-fixes Chunk 1). ``src_path`` is the rename source (None for
    non-renames); ``path`` is the current/destination path, quote-stripped.
    Returns None for blank or malformed lines. Two accepted caveats, both
    classification-only impact: octal escapes inside quoted paths (non-ASCII
    filenames) are left as-is — quote-stripping is sufficient for path
    *classification* by prefix/suffix, which is all the callers do; and a
    quoted rename SOURCE itself containing ``" -> "`` mis-splits at the first
    arrow (vanishingly rare, still strictly better than the ``split()[-1]``
    parse this replaced).
    """
    if len(line) < 4:
        return None
    status = line[:2]
    raw = line[3:].strip()
    src_path: str | None = None
    if " -> " in raw:
        src_raw, dst_raw = raw.split(" -> ", 1)
        src_path = src_raw.strip()
        if src_path.startswith('"') and src_path.endswith('"'):
            src_path = src_path[1:-1]
        raw = dst_raw.strip()
    path = raw
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    if not path:
        return None
    return status, src_path, path


def git_has_session_changes(project_dir: Path) -> str:
    """Check if non-metadata uncommitted changes differ from session baseline.

    Compares current git status to the baseline captured at session start.
    Ignores .prawduct/ metadata and framework-managed files.
    Returns first new changed file or empty string. Falls back to
    git_has_changes if no baseline exists (backward compat).
    """
    prawduct_dir = get_prawduct_dir(project_dir)
    baseline_path = prawduct_dir / ".session-git-baseline"

    if not baseline_path.is_file():
        return git_has_changes(project_dir)

    current = git_status_output(project_dir)
    if current is None:
        return ""

    try:
        baseline = baseline_path.read_text()
    except (UnicodeDecodeError, OSError):
        return ""  # Corrupted baseline — treat as no baseline (safe: permits session end)
    # No whole-output .strip(): it eats the FIRST line's leading status space
    # (" M x" → "M x"), corrupting the fixed-offset porcelain parse. Both sides
    # unstripped, matching the trivial gate's reads (review-fixes Chunk 1).
    baseline_lines = set(baseline.splitlines())
    current_lines = current.splitlines()

    for line in current_lines:
        if line not in baseline_lines:
            parsed = parse_porcelain_line(line)
            if parsed and not _is_metadata_path(parsed[2]):
                return line

    return ""


def _session_changes_are_doc_only(project_dir: Path) -> bool:
    """Check if all non-metadata session changes are documentation (.md) files.

    Returns True if changes exist but are all .md files — used to skip
    the reflection gate for doc-only edits.
    """
    prawduct_dir = get_prawduct_dir(project_dir)
    baseline_path = prawduct_dir / ".session-git-baseline"

    current = git_status_output(project_dir)
    if current is None:
        return False

    baseline_lines: set[str] = set()
    if baseline_path.is_file():
        try:
            # Unstripped on both sides — see git_has_session_changes.
            baseline_lines = set(baseline_path.read_text().splitlines())
        except (UnicodeDecodeError, OSError):
            pass

    has_any = False
    for line in current.splitlines():
        if line in baseline_lines:
            continue
        parsed = parse_porcelain_line(line)
        if parsed is None:
            continue
        filepath = parsed[2]
        if _is_metadata_path(filepath):
            continue
        has_any = True
        if not filepath.endswith(".md"):
            return False

    return has_any


def git_has_code_changes(project_dir: Path) -> bool:
    """Check if non-metadata files were modified since session baseline.

    Mirrors git_has_session_changes() baseline-diff logic but returns a bool.
    Skips files that match the session baseline (pre-existing dirt) and
    framework metadata (.prawduct/, .claude/settings.json, etc.).
    """
    return bool(git_has_session_changes(project_dir))


def _is_framework_tooling(f: Path, project_dir: Path) -> bool:
    """True if ``f`` is Prawduct framework infrastructure shipped into a product
    repo (``tools/product-hook`` or ``tools/lib/*``), not the product's own code.

    Used by the "has product code?" heuristic so that sync-delivered tooling
    doesn't make a freshly-initialized empty repo look like it contains source.
    Deliberately NOT used by the compliance canary's source detection: in the
    framework repo itself these paths ARE the source under test.
    """
    try:
        rel = f.relative_to(project_dir).as_posix()
    except ValueError:
        return False
    return rel == "tools/product-hook" or rel.startswith("tools/lib/")


# Suffixes that count as the product's own source code. Shared by the
# project-preferences CRITICAL and the discovery-capture nudge in cmd_clear.
_PRODUCT_CODE_SUFFIXES = (
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".swift", ".kt",
    ".c", ".cpp", ".h",
)


def _has_product_code(project_dir: Path) -> bool:
    """True if the repo contains the product's OWN source code — not framework
    tooling, not ``.prawduct/`` state, not vendored deps. The single definition
    behind both the project-preferences CRITICAL and the discovery-capture nudge.
    """
    return any(
        f.suffix in _PRODUCT_CODE_SUFFIXES
        for f in project_dir.rglob("*")
        if f.is_file()
        and ".prawduct" not in f.parts
        and "node_modules" not in f.parts
        and f.name != "conftest.py"
        and not _is_framework_tooling(f, project_dir)
    )


# Conventional documentation roots prawduct recognizes — CLAUDE.md (and the
# MIG-6B0R backlog item) both name docs/ and documentation/ as real product-doc
# trees worth keeping on deploy-to-main.
_DOC_ROOTS = ("docs", "documentation")


def _has_product_definition_work(project_dir: Path) -> bool:
    """True if the repo shows deliberate product-definition work — source code OR
    markdown under a documentation root (``docs/`` or ``documentation/``).
    Distinguishes a repo someone has started building or specifying (worth a
    discovery nudge) from a freshly-onboarded empty repo (silent). A doc root is a
    deliberate user creation — ``init-product`` never scaffolds one — so markdown
    there is a real "product work happened" signal.
    """
    if _has_product_code(project_dir):
        return True
    for root in _DOC_ROOTS:
        d = project_dir / root
        if d.is_dir() and any(p.suffix == ".md" for p in d.rglob("*") if p.is_file()):
            return True
    return False


def _discovery_uncaptured(state_path: Path) -> bool:
    """True if ``project-state.yaml`` still carries BOTH template sentinels for the
    canonical discovery outputs — ``classification.domain`` and
    ``product_definition.vision`` both ``null``. Discovery filling either one
    clears its sentinel, so requiring BOTH is conservative: it fires only when
    discovery clearly never ran, never mid-discovery. Mirrors the parser-free
    substring heuristic the project-preferences unfilled check uses.
    """
    try:
        content = state_path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
    return "\n  domain: null\n" in content and "\n  vision: null\n" in content


def _read_advisory_store(prawduct_dir: Path) -> dict:
    """Read `.prawduct/.advisories.json` (the post-sync nag log).

    Dependency-light standalone reader: the briefing parses the store directly
    rather than importing the bundled advisory_store, so the hot path stays
    robust even on an incomplete plugin install. (cmd_clear's probe step DOES
    import advisory_store to refresh this file before the briefing is assembled.)
    Missing/unreadable/malformed → empty store; never raises (briefing must not
    break on a bad file).
    """
    path = prawduct_dir / ".advisories.json"
    if not path.is_file():
        return {"schema_version": 1, "advisories": []}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "advisories": []}
    if not isinstance(data, dict) or not isinstance(data.get("advisories"), list):
        return {"schema_version": 1, "advisories": []}
    return data


def _git_head_sha(project_dir: Path) -> str:
    """Return current HEAD SHA, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash hook
        pass
    return ""


def git_path_is_ignored(project_dir: Path, rel_path: str) -> bool:
    """True if ``rel_path`` is git-ignored within ``project_dir``.

    Used by the build-plan ref-existence check so an intentionally-gitignored
    managed path (e.g. ``.prawduct/.bug-inbox``) is not flagged as a missing
    deliverable (BLD-4K7P) — such paths are generated/managed and legitimately
    absent from a fresh checkout. Fail-closed: ``git check-ignore`` exits 0 when
    ignored, 1 when not, and 128 on error (e.g. not a git repo); any non-zero or
    exception returns False ("couldn't prove it's ignored"), so a genuinely
    missing path is still flagged rather than silently passed.
    """
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel_path],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        return result.returncode == 0
    except Exception:  # prawduct:allow prawduct/broad-except -- git failure must not crash the ref check
        return False


def _get_session_changed_files(project_dir: Path) -> list[str]:
    """Get files changed since session start. Returns list of file paths."""
    prawduct_dir = get_prawduct_dir(project_dir)
    current = git_status_output(project_dir)
    if current is None:
        return []

    baseline_path = prawduct_dir / ".session-git-baseline"
    baseline_lines: set[str] = set()
    if baseline_path.is_file():
        try:
            # Unstripped on both sides — see git_has_session_changes.
            baseline_lines = set(baseline_path.read_text().splitlines())
        except (UnicodeDecodeError, OSError):
            pass  # Corrupted baseline — same stance as the sibling readers above
    changed = []
    for line in current.splitlines():
        if line and line not in baseline_lines:
            parsed = parse_porcelain_line(line)
            if parsed:
                changed.append(parsed[2])
    return changed
