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
import re
import subprocess
from pathlib import Path

import pytest

from lib import boundary_coverage as bc  # noqa: E402
from lib import release_readiness, review_lane  # noqa: E402
from lib.core import GITIGNORE_ENTRIES  # noqa: E402
from test_fix_tail_deferral import _merged as _tail_merged
from test_release_batch_review import (
    _begin_release,
    _commit,
    _consolidate,
    _cut,
    _git,
    _hook,
    _lane,
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
