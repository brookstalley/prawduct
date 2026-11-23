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


def test_a_slash_command_opens_its_own_uncounted_turn(tmp_path):
    """A skill's questions and edits belong to the skill's turn, never to the typed
    request before it, and the echo itself is not an owner request."""
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("Edit"),
        _owner("<command-message>prawduct:pr</command-message>\n<command-name>/prawduct:pr</command-name>"),
        _calls("Edit"), _calls("AskUserQuestion"),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["requests"] == 1
    assert row["mid_build_asks"] == 0


def test_a_session_opening_with_a_slash_command_counts_no_request(tmp_path):
    path = _session(tmp_path, "p", [
        _owner("<command-name>/prawduct:critic</command-name>"), _calls("AskUserQuestion"),
    ])
    assert _total(tool.measure([path], None, None, 60, ())) == {}


def test_unparsed_lines_and_empty_transcripts_are_reported_not_silent(tmp_path):
    proj = tmp_path / "projects" / "p"
    proj.mkdir(parents=True)
    bad = proj / "bad.jsonl"
    bad.write_bytes(b'{not json\n\xff\xfe binary\n' + json.dumps(_owner(LONG)).encode() + b"\n")
    renamed = _write(proj / "renamed.jsonl", [{"kind": "user", "text": LONG}])
    health = __import__("collections").Counter()
    by = tool.measure([bad, renamed, proj / "gone.jsonl"], None, None, 60, (), health=health)
    assert _total(by)["requests"] == 1
    assert health["lines_unparsed"] == 2
    assert health["transcripts_without_owner_turns"] == 1
    assert health["transcripts_unreadable"] == 1


def test_an_owner_quoting_the_digest_does_not_govern_the_session(tmp_path):
    gone = "/nonexistent/repo"
    path = _session(tmp_path, "q", [
        _owner(f"why does it say '{tool.DIGEST_MARKER} Prawduct' here?", cwd=gone), _calls("Edit"),
    ])
    by = tool.measure([path], None, None, 60, ())
    assert _total(by, governed=True) == {}
    assert _total(by, governed=False)["requests"] == 1


def test_a_turn_without_a_timestamp_is_outside_every_window(tmp_path):
    rec = _owner(LONG)
    del rec["timestamp"]
    path = _session(tmp_path, "p", [rec, _calls("Edit")])
    health = __import__("collections").Counter()
    for since, until in (("2026-01-01", None), (None, "2026-10-09")):
        assert _total(tool.measure([path], since, until, 60, (), health=health)) == {}
    assert health["turns_without_timestamp"] == 2
    assert _total(tool.measure([path], None, None, 60, ()))["requests"] == 1


def test_json_totals_carry_every_count_even_when_zero(tmp_path, capsys):
    _session(tmp_path, "p", [_owner("short", cwd="/work/app")])
    tool.main(["--glob", str(tmp_path / "projects" / "*" / "*.jsonl"), "--json"])
    out = json.loads(capsys.readouterr().out)
    for side in ("governed", "ungoverned"):
        assert set(out["total"][side]) == set(tool.KEYS)
    assert out["projects"][0]["corrections"] == 0
    assert out["projects"][0]["goal_questions"] == 0
    assert "health" in out


def test_an_agent_reading_the_digest_file_does_not_govern_the_session(tmp_path):
    """The realistic false positive: a tool result carrying session-digest.md's text."""
    gone = "/nonexistent/repo"
    result = _tool_result(cwd=gone)
    result["message"]["content"][0]["content"] = tool.DIGEST_MARKER + " **Prawduct**"
    path = _session(tmp_path, "r", [_owner(LONG, cwd=gone), _calls("Edit"), result])
    assert _total(tool.measure([path], None, None, 60, ()), governed=True) == {}


def test_an_owner_asking_what_the_work_is_for_counts_as_a_goal_question(tmp_path):
    """The goal-grounding control's yield: the owner, not the agent, asking what the product or
    the work is trying to achieve. Counted on any owner turn, built or not, because the owner's
    complaint was having to ask it at all. A solution question is not one."""
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("Edit"),
        _owner("wait, what are we really trying to achieve here?"),
        _owner("how does this implementation meet our product goals?"),
        _owner("is it clear what this build plan is trying to achieve, at the product level?"),
        _owner("can you sharpen what we’re trying to achieve before you plan?"),
        _owner("what\u2019s the point here, really?"),
        _owner("should this use AWS or Azure?"),
        _owner("what's the point of telling me a reason that was not used?"),
    ])
    assert _total(tool.measure([path], None, None, 60, ()))["goal_questions"] == 5


