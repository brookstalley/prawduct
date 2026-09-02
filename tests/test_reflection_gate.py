"""The Stop hook's reflection gate — what makes it fire, and what it grades.

Two things changed and both are pinned here.

**What makes it fire.** The gate used to ask "is a build plan active, and is
porcelain dirty?" Both were wrong in the same direction. A planless session that
wrote and committed code — the ordinary shape of a bug fix, a sweep, a
one-file change nobody drew a plan for — got an advisory note and ended in
silence, so the sessions least likely to have a plan were the ones whose lesson
was never written down. And porcelain empties the moment you commit, so even a
planned session could satisfy the gate by committing first. It now asks one
question of `gates.session_work_span`: did judgeable code change between this
session's base tree and the working tree, committed work included.

**What it grades.** The old floor was fifty characters, which graded nothing —
"did the chunk, tests green, shipping it" cleared it, and so did two hundred
characters of the same. It now grades SHAPE
(`gates.reflection_shape`): the text must name what was expected and what was
actual, plus a root cause or its explicit absence. Substring tests, deliberately
the weakest check that can tell the two shapes apart, because anything stronger
grades phrasing rather than whether the work was done.

**The half that did NOT change, pinned in `TestTheCriticGuardIsUnchanged`.** The
Critic composition gate keeps its porcelain guard. A reflection false-fire costs
two lines; a Critic false-fire costs a review round. Flipping both at once was
available and was declined, so the test that would notice the flip lives here
next to the span that would do it.

Fixture shape mirrors `tests/test_learnings_cutover_gate.py`: a real git repo,
`cmd_stop` called in-process, stderr read back.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
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


class TestTheKnownFalseFire:
    """The one class of fire nobody authored, measured rather than argued.

    The span is base tree → working tree with no authorship test, so judgeable
    files that arrive by `git merge` or `git pull` mid-session are inside it and
    the gate fires on work this session did not write. That is a recorded
    assumption of the design, not an oversight: an authorship test means asking
    git who wrote each hunk on every turn, and the cost of being wrong here is
    two lines. The test exists so the claim is a reading rather than a belief,
    and so that a future authorship exclusion has the case it must silence.
    """

    def test_a_merge_that_brings_judgeable_files_fires(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "other")
        (repo / "theirs.py").write_text("their_work = 1\n")
        # `add theirs.py`, not `add -A`: `-A` would stage the untracked
        # `.prawduct/` too, and checking `main` back out would then delete the
        # session state this fixture is about to write.
        _git(repo, "add", "theirs.py")
        _git(repo, "commit", "-q", "-m", "someone else's commit")
        _git(repo, "checkout", "-q", "main")

        _mark_base(repo)                       # session starts here, on main
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge other", "other")

        rc, err = _stop(repo, capsys)
        assert rc == 2, "documented false fire — if this goes silent, the design changed"
        assert BLOCKER in err
        assert "theirs.py" in gates.session_work_span(repo)["changed"]

    def test_and_two_lines_end_it(self, tmp_path, capsys):
        """The price of the false fire above, stated as a test: one reflection,
        no re-run of anything, no review. That is the whole cost, and it is what
        makes this class acceptable at the reflection gate and not at the Critic
        gate, where the same fire would cost a review round."""
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "other")
        (repo / "theirs.py").write_text("their_work = 1\n")
        # `add theirs.py`, not `add -A`: `-A` would stage the untracked
        # `.prawduct/` too, and checking `main` back out would then delete the
        # session state this fixture is about to write.
        _git(repo, "add", "theirs.py")
        _git(repo, "commit", "-q", "-m", "someone else's commit")
        _git(repo, "checkout", "-q", "main")
        _mark_base(repo)
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge other", "other")

        _reflect(repo, "Expected: sync only. Actual: same. No defect.\n")
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err


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


# ---------------------------------------------------------------------------
# The decision's other half
# ---------------------------------------------------------------------------


class TestTheCriticGuardIsUnchanged:
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
        """Force the composition verdict to the blocking answer.

        Not decoration: on a fresh single-branch fixture the real verdict
        composes to `covered` through the merge-base fallback, so a test that
        let it run would report the Critic gate silent no matter what its guard
        read. Pinning the verdict leaves the GUARD as the only variable, which
        is what this class is about.
        """
        monkeypatch.setattr(
            gates,
            "session_review_verdict",
            lambda *_a, **_k: {"status": "uncovered", "reason": "no composed review coverage"},
        )

    def test_a_committed_change_leaves_the_critic_gate_silent(
        self, tmp_path, capsys, monkeypatch
    ):
        """The recorded decision: in this wave ONLY the reflection gate reads
        the span. This fixture has an active build plan, a committed judgeable
        change and no review evidence — every ingredient the Critic gate needs
        except a dirty porcelain. It must stay silent, and the span assertion
        beside it proves the silence is the guard's choice rather than an empty
        diff. Flip that guard onto `session_work_span` and this goes red, which
        is the point: the flip is a decision, not a refactor.
        """
        repo = self._plan_repo(tmp_path)
        _mark_base(repo)
        _commit_code(repo)
        _reflect(repo, SHAPED_REFLECTION)
        self._verdict_says_uncovered(monkeypatch)

        span = gates.session_work_span(repo)
        assert span["judgeable"] is True, (
            "the span must SEE this work, or the silence below proves nothing"
        )

        rc, err = _stop(repo, capsys)
        assert rc == 0, f"the Critic gate must not have fired. stderr={err!r}"
        assert "CRITIC" not in err

    def test_the_control_the_gate_does_fire_on_a_dirty_porcelain(
        self, tmp_path, capsys, monkeypatch
    ):
        """The positive control the test above needs.

        Without it, "the Critic gate stayed silent" is satisfied by a fixture
        the gate could never fire on for some unrelated reason, and the guard
        assertion measures nothing. Same repo, same plan, same forced verdict —
        the change is left UNCOMMITTED, which is the one thing the porcelain
        guard reads.
        """
        repo = self._plan_repo(tmp_path)
        _mark_base(repo)
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

    def test_it_costs_one_status_and_one_diff(self, tmp_path, monkeypatch):
        """The requirement is a COST — this gate runs on every turn — so the
        assertion is over the operations that cost, not over a side effect that
        usually accompanies them.

        Two readers below need the porcelain snapshot and each would spawn its
        own `git status` if the span did not take one and thread it. Pass the
        snapshot in (what `cmd_stop` does) and even that goes away, leaving the
        single `git diff` this design is bounded by. `capture_tree` must not
        appear at all: it writes an index file and walks the whole tree, which
        is a review-time cost, not a per-turn one.
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

        gates.session_work_span(repo)
        assert [c[0] for c in git_calls] == ["status", "diff"], git_calls

        git_calls.clear()
        snapshot = real_status(repo)
        gates.session_work_span(repo, snapshot)
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
