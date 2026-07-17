"""L5 live smoke — one real round-trip per front, against a throwaway repo.

This is the acceptance evidence for Chunk 01: ``provision`` → ``file`` → ``get``
through the real ``gh``-backed transport (Test Specs §6 live-smoke set, and the
build plan's per-front L5). It is **gated** — it mutates a real GitHub repo, so it
never runs in the fast/CI loop (Build & Test Config: the default suite stays green
with no ``gh`` and no network). Run it by hand against a disposable repo:

    BACKLOG_LIVE_REPO=my-throwaway/backlog-test \
        python -m pytest tests/test_backlog_smoke_live.py -q

Requires: ``gh`` on PATH, authenticated (``repo`` scope), and write access to the
named repo. It creates one issue and provisions labels there.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from lib.backlog import core, ids  # noqa: E402

_LIVE_REPO = os.environ.get("BACKLOG_LIVE_REPO")

pytestmark = pytest.mark.skipif(
    not _LIVE_REPO,
    reason="live smoke gated: set BACKLOG_LIVE_REPO=owner/repo to run against a throwaway repo",
)


@pytest.fixture(scope="module")
def transport():
    from lib.backlog.transport import GhTransport

    return GhTransport()


def test_provision_file_get_round_trip(transport):
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"
    owner, repo = parsed

    provisioned = core.provision_labels(transport, owner=owner, repo=repo)
    assert provisioned["status"] == "ok", provisioned

    filed = core.file_item(
        transport,
        owner=owner,
        repo=repo,
        title="prawduct backlog L5 smoke",
        body="Created by the Chunk-01 live smoke; safe to close.",
        facets={"stage": "ready"},
    )
    assert filed["status"] == "ok", filed
    item_id = filed["data"]["id"]
    assert filed["data"]["stage"] == "ready"

    got = core.get_item(transport, id_raw=item_id)
    assert got["status"] == "ok", got
    assert got["data"]["id"] == item_id
    assert got["data"]["title"] == "prawduct backlog L5 smoke"

    # SEC-1 sanity on real output: no token in the round-trip payloads.
    import json

    blob = json.dumps([provisioned, filed, got])
    for marker in ("ghp_", "gho_", "ghs_", "ghr_", "github_pat_", "proxy-injected"):
        assert marker not in blob