# --- #1211: compaction summaries, per-window health, the saved baseline -----------------------

#: A Claude Code compaction summary, in the shape read off a real transcript (keys and flags only,
#: text synthetic): a user record, `isCompactSummary` true, string content, not `isMeta`.
SUMMARY = ("This session is being continued from a previous conversation that ran out of context. "
           "The user said the banner was wrong and asked to revert it.")


def _summary(ts="2026-09-01T10:00:00Z", cwd="/work/app"):
    rec = _owner(SUMMARY, ts=ts, cwd=cwd)
    rec["isCompactSummary"] = True
    rec["isVisibleInTranscriptOnly"] = True
    return rec


def test_a_compaction_summary_is_not_an_owner_turn(tmp_path):
    """The summary arrives as a user record, long and full of correction words. Counted as an
    owner turn it inflated requests, substantive and corrections in the 2026-11 re-run."""
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("Edit"), _summary(), _calls("Edit"),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["requests"] == 1
    assert row["substantive"] == 1
    assert row["corrections"] == 0
    # The control: the same text without the flag is an owner typing it.
    typed = _session(tmp_path, "t", [
        _owner(LONG), _calls("Edit"), _owner(SUMMARY), _calls("Edit"),
    ])
    row = _total(tool.measure([typed], None, None, 60, ()))
    assert row["requests"] == 2
    assert row["corrections"] == 1


def test_work_after_a_compaction_summary_stays_with_the_request_it_continues(tmp_path):
    path = _session(tmp_path, "p", [
        _owner(LONG), _calls("AskUserQuestion"), _summary(), _calls("Edit"),
        _calls("AskUserQuestion"),
    ])
    row = _total(tool.measure([path], None, None, 60, ()))
    assert row["substantive"] == 1
    assert row["asked_first"] == 1
    assert row["mid_build_asks"] == 1


def _two_window_corpus(tmp_path):
    """Two transcripts per window. The baseline window holds one with no owner turns and one with a
    bad line; the after window holds one with no owner turns and one clean."""
    def _bare(ts):
        return {"type": "system", "timestamp": ts, "cwd": "/work/app"}
    proj = tmp_path / "projects" / "p"
    proj.mkdir(parents=True)
    before_empty = _write(proj / "b1.jsonl", [_bare("2026-09-01T10:00:00Z")])
    before_bad = proj / "b2.jsonl"
    before_bad.write_text(
        "{not json\n" + json.dumps(_owner(LONG, ts="2026-09-02T10:00:00Z")) + "\n", encoding="utf-8")
    after_empty = _write(proj / "a1.jsonl", [_bare("2026-10-20T10:00:00Z")])
    after_clean = _write(proj / "a2.jsonl", [_owner(LONG, ts="2026-10-21T10:00:00Z"), _calls("Edit")])
    return [before_empty, before_bad, after_empty, after_clean]


def test_health_is_tallied_over_the_transcripts_the_window_selects(tmp_path):
    import collections
    paths = _two_window_corpus(tmp_path)
    before, after = collections.Counter(), collections.Counter()
    tool.measure(paths, None, "2026-10-09", 60, (), health=before)
    tool.measure(paths, "2026-10-09", None, 60, (), health=after)
    assert before["transcripts_without_owner_turns"] == 1
    assert before["lines_unparsed"] == 1
    assert after["transcripts_without_owner_turns"] == 1
    assert after.get("lines_unparsed", 0) == 0
    assert before != after
    everything = collections.Counter()
    tool.measure(paths, None, None, 60, (), health=everything)
    assert everything["transcripts_without_owner_turns"] == 2
    assert everything["lines_unparsed"] == 1


def _run_json(tmp_path, capsys, *argv):
    glob = str(tmp_path / "projects" / "*" / "*.jsonl")
    rc = tool.main(["--glob", glob, "--json", *argv])
    return rc, json.loads(capsys.readouterr().out)


