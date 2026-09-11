"""Tests for the missing-change-log-entry probe — ``prawduct-hook check-change-log-entry``.

REL-6C3W: a code-changing branch could merge with NO change-log entry and
nothing flagged it — the gap surfaced only at release reconstruction
(CRT-7B4M/#82, found at the v2.0.16 release). The probe runs at the PR
boundary (`/prawduct:pr` Create Step 1c): a diff in ``merge-base...HEAD``
carrying **judgeable** work — ``coverage_algebra.is_judgeable_path``, the same
predicate ``check-pr-doc-only`` asks, NOT a ``.md`` suffix test — must ADD an
entry header (``+## `` line) to ``.prawduct/change-log.md``. Diffs with no
judgeable file, and empty diffs, are exempt;
un-evaluable git state fails closed (named reason, exit 1) so the caller
falls back to manual judgment rather than silently skipping the probe —
learnings: a skip-gate needs the most adversarial coverage, so the exempt
paths are pinned alongside the failing ones.

Uses real ``git`` repos (mirrors test_cumulative_gate.py) so merge-base and
name-only diffs behave as in production.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

CHANGE_LOG = ".prawduct/change-log.md"


def _git_env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")


def _make_branched_repo(tmp_path: Path) -> Path:
    """A repo with a ``main`` baseline (code + change-log) and a checked-out
    ``feature/x`` branch ready for branch commits. The probe's base resolution
    falls back to ``main`` (no origin, no ``base_branch:`` knob)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_file(repo, "app.py", "print(1)\n", "baseline code")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-01: baseline entry\n\nBody.\n",
        "baseline change-log",
    )
    _git(repo, "checkout", "-q", "-b", "feature/x")
    return repo


def _run_probe(repo: Path) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "check-change-log-entry"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


# ---------------------------------------------------------------------------
# Passing cases
# ---------------------------------------------------------------------------


def test_code_change_with_new_entry_passes(tmp_path):
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-10: new work\n"
        "<!-- prawduct: type=fix | chunks=01 | scope=x -->\n\n"
        "## 2026-06-01: baseline entry\n\nBody.\n",
        "add entry",
    )
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "entry-present" in result.stdout


def test_doc_only_branch_exempt(tmp_path):
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "docs/notes.md", "notes\n", "doc change")
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "doc-only" in result.stdout


def test_session_metadata_is_not_code(tmp_path):
    """The consumer-reported defect: `.prawduct/` metadata read as code.

    This gate classified with an inline `not f.endswith(".md")`, so any non-`.md`
    file was "code" — including the `.prawduct/` session metadata that
    `coverage_algebra.is_judgeable_path` (whose docstring calls it "THE predicate
    (CRT-5D8Q fix)") exists to exclude. CRT-5D8Q consolidated three classifiers;
    this was a fourth that was never folded in.

    **Worse than a spurious block, which is why it is pinned.** The gate's remedy
    text is executable advice, and it was wrong advice: in the case that surfaced
    this, the `.prawduct/corpus-state.json` on the blocked branch was another
    session's corpus refresh riding along on a cherry-pick, so obeying the gate
    would have produced a change-log entry describing someone else's work as the
    author's own — the gate demanding a false provenance record.
    """
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, ".prawduct/corpus-state.json", '{"n": 1}\n', "corpus refresh")
    result = _run_probe(repo)
    assert result.returncode == 0, (
        f"session metadata was read as code and blocked the PR: {result.stderr}"
    )
    assert "doc-only" in result.stdout


def test_a_governance_protected_md_branch_still_needs_an_entry(tmp_path):
    """The direction the same one-line routing change TIGHTENS.

    `is_judgeable_path` rates a `.md` file judgeable when it sits under a
    protected path (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`) —
    skill prose is behavioral logic, not docs. So routing this gate through
    `judgeable_files` moves it in *both* directions: a branch changing only
    `plugin/skills/pr/SKILL.md` went from exit 0 (all `.md`, exempt) to exit 1
    (judgeable, entry required).

    Pinned because it is changed behavior, and because the loosening direction
    alone is the easy half to test — `learnings.md`: pin the DIRECTION
    separately, on a fixture from the population the predicate is worst at. The
    backlog item this closes (`#245`) names both directions explicitly; shipping
    only the `.prawduct/` case would close it against half its recorded scope.
    """
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "plugin/skills/pr/SKILL.md", "# skill\nprose\n", "skill prose")
    result = _run_probe(repo)
    assert result.returncode == 1, (
        "a governance-protected .md branch is judgeable and must still require "
        f"an entry; got exit {result.returncode}: {result.stdout}{result.stderr}"
    )
    assert "no-entry" in result.stderr
    assert "SKILL.md" in result.stderr, (
        "the remedy names the .md files it counted, or the author cannot tell "
        "why a prose branch was asked for a change-log entry"
    )


