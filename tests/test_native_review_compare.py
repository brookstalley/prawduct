"""The comparison script for the paired native review (#1130 step 5).

The script lives with the experiment's research (`.prawduct/research/native-review-paired/compare.py`),
because it is run monthly by hand rather than shipped. Its matcher is what the owner's decision
table rests on, so it is pinned here: #1130's known-answer case, the goal tally, the stop
condition, the blind sheet's blinding, and one end-to-end run over a real paired review.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".prawduct" / "research" / "native-review-paired" / "compare.py"
_spec = importlib.util.spec_from_file_location("native_review_compare", SCRIPT)
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)


def _critic(fid, goal, *files):
    return {"fid": fid, "goal": goal, "title": f"critic {fid}", "recommendation": "fix", "files": list(files)}


def _native(file, line=1):
    return {"file": file, "line": line, "summary": f"native on {file}", "failure_scenario": "boom"}


class TestKnownAnswer:
    def test_three_and_three_with_one_overlap(self):
        """#1130 acceptance: three Critic findings and three native findings with
        one overlap yield one shared, two and two unique."""
        critic = [
            _critic("R-1", "Nothing Is Broken", "a.py"),
            _critic("R-2", "Nothing Is Missing", "b.py"),
            _critic("R-3", "The Design Is Sound", "c.py"),
        ]
        native = [_native("b.py"), _native("x.py"), _native("y.py")]
        result = compare.match(critic, native)
        assert [(c["fid"], n["file"]) for c, n in result["shared"]] == [("R-2", "b.py")]
        assert [c["fid"] for c in result["critic_only"]] == ["R-1", "R-3"]
        assert [n["file"] for n in result["native_only"]] == ["x.py", "y.py"]

    def test_pairing_is_one_to_one(self):
        """Two native findings in one file pair with at most one Critic finding
        there each — never both with the same one."""
        result = compare.match([_critic("R-1", "g", "a.py")], [_native("a.py", 1), _native("a.py", 9)])
        assert len(result["shared"]) == 1 and len(result["native_only"]) == 1

    def test_a_critic_finding_with_no_files_never_pairs(self):
        result = compare.match([{"fid": "R-1", "goal": "g", "files": None}], [_native("a.py")])
        assert result["shared"] == [] and len(result["critic_only"]) == 1


class TestTally:
    def test_goals_are_counted_and_native_only_waits_for_the_verifier(self):
        m = compare.match(
            [_critic("R-1", "Nothing Is Broken", "a.py"), _critic("R-2", "Nothing Is Broken", "b.py")],
            [_native("a.py"), _native("z.py")],
        )
        table = compare.tally_by_goal([m])
        assert table["Nothing Is Broken"] == {"shared": 1, "critic_only": 1, "native_only": 0}
        assert table[compare.NO_GOAL] == {"shared": 0, "critic_only": 0, "native_only": 1}


class TestStopCondition:
    NOW = datetime(2026, 12, 31, tzinfo=timezone.utc)

    def test_both_conditions_must_hold(self):
        early = "2026-11-01T00:00:00Z"
        assert compare.stop_progress([early] * 60, self.NOW)["stop"] is True
        assert compare.stop_progress([early] * 59, self.NOW)["stop"] is False  # weeks, not reviews
        late = "2026-12-20T00:00:00Z"
        assert compare.stop_progress([late] * 80, self.NOW)["stop"] is False  # reviews, not weeks

    def test_no_reviews_is_no_stop(self):
        assert compare.stop_progress([], self.NOW) == {"paired_reviews": 0, "weeks": 0.0, "stop": False}


class TestBlindSheet:
    def test_the_sheet_never_names_an_instrument_and_the_key_does(self):
        pair = {"review_id": "rev-1"}
        m = compare.match([_critic("R-1", "g", "a.py"), _critic("R-2", "g", "b.py")],
                          [_native("a.py"), _native("z.py")])
        items, key = compare.blind_sheet([pair], [m])
        assert len(items) == 3 and set(key) == {i["id"] for i in items}
        # Only these fields reach the verifier: the question, the words and the
        # place — no source, no fid, no review id.
        allowed = {"id", "ask", "finding", "first", "second"}
        assert all(set(i) <= allowed for i in items), items
        for item in items:
            for words in (item.get("finding"), item.get("first"), item.get("second")):
                if words is not None:
                    assert set(words) <= {"files", "line", "text"}, words
        # The key is where the source lives.
        assert sorted(v.get("source", "pair") for v in key.values()) == ["critic", "native", "pair"]


@pytest.fixture
def paired_repo(tmp_path, monkeypatch):
    """One real paired review: a development build's cumulative dispatched, the
    Critic consolidated with one finding on src/app.py, and the native text with
    two findings — one on src/app.py, one elsewhere."""
    sys.path.insert(0, str(REPO / "tests"))
    import test_native_review_pairing as pairing  # noqa: PLC0415

    repo = _branch_repo(tmp_path, pairing)
    result = pairing._begin(repo, "cumulative", monkeypatch, pairing.DEV)
    manifest = result["manifest"]
    partial = {
        "role": "reviewer", "goals": "1-7", "dispatch_id": result["id"],
        "commit_reviewed": manifest["commit_reviewed"], "model": "opus", "duration_seconds": 60,
        "findings": [{
            "goal": "Nothing Is Broken", "severity": "warning", "name": "x can be wrong",
            "recommendation": "check x", "files": ["src/app.py"],
        }],
        "summary": "one finding",
    }
    (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(json.dumps(partial))
    assert pairing.cc.consolidate(repo, trigger="explicit") == 0
    pd = repo / ".prawduct"
    pairing.native_review.text_path(pd, result["id"]).write_text(json.dumps([
        {"file": "src/app.py", "line": 1, "summary": "x drifts", "failure_scenario": "a"},
        {"file": "src/other.py", "line": 4, "summary": "y leaks", "failure_scenario": "b"},
    ]))
    assert pairing.native_review.record(repo, pd, result["id"])[0] == 0
    return repo, result["id"]


def _branch_repo(tmp_path, pairing):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (("init", "--quiet", "-b", "main"), ("config", "user.email", "t@example.com"),
                 ("config", "user.name", "T"), ("config", "commit.gpgsign", "false")):
        pairing._git(repo, *args)
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("x = 1\n")
    pairing._git(repo, "add", "-A")
    pairing._git(repo, "commit", "--quiet", "-m", "init")
    pairing._git(repo, "switch", "--quiet", "-c", "feature/thing")
    (repo / "src/app.py").write_text("x = 2\n")
    pairing._git(repo, "commit", "--quiet", "-am", "feat: change x")
    (repo / ".prawduct").mkdir()
    return repo.resolve()


class TestEndToEnd:
    def test_a_real_paired_review_compares(self, paired_repo, tmp_path, capsys):
        repo, review_id = paired_repo
        [pair] = compare.load_pairs(repo)
        assert pair["review_id"] == review_id
        assert pair["critic_fact"] is not None and pair["critic_event"] is not None
        out = tmp_path / "out"
        assert compare.main([str(repo), "--out", str(out)]) == 0
        printed = capsys.readouterr().out
        assert "1 recorded, 1 comparable" in printed
        assert "Nothing Is Broken: 1 / 0 / 0" in printed
        assert f"{compare.NO_GOAL}: 0 / 0 / 1" in printed
        items = json.loads((out / "blind-sheet.json").read_text())
        assert sorted(i["ask"] for i in items) == ["real defect? and which goal?", "same defect?"]

    def test_a_dispatched_run_never_recorded_is_reported(self, paired_repo, tmp_path, capsys):
        """Boundary review R-6: a wrapper that died leaves a sidecar and no event,
        and only a comparison of the two can see it."""
        repo, _review_id = paired_repo
        orphan = "rev-20990101T000000Z-deadbeef"
        (repo / ".prawduct" / ".native-reviews" / f"{orphan}.json").write_text("{}")
        assert compare.main([str(repo)]) == 0
        assert f"1 dispatched and never recorded: {orphan}" in capsys.readouterr().out

    def test_the_recipe_each_fork_ran_is_reported(self, paired_repo, tmp_path, capsys):
        """Boundary review R-8: the level asked is not the level run, so the
        report names the recipe from each fork's own prompt."""
        repo, _review_id = paired_repo
        [pair] = compare.load_pairs(repo)
        target = pair["native_event"]["native"]["args"].split(" ", 1)[1]
        forks = tmp_path / "subagents"
        forks.mkdir()
        lines = [
            {"type": "user", "timestamp": "2026-11-12T10:00:00Z",
             "message": {"content": f"Review target: `{target}`\n\n`high effort → 8 inline angles`"}},
            {"type": "assistant", "timestamp": "2026-11-12T10:01:30Z",
             "message": {"model": "claude-opus-5-5", "usage": {
                 "input_tokens": 1, "output_tokens": 2, "cache_creation_input_tokens": 3,
                 "cache_read_input_tokens": 4}}},
        ]
        (forks / "agent-x.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        assert compare.main([str(repo), "--transcripts", str(forks)]) == 0
        out = capsys.readouterr().out
        assert "over 1 fork(s)" in out and "recipes run: {'high': 1}" in out
