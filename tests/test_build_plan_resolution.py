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
import subprocess

import pytest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

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
from lib import plan_index as _plan_index  # noqa: E402

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
        prawduct = _prawduct(tmp_path, "coverage_required: true\n")
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

    def test_null_pointer_falls_back_to_default(self, tmp_path: Path):
        # VWS-7N3K: `active_build_plan: null` must behave like an absent pointer
        # (fall back to the default plan), NOT resolve to the phantom
        # `.prawduct/null` that mis-fired the STH-5P2W briefing guard.
        prawduct = _prawduct(tmp_path, "active_build_plan: null\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "build-plan.md"

    def test_default_constant(self):
        assert DEFAULT_BUILD_PLAN_REL == "artifacts/build-plan.md"
        assert BUILD_PLAN_POINTER_KEY == "active_build_plan"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


def _branch_repo(tmp_path: Path, branch: str, state: str = "") -> Path:
    """A real git work tree on ``branch``, with a ``.prawduct/`` inside it.

    Real git rather than a monkeypatch: the resolver asks git for the branch, and
    the detached-HEAD and no-work-tree cases only exist in git.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-qm", "seed")
    prawduct = repo / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(state)
    return repo


def _plan(prawduct: Path, rel: str, *, branch: str | None = None, artifact: str | None = "build-plan") -> Path:
    path = prawduct / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---"]
    if artifact is not None:
        fm.append(f"artifact: {artifact}")
    if branch is not None:
        fm.append(f"branch: {branch}")
    fm.append("---")
    path.write_text("\n".join(fm) + "\n\n## Status\n\n- [ ] Chunk 01: a chunk\n")
    return path


class TestBranchScopedResolution:
    """Precedence (1) the live plan claiming the checked-out branch, (2) the
    ``active_build_plan`` scalar, (3) the conventional default.

    The pointer is branch state kept in a product-level scalar: two concurrent
    branches conflict on that one line every time, and after the merge one plan
    is invisible to every pointer-resolved surface. Inverting it — the plan
    declares its branch — is what these pin.
    """

    def test_branch_claim_wins_over_the_scalar(self, tmp_path: Path):
        # Precedence is demonstrated against a scalar pointing SOMEWHERE ELSE.
        # Pointing it at the same plan would make both routes agree and test
        # nothing.
        repo = _branch_repo(
            tmp_path, "feat/x", "active_build_plan: artifacts/other-plan.md\n"
        )
        prawduct = repo / ".prawduct"
        _plan(prawduct, "other-plan.md")
        claimed = _plan(prawduct, "branch-plan.md", branch="feat/x")
        assert resolve_build_plan_path(prawduct) == claimed

    def test_scalar_still_wins_when_no_plan_claims_the_branch(self, tmp_path: Path):
        repo = _branch_repo(
            tmp_path, "feat/x", "active_build_plan: artifacts/other-plan.md\n"
        )
        prawduct = repo / ".prawduct"
        _plan(prawduct, "other-plan.md")
        _plan(prawduct, "branch-plan.md", branch="feat/somewhere-else")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "other-plan.md"

    def test_default_when_neither_claims_nor_points(self, tmp_path: Path):
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        _plan(prawduct, "branch-plan.md", branch="feat/other")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "build-plan.md"

    def test_a_repo_with_no_opt_in_is_unchanged(self, tmp_path: Path):
        # The compatibility contract: existing repos behave identically until a
        # plan opts in. Nothing here declares `branch:`, so both the scalar and
        # the default routes must answer exactly as they did before.
        repo = _branch_repo(
            tmp_path, "feat/x", "active_build_plan: artifacts/pointed-plan.md\n"
        )
        prawduct = repo / ".prawduct"
        _plan(prawduct, "pointed-plan.md")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "pointed-plan.md"

    def test_two_live_plans_claiming_one_branch_is_a_loud_error(self, tmp_path: Path):
        repo = _branch_repo(
            tmp_path, "feat/x", "active_build_plan: artifacts/other-plan.md\n"
        )
        prawduct = repo / ".prawduct"
        _plan(prawduct, "other-plan.md")
        _plan(prawduct, "a-plan.md", branch="feat/x")
        _plan(prawduct, "b-plan.md", branch="feat/x")
        with pytest.raises(_mod.AmbiguousPlanBranchError) as excinfo:
            resolve_build_plan_path(prawduct)
        # It must name BOTH candidates and the branch: an operator cannot act on
        # "ambiguous" alone, and falling back to the scalar here would be the
        # silent wrong-plan pick the refusal exists to prevent.
        message = str(excinfo.value)
        assert "feat/x" in message
        assert "a-plan.md" in message and "b-plan.md" in message

    def test_an_archived_plan_claims_nothing(self, tmp_path: Path):
        # Archiving ends the claim, which is what makes the move the whole
        # retirement step — no pointer to un-set afterwards.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        _plan(prawduct, "archive/old-plan.md", branch="feat/x")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "build-plan.md"

    def test_an_archived_twin_does_not_make_a_live_claim_ambiguous(self, tmp_path: Path):
        # The pair of the case above: the live plan still resolves, rather than
        # colliding with its own archived copy.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        _plan(prawduct, "archive/plan.md", branch="feat/x")
        live = _plan(prawduct, "plan.md", branch="feat/x")
        assert resolve_build_plan_path(prawduct) == live

    def test_detached_head_falls_through_to_the_scalar(self, tmp_path: Path):
        repo = _branch_repo(
            tmp_path, "feat/x", "active_build_plan: artifacts/other-plan.md\n"
        )
        prawduct = repo / ".prawduct"
        _plan(prawduct, "other-plan.md")
        _plan(prawduct, "branch-plan.md", branch="feat/x")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        _git(repo, "checkout", "-q", "--detach", head)
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "other-plan.md"

    def test_outside_a_work_tree_falls_through_to_the_scalar(self, tmp_path: Path):
        # No git at all: the claim cannot be evaluated, so the pre-existing
        # route answers rather than the resolver failing.
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/other-plan.md\n")
        _plan(prawduct, "branch-plan.md", branch="feat/x")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "other-plan.md"

    def test_a_non_plan_artifact_cannot_claim_a_branch(self, tmp_path: Path):
        # `branch:` on a design note must not make that note the document every
        # gate reads chunk Status from — it has no roster, so governance would
        # go quiet rather than fail.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        _plan(prawduct, "a-design-note.md", branch="feat/x", artifact="design")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "build-plan.md"

    def test_a_plan_declaring_no_artifact_type_may_still_claim(self, tmp_path: Path):
        # Inherits `plan_index`'s fail-safe direction: at least one real plan in
        # this repo declares no `artifact:` at all, so absence reads as a plan.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        claimed = _plan(prawduct, "typeless-plan.md", branch="feat/x", artifact=None)
        assert resolve_build_plan_path(prawduct) == claimed

    def test_a_nested_plan_can_claim(self, tmp_path: Path):
        # Discovery is recursive, as it is for `scope:` — repos that organize
        # plans as `plans/<id>/build-plan.md` are a surveyed real shape.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        claimed = _plan(prawduct, "plans/007/build-plan.md", branch="feat/x")
        assert resolve_build_plan_path(prawduct) == claimed

    def test_long_frontmatter_still_yields_its_claim(self, tmp_path: Path):
        # The bounded header read must not become a silent correctness knob: a
        # plan whose frontmatter exceeds the probe is re-read whole.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        path = prawduct / "artifacts" / "verbose-plan.md"
        filler = "\n".join(f"note_{i}: {'x' * 200}" for i in range(200))
        path.write_text(f"---\nartifact: build-plan\n{filler}\nbranch: feat/x\n---\n\n# P\n")
        assert len(path.read_text()) > _plan_index._FRONTMATTER_PROBE_CHARS
        assert resolve_build_plan_path(prawduct) == path

    def test_a_null_branch_claims_nothing(self, tmp_path: Path):
        repo = _branch_repo(
            tmp_path, "feat/x", "active_build_plan: artifacts/other-plan.md\n"
        )
        prawduct = repo / ".prawduct"
        _plan(prawduct, "other-plan.md")
        _plan(prawduct, "opted-out.md", branch="null")
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "other-plan.md"

    def test_a_nested_branch_key_does_not_claim(self, tmp_path: Path):
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        (prawduct / "artifacts" / "nested.md").write_text(
            "---\nartifact: build-plan\nwip:\n  branch: feat/x\n---\n\n# P\n"
        )
        assert resolve_build_plan_path(prawduct) == prawduct / "artifacts" / "build-plan.md"


class TestTheCliRefusesRatherThanGuessing:
    """The fail-closed posture, through the real binary.

    A refused gate is a blocked gate — the intended end state — but a traceback
    would be loud and unreadable, and the refusal already names its own remedy.
    Subprocess because ``main``'s wrapper and the lazy ``_core()`` lookup in its
    ``except`` clause exist only when the script is actually run.
    """

    _HOOK = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"

    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self._HOOK), *args],
            cwd=str(repo), capture_output=True, text=True,
        )

    def test_a_contested_branch_exits_nonzero_with_the_remedy(self, tmp_path: Path):
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        _plan(prawduct, "a-plan.md", branch="feat/x")
        _plan(prawduct, "b-plan.md", branch="feat/x")
        result = self._run(repo, "infer-critic-mode")
        assert result.returncode == 1, result.stdout
        assert "REFUSING" in result.stderr
        assert "a-plan.md" in result.stderr and "b-plan.md" in result.stderr
        # No traceback: the refusal is a message, not a crash.
        assert "Traceback" not in result.stderr

    def test_the_same_command_succeeds_once_one_claim_is_withdrawn(self, tmp_path: Path):
        # The control. Without it the assertion above is satisfied by any repo
        # shape that makes the command exit 1.
        repo = _branch_repo(tmp_path, "feat/x")
        prawduct = repo / ".prawduct"
        _plan(prawduct, "a-plan.md", branch="feat/x")
        _plan(prawduct, "b-plan.md")
        result = self._run(repo, "infer-critic-mode")
        assert result.returncode == 0, result.stderr
        assert "REFUSING" not in result.stderr


class TestBranchClaimParsing:
    def test_reads_the_claim(self):
        assert _plan_index.parse_build_plan_frontmatter_branch(
            "---\nartifact: build-plan\nbranch: feat/x\n---\n"
        ) == "feat/x"

    def test_strips_quotes_and_comments(self):
        assert _plan_index.parse_build_plan_frontmatter_branch(
            '---\nbranch: "feat/x"  # the branch this plan governs\n---\n'
        ) == "feat/x"

    def test_tolerates_a_leading_html_comment_header(self):
        # A third of this repo's plans open with one, and the template does too.
        assert _plan_index.parse_build_plan_frontmatter_branch(
            "<!-- header -->\n---\nbranch: feat/x\n---\n"
        ) == "feat/x"

    def test_absent_key_reads_as_no_claim(self):
        assert _plan_index.parse_build_plan_frontmatter_branch(
            "---\nartifact: build-plan\n---\n"
        ) is None

    @pytest.mark.parametrize("literal", ["null", "~", "NULL", ""])
    def test_null_literals_read_as_no_claim(self, literal: str):
        assert _plan_index.parse_build_plan_frontmatter_branch(
            f"---\nbranch: {literal}\n---\n"
        ) is None

    def test_a_key_merely_starting_with_branch_does_not_match(self):
        assert _plan_index.parse_build_plan_frontmatter_branch(
            "---\nbranches: feat/x\nbranch_base: develop\n---\n"
        ) is None

    def test_outside_the_frontmatter_does_not_claim(self):
        assert _plan_index.parse_build_plan_frontmatter_branch(
            "---\nartifact: build-plan\n---\n\nbranch: feat/x\n"
        ) is None

    def test_no_frontmatter_at_all(self):
        assert _plan_index.parse_build_plan_frontmatter_branch("# Just a doc\n") is None


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
        p.write_text("coverage_required: true\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_missing_file_returns_none(self, tmp_path: Path):
        assert read_str_yaml_key(tmp_path / "nope.yaml", "active_build_plan") is None

    def test_null_literal_reads_as_none(self, tmp_path: Path):
        # VWS-7N3K: the YAML null literal is the canonical "no active plan" form;
        # it must read as unset, not as the truthy string "null".
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: null\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_tilde_literal_reads_as_none(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: ~\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_null_literal_case_insensitive(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: NULL\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_null_with_inline_comment_reads_as_none(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: null  # no plan between build plans\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_value_containing_null_substring_preserved(self, tmp_path: Path):
        # Only the bare null/~ literal normalizes — a real path that merely
        # contains "null" is a value, not the opt-out.
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: artifacts/nullable-plan.md\n")
        assert read_str_yaml_key(p, "active_build_plan") == "artifacts/nullable-plan.md"


class TestProductHookMirrorParity:
    """The inline prawduct-hook scalar reader must match the lib one on the same
    inputs (same discipline as the GITIGNORE_ENTRIES mirror test).

    The RESOLVER half of this mirror is gone. ``_resolve_build_plan_path`` lost
    its last caller when ``staleness_scan`` moved to ``lib/briefing.py`` and was
    rewritten onto ``core.resolve_build_plan_path``, so the cases deleted here
    pinned two implementations of which only one was ever run — and branch-scoped
    resolution would have meant duplicating a directory walk and a git subprocess
    into the unreachable one. What is asserted instead is that the mirror is
    really gone, so a future edit cannot quietly restore the duplicate.

    ``_read_str_yaml_key`` STAYS: it has four live callers in the hook, and its
    parity cases below are unchanged.
    """

    def test_the_resolver_mirror_is_retired(self):
        # Deletion is the contract now. A reinstated inline resolver is a second
        # implementation of branch precedence that nothing calls and nothing
        # would notice drifting.
        assert not hasattr(_hook, "_resolve_build_plan_path")
        assert not hasattr(_hook, "_BUILD_PLAN_POINTER_KEY")
        assert not hasattr(_hook, "_DEFAULT_BUILD_PLAN_REL")

    def test_the_lib_constants_are_still_the_contract(self):
        # They were asserted through the mirror; they are still the public names
        # every consumer reads, so they keep a home here.
        assert DEFAULT_BUILD_PLAN_REL == "artifacts/build-plan.md"
        assert BUILD_PLAN_POINTER_KEY == "active_build_plan"

    def test_str_key_parity(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text('active_build_plan: "artifacts/y-plan.md"  # c\n')
        assert _hook._read_str_yaml_key(p, "active_build_plan") == read_str_yaml_key(p, "active_build_plan")

    def test_str_key_null_parity(self, tmp_path: Path):
        # VWS-7N3K: both mirrors normalize the YAML null literal to None.
        for literal in ("null", "~", "NULL"):
            p = tmp_path / "s.yaml"
            p.write_text(f"active_build_plan: {literal}\n")
            assert _hook._read_str_yaml_key(p, "active_build_plan") is None
            assert _hook._read_str_yaml_key(p, "active_build_plan") == read_str_yaml_key(
                p, "active_build_plan"
            )


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
    """Leading-zero-normalized IDs of chunk headings **the production parser accepts**.

    #211: this used to REPLICATE the matcher (hard-coded three-hash + a literal
    colon) and had drifted strictly narrower than production, which accepts
    ``##`` or ``###`` and any of ``: — – ( -`` or end-of-line
    (``_CHUNK_HEADING_RE``, broadened by BLD-5J8N for the em-dash research-plan
    form). A guard narrower than the thing it guards fails plans that parse
    perfectly well.

    The fix is to CONSUME the production regex rather than widen a copy of it —
    `plugin/lib/buildplan_refs.py` owns the chunk-heading contract, and a second
    implementation of an owned contract is what drifted in the first place. Do
    NOT re-narrow `_CHUNK_ID_SEP` to match what this used to accept: that would
    re-break the em-dash form on purpose enabled earlier.
    """
    found: set[str] = set()
    for line in content.splitlines():
        match = _bpr._CHUNK_HEADING_RE.match(line.strip())
        if match:
            found.add(match.group(1).lstrip("0") or "0")
    return found


def _assert_status_chunks_parse(content: str) -> None:
    """Every ``## Status`` chunk ID must resolve to a parseable body heading."""
    body = _parseable_body_chunk_ids(content)
    unresolved = [
        cid for cid in _status_chunk_ids(content)
        if (cid.lstrip("0") or "0") not in body
    ]
    assert not unresolved, (
        f"Status chunk IDs with no parseable chunk heading: {unresolved}. "
        f"`buildplan_refs._CHUNK_HEADING_RE` accepts `##` or `###` + `Chunk "
        f"<id>` + one of `: — – ( -` or end-of-line; a `#### Chunk` (wrong "
        f"depth) or a separator outside that set silently defeats every chunk "
        f"parser — fix the heading depth/form."
    )


