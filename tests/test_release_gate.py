"""The release check blocks a per_release release (#1232 Chunk 06).

Under ``boundary_review: per_release`` (read at the integration branch's tip,
``review_lane.release_policy``) the boundary review an eligible branch moved to
the release, and a fix tail the PR gate deferred to it, are owed to ONE verdict,
``boundary_coverage.release_gate``. Two callers read it, each pinned at its own
layer: ``check-boundary-coverage --gate`` exits with it, and
``check-releasability`` refuses on it. Under ``per_pr`` (the default) both stay
advice and every exit is what it was.

Real git repositories and the real CLI: the policy is a tracked
``project-state.yaml``, the anchor a committed release file or a tag, the batch
review a ``critic-begin --span release`` dispatch consolidated through the store.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from lib import boundary_coverage as bc  # noqa: E402
from lib import release_readiness, review_lane  # noqa: E402
from lib.core import GITIGNORE_ENTRIES  # noqa: E402
from test_fix_tail_deferral import _merged as _tail_merged
from test_release_batch_review import (
    CHUNK as _CHUNK,
    HOOK,
    ROOT,
    _begin_release,
    _branch,
    _commit,
    _consolidate,
    _cut,
    _env,
    _fragment,
    _git,
    _hook,
    _lane,
    _manifest,
    _merge,
    _review,
    _tree,
)

_PLAN = (
    "# Release plan v1.1.0\n\n## Release classification\n\n"
    "| Scope | Disposition | Blocker |\n|---|---|---|\n"
)


def _repo(tmp_path: Path, key: "str | None" = "per_release", base: str = "main") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    state = f"base_branch: {base}\n" + (f"boundary_review: {key}\n" if key else "")
    _commit(repo, {"src/app.py": "x = 0\n", ".gitignore": "\n".join(GITIGNORE_ENTRIES) + "\n",
                   ".prawduct/project-state.yaml": state}, "base")
    return repo


def _released(repo: Path, *scopes: str) -> None:
    """A release, its classification table for ``scopes`` (committed on the base:
    a `.prawduct/` file, so not walked), then a lane merge per scope with an inner
    review only, which the release check reads not covered."""
    _cut(repo, "v1.0.0")
    rows = "".join(f"| {s} | ships | |\n" for s in scopes)
    _commit(repo, {".prawduct/artifacts/release-plan-v1.1.0.md": _PLAN + rows}, "release plan")
    for scope in scopes:
        _lane(repo, scope)


def _gate(repo: Path, tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    return _hook(repo, tmp_path, "check-boundary-coverage", "--gate", *extra)


def _unrelated_root(repo: Path, files: dict) -> str:
    """A root commit holding ``files``, sharing no history with ``main``, built
    with a scratch index so the checkout (and its ignored files) is untouched."""
    env = {**os.environ, "GIT_INDEX_FILE": str(repo / ".git" / "scratch-index")}

    def git(*args: str, stdin: "str | None" = None) -> str:
        proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                              input=stdin, env=env, timeout=15)
        assert proc.returncode == 0, proc.stderr
        return proc.stdout.strip()

    for rel, content in files.items():
        blob = git("hash-object", "-w", "--stdin", stdin=content)
        git("update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}")
    return git("commit-tree", git("write-tree"), "-m", "an unrelated root")


def _gate_injected(repo: Path, tmp_path: Path, patch: str) -> subprocess.CompletedProcess:
    """``check-boundary-coverage --gate`` in a child whose sitecustomize defines
    ``boom`` (raises ``RuntimeError: injected``) and runs ``patch``."""
    inject = tmp_path / "inject"
    inject.mkdir(exist_ok=True)
    (inject / "sitecustomize.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'plugin')!r})\n"
        "def boom(*_a, **_k):\n    raise RuntimeError('injected')\n" + patch,
        encoding="utf-8",
    )
    return subprocess.run([sys.executable, str(HOOK), "check-boundary-coverage", "--gate"],
                          cwd=str(repo), capture_output=True, text=True, timeout=120,
                          env={**_env(tmp_path, repo), "PYTHONPATH": str(inject)})


@pytest.fixture
def green_suite(monkeypatch):
    """The suite verdict is not what these tests are about: a fixture staging a
    release must not be refused for an unrelated missing evidence record."""
    monkeypatch.setattr(release_readiness, "_suite_verdict", lambda _p: (True, "a fixture"))


def _releasability(repo: Path, capsys) -> "tuple[int, str, str]":
    rc = release_readiness.check_releasability(repo, "v1.1.0")
    got = capsys.readouterr()
    return rc, got.out, got.err


def _refusal(err: str, code: str) -> str:
    (line,) = [ln for ln in err.splitlines() if ln.startswith(f"{code}:")]
    return line


# ---------------------------------------------------------------------------
# check-boundary-coverage --gate: the exit table
# ---------------------------------------------------------------------------


class TestTheGateExitTable:
    """| policy | answer | `--gate` | bare op |
    | per_release | not covered | 1 boundary-uncovered | 0 |
    | per_release | covered | 0 | 0 |
    | per_release | no anchor | 3 boundary-unevaluable | 0 |
    | per_release | unevaluable / refused fragment | 3 boundary-unevaluable | 3 / 0 |
    | per_pr | any | 0 | unchanged |"""

    def test_an_unreviewed_lane_merge_is_exit_1_naming_the_batch_review(self, tmp_path):
        repo = _repo(tmp_path)
        _released(repo, "a")
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        line = _refusal(proc.stderr, bc.GATE_UNCOVERED)
        assert "1 of 1 release entry on main no boundary review covered" in line, line
        assert "critic-begin --mode cumulative --span release" in line, line
        assert "verify-resolutions" in line, line
        assert "boundary_review: per_release (read at main)" in proc.stdout
        # The bare op's exit is a published meaning and does not move.
        bare = _hook(repo, tmp_path, "check-boundary-coverage")
        assert bare.returncode == 0, bare.stderr

    def test_after_a_release_batch_review_it_passes(self, tmp_path):
        repo = _repo(tmp_path)
        _released(repo, "a", "b")
        assert _gate(repo, tmp_path).returncode == 1
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "batch-covered" in proc.stdout and not proc.stderr.strip()

    def test_a_batch_blocker_holds_it_until_resolved(self, tmp_path):
        repo = _repo(tmp_path)
        _released(repo, "a")
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path, findings=[{
            "name": "a defect in a", "goal": "3", "severity": "blocking",
            "recommendation": "fix it", "files": ["src/a.py"]}])
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "unresolved blocking" in proc.stdout

    def test_no_release_anchor_is_exit_3_with_the_route_out(self, tmp_path):
        repo = _repo(tmp_path)
        _lane(repo, "a")
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 3, proc.stdout + proc.stderr
        line = _refusal(proc.stderr, bc.GATE_UNEVALUABLE)
        assert "there is no release anchor" in line and "git tag vX.Y.Z <commit>" in line, line
        assert "keeps `per_pr` until its first" in line, line

    def test_no_anchor_and_every_entry_covered_still_refuses(self, tmp_path):
        """Nothing since a release could be walked, so "covered" is a claim about
        the fragments alone: work committed with none would ship unseen."""
        repo = _repo(tmp_path)
        _lane(repo, "pr", review=bc_cumulative())
        assert _gate(repo, tmp_path).returncode == 3

    def test_an_unresolvable_base_fails_closed_on_the_checkout_s_declaration(self, tmp_path):
        """No integration base resolves, so the policy cannot be read there: this
        checkout's `per_release` stands, and the unanswered check refuses."""
        repo = _repo(tmp_path, base="nowhere")
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 3, proc.stdout + proc.stderr
        assert "the release check fails closed" in proc.stdout, proc.stdout
        line = _refusal(proc.stderr, bc.GATE_UNEVALUABLE)
        assert "could not be evaluated (no integration base resolves" in line, line
        # Control: the same unresolvable base without the key is per_pr advice.
        per_pr = _repo(tmp_path / "per_pr", key=None, base="nowhere")
        assert _gate(per_pr, tmp_path).returncode == 0

    def test_a_fragment_the_pending_set_refused_is_exit_3(self, tmp_path):
        repo = _repo(tmp_path)
        _cut(repo, "v1.0.0")
        _commit(repo, {".prawduct/changes/bad.md": "no frontmatter here\n"}, "a bad fragment")
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 3, proc.stdout + proc.stderr
        assert "the pending set refused are not classified" in _refusal(proc.stderr, bc.GATE_UNEVALUABLE)

    def test_a_merged_deferred_tail_is_exit_1(self, tmp_path):
        """The PR gate let it merge as a deferral; the release check reads it
        `tail-deferred`, not covered, until a batch review has read it."""
        repo, merge = _tail_merged(tmp_path)
        _git(repo, "tag", "v1.0.0", f"{merge}^1")  # the release the tail merged after
        (repo / ".prawduct" / "changes").mkdir(parents=True, exist_ok=True)  # a change record
        proc = _gate(repo, tmp_path)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "tail-deferred" in proc.stdout and _refusal(proc.stderr, bc.GATE_UNCOVERED)

    def test_an_octopus_merge_is_owed_and_a_batch_review_credits_it(self, tmp_path):
        """Read branch by branch it is `unknown`, which nothing used to credit, so
        a per_release release holding one was held for good."""
        repo = _repo(tmp_path)
        _cut(repo, "v1.0.0")
        for name in ("o1", "o2"):
            _git(repo, "checkout", "-q", "-b", name, "main")
            _commit(repo, {f"src/{name}.py": f"{name} = 1\n"}, name)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "octopus", "o1", "o2")
        octopus = _git(repo, "rev-parse", "HEAD")
        proc = _gate(repo, tmp_path, "--json")
        assert proc.returncode == 1, proc.stdout
        (entry,) = [e for e in json.loads(proc.stdout)["entries"] if e["commit"] == octopus]
        assert entry["classification"] == bc.UNKNOWN and "octopus" in entry["reason"], entry
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        proc = _gate(repo, tmp_path, "--json")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        (entry,) = [e for e in json.loads(proc.stdout)["entries"] if e["commit"] == octopus]
        assert entry["classification"] == bc.BATCH_COVERED, entry

    def test_an_unrelated_history_merge_is_owed_and_a_batch_review_credits_it(self, tmp_path):
        """W1: a merge whose side shares no merge-base with the base (a subtree
        import, `--allow-unrelated-histories`) reads `unknown`. The gate's remedy
        dispatches a batch review that rates what it brought onto the base, so
        that review must credit it, or running the remedy changes nothing and
        the release is held for good."""
        repo = _repo(tmp_path)
        _cut(repo, "v1.0.0")
        side = _unrelated_root(repo, {"src/vendor.py": "v = 1\n"})
        _git(repo, "merge", "-q", "--no-ff", "--allow-unrelated-histories", "-m", "import vendor", side)
        merge = _git(repo, "rev-parse", "HEAD")
        proc = _gate(repo, tmp_path, "--json")
        assert proc.returncode == 1, proc.stdout + proc.stderr
        (entry,) = [e for e in json.loads(proc.stdout)["entries"] if e["commit"] == merge]
        assert entry["classification"] == bc.UNKNOWN and "no merge-base" in entry["reason"], entry
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        proc = _gate(repo, tmp_path, "--json")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        (entry,) = [e for e in json.loads(proc.stdout)["entries"] if e["commit"] == merge]
        assert entry["classification"] == bc.BATCH_COVERED, entry

    def test_a_policy_read_that_fails_is_exit_3_not_main_s_floor(self, tmp_path):
        """The native review's `--gate` nit: a failure reading the policy must
        never reach main()'s exit 1, which reads as `boundary-uncovered`. Under a
        checkout declaring per_release the read's failure is named, exit 3."""
        repo = _repo(tmp_path)
        _released(repo, "a")
        proc = _gate_injected(repo, tmp_path, "from lib import review_lane as m\n"
                                              "m._release_policy = boom\n")
        assert proc.returncode == 3, proc.stdout + proc.stderr
        line = _refusal(proc.stderr, bc.GATE_UNEVALUABLE)
        assert "could not be read at the integration branch (RuntimeError: injected)" in line, line
        assert "Traceback" not in proc.stderr and bc.GATE_UNCOVERED not in proc.stderr

    def test_a_walk_git_could_not_run_is_exit_3_not_uncovered(self, tmp_path):
        """A shallow clone or a corrupt ref fails `git log anchor..base`: that is
        a check that could not answer, not unreviewed work, and no batch review
        could ever credit the entry standing for it."""
        repo = _repo(tmp_path)
        _cut(repo, "v1.0.0")
        _lane(repo, "a", review=bc_cumulative())
        assert _gate(repo, tmp_path).returncode == 0  # control: the walk runs and covers
        proc = _gate_injected(repo, tmp_path, "from lib import boundary_coverage as m\n"
                                              "m._Classifier.walk = lambda self, anchor: None\n")
        assert proc.returncode == 3, proc.stdout + proc.stderr
        line = _refusal(proc.stderr, bc.GATE_UNEVALUABLE)
        assert "git could not list the first-parent commits on main since the release anchor" in line, line
        assert bc.GATE_UNCOVERED not in proc.stderr

    def test_a_fault_in_the_verdict_is_exit_3_not_main_s_floor(self, tmp_path):
        repo = _repo(tmp_path)
        _released(repo, "a")
        proc = _gate_injected(repo, tmp_path, "from lib import boundary_coverage as m\n"
                                              "m.release_gate = boom\n")
        assert proc.returncode == 3, proc.stdout + proc.stderr
        line = _refusal(proc.stderr, bc.GATE_UNEVALUABLE)
        assert "the release gate could not be evaluated (RuntimeError: injected)" in line, line
        assert "Traceback" not in proc.stderr

    def test_per_pr_passes_whatever_it_found(self, tmp_path):
        for name, shape in (("uncovered", lambda r: _released(r, "a")),
                            ("no-anchor", lambda r: _lane(r, "a"))):
            repo = _repo(tmp_path / name, key=None)
            shape(repo)
            proc = _gate(repo, tmp_path)
            assert proc.returncode == 0, (name, proc.stdout + proc.stderr)
            assert "boundary_review: per_pr (read at main); the release check does not block on this" \
                in proc.stdout, proc.stdout
            assert bc.GATE_UNCOVERED not in proc.stderr and bc.GATE_UNEVALUABLE not in proc.stderr

    def test_json_carries_the_policy_and_the_gate(self, tmp_path):
        repo = _repo(tmp_path)
        _released(repo, "a")
        proc = _gate(repo, tmp_path, "--json")
        assert proc.returncode == 1
        got = json.loads(proc.stdout)
        assert got["policy"] == {"value": "per_release", "source": "main", "note": ""}
        assert (got["gate"]["exit"], got["gate"]["code"]) == (1, bc.GATE_UNCOVERED)
        assert got["counts"][bc.INNER_ONLY] == 1  # the report's keys still ride
        # The bare --json is unchanged: no policy, no gate.
        bare = json.loads(_hook(repo, tmp_path, "check-boundary-coverage", "--json").stdout)
        assert "policy" not in bare and "gate" not in bare

    def test_the_note_says_why_a_checkout_s_per_release_is_not_in_force(self, tmp_path):
        """`Policy.note` reaches the operator: a checkout declaring per_release
        that the integration branch's tip does not is told so, and not gated."""
        repo = _repo(tmp_path, key=None)
        _released(repo, "a")
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "base_branch: main\nboundary_review: per_release\n")
        got = json.loads(_gate(repo, tmp_path, "--json").stdout)
        assert got["policy"]["value"] == "per_pr"
        assert "this checkout declares `boundary_review: per_release` and main's tip does not" \
            in got["policy"]["note"], got["policy"]
        assert got["gate"]["exit"] == 0


