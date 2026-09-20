"""Tests for the governance-event ledger (review-proportionality ch.02).

Three surfaces, one keystone:

* ``prawduct-hook ledger-append`` — the STRUCTURAL WRITER. Agents never
  hand-author JSONL; the helper validates the just-written findings record,
  computes the envelope itself (ts/project/git/scope-fallback), and appends
  one line. Envelope correctness is the schema contract every later event
  kind (``review.pr``, ``build.chunk``, …) and the cross-project aggregator
  (TEL-7A4X) will key on — so it is pinned field by field here.

* (The ``check-cumulative-critic`` LEDGER FALLBACK this file once pinned
  was deleted in kernel-v3 chunk 04: the PR gate now composes over the
  multi-record evidence store, so a later chunk review can no longer
  destroy the gate's evidence and no fallback source is needed. Its
  still-blocks coverage lives in ``tests/test_cumulative_gate.py``.)

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

ROOT = Path(__file__).resolve().parent.parent / "plugin"
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

    def test_fallback_reads_scope_under_a_comment_header(self, tmp_path):
        """A third of this repo's plans open with an HTML comment before the
        frontmatter, and the hand-rolled scan this fallback used to run required
        `---` on line 1 — so it silently fell through to the filename stem for
        all of them. The filename here deliberately does NOT match the scope, so
        the stem fallback cannot satisfy the assertion by accident."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        self._write_plan(
            repo,
            frontmatter_scope="plan-scope",
            name="build-plan-other.md",
            header=True,
        )
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] == "plan-scope"

    def test_null_scope_falls_through_to_the_filename(self, tmp_path):
        """`scope: null` is the documented explicit opt-out. The old scan
        returned any truthy token, so it wrote the literal string "null" into
        the ledger's scope field."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        self._write_plan(
            repo, frontmatter_scope="null", name="build-plan-my-feature.md"
        )
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] == "my-feature"

    def test_indented_scope_under_another_key_is_not_read(self, tmp_path):
        """The old scan compared `line.strip()`, so a `scope:` nested under
        another frontmatter key matched as if it were top-level."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        prawduct = repo / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "build-plan-my-feature.md").write_text(
            "---\nartifact: build-plan\ngoverned_by:\n  scope: nested-not-mine\n---\n\n"
            "# Plan\n\n## Status\n- [ ] Chunk 01: A\n",
            encoding="utf-8",
        )
        (prawduct / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-my-feature.md\n"
        )
        r = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert r.returncode == 0, r.stderr
        assert _ledger_events(repo)[0]["scope"] == "my-feature"

    @staticmethod
    def _write_plan(
        repo: Path,
        *,
        frontmatter_scope,
        name: str = "build-plan-x.md",
        header: bool = False,
    ):
        prawduct = repo / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        body = "# Plan\n\n## Status\n- [ ] Chunk 01: A\n"
        if frontmatter_scope:
            body = f"---\nartifact: build-plan\nscope: {frontmatter_scope}\n---\n\n{body}"
        if header:
            body = f"<!-- Build Plan — {name} -->\n\n{body}"
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
        "mode": "pr",
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


class TestReviewAnchorIdempotency:
    """One review must anchor exactly one ledger event.

    The evidence fact survives a second consolidation via `(kind, id)`
    first-wins dedupe, but this ledger has no key and no dedupe, and
    `review-stats` counts its lines — so a second anchor double-counts the
    review in the instrument review proportionality is judged by. Observed live
    2026-07-29: one fact anchored two `review.critic` events a second apart.

    Two paths reach a second consolidation, and the probe treats them
    differently. A **replay** — the same manifest and partials re-materializing
    after success, or a crash between the fact append and `remove_partials` —
    is closed outright. An **overlap**, two consolidations running past the
    manifest check at once, is only narrowed: the probe is read-then-write with
    no lock. Not a sequential two-caller story: a successful consolidation
    deletes the manifest the Stop-hook self-heal needs, so that path is a
    no-op. A maintainer seeing this recur should look for the lock.
    """

    def test_probe_finds_an_existing_anchor_by_fact_id(self, tmp_path):
        from lib import ledger

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        _commit_file(repo, "app.py", "x = 1\n", "c1")
        _write_findings(repo, fact_id="rev-abc123")
        assert _run_hook(
            repo, "ledger-append", "--event", "review.critic"
        ).returncode == 0

        prawduct = repo / ".prawduct"
        assert ledger.review_event_exists(prawduct, "rev-abc123") is True
        assert ledger.review_event_exists(prawduct, "rev-nope") is False
        # A non-string / empty id is never a match rather than an error.
        assert ledger.review_event_exists(prawduct, "") is False
        assert ledger.review_event_exists(prawduct, None) is False

    def test_probe_is_false_on_an_absent_ledger(self, tmp_path):
        from lib import ledger

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        assert ledger.review_event_exists(repo / ".prawduct", "rev-abc123") is False

    def test_probe_ignores_events_without_the_fact_id(self, tmp_path):
        """Older events carry no `review.fact_id`; they must not match, and must
        not stop the scan from reaching an event that does."""
        from lib import ledger

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        _commit_file(repo, "app.py", "x = 1\n", "c1")
        _write_findings(repo, fact_id="rev-first")
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0
        _write_findings(repo)  # no fact_id at all
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0

        prawduct = repo / ".prawduct"
        assert ledger.review_event_exists(prawduct, "rev-first") is True


