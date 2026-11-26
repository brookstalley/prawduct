"""The release batch review, and the relax-only rule that credits it (#1232 Chunk 03).

`critic-begin --mode cumulative --span release` reviews release anchor → HEAD on the
integration base, rating only the files of the release entries no boundary review
covered. Its fact is never a coverage edge, so no PR gate can move because it exists;
`check-boundary-coverage` credits it entry by entry through
`coverage_algebra.batch_review_covers`.

Real git repositories and the real CLI throughout: the dispatch is driven through
`critic-begin`, the fact through `critic-consolidate`, the answer through
`check-boundary-coverage --json`. Fix verification is written as facts, through the
store's own writer, as the boundary-coverage tests write theirs.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import scrubbed_env  # noqa: E402

from lib import boundary_coverage as bc  # noqa: E402
from lib import coverage_algebra, evidence, gates  # noqa: E402
from lib import critic_consolidate as cc  # noqa: E402
from lib.core import GITIGNORE_ENTRIES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "plugin" / "bin" / "prawduct-hook"
_ids = itertools.count(1)

CUMULATIVE = cc.MODE_TOKEN_TO_VERBOSE["cumulative"]
VERIFY = cc.MODE_TOKEN_TO_VERBOSE["verify-resolutions"]
CHUNK = cc.MODE_TOKEN_TO_VERBOSE["chunk"]
#: A reviewer's BLOCKING finding, in the partial's shape.
_BLOCKER = {"name": "a defect in a", "goal": "3", "severity": "blocking",
            "recommendation": "fix it", "files": ["src/a.py"]}


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, files: dict, msg: str) -> str:
    for rel, content in files.items():
        _write(repo, rel, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


def _fragment(scope: str) -> dict:
    return {
        f".prawduct/changes/{scope}.md": (
            "---\nschema: 1\ntype: fix\n"
            f"scope: {scope}\ndate: 2026-11-25\ntitle: {scope}\ncloses: []\n---\n"
            f"What {scope} changed.\n\n## Consumer note\nnone: a fixture\n"
        )
    }


def _review(repo: Path, base_tree: str, head_tree: str, mode: str, *, blocking: bool = False,
            reviewed: "list[str] | None" = None, extra: "dict | None" = None) -> str:
    fact_id = f"rev-rb-{next(_ids):04d}"
    files = evidence.tree_diff(repo, base_tree, head_tree)
    body = {
        "base_tree": base_tree,
        "head_tree": head_tree,
        "files_changed": files,
        "files_reviewed": files if reviewed is None else reviewed,
        "findings": [{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}] if blocking else [],
        "mode": mode,
        **(extra or {}),
    }
    assert evidence.append_fact(repo, "review", fact_id, body)["status"] == "appended"
    return fact_id


def _resolve(repo: Path, review_id: str, fid: str = "R-1") -> None:
    body = {"finding": {"review_id": review_id, "fid": fid}, "disposition": "fixed"}
    assert evidence.append_fact(repo, "resolution", f"res-rb-{next(_ids):04d}", body)["status"] == "appended"


def _branch(repo: Path, name: str) -> str:
    _git(repo, "checkout", "-q", "-b", name, "main")
    return _tree(repo)


def _merge(repo: Path, name: str) -> str:
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)
    return _git(repo, "rev-parse", "HEAD")


def _cut(repo: Path, version: str, ship: tuple = ()) -> str:
    _git(repo, "checkout", "-q", "main")
    _write(repo, ".prawduct/changes/.gitkeep", "")
    for scope in ship:
        _git(repo, "rm", "-q", f".prawduct/changes/{scope}.md")
    return _commit(repo, {f".prawduct/releases/{version}.md": f"# {version}\n"}, f"release: prep {version}")


def _lane(repo: Path, scope: str, *, review: "str | None" = CHUNK) -> str:
    """A merged branch whose only review is ``review`` (an inner one by default),
    so the release check reads it not covered."""
    base = _branch(repo, scope)
    _commit(repo, {f"src/{scope}.py": f"{scope} = 1\n", **_fragment(scope)}, scope)
    if review is not None:
        _review(repo, base, _tree(repo), review)
    return _merge(repo, scope)


def _env(tmp_path: Path, repo: Path) -> dict:
    return {**scrubbed_env(tmp_path / "home", CLAUDE_PROJECT_DIR=str(repo)),
            "CLAUDE_PLUGIN_ROOT": str(ROOT / "plugin")}


def _hook(repo: Path, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK), *args], cwd=str(repo), capture_output=True,
                          text=True, timeout=120, env=_env(tmp_path, repo))


def _begin_release(repo: Path, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    return _hook(repo, tmp_path, "critic-begin", "--mode", "cumulative", "--span", "release", *extra)


def _manifest(repo: Path) -> dict:
    return json.loads((repo / ".prawduct" / ".critic-partials" / "manifest.json").read_text())


def _manifest_written(repo: Path) -> bool:
    return (repo / ".prawduct" / ".critic-partials" / "manifest.json").exists()


def _consolidate(repo: Path, tmp_path: Path, findings: "list[dict] | None" = None) -> str:
    manifest = _manifest(repo)
    partial = {
        "role": "reviewer", "goals": "1-7", "dispatch_id": manifest["id"],
        "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
        "duration_seconds": 60, "findings": findings or [], "summary": "release batch",
    }
    path = Path(manifest["rendezvous"]["reviewer"]["partial"])
    path = path if path.is_absolute() else repo / path
    path.write_text(json.dumps(partial))
    proc = _hook(repo, tmp_path, "critic-consolidate")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return manifest["id"]


def _coverage(repo: Path, tmp_path: Path) -> dict:
    proc = _hook(repo, tmp_path, "check-boundary-coverage", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return {e["commit"]: e for e in json.loads(proc.stdout)["entries"]}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    # The entries onboarding installs, so a consolidated review leaves the tree clean.
    _commit(repo, {"src/app.py": "x = 0\n", ".gitignore": "\n".join(GITIGNORE_ENTRIES) + "\n"}, "base")
    return repo


def _released(repo: Path) -> dict:
    """After a release: two lane merges with inner reviews only, one commit made on
    the base, and one merge its PR's cumulative covered."""
    _cut(repo, "v1.0.0")
    shapes = {"a": _lane(repo, "a"), "b": _lane(repo, "b")}
    shapes["direct"] = _commit(repo, {"src/direct.py": "d = 1\n"}, "direct work on main")
    shapes["pr"] = _lane(repo, "pr", review=CUMULATIVE)
    return shapes


