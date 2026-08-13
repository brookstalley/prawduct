"""Tests for the change-log merge-attribute advisory probe (analysis F6).

Two surfaces, both covered here:

* ``gitstate.git_merge_attribute`` / ``gitstate.git_path_is_tracked`` — the
  read-only git boundary. Both are TRI-state: an answer, the other answer, and
  ``None`` for "git could not be asked". The ``None`` cases are the point — a
  probe that reads "could not ask" as "no attribute" nags every repo where git
  is unavailable, and one that reads it as "attribute present" goes silent
  exactly where it is needed.
* ``gitattributes_probes.probe_change_log_union_merge`` — fires only on a
  COMMITTED change-log with no ``merge=union``, **self-resolves** once the
  attribute is in force, and prints a ``NOTE:`` rather than nothing when the
  attribute lookup fails on a committed log.

Registry isolation mirrors ``test_stale_base_probes.py`` (autouse
``clear_registry``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import gitattributes_probes as gap
from lib import gitstate
from lib.advisory_store import (
    ProjectState,
    clear_registry,
    make_codebase,
    run_all_probes,
)
from lib.change_log import CHANGE_LOG_REL_PATH


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


# ---------------------------------------------------------------------------
# Repo builder
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _repo(
    tmp_path: Path,
    *,
    change_log: str = "committed",  # "committed" | "untracked" | "ignored" | "absent"
    attribute: str | None = None,  # a .gitattributes line to commit, or None
) -> Path:
    """Build a repo in the F6 shape: a change-log, optionally attributed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    if change_log != "absent":
        log_path = repo / CHANGE_LOG_REL_PATH
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("# Change Log\n\n## 2026-08-13: first\n")
    if change_log == "ignored":
        (repo / ".gitignore").write_text(f"{CHANGE_LOG_REL_PATH}\n")
    if attribute is not None:
        (repo / ".gitattributes").write_text(f"{attribute}\n")
    _git(repo, "add", "-A")
    if change_log == "untracked":
        _git(repo, "reset", "-q", "--", CHANGE_LOG_REL_PATH)
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _probe(repo: Path):
    return gap.probe_change_log_union_merge(ProjectState({}), make_codebase(repo))


# ---------------------------------------------------------------------------
# The git boundary — three answers, kept apart
# ---------------------------------------------------------------------------


class TestGitMergeAttribute:
    def test_union_when_attribute_is_set(self, tmp_path):
        repo = _repo(tmp_path, attribute=gap.UNION_MERGE_LINE)
        assert gitstate.git_merge_attribute(repo, CHANGE_LOG_REL_PATH) == "union"

    def test_unspecified_when_no_attribute_applies(self, tmp_path):
        repo = _repo(tmp_path)
        assert gitstate.git_merge_attribute(repo, CHANGE_LOG_REL_PATH) == "unspecified"

    def test_reports_a_different_driver_verbatim(self, tmp_path):
        # Git's own answer is returned, not a boolean — a repo that deliberately
        # set another driver is a distinguishable state, not "no attribute".
        repo = _repo(tmp_path, attribute=f"{CHANGE_LOG_REL_PATH} merge=binary")
        assert gitstate.git_merge_attribute(repo, CHANGE_LOG_REL_PATH) == "binary"

    def test_none_and_no_raise_outside_a_repo(self, tmp_path):
        not_a_repo = tmp_path / "bare"
        not_a_repo.mkdir()
        assert gitstate.git_merge_attribute(not_a_repo, CHANGE_LOG_REL_PATH) is None

    def test_path_with_a_colon_parses(self, tmp_path):
        # The plain (non -z) output is `path: attr: value`, which a colon in the
        # path makes ambiguous. -z is why this reads correctly.
        repo = _repo(tmp_path)
        weird = "notes/a:b.md"
        (repo / "notes").mkdir()
        (repo / weird).write_text("x\n")
        (repo / ".gitattributes").write_text(f'"{weird}" merge=union\n')
        assert gitstate.git_merge_attribute(repo, weird) == "union"


