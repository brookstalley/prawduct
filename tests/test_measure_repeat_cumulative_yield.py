"""Guards for `tools/measure-repeat-cumulative-yield.py`.

The tool re-derives the bounded-cumulative design's measured trade: for each
repeat cumulative review, which of its findings sat on files a review bounded
to the delta since the previous cumulative would still have rated. Each test
below names the misreading it would catch. They run on a synthetic git repo
and ledger whose answer is known, built once per module:

    main:    B ── B2 (advances the base: touches c.py and a.py)
              \\        \\
    feature:   C1 ── C2 ── C3 (merges B2)
              \\
    side:      S  (a sibling branch: never an ancestor of C2)

Cumulatives, in ledger order: R1 at C1 (base B), RS at S (base B), R2 at C2
(base B), R2b at C2 again (base B), R3 at C3 (base B2), and RN on a new
branch cut after the feature merged into main.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-repeat-cumulative-yield.py"


def _load():
    spec = importlib.util.spec_from_file_location("measure_repeat_cumulative_yield", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_repeat_cumulative_yield"] = module
    spec.loader.exec_module(module)
    return module


tool = _load()

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, **_GIT_ENV}
    out = subprocess.run(["git", "-C", str(repo), *args], check=True,
                         capture_output=True, text=True, env=env)
    return out.stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        (repo / name).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _finding(fid, severity, files, title="t"):
    f = {"fid": fid, "goal": "g", "severity": severity, "summary": title}
    if files is not None:
        f["files"] = files
    return f


def _event(fact_id, ts, commit, base, files_reviewed, findings, mode="cumulative (bundle)"):
    return {"schema_version": 1, "event": "review.critic", "ts": ts,
            "review": {"mode": mode, "commit_reviewed": commit, "base_reviewed": base,
                       "files_reviewed": files_reviewed, "findings": findings,
                       "fact_id": fact_id}}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    repo = tmp_path_factory.mktemp("repo")
    _git(repo, "init", "-q", "-b", "main")
    base = _commit(repo, {
        "a.py": "def keep():\n    return 1\n",
        "b.py": ("def old_helper():\n    return 2\nMSG = \"the helper is ready now\"\n"
                 "LEGACY_MODE = 1\n"),
        "c.py": "x = 1\n",
        "docs.md": "Intro.\n",
        "guide.md": "Nothing here yet.\n",
    }, "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    c1 = _commit(repo, {
        "a.py": "def keep():\n    return 10\n",
        "docs.md": ("Call `old_helper` to get two.\nNote: the helper is\nready now.\n"
                    "Set LEGACY_MODE first.\n"),
        "plan.md": "plan\n",
    }, "c1")
    # C2 retires `old_helper`, but docs.md (rated at C1) still teaches it. It also
    # retires LEGACY_MODE, which its own plan.md now names: gone from b.py, the
    # file it was removed from, but not from every file the delta changed.
    c2 = _commit(repo, {"b.py": "def new_helper():\n    return 3\n",
                        "plan.md": "plan v2\nLEGACY_MODE is retired.\n"}, "c2")
    _git(repo, "checkout", "-q", "-b", "side", base)
    side = _commit(repo, {"b.py": "def side():\n    return 3\n"}, "side")
    _git(repo, "checkout", "-q", "main")
    b2 = _commit(repo, {"c.py": "x = 2\n", "a.py": "def keep():\n    return 1\n# base\n"},
                 "advance the base")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "merge", "-q", "-X", "ours", "--no-edit", "main")
    c3 = _git(repo, "rev-parse", "HEAD")
    # The feature lands; a new branch starts from the base that now holds it.
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "feature")
    landed = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "next")
    n1 = _commit(repo, {"d.py": "y = 1\n"}, "n1")

    events = [
        _event("R1", "2026-09-01T00:00:00Z", c1, base, ["a.py", "docs.md"], []),
        _event("RS", "2026-09-01T01:00:00Z", side, base, ["b.py"], []),
        _event("R2", "2026-09-01T02:00:00Z", c2, base, ["a.py", "b.py", "docs.md"], [
            _finding("D1", "blocking", ["b.py"]),
            _finding("O1", "blocking", ["docs.md"], "docs.md still teaches old_helper"),
            _finding("O2", "warning", ["a.py"]),
            # plan.md changed in the delta but is not a rated (subject) file.
            _finding("P1", "blocking", ["plan.md"]),
            _finding("N1", "warning", []),
            _finding("N2", "blocking", None),
            # A second finding reusing D1's id, on an old-only file: classes are
            # kept by position, so it must not overwrite the first D1's.
            _finding("D1", "blocking", ["docs.md"], "a second finding reusing an id"),
        ]),
        # The same commit reviewed again.
        _event("R2b", "2026-09-01T03:00:00Z", c2, base, ["a.py", "b.py", "docs.md"],
               [_finding("X", "blocking", ["a.py"])]),
        _event("R3", "2026-09-01T04:00:00Z", c3, b2, ["a.py", "b.py", "docs.md"],
               [_finding("A1", "warning", ["a.py"])]),
        # A new branch: R3's commit is already in this base.
        _event("RN", "2026-09-01T04:30:00Z", n1, landed, ["d.py"],
               [_finding("NB", "blocking", ["a.py"])]),
        # Not a cumulative: never a prior and never a row.
        _event("CH", "2026-09-01T05:00:00Z", c3, b2, ["a.py"], [], mode="chunk"),
    ]
    ledger = repo / ".prawduct" / ".governance-ledger.jsonl"
    ledger.parent.mkdir()
    lines = [json.dumps(e) for e in events]
    lines.insert(2, "{not json")
    lines.insert(4, "[1, 2]")
    ledger.write_text("\n".join(lines) + "\n")

    # The clone's evidence store: one fact a ledger row also carries (R2, which
    # `both` must not read twice), one no ledger row carries (E1, as from a
    # review whose worktree, and ledger line, is gone), a fact that is not a
    # review, and one corrupt line. E1's base is under `base_reviewed`, R2's
    # under `base_commit`: both spellings are read.
    facts = [
        {"id": "R2", "kind": "review", "ts": "2026-09-01T02:00:00Z",
         "body": {"mode": "cumulative (bundle)", "head_commit": c2, "base_commit": base,
                  "files_reviewed": ["a.py", "b.py", "docs.md"],
                  "findings": [_finding("D1", "blocking", ["b.py"])]}},
        "{corrupt",
        {"id": "T1", "kind": "test", "ts": "2026-09-01T05:30:00Z", "body": {"mode": "cumulative"}},
        {"id": "E1", "kind": "review", "ts": "2026-09-01T06:00:00Z",
         "body": {"mode": "cumulative (bundle)", "head_commit": c3, "base_reviewed": base,
                  "files_reviewed": ["a.py", "docs.md"],
                  "findings": [_finding("EO", "blocking", ["docs.md"]),
                               _finding("EW", "warning", ["docs.md"])]}},
    ]
    store = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "prawduct"
    store.mkdir()
    (store / "evidence.jsonl").write_text(
        "\n".join(f if isinstance(f, str) else json.dumps(f) for f in facts) + "\n")
    return {"repo": repo, "base": base, "b2": b2, "c1": c1, "c2": c2, "c3": c3,
            "side": side, "ledger": ledger}


@pytest.fixture(scope="module")
def result(world):
    return tool.measure(world["repo"], source="ledger")


def _classes(rec, fid):
    """(class, bucket) of every finding in ``rec`` with this id, in review order."""
    return [(f["class"], f["bucket"]) for f in rec["findings"] if f["fid"] == fid]


def _cls(rec, fid):
    (only,) = _classes(rec, fid)
    return only[0]


def _bucket(rec, fid):
    (only,) = _classes(rec, fid)
    return only[1]


def _repeat(result, fact_id):
    matches = [r for r in result["repeats"] if r["id"] == fact_id]
    assert len(matches) == 1, f"{fact_id} not measured once: {result['repeats']}"
    return matches[0]


class TestReading:
    def test_corrupt_lines_are_skipped_and_counted_not_fatal(self, result):
        """Red if a corrupt line raises, or is dropped without being counted."""
        assert result["corrupt_lines"] == {"ledger": 2}
        assert result["cumulatives"] == 6, "the chunk review must not be read as cumulative"


class TestPrior:
    def test_a_non_ancestor_prior_is_not_used(self, result):
        """RS is newer than R1 but sits on a sibling branch; R2's prior is R1."""
        assert _repeat(result, "R2")["prior"] == "R1"

    def test_a_rereview_of_the_same_commit_looks_past_it_and_is_flagged(self, result):
        """R2b reviews C2 again. Its prior is the newest STRICT ancestor (R1),
        which is what reproduces the 2026-09-22 reading, and it is flagged,
        because the design's frontier would run it full (condition 4)."""
        r2b = _repeat(result, "R2b")
        assert r2b["prior"] == "R1" and r2b["rereview"] is True
        assert _repeat(result, "R2")["rereview"] is False
        assert result["rereviews"] == 1
        flagged = {e["fid"]: e["rereview"] for e in result["old_only_blocking"]}
        assert flagged == {"O1": False, "P1": False, "D1": False, "X": True, "NB": False}

    def test_the_first_cumulative_on_a_lineage_is_not_a_repeat(self, result):
        ids = {r["id"] for r in result["repeats"]}
        assert "R1" not in ids and "RS" not in ids


