"""Stop-hook catch for an ABANDONED Critic review (Chunk 01, CRT-9K7T follow-up).

Root cause (verified this session): Claude Code v2.1.198 flipped Agent subagents
to background-by-default. A `context: fork` Critic coordinator dispatches its
review subagents and returns before resuming, so SKILL steps 7-8 (findings write,
`ledger-append`, `critic-end`) never run — the `.critic-active` marker set by
`critic-begin` is never cleared. Chunk 03's exit-time assertion lives INSIDE
`critic-end`, so it cannot fire on this "never-reaches-critic-end" variant. The
existing Stop Critic gate keys on findings *mtime* freshness, so a stale-content
findings file with a fresh mtime SATISFIES it and the session ends "clean" —
the failure only surfaces later as a `check-cumulative-critic` deadlock.

This gate closes that hole: a lingering marker is the out-of-fork signal that a
review never completed. `cmd_stop` blocks loudly on it (exit 2) so the review is
re-run/completed before session end, never silently deferred to the PR gate.

Harness mirrors `test_critic_gate_fallthrough.py` — subprocess `bin/prawduct-hook
stop` with a mock git on PATH — because the gate decision (marker presence, the
doc-only shortcut, the deferral, and the freshness-gate suppression) is only
observable end-to-end inside `cmd_stop`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from conftest import V2_MANIFEST

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

# A non-`.md` code diff: keeps the empirical doc-only shortcut False so the only
# thing that could suppress the gate is a carveout we are deliberately testing.
_CODE_DIFF = " M src/app.py"
_DOC_DIFF = " M docs/notes.md"
MARKER_REL = ".prawduct/.critic-active"
# The generic coverage blocker's signature line (kernel-v3 chunk 04) — must be
# SUPPRESSED when the more-specific abandoned-review blocker fires (one cause,
# one block).
_GENERIC_CRITIC_MSG = "no composed review coverage"
_ABANDONED_MSG = "CRITIC REVIEW (not completed)"


def _write_mock_git(mock_bin: Path, *, status: str, branch: str = "main") -> None:
    mock_bin.mkdir(parents=True, exist_ok=True)
    status_file = mock_bin / "_status"
    status_file.write_text(status)
    git = mock_bin / "git"
    git.write_text(
        "#!/bin/bash\n"
        'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then echo "deadbeefdeadbeef"; exit 0; fi\n'
        'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
        'if [[ "$1" == "status" ]]; then cat "%s"; exit 0; fi\n'
        'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "%s"; exit 0; fi\n'
        'if [[ "$1" == "worktree" ]]; then exit 0; fi\n'
        'if [[ "$1" == "ls-files" ]]; then exit 1; fi\n'
        "exit 0\n" % (status_file, branch)
    )
    git.chmod(0o755)
    gh = mock_bin / "gh"
    gh.write_text("#!/bin/bash\necho '[]'\nexit 0\n")
    gh.chmod(0o755)


def _run_stop(
    project_dir: Path, *, status: str, stdin: str | None = None
) -> subprocess.CompletedProcess:
    mock_bin = project_dir.parent / "_mock_bin"
    _write_mock_git(mock_bin, status=status)
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": f"{mock_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "stop"],
        capture_output=True, text=True, env=env, timeout=20,
        input=stdin,
    )


def _active_plan_repo(tmp_path: Path, *, chunk_type: str = "code") -> Path:
    """Active-build-plan fixture. Reflection is pre-satisfied so the Critic gate
    (freshness or abandoned) is the only gate in play. No findings written."""
    prawduct = tmp_path / ".prawduct"
    artifacts = prawduct / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "build-plan.md").write_text(
        "# Build Plan\n\n"
        "## Status\n- [ ] Chunk 01: Demo\n\n"
        f"### Chunk 01: Demo\n**Type:** {chunk_type}\n\nBody.\n"
    )
    (prawduct / ".session-reflected").write_text(
        "Session reflection: implemented the chunk and verified all tests pass cleanly."
    )
    (prawduct / ".session-git-baseline").write_text("")
    ts = datetime.now(timezone.utc) - timedelta(seconds=60)
    (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return prawduct


def _set_marker(prawduct: Path) -> None:
    (prawduct / ".critic-active").write_text(
        json.dumps({"started_at": "2026-07-09T00:00:00Z", "pid": 1, "tool": "critic"})
    )


# The mock git's `rev-parse HEAD` (see _write_mock_git) — the manifest/partials
# must claim this commit so consolidate's HEAD-coverage check resolves to "covered".
_MOCK_HEAD = "deadbeefdeadbeef"
_FINAL_MODE = "final (full review, ready for push)"
_ROSTER = ["correctness", "design", "sustainability"]


_FAKE_REVIEW_ID = "rev-test-0001"


def _rendezvous(roster, review_id: str) -> dict:
    """The per-role write paths, exactly as `begin_review` records them — a
    partial is keyed by the review that dispatched it, so a fixture that
    composes `<role>.json` writes where nothing looks."""
    return {
        role: {
            "partial": f".prawduct/.critic-partials/{role}.{review_id}.json",
            "started": f".prawduct/.critic-partials/{role}.{review_id}.started",
        }
        for role in roster
    }


def _review_id(prawduct: Path) -> str:
    try:
        mpath = prawduct / ".critic-partials" / "manifest.json"
        return json.loads(mpath.read_text())["id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return _FAKE_REVIEW_ID


def _write_manifest(prawduct: Path, *, commit: str = _MOCK_HEAD) -> None:
    # v3 dispatch-manifest shape (kernel v3 ch.03) — tree SHAs are opaque to
    # the consolidator, so fakes suffice here.
    d = prawduct / ".critic-partials"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({
        "id": _FAKE_REVIEW_ID,
        "mode": _FINAL_MODE, "mode_chosen_by": "rule-3", "roster": _ROSTER,
        "roster_chosen_by": "test fixture",
        "rendezvous": _rendezvous(_ROSTER, _FAKE_REVIEW_ID),
        "commit_reviewed": commit,
        "base_commit": commit, "base_tree": "basetree000000000000",
        "head_tree": "headtree000000000000", "head_commit": None,
        "files_changed": ["src/app.py"], "files_reviewed": ["src/app.py"],
        "tier": None, "scope": "demo", "chunk": None, "base_reviewed": None,
    }))


def _write_partial(prawduct: Path, role: str, *, commit: str = _MOCK_HEAD) -> None:
    d = prawduct / ".critic-partials"
    d.mkdir(parents=True, exist_ok=True)
    rid = _review_id(prawduct)
    (d / f"{role}.{rid}.json").write_text(json.dumps({
        "role": role, "goals": "1-3", "dispatch_id": rid, "commit_reviewed": commit,
        "model": "opus", "duration_seconds": 60, "findings": [],
        "summary": f"{role} clean.",
    }))


def _dispatched_real_repo(tmp_path: Path) -> tuple[Path, Path, dict]:
    """A real git repo with an active plan, a session edit, and a dispatched
    review. Returns ``(repo, prawduct_dir, env)``.

    Real git rather than the mock: the dispatch manifest and the gate's own tree
    capture have to agree on real tree SHAs, so a faked HEAD makes the self-heal
    unreachable for a reason that has nothing to do with what is being tested.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=str(repo), check=True, timeout=15)
    (repo / ".gitignore").write_text(".prawduct/\n")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    subprocess.run([*git, "add", "-A"], cwd=str(repo), check=True, timeout=15)
    subprocess.run([*git, "commit", "-q", "-m", "c1"], cwd=str(repo), check=True, timeout=15)
    prawduct = _active_plan_repo(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")  # the session's edit

    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(repo),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    begin = subprocess.run(
        ["python3", str(HOOK), "critic-begin", "--mode", "chunk"],
        capture_output=True, text=True, env=env, cwd=str(repo), timeout=20,
    )
    assert begin.returncode == 0, begin.stderr
    return repo, prawduct, env


def _write_complete_review(prawduct: Path, *, commit: str = _MOCK_HEAD) -> None:
    _write_manifest(prawduct, commit=commit)
    for role in _ROSTER:
        _write_partial(prawduct, role, commit=commit)


class TestAbandonedReviewBlocks:
    def test_lingering_marker_blocks_with_actionable_message(self, tmp_path):
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2, (
            f"a lingering .critic-active marker must block session end. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert _ABANDONED_MSG in result.stderr
        # Actionable: names the re-run path and the escape hatch (Chunk 05 dropped
        # the interim "run critic-end" advice — consolidate now owns persistence).
        assert "/prawduct:critic" in result.stderr
        # The escape hatch clears the leftover partials — otherwise the next
        # dispatch at the same HEAD could merge a stale partial as current work —
        # but it does so through `critic-discard`, which ARCHIVES them. The two
        # `rm` lines this once asserted destroyed a roster that may be one
        # consolidation from being recorded; TestTheEscapeHatchNeverDestroys
        # below binds that for every branch, not just this one.
        assert "critic-discard" in result.stderr

    def test_abandoned_block_suppresses_generic_findings_block(self, tmp_path):
        """One cause → one block. With the marker present AND no findings, the
        freshness gate would ALSO fire; the abandoned (accurate) message must win
        and the generic 'no findings recorded' message must not also appear."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert _ABANDONED_MSG in result.stderr
        assert _GENERIC_CRITIC_MSG not in result.stderr, (
            f"the generic findings blocker must be suppressed when the abandoned "
            f"blocker fires. stderr={result.stderr!r}"
        )

    def test_stop_does_not_sweep_the_marker(self, tmp_path):
        """The Stop hook only INSPECTS the marker; sweeping it would erase the
        signal it blocks on and silently mutate the session it gates."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        _run_stop(tmp_path, status=_CODE_DIFF)
        assert (prawduct / ".critic-active").is_file(), (
            "cmd_stop must not clear the critic-active marker it inspects"
        )


class TestNoFalsePositive:
    def test_no_marker_no_abandoned_block(self, tmp_path):
        """Marker absent → the abandoned blocker must not fire. (The generic
        freshness gate still does its own job — asserted separately below.)"""
        _active_plan_repo(tmp_path)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert _ABANDONED_MSG not in result.stderr

    def test_no_marker_generic_gate_still_fires(self, tmp_path):
        """Contrast: with no marker and no findings, the EXISTING freshness gate
        must still block — Chunk 05 must not weaken the pre-existing gate."""
        _active_plan_repo(tmp_path)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert _GENERIC_CRITIC_MSG in result.stderr

    def test_marker_but_no_build_plan_no_block(self, tmp_path):
        """A lingering marker with no active build plan is not an abandoned
        *build-plan* review — same firing conditions as the Critic gate."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / ".session-reflected").write_text("x" * 60)
        (prawduct / ".session-git-baseline").write_text("")
        ts = datetime.now(timezone.utc) - timedelta(seconds=60)
        (prawduct / ".session-start").write_text(ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
        _set_marker(prawduct)
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert _ABANDONED_MSG not in result.stderr

    def test_doc_only_diff_skips_the_gate(self, tmp_path):
        """Doc-only changes have no code to review — the abandoned gate, like the
        Critic gate, does not fire (a stray marker on a docs-only turn is noise)."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        result = _run_stop(tmp_path, status=_DOC_DIFF)
        assert _ABANDONED_MSG not in result.stderr


class TestWaiverAndDeferral:
    def test_critic_waiver_suppresses_and_notes(self, tmp_path):
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        (prawduct / ".gates-waived").write_text(
            json.dumps({"critic": "reviewer agent could not complete this session"})
        )
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 0, (
            f"a critic waiver must clear the abandoned block. stderr={result.stderr!r}"
        )
        assert _ABANDONED_MSG not in result.stderr
        assert "critic: waived" in result.stderr

    def test_in_flight_background_work_defers_not_blocks(self, tmp_path):
        """A review whose subagents are still running is IN-FLIGHT, not
        abandoned: `background_tasks` non-empty → the block defers (exit 0) and
        re-arms on the next Stop once the array empties. This is the load-bearing
        distinction — without it the gate would false-block every legitimate
        review the instant the fork yields."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        stdin = json.dumps(
            {"background_tasks": [{"type": "task", "agent_type": "critic-reviewer"}]}
        )
        result = _run_stop(tmp_path, status=_CODE_DIFF, stdin=stdin)
        assert result.returncode == 0, (
            f"an in-flight review must DEFER, not block. stderr={result.stderr!r}"
        )
        assert "DEFERRED" in result.stderr


class TestChunk05ConsolidateOrBlock:
    """The evolved backstop reads the on-disk partials state and consolidates or
    blocks accordingly (critic-persistence-redesign Ch.05)."""

    def test_complete_partials_self_heal(self, tmp_path):
        """Marker + complete partials at the current tree → the Stop hook runs
        critic-consolidate itself (no model re-run): the fact lands, the marker
        clears, and the healed fact COMPOSES over the session's diff (kernel-v3
        chunk 04 — self-heal feeds the coverage gate rather than bypassing it),
        so the session ends clean. Real git throughout: the dispatch manifest
        and the gate's tree capture must agree on real tree SHAs."""
        repo, prawduct, env = _dispatched_real_repo(tmp_path)
        # Single-pass roster: one "reviewer" partial, then abandon (no
        # consolidate) — the background-by-default failure shape.
        manifest = json.loads(
            (prawduct / ".critic-partials" / "manifest.json").read_text()
        )
        _write_partial(prawduct, "reviewer", commit=manifest["commit_reviewed"])
        result = subprocess.run(
            ["python3", str(HOOK), "stop"],
            capture_output=True, text=True, env=env, cwd=str(repo), timeout=20,
        )
        assert result.returncode == 0, (
            f"complete partials must self-heal to a clean exit. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # Findings cache written by the self-heal; marker cleared; partials consumed.
        assert (prawduct / ".critic-findings.json").is_file()
        assert not (prawduct / ".critic-active").is_file()
        assert not (prawduct / ".critic-partials").exists()
        assert "self-healed" in result.stderr

    def test_incomplete_partials_block_naming_missing(self, tmp_path):
        """Marker + manifest but a missing reviewer → block naming who's missing;
        do NOT self-heal (a partial review must not persist as complete)."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        _write_manifest(prawduct)
        _write_partial(prawduct, "correctness")
        _write_partial(prawduct, "design")
        # sustainability missing.
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2, f"stderr={result.stderr!r}"
        assert "incomplete" in result.stderr.lower()
        assert "sustainability" in result.stderr
        # Nothing persisted; marker + manifest intact for re-dispatch.
        assert not (prawduct / ".critic-findings.json").is_file()
        assert (prawduct / ".critic-partials" / "manifest.json").is_file()

    def test_marker_no_manifest_blocks(self, tmp_path):
        """Marker but no coordinator manifest (a crashed single-pass or
        never-dispatched review) → block, re-run /prawduct:critic."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        # No manifest/partials written.
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert "not completed" in result.stderr.lower()
        assert "no coordinator manifest is present" in result.stderr
        assert "/prawduct:critic" in result.stderr
        assert not (prawduct / ".critic-findings.json").is_file()

    def test_corrupt_manifest_blocks_with_accurate_cause(self, tmp_path):
        """Marker + corrupt manifest → block, but the message must not claim
        'no manifest is present' (the manifest exists; it is unreadable).

        The cause used to read "unreadable or schema-invalid" — one sentence
        for two disks, because this surface computed the distinction itself and
        the refusal surface computed a different (and false) one. Both now read
        `critic_consolidate.manifest_condition`, so this asserts the specific
        cause rather than the disjunction (#676)."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        d = prawduct / ".critic-partials"
        d.mkdir()
        (d / "manifest.json").write_text("{not json")
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert "not completed" in result.stderr.lower()
        assert "not valid JSON" in result.stderr
        assert "OLDER PRAWDUCT" not in result.stderr
        assert "no coordinator manifest is present" not in result.stderr

    def test_stale_schema_manifest_names_the_version_skew(self, tmp_path):
        """The case the source report actually hit (#676): a manifest written by
        a pre-3.3.4 prawduct. It parses; it is not corrupt; and the operator
        must be told which of the two they have, because the remedies differ in
        how much they should trust the partials sitting beside it."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        d = prawduct / ".critic-partials"
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps(V2_MANIFEST))
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert "OLDER PRAWDUCT" in result.stderr
        assert "not valid JSON" not in result.stderr
        assert "no coordinator manifest is present" not in result.stderr
        # This fixture plants the manifest ALONE, so the honest verdict is that
        # there is nothing to preserve. The first cut asserted "are NOT lost"
        # here, pinning a claim that was false in the very disk it built (R-11).
        assert "No reviewer output is on disk" in result.stderr
        # Scoped to the preservation clause, not to the whole message: the
        # escape-hatch text below it names `critic-restore` on every branch and
        # is right to, so a bare "critic-restore not in stderr" tests the wrong
        # sentence.
        assert "reviewer partial(s) ARE on disk" not in result.stderr
        assert "critic-restore" in result.stderr

    def test_stale_schema_with_partials_says_they_are_preserved(self, tmp_path):
        """The other half of the same disk — and the half that matters, because
        an operator told nothing is attached will not run `critic-restore`
        before the archive ring evicts real reviewer output."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        d = prawduct / ".critic-partials"
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps(V2_MANIFEST))
        (d / "correctness.rev-old.json").write_text('{"role": "correctness"}')
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert "OLDER PRAWDUCT" in result.stderr
        assert "1 reviewer partial(s)" in result.stderr
        assert "critic-restore" in result.stderr
        assert "No reviewer output is on disk" not in result.stderr

    def test_the_long_validation_reason_is_not_smuggled_into_the_blocker(self, tmp_path):
        """R-12's SECOND interpolation site, pinned where it actually composes.

        Every other Stop-hook fixture plants `V2_MANIFEST`, whose invalid `mode`
        short-circuits validation into a one-line reason — so `short_detail()`
        is a no-op there and reverting it to the raw `detail` stays green. The
        only reason that matters is the `missing 'rendezvous'` branch: the shape
        a pre-3.3.4 archive actually has, and a ~700-character paragraph
        prescribing its OWN recovery ("/reload-plugins … then `critic-end` …
        then dispatch again"). Printed above this surface's "Re-run the review:
        /prawduct:critic", that is one disk with two recovery stories — which is
        the whole defect #676 is about, arriving through a borrowed string.
        """
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        _write_manifest(prawduct)
        mpath = prawduct / ".critic-partials" / "manifest.json"
        manifest = json.loads(mpath.read_text())
        manifest.pop("rendezvous")
        mpath.write_text(json.dumps(manifest))

        # Fixture guard: this must be the LONG reason, or the test proves nothing.
        sys.path.insert(0, str(ROOT))
        from lib.critic_consolidate import validate_manifest  # noqa: PLC0415
        ok, reason = validate_manifest(manifest)
        assert not ok and "rendezvous" in reason
        assert len(reason) > 200, "fixture guard: expected the remedy-bearing paragraph"

        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert "OLDER PRAWDUCT" in result.stderr
        assert "rendezvous" in result.stderr, "the cause still has to be named"
        # The borrowed reason must not bring its own competing remedy along.
        assert "/reload-plugins" not in result.stderr
        assert "restart the session" not in result.stderr

    def test_the_stop_blocker_carries_the_shared_keep_verdict(self, tmp_path):
        """The fifth `anything_worth_keeping` call site.

        `TestNoSurfacePairsPreservationWithDiscard` composes the other four
        in-process; `cmd_stop`'s is reachable only through the CLI, so it is
        pinned here rather than left to a docstring's claim of "every surface"."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        d = prawduct / ".critic-partials"
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps(V2_MANIFEST))
        (d / "correctness.rev-old.json").write_text('{"role": "correctness"}')

        sys.path.insert(0, str(ROOT))
        from lib.critic_consolidate import anything_worth_keeping  # noqa: PLC0415
        _keep, clause = anything_worth_keeping(prawduct)

        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2
        assert clause in result.stderr, (
            "the blocker must carry the SHARED verdict verbatim, not a local "
            f"paraphrase of it. Expected:\n{clause}\nGot:\n{result.stderr}"
        )

    def test_self_heal_still_no_sweep_on_incomplete(self, tmp_path):
        """The incomplete-block path must not sweep the marker it reads (the
        signal the next Stop re-checks)."""
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        _write_manifest(prawduct)
        _write_partial(prawduct, "correctness")
        _run_stop(tmp_path, status=_CODE_DIFF)
        assert (prawduct / ".critic-active").is_file()


class TestTheEscapeHatchNeverDestroys:
    """Every state that prints the escape hatch is a state holding reviewer output.

    The class, stated as the reason it broke: *one `_escape` string is appended to
    every abandoned-review branch, and each of those branches is reached only when
    reviewer output is on disk.* That sentence names the string, not any one
    branch — so pinning the branches individually would leave the next branch
    someone adds free to ship the old recipe again. These drive all four wedged
    states and assert the property on whatever each one emits.

    `rm -rf .prawduct/.critic-partials` was the shipped advice, on all four. On the
    complete-roster-but-consolidation-failed branch it destroys a review one
    deterministic step from being recorded — the exact loss `boundary_sweep`'s
    roster question and `write_marker`'s guard exist to prevent. `critic-discard`
    reaches the same end state (marker cleared, partials out of the way, next
    dispatch unblocked) and archives, printing `critic-restore <id>`.
    """

    def _stderr_for(self, tmp_path, state: str) -> str:
        prawduct = _active_plan_repo(tmp_path)
        _set_marker(prawduct)
        if state == "complete":
            # The consolidation-FAILED branch, and the one that matters most:
            # every reviewer reported, so the roster is complete, but the
            # partials cannot be consolidated. `pending_state` is presence-only
            # by design (it is the cheap liveness read), so a malformed partial
            # reads as complete and fails inside `consolidate` — which is the
            # real-world shape too. A wrong commit_reviewed does NOT produce this
            # state: the self-heal succeeds and the generic coverage gate fires
            # instead, with no escape hatch in it.
            _write_manifest(prawduct)
            _write_partial(prawduct, "correctness")
            _write_partial(prawduct, "design")
            rid = _review_id(prawduct)
            (prawduct / ".critic-partials" / f"sustainability.{rid}.json").write_text(
                "{not json"
            )
        elif state == "incomplete":
            _write_manifest(prawduct)
            _write_partial(prawduct, "correctness")
        elif state == "unreadable":
            d = prawduct / ".critic-partials"
            d.mkdir()
            (d / "manifest.json").write_text("{not json")
        elif state != "none":
            raise AssertionError(f"unknown wedged state {state!r}")
        result = _run_stop(tmp_path, status=_CODE_DIFF)
        assert result.returncode == 2, (
            f"state={state!r} must block. stderr={result.stderr!r}"
        )
        return result.stderr

    def test_every_wedged_state_names_critic_discard(self, tmp_path):
        for state in ("complete", "incomplete", "none", "unreadable"):
            stderr = self._stderr_for(tmp_path / state, state)
            assert "prawduct-hook critic-discard" in stderr, (
                f"state={state!r} printed an escape hatch that does not name "
                f"critic-discard: {stderr!r}"
            )

    def test_no_wedged_state_recommends_deleting_reviewer_output(self, tmp_path):
        for state in ("complete", "incomplete", "none", "unreadable"):
            stderr = self._stderr_for(tmp_path / state, state)
            for destructive in (
                "rm .prawduct/.critic-active",
                "rm -rf .prawduct/.critic-partials",
                "rm -r .prawduct/.critic-partials",
            ):
                assert destructive not in stderr, (
                    f"state={state!r} recommends {destructive!r} — that discards "
                    f"reviewer output with no archive. Use critic-discard."
                )

    def test_the_escape_hatch_still_names_the_waiver(self, tmp_path):
        """The hatch has two halves and only one of them changed: clearing the
        review, and declaring the waiver that stops the gate re-firing. Dropping
        the second would trade a destructive recipe for an incomplete one."""
        stderr = self._stderr_for(tmp_path, "none")
        assert ".prawduct/.gates-waived" in stderr
        assert '"critic"' in stderr


class TestASelfHealSurvivesTheSessionBoundary:
    """The retention and the self-heal are one behaviour across two invocations.

    Each half passes on its own while the pair is broken, which is how the
    defect shipped: the boundary swept every expired marker, and a review that
    ran long enough to expire one lost the backstop that would have consolidated
    it. Nothing in the boundary's own session could observe that — the cost
    lands on the NEXT invocation, so this is where it has to be asserted.
    """

    def test_a_complete_roster_kept_by_the_boundary_still_self_heals(self, tmp_path):
        repo, prawduct, env = _dispatched_real_repo(tmp_path)
        manifest = json.loads(
            (prawduct / ".critic-partials" / "manifest.json").read_text()
        )
        _write_partial(prawduct, "reviewer", commit=manifest["commit_reviewed"])
        # The review outran the TTL. `_set_marker` stamps a fixed past instant,
        # so "expired" is decided by the stamp alone and every reader here — this
        # process and both subprocesses — reads it against the same wall clock.
        _set_marker(prawduct)

        boundary = subprocess.run(
            ["python3", str(HOOK), "clear", "--session-start"],
            capture_output=True, text=True, env=env, cwd=str(repo), timeout=20,
        )
        assert boundary.returncode == 0, boundary.stderr
        assert (prawduct / ".critic-active").is_file(), (
            "the boundary must keep a complete roster's marker — it is the handle "
            "the backstop below consolidates from"
        )

        # The new session does what a new session does: it edits, and it
        # reflects. The boundary re-captured the git baseline and consumed the
        # reflection, so both have to come back or Stop never reaches the gate
        # under test — and the assertions below would pass on a Stop that judged
        # nothing. A NEW file, because the baseline already carries a modified
        # `src/app.py`: editing it again leaves `git status` byte-identical.
        (repo / "src" / "new.py").write_text("y = 1\n")
        (prawduct / ".session-reflected").write_text(
            "Session reflection: continued after the boundary; suite green."
        )
        result = subprocess.run(
            ["python3", str(HOOK), "stop"],
            capture_output=True, text=True, env=env, cwd=str(repo), timeout=20,
        )

        # The self-heal ran: the review was consolidated, its fact recorded, and
        # the marker cleared by the act that consumed it.
        assert "self-healed" in result.stderr, (
            "the session boundary must not have cost this review its self-heal. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert (prawduct / ".critic-findings.json").is_file()
        assert not (prawduct / ".critic-active").is_file()
        assert not (prawduct / ".critic-partials").exists()
        assert _ABANDONED_MSG not in result.stderr
        assert "CRITIC REVIEW (incomplete)" not in result.stderr
        # Deliberately NOT asserting a clean exit. This session edited a file
        # AFTER the review it healed, so the coverage gate has a real gap to
        # report — a different gate answering a different question. Pinning
        # rc == 0 here would make this test fail whenever the fixture's
        # post-boundary edit changes, for a reason that has nothing to do with
        # whether the boundary preserved the self-heal.


class TestNoShippedSurfaceSanctionsTheBareDelete:
    """The construction, because three per-site pins did not stop a fourth site.

    Guidance sanctioning `rm` of the critic marker or partials has been fixed at
    three separate surfaces in three commits — the marker-refusal remedy,
    `lib/critic_marker`'s own prose, and the Stop hook's escape hatch. Each was
    pinned only where it was found, so each fix left the NEXT surface free to
    reintroduce it. A per-site assertion cannot close a class whose next member
    has not been written yet.

    This derives its subject from the tree instead: every shipped file under
    `plugin/`, matched against the act rather than any one spelling of it. It
    fails on a surface nobody has thought of, which is the whole point.

    Scoped to `plugin/` because that is what consumers execute and read, minus
    the release record: a change-log DESCRIBES the retired recipe, and quoting
    what was removed is how a record works. `.prawduct/change-log.md` is out of
    scope by living outside `plugin/`; `plugin/CHANGELOG.md` ships inside it and
    so is named below. That exemption is one file and is asserted to stay one —
    a record is the only genre where the string is not advice, and widening the
    list is how the class would quietly reopen.
    """

    #: Record-genre files: they quote the retired recipe rather than advise it.
    _RECORD_FILES = frozenset({"CHANGELOG.md"})

    #: The act, not its spellings: an `rm` (any flags) reaching either file.
    #: Backticks are allowed through — a prohibition often quotes the command
    #: it forbids, and relying on punctuation to tell those apart is what made
    #: the first cut of this pin fire on the sentence doing the forbidding.
    _NAMES_THE_ACT = re.compile(
        r"\brm\b[^\n]{0,40}?\.(?:prawduct/\.)?critic-(?:active|partials)"
    )

    #: What separates advice from prohibition is the sentence's stance, so that
    #: is what is matched — not the presence of backticks around the command.
    #: A line that tells you NOT to do it is the pin working, not a violation.
    #: Prohibition markers only. A bare ``not`` was deliberately left out: it is
    #: common enough that it would excuse a genuine recommendation that happened
    #: to contain one, and every prohibition this guards actually leads with one
    #: of these.
    _FORBIDS = re.compile(
        r"\b(?:do not|don't|never|must not|no longer|rather than|instead of)\b",
        re.IGNORECASE,
    )

    def _sanctions_delete(self, line: str) -> bool:
        """Does this line RECOMMEND the delete, as opposed to forbidding it?

        The residual bypass is stated rather than left to be discovered: a line
        that both recommends the act and happens to contain a negation ("do not
        wait — rm .prawduct/.critic-partials") reads as a prohibition here. That
        is the safe direction for a *style* pin and the wrong one for a security
        check; this is the former. Narrowing it further would cost the property
        that makes the pin worth having, which is that it needs no maintenance
        as surfaces are reworded.
        """
        return bool(self._NAMES_THE_ACT.search(line)) and not self._FORBIDS.search(line)

    def _shipped_files(self) -> list[Path]:
        skip = {".git", "__pycache__", ".critic-partials", ".critic-partials-archive"}
        out = [
            p
            for p in ROOT.rglob("*")
            if p.is_file()
            and p.suffix in {".py", ".md", ".json", ""}
            and not any(part in skip for part in p.parts)
        ]
        assert len(out) > 20, f"tree walk found only {len(out)} files — wrong root?"
        return out

    def test_the_record_exemption_stays_one_file(self):
        """A one-file exemption is a judgement; a growing one is a loophole."""
        assert self._RECORD_FILES == {"CHANGELOG.md"}, (
            "the record-genre exemption grew. Each added file is a surface this "
            "pin no longer protects — justify it here or drop it."
        )

    def test_no_shipped_file_recommends_deleting_the_marker_or_partials(self):
        offenders: list[str] = []
        for path in self._shipped_files():
            if path.name in self._RECORD_FILES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if self._sanctions_delete(line):
                    rel = path.relative_to(ROOT.parent)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        assert not offenders, (
            "a shipped surface tells the operator to delete the critic marker or "
            "partials by hand. That destroys a roster that may be one "
            "consolidation from being recorded, and says nothing. Use "
            "`prawduct-hook critic-discard`, which archives and can be restored.\n  "
            + "\n  ".join(offenders)
        )

    def test_the_pattern_actually_matches_the_recipe_it_retired(self):
        """The pin above passes when the tree is clean AND when the pattern is
        broken. This tells the two apart by feeding it the exact string that
        shipped in v3.3.4, plus the spellings a re-introduction would plausibly
        use."""
        for shipped in (
            "    rm .prawduct/.critic-active",
            "    rm -rf .prawduct/.critic-partials",
            "rm -r .prawduct/.critic-partials",
            "run `rm .critic-active` to clear it",
        ):
            assert self._sanctions_delete(shipped), (
                f"the pattern cannot see {shipped!r} — it would pass over a "
                "reintroduction of the very recipe it exists to catch"
            )
        for innocent in (
            "critic-discard archives the partials rather than deleting them",
            "the marker is removed by name — critic-end, critic-discard",
            # The live PROHIBITION, quoted from the escape hatch it guards.
            # Today only the backticks keep the pattern off it, which is
            # incidental rather than designed — a rewording that drops them
            # would make this pin fire on the sentence forbidding the act.
            # Listed so that rewording fails HERE, next to the reason, rather
            # than as a mystery failure in the sweep above.
            "Do not `rm` the marker or .critic-partials by hand: most states",
            "Do not rm the marker or .critic-partials by hand",
        ):
            assert not self._sanctions_delete(innocent), (
                f"the pattern fires on {innocent!r} — a pin that cries wolf gets "
                "waived, which is how the class reopens"
            )
