"""The learning loop's two ledger events, end to end.

`learning.written` (the Stop hook) and `learning.fired` (`critic-consolidate`)
exist so that an audit of the rules corpus reads a number instead of sampling
transcripts. Both are MEASUREMENTS of something that already happened, which
fixes two properties everything below is built around:

* **Neither may change a verdict.** A ledger failure leaves the Stop gate's exit
  code and the consolidation's exit code exactly where they were, and says so on
  stderr — a measurement that silently does not happen is how an instrument
  reads zero forever.
* **Both are re-observed.** The Stop hook runs every turn, so a rule written
  once looks new on every turn until the session ends; a re-consolidation
  re-reads the same findings. The idempotence key
  `(kind, session, file, unit_hash, review_id)` is the only thing keeping each
  at one line, so it is pinned here from both directions.

The emission rides the learnings BUDGET block's trigger and its base-tree
marker on purpose: "did the corpus grow past its ceiling" and "which rules did
this session write" are the same comparison against the same base, so one state
answers both and the two cannot disagree about whether it happened.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_learning_events", str(_ROOT / "bin" / "prawduct-hook")
)
_spec = importlib.util.spec_from_loader("prawduct_hook_learning_events", _loader)
_hook = importlib.util.module_from_spec(_spec)
_loader.exec_module(_hook)

from lib import learnings_files as lf  # noqa: E402
from lib import ledger  # noqa: E402

HOOK = _ROOT / "bin" / "prawduct-hook"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"
RULES_REL = f"{lf.RULES_DIR_REL}/{lf.CORE_NAME}"
FINAL_MODE = "final (full review, ready for push)"

#: A rule long enough that its opening eight words are a real citation, and
#: distinctive enough that no other string in a fixture contains them.
RULE_A = (
    "When a guard test pins a safety claim, assert the property rather than "
    "one spelling of it"
)
RULE_B = (
    "When you relocate a fact, grep the prose naming its old home as well as "
    "the fact itself"
)


# ---------------------------------------------------------------------------
# Fixture repo
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15, check=True,
    )


def _corpus(*rules: str) -> str:
    return lf.CORE_HEADER + "\n" + "".join(f"\n### {r}\n" for r in rules)


def _repo(tmp_path: Path, *, rules: tuple[str, ...] = ()) -> Path:
    """A committed repo whose only live gate is the budget block.

    No build plan, and a satisfied reflection — the Critic and reflection gates
    both need one, so their absence leaves the exit code free to mean what the
    assertions below say it means.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "code.py").write_text("x = 1\n")
    rules_path = repo / RULES_REL
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(_corpus(*rules), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    prawduct = repo / ".prawduct"
    prawduct.mkdir(exist_ok=True)
    (prawduct / ".session-reflected").write_text(
        "A sufficiently long session reflection so the reflection gate stays quiet here.\n"
    )
    (prawduct / ".session-start").write_text("")
    _base_tree(repo)
    return repo


def _base_tree(repo: Path) -> None:
    """Record the session base tree the way `cmd_clear` does at session start."""
    out = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    (repo / ".prawduct" / ".session-base-tree").write_text(out)


def _write_rules(repo: Path, *rules: str) -> None:
    (repo / RULES_REL).write_text(_corpus(*rules), encoding="utf-8")


def _touch_code(repo: Path) -> None:
    (repo / "code.py").write_text("x = 2\n")


def _stop(repo: Path, capsys) -> tuple[int, str]:
    rc = _hook.cmd_stop(repo, {})
    return rc, capsys.readouterr().err


def _events(repo: Path, kind: str | None = None) -> list[dict]:
    path = repo / LEDGER_REL
    if not path.is_file():
        return []
    out = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    return [e for e in out if kind is None or e.get("event") == kind]


# ---------------------------------------------------------------------------
# learning.written — the Stop hook
# ---------------------------------------------------------------------------


class TestStopRecordsRulesWritten:
    def test_one_event_per_unit_new_since_the_base(self, tmp_path, capsys):
        repo = _repo(tmp_path)  # base tree: the scaffold header, zero rules
        _write_rules(repo, RULE_A, RULE_B)
        rc, _err = _stop(repo, capsys)
        assert rc == 0

        events = _events(repo, "learning.written")
        assert len(events) == 2
        assert {e["learning"]["unit_hash"] for e in events} == {
            lf.unit_hash(RULE_A), lf.unit_hash(RULE_B)
        }
        assert {e["learning"]["file"] for e in events} == {RULES_REL}
        assert all(e["learning"]["review_id"] is None for e in events)
        assert all(e["actor"]["role"] == "builder" for e in events)

    def test_only_the_new_unit_is_recorded(self, tmp_path, capsys):
        """The base already carries RULE_A, so only RULE_B is this session's
        work. Without the base comparison every Stop would re-record the whole
        corpus as freshly written."""
        repo = _repo(tmp_path, rules=(RULE_A,))
        _write_rules(repo, RULE_A, RULE_B)
        _stop(repo, capsys)
        events = _events(repo, "learning.written")
        assert len(events) == 1
        assert events[0]["learning"]["unit_hash"] == lf.unit_hash(RULE_B)

    def test_nothing_when_the_corpus_did_not_change(self, tmp_path, capsys):
        repo = _repo(tmp_path, rules=(RULE_A,))
        _touch_code(repo)  # judgeable work, untouched rules
        rc, _err = _stop(repo, capsys)
        assert rc == 0
        assert _events(repo, "learning.written") == []

    def test_a_second_stop_in_the_same_session_adds_nothing(self, tmp_path, capsys):
        """The Stop hook runs EVERY turn and the rule stays new against the
        session base for all of them. This is the idempotence key's whole job."""
        repo = _repo(tmp_path)
        _write_rules(repo, RULE_A)
        _stop(repo, capsys)
        assert len(_events(repo, "learning.written")) == 1
        _stop(repo, capsys)
        assert len(_events(repo, "learning.written")) == 1

    def test_a_rules_file_absent_at_base_has_every_unit_new(self, tmp_path, capsys):
        repo = _repo(tmp_path, rules=(RULE_A,))
        area = repo / lf.RULES_DIR_REL / "area.md"
        area.write_text("---\npaths:\n  - 'src/**'\n---\n\n# Area\n\n### " + RULE_B + "\n")
        _stop(repo, capsys)
        events = _events(repo, "learning.written")
        assert len(events) == 1
        assert events[0]["learning"]["file"] == f"{lf.RULES_DIR_REL}/area.md"
        assert events[0]["learning"]["unit_hash"] == lf.unit_hash(RULE_B)

    def test_no_marker_records_nothing_and_says_so_in_the_budget_message(
        self, tmp_path, capsys
    ):
        """ONE message derived from ONE state. The missing base is the reason
        the budget could not be measured AND the reason nothing was recorded;
        a second sentence for the same state teaches a reader to skip both."""
        repo = _repo(tmp_path)
        (repo / ".prawduct" / ".session-base-tree").unlink()
        _write_rules(repo, RULE_A)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert _events(repo, "learning.written") == []
        assert "no .session-base-tree marker" in err
        assert "`learning.written`" in err
        # ...and it is the budget line carrying it, not a second NOTE of its own.
        assert err.count("no .session-base-tree marker") == 1

    def test_an_unresolvable_base_records_nothing_rather_than_the_whole_corpus(
        self, tmp_path, capsys
    ):
        """A base tree git cannot resolve makes every file look absent-at-base,
        which would persist the ENTIRE corpus as written this session. Unlike a
        wall of findings, that noise is durable and counted."""
        repo = _repo(tmp_path, rules=(RULE_A, RULE_B))
        (repo / ".prawduct" / ".session-base-tree").write_text("0" * 40)
        _touch_code(repo)
        rc, err = _stop(repo, capsys)
        assert rc == 0
        assert _events(repo, "learning.written") == []
        assert "`learning.written` was not recorded" in err

    def test_an_append_failure_notes_the_consequence_and_leaves_the_exit_code(
        self, tmp_path, capsys, monkeypatch
    ):
        repo = _repo(tmp_path)
        _write_rules(repo, RULE_A)
        clean_rc, _ = _stop(repo, capsys)
        (repo / LEDGER_REL).unlink()

        def _boom(*_args, **_kwargs):
            raise OSError("ledger is on fire")

        monkeypatch.setattr(ledger, "append_learning_event", _boom)
        rc, err = _stop(repo, capsys)
        assert rc == clean_rc == 0
        assert _events(repo) == []
        assert "`learning.written` was not recorded" in err
        assert "ledger is on fire" in err
        # The consequence, not just the exception: an audit under-counts.
        assert "under-count" in err

    def test_the_corpus_gate_still_blocks_while_telemetry_is_broken(
        self, tmp_path, capsys, monkeypatch
    ):
        """The control for the assertion above. A telemetry failure that also
        suppressed the gate would satisfy 'exit code unchanged' in a fixture
        where the gate was never going to fire."""
        repo = _repo(tmp_path)
        (repo / ".prawduct" / "learnings.md").write_text("# L\n\n## old\n")
        _touch_code(repo)

        def _boom(*_args, **_kwargs):
            raise OSError("ledger is on fire")

        monkeypatch.setattr(ledger, "append_learning_event", _boom)
        rc, err = _stop(repo, capsys)
        assert rc == 2
        assert "LEARNINGS UNMIGRATED" in err


# ---------------------------------------------------------------------------
# learning.fired — critic-consolidate
# ---------------------------------------------------------------------------

PARTIALS_REL = ".prawduct/.critic-partials"
REVIEW_ID = "rev-fired-0001"


def _consolidate_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CLAUDE_PLUGIN_ROOT": str(_ROOT),
    }


