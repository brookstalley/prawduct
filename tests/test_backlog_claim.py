"""Tests for lib/backlog/core.py claim / unclaim (Chunk 03, L1).

CRASH-6 — atomic take-and-verify → non-fatal ``claim_conflict``; the claim
carries actor + timestamp; a claim past its TTL is reap-eligible so ``pick``
cannot starve (the residual double-take race is accepted by design — this
asserts the take-and-verify *surfaces* it, not that it is eliminated).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, core, encode  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
NOSLEEP = lambda _attempt: None  # noqa: E731


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _file(fake, *, title="claim: the t item under test", **facets):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body="b", facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _as_actor(fake, login):
    """Switch the fake's authenticated identity (a second claimant)."""
    fake.user = {"login": login, "id": 99}
    fake._user_cache = None


class TestClaim:
    def test_claim_unassigned_takes_and_stamps(self, fake):
        item = _file(fake, title="claim: the free item under test")
        result = core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        assert result["status"] == "ok"
        assert result["data"]["assignee"] == "agent-a"
        assert result["data"]["claimed_at"] == NOW.isoformat()

    def test_claim_idempotent_for_same_actor(self, fake):
        item = _file(fake, title="claim: the free item under test")
        core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        later = NOW + timedelta(minutes=5)
        again = core.claim(fake, id_raw=item, now=later, sleeper=NOSLEEP)
        assert again["status"] == "ok"
        assert again["data"]["assignee"] == "agent-a"
        # Re-claim refreshes the heartbeat stamp (keeps the claim alive).
        assert again["data"]["claimed_at"] == later.isoformat()

    def test_live_claim_by_other_actor_is_non_fatal_conflict(self, fake):
        item = _file(fake, title="claim: the contended item under test")
        core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)  # agent-a holds it
        _as_actor(fake, "agent-b")
        result = core.claim(fake, id_raw=item, now=NOW + timedelta(hours=1), sleeper=NOSLEEP)
        assert result["status"] == "error"
        assert result["error"]["code"] == "claim_conflict"
        assert result["error"]["retryable"] is True  # non-fatal
        assert result["error"]["details"]["holder"] == "agent-a"

    def test_stale_claim_past_ttl_is_reaped(self, fake):
        item = _file(fake, title="claim: the abandoned item under test")
        core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)  # agent-a
        _as_actor(fake, "agent-b")
        future = NOW + timedelta(days=2)  # past the 24h default TTL
        result = core.claim(fake, id_raw=item, now=future, sleeper=NOSLEEP)
        assert result["status"] == "ok"
        assert result["data"]["assignee"] == "agent-b"
        assert result["data"]["claimed_at"] == future.isoformat()

    def test_ttl_boundary_respects_override(self, fake):
        item = _file(fake, title="claim: the short-ttl item under test")
        core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        _as_actor(fake, "agent-b")
        # A 1-hour TTL: two hours later the claim is reap-eligible.
        result = core.claim(
            fake, id_raw=item, now=NOW + timedelta(hours=2), claim_ttl_seconds=3600, sleeper=NOSLEEP
        )
        assert result["status"] == "ok" and result["data"]["assignee"] == "agent-b"

    def test_assignee_without_stamp_treated_as_live(self, fake):
        """A human/UI assignment (assignee set, no claimed_at) is never reaped."""
        item = _file(fake, title="claim: the human-assigned item under test")
        _owner, _repo, number = OWNER, REPO, int(item.split("#")[1])
        fake.update_issue(_owner, _repo, number, fields={"assignees": ["a-human"]})  # no stamp
        _as_actor(fake, "agent-b")
        result = core.claim(fake, id_raw=item, now=NOW + timedelta(days=30), sleeper=NOSLEEP)
        assert result["status"] == "error" and result["error"]["code"] == "claim_conflict"

    def test_crash_during_take_leaves_free_and_reruns_cleanly(self, fake):
        """The take is one atomic PATCH — a crash mid-take leaves the item *free*
        (never a torn assignee-set/no-stamp state that TTL-reap could not free),
        and a re-run converges (CC3/M11 crash-safety, parallel to CRASH-1)."""
        item = _file(fake, title="claim: the crash-take item under test")
        _owner, _repo, number = OWNER, REPO, int(item.split("#")[1])
        fake.fail_at_mutation(1)  # the claim's atomic PATCH fails
        crashed = core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        assert crashed["status"] == "error"  # the injected transport failure

        issue = fake.get_issue(_owner, _repo, number)
        settled, _ = encode.decode_item(issue)
        assert settled["assignee"] is None and settled["claimed_at"] is None  # untouched, free

        retry = core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        assert retry["status"] == "ok" and retry["data"]["assignee"] == "agent-a"

    def test_take_and_verify_surfaces_a_lost_race(self, fake):
        """A concurrent claimant that wins between our set and our verify read is
        surfaced as claim_conflict (the residual race, made observable)."""

        class RacingFake(FakeGitHub):
            def update_issue(self, owner, repo, number, *, fields):
                result = super().update_issue(owner, repo, number, fields=fields)
                # A rival overwrites the assignee immediately after our take PATCH.
                if fields.get("assignees"):
                    super().update_issue(owner, repo, number, fields={"assignees": ["rival"]})
                return result

        racing = RacingFake(user={"login": "agent-a", "id": 1})
        item = core.file_item(racing, owner=OWNER, repo=REPO, title="claim: the raced item under test", body="b")["data"]["id"]
        result = core.claim(racing, id_raw=item, now=NOW, sleeper=NOSLEEP)
        assert result["status"] == "error"
        assert result["error"]["code"] == "claim_conflict"
        assert result["error"]["details"]["holder"] == "rival"

    def test_claim_conflict_maps_to_exit_class_4(self, fake, capsys):
        import json

        item = _file(fake, title="claim: the contended item under test")
        # Both claims go through the CLI so holder and challenger share one clock
        # domain — a fixed-NOW first claim expires against the CLI's real clock
        # once wall time passes NOW + TTL, turning the conflict into a legal reap.
        code = cli.run(None, ["claim", item, "--json"], transport=fake)
        capsys.readouterr()
        assert code == 0
        _as_actor(fake, "agent-b")
        code = cli.run(None, ["claim", item, "--json"], transport=fake)
        env = json.loads(capsys.readouterr().out)
        assert code == 4  # conflict exit class
        assert env["error"]["code"] == "claim_conflict"


class TestUnclaim:
    def test_unclaim_clears_assignee_and_stamp(self, fake):
        item = _file(fake, title="claim: the mine item under test")
        core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        result = core.unclaim(fake, id_raw=item)
        assert result["status"] == "ok"
        assert result["data"]["assignee"] is None
        assert result["data"]["claimed_at"] is None

    def test_unclaim_free_item_is_a_near_no_op(self, fake):
        item = _file(fake, title="claim: the already free item under test")
        before = len(fake.calls)
        result = core.unclaim(fake, id_raw=item)
        assert result["status"] == "ok"
        # No redundant writes: an unclaimed item triggers no update PATCH.
        mutations = [c for c in fake.calls[before:] if c[0] == "update_issue"]
        assert mutations == []

    def test_reclaim_after_unclaim(self, fake):
        item = _file(fake, title="claim: the cycle item under test")
        core.claim(fake, id_raw=item, now=NOW, sleeper=NOSLEEP)
        core.unclaim(fake, id_raw=item)
        _as_actor(fake, "agent-b")
        result = core.claim(fake, id_raw=item, now=NOW + timedelta(minutes=1), sleeper=NOSLEEP)
        assert result["status"] == "ok" and result["data"]["assignee"] == "agent-b"