class TestClassification:
    def test_a_finding_on_a_file_changed_since_the_prior_is_delta(self, result):
        assert _classes(_repeat(result, "R2"), "D1")[0] == ("delta", None)

    def test_a_finding_on_a_file_only_the_prior_rated_is_old_only(self, result):
        r2 = _repeat(result, "R2")
        assert _cls(r2, "O1") == "old_only"
        assert _cls(r2, "O2") == "old_only"

    def test_a_finding_on_a_changed_file_outside_the_subject_set_is_old_only(self, result):
        """A bounded review's subject is the JUDGEABLE delta: a plan or record the
        delta changed is not rated there, so a finding on it is lost. Red if
        delta is read as 'any file changed since the prior'."""
        r2 = _repeat(result, "R2")
        assert _cls(r2, "P1") == "old_only"
        assert _bucket(r2, "P1") == "changed_not_subject"
        assert _bucket(r2, "O1") == "prior_rated"

    def test_a_finding_with_no_file_is_no_files_whether_empty_or_unrecorded(self, result):
        r2 = _repeat(result, "R2")
        assert _cls(r2, "N1") == "no_files"
        assert _cls(r2, "N2") == "no_files"
        assert result["files_unrecorded"] == 1, "an absent `files` is not an empty one"

    def test_subject_and_delta_file_counts(self, result):
        r2 = _repeat(result, "R2")
        assert (r2["subject_files"], r2["delta_files"]) == (3, 1)