def test_cli_json_reports_per_window_health_and_transcript_count(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    _, before = _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", "")
    _, after = _run_json(tmp_path, capsys, "--since", "2026-10-09", "--baseline-file", "")
    assert before["transcripts"] == 2 and after["transcripts"] == 2
    assert before["transcripts_on_disk"] == after["transcripts_on_disk"] == 4
    assert before["health"] != after["health"]
    assert before["health"]["lines_unparsed"] == 1
    assert "lines_unparsed" not in after["health"]


def test_save_baseline_writes_counts_once_and_never_overwrites(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    store = tmp_path / "baselines.json"
    rc, out = _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store),
                        "--save-baseline", "--read-date", "2026-10-09")
    assert rc == 0 and out["baseline_saved"] is True
    saved = json.loads(store.read_text(encoding="utf-8"))
    entry = saved["windows"][tool.window_key(None, "2026-10-09")]
    assert entry["counts"]["ungoverned"]["requests"] == 1
    assert entry["counts"]["ungoverned"]["substantive"] == 0
    assert entry["health"]["lines_unparsed"] == 1
    assert entry["source"] == "measured" and entry["read"] == "2026-10-09"
    assert entry["tool_basis"].startswith("blob:")
    # Transcripts are pruned; a second --save-baseline must keep the first reading.
    for p in (tmp_path / "projects" / "p").glob("b*.jsonl"):
        p.unlink()
    rc, out = _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store),
                        "--save-baseline", "--read-date", "2026-10-09")
    assert rc == 0 and out["baseline_saved"] is False
    assert json.loads(store.read_text(encoding="utf-8")) == saved


def test_the_saved_baseline_leaks_no_text_paths_or_project_names(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    store = tmp_path / "baselines.json"
    _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store),
              "--save-baseline", "--read-date", "2026-10-09")
    text = store.read_text(encoding="utf-8")
    assert text.strip()
    assert LONG not in text and str(tmp_path) not in text and "/work/app" not in text
    assert '"p"' not in text


def test_a_rerun_reports_against_the_saved_counts_when_transcripts_were_pruned(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    store = tmp_path / "baselines.json"
    _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store),
              "--save-baseline", "--read-date", "2026-10-09")
    _, intact = _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store))
    assert intact["saved_baseline"]["pruned"] is False
    for p in (tmp_path / "projects" / "p").glob("b*.jsonl"):
        p.unlink()
    _, out = _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store))
    assert out["saved_baseline"]["counts"]["ungoverned"]["requests"] == 1
    assert out["saved_baseline"]["pruned"] is True
    assert out["saved_baseline"]["vs_live"]["ungoverned"]["requests"] == {"saved": 1, "live": 0}
    # A window with no saved reading reports none.
    _, other = _run_json(tmp_path, capsys, "--since", "2026-10-09", "--baseline-file", str(store))
    assert "saved_baseline" not in other


def test_a_saved_baseline_is_not_compared_across_min_chars(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    store = tmp_path / "baselines.json"
    _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store),
              "--save-baseline", "--read-date", "2026-10-09")
    _, out = _run_json(tmp_path, capsys, "--until", "2026-10-09", "--min-chars", "10",
                       "--baseline-file", str(store))
    assert out["saved_baseline"]["comparable"] is False
    assert "vs_live" not in out["saved_baseline"]


def test_a_corrupt_baseline_file_is_an_error_not_an_overwrite(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    store = tmp_path / "baselines.json"
    store.write_text("{not json", encoding="utf-8")
    glob = str(tmp_path / "projects" / "*" / "*.jsonl")
    rc = tool.main(["--glob", glob, "--json", "--until", "2026-10-09", "--baseline-file", str(store),
                    "--save-baseline"])
    assert rc == 2
    assert store.read_text(encoding="utf-8") == "{not json"


def test_the_committed_baseline_is_the_recorded_2026_10_09_reading():
    """The real file, read: the baseline the 2026-11 re-run found pruned. Its figures are the
    ones `requirements-alignment-discovery.md` records, null where that artifact records none."""
    store = tool.load_baselines(tool.DEFAULT_BASELINES)
    entry = store["windows"][tool.window_key(None, "2026-10-09")]
    assert entry["source"] == "artifact"
    gov = entry["counts"]["governed"]
    assert (gov["substantive"], gov["asked_first"], gov["mid_build_asks"], gov["corrections"]) == (
        963, 140, 349, 18)
    assert set(gov) == set(tool.KEYS)
    assert entry["counts"]["ungoverned"] is None
    assert entry["min_chars"] == 60


def _pruned_store(tmp_path, capsys, basis):
    """Save the baseline window, set its recorded tool_basis, then prune its transcripts."""
    _two_window_corpus(tmp_path)
    store = tmp_path / "baselines.json"
    _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store),
              "--save-baseline", "--read-date", "2026-10-09")
    doc = json.loads(store.read_text(encoding="utf-8"))
    doc["windows"][tool.window_key(None, "2026-10-09")]["tool_basis"] = basis
    store.write_text(json.dumps(doc), encoding="utf-8")
    for p in (tmp_path / "projects" / "p").glob("b*.jsonl"):
        p.unlink()
    return store


