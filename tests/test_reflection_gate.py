"""The Stop hook's reflection gate — what makes it fire, and what it grades.

Two things changed and both are pinned here.

**What makes it fire.** The gate used to ask "is a build plan active, and is
porcelain dirty?" Both were wrong in the same direction. A planless session that
wrote and committed code — the ordinary shape of a bug fix, a sweep, a
one-file change nobody drew a plan for — got an advisory note and ended in
silence, so the sessions least likely to have a plan were the ones whose lesson
was never written down. And porcelain empties the moment you commit, so even a
planned session could satisfy the gate by committing first. It now asks one
question of `gates.session_work_span`: did this session author judgeable code
between its base tree and the working tree, committed work included — history
a pull, merge or branch switch brought in is not its work
(`TestMovesThisSessionDidNotAuthor`).

**What it grades.** The old floor was fifty characters, which graded nothing —
"did the chunk, tests green, shipping it" cleared it, and so did two hundred
characters of the same. It now grades SHAPE
(`gates.reflection_shape`): the text must name what was expected and what was
actual, plus a root cause or its explicit absence. Substring tests, deliberately
the weakest check that can tell the two shapes apart, because anything stronger
grades phrasing rather than whether the work was done.

**The Critic gate reads the same span, pinned in `TestTheCriticGuardReadsTheSpan`.**
Its firing guard and its doc-only carveout moved onto `session_work_span`
together (#304), so a pull-only session leaves both silent.

Fixture shape mirrors `tests/test_learnings_cutover_gate.py`: a real git repo,
`cmd_stop` called in-process, stderr read back.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"

sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import SHAPED_REFLECTION  # noqa: E402 — one home for the shape
from lib import gates  # noqa: E402

_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_reflection_gate", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader(
    "prawduct_hook_reflection_gate", _hook_loader
)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)

#: The blocker's opening word — anchored on, rather than on a paragraph, so a
#: wording fix does not read as a regression.
BLOCKER = "REFLECTION:"

#: The two missing-line phrases the blocker prints, sourced from the module that
#: produces them. Re-typing them here would be a second copy of the contract
#: that could agree with itself while disagreeing with the gate.
MISSING_EXPECTED_VS_ACTUAL = gates._REFLECTION_EXPECTED_VS_ACTUAL
MISSING_ROOT_CAUSE = gates._REFLECTION_ROOT_CAUSE

#: Advisory ids and prawduct-internal requirement ids may not appear in
#: operator-emitted text (same rule, same shapes, as the cutover-gate file).
_ID_SHAPES = (
    re.compile(r"-v\d+-[0-9a-f]{6}\b"),
    re.compile(r"\b[A-Z]{3}-[A-Z0-9]{4}\b"),
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """A committed repo with no build plan, no reflection and no base marker.

    No build plan on purpose: it is what the gate used to require, so its
    absence is what every "fires anyway" assertion below is about.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    (repo / "notes.md").write_text("notes\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    (repo / ".prawduct").mkdir()
    # The session baseline, as `cmd_clear` records it at session start. Without
    # one, `git_has_session_changes` falls through to `git_has_changes`, which
    # does no metadata filtering — so the fixture's own `.prawduct/` scratch
    # would read as session work and the Critic gate would fire on it. That is
    # pre-existing fallback behaviour, not this gate's, and a fixture that trips
    # it is measuring the fallback rather than the subject.
    (repo / ".prawduct" / ".session-git-baseline").write_text(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo), capture_output=True, text=True, check=True,
        ).stdout
    )
    return repo


def _mark_base(repo: Path) -> str:
    """Record `HEAD^{tree}` as `.session-base-tree`, the way `cmd_clear` does at
    session start. Called BEFORE the work, so the marker is the session's
    "before" and anything committed after it is inside the span."""
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    (repo / ".prawduct" / ".session-base-tree").write_text(tree)
    return tree


def _commit_code(repo: Path) -> None:
    (repo / "code.py").write_text("x = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2")


def _commit_doc(repo: Path) -> None:
    (repo / "notes.md").write_text("notes, revised\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2")


def _reflect(repo: Path, text: str) -> None:
    (repo / ".prawduct" / ".session-reflected").write_text(text)


def _stop(repo: Path, capsys) -> tuple[int, str]:
    rc = _hook.cmd_stop(repo, {})
    return rc, capsys.readouterr().err


# ---------------------------------------------------------------------------
# The widening: a planless, committed session
# ---------------------------------------------------------------------------