class TestBaseAdvance:
    def test_a_base_advanced_repeat_is_counted_apart_from_same_base(self, result):
        r3 = _repeat(result, "R3")
        assert r3["prior"] == "R2b" and r3["same_base"] is False
        assert _repeat(result, "R2")["same_base"] is True
        same = result["tables"]["same_base"]
        assert same["repeats"] == 2
        assert result["tables"]["all"]["repeats"] == 4
        assert result["tables"]["base_advanced"]["repeats"] == 1
        assert same["warning"]["old_only"] == 1  # O2 only, not R3's A1

    def test_a_prior_already_merged_into_the_base_is_a_new_branch_not_an_advance(self, result):
        """RN's prior R3 landed in RN's base. Red if RN is read as a base-advanced
        repeat, which would put new-branch rows into Decision 4's overlap rate."""
        rn = _repeat(result, "RN")
        assert rn["prior"] == "R3" and rn["kind"] == "prior_in_base"
        assert _repeat(result, "R3")["kind"] == "base_advanced"
        assert result["tables"]["prior_in_base"]["repeats"] == 1
        assert result["tables"]["prior_in_base"]["blocking"]["old_only"] == 1

    def test_the_overlap_is_branch_files_the_base_advance_also_touched(self, result):
        """B2 touched a.py and c.py; the branch rates a.py, b.py, docs.md."""
        overlap = result["base_advance"]
        assert overlap["repeats"] == 1
        assert overlap["branch_files"] == 3
        assert overlap["overlap_files"] == 1
        assert overlap["repeats_with_overlap"] == 1


