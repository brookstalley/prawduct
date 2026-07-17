"""Tests for the governance surface — Chunk 04, L1.

Covers, against the transport-seam fake (offline, no ``gh``, no network):
- the ``briefing_counts`` snapshot (GV2/M3): persist + visible-age read (FRESH-2,
  §3.3), atomic no-corrupt writes, multi-scope merge, disposable-cache tolerance.
- ``refresh-counts``: derive + persist; degrade (not crash) when unpersistable;
  **never clobber** the last-good snapshot on a backend failure.
- never-block / graceful degradation (§3.4): backend-down ops fail fast with a
  retryable ``unavailable`` and never hang; the snapshot read is
  network-independent (BLOCK-5).
- ``reconcile-labels`` (GV6/PROV-1): create the missing taxonomy, leave every
  foreign label untouched, idempotent, never delete.
- unattended context + the Actions pwn-request guard (SEC-5): writes withheld
  under an untrusted trigger, reads allowed, an authorized actor proceeds.
- unattended marking + fail-clean (SEC-6): an unattended create stamps
  ``automated``/``worker``; an attended one does not; a backend/auth failure fails
  fast with no half-write.
- the detached refresh spawn (D6): correct detached Popen invariants.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, context, core, encode, provision, query, snapshot  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"
SCOPE = f"{OWNER}/{REPO}"
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _file(fake, *, title="t", body="b", **facets):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body=body, facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _git(repo: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"


def _make_repo(base: Path) -> Path:
    repo = base / "clone"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


# --- Snapshot (GV2 briefing_counts — the degenerate cache) -------------------


class TestSnapshot:
    def test_write_read_round_trip_carries_visible_age(self, tmp_path):
        # FRESH-2 / §3.3: a snapshot read is never age-silent.
        path = tmp_path / "counts.json"
        counts = {"repo": SCOPE, "total": 3, "by_status": {"open": 3}, "by_stage": {}}
        snapshot.write(path, SCOPE, counts, now=NOW)
        got = snapshot.read(path, SCOPE, now=NOW + timedelta(seconds=90))
        assert got["counts"] == counts
        assert got["fetched_at"] == "2026-07-17T12:00:00Z"
        assert got["age_seconds"] == 90  # visible age, not None

    def test_absent_scope_reads_none(self, tmp_path):
        path = tmp_path / "counts.json"
        snapshot.write(path, SCOPE, {"total": 1}, now=NOW)
        assert snapshot.read(path, "other/repo", now=NOW) is None

    def test_absent_file_reads_none(self, tmp_path):
        assert snapshot.read(tmp_path / "nope.json", SCOPE, now=NOW) is None

    def test_multi_scope_merge_preserves_other_scopes(self, tmp_path):
        path = tmp_path / "counts.json"
        snapshot.write(path, "a/one", {"total": 1}, now=NOW)
        snapshot.write(path, "b/two", {"total": 2}, now=NOW)
        assert snapshot.read(path, "a/one", now=NOW)["counts"]["total"] == 1
        assert snapshot.read(path, "b/two", now=NOW)["counts"]["total"] == 2

    def test_rewrite_is_atomic_and_leaves_no_temp(self, tmp_path):
        path = tmp_path / "counts.json"
        snapshot.write(path, SCOPE, {"total": 1}, now=NOW)
        snapshot.write(path, SCOPE, {"total": 2}, now=NOW + timedelta(hours=1))
        assert snapshot.read(path, SCOPE, now=NOW)["counts"]["total"] == 2
        # No stray temp files left beside the snapshot (atomic replace).
        assert [p.name for p in tmp_path.iterdir()] == ["counts.json"]

    def test_corrupt_file_is_treated_as_empty_not_error(self, tmp_path):
        path = tmp_path / "counts.json"
        path.write_text("{ this is not json")
        assert snapshot.read(path, SCOPE, now=NOW) is None  # disposable, no raise
        # And a subsequent write recovers cleanly.
        assert snapshot.write(path, SCOPE, {"total": 5}, now=NOW)["status"] == "written"
        assert snapshot.read(path, SCOPE, now=NOW)["counts"]["total"] == 5

    def test_schema_mismatch_is_discarded(self, tmp_path):
        path = tmp_path / "counts.json"
        path.write_text('{"schema": 999, "scopes": {"octo/repo": {"counts": {"total": 7}}}}')
        assert snapshot.read(path, SCOPE, now=NOW) is None

    def test_snapshot_path_resolves_under_git_common_dir(self, tmp_path):
        repo = _make_repo(tmp_path)
        path = snapshot.snapshot_path(repo)
        assert path is not None
        assert path.name == "backlog-counts.json"
        assert path.parent.name == "prawduct"
        # Inside .git (never committed) — the same home as the evidence store.
        assert ".git" in path.parts

    def test_snapshot_path_none_outside_git_repo(self, tmp_path):
        assert snapshot.snapshot_path(tmp_path) is None


# --- refresh-counts ----------------------------------------------------------


class TestRefreshCounts:
    def test_persists_snapshot_readable_with_age(self, fake, tmp_path):
        repo = _make_repo(tmp_path)
        _file(fake, stage="ready")
        _file(fake)
        res = query.refresh_counts(fake, project_dir=repo, owner=OWNER, repo=REPO, now=NOW)
        assert res["status"] == "ok"
        assert res["data"]["persisted"] is True
        assert res["data"]["total"] == 2
        # The persisted snapshot is readable back with a visible age.
        got = snapshot.read(snapshot.snapshot_path(repo), SCOPE, now=NOW + timedelta(seconds=5))
        assert got["counts"]["total"] == 2
        assert got["age_seconds"] == 5

    def test_degrades_when_not_a_git_repo(self, fake, tmp_path):
        # No git repo → counts still returned, but flagged un-persisted (not a crash).
        _file(fake)
        res = query.refresh_counts(fake, project_dir=tmp_path, owner=OWNER, repo=REPO, now=NOW)
        assert res["status"] == "ok"
        assert res["data"]["persisted"] is False
        assert any("not persisted" in w for w in res["warnings"])

    def test_backend_down_returns_unavailable_and_does_not_clobber(self, fake, tmp_path):
        # §3.4 never-block + never-corrupt: a failed refresh keeps the last good snapshot.
        repo = _make_repo(tmp_path)
        _file(fake)
        good = query.refresh_counts(fake, project_dir=repo, owner=OWNER, repo=REPO, now=NOW)
        assert good["data"]["total"] == 1

        fake.set_unreachable(True)
        later = NOW + timedelta(hours=2)
        res = query.refresh_counts(fake, project_dir=repo, owner=OWNER, repo=REPO, now=later)
        assert res["status"] == "error"
        assert res["error"]["code"] == "unavailable"
        assert res["error"]["retryable"] is True
        # The prior snapshot is intact — not clobbered, not zeroed.
        got = snapshot.read(snapshot.snapshot_path(repo), SCOPE, now=later)
        assert got["counts"]["total"] == 1
        assert got["fetched_at"] == "2026-07-17T12:00:00Z"


# --- never-block / graceful degradation (§3.4) -------------------------------


class TestNeverBlock:
    def test_write_op_fails_fast_retryable_when_backend_down(self, fake):
        fake.set_unreachable(True)
        res = core.file_item(fake, owner=OWNER, repo=REPO, title="t", body="b")
        assert res["status"] == "error"
        assert res["error"]["code"] == "unavailable"
        assert res["error"]["retryable"] is True

    def test_read_op_fails_fast_retryable_when_backend_down(self, fake):
        fake.set_unreachable(True)
        res = query.counts(fake, owner=OWNER, repo=REPO)
        assert res["status"] == "error"
        assert res["error"]["code"] == "unavailable"

    def test_snapshot_read_is_network_independent(self, fake, tmp_path):
        # BLOCK-5: reading the persisted snapshot issues no transport call at all.
        repo = _make_repo(tmp_path)
        _file(fake)
        query.refresh_counts(fake, project_dir=repo, owner=OWNER, repo=REPO, now=NOW)
        calls_before = len(fake.calls)
        got = snapshot.read(snapshot.snapshot_path(repo), SCOPE, now=NOW)
        assert got is not None
        assert len(fake.calls) == calls_before  # zero network calls on the read path


# --- reconcile-labels (GV6 / PROV-1 coexistence) -----------------------------


class TestReconcileLabels:
    def test_creates_missing_taxonomy_and_leaves_foreign_untouched(self, fake):
        # Never an empty tracker (Test Specs §3.11 setup): pre-existing foreign labels.
        fake.seed_labels(OWNER, REPO, ["bug", "wontfix", "priority/high"])
        res = core.reconcile_labels(fake, owner=OWNER, repo=REPO)
        assert res["status"] == "ok"
        created = set(res["data"]["created"])
        assert created == set(provision.base_labels())
        assert res["data"]["foreign_untouched"] == ["bug", "priority/high", "wontfix"]
        # The foreign labels still exist, unmodified.
        names = {label["name"] for label in fake.list_labels(OWNER, REPO)}
        assert {"bug", "wontfix", "priority/high"} <= names

    def test_is_idempotent(self, fake):
        core.reconcile_labels(fake, owner=OWNER, repo=REPO)
        res2 = core.reconcile_labels(fake, owner=OWNER, repo=REPO)
        assert res2["data"]["created"] == []  # a reconciled repo creates nothing

    def test_never_deletes_a_stale_prawduct_label(self, fake):
        # A prawduct label not in the base set (e.g. a retired stage) is left in place —
        # reconcile corrects drift by adding, never by removing (DM7 posture).
        fake.seed_labels(OWNER, REPO, ["stage:retired-value"])
        core.reconcile_labels(fake, owner=OWNER, repo=REPO)
        names = {label["name"] for label in fake.list_labels(OWNER, REPO)}
        assert "stage:retired-value" in names

    def test_backend_down_is_unavailable(self, fake):
        fake.set_unreachable(True)
        res = core.reconcile_labels(fake, owner=OWNER, repo=REPO)
        assert res["error"]["code"] == "unavailable"


# --- unattended context + Actions guard (unit truth table) -------------------


class TestContext:
    def test_is_unattended(self):
        assert context.is_unattended({"PRAWDUCT_UNATTENDED": "1"}) is True
        assert context.is_unattended({"GITHUB_ACTIONS": "true"}) is True
        assert context.is_unattended({}) is False
        # Never inferred from "no TTY" — nothing in an empty/interactive env flips it.
        assert context.is_unattended({"TERM": "dumb"}) is False

    def test_worker_marker_precedence(self):
        assert context.worker_marker({"PRAWDUCT_WORKER": "sweeper"}) == "sweeper"
        assert context.worker_marker({"GITHUB_WORKFLOW": "ci"}) == "ci"
        assert context.worker_marker({}) == "prawduct-hook"

    def test_untrusted_trigger_named_events(self):
        for event in ("pull_request_target", "issue_comment", "issues"):
            env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": event}
            assert context.is_untrusted_trigger(env) is True

    def test_untrusted_trigger_fork_pull_request(self):
        # Fork detection needs the workflow-surfaced PRAWDUCT_PR_HEAD_REPO signal
        # (not a native Actions var); defense-in-depth over the read-only fork token.
        env = {
            "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_HEAD_REF": "feature", "GITHUB_REPOSITORY": "octo/repo",
            "PRAWDUCT_PR_HEAD_REPO": "outsider/repo",
        }
        assert context.is_untrusted_trigger(env) is True
        # A same-repo PR (not a fork) is not untrusted-triggerable.
        env["PRAWDUCT_PR_HEAD_REPO"] = "octo/repo"
        assert context.is_untrusted_trigger(env) is False
        # Absent the wiring, the branch is inert (safe — fork token is read-only).
        env.pop("PRAWDUCT_PR_HEAD_REPO")
        assert context.is_untrusted_trigger(env) is False

    def test_not_untrusted_outside_actions(self):
        assert context.is_untrusted_trigger({"GITHUB_EVENT_NAME": "pull_request_target"}) is False

    def test_writes_withheld_truth_table(self):
        untrusted = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "issue_comment"}
        assert context.writes_withheld(untrusted) is True
        authorized = {**untrusted, "PRAWDUCT_ACTOR_AUTHORIZED": "1"}
        assert context.writes_withheld(authorized) is False  # explicit authz lifts it
        trusted = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push"}
        assert context.writes_withheld(trusted) is False  # trusted event
        assert context.writes_withheld({}) is False  # not in Actions at all


# --- SEC-5: Actions untrusted-trigger writes withheld ------------------------


class TestSec5Withhold:
    @pytest.fixture(autouse=True)
    def _untrusted_actions(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
        monkeypatch.delenv("PRAWDUCT_ACTOR_AUTHORIZED", raising=False)

    def test_write_path_refuses(self, fake):
        rc = cli.run(".", ["file", "--repo", SCOPE, "--title", "x", "--body", "y", "--json"], transport=fake)
        assert rc == 5  # auth exit class
        # Nothing was created — the refusal is before dispatch (no half-write).
        assert fake.calls == []

    def test_claim_via_pick_refuses(self, fake):
        rc = cli.run(".", ["pick", "--repo", SCOPE, "--claim", "--json"], transport=fake)
        assert rc == 5
        assert fake.calls == []

    def test_read_report_allowed(self, fake):
        rc = cli.run(".", ["counts", "--repo", SCOPE, "--json"], transport=fake)
        assert rc == 0  # read-only reporting is fine under an untrusted trigger

    def test_bare_pick_read_allowed(self, fake):
        rc = cli.run(".", ["pick", "--repo", SCOPE, "--json"], transport=fake)
        assert rc == 0  # pick without --claim is a read

    def test_authorized_actor_write_proceeds(self, fake, monkeypatch):
        monkeypatch.setenv("PRAWDUCT_ACTOR_AUTHORIZED", "1")
        rc = cli.run(".", ["file", "--repo", SCOPE, "--title", "x", "--body", "y", "--json"], transport=fake)
        assert rc == 0  # the explicit authz check cleared the withhold


# --- SEC-6: unattended marks automated + fails clean -------------------------


class TestSec6Unattended:
    def test_unattended_create_stamps_automated_and_worker(self, fake, monkeypatch):
        monkeypatch.setenv("PRAWDUCT_UNATTENDED", "1")
        monkeypatch.setenv("PRAWDUCT_WORKER", "nightly-sweep")
        rc = cli.run(".", ["file", "--repo", SCOPE, "--title", "x", "--body", "y", "--json"], transport=fake)
        assert rc == 0
        # The created issue's block carries the marker (self-asserted audit).
        issue = fake.get_issue(OWNER, REPO, 1)
        block = encode.parse_block(issue["body"])
        assert block.get("automated") == "true"
        assert block.get("worker") == "nightly-sweep"
        item, _ = encode.decode_item(issue)
        assert item["automated"] is True

    def test_attended_create_has_no_marker(self, fake, monkeypatch):
        monkeypatch.delenv("PRAWDUCT_UNATTENDED", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        rc = cli.run(".", ["file", "--repo", SCOPE, "--title", "x", "--body", "y", "--json"], transport=fake)
        assert rc == 0
        item, _ = encode.decode_item(fake.get_issue(OWNER, REPO, 1))
        assert item["automated"] is False

    def test_unattended_create_never_prompts_uses_noninteractive_env(self):
        # SEC-6 mechanism (INV-2): the gh env disables prompts — nothing to hang on.
        from lib.backlog import transport as tp
        built = tp.build_env({})
        assert built["GH_PROMPT_DISABLED"] == "1"
        assert built["GH_PAGER"] == ""

    def test_backend_failure_is_clean_no_half_write(self, fake, monkeypatch):
        # An unattended create against a down backend fails fast, writes nothing.
        monkeypatch.setenv("PRAWDUCT_UNATTENDED", "1")
        fake.set_unreachable(True)
        res = core.file_item(fake, owner=OWNER, repo=REPO, title="t", body="b", automated=True, worker="w")
        assert res["status"] == "error"
        assert res["error"]["code"] == "unavailable"
        # No issue materialized.
        assert fake._repo(OWNER, REPO).issues == {}


# --- Detached refresh spawn (D6) ---------------------------------------------


class _RecordingPopen:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return object()  # a stand-in process handle; never waited on


class TestSpawnRefresh:
    def test_spawns_detached_unattended_with_devnull_stdio(self, tmp_path):
        rec = _RecordingPopen()
        ok = snapshot.spawn_refresh(["prawduct-hook"], tmp_path, SCOPE, popen=rec, env={})
        assert ok is True
        (argv, kwargs) = rec.calls[0]
        assert argv == ["prawduct-hook", "backlog", "refresh-counts", "--repo", SCOPE]
        assert kwargs["start_new_session"] is True  # detached from the parent session
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["env"]["PRAWDUCT_UNATTENDED"] == "1"  # the child marks itself

    def test_spawn_failure_returns_false_never_raises(self, tmp_path):
        def _boom(*_a, **_k):
            raise OSError("cannot fork")

        assert snapshot.spawn_refresh(["x"], tmp_path, SCOPE, popen=_boom, env={}) is False
