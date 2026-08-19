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
fires only on a marker that has already failed the 30-minute TTL; a fresh one
survives every session event.

The premise was verified empirically before this was built, not reasoned about:
a headless session was given a codeword, resumed by session id, and returned the
codeword — so a resumed session has not lost context. The same probe confirmed
`source: "resume"` and `source: "fork"` fire, the latter with a new session id.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
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
        not a relaxation: the marker's three independent recoveries (30-min TTL,
        `--force`, `rm`) all survive, and the boundary sweep below still fires.
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