def _run_consolidate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "critic-consolidate"],
        cwd=str(repo), capture_output=True, text=True,
        env=_consolidate_env(repo), timeout=60,
    )


def _dispatch(repo: Path, findings: list[dict]) -> None:
    """A complete single-reviewer review, ready to consolidate."""
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    partials = repo / PARTIALS_REL
    partials.mkdir(parents=True, exist_ok=True)
    (repo / ".prawduct" / ".critic-active").write_text(
        json.dumps({"started_at": "2026-09-02T00:00:00Z"})
    )
    manifest = {
        "id": REVIEW_ID,
        "mode": FINAL_MODE,
        "mode_chosen_by": "rule-3 final",
        "roster": ["correctness"],
        "roster_chosen_by": "single-pass",
        "commit_reviewed": head,
        "base_commit": head,
        "base_tree": "basetree000000000000",
        "head_tree": "headtree000000000000",
        "head_commit": None,
        "files_changed": ["code.py"],
        "files_reviewed": ["code.py"],
        "tier": None,
        "scope": "demo-scope",
        "chunk": "01",
        "base_reviewed": None,
        "rendezvous": {
            "correctness": {
                "partial": f"{PARTIALS_REL}/correctness.{REVIEW_ID}.json",
                "started": f"{PARTIALS_REL}/correctness.{REVIEW_ID}.started",
            }
        },
    }
    (partials / "manifest.json").write_text(json.dumps(manifest))
    (partials / f"correctness.{REVIEW_ID}.json").write_text(json.dumps({
        "role": "correctness",
        "goals": "1-3",
        "dispatch_id": REVIEW_ID,
        "commit_reviewed": head,
        "model": "opus",
        "duration_seconds": 90,
        "findings": findings,
        "summary": "correctness review complete.",
    }))


