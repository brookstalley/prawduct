"""SCN-4H9T ch.1 — the forward channel and the non-destructive handoff generator.

`.session-handoff.md` had exactly one writer (the machine, at `/clear`) and no
reader-facing way for an agent to leave *forward*-looking context: every source
feeding it is backward-looking machine state. Agents therefore wrote the handoff
file itself, and `/clear` overwrote it — guarded only by `if len(sections) > 2`,
which preserved a hand-authored handoff precisely when the machine had nothing
to say, i.e. when it mattered least. Intermittent loss, therefore unlearnable.

Two independent mechanisms, tested independently because they fail differently:

  * **The channel** — `.prawduct/.handoff-notes.md` is model-owned; the generator
    consumes it into the handoff, above every machine section, and `/clear`
    clears it only once the write succeeded.
  * **The preservation net** — every generated handoff carries a machine marker.
    A `.session-handoff.md` *without* it was hand-authored, so its body is folded
    into the new handoff instead of being dropped. The marker is what keeps this
    from compounding: a generated handoff is never re-preserved into the next.

Layers: unit against `lib/briefing` for assembly, behavioral through the real
`clear` CLI for consumption/archival (where the ordering bug actually lived).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import briefing, core  # noqa: E402

from test_plugin_runtime import run_plugin_hook  # noqa: E402


def _prawduct(tmp_path: Path) -> Path:
    p = tmp_path / ".prawduct"
    (p / "artifacts").mkdir(parents=True)
    (p / "project-state.yaml").write_text("backlog_format_version: 2\n")
    return p


def _quiet_git(monkeypatch) -> None:
    """Silence the git-backed handoff sources so assembly is the only variable."""
    monkeypatch.setattr(briefing.gitstate, "_get_session_changed_files", lambda d: [])
    monkeypatch.setattr(briefing, "_git_session_commits", lambda d: [])
    monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})


# =============================================================================
# The channel — notes reach the next session, first
# =============================================================================
class TestForwardChannel:
    def test_notes_appear_in_handoff(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_text(
            "Blocked on the schema decision — do NOT start chunk 3 before it lands."
        )

        assert briefing.generate_session_handoff(tmp_path).written is True
        text = (pr / ".session-handoff.md").read_text()
        assert "## Notes For The Next Session" in text
        assert "do NOT start chunk 3" in text

    def test_notes_precede_every_machine_section(self, tmp_path, monkeypatch):
        # The ordering is the point: intent for the next session outranks the
        # record of the last one, and a reader who stops early must hit it first.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_text("forward intent")
        (pr / ".session-reflected").write_text("backward reflection about the session")
        (pr / "project-state.yaml").write_text(
            "work_in_progress:\n  description: ship it\n"
        )

        briefing.generate_session_handoff(tmp_path)
        text = (pr / ".session-handoff.md").read_text()
        assert text.index("## Notes For The Next Session") < text.index("## Work In Progress")
        assert text.index("## Notes For The Next Session") < text.index(
            "## Previous Session Reflection"
        )

    def test_empty_notes_file_contributes_nothing(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_text("   \n\n")

        assert briefing.generate_session_handoff(tmp_path).written is False
        assert not (pr / ".session-handoff.md").exists()

    def test_useful_handoff_without_notes(self, tmp_path, monkeypatch):
        # The no-warning `/clear`: the user never asked for a handoff and the
        # agent never wrote one, and continuity must still work.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".session-reflected").write_text("what happened this session")

        assert briefing.generate_session_handoff(tmp_path).written is True
        text = (pr / ".session-handoff.md").read_text()
        assert "## Previous Session Reflection" in text
        assert "## Notes For The Next Session" not in text


# =============================================================================
# The preservation net — a hand-authored handoff survives
# =============================================================================
class TestPreservationNet:
    def test_unmarked_handoff_is_preserved(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".session-handoff.md").write_text(
            "# Session Handoff\n\nHand-written: the migration is half-applied.\n"
        )
        (pr / ".session-reflected").write_text("machine has plenty to say this time")

        assert briefing.generate_session_handoff(tmp_path).written is True
        text = (pr / ".session-handoff.md").read_text()
        assert "## Preserved: Hand-Authored Handoff" in text
        assert "the migration is half-applied" in text
        # The regression: it used to survive ONLY when the machine had nothing.
        assert "## Previous Session Reflection" in text

    def test_preserved_body_drops_duplicate_h1(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".session-handoff.md").write_text("# Session Handoff\n\nbody text\n")

        briefing.generate_session_handoff(tmp_path)
        text = (pr / ".session-handoff.md").read_text()
        assert text.count("# Session Handoff") == 1
        assert "body text" in text

    def test_generated_handoff_is_not_re_preserved(self, tmp_path, monkeypatch):
        # Without the marker this compounds: every /clear would nest the previous
        # handoff inside the new one, unbounded.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".session-reflected").write_text("round one reflection")

        briefing.generate_session_handoff(tmp_path)
        first = (pr / ".session-handoff.md").read_text()
        assert briefing.HANDOFF_MARKER_PREFIX in first

        (pr / ".session-reflected").write_text("round two reflection")
        briefing.generate_session_handoff(tmp_path)
        second = (pr / ".session-handoff.md").read_text()
        assert "## Preserved: Hand-Authored Handoff" not in second
        assert "round one reflection" not in second
        assert "round two reflection" in second

    def test_marker_names_the_notes_file(self, tmp_path, monkeypatch):
        # The marker is read by an agent that opened the wrong file — it has to
        # say where forward notes actually go, or it just labels the mistake.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".session-reflected").write_text("something to say")

        briefing.generate_session_handoff(tmp_path)
        assert ".handoff-notes.md" in (pr / ".session-handoff.md").read_text()

    def test_lone_unmarked_handoff_still_written(self, tmp_path, monkeypatch):
        # Machine has nothing; the rescued body is the only content. It must
        # still be written back, not silently left as the "no content" no-op.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".session-handoff.md").write_text("only hand-written context here\n")

        assert briefing.generate_session_handoff(tmp_path).written is True
        text = (pr / ".session-handoff.md").read_text()
        assert "only hand-written context here" in text
        assert briefing.HANDOFF_MARKER_PREFIX in text


# =============================================================================
# Consumption — transactional, through the real CLI
# =============================================================================
class TestNotesConsumption:
    def test_clear_consumes_notes_into_handoff(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".handoff-notes.md").write_text("carry this forward to the next session")

        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr

        assert "carry this forward" in (pr / ".session-handoff.md").read_text()
        assert not (pr / ".handoff-notes.md").exists(), "consumed notes must not resurface"

    def test_notes_survive_a_failed_handoff_write(self, tmp_path, monkeypatch):
        # Consumption is gated on delivery, not on the attempt: a note deleted
        # after a failed generation is the exact loss this channel prevents.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_text("must not be lost")

        def _boom(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr(briefing, "atomic_write_text", _boom)
        result = briefing.generate_session_handoff(tmp_path)
        assert result.written is False
        assert result.notes_state == briefing.NOTES_UNDELIVERED
        assert result.notes_consumed is False
        assert (pr / ".handoff-notes.md").is_file()

    def test_failed_write_is_reported_not_silent(self, tmp_path, monkeypatch, capsys):
        # Fails soft, never silent — an agent that saw /clear succeed and said
        # "safe to clear" is wrong, and this is the only layer that knows.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_text("must not be lost")
        monkeypatch.setattr(briefing, "atomic_write_text", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))

        briefing.generate_session_handoff(tmp_path)
        err = capsys.readouterr().err
        assert "could not write .session-handoff.md" in err
        assert ".handoff-notes.md is kept" in err

    def test_unreadable_notes_are_never_consumed(self, tmp_path, monkeypatch):
        # The narrow, worse failure: an undecodable notes file reads as "" —
        # indistinguishable from "no notes" if the states are collapsed — so a
        # handoff written from ANY other section used to delete it, destroying
        # text that reached nothing. Unrecoverable, unlike a failed write.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_bytes(b"\xff\xfe not utf-8 \x00")
        (pr / ".session-reflected").write_text("some other section has content")

        result = briefing.generate_session_handoff(tmp_path)
        assert result.written is True, "other sections still produce a handoff"
        assert result.notes_state == briefing.NOTES_UNREADABLE
        assert result.notes_consumed is False

    def test_clear_keeps_and_reports_unreadable_notes(self, tmp_path):
        pr = _prawduct(tmp_path)
        (pr / ".handoff-notes.md").write_bytes(b"\xff\xfe not utf-8 \x00")

        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        assert (pr / ".handoff-notes.md").is_file(), "undelivered notes must not be destroyed"
        # stdout, not stderr: SessionStart shows stdout to the model, and the
        # incoming agent — whose predecessor's note just went missing — is the
        # audience. stderr would tell only the operator watching the terminal.
        assert "could not be read" in result.stdout
        assert "remove or rewrite it" in result.stdout, "a notice that re-fires needs a remedy"

    def test_empty_notes_are_consumed(self, tmp_path, monkeypatch):
        # An empty file has nothing to lose, so it is cleared like a delivered
        # one — otherwise it lingers forever, reported as a failure every run.
        pr = _prawduct(tmp_path)
        _quiet_git(monkeypatch)
        (pr / ".handoff-notes.md").write_text("\n  \n")
        (pr / ".session-reflected").write_text("machine has something to say")

        result = briefing.generate_session_handoff(tmp_path)
        assert result.notes_state == briefing.NOTES_EMPTY
        assert result.notes_consumed is True

    def test_handoff_failure_never_blocks_clear(self, tmp_path):
        # The whole feature is advisory. A corrupt notes file must degrade to a
        # missing section, never to a session that cannot start.
        pr = _prawduct(tmp_path)
        (pr / ".handoff-notes.md").write_bytes(b"\xff\xfe not utf-8 \x00")

        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        assert (pr / ".session-start").is_file()

    def test_clear_preserves_a_hand_authored_handoff(self, tmp_path):
        # Done-when #2 through the real CLI, not just the generator: the whole
        # defect was that `/clear` — not `generate_session_handoff` in isolation —
        # destroyed the file.
        pr = _prawduct(tmp_path)
        (pr / ".session-handoff.md").write_text(
            "# Session Handoff\n\nHand-written: the migration is half-applied.\n"
        )

        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        text = (pr / ".session-handoff.md").read_text()
        assert "the migration is half-applied" in text
        assert briefing.HANDOFF_MARKER_PREFIX in text

    def test_generation_failure_is_reported_and_keeps_notes(self, tmp_path, monkeypatch, capsys):
        # The OUTER half of "fails soft was never fails silent": cmd_clear's
        # catch-all covers what the write guard cannot — an incomplete install,
        # or a raise from any section builder before the write is reached. The
        # notes must survive that too, or a broken install silently eats them.
        from test_briefing_extraction import _load_hook  # noqa: PLC0415

        pr = _prawduct(tmp_path)
        (pr / ".handoff-notes.md").write_text("must outlive a broken install")
        hook = _load_hook()

        def _boom():
            raise ImportError("simulated incomplete install: lib.briefing unavailable")

        monkeypatch.setattr(hook, "_briefing", _boom)

        assert hook.cmd_clear(tmp_path) == 0, "a broken install must never block session start"
        assert "could not generate the session handoff" in capsys.readouterr().err
        assert (pr / ".handoff-notes.md").is_file()

    def test_undelivered_note_is_announced_to_the_next_agent(self, tmp_path, monkeypatch, capsys):
        # The likelier trigger for "your predecessor's note did not arrive": the
        # write failed, so `generate_session_handoff` RETURNS undelivered rather
        # than raising. Data preservation on that path is pinned above; this
        # pins the announcement, which is the half the agent actually sees.
        from test_briefing_extraction import _load_hook  # noqa: PLC0415

        pr = _prawduct(tmp_path)
        (pr / ".handoff-notes.md").write_text("the predecessor's note")
        hook = _load_hook()
        monkeypatch.setattr(
            briefing,
            "atomic_write_text",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")),
        )

        assert hook.cmd_clear(tmp_path) == 0
        captured = capsys.readouterr()
        assert "could not be written into this handoff" in captured.out
        assert (pr / ".handoff-notes.md").is_file(), "an undelivered note must survive"

    def test_no_notes_is_not_an_error(self, tmp_path):
        pr = _prawduct(tmp_path)
        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        assert not (pr / ".handoff-notes.md").exists()


# =============================================================================
# Session-file registration
# =============================================================================
class TestSessionFileRegistration:
    def test_notes_file_is_gitignored(self):
        assert ".prawduct/.handoff-notes.md" in core.GITIGNORE_ENTRIES

    # The hook's own `_SESSION_GITIGNORED_PATHS` (the untrack set) is held in
    # sync with GITIGNORE_ENTRIES by the parity test in
    # test_build_plan_resolution.py — asserting it again here would pin source
    # text rather than behavior, and would pass for a list that had drifted.

    def test_this_repo_ignores_it(self):
        gitignore = (_ROOT.parent / ".gitignore").read_text()
        assert ".prawduct/.handoff-notes.md" in gitignore
