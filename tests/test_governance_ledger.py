"""Tests for the governance-event ledger (review-proportionality ch.02).

Three surfaces, one keystone:

* ``prawduct-hook ledger-append`` — the STRUCTURAL WRITER. Agents never
  hand-author JSONL; the helper validates the just-written findings record,
  computes the envelope itself (ts/project/git/scope-fallback), and appends
  one line. Envelope correctness is the schema contract every later event
  kind (``review.pr``, ``build.chunk``, …) and the cross-project aggregator
  (TEL-7A4X) will key on — so it is pinned field by field here.

* ``check-cumulative-critic`` LEDGER FALLBACK — when the latest findings
  file is the wrong kind for the PR gate (chunk/final, or verify with no
  chain anchor), the gate scans the ledger newest-first for a qualifying
  ``review.critic`` payload and evaluates THAT under the unchanged checks.
  The fallback is a cheaper-path gate, so the reject cases are the
  load-bearing coverage (learnings: a skip-gate needs the most adversarial
  coverage): a stale ledger record still fails, a blocking one still fails,
  corrupt lines never crash, and an empty/absent ledger leaves today's
  failure messages intact.

* ``validate_critic_findings`` SCHEMA ADDITIONS — record-level ``model`` and
  per-finding ``files``, optional, validated-when-present (the established
  optional-field pattern).

Real ``git`` repos, sterile env (HOME outside the repo — pyc-cache learning),
mirroring ``tests/test_cumulative_gate.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
CUMULATIVE_MODE = "cumulative (bundle review, ready for merge)"
CHUNK_MODE = "chunk (lighter pass, not ready for push)"
FINAL_MODE = "final (full review, ready for push)"
VERIFY_MODE = "verify-resolutions (delta review, prior findings only)"
LEDGER_REL = ".prawduct/.governance-ledger.jsonl"


# ---------------------------------------------------------------------------
# Helpers (real git, sterile env — mirrors test_cumulative_gate.py)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_findings(repo: Path, **overrides) -> dict:
    data: dict = {
        "mode": CHUNK_MODE,
        "files_reviewed": ["app.py"],
        "findings": [],
        "summary": "Review.",
    }
    data.update(overrides)
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / ".critic-findings.json").write_text(json.dumps(data))
    return data


def _run_hook(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


def _ledger_events(repo: Path) -> list[dict]:
    path = repo / LEDGER_REL
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _append_ledger_event(
    repo: Path,
    payload: dict,
    *,
    event: str = "review.critic",
) -> None:
    """Hand-build a ledger line for GATE tests (the writer tests above pin
    that production lines look exactly like this)."""
    line = json.dumps({
        "schema_version": 1,
        "event": event,
        "ts": "2026-06-10T00:00:00Z",
        "duration_seconds": None,
        "project": repo.name,
        "scope": None,
        "chunk": None,
        "actor": {"role": "critic", "model": None},
        "git": {"head": None, "base": None},
        "review": payload,
    })
    path = repo / LEDGER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _write_session_start(repo: Path, ts: str = "2026-06-09T00:00:00Z") -> None:
    """Mark a governed session as started at ``ts`` (default: before the
    fixture ledger events' ``2026-06-10T00:00:00Z`` envelope ts, so those
    events read as same-session). CRT-8W3F: the ledger fallback requires the
    selected event's ``ts >= .session-start`` and fails closed without the
    marker — fallback tests that expect acceptance must declare the marker."""
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / ".session-start").write_text(ts + "\n")


def _cumulative_payload(commit_reviewed: str, *, blocking: bool = False) -> dict:
    return {
        "mode": CUMULATIVE_MODE,
        "files_reviewed": ["app.py", "core.py"],
        "findings": (
            [{"goal": "Nothing Is Broken", "severity": "blocking", "summary": "boom"}]
            if blocking else []
        ),
        "summary": "Cumulative review.",
        "commit_reviewed": commit_reviewed,
    }


# ---------------------------------------------------------------------------
# ledger-append: envelope correctness (the writer IS the schema)
# ---------------------------------------------------------------------------


class TestLedgerAppendEnvelope:
    def test_envelope_fields_and_payload_equality(self, tmp_path):
        repo = tmp_path / "myproject"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        record = _write_findings(
            repo, mode=FINAL_MODE, duration_seconds=180, commit_reviewed=head,
        )
        r = _run_hook(
            repo, "ledger-append", "--event", "review.critic",
            "--scope", "my-feature", "--chunk", "02", "--model", "opus",
        )
        assert r.returncode == 0, r.stderr
        assert "appended" in r.stdout

        events = _ledger_events(repo)
        assert len(events) == 1
        ev = events[0]
        assert ev["schema_version"] == 1
        assert ev["event"] == "review.critic"
        # ts is ISO-8601 UTC ("Z" suffix) — the cross-project sort key.
        assert ev["ts"].endswith("Z") and "T" in ev["ts"]
        assert ev["duration_seconds"] == 180
        assert ev["project"] == "myproject"
        assert ev["scope"] == "my-feature"
        assert ev["chunk"] == "02"
        assert ev["actor"] == {"role": "critic", "model": "opus"}
        assert ev["git"]["head"] == head
        # Payload is the findings record VERBATIM — the latest-record file
        # and the ledger never drift because the same bytes feed both.
        assert ev["review"] == record

    def test_nullable_duration_and_model_never_invented(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)  # no duration_seconds, no model
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert ev["duration_seconds"] is None
        assert ev["actor"]["model"] is None

    def test_model_falls_back_to_findings_record(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo, model="opus")
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["actor"]["model"] == "opus"

    def test_appends_accumulate(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0
        _write_findings(repo, mode=FINAL_MODE)
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0
        events = _ledger_events(repo)
        assert len(events) == 2
        assert events[0]["review"]["mode"] == CHUNK_MODE
        assert events[1]["review"]["mode"] == FINAL_MODE


class TestLedgerAppendScopeFallback:
    """--scope explicit > plan frontmatter `scope:` > filename > null."""

    def test_explicit_scope_wins_over_plan(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        self._write_plan(repo, frontmatter_scope="plan-scope")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.critic",
                      "--scope", "explicit-scope")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] == "explicit-scope"

    def test_fallback_reads_plan_frontmatter_scope(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        self._write_plan(repo, frontmatter_scope="plan-scope")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] == "plan-scope"

    def test_fallback_derives_scope_from_plan_filename(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        self._write_plan(repo, frontmatter_scope=None, name="build-plan-my-feature.md")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] == "my-feature"

    def test_no_plan_means_null_scope(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] is None

    @staticmethod
    def _write_plan(repo: Path, *, frontmatter_scope, name: str = "build-plan-x.md"):
        prawduct = repo / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        body = "# Plan\n\n## Status\n- [ ] Chunk 01: A\n"
        if frontmatter_scope:
            body = f"---\nartifact: build-plan\nscope: {frontmatter_scope}\n---\n\n{body}"
        (artifacts / name).write_text(body)
        (prawduct / "project-state.yaml").write_text(
            f"active_build_plan: artifacts/{name}\n"
        )


class TestLedgerAppendRejects:
    """The writer is the validation boundary — bad input never enters the
    history the PR gate trusts."""

    def test_missing_findings_file_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 1
        assert "no findings record" in r.stderr
        assert not (repo / LEDGER_REL).exists()

    def test_invalid_findings_rejected_nothing_appended(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        prawduct = repo / ".prawduct"
        prawduct.mkdir(parents=True, exist_ok=True)
        (prawduct / ".critic-findings.json").write_text(
            json.dumps({"mode": "chunk", "findings": [], "summary": "x"})  # bare token + no files_reviewed
        )
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 1
        assert "schema validation" in r.stderr
        assert not (repo / LEDGER_REL).exists()

    def test_unknown_event_kind_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.unknown")
        assert r.returncode == 1
        assert "unknown event kind" in r.stderr
        assert not (repo / LEDGER_REL).exists()

    def test_missing_event_flag_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append")
        assert r.returncode == 1
        assert "--event is required" in r.stderr


# ---------------------------------------------------------------------------
# ledger-append --event review.pr (review-proportionality ch.05)
# ---------------------------------------------------------------------------


PR_EVIDENCE_REL = ".prawduct/.pr-reviews/feature--example.json"


def _write_pr_evidence(repo: Path, **overrides) -> dict:
    data: dict = {
        "timestamp": "2026-06-10T00:00:00Z",
        "branch": "feature/example",
        "base": "develop",
        "pr_number": None,
        "mode": "pr-scoped",
        "record_consumed": True,
        "spot_checks": [{"claim": "x pinned by test y", "verified": True}],
        "findings": [],
        "summary": "No issues found. PR is ready to create.",
    }
    data.update(overrides)
    path = repo / PR_EVIDENCE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


class TestLedgerAppendReviewPr:
    """``review.pr`` events: the PR reviewer's evidence joins the same ledger
    so role-vs-role model-efficiency comparisons (data requirement 1) have
    both review roles. The evidence source is the caller-computed
    ``--findings`` path — required for ``review.pr``, rejected for
    ``review.critic`` (whose only trusted source stays the canonical file)."""

    def test_envelope_role_pr_and_payload_equality(self, tmp_path):
        repo = tmp_path / "myproject"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        record = _write_pr_evidence(repo, duration_seconds=240, model="opus")
        r = _run_hook(
            repo, "ledger-append", "--event", "review.pr",
            "--findings", PR_EVIDENCE_REL, "--scope", "my-feature",
        )
        assert r.returncode == 0, r.stderr
        events = _ledger_events(repo)
        assert len(events) == 1
        ev = events[0]
        assert ev["event"] == "review.pr"
        assert ev["actor"] == {"role": "pr", "model": "opus"}
        assert ev["duration_seconds"] == 240
        assert ev["scope"] == "my-feature"
        assert ev["git"]["head"] == head
        # Same family-named payload key as review.critic — review-stats
        # aggregates both roles without a telemetry change.
        assert ev["review"] == record

    def test_explicit_model_flag_wins(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo, model="opus")
        r = _run_hook(repo, "ledger-append", "--event", "review.pr",
                      "--findings", PR_EVIDENCE_REL, "--model", "fable")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["actor"]["model"] == "fable"

    def test_review_pr_requires_findings_path(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.pr")
        assert r.returncode == 1
        assert "--findings" in r.stderr
        assert not (repo / LEDGER_REL).exists()

    def test_review_critic_rejects_findings_path(self, tmp_path):
        # The canonical-source property: an arbitrary file must never enter
        # the history the PR gate trusts as a review.critic payload.
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "review.critic",
                      "--findings", ".prawduct/.critic-findings.json")
        assert r.returncode == 1
        assert "only valid for review.pr" in r.stderr
        assert not (repo / LEDGER_REL).exists()

    def test_missing_evidence_file_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        r = _run_hook(repo, "ledger-append", "--event", "review.pr",
                      "--findings", PR_EVIDENCE_REL)
        assert r.returncode == 1
        assert "no findings record" in r.stderr
        assert not (repo / LEDGER_REL).exists()

    @pytest.mark.parametrize(
        "overrides",
        [{"findings": "not-a-list"}, {"summary": ""}, {"summary": 7}],
        ids=["findings_not_list", "summary_empty", "summary_not_str"],
    )
    def test_invalid_evidence_rejected_nothing_appended(self, tmp_path, overrides):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo, **overrides)
        r = _run_hook(repo, "ledger-append", "--event", "review.pr",
                      "--findings", PR_EVIDENCE_REL)
        assert r.returncode == 1
        assert "PR-evidence validation" in r.stderr
        assert not (repo / LEDGER_REL).exists()


# ---------------------------------------------------------------------------
# check-cumulative-critic: the ledger fallback
# ---------------------------------------------------------------------------


def _run_gate(repo: Path) -> subprocess.CompletedProcess:
    return _run_hook(repo, "check-cumulative-critic")


def _interleaved_repo(tmp_path):
    """Repo modeling an interleaved Critic→PR cycle: HEAD is on branch X, but
    the single findings slot was last written for a SIBLING branch Y. Returns
    ``(repo, x_head, y_head)`` — ``x_head`` IS HEAD; ``y_head`` is the sibling's
    tip (resolves in the shared object store, does not cover ``x_head``)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _commit_file(repo, "app.py", "print(1)\n", "base")
    x_head = _commit_file(repo, "x.py", "x = 1\n", "x branch work")  # main == X
    _git(repo, "checkout", "--quiet", "-b", "siblingY", base)
    y_head = _commit_file(repo, "y.py", "y = 1\n", "y branch work")
    _git(repo, "checkout", "--quiet", "main")  # back to X; HEAD == x_head
    return repo, x_head, y_head