def _finding(name: str, recommendation: str = "Fix it.") -> dict:
    return {
        "name": name,
        "goal": "Nothing Is Broken",
        "severity": "warning",
        "recommendation": recommendation,
    }


class TestConsolidateRecordsRulesFired:
    def test_a_finding_quoting_a_rule_opening_fires_that_rule(self, tmp_path):
        repo = _repo(tmp_path, rules=(RULE_A, RULE_B))
        _dispatch(repo, [_finding(
            f"Regression: {lf.unit_citation(RULE_A)} — this guard matches a literal"
        )])
        result = _run_consolidate(repo)
        assert result.returncode == 0, result.stderr

        fired = _events(repo, "learning.fired")
        assert len(fired) == 1
        assert fired[0]["learning"] == {
            "file": RULES_REL,
            "unit_hash": lf.unit_hash(RULE_A),
            "session": fired[0]["learning"]["session"],
            "review_id": REVIEW_ID,
        }
        assert fired[0]["actor"]["role"] == "critic"

    def test_a_finding_that_cites_nothing_fires_nothing(self, tmp_path):
        repo = _repo(tmp_path, rules=(RULE_A, RULE_B))
        _dispatch(repo, [_finding("The retry loop drops the terminal event")])
        assert _run_consolidate(repo).returncode == 0
        assert _events(repo, "learning.fired") == []

    def test_a_citation_one_word_short_does_not_count(self, tmp_path):
        """The matcher's discriminating case. Seven of the eight opening words
        is a paraphrase, and a matcher that accepted it would fire on any
        finding whose wording happened to overlap a rule's first clause."""
        seven = " ".join(lf.unit_citation(RULE_A).split()[:7])
        repo = _repo(tmp_path, rules=(RULE_A,))
        _dispatch(repo, [_finding(f"Regression: {seven} ...")])
        assert _run_consolidate(repo).returncode == 0
        assert _events(repo, "learning.fired") == []

    def test_the_recommendation_carries_a_citation_too(self, tmp_path):
        """`summary` and `recommendation` are the finding's two prose fields;
        a reviewer may cite the rule in either."""
        repo = _repo(tmp_path, rules=(RULE_A,))
        _dispatch(repo, [_finding(
            "Guard matches a literal",
            recommendation=f"See the rule: {lf.unit_citation(RULE_A)}.",
        )])
        assert _run_consolidate(repo).returncode == 0
        assert len(_events(repo, "learning.fired")) == 1

    def test_a_citation_survives_case_and_whitespace_differences(self, tmp_path):
        repo = _repo(tmp_path, rules=(RULE_A,))
        loud = lf.unit_citation(RULE_A).upper().replace(" ", "\n")
        _dispatch(repo, [_finding(f"Regression: {loud} — see the corpus")])
        assert _run_consolidate(repo).returncode == 0
        assert len(_events(repo, "learning.fired")) == 1

    def test_an_area_file_rule_can_fire(self, tmp_path):
        """Every file the resolver returns, not just core.md — a reviewer reads
        the area files the harness loaded, so a finding may cite any of them."""
        repo = _repo(tmp_path, rules=(RULE_A,))
        area = repo / lf.RULES_DIR_REL / "area.md"
        area.write_text(f"---\npaths:\n  - 'src/**'\n---\n\n# Area\n\n### {RULE_B}\n")
        _dispatch(repo, [_finding(f"Regression: {lf.unit_citation(RULE_B)} ...")])
        assert _run_consolidate(repo).returncode == 0
        fired = _events(repo, "learning.fired")
        assert len(fired) == 1
        assert fired[0]["learning"]["file"] == f"{lf.RULES_DIR_REL}/area.md"

    def test_two_findings_citing_one_rule_are_one_line(self, tmp_path):
        """The question is "did this rule fire in this review". A per-finding
        count would grade reviewers' wording, not the corpus."""
        repo = _repo(tmp_path, rules=(RULE_A,))
        citation = lf.unit_citation(RULE_A)
        _dispatch(repo, [
            _finding(f"First: {citation} here"),
            _finding(f"Second: {citation} there"),
        ])
        assert _run_consolidate(repo).returncode == 0
        assert len(_events(repo, "learning.fired")) == 1

    def test_re_consolidating_does_not_double_emit(self, tmp_path):
        """A replay re-reads the same findings. The review anchor is skipped by
        its own probe; this one has to be skipped by the learning key, which
        includes the review id."""
        repo = _repo(tmp_path, rules=(RULE_A,))
        findings = [_finding(f"Regression: {lf.unit_citation(RULE_A)} ...")]
        _dispatch(repo, findings)
        assert _run_consolidate(repo).returncode == 0
        assert len(_events(repo, "learning.fired")) == 1
        _dispatch(repo, findings)  # the manifest and partials re-materialize
        assert _run_consolidate(repo).returncode == 0
        assert len(_events(repo, "learning.fired")) == 1

    def test_a_repo_with_no_corpus_consolidates_cleanly(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / RULES_REL).unlink()
        _dispatch(repo, [_finding("Something is wrong")])
        result = _run_consolidate(repo)
        assert result.returncode == 0, result.stderr
        assert _events(repo, "learning.fired") == []