class TestLedgerAppendRefusesLearningKinds:
    """`learning.*` is machine-emitted or it is nothing.

    The fields are DERIVED — a unit hash from the corpus, a session from the
    `.session-start` marker — so a hand-typed event agrees with neither, and
    the instrument then reports a rule that fired in no review or a rule nobody
    wrote. The refusal is what keeps a `learning.*` line meaning what the join
    assumes it means.
    """

    @pytest.mark.parametrize("kind", ["learning.written", "learning.fired"])
    def test_cli_refuses_a_real_learning_kind(self, tmp_path, kind):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", kind)
        assert r.returncode == 1
        assert "never by hand" in r.stderr
        assert _ledger_events(repo) == []

    def test_a_mistyped_learning_kind_gets_the_same_answer(self, tmp_path):
        """Not "unknown kind (allowed: … learning.written …)" — that message
        invites the caller to fix the spelling and try again, and the retry
        would be refused for a reason the message never gave."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "learning.writen")
        assert r.returncode == 1
        assert "never by hand" in r.stderr

    def test_the_unknown_kind_message_never_advertises_a_learning_kind(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        r = _run_hook(repo, "ledger-append", "--event", "build.chunk")
        assert r.returncode == 1
        assert "unknown event kind" in r.stderr
        assert "learning." not in r.stderr

    def test_review_kinds_still_append(self, tmp_path):
        """The control. A refusal that also refused `review.critic` would pass
        every assertion above while breaking the writer."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0
        assert len(_ledger_events(repo)) == 1


