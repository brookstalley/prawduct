"""Tests for active build-plan resolution (v1.6.0 Chunk 06).

The build-plan-consuming tooling resolves the active plan via an optional
`active_build_plan:` pointer in project-state.yaml, falling back to the
conventional `artifacts/build-plan.md`. The resolver lives in lib/core.py
and is mirrored inline in bin/prawduct-hook (kept import-light on the hot path).
A parity test pins the two implementations together, like the GITIGNORE mirror.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re

import pytest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# lib resolver — the plugin's lib/core
import sys
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from lib import core as _mod  # noqa: E402
resolve_build_plan_path = _mod.resolve_build_plan_path
read_str_yaml_key = _mod.read_str_yaml_key
BUILD_PLAN_POINTER_KEY = _mod.BUILD_PLAN_POINTER_KEY
DEFAULT_BUILD_PLAN_REL = _mod.DEFAULT_BUILD_PLAN_REL

# chunk-ref parsing + verification moved to lib/buildplan_refs (STH-9V4K ch.3) —
# test the parsers where they now live, not via the hook (which only keeps a
# thin wrapper + the import-light resolver mirror, parity-tested below).
from lib import buildplan_refs as _bpr  # noqa: E402

# plugin-runtime inline mirror via SourceFileLoader (extensionless shebang script)
_hook_loader = importlib.machinery.SourceFileLoader("prawduct_hook_res", str(_ROOT / "bin" / "prawduct-hook"))
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_res", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


def _prawduct(tmp_path: Path, state: str = "") -> Path:
    p = tmp_path / ".prawduct"
    (p / "artifacts").mkdir(parents=True)
    (p / "project-state.yaml").write_text(state)
    return p


class TestResolveBuildPlanPath:
    def test_pointer_set_returns_pointed_file(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/v1.6.0-foo-plan.md\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "v1.6.0-foo-plan.md"

    def test_pointer_absent_falls_back_to_default(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "views_enabled: true\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "build-plan.md"

    def test_no_project_state_falls_back_to_default(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "build-plan.md"

    def test_pointer_to_missing_file_still_returned(self, tmp_path: Path):
        # The resolver returns the pointed path even if it doesn't exist;
        # callers treat a missing plan as "no active build plan".
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/gone-plan.md\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "gone-plan.md"
        assert not resolved.is_file()

    def test_repo_relative_pointer_accepted(self, tmp_path: Path):
        # STH-5P2W: the natural repo-relative spelling (".prawduct/artifacts/…")
        # resolves to the same file as the canonical .prawduct/-relative form —
        # it once shipped and silently disabled the gates for a work cycle.
        prawduct = _prawduct(
            tmp_path, "active_build_plan: .prawduct/artifacts/v1.6.0-foo-plan.md\n"
        )
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "v1.6.0-foo-plan.md"

    def test_prefix_stripped_only_at_start(self, tmp_path: Path):
        # The strip is a leading-prefix fix, not a path rewrite — an interior
        # ".prawduct/" segment is preserved verbatim.
        prawduct = _prawduct(
            tmp_path, "active_build_plan: artifacts/.prawduct/odd-plan.md\n"
        )
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / ".prawduct" / "odd-plan.md"

    def test_default_constant(self):
        assert DEFAULT_BUILD_PLAN_REL == "artifacts/build-plan.md"
        assert BUILD_PLAN_POINTER_KEY == "active_build_plan"


class TestReadStrYamlKey:
    def test_reads_top_level_scalar(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: artifacts/x-plan.md\nother: 1\n")
        assert read_str_yaml_key(p, "active_build_plan") == "artifacts/x-plan.md"

    def test_strips_quotes_and_comments(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text('active_build_plan: "artifacts/y-plan.md"  # the active one\n')
        assert read_str_yaml_key(p, "active_build_plan") == "artifacts/y-plan.md"

    def test_ignores_nested_key(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("nested:\n  active_build_plan: artifacts/z-plan.md\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_missing_key_returns_none(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("views_enabled: true\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_missing_file_returns_none(self, tmp_path: Path):
        assert read_str_yaml_key(tmp_path / "nope.yaml", "active_build_plan") is None


class TestProductHookMirrorParity:
    """The inline prawduct-hook resolver must match the lib resolver on the same
    inputs (same discipline as the GITIGNORE_ENTRIES mirror test)."""

    def test_constants_match(self):
        assert _hook._BUILD_PLAN_POINTER_KEY == BUILD_PLAN_POINTER_KEY
        assert _hook._DEFAULT_BUILD_PLAN_REL == DEFAULT_BUILD_PLAN_REL

    def test_pointer_set_parity(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/v1.6.0-foo-plan.md\n")
        assert _hook._resolve_build_plan_path(prawduct) == resolve_build_plan_path(prawduct)

    def test_pointer_absent_parity(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "views_enabled: true\n")
        assert _hook._resolve_build_plan_path(prawduct) == resolve_build_plan_path(prawduct)

    def test_repo_relative_pointer_parity(self, tmp_path: Path):
        # STH-5P2W: both resolvers strip the leading ".prawduct/" identically.
        prawduct = _prawduct(
            tmp_path, "active_build_plan: .prawduct/artifacts/v1.6.0-foo-plan.md\n"
        )
        assert _hook._resolve_build_plan_path(prawduct) == resolve_build_plan_path(prawduct)
        assert _hook._resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "v1.6.0-foo-plan.md"

    def test_str_key_parity(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text('active_build_plan: "artifacts/y-plan.md"  # c\n')
        assert _hook._read_str_yaml_key(p, "active_build_plan") == read_str_yaml_key(p, "active_build_plan")


class TestSessionGitignoreMirror:
    """The hook's inline ``_SESSION_GITIGNORED_PATHS`` (used by
    ``_untrack_session_files``) must stay in sync with ``core.GITIGNORE_ENTRIES``
    (the ``.gitignore`` writer's source). The two cover the same session-file set;
    the documented differences are that core additionally carries ``__pycache__/``
    and a trailing slash on ``.pr-reviews/`` (it writes ``.gitignore`` lines),
    while the hook uses bare paths (it feeds ``git ls-files`` untracking).

    Restores the parity test deleted with ``tests/test_coverage_gaps.py`` in M4 —
    without it the two lists drift silently, re-tracking a session file in one path
    while gitignoring it in the other.
    """

    def test_session_file_sets_match(self):
        hook_set = {p.rstrip("/") for p in _hook._SESSION_GITIGNORED_PATHS}
        core_session = {p.rstrip("/") for p in _mod.GITIGNORE_ENTRIES} - {"__pycache__"}
        assert hook_set == core_session

    def test_pycache_is_core_only(self):
        # core writes __pycache__/ to .gitignore; the hook never untracks it.
        assert any(p.rstrip("/") == "__pycache__" for p in _mod.GITIGNORE_ENTRIES)
        assert not any(p.rstrip("/") == "__pycache__" for p in _hook._SESSION_GITIGNORED_PATHS)


# --- build-plan chunk-heading parse guard (BLD-7P3K) ------------------------
#
# A plan that lists chunks in `## Status` as `- [ ] Chunk NN: ...` but writes
# their bodies as `#### Chunk NN:` (four-hash, e.g. nested under a `### Lane`
# grouping) silently defeats every `### Chunk ` parser in the codebase —
# verify-chunk-refs, `_parse_build_plan_chunk_type` (fail-closes the chunk
# type to `code`), and the `lib/critic_mode.py` plan-override. Nothing errors;
# governance just quietly stops resolving the chunk. These helpers mirror the
# production heading rule exactly (``lib/buildplan_refs.py`` — moved there in
# STH-9V4K ch.3): a heading counts only if it `startswith("### Chunk ")` AND
# carries a colon, with the leading-zero-tolerant ID before the colon.

# Status line: "- [ ] Chunk 01: ..." / "- [x] Chunk 01: ..." (checkbox + colon).
_STATUS_CHUNK_RE = re.compile(r"^- \[[ xX]\] Chunk (\S+):")


def _status_chunk_ids(content: str) -> list[str]:
    """Chunk IDs listed in the plan's ``## Status`` section, in order."""
    ids: list[str] = []
    in_status = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_status = stripped == "## Status"
            continue
        if not in_status:
            continue
        m = _STATUS_CHUNK_RE.match(line)
        if m:
            ids.append(m.group(1))
    return ids


def _parseable_body_chunk_ids(content: str) -> set[str]:
    """Leading-zero-normalized IDs of parseable ``### Chunk <id>:`` headings.

    Replicates the matcher the production parsers use: three-hash + ``Chunk ``
    + a colon. A ``#### Chunk`` (four-hash), a missing colon, or an em-dash
    heading is NOT counted — which is exactly the silent-defeat we guard.
    """
    found: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("### Chunk "):
            continue
        rest = stripped[len("### Chunk "):]
        if ":" not in rest:  # parsers split on ":" — no colon, no match
            continue
        head = rest.split(":", 1)[0].strip()
        found.add(head.lstrip("0") or "0")
    return found


def _assert_status_chunks_parse(content: str) -> None:
    """Every ``## Status`` chunk ID must resolve to a parseable body heading."""
    body = _parseable_body_chunk_ids(content)
    unresolved = [
        cid for cid in _status_chunk_ids(content)
        if (cid.lstrip("0") or "0") not in body
    ]
    assert not unresolved, (
        f"Status chunk IDs with no parseable `### Chunk <id>:` heading: "
        f"{unresolved}. A `#### Chunk`/missing-colon/wrong-depth heading "
        f"silently defeats the `### Chunk ` parsers — fix the heading depth/form."
    )


class TestActiveBuildPlanChunkHeadingsParse:
    """Guard: the active build plan's `## Status` chunk IDs each map to a
    parseable `### Chunk <id>:` body heading (three-hash, colon form).

    Scope is **test-only** for this batch; a runtime-check-for-any-product
    variant (the hook flagging the active plan at session start) is deferred —
    backlog BLD-7P3K.

    The live-active-plan guard is the primary requirement; the in-test fixtures
    keep the guard deterministic even when this worktree's active pointer is
    unset (the integrator sets it, so the live check dogfoods the cleanup-batch
    plan once merged).
    """

    def test_active_plan_status_chunks_have_parseable_headings(self):
        plan_path = resolve_build_plan_path(_ROOT / ".prawduct")
        if not plan_path.is_file():
            pytest.skip(f"no active build plan resolved at {plan_path}")
        content = plan_path.read_text()
        status_ids = _status_chunk_ids(content)
        if not status_ids:
            pytest.skip(f"active plan {plan_path.name} has no `## Status` chunk list")
        _assert_status_chunks_parse(content)

    def test_fixture_good_plan_passes(self):
        good = (
            "## Status\n"
            "- [ ] Chunk 01: AAA — do a thing\n"
            "- [x] Chunk 02: BBB — done thing\n"
            "## Build Chunks\n"
            "### Chunk 01: AAA — do a thing\n"
            "**Type:** code\n"
            "### Chunk 02: BBB — done thing\n"
            "**Type:** doc-only\n"
        )
        _assert_status_chunks_parse(good)  # no AssertionError

    def test_fixture_four_hash_heading_fails(self):
        # The exact bug: bodies written as `#### Chunk` under a `### Lane`.
        malformed = (
            "## Status\n"
            "- [ ] Chunk 01: AAA — do a thing\n"
            "## Build Chunks\n"
            "### Lane A\n"
            "#### Chunk 01: AAA — do a thing\n"
            "**Type:** code\n"
        )
        with pytest.raises(AssertionError):
            _assert_status_chunks_parse(malformed)

    def test_fixture_missing_colon_heading_fails(self):
        # `### Chunk 01 AAA` (no colon) — the parsers split on ":" and miss it.
        malformed = (
            "## Status\n"
            "- [ ] Chunk 01: AAA — do a thing\n"
            "## Build Chunks\n"
            "### Chunk 01 AAA — do a thing\n"
            "**Type:** code\n"
        )
        with pytest.raises(AssertionError):
            _assert_status_chunks_parse(malformed)


# =============================================================================
# BLD-8F2Q — verify-chunk-refs handles `path::symbol` tokens (path-only check)
# =============================================================================


def _project_with_chunk(tmp_path: Path, chunk_body: str) -> tuple[Path, Path]:
    """Create a project root with a one-chunk build-plan. Returns (project, prawduct)."""
    project = tmp_path / "proj"
    prawduct = project / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text("")
    plan = (
        "---\nartifact: build-plan\n---\n\n"
        "## Build Chunks\n\n"
        "### Chunk 01: a chunk\n\n"
        + chunk_body
        + "\n## Next Section\n"
    )
    (prawduct / "artifacts" / "build-plan.md").write_text(plan)
    return project, prawduct


class TestVerifyChunkRefsPathSymbol:
    def test_existing_path_symbol_reports_no_missing(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/views.py::is_views_enabled`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "views.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        # The stored ref is the PATH portion only — not the full `path::symbol`.
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/views.py"]
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_missing_path_symbol_reports_path_portion_only(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gone.py::foo`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/gone.py"]
        missing = _bpr._verify_chunk_refs(project, refs)
        assert len(missing) == 1
        # The missing-ref message names the path, not `lib/gone.py::foo`.
        assert missing[0]["ref"] == "lib/gone.py"

    def test_new_qualifier_with_symbol_is_forward_ref(self, tmp_path: Path):
        # `new `-prefixed path::symbol -> skipped (a file the chunk creates).
        project, prawduct = _project_with_chunk(
            tmp_path, "- creates new `lib/created.py::bar`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_path_and_path_symbol_same_line_dedup(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- see `lib/views.py` and `lib/views.py::sym`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "views.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        # Both collapse to one path existence-check.
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/views.py"]

    def test_plain_path_unchanged(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(tmp_path, "- see `docs/x.md`\n")
        (project / "docs").mkdir()
        (project / "docs" / "x.md").write_text("doc\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["docs/x.md"]
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_symbol_without_slashed_path_skipped(self, tmp_path: Path):
        # No `/` before `::` -> not a path reference (e.g. a bare class::method).
        project, prawduct = _project_with_chunk(
            tmp_path, "- the `SomeClass::method` helper\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []


# =============================================================================
# BLD-2R9X — verify-chunk-refs skips glob patterns written as prose
# =============================================================================


class TestVerifyChunkRefsGlobPaths:
    """A backticked token carrying a shell-glob metacharacter (`*`, `?`, `[`) is a
    glob written in prose (e.g. `docs/requirements/*.md` in a Tests bullet), not a
    literal file. The parser must skip it, not capture it as a `missing-ref`
    (BLD-2R9X) — a literal source path never contains glob metacharacters."""

    def test_star_glob_is_skipped(self, tmp_path: Path):
        # The exact shape from the filing: a Tests bullet naming a `*.md` set.
        project, prawduct = _project_with_chunk(
            tmp_path, "- Tests: uncaptured + `docs/requirements/*.md` present\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert refs["file_paths"] == []
        # And it produces no missing-ref at verification time.
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_question_mark_glob_is_skipped(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(tmp_path, "- see `src/foo?.py`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_bracket_glob_is_skipped(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(tmp_path, "- see `src/[abc].py`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_literal_path_alongside_glob_still_captured(self, tmp_path: Path):
        # Per-token filter: the glob is skipped while a real path on the SAME line
        # is still existence-checked (the fix doesn't drop the whole line).
        project, prawduct = _project_with_chunk(
            tmp_path, "- `lib/views.py` plus all `docs/*.md`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "views.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/views.py"]
        assert _bpr._verify_chunk_refs(project, refs) == []
