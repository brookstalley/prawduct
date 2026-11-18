"""The blind-verification join (#1197): verdicts are carried by item id, the per-goal table
shows the non-minor share beside the native share, and every rate is over the frozen sheet's
reviews."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".prawduct" / "research" / "native-review-paired" / "join.py"
sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("native_review_join", SCRIPT)
join = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(join)

GOAL = "The Design Is Sound"
META = {("r1", "R-1"): (GOAL, "blocking"), ("r1", "R-2"): (GOAL, "warning"), ("r2", "O-1"): (GOAL, "observation")}
STAGES = {"r1": "boundary", "r2": "inner"}
KEY = {
    "V-1": {"review": "r1", "first_source": "native", "critic_fid": "R-1"},
    "V-2": {"review": "r1", "source": "critic", "fid": "R-2"},
    "V-3": {"review": "r2", "source": "native"},
    "V-4": {"review": "r2", "source": "native"},
    "V-5": {"review": "r2", "reraise_by": "native", "earlier_kind": "native", "earlier_review": "r1"},
}
ANSWERS = [  # deliberately out of key order
    {"id": "V-5", "repeats": "no", "real": "yes"},
    {"id": "V-4", "real": "yes", "goal": GOAL, "minor": False},
    {"id": "V-3", "real": "yes", "goal": GOAL, "minor": True},
    {"id": "V-2", "real": "yes", "minor": False},
    # native came first: its side is "first"; the Critic's is "second"
    {"id": "V-1", "same": "yes", "first_real": "yes", "second_real": "yes", "first_goal": GOAL, "minor": False},
]


def test_join_is_by_id_and_tallies_goal_stage_severity():
    r = join.join(KEY, ANSWERS, META, STAGES)
    g = r["goal"][GOAL]
    assert (g["both"], g["critic_only"], g["native_only"], g["native_only_minor"]) == (1, 1, 2, 1)
    assert r["stage"]["boundary"]["both"] == 1 and r["stage"]["inner"]["native_only"] == 2
    assert r["severity"]["blocking"]["also_native"] == 1 and r["severity"]["warning"]["real"] == 1
    assert r["reraise"]["native"]["repeats=no"] == 1
    assert r["reviews"] == 2 and r["missing"] == []


def test_non_minor_share_sits_beside_native_share():
    r = join.join(KEY, ANSWERS, META, STAGES)
    native, non_minor = join.shares(r["goal"][GOAL])
    assert round(native, 2) == 0.75  # (1 both + 2 native-only) of 4
    assert round(non_minor, 2) == 0.67  # drop the one minor native-only: 2 of 3
    assert "native share 75%; non-minor native share 67%" in join.render(r)


def test_denominator_is_the_frozen_sheets_reviews_and_missing_answers_are_named():
    r = join.join(KEY, ANSWERS[:-1], META, STAGES)  # V-1 unanswered
    assert r["missing"] == ["V-1"] and r["reviews"] == 2
    assert r["goal"][GOAL]["both"] == 0
    r = join.join(KEY, ANSWERS, META, {})  # repos no longer hold the reviews
    assert r["unknown_reviews"] == ["r1", "r2"] and "WARNING" in join.render(r)


def test_runs_from_arguments_alone(tmp_path):
    (tmp_path / "key.json").write_text(json.dumps(KEY))
    (tmp_path / "a.json").write_text(json.dumps(ANSWERS))
    out = subprocess.run([sys.executable, "-I", str(SCRIPT), "--key", str(tmp_path / "key.json"),
                          "--answers", str(tmp_path / "a.json")], capture_output=True, text=True)
    assert out.returncode == 0 and "reviews 2" in out.stdout
