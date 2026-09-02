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
