#!/usr/bin/env python3
"""Compare the Critic with the paired native review (#1130 step 5).

Usage:
    python3 -I compare.py <repo> [<repo> ...] [--out <dir>] [--transcripts <subagents dir> ...]

For every ``review.native`` event in each repo's governance ledger, joins the
native run to the Critic review it was paired with (the evidence store's review
fact of the same id) and matches their findings. Prints, per Critic goal, the
findings both raised, those only the Critic raised, and the native-only
findings; per instrument, wall clock (and, with ``--transcripts``, the native
forks' tokens via ``fork_costs.py``); and progress toward #1130's stop
condition. With ``--out`` it also writes the blind verification sheet and its
key.

**Matching is by file, and is a proposal.** A Critic finding names files and no
line; a native finding names one file and a line. So two findings pair when the
native one's file is among the Critic one's files, one to one, first come. Two
different defects in one file pair too — which is why the blind sheet asks the
verifier to confirm or reject each proposed pair, as well as to judge each
unique finding real or not, without being told which instrument raised what.

Reads the ledger, the evidence store and the per-clone native texts of each
repo; writes only under ``--out``.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from lib import evidence, gitstate, ledger, native_review  # noqa: E402

#: #1130 step 7: stop after four weeks or sixty paired reviews, whichever is later.
STOP_WEEKS = 4
STOP_REVIEWS = 60
NO_GOAL = "(no goal — the verifier names one)"


def match(critic: list[dict], native: list[dict]) -> dict:
    """Pair findings one to one: a native finding pairs with the first unpaired
    Critic finding whose ``files`` include its ``file``. Returns ``shared``
    (pairs), ``critic_only`` and ``native_only``. Pure."""
    used: set[int] = set()
    shared, native_only = [], []
    for n in native:
        hit = next(
            (i for i, c in enumerate(critic)
             if i not in used and n.get("file") and n["file"] in (c.get("files") or [])),
            None,
        )
        if hit is None:
            native_only.append(n)
        else:
            used.add(hit)
            shared.append((critic[hit], n))
    critic_only = [c for i, c in enumerate(critic) if i not in used]
    return {"shared": shared, "critic_only": critic_only, "native_only": native_only}


def tally_by_goal(matches: list[dict]) -> dict:
    """``{goal: {shared, critic_only, native_only}}`` over many reviews'
    matches. A native-only finding has no Critic goal until the verifier names
    one, so it counts under :data:`NO_GOAL`."""
    table: dict[str, dict[str, int]] = {}

    def bump(goal, key):
        table.setdefault(goal or NO_GOAL, {"shared": 0, "critic_only": 0, "native_only": 0})[key] += 1

    for m in matches:
        for c, _n in m["shared"]:
            bump(c.get("goal"), "shared")
        for c in m["critic_only"]:
            bump(c.get("goal"), "critic_only")
        for _n in m["native_only"]:
            bump(None, "native_only")
    return dict(sorted(table.items()))


def stop_progress(stamps: list[str], now: "datetime | None" = None) -> dict:
    """How far the experiment is toward its stop condition: both four weeks
    since the first paired review and sixty paired reviews."""
    now = now or datetime.now(timezone.utc)
    parsed = sorted(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) for s in stamps)
    weeks = (now - parsed[0]).days / 7 if parsed else 0.0
    return {
        "paired_reviews": len(parsed),
        "weeks": round(weeks, 1),
        "stop": len(parsed) >= STOP_REVIEWS and weeks >= STOP_WEEKS,
    }


def load_pairs(repo: Path) -> list[dict]:
    """Every paired review in ``repo``: the native run's event and text, and
    the Critic review fact it was paired with (``None`` when the store does not
    hold it — a review that never consolidated)."""
    prawduct_dir = gitstate.get_prawduct_dir(repo)
    store = evidence.read_facts(repo)
    if store.get("status") == "error":
        raise SystemExit(f"{repo}: the evidence store could not be read ({store.get('reason')})")
    facts = {f["id"]: f for f in store.get("facts") or [] if f.get("kind") == "review"}
    critic_events = {}
    pairs = []
    for _line, event in ledger.iter_events_newest_first(prawduct_dir):
        review = event.get("review") if isinstance(event.get("review"), dict) else {}
        if event.get("event") == "review.critic" and review.get("fact_id"):
            critic_events.setdefault(review["fact_id"], event)
        if event.get("event") != "review.native":
            continue
        review_id = review.get("critic_review_id")
        path = native_review.text_path(prawduct_dir, review_id)
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        pairs.append({
            "repo": str(repo),
            "review_id": review_id,
            "ts": event.get("ts"),
            "native_event": event,
            "native_findings": native_review.findings_detail(text) if text else None,
            "critic_fact": facts.get(review_id),
        })
    for pair in pairs:
        pair["critic_event"] = critic_events.get(pair["review_id"])
    return pairs


def _seconds(event: "dict | None") -> "float | None":
    if not event:
        return None
    from lib.review_dispatch import event_interval_seconds  # noqa: PLC0415

    return event_interval_seconds(event)


def blind_sheet(pairs: list[dict], matches: list[dict], seed: int = 0) -> "tuple[list[dict], dict]":
    """The verifier's sheet and its key. Each item is a proposed pair to confirm
    or reject, or one unique finding to judge real or not — with its words and
    location and nothing that says which instrument raised it."""
    items, key = [], {}

    def critic_words(c):
        return {"files": c.get("files"), "text": f"{c.get('title', '')} — {c.get('recommendation', '')}"}

    def native_words(n):
        return {"files": [n.get("file")], "line": n.get("line"),
                "text": f"{n.get('summary') or ''} — {n.get('failure_scenario') or ''}"}

    for pair, m in zip(pairs, matches):
        for c, n in m["shared"]:
            a, b = critic_words(c), native_words(n)
            items.append({"ask": "same defect?", "first": a, "second": b,
                          "_key": {"review": pair["review_id"], "critic_fid": c.get("fid")}})
        for c in m["critic_only"]:
            items.append({"ask": "real defect?", "finding": critic_words(c),
                          "_key": {"review": pair["review_id"], "source": "critic", "fid": c.get("fid")}})
        for n in m["native_only"]:
            items.append({"ask": "real defect? and which goal?", "finding": native_words(n),
                          "_key": {"review": pair["review_id"], "source": "native"}})
    random.Random(seed).shuffle(items)
    for i, item in enumerate(items, 1):
        item_id = f"V-{i}"
        key[item_id] = item.pop("_key")
        item["id"] = item_id
    return items, key


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repos", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--transcripts", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    pairs = [p for repo in args.repos for p in load_pairs(repo.resolve())]
    joined = [p for p in pairs if p["critic_fact"] is not None and p["native_findings"] is not None]
    matches = [match(p["critic_fact"]["body"].get("findings") or [], p["native_findings"]) for p in joined]

    print(f"paired reviews: {len(pairs)} recorded, {len(joined)} comparable "
          f"(a Critic fact in the store and a countable native text)")
    print(f"stop condition (#1130 step 7): {stop_progress([p['ts'] for p in pairs if p['ts']])}")
    print("\nper Critic goal — shared / Critic only / native only:")
    for goal, row in tally_by_goal(matches).items():
        print(f"  {goal}: {row['shared']} / {row['critic_only']} / {row['native_only']}")
    critic_s = [s for s in (_seconds(p["critic_event"]) for p in joined) if s is not None]
    native_s = [s for s in (_seconds(p["native_event"]) for p in joined) if s is not None]

    def med(values):
        return f"median {sorted(values)[len(values) // 2]:.0f}s over {len(values)}" if values else "none clocked"

    print(f"\nwall clock — Critic: {med(critic_s)}; native: {med(native_s)}")
    if args.transcripts:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import fork_costs  # noqa: PLC0415

        ranges = {p["native_event"]["review"].get("args", "").split(" ", 1)[-1] for p in joined}
        forks = [r for d in args.transcripts for p in sorted(d.glob("agent-*.jsonl"))
                 if (r := fork_costs.fork_row(p)) and r["target"].strip("`") in ranges]
        tokens = {k: sum(r[k] for r in forks) for k in ("cache_create", "cache_read", "input", "output")}
        print(f"native fork tokens over {len(forks)} fork(s): {tokens}")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        items, key = blind_sheet(joined, matches)
        (args.out / "blind-sheet.json").write_text(json.dumps(items, indent=2))
        (args.out / "blind-key.json").write_text(json.dumps(key, indent=2))
        print(f"\nblind sheet: {len(items)} item(s) → {args.out / 'blind-sheet.json'} (key beside it)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
