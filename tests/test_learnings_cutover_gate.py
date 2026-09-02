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
BLOCKER = "LEARNINGS UNMIGRATED:"

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

    No build plan on purpose: the reflection and Critic gates both need one to
    block, so their absence leaves this gate as the only thing that can fire and
    every assertion below reads the blocker it means.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    (repo / "notes.md").write_text("notes\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    (prawduct / ".session-reflected").write_text(
        "A sufficiently long session reflection so the reflection gate stays quiet here.\n"
    )
    return repo


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
