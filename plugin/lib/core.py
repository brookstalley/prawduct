"""
Core utilities and constants shared across the plugin's governance modules.

After the file-sync engine was retired in M4 (``MIG-M4-REMOVE``), the only
consumers of this module are the plugin-native governance commands — chiefly
``migrate_plugin`` (which derives its file-sync→plugin REMOVE set from the
``MANAGED_FILES`` / ``MANAGED_DIRS`` path registry) and ``init_product`` (which
renders the place-once product-state templates and seeds ``.gitignore``). The
sync/init/validate command layer that once lived in ``tools/lib/`` — and the
helper functions here that only served it (manifest building, settings merge,
template/skill placement, framework-dir resolution, vN gitignore migration) —
is gone.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The plugin root: ``<root>/lib/core.py`` → ``<root>``. The previous
# ``parent.parent.parent`` was a byte-parity holdover from the file-sync
# ``tools/lib/`` depth — it resolved one level ABOVE the plugin root, so
# ``TEMPLATES_DIR`` pointed at a nonexistent path and ``PRAWDUCT_VERSION``
# silently read ``"dev"``. Fixed in review-fixes Chunk 1 (the file-sync
# engine, the parity constraint's reason, was removed in M4).
FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"


# =============================================================================
# Constants
# =============================================================================

try:
    PRAWDUCT_VERSION = (FRAMEWORK_DIR / "VERSION").read_text().strip()
except FileNotFoundError:
    PRAWDUCT_VERSION = "dev"

BLOCK_BEGIN = "<!-- PRAWDUCT:BEGIN -->"
BLOCK_END = "<!-- PRAWDUCT:END -->"

# The framework-managed file path registry. These are the file-sync framework
# files a *consuming* repo carries; ``migrate_plugin`` derives the cutover
# REMOVE / edit-in-place set from this registry (CLAUDE.md + .claude/settings.json
# are edited, the rest are removed), and ``update_gitignore`` un-ignores them so
# they stay committed. The plugin never *places* these — it ships governance from
# its own ``skills/`` + ``methodology/`` — so only the paths matter; the file-sync
# template/strategy metadata retired with the engine.
MANAGED_FILES: frozenset[str] = frozenset({
    "CLAUDE.md",
    ".prawduct/critic-review.md",
    ".prawduct/pr-review.md",
    ".prawduct/build-governance.md",
    ".claude/skills/pr/SKILL.md",
    ".claude/skills/janitor/SKILL.md",
    ".claude/skills/prawduct-doctor/SKILL.md",
    ".claude/skills/learnings/SKILL.md",
    ".claude/skills/prawduct-advisory/SKILL.md",
    ".claude/skills/backlog/SKILL.md",
    ".claude/skills/critic/SKILL.md",
    "tools/product-hook",  # prawduct:allow prawduct/legacy-ref -- 1.x file-sync hook; migration removes it from the consumer
    ".claude/settings.json",
})

# Managed directories: every matching file is framework-owned. The sole consumer
# is ``migrate_plugin``, which globs the *consumer's* ``tools/lib`` so it removes
# that repo's full (possibly older) module set during the cutover onto the plugin.
MANAGED_DIRS: dict[str, dict] = {
    "tools/lib": {  # prawduct:allow prawduct/legacy-ref -- 1.x file-sync module dir; migration globs + removes it
        "glob": "*.py",
    },
}

# Session files that should be gitignored in product repos
GITIGNORE_ENTRIES = [
    ".claude/settings.local.json",
    ".prawduct/.bug-inbox",
    ".prawduct/.critic-active",
    ".prawduct/.critic-findings.json",
    ".prawduct/.critic-partials/",
    ".prawduct/.critic-partials-archive/",
    ".prawduct/.governance-ledger.jsonl",
    ".prawduct/.handoff-notes.md",
    ".prawduct/.test-evidence.json",
    ".prawduct/.pr-reviews/",
    ".prawduct/.session-base-tree",
    ".prawduct/.session-git-baseline",
    ".prawduct/.session-handoff.md",
    ".prawduct/.session-reflected",
    ".prawduct/.session-start",
    ".prawduct/.subagent-briefing.md",
    ".prawduct/.gates-waived",
    ".prawduct/.advisories.json",
    ".prawduct/.work-model-index.json",
    ".prawduct/reflections.md",
    "__pycache__/",
]

# Entries this list used to carry but that must now be TRACKED —
# update_gitignore strips them from existing repos and reports them so
# init-product/doctor can advise `git add`. Build plans (gate-soundness ch.3):
# a build plan is a durable, multi-session, release-spanning artifact — the
# methodology retains it through a gitflow release-pending window while
# tracked project-state.yaml points `active_build_plan:` at it. Ignoring it
# made every multi-clone repo carry a tracked pointer to a file the other
# clones don't have (scriob PR #43), and `_untrack_session_files` actively
# reverted any product that tracked its plan.
RETIRED_GITIGNORE_ENTRIES = [
    ".prawduct/artifacts/build-plan.md",
]


# =============================================================================
# Core utilities
# =============================================================================


def log(msg: str) -> None:
    """Print status to stderr."""
    print(msg, file=sys.stderr)


def atomic_write_text(
    path: Path, text: str, *, encoding: str = "utf-8", newline: str | None = None
) -> None:
    """Write ``text`` to ``path`` atomically: tmp sibling + ``os.replace``.

    ``encoding`` defaults to **utf-8**. It previously defaulted to ``None``,
    i.e. ``locale.getpreferredencoding(False)``, which made the round trip
    lossy on any non-UTF-8 locale and raised ``UnicodeEncodeError`` outright on
    non-ASCII content. That stayed latent only because the early callers wrote
    JSON at ``ensure_ascii=True``; ``.session-handoff.md`` does not, and it
    routinely carries em-dashes. The defect is invisible on a UTF-8 machine,
    which is why it survived so long — the guarding test forces the locale in a
    subprocess rather than asserting in-process.

    **The writer alone does not settle the round trip — each reader must ask
    for utf-8 too.** There are 11 call sites (four of them in the extensionless
    ``bin/prawduct-hook``, which a ``*.py``-filtered grep does not see), and
    their readers were not uniformly utf-8: ``operator_verification`` wrote
    through here and read back with a bare ``read_text()``. That pair was
    self-inverse while both used the locale encoding and became asymmetric the
    moment this default changed — transcoding a committed product file on the
    next status mutation. Fixed at that reader. Before adding a call site,
    check what reads the file back.

    ``newline`` still defaults to ``None`` (universal-newline translation) and
    is a separate concern: it exists for the one caller whose target is **not**
    framework state, where a write into a product's authored file must not
    re-line-end the bytes around its insertion.

    The shared writer for ``.prawduct/`` state files (STH-8M3V; same pattern
    as the hook's ``.test-evidence.json`` writer). Their readers fail open on
    a missing or corrupt file, so a torn write from two concurrent sessions
    on one repo degrades a gate silently rather than crashing — ``os.replace``
    guarantees every reader sees either the old content or the new, never a
    prefix. OSErrors propagate: each caller owns its failure policy
    (best-effort + stderr NOTE on the hook's session paths, a
    ``{status: error}`` return in ``advisory_store.write_store``). A stale
    ``.tmp`` sibling left by a crash between write and replace is harmless —
    the next write overwrites it.
    """
    tmp = path.with_name(path.name + ".tmp")
    # `open` rather than `write_text(newline=…)`: the latter wants Python 3.10+,
    # and the hook runs under whatever `python3` a product's PATH resolves to —
    # 3.9.6 on a stock macOS. `open` has taken both keywords since forever.
    with tmp.open("w", encoding=encoding, newline=newline) as handle:
        handle.write(text)
    os.replace(tmp, path)


# Optional project-state pointer naming the active build plan (relative to the
# `.prawduct/` dir). When unset, tooling uses the conventional default below, so
# repos that don't set it keep their existing behavior.
BUILD_PLAN_POINTER_KEY = "active_build_plan"
DEFAULT_BUILD_PLAN_REL = "artifacts/build-plan.md"


def read_str_yaml_key(state_path: Path, key: str) -> str | None:
    """Value of a top-level (column-0) ``key: value`` scalar, or None.

    Mirrors the column-0 idiom used by ``is_views_enabled`` and bin/prawduct-hook's
    ``_read_bool_yaml_key`` — no PyYAML dependency, fail-soft to None on a
    missing/unreadable file or absent key. Surrounding quotes and inline ``#``
    comments are stripped; an empty value, or the YAML null literal (``null`` /
    ``~``, case-insensitive), reads as None — so ``active_build_plan: null`` means
    "unset", the same opt-out :func:`lib.plan_index.parse_build_plan_frontmatter_scope`
    already honors for ``scope:`` (VWS-7N3K). Without this, a literal ``null``
    survived as the truthy string ``"null"`` and resolved to ``.prawduct/null``.
    """
    try:
        content = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    needle = f"{key}:"
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        value = line.split(":", 1)[1].strip().strip("\"'")
        if not value or value.lower() in ("null", "~"):
            return None
        return value
    return None


def read_bool_yaml_key(path: Path, key: str) -> bool:
    """True if ``path`` has a top-level (column-0) ``key: true`` scalar.

    The boolean sibling of ``read_str_yaml_key``, sharing the same no-PyYAML
    column-0 idiom but with boolean semantics: the value is lowercased and
    compared to ``"true"`` (quotes are *not* stripped — a quoted ``"true"``
    reads as False). Fail-soft to False on a missing/unreadable file, an absent
    key, or a malformed/indented line — opt-in by design.

    Factors out the scan shared by ``is_views_enabled`` (``views_enabled``) and
    bin/prawduct-hook's ``_read_bool_yaml_key`` (``coverage_required``); the
    latter stays an inline mirror (import-light hot path), pinned by a parity
    test.
    """
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    needle = f"{key}:"
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t"):
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line.startswith(needle):
            continue
        value = line.split(":", 1)[1].strip().lower()
        return value == "true"
    return False


def resolve_build_plan_path(prawduct_dir: Path) -> Path:
    """Resolve the active build-plan path (supports standard + scope-named plans).

    Reads an optional ``active_build_plan:`` pointer (a path relative to the
    ``.prawduct/`` dir) from ``project-state.yaml``; when set, that file is the
    active plan, letting a project name its plan by scope
    (``artifacts/v1.6.0-foo-plan.md``). When the pointer is absent, falls back to
    the conventional ``artifacts/build-plan.md`` — so repos that don't set it
    behave exactly as before. The returned path may not exist; callers treat a
    missing plan as "no active build plan."

    Kept in sync with the inline mirror in ``bin/prawduct-hook``
    (``_resolve_build_plan_path``), which cannot import this module in product
    repos — a parity test pins the two together.

    The pointer is ``.prawduct/``-relative, but the natural repo-relative
    spelling (``.prawduct/artifacts/x-plan.md``) is accepted by stripping the
    prefix — that spelling once shipped and silently disabled the gates for a
    work cycle (STH-5P2W).
    """
    pointer = read_str_yaml_key(prawduct_dir / "project-state.yaml", BUILD_PLAN_POINTER_KEY)
    if pointer and pointer.startswith(".prawduct/"):
        pointer = pointer[len(".prawduct/"):]
    if pointer:
        return prawduct_dir / pointer
    return prawduct_dir / DEFAULT_BUILD_PLAN_REL


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


# =============================================================================
# Template / file operations
# =============================================================================


def render_template(template_path: Path, subs: dict[str, str]) -> str:
    """Read a template file and apply variable substitutions."""
    content = template_path.read_text()
    for key, value in subs.items():
        content = content.replace(key, value)
    return content


def write_template(src: Path, dst: Path, subs: dict[str, str], *, overwrite: bool = False) -> bool:
    """Copy a template with variable substitution.

    Without overwrite: skips if dst exists.
    With overwrite: idempotent via content comparison.
    Returns True if file was written.
    """
    content = render_template(src, subs)

    if dst.is_file():
        if not overwrite:
            return False
        if dst.read_text() == content:
            return False  # Already up to date

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content)
    return True


def _contract_diff(existing_lines: set[str]) -> dict:
    """Pure gitignore-contract diff for a set of existing ``.gitignore`` lines.

    The single source of truth for what "satisfies the session-file contract"
    means, shared by :func:`update_gitignore` (which reads it to decide what to
    write) and the ``gitignore`` advisory probe (which reads
    :func:`gitignore_contract_drift` to decide whether to nudge) — so the nudge
    can never disagree with the fix. Returns
    ``{"missing", "incorrectly_ignored"}``: session entries that SHOULD be ignored
    but aren't, and managed/retired entries that ARE ignored but shouldn't be.
    Both empty ⇔ :func:`update_gitignore` makes no change (its ``modified``
    condition is exactly ``missing or incorrectly_ignored``). The two entry sets
    are disjoint (session files to ignore vs. managed files to commit), so the
    order in which the fixer removes then adds never affects either set.
    """
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    incorrectly_ignored = sorted(
        e for e in (*MANAGED_FILES, *RETIRED_GITIGNORE_ENTRIES) if e in existing_lines
    )
    return {"missing": missing, "incorrectly_ignored": incorrectly_ignored}


def gitignore_contract_drift(target: Path) -> dict:
    """Read-only: how ``target``'s ``.gitignore`` diverges from the contract.

    Reads ``target/.gitignore`` (a missing or unreadable file reads as empty, so
    every session entry then counts as ``missing``) and returns the
    :func:`_contract_diff` result. Never mutates and never raises on a missing
    file — the ``gitignore`` advisory probe calls this on every session start, so
    it must be cheap and side-effect-free.
    """
    gitignore = target / ".gitignore"
    try:
        existing_lines = set(gitignore.read_text().splitlines())
    except OSError:
        existing_lines = set()
    return _contract_diff(existing_lines)


def update_gitignore(target: Path) -> dict:
    """Add prawduct entries to .gitignore and remove incorrect ones.

    Managed files (MANAGED_FILES) should be committed, not gitignored.
    Session files (GITIGNORE_ENTRIES) should be gitignored.
    Returns dict with 'modified' bool and 'unignored' list of paths
    that were removed from .gitignore (caller should advise user to
    git-add these).
    """
    gitignore = target / ".gitignore"

    if gitignore.is_file():
        content = gitignore.read_text()
        existing_lines = set(content.splitlines())
    else:
        content = ""
        existing_lines = set()

    modified = False
    unignored: list[str] = []

    # Shared contract diff (single source of truth with the advisory probe):
    # managed/retired entries wrongly ignored, and session entries still missing.
    # The sets are disjoint, so computing both up front (before the removal
    # mutates the file) yields the same result as the sequential passes below.
    diff = _contract_diff(existing_lines)
    incorrectly_ignored = set(diff["incorrectly_ignored"])
    missing = diff["missing"]

    # Remove lines that gitignore managed files (they should be committed) —
    # plus retired entries the framework used to write itself (tracked-by-
    # default build plans, gate-soundness ch.3).
    if incorrectly_ignored:
        lines = content.splitlines(keepends=True)
        filtered = [line for line in lines if line.rstrip("\n") not in incorrectly_ignored]
        content = "".join(filtered)
        unignored = sorted(incorrectly_ignored)
        modified = True

    # Add missing session file entries
    if missing:
        parts = []
        if content and not content.endswith("\n"):
            parts.append("\n")
        if content.strip():
            parts.append("\n")
        parts.append("# Prawduct session files\n")
        for entry in missing:
            parts.append(entry + "\n")
        content += "".join(parts)
        modified = True

    if modified:
        gitignore.write_text(content)

    return {"modified": modified, "unignored": unignored}
