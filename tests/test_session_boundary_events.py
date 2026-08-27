"""SCN-5B8Q — orientation and boundary are separate acts.

`clear --session-start` did two categorically different jobs under one entry
point, and its SessionStart matcher (`startup|resume|clear`) could not tell them
apart. So `claude --resume` — a *continuation*, where the transcript is restored
and nothing was lost — ran a full boundary reset: it folded `.handoff-notes.md`
into a handoff for a session that had not ended, archived `.session-reflected`
away mid-session, and re-captured all three session anchors (which silently
NARROWS the session Critic gate's jurisdiction to work done after the resume).

The split is by matcher, not by parsing the event payload — the matcher already
carries the one fact needed:

    startup|clear           -> clear --session-start                 (boundary)
    resume|compact|fork     -> clear --session-start --brief-only    (orientation)

`--brief-only` is orthogonal to `--session-start` rather than replacing it:
`--session-start` keeps meaning "a genuine hook invocation" — as opposed to a
reviewer subagent's bare `clear`, which the CRT-3X9D guard refuses — so the
boundary is `--session-start` *without* `--brief-only`.

Statements here sort into THREE kinds, and the middle one is the easy mistake:
destructive boundary acts; **boundary-dependent readers**, which destroy nothing
but interpret session state as a *finished* session's (the critic-active marker
sweep and the previous-session gate check); and orientation, safe on every
source. Only orientation runs on a continuation. In particular the marker sweep
is boundary-only: `compact` fires in-process and `fork`'s parent is often still
running, so a marker seen there is likely LIVE, and sweeping it would disarm the
guard while a reviewer is working.

The marker sweep is scoped a second time, *inside* the boundary column, because
source is only a proxy for the question it asks. What licenses deleting someone
else's marker is that the dispatching process is gone — and `clear` discards the
transcript WITHOUT ending the process, so it passes the test that sorts this
column while failing the one the sweep needs. At a boundary the sweep therefore
asks two questions, not one: the TTL answers *is the dispatching process gone*,
and the roster answers *is there anything left to finish*. A fresh marker
survives every session event, and so does an expired one whose reviewers have
all reported — that review is one deterministic consolidation from being
recorded, and the Stop hook's backstop runs that step itself.

The premise was verified empirically before this was built, not reasoned about:
a headless session was given a codeword, resumed by session id, and returned the
codeword — so a resumed session has not lost context. The same probe confirmed
`source: "resume"` and `source: "fork"` fire, the latter with a new session id.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from test_plugin_runtime import HOOKS_JSON, run_plugin_hook  # noqa: E402

# The five documented SessionStart sources, pinned locally from
# https://code.claude.com/docs/en/hooks (verified 2026-07-27).
#
# HONEST LIMIT: this roster is a local pin of an EXTERNAL fact. It cannot
# discover a sixth source Claude Code adds later — it can only keep the five we
# know about exhaustively partitioned. That is still the right guard: the
# failure this branch keeps re-learning is a check that spot-tests one instance
# (`compact`) and stays silent when the *class* grows, which is exactly how
# `fork` went unnoticed while this plan was being written.
DOCUMENTED_SOURCES = ("startup", "resume", "clear", "compact", "fork")

# Session-scoped evidence a continuation must never destroy.
SESSION_EVIDENCE = (
    ".handoff-notes.md",
    ".session-reflected",
    ".session-start",
    ".session-git-baseline",
    ".session-base-tree",
    ".gates-waived",
)


def _seed_session(tmp_path: Path) -> Path:
    """A repo mid-session: every session-scoped file present with known content."""
    prawduct = tmp_path / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text("backlog_format_version: 2\n")
    # Filled preferences, so the CRITICAL nudge stays quiet and doesn't confound
    # the stdout assertions.
    (prawduct / "artifacts" / "project-preferences.md").write_text(
        "- **Language**: Python\n"
    )
    (prawduct / ".handoff-notes.md").write_text("forward notes: pick up chunk 02\n")
    (prawduct / ".session-reflected").write_text("reflection: the chunk went fine\n")
    (prawduct / ".session-start").write_text("2026-07-27T06:00:00Z")
    (prawduct / ".session-git-baseline").write_text(" M some/file.py\n")
    (prawduct / ".session-base-tree").write_text("a" * 40)
    (prawduct / ".gates-waived").write_text('{"critic": "doc-only"}')
    return prawduct


def _snapshot(prawduct: Path) -> dict[str, str | None]:
    return {
        name: (prawduct / name).read_text() if (prawduct / name).is_file() else None
        for name in SESSION_EVIDENCE
    }


# =============================================================================
# Done-when 1 — a continuation destroys no session-scoped evidence
# =============================================================================


class TestBriefOnlyPreservesSessionEvidence:
    def test_resume_leaves_every_session_file_untouched(self, tmp_path):
        """The case reproduced in SCN-5B8Q, pinned."""
        prawduct = _seed_session(tmp_path)
        before = _snapshot(prawduct)

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr

        after = _snapshot(prawduct)
        for name in SESSION_EVIDENCE:
            assert after[name] == before[name], (
                f"{name} was mutated by a continuation — a resumed session must "
                f"not lose session-scoped evidence"
            )

    def test_resume_writes_no_handoff(self, tmp_path):
        """A handoff describes a session that ENDED. Writing one mid-session
        both lies about the boundary and consumes the forward notes."""
        prawduct = _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        # Assert the invocation SUCCEEDED first. Without this, the test passes
        # while the flag is unrecognized (exit 2, nothing runs) — a pass earned
        # by the command not executing is not evidence about the boundary.
        assert res.returncode == 0, res.stderr
        assert not (prawduct / ".session-handoff.md").is_file(), (
            "a continuation must not generate a session handoff"
        )

    def test_resume_does_not_archive_the_live_reflection(self, tmp_path):
        """Archiving to reflections.md mid-session moves the running session's
        reflection out from under it — the reflection gate then sees nothing."""
        prawduct = _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr  # see note above: no free pass on exit 2
        reflections = prawduct / "reflections.md"
        if reflections.is_file():
            assert "the chunk went fine" not in reflections.read_text(), (
                "the live reflection was archived away by a continuation"
            )

    def test_boundary_still_resets_without_the_flag(self, tmp_path):
        """The discriminating half: prove `--brief-only` is what preserves the
        evidence, not an inert fixture. Without it, the boundary still fires."""
        prawduct = _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr

        assert not (prawduct / ".handoff-notes.md").is_file(), (
            "a real boundary must still consume the forward notes"
        )
        assert not (prawduct / ".gates-waived").is_file(), (
            "a real boundary must still clear gate waivers"
        )
        assert (prawduct / ".session-start").read_text() != "2026-07-27T06:00:00Z", (
            "a real boundary must still re-stamp the session clock"
        )


# =============================================================================
# Done-when 2 — a continuation still gets the whole orientation half
# =============================================================================


class TestBriefOnlyStillOrients:
    def test_resume_still_emits_the_briefing(self, tmp_path):
        _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert "== SESSION BRIEFING ==" in res.stdout, (
            "the briefing is the half whose value the owner confirmed from "
            "repeated observation — a continuation must still receive it"
        )

    def test_resume_refreshes_advisories(self, tmp_path):
        prawduct = _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr
        assert (prawduct / ".advisories.json").is_file(), (
            "advisory probes must still run on a continuation"
        )


# =============================================================================
# R-14 — the boundary's last silent-loss path: consumption keys on preservation
# =============================================================================


class TestReflectionArchivalIsDeliveryKeyed:
    def test_unarchivable_reflection_is_kept_not_deleted(self, tmp_path):
        """Archival used to swallow its failure and the deletion loop unlinked the
        file anyway — destroying a reflection that reached no archive. Same rule as
        `.handoff-notes.md`: consume only what was preserved."""
        prawduct = _seed_session(tmp_path)
        # Make reflections.md un-appendable so archival fails at the write, while
        # the reflection itself stays perfectly readable.
        archive = prawduct / "reflections.md"
        archive.mkdir()  # a directory where a file is expected -> OSError on open()

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        assert (prawduct / ".session-reflected").is_file(), (
            "an un-archivable reflection must be KEPT, not silently destroyed"
        )
        assert "could not archive .session-reflected" in res.stderr, (
            "the failure must be announced, not silent"
        )

    def test_archived_reflection_is_still_deleted(self, tmp_path):
        """The discriminating half — preservation is what licenses the delete, so
        the normal path must still clear the file."""
        prawduct = _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        assert not (prawduct / ".session-reflected").is_file(), (
            "a successfully archived reflection must still be consumed"
        )
        assert "the chunk went fine" in (prawduct / "reflections.md").read_text()


# =============================================================================
# The third category: statements that DESTROY nothing but INTERPRET session
# state as a finished session's. Neither orientation nor a destructive act.
# =============================================================================


class TestBoundaryDependentInterpretation:
    """The first cut of this split classified two statements as orientation
    because they destroy no evidence. Both actually assume a boundary just
    happened, and both are wrong on a continuation (review R-1/R-4/R-6)."""

    def test_continuation_does_not_sweep_the_critic_marker(self, tmp_path):
        """What licenses deleting someone else's marker is that an in-flight
        review dies with the process that dispatched it — true for a session that
        ENDED, false for `compact` (fires mid-session, in-process) and often false
        for `fork` (parent still running). Sweeping there disarms CRT-3X9D and the
        Stop hook's abandoned-review backstop while a reviewer is genuinely live.

        This replaces test_resume_still_sweeps_a_stale_critic_marker, which pinned
        the opposite. That test asserted a real defect, so this is a correction,
        not a relaxation: the marker's three independent recoveries (TTL expiry,
        the boundary sweep, and an explicit named act — `critic-end`,
        `critic-discard`, `clear --force`) all survive, and the boundary sweep
        below still fires. A bare `rm` is NOT among them: it does the same damage
        while saying nothing.
        """
        prawduct = _seed_session(tmp_path)
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": "2026-07-27T06:00:00Z"}))

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr
        assert marker.is_file(), (
            "a continuation must NOT sweep the marker — the reviewing process may "
            "still be alive (compact is in-process; fork's parent often is)"
        )

    def test_force_does_not_promote_a_continuation_to_a_boundary(self, tmp_path):
        """`--force` overrides the GUARDED refusal; it must NOT make a
        continuation sweep. The three flags used to recombine into a different
        boolean at each site, and `--session-start --brief-only --force` swept the
        marker on a continuation — the exact act the design calls a silent
        governance failure (review R-5)."""
        prawduct = _seed_session(tmp_path)
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": "2026-07-27T06:00:00Z"}))

        res = run_plugin_hook(
            "clear", tmp_path, "--session-start", "--brief-only", "--force"
        )
        assert res.returncode == 0, res.stderr
        assert marker.is_file(), (
            "--force must not promote a continuation to a boundary; forcing a "
            "sweep on a live session is the failure mode, not an override of it"
        )
        # And it is still a continuation in every other respect.
        assert (prawduct / ".handoff-notes.md").is_file()
        assert not (prawduct / ".session-handoff.md").is_file()

    def test_force_still_overrides_the_guarded_refusal(self, tmp_path):
        """The discriminating half — `--force` keeps the job it exists for."""
        prawduct = _seed_session(tmp_path)
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": "2026-07-27T06:00:00Z"}))

        res = run_plugin_hook("clear", tmp_path, "--force")
        assert res.returncode == 0, res.stderr
        assert not marker.is_file(), "a forced bare clear must still sweep"

    def test_bare_clear_still_refuses_while_a_review_is_live(self, tmp_path):
        """GUARDED, unforced — the CRT-3X9D invariant, unchanged by the refactor.

        The marker must be stamped NOW: the other markers in this module are
        deliberately hours old, and a marker past the 30-minute TTL is correctly
        *not* active, so a fixed timestamp would make this test assert the TTL
        rather than the refusal (it did, on first run).
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (prawduct / ".critic-active").write_text(json.dumps({"started_at": now}))

        res = run_plugin_hook("clear", tmp_path)
        assert res.returncode == 2, "a bare clear must refuse during a live review"
        assert (prawduct / ".handoff-notes.md").is_file(), "and mutate nothing"

    def test_boundary_still_sweeps_the_critic_marker(self, tmp_path):
        """The discriminating half — the sweep is not lost, only re-scoped.

        The marker is deliberately hours old: past the TTL, so it is the case
        the sweep exists for (a crashed Critic), and the one that must survive
        the freshness gate added beside it.
        """
        prawduct = _seed_session(tmp_path)
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": "2026-07-27T06:00:00Z"}))

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        assert not marker.is_file(), (
            "a genuine boundary must still sweep a stale marker"
        )

    def test_boundary_does_not_sweep_a_marker_that_is_still_live(self, tmp_path):
        """`/clear` is the one boundary source where the column's test and the
        sweep's premise disagree.

        The boundary/continuation split sorts on *was the transcript restored?*
        — correct for every destructive act here, because those all destroy a
        finished session's evidence. The sweep asks something narrower: *is the
        process that dispatched the review gone?* `startup` answers yes to both.
        `clear` answers yes to the first and NO to the second — it resets context
        in-process — so a review subagent dispatched before it may still be
        running, and deleting its marker disarms both the CRT-3X9D refusal and
        the Stop hook's abandoned-review backstop (which does not merely block:
        it consolidates a review whose reviewers all reported).

        Gating on the TTL answers the real question at every source, which is why
        this needs no finer matcher — `startup|clear` share one hook entry and
        are indistinguishable to the command.

        Stamped NOW rather than at a fixed date, for the reason
        `test_bare_clear_still_refuses_while_a_review_is_live` records: a marker
        past the 30-minute TTL is correctly not active, so a frozen timestamp
        would make this assert the TTL instead of the gate.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        assert marker.is_file(), (
            "a boundary must not sweep a marker that is still within the TTL — "
            "/clear does not end the process, so the reviewer may be alive"
        )
        # And the boundary still HAPPENED: the gate is scoped to the marker, not
        # a demotion of the whole event. Without this the assertion above would
        # also pass if `clear` had silently become a continuation.
        assert (prawduct / ".session-handoff.md").is_file(), (
            "the freshness gate must scope the SWEEP only, not demote the boundary"
        )

    def test_a_retained_marker_is_announced_to_the_new_session(self, tmp_path):
        """Retention must not be silent, and this is the session that most needs
        telling: `/clear` just discarded the context in which the review was
        dispatched, so nothing else in the new session knows one is pending.

        Asserted on the RECOVERY, not on the wording. A message that says only
        "a review is active" leaves the reader stuck at the refusal they will
        hit next, so the pin is that a named release command travels with it —
        which is the half a phrasing check would miss.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (prawduct / ".critic-active").write_text(json.dumps({"started_at": now}))

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        assert "critic-end" in out, (
            "a retained marker must travel with the command that releases it — "
            "the reader's next step is otherwise an unexplained refusal"
        )

    def test_force_sweeps_a_live_marker_at_a_boundary_too(self, tmp_path):
        """`--force` is orthogonal to the freshness gate, at every kind that can
        carry it.

        The regression this pins actually shipped for one commit: splitting the
        sweep into `if BOUNDARY / elif GUARDED and force` made
        `--session-start --force` take the BOUNDARY branch, so the flag was
        silently ignored — while the call-site comment, `cmd_clear`'s docstring
        and `architecture.md` all still promised it was unconditional, and the
        retained-marker notice recommended it. The bare-`--force` test passed
        throughout, because it exercises the GUARDED path.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--force")
        assert res.returncode == 0, res.stderr
        assert not marker.is_file(), (
            "--force must sweep a live marker at a BOUNDARY as well as a bare "
            "clear; it is the operator's only escape from a fresh marker"
        )

    def test_forcing_a_sweep_names_a_recovery_that_can_actually_be_run(self, tmp_path):
        """An INCOMPLETE roster: the partials will be archived, so restore is the
        recovery — but only at a moment when `critic-restore` will run.

        The first cut of this notice said "restore after the next dispatch",
        which is the one moment the command is guaranteed to refuse:
        `restore_review` bails while partials are present or a marker is active,
        and a dispatch makes both true. The refusal it landed on then offers
        `critic-discard` — i.e. it walked the operator toward discarding the
        review that was running right then.

        So the assertion is on the ORDERING, not on the command name. The
        previous pin looked for the id and the substring `critic-restore`, both
        of which were present in the broken message; a substring check cannot
        tell a runnable instruction from an unrunnable one.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))
        # Build the fixture from the module that OWNS the layout, not from a
        # hardcoded literal: the code used to hardcode the same path, so a
        # rename would have moved both together and stayed green.
        from lib.critic_consolidate import manifest_path  # noqa: PLC0415
        mpath = manifest_path(prawduct)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        roster = ["correctness", "design"]
        mpath.write_text(json.dumps({
            "id": "rev-forced",
            "mode": "cumulative (bundle review, ready for merge)",
            "mode_chosen_by": "test", "roster_chosen_by": "test",
            "commit_reviewed": "0" * 40,
            "base_tree": "1" * 40, "head_tree": "2" * 40,
            "files_reviewed": ["some/file.py"], "files_changed": ["some/file.py"],
            "roster": roster,
            "rendezvous": {
                r: {"partial": f".prawduct/.critic-partials/{r}.rev-forced.json",
                    "started": f".prawduct/.critic-partials/{r}.rev-forced.started"}
                for r in roster
            },
        }))
        from lib.critic_consolidate import pending_state  # noqa: PLC0415
        assert pending_state(prawduct)[0] == "incomplete", (
            "fixture must build an INCOMPLETE roster; the complete branch says "
            "something different and this would grade the wrong one"
        )

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--force")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        assert not marker.is_file(), "--force must still sweep; this pins the notice"
        assert "rev-forced" in out, (
            "the forced sweep did not name the review it unguarded — without the "
            "id no recovery is addressable at all"
        )
        assert "once the next one has consolidated" in out, (
            "the notice does not say WHEN `critic-restore` can run. `restore_review` "
            "refuses while partials or a marker are present, so a recovery timed to "
            "'after the next dispatch' is unrunnable and lands the operator on a "
            "refusal that offers `critic-discard`"
        )
        assert "after the next dispatch" not in out, (
            "the notice is back on the unrunnable timing — that phrasing names the "
            "one moment `critic-restore` is guaranteed to refuse"
        )

    def test_a_sweep_with_no_readable_id_offers_a_handle_that_exists(self, tmp_path):
        """The disk where the id is not a name but a sentence: partials on disk
        with no manifest describing them. The notice promises preservation
        (correctly — that output is real) and then used to render
        `prawduct-hook critic-restore (id unavailable — …)` as the ONLY handle.
        An operator who copies it gets `no archived review named '(id…'`, and
        the two handles that work — the bare listing, and the
        `unmanifested-<ts>` name the archiving dispatch prints — are never
        mentioned. The partials then age out of the archive ring unread, which
        is exactly the harm the preservation clause exists to prevent.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))
        from lib.critic_consolidate import manifest_path  # noqa: PLC0415
        partials = manifest_path(prawduct).parent
        partials.mkdir(parents=True, exist_ok=True)
        (partials / "correctness.rev-orphan.json").write_text("{}")

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--force")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        assert not marker.is_file(), "--force must still sweep; this pins the notice"
        assert "reviewer partial(s)" in out, (
            "fixture guard: this disk must reach the preservation branch, or the "
            "recovery line under test is never rendered"
        )
        assert "critic-restore (id unavailable" not in out, (
            "the notice offered a command whose argument is a sentence about not "
            "having an argument"
        )
        assert "prawduct-hook critic-restore\n" in out, (
            "the runnable handle — bare `critic-restore` lists the archive — must "
            "be the one offered when the id cannot be read"
        )

    def test_forcing_a_sweep_of_a_complete_roster_names_the_lost_self_heal(self, tmp_path):
        """A COMPLETE roster: nothing will archive those partials — and nothing
        will consolidate them either, which is what the sweep actually cost.

        The notice called itself the retention notice's "mirror image" while
        asking no roster question, so on a complete roster its central claim was
        false in both directions: `begin_review` refuses on a complete roster at
        any age, so the next `critic-begin` does NOT archive the partials, and
        the Stop hook's self-heal keys on the marker — so sweeping it removed the
        one automatic recovery a finished review was about to get, which the
        message never mentioned.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))
        from lib.critic_consolidate import manifest_path, pending_state  # noqa: PLC0415
        mpath = manifest_path(prawduct)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(json.dumps({
            "id": "rev-done",
            "mode": "chunk (lighter pass, not ready for push)",
            "mode_chosen_by": "test", "roster_chosen_by": "test",
            "commit_reviewed": "0" * 40,
            "base_tree": "1" * 40, "head_tree": "2" * 40,
            "files_reviewed": ["some/file.py"], "files_changed": ["some/file.py"],
            "roster": ["reviewer"],
            "rendezvous": {"reviewer": {
                "partial": ".prawduct/.critic-partials/reviewer.rev-done.json",
                "started": ".prawduct/.critic-partials/reviewer.rev-done.started",
            }},
        }))
        (mpath.parent / "reviewer.rev-done.json").write_text(json.dumps({"findings": []}))
        assert pending_state(prawduct)[0] == "complete", (
            "fixture must build a COMPLETE roster or this grades another branch"
        )

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--force")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        assert "critic-consolidate" in out, (
            "a complete roster's findings are written and only need consolidating; "
            "the notice must route there"
        )
        assert "self-heal" in out, (
            "the notice does not name what the sweep COST — the Stop hook's "
            "self-heal keys on the marker, so removing it is what stops a "
            "finished review from being consolidated automatically"
        )
        assert "will archive its" not in out, (
            "the notice still claims the next dispatch will archive these partials; "
            "`begin_review` refuses on a complete roster at any age, so it will not"
        )

    def test_force_sweeps_a_marker_it_cannot_read(self, tmp_path):
        """`--force` does not depend on classifying the marker first.

        **Named for what it proves, after two versions that named what they did
        not.** The reorder this guards (the pre-read in its own `try`, so
        `clear_marker` is always reached) was raised against a read that raises
        — and through this call path it cannot. `_marker_age_seconds` catches
        `OSError` and falls back to `stat().st_mtime`, which succeeds on a mode
        `000` file, so `review_active` degrades internally and never propagates.
        The reorder remains correct as defence in depth; the fault it defends
        against is unreachable here, and a test claiming to inject it passes as
        an ordinary sweep. (v1 claimed an unparseable marker was "undatable" —
        mtime dates it. v2 claimed `chmod 000` made the read raise — `OSError`
        is caught. Both passed; reverting the reorder left both green.)

        What IS true and worth pinning: `--force` is the operator's unconditional
        escape, so an unreadable marker must not become one it cannot remove.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))
        marker.chmod(0o000)
        try:
            res = run_plugin_hook("clear", tmp_path, "--session-start", "--force")
            assert res.returncode == 0, res.stderr
            assert not marker.is_file(), (
                "--force left behind a marker whose contents it could not read; "
                "unreadable must not mean unremovable, or the operator's "
                "documented escape has a state it cannot escape"
            )
        finally:
            if marker.is_file():
                marker.chmod(0o600)

    def test_forcing_a_sweep_of_a_dead_marker_stays_quiet(self, tmp_path):
        """The discriminating half. An announcement on every `--force` is noise,
        and noise on the routine case trains the reader past the one case that
        means something. An EXPIRED marker is what the sweep exists to clear —
        nothing was destroyed, so nothing is reported.
        """
        prawduct = _seed_session(tmp_path)
        stale = datetime.now(timezone.utc) - timedelta(days=1)
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({
            "started_at": stale.strftime("%Y-%m-%dT%H:%M:%SZ")
        }))

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--force")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        assert not marker.is_file()
        assert "swept a LIVE" not in out, (
            "an expired marker is the sweep's ordinary business; announcing it "
            "trains the reader past the live case that actually matters"
        )

    def test_the_retained_notice_never_advises_clearing_a_complete_roster(self, tmp_path):
        """The remedy is conditional, and the wrong one is destructive.

        `critic-end` clears the marker only. On a COMPLETE roster the Stop hook
        would have consolidated those partials into a review fact — so advising
        `critic-end` there tells the reader to discard a finished review's
        findings. The notice therefore asks `pending_state` before advising, the
        same split `active_dispatch_refusal` already makes.

        Asserted as a positive and a negative together: naming `consolidate` is
        not enough if it also offers the destructive command beside it.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (prawduct / ".critic-active").write_text(json.dumps({"started_at": now}))
        partials = prawduct / ".critic-partials"
        partials.mkdir(exist_ok=True)
        (partials / "manifest.json").write_text(json.dumps({
            "id": "rev-test",
            "mode": "chunk (lighter pass, not ready for push)",
            "mode_chosen_by": "test", "roster_chosen_by": "test",
            "commit_reviewed": "0" * 40,
            "base_tree": "1" * 40, "head_tree": "2" * 40,
            "files_reviewed": ["some/file.py"],
            "files_changed": ["some/file.py"],
            "roster": ["reviewer"],
            "rendezvous": {"reviewer": {
                "partial": ".prawduct/.critic-partials/reviewer.rev-test.json",
                "started": ".prawduct/.critic-partials/reviewer.rev-test.started",
            }},
        }))
        (partials / "reviewer.rev-test.json").write_text(json.dumps({"findings": []}))
        # Guard the fixture itself: pending_state falls back to "unreadable" on a
        # manifest it cannot validate, and "unreadable" also routes to
        # `critic-end` — so a malformed fixture would make the negative assertion
        # below pass for the wrong reason. Assert the state we meant to build.
        from lib.critic_consolidate import pending_state  # noqa: PLC0415
        assert pending_state(prawduct)[0] == "complete", (
            "fixture does not build a complete roster; the assertions below "
            "would grade the unreadable branch instead"
        )

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        assert "critic-consolidate" in out, (
            "a complete roster must be routed to consolidation — its findings "
            "are already written and only need a fact appended"
        )
        assert "prawduct-hook critic-end" not in out, (
            "the notice offered `critic-end` on a complete roster; following it "
            "discards a finished review's findings"
        )

    def test_the_retained_notice_names_both_readings_on_an_incomplete_roster(self, tmp_path):
        """The branch a `/clear` during a live coordinator review actually lands in.

        Three outcomes, and this was the unpinned one — while being the state
        the feature exists for: reviewers dispatched, partials not all written.
        Its wrong value is destructive in the direction this bundle has already
        been bitten in once. The reader has *just* run `/clear`, so a message
        saying only "if that session is gone they will never land" reads as
        already satisfied; they run `critic-end`, the marker clears, the
        in-flight guard stops refusing, and the next dispatch archives partials
        that reviewers are still writing.

        So the assertion is that BOTH readings are present and the remedy is
        conditioned on the tell — not merely that the missing role is named. A
        message naming the role and one reading passes any phrasing check and
        still sends the reader to the destructive command.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (prawduct / ".critic-active").write_text(json.dumps({"started_at": now}))
        partials = prawduct / ".critic-partials"
        partials.mkdir(exist_ok=True)
        roster = ["correctness", "design", "sustainability"]
        (partials / "manifest.json").write_text(json.dumps({
            "id": "rev-test",
            "mode": "cumulative (bundle review, ready for merge)",
            "mode_chosen_by": "test", "roster_chosen_by": "test",
            "commit_reviewed": "0" * 40,
            "base_tree": "1" * 40, "head_tree": "2" * 40,
            "files_reviewed": ["some/file.py"],
            "files_changed": ["some/file.py"],
            "roster": roster,
            "rendezvous": {
                role: {
                    "partial": f".prawduct/.critic-partials/{role}.rev-test.json",
                    "started": f".prawduct/.critic-partials/{role}.rev-test.started",
                }
                for role in roster
            },
        }))
        # One reporter, two still out -- the shape of a real coordinator review
        # interrupted mid-flight.
        (partials / "correctness.rev-test.json").write_text(json.dumps({"findings": []}))
        # Guard the fixture, for the reason this class's complete-roster test
        # already documents: an invalid manifest degrades to "unreadable", which
        # routes to `critic-end` too -- so the assertions below would grade the
        # wrong branch and the conditional-remedy check would pass vacuously.
        from lib.critic_consolidate import pending_state  # noqa: PLC0415
        assert pending_state(prawduct)[0] == "incomplete", (
            "fixture does not build an incomplete roster; the assertions below "
            "would grade a different branch"
        )

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        out = res.stdout + res.stderr
        for role in ("design", "sustainability"):
            assert role in out, (
                f"the notice does not name {role} as outstanding — the reader "
                "cannot tell what the review is waiting on"
            )
        assert "still running" in out, (
            "the notice omits the reading in which the reviewers are ALIVE. "
            "At a boundary the reader has just ended a session, so without it "
            "they conclude the review is dead and run the destructive remedy"
        )
        assert "Only if nothing lands" in out, (
            "the notice offers `critic-end` unconditionally on an incomplete "
            "roster; following it while reviewers are still writing lets the "
            "next dispatch archive their partials"
        )

    def test_a_swept_marker_is_not_announced(self, tmp_path):
        """The discriminating half. Without it the announcement could fire on
        every boundary and still pass the test above, which would train the
        reader to ignore the one case that means something.
        """
        prawduct = _seed_session(tmp_path)
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": "2026-07-27T06:00:00Z"}))

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        assert not marker.is_file()
        assert "still marked active" not in (res.stdout + res.stderr), (
            "a swept marker must announce nothing — there is no review to report"
        )

    def test_force_sweeps_a_live_marker_the_ttl_has_not_released(self, tmp_path):
        """The operator override stays unconditional, which is the whole point of
        it: `--force` exists for a marker the TTL has not released yet, so gating
        it on freshness would disable the one case it serves. Pinned because the
        boundary gate above and this branch now differ, and a later simplification
        that merges them silently removes the escape hatch the refusal message
        tells the operator to use.
        """
        prawduct = _seed_session(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        marker = prawduct / ".critic-active"
        marker.write_text(json.dumps({"started_at": now}))

        res = run_plugin_hook("clear", tmp_path, "--force")
        assert res.returncode == 0, res.stderr
        assert not marker.is_file(), (
            "--force must sweep a live marker; it is the documented override for "
            "exactly the marker the TTL has not released"
        )

    def test_continuation_announces_a_missing_base_tree_anchor(self, tmp_path):
        """Not writing the anchor is correct; degrading in silence is not. With no
        anchor the Critic gate shrinks to uncommitted work and skips the merge-base
        rescue — the boundary path announces that, the continuation path had no
        notice at all (review R-15)."""
        prawduct = _seed_session(tmp_path)
        (prawduct / ".session-base-tree").unlink()

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr
        assert ".session-base-tree" in res.stderr and "uncommitted work only" in res.stderr, (
            "a missing anchor on a continuation must name its consequence"
        )

    def test_continuation_is_quiet_when_the_anchor_is_present(self, tmp_path):
        """The discriminating half — the notice fires on the degradation, not on
        every continuation."""
        _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr
        assert "session-base-tree" not in res.stderr, (
            "an anchored continuation must not emit the degradation notice"
        )

    def test_continuation_does_not_warn_about_the_running_session(self, tmp_path):
        """`_check_previous_session_gates` reads `.session-reflected` /
        `.gates-waived` / the change baseline and reports them as a *finished*
        session's record. On a continuation they belong to the session still
        running, so the warning would blame work that has not reached its close —
        repeatedly, since `compact` can fire many times in one session."""
        prawduct = _seed_session(tmp_path)
        # Mid-session state that WOULD trip the gate check at a boundary: a
        # too-short reflection, with the waiver file removed so nothing excuses it.
        (prawduct / ".session-reflected").write_text("wip\n")
        (prawduct / ".gates-waived").unlink()

        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr
        assert "Previous session had unmet governance" not in res.stdout, (
            "a continuation must not report the running session as a previous "
            "session with unmet gates"
        )


# =============================================================================
# Done-when 4/5 — the wiring: partition property + arg guard
# =============================================================================


class TestMatcherPartition:
    @staticmethod
    def _clear_entries():
        """The two SessionStart entries that run `prawduct-hook clear`, split by
        whether they carry --brief-only."""
        data = json.loads(HOOKS_JSON.read_text())
        boundary, orientation = [], []
        for entry in data["hooks"]["SessionStart"]:
            cmds = [h["command"] for h in entry["hooks"]]
            if not any("bin/prawduct-hook" in c and "clear" in c.split() for c in cmds):
                continue
            if any("--brief-only" in c for c in cmds):
                orientation.append(entry)
            else:
                boundary.append(entry)
        return boundary, orientation

    def test_exactly_one_boundary_and_one_orientation_entry(self):
        boundary, orientation = self._clear_entries()
        assert len(boundary) == 1, f"expected 1 boundary clear entry, got {len(boundary)}"
        assert len(orientation) == 1, (
            f"expected 1 orientation clear entry, got {len(orientation)}"
        )

    def test_every_documented_source_is_covered_exactly_once(self):
        """The partition property. A source covered twice would run the boundary
        AND the orientation path; a source covered zero times gets no governance
        context at all — which is how `fork` was being dropped."""
        boundary, orientation = self._clear_entries()
        b_sources = set(boundary[0]["matcher"].split("|"))
        o_sources = set(orientation[0]["matcher"].split("|"))

        assert not (b_sources & o_sources), (
            f"a source is on BOTH paths: {sorted(b_sources & o_sources)}"
        )
        assert b_sources | o_sources == set(DOCUMENTED_SOURCES), (
            f"the two matchers must exhaustively partition {DOCUMENTED_SOURCES}; "
            f"uncovered: {sorted(set(DOCUMENTED_SOURCES) - (b_sources | o_sources))}, "
            f"unknown: {sorted((b_sources | o_sources) - set(DOCUMENTED_SOURCES))}"
        )

    def test_only_startup_and_clear_reset_the_session(self):
        """Successor to test_clear_matcher_excludes_compact. That test protected
        'compaction must not reset the session' and checked only `compact`; this
        asserts the real invariant over every continuation source, so `resume`
        and `fork` are covered too."""
        boundary, _ = self._clear_entries()
        assert set(boundary[0]["matcher"].split("|")) == {"startup", "clear"}, (
            "only a genuine session start may run the boundary reset"
        )

    def test_orientation_only_hooks_cover_every_source(self):
        """banner / digest carry no boundary reset, so they should fire on every
        source. A forked session that receives no banner and no digest is the same
        defect one level down.

        `build-index` was the third such entry until v3.3.2 deleted it with the
        work-model tripwire; the rule is unchanged and the assertion below reads
        the file rather than a list, so it covers whatever orientation-only
        entries exist."""
        data = json.loads(HOOKS_JSON.read_text())
        for entry in data["hooks"]["SessionStart"]:
            cmds = [h["command"] for h in entry["hooks"]]
            if any("bin/prawduct-hook" in c and "clear" in c.split() for c in cmds):
                continue  # the split pair, asserted above
            sources = set(entry["matcher"].split("|"))
            assert sources == set(DOCUMENTED_SOURCES), (
                f"orientation-only hook {cmds} covers {sorted(sources)}, "
                f"missing {sorted(set(DOCUMENTED_SOURCES) - sources)}"
            )


class TestArgGuard:
    def test_brief_only_is_accepted(self, tmp_path):
        _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-only")
        assert res.returncode == 0, res.stderr
        assert "unknown argument" not in res.stderr

    def test_brief_only_accepted_without_session_start(self, tmp_path):
        """--brief-only is orthogonal to --session-start, so the guard must not
        couple them. (No marker present, so the bare-clear guard lets it pass.)"""
        _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--brief-only")
        assert res.returncode == 0, res.stderr

    def test_unknown_flag_still_rejected(self, tmp_path):
        _seed_session(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start", "--brief-onlyy")
        assert res.returncode == 2
        assert "unknown argument" in res.stderr

    def test_usage_string_documents_the_flag(self):
        src = (_ROOT / "bin" / "prawduct-hook").read_text()
        assert "--brief-only" in src.split("_USAGE = ")[1][:600], (
            "--brief-only must appear in the usage string"
        )
