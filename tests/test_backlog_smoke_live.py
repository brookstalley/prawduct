"""L5 live smoke — one real round-trip **through the CLI front**, throwaway repo.

This is the acceptance evidence for Chunk 01: ``provision`` → ``file`` → ``get``
driven through ``cli.run`` (the ``prawduct-hook backlog <op>`` runner) against the
real ``gh``-backed transport — Test Specs §6 live-smoke set, and the build plan's
Verification Strategy, which requires the per-front L5 to run **through the CLI
front** because "a core-only test does not prove the CLI": flag parsing, the
envelope serialization, the ``--json`` sole-stdout discipline, and the exit-code
mapping are contract surface a ``core.*`` call never exercises.

It is **gated** — it mutates a real GitHub repo, so it never runs in the fast/CI
loop (Build & Test Config: the default suite stays green with no ``gh`` and no
network). Run it by hand against a disposable repo:

    BACKLOG_LIVE_REPO=my-throwaway/backlog-test \
        python -m pytest tests/test_backlog_smoke_live.py -q

Requires: ``gh`` on PATH, authenticated (``repo`` scope), and write access to the
named repo. It creates one issue and provisions labels there.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from lib.backlog import cli, ids  # noqa: E402

_LIVE_REPO = os.environ.get("BACKLOG_LIVE_REPO")

pytestmark = pytest.mark.skipif(
    not _LIVE_REPO,
    reason="live smoke gated: set BACKLOG_LIVE_REPO=owner/repo to run against a throwaway repo",
)

# GitHub token prefixes + the seam-fake sentinel: none may appear in any output path (SEC-1).
_TOKEN_MARKERS = ("ghp_", "gho_", "ghs_", "ghr_", "github_pat_", "proxy-injected")


@pytest.fixture(scope="module")
def transport():
    from lib.backlog.transport import GhTransport

    return GhTransport()


def _run_cli(capsys, argv, transport, sink):
    """Drive the CLI front with ``--json``; return ``(exit_code, envelope)``.

    ``--json`` makes the envelope the *sole* stdout content, so ``json.loads`` of
    stdout must never choke. Raw stdout+stderr are appended to ``sink`` so the
    SEC-1 assertion covers the actual bytes a caller would see, not just the
    re-serialized payload.
    """
    exit_code = cli.run(None, [*argv, "--json"], transport=transport)
    captured = capsys.readouterr()
    sink.append(captured.out)
    sink.append(captured.err)
    envelope = json.loads(captured.out)  # sole-stdout discipline: this must parse
    return exit_code, envelope


def test_provision_file_get_round_trip(transport, capsys):
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"

    output_sink: list[str] = []

    code, provisioned = _run_cli(capsys, ["provision", "--repo", _LIVE_REPO], transport, output_sink)
    assert code == 0, provisioned
    assert provisioned["status"] == "ok", provisioned

    code, filed = _run_cli(
        capsys,
        [
            "file",
            "--repo",
            _LIVE_REPO,
            "--title",
            "prawduct backlog L5 smoke",
            "--body",
            "Created by the Chunk-01 live smoke; safe to close.",
            "--stage",
            "ready",
        ],
        transport,
        output_sink,
    )
    assert code == 0, filed
    assert filed["status"] == "ok", filed
    item_id = filed["data"]["id"]
    assert filed["data"]["stage"] == "ready"

    code, got = _run_cli(capsys, ["get", item_id], transport, output_sink)
    assert code == 0, got
    assert got["status"] == "ok", got
    assert got["data"]["id"] == item_id
    assert got["data"]["title"] == "prawduct backlog L5 smoke"

    # SEC-1 on real output: no token in any output path — assert over the actual
    # stdout+stderr the CLI emitted, plus the re-serialized envelopes for good measure.
    blob = "".join(output_sink) + json.dumps([provisioned, filed, got])
    for marker in _TOKEN_MARKERS:
        assert marker not in blob