class TestSweep:
    def test_a_vanished_token_still_named_by_an_old_file_is_caught(self, result):
        """`old_helper` left b.py in the delta and docs.md still names it."""
        sweeps = {s["fid"]: s for s in result["old_only_blocking"]}
        assert sweeps["O1"]["caught"] is True
        assert "old_helper" in sweeps["O1"]["hit_tokens"]
        assert sweeps["O1"]["hit_tokens_named_by_finding"] == ["old_helper"]

    def test_a_finding_no_vanished_token_reaches_is_missed(self, result):
        """Control: X sits on a.py, which names no token the delta retired."""
        sweeps = {s["fid"]: s for s in result["old_only_blocking"]}
        assert sweeps["X"]["caught"] is False and sweeps["X"]["caught_uncapped"] is False

    def test_a_token_still_present_in_the_changed_files_is_not_vanished(self, world):
        g = tool.Git(world["repo"])
        tokens = tool.vanished_tokens(g, world["c1"], world["c2"])
        assert "old_helper" in tokens
        assert "return" not in tokens, "a token still in b.py at HEAD did not vanish"

    def test_a_hard_wrapped_quotation_is_reached_only_by_a_phrase_window(self, world):
        """The removed literal is quoted in docs.md across a line break, so the
        whole-literal grep (the design's sweep) misses it; a 3-word window hits."""
        g = tool.Git(world["repo"])
        plain = tool.vanished_tokens(g, world["c1"], world["c2"])
        assert "the helper is ready now" in plain
        assert g.grep_files(world["c2"], "the helper is ready now") == []
        assert "the helper is" not in plain
        phrased = tool.vanished_tokens(g, world["c1"], world["c2"], phrase_words=3)
        assert "the helper is" in phrased
        assert "docs.md" in g.grep_files(world["c2"], "the helper is")

    def test_a_wide_reach_token_is_not_read_site_by_site(self, world):
        g = tool.Git(world["repo"])
        hits = tool.sweep_hits(g, world["c2"], ["old_helper"], max_tokens=10, max_sites=0)
        assert hits["old_helper"]["wide"] is True
        assert hits["old_helper"]["files"] == []


