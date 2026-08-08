"""L5 live smoke — one real round-trip **through the CLI front**, throwaway repo.

This is the live acceptance evidence for the backlog service: ``provision`` →
``file`` → ``get`` → ``status`` transition, each driven through ``cli.run`` (the
``prawduct-hook backlog <op>`` runner) against the
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
import subprocess
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


@pytest.fixture(scope="module")
def live_work_tree(tmp_path_factory):
    """A throwaway git work tree for the store-backed ops.

    ``pick`` reads its candidates from the clone-shared backlog cache and syncs on
    its way in, so it needs a real work tree — and it must **not** be the
    developer's own clone, because a sync against the live smoke repo would
    rebuild that clone's store around a different backlog. Module-scoped so the
    cache is built once and the later `pick` calls exercise the warm path, which
    is the one an operator meets.
    """
    path = tmp_path_factory.mktemp("live-backlog-store")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return str(path)


def _run_cli(capsys, argv, transport, sink, project_dir="."):
    """Drive the CLI front with ``--json``; return ``(exit_code, envelope)``.

    ``--json`` makes the envelope the *sole* stdout content, so ``json.loads`` of
    stdout must never choke. Raw stdout+stderr are appended to ``sink`` so the
    SEC-1 assertion covers the actual bytes a caller would see, not just the
    re-serialized payload.

    ``project_dir`` matters only for the store-backed ops (``pick``, ``sync``,
    ``refresh-counts``); pass ``live_work_tree`` for those. It was ``None`` for
    every call until `pick` moved onto the cache, at which point ``Path(None)``
    raised inside the CLI boundary and came back as a bare ``unavailable``.
    """
    exit_code = cli.run(project_dir, [*argv, "--json"], transport=transport)
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


def test_status_transition_round_trip(transport, capsys):
    """A real two-axis status transition through the CLI front (the state machine).

    file (open) → status in-progress (open sub-state label) → status shipped
    (closed + state_reason, status: label stripped) → get confirms the decoded
    status. Exercises the crash-safe write path against live GitHub — where the
    fake's label/state semantics are confirmed (CONTRACT-1 / VRF).
    """
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"

    output_sink: list[str] = []

    code, _ = _run_cli(capsys, ["provision", "--repo", _LIVE_REPO], transport, output_sink)
    assert code == 0

    code, filed = _run_cli(
        capsys,
        ["file", "--repo", _LIVE_REPO, "--title", "prawduct L5 status smoke",
         "--body", "Created by the live status-transition smoke; safe to close."],
        transport, output_sink,
    )
    assert code == 0, filed
    item_id = filed["data"]["id"]
    assert filed["data"]["status"] == "open"  # new item is plain open

    code, moved = _run_cli(capsys, ["status", item_id, "--to", "in-progress"], transport, output_sink)
    assert code == 0, moved
    assert moved["data"]["status"] == "in-progress"
    assert "status:in-progress" in moved["data"]["labels"]

    code, shipped = _run_cli(capsys, ["status", item_id, "--to", "shipped"], transport, output_sink)
    assert code == 0, shipped
    assert shipped["data"]["status"] == "shipped"
    # closed states carry no status: label (Data Model §4)
    assert not [l for l in shipped["data"]["labels"] if l.startswith("status:")]

    # re-run is idempotent (a crashed client re-running converges, no error)
    code, again = _run_cli(capsys, ["status", item_id, "--to", "shipped"], transport, output_sink)
    assert code == 0 and again["data"]["status"] == "shipped"

    code, got = _run_cli(capsys, ["get", item_id], transport, output_sink)
    assert code == 0 and got["data"]["status"] == "shipped"

    blob = "".join(output_sink)
    for marker in _TOKEN_MARKERS:
        assert marker not in blob


def test_list_pick_round_trip(transport, capsys, live_work_tree):
    """A real ``list`` + ``pick`` round-trip through the CLI front (Chunk 03).

    file a ``stage: ready`` item → ``list --stage ready`` sees it online
    (read-your-writes in practice) → ``pick`` returns it as ready work with a
    *why*. Proves the query fan-out wires to live GitHub, not just the fake.
    """
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"

    output_sink: list[str] = []

    code, _ = _run_cli(capsys, ["provision", "--repo", _LIVE_REPO], transport, output_sink)
    assert code == 0

    code, filed = _run_cli(
        capsys,
        ["file", "--repo", _LIVE_REPO, "--title", "prawduct L5 pick smoke",
         "--body", "Created by the Chunk-03 list/pick smoke; safe to close.", "--stage", "ready"],
        transport, output_sink,
    )
    assert code == 0, filed
    item_id = filed["data"]["id"]

    code, listed = _run_cli(capsys, ["list", "--repo", _LIVE_REPO, "--stage", "ready"], transport, output_sink)
    assert code == 0, listed
    assert item_id in {i["id"] for i in listed["data"]["items"]}

    code, picked = _run_cli(
        capsys, ["pick", "--repo", _LIVE_REPO, "--limit", "10"], transport, output_sink,
        project_dir=live_work_tree,
    )
    assert code == 0, picked
    picked_ids = {c["id"] for c in picked["data"]["candidates"]}
    assert item_id in picked_ids  # unassigned, no open blockers → ready work
    for cand in picked["data"]["candidates"]:
        assert cand["why"]

    blob = "".join(output_sink)
    for marker in _TOKEN_MARKERS:
        assert marker not in blob


# A minimal live-import fixture (kept inline so the gated module needs no extra
# sys.path wiring for the offline fixtures package).
_LIVE_BACKLOG_MD = """# Backlog — L5 import smoke