# ---------------------------------------------------------------------------
# The dispatch: interval, subject and context
# ---------------------------------------------------------------------------


class TestTheReleaseDispatch:
    def test_the_interval_is_anchor_to_head_and_the_subject_is_what_was_owed(self, repo, tmp_path):
        _released(repo)
        anchor = bc.release_anchor(repo, "main")
        proc = _begin_release(repo, tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        m = _manifest(repo)
        assert (m["base_commit"], m["base_tree"]) == (anchor.commit, anchor.tree)
        assert (m["head_commit"], m["head_tree"]) == (_git(repo, "rev-parse", "HEAD"), _tree(repo))
        assert (m["span"], m["span_reason"], m["bounded_from"]) == ("release", anchor.reason, None)
        assert m["stage"] == "boundary"
        # The subject: the two lanes and the direct commit; the PR-covered merge is context.
        assert sorted(m["files_reviewed"]) == ["src/a.py", "src/b.py", "src/direct.py"]
        assert "src/pr.py" in m["files_context"] and "src/pr.py" not in m["files_reviewed"]
        assert m["signals"].endswith(f" · Span: release from {anchor.commit[:12]}")
        assert "release batch review of main" in proc.stderr

    def test_its_fact_is_never_an_edge_even_with_every_file_rated(self, repo, tmp_path):
        """Everything after the anchor is owed (no PR-covered merge), so the subject
        is every judgeable file and the fact would be a valid edge but for its span."""
        _cut(repo, "v1.0.0")
        _lane(repo, "a")
        assert _begin_release(repo, tmp_path).returncode == 0
        fid = _consolidate(repo, tmp_path)
        (fact,) = [f for f in evidence.read_facts(repo)["facts"] if f.get("id") == fid]
        body = fact["body"]
        assert body["span"] == "release"
        assert not [f for f in coverage_algebra.judgeable_files(body["files_changed"])
                    if f not in body["files_reviewed"]], "the fixture must rate every judgeable file"
        assert coverage_algebra.review_edges([fact]) == []
        verdict = coverage_algebra.coverage_verdict(
            [fact], body["base_tree"], body["head_tree"], lambda a, b: evidence.tree_diff(repo, a, b))
        assert verdict["status"] == "uncovered", verdict


# ---------------------------------------------------------------------------
# The relax-only rule, end to end
# ---------------------------------------------------------------------------


class TestTheBatchCreditsWhatItRead:
    def test_a_batch_review_covers_every_owed_entry_and_leaves_the_rest(self, repo, tmp_path):
        shapes = _released(repo)
        before = _coverage(repo, tmp_path)
        assert {before[shapes[k]]["classification"] for k in ("a", "b")} == {bc.INNER_ONLY}
        assert before[shapes["direct"]]["classification"] == bc.DIRECT
        assert before[shapes["pr"]]["classification"] == bc.PR_COVERED
        assert _begin_release(repo, tmp_path).returncode == 0
        fid = _consolidate(repo, tmp_path)
        after = _coverage(repo, tmp_path)
        for key in ("a", "b", "direct"):
            assert after[shapes[key]]["classification"] == bc.BATCH_COVERED, after[shapes[key]]
            assert fid in after[shapes[key]]["reason"]
        # A PR-covered merge outside the subject stays PR-covered, and did not stop
        # the batch crediting the others.
        assert after[shapes["pr"]]["classification"] == bc.PR_COVERED
        # Nothing owed now: a second release dispatch has nothing to rate.
        proc = _begin_release(repo, tmp_path)
        assert proc.returncode == 3, proc.stdout + proc.stderr
        assert "every release entry is already covered" in proc.stdout

    def test_a_merge_after_the_batch_review_is_not_credited_by_it(self, repo, tmp_path):
        _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        late = _lane(repo, "late")
        assert _coverage(repo, tmp_path)[late]["classification"] == bc.INNER_ONLY

    def test_a_review_starting_after_the_merge_is_not_credited_for_it(self, repo, tmp_path):
        """The other side of the bracket: a release-span review whose base is after
        the merge, rating the merge's file, does not read the merge's change."""
        _cut(repo, "v1.0.0")
        merge = _lane(repo, "a")
        start = _tree(repo)
        _commit(repo, {"src/a.py": "a = 2\n"}, "a later edit on main")
        _review(repo, start, _tree(repo), CUMULATIVE, extra={"span": "release"})
        assert _coverage(repo, tmp_path)[merge]["classification"] == bc.INNER_ONLY

    def test_the_review_s_own_head_is_no_fix_tail_for_a_commit_it_did_not_rate(self, repo, tmp_path):
        """A commit the batch did not rate, at the batch's own head tree, is not
        covered by composing that tree to itself: the tail starts after the review."""
        anchor_tree = _tree(repo, _cut(repo, "v1.0.0"))
        _lane(repo, "a")
        direct = _commit(repo, {"src/direct.py": "d = 1\n"}, "direct work on main")
        _review(repo, anchor_tree, _tree(repo), CUMULATIVE, reviewed=["src/a.py"],
                extra={"span": "release"})
        got = _coverage(repo, tmp_path)[direct]
        assert got["classification"] == bc.DIRECT, got

    def test_only_an_entry_naming_no_commit_is_uncreditable(self, repo, monkeypatch):
        """An entry with no commit on the base (a fragment no commit added, or a
        walk git could not run) is the one no review can bracket; it is named,
        and the rest of the subject still dispatches."""
        _cut(repo, "v1.0.0")
        _lane(repo, "a")
        real = bc.classify_pending(repo)
        ghost = bc.Entry("ghost", bc.UNKNOWN, "no first-parent commit added its fragment")
        monkeypatch.setattr(bc, "classify_pending",
                            lambda _p: bc.Report("ok", base=real.base, entries=[*real.entries, ghost],
                                                 anchor=real.anchor))
        subject = bc.release_subject(repo, clean=True)
        assert subject.status == bc.RELEASE_OK, subject.reason
        assert subject.uncreditable == [ghost]
        assert coverage_algebra.judgeable_files(subject.files) == ["src/a.py"]
        assert subject.start[0] == real.anchor.commit

    def test_an_owed_entry_before_the_anchor_is_read_and_credited(self, repo, tmp_path):
        """A pruned release withheld `w`; a lane merged after the anchor is owed too.
        The span starts at `w`'s first parent, so one review rates both, and the
        release check credits both. Until Chunk 06 the span started at the anchor
        and `w` could never be credited: a per_release release held forever."""
        w = _lane(repo, "w")
        _cut(repo, "v1.0.0")
        a = _lane(repo, "a")
        proc = _begin_release(repo, tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        m = _manifest(repo)
        assert m["base_commit"] == _git(repo, "rev-parse", f"{w}^1"), m["base_commit"]
        assert m["span"] == "release" and "before the release anchor" in m["span_reason"], m["span_reason"]
        assert sorted(m["files_reviewed"]) == ["src/a.py", "src/w.py"]
        assert "cannot credit" not in proc.stderr, proc.stderr
        _consolidate(repo, tmp_path)
        got = _coverage(repo, tmp_path)
        assert {got[w]["classification"], got[a]["classification"]} == {bc.BATCH_COVERED}, got

    def test_a_batch_blocker_holds_the_entries_until_verify_resolutions_resolves_it(self, repo, tmp_path):
        shapes = _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        batch = _consolidate(repo, tmp_path, findings=[_BLOCKER])
        (fact,) = [f for f in evidence.read_facts(repo)["facts"] if f.get("id") == batch]
        fid = coverage_algebra.blocking_findings(fact)[0]["fid"]
        blocked = _coverage(repo, tmp_path)
        entry = blocked[shapes["a"]]
        assert entry["classification"] == bc.INNER_ONLY, entry
        assert batch in entry["reason"] and "unresolved blocking" in entry["reason"], entry
        # The fix, committed on the base, and a verify pass anchored to the batch.
        reviewed = fact["body"]["head_tree"]
        fix = _commit(repo, {"src/a.py": "a = 2\n"}, "fix the batch finding")
        _review(repo, reviewed, _tree(repo), VERIFY, extra={"verifies": batch})
        _resolve(repo, batch, fid)
        fixed = _coverage(repo, tmp_path)
        for key in ("a", "b", "direct"):
            assert fixed[shapes[key]]["classification"] == bc.BATCH_COVERED, fixed[shapes[key]]
        assert fixed[fix]["classification"] == bc.BATCH_COVERED, fixed[fix]
        assert batch in fixed[fix]["reason"] and "verify-resolutions" in fixed[fix]["reason"]

    def test_a_branch_merged_over_a_blocker_is_not_credited_until_it_is_resolved(self, repo, tmp_path):
        """W2: the PR gate refuses a blocked branch, so this merge bypassed it,
        and catching bypassed merges is the release check's job. A clean batch
        review that outlives the blocker does not clear it: only a resolution
        does (`BLOCKING findings clear only through verify-resolutions`)."""
        _cut(repo, "v1.0.0")
        base = _branch(repo, "a")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("a")}, "a")
        blocker = _review(repo, base, _tree(repo), CHUNK, blocking=True)
        branch_tip = _tree(repo)
        # The base moves first, so the merge's tree (the batch review's head) is
        # not the branch tip's, where the blocker stands: only the entry's own
        # trees can carry it to the batch rule.
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        merge = _merge(repo, "a")
        assert _tree(repo, merge) != branch_tip, "the fixture must keep the blocker off the batch's trees"
        before = _coverage(repo, tmp_path)[merge]
        assert before["classification"] == bc.UNCOVERED and "unresolved blocking" in before["reason"], before
        assert _begin_release(repo, tmp_path).returncode == 0
        batch = _consolidate(repo, tmp_path)
        after = _coverage(repo, tmp_path)[merge]
        assert after["classification"] == bc.UNCOVERED, after
        assert batch in after["reason"] and f"{blocker} R-1" in after["reason"], after
        assert "the commit's own" in after["reason"], after
        _resolve(repo, blocker)
        resolved = _coverage(repo, tmp_path)[merge]
        assert resolved["classification"] == bc.BATCH_COVERED and batch in resolved["reason"], resolved

    def test_verify_resolutions_dispatches_on_the_base_against_the_batch(self, repo, tmp_path):
        """The fix tail's route exists: after the batch blocker is fixed on the base,
        a verify pass anchors to the batch review and names its blocker."""
        _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        batch = _consolidate(repo, tmp_path, findings=[_BLOCKER])
        _commit(repo, {"src/a.py": "a = 2\n"}, "fix the batch finding")
        proc = _hook(repo, tmp_path, "critic-begin", "--mode", "verify-resolutions")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        m = _manifest(repo)
        assert m["verifies"] == batch
        assert any("a defect in a" in d for d in m.get("dispatch_directives") or []), m.get("dispatch_directives")


