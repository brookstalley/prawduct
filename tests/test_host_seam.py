"""The host seam (`plugin/lib/host.py`) is the one place host shapes live.

#928 R-2: a second host adapter must be a second implementation of one module,
not a patch at every call site. So:

* no file under `plugin/bin`, `plugin/lib` or `plugin/hooks` but `host.py`
  names a host environment variable, reads a host payload key, or writes a host
  response key;
* `read_event` keeps what each payload field said, including null versus
  absent;
* an unknown `PRAWDUCT_HOST` fails closed: the Stop gate blocks naming the
  variable, and the hooks that cannot block note it and do nothing.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import copy_seam_files  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / "plugin"
HOOK = PLUGIN / "bin" / "prawduct-hook"
sys.path.insert(0, str(PLUGIN))

from lib import gates, host  # noqa: E402

_SEAM = PLUGIN / "lib" / "host.py"
_SCANNED_DIRS = ("bin", "lib", "hooks")

# Any quoted host variable name: an environment read needs the literal name
# whatever accessor carries it (`os.environ.get`, `getenv`, an `env` dict
# passed down), so the literal is the thing to look for. Prose mentions
# (``CLAUDE_PROJECT_DIR``, `${CLAUDE_PLUGIN_ROOT}`) are not quoted literals.
_HOST_VARIABLE = re.compile(r"""["']CLAUDE_[A-Z_]+["']""")
# Payload keys read off a dict, by `.get` or subscript: every key the seam
# itself reads, taken from the seam so a key it gains is scanned for too.
_PAYLOAD_KEYS = (
    host._MESSAGE_KEY, host._TASKS_KEY, host._CWD_KEY, host._AGENT_TYPE_KEY,
    host._TRANSCRIPT_KEY,
)
_PAYLOAD_READ = re.compile(
    r"""(\.get\(\s*|\[\s*)["'](""" + "|".join(map(re.escape, _PAYLOAD_KEYS)) + r""")["']"""
)
# Response keys written as dict-literal keys or item assignments.
_RESPONSE_WRITE = re.compile(
    r"""["'](systemMessage|hookSpecificOutput|additionalContext|hookEventName|reloadSkills)["']"""
    r"""\s*(:|\]\s*=)"""
)


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for name in _SCANNED_DIRS:
        for path in sorted((PLUGIN / name).rglob("*")):
            if "__pycache__" in path.parts or not path.is_file():
                continue
            if path.suffix == ".py" or path.parent.name == "bin":
                files.append(path)
    return files


def _violations(files: list[Path]) -> list[str]:
    found: list[str] = []
    for path in files:
        if path == _SEAM:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for pattern in (_HOST_VARIABLE, _PAYLOAD_READ, _RESPONSE_WRITE):
                if pattern.search(line):
                    found.append(f"{path}:{number}: {line.strip()}")
    return found


class TestOnePlace:
    def test_the_scan_reaches_the_entry_points_and_the_seam(self):
        files = _scanned_files()
        names = {p.relative_to(PLUGIN).as_posix() for p in files}
        # The entry points and the modules that used to read host shapes are
        # all inside the scan, and so is the seam itself.
        for expected in (
            "bin/prawduct-hook", "hooks/banner.py", "hooks/digest.py", "lib/gates.py",
            "lib/plugin_activation.py", "lib/stranded_work.py", "lib/host.py",
        ):
            assert expected in names
        assert len(files) > 50

    def test_the_patterns_match_what_the_seam_itself_does(self):
        """Positive control: the seam's own reads and writes are what the scan
        looks for, so a clean scan elsewhere means absence, not blindness."""
        text = _SEAM.read_text(encoding="utf-8")
        assert _HOST_VARIABLE.search(text)
        assert re.search(r"""["']systemMessage["']\s*:""", text)
        assert re.search(r"""["']hookSpecificOutput["']\s*:""", text)

    def test_no_host_shape_outside_the_seam(self):
        assert _violations(_scanned_files()) == []

    def test_a_restored_site_is_found(self, tmp_path):
        """Red check: one site put back the way it was is a violation."""
        restored = tmp_path / "restored.py"
        restored.write_text(
            'import os\nroot = os.environ.get("CLAUDE_PLUGIN_ROOT")\n'
            'msg = stop_input.get("last_assistant_message")\n'
            'cwd = stop_input.get("cwd")\n'
            'print(json.dumps({"systemMessage": text}))\n'
            'hook_output["reloadSkills"] = True\n'
        )
        assert len(_violations([restored])) == 5

    def test_a_blocking_stop_exits_through_the_seam(self, tmp_path, monkeypatch):
        """The blocking exit is whatever `host.block` returns, and the whole
        block reason goes through it: a sentinel exit code proves no other
        path chose the code, and an empty stderr proves no other path wrote
        the reason."""
        loader = importlib.machinery.SourceFileLoader("prawduct_hook_seam", str(HOOK))
        spec = importlib.util.spec_from_loader("prawduct_hook_seam", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        calls: list[str] = []

        def spy(reason: str) -> int:
            calls.append(reason)
            return 77

        monkeypatch.setattr(module._host(), "block", spy)
        repo = _governed_repo(tmp_path)
        (repo / ".prawduct" / ".session-git-baseline").write_text("")
        base_tree = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=str(repo), capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        (repo / ".prawduct" / ".session-base-tree").write_text(base_tree)
        (repo / "code.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c2")
        assert module.cmd_stop(repo, {}) == 77
        assert len(calls) == 1 and "BLOCKED — resolve before ending session:" in calls[0]


class TestReadEvent:
    def test_null_and_absent_message_both_read_none_and_stay_apart(self):
        absent = host.read_event("stop", {})
        null = host.read_event("stop", {"last_assistant_message": None})
        assert absent.last_assistant_message is None and null.last_assistant_message is None
        assert "last_assistant_message" not in absent.fields_present
        assert "last_assistant_message" in null.fields_present

    def test_a_message_is_kept_as_sent(self):
        event = host.read_event("stop", {"last_assistant_message": "  done  "})
        assert event.last_assistant_message == "  done  "

    def test_absent_background_tasks_is_none_and_empty_is_empty(self):
        assert host.read_event("stop", {}).background_tasks is None
        assert host.read_event("stop", {"background_tasks": []}).background_tasks == ()
        assert host.read_event("stop", {"background_tasks": "x"}).background_tasks == ()

    def test_background_tasks_are_labelled_by_their_best_identifier(self):
        event = host.read_event("stop", {"background_tasks": [
            {"type": "workflow", "name": "review", "id": "wf_1"},
            {"type": "agent", "agent_type": "critic-reviewer", "id": "a_2"},
            {"id": "x_3"},
            {},
            "not a task",
            {"type": "shell", "command": "y" * 200},
        ]})
        assert event.background_tasks == (
            "workflow:review", "agent:critic-reviewer", "task:x_3", "task", "shell:" + "y" * 74,
        )

    def test_empty_and_garbage_payloads_read_as_empty(self):
        for raw in ({}, None, "text", [1, 2]):
            event = host.read_event("stop", raw)
            assert event == host.HostEvent(event="stop")

    def test_non_string_agent_type_and_cwd_read_as_none(self):
        event = host.read_event("subagent_stop", {"agent_type": 7, "cwd": ["/x"]})
        assert event.agent_type is None and event.cwd is None
        assert {"agent_type", "cwd"} <= event.fields_present

    def test_agent_type_is_stripped_and_cwd_kept_as_sent(self):
        """A name is compared, so its padding is noise; a path is used, and a
        directory may really end in a space."""
        event = host.read_event(
            "subagent_stop", {"agent_type": " prawduct:critic-reviewer ", "cwd": " /r "}
        )
        assert event.agent_type == "prawduct:critic-reviewer" and event.cwd == " /r "

    def test_an_unknown_event_is_a_caller_bug(self):
        with pytest.raises(ValueError):
            host.read_event("pre_tool_use", {})

    def test_the_transcript_path_is_kept_as_sent_and_garbage_is_none(self):
        event = host.read_event("stop", {"transcript_path": " /t/s.jsonl"})
        assert event.transcript_path == " /t/s.jsonl"
        assert host.read_event("stop", {"transcript_path": 3}).transcript_path is None
        assert host.read_event("stop", {}).transcript_path is None


def _record(kind: str, when: str, *blocks: dict) -> str:
    """One transcript line in the shape Claude Code writes: these keys and
    nesting were read off a real transcript (2026-11); the fields the reader
    ignores are left out."""
    return json.dumps({
        "type": kind, "timestamp": when, "isSidechain": False,
        "message": {"role": kind, "content": list(blocks)},
    }) + "\n"


class TestTheSessionRecord:
    """`host.session_tool_activity` and `host.other_session_wrote_since`: the
    reads #1071's span narrowing stands on."""

    def test_a_call_runs_from_its_use_to_its_result(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        transcript.write_text(
            json.dumps({"type": "user", "timestamp": "2026-11-15T10:00:00.000Z",
                        "message": {"role": "user", "content": "hi"}}) + "\n"
            + _record("assistant", "2026-11-15T10:01:00.500Z",
                      {"type": "tool_use", "id": "a", "name": "Bash", "input": {}})
            + _record("user", "2026-11-15T10:01:30.000Z",
                      {"type": "tool_result", "tool_use_id": "a", "content": "ok"})
            # A record with no timestamp (the host's request blobs) is skipped.
            + json.dumps({"type": "api-request-blob", "message": {"content": [
                {"type": "tool_use", "id": "z", "name": "Bash", "input": {}}]}}) + "\n"
        )
        activity = host.session_tool_activity(str(transcript))
        start = 1794736860.5  # 2026-11-15T10:01:00.5Z
        assert activity is not None
        assert activity.windows == ((start, start + 29.5),)
        assert activity.covered_from == start - 60.5
        assert activity.acting_at(start + 10) is True
        assert activity.acting_at(start + 29.5 + host.ACTIVITY_SLACK_SECONDS) is True
        assert activity.acting_at(start + 40) is False
        assert activity.acting_at(start - 600) is None

    def test_a_background_call_never_closes(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        transcript.write_text(
            _record("assistant", "2026-11-15T10:01:00Z", {
                "type": "tool_use", "id": "a", "name": "Agent",
                "input": {"run_in_background": True}})
            + _record("user", "2026-11-15T10:01:01Z",
                      {"type": "tool_result", "tool_use_id": "a", "content": "launched"})
        )
        activity = host.session_tool_activity(str(transcript))
        assert activity.acting_at(1794736860 + 86400) is True

    def test_nothing_timestamped_or_nothing_there_is_none(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        transcript.write_text('{"type": "user"}\n')
        assert host.session_tool_activity(str(transcript)) is None
        assert host.session_tool_activity(str(tmp_path / "missing.jsonl")) is None

    def test_a_transcript_it_does_not_understand_is_none(self, tmp_path):
        """Read as idle throughout, an unrecognised format would disown the
        session's own commits, so it says nothing instead."""
        transcript = tmp_path / "s.jsonl"
        prompt = json.dumps({"type": "user", "timestamp": "2026-11-15T10:00:00Z",
                             "message": {"role": "user", "content": "hi"}}) + "\n"
        transcript.write_text(prompt)
        assert host.session_tool_activity(str(transcript)) is None  # no call at all
        transcript.write_text(
            prompt + _record("user", "2026-11-15T10:01:01Z",
                             {"type": "tool_result", "tool_use_id": "a", "content": "ok"})
        )
        assert host.session_tool_activity(str(transcript)) is None  # result, no use

    def test_a_sibling_written_since_counts_and_older_or_nested_ones_do_not(
        self, tmp_path
    ):
        ours = tmp_path / "ours.jsonl"
        ours.write_text("")
        (tmp_path / "old.jsonl").write_text("")
        os.utime(tmp_path / "old.jsonl", (1000, 1000))
        (tmp_path / "ours").mkdir()
        (tmp_path / "ours" / "agent.jsonl").write_text("")  # a subagent's
        os.utime(ours, (5000, 5000))
        assert host.other_session_wrote_since(str(ours), 2000) is False
        (tmp_path / "theirs.jsonl").write_text("")
        os.utime(tmp_path / "theirs.jsonl", (3000, 3000))
        assert host.other_session_wrote_since(str(ours), 2000) is True
        # Within the slack of the start is the boundary, not a second session.
        assert host.other_session_wrote_since(
            str(ours), 3000 - host.ACTIVITY_SLACK_SECONDS
        ) is False

    def test_no_own_transcript_is_no_evidence(self, tmp_path):
        (tmp_path / "theirs.jsonl").write_text("")
        assert host.other_session_wrote_since(str(tmp_path / "ours.jsonl"), 0) is None

    def test_the_paths_this_sessions_edits_targeted_are_collected(self, tmp_path):
        """Edit, Write and MultiEdit name ``file_path``, NotebookEdit
        ``notebook_path``; a Read names a path it did not change."""
        transcript = tmp_path / "s.jsonl"
        transcript.write_text(
            _record("assistant", "2026-11-15T10:01:00Z",
                    {"type": "tool_use", "id": "a", "name": "Edit",
                     "input": {"file_path": "/r/a.py", "old_string": "", "new_string": ""}},
                    {"type": "tool_use", "id": "b", "name": "Write",
                     "input": {"file_path": "/r/b.py", "content": ""}},
                    {"type": "tool_use", "id": "c", "name": "MultiEdit",
                     "input": {"file_path": "/r/c.py", "edits": []}},
                    {"type": "tool_use", "id": "d", "name": "NotebookEdit",
                     "input": {"notebook_path": "/r/d.ipynb", "new_source": ""}},
                    {"type": "tool_use", "id": "e", "name": "Read",
                     "input": {"file_path": "/r/e.py"}},
                    {"type": "tool_use", "id": "f", "name": "Edit", "input": {"file_path": 7}})
        )
        activity = host.session_tool_activity(str(transcript))
        assert activity.edited_paths == frozenset(
            {"/r/a.py", "/r/b.py", "/r/c.py", "/r/d.ipynb"}
        )

    def test_a_bang_command_runs_from_its_input_to_its_output(self, tmp_path):
        """Claude Code's ``!`` mode records no tool call: a user message whose
        content is ``<bash-input>…`` when entered, and one starting
        ``<bash-stdout>`` when the command ended. The shape was read off this
        machine's transcripts (Claude Code 2.1.220)."""
        def user(when: str, content: str) -> str:
            return json.dumps({"type": "user", "timestamp": when,
                               "message": {"role": "user", "content": content}}) + "\n"

        transcript = tmp_path / "s.jsonl"
        transcript.write_text(
            _record("assistant", "2026-11-15T10:00:00Z",
                    {"type": "tool_use", "id": "a", "name": "Bash", "input": {}})
            + _record("user", "2026-11-15T10:00:01Z",
                      {"type": "tool_result", "tool_use_id": "a", "content": "ok"})
            + user("2026-11-15T10:05:00Z", "<bash-input>git commit -am x</bash-input>")
            + user("2026-11-15T10:05:30Z", "<bash-stdout>[main 1] x</bash-stdout><bash-stderr></bash-stderr>")
            + user("2026-11-15T10:09:00Z", "<bash-input>sleep 999</bash-input>")
        )
        activity = host.session_tool_activity(str(transcript))
        five = 1794736800 + 300  # 2026-11-15T10:05:00Z
        assert activity.acting_at(five + 15) is True
        assert activity.acting_at(five + 120) is False
        # No output yet: the command may still be running.
        assert activity.acting_at(five + 240 + 86400) is True

    def test_text_that_merely_mentions_bash_input_opens_nothing(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        transcript.write_text(
            _record("assistant", "2026-11-15T10:00:00Z",
                    {"type": "tool_use", "id": "a", "name": "Bash", "input": {}})
            + _record("user", "2026-11-15T10:00:01Z",
                      {"type": "tool_result", "tool_use_id": "a", "content": "ok"})
            + json.dumps({"type": "user", "timestamp": "2026-11-15T10:05:00Z",
                          "message": {"role": "user",
                                      "content": "what does <bash-input> mean?"}}) + "\n"
        )
        activity = host.session_tool_activity(str(transcript))
        assert activity.acting_at(1794736800 + 3600) is False


def _transcript_lines() -> list[str]:
    """A transcript exercising every reader branch, in order: a prompt, a call
    and its result, an edit, a background call, a ``!`` command and its output."""
    def user(when: str, content) -> str:
        return json.dumps({"type": "user", "timestamp": when,
                           "message": {"role": "user", "content": content}}) + "\n"

    return [
        user("2026-11-15T10:00:00Z", "hi"),
        _record("assistant", "2026-11-15T10:01:00Z",
                {"type": "tool_use", "id": "a", "name": "Bash", "input": {}}),
        _record("user", "2026-11-15T10:01:10Z",
                {"type": "tool_result", "tool_use_id": "a", "content": "ok"}),
        _record("assistant", "2026-11-15T10:02:00Z",
                {"type": "tool_use", "id": "b", "name": "Edit",
                 "input": {"file_path": "/r/a.py"}}),
        _record("user", "2026-11-15T10:02:01Z",
                {"type": "tool_result", "tool_use_id": "b", "content": "ok"}),
        _record("assistant", "2026-11-15T10:03:00Z",
                {"type": "tool_use", "id": "c", "name": "Agent",
                 "input": {"run_in_background": True}}),
        _record("user", "2026-11-15T10:03:01Z",
                {"type": "tool_result", "tool_use_id": "c", "content": "launched"}),
        user("2026-11-15T10:04:00Z", "<bash-input>git commit</bash-input>"),
        user("2026-11-15T10:04:05Z", "<bash-stdout>ok</bash-stdout>"),
        _record("assistant", "2026-11-15T10:05:00Z",
                {"type": "tool_use", "id": "d", "name": "Write",
                 "input": {"file_path": "/r/b.py"}}),
    ]


class TestTheTranscriptCache:
    """``session_tool_activity(path, cache_path)`` keeps what it parsed, keyed
    by the transcript's path, device, inode and byte offset, and parses only the
    bytes appended since. Whatever the cache, the answer must be the one a full
    read gives."""

    def test_any_split_gives_the_full_reads_answer(self, tmp_path):
        """Two Stops, the first seeing the transcript up to every byte offset,
        including mid-line (the host may be mid-append), agree with one read of
        the whole."""
        text = "".join(_transcript_lines())
        whole = tmp_path / "whole.jsonl"
        whole.write_text(text)
        expected = host.session_tool_activity(str(whole))
        assert expected is not None and expected.edited_paths
        data = text.encode()
        for cut in range(0, len(data) + 1, 7):
            transcript = tmp_path / "s.jsonl"
            cache = tmp_path / f"cache-{cut}.json"
            transcript.write_bytes(data[:cut])
            host.session_tool_activity(str(transcript), cache_path=str(cache))
            with transcript.open("ab") as fh:
                fh.write(data[cut:])
            got = host.session_tool_activity(str(transcript), cache_path=str(cache))
            assert got == expected, cut

    def test_a_replaced_or_rewritten_transcript_is_read_again(self, tmp_path):
        lines = _transcript_lines()
        transcript = tmp_path / "s.jsonl"
        cache = str(tmp_path / "cache.json")
        transcript.write_text("".join(lines))
        host.session_tool_activity(str(transcript), cache_path=cache)
        # Rewritten in place at the same length, the last record changed: the
        # cached scan no longer describes the file. (The host only appends; the
        # check reads the bytes before the offset, not the whole prefix.)
        rewritten = "".join(lines).replace('"/r/b.py"', '"/r/z.py"')
        assert len(rewritten) == len("".join(lines)) and rewritten != "".join(lines)
        transcript.write_text(rewritten)
        fresh = host.session_tool_activity(str(tmp_path / "s.jsonl"))
        assert host.session_tool_activity(str(transcript), cache_path=cache) == fresh
        # Replaced by a new, shorter file.
        transcript.unlink()
        transcript.write_text("".join(lines[:3]))
        fresh = host.session_tool_activity(str(transcript))
        assert host.session_tool_activity(str(transcript), cache_path=cache) == fresh

    def test_a_broken_line_stays_fatal_across_stops(self, tmp_path):
        """A broken line is forgiven only while it is the last; a line appended
        after it, at a later Stop, makes the transcript unreadable for good."""
        lines = _transcript_lines()
        transcript = tmp_path / "s.jsonl"
        cache = str(tmp_path / "cache.json")
        transcript.write_text("".join(lines[:3]) + '{"type": "assist\n')
        assert host.session_tool_activity(str(transcript), cache_path=cache) is not None
        with transcript.open("a") as fh:
            fh.write(lines[3])
        assert host.session_tool_activity(str(transcript), cache_path=cache) is None
        # Nothing appended: the cached verdict alone must still say so.
        assert host.session_tool_activity(str(transcript), cache_path=cache) is None
        with transcript.open("a") as fh:
            fh.write(lines[4])
        assert host.session_tool_activity(str(transcript), cache_path=cache) is None

    def test_a_garbage_cache_is_ignored(self, tmp_path):
        transcript = tmp_path / "s.jsonl"
        transcript.write_text("".join(_transcript_lines()))
        expected = host.session_tool_activity(str(transcript))
        cache = tmp_path / "cache.json"
        for garbage in ("not json", "[]", '{"transcripts": 3}',
                        json.dumps({"transcripts": {str(transcript): {"offset": "x"}}})):
            cache.write_text(garbage)
            assert host.session_tool_activity(str(transcript), cache_path=str(cache)) == expected

    def test_the_cache_holds_a_bounded_number_of_transcripts(self, tmp_path):
        cache = str(tmp_path / "cache.json")
        for n in range(host.ACTIVITY_CACHE_TRANSCRIPTS + 3):
            transcript = tmp_path / f"s{n}.jsonl"
            transcript.write_text("".join(_transcript_lines()))
            host.session_tool_activity(str(transcript), cache_path=cache)
        kept = json.loads(Path(cache).read_text())["transcripts"]
        assert len(kept) == host.ACTIVITY_CACHE_TRANSCRIPTS
        assert str(tmp_path / f"s{host.ACTIVITY_CACHE_TRANSCRIPTS + 2}.jsonl") in kept
        assert str(tmp_path / "s0.jsonl") not in kept


class TestGatesReadTheEvent:
    """The gates take a `HostEvent`; what they decide from it is unchanged."""

    def test_in_flight_tasks_defer(self):
        event = host.read_event("stop", {"background_tasks": [{"type": "workflow", "name": "w"}]})
        assert gates.background_tasks_in_flight(event) == (True, ["workflow:w"])

    def test_no_usable_tasks_do_not_defer(self):
        for raw in ({}, {"background_tasks": []}, {"background_tasks": ["x"]}):
            assert gates.background_tasks_in_flight(host.read_event("stop", raw)) == (False, [])


def _load_hook_script(name: str):
    path = PLUGIN / "hooks" / name
    spec = importlib.util.spec_from_file_location(f"seam_test_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRoots:
    def test_plugin_root_prefers_the_variable(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/somewhere")
        assert host.plugin_root() == "/somewhere"

    def test_plugin_root_falls_back_to_the_tree_holding_the_seam(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        assert Path(host.plugin_root()) == PLUGIN.resolve()

    def test_project_dir_hint_is_none_when_unset_or_empty(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        assert host.project_dir_hint() is None
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", "")
        assert host.project_dir_hint() is None
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/launch")
        assert host.project_dir_hint() == "/launch"

    def test_config_home(self, tmp_path):
        assert host.config_home(env={}, home=tmp_path) == tmp_path / ".claude"
        assert host.config_home(env={"CLAUDE_CONFIG_DIR": str(tmp_path / "c")}) == tmp_path / "c"

    def test_a_configured_home_expands_tilde_for_every_reader(self, tmp_path, monkeypatch):
        """All three config readers ask `host.config_home`, so a `~` in the
        variable means the user's home for each — the banner's managed-install
        check included, which used to take it literally."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "~/cfg")
        assert host.config_home() == tmp_path / "cfg"
        banner = _load_hook_script("banner.py")
        assert banner.managed_plugin_home() == tmp_path / "cfg" / "plugins"
        from lib import plugin_activation

        assert plugin_activation.default_plugins_file() == (
            tmp_path / "cfg" / "plugins" / "installed_plugins.json"
        )

    def test_config_roots_lists_candidates_most_specific_first(self, tmp_path):
        (tmp_path / ".claude-work").mkdir()
        (tmp_path / ".claude-alt").mkdir()
        roots = host.config_roots(env={"CLAUDE_CONFIG_DIR": "/cfg"}, home=tmp_path)
        assert roots == [
            Path("/cfg"), tmp_path / ".claude", tmp_path / ".claude-alt", tmp_path / ".claude-work",
        ]


class TestResponses:
    def test_session_context(self, capsys):
        host.emit_session_context("ctx")
        assert json.loads(capsys.readouterr().out) == {
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "ctx"}
        }
        host.emit_session_context("ctx", reload_skills=True)
        assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["reloadSkills"] is True

    def test_stop_advisory(self, capsys):
        host.emit_stop_advisory("note")
        assert json.loads(capsys.readouterr().out) == {"systemMessage": "note"}

    def test_block_writes_the_reason_as_given_and_returns_the_blocking_exit(self, capsys):
        assert host.block("why\n") == 2
        captured = capsys.readouterr()
        assert captured.err == "why\n" and captured.out == ""


# --- an unknown host fails closed ---------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, check=True, timeout=30,
    )


def _governed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    (repo / ".prawduct").mkdir()
    return repo


def _run(argv: list[str], repo: Path, tmp_path: Path, host_value: str | None, stdin: str = "{}"):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "PYTHONDONTWRITEBYTECODE": "1",
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
        "CLAUDE_PROJECT_DIR": str(repo),
    }
    if host_value is not None:
        env["PRAWDUCT_HOST"] = host_value
    return subprocess.run(
        [sys.executable, *argv], input=stdin, capture_output=True, text=True,
        env=env, cwd=str(repo), timeout=120,
    )


class TestUnknownHost:
    def test_stop_blocks_naming_the_variable(self, tmp_path):
        repo = _governed_repo(tmp_path)
        result = _run([str(HOOK), "stop"], repo, tmp_path, "bogus")
        assert result.returncode == 2
        assert "PRAWDUCT_HOST='bogus'" in result.stderr

    def test_the_unknown_host_block_says_how_to_answer_it(self, tmp_path):
        """It is a Stop block like any gate's, so it opens the same way (#1095)."""
        from test_stop_verdict_defer import assert_block_says_how_to_answer

        repo = _governed_repo(tmp_path)
        result = _run([str(HOOK), "stop"], repo, tmp_path, "bogus")
        assert result.returncode == 2
        assert_block_says_how_to_answer(result.stderr)

    def test_the_unknown_host_block_is_recorded_as_a_gate_block(self, tmp_path):
        """Like every Stop block, it leaves one countable fact, under its own
        gate id, so a misconfigured adapter is a query and not a transcript."""
        from lib import evidence

        repo = _governed_repo(tmp_path)
        result = _run([str(HOOK), "stop"], repo, tmp_path, "bogus")
        assert result.returncode == 2
        # The stamp gains "· NEW this release (vX)" while the running version is the
        # gate's `since`, so it must match before and after the release that ships it.
        assert re.search(r"\[prawduct v[^\]\n]* · gate: unknown-host(?: · NEW this release \(v[^)]+\))?\]", result.stderr)
        facts = evidence.facts_of_kind(evidence.read_facts(repo), "guard-refusal")
        assert [f["body"].get("guard") for f in facts] == ["stop-gate:host"]

    def test_stop_control_runs_the_gates_as_claude(self, tmp_path):
        """Control: the same clean repo passes the Stop gate as Claude, named
        in any case or by default, so the block above is the host check and
        nothing else."""
        repo = _governed_repo(tmp_path)
        for value in (None, "", "claude", "Claude", " CLAUDE "):
            result = _run([str(HOOK), "stop"], repo, tmp_path, value)
            assert result.returncode == 0, result.stderr
            assert "PRAWDUCT_HOST" not in result.stderr

    def test_stop_outside_a_governed_repo_stays_silent(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        result = _run([str(HOOK), "stop"], plain, tmp_path, "bogus")
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

    @pytest.mark.parametrize(
        "argv",
        [
            ["clear", "--session-start"],
            ["clear", "--session-start", "--brief-only"],
            ["subagent-stop"],
        ],
    )
    def test_hooks_that_cannot_block_note_it_and_do_nothing(self, tmp_path, argv):
        repo = _governed_repo(tmp_path)
        before = sorted(p.name for p in (repo / ".prawduct").iterdir())
        result = _run([str(HOOK), *argv], repo, tmp_path, "bogus")
        assert result.returncode == 0
        assert result.stdout == ""
        assert "PRAWDUCT_HOST='bogus'" in result.stderr
        assert sorted(p.name for p in (repo / ".prawduct").iterdir()) == before

    def test_session_start_control_writes_state_as_claude(self, tmp_path):
        repo = _governed_repo(tmp_path)
        result = _run([str(HOOK), "clear", "--session-start"], repo, tmp_path, None)
        assert result.returncode == 0
        assert any((repo / ".prawduct").iterdir())

    def test_digest_outside_a_governed_repo_stays_silent(self, tmp_path):
        """The digest speaks only in a governed repo, so an unknown host has
        nothing to refuse there either."""
        plain = tmp_path / "plain"
        plain.mkdir()
        result = _run([str(PLUGIN / "hooks" / "digest.py")], plain, tmp_path, "bogus")
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

    def test_digest_names_an_unresolvable_project_dir_as_that(self, tmp_path):
        """With no project variable and a deleted working directory, the
        digest says the project directory could not be located — not that its
        host seam failed to load, which would send the reader the wrong way."""
        gone = tmp_path / "gone"
        gone.mkdir()
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path),
               "PYTHONDONTWRITEBYTECODE": "1"}
        script = (
            f'cd "{gone}" && rmdir "{gone}" && '
            f'exec "{sys.executable}" "{PLUGIN / "hooks" / "digest.py"}"'
        )
        result = subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True,
                                env=env, cwd=str(tmp_path), timeout=60)
        assert result.returncode == 0
        assert result.stdout == ""
        assert "could not locate the project directory" in result.stderr
        assert "host seam" not in result.stderr

    @pytest.mark.parametrize("script", ["banner.py", "digest.py"])
    def test_session_start_scripts_note_it_and_print_nothing(self, tmp_path, script):
        repo = _governed_repo(tmp_path)
        result = _run([str(PLUGIN / "hooks" / script)], repo, tmp_path, "bogus")
        assert result.returncode == 0
        assert result.stdout == ""
        assert "PRAWDUCT_HOST='bogus'" in result.stderr


class TestSeamLoaders:
    """Each entry point loads the seam by file path. A seam that fails to load
    must fail every time, never leave a half-built module for the next caller."""

    @pytest.mark.parametrize("script", ["bin/prawduct-hook", "hooks/banner.py", "hooks/digest.py"])
    def test_a_failed_load_is_not_cached(self, tmp_path, monkeypatch, script):
        tree = tmp_path / "plugin"
        copy = tree / script
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_text((PLUGIN / script).read_text(encoding="utf-8"), encoding="utf-8")
        # The tree carries this checkout's shared loader and a seam that raises
        # on load; evicting a cached loader makes this tree's loader answer.
        copy_seam_files(tree)
        (tree / "lib" / "host.py").write_text("raise RuntimeError('broken seam')\n")
        monkeypatch.delitem(sys.modules, "_host_seam", raising=False)
        monkeypatch.delitem(sys.modules, "prawduct_host", raising=False)
        loader = importlib.machinery.SourceFileLoader(f"loader_{copy.stem}", str(copy))
        spec = importlib.util.spec_from_loader(f"loader_{copy.stem}", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        for _ in range(2):
            with pytest.raises(RuntimeError, match="broken seam"):
                module._host()
            assert "prawduct_host" not in sys.modules