class TestGitPathIsTracked:
    def test_true_for_a_committed_path(self, tmp_path):
        repo = _repo(tmp_path)
        assert gitstate.git_path_is_tracked(repo, CHANGE_LOG_REL_PATH) is True

    def test_false_for_an_untracked_path(self, tmp_path):
        repo = _repo(tmp_path, change_log="untracked")
        assert gitstate.git_path_is_tracked(repo, CHANGE_LOG_REL_PATH) is False

    def test_none_and_no_raise_outside_a_repo(self, tmp_path):
        not_a_repo = tmp_path / "bare"
        not_a_repo.mkdir()
        assert gitstate.git_path_is_tracked(not_a_repo, CHANGE_LOG_REL_PATH) is None

    def test_glob_metacharacters_do_not_match_a_sibling(self, tmp_path):
        # The pathspec is `:(literal)`: without it, `a*.md` is wildmatch and
        # would match the committed `ab.md`, reporting an untracked path tracked.
        repo = _repo(tmp_path)
        (repo / "ab.md").write_text("x\n")
        _git(repo, "add", "ab.md")
        _git(repo, "commit", "-q", "-m", "c2")
        assert gitstate.git_path_is_tracked(repo, "a*.md") is False


# ---------------------------------------------------------------------------
# The probe
# ---------------------------------------------------------------------------


class TestProbe:
    def test_fires_on_committed_change_log_without_the_attribute(self, tmp_path):
        repo = _repo(tmp_path)
        out = _probe(repo)
        assert len(out) == 1
        cand = out[0]
        assert cand.type == "change-log-union-merge"
        assert cand.priority == "info"
        assert gap.UNION_MERGE_LINE in cand.recommended_action
        # The recommendation is the literal line, spelled the way git needs it.
        assert gap.UNION_MERGE_LINE == ".prawduct/change-log.md merge=union"
        assert "merge=union" in cand.trigger_summary

    def test_inert_once_the_attribute_is_committed(self, tmp_path):
        # Self-resolution: the same observable state that triggers it clears it,
        # so `reconcile` flips the advisory to resolved on the next sync.
        repo = _repo(tmp_path, attribute=gap.UNION_MERGE_LINE)
        assert _probe(repo) == []

    def test_inert_when_the_attribute_comes_from_a_pattern(self, tmp_path):
        # git resolves attributes by pattern; the probe asks git rather than
        # matching the path itself, so a directory-wide rule resolves it too.
        repo = _repo(tmp_path, attribute=".prawduct/*.md merge=union")
        assert _probe(repo) == []

    def test_fires_when_a_different_driver_is_set(self, tmp_path):
        repo = _repo(tmp_path, attribute=f"{CHANGE_LOG_REL_PATH} merge=binary")
        assert len(_probe(repo)) == 1

    def test_inert_when_the_change_log_is_absent(self, tmp_path):
        repo = _repo(tmp_path, change_log="absent")
        assert _probe(repo) == []

    def test_inert_when_the_change_log_is_untracked(self, tmp_path):
        # On disk but never committed — nothing to conflict on at merge time.
        repo = _repo(tmp_path, change_log="untracked")
        assert _probe(repo) == []

    def test_inert_when_the_change_log_is_gitignored(self, tmp_path):
        repo = _repo(tmp_path, change_log="ignored")
        assert _probe(repo) == []

    def test_inert_and_silent_outside_a_repo(self, tmp_path, capsys):
        # No git, no merges, no harm — and so no NOTE either. The diagnostic is
        # reserved for the case where the harm is live (see the test below).
        plain = tmp_path / "plain"
        (plain / ".prawduct").mkdir(parents=True)
        (plain / CHANGE_LOG_REL_PATH).write_text("# Change Log\n")
        assert _probe(plain) == []
        assert "NOTE:" not in capsys.readouterr().err

    def test_says_why_when_the_attribute_cannot_be_read(self, tmp_path, monkeypatch, capsys):
        """A committed log whose merge driver git could not report.

        "No attribute found" and "I could not ask" are the same empty answer
        unless the probe says so: it must not raise the advisory (that would nag
        a repo that may already be fixed) and must not stay silent (that reads as
        "checked, and fine").
        """
        repo = _repo(tmp_path)
        monkeypatch.setattr(gitstate, "git_merge_attribute", lambda *_a, **_k: None)
        assert _probe(repo) == []
        err = capsys.readouterr().err
        assert "NOTE:" in err
        assert CHANGE_LOG_REL_PATH in err
        assert "did not check" in err

    def test_evidence_is_stable_across_firings(self, tmp_path):
        # Evidence is hashed into the advisory id: appending entries to the log
        # (the thing that happens between every two sessions) must not churn it.
        repo = _repo(tmp_path)
        one = _probe(repo)
        log_path = repo / CHANGE_LOG_REL_PATH
        log_path.write_text("# Change Log\n\n## 2026-08-14: second\n" + log_path.read_text())
        _git(repo, "commit", "-q", "-am", "c2")
        two = _probe(repo)
        assert one[0].evidence == two[0].evidence

    def test_probe_is_wired_into_the_composition_root(self, tmp_path):
        # `register()` alone stays green if the two `register_all` lines are
        # deleted and the probe is dead in production.
        from lib.probe_families import register_all

        repo = _repo(tmp_path)
        register_all()
        fired = [
            c
            for c in run_all_probes(ProjectState({}), make_codebase(repo))
            if c.feature == gap.FEATURE and c.type == "change-log-union-merge"
        ]
        assert len(fired) == 1
        assert fired[0].probe_version == gap.PROBE_VERSION

    def test_recommended_line_is_what_git_resolves(self, tmp_path):
        # The advisory's recommendation, taken literally, must be the thing that
        # clears the advisory — a recommendation git does not honour would nag
        # forever after being followed.
        repo = _repo(tmp_path)
        (repo / ".gitattributes").write_text(f"{gap.UNION_MERGE_LINE}\n")
        _git(repo, "add", ".gitattributes")
        _git(repo, "commit", "-q", "-m", "attr")
        assert _probe(repo) == []

    def test_direct_register_is_idempotent_and_fires(self, tmp_path):
        repo = _repo(tmp_path)
        gap.register()
        gap.register()  # idempotent — register_probe overwrites
        fired = [
            c
            for c in run_all_probes(ProjectState({}), make_codebase(repo))
            if c.type == "change-log-union-merge"
        ]
        assert len(fired) == 1
        assert fired[0].feature == "gitattributes"