class TestGateLedgerFallbackAccepts:
    def test_stale_sibling_slot_rescued_by_covering_ledger(self, tmp_path):
        # CRT-2K9F: interleaved Critic→PR cycles overwrote the single slot with
        # a SIBLING branch's cumulative (covers Y's HEAD — stale here). THIS
        # branch's own covering record is still in the append-only ledger, so
        # the gate passes via fallback instead of forcing a needless re-review.
        repo, x_head, y_head = _interleaved_repo(tmp_path)
        _append_ledger_event(repo, _cumulative_payload(x_head))  # X's own record
        _write_session_start(repo)
        _write_findings(repo, mode=CUMULATIVE_MODE, commit_reviewed=y_head)  # sibling slot
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr
        assert "satisfied" in r.stdout and "ledger fallback" in r.stdout
        assert "ledger-fallback" in r.stderr and "CRT-2K9F" in r.stderr

    def test_chunk_latest_plus_qualifying_ledger_cumulative_passes(self, tmp_path):
        # THE deferred-review fix: a chunk review after the cumulative no
        # longer destroys the PR gate's evidence — the ledger still holds it.
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)  # latest slot = chunk review
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr
        assert "satisfied" in r.stdout and "ledger fallback" in r.stdout
        assert "ledger-fallback" in r.stderr  # the gate teaches what it did

    def test_newest_qualifying_event_wins(self, tmp_path):
        # Two cumulatives in history: only the newer covers HEAD. Newest-first
        # scan must pick it (oldest-first would fail the gate on stale data).
        repo = tmp_path / "repo"
        _init_repo(repo)
        old = _commit_file(repo, "app.py", "print(1)\n", "init")
        head = _commit_file(repo, "core.py", "x = 2\n", "more code")
        _append_ledger_event(repo, _cumulative_payload(old))
        _append_ledger_event(repo, _cumulative_payload(head))
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr

    def test_corrupt_lines_skipped_with_note_then_passes(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))
        path = repo / LEDGER_REL
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("{not json\n")
            fh.write('"a bare string"\n')
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr
        assert "skipping" in r.stderr  # corrupt lines noted, never fatal

    def test_non_review_event_kinds_are_skipped(self, tmp_path):
        # Forward-compat: a future event kind in the history must not confuse
        # the gate — it scans past to the qualifying review.critic event.
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))
        _append_ledger_event(repo, {"anything": True}, event="build.chunk")
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr


