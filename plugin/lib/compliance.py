"""Session-end compliance canary + its file classifiers for the runtime.

Extracted from ``bin/prawduct-hook`` (STH-9V4K, Chunk 4) — the lightweight
failure-detection pass the Stop hook runs at session end: it inspects the
session's changed files for dependency-without-manifest and reason-less
``prawduct:allow`` waivers, returning informational ``CANARY:`` findings.
Best-effort by design — every probe fails open (never crashes, never blocks
session end).

**Two of the original four checks were retired (#164), and what covers their
ground is named here rather than left to be rediscovered.** Both re-derived, per
language, rules that a linter or a reviewer already owns, so both false-positived
off Python/JS and failed open everywhere else — which is the opposite of what a
canary is for.

- *Source changed, no tests* is covered by **Critic Goal 1**, which judges test
  adequacy against the change rather than counting file suffixes. Its classifier
  (``_is_test_file``) did not recognize ``FooTests.swift``, so on any non-Python
  repo the check nagged every session about a gap that was not there.
- *Broad exception handling* is covered by **ruff** — ``E722`` and ``BLE001``,
  configured in this repo's ``pyproject.toml`` — and, for the judgment half
  (is this catch legitimate at a boundary?), by ``skills/critic/review-protocol.md``
  and the Enforcement table's "Error handling" row, which already assigns it to
  the Critic. The deleted implementation approximated that judgment with a
  three-line lookahead for a ``raise`` or a log call, and had no analogue at all
  for a language without exceptions.

The two survivors are the ones with no language judgment in them: check 1 below
asks a purely factual question (did a dependency manifest change alongside a
dependency file?), and check 2 is mechanical and already language-agnostic.

Depends only on its lib sibling ``gitstate`` (for ``_get_session_changed_files``
and ``get_prawduct_dir``) and, lazily, ``waivers`` (the shared pragma
recognizer), plus the stdlib — a clean DAG node (``gitstate`` ← ``compliance``).
The hook calls ``compliance_canary`` lazily via ``_compliance()``, keeping its
top level lib-free; the ``cmd_stop`` call site wraps it in a broad catch so a
canary failure can never block session end.

The file classifiers (``_is_source_file`` / ``_is_dependency_file``) move with
the canary — it is their only caller.
"""

from __future__ import annotations

from pathlib import Path

from . import gitstate


def _is_source_file(filepath: str) -> bool:
    """Check if a filepath looks like a source code file (not test, not config)."""
    p = Path(filepath)
    suffix = p.suffix

    if suffix not in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb", ".swift", ".kt", ".cs", ".c", ".cpp", ".h"):
        return False

    name = p.name
    if name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".test.ts", ".test.jsx", ".test.tsx", ".spec.js", ".spec.ts")):
        return False

    if filepath.startswith(".prawduct/"):
        return False

    return True


#: Dependency-declaration filenames, matched exactly.
#:
#: A table of names, deliberately — no grammar, no per-language parsing. Adding
#: an ecosystem here costs one line and cannot false-positive on the others,
#: which is why this check survived the #164 retirement that took the two
#: language-deriving ones with it.
_DEPENDENCY_FILENAMES = frozenset({
    "requirements.txt",     # Python (pip)
    "pyproject.toml",       # Python (PEP 621)
    "Pipfile",              # Python (pipenv)
    "package.json",         # JavaScript / TypeScript
    "Cargo.toml",           # Rust
    "go.mod",               # Go
    "Gemfile",              # Ruby
    "Package.swift",        # Swift (SwiftPM)
    "CMakeLists.txt",       # C / C++ (CMake)
})

#: Dependency-declaration suffixes, for ecosystems that name the file after the
#: project rather than after the tool. `.csproj`/`.sln` carry `<PackageReference>`
#: and the project list respectively, so either changing is a dependency change.
_DEPENDENCY_SUFFIXES = (".csproj", ".sln")   # .NET / C#


def _is_dependency_file(filepath: str) -> bool:
    """Check if a filepath is a dependency declaration file."""
    name = Path(filepath).name
    return name in _DEPENDENCY_FILENAMES or name.endswith(_DEPENDENCY_SUFFIXES)


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
    dep_changed = [f for f in changed if _is_dependency_file(f)]

    # 1. Dependency file changed without manifest update
    if dep_changed:
        prawduct_dir = gitstate.get_prawduct_dir(project_dir)
        manifest_path = prawduct_dir / "artifacts" / "dependency-manifest.md"
        dep_manifest_in_changes = any(f.endswith("dependency-manifest.md") for f in changed)
        if manifest_path.is_file() and not dep_manifest_in_changes:
            findings.append(
                f"CANARY: Dependency file(s) changed ({', '.join(dep_changed)}) "
                f"but dependency-manifest.md was not updated."
            )

    # 2. Reason-less prawduct:allow waivers (malformed — a waiver must say why)
    invalid_waiver_files = _check_invalid_waivers(project_dir, source_changed)
    if invalid_waiver_files:
        findings.append(
            f"CANARY: Reason-less prawduct:allow waiver in: {', '.join(invalid_waiver_files)}. "
            f"A waiver must state why it's intentional (see docs/waivers.md)."
        )

    return findings
