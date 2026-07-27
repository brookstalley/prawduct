"""The handoff affordance: can each party see the right file, and its real state?

Chunk 01 built the forward channel; agents still reached for `.session-handoff.md`
because that is the file the guides named. Three surfaces close that gap, and this
module pins all three — the two runtime ones behaviorally, the prose one
structurally.

Continuity was lost *silently while the agent reported success*, and neither party
to the session boundary could see it:

  * **The incoming agent** received a handoff full of machine sections and no
    way to tell "the previous agent left you their intent" from "the previous
    agent left nothing and this is only a log". So when work happened and the
    forward channel went unused, the handoff now says so, in the position the
    note would have occupied. Advisory by construction — it adds a section, it
    never blocks anything.
  * **The outgoing agent** could only see what the next session would receive by
    causing it: `/clear` both renders the handoff and destroys what it replaces.
    `prawduct-hook handoff preview` renders through the same function and stops,
    so checking is no longer the same act as committing.

  * **The guides** named `.session-handoff.md` and nothing else, so the file the
    agent must not touch was the only one they had a name for. The prose pin
    below is structural rather than a verb list, for the reason the branch has
    already learned twice: a detector keyed on a convention drifts with the
    convention.

The discriminations the runtime halves rest on are the ones a collapsed reader
loses: "no note was left" is not "a note was left and could not be read", and
"rendered" is not "written".
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import briefing  # noqa: E402

from test_plugin_runtime import run_plugin_hook  # noqa: E402

SIGNAL_HEADING = "## No Forward Note From The Previous Session"


def _prawduct(tmp_path: Path) -> Path:
    p = tmp_path / ".prawduct"
    (p / "artifacts").mkdir(parents=True)
    (p / "project-state.yaml").write_text("backlog_format_version: 2\n")
    return p


def _session_did_work(monkeypatch, *, files: int = 3, commits: int = 2) -> None:
    """A session with a diff behind it, and no build plan to distract the parse."""
    monkeypatch.setattr(
        briefing.gitstate,
        "_get_session_changed_files",
        lambda d: [f"src/mod_{i}.py" for i in range(files)],
    )
    monkeypatch.setattr(
        briefing,
        "_git_session_commits",
        lambda d: [f"abc{i:03d} did a thing" for i in range(commits)],
    )
    monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})


def _session_did_nothing(monkeypatch) -> None:
    monkeypatch.setattr(briefing.gitstate, "_get_session_changed_files", lambda d: [])
    monkeypatch.setattr(briefing, "_git_session_commits", lambda d: [])
    monkeypatch.setattr(briefing.buildplan_refs, "_parse_build_plan_status", lambda d: {})


# =============================================================================
# The soft signal — the handoff states that its forward half is missing
# =============================================================================
class TestNoForwardNoteSignal:
    def test_fires_when_work_happened_and_no_note_was_left(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)

        assert briefing.generate_session_handoff(tmp_path).written is True
        text = (pr / ".session-handoff.md").read_text()
        assert SIGNAL_HEADING in text
        # It must name the file the reader's successor should write, or it
        # diagnoses without pointing at the remedy.
        assert ".handoff-notes.md" in text.split(SIGNAL_HEADING)[1]

    def test_names_what_the_session_did(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch, files=3, commits=2)

        briefing.generate_session_handoff(tmp_path)
        body = (pr / ".session-handoff.md").read_text().split(SIGNAL_HEADING)[1]
        assert "3 files changed" in body
        assert "2 commits" in body

    def test_counts_of_one_are_singular(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch, files=1, commits=1)

        briefing.generate_session_handoff(tmp_path)
        body = (pr / ".session-handoff.md").read_text().split(SIGNAL_HEADING)[1]
        assert "1 file changed" in body
        assert "1 commit " in body or "1 commit)" in body
        assert "1 files" not in body and "1 commits" not in body

    def test_silent_when_the_session_produced_no_diff(self, tmp_path, monkeypatch):
        # A known limit, not a claim that nothing happened: a design session has
        # plenty to hand off and no diff. But its handoff is visibly thin, so it
        # cannot pass for a complete account the way a commit list can — and a
        # notice on every read-only session teaches the reader to skip it.
        pr = _prawduct(tmp_path)
        _session_did_nothing(monkeypatch)
        (pr / ".session-reflected").write_text("read some code, changed nothing")

        assert briefing.generate_session_handoff(tmp_path).written is True
        assert SIGNAL_HEADING not in (pr / ".session-handoff.md").read_text()

    def test_silent_when_notes_were_written(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".handoff-notes.md").write_text("the schema decision is still open")

        briefing.generate_session_handoff(tmp_path)
        assert SIGNAL_HEADING not in (pr / ".session-handoff.md").read_text()

    def test_silent_when_a_hand_authored_handoff_was_rescued(self, tmp_path, monkeypatch):
        # The agent used the wrong file, not no file. The preservation net
        # carried their forward context in, so accusing them of leaving none
        # would contradict the section printed directly above.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".session-handoff.md").write_text("# Session Handoff\n\nPick up at the parser.\n")

        briefing.generate_session_handoff(tmp_path)
        text = (pr / ".session-handoff.md").read_text()
        assert "## Preserved: Hand-Authored Handoff" in text
        assert SIGNAL_HEADING not in text

    def test_silent_when_notes_exist_but_could_not_be_read(self, tmp_path, monkeypatch):
        # The discrimination the whole signal rests on. A note WAS left; the
        # machine could not read it. Saying "you left no note" blames the agent
        # for the machine's failure — and that state already has its own notice
        # at the consumption site, which this must not contradict.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".handoff-notes.md").write_bytes(b"\xff\xfe not utf-8 \xff")

        result = briefing.generate_session_handoff(tmp_path)
        assert result.notes_state == briefing.NOTES_UNREADABLE
        assert SIGNAL_HEADING not in (pr / ".session-handoff.md").read_text()

    def test_precedes_every_machine_section(self, tmp_path, monkeypatch):
        # It is a caveat over everything below it, so a reader who stops early
        # must still have been told what they are reading.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".session-reflected").write_text("what happened")

        briefing.generate_session_handoff(tmp_path)
        text = (pr / ".session-handoff.md").read_text()
        assert text.index(SIGNAL_HEADING) < text.index("## Previous Session Reflection")
        assert text.index(SIGNAL_HEADING) < text.index("## Files Changed This Session")

    def test_never_blocks_or_replaces_the_rest_of_the_handoff(self, tmp_path, monkeypatch):
        # Advice fails soft: the signal is additive. The machine sections that
        # would have been produced anyway are all still there.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".session-reflected").write_text("what happened")

        assert briefing.generate_session_handoff(tmp_path).written is True
        text = (pr / ".session-handoff.md").read_text()
        for heading in (
            "## Previous Session Reflection",
            "## Files Changed This Session",
            "## Commits This Session",
        ):
            assert heading in text


# =============================================================================
# `handoff preview` — see it without causing it
# =============================================================================
class TestHandoffPreviewIsReadOnly:
    def _snapshot(self, root: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    def test_preview_writes_nothing(self, tmp_path, monkeypatch):
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".handoff-notes.md").write_text("do not lose me")
        before = self._snapshot(pr)

        assert briefing.handoff_cmd(tmp_path, ["preview"]) == 0
        assert self._snapshot(pr) == before
        assert not (pr / ".session-handoff.md").exists()

    def test_preview_does_not_consume_the_notes(self, tmp_path, monkeypatch):
        # Consumption is the destructive half of `/clear`. A preview that ate
        # the notes would destroy exactly what it was asked to display.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".handoff-notes.md").write_text("still needed next session")

        briefing.handoff_cmd(tmp_path, ["preview"])
        assert (pr / ".handoff-notes.md").read_text() == "still needed next session"

    def test_preview_matches_what_clear_would_write(self, tmp_path, monkeypatch, capsys):
        # The contract that makes a preview worth anything: same renderer, so
        # the preview IS the artifact rather than a description of it.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".handoff-notes.md").write_text("carry this forward")
        (pr / ".session-reflected").write_text("what happened")

        assert briefing.handoff_cmd(tmp_path, ["preview"]) == 0
        previewed = capsys.readouterr().out

        assert briefing.generate_session_handoff(tmp_path).written is True
        assert previewed == (pr / ".session-handoff.md").read_text()

    def test_diagnostics_never_land_on_stdout(self, tmp_path, monkeypatch, capsys):
        # stdout is the content channel so the preview can be piped; a NOTE
        # mixed into it would be indistinguishable from handoff text.
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        (pr / ".handoff-notes.md").write_bytes(b"\xff\xfe not utf-8 \xff")

        assert briefing.handoff_cmd(tmp_path, ["preview"]) == 0
        captured = capsys.readouterr()
        assert "NOTE:" not in captured.out
        assert ".handoff-notes.md" in captured.err
        assert captured.out.startswith("# Session Handoff")

    def test_an_unexpected_render_failure_is_attributed_not_raised(
        self, tmp_path, monkeypatch, capsys
    ):
        # The CLI error model forbids a stack trace crossing the boundary. Every
        # reader on the render path degrades internally, so this guard is for
        # what nobody anticipated — and a crashing *preview* must not read as
        # evidence that `/clear` itself is broken.
        _prawduct(tmp_path)

        def _boom(_):
            raise RuntimeError("something nobody anticipated")

        monkeypatch.setattr(briefing, "render_session_handoff", _boom)

        assert briefing.handoff_cmd(tmp_path, ["preview"]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "could not render the preview" in captured.err
        assert "something nobody anticipated" in captured.err

    def test_nothing_to_hand_off_is_reported_truthfully(self, tmp_path, monkeypatch, capsys):
        _prawduct(tmp_path)
        _session_did_nothing(monkeypatch)

        assert briefing.handoff_cmd(tmp_path, ["preview"]) == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "nothing to hand off" in captured.err

    def test_an_unreadable_note_is_reported_even_with_nothing_else_to_show(
        self, tmp_path, monkeypatch, capsys
    ):
        # `/clear` announces an unreadable note. A preview that reported only
        # "nothing to hand off" would disagree with it about the single fact
        # most worth acting on, and send the agent away reassured.
        pr = _prawduct(tmp_path)
        _session_did_nothing(monkeypatch)
        (pr / ".handoff-notes.md").write_bytes(b"\xff\xfe not utf-8 \xff")

        assert briefing.handoff_cmd(tmp_path, ["preview"]) == 0
        err = capsys.readouterr().err
        assert ".handoff-notes.md" in err and "could not be read" in err
        assert "kept, not consumed" in err

    def test_unreadable_existing_handoff_is_reported(self, tmp_path, monkeypatch, capsys):
        # `/clear` would decline to overwrite it, so the honest preview is not
        # the text that would be generated but the fact that none would land.
        # The failure is injected at the read, not by stubbing the reader, so
        # this exercises the real degradation path rather than asserting the
        # answer it was handed. (Undecodable *bytes* are recovered lossily by
        # design, so they would not reach this state — only an I/O error does.)
        pr = _prawduct(tmp_path)
        _session_did_work(monkeypatch)
        handoff = pr / ".session-handoff.md"
        handoff.write_text("# Session Handoff\n\nirreplaceable hand-written context\n")

        real_read = Path.read_text

        def _explode(self, *a, **kw):
            if self.name == ".session-handoff.md":
                raise OSError("simulated I/O error")
            return real_read(self, *a, **kw)

        monkeypatch.setattr(Path, "read_text", _explode)
        rc = briefing.handoff_cmd(tmp_path, ["preview"])
        monkeypatch.undo()

        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "cannot be read" in captured.err
        # And previewing must not have "fixed" it by writing over it.
        assert handoff.read_text() == (
            "# Session Handoff\n\nirreplaceable hand-written context\n"
        )


class TestHandoffPreviewCli:
    def test_preview_runs_through_the_real_cli(self, tmp_path):
        proj = tmp_path / "repo"
        proj.mkdir()
        pr = proj / ".prawduct"
        (pr / "artifacts").mkdir(parents=True)
        (pr / "project-state.yaml").write_text("backlog_format_version: 2\n")
        (pr / ".handoff-notes.md").write_text("pick up at the parser rewrite")

        proc = run_plugin_hook("handoff", proj, "preview")
        assert proc.returncode == 0, proc.stderr
        assert "# Session Handoff" in proc.stdout
        assert "pick up at the parser rewrite" in proc.stdout
        # Read-only through the real entry point too, not just the lib call.
        assert not (pr / ".session-handoff.md").exists()
        assert (pr / ".handoff-notes.md").is_file()

    def test_missing_subcommand_is_a_usage_error(self, tmp_path):
        proj = tmp_path / "repo"
        (proj / ".prawduct").mkdir(parents=True)
        proc = run_plugin_hook("handoff", proj)
        assert proc.returncode == 2
        assert "Usage" in proc.stderr

    def test_unknown_subcommand_is_a_usage_error(self, tmp_path):
        proj = tmp_path / "repo"
        (proj / ".prawduct").mkdir(parents=True)
        proc = run_plugin_hook("handoff", proj, "write")
        assert proc.returncode == 2

    def test_extra_args_are_rejected(self, tmp_path):
        # Fail closed on tokens we do not understand: a silently-ignored
        # positional is how a fixture path once got swallowed and the live repo
        # audited instead.
        proj = tmp_path / "repo"
        (proj / ".prawduct").mkdir(parents=True)
        proc = run_plugin_hook("handoff", proj, "preview", "--json")
        assert proc.returncode == 2

    def test_repo_without_prawduct_exits_one(self, tmp_path):
        proj = tmp_path / "repo"
        proj.mkdir()
        proc = run_plugin_hook("handoff", proj, "preview")
        assert proc.returncode == 1
        assert proc.stdout == ""

    def test_subcommand_is_wired_and_advertised(self):
        # Same shape as the other wiring pins: a dispatch branch, a wrapper, and
        # an entry inside _USAGE specifically — "the string appears somewhere in
        # the file" would be satisfied by a docstring or a comment.
        src = (_ROOT / "bin" / "prawduct-hook").read_text(encoding="utf-8")
        assert 'command == "handoff"' in src
        assert "def cmd_handoff(" in src
        assert "briefing.handoff_cmd(" in src
        assert "handoff preview" in src.split("_USAGE = (", 1)[1].split(")", 1)[0]