class TestGuardMatchesProductionHeadingContract:
    """#211: the guard must not be narrower than the parser it guards.

    It replicated the matcher as three-hash + a literal colon while production
    accepted `##`/`###` and five separators, so a plan using an authoring form
    the runtime parses fine failed the guard. Consuming `_CHUNK_HEADING_RE`
    makes the drift structurally impossible; these cases pin that it is really
    consumed, so re-introducing a copy fails here.
    """

    @pytest.mark.parametrize(
        "heading",
        [
            "### Chunk 01: Name",
            "## Chunk 01: Name",
            "### Chunk 01 — Name",
            "## Chunk 01 — Name",
            "### Chunk 01 – Name",
            "### Chunk 01 (adapter)",
            "### Chunk 01 - Name",
            "### Chunk 01",
            # The leading checkbox: a plan that carries its roster's tick marks
            # into the body headings.
            "### [ ] Chunk 01: Name",
            "### - [x] Chunk 01 — Name",
        ],
    )
    def test_production_accepted_forms_are_accepted_by_the_guard(self, heading: str):
        assert _parseable_body_chunk_ids(heading + "\n") == {"1"}

    def test_a_dotted_id_survives_normalization_intact(self):
        # Sub-chunk numbering: the guard normalizes leading zeros only, so the
        # dot must reach the comparison — `1.2` folding to `1` would silently
        # resolve a Status entry against the wrong chunk's heading.
        assert _parseable_body_chunk_ids("### Chunk 01.2: Name\n") == {"1.2"}

    def test_wrong_depth_is_still_rejected(self):
        # The silent-defeat the guard exists for: `####` is outside `#{2,3}`.
        assert _parseable_body_chunk_ids("#### Chunk 01: Name\n") == set()