class TestTheGateFiresOnCommittedPlanlessWork:
    def test_committed_code_with_no_plan_and_no_reflection_blocks(
        self, tmp_path, capsys
    ):
        """The target case (#685). Nothing here is uncommitted and nothing is
        planned, which is exactly why the old gate said nothing."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err

    def test_the_blocker_names_both_missing_lines(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        _, err = _stop(repo, capsys)
        assert MISSING_EXPECTED_VS_ACTUAL in err
        assert MISSING_ROOT_CAUSE in err

    def test_a_shaped_reflection_passes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        _reflect(repo, SHAPED_REFLECTION)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_two_hundred_shapeless_characters_still_block(self, tmp_path, capsys):
        """The floor this replaced: length was never evidence. This text is four
        times the old floor and says nothing the gate asked for."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        filler = "Worked on the chunk today and it went fine, shipping it now. " * 4
        assert len(filler) > 200
        _reflect(repo, filler)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err

    def test_an_untracked_new_file_is_inside_the_span(self, tmp_path, capsys):
        """`git diff <base-tree>` cannot see a file that is in no tree, so the
        span reads the porcelain `??` lines too. Without that, a session whose
        whole output is a brand-new module ends silent."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        (repo / "brand_new.py").write_text("y = 1\n")
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err


class _Session:
    """A session whose start is pinned on the clock, so the reflog can tell
    history made before it from moves made during it.

    The span bounds its reflog walk by the base-tree marker's mtime, and git
    stamps reflog entries with the committer date. Fixture history is written at
    the real clock; the session's marker and every git move it makes sit
    minutes later, so no fixture step can land in the session's first second
    and be read as the session's own.
    """

    def __init__(self, repo: Path):
        self.repo = repo
        self.started = int(time.time()) + 600
        _mark_base(repo)
        marker = repo / ".prawduct" / ".session-base-tree"
        os.utime(marker, (self.started, self.started))

    def git(self, *args: str) -> str:
        env = dict(os.environ, GIT_COMMITTER_DATE=f"@{self.started + 60} +0000")
        return subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(self.repo), capture_output=True, text=True, timeout=15,
            check=True, env=env,
        ).stdout.strip()


def _their_branch(repo: Path, path: str = "theirs.py") -> None:
    """Someone else's commit on `other`, made before the session; `main` checked
    back out. `add <path>`, not `add -A`: `-A` would stage the untracked
    `.prawduct/` too, and checking `main` back out would then delete the
    session state the fixture is about to write."""
    _git(repo, "checkout", "-q", "-b", "other")
    (repo / path).write_text("their_work = 1\n")
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", "someone else's commit")
    _git(repo, "checkout", "-q", "main")


class TestMovesThisSessionDidNotAuthor:
    """Moves that bring in history this session did not write are not its work.

    The span used to be base tree → working tree with no authorship test, so a
    pull, merge or branch switch mid-session fired the reflection gate — and,
    under an active plan, the Critic gate — on files nobody in the session
    touched. That was a recorded assumption, priced at "asking git who wrote
    each hunk on every turn". HEAD's reflog answers it far more cheaply: it
    records why HEAD moved. These cases were the documented false fire and are
    now silent; the ones below them keep the session's own commits firing.
    """

    def test_a_no_ff_merge_of_their_branch_is_silent(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("merge", "-q", "--no-ff", "-m", "merge other", "other")

        span = gates.session_work_span(repo)
        assert span["source"] == "base-tree"
        assert "theirs.py" not in span["changed"]
        rc, err = _stop(repo, capsys)
        assert rc == 0, err
        assert BLOCKER not in err

    def test_a_fast_forward_pull_is_silent(self, tmp_path):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("pull", "-q", "--no-rebase", ".", "other")
        assert (repo / "theirs.py").is_file()
        assert gates.session_work_span(repo)["changed"] == []

    def test_switching_to_their_branch_is_silent(self, tmp_path):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("checkout", "-q", "other")
        assert gates.session_work_span(repo)["changed"] == []

    def test_a_hard_reset_onto_their_commit_is_silent(self, tmp_path):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("reset", "-q", "--hard", "other")
        assert gates.session_work_span(repo)["changed"] == []

    def test_a_session_commit_still_fires_beside_a_pull(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        (repo / "code.py").write_text("x = 2\n")
        s.git("commit", "-q", "-am", "mine")
        s.git("pull", "-q", "--no-rebase", "--no-edit", ".", "other")

        span = gates.session_work_span(repo)
        assert span["changed"] == ["code.py"]
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err

    def test_a_rebased_session_commit_still_fires(self, tmp_path):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        (repo / "code.py").write_text("x = 2\n")
        s.git("commit", "-q", "-am", "mine")
        s.git("rebase", "-q", "other")
        assert gates.session_work_span(repo)["changed"] == ["code.py"]

    def test_a_hand_concluded_merge_counts_only_what_it_resolved(self, tmp_path):
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "other")
        (repo / "code.py").write_text("x = 'theirs'\n")
        (repo / "theirs.py").write_text("their_work = 1\n")
        _git(repo, "add", "code.py", "theirs.py")
        _git(repo, "commit", "-q", "-m", "their conflicting commit")
        _git(repo, "checkout", "-q", "main")
        (repo / "code.py").write_text("x = 'ours'\n")
        _git(repo, "commit", "-q", "-am", "our side, before the session")

        s = _Session(repo)
        # The identity matters even though a conflicted merge commits nothing:
        # git checks it before merging, so without one (a runner with no global
        # config) the merge refuses outright and there is nothing to conclude.
        merge = subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "merge", "-q", "other"],
            cwd=str(repo), capture_output=True,
        )
        assert merge.returncode != 0, "fixture must conflict"
        assert (repo / ".git" / "MERGE_HEAD").is_file(), merge.stderr
        (repo / "code.py").write_text("x = 'resolved'\n")
        s.git("add", "code.py")
        s.git("commit", "-q", "--no-edit")

        assert gates.session_work_span(repo)["changed"] == ["code.py"]

    def test_uncommitted_work_on_their_branch_still_fires(self, tmp_path):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("checkout", "-q", "other")
        (repo / "theirs.py").write_text("edited in session\n")
        assert gates.session_work_span(repo)["changed"] == ["theirs.py"]

    def test_an_unrecognised_reflog_subject_keeps_the_whole_span(self, tmp_path):
        """git's reflog wording is not a contract. A move the classifier cannot
        name gives up on authorship and answers the base-tree span."""
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("update-ref", "-m", "frobnicate: something new", "HEAD", "other")
        s.git("reset", "-q", "--hard")
        assert gates.session_work_span(repo)["changed"] == ["theirs.py"]

    def test_a_failing_reflog_keeps_the_whole_span(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("merge", "-q", "--no-ff", "-m", "merge other", "other")
        real = gates.evidence.run_git

        def _no_reflog(project_dir, *args, **kwargs):
            if args and args[0] == "reflog":
                return 1, "", "simulated failure"
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(gates.evidence, "run_git", _no_reflog)
        assert gates.session_work_span(repo)["changed"] == ["theirs.py"]

    def test_no_reflog_read_while_heads_tree_is_unmoved(self, tmp_path, monkeypatch):
        """The Stop path runs every turn: a session that has not moved HEAD's
        tree pays one `rev-parse` and never walks the reflog."""
        repo = _repo(tmp_path)
        _Session(repo)
        (repo / "code.py").write_text("x = 2\n")
        calls: list[str] = []
        real = gates.evidence.run_git

        def _recording(project_dir, *args, **kwargs):
            calls.append(args[0] if args else "")
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(gates.evidence, "run_git", _recording)
        assert gates.session_work_span(repo)["changed"] == ["code.py"]
        assert "rev-parse" in calls, "the guard must have been reached"
        assert "reflog" not in calls and "diff-tree" not in calls


# ---------------------------------------------------------------------------
# What stays silent
# ---------------------------------------------------------------------------


class TestTheGateStaysQuiet:
    def test_a_committed_doc_only_change_is_silent(self, tmp_path, capsys):
        """The companion trap (#304's comment): widening the trigger to
        committed work while asking a PORCELAIN question about docs makes this
        session fire. Porcelain is empty here — the doc change is committed — so
        a `doc_only` read from it is False, and only a span-derived one is
        right."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_doc(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_a_metadata_only_session_is_silent(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _mark_base(repo)
        (repo / ".prawduct" / "scratch.txt").write_text("state\n")
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_a_session_that_changed_nothing_is_silent(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _mark_base(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_the_waiver_key_suppresses_the_blocker(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        (repo / ".prawduct" / ".gates-waived").write_text(
            json.dumps({"reflection": "spike branch, discarded at the end"})
        )
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err
        assert "reflection: waived" in err


# ---------------------------------------------------------------------------
# The fallback, pinned: no marker means exactly today's behaviour
# ---------------------------------------------------------------------------


class TestTheNoMarkerFallback:
    def test_no_marker_plus_dirty_porcelain_blocks(self, tmp_path, capsys):
        """Today's behaviour, unchanged: with no base tree the span degrades to
        the porcelain one, which still sees an uncommitted code edit."""
        repo = _repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err
        assert gates.session_work_span(repo)["source"] == "porcelain"

    def test_the_blocker_says_when_it_read_porcelain_only(self, tmp_path, capsys):
        """`source` is part of the span's contract, and this is its consumer: a
        blocker that fired off the degraded span says so, because the same
        session's COMMITTED work was invisible to it and the reader owes the
        operator that difference (the degradation used to be announced for the
        Critic gate only)."""
        repo = _repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert "uncommitted changes only" in err
        assert "no .prawduct/.session-base-tree" in err

    def test_no_marker_plus_committed_change_is_silent(self, tmp_path, capsys):
        """The other half of today's behaviour, and the direction that matters:
        degrading SHRINKS this gate's jurisdiction to uncommitted work. It never
        widens it, which is how authority is allowed to fail."""
        repo = _repo(tmp_path)
        _commit_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err
        assert gates.session_work_span(repo)["source"] == "porcelain"

    def test_a_malformed_marker_never_reaches_git_argv(self, tmp_path, monkeypatch):
        """A hand-edited or truncated marker is not a tree id, and the point of
        rejecting it here is that it never becomes an argument.

        Asserting only on the returned span cannot see that: git refuses the
        value too, so the span degrades to porcelain either way and the test
        passes with the shape guard deleted. The assertion is therefore over
        what reaches argv — the thing the guard actually controls.
        """
        from lib import evidence

        repo = _repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").write_text("--upload-pack=evil")
        _commit_code(repo)

        seen: list[tuple] = []
        real = evidence.run_git

        def spy(project_dir, *args, **kwargs):
            seen.append(args)
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(evidence, "run_git", spy)
        span = gates.session_work_span(repo)

        assert span["source"] == "porcelain"
        assert span["judgeable"] is False
        assert not any("--upload-pack=evil" in a for call in seen for a in call), seen

    def test_an_unresolvable_tree_id_degrades(self, tmp_path):
        """Well-formed but not in this repo — `git diff` fails, and a failed
        diff is not an empty one."""
        repo = _repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").write_text("0" * 40)
        _commit_code(repo)
        assert gates.session_work_span(repo)["source"] == "porcelain"


# ---------------------------------------------------------------------------
# The message
# ---------------------------------------------------------------------------


class TestTheBlockerText:
    def test_with_a_marker_the_blocker_does_not_claim_porcelain(self, tmp_path, capsys):
        """The positive control for the porcelain clause: with the marker in
        place the span is the real one and the clause must not appear."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        (repo / "code.py").write_text("x = 2\n")
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err
        assert "uncommitted changes only" not in err


    def _err(self, tmp_path, capsys) -> str:
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        return _stop(repo, capsys)[1]

    def test_it_names_the_waiver_key(self, tmp_path, capsys):
        assert '{"reflection": "reason — be specific"}' in self._err(tmp_path, capsys)

    def test_it_names_where_a_durable_rule_goes(self, tmp_path, capsys):
        assert ".claude/rules/learnings/" in self._err(tmp_path, capsys)

    def test_it_never_mentions_a_character_count(self, tmp_path, capsys):
        """The gate does not count characters, so the message must not imply it
        does — an operator who reads "50" pads the file and blocks again."""
        err = self._err(tmp_path, capsys)
        block = err[err.index(BLOCKER):]
        assert "50" not in block
        assert "character" not in block.lower()

    def test_it_does_not_promise_an_archive(self, tmp_path, capsys):
        """`reflections.md` is not written any more; a message naming it sends
        the reader to a file that will not appear."""
        err = self._err(tmp_path, capsys)
        assert "reflections.md" not in err[err.index(BLOCKER):]

    def test_it_carries_no_internal_ids(self, tmp_path, capsys):
        err = self._err(tmp_path, capsys)
        block = err[err.index(BLOCKER):]
        block = block[: block.index("\n\n  Escape hatch")]
        for shape in _ID_SHAPES:
            assert not shape.search(block), f"id-shaped token in blocker: {block}"

    def test_the_waiver_recipe_follows_the_blockers_once(self, tmp_path, capsys):
        """The recipe is one footer after the `BLOCKED` list, not a paragraph
        inside each blocker — a copy per blocker made the waiver the loudest
        thing in a two-gate block."""
        err = self._err(tmp_path, capsys)
        assert err.count("Escape hatch") == 1, err
        assert err.index(BLOCKER) < err.index("Escape hatch")


# ---------------------------------------------------------------------------
# The waiver footer, every branch
# ---------------------------------------------------------------------------


def _echoed_waiver(footer: str) -> dict:
    """The JSON object the footer's `echo` line would write."""
    (line,) = [ln for ln in footer.splitlines() if ln.strip().startswith("echo '")]
    return json.loads(shlex.split(line)[1])


class TestTheWaiverFooter:
    def test_every_blocking_waivable_gate_lands_in_one_object(self):
        """Two `echo … >` lines, one per blocker, overwrite each other's file;
        one object carries both keys and survives being run."""
        footer = _hook._waiver_footer(["reflection", "critic", "critic"], False)
        assert footer.count("echo '") == 1
        assert set(_echoed_waiver(footer)) == {"reflection", "critic"}

    def test_a_gate_is_named_by_its_waiver_key_not_its_id(self):
        footer = _hook._waiver_footer(["learnings-unmigrated"], False)
        assert set(_echoed_waiver(footer)) == {"learnings"}

    def test_the_printed_recipe_clears_the_block_it_was_printed_for(
        self, tmp_path, capsys
    ):
        """The recipe is only a remedy if running it reaches the gate: write
        the object the block printed, with a real reason, and stop again."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        footer = err[err.index("  Escape hatch"):]
        waiver = {k: "probe: recipe round-trip" for k in _echoed_waiver(footer)}
        (repo / ".prawduct" / ".gates-waived").write_text(json.dumps(waiver))
        rc, err = _stop(repo, capsys)
        assert rc == 0, err

    def test_nothing_waivable_prints_no_footer(self):
        """The budget floor and the clear verdict have no waiver, so a block
        made only of them offers none."""
        for gate_ids in ([], ["clear-verdict"], ["learnings-over-budget", None]):
            assert _hook._waiver_footer(gate_ids, True) == "", gate_ids

    def test_a_waiver_already_in_the_file_survives_the_printed_recipe(
        self, tmp_path, capsys
    ):
        """The recipe replaces the file, so it must carry what is already
        there: a waiver declared at an earlier Stop, dropped by the next
        recipe, re-blocks its gate and sends the reader round a loop."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        waived = repo / ".prawduct" / ".gates-waived"
        waived.write_text(json.dumps({"pr": "merge is not happening today"}))
        rc, err = _stop(repo, capsys)
        assert rc == 2
        recipe = _echoed_waiver(err[err.index("  Escape hatch"):])
        assert recipe["pr"] == "merge is not happening today"
        assert "reflection" in recipe

    def test_every_gate_reads_its_waiver_key_from_the_map(self):
        """The footer prints keys from `_WAIVER_KEY_BY_GATE`; a gate that
        tested a typed literal instead could drift from it, and the printed
        recipe would then stop clearing that gate with the suite green."""
        source = (_ROOT / "bin" / "prawduct-hook").read_text()
        typed = [
            key for key in set(_hook._WAIVER_KEY_BY_GATE.values())
            if f'"{key}" in waivers' in source or f"waivers['{key}']" in source
        ]
        assert not typed, f"waiver keys typed at a check site: {sorted(typed)}"
        assert "_WAIVER_KEY_BY_GATE[\"reflection\"] in waivers" in source

    def test_a_pending_review_is_discarded_never_deleted(self):
        footer = _hook._waiver_footer(["critic"], True)
        assert "prawduct-hook critic-discard" in footer
        assert "critic-restore <id>" in footer

    def test_the_discard_step_needs_both_a_pending_review_and_a_critic_block(self):
        assert "critic-discard" not in _hook._waiver_footer(["critic"], False)
        assert "critic-discard" not in _hook._waiver_footer(["reflection"], True)


# ---------------------------------------------------------------------------
# The Critic composition gate reads the same span (#304)
# ---------------------------------------------------------------------------


class TestTheCriticGuardReadsTheSpan:
    """The Critic gate's firing guard used to be porcelain, so a session that
    committed its work ended without the composition verdict. It now reads
    `session_work_span` — the same span, read once, as the reflection gate —
    and its doc-only carveout moves with it."""

    def _plan_repo(self, tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Demo\n"
        )
        return repo

    @staticmethod
    def _verdict_says_uncovered(monkeypatch) -> None:
        """Force the composition verdict to the blocking answer, so the GUARD is
        the only variable: on a fresh single-branch fixture the real verdict
        composes to `covered` through the merge-base fallback."""
        monkeypatch.setattr(
            gates,
            "session_review_verdict",
            lambda *_a, **_k: {"status": "uncovered", "reason": "no composed review coverage"},
        )

    def test_a_committed_change_fires_the_critic_gate(
        self, tmp_path, capsys, monkeypatch
    ):
        """Active plan, committed judgeable change, clean porcelain, no review:
        the case the porcelain guard left silent."""
        repo = self._plan_repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        _reflect(repo, SHAPED_REFLECTION)
        self._verdict_says_uncovered(monkeypatch)
        assert _git(repo, "status", "--porcelain", "--", "code.py") == ""

        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert "gate: critic" in err
        assert "CRITIC" in err

    def test_a_committed_change_with_no_review_fact_blocks_on_the_real_verdict(
        self, tmp_path, capsys
    ):
        """The same case with nothing forced: a feature branch whose own diff no
        review covers."""
        repo = self._plan_repo(tmp_path)
        (repo / ".gitignore").write_text(".prawduct/\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "ignore")
        _git(repo, "checkout", "-q", "-b", "feature")
        _mark_base(repo)
        _commit_code(repo)
        _reflect(repo, SHAPED_REFLECTION)

        rc, err = _stop(repo, capsys)
        assert rc == 2, err
        assert "gate: critic" in err

    def test_a_pull_only_session_leaves_it_silent(
        self, tmp_path, capsys, monkeypatch
    ):
        """The Critic guard reads the same span, so a session that only pulled
        under an active plan owes no review round for history it did not
        write — the costlier half of the false fire."""
        repo = self._plan_repo(tmp_path)
        _their_branch(repo)
        s = _Session(repo)
        s.git("merge", "-q", "--no-ff", "-m", "merge other", "other")
        self._verdict_says_uncovered(monkeypatch)

        rc, err = _stop(repo, capsys)
        assert rc == 0, err
        assert "gate: critic" not in err

    def test_a_committed_designer_handoff_chunk_still_skips_it(
        self, tmp_path, capsys, monkeypatch
    ):
        """The `Type: designer-handoff` carveout is read under the same span as
        the guard, so widening the guard to committed work does not drop it."""
        repo = self._plan_repo(tmp_path)
        (repo / ".prawduct" / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Demo\n\n"
            "### Chunk 01: Demo\n**Type:** designer-handoff\n\nBody.\n"
        )
        _mark_base(repo)
        _commit_code(repo)
        _reflect(repo, SHAPED_REFLECTION)
        self._verdict_says_uncovered(monkeypatch)

        rc, err = _stop(repo, capsys)
        assert rc == 0, err
        assert "CRITIC" not in err
        assert "designer-handoff" in err

    def test_a_committed_doc_only_change_leaves_it_silent(
        self, tmp_path, capsys, monkeypatch
    ):
        """The companion trap: widening the trigger without moving `doc_only`
        onto the span makes a docs-only committed session fire."""
        repo = self._plan_repo(tmp_path)
        _mark_base(repo)
        _commit_doc(repo)
        self._verdict_says_uncovered(monkeypatch)

        rc, err = _stop(repo, capsys)
        assert rc == 0, err
        assert "CRITIC" not in err

    def test_a_merge_of_the_base_over_covered_work_leaves_it_silent(
        self, tmp_path, capsys
    ):
        """Merge-only: the branch's own diff is covered by a cumulative review;
        the session merges the base, bringing judgeable files nobody here wrote.
        The verdict's merge-base fallback confines the demand to the branch's
        own work, so the gate passes."""
        from lib import evidence

        repo = self._plan_repo(tmp_path)
        (repo / ".gitignore").write_text(".prawduct/\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "ignore")
        _git(repo, "checkout", "-q", "-b", "feature")
        (repo / "feature.py").write_text("y = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "feature work")
        result = evidence.append_fact(
            repo,
            "review",
            "rev-cumulative-0001",
            {
                "base_tree": _git(repo, "rev-parse", "main^{tree}"),
                "head_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
                "files_changed": ["feature.py"],
                "files_reviewed": ["feature.py"],
                "findings": [],
            },
        )
        assert result["status"] == "appended", result
        _mark_base(repo)  # the session opens on the reviewed branch tip
        _git(repo, "checkout", "-q", "main")
        (repo / "upstream.py").write_text("z = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base advances")
        _git(repo, "checkout", "-q", "feature")
        _git(repo, "merge", "-q", "--no-edit", "main")
        _reflect(repo, SHAPED_REFLECTION)
        # The base-advance transfer needs a saved suite run at this tree — the
        # remedy `/prawduct:pr` would demand anyway, not a review round.
        capture = evidence.capture_tree(repo)
        assert capture["status"] == "ok", capture
        (repo / ".prawduct" / ".test-evidence.json").write_text(json.dumps({
            "timestamp": "2026-08-13T12:00:00Z",
            "passed": 1, "failed": 0, "skipped": 0, "duration_seconds": 1,
            "command": "pytest",
            "verifier": "test-reference-verify (floor: symbol-grep)",
            "tests_executed": ["tests/test_x.py"],
            "changes_referenced": ["feature.py"],
            "coverage_level": "referenced",
            "evidence_tree": capture["tree"],
        }))
        assert gates.session_work_span(repo)["judgeable"] is True, (
            "the merge must put judgeable work in the span, or the pass proves nothing"
        )

        rc, err = _stop(repo, capsys)
        assert rc == 0, err
        assert "CRITIC" not in err

    def test_without_a_base_marker_a_committed_change_stays_silent(
        self, tmp_path, capsys, monkeypatch
    ):
        """Missing `.session-base-tree`: the span degrades to porcelain, so the
        guard behaves as the porcelain guard did — committed work unseen."""
        repo = self._plan_repo(tmp_path)
        _commit_code(repo)
        _reflect(repo, SHAPED_REFLECTION)
        self._verdict_says_uncovered(monkeypatch)
        assert gates.session_work_span(repo)["source"] == "porcelain"

        rc, err = _stop(repo, capsys)
        assert rc == 0, err
        assert "CRITIC" not in err

    def test_without_a_base_marker_a_dirty_change_still_fires(
        self, tmp_path, capsys, monkeypatch
    ):
        """The control for the test above: the porcelain answer still fires on
        uncommitted work, so that silence is the degraded span's, not a fixture
        the gate could never fire on."""
        repo = self._plan_repo(tmp_path)
        (repo / "code.py").write_text("x = 2\n")   # dirty, not committed
        _reflect(repo, SHAPED_REFLECTION)
        self._verdict_says_uncovered(monkeypatch)

        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert "CRITIC" in err


# ---------------------------------------------------------------------------
# `reflection_shape` — each conjunct on its own
# ---------------------------------------------------------------------------


class TestReflectionShape:
    def test_all_three_present_is_ok(self):
        ok, missing = gates.reflection_shape(
            "Expected a clean merge; actual: three conflicts. Root cause: stale base."
        )
        assert ok and missing == []

    def test_missing_expected_blocks(self):
        """`actual` and a cause, no `expected` — the conjunct on its own."""
        ok, missing = gates.reflection_shape(
            "The actual outcome was three conflicts. Root cause: a stale base."
        )
        assert not ok
        assert missing == [MISSING_EXPECTED_VS_ACTUAL]

    def test_missing_actual_blocks(self):
        ok, missing = gates.reflection_shape(
            "I expected a clean merge. Root cause: a stale base."
        )
        assert not ok
        assert missing == [MISSING_EXPECTED_VS_ACTUAL]

    def test_missing_cause_blocks(self):
        ok, missing = gates.reflection_shape(
            "Expected a clean merge; actual: three conflicts."
        )
        assert not ok
        assert missing == [MISSING_ROOT_CAUSE]

    def test_empty_text_reports_both(self):
        ok, missing = gates.reflection_shape("")
        assert not ok
        assert missing == [MISSING_EXPECTED_VS_ACTUAL, MISSING_ROOT_CAUSE]

    def test_a_non_string_is_treated_as_empty(self):
        """The docstring says it never raises; a caller that read nothing hands
        it None, and the answer must be the blocking one."""
        ok, missing = gates.reflection_shape(None)
        assert not ok and len(missing) == 2

    def test_each_cause_spelling_is_accepted(self):
        for spelling in ("root cause", "root-cause", "no defect"):
            ok, _ = gates.reflection_shape(f"expected x, actual y, {spelling} z")
            assert ok, spelling

    def test_the_check_is_case_insensitive(self):
        ok, _ = gates.reflection_shape("EXPECTED x. ACTUAL y. NO DEFECT.")
        assert ok


# ---------------------------------------------------------------------------
# `session_work_span` — the span itself
# ---------------------------------------------------------------------------


class TestSessionWorkSpan:
    def test_the_base_tree_span_reports_its_source_and_paths(self, tmp_path):
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        span = gates.session_work_span(repo)
        assert span["source"] == "base-tree"
        assert "code.py" in span["changed"]
        assert span["judgeable"] is True

    def test_metadata_paths_are_dropped_from_the_span(self, tmp_path):
        repo = _repo(tmp_path)
        _mark_base(repo)
        (repo / ".prawduct" / "scratch.txt").write_text("state\n")
        span = gates.session_work_span(repo)
        assert not any(p.startswith(".prawduct/") for p in span["changed"])
        assert span["judgeable"] is False

    def test_a_doc_only_span_is_not_judgeable_but_is_not_empty(self, tmp_path):
        """`judgeable` and "nothing changed" are different answers, and the gate
        needs the first. A doc change is IN the span and does not fire it."""
        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_doc(repo)
        span = gates.session_work_span(repo)
        assert span["changed"] == ["notes.md"]
        assert span["judgeable"] is False

    def test_its_git_calls_are_bounded_by_what_the_session_did(
        self, tmp_path, monkeypatch
    ):
        """The requirement is a COST — this gate runs on every turn — so the
        assertion is over the operations that cost, not over a side effect that
        usually accompanies them.

        Two readers below need the porcelain snapshot and each would spawn its
        own `git status` if the span did not take one and thread it. Pass the
        snapshot in (what `cmd_stop` does) and even that goes away. `capture_tree`
        must not appear at all: it writes an index file and walks the whole tree,
        which is a review-time cost, not a per-turn one.

        The bound used to be one `git diff`. Telling the session's own commits
        from history a pull or branch switch brought in costs more, and only
        when there is something to tell: an empty span stops at the diff, an
        unmoved HEAD tree at one `rev-parse`, and a moved one reads the reflog,
        diffs the session's commits in one batch, and diffs the working tree.
        """
        from lib import evidence, gitstate

        repo = _repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)

        git_calls: list[tuple] = []
        real_run_git = evidence.run_git
        real_status = gitstate.git_status_output

        def spy_run_git(project_dir, *args, **kwargs):
            git_calls.append(args)
            return real_run_git(project_dir, *args, **kwargs)

        def spy_status(project_dir):
            git_calls.append(("status",))
            return real_status(project_dir)

        def forbidden_capture(*_a, **_k):  # pragma: no cover - must not run
            raise AssertionError("session_work_span must not capture a tree")

        monkeypatch.setattr(evidence, "run_git", spy_run_git)
        monkeypatch.setattr(gitstate, "git_status_output", spy_status)
        monkeypatch.setattr(evidence, "capture_tree", forbidden_capture)

        moved = ["rev-parse", "reflog", "diff-tree", "diff"]
        gates.session_work_span(repo)
        assert [c[0] for c in git_calls] == ["status", "diff", *moved], git_calls

        git_calls.clear()
        snapshot = real_status(repo)
        gates.session_work_span(repo, snapshot)
        assert [c[0] for c in git_calls] == ["diff", *moved], git_calls

        # HEAD's tree back where the session started, the work uncommitted.
        _git(repo, "reset", "-q", "HEAD~1")
        git_calls.clear()
        gates.session_work_span(repo, real_status(repo))
        assert [c[0] for c in git_calls] == ["diff", "rev-parse"], git_calls

        # Nothing changed: no authorship question to ask.
        _git(repo, "checkout", "-q", "--", "code.py")
        git_calls.clear()
        gates.session_work_span(repo, real_status(repo))
        assert [c[0] for c in git_calls] == ["diff"], git_calls

    def test_a_pre_existing_untracked_file_is_not_this_session_s_work(
        self, tmp_path
    ):
        """The baseline rule has one home. An untracked file that was already
        there at session start is dirt under the porcelain span, and it must be
        dirt under this one too — otherwise the same repo answers two ways."""
        repo = _repo(tmp_path)
        (repo / "left_over.py").write_text("z = 1\n")
        # Re-taken so the leftover is INSIDE the baseline — it was already there
        # when this session started, which is the whole premise.
        (repo / ".prawduct" / ".session-git-baseline").write_text(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo), capture_output=True, text=True, check=True,
            ).stdout
        )
        _mark_base(repo)
        span = gates.session_work_span(repo)
        assert "left_over.py" not in span["changed"]
        assert span["judgeable"] is False
