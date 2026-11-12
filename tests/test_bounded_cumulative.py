"""A repeat cumulative reviews the delta since the last boundary review.

``gates.boundary_frontier`` finds the newest boundary review that the current
bundle extends cleanly (the design's conditions 1-5,
`.prawduct/artifacts/bounded-cumulative-design.md` § The anchor), and
``critic_consolidate.begin_review`` bounds a ``cumulative`` interval to
``frontier → HEAD`` when one exists. Every declined condition falls back to the
full span and says why. Composition and the PR gate are unchanged: a bounded
fact composes with the frontier's.

Real git repos throughout; facts are written through ``evidence.append_fact``,
the writer consolidation uses, and the end-to-end cases run the real
``critic-consolidate``.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

sys.path.insert(0, str(ROOT))
from lib import critic_consolidate as cc  # noqa: E402
from lib import critic_mode, evidence, gates  # noqa: E402

CUMULATIVE = cc.MODE_TOKEN_TO_VERBOSE["cumulative"]
CHUNK = cc.MODE_TOKEN_TO_VERBOSE["chunk"]
_ids = itertools.count(1)

PLAN = (
    "---\nartifact: build-plan\nscope: bc\nbranch: feat/bc\nbase: main\n---\n\n# Plan\n\n"
    "### Chunk 01: one\n\n- **Deliverables:** `src/b.py`\n\n"
    "### Chunk 02: two\n\n- **Deliverables:** `src/c.py`\n"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(repo: Path) -> dict:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_env(repo), timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


def _repo(tmp_path: Path) -> Path:
    """main → feat/bc with one reviewed commit (src/b.py plus a record), so a
    frontier fact can be written at its tip. The caller commits the delta."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit(repo, "src/a.py", "a = 1\n", "a")
    _commit(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    _commit(repo, ".prawduct/artifacts/build-plan-bc.md", PLAN, "plan")
    _git(repo, "checkout", "-q", "-b", "feat/bc")
    _commit(repo, "docs/notes.md", "# Notes\n", "notes")
    _commit(repo, "src/b.py", "b = 1\n", "b")
    return repo


def _merge_base(repo: Path) -> str:
    return _git(repo, "merge-base", "main", "HEAD")


def _fact(
    repo: Path,
    base_tree: str,
    head_tree: str,
    *,
    head_commit: "str | None",
    mode: str = CUMULATIVE,
    stage: "str | None" = "boundary",
    findings: "list[dict] | None" = None,
    base_reviewed: "str | None" = None,
    extra: "dict | None" = None,
) -> str:
    fact_id = f"rev-bc-{next(_ids):04d}"
    files = evidence.tree_diff(repo, base_tree, head_tree)
    body = {
        "base_tree": base_tree,
        "head_tree": head_tree,
        "head_commit": head_commit,
        "dispatch_commit": head_commit,
        "files_changed": list(files),
        "files_reviewed": list(files),
        "findings": findings or [],
        "counts": {"blocking": sum(1 for f in findings or [] if f.get("severity") == "blocking"),
                   "warning": 0, "note": 0},
        "mode": mode,
        "base_reviewed": base_reviewed,
    }
    if stage is not None:
        body["stage"] = stage
    body.update(extra or {})
    result = evidence.append_fact(repo, "review", fact_id, body)
    assert result["status"] == "appended", result
    return fact_id


def _frontier_fact(repo: Path, **kwargs) -> str:
    """A full-span cumulative over merge-base → HEAD, as one would record it."""
    mb = _merge_base(repo)
    return _fact(repo, _tree(repo, mb), _tree(repo), head_commit=_git(repo, "rev-parse", "HEAD"),
                 base_reviewed=mb, **kwargs)


def _blocker(fid: str = "R-1") -> dict:
    return {"fid": fid, "severity": "blocking", "title": "broken", "files": ["src/b.py"]}


def _frontier(repo: Path) -> dict:
    return gates.boundary_frontier(repo)


# ---------------------------------------------------------------------------
# The frontier: each condition, and the walk
# ---------------------------------------------------------------------------


class TestFrontier:
    def test_a_clean_boundary_review_behind_head_is_the_frontier(self, tmp_path):
        repo = _repo(tmp_path)
        fid = _frontier_fact(repo)
        t1, c1 = _tree(repo), _git(repo, "rev-parse", "HEAD")
        _commit(repo, "src/c.py", "c = 1\n", "c")
        got = _frontier(repo)
        assert got["status"] == "bounded", got
        assert (got["fact_id"], got["head_tree"], got["head_commit"]) == (fid, t1, c1)

    def test_condition_1_no_boundary_review_declines(self, tmp_path):
        repo = _repo(tmp_path)
        _frontier_fact(repo, mode=CHUNK, stage="inner")
        _commit(repo, "src/c.py", "c = 1\n", "c")
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_NO_BOUNDARY_REVIEW), got
        assert got["reason"]

    def test_an_old_fact_without_stage_is_read_from_its_mode(self, tmp_path):
        repo = _repo(tmp_path)
        fid = _frontier_fact(repo, stage=None)
        _commit(repo, "src/c.py", "c = 1\n", "c")
        assert _frontier(repo)["fact_id"] == fid

    def test_condition_2_base_moved_declines(self, tmp_path):
        repo = _repo(tmp_path)
        _frontier_fact(repo)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "src/up.py", "u = 1\n", "upstream")
        _git(repo, "checkout", "-q", "feat/bc")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_BASE_MOVED), got

    def test_condition_3_a_review_off_this_lineage_is_not_this_branch_s(self, tmp_path):
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "sibling")
        _commit(repo, "src/s.py", "s = 1\n", "sibling work")
        _frontier_fact(repo)
        _git(repo, "checkout", "-q", "feat/bc")
        _commit(repo, "src/c.py", "c = 1\n", "c")
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_NO_BOUNDARY_REVIEW), got

    def test_another_branch_s_review_on_another_base_never_reads_as_base_moved(self, tmp_path):
        # The store is clone-wide: a sibling reviewed against an older base must
        # not tell this branch, which has no boundary review, that its base moved.
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "old-sibling", "main")
        _commit(repo, "src/s.py", "s = 1\n", "sibling work")
        _frontier_fact(repo)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, "src/up.py", "u = 1\n", "upstream")
        _git(repo, "checkout", "-q", "feat/bc")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_NO_BOUNDARY_REVIEW), got

    def test_a_sibling_lineage_s_newer_fact_is_skipped_not_taken(self, tmp_path):
        repo = _repo(tmp_path)
        fid = _frontier_fact(repo)
        _git(repo, "checkout", "-q", "-b", "sibling")
        _commit(repo, "src/s.py", "s = 1\n", "sibling work")
        _frontier_fact(repo)  # newer, same base, not an ancestor of feat/bc
        _git(repo, "checkout", "-q", "feat/bc")
        _commit(repo, "src/c.py", "c = 1\n", "c")
        got = _frontier(repo)
        assert (got["status"], got["fact_id"]) == ("bounded", fid), got

    def test_condition_4_head_already_reviewed_declines(self, tmp_path):
        repo = _repo(tmp_path)
        _frontier_fact(repo)
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_HEAD_REVIEWED), got

    def test_condition_5_a_blocker_at_the_frontier_declines(self, tmp_path):
        repo = _repo(tmp_path)
        _frontier_fact(repo, findings=[_blocker()])
        _commit(repo, "src/c.py", "c = 1\n", "c")
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_PATH_NOT_CLEAN), got

    def test_condition_5_a_resolved_blocker_does_not_decline(self, tmp_path):
        repo = _repo(tmp_path)
        fid = _frontier_fact(repo, findings=[_blocker()])
        res = evidence.append_fact(
            repo, "resolution", "res-bc-0001",
            {"finding": {"review_id": fid, "fid": "R-1"}, "disposition": "fixed"},
        )
        assert res["status"] == "appended", res
        _commit(repo, "src/c.py", "c = 1\n", "c")
        assert _frontier(repo)["fact_id"] == fid

    def test_a_blocked_newest_review_forces_full_not_an_older_frontier(self, tmp_path):
        # Falling back to the older clean review would bound the interval
        # around the newer one's blocker; only a full span may do that.
        repo = _repo(tmp_path)
        _frontier_fact(repo)
        _commit(repo, "src/c.py", "c = 1\n", "c")
        _frontier_fact(repo, findings=[_blocker()])
        _commit(repo, "src/d.py", "d = 1\n", "d")
        got = _frontier(repo)
        assert (got["status"], got["code"]) == ("full", gates.SPAN_FULL_PATH_NOT_CLEAN), got

    def test_a_bounded_review_is_itself_a_frontier_for_the_next_repeat(self, tmp_path):
        # Its base_tree is the earlier frontier, not the merge-base: condition 2
        # reads the bundle base it records (`base_reviewed`).
        repo = _repo(tmp_path)
        _frontier_fact(repo)
        t1 = _tree(repo)
        _commit(repo, "src/c.py", "c = 1\n", "c")
        fid = _fact(repo, t1, _tree(repo), head_commit=_git(repo, "rev-parse", "HEAD"),
                    base_reviewed=_merge_base(repo),
                    extra={"span": "bounded", "bounded_from": "rev-x"})
        _commit(repo, "src/d.py", "d = 1\n", "d")
        got = _frontier(repo)
        assert (got["status"], got["fact_id"]) == ("bounded", fid), got