class TestConsolidateTelemetryIsBestEffort:
    def test_a_ledger_failure_notes_the_consequence_and_leaves_the_exit_code(
        self, tmp_path, monkeypatch
    ):
        """In-process, because the failure has to be injected. The subprocess
        tests above are what prove the same code path runs for real."""
        from lib import critic_consolidate as cc

        repo = _repo(tmp_path, rules=(RULE_A,))
        _dispatch(repo, [_finding(f"Regression: {lf.unit_citation(RULE_A)} ...")])

        def _boom(*_args, **_kwargs):
            raise OSError("ledger is on fire")

        monkeypatch.setattr(cc.ledger, "append_learning_event", _boom)
        rc = cc.consolidate(repo)
        assert rc == 0
        assert _events(repo, "learning.fired") == []
        assert (repo / ".prawduct" / ".critic-findings.json").is_file()

    def test_the_note_names_what_is_lost(self, tmp_path, monkeypatch, capsys):
        from lib import critic_consolidate as cc

        repo = _repo(tmp_path, rules=(RULE_A,))
        _dispatch(repo, [_finding(f"Regression: {lf.unit_citation(RULE_A)} ...")])
        monkeypatch.setattr(
            cc.ledger, "append_learning_event",
            lambda *a, **k: (_ for _ in ()).throw(OSError("ledger is on fire")),
        )
        cc.consolidate(repo)
        err = capsys.readouterr().err
        assert "`learning.fired` was not recorded" in err
        assert "never-fired" in err
        assert "ledger is on fire" in err