class TestAMergedBranchBlockerClearsOnTheBase:
    """The route the gate names for a merge whose branch carries an unresolved
    BLOCKING finding (its PR gate was bypassed) terminates. The batch review
    never clears that blocker (it is not the batch's), and BLOCKING findings
    clear only through `verify-resolutions`, so the verify pass on the base must
    be told it: its roll-call names it (`release_owed_blockers`), its resolution
    clears it, and the release passes. Every step is the real CLI."""

    @staticmethod
    def _verify_consolidate(repo: Path, tmp_path: Path, resolutions: list) -> str:
        manifest = _manifest(repo)
        partial = {
            "role": "reviewer", "goals": "1-7", "dispatch_id": manifest["id"],
            "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
            "duration_seconds": 60, "findings": [], "resolutions": resolutions,
            "summary": "verify the branch blocker's fix",
        }
        path = Path(manifest["rendezvous"]["reviewer"]["partial"])
        path = path if path.is_absolute() else repo / path
        path.write_text(json.dumps(partial))
        proc = _hook(repo, tmp_path, "critic-consolidate")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return manifest["id"]

    def test_gate_batch_gate_verify_gate(self, tmp_path):
        repo = _repo(tmp_path)
        _cut(repo, "v1.0.0")
        base = _branch(repo, "a")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("a")}, "a")
        blocker = _review(repo, base, _tree(repo), _CHUNK, blocking=True)
        # The base moves first, so the blocker stands on the branch's tree only,
        # never on a tree the batch review records.
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        _merge(repo, "a")

        held = _gate(repo, tmp_path)
        assert held.returncode == 1, held.stdout + held.stderr
        line = _refusal(held.stderr, bc.GATE_UNCOVERED)
        assert f"({blocker} R-1), a merged branch's" in line, line
        assert "run `/prawduct:critic verify-resolutions` there, whose roll-call names it" in line, line

        # The batch review, by the remedy's own invocation: a plain cumulative here.
        assert _hook(repo, tmp_path, "critic-begin", "--mode", "cumulative").returncode == 0
        assert _manifest(repo)["span"] == "release"
        _consolidate(repo, tmp_path)
        still = _gate(repo, tmp_path)
        assert still.returncode == 1, still.stdout + still.stderr
        assert f"({blocker} R-1), a merged branch's" in _refusal(still.stderr, bc.GATE_UNCOVERED)

        _commit(repo, {"src/a.py": "a = 2\n"}, "fix the branch's blocker on the base")
        proc = _hook(repo, tmp_path, "critic-begin", "--mode", "verify-resolutions")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        roll_call = [d for d in _manifest(repo).get("dispatch_directives") or [] if blocker in d]
        assert roll_call and "R-1" in roll_call[0], _manifest(repo).get("dispatch_directives")
        self._verify_consolidate(repo, tmp_path, [
            {"review_id": blocker, "fid": "R-1", "disposition": "fixed",
             "rationale": "the fix on the base removes the defect"}])

        passed = _gate(repo, tmp_path)
        assert passed.returncode == 0, passed.stdout + passed.stderr

    def test_off_the_base_nothing_is_owed(self, tmp_path):
        """Control: the same store, asked from a feature branch, names nothing,
        and under per_pr nothing either (no release gate counts it)."""
        for key in ("per_release", None):
            repo = _repo(tmp_path / str(key), key=key)
            _cut(repo, "v1.0.0")
            base = _branch(repo, "a")
            _commit(repo, {"src/a.py": "a = 1\n", **_fragment("a")}, "a")
            blocker = _review(repo, base, _tree(repo), _CHUNK, blocking=True)
            _git(repo, "checkout", "-q", "main")
            _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
            _merge(repo, "a")
            owed = [b["review_id"] for b in bc.release_owed_blockers(repo)]
            assert owed == ([blocker] if key else []), (key, owed)
            _git(repo, "checkout", "-q", "-b", "feature")
            assert bc.release_owed_blockers(repo) == [], key

    def test_ahead_of_the_remote_tip_the_blocker_is_still_owed(self, tmp_path):
        """The fix committed on the base and not yet pushed: HEAD is ahead of
        `origin/main`, so no release review can be taken there, but the verify
        pass of that fix is still the one that owes the branch's blocker."""
        repo = _repo(tmp_path, base="origin/main")
        _cut(repo, "v1.0.0")
        base = _branch(repo, "a")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("a")}, "a")
        blocker = _review(repo, base, _tree(repo), _CHUNK, blocking=True)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        _merge(repo, "a")
        remote = tmp_path / "remote.git"
        _git(repo, "clone", "-q", "--bare", str(repo), str(remote))
        _git(repo, "remote", "add", "origin", str(remote))
        _git(repo, "fetch", "-q", "origin")
        _commit(repo, {"src/a.py": "a = 2\n"}, "the fix, not pushed")
        where = bc.integration_base_tip(repo)
        assert (where.on_branch, where.at_tip, where.code) == (True, False, bc.RELEASE_OFF_BASE), where
        assert [b["review_id"] for b in bc.release_owed_blockers(repo)] == [blocker]