class TestTheBatchFixTail:
    def test_a_fix_on_the_base_with_no_verify_pass_is_direct(self, repo, tmp_path):
        _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        fix = _commit(repo, {"src/a.py": "a = 2\n"}, "unverified edit")
        assert _coverage(repo, tmp_path)[fix]["classification"] == bc.DIRECT

    def test_a_verify_pass_ending_before_a_later_commit_does_not_cover_it(self, repo, tmp_path):
        _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        batch = _consolidate(repo, tmp_path)
        reviewed = _tree(repo)
        fix = _commit(repo, {"src/a.py": "a = 2\n"}, "fix")
        _review(repo, reviewed, _tree(repo), VERIFY, extra={"verifies": batch})
        later = _commit(repo, {"src/later.py": "l = 1\n"}, "new work after the verify")
        got = _coverage(repo, tmp_path)
        assert got[fix]["classification"] == bc.BATCH_COVERED
        assert got[later]["classification"] == bc.DIRECT

    def test_a_tail_from_a_blocked_review_is_not_covered(self, repo, tmp_path):
        _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        batch = _consolidate(repo, tmp_path, findings=[_BLOCKER])
        reviewed = _tree(repo)
        fix = _commit(repo, {"src/a.py": "a = 2\n"}, "fix")
        _review(repo, reviewed, _tree(repo), VERIFY, extra={"verifies": batch})
        assert _coverage(repo, tmp_path)[fix]["classification"] == bc.DIRECT

    def test_a_chunk_review_is_not_a_verify_only_tail(self, repo, tmp_path):
        _released(repo)
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        reviewed = _tree(repo)
        work = _commit(repo, {"src/new.py": "n = 1\n"}, "new work")
        _review(repo, reviewed, _tree(repo), CHUNK)
        assert _coverage(repo, tmp_path)[work]["classification"] == bc.DIRECT