class TestGateLedgerFallbackStaysHonest:
    """The fallback is a cheaper path, not a softer gate — every existing
    check still applies to the ledger record it selects."""

    def test_stale_ledger_cumulative_still_fails(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        reviewed = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(reviewed))
        _commit_file(repo, "core.py", "x = 2\n", "code after review")  # HEAD moves
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "stale" in r.stderr and "core.py" in r.stderr

    def test_blocking_ledger_cumulative_still_fails(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head, blocking=True))
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "blocking" in r.stderr

    def test_no_ledger_keeps_wrong_mode_message(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo, mode=CHUNK_MODE, commit_reviewed=head)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "wrong-mode" in r.stderr

    def test_ledger_with_only_nonqualifying_events_keeps_wrong_mode(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        chunk_payload = {
            "mode": CHUNK_MODE, "files_reviewed": ["app.py"],
            "findings": [], "summary": "chunk.", "commit_reviewed": head,
        }
        _append_ledger_event(repo, chunk_payload)
        _write_findings(repo, mode=CHUNK_MODE, commit_reviewed=head)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "wrong-mode" in r.stderr

    def test_verify_without_anchor_keeps_chain_missing_anchor_message(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo, mode=VERIFY_MODE, commit_reviewed=head)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "chain-missing-anchor" in r.stderr

    def test_verify_without_anchor_falls_back_to_ledger(self, tmp_path):
        # The OTHER single-slot conflict: a plain (anchor-less) verify pass
        # in the latest slot, with the real cumulative preserved in history.
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))
        _write_session_start(repo)
        _write_findings(repo, mode=VERIFY_MODE, commit_reviewed=head)
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr

    def test_review_pr_event_never_satisfies_the_critic_gate(self, tmp_path):
        # ch.05: review.pr events share the ledger, but the cumulative-Critic
        # gate's evidence is review.critic ONLY — a PR-review payload (even
        # one dressed in a cumulative-looking mode) must not vouch for code
        # soundness.
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(
            repo, _cumulative_payload(head), event="review.pr",
        )
        _write_findings(repo, mode=CHUNK_MODE, commit_reviewed=head)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "wrong-mode" in r.stderr

    def test_stale_sibling_slot_no_covering_ledger_still_blocks(self, tmp_path):
        # CRT-2K9F honesty: the slot covers a sibling's HEAD (stale here) and
        # the ledger holds NO record covering THIS HEAD → the gate still blocks
        # on the slot's stale verdict; the fallback never invents coverage.
        repo, _x_head, y_head = _interleaved_repo(tmp_path)
        _append_ledger_event(repo, _cumulative_payload(y_head))  # sibling's, also stale here
        _write_session_start(repo)
        _write_findings(repo, mode=CUMULATIVE_MODE, commit_reviewed=y_head)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "stale" in r.stderr
        assert "satisfied" not in r.stdout

    def test_covering_slot_record_evaluated_directly_not_via_ledger(self, tmp_path):
        # The CRT-2K9F rescue is scoped to a STALE slot: a qualifying slot that
        # COVERS HEAD is evaluated directly — the ledger is never consulted, so
        # a clean covering slot passes without any fallback message.
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))  # present but unused
        _write_session_start(repo)
        _write_findings(repo, mode=CUMULATIVE_MODE, commit_reviewed=head)
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr
        assert "satisfied" in r.stdout
        assert "ledger-fallback" not in r.stderr  # direct eval, no fallback