@pytest.mark.parametrize(
    "paths",
    [
        pytest.param([".prawduct/corpus-state.json"], id="session-metadata-only"),
        pytest.param([".prawduct/corpus-state.json", "docs/notes.md"], id="metadata-plus-docs"),
        pytest.param(["docs/notes.md"], id="docs-only"),
        pytest.param(["app.py"], id="code-only"),
        pytest.param(["plugin/skills/pr/SKILL.md"], id="protected-md"),
        pytest.param(["app.py", "docs/notes.md"], id="code-plus-docs"),
    ],
)
def test_both_pr_gates_agree_on_the_same_diff(tmp_path, paths):
    """The two PR-boundary gates must never contradict each other.

    `check-pr-doc-only` said "none judgeable, gates may be skipped" while
    `check-change-log-entry` said "branch changes code" — about the same file, at
    the same boundary, in the same command. Asserted as *agreement* rather than
    as two expected verdicts, because the defect was the disagreement: pinning
    each gate's answer independently is what let them drift apart.

    **Deliberately NOT parametrized over the empty diff.** The two gates diverge
    there by design — `_pr_diff_is_doc_only` returns False (there is nothing to
    call doc-only) while this gate returns 0 (nothing to write an entry about) —
    so including it would assert an invariant the code does not hold and go red
    on the next fixture someone adds. The shared question is "does this diff
    contain judgeable work", which an empty diff does not pose.

    The fixture set spans both sides of the predicate on purpose: a case where
    both exempt, both block, and each mixed shape. An all-exempt or all-blocking
    parameter list would pass while the gates agreed only by luck.
    """
    repo = _make_branched_repo(tmp_path)
    for i, rel in enumerate(paths):
        _commit_file(repo, rel, f"content {i}\n", f"change {rel}")

    change_log = _run_probe(repo)
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    doc_only = subprocess.run(
        ["python3", str(HOOK), "check-pr-doc-only"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )
    # doc-only exits 0 when the diff needs no review; the change-log gate exits 0
    # when it needs no entry. Same underlying question, so the same answer.
    assert (doc_only.returncode == 0) == (change_log.returncode == 0), (
        f"the two PR-boundary gates disagree about {paths}: "
        f"check-pr-doc-only exit={doc_only.returncode} "
        f"({doc_only.stdout.strip() or doc_only.stderr.strip()}), "
        f"check-change-log-entry exit={change_log.returncode} "
        f"({change_log.stdout.strip() or change_log.stderr.strip()})"
    )


def test_the_two_gates_diverge_on_an_empty_diff_by_design(tmp_path):
    """The one case the agreement test excludes, pinned so it stays a decision.

    An excluded case with no test is indistinguishable from an oversight, and
    the next person to notice the divergence would either "fix" it or widen the
    agreement test until it went red. Neither gate is wrong here: there is no
    judgeable work to review AND nothing to write an entry about.
    """
    repo = _make_branched_repo(tmp_path)
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    doc_only = subprocess.run(
        ["python3", str(HOOK), "check-pr-doc-only"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )
    assert _run_probe(repo).returncode == 0, "an empty diff owes no entry"
    assert doc_only.returncode != 0, (
        "check-pr-doc-only now calls an empty diff doc-only — if that is "
        "intended, the agreement test above can stop excluding it"
    )


def test_empty_diff_exempt(tmp_path):
    repo = _make_branched_repo(tmp_path)
    # No branch commits: merge-base...HEAD is empty.
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "empty-diff" in result.stdout


# ---------------------------------------------------------------------------
# Failing cases (the load-bearing coverage)
# ---------------------------------------------------------------------------


def test_code_change_without_entry_fails(tmp_path):
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no-entry" in result.stderr
    assert "app.py" in result.stderr


def test_entry_edited_but_not_added_fails(tmp_path):
    """Touching the change-log (rewording an OLD entry) must not vouch for the
    branch's code changes — a new ``+## `` header is required."""
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-01: baseline entry\n\nReworded body.\n",
        "reword old entry",
    )
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "entry-edited-not-added" in result.stderr


def test_unresolvable_base_fails_closed(tmp_path):
    """No git repo at all → no base resolves → exit 1 with a named reason
    (manual judgment, never a silent skip)."""
    plain = tmp_path / "plain"
    (plain / ".prawduct").mkdir(parents=True)
    (plain / CHANGE_LOG).write_text("# Change Log\n")
    result = _run_probe(plain)
    assert result.returncode == 1
    assert "no-base" in result.stderr or "git-failed" in result.stderr


# ---------------------------------------------------------------------------
# Edge: header-add detection is diff-line anchored
# ---------------------------------------------------------------------------


def test_plus_h2_in_body_prose_does_not_count(tmp_path):
    """A body line that merely CONTAINS '## ' (e.g. markdown quoting) is not an
    added entry header — only a diff line starting '+## ' counts."""
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    _commit_file(
        repo, CHANGE_LOG,
        "# Change Log\n\n## 2026-06-01: baseline entry\n\n"
        "Body now mentions a header-like token: `## not a header`.\n",
        "edit body only",
    )
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "entry-edited-not-added" in result.stderr


# ---------------------------------------------------------------------------
# The log is UNTRACKED (repo gitignores `.prawduct/` wholesale)
#
# A path git does not track can never appear in a diff, so the diff's silence
# is not evidence of a missing entry. Repos that ignore `.prawduct/` wholesale
# kept a real change-log on disk and got `no-entry` anyway — with a remedy
# ("add a change-log entry") that no amount of following could ever clear.
# ---------------------------------------------------------------------------


def _make_untracked_log_repo(tmp_path: Path, log_body: str | None) -> Path:
    """A branched repo whose `.prawduct/` is gitignored wholesale.

    ``log_body`` is written to disk (never committed — git cannot see it); pass
    ``None`` to leave the repo with no change-log file at all.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_file(repo, ".gitignore", ".prawduct/\n", "ignore prawduct state")
    _commit_file(repo, "app.py", "print(1)\n", "baseline code")
    if log_body is not None:
        log = repo / CHANGE_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(log_body)
    _git(repo, "checkout", "-q", "-b", "feature/x")
    return repo


def test_untracked_log_with_entries_passes_on_the_weaker_check(tmp_path):
    """The defect this family exists for: a real log, on disk, read as absent."""
    repo = _make_untracked_log_repo(
        tmp_path,
        "# Change Log\n\n## 2026-06-10: this branch's work\n\nBody.\n"
        "\n## 2026-06-01: baseline entry\n\nBody.\n",
    )
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    # The log really is invisible to git — the premise of the whole case.
    assert not _git(repo, "log", "--all", "--", CHANGE_LOG).stdout.strip()

    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "entry-present-untracked" in result.stdout
    # The message must not claim the strong check ran, and must not repeat the
    # unfollowable remedy.
    assert "no-entry" not in result.stdout + result.stderr


def test_untracked_log_missing_from_disk_still_fails(tmp_path):
    """Degrading the check must not disarm it: no log at all is still no entry."""
    repo = _make_untracked_log_repo(tmp_path, None)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no-entry" in result.stderr


def test_untracked_log_with_no_entries_still_fails(tmp_path):
    """A stub log — a header and no `## ` entry — does not vouch for anything."""
    repo = _make_untracked_log_repo(tmp_path, "# Change Log\n\nNothing yet.\n")
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no-entry" in result.stderr


def test_untracked_log_does_not_rescue_a_doc_only_branch(tmp_path):
    """The judgeability exemption still short-circuits first, unchanged."""
    repo = _make_untracked_log_repo(
        tmp_path, "# Change Log\n\n## 2026-06-10: work\n\nBody.\n"
    )
    _commit_file(repo, "docs/notes.md", "notes\n", "doc change")
    result = _run_probe(repo)
    assert result.returncode == 0, result.stderr
    assert "doc-only" in result.stdout


def test_tracked_log_untouched_by_the_branch_still_says_no_entry(tmp_path):
    """The tracked path is untouched by the fix — pinned so it cannot drift.

    `test_code_change_without_entry_fails` asserts the same outcome; this one
    asserts it did NOT arrive via the untracked branch, which is the regression
    that would silently pass every tracked repo.
    """
    repo = _make_branched_repo(tmp_path)
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no-entry" in result.stderr
    assert "untracked" not in result.stderr


# ---------------------------------------------------------------------------
# The probe's verdicts and Step 1c's enumeration must not drift apart
#
# Step 1c routes on the verdict NAME, so a verdict the prose does not list
# falls into whichever row the reader generalises from — which is how
# `entry-present-untracked` was first swallowed by a blanket "Exit 0: proceed",
# reopening the very REL-6C3W failure this gate exists to prevent. Prose has no
# compiler; this is the pin. Same shape as test_cutover_prose_coherence.py.
# ---------------------------------------------------------------------------

SOURCE = Path(__file__).resolve().parent.parent / "plugin"
COVERAGE_PY = SOURCE / "lib" / "coverage.py"
PR_SKILL = SOURCE / "skills" / "pr" / "SKILL.md"

# A verdict is the hyphenated token a message opens with (`no-entry: ...`),
# captured at a string-literal boundary so prose mentions do not count. Every
# verdict this gate has ever emitted is hyphenated; a future single-word one
# would slip past this and needs the pattern widened with it.
_VERDICT_RE = re.compile(r"""["'](?:\s*)([a-z][a-z0-9]*(?:-[a-z0-9]+)+):\s""")


def _probe_source() -> str:
    """The two functions that emit this gate's verdicts, and nothing else."""
    text = COVERAGE_PY.read_text(encoding="utf-8")
    start = text.index("def _entry_check_without_history")
    end = text.index("\ndef ", text.index("def check_change_log_entry"))
    return text[start:end]


def _step_1c() -> str:
    text = PR_SKILL.read_text(encoding="utf-8")
    start = text.index("### Step 1c:")
    return text[start:text.index("### Step 1d:", start)]


def test_every_verdict_the_probe_emits_is_routed_by_step_1c():
    verdicts = set(_VERDICT_RE.findall(_probe_source()))
    # Guard the extractor itself: a regex that silently matched nothing would
    # make this test pass while pinning absolutely nothing.
    assert len(verdicts) >= 6, f"verdict extraction looks broken: {verdicts}"

    step = _step_1c()
    missing = sorted(v for v in verdicts if f"`{v}`" not in step)
    assert not missing, (
        f"{PR_SKILL.name} Step 1c does not route these verdicts: {missing}. "
        "An unlisted verdict is read under whichever row the agent generalises "
        "from, which for an exit-0 verdict means proceeding on an unanswered check."
    )


def test_step_1c_does_not_route_a_verdict_the_probe_no_longer_emits():
    """The other drift direction — prose outliving the code that fed it.

    Reads only the ``- **Exit N with `x`, `y`**:`` bullet headers, so what it
    compares is the routing table itself rather than every token Step 1c
    happens to mention (paths, predicates and REL ids are all backticked too).
    """
    routed = set()
    for line in _step_1c().splitlines():
        if not line.startswith("- **Exit "):
            continue
        header = line.split("**:", 1)[0]
        routed.update(re.findall(r"`([a-z][a-z0-9-]+)`", header))
    assert routed, "no exit rows parsed out of Step 1c — the bullet shape moved"

    stale = sorted(routed - set(_VERDICT_RE.findall(_probe_source())))
    assert not stale, (
        f"Step 1c routes verdicts the probe no longer emits: {stale}. A row for "
        "a dead verdict is an instruction that can never fire."
    )


def test_untracked_log_that_is_not_utf8_fails_with_a_verdict_not_a_traceback(tmp_path):
    """A non-UTF-8 byte is as unreadable as a missing file. Escaping as an
    exception would be the one outcome Step 1c has no row for."""
    repo = _make_untracked_log_repo(tmp_path, None)
    log = repo / CHANGE_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"# Change Log\n\n## 2026-06-10: work\n\n\xff\xfe body\n")
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no-entry" in result.stderr and "could not be read" in result.stderr
    assert "Traceback" not in result.stderr