class TestSources:
    """The evidence store and the `both` merge. The 2026-11-11 reading's
    `--source both` figures come through these paths."""

    def test_evidence_reads_the_review_facts_and_counts_its_corrupt_line(self, world):
        """Red if a fact's commit, base, rated files or findings are read from
        the wrong key, or a corrupt line is fatal or uncounted."""
        data = tool.measure(world["repo"], source="evidence")
        assert data["corrupt_lines"] == {"evidence": 1}
        assert data["cumulatives"] == 2, "R2 and E1; the test fact is not a review"
        assert data["unresolvable"] == 0
        (e1,) = data["repeats"]
        assert (e1["id"], e1["source"], e1["prior"]) == ("E1", "evidence", "R2")
        assert (e1["commit"], e1["prior_commit"]) == (world["c3"], world["c2"])
        # E1's base is under base_reviewed and R2's under base_commit.
        assert e1["base"] == e1["prior_base"] == world["base"]
        assert e1["kind"] == "same_base"
        assert e1["subject_files"] == 2
        assert _classes(e1, "EO") == [("old_only", "prior_rated")]
        assert _classes(e1, "EW") == [("old_only", "prior_rated")]

    def test_both_adds_only_the_facts_no_ledger_row_carries(self, world, result):
        """Red if `both` reads R2 twice (once from the ledger, once from the
        store), or drops the store-only E1."""
        data = tool.measure(world["repo"], source="both")
        assert data["corrupt_lines"] == {"ledger": 2, "evidence": 1}
        assert data["cumulatives"] == result["cumulatives"] + 1
        r2 = _repeat(data, "R2")
        assert r2["source"] == "ledger"
        e1 = _repeat(data, "E1")
        assert e1["source"] == "evidence"
        assert e1["prior"] == "R2b" and e1["rereview"] is True, "R3 already reviewed C3"
        assert {r["id"] for r in data["repeats"]} == {r["id"] for r in result["repeats"]} | {"E1"}