# ---------------------------------------------------------------------------
# The dispatch
# ---------------------------------------------------------------------------


def _manifest(repo: Path) -> dict:
    return json.loads((repo / ".prawduct" / ".critic-partials" / "manifest.json").read_text())


def _abandon(repo: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(HOOK), "critic-end"], cwd=str(repo), capture_output=True,
        text=True, env={**_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr


def _consolidate(repo: Path) -> None:
    manifest = _manifest(repo)
    partial = {
        "role": "reviewer", "goals": "1-7", "dispatch_id": manifest["id"],
        "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
        "duration_seconds": 60, "findings": [], "summary": "clean",
    }
    path = Path(manifest["rendezvous"]["reviewer"]["partial"])
    if not path.is_absolute():
        path = repo / path
    path.write_text(json.dumps(partial))
    proc = subprocess.run(
        [sys.executable, str(HOOK), "critic-consolidate"], cwd=str(repo), capture_output=True,
        text=True, env={**_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _bounded_repo(tmp_path: Path) -> "tuple[Path, str, str]":
    repo = _repo(tmp_path)
    fid = _frontier_fact(repo)
    t1 = _tree(repo)
    _commit(repo, "src/c.py", "c = 1\n", "c")
    return repo, fid, t1


class TestBoundedDispatch:
    def test_the_interval_is_frontier_to_head_and_the_record_says_so(self, tmp_path):
        repo, fid, t1 = _bounded_repo(tmp_path)
        result = cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)
        assert result["status"] == "ok", result
        m = _manifest(repo)
        assert (m["span"], m["bounded_from"], m["span_reason"]) == ("bounded", fid, None)
        assert (m["base_tree"], m["head_tree"]) == (t1, _tree(repo))
        assert m["base_commit"] == _git(repo, "rev-parse", "HEAD~1")
        assert m["base_reviewed"] == _merge_base(repo)
        assert m["stage"] == "boundary"
        assert m["files_changed"] == ["src/c.py"]
        assert m["files_reviewed"] == ["src/c.py"]
        # The rest of the bundle is read, not rated — and not handed over as
        # oracle, which the Records Pass rates at the boundary stage.
        assert m["files_context"] == ["docs/notes.md", "src/b.py"]
        assert not {"docs/notes.md", "src/b.py"} & set(m["files_oracle"])
        assert m["signals"].endswith(f" · Span: bounded from {fid}")
        assert any(fid in n and "bounded" in n for n in result["notes"]), result["notes"]

    def test_the_machine_relays_grade_the_bundle_as_a_full_span_would(self, tmp_path):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        assert cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)["status"] == "ok"
        bounded = _manifest(repo)
        _abandon(repo)
        full = cc.begin_review(
            repo, "cumulative", chosen_by=critic_mode.FULL_SPAN_RATIONALE, force=True
        )
        assert full["status"] == "ok", full
        whole = _manifest(repo)
        assert whole["span"] == "full"
        # A record changed before the frontier is still graded.
        assert "docs/notes.md" in bounded["record_lint"]["records"]
        assert bounded["record_lint"]["records"] == whole["record_lint"]["records"]
        assert bounded["chunks_proposed"] == whole["chunks_proposed"] == ["01", "02"]

    def test_the_roster_comes_from_the_delta(self, tmp_path, monkeypatch):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        seen = []
        real = cc._derive_roster

        def spy(mode_token, files_changed, prawduct_dir):
            seen.append(list(files_changed))
            return real(mode_token, files_changed, prawduct_dir)

        monkeypatch.setattr(cc, "_derive_roster", spy)
        assert cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)["status"] == "ok"
        assert seen == [["src/c.py"]]

    def test_the_full_override_dispatches_the_whole_bundle_and_says_why(self, tmp_path):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        result = cc.begin_review(
            repo, "cumulative", chosen_by=critic_mode.FULL_SPAN_RATIONALE, force=True
        )
        m = _manifest(repo)
        assert (m["span"], m["bounded_from"], m["span_reason"]) == (
            "full", None, gates.SPAN_FULL_OVERRIDE
        )
        assert m["base_tree"] == _tree(repo, _merge_base(repo))
        assert m["files_context"] == []
        assert m["signals"].endswith(" · Span: full")
        assert any("full" in n and "override" in n for n in result["notes"]), result["notes"]

    def test_a_declined_frontier_dispatches_full_with_its_reason(self, tmp_path):
        repo = _repo(tmp_path)
        _frontier_fact(repo, findings=[_blocker()])
        _commit(repo, "src/c.py", "c = 1\n", "c")
        result = cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)
        m = _manifest(repo)
        assert (m["span"], m["span_reason"]) == ("full", gates.SPAN_FULL_PATH_NOT_CLEAN)
        assert m["base_tree"] == _tree(repo, _merge_base(repo))
        reason = _frontier(repo)["reason"]
        assert any(reason in n for n in result["notes"]), result["notes"]

    def test_other_modes_carry_no_span(self, tmp_path):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        (repo / "src/c.py").write_text("c = 2\n")
        assert cc.begin_review(repo, "chunk", chosen_by="rule-4", force=True)["status"] == "ok"
        m = _manifest(repo)
        assert (m.get("span"), m.get("bounded_from"), m.get("span_reason")) == (None, None, None)
        assert "files_context" not in m and "Span:" not in m["signals"]