class TestAppendLearningEvent:
    """The one entry point for `learning.*`, and its idempotence key."""

    @staticmethod
    def _repo(tmp_path, *, session: bool = True) -> Path:
        repo = tmp_path / "myproject"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        prawduct = repo / ".prawduct"
        prawduct.mkdir(parents=True, exist_ok=True)
        if session:
            (prawduct / ".session-start").write_text("")
        return repo

    def test_written_envelope_role_and_payload(self, tmp_path):
        from lib import ledger

        repo = self._repo(tmp_path)
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert ledger.append_learning_event(
            repo, "learning.written",
            file=".claude/rules/learnings/core.md", unit_hash="abc1234567890def",
        ) is True

        events = _ledger_events(repo)
        assert len(events) == 1
        ev = events[0]
        assert ev["schema_version"] == 1
        assert ev["event"] == "learning.written"
        assert ev["ts"].endswith("Z") and "T" in ev["ts"]
        assert ev["project"] == "myproject"
        assert ev["git"]["head"] == head
        # A measurement of an act, not of a duration, and no model produced it.
        assert ev["duration_seconds"] is None
        assert ev["actor"] == {"role": "builder", "model": None}
        assert ev["learning"] == {
            "file": ".claude/rules/learnings/core.md",
            "unit_hash": "abc1234567890def",
            "session": ev["learning"]["session"],
            "review_id": None,
        }
        assert ev["learning"]["session"].endswith("Z")
        # The payload nests under its own family key — `review` belongs to the
        # review kinds and a consumer switching on it must not see this line.
        assert "review" not in ev

    def test_fired_carries_the_review_id_and_the_critic_role(self, tmp_path):
        from lib import ledger

        repo = self._repo(tmp_path)
        assert ledger.append_learning_event(
            repo, "learning.fired", file="a.md", unit_hash="h1", review_id="rev-9",
        ) is True
        ev = _ledger_events(repo)[0]
        assert ev["actor"]["role"] == "critic"
        assert ev["learning"]["review_id"] == "rev-9"

    def test_session_is_null_when_no_marker_exists(self, tmp_path):
        """Nullable, never invented: a headless probe or a fixture has no
        session, and a made-up id would bucket those events on their own."""
        from lib import ledger

        repo = self._repo(tmp_path, session=False)
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is True
        assert _ledger_events(repo)[0]["learning"]["session"] is None

    def test_scope_uses_the_existing_build_plan_fallback(self, tmp_path):
        from lib import ledger

        repo = self._repo(tmp_path)
        plans = repo / ".prawduct" / "artifacts"
        plans.mkdir(parents=True, exist_ok=True)
        (plans / "build-plan-my-feature.md").write_text("---\nscope: plan-scope\n---\n")
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "active_build_plan: artifacts/build-plan-my-feature.md\n"
        )
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is True
        assert _ledger_events(repo)[0]["scope"] == "plan-scope"

    def test_a_second_call_with_the_same_key_appends_nothing(self, tmp_path):
        """The Stop hook runs every turn, so the same new rule is re-observed
        until the session ends. Without the key the ledger counts one rule as
        dozens and the instrument reads the opposite of the truth."""
        from lib import ledger

        repo = self._repo(tmp_path)
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is True
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is False
        assert len(_ledger_events(repo)) == 1

    @pytest.mark.parametrize(
        "second",
        [
            {"file": "b.md", "unit_hash": "h1"},
            {"file": "a.md", "unit_hash": "h2"},
            {"file": "a.md", "unit_hash": "h1", "review_id": "rev-1"},
        ],
        ids=["different-file", "different-unit", "different-review"],
    )
    def test_each_key_field_separates_two_events(self, tmp_path, second):
        from lib import ledger

        repo = self._repo(tmp_path)
        ledger.append_learning_event(
            repo, "learning.fired", file="a.md", unit_hash="h1",
        )
        assert ledger.append_learning_event(repo, "learning.fired", **second) is True
        assert len(_ledger_events(repo)) == 2

    def test_the_kind_separates_two_events(self, tmp_path):
        from lib import ledger

        repo = self._repo(tmp_path)
        ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        )
        assert ledger.append_learning_event(
            repo, "learning.fired", file="a.md", unit_hash="h1",
        ) is True
        assert len(_ledger_events(repo)) == 2

    def test_a_new_session_records_the_same_rule_again(self, tmp_path):
        """`session` is in the key because question 1 counts rules written PER
        SESSION — the same rule surviving into a second session's base tree is
        not written twice, but a corpus arriving fresh in two repos is."""
        import os
        import time

        from lib import ledger

        repo = self._repo(tmp_path)
        marker = repo / ".prawduct" / ".session-start"
        os.utime(marker, (time.time() - 7200, time.time() - 7200))
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is True
        os.utime(marker, None)  # a new session boundary
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is True
        assert len(_ledger_events(repo)) == 2

    def test_a_non_learning_kind_is_refused_at_the_api_too(self, tmp_path):
        """Fail-closed at the write boundary, exactly as the CLI does — the
        caller catching this turns the mistake into a visible NOTE."""
        from lib import ledger

        repo = self._repo(tmp_path)
        for kind in ("review.critic", "learning.typo", ""):
            with pytest.raises(ValueError):
                ledger.append_learning_event(
                    repo, kind, file="a.md", unit_hash="h1",
                )
        assert _ledger_events(repo) == []

    def test_the_probe_ignores_review_events_and_malformed_payloads(self, tmp_path):
        from lib import ledger

        repo = self._repo(tmp_path)
        _write_findings(repo)
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0
        path = repo / LEDGER_REL
        with open(path, "a") as fh:
            fh.write(json.dumps({"event": "learning.written", "learning": "not-a-dict"}) + "\n")
        assert ledger.append_learning_event(
            repo, "learning.written", file="a.md", unit_hash="h1",
        ) is True


