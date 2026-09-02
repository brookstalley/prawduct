"""The Stop hook's learnings cutover floor — the reflection gate's sibling (R4).

A repo still holding `.prawduct/learnings.md` and no `.claude/rules/learnings/`
gets **nothing** loaded by the harness: to every session it reads exactly like a
repo that has no rules at all, and the only difference is that this one paid for
its rules and is silently not getting them. The session briefing says so at
launch; this gate is the end of the same session saying it again, on the disk
where it matters most — code was written here today without the rules that
govern it.

Two things about its shape are load-bearing and are pinned below:

* **The trigger is judgeable code, not any change.** A doc-only session judged
  nothing, so it owes nothing — the carve-out the Critic gate takes, for the same
  reason. A `.prawduct/`-only session is exempt too, which is where this gate's
  predicate is deliberately narrower than the Critic gate's.
* **It is waivable under the key `learnings`.** A migration can be genuinely
  impossible this session (mid-rebase, a learnings file still being edited), and
  a gate with no escape hatch gets satisfied by whatever is cheapest, which here
  would be deleting the corpus.

The blocker's TEXT is the briefing's directive verbatim, so the agent that
scrolled past it at session start meets the same commands here rather than a
second, subtly different recipe.
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

_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_learnings_cutover", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader(
    "prawduct_hook_learnings_cutover", _hook_loader
)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)

#: The blocker's opening words — what a reader greps for, and what every
#: assertion below is anchored on rather than on a whole paragraph that would
#: make a wording fix look like a regression.
BLOCKER = "LEARNINGS UNMIGRATED"
BLOCKER_LEGACY = "LEARNINGS UNMIGRATED: this session changed judgeable code"
BLOCKER_BOTH = "LEARNINGS UNMIGRATED (both layouts present)"
BUDGET_BLOCKER = "LEARNINGS BUDGET"
BUDGET_OVER = "LEARNINGS BUDGET (over and grown):"
BUDGET_UNREASONED = "LEARNINGS BUDGET (ceiling with no reason):"

#: Advisory ids (`<feature>-<probe>-v<n>-<hash6>`) and prawduct-internal
#: requirement ids (`ABC-1D2E`) may not appear in operator-emitted text.
_ID_SHAPES = (
    re.compile(r"-v\d+-[0-9a-f]{6}\b"),
    re.compile(r"\b[A-Z]{3}-[A-Z0-9]{4}\b"),
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )


def _repo(tmp_path: Path) -> Path:
    """A committed repo with a satisfied reflection gate and no build plan.

    No build plan on purpose: the CRITIC gate needs one to block, so its absence
    leaves this gate as the only other thing that can fire and every assertion
    below reads the blocker it means. The reflection gate stopped needing one
    (#685) — it fires on judgeable code whether or not a plan is active — so it
    is silenced here the only way left, by writing a reflection that satisfies
    its shape check. `SHAPED_REFLECTION` is that text, and it lives in
    `conftest.py` because the shape is a governance decision every Stop-gate
    fixture in this suite has to track.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    (repo / "notes.md").write_text("notes\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    return repo


def _base_tree(repo: Path) -> None:
    """Record the session base tree the way `cmd_clear` does at session start.

    Without it the budget gate has no "before" to compare against and correctly
    reports itself unchecked rather than guessing.
    """
    out = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=str(repo), capture_output=True, text=True, check=True,
    ).stdout.strip()
    (repo / ".prawduct" / ".session-base-tree").write_text(out)


def _legacy(repo: Path) -> None:
    (repo / ".prawduct" / "learnings.md").write_text("# L\n\n## a rule\n")


def _rules(repo: Path, *names: str) -> None:
    d = repo / ".claude" / "rules" / "learnings"
    d.mkdir(parents=True, exist_ok=True)
    for name in names or ("core.md",):
        (d / name).write_text("# rules\n")


def _touch_code(repo: Path) -> None:
    (repo / "code.py").write_text("x = 2\n")


def _touch_doc(repo: Path) -> None:
    (repo / "notes.md").write_text("notes, revised\n")


def _stop(repo: Path, capsys) -> tuple[int, str]:
    rc = _hook.cmd_stop(repo, {})
    return rc, capsys.readouterr().err


class TestTheFloorFires:
    def test_legacy_layout_plus_code_blocks(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err

    def test_both_layout_plus_code_blocks(self, tmp_path, capsys):
        # An interrupted migration, or a branch that reintroduced the old file.
        # The rules ARE loading, so the harm is subtler than `legacy` — two
        # corpora, one of them stale, and no way to tell which rule is live.
        repo = _repo(tmp_path)
        _legacy(repo)
        _rules(repo)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err

    def test_each_state_gets_its_own_diagnosis(self, tmp_path, capsys):
        """One headline for two states told the `both` agent something false.

        In `both` the rules tree exists and the harness loaded it — the same
        session's briefing said so in as many words. A blocker claiming "the
        harness loaded none of it" hands that agent a diagnosis it will act on,
        most likely by re-running a migration that refuses `both` outright.
        """
        legacy_repo = _repo(tmp_path / "a")
        _legacy(legacy_repo)
        _touch_code(legacy_repo)
        _, legacy_err = _stop(legacy_repo, capsys)
        assert BLOCKER_LEGACY in legacy_err
        assert "loaded none of it" in legacy_err

        both_repo = _repo(tmp_path / "b")
        _legacy(both_repo)
        _rules(both_repo)
        _touch_code(both_repo)
        _, both_err = _stop(both_repo, capsys)
        assert BLOCKER_BOTH in both_err
        # The true half, said out loud...
        assert "those rules WERE in context" in both_err
        # ...and the false half, never said.
        assert "loaded none of it" not in both_err

    def test_the_blocker_carries_the_briefing_directive_verbatim(self, tmp_path, capsys):
        from lib import briefing

        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        _, err = _stop(repo, capsys)
        for line in briefing._learnings_lines(repo):
            assert line in err, f"the gate rephrased the briefing's line: {line!r}"

    def test_the_blocker_names_the_waiver_key(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        _, err = _stop(repo, capsys)
        assert '{"learnings": "reason — be specific"}' in err

    def test_the_blocker_carries_no_internal_ids(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        _, err = _stop(repo, capsys)
        block = err[err.index(BLOCKER):]
        block = block[: block.index("\n\n  Escape hatch")]
        for shape in _ID_SHAPES:
            assert not shape.search(block), f"id-shaped token in blocker: {block}"


class TestTheFloorStaysQuiet:
    def test_migrated_layout_passes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _rules(repo, "core.md", "gates.md")
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_no_learnings_at_all_passes(self, tmp_path, capsys):
        # `none` is a healthy state — a repo that has authored no rules yet is
        # not a repo that lost them.
        repo = _repo(tmp_path)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_doc_only_session_passes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_doc(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_a_metadata_only_session_passes(self, tmp_path, capsys):
        # Only `.prawduct/` moved. `session_changes_all_non_judgeable` reads
        # False for that (an empty non-metadata set is deliberately not
        # "doc-only", so the reflection and Critic gates still fire on a
        # governance-only session) — which is why this gate asks for judgeable
        # code directly rather than borrowing that predicate. Nothing was
        # judged here, so nothing is owed.
        repo = _repo(tmp_path)
        _legacy(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err

    def test_a_session_that_changed_nothing_passes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c2")
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err


class TestTheWaiver:
    def test_the_learnings_key_suppresses_the_blocker(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        (repo / ".prawduct" / ".gates-waived").write_text(
            json.dumps({"learnings": "mid-rebase; migrating next session"})
        )
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err
        # Suppression is never silent: a waived gate is reported as waived.
        assert "learnings: waived (mid-rebase; migrating next session)" in err

    def test_the_key_is_recognised_not_reported_as_a_typo(self, tmp_path, capsys):
        # `KNOWN_WAIVER_KEYS` drives an "unknown keys (no effect)" warning. A key
        # that suppresses a real blocker while being reported as ineffective is
        # the worst of both readings.
        repo = _repo(tmp_path)
        _rules(repo)
        _touch_code(repo)
        (repo / ".prawduct" / ".gates-waived").write_text(
            json.dumps({"learnings": "not needed here"})
        )
        _, err = _stop(repo, capsys)
        assert "unknown keys" not in err

    def test_an_unrelated_waiver_does_not_suppress_it(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        (repo / ".prawduct" / ".gates-waived").write_text(
            json.dumps({"critic": "different gate entirely"})
        )
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BLOCKER in err


class TestTheGateNeverCrashesSessionEnd:
    def test_an_unreadable_layout_is_not_an_unmigrated_one(
        self, tmp_path, capsys, monkeypatch
    ):
        # Fail OPEN here, deliberately, and against the usual fail-closed
        # posture: a gate that cannot see the tree has no verdict, and inventing
        # a block would fire on every repo with a broken install.
        from lib import learnings_files

        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        monkeypatch.setattr(
            learnings_files,
            "resolve",
            lambda d: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err


class TestTheCrossCheckNudgeNamesWhatWillBeRead:
    """The advisory that says "run /prawduct:critic final" also says what the
    Learnings Cross-Check will open.

    The failure it guards is silent in the only direction that matters: an area
    file the harness put in context and the reviewer never read. Naming the set
    in the nudge — from the resolver, over the session's own changed paths — is
    what turns that from invisible into something a reader can notice.
    """

    def test_it_names_core_and_the_areas_the_diff_pulls_in(self, tmp_path):
        from lib import gates

        repo = _repo(tmp_path)
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True)
        (d / "core.md").write_text("# core\n")
        (d / "code.md").write_text('---\npaths: ["code.py"]\n---\n# code rules\n')
        (d / "web.md").write_text('---\npaths: ["web/**"]\n---\n# web rules\n')
        _touch_code(repo)

        note = gates.learnings_cross_check_note(repo)
        assert ".claude/rules/learnings/core.md" in note
        assert ".claude/rules/learnings/code.md" in note
        # The area whose globs the diff does NOT intersect is not claimed to be read.
        assert "web.md" not in note

    def test_an_empty_answer_is_stated_not_omitted(self, tmp_path):
        # "no rules file matches this diff" and "the cross-check ran and found
        # nothing" look identical in a report that says neither.
        from lib import gates

        repo = _repo(tmp_path)
        _touch_code(repo)
        note = gates.learnings_cross_check_note(repo)
        assert "nothing to read" in note

    def test_the_advisory_carries_it(self, tmp_path):
        """The nudge itself, not just the helper — the reason lives in
        `_critic_session_satisfies_gate`'s message and nowhere else."""
        from lib import gates

        repo = _repo(tmp_path)
        prawduct = repo / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Plan\n\n## Status\n\n- [x] Chunk 01: a\n- [x] Chunk 02: b\n"
        )
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: P\nactive_build_plan: "
            ".prawduct/artifacts/build-plan.md\n"
        )
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True)
        (d / "core.md").write_text("# core\n")
        _touch_code(repo)
        _hook_evidence(repo)

        satisfied, reason = gates._critic_session_satisfies_gate(repo)
        assert not satisfied
        assert "Learnings Cross-Check reads: .claude/rules/learnings/core.md." in reason


def _hook_evidence(repo: Path) -> None:
    """One `chunk`-mode review fact — the state the mode nudge fires on."""
    from lib import evidence

    from lib import gates

    # The stored mode is the gate's own vocabulary string, not the bare word —
    # `_CRITIC_MODE_GOALS_1_3_ONLY` matches on it, so a hand-written "chunk"
    # here would silently satisfy the gate and the test would pass for nothing.
    result = evidence.append_fact(
        repo,
        "review",
        "rev-20260902T000000Z-deadbeef",
        {"mode": gates._CRITIC_MODE_CHUNK, "base": "0" * 40, "head": "0" * 40},
    )
    assert result["status"] == "appended", result


class TestDegradationIsNeverSilent:
    """Both detection channels name their own failure, and neither un-detects.

    R4 exists because "a silent failure here is *an unmigrated repo the new
    version reads as empty*". A channel that swallows its own exception
    reproduces exactly that, and takes the operator's only signal with it —
    which is why failing OPEN here is right and failing QUIET is not.
    """

    def test_a_rendering_failure_does_not_clear_a_detected_state(
        self, tmp_path, capsys, monkeypatch
    ):
        """The reset that mattered: the first cut caught import + resolve +
        render in one `except` that set the verdict to "migrated", so a repo
        correctly DETECTED as legacy passed the floor because the sentence
        describing it could not be built."""
        from lib import briefing

        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        monkeypatch.setattr(
            briefing,
            "_learnings_lines",
            lambda d: (_ for _ in ()).throw(RuntimeError("render-boom")),
        )
        rc, err = _stop(repo, capsys)
        assert rc == 2, "a rendering failure cleared a detected legacy state"
        assert BLOCKER_LEGACY in err
        # ...and it says the message is the short form, rather than implying the
        # recipe was omitted on purpose.
        assert "could not be rendered" in err
        assert "render-boom" in err

    def test_an_unreadable_layout_says_so_at_stop(self, tmp_path, capsys, monkeypatch):
        # Fail OPEN, deliberately — a gate that cannot see the tree has no
        # verdict — but never fail quiet.
        from lib import learnings_files

        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        monkeypatch.setattr(
            learnings_files,
            "resolve",
            lambda d: (_ for _ in ()).throw(RuntimeError("resolve-boom")),
        )
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err
        assert "the learnings layout could not be read" in err
        assert "resolve-boom" in err

    def test_the_briefing_says_so_too(self, tmp_path, monkeypatch):
        """The same defect takes out session start and session end together, so
        a silent briefing plus a silent floor is a fully governed-looking
        session on a repo whose rules were never loaded."""
        from lib import briefing

        repo = _repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "product_identity:\n  name: P\n"
        )
        monkeypatch.setattr(
            briefing,
            "_learnings_lines",
            lambda d: (_ for _ in ()).throw(RuntimeError("briefing-boom")),
        )
        out = briefing.assemble_session_briefing(repo, [])
        assert "== SESSION BRIEFING ==" in out  # still never blocks session start
        assert "NOTE: the learnings layout could not be read" in out
        assert "briefing-boom" in out


class TestTheBudgetFloor:
    """The ceiling fires at Stop, which is the channel the ruling picked.

    Discovery §2 criterion 4: an over-budget rule file "blocks the *next
    addition* at Stop and nothing else"; §8.8 Q1 chose Stop over a Critic
    finding *because* rules are written at work boundaries of every size while
    the Critic runs only on medium+. Enforced only at review time, the ceiling
    is absent exactly where the audit measured the growth.
    """

    def _over_budget(self, repo: Path, *, grown: bool) -> None:
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True, exist_ok=True)
        core = d / "core.md"
        core.write_text("# core\n" + "x" * (20 * 1024))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)
        if grown:
            core.write_text("# core\n" + "x" * (24 * 1024))

    def test_over_and_grew_blocks_at_stop(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        self._over_budget(repo, grown=True)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BUDGET_BLOCKER in err
        # The finding text is carried, not re-worded: one wording wherever the
        # builder meets this check.
        assert "learnings-over-budget" in err
        assert "never trim a rule to fit" in err

    def test_over_but_unchanged_passes(self, tmp_path, capsys):
        # Over alone is a one-time sweep, not this gate's business — the
        # direction of travel is the finding.
        repo = _repo(tmp_path)
        self._over_budget(repo, grown=False)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BUDGET_BLOCKER not in err

    def test_under_budget_passes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _rules(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BUDGET_BLOCKER not in err

    def test_the_budget_waiver_key_suppresses_it(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        self._over_budget(repo, grown=True)
        _touch_code(repo)
        (repo / ".prawduct" / ".gates-waived").write_text(
            json.dumps({"learnings-budget": "compaction lands next session"})
        )
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BUDGET_BLOCKER not in err
        assert "learnings-budget: waived (compaction lands next session)" in err
        # A key that suppresses a real blocker while being reported ineffective
        # is the worst of both readings.
        assert "unknown keys" not in err

    def test_the_cutover_floors_waiver_does_not_suppress_the_budget(
        self, tmp_path, capsys
    ):
        repo = _repo(tmp_path)
        self._over_budget(repo, grown=True)
        _touch_code(repo)
        (repo / ".prawduct" / ".gates-waived").write_text(
            json.dumps({"learnings": "different gate entirely"})
        )
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BUDGET_BLOCKER in err

    def test_an_unchecked_result_is_a_note_never_silence(self, tmp_path, capsys):
        """No base tree means no growth comparison. That is not a pass, and a
        ceiling that could not be measured must not read as one that held."""
        repo = _repo(tmp_path)
        _rules(repo)
        _touch_code(repo)  # no _base_tree() call
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert "learnings-over-budget unchecked" in err
        assert "no .session-base-tree marker" in err

    def test_an_unmigrated_repo_is_not_budgeted(self, tmp_path, capsys):
        # Two controls naming one state teach a reader to skip both; the legacy
        # state is the cutover floor's business.
        repo = _repo(tmp_path)
        _legacy(repo)
        _touch_code(repo)
        _, err = _stop(repo, capsys)
        assert BUDGET_BLOCKER not in err
        assert "learnings-over-budget unchecked" not in err


class TestOneDefinitionOfTheDiff:
    """The gate note and `learnings-files --for-diff` resolve the same change set.

    They were built against different helpers — session-changed files versus the
    base BRANCH — so a builder who commits the chunk before Stop fires (the
    ordinary cadence) got a nudge naming `core.md` alone while the verb named
    the area files the harness had actually loaded. The one line whose purpose
    is to make a silent disagreement noticeable was the disagreement.
    """

    def _corpus(self, repo: Path) -> None:
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True, exist_ok=True)
        (d / "core.md").write_text("# core\n")
        (d / "code.md").write_text('---\npaths: ["code.py"]\n---\n# code rules\n')
        (d / "web.md").write_text('---\npaths: ["web/**"]\n---\n# web rules\n')

    def test_committed_and_uncommitted_changes_give_one_answer(self, tmp_path, capsys):
        """One committed change and one uncommitted, which is where the two
        definitions used to part company."""
        from lib import gates

        repo = _repo(tmp_path)
        self._corpus(repo)
        (repo / "web").mkdir()
        (repo / "web" / "app.ts").write_text("//\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)

        # committed this session...
        (repo / "code.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "committed work")
        # ...and uncommitted.
        (repo / "web" / "app.ts").write_text("// edited\n")

        changed, reason = gates.learnings_change_set(repo)
        assert reason == ""
        assert "code.py" in changed and "web/app.ts" in changed

        note = gates.learnings_cross_check_note(repo)
        assert _hook.cmd_learnings_files(repo, ["--for-diff"]) == 0
        printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

        # The verb names the committed change's area file, which the old
        # session-scoped reading dropped...
        assert printed == [
            ".claude/rules/learnings/core.md",
            ".claude/rules/learnings/code.md",
            ".claude/rules/learnings/web.md",
        ]
        # ...and the gate note names exactly what the verb printed. THIS is the
        # agreement: a reviewer following the line and a reviewer running the
        # command open the same files.
        assert note == "The Learnings Cross-Check reads: " + ", ".join(printed) + "."

    def test_the_note_says_when_it_could_not_compute(self, tmp_path, monkeypatch):
        # "nothing changed" and "could not tell" are opposite facts.
        from lib import coverage, gates

        repo = _repo(tmp_path)
        self._corpus(repo)
        monkeypatch.setattr(
            coverage,
            "_coverage_changed_files",
            lambda d, b: (_ for _ in ()).throw(RuntimeError("diff-boom")),
        )
        note = gates.learnings_cross_check_note(repo)
        assert "could not be computed" in note
        assert "diff-boom" in note
        assert "nothing to read" not in note

    def test_a_slow_git_reads_as_could_not_tell_not_a_traceback(self, tmp_path, monkeypatch):
        """coverage's git calls carry a 30s bound; TimeoutExpired is a
        SubprocessError, not an OSError, and used to escape the helper."""
        import subprocess

        from lib import coverage, gates

        repo = _repo(tmp_path)
        self._corpus(repo)
        monkeypatch.setattr(
            coverage,
            "_coverage_changed_files",
            lambda d, b: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(["git", "diff"], 30)),
        )
        changed, reason = gates.learnings_change_set(repo)
        assert changed == [] and reason.startswith("TimeoutExpired")

    def test_the_verb_fails_loud_on_the_same_failure(self, tmp_path, capsys, monkeypatch):
        from lib import coverage

        repo = _repo(tmp_path)
        self._corpus(repo)
        monkeypatch.setattr(
            coverage,
            "_coverage_changed_files",
            lambda d, b: (_ for _ in ()).throw(RuntimeError("diff-boom")),
        )
        rc = _hook.cmd_learnings_files(repo, ["--for-diff"])
        assert rc == 1, "a silent empty list is a narrowing that looks like an answer"
        assert "diff-boom" in capsys.readouterr().err


class TestTheReflectionNudgeDoesNotRecreateTheLegacyFile:
    """The Stop hook must not direct the agent to write the file it blocks on.

    Both messages come out of `cmd_stop` into the same blocker list, seventy
    lines apart: the reflection blocker said "also add it to
    `.prawduct/learnings.md`" while the cutover floor blocks any repo holding
    that file. An agent obeying the first recreates the corpus, `resolve()`
    flips to `both`, the next session's floor fires, and `learnings-migrate`
    refuses the state outright — governance manufacturing the defect it gates.
    """

    @staticmethod
    def _reflection_blocks(tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        (repo / ".prawduct" / ".session-reflected").unlink()
        artifacts = repo / ".prawduct" / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text(
            "# Plan\n\n## Status\n\n- [ ] Chunk 01: work\n"
        )
        _touch_code(repo)
        return repo

    def test_it_points_at_the_rules_files(self, tmp_path, capsys):
        repo = self._reflection_blocks(tmp_path)
        _rules(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert "REFLECTION:" in err
        assert ".claude/rules/learnings/core.md" in err
        assert ".prawduct/learnings.md" not in err

    def test_it_names_the_area_files_too(self, tmp_path, capsys):
        # A rule about one area belongs in that area's file, not in the file
        # every session pays for.
        repo = self._reflection_blocks(tmp_path)
        _rules(repo)
        _, err = _stop(repo, capsys)
        assert "area file under .claude/rules/learnings/ whose `paths:` cover it" in err

    def test_an_unreadable_layout_leaves_a_path_free_pointer(
        self, tmp_path, capsys, monkeypatch
    ):
        """The fallback names no path at all. A hardcoded second opinion about
        the layout is precisely what the one-resolver rule exists to remove —
        so when the resolver cannot answer, this says less rather than guessing.
        """
        from lib import learnings_files

        repo = self._reflection_blocks(tmp_path)
        monkeypatch.setattr(
            learnings_files,
            "resolve",
            lambda d: (_ for _ in ()).throw(RuntimeError("resolve-boom")),
        )
        _, err = _stop(repo, capsys)
        assert "REFLECTION:" in err
        assert "this repo's learnings rules files" in err
        assert ".prawduct/learnings.md" not in err


class TestOneGitignorePredicate:
    """`briefing` asks the resolver; it holds no copy of the question.

    Two chunks answered it independently — one against the directory, one
    against `core.md` — and the two disagree under check-ignore's index
    awareness: a directory pathspec is satisfied by ANY tracked file beneath it,
    so a repo with one area file committed and `core.md` untracked read as
    "tracked" and got no GITIGNORED suffix. That half-committed corpus is the
    exact state the suffix exists to name.
    """

    def test_briefing_holds_no_second_implementation(self):
        """Scoped to the LEARNINGS question, not to `check-ignore` generally —
        `briefing` legitimately asks git about other candidate files, and a
        blanket ban would fail for a reason this test is not about."""
        from lib import briefing

        source = (
            Path(__file__).resolve().parent.parent
            / "plugin" / "lib" / "briefing.py"
        ).read_text()
        assert not hasattr(briefing, "_rules_dir_is_gitignored"), (
            "briefing still carries its own copy of the rules-tree predicate"
        )
        assert "learnings_files.rules_dir_is_gitignored(" in source, (
            "briefing no longer asks the resolver whether the corpus is committed"
        )

    def test_the_suffix_follows_the_resolver(self, tmp_path, monkeypatch):
        from lib import briefing, learnings_files

        repo = _repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "product_identity:\n  name: P\n"
        )
        _rules(repo)
        monkeypatch.setattr(learnings_files, "rules_dir_is_gitignored", lambda d: True)
        assert "GITIGNORED" in "\n".join(briefing._learnings_lines(repo))
        monkeypatch.setattr(learnings_files, "rules_dir_is_gitignored", lambda d: False)
        assert "GITIGNORED" not in "\n".join(briefing._learnings_lines(repo))


class TestTheBudgetBlockerIsDerivedFromItsFindings:
    """One list, two checks, two remedies — so two blockers.

    `_check_learnings_budget` returns `learnings-over-budget` and
    `learnings-budget-unreasoned` together. They share nothing: the second's
    subject is a `learnings_budgets:` entry in project-state.yaml, it is emitted
    before the check ever looks at a rules file (so it reaches a repo with no
    corpus at all), and its remedy is one `reason:` line. Relayed under the
    over-budget headline, an operator is sent hunting for growth that never
    happened, and the blocker id names a control that did not fire.

    Every rendered branch is pinned, because the rule that asks for this
    ("a message covering two states must be DERIVED from the state, never
    written for the one in mind") was earned by exactly this defect.
    """

    @staticmethod
    def _budgets(repo: Path, body: str) -> None:
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "product_identity:\n  name: P\nlearnings_budgets:\n" + body
        )

    def test_the_unreasoned_case_gets_its_own_headline_and_id(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _rules(repo)
        self._budgets(repo, "  core.md:\n    kb: 64\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BUDGET_UNREASONED in err
        assert "the fix is one `reason:` line" in err
        # The over-budget diagnosis must not appear: no file is over anything.
        assert BUDGET_OVER not in err
        assert "grew this session" not in err
        # ...and the blocker is attributed to the check that actually fired.
        assert "gate: learnings-budget-unreasoned" in err
        assert "gate: learnings-over-budget" not in err

    def test_the_unreasoned_case_reaches_a_repo_with_no_corpus(self, tmp_path, capsys):
        """It fires before the check looks at a rules file, so a `none`-state
        repo meets it — the one shape where the over-budget wording could not
        possibly be true."""
        repo = _repo(tmp_path)
        self._budgets(repo, "  core.md:\n    kb: 64\n")
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BUDGET_UNREASONED in err
        assert BUDGET_OVER not in err

    def test_the_over_budget_case_keeps_its_own_headline_and_id(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True)
        (d / "core.md").write_text("# core\n" + "x" * (20 * 1024))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)
        (d / "core.md").write_text("# core\n" + "x" * (24 * 1024))
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BUDGET_OVER in err
        assert "gate: learnings-over-budget" in err
        assert BUDGET_UNREASONED not in err

    def test_both_checks_at_once_render_as_two_blockers(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True)
        (d / "core.md").write_text("# core\n" + "x" * (20 * 1024))
        self._budgets(repo, "  areas.md:\n    kb: 64\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)
        (d / "core.md").write_text("# core\n" + "x" * (24 * 1024))
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert BUDGET_OVER in err and BUDGET_UNREASONED in err
        assert "gate: learnings-over-budget" in err
        assert "gate: learnings-budget-unreasoned" in err


class TestARulesOnlySessionPays:
    """The floor runs on its own subject, not on Gate 1b's.

    A rules file is neither metadata nor judgeable — a `.md` outside the
    protected set — so a session whose only change was growing `core.md`
    computed `doc_only`, skipped the floor, committed the growth into the next
    session's base tree, and was never charged. The ceiling was bypassable,
    permanently and silently, by the exact write path it exists to govern
    (discovery criterion 4: it blocks the *next addition* at Stop).
    """

    @staticmethod
    def _corpus(repo: Path, kb: int) -> Path:
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True, exist_ok=True)
        core = d / "core.md"
        core.write_text("# core\n" + "x" * (kb * 1024))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "corpus")
        _base_tree(repo)
        return core

    def test_growing_a_rules_file_alone_blocks(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        core = self._corpus(repo, 20)
        core.write_text("# core\n" + "x" * (24 * 1024))  # the ONLY change
        rc, err = _stop(repo, capsys)
        assert rc == 2, "a rules-only session skipped the floor it exists for"
        assert BUDGET_OVER in err

    def test_a_rules_only_session_under_budget_passes(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        core = self._corpus(repo, 2)
        core.write_text("# core\n" + "x" * (3 * 1024))
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BUDGET_BLOCKER not in err

    def test_the_cutover_floor_is_not_widened_by_the_same_change(
        self, tmp_path, capsys
    ):
        """Gate 1b keeps its own, narrower trigger. Its first sentence names
        judgeable code, and a rules-only session did not change any."""
        repo = _repo(tmp_path)
        _legacy(repo)
        d = repo / ".claude" / "rules" / "learnings"
        d.mkdir(parents=True)
        core = d / "core.md"
        core.write_text("# core\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "both corpora")
        _base_tree(repo)
        core.write_text("# core\n\n## a rule\n")  # the ONLY change
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert BLOCKER not in err


class TestTheBothDirectiveNamesTheResumePath:
    """`apply()` leaves a half-written tree ON PURPOSE so a re-run can finish it.

    `learnings_migrate._resume_state` tells its own wreckage from a genuine
    two-corpus repo (every file on disk byte-identical to what the plan would
    write). Across a session boundary the operator meets only these two
    surfaces, and both told them to hand-fold and delete — when after a write
    that failed partway, the rules that never landed exist ONLY in the legacy
    file, so "delete it" is the destructive reading.
    """

    def test_the_briefing_directive_offers_the_re_run_first(self, tmp_path):
        from lib import briefing

        repo = _repo(tmp_path)
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "product_identity:\n  name: P\n"
        )
        _legacy(repo)
        _rules(repo)
        directive = next(
            ln for ln in briefing._learnings_lines(repo) if ln.startswith("agent →")
        )
        assert "learnings-migrate --apply` was interrupted, re-run it" in directive
        assert "finishes a half-written tree" in directive
        # The hand-fold survives as the OTHER branch, not as the only one.
        assert "otherwise fold" in directive
        assert "by hand and delete it" in directive

    def test_the_stop_headline_drops_the_dead_weight_claim(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _legacy(repo)
        _rules(repo)
        _touch_code(repo)
        _, err = _stop(repo, capsys)
        assert BLOCKER_BOTH in err
        assert "dead weight" not in err, (
            "the blocker still calls the legacy file dead weight while the "
            "directive beneath it says to fold the file in — one blocker, two "
            "contradictory instructions"
        )
        assert "nothing reads" not in err
        flat = " ".join(err.split())
        assert "may still hold rules that never reached the tree" in flat
        # The resume path reaches the Stop channel too, via the directive.
        assert "re-run it" in err
