"""The comparison script for the paired native review (#1130 step 5).

The script lives with the experiment's research (`.prawduct/research/native-review-paired/compare.py`),
because it is run monthly by hand rather than shipped. Its matcher is what the owner's decision
table rests on, so it is pinned here: #1130's known-answer case, the goal tally, the stop
condition, the blind sheet's blinding, and one end-to-end run over a real paired review.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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
        assert table["Nothing Is Broken"] == {"shared": 1, "shared_observation": 0, "critic_only": 1, "native_only": 0}
        assert table[compare.NO_GOAL] == {"shared": 0, "shared_observation": 0, "critic_only": 0, "native_only": 1}

    def test_a_match_to_an_observation_counts_apart_from_shared(self):
        """Unmatched observations are no one's `critic_only`, so folding the
        matched ones into `shared` alone would overstate the overlap."""
        m = compare.match([_critic("R-1", "Nothing Is Broken", "a.py")], [_native("o.py")],
                          observations=[_obs("O-1", "Nothing Is Broken", "o.py"), _obs("O-2", "Nothing Is Broken", "q.py")])
        row = compare.tally_by_goal([m])["Nothing Is Broken"]
        assert row == {"shared": 0, "shared_observation": 1, "critic_only": 1, "native_only": 0}


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
        # Only these fields reach the verifier: the question, the words, the
        # place, and the trees the review read (so the verifier reads the code as
        # reviewed, not a later fix) — no source, no fid, no review id.
        allowed = {"id", "ask", "finding", "first", "second", "earlier", "repo", "base_tree", "head_tree",
                   "earlier_head_tree", "tree_moved"}
        assert all(set(i) <= allowed for i in items), items
        for item in items:
            for words in (item.get("finding"), item.get("first"), item.get("second")):
                if words is not None:
                    # No `line`: only native findings carry one, so it would
                    # tell the verifier which instrument raised what.
                    assert set(words) == {"files", "text"}, words
        # The key is where the source lives.
        assert sorted(v.get("source", "pair") for v in key.values()) == ["critic", "native", "pair"]

    def test_every_unique_finding_is_asked_the_same_question(self):
        # A Critic-only finding was asked "real defect?" and a native-only one
        # "real defect? and which goal?", so the question named the instrument.
        m = compare.match([_critic("R-1", "g", "a.py")], [_native("z.py")])
        items, key = compare.blind_sheet([{"review_id": "rev-1"}], [m])
        sources = {key[i["id"]]["source"] for i in items}
        assert sources == {"critic", "native"}, "the fixture must hold one unique of each"
        assert len({i["ask"] for i in items}) == 1, [i["ask"] for i in items]

    def test_a_pairs_order_is_shuffled_and_the_key_says_which_came_first(self):
        # First was always the Critic's, so the order named the instrument.
        critic = [_critic(f"R-{n}", "g", f"f{n}.py") for n in range(30)]
        native = [_native(f"f{n}.py") for n in range(30)]
        items, key = compare.blind_sheet([{"review_id": "rev-1"}], [compare.match(critic, native)])
        firsts = {key[i["id"]]["first_source"] for i in items}
        assert firsts == {"critic", "native"}, firsts
        for item in items:
            critic_side = item["first"] if key[item["id"]]["first_source"] == "critic" else item["second"]
            assert critic_side["text"].startswith("critic R-"), "the key names the side the Critic's words are on"

    def test_a_reraise_item_names_its_reviews_trees_and_the_earlier_reviews(self):
        later = {"review_id": "rev-2", "repo": "/r",
                 "native_event": {"native": {"base_tree": "b" * 40, "head_tree": "h" * 40, "tree_moved": True}}}
        earlier = {"review_id": "rev-1", "repo": "/r",
                   "native_event": {"native": {"base_tree": "a" * 40, "head_tree": "e" * 40}}}
        reraised = [{"review": "rev-2", "by": "native", "finding": _native("a.py"),
                     "earlier": [_critic("R-1", "g", "a.py")], "earlier_kind": "finding",
                     "earlier_review": "rev-1"}]
        empty = compare.match([], [])
        items, _ = compare.blind_sheet([later, earlier], [empty, empty], reraised=reraised)
        [item] = items
        assert (item["repo"], item["base_tree"], item["head_tree"]) == ("/r", "b" * 40, "h" * 40)
        assert item["earlier_head_tree"] == "e" * 40
        assert item["tree_moved"] is True

    def test_each_item_names_the_repo_and_the_trees_the_review_read(self):
        pair = {"review_id": "rev-1", "repo": "/r",
                "native_event": {"native": {"base_tree": "b" * 40, "head_tree": "h" * 40}}}
        m = compare.match([_critic("R-1", "g", "a.py")], [_native("a.py"), _native("z.py")])
        items, _ = compare.blind_sheet([pair], [m])
        assert items and all(
            (i["repo"], i["base_tree"], i["head_tree"]) == ("/r", "b" * 40, "h" * 40) for i in items
        ), items


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


def _rewrite_native_event(repo: Path, change) -> None:
    ledger_path = repo / ".prawduct" / ".governance-ledger.jsonl"
    lines = []
    for line in ledger_path.read_text().splitlines():
        event = json.loads(line)
        if event.get("event") == "native.review":
            change(event)
        lines.append(json.dumps(event))
    ledger_path.write_text("\n".join(lines) + "\n")


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
    def test_a_real_paired_reviews_items_name_trees_the_repo_holds(self, paired_repo):
        # Production obtains the trees from the native.review ledger event, which
        # no unit test above exercises: they hand the pair its trees directly.
        repo, _review_id = paired_repo
        pairs = compare.load_pairs(repo)
        matches = [compare.match(p["critic_fact"]["body"].get("findings") or [], p["native_findings"])
                   for p in pairs]
        items, _ = compare.blind_sheet(pairs, matches)
        assert items
        for item in items:
            assert item["repo"] == str(repo)
            for tree in (item["base_tree"], item["head_tree"]):
                kind = subprocess.run(  # noqa: S603 — list-form argv, no shell (project preference)
                    ["git", "-C", str(repo), "cat-file", "-t", tree], capture_output=True, text=True,
                ).stdout.strip()
                assert kind == "tree", (tree, kind)

    def test_pin_backfills_a_run_recorded_before_pins_existed(self, paired_repo, capsys):
        repo, review_id = paired_repo
        for name in ("base", "head"):  # as a run recorded before record() pinned
            subprocess.run(["git", "-C", str(repo), "update-ref", "-d",  # noqa: S603 — list-form argv
                            f"{compare.native_review.PIN_PREFIX}/{review_id}/{name}"], check=True)
        assert compare.main([str(repo), "--pin"]) == 0
        assert "trees pinned: 1 of 1" in capsys.readouterr().out
        [pair] = compare.load_pairs(repo)
        head = subprocess.run(  # noqa: S603 — list-form argv, no shell (project preference)
            ["git", "-C", str(repo), "rev-parse", f"{compare.native_review.PIN_PREFIX}/{review_id}/head"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert head == pair["native_event"]["native"]["head_tree"]

    def test_a_review_whose_tree_is_gone_is_named_loudly(self, paired_repo, capsys):
        repo, review_id = paired_repo
        _rewrite_native_event(repo, lambda e: e["native"].update(head_tree="0" * 40))
        assert compare.main([str(repo)]) == 0
        printed = capsys.readouterr().out
        assert "WARNING: 1 review(s) whose reviewed tree is gone" in printed and review_id in printed

    def test_a_review_whose_event_names_no_tree_is_told_apart_from_a_pruned_one(self, paired_repo, capsys):
        repo, review_id = paired_repo
        _rewrite_native_event(repo, lambda e: e["native"].pop("head_tree"))
        assert compare.main([str(repo)]) == 0
        printed = capsys.readouterr().out
        assert "WARNING: 1 review(s) whose event names no reviewed tree" in printed
        assert "whose reviewed tree is gone" not in printed

    def test_a_real_paired_review_compares(self, paired_repo, tmp_path, capsys):
        repo, review_id = paired_repo
        [pair] = compare.load_pairs(repo)
        assert pair["review_id"] == review_id
        assert pair["critic_fact"] is not None and pair["critic_event"] is not None
        out = tmp_path / "out"
        assert compare.main([str(repo), "--out", str(out)]) == 0
        printed = capsys.readouterr().out
        assert "1 recorded, 1 comparable" in printed
        assert "Nothing Is Broken: 1 / 0 / 0 / 0" in printed
        assert f"{compare.NO_GOAL}: 0 / 0 / 0 / 1" in printed
        assert "outside the Critic's interval, boundary: 1 of 2" in printed
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
        # #1161: the model too, since the comparison assumes it matches the Critic's.
        assert "models: {'claude-opus-5-5': 1}" in out
        assert "WARNING" not in out

    def test_a_fork_that_ran_another_recipe_is_flagged(self, paired_repo, tmp_path, capsys):
        """#1161: the comparison assumes every native run was `high`; a fork whose
        own prompt names another recipe breaks that, and the report says so."""
        repo, _review_id = paired_repo
        [pair] = compare.load_pairs(repo)
        target = pair["native_event"]["native"]["args"].split(" ", 1)[1]
        forks = tmp_path / "subagents"
        forks.mkdir()
        lines = [
            {"type": "user", "timestamp": "2026-11-12T10:00:00Z",
             "message": {"content": f"Review target: `{target}`\n\n`low effort → 1 diff pass`"}},
            {"type": "assistant", "timestamp": "2026-11-12T10:00:05Z",
             "message": {"model": "claude-sonnet-5-5", "usage": {"output_tokens": 1}}},
        ]
        (forks / "agent-y.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        assert compare.main([str(repo), "--transcripts", str(forks)]) == 0
        out = capsys.readouterr().out
        assert "WARNING: 1 fork(s) ran a recipe other than their run's recorded level: low 1" in out

    def test_a_run_on_another_model_than_its_critic_review_is_flagged(self, paired_repo, capsys):
        """The paired native review on #1161: the comparison assumes the two ran on
        one model, so a pair that did not is named — compared by family, since the
        Critic records `opus` where the native run records `claude-opus-5-5`."""
        repo, review_id = paired_repo
        assert compare.main([str(repo)]) == 0
        assert "model mismatch" not in capsys.readouterr().out  # opus == claude-opus-5-5
        _rewrite_native_event(repo, lambda e: e["actor"].update(model="claude-sonnet-5-5"))
        assert compare.main([str(repo)]) == 0
        out = capsys.readouterr().out
        assert f"WARNING: 1 model mismatch(es): {review_id} (critic opus, native sonnet)" in out

    def test_the_counts_are_checked_against_the_ledger(self, paired_repo, capsys):
        """#1161 acceptance: compare reports the same counts as the ledger events —
        checked by the script itself on every run, so a parse change that moves a
        count is seen, not assumed."""
        repo, review_id = paired_repo
        assert compare.main([str(repo)]) == 0
        assert "count check: 1 of 1 countable run(s) agree with the ledger" in capsys.readouterr().out
        # Control: a text edited after it was recorded disagrees, and is named.
        text = repo / ".prawduct" / ".native-reviews" / f"{review_id}.md"
        text.write_text(json.dumps([{"file": "only.py", "line": 1, "summary": "s"}]))
        assert compare.main([str(repo)]) == 0
        out = capsys.readouterr().out
        assert "count check: 0 of 1 countable run(s) agree with the ledger" in out
        assert f"{review_id} (ledger 2, text 1)" in out

    def test_the_check_names_a_run_whose_countability_changed(self, paired_repo, capsys):
        """Boundary Critic on #1161 (and the paired native review's first finding):
        a run the ledger counted whose text now parses as uncountable — exactly
        what a parse change does — is a disagreement, not a skip."""
        repo, review_id = paired_repo
        text = repo / ".prawduct" / ".native-reviews" / f"{review_id}.md"
        text.write_text("Result:\n(none)\n\nThe pass found two problems.")
        assert compare.main([str(repo)]) == 0
        out = capsys.readouterr().out
        assert f"{review_id} (ledger 2, text not countable)" in out

    def test_the_check_compares_which_findings_not_how_many(self, paired_repo, capsys):
        repo, review_id = paired_repo
        text = repo / ".prawduct" / ".native-reviews" / f"{review_id}.md"
        text.write_text(json.dumps([
            {"file": "src/app.py", "line": 1, "summary": "a"},
            {"file": "elsewhere.py", "line": 4, "summary": "b"},  # same count, other file
        ]))
        assert compare.main([str(repo)]) == 0
        out = capsys.readouterr().out
        assert "count check: 0 of 1" in out and f"{review_id} (ledger 2, text 2, findings differ)" in out

    def test_a_run_whose_text_is_missing_is_not_compared(self, paired_repo, capsys):
        repo, review_id = paired_repo
        (repo / ".prawduct" / ".native-reviews" / f"{review_id}.md").unlink()
        assert compare.main([str(repo)]) == 0
        assert "count check: 0 of 0 countable run(s)" in capsys.readouterr().out


# --- Severity, stage and re-raises (#1164, #1165, #1166) -----------------------


def _obs(oid, goal, *files):
    return {"oid": oid, "goal": goal, "title": f"observation {oid}", "recommendation": "-", "files": list(files)}


class TestObservationsAreMatched:
    def test_a_native_finding_the_critic_demoted_is_shared_not_native_only(self):
        """#1164: the Critic rates some defects as observations, so a native
        finding matching only an observation is one both raised."""
        result = compare.match([_critic("R-1", "g", "a.py")], [_native("b.py")],
                               observations=[_obs("O-1", "Nothing Is Broken", "b.py")])
        assert [(c["oid"], n["file"]) for c, n in result["shared"]] == [("O-1", "b.py")]
        assert result["native_only"] == []
        assert [c["fid"] for c in result["critic_only"]] == ["R-1"]

    def test_a_finding_is_matched_before_an_observation(self):
        result = compare.match([_critic("R-1", "g", "a.py")], [_native("a.py")],
                               observations=[_obs("O-1", "g", "a.py")])
        assert [c.get("fid") for c, _n in result["shared"]] == ["R-1"]
        assert [o["oid"] for o in result["observations_unmatched"]] == ["O-1"]

    def test_control_without_observations_the_known_answer_stands(self):
        result = compare.match([_critic("R-1", "g", "a.py")], [_native("b.py")])
        assert result["shared"] == [] and len(result["native_only"]) == 1


class TestSeverityTally:
    def test_rows_are_per_stage_and_per_critic_severity(self):
        boundary = compare.match(
            [dict(_critic("R-1", "g", "a.py"), severity="blocking"),
             dict(_critic("R-2", "g", "b.py"), severity="warning")],
            [_native("a.py"), _native("z.py"), _native("o.py")],
            observations=[_obs("O-1", "g", "o.py"), _obs("O-2", "g", "q.py")],
        )
        inner = compare.match([dict(_critic("R-9", "g", "c.py"), severity="blocking")], [])
        table = compare.tally_by_severity([("boundary", boundary), ("inner", inner)])
        assert table["boundary"]["blocking"] == {"shared": 1, "critic_only": 0}
        assert table["boundary"]["warning"] == {"shared": 0, "critic_only": 1}
        assert table["boundary"]["observation"] == {"shared": 1, "critic_only": 1}
        assert table["boundary"]["native_only"] == 1
        assert table["inner"]["blocking"] == {"shared": 0, "critic_only": 1}
        assert table["inner"]["native_only"] == 0


class TestReach:
    """A later review's reach is the Critic's own prior-dispositions rule: the
    same plan scope (any, when it has none), and a cited file it changes."""

    def _review(self, rid, seq, scope=None):
        return {"review_id": rid, "seq": seq, "scope": scope}

    def test_the_same_plan_scope_is_in_reach(self):
        assert compare.in_reach(self._review("J", 1, "memo"), self._review("K", 2, "memo"))

    def test_another_scope_is_not(self):
        assert not compare.in_reach(self._review("J", 1, "a"), self._review("K", 2, "b"))

    def test_a_review_with_no_scope_reaches_every_earlier_one(self):
        assert compare.in_reach(self._review("J", 1, "a"), self._review("K", 2, None))

    def test_a_later_review_is_never_earlier(self):
        assert not compare.in_reach(self._review("J", 3, "memo"), self._review("K", 2, "memo"))
        assert not compare.in_reach(self._review("J", 2, "memo"), self._review("K", 2, "memo"))

    def test_earlier_is_store_order_not_the_timestamp(self, inner_pair, monkeypatch, capsys):
        """Two reviews can consolidate in one second (a fast runner does), and a
        timestamp comparison then finds nothing earlier. Pin it by stamping
        every fact with one second."""
        repo, _b, _i = inner_pair
        real = compare.evidence.read_facts

        def same_second(project_dir):
            store = real(project_dir)
            for fact in store.get("facts") or []:
                fact["ts"] = "2026-11-13T00:00:00Z"
            return store

        monkeypatch.setattr(compare.evidence, "read_facts", same_second)
        assert compare.main([str(repo)]) == 0
        assert "re-raise candidates — native: 1 of 1" in capsys.readouterr().out

    def test_the_file_rule_is_prior_dispositions_own(self):
        """A finding is in reach when it cites a file the later review changes,
        and every finding is when the later review names none — as
        `prior_dispositions` treats an empty `files_changed`."""
        assert compare.cites_a_changed_file(_native("a.py"), ["a.py", "b.py"])
        assert not compare.cites_a_changed_file(_native("a.py"), ["b.py"])
        assert compare.cites_a_changed_file(_native("a.py"), [])
        assert compare.cites_a_changed_file(_native("a.py"), None)


class TestReraiseCandidates:
    def test_a_native_finding_on_an_earlier_findings_file_is_a_candidate(self):
        earlier = [{"review_id": "J", "options": [(_critic("R-3", "g", "a.py"), "critic-accept")]}]
        later = {"review_id": "K", "critic": [], "native": [_native("a.py"), _native("b.py")]}
        [cand] = compare.reraise_candidates(later, earlier)
        assert cand["by"] == "native" and cand["earlier_kind"] == "critic-accept"
        assert [e["fid"] for e in cand["earlier"]] == ["R-3"] and cand["finding"]["file"] == "a.py"

    def test_the_critic_is_measured_too_as_the_baseline(self):
        earlier = [{"review_id": "J", "options": [(_critic("R-3", "g", "a.py"), "critic-file")]}]
        later = {"review_id": "K", "critic": [_critic("R-1", "g", "a.py", "x.py")], "native": None}
        [cand] = compare.reraise_candidates(later, earlier)
        assert (cand["by"], cand["earlier_kind"]) == ("critic", "critic-file")

    def test_every_earlier_finding_on_the_file_is_offered(self):
        """A file can hold several earlier findings; offering only the first
        would hide the one the later finding repeats."""
        earlier = [{"review_id": "J", "options": [
            (_critic("R-1", "g", "a.py"), "critic-accept"), (_critic("R-2", "g", "b.py"), "critic-accept"),
            (_native("a.py", 40), "native"),
        ]}]
        later = {"review_id": "K", "critic": [], "native": [_native("a.py", 41)]}
        [cand] = compare.reraise_candidates(later, earlier)
        assert [e.get("fid") or e.get("line") for e in cand["earlier"]] == ["R-1", 40]
        assert cand["earlier_kind"] == "critic-accept+native"

    def test_one_candidate_per_later_finding_against_the_nearest_review(self):
        earlier = [
            {"review_id": "J2", "options": [(_critic("R-1", "g", "a.py"), "critic-accept")]},
            {"review_id": "J1", "options": [(_critic("R-2", "g", "a.py"), "critic-accept")]},
        ]
        later = {"review_id": "K", "critic": [], "native": [_native("a.py")]}
        [cand] = compare.reraise_candidates(later, earlier)
        assert cand["earlier_review"] == "J2"

    def test_control_another_file_is_no_candidate(self):
        earlier = [{"review_id": "J", "options": [(_critic("R-3", "g", "a.py"), "critic-accept"),
                                                  (_native("a.py"), "native")]}]
        later = {"review_id": "K", "critic": [_critic("R-1", "g", "b.py")], "native": [_native("b.py")]}
        assert compare.reraise_candidates(later, earlier) == []


@pytest.fixture
def inner_pair(paired_repo, monkeypatch):
    """The boundary pair above, then a sampled inner `chunk` review of a later
    edit, consolidated clean, with its native text."""
    import test_native_review_pairing as pairing  # noqa: PLC0415

    repo, boundary_id = paired_repo
    monkeypatch.setattr(pairing.cc, "native_review_sampled", lambda _id: True)
    (repo / "src/app.py").write_text("x = 3\n")
    result = pairing._begin(repo, "chunk", monkeypatch, pairing.DEV)
    manifest = result["manifest"]
    assert manifest["native_review"]["synthetic_range"] is True
    partial = {
        "role": "reviewer", "goals": "1-3", "dispatch_id": result["id"],
        "commit_reviewed": manifest["commit_reviewed"], "model": "opus", "duration_seconds": 30,
        "findings": [], "summary": "clean",
    }
    (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(json.dumps(partial))
    assert pairing.cc.consolidate(repo, trigger="explicit") == 0
    pd = repo / ".prawduct"
    pairing.native_review.text_path(pd, result["id"]).write_text(json.dumps([
        {"file": "src/app.py", "line": 1, "summary": "x drifts again", "failure_scenario": "a"},
    ]))
    assert pairing.native_review.record(repo, pd, result["id"])[0] == 0
    return repo, boundary_id, result["id"]


class TestStages:
    def test_an_inner_pair_is_reported_apart_and_does_not_advance_the_stop(self, inner_pair, capsys):
        repo, _b, _i = inner_pair
        assert compare.main([str(repo)]) == 0
        out = capsys.readouterr().out
        assert "2 recorded, 2 comparable" in out
        assert "'paired_reviews': 1" in out  # boundary pairs only, as #1130 counts
        assert "inner pairs (#1166): 1" in out
        assert "  boundary warning: 1 / 0" in out
        assert "  boundary native only: 1" in out
        assert "  inner native only: 1" in out

    def test_a_moved_tree_is_named(self, inner_pair, capsys):
        repo, _b, inner_id = inner_pair
        _rewrite_native_event(
            repo, lambda e: e["native"].update(tree_moved=True)
            if e["native"]["critic_review_id"] == inner_id else None,
        )
        assert compare.main([str(repo)]) == 0
        assert f"WARNING: 1 run(s) read a tree that moved before they landed: {inner_id}" in capsys.readouterr().out

    def test_control_no_moved_tree_no_warning(self, inner_pair, capsys):
        repo, _b, _i = inner_pair
        assert compare.main([str(repo)]) == 0
        assert "moved before" not in capsys.readouterr().out

    def test_an_inner_run_names_the_file_a_shown_native_finding_named(self, inner_pair, capsys):
        """The inner review changes src/app.py, which the boundary run's native
        finding (put to the builder) names, and its native run names it again."""
        repo, _b, _i = inner_pair
        assert compare.main([str(repo)]) == 0
        assert "re-raise candidates — native: 1 of 1" in capsys.readouterr().out

    def test_a_later_boundary_review_is_compared(self, inner_pair, monkeypatch, tmp_path, capsys):
        """End to end: a second cumulative changes src/app.py again and its
        native run raises it again. The nearest earlier finding in reach that
        the builder saw is the first boundary run's native finding — the inner
        run's was never shown."""
        import test_native_review_pairing as pairing  # noqa: PLC0415

        repo, boundary_id, _inner_id = inner_pair
        pairing._git(repo, "commit", "--quiet", "-am", "feat: x again")
        result = pairing._begin(repo, "cumulative", monkeypatch, pairing.DEV)
        manifest = result["manifest"]
        partial = {
            "role": "reviewer", "goals": "1-7", "dispatch_id": result["id"],
            "commit_reviewed": manifest["commit_reviewed"], "model": "opus", "duration_seconds": 60,
            "findings": [], "summary": "clean",
        }
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(json.dumps(partial))
        assert pairing.cc.consolidate(repo, trigger="explicit") == 0
        pd = repo / ".prawduct"
        pairing.native_review.text_path(pd, result["id"]).write_text(json.dumps([
            {"file": "src/app.py", "line": 1, "summary": "x drifts, still", "failure_scenario": "a"},
        ]))
        assert pairing.native_review.record(repo, pd, result["id"])[0] == 0
        out_dir = tmp_path / "out"
        assert compare.main([str(repo), "--out", str(out_dir)]) == 0
        # Both later native findings — the inner run's and this one — repeat it.
        assert "re-raise candidates — native: 2 of 2" in capsys.readouterr().out
        key = json.loads((out_dir / "blind-key.json").read_text())
        [reraise] = [v for v in key.values() if v.get("reraise_by") and v["review"] == result["id"]]
        assert reraise == {"review": result["id"], "reraise_by": "native", "earlier_kind": "native",
                           "earlier_review": boundary_id}