class TestChunkLineForms:
    """The Status-line matcher must accept every form plans actually write.

    This class once pinned an AGREEMENT between two matchers — the derived-view
    module matched the Status line to flip its box, `buildplan_refs` parsed the
    id out of the same line, and widening one side alone was a new defect rather
    than a partial fix: a bold Status line whose box flipped but whose id could
    not be parsed made the plan read as having NO current chunk, so
    `verify-chunk-refs` exited 0 having verified nothing — strictly worse than
    the uniformly-invisible pre-state.

    There is one matcher now, so the two cannot disagree. What survives is the
    obligation that made the disagreement matter: every form a plan author
    writes must parse. The bold form is in the list because it is the one that
    was silently unparseable.
    """

    @pytest.mark.parametrize(
        "item_text,expected",
        [
            ("Chunk 01: A", "01"),
            ("Chunk 01 — A", "01"),
            ("**Chunk 01** — A", "01"),
            ("**Chunk 01**: A", "01"),
            ("Chunk 01", "01"),
        ],
    )
    def test_item_matcher_accepts_every_status_form(self, item_text: str, expected: str):
        assert _bpr._chunk_id_from_item_text(item_text) == expected

    def test_a_bold_status_line_resolves_end_to_end(self):
        """The end-to-end shape of the original defect, now single-sided: the id
        must come out of a real Status line including its `- [ ] ` prefix."""
        line = "- [ ] **Chunk 03** — the adapter"
        items = list(_bpr._iter_status_section_items(f"## Status\n\n{line}\n"))
        assert items == [(False, "**Chunk 03** — the adapter")]
        assert _bpr._chunk_id_from_item_text(items[0][1]) == "03"