# ---------------------------------------------------------------------------
# The recommendation itself
# ---------------------------------------------------------------------------


def _prepend_entry(repo: Path, header: str, scope: str) -> None:
    path = repo / CHANGE_LOG_REL_PATH
    path.write_text(
        f"# Change Log\n\n## {header}\n<!-- prawduct: scope={scope} -->\n\n"
        f"{scope} body.\n\n" + path.read_text().split("# Change Log\n\n", 1)[1]
    )
    _git(repo, "commit", "-q", "-am", scope)


def _two_branch_prepend_merge(tmp_path: Path, *, attribute: bool) -> subprocess.CompletedProcess:
    """Both branches prepend a tagged entry; merge one into the other."""
    repo = _repo(tmp_path, attribute=gap.UNION_MERGE_LINE if attribute else None)
    _git(repo, "checkout", "-q", "-b", "feat")
    _prepend_entry(repo, "2026-08-13: feature", "feat")
    _git(repo, "checkout", "-q", "main")
    _prepend_entry(repo, "2026-08-12: develop", "dev")
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "merge", "--no-edit", "feat"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestUnionMergeRecommendation:
    """What the advisory claims, exercised against real git.

    The advisory tells an operator that this attribute removes the dominant
    conflict class without damaging the log. Both halves are asserted here, so
    the claim is a contract rather than a docstring — and the no-attribute case
    is the control that proves the attribute, not the fixture, is what does it.
    """

    def test_prepends_conflict_without_the_attribute(self, tmp_path):
        proc = _two_branch_prepend_merge(tmp_path, attribute=False)
        assert proc.returncode != 0
        assert "CONFLICT" in proc.stdout + proc.stderr

    def test_prepends_merge_cleanly_with_tags_intact(self, tmp_path):
        from lib import change_log as change_log_mod

        proc = _two_branch_prepend_merge(tmp_path, attribute=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        merged = (tmp_path / "repo" / CHANGE_LOG_REL_PATH).read_text()
        assert "<<<<<<<" not in merged
        entries = change_log_mod.parse_change_log(merged)
        # Both sides' entries survive, and each tag line stays under the header
        # it was written for — the union driver concatenates whole hunks, so the
        # header/tag pairing is never crossed.
        assert [e.tags.get("scope") for e in entries] == ["dev", "feat", None]
        assert change_log_mod.validate_change_log_tags(entries) == ([], [])