class TestLearningEventProbe:
    """`learning_event_exists` directly — the same three cases the review
    anchor's probe carries, because the class of defect is identical: a probe
    that answers wrong makes the ledger double-count, and `review-stats` and
    the never-fired join both read counts.
    """

    @staticmethod
    def _seed(repo: Path) -> None:
        from lib import ledger

        _init_repo(repo)
        _commit_file(repo, "app.py", "x = 1\n", "c1")
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)
        ledger.append_learning_event(
            repo, "learning.fired", file="a.md", unit_hash="h1", review_id="rev-1",
        )

    def test_finds_an_existing_event_by_its_whole_key(self, tmp_path):
        from lib import ledger

        repo = tmp_path / "repo"
        repo.mkdir()
        self._seed(repo)
        prawduct = repo / ".prawduct"
        key = dict(file="a.md", unit_hash="h1", session=None, review_id="rev-1")
        assert ledger.learning_event_exists(prawduct, "learning.fired", **key) is True
        # Each field, alone, makes it a different event.
        assert ledger.learning_event_exists(
            prawduct, "learning.written", **key
        ) is False
        assert ledger.learning_event_exists(
            prawduct, "learning.fired", **{**key, "file": "b.md"}
        ) is False
        assert ledger.learning_event_exists(
            prawduct, "learning.fired", **{**key, "unit_hash": "h2"}
        ) is False
        assert ledger.learning_event_exists(
            prawduct, "learning.fired", **{**key, "review_id": "rev-2"}
        ) is False
        assert ledger.learning_event_exists(
            prawduct, "learning.fired", **{**key, "session": "2026-01-01T00:00:00Z"}
        ) is False

    def test_is_false_on_an_absent_ledger(self, tmp_path):
        from lib import ledger

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_repo(repo)
        assert ledger.learning_event_exists(
            repo / ".prawduct", "learning.written",
            file="a.md", unit_hash="h1", session=None,
        ) is False

    def test_a_review_event_does_not_stop_the_scan(self, tmp_path):
        """`review.*` lines sit between learning events and carry no `learning`
        key; they must be skipped, not read as a mismatch that ends the walk."""
        from lib import ledger

        repo = tmp_path / "repo"
        repo.mkdir()
        self._seed(repo)
        _write_findings(repo)
        assert _run_hook(repo, "ledger-append", "--event", "review.critic").returncode == 0
        assert ledger.learning_event_exists(
            repo / ".prawduct", "learning.fired",
            file="a.md", unit_hash="h1", session=None, review_id="rev-1",
        ) is True


# ---------------------------------------------------------------------------
# The dispatch clock: `dispatched_at` on the envelope (pr-review-payload ch.01)
# ---------------------------------------------------------------------------


MARKER_REL = ".prawduct/.pr-review-dispatch.json"
CRITIC_MARKER_REL = ".prawduct/.critic-review-dispatch.json"


def _duration_reason(result: subprocess.CompletedProcess) -> str:
    """The `duration:` line `ledger-append` printed, and nothing else.

    Asserting a phrase against the whole of stdout does not test the reason: the
    append prints the ledger's absolute path, and under pytest that path contains
    the TEST's own name, so `assert "unreadable" in result.stdout` passed for
    `test_an_unreadable_mark_...` with the reason blanked out. A mutation sweep
    found it; reading could not. Bind each assertion to the line that carries the
    behaviour.
    """
    lines = [ln for ln in result.stdout.splitlines() if ln.startswith("duration: ")]
    assert len(lines) == 1, f"expected exactly one duration line, got {lines!r}"
    return lines[0][len("duration: "):]