class TestGateLedgerFallbackFreshness:
    """CRT-8W3F: the fallback only rescues evidence from THIS session.

    The findings file is a single slot constantly overwritten by the live
    flow, but the ledger keeps every review forever — without a freshness
    bound, a days-old cumulative from prior work satisfies the PR gate
    whenever only ``.md`` changed since. The fallback record's envelope
    ``ts`` must be ``>= .prawduct/.session-start`` (the ``tests_are_current``
    session model); a missing marker or a ts-less event fails closed to the
    gate's honest wrong-mode message.
    """

    def test_record_predating_session_fails_closed(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))  # ts 06-10T00:00
        _write_session_start(repo, ts="2026-06-10T12:00:00Z")  # session after
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "wrong-mode" in r.stderr
        assert "predates session" in r.stderr  # the skip is taught, not silent
        assert "ledger-fallback" not in r.stderr

    def test_missing_session_start_marker_fails_closed(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _append_ledger_event(repo, _cumulative_payload(head))
        _write_findings(repo, mode=CHUNK_MODE)  # no .session-start written
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "wrong-mode" in r.stderr
        assert "ledger-fallback" not in r.stderr

    def test_event_without_ts_is_skipped(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        # Hand-build an envelope with no ts at all — freshness unverifiable.
        line = json.dumps({
            "schema_version": 1, "event": "review.critic",
            "review": _cumulative_payload(head),
        })
        path = repo / LEDGER_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(line + "\n")
        _write_session_start(repo)
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 1
        assert "wrong-mode" in r.stderr
        assert "skipping" in r.stderr

    def test_fresh_record_behind_stale_one_still_wins(self, tmp_path):
        # Newest-first scan + freshness filter compose: a stale qualifying
        # event in front of (newer than) nothing, behind a fresh one — the
        # fresh event is newest, the stale one is never reached. The inverse
        # layering (stale NEWER than fresh) cannot occur: ledger ts is
        # append-ordered. So the meaningful composition is: history holds
        # old prior-work reviews AND this session's cumulative — gate passes.
        repo = tmp_path / "repo"
        _init_repo(repo)
        old = _commit_file(repo, "app.py", "print(1)\n", "init")
        head = _commit_file(repo, "core.py", "x = 2\n", "more code")
        _append_ledger_event(repo, _cumulative_payload(old))   # prior work
        _append_ledger_event(repo, _cumulative_payload(head))  # this session
        _write_session_start(repo, ts="2026-06-09T00:00:00Z")
        _write_findings(repo, mode=CHUNK_MODE)
        r = _run_gate(repo)
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Schema additions: record-level `model`, per-finding `files`
# ---------------------------------------------------------------------------


class TestFindingsSchemaAdditions:
    def _valid(self, **overrides) -> dict:
        data = {
            "mode": FINAL_MODE,
            "files_reviewed": ["app.py"],
            "findings": [],
            "summary": "ok",
        }
        data.update(overrides)
        return data

    def _validate(self, data: dict) -> bool:
        from lib.gates import _validate_critic_findings_data

        return _validate_critic_findings_data(data)

    @pytest.mark.parametrize("model", ["opus", None])
    def test_model_valid_shapes_accepted(self, model):
        assert self._validate(self._valid(model=model))

    @pytest.mark.parametrize("model", ["", "   ", 7, ["opus"]])
    def test_model_invalid_shapes_rejected(self, model):
        assert not self._validate(self._valid(model=model))

    def test_finding_files_valid_list_accepted(self):
        finding = {"goal": "g", "severity": "warning", "summary": "s",
                   "files": ["a.py", "b.py"]}
        assert self._validate(self._valid(findings=[finding]))

    @pytest.mark.parametrize("files", ["a.py", {"a.py": 1}, [""], [7], ["a.py", "  "]])
    def test_finding_files_invalid_shapes_rejected(self, files):
        finding = {"goal": "g", "severity": "warning", "summary": "s",
                   "files": files}
        assert not self._validate(self._valid(findings=[finding]))

    def test_finding_without_files_still_valid(self):
        finding = {"goal": "g", "severity": "warning", "summary": "s"}
        assert self._validate(self._valid(findings=[finding]))