def test_untracked_log_holding_only_shipped_entries_still_fails(tmp_path):
    """An entry carrying `release=` shipped long ago and vouches for nothing;
    otherwise one old entry would pass every branch in the repo forever."""
    repo = _make_untracked_log_repo(
        tmp_path,
        "# Change Log\n\n## 2026-01-01: old\n\n<!-- prawduct: scope=old | release=v1.0.0 -->\n\nBody.\n",
    )
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    result = _run_probe(repo)
    assert result.returncode == 1
    assert "no release-pending entry" in result.stderr


def test_a_failed_tracked_probe_is_git_failed_not_the_weak_check(tmp_path, monkeypatch):
    """`git_path_is_tracked` is three-valued so that a probe that could not run
    is never read as "untracked": that arm must route to `git-failed` (exit 1),
    never into the weaker on-disk check (exit 0)."""
    import sys as _sys

    _sys.path.insert(0, str(ROOT))
    from lib import coverage, gitstate  # noqa: PLC0415

    repo = _make_untracked_log_repo(
        tmp_path, "# Change Log\n\n## 2026-06-10: work\n\nBody.\n"
    )
    _commit_file(repo, "app.py", "print(2)\n", "code change")
    monkeypatch.setattr(gitstate, "git_path_is_tracked", lambda *_a, **_k: None)
    import io, contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = coverage.check_change_log_entry(repo)
    assert code == 1
    assert "git-failed" in err.getvalue()