class TestDispatchClock:
    """`duration_seconds` is the reviewing model's estimate; `dispatched_at` is a
    clock this code read. The whole value of the field is that its ABSENCE is
    unambiguous, so most of what follows asserts degradations: every one of them
    must omit the key entirely and say why, because a null or a zero is a VALUE
    naming the absence and would be averaged into a real population."""

    def _pr_append(self, repo: Path, **kw):
        return _run_hook(
            repo, "ledger-append", "--event", "review.pr",
            "--findings", PR_EVIDENCE_REL, **kw
        )

    def test_a_marked_dispatch_produces_dispatched_at(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo, duration_seconds=240)

        marked = _run_hook(repo, "pr-review-dispatch", "--begin")
        assert marked.returncode == 0, marked.stderr
        # The WRITING run's own output is what an operator reads; checking only
        # the state afterwards would not verify what it reported.
        assert "dispatch marked:" in marked.stdout

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        # The stamp the writing run reported is the stamp that lands on the event.
        reported = marked.stdout.split("dispatch marked:", 1)[1].split("(")[0].strip()
        assert ev["dispatched_at"] == reported
        assert ev["dispatched_at"].endswith("Z")
        # The estimate is NOT displaced — both populations stay readable.
        assert ev["duration_seconds"] == 240
        assert "measured from a dispatch mark" in _duration_reason(r)

    def test_an_unmarked_dispatch_omits_the_key_entirely(self, tmp_path):
        """Red if absence is ever rendered as a null or a zero.

        `not in` rather than `is None`: a key present with a null value is the
        exact failure this field was designed against, and `.get()` cannot tell
        the two apart.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo, duration_seconds=240)

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert "dispatched_at" not in ev
        assert "no dispatch mark" in _duration_reason(r)

    def test_the_mark_is_cleared_so_it_cannot_attach_twice(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)

        _run_hook(repo, "pr-review-dispatch", "--begin")
        assert (repo / MARKER_REL).is_file()
        self._pr_append(repo)
        assert not (repo / MARKER_REL).is_file()

        self._pr_append(repo)
        events = _ledger_events(repo)
        assert len(events) == 2
        assert "dispatched_at" in events[0]
        assert "dispatched_at" not in events[1]

    def test_a_stale_mark_from_another_tree_does_not_attach(self, tmp_path):
        """The abandoned-run case, and the reason staleness is a TREE question.

        A review dispatched, never appended, then work committed on top: the
        marker survives, and attaching it would report an interval spanning
        everything that happened in between as if it were review time.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)

        _run_hook(repo, "pr-review-dispatch", "--begin")
        _commit_file(repo, "app.py", "print(2)\n", "work landed while the review was abandoned")

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert "dispatched_at" not in ev
        assert "different tree" in _duration_reason(r)
        # Cleared even though it did not attach: HEAD only moves forward, so a
        # mark that does not match today can never match later.
        assert not (repo / MARKER_REL).is_file()

    def test_a_critic_append_leaves_a_live_pr_mark_alone(self, tmp_path):
        """The concurrency case. The Critic and the PR reviewer run at the same
        time, so a `review.critic` append that consumed this marker would delete
        a live PR review's measurement — silently, and only on the timing where
        the two actually overlap, which is the timing the design wants."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo, duration_seconds=240)
        _write_findings(repo)

        _run_hook(repo, "pr-review-dispatch", "--begin")
        critic = _run_hook(repo, "ledger-append", "--event", "review.critic")
        assert critic.returncode == 0, critic.stderr
        assert (repo / MARKER_REL).is_file(), "the critic append consumed the PR mark"

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        events = _ledger_events(repo)
        assert "dispatched_at" not in events[0], (
            "the critic event carried a measurement no critic mark was written for "
            "— it can only have come from the PR reviewer's slot"
        )
        assert "dispatched_at" in events[1]

    def test_an_unreadable_mark_degrades_with_a_named_reason(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)

        (repo / MARKER_REL).parent.mkdir(parents=True, exist_ok=True)
        (repo / MARKER_REL).write_text("{not json")

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert "dispatched_at" not in ev
        assert "unreadable" in _duration_reason(r)
        assert not (repo / MARKER_REL).is_file()

    def test_a_mark_with_no_timestamp_degrades_with_a_named_reason(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)

        (repo / MARKER_REL).parent.mkdir(parents=True, exist_ok=True)
        (repo / MARKER_REL).write_text(json.dumps({"head": head}))

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        assert "dispatched_at" not in _ledger_events(repo)[0]
        assert "carries no timestamp" in _duration_reason(r)

    def test_the_marker_head_and_the_envelope_head_are_the_same_read(self, tmp_path):
        """Red if the marker and the envelope ever ask git separately.

        This is the pin on `head_sha` being one home: staleness is decided by
        comparing these two values, so a second reader spelling failure `""`
        instead of `None` — or landing either side of a commit — renders a live
        dispatch as an abandoned one.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)

        _run_hook(repo, "pr-review-dispatch", "--begin")
        marker = json.loads((repo / MARKER_REL).read_text())
        assert marker["head"] == head

        self._pr_append(repo)
        ev = _ledger_events(repo)[0]
        assert ev["git"]["head"] == marker["head"]
        assert "dispatched_at" in ev

    def test_a_mark_that_cannot_be_checked_against_a_tree_is_not_measured(self, tmp_path):
        """Two nulls compare EQUAL — so the tree check passed vacuously on the one
        input where it cannot show the mark belongs to this review.

        When git cannot answer at mark time, the marker records `head: null`; if
        it also cannot answer at append time, `None != None` is false and the
        mark attached with no staleness protection whatsoever. Unverifiable is
        not the same as verified, so this now degrades by name.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_pr_evidence(repo)

        (repo / MARKER_REL).parent.mkdir(parents=True, exist_ok=True)
        (repo / MARKER_REL).write_text(
            json.dumps({"dispatched_at": "2026-09-18T12:00:00Z", "head": None})
        )

        r = self._pr_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert "dispatched_at" not in ev, "a mark with no tree attached anyway"
        assert "cannot be checked against a tree" in _duration_reason(r)

    def test_bad_arguments_are_refused_without_writing_a_mark(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        for argv in ([], ["--bogus"], ["--begin", "extra"]):
            r = _run_hook(repo, "pr-review-dispatch", *argv)
            assert r.returncode == 1, argv
            assert "usage:" in r.stderr
            assert not (repo / MARKER_REL).is_file(), argv


class TestCriticDispatchClock:
    """The Critic's own stopwatch — the same contract as the PR reviewer's, on
    its own slot.

    Why this class exists at all, measured rather than supposed: across the
    first 1,026 ledger rounds, exactly 2 carried a measured duration and both
    were ``review.pr``. The other 1,024 were reviewer estimates taking 63
    distinct values, 80% of them multiples of 30 seconds. Every wall-clock
    figure the review-economics work is argued from was a sum of those.

    **The first two tests are a treatment and its control on one fixture**, and
    they are the reason the rest can be believed: an instrument whose tests pass
    against a clock that never ticks is exactly the failure this whole chunk
    exists to end, so one test must show the key ARRIVING and its twin must show
    the same fixture reporting self-reported when the mark is withheld.
    """

    def _mark_critic(self, repo: Path) -> dict:
        """Write a Critic dispatch mark the way ``critic-begin`` does."""
        from lib import review_dispatch

        return review_dispatch.begin(
            repo / ".prawduct", "review.critic", review_dispatch.head_sha(repo)
        )

    def _critic_append(self, repo: Path):
        return _run_hook(repo, "ledger-append", "--event", "review.critic")

    def test_a_marked_critic_dispatch_produces_dispatched_at(self, tmp_path):
        """The TREATMENT half of the control pair."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo, duration_seconds=240)

        record = self._mark_critic(repo)
        # The literal path is pinned independently of the helper that wrote it:
        # three registries and `.gitignore` name this string, and a marker that
        # silently moved would be uncommitted state in every consumer's repo.
        assert (repo / CRITIC_MARKER_REL).is_file()

        r = self._critic_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert ev["dispatched_at"] == record["dispatched_at"]
        assert ev["dispatched_at"].endswith("Z")
        # The estimate is NOT displaced — both populations stay readable, which
        # is what makes the before/after comparison possible at all.
        assert ev["duration_seconds"] == 240
        assert "measured from a dispatch mark" in _duration_reason(r)
        assert not (repo / CRITIC_MARKER_REL).is_file(), "the mark was not consumed"

    def test_an_unmarked_critic_append_omits_the_key_entirely(self, tmp_path):
        """The CONTROL half: same fixture, mark withheld.

        Without this, the treatment above proves only that the plumbing carries
        a value it was handed — not that withholding the mark is distinguishable
        from supplying one.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo, duration_seconds=240)

        r = self._critic_append(repo)
        assert r.returncode == 0, r.stderr
        ev = _ledger_events(repo)[0]
        assert "dispatched_at" not in ev
        assert ev["duration_seconds"] == 240
        assert "no dispatch mark" in _duration_reason(r)

    def test_the_two_clocks_do_not_contend(self, tmp_path):
        """Both reviews in flight at once, both measured.

        This is the assertion that makes the per-kind split CHECKABLE rather
        than argued. The two boundary reviews run in parallel by deliberate
        arrangement, so the interleaving below is the ordinary case and not an
        edge: mark both, append both, and neither may lose its measurement.
        A single shared marker passes every other test in this class and fails
        precisely here.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        _write_pr_evidence(repo)

        _run_hook(repo, "pr-review-dispatch", "--begin")
        self._mark_critic(repo)

        critic = self._critic_append(repo)
        assert critic.returncode == 0, critic.stderr
        assert (repo / MARKER_REL).is_file(), (
            "the critic append consumed the PR reviewer's mark"
        )

        pr = _run_hook(
            repo, "ledger-append", "--event", "review.pr",
            "--findings", PR_EVIDENCE_REL,
        )
        assert pr.returncode == 0, pr.stderr

        events = _ledger_events(repo)
        assert "dispatched_at" in events[0], "the critic review lost its measurement"
        assert "dispatched_at" in events[1], "the PR review lost its measurement"

    def test_a_pr_append_leaves_a_live_critic_mark_alone(self, tmp_path):
        """The mirror of the PR-side concurrency test, in the other direction.

        Asserted separately because consumption is per-kind on BOTH sides and a
        one-directional guard would pass against a design that special-cased
        only the direction someone happened to test.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)
        _write_pr_evidence(repo)

        self._mark_critic(repo)
        pr = _run_hook(
            repo, "ledger-append", "--event", "review.pr",
            "--findings", PR_EVIDENCE_REL,
        )
        assert pr.returncode == 0, pr.stderr
        assert (repo / CRITIC_MARKER_REL).is_file(), (
            "the PR append consumed the Critic's mark"
        )
        assert "dispatched_at" not in _ledger_events(repo)[0]

    def test_a_critic_mark_from_another_tree_is_refused(self, tmp_path):
        """Staleness is a tree question here too — the degradation direction
        that matters, since a stale mark attests an interval nobody spent."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        self._mark_critic(repo)
        _commit_file(repo, "app.py", "print(2)\n", "work landed after dispatch")
        _write_findings(repo)

        r = self._critic_append(repo)
        assert r.returncode == 0, r.stderr
        assert "dispatched_at" not in _ledger_events(repo)[0]
        assert "different tree" in _duration_reason(r)
        assert not (repo / CRITIC_MARKER_REL).is_file()

    def test_an_unreadable_critic_mark_degrades_with_a_named_reason(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)

        (repo / CRITIC_MARKER_REL).parent.mkdir(parents=True, exist_ok=True)
        (repo / CRITIC_MARKER_REL).write_text("{not json")

        r = self._critic_append(repo)
        assert r.returncode == 0, r.stderr
        assert "dispatched_at" not in _ledger_events(repo)[0]
        assert "unreadable" in _duration_reason(r)
        assert not (repo / CRITIC_MARKER_REL).is_file()

    def test_a_critic_mark_with_no_timestamp_degrades_with_a_named_reason(self, tmp_path):
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _commit_file(repo, "app.py", "print(1)\n", "init")
        _write_findings(repo)

        (repo / CRITIC_MARKER_REL).parent.mkdir(parents=True, exist_ok=True)
        (repo / CRITIC_MARKER_REL).write_text(json.dumps({"head": head}))

        r = self._critic_append(repo)
        assert r.returncode == 0, r.stderr
        assert "dispatched_at" not in _ledger_events(repo)[0]
        assert "carries no timestamp" in _duration_reason(r)

    def test_a_kind_with_no_slot_marks_nothing_and_consumes_nothing(self, tmp_path):
        """The mapping is the design, so a kind outside it must get no cell —
        never a fallback into someone else's, which is the contention the split
        exists to make unreachable."""
        from lib import review_dispatch

        repo = tmp_path / "repo"
        _init_repo(repo)
        (repo / ".prawduct").mkdir(parents=True, exist_ok=True)

        assert "learning.written" not in review_dispatch.CONSUMING_EVENT_KINDS
        stamp, reason = review_dispatch.consume(
            repo / ".prawduct", "learning.written", "abc123"
        )
        assert stamp is None
        assert "does not consume" in reason
        with pytest.raises(KeyError):
            review_dispatch.marker_path(repo / ".prawduct", "learning.written")


