"""Guards for `tools/measure-alignment-yield.py`.

The script is the alignment pass's yield: whether agents ask before building,
how often a build is interrupted by a question, and how often the owner
corrects one afterwards. Each count is a claim about which transcript records
are an owner speaking and which tool calls are a build, so the cases here are
the records that look like one and are not: tool results, sidechains, short
continuations, a question asked after the first edit, and correction words
following a turn that built nothing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-alignment-yield.py"

LONG = "Please add expiry alerts to the counter view so the household sees what goes off soon."


def _load():
    """Import the hyphenated script by path — not an importable module name."""
    spec = importlib.util.spec_from_file_location("measure_alignment_yield", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_alignment_yield"] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


def _owner(text, ts="2026-09-01T10:00:00Z", cwd="/work/app", **extra):
    return {"type": "user", "timestamp": ts, "cwd": cwd,
            "message": {"role": "user", "content": text}, **extra}


def _tool_result(cwd="/work/app"):
    return {"type": "user", "cwd": cwd, "timestamp": "2026-09-01T10:00:01Z",
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def _calls(*names, **extra):
    blocks = []
    for name in names:
        inp = {"command": "cat > notes.md"} if name == "Bash-write" else {"command": "ls"}
        blocks.append({"type": "tool_use", "name": "Bash" if name.startswith("Bash") else name,
                       "input": inp if name.startswith("Bash") else {}})
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}, **extra}


def _write(path: Path, records) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _session(tmp_path, name, records):
    proj = tmp_path / "projects" / name
    proj.mkdir(parents=True, exist_ok=True)
    return _write(proj / "s.jsonl", records)


def _total(by, governed=None):
    out = {}
    for (_, g), row in by.items():
        if governed is None or g == governed:
            for k, v in row.items():
                out[k] = out.get(k, 0) + v
    return out


def test_asked_first_counts_a_question_before_the_first_build(tmp_path):
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("AskUserQuestion"), _tool_result(), _calls("Edit"),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["substantive"] == 1
    assert row["asked_first"] == 1
    assert row["mid_build_asks"] == 0


def test_a_question_after_the_first_build_is_mid_build_not_asked_first(tmp_path):
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("Write"), _tool_result(), _calls("AskUserQuestion"),
        _calls("AskUserQuestion"),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["asked_first"] == 0
    assert row["mid_build_asks"] == 2


def test_tool_results_and_sidechains_are_not_owner_turns(tmp_path):
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("Edit"), _tool_result(),
        _owner("a subagent's brief that is long enough to count as a request otherwise",
               isSidechain=True),
        _owner("<command-name>/clear</command-name>"),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["requests"] == 1


def test_a_short_continuation_that_builds_is_not_substantive(tmp_path):
    path = _session(tmp_path, "p", [_owner("yes, do it"), _calls("Edit")])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["requests"] == 1
    assert row.get("substantive", 0) == 0


def test_a_bash_file_write_is_a_build_and_a_bash_read_is_not(tmp_path):
    wrote = _session(tmp_path, "w", [_owner(LONG), _calls("Bash-write")])
    read = _session(tmp_path, "r", [_owner(LONG), _calls("Bash-read")])
    assert _total(tool.measure([wrote], None, None, 60, ()))["substantive"] == 1
    assert _total(tool.measure([read], None, None, 60, ())).get("substantive", 0) == 0


def test_a_correction_counts_only_after_a_turn_that_built(tmp_path):
    after_build = _session(tmp_path, "a", [
        _owner(LONG), _calls("Edit"), _owner("that's wrong, revert the banner"),
    ])
    after_talk = _session(tmp_path, "b", [
        _owner(LONG), _calls("Bash-read"), _owner("that's wrong, revert the banner"),
    ])
    assert _total(tool.measure([after_build], None, None, 60, ()))["corrections"] == 1
    assert _total(tool.measure([after_talk], None, None, 60, ())).get("corrections", 0) == 0


def test_the_window_includes_since_and_excludes_until(tmp_path):
    path = _session(tmp_path, "p", [
        _owner(LONG, ts="2026-10-08T23:00:00Z"), _calls("Edit"),
        _owner(LONG, ts="2026-10-09T01:00:00Z"), _calls("Edit"),
    ])
    assert _total(tool.measure([path], None, "2026-10-09", 60, ()))["requests"] == 1
    assert _total(tool.measure([path], "2026-10-09", None, 60, ()))["requests"] == 1


def test_governed_comes_from_the_digest_even_when_the_directory_is_gone(tmp_path):
    digest = {"type": "attachment", "attachment": {
        "type": "hook_success", "content": tool.DIGEST_MARKER + " **Prawduct**"}}
    gone = "/nonexistent/deleted-worktree"
    with_digest = _session(tmp_path, "g", [digest, _owner(LONG, cwd=gone), _calls("Edit")])
    without = _session(tmp_path, "u", [_owner(LONG, cwd=gone), _calls("Edit")])
    by = tool.measure([with_digest, without], None, None, 60, ())
    assert _total(by, governed=True)["requests"] == 1
    assert _total(by, governed=False)["requests"] == 1


def test_governed_from_disk_when_the_directory_carries_prawduct_state(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    path = _session(tmp_path, "d", [_owner(LONG, cwd=str(repo)), _calls("Edit")])
    assert _total(tool.measure([path], None, None, 60, ()), governed=True)["requests"] == 1


def test_scratch_sessions_are_skipped(tmp_path):
    path = _session(tmp_path, "s", [_owner(LONG, cwd="/private/tmp/probe"), _calls("Edit")])
    assert _total(tool.measure([path], None, None, 60, tool.SCRATCH_PREFIXES)) == {}
    assert _total(tool.measure([path], None, None, 60, ()))["requests"] == 1


def test_the_marker_is_the_digest_the_plugin_injects():
    """The governed signal is only as good as this coupling: a reworded digest
    opening would silently reclassify every governed session as ungoverned."""
    digest = (REPO_ROOT / "plugin" / "methodology" / "session-digest.md").read_text(encoding="utf-8")
    assert digest.startswith(tool.DIGEST_MARKER)


def test_cli_json_reports_the_window_and_totals(tmp_path, capsys):
    _session(tmp_path, "p", [_owner(LONG, cwd="/work/app"), _calls("AskUserQuestion"), _calls("Edit")])
    rc = tool.main(["--glob", str(tmp_path / "projects" / "*" / "*.jsonl"), "--json",
                    "--until", "2026-10-09"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["transcripts"] == 1
    assert out["window"]["until"] == "2026-10-09"
    assert out["total"]["ungoverned"]["asked_first"] == 1


def test_a_subagents_questions_and_edits_are_not_the_main_agents(tmp_path):
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("Edit", isSidechain=True), _calls("AskUserQuestion", isSidechain=True),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["requests"] == 1
    assert row.get("substantive", 0) == 0
    assert row.get("mid_build_asks", 0) == 0