class TestTheRecordAndTheGate:
    def test_a_bounded_fact_composes_to_a_passing_pr_gate(self, tmp_path):
        repo, fid, _t1 = _bounded_repo(tmp_path)
        assert gates.check_cumulative_critic(repo) != 0  # the delta is unreviewed
        assert cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)["status"] == "ok"
        _consolidate(repo)
        facts = [f for f in evidence.read_facts(repo)["facts"] if f.get("kind") == "review"]
        body = facts[-1]["body"]
        assert (body["span"], body["bounded_from"], body["span_reason"]) == ("bounded", fid, None)
        cache = json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())
        assert (cache["span"], cache["bounded_from"]) == ("bounded", fid)
        ledger = repo / ".prawduct" / ".governance-ledger.jsonl"
        events = [json.loads(line) for line in ledger.read_text().splitlines()]
        (event,) = [e for e in events if e.get("event") == "review.critic"]
        assert (event["review"]["span"], event["review"]["bounded_from"]) == ("bounded", fid)
        assert gates.check_cumulative_critic(repo) == 0

    def test_a_full_fact_records_its_span_and_reason(self, tmp_path):
        repo = _repo(tmp_path)
        assert cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)["status"] == "ok"
        _consolidate(repo)
        body = [f for f in evidence.read_facts(repo)["facts"] if f.get("kind") == "review"][-1]["body"]
        assert (body["span"], body["bounded_from"], body["span_reason"]) == (
            "full", None, gates.SPAN_FULL_NO_BOUNDARY_REVIEW
        )