class TestTheMarkerNormKeepsItsReason:
    """The amended `data-model.md` norm must carry its WHY, not just its verdict.

    An amendment that keeps the conclusion and drops the reason is how the next
    shape change loses the argument: a reader who finds "each kind owns its own
    marker" with no stated cause has no way to know that merging them back is the
    exact failure the norm was written against, and the concurrency it protects is
    invisible from the code alone — the two reviews only contend on the timing the
    parallel design deliberately produces.

    Bound to the norm's own bullet rather than the file, so a matching phrase
    elsewhere in a 1,000-line artifact cannot satisfy it.
    """

    NORM = Path(__file__).resolve().parent.parent / ".prawduct" / "artifacts" / "data-model.md"

    def _bullet(self) -> str:
        text = self.NORM.read_text(encoding="utf-8")
        marker = "- **Each consuming event kind owns its OWN marker"
        assert marker in text, (
            "the per-kind marker norm is gone from data-model.md — if it was "
            "renamed, this pin must move with it rather than be deleted"
        )
        start = text.index(marker)
        end = text.index("\n- ", start + 1)
        return text[start:end]

    def test_the_norm_states_the_concurrency_it_protects(self):
        bullet = self._bullet()
        assert "concurrent" in bullet, "the norm no longer says the two reviews overlap"
        assert "unreachable" in bullet, (
            "the norm dropped the distinction that makes the per-kind split worth "
            "its cost — unreachable by construction, not merely avoided by care"
        )

    def test_the_norm_records_the_alternative_it_rejected(self):
        """The reader's first instinct is the shared marker with a wider consumer
        set. A norm that does not name what it refused invites exactly that."""
        bullet = self._bullet()
        assert "shared" in bullet
        assert "[DECISION:" in bullet, "the amendment landed with no recorded decision"

    def test_the_amendment_points_outside_itself_for_its_authority(self):
        """A governance change cannot supply its own authority, so the amendment
        must name where the confirmation landed — somewhere that is not this
        artifact."""
        bullet = self._bullet()
        assert "build-plan-critic-dispatch-clock" in bullet, (
            "the amendment cites no confirmation outside data-model.md"
        )