def bc_cumulative() -> str:
    from lib import critic_consolidate as cc  # noqa: PLC0415

    return cc.MODE_TOKEN_TO_VERBOSE["cumulative"]


# ---------------------------------------------------------------------------
# check-releasability refuses on the same verdict
# ---------------------------------------------------------------------------


class TestCheckReleasability:
    def test_an_unreviewed_merge_refuses_until_a_batch_review_reads_it(self, tmp_path, capsys, green_suite):
        repo = _repo(tmp_path)
        _released(repo, "a")
        rc, _out, err = _releasability(repo, capsys)
        assert rc == 1, err
        line = _refusal(err, bc.GATE_UNCOVERED)
        assert "critic-begin --mode cumulative --span release" in line, line
        assert any(ln.startswith("  a is inner-only — ") for ln in err.splitlines()), err
        assert "not-releasable" not in err  # its own refusal, not a classification problem
        assert _begin_release(repo, tmp_path).returncode == 0
        _consolidate(repo, tmp_path)
        rc, out, err = _releasability(repo, capsys)
        assert rc == 0, err
        assert "releasable: v1.1.0" in out and "1 batch-covered" in out

    def test_per_pr_control_the_same_history_is_releasable(self, tmp_path, capsys, green_suite):
        """This repo's default: the uncovered merge is a NOTE and the exit is 0."""
        repo = _repo(tmp_path, key=None)
        _released(repo, "a")
        rc, out, err = _releasability(repo, capsys)
        assert rc == 0, err
        assert "NOTE: boundary-coverage: a is inner-only, not covered" in err
        assert bc.GATE_UNCOVERED not in err and "releasable: v1.1.0" in out

    def test_a_missing_anchor_refuses(self, tmp_path, capsys, green_suite):
        repo = _repo(tmp_path)
        _commit(repo, {".prawduct/artifacts/release-plan-v1.1.0.md": _PLAN + "| a | ships | |\n"}, "plan")
        _lane(repo, "a")
        rc, _out, err = _releasability(repo, capsys)
        assert rc == 1, err
        assert "there is no release anchor" in _refusal(err, bc.GATE_UNEVALUABLE)

    def test_a_deferred_tail_with_nothing_pending_still_refuses(self, tmp_path, capsys, green_suite):
        """The tail's branch wrote no fragment, so nothing is pending, and the
        no-pending branch used to answer "nothing to classify". The walk saw the
        merge, so per_release refuses there too."""
        repo, merge = _tail_merged(tmp_path)
        _git(repo, "tag", "v1.0.0", f"{merge}^1")
        (repo / ".prawduct" / "changes").mkdir(parents=True, exist_ok=True)
        rc, out, err = _releasability(repo, capsys)
        assert rc == 1, out + err
        assert "tail-deferred" in err and _refusal(err, bc.GATE_UNCOVERED)
        assert "releasable:" not in out

    def test_a_policy_read_that_fails_refuses_and_names_the_failure(self, tmp_path, capsys, green_suite,
                                                                   monkeypatch):
        """W3: the release gate's fail-closed path for a crashed policy read. The
        checkout declares per_release and a merge is unreviewed; the reading at
        the integration branch raises. The release is refused as unevaluable,
        naming the failure: neither a pass, nor a traceback, nor an answer given
        under a guessed policy."""
        repo = _repo(tmp_path)
        _released(repo, "a")

        def boom(_p):
            raise RuntimeError("policy boom")

        monkeypatch.setattr(review_lane, "_release_policy", boom)
        rc, out, err = _releasability(repo, capsys)
        assert rc == 1, out + err
        line = _refusal(err, bc.GATE_UNEVALUABLE)
        assert "the policy could not be read at the integration branch (RuntimeError: policy boom)" in line, line
        assert "this checkout's declaration stands (per_release)" in line, line
        assert bc.GATE_UNCOVERED not in err and "releasable: v1.1.0" not in out
        # Control: a checkout declaring per_pr is not gated by the same failure.
        per_pr = _repo(tmp_path / "per_pr", key=None)
        _released(per_pr, "a")
        rc, out, err = _releasability(per_pr, capsys)
        assert rc == 0 and bc.GATE_UNEVALUABLE not in err, out + err
        assert "could not be read at the integration branch" in err, err

    def test_per_pr_with_nothing_pending_classifies_nothing(self, tmp_path, capsys, green_suite, monkeypatch):
        """Control: under per_pr the no-pending branch is unchanged, and pays for
        no classification."""
        repo, merge = _tail_merged(tmp_path, key=None)
        _git(repo, "tag", "v1.0.0", f"{merge}^1")
        (repo / ".prawduct" / "changes").mkdir(parents=True, exist_ok=True)

        def boom(_p):
            raise AssertionError("classified under per_pr with nothing pending")

        monkeypatch.setattr(bc, "classify_pending", boom)
        rc, out, _err = _releasability(repo, capsys)
        assert rc == 0 and "releasable: no release-pending scopes" in out