# ---------------------------------------------------------------------------
# The control: no PR gate moves because a batch fact exists
# ---------------------------------------------------------------------------


class TestNoGateMoves:
    def _branch_with_inner_review(self, repo: Path) -> "tuple[str, str]":
        _cut(repo, "v1.0.0")
        base = _branch(repo, "feature")
        _commit(repo, {"src/feature.py": "f = 1\n"}, "feature work")
        return base, _tree(repo)

    def test_a_batch_fact_over_exactly_the_branch_s_span_does_not_cover_it(self, repo, tmp_path):
        """The strongest shape: a release-span fact whose trees are the branch's own
        span and which rated every file. Without its span it would be an edge and the
        branch would read covered; with it, the gate reads exactly what it read."""
        base, tip = self._branch_with_inner_review(repo)
        before = gates.branch_coverage_verdict(repo)["status"]
        before_rc = gates.check_cumulative_critic(repo)
        _review(repo, base, tip, CUMULATIVE, extra={"span": "release"})
        assert gates.branch_coverage_verdict(repo)["status"] == before == "uncovered"
        assert gates.check_cumulative_critic(repo) == before_rc != 0
        # Positive control: the same fact without the span covers the branch.
        _review(repo, base, tip, CUMULATIVE)
        assert gates.branch_coverage_verdict(repo)["status"] == "covered"

    def test_a_clean_batch_fact_beside_a_covered_branch_changes_nothing(self, repo, tmp_path):
        base, tip = self._branch_with_inner_review(repo)
        _review(repo, base, tip, CHUNK)
        before = gates.branch_coverage_verdict(repo)
        _review(repo, base, tip, CUMULATIVE, reviewed=[], extra={"span": "release"})
        after = gates.branch_coverage_verdict(repo)
        assert (before["status"], after["status"]) == ("covered", "covered")

    def test_a_batch_blocker_still_stands_at_its_trees(self, repo, tmp_path):
        """Its findings are a property of the trees it read (CRT-5H2D), so a branch
        standing on one sees them: the batch fact can block, never cover."""
        base, tip = self._branch_with_inner_review(repo)
        _review(repo, base, tip, CHUNK)
        _review(repo, base, tip, CUMULATIVE, blocking=True, extra={"span": "release"})
        assert gates.branch_coverage_verdict(repo)["status"] == "blocked"


    def test_a_release_batch_blocker_does_not_hold_a_branch_forked_at_its_tree(self, repo, tmp_path):
        """The native review's cross-branch blocker: the release batch review is
        taken at the base's tip, and a branch forked there stands on that tree
        as its merge-base. Its blocker says the base is not fit to RELEASE, owed
        by the release check and the base's verify pass, never by unrelated work
        built on top. Control: the same blocker on an ordinary review holds it."""
        _cut(repo, "v1.0.0")
        tip = _tree(repo)
        batch = _review(repo, _tree(repo, "main~1"), tip, CUMULATIVE, blocking=True,
                        extra={"span": "release"})
        _branch(repo, "feature")
        _commit(repo, {"src/feature.py": "f = 1\n"}, "unrelated work")
        _review(repo, tip, _tree(repo), CHUNK)
        assert gates.branch_coverage_verdict(repo)["status"] == "covered"
        # The release check still counts it, at the base's own tree.
        (fact,) = [f for f in evidence.read_facts(repo)["facts"] if f.get("id") == batch]
        facts = evidence.read_facts(repo)["facts"]
        assert coverage_algebra.batch_review_blockers(facts, fact)
        verdict = coverage_algebra.coverage_verdict(facts, tip, tip, lambda a, b: evidence.tree_diff(repo, a, b))
        assert verdict["status"] == "blocked", verdict
        _review(repo, _tree(repo, "main~1"), tip, CUMULATIVE, blocking=True)  # the control
        assert gates.branch_coverage_verdict(repo)["status"] == "blocked"