class TestManifestValidation:
    def _valid(self, tmp_path) -> dict:
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        assert cc.begin_review(repo, "cumulative", chosen_by="rule-2", force=True)["status"] == "ok"
        return _manifest(repo)

    def test_the_derived_manifest_validates(self, tmp_path):
        assert cc.validate_manifest(self._valid(tmp_path)) == (True, "")

    def test_an_unknown_span_is_refused(self, tmp_path):
        m = self._valid(tmp_path)
        m["span"] = "partial"
        ok, reason = cc.validate_manifest(m)
        assert not ok and "span" in reason

    def test_a_malformed_context_set_is_refused(self, tmp_path):
        m = self._valid(tmp_path)
        m["files_context"] = ["ok.py", ""]
        ok, reason = cc.validate_manifest(m)
        assert not ok and "files_context" in reason

    def test_bounded_without_its_frontier_is_refused(self, tmp_path):
        m = self._valid(tmp_path)
        m["bounded_from"] = None
        ok, reason = cc.validate_manifest(m)
        assert not ok and "bounded_from" in reason

    def test_a_manifest_from_before_the_fields_still_validates(self, tmp_path):
        m = self._valid(tmp_path)
        for key in ("span", "bounded_from", "span_reason", "files_context"):
            m.pop(key)
        assert cc.validate_manifest(m) == (True, "")


