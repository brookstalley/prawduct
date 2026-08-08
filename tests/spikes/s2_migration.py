#!/usr/bin/env python3
"""SPIKE-S2 — the live migration dry-run (L4, dev-only, run by hand).

This is **not** a CI test. It is a one-time spike script (Test Specs §5) that runs
the real importer against a **throwaway** GitHub repo over live ``gh`` and records
the settled facts the offline suite cannot prove:

  1. **body/ID/section fidelity** — import a real backlog → export → diff bodies,
     IDs, and sections verbatim (the live counterpart of MIG-1, which only runs
     against the in-process fake).
  2. **ID aliasing** — every hand-minted ``PFX`` becomes a permanent ``id:PFX``
     alias; no new PFX is minted (the live MIG-2).
  3. **relationship reconstruction** — native deps/sub-issues survive the round-trip
     (the live MIG-3).
  4. **archive volume + paced-burst constants** — how many closed issues the archive
     import creates, and — under ``--archive-scope all`` — the real REST-point pacing
     the create-then-close stretch incurs (points charged, how often the 900-pts/min
     burst throttled, wall-clock), settling the constants NFR §9 S2 leaves open.
  5. **rollback-free resume** — interrupt mid-import, re-run, confirm no duplicates
     (the live CRASH-4).
  6. **fan-out slope** — time ``pick`` at increasing candidate counts to
     (*was "batched-vs-N+1"; settled 2026-07-28 as N+1 REST, and this probe could
     not have answered it before ``pick`` began bounding the fan-out by ``limit``
     — see ``check_pick_latency``*)
     pin its latency floor (the PROBE-LAT constant that the offline suite marks
     ``target``-grade only).
  7. **node_id stability across transfer** — capture an issue's GraphQL node_id,
     ``gh issue transfer`` it, re-capture, compare (ID-4's genuinely-undocumented
     open fact — whether ``node_id`` survives a transfer).

Its output is a **settled fact recorded in NFR §4 / the build plan**, not a
repeatable assertion. Because it can only run against live GitHub, its steps are
**validated when it is run**, not before (Principle 5 — honest confidence): treat
the assertions here as the intended checks, to be confirmed on the live dry-run.

Safety: it refuses to run without an explicit ``--repo <throwaway-owner/repo>`` and
``--yes``, because it **creates and closes real issues**. Run it prawduct-first,
against a throwaway copy of the repo, after the scrub — never against a repo whose
issues you care about.

Usage:
    python tests/spikes/s2_migration.py --repo <throwaway-owner/repo> --yes \
        [--from .prawduct/backlog.md] [--archive <archive.md>] \
        [--archive-scope {all|open}] [--transfer-to <other-owner/repo>]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SPIKE_DIR = Path(__file__).resolve().parent
# The plugin lives in plugin/, not at the repo root (v3.1.1, GOV-4H7T) — mirror the
# root conftest's insert so a standalone `python tests/spikes/s2_migration.py` run
# (this script is dev-only, never run under pytest, so conftest does not fire for it)
# resolves `lib.backlog` the same way the suite does.
_PLUGIN_ROOT = _SPIKE_DIR.parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib.backlog import ids, legacy, migrate, query  # noqa: E402
from lib.backlog.transport import GhTransport, build_env  # noqa: E402


def _facts() -> dict:
    """The settled facts this run records back into NFR §4 / the build plan."""
    return {
        "fidelity_ok": None,
        "aliases_minted": None,
        "new_pfx_minted": None,
        "relationships_reconstructed": None,
        "archive_issue_count": None,
        "resume_created_duplicates": None,
        "pick_latency_ms_by_candidates": {},
        "node_id_stable_across_transfer": None,
        # Paced create-then-close archive burst (NFR §9 S2). Surfaced from the Pacer
        # that meters the `--archive-scope all` import: point_waits > 0 means the
        # 900-pts/min REST burst was actually hit and paced; 0 means the stretch
        # stayed under the ceiling on its own.
        "archive_scope": None,
        "archive_burst_wall_seconds": None,
        "rest_points_charged": None,
        "rest_point_waits": None,
        "rest_point_wait_seconds": None,
        "content_creation_waits": None,
        "content_creation_wait_seconds": None,
        "pacer_budgets": None,
    }


def _split_repo(slug: str) -> tuple[str, str]:
    owner, _, repo = slug.partition("/")
    if not owner or not repo:
        raise SystemExit(f"--repo must be owner/repo, got {slug!r}")
    return owner, repo


def _record_pacing(pacer, facts) -> None:
    """Lift the Pacer's run-summary counters into the settled facts. These are the
    real create-then-close pacing constants NFR §9 S2 leaves for the live run to
    settle: total REST points the burst spent, how often each budget throttled, and
    the budget ceilings in force (so the recorded fact is self-describing)."""
    facts["rest_points_charged"] = pacer.points_charged
    facts["rest_point_waits"] = pacer.point_waits
    facts["rest_point_wait_seconds"] = round(pacer.total_point_waited, 3)
    facts["content_creation_waits"] = pacer.waits
    facts["content_creation_wait_seconds"] = round(pacer.total_waited, 3)
    facts["pacer_budgets"] = {
        "per_minute_creates": pacer.per_minute,
        "per_hour_creates": pacer.per_hour,
        "per_minute_points": pacer.per_minute_points,
    }


def check_fidelity_and_aliases(
    transport, owner, repo, source, archive, archive_scope, pacer, facts
) -> None:
    """Steps 1–4: import → export → diff bodies/IDs/sections; confirm aliases and the
    native graph survived. The import here is the create-then-close **archive burst**
    (under the chosen ``archive_scope``), metered by ``pacer`` — its wall-clock and the
    Pacer's point counters are the paced-burst facts NFR §9 S2 settles. Only the import
    routes through the paced transport (export uses the raw one), so ``points_charged``
    reflects the burst alone."""
    facts["archive_scope"] = archive_scope
    src = legacy.parse_backlog(Path(source).read_text())
    burst_start = time.monotonic()
    result = migrate.import_backlog(
        transport,
        owner=owner,
        repo=repo,
        content=Path(source).read_text(),
        archive_content=Path(archive).read_text() if archive else None,
        archive_scope=archive_scope,
        pacer=pacer,
    )
    facts["archive_burst_wall_seconds"] = round(time.monotonic() - burst_start, 3)
    _record_pacing(pacer, facts)
    if result["status"] != "ok":
        facts["fidelity_ok"] = False
        print(f"  import failed: {result['error']}")
        return

    with tempfile.TemporaryDirectory() as dest:
        exported = migrate.export_backlog(transport, owner=owner, repo=repo, dest=Path(dest))
        assert exported["status"] == "ok", exported
        dumped = [json.loads(p.read_text()) for p in sorted(Path(dest).glob("item-*.json"))]

    by_pfx = {a: rec for rec in dumped for a in (rec.get("id_aliases") or [])}
    # Only items carrying a hand-minted [PFX-XXXX] participate in the alias check.
    source_items = [
        i for i in (src.pending_items() + src.archived_items()) if ids.is_pfx(i.item_id)
    ]
    source_pfxs = {i.item_id for i in source_items}
    minted, missing_body = 0, []
    for item in source_items:
        pfx = item.item_id  # the hand-minted [PFX-XXXX]
        rec = by_pfx.get(pfx)
        if rec is None:
            missing_body.append(pfx)
            continue
        minted += 1
        if item.body.strip() and item.body.strip() not in (rec.get("body") or ""):
            missing_body.append(pfx)

    facts["aliases_minted"] = minted
    facts["new_pfx_minted"] = sorted(a for a in by_pfx if a not in source_pfxs)
    facts["fidelity_ok"] = not missing_body
    # The native graph is nested under `relationships` in the export record
    # (migrate._export_record): {"blocked_by": [...], "sub_issues": [...]}.
    facts["relationships_reconstructed"] = any(
        (rec.get("relationships") or {}).get("blocked_by")
        or (rec.get("relationships") or {}).get("sub_issues")
        for rec in dumped
    )
    if missing_body:
        print(f"  fidelity gaps for: {missing_body}")


def check_resume(transport, owner, repo, source, facts) -> None:
    """Step 5: a second import is a pure no-op (skip-if-exists) — no duplicates.
    (The true crash test interrupts mid-run; here the re-run convergence is the
    offline-provable half, confirmed live.)"""
    before = len(transport.list_issues(owner, repo, state="all", per_page=100, page=1))
    migrate.import_backlog(transport, owner=owner, repo=repo, content=Path(source).read_text())
    after = len(transport.list_issues(owner, repo, state="all", per_page=100, page=1))
    facts["resume_created_duplicates"] = after - before


def check_pick_latency(transport, owner, repo, facts, project_dir=None) -> None:
    """Step 6: time pick's ready-work fan-out (pins the PROBE-LAT floor, NFR §4).

    **Read the result carefully — before 2026-07-28 this probe could not detect
    what it was built to detect.** The original reading was "flat as candidates
    grow ⇒ the batched path; grows linearly ⇒ N+1". That inference was invalid:
    the candidate count here IS ``limit``, and ``pick`` applied ``limit`` only
    *after* fanning out over every eligible issue — so varying 1/3/5 varied
    nothing about the number of blocker reads. The measured flatness came from
    the constant ``all_issues`` full-scan and was recorded across four documents
    as evidence of a batched fan-out that was never built.

    ``pick`` now bounds the fan-out by ``limit``, so the parameterization is
    meaningful for the first time and the linear-vs-flat reading is finally
    sound.

    **And the full scan it used to be dominated by is gone.** The candidate set
    comes from the local store after one conditional revalidation, so what remains
    on the wire is the blocker fan-out — which means the slope IS the measurement
    now, and the intercept is a revalidation plus a local read rather than a
    paginated walk of the whole backlog. The first call against a fresh
    ``project_dir`` builds the store, so it measures a cold cache; the 3 and 5
    readings are the warm path an operator meets.
    """
    store = Path(project_dir or tempfile.mkdtemp(prefix="s2-backlog-store-"))
    subprocess.run(["git", "init", "-q"], cwd=store, check=True)
    for limit in (1, 3, 5):
        start = time.monotonic()
        query.pick(transport, project_dir=store, owner=owner, repo=repo, limit=limit)
        facts["pick_latency_ms_by_candidates"][limit] = round((time.monotonic() - start) * 1000)


def check_node_id_transfer(source_slug, dest_slug, facts) -> None:
    """Step 7: does an issue's GraphQL node_id survive `gh issue transfer`?
    Directly probes the open fact — the service has no transfer op (that is W3);
    this uses `gh` straight."""
    owner, repo = _split_repo(source_slug)
    env = build_env()

    def _view(slug: str, number: int) -> dict:
        out = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", slug, "--json", "id,number"],
            capture_output=True, text=True, env=env, check=False,
        )
        return json.loads(out.stdout) if out.returncode == 0 else {}

    listed = GhTransport().list_issues(owner, repo, state="all", per_page=1, page=1)
    if not listed:
        print("  no issue to transfer; skipping node_id check")
        return
    number = listed[0]["number"]
    before = _view(source_slug, number).get("id")
    subprocess.run(
        ["gh", "issue", "transfer", str(number), dest_slug],
        capture_output=True, text=True, env=env, check=False,
    )
    # After transfer the number changes; the operator records the new number the
    # transfer prints. This records the *before* node_id for the manual compare.
    facts["node_id_stable_across_transfer"] = {
        "before_node_id": before,
        "note": "compare against the transferred issue's id in the destination repo",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SPIKE-S2 — live migration dry-run (dev-only)")
    ap.add_argument("--repo", required=True, help="throwaway owner/repo — issues WILL be created")
    ap.add_argument("--from", dest="source", default=".prawduct/backlog.md")
    ap.add_argument("--archive", default=None)
    ap.add_argument(
        "--archive-scope",
        dest="archive_scope",
        choices=("all", "open"),
        default="all",
        help="MG4b archive-volume lever: 'all' (default) imports the full historical "
        "archive as closed issues — the paced create-then-close burst this dry-run "
        "measures; 'open' migrates only the live set",
    )
    ap.add_argument("--transfer-to", dest="transfer_to", default=None)
    ap.add_argument("--yes", action="store_true", help="confirm: this mutates a real repo")
    args = ap.parse_args(argv)

    if not args.yes:
        print("Refusing to run: this creates and closes real GitHub issues.")
        print("Re-run with --yes against a THROWAWAY repo.")
        return 2

    owner, repo = _split_repo(args.repo)
    transport = GhTransport()
    facts = _facts()
    pacer = migrate.Pacer()  # meters the archive burst; counters land in the facts

    print(
        f"SPIKE-S2 against {args.repo} (from {args.source}, "
        f"archive-scope={args.archive_scope}) — live gh\n"
    )
    print("1-4. fidelity + aliases + relationships + paced archive burst …")
    check_fidelity_and_aliases(
        transport, owner, repo, args.source, args.archive, args.archive_scope, pacer, facts
    )
    print("5. resume convergence …")
    check_resume(transport, owner, repo, args.source, facts)
    print("6. pick latency by candidates …")
    check_pick_latency(transport, owner, repo, facts)
    if args.transfer_to:
        print("7. node_id across transfer …")
        check_node_id_transfer(args.repo, args.transfer_to, facts)

    print("\n=== settled facts — record into NFR §4 / the build plan ===")
    print(json.dumps(facts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