class TestTheTwoEventsJoin:
    """The point of the format: `written` minus `fired` on the unit hash is the
    list of rules nobody has ever cited (question 3). If the two emitters ever
    hashed differently the join would be empty and the answer would read as
    "every rule is dead", which is indistinguishable from a healthy corpus
    nobody cites."""

    def test_written_and_fired_agree_on_the_unit_hash(self, tmp_path, capsys):
        repo = _repo(tmp_path)
        _write_rules(repo, RULE_A, RULE_B)
        _stop(repo, capsys)
        _dispatch(repo, [_finding(f"Regression: {lf.unit_citation(RULE_A)} ...")])
        assert _run_consolidate(repo).returncode == 0

        written = {e["learning"]["unit_hash"] for e in _events(repo, "learning.written")}
        fired = {e["learning"]["unit_hash"] for e in _events(repo, "learning.fired")}
        assert fired and fired < written
        assert written - fired == {lf.unit_hash(RULE_B)}


class TestReviewStatsToleratesTheNewKinds:
    """v1's contract: consumers skip unknown event kinds. `review-stats` counts
    them under `skipped.unknown_kinds` — documented, never renamed, because a
    JSON key is not repurposed and `--json` consumers pin it."""

    def test_learning_events_are_counted_as_unknown_kinds(self, tmp_path, capsys):
        from lib import telemetry

        repo = _repo(tmp_path)
        _write_rules(repo, RULE_A, RULE_B)
        _stop(repo, capsys)
        assert len(_events(repo, "learning.written")) == 2
        capsys.readouterr()

        assert telemetry.review_stats(repo, ["--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        # Skipped WITH A COUNT, never silently — and under the key the `--json`
        # contract already documents rather than a new one.
        assert report["skipped"]["unknown_kinds"] == 2
        assert report["events_total"] == 0

    def test_a_review_event_beside_them_still_aggregates(self, tmp_path, capsys):
        """The control: a `skipped` count that swallowed everything would pass
        the assertion above while breaking the report."""
        from lib import telemetry

        repo = _repo(tmp_path)
        _write_rules(repo, RULE_A)
        _stop(repo, capsys)
        _dispatch(repo, [_finding(f"Regression: {lf.unit_citation(RULE_A)} ...")])
        assert _run_consolidate(repo).returncode == 0
        capsys.readouterr()

        assert telemetry.review_stats(repo, ["--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["events_total"] == 1
        assert report["skipped"]["unknown_kinds"] == 2  # one written, one fired