# ---------------------------------------------------------------------------
# The override token
# ---------------------------------------------------------------------------


class TestFullToken:
    def test_cumulative_full_is_explicit_and_says_full(self, tmp_path):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        assert critic_mode.infer_mode(repo, "cumulative full") == (
            "cumulative", critic_mode.FULL_SPAN_RATIONALE
        )

    def test_full_alone_means_a_full_cumulative(self, tmp_path):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        assert critic_mode.infer_mode(repo, "full") == (
            "cumulative", critic_mode.FULL_SPAN_RATIONALE
        )

    def test_plain_cumulative_is_unchanged(self, tmp_path):
        repo, _fid, _t1 = _bounded_repo(tmp_path)
        assert critic_mode.infer_mode(repo, "cumulative") == ("cumulative", "explicit-args")


# ---------------------------------------------------------------------------
# The protocol names what the code renders
# ---------------------------------------------------------------------------


class TestProtocolAgreesWithCode:
    """The reviewer meets the span through the `Signals:` line (code) and the
    protocol's `cumulative` bullet (prose); the operator meets the override
    through the skill and `review-cycle.md`. Each pair is pinned both ways."""

    def _bullet(self) -> str:
        text = (ROOT / "skills" / "critic" / "review-protocol.md").read_text(encoding="utf-8")
        (line,) = [ln for ln in text.splitlines() if ln.startswith("- **`cumulative`**")]
        return line

    def test_the_cumulative_bullet_reads_the_rendered_span(self):
        rendered = cc.signals_line({"stage": "boundary", "span": cc.SPAN_BOUNDED, "bounded_from": "<id>"})
        assert rendered.endswith(" · Span: bounded from <id>")
        assert "`Span: bounded from <id>`" in self._bullet()

    def test_the_cumulative_bullet_names_the_unrated_set_and_the_kept_relays(self):
        bullet = self._bullet()
        assert "`files_context`" in bullet and "never rated" in bullet
        assert "Record-lint" in bullet and "`test-status`" in bullet

    def test_the_override_is_spelled_as_the_code_answers_it(self):
        cycle = (ROOT / "skills" / "critic" / "review-cycle.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
        assert f"`{critic_mode.FULL_SPAN_RATIONALE}`" in cycle
        assert f"cumulative {critic_mode.FULL_SPAN_TOKEN}" in cycle
        assert f"cumulative [{critic_mode.FULL_SPAN_TOKEN}]" in skill