class TestThePrDispatchClockAlsoFailsSoft:
    """The Critic arm's sibling, ported rather than left behind.

    `TestTheClockFailsSoft` pins `begin_review`'s degraded path; this is the
    same guarantee at `cmd_pr_review_dispatch`, which had no test at all. Both
    arms exist because a stopwatch that cannot be written must never cost the
    review it precedes — and an untested error arm is where that promise decays
    silently, since nobody exercises it by hand.

    Driven through the command rather than the library, because the promise
    being pinned is the EXIT CODE and the operator-facing sentence, neither of
    which `review_dispatch.begin` owns.
    """

    def _hook_module(self):
        import importlib.machinery
        import importlib.util

        hook = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"
        loader = importlib.machinery.SourceFileLoader("prawduct_hook_clock", str(hook))
        spec = importlib.util.spec_from_loader("prawduct_hook_clock", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def test_an_unwritable_pr_mark_tells_the_operator_to_carry_on(self, tmp_path, capsys):
        from lib import review_dispatch

        hook = self._hook_module()
        repo = tmp_path / "repo"
        _init_repo(repo)
        _commit_file(repo, "app.py", "print(1)\n", "init")

        def _boom(*_a, **_k):
            raise OSError("injected: marker unwritable")

        original = review_dispatch.begin
        review_dispatch.begin = _boom
        try:
            rc = hook.cmd_pr_review_dispatch(repo, ["--begin"])
        finally:
            review_dispatch.begin = original

        err = capsys.readouterr().err
        assert rc == 1, "a failed stopwatch must report, not succeed silently"
        assert "could not write the dispatch mark" in err
        assert "self-reported" in err, (
            "the operator is not told what they get instead — an unnamed "
            "degradation manufactures the false success it exists to prevent"
        )
        assert "dispatch the review anyway" in err, (
            "the message does not say the review should still run, so a caller "
            "reading an exit 1 may abandon a review that was going to work"
        )
        assert not (repo / MARKER_REL).is_file()