class TestGitRefPrefixes:
    """#333: `missing-ref:` is BLOCKING, so a branch name in plan prose that is
    not recognized as a ref fails a review on the branch name itself."""

    @pytest.mark.parametrize(
        "token",
        [
            "feat/backlog-burndown",
            "chore/deps",
            "refactor/views",
            "perf/pacer",
            "ci/matrix",
            "wip/spike",
            "dependabot/pip/urllib3-2.0.7",
            "renovate/lock-file-maintenance",
            # pre-existing git-flow coverage must not regress
            "feature/upgrade-discovery-relay",
            "release/v3.2.0",
            "origin/develop",
        ],
    )
    def test_branch_token_is_not_treated_as_a_file_path(self, token: str):
        assert not _bpr._looks_like_file_path(token)

    @pytest.mark.parametrize(
        "token",
        [
            # A real extensionless path under a ref-shaped first segment stays
            # checked only when it carries an extension — this is the coverage
            # the rejected shape-rule alternative would have dropped wholesale.
            "feat/module.py",
            "ci/config.yml",
            # Ordinary source paths are unaffected.
            "plugin/lib/plan_index.py",
            "documentation/release-process.md",
            # THE load-bearing case for rejecting the shape-rule alternative:
            # this repo's most-cited path carries no extension, so "a token is a
            # path only if its final segment looks like a filename" would stop
            # verifying it. If this ever stops being checked, the rationale in
            # `_GIT_REF_PREFIXES` is void and needs rewriting, not patching.
            "plugin/bin/prawduct-hook",
        ],
    )
    def test_real_paths_are_still_checked(self, token: str):
        assert _bpr._looks_like_file_path(token)