class TestWindow:
    def test_until_drops_later_rows_and_keeps_the_boundary_row(self, world, result):
        """Red if `--until` is ignored, or excludes a row stamped exactly at it."""
        data = tool.measure(world["repo"], until="2026-09-01T03:00:00Z")
        assert data["cumulatives"] == 4
        assert {r["id"] for r in data["repeats"]} == {"R2", "R2b"}
        assert len(data["repeats"]) < len(result["repeats"])

    def test_since_drops_earlier_rows_including_the_prior_they_would_supply(self, world):
        """Without R1, R2 and R2b have no strict-ancestor prior inside the window."""
        data = tool.measure(world["repo"], since="2026-09-01T02:00:00Z")
        assert data["cumulatives"] == 4
        assert {r["id"]: r["prior"] for r in data["repeats"]} == {"R3": "R2b", "RN": "R3"}

    def test_the_cli_passes_the_window_through(self, world):
        out = subprocess.run([sys.executable, str(_TOOL), str(world["repo"]), "--json",
                              "--until", "2026-09-01T03:00:00Z", "--no-sweep"],
                             capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        assert data["window"]["until"] == "2026-09-01T03:00:00Z"
        assert data["tables"]["all"]["repeats"] == 2


class TestDuplicateIds:
    def test_two_findings_sharing_an_id_keep_their_own_classes(self, result):
        """R2 carries two findings with id D1: on b.py (delta) and on docs.md
        (old-only). Red if classes are keyed by id: the second overwrites the
        first, so both count as old-only and both list as old-only blockers."""
        r2 = _repeat(result, "R2")
        assert _classes(r2, "D1") == [("delta", None), ("old_only", "prior_rated")]
        same = result["tables"]["same_base"]["blocking"]
        assert (same["delta"], same["old_only"], same["no_files"]) == (1, 4, 1)
        listed = [e["files"] for e in result["old_only_blocking"] if e["fid"] == "D1"]
        assert listed == [["docs.md"]]


def _diff_repo(tmp_path, before: dict[str, str], after: dict[str, str]) -> tuple[Path, str, str]:
    repo = tmp_path / "diffrepo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    a = _commit(repo, before, "before")
    for name in before:
        if name not in after:
            (repo / name).unlink()
    b = _commit(repo, after, "after")
    return repo, a, b


class TestRemovedLines:
    """Removed lines are read by hunk state: a `--- ` line is a header only
    before a file's first `@@`."""

    def test_a_removed_line_starting_with_two_dashes_is_kept(self, tmp_path):
        """Its diff line reads `---verbose`. Red if every `---` line is skipped."""
        repo, a, b = _diff_repo(tmp_path, {"run.sh": "--verbose\nkeep\n"}, {"run.sh": "keep\n"})
        assert dict(tool.Git(repo).removed_lines(a, b)) == {"run.sh": ["--verbose"]}

    def test_a_removed_dash_dash_space_line_is_not_a_header(self, tmp_path):
        """Its diff line reads `--- a comment`. Red if it is taken for a file
        header, which drops it and every later removed line of the file."""
        repo, a, b = _diff_repo(
            tmp_path,
            {"q.sql": "one\n-- a comment\ntwo\nretired_name\nthree\n", "z.txt": "gone_too\nstay\n"},
            {"q.sql": "one\ntwo\nthree\n", "z.txt": "stay\n"})
        removed = tool.Git(repo).removed_lines(a, b)
        assert dict(removed) == {"q.sql": ["-- a comment", "retired_name"], "z.txt": ["gone_too"]}

    def test_headers_of_deleted_added_and_spaced_paths(self, tmp_path):
        """Control: a deleted file's lines are read under its old path, an added
        file has none, and a path with a space is read without git's trailing tab."""
        repo, a, b = _diff_repo(
            tmp_path, {"old.py": "def gone():\n    pass\n", "my notes.txt": "drop me\nkeep\n"},
            {"new.py": "def fresh():\n    pass\n", "my notes.txt": "keep\n"})
        removed = tool.Git(repo).removed_lines(a, b)
        assert dict(removed) == {"old.py": ["def gone():", "    pass"], "my notes.txt": ["drop me"]}


class TestVanishedIn:
    """C2 retires LEGACY_MODE from b.py; its own plan.md names it. Step 2 read
    literally ("those files") calls it vanished; the every-changed-file reading
    is masked by the plan."""

    def test_the_two_readings_differ_on_a_name_the_delta_s_own_plan_mentions(self, world):
        g = tool.Git(world["repo"])
        changed = tool.vanished_tokens(g, world["c1"], world["c2"], vanished_in="changed")
        source = tool.vanished_tokens(g, world["c1"], world["c2"], vanished_in="source")
        assert "old_helper" in changed and "old_helper" in source
        assert "LEGACY_MODE" not in changed
        assert "LEGACY_MODE" in source
        assert "return" not in source, "still in b.py, the file it was removed from"
        assert set(changed) <= set(source)

    def test_the_default_is_the_every_changed_file_reading(self, world):
        g = tool.Git(world["repo"])
        assert tool.vanished_tokens(g, world["c1"], world["c2"]) == tool.vanished_tokens(
            g, world["c1"], world["c2"], vanished_in="changed")

    def test_an_unknown_reading_is_refused(self, world):
        with pytest.raises(ValueError):
            tool.vanished_tokens(tool.Git(world["repo"]), world["c1"], world["c2"], vanished_in="all")

    def test_the_cli_option_reaches_the_sweep(self, world):
        """Red if `--vanished-in` is parsed but not passed down: O1's docs.md is
        reached through LEGACY_MODE only under the literal reading."""
        def o1(*extra):
            out = subprocess.run([sys.executable, str(_TOOL), str(world["repo"]), "--json", *extra],
                                 capture_output=True, text=True, check=True)
            data = json.loads(out.stdout)
            (entry,) = [e for e in data["old_only_blocking"] if e["fid"] == "O1"]
            return data["sweep_caps"]["vanished_in"], entry["hit_tokens"]

        reading, hits = o1("--vanished-in", "source")
        assert reading == "source" and "LEGACY_MODE" in hits and "old_helper" in hits
        reading, hits = o1()
        assert reading == "changed" and "LEGACY_MODE" not in hits and "old_helper" in hits


class TestCli:
    def test_json_and_human_output(self, world):
        out = subprocess.run([sys.executable, str(_TOOL), str(world["repo"]), "--json"],
                             capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        assert data["tables"]["all"]["repeats"] == 4
        human = subprocess.run([sys.executable, str(_TOOL), str(world["repo"])],
                               capture_output=True, text=True, check=True)
        assert "same base" in human.stdout and "blocking" in human.stdout
