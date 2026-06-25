"""Unit coverage for the STH-3W7F deferral decision — ``gates.background_tasks_in_flight``.

The Stop hook reads Claude Code's ``background_tasks`` array (v2.1.145+) and
defers the session-end blockers while harness-tracked work is in flight, rather
than blocking on a diff that isn't final and a session that can't end. This
module pins the *decision* in isolation (the end-to-end gate behavior lives in
``test_plugin_runtime.py::TestPluginStopGateBackgroundDefer``).

The load-bearing invariant is the degradation ladder: the permissive direction
(defer = suppress the block) is taken ONLY on a clearly-present, non-empty list;
every other case — absent, empty, or malformed — must fall to the blocking
default (``in_flight=False``). A regression that defers on garbage would silently
disable the Critic gate, so each malformed shape is pinned explicitly.
"""
from __future__ import annotations

from lib import gates


class TestNoDeferral:
    """All the ways the helper must NOT defer (gate keeps blocking)."""

    def test_absent_key_does_not_defer(self):
        # Field absent (older client, registry unreachable, empty stdin parsed to {}).
        in_flight, labels = gates.background_tasks_in_flight({})
        assert in_flight is False
        assert labels == []

    def test_empty_list_does_not_defer(self):
        # Present but empty = genuinely idle.
        in_flight, labels = gates.background_tasks_in_flight({"background_tasks": []})
        assert in_flight is False
        assert labels == []

    def test_other_keys_present_but_no_tasks(self):
        # A real Stop payload with session_crons but no live tasks.
        payload = {"session_id": "abc", "session_crons": [{"id": "c1"}], "background_tasks": []}
        assert gates.background_tasks_in_flight(payload) == (False, [])


class TestMalformedFailsClosed:
    """Malformed shapes must fail CLOSED — never defer on garbage."""

    def test_non_dict_input(self):
        assert gates.background_tasks_in_flight(None) == (False, [])
        assert gates.background_tasks_in_flight("nope") == (False, [])
        assert gates.background_tasks_in_flight([1, 2, 3]) == (False, [])

    def test_background_tasks_not_a_list(self):
        assert gates.background_tasks_in_flight({"background_tasks": "running"}) == (False, [])
        assert gates.background_tasks_in_flight({"background_tasks": {"id": "x"}}) == (False, [])

    def test_list_with_no_usable_entries(self):
        # Entries that aren't dicts contribute no labels -> no defer.
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": ["x", 1, None]}
        )
        assert in_flight is False
        assert labels == []


class TestDefersOnLiveWork:
    """A clearly-present, non-empty list defers and labels each task."""

    def test_single_workflow_defers(self):
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": [{"id": "wf-1", "type": "workflow", "name": "build-pipeline"}]}
        )
        assert in_flight is True
        assert labels == ["workflow:build-pipeline"]

    def test_subagent_uses_agent_type(self):
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": [{"id": "t-1", "type": "subagent", "agent_type": "Explore"}]}
        )
        assert in_flight is True
        assert labels == ["subagent:Explore"]

    def test_shell_uses_command_then_falls_back_to_id(self):
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": [
                {"id": "sh-1", "type": "shell", "command": "npm test"},
                {"id": "sh-2", "type": "shell"},
            ]}
        )
        assert in_flight is True
        assert labels == ["shell:npm test", "shell:sh-2"]

    def test_missing_type_falls_back_to_task(self):
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": [{"id": "x-1"}]}
        )
        assert in_flight is True
        assert labels == ["task:x-1"]

    def test_label_is_truncated(self):
        long = "z" * 200
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": [{"type": "shell", "command": long}]}
        )
        assert in_flight is True
        assert len(labels[0]) <= 80

    def test_mixed_valid_and_invalid_entries_defers_on_valid(self):
        # One malformed entry among valid ones still defers (the valid one is live).
        in_flight, labels = gates.background_tasks_in_flight(
            {"background_tasks": ["junk", {"type": "workflow", "name": "real"}]}
        )
        assert in_flight is True
        assert labels == ["workflow:real"]