## Open

- **[SMK-0001]** live import smoke item one
  `effort: S · impact: S · area: core · source: builder · status: open · stage: ready`

  Created by the Chunk-05 import smoke; safe to close.

## Archive

- **[SMK-0002]** live import smoke archived item
  `effort: S · impact: S · area: core · source: builder · status: shipped`

  An archived item; imports closed.
"""


def test_import_export_round_trip(transport, capsys, tmp_path):
    """A real ``import``→``export`` round-trip through the CLI front (Chunk 05).

    The per-front L5 for migration: import a tiny ``backlog.md`` into the live repo
    (idempotent — safe to re-run), then export the repo and confirm the manifest +
    the imported items land. ``import`` uses ``project_dir`` for its checkpoint, so
    this drives ``cli.run`` with a real dir (not ``None``).
    """
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"

    src = tmp_path / "backlog.md"
    src.write_text(_LIVE_BACKLOG_MD)
    out_dir = tmp_path / "export"

    code = cli.run(
        str(tmp_path),
        ["import", "--repo", _LIVE_REPO, "--from", str(src), "--json"],
        transport=transport,
    )
    imported = json.loads(capsys.readouterr().out)
    assert code == 0, imported
    assert imported["status"] == "ok", imported

    code = cli.run(
        str(tmp_path),
        ["export", "--repo", _LIVE_REPO, "--to", str(out_dir), "--json"],
        transport=transport,
    )
    exported = json.loads(capsys.readouterr().out)
    assert code == 0, exported
    assert exported["status"] == "ok", exported
    assert (out_dir / "export-manifest.json").exists()

    # Re-import is a full no-op (idempotent, keyed on the id: alias — CRASH-4 live).
    code = cli.run(
        str(tmp_path),
        ["import", "--repo", _LIVE_REPO, "--from", str(src), "--json"],
        transport=transport,
    )
    reimported = json.loads(capsys.readouterr().out)
    assert code == 0
    assert reimported["data"]["created"] == []  # nothing re-created

    blob = json.dumps([imported, exported, reimported])
    for marker in _TOKEN_MARKERS:
        assert marker not in blob


def test_merge_round_trip(transport, capsys):
    """A real ``merge`` through the CLI front: fold a duplicate into a survivor
    (redirect-before-close). Source ends up closed + redirected; the survivor is
    untouched (both bodies preserved — DM7)."""
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"

    output_sink: list[str] = []
    code, _ = _run_cli(capsys, ["provision", "--repo", _LIVE_REPO], transport, output_sink)
    assert code == 0

    code, dup = _run_cli(
        capsys,
        ["file", "--repo", _LIVE_REPO, "--title", "prawduct L5 merge source",
         "--body", "Duplicate; folded by the merge smoke."],
        transport, output_sink,
    )
    assert code == 0, dup
    code, keep = _run_cli(
        capsys,
        ["file", "--repo", _LIVE_REPO, "--title", "prawduct L5 merge target",
         "--body", "Survivor of the merge smoke; safe to close."],
        transport, output_sink,
    )
    assert code == 0, keep

    code, merged = _run_cli(
        capsys, ["merge", dup["data"]["id"], "--into", keep["data"]["id"]], transport, output_sink
    )
    assert code == 0, merged
    assert merged["data"]["superseded_by"] == keep["data"]["id"]

    code, got = _run_cli(capsys, ["get", dup["data"]["id"]], transport, output_sink)
    assert code == 0
    assert got["data"]["status"] == "dropped"  # closed, not deleted
    assert got["data"]["superseded_by"] == keep["data"]["id"]

    blob = "".join(output_sink)
    for marker in _TOKEN_MARKERS:
        assert marker not in blob


def test_blocked_item_excluded_from_pick(transport, capsys, live_work_tree):
    """The Chunk-05 Done-when-0 live check: the ``blocked_by`` *read* shape ``pick``
    parses is confirmed against live GitHub (Chunk 03 built it against the fake
    only). Link a real blocker → ``pick`` excludes the blocked item; close the
    blocker → ``pick`` includes it. A live-shape mismatch would surface a blocked
    item as ready — this catches it."""
    parsed = ids.parse_repo(_LIVE_REPO)
    assert parsed, f"BACKLOG_LIVE_REPO must be owner/repo, got {_LIVE_REPO!r}"

    output_sink: list[str] = []
    code, _ = _run_cli(capsys, ["provision", "--repo", _LIVE_REPO], transport, output_sink)
    assert code == 0

    code, blocked = _run_cli(
        capsys,
        ["file", "--repo", _LIVE_REPO, "--title", "prawduct L5 blocked item",
         "--body", "Blocked; should not be picked until its blocker closes.", "--stage", "ready"],
        transport, output_sink,
    )
    assert code == 0, blocked
    code, blocker = _run_cli(
        capsys,
        ["file", "--repo", _LIVE_REPO, "--title", "prawduct L5 blocker",
         "--body", "The blocker; close me to unblock.", "--stage", "ready"],
        transport, output_sink,
    )
    assert code == 0, blocker

    code, linked = _run_cli(
        capsys,
        ["link", blocked["data"]["id"], "--edge", "blocked-by", "--to", blocker["data"]["id"]],
        transport, output_sink,
    )
    assert code == 0, linked

    code, picked = _run_cli(
        capsys, ["pick", "--repo", _LIVE_REPO, "--limit", "50"], transport, output_sink,
        project_dir=live_work_tree,
    )
    assert code == 0
    assert blocked["data"]["id"] not in {c["id"] for c in picked["data"]["candidates"]}

    code, _ = _run_cli(capsys, ["status", blocker["data"]["id"], "--to", "shipped"], transport, output_sink)
    assert code == 0
    code, picked2 = _run_cli(
        capsys, ["pick", "--repo", _LIVE_REPO, "--limit", "50"], transport, output_sink,
        project_dir=live_work_tree,
    )
    assert code == 0
    assert blocked["data"]["id"] in {c["id"] for c in picked2["data"]["candidates"]}

    blob = "".join(output_sink)
    for marker in _TOKEN_MARKERS:
        assert marker not in blob