class TestActiveBuildPlanChunkHeadingsParse:
    """Guard: the active build plan's `## Status` chunk IDs each map to a body
    heading the production parser accepts (`buildplan_refs._CHUNK_HEADING_RE` —
    `##`/`###` plus any of `: — – ( -` or end-of-line, consumed here rather than
    replicated; #211).

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


def _project_with_status_and_chunk(
    tmp_path: Path, status: str, chunk_body: str
) -> tuple[Path, Path]:
    """Like `_project_with_chunk` but with a real `## Status` roster, so
    `resolve_chunk_progress` has something to read."""
    project = tmp_path / "proj"
    prawduct = project / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text("")
    plan = (
        "---\nartifact: build-plan\n---\n\n"
        f"## Status\n\n{status}\n"
        "## Build Chunks\n\n"
        "### Chunk 01: a chunk\n\n" + chunk_body + "\n## Next Section\n"
    )
    (prawduct / "artifacts" / "build-plan.md").write_text(plan)
    return project, prawduct


class TestUntickedChunkNoticeNarrowing:
    """The tripwire's silence conditions, in a NON-git tree.

    This class replaces one that pinned the opposite notice: when the retired
    git-derived reading bailed, the checkbox reading taking over was the one
    known to be wrong, and nothing said so. The checkbox reading is now simply
    correct, so that notice has no subject. What remains worth pinning is the
    narrowing — the successor control must stay quiet unless it has something to
    say, since a control that fires on every session stops being read
    (`nonfunctional-requirements.md` § Direction).

    Deliberately non-git fixtures: they exercise the paths where the tripwire has
    no evidence at all. Its POSITIVE behaviour needs real commits and is pinned
    in `test_handoff_parser_correctness.py` against real `git init` repos.
    """

    def _repo(self, tmp_path: Path, *, status: str) -> Path:
        project = tmp_path / "proj"
        prawduct = project / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text("base_branch: main\n")
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "---\nartifact: build-plan\n---\n\n"
            f"## Status\n\n{status}\n"
            "## Build Chunks\n\n### Chunk 01: a chunk\n\n- does a thing\n"
        )
        return project

    def test_silent_outside_a_git_work_tree(self, tmp_path: Path):
        # No git, so no commits to compare the boxes against. Silence is the
        # honest answer; a claim here would be manufactured from nothing.
        project = self._repo(tmp_path, status="- [ ] Chunk 01: a chunk\n")
        assert _bpr.unticked_committed_chunk_notice(project) is None

    def test_silent_when_there_is_no_plan(self, tmp_path: Path):
        project = tmp_path / "proj"
        (project / ".prawduct" / "artifacts").mkdir(parents=True)
        (project / ".prawduct" / "project-state.yaml").write_text("base_branch: main\n")
        assert _bpr.unticked_committed_chunk_notice(project) is None

    def test_silent_when_the_plan_has_no_status_roster(self, tmp_path: Path):
        # "plan read, nothing to compare" must be distinguishable from "no plan".
        project = self._repo(tmp_path, status="")
        assert _bpr.unticked_committed_chunk_notice(project) is None

    def test_silent_when_every_box_is_ticked(self, tmp_path: Path):
        # Nothing unticked means nothing to report, before git is consulted at
        # all — the cheap exit that keeps this off the cost budget.
        project = self._repo(tmp_path, status="- [x] Chunk 01: a chunk\n")
        assert _bpr.unticked_committed_chunk_notice(project) is None

    def test_the_token_is_stable_and_greppable(self):
        # The proportionality norm: a control whose findings are printed and
        # forgotten can never be retired on evidence, so the token is a stable
        # literal rather than a reworded sentence. This control is NEW, so it
        # owes that evidence from the start.
        assert _bpr.UNTICKED_CHUNK_TOKEN == "unticked-committed-chunk"


class TestChunkRefWaiver:
    """A chunk body DISCUSSES paths as well as declaring them, and a backtick
    scan cannot tell the two apart.

    The forcing case: a carried-in review observation naming the path a past
    defect was about — a scan root that never existed on any branch. The prose
    is correct *because* the path is missing, so the check fires on every future
    run and the only escapes are to launder the record to satisfy the linter or
    to carry a permanent blocking finding. The exemption is the repo's ordinary
    waiver pragma, so it demands a reason and stays visible where it applies.
    """

    _REASON = "the path is the SUBJECT of a recorded defect, not a deliverable"

    def test_a_waived_line_contributes_no_refs(self, tmp_path: Path):
        _project, prawduct = _project_with_chunk(
            tmp_path,
            f"- <!-- prawduct:allow prawduct/chunk-ref-missing -- {self._REASON} -->\n"
            "  the `lib/never_existed.py` scan root\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_the_same_line_without_the_waiver_still_reports(self, tmp_path: Path):
        """The paired positive. Without it, the test above is satisfied by an
        extractor that stopped reporting anything at all."""
        _project, prawduct = _project_with_chunk(
            tmp_path, "- the `lib/never_existed.py` scan root\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/never_existed.py"]

    def test_a_reasonless_waiver_does_not_waive(self, tmp_path: Path):
        """`waivers.line_waives` requires a reason, and this check must inherit
        that rather than accept a bare pragma — an unexplained exemption is the
        thing the waiver mechanism exists to prevent."""
        _project, prawduct = _project_with_chunk(
            tmp_path,
            "- <!-- prawduct:allow prawduct/chunk-ref-missing -->\n"
            "  the `lib/never_existed.py` scan root\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/never_existed.py"]

    def test_the_waiver_does_not_leak_to_other_lines(self, tmp_path: Path):
        """Scoped to the line it sits on (and the one below, per `waivers.waives`)
        — a chunk-wide exemption would silently stop checking real deliverables."""
        _project, prawduct = _project_with_chunk(
            tmp_path,
            f"- <!-- prawduct:allow prawduct/chunk-ref-missing -- {self._REASON} -->\n"
            "  the `lib/never_existed.py` scan root\n"
            "\n"
            "- touches `lib/also_missing.py`\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/also_missing.py"]

    def test_an_unrelated_rule_id_does_not_waive(self, tmp_path: Path):
        _project, prawduct = _project_with_chunk(
            tmp_path,
            "- <!-- prawduct:allow prawduct/broad-except -- unrelated -->\n"
            "  the `lib/never_existed.py` scan root\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/never_existed.py"]


class TestNewQualifierExpiry:
    """#224(a): `new `path`` is a forward reference only while the chunk is open.

    An exemption that never expires means a chunk can promise to create a file,
    not create it, and never be caught.
    """

    def test_exemption_holds_while_the_chunk_is_open(self, tmp_path: Path):
        _project, prawduct = _project_with_status_and_chunk(
            tmp_path,
            "- [ ] Chunk 01: a chunk\n",
            "- creates new `lib/created.py`\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_exemption_expires_once_the_chunk_is_complete(self, tmp_path: Path):
        _project, prawduct = _project_with_status_and_chunk(
            tmp_path,
            "- [x] Chunk 01: a chunk\n",
            "- creates new `lib/created.py`\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/created.py"]

    def test_uncertain_completion_fails_toward_the_exemption(self, tmp_path: Path):
        # No `## Status` roster at all — nothing to reason about, so nothing
        # expires. A false missing-ref fires on every review of an open chunk;
        # a missed one surfaces at the next verify.
        _project, prawduct = _project_with_chunk(
            tmp_path, "- creates new `lib/created.py`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_non_contiguous_roster_never_expires_an_open_chunk(
        self, tmp_path: Path
    ):
        # `- [x] 01, - [ ] 02, - [x] 03` on the CHECKBOX path. This roster is
        # chosen to be wrong under BOTH rival rules, and each assertion below
        # kills a different one:
        #   * a count-slice (`progress.complete` is 2) names 01 and 02, expiring
        #     the exemption on 02 — which is OPEN;
        #   * a uniform prefix-before-`current_id` names only 01, letting 03 —
        #     which is CHECKED, i.e. done under the reading in force — keep an
        #     exemption it has no claim to.
        # So on this path the `checked` flags are read directly — which is now
        # the ONLY path: the git-derived reading this sentence used to contrast
        # against was retired with the derived-view model, and the test it named
        # went with it. Kept as the reason the flags are read directly rather
        # than rewritten away, because the alternative it rejects is the one a
        # future reader would otherwise re-propose.
        project = tmp_path / "proj"
        prawduct = project / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text("")
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "---\nartifact: build-plan\n---\n\n"
            "## Status\n\n"
            "- [x] Chunk 01: first\n- [ ] Chunk 02: open\n- [x] Chunk 03: later\n\n"
            "## Build Chunks\n\n"
            "### Chunk 02: open\n\n- creates new `lib/open.py`\n\n"
            "### Chunk 03: later\n\n- creates new `lib/later.py`\n"
        )
        # Chunk 02 is OPEN — exempt under any correct rule. This is the
        # assertion the count-slice defect breaks.
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "02")["file_paths"] == []
        # Chunk 03 is CHECKED, i.e. complete under the reading actually in force,
        # but it sits AFTER `current_id`. A uniform prefix-before-current rule
        # under-reports it and lets it keep an exemption it has no claim to —
        # so on the checkbox path the `checked` flags are read directly, and
        # this is the assertion that tells the two rules apart.
        refs03 = _bpr._parse_build_plan_chunk_refs(prawduct, "03")
        assert [r["ref"] for r in refs03["file_paths"]] == ["lib/later.py"]

    # `test_git_derived_reading_drives_the_expiry_when_boxes_are_unflipped` stood
    # here. It pinned the count-slice defect, which existed only on the retired
    # git-derived reading: there `progress.complete` was a bare COUNT and slicing
    # a non-contiguous roster by it expired the exemption on the OPEN chunk. With
    # one reading the `checked` flag is per-item and exact, so the defect has no
    # route back. The non-contiguous case itself is still covered — by the
    # checkbox test directly above, which is where it now belongs.

    def test_unparseable_roster_entry_fails_toward_the_exemption(
        self, tmp_path: Path
    ):
        _project, prawduct = _project_with_status_and_chunk(
            tmp_path,
            "- [x] Chunk 01: a chunk\n- [x] not a chunk line at all\n",
            "- creates new `lib/created.py`\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_completed_chunk_still_exempts_a_file_that_now_exists(
        self, tmp_path: Path
    ):
        # Expiry is not "always report" — the file the chunk promised was
        # created, so there is nothing to report.
        project, prawduct = _project_with_status_and_chunk(
            tmp_path,
            "- [x] Chunk 01: a chunk\n",
            "- creates new `lib/created.py`\n",
        )
        (project / "lib").mkdir()
        (project / "lib" / "created.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        # The ref is now CHECKED (the exemption expired)...
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/created.py"]
        # ...and passes, because the chunk really did create it. Expiry surfaces
        # the ref for verification; it does not assert the file is missing.
        assert _bpr._verify_chunk_refs(project, refs) == []


class TestRemovalQualifier:
    """A deliverable declared as a REMOVAL is satisfied by absence.

    Without this the check is structurally unable to pass a retirement chunk: it
    asserts existence for every backticked deliverable ref, so a chunk whose job
    is deleting `x.py` reports `missing-ref: x.py` **because it succeeded** — at
    BLOCKING severity, so the work cannot be closed honestly. It bit this repo's
    own derived-views retirement, on three refs at once.
    """

    def test_verb_before_the_path_exempts(self, tmp_path: Path):
        _project, prawduct = _project_with_chunk(
            tmp_path, "- deleted `lib/gone.py` — the derived-view module\n"
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []

    @pytest.mark.parametrize("phrase", ["deleted", "removed", "retired", "is deleted", "are removed"])
    def test_verb_after_the_path_exempts(self, tmp_path: Path, phrase: str):
        """Both orders, because both read naturally in a Deliverables line and a
        plan author should not have to know which one the parser prefers."""
        _project, prawduct = _project_with_chunk(
            tmp_path, f"- `lib/gone.py` {phrase} here\n"
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []

    def test_wrapped_list_item_continuation_still_exempts(self, tmp_path: Path):
        _project, prawduct = _project_with_chunk(
            tmp_path,
            "- **Deliverables:**\n"
            "  - the machinery goes, which means\n"
            "    deleted `lib/gone.py` alongside its tests\n",
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []

    def test_narrative_prose_does_not_exempt(self, tmp_path: Path):
        """Same narrowing as `new`, for the same reason: one sentence mentioning
        a deletion must not exempt a real deliverable for the whole chunk."""
        _project, prawduct = _project_with_chunk(
            tmp_path,
            "Context: this follows the run that deleted `lib/gone.py` last week.\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/gone.py"]

    def test_an_undeclared_missing_path_is_still_reported(self, tmp_path: Path):
        """The exemption must be NARROW — the control's whole value is catching a
        deliverable that was promised and skipped. A removal declaration for one
        path must not blanket the item it sits in.
        """
        project, prawduct = _project_with_chunk(
            tmp_path, "- deleted `lib/gone.py`, and `lib/promised.py` lands\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/promised.py"]
        assert [m["ref"] for m in _bpr._verify_chunk_refs(project, refs)] == [
            "lib/promised.py"
        ]

    def test_a_removed_path_that_still_exists_is_not_reported_either(
        self, tmp_path: Path
    ):
        """No expiry, where `new` has one, and this is the asymmetry.

        `new` expires when the chunk completes because a promised file that still
        does not exist is a real miss. A removal is the opposite: before the work
        lands the file is still there and resolves on its own, and after it lands
        its absence IS the delivery — so there is no state in which the ref check
        is the right instrument for "was it actually deleted?".
        """
        project, prawduct = _project_with_chunk(
            tmp_path, "- deleted `lib/gone.py` — retiring the module\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "gone.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []


class TestNewQualifierScope:
    """#224(b): `new` before a backticked token is not always a declaration."""

    def test_list_item_declaration_exempts(self, tmp_path: Path):
        _project, prawduct = _project_with_chunk(
            tmp_path, "- new `lib/created.py` — the parser\n"
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []

    def test_numbered_list_item_declaration_exempts(self, tmp_path: Path):
        _project, prawduct = _project_with_chunk(
            tmp_path, "1. new `lib/created.py` — the parser\n"
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []

    def test_wrapped_list_item_continuation_still_exempts(self, tmp_path: Path):
        # A list item does not end at its first newline, and this repo's plans
        # wrap deliverable bullets — the declaration routinely lands on a
        # continuation line. Matching per-line dropped the exemption for the
        # DOMINANT declaration form and would have emitted BLOCKING
        # `missing-ref:` on open chunks.
        _project, prawduct = _project_with_chunk(
            tmp_path,
            "- **Deliverables:**\n"
            "  - the parser rewrite, which lands as\n"
            "    new `lib/created.py` alongside the existing walk\n",
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []

    def test_narrative_prose_does_not_exempt(self, tmp_path: Path):
        # The defect: one adjectival sentence in a paragraph silently exempted a
        # real path from verification for the WHOLE chunk section.
        _project, prawduct = _project_with_chunk(
            tmp_path,
            "Context: this reworks the new `lib/created.py` behaviour.\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [r["ref"] for r in refs["file_paths"]] == ["lib/created.py"]

    def test_declaration_still_exempts_outside_deliverables(self, tmp_path: Path):
        # Why this is scoped to list items and not to the Deliverables block:
        # real plans name files they create in `- **Tests:**` and in acceptance
        # criteria, and those are legitimate forward references.
        _project, prawduct = _project_with_chunk(
            tmp_path, "- **Tests:** the new `tests/test_created.py` above\n"
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []


class TestVerifyChunkRefsPathSymbol:
    def test_existing_path_symbol_reports_no_missing(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gone.py::some_symbol`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "gone.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        # The stored ref is the PATH portion only — not the full `path::symbol`.
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/gone.py"]
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
            tmp_path, "- see `lib/gone.py` and `lib/gone.py::sym`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "gone.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        # Both collapse to one path existence-check.
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/gone.py"]

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
            tmp_path, "- `lib/gone.py` plus all `docs/*.md`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "gone.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/gone.py"]
        assert _bpr._verify_chunk_refs(project, refs) == []


class TestVerifyChunkRefsGitRefs:
    """Git branch/ref names backticked in a build/release plan (`feature/…`,
    `origin/develop`) contain `/` but name a branch, not a file — the parser must
    skip them, not flag a `missing-ref`. The carveout is gated on the SUFFIX SHAPE
    of the final segment, not on the presence of a dot: a real path that merely
    starts with a git-flow prefix keeps being captured (so the carveout does not
    blind the verifier to genuine drift), while a version-numbered branch is still
    recognised as a ref."""

    def test_feature_branch_name_is_skipped(self, tmp_path: Path):
        # The exact shape that false-positived: a Prerequisites bullet naming a branch.
        project, prawduct = _project_with_chunk(
            tmp_path, "- resumes by landing `feature/backlog-service-relayout`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert refs["file_paths"] == []
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_remote_tracking_ref_is_skipped(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(tmp_path, "- rebased on `origin/develop`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_extensioned_path_under_git_prefix_still_captured(self, tmp_path: Path):
        # Extension-gated: a real file whose path starts with a git-flow prefix is
        # still captured for existence-checking, so drift under such a path is not
        # silently skipped by the carveout.
        project, prawduct = _project_with_chunk(tmp_path, "- touches `feature/gen.py`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["feature/gen.py"]

    @pytest.mark.parametrize(
        "branch",
        [
            "release/v3.2.0",
            "release/v3.1.2",
            "feature/v3.2.0-c02-adapter-safety",
            "hotfix/v10.0.1",
        ],
    )
    def test_version_numbered_branch_is_skipped(self, tmp_path: Path, branch: str):
        """A dot in a branch name is not an extension.

        Keying the carveout on "contains no dot" left it inert for every
        version-numbered branch — precisely the ones a release cuts — so a plan
        naming its own release branch drew a BLOCKING `missing-ref:`. The gate is
        the suffix SHAPE, so `v3.2.0` (trailing dot-part `0`) reads as a ref.
        """
        project, prawduct = _project_with_chunk(tmp_path, f"- cut from `{branch}`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert refs["file_paths"] == []
        assert _bpr._verify_chunk_refs(project, refs) == []

    @pytest.mark.parametrize(
        "ref",
        ["refs/tags/v3.2.1", "refs/heads/develop", "refs/remotes/origin/main"],
    )
    def test_full_ref_namespace_is_skipped(self, tmp_path: Path, ref: str):
        """`refs/…` names the git ref namespace, not a path on disk — a release
        plan backticks it for the same reason it backticks a branch."""
        project, prawduct = _project_with_chunk(tmp_path, f"- tag `{ref}`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert refs["file_paths"] == []
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_extensioned_path_under_refs_still_captured(self, tmp_path: Path):
        """The carveout is suffix-gated, so it does not blind the verifier: a
        real file under `refs/` is still captured and still reported missing."""
        project, prawduct = _project_with_chunk(tmp_path, "- touches `refs/gen.py`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["refs/gen.py"]
        assert [m["ref"] for m in _bpr._verify_chunk_refs(project, refs)] == ["refs/gen.py"]

    def test_multi_dot_path_under_git_prefix_still_captured(self, tmp_path: Path):
        # The counter-case to the version branches above: a genuine path whose
        # stem carries dots still ends in an extension-shaped suffix, so it stays
        # captured rather than being waved through as a ref.
        project, prawduct = _project_with_chunk(
            tmp_path, "- edits `release/notes.v2.md`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["release/notes.v2.md"]


class TestVerifyChunkRefsNonPathTokens:
    """BLD-4K7P: backticked tokens that aren't literal on-disk paths must not
    produce false `missing-ref` positives — angle-bracket write-target templates
    (`<inbox>/<slug>.md`) and URLs (`https://…`) are skipped at parse (same
    form-family as the glob carveout), and an intentionally-gitignored managed
    path (`.prawduct/.bug-inbox`) is captured but skipped at verification because
    it's a generated/managed file, legitimately absent from a fresh checkout."""

    def test_angle_bracket_template_is_skipped(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- writes `<inbox>/<kebab-slug>.md` per report\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert refs["file_paths"] == []
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_url_is_skipped(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- see `https://example.com/spec/x.md`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_gitignored_managed_path_not_flagged_missing(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- the resolver writes to `.prawduct/.bug-inbox`\n"
        )
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        (project / ".gitignore").write_text(".prawduct/.bug-inbox\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        # It IS a path-shaped token (captured), but verification skips it.
        assert [e["ref"] for e in refs["file_paths"]] == [".prawduct/.bug-inbox"]
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_non_ignored_missing_path_still_flagged(self, tmp_path: Path):
        # Contrast: a genuinely-missing, NON-ignored path is still a missing-ref —
        # the gitignore skip must not suppress real drift.
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/does_not_exist.py`\n"
        )
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        (project / ".gitignore").write_text(".prawduct/.bug-inbox\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/does_not_exist.py"]


# =============================================================================
# BLD-4V7Q — a `path:line` citation is existence-checked as the file alone
# =============================================================================


class TestVerifyChunkRefsLineSuffix:
    """A backticked code-location citation carries a `:line` or `:line-range`
    suffix (`lib/critic_mode.py:452`, `lib/foo.py:5-8`). The suffix names a
    location inside the file, so the existence check must run against the path
    half — checking the literal `path:line` string reports a present file as a
    missing ref. Sibling of the `path::symbol` carveout above."""

    def test_line_suffix_stripped_before_existence_check(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- the guard at `lib/critic_mode.py:452`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "critic_mode.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/critic_mode.py"]
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_line_range_suffix_stripped(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(tmp_path, "- see `lib/foo.py:5-8`\n")
        (project / "lib").mkdir()
        (project / "lib" / "foo.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/foo.py"]
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_missing_path_with_line_suffix_reports_path_only(self, tmp_path: Path):
        # The fix must not suppress real drift: a citation of a file that does
        # not exist is still a missing-ref, named by its path.
        project, prawduct = _project_with_chunk(tmp_path, "- see `lib/gone.py:12`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/gone.py"]

    def test_symbol_suffix_ending_in_digits_not_read_as_line(self, tmp_path: Path):
        # `::` splits first, so a digit-tailed symbol is discarded with the
        # symbol half rather than mistaken for a line number.
        project, prawduct = _project_with_chunk(
            tmp_path, "- see `lib/rules.py::rule42`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "rules.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/rules.py"]

    def test_path_and_line_citation_dedup_on_same_line(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- `lib/gone.py` at `lib/gone.py:10`\n"
        )
        (project / "lib").mkdir()
        (project / "lib" / "gone.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/gone.py"]

    def test_line_and_column_suffix_stripped(self, tmp_path: Path):
        # Editor-style `path:line:col` — both numeric groups belong to the
        # citation, so the whole suffix comes off (not just the column).
        project, prawduct = _project_with_chunk(tmp_path, "- see `lib/foo.py:12:34`\n")
        (project / "lib").mkdir()
        (project / "lib" / "foo.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/foo.py"]
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_trailing_colon_without_digits_is_not_stripped(self, tmp_path: Path):
        # Only a numeric suffix is a line citation; `path:` keeps its shape and
        # is checked (and reported) literally.
        project, prawduct = _project_with_chunk(tmp_path, "- see `lib/odd.py:x`\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/odd.py:x"]


# =============================================================================
# BLD-6T4R — the `new ` forward-ref exemption is chunk-scoped, not line-local
# =============================================================================


class TestVerifyChunkRefsForwardRefScope:
    """A path declared `new` on a Deliverables line is a file the chunk creates.
    Naming it again in a later Done-when step doesn't make it exist yet, so the
    exemption must cover the whole chunk section — not only the occurrence that
    carried the qualifier."""

    def test_new_path_rereferenced_later_in_chunk_is_exempt(self, tmp_path: Path):
        # The filed shape: declared `new` on Deliverables, re-referenced bare in
        # a Done-when step.
        project, prawduct = _project_with_chunk(
            tmp_path,
            "- Deliverables: new `docs/api-notes.md`\n"
            "- Done when: `docs/api-notes.md` documents the contract\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["error"] is None
        assert refs["file_paths"] == []
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_new_declaration_after_the_reference_still_exempts(self, tmp_path: Path):
        # Order-independent: the whole section is scanned for `new` before any
        # token is judged, so a declaration below the citation still exempts it.
        project, prawduct = _project_with_chunk(
            tmp_path,
            "- Done when: `docs/api-notes.md` documents the contract\n"
            "- Deliverables: new `docs/api-notes.md`\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_new_declaration_exempts_a_later_line_citation(self, tmp_path: Path):
        # The two fixes compose: the `new` set is normalized like the tokens, so
        # a `new `path`` declaration also covers a later `path:line` citation.
        project, prawduct = _project_with_chunk(
            tmp_path,
            "- Deliverables: new `lib/created.py`\n"
            "- Done when: the guard at `lib/created.py:42` returns early\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []

    def test_exemption_does_not_leak_to_a_sibling_chunk(self, tmp_path: Path):
        # Scoped to the chunk, not the file: chunk 02's reference to a path that
        # chunk 01 declares `new` is still existence-checked.
        project = tmp_path / "proj"
        prawduct = project / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text("")
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "---\nartifact: build-plan\n---\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: creates it\n\n"
            "- Deliverables: new `lib/created.py`\n\n"
            "### Chunk 02: uses it\n\n"
            "- Done when: `lib/created.py` is wired in\n\n"
            "## Next Section\n"
        )
        assert _bpr._parse_build_plan_chunk_refs(prawduct, "01")["file_paths"] == []
        refs2 = _bpr._parse_build_plan_chunk_refs(prawduct, "02")
        assert [e["ref"] for e in refs2["file_paths"]] == ["lib/created.py"]

    def test_undeclared_path_in_same_chunk_still_flagged(self, tmp_path: Path):
        # The exemption is per-path, not per-chunk: one `new` declaration must
        # not silence every other missing ref in the section.
        project, prawduct = _project_with_chunk(
            tmp_path,
            "- Deliverables: new `docs/api-notes.md`\n"
            "- Done when: `lib/does_not_exist.py` is updated\n",
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert [e["ref"] for e in refs["file_paths"]] == ["lib/does_not_exist.py"]
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/does_not_exist.py"]


# =============================================================================
# BLD-ZQ2V — plugin-relative shorthand resolves; ambiguity is reported, not excused
# =============================================================================


def _declare_ref_root(project: Path, name: str = "plugin") -> Path:
    """Declare an additional build-plan ref root, the way a repo opts in."""
    state = project / ".prawduct" / "project-state.yaml"
    state.write_text(state.read_text() + f"\n{_bpr.REF_ROOT_KEY}: {name}\n")
    root = project / name
    root.mkdir(parents=True, exist_ok=True)
    return root


class TestVerifyChunkRefsDeclaredRefRoot:
    """A repo may DECLARE a second root its plan refs are written relative to.
    Declared, never inferred — see `test_undeclared_repo_does_NOT_resolve`."""

    def test_plugin_relative_ref_resolves(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gates.py`\n"
        )
        plugin = _declare_ref_root(project)
        (plugin / "lib").mkdir()
        (plugin / "lib" / "gates.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_plugin_relative_directory_ref_resolves(self, tmp_path: Path):
        # A trailing-slash directory ref has no file extension; it must still
        # resolve under the plugin subtree rather than being second-guessed.
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/backlog/`\n"
        )
        plugin = _declare_ref_root(project)
        (plugin / "lib" / "backlog").mkdir(parents=True)
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_undeclared_repo_does_NOT_resolve(self, tmp_path: Path):
        """The load-bearing guard for every consuming product.

        A repo with a `plugin/` tree it never declared — a product that ships a
        Claude Code plugin, a VS Code extension, a vendored bundle — must not
        get refs resolved against it. Inferring the affordance from layout
        silently excuses a genuinely missing deliverable, i.e. weakens the gate
        everywhere its shape happens to match. Absence of the key is the
        fail-closed default.
        """
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gates.py`\n"
        )
        plugin = project / "plugin"  # present, and even plugin-shaped...
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "x"}\n')
        (plugin / "lib").mkdir()
        (plugin / "lib" / "gates.py").write_text("x = 1\n")
        # ...but never declared, so it is not a ref root.
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/gates.py"]

    def test_declared_root_escaping_the_repo_is_ignored(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gates.py`\n"
        )
        outside = tmp_path / "outside"
        (outside / "lib").mkdir(parents=True)
        (outside / "lib" / "gates.py").write_text("x = 1\n")
        state = project / ".prawduct" / "project-state.yaml"
        state.write_text(
            state.read_text() + f"\n{_bpr.REF_ROOT_KEY}: ../outside\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/gates.py"]

    def test_declared_root_that_does_not_exist_is_ignored(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gates.py`\n"
        )
        state = project / ".prawduct" / "project-state.yaml"
        state.write_text(state.read_text() + f"\n{_bpr.REF_ROOT_KEY}: nope\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/gates.py"]

    def test_root_wins_over_plugin(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/gates.py`\n"
        )
        _declare_ref_root(project)
        (project / "lib").mkdir()
        (project / "lib" / "gates.py").write_text("x = 1\n")
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        assert _bpr._verify_chunk_refs(project, refs) == []

    def test_absent_from_both_still_reports(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `lib/nope.py`\n"
        )
        _declare_ref_root(project)
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["lib/nope.py"]


class TestIssueRefsAreNotFilePaths:
    """`#` names a location in a tracker or document, never a source file."""

    def test_issue_reference_excluded(self):
        assert not _bpr._looks_like_file_path("owner/repo#12")

    def test_document_anchor_excluded(self):
        assert not _bpr._looks_like_file_path("docs/api#usage")

    def test_ordinary_path_still_included(self):
        assert _bpr._looks_like_file_path("lib/gates.py")


class TestPathShapedAmbiguityIsReported:
    """A gate that guesses "probably prose" fails open on the exact input it
    exists to judge. A bare `owner/repo` slug is path-shaped and stays checked;
    the author disambiguates in the plan (`<owner>/<repo>`, or unbackticked).

    These pin the ABSENCE of a fail-open heuristic — if a later change teaches
    the verifier to skip extension-less refs whose first segment is missing,
    these fail, which is the point.
    """

    def test_repo_slug_is_still_path_shaped(self):
        assert _bpr._looks_like_file_path("brookstalley/prawduct")

    def test_unresolvable_slug_is_reported_not_excused(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- see `brookstalley/prawduct`\n"
        )
        _declare_ref_root(project)
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["brookstalley/prawduct"]

    def test_extensionless_ref_under_absent_dir_is_reported(self, tmp_path: Path):
        project, prawduct = _project_with_chunk(
            tmp_path, "- touches `docs/design`\n"
        )
        refs = _bpr._parse_build_plan_chunk_refs(prawduct, "01")
        missing = _bpr._verify_chunk_refs(project, refs)
        assert [m["ref"] for m in missing] == ["docs/design"]

    def test_placeholder_form_is_the_disambiguator(self):
        # The escape hatch the docstring points authors at, already supported.
        assert not _bpr._looks_like_file_path("<owner>/<repo>")