# ---------------------------------------------------------------------------
# Every refusal, named
# ---------------------------------------------------------------------------


class TestEveryRefusalIsNamed:
    def _refused(self, proc: subprocess.CompletedProcess, code: str, repo: Path) -> None:
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert f"--span release refused ({code})" in proc.stderr, proc.stderr
        assert not _manifest_written(repo)

    def test_off_the_base_branch(self, repo, tmp_path):
        _released(repo)
        _branch(repo, "feature")
        proc = _begin_release(repo, tmp_path)
        self._refused(proc, bc.RELEASE_OFF_BASE, repo)
        assert "this one is on feature" in proc.stderr

    def test_on_the_base_but_not_at_its_tip(self, repo, tmp_path):
        """The base is the remote's branch, and local main is a commit ahead of it."""
        _released(repo)
        remote = tmp_path / "remote.git"
        _git(repo, "clone", "-q", "--bare", str(repo), str(remote))
        _git(repo, "remote", "add", "origin", str(remote))
        _git(repo, "fetch", "-q", "origin")
        _commit(repo, {"src/unpushed.py": "u = 1\n"}, "not pushed")
        proc = _begin_release(repo, tmp_path)
        self._refused(proc, bc.RELEASE_OFF_BASE, repo)
        assert "is not origin/main's tip" in proc.stderr

    def test_at_the_remote_base_s_tip_it_dispatches(self, repo, tmp_path):
        """Control for the one above: pushed, the same checkout dispatches."""
        _released(repo)
        remote = tmp_path / "remote.git"
        _git(repo, "clone", "-q", "--bare", str(repo), str(remote))
        _git(repo, "remote", "add", "origin", str(remote))
        _git(repo, "fetch", "-q", "origin")
        proc = _begin_release(repo, tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_on_a_dirty_tree(self, repo, tmp_path):
        _released(repo)
        _write(repo, "src/a.py", "a = 99\n")
        self._refused(_begin_release(repo, tmp_path), bc.RELEASE_DIRTY, repo)

    def test_with_no_release_anchor(self, repo, tmp_path):
        _lane(repo, "a")
        proc = _begin_release(repo, tmp_path)
        self._refused(proc, bc.RELEASE_NO_ANCHOR, repo)
        assert "no first-parent commit on main adds a release file" in proc.stderr

    def test_when_what_is_owed_changes_nothing_still_there(self, repo, tmp_path):
        """A lane added `src/a.py` and work on the base removed it again: both
        are owed, and nothing they changed still differs from where the span
        starts, so a batch review would rate nothing. (Until Chunk 06 this was
        the withheld-before-the-anchor case, which now dispatches: below.)"""
        _cut(repo, "v1.0.0")
        _lane(repo, "a")
        _git(repo, "rm", "-q", "src/a.py")
        _git(repo, "commit", "-q", "-m", "drop a again")
        proc = _begin_release(repo, tmp_path)
        self._refused(proc, bc.RELEASE_NO_SUBJECT, repo)
        assert "change no judgeable file that still differs from" in proc.stderr, proc.stderr

    def test_what_is_owed_before_the_anchor_alone_starts_the_span_there(self, repo, tmp_path):
        """A pruned release withheld scope `w`: merged before the anchor, still
        pending. Started at the anchor no review could bracket it and the
        release would be held forever, so the span starts at `w`'s first parent."""
        merge = _lane(repo, "w")
        _cut(repo, "v1.0.0")
        proc = _begin_release(repo, tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        m = _manifest(repo)
        assert m["base_commit"] == _git(repo, "rev-parse", f"{merge}^1")
        assert m["files_reviewed"] == ["src/w.py"]
        assert "before the release anchor" in proc.stderr, proc.stderr

    def test_with_nothing_owed_it_is_exit_3(self, repo, tmp_path):
        _cut(repo, "v1.0.0")
        _lane(repo, "pr", review=CUMULATIVE)
        proc = _begin_release(repo, tmp_path)
        assert proc.returncode == 3, proc.stdout + proc.stderr
        assert "no review needed" in proc.stdout and "already covered" in proc.stdout
        # The release wording, not the coverage-gate interval block.
        assert "`prawduct-hook check-boundary-coverage` already reads every release entry" in proc.stdout
        assert "free files" not in proc.stdout
        assert not _manifest_written(repo)

    def test_force_overrides_none_of_them(self, repo, tmp_path):
        _cut(repo, "v1.0.0")
        _lane(repo, "pr", review=CUMULATIVE)
        assert _begin_release(repo, tmp_path, "--force").returncode == 3
        _branch(repo, "feature")
        self._refused(_begin_release(repo, tmp_path, "--force"), bc.RELEASE_OFF_BASE, repo)

    def test_a_classification_that_cannot_run_is_unevaluable(self, repo, monkeypatch):
        _released(repo)
        monkeypatch.setattr(bc, "classify_pending",
                            lambda _p: bc.Report("unevaluable", reason="the store is from the future"))
        got = cc.begin_review(repo, "cumulative", span_request="release")
        assert (got["status"], got["kind"]) == ("error", f"release-{bc.RELEASE_UNEVALUABLE}"), got
        assert "the store is from the future" in got["reason"]

    def test_a_fault_is_unevaluable_not_a_traceback(self, repo, monkeypatch):
        _released(repo)

        def boom(_p):
            raise RuntimeError("injected")

        monkeypatch.setattr(bc, "classify_pending", boom)
        got = bc.release_subject(repo, clean=True)
        assert (got.status, got.code) == (bc.RELEASE_REFUSED, bc.RELEASE_UNEVALUABLE)
        assert "RuntimeError: injected" in got.reason

    @pytest.mark.parametrize("args", [("--mode", "chunk", "--span", "release"),
                                      ("--mode", "cumulative", "--span", "full")])
    def test_a_span_other_than_a_cumulative_release_is_refused(self, repo, tmp_path, args):
        _released(repo)
        proc = _hook(repo, tmp_path, "critic-begin", *args)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "the only span a dispatch may ask for is `release`" in proc.stderr
        assert not _manifest_written(repo)


class TestTailDeferred:
    def test_it_is_not_covered_and_a_release_review_owes_it_a_read(self, repo, monkeypatch):
        """Chunk 05's PR gate produces it; here it must read not covered, so the
        release check holds it and the batch review rates it."""
        assert bc.TAIL_DEFERRED in bc.CLASSES and bc.TAIL_DEFERRED not in bc.COVERED
        shapes = _released(repo)
        real = bc.classify_pending

        def deferred(project_dir):
            report = real(project_dir)
            for entry in report.entries:
                if entry.classification in bc.COVERED:
                    entry.classification = bc.TAIL_DEFERRED
            return report

        monkeypatch.setattr(bc, "classify_pending", deferred)
        subject = bc.release_subject(repo, clean=True)
        assert subject.status == bc.RELEASE_OK, subject
        assert shapes["pr"] in {e.commit for e in subject.owed}
        assert "src/pr.py" in subject.files


# ---------------------------------------------------------------------------
# The round budget never charges it (Chunk 06)
# ---------------------------------------------------------------------------


class TestTheRoundBudgetNeverChargesIt:
    """A release batch review is the release's own step on the integration
    branch, not a round on a scope's body of work: charged, a scope resolving on
    the base could refuse it, holding a per_release release with `--force` the
    only route."""

    def test_a_release_span_is_cadence_and_takes_no_boundary_slot(self):
        body_of = {"r1": {"mode": CUMULATIVE, "span": "release"}, "b1": {"mode": CUMULATIVE},
                   "r2": {"mode": CUMULATIVE, "span": "release"}, "b2": {"mode": CUMULATIVE}}
        # b1 keeps the scope's first-boundary slot; b2 is a charged repeat.
        assert cc._cadence_round_ids(["r1", "b1", "r2", "b2"], body_of) == {"r1", "b1", "r2"}

    def test_the_dispatch_passes_an_exhausted_budget(self, repo, tmp_path):
        _commit(repo, {".prawduct/project-state.yaml": "review_round_budget: 1\n"}, "budget")
        _released(repo)
        head = _tree(repo)
        for _ in range(2):  # the first takes the boundary slot, the second spends the budget
            _review(repo, head, head, CUMULATIVE, extra={"scope": "x"})
        proc = _begin_release(repo, tmp_path, "--scope", "x")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _manifest(repo)["span"] == "release"