def test_the_release_policy_reads_the_tip_not_the_checkout(tmp_path):
    """The tip opted in; this checkout says per_pr. The release check reads the
    tip, because that is what the merged PRs were judged against."""
    repo = _repo(tmp_path)
    (repo / ".prawduct" / "project-state.yaml").write_text("base_branch: main\nboundary_review: per_pr\n")
    assert review_lane.release_policy(repo).per_release


# ---------------------------------------------------------------------------
# Every artifact describing the gate agrees with it
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


def _key_section() -> str:
    text = _read("plugin/docs/project-state-keys.md")
    return text.split("## boundary_review", 1)[1].split("\n## ", 1)[0]


class TestTheDescriptionsAgree:
    def test_every_surface_names_both_refusal_codes(self):
        for rel, text in (("project-state-keys.md", _key_section()),
                          ("api-contract.md", _read(".prawduct/artifacts/api-contract.md")),
                          ("release-process.md", _read("documentation/release-process.md")),
                          ("pr/SKILL.md", _read("plugin/skills/pr/SKILL.md")),
                          ("the fragment", _read(".prawduct/changes/boundary-review-per-release.md"))):
            for code in (bc.GATE_UNCOVERED, bc.GATE_UNEVALUABLE):
                assert f"{code}:" in text, (rel, code)
            assert "--span release" in text, rel

    def test_the_release_guard_names_only_flags_the_op_accepts(self):
        """The guard's prose names a flag the op has; derived from the parser."""
        hook = _read("plugin/bin/prawduct-hook")
        accepted = set(re.findall(r'"(--[a-z-]+)"', re.search(
            r'_reject_unknown_args\("check-boundary-coverage", argv, \{([^}]*)\}', hook).group(1)))
        assert {"--json", "--gate"} <= accepted, accepted
        named = re.findall(r"check-boundary-coverage((?: --[a-z-]+)+)", _read("plugin/skills/pr/SKILL.md"))
        flags = {f for group in named for f in group.split()}
        assert "--gate" in flags and flags <= accepted, (flags, accepted)

    def test_the_audit_names_each_class_a_correct_release_can_meet(self):
        section = _key_section()
        for phrase in ("Squash merge", "Octopus merge", "untracked", "No release anchor",
                       "`pr-transferred`", "withheld scope", "`walk-failed`"):
            assert phrase in section, phrase
        rows = [ln for ln in section.splitlines() if ln.startswith("| ") and "---" not in ln][1:]
        assert len(rows) >= 10 and all(ln.count(" | ") == 2 for ln in rows), rows

    def test_the_protocol_reads_the_span_the_code_renders(self):
        from lib import critic_consolidate as cc  # noqa: PLC0415

        rendered = cc.signals_line({"stage": "boundary", "span": cc.SPAN_RELEASE, "base_commit": "c" * 40})
        assert rendered.endswith(f" · Span: release from {'c' * 12}"), rendered
        protocol = _read("plugin/skills/critic/review-protocol.md")
        (bullet,) = [ln for ln in protocol.splitlines() if ln.startswith("- **`cumulative`**")]
        assert "`Span: release from <commit>`" in bullet
        assert "A bounded or release cumulative's `files_context`" in protocol

    def test_no_surface_still_says_per_release_does_not_block(self):
        """Chunk 01's temporary wording, retired when this chunk made it false."""
        for rel in ("plugin/docs/project-state-keys.md", ".prawduct/changes/boundary-review-per-release.md",
                    "plugin/skills/pr/SKILL.md", "plugin/skills/critic/review-cycle.md",
                    "documentation/release-process.md"):
            flat = " ".join(_read(rel).split())
            for claim in ("does not block yet", "leave it unset", "is read and changes nothing",
                          "changes nothing yet"):
                assert claim not in flat, (rel, claim)