class TestCriticPriorsEndToEnd:
    def test_an_accepted_critic_finding_is_offered_as_the_critic_was_handed_it(self, paired_repo, monkeypatch, capsys):
        """The boundary review's warning on src/app.py is accepted; a later
        sampled inner review changes src/app.py and its native run names it.
        The earlier finding reaches it through `prior_dispositions` itself."""
        import test_native_review_pairing as pairing  # noqa: PLC0415
        from lib import dispositions  # noqa: PLC0415

        repo, boundary_id = paired_repo
        fid = json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())["findings"][0]["fid"]
        assert dispositions.record(repo, boundary_id, fid, "accept", reason="fine")["status"] == "recorded"
        monkeypatch.setattr(pairing.cc, "native_review_sampled", lambda _id: True)
        (repo / "src/app.py").write_text("x = 3\n")
        result = pairing._begin(repo, "chunk", monkeypatch, pairing.DEV)
        manifest = result["manifest"]
        partial = {"role": "reviewer", "goals": "1-3", "dispatch_id": result["id"],
                   "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
                   "duration_seconds": 30, "findings": [], "summary": "clean"}
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(json.dumps(partial))
        assert pairing.cc.consolidate(repo, trigger="explicit") == 0
        pd = repo / ".prawduct"
        pairing.native_review.text_path(pd, result["id"]).write_text(json.dumps([
            {"file": "src/app.py", "line": 1, "summary": "x again", "failure_scenario": "a"}]))
        assert pairing.native_review.record(repo, pd, result["id"])[0] == 0
        [inner] = [p for p in compare.load_pairs(repo) if p["review_id"] == result["id"]]
        found, exposed = compare.reraises(repo, compare.load_pairs(repo))
        [cand] = [c for c in found if c["review"] == result["id"]]
        assert cand["earlier_kind"] == "critic-accept+native"  # the boundary run's native finding too
        assert any(e.get("fid") == fid for e in cand["earlier"])
        assert exposed["native"] >= 1 and inner["stage"] == "inner"