def _shortfall(tmp_path, capsys, basis, text=False):
    store = _pruned_store(tmp_path, capsys, basis)
    if text:
        glob = str(tmp_path / "projects" / "*" / "*.jsonl")
        tool.main(["--glob", glob, "--until", "2026-10-09", "--baseline-file", str(store)])
        return capsys.readouterr().out
    return _run_json(tmp_path, capsys, "--until", "2026-10-09", "--baseline-file", str(store))[1]


def test_a_shortfall_is_pruning_only_when_the_same_script_read_it(tmp_path, capsys):
    out = _shortfall(tmp_path, capsys, tool._tool_basis(), text=True)
    assert "transcripts were pruned" in out
    assert tool._instrument(tool._tool_basis()) == "same"


def test_a_shortfall_from_a_different_script_is_not_attributed_to_pruning(tmp_path, capsys):
    saved = _shortfall(tmp_path, capsys, "blob:" + "0" * 40)["saved_baseline"]
    assert saved["short"] is True and saved["pruned"] is False
    assert saved["instrument"] == "different"
    capsys.readouterr()
    out = _shortfall(tmp_path / "again", capsys, "blob:" + "0" * 40, text=True)
    assert "transcripts were pruned" not in out
    assert "different version of this script" in out


def test_a_saved_basis_that_resolves_to_nothing_is_unknown_not_same_or_different(tmp_path, capsys):
    for basis in ("commit:0000000000000000", None, "garbage"):
        assert tool._instrument(basis) == "unknown"
    saved = _shortfall(tmp_path, capsys, "commit:0000000000000000")["saved_baseline"]
    assert saved["instrument"] == "unknown" and saved["pruned"] is False and saved["short"] is True
    capsys.readouterr()
    out = _shortfall(tmp_path / "again", capsys, "commit:0000000000000000", text=True)
    assert "cannot be resolved" in out and "transcripts were pruned" not in out


def test_the_committed_baseline_is_a_different_instrument_not_pruning():
    entry = tool.load_baselines(tool.DEFAULT_BASELINES)["windows"][tool.window_key(None, "2026-10-09")]
    assert tool._instrument(entry["tool_basis"]) in ("different", "unknown")


def _save(tmp_path, capsys, *argv):
    glob = str(tmp_path / "projects" / "*" / "*.jsonl")
    store = tmp_path / "baselines.json"
    rc = tool.main(["--glob", glob, "--json", "--baseline-file", str(store), "--save-baseline",
                    "--read-date", "2026-11-01", *argv])
    captured = capsys.readouterr()
    return rc, captured.err, store


def test_save_baseline_refuses_an_open_ended_window(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    rc, err, store = _save(tmp_path, capsys, "--since", "2026-10-09")
    assert rc != 0 and "closed window" in err and not store.exists()


def test_save_baseline_refuses_an_until_after_the_read_date(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    rc, err, store = _save(tmp_path, capsys, "--until", "2026-11-02")
    assert rc != 0 and "closed window" in err and not store.exists()


def test_save_baseline_refuses_a_run_that_matched_no_transcripts(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    rc, err, store = _save(tmp_path, capsys, "--until", "2026-10-09", "--glob", str(tmp_path / "nope" / "*.jsonl"))
    assert rc != 0 and "no transcript" in err and not store.exists()


def test_save_baseline_accepts_a_closed_window_ending_on_the_read_date(tmp_path, capsys):
    _two_window_corpus(tmp_path)
    rc, err, store = _save(tmp_path, capsys, "--until", "2026-11-01")
    assert rc == 0 and err == "" and store.exists()
