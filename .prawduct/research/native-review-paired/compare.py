#!/usr/bin/env python3
"""Compare the Critic with the paired native review (#1130 step 5).

Usage:
    python3 -I compare.py <repo> [<repo> ...] [--out <dir>] [--transcripts <subagents dir> ...]

For every ``native.review`` event in each repo's governance ledger, joins the
native run to the Critic review it was paired with (the evidence store's review
fact of the same id) and matches their findings. Prints, per Critic goal and per
stage and Critic severity, the findings both raised, those only the Critic
raised, and the native-only findings; per instrument and stage, wall clock (and,
with ``--transcripts``, the native forks' tokens and the recipe each ran via
``fork_costs.py``); the runs that were dispatched and never recorded; each
instrument's re-raise candidates; and progress toward #1130's stop condition,
which counts boundary pairs. With ``--out`` it also writes the blind
verification sheet and its key.

**Matching is by file, and is a proposal.** A Critic finding names files and no
line; a native finding names one file and a line. So two findings pair when the
native one's file is among the Critic one's files, one to one, first come. Two
different defects in one file pair too — which is why the blind sheet asks the
verifier to confirm or reject each proposed pair, as well as to judge each
unique finding real or not, without being told which instrument raised what.
A native finding is matched against the Critic's findings first and then its
observations, since a defect the Critic rated an observation is one both raised.

**A re-raise is a candidate, by file, and a proposal too.** A finding of a
paired review K repeats an earlier finding E when E is within K's reach and
names one of the finding's files. E is a Critic finding left accepted or filed,
or a native finding of a boundary run — one the builder was shown; a native
finding of an inner run never counts, since it was not put to the builder. K's
reach is the Critic's own prior-dispositions rule (``dispositions.
prior_dispositions``): earlier reviews of K's plan scope (any earlier review
when K has none) whose finding cites a file K changes. So the native review is
measured against exactly what the Critic is handed, and the Critic, measured
the same way, is the baseline. The verifier confirms or rejects each candidate
as "same defect?".

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

from lib import dispositions, evidence, gitstate, ledger, model_tier, native_review  # noqa: E402

#: #1130 step 7: stop after four weeks or sixty paired reviews, whichever is later.
STOP_WEEKS = 4
STOP_REVIEWS = 60
NO_GOAL = "(no goal — the verifier names one)"
OBSERVATION = "observation"
SEVERITIES = ("blocking", "warning", OBSERVATION)
#: Finding states an earlier review leaves for a later one to re-raise: the
#: builder chose not to fix them. A fixed finding is gone from the code.
SETTLED_STATES = {dispositions.STATE_ACCEPTED: "critic-accepted", dispositions.STATE_FILED: "critic-filed"}


def match(critic: list[dict], native: list[dict], observations: "list[dict] | None" = None) -> dict:
    """Pair findings one to one: a native finding pairs with the first unpaired
    Critic finding whose ``files`` include its ``file``, else with the first
    such unpaired observation. Returns ``shared`` (pairs; an observation's
    severity reads ``observation``), ``critic_only`` (findings),
    ``observations_unmatched`` and ``native_only``. Pure."""
    rated = [dict(c, severity=c.get("severity")) for c in critic]
    demoted = [dict(o, severity=OBSERVATION) for o in observations or []]
    used_rated: set[int] = set()
    used_demoted: set[int] = set()
    shared, native_only = [], []

    def first(pool, used, n):
        return next(
            (i for i, c in enumerate(pool)
             if i not in used and n.get("file") and n["file"] in (c.get("files") or [])),
            None,
        )

    for n in native:
        hit = first(rated, used_rated, n)
        if hit is not None:
            used_rated.add(hit)
            shared.append((critic[hit], n))
            continue
        hit = first(demoted, used_demoted, n)
        if hit is not None:
            used_demoted.add(hit)
            shared.append((demoted[hit], n))
            continue
        native_only.append(n)
    return {
        "shared": shared,
        "critic_only": [c for i, c in enumerate(critic) if i not in used_rated],
        "observations_unmatched": [o for i, o in enumerate(demoted) if i not in used_demoted],
        "native_only": native_only,
    }


def tally_by_severity(staged: "list[tuple[str, dict]]") -> dict:
    """``{stage: {severity: {shared, critic_only}, "native_only": n}}`` over
    ``(stage, match)`` pairs. The question #1164 asks: which of the Critic's
    findings, by how much they mattered, the native review also raised."""
    table: dict[str, dict] = {}
    for stage, m in staged:
        row = table.setdefault(stage, {**{s: {"shared": 0, "critic_only": 0} for s in SEVERITIES},
                                       "native_only": 0})
        for c, _n in m["shared"]:
            row.setdefault(c.get("severity") or "unrated", {"shared": 0, "critic_only": 0})["shared"] += 1
        for c in m["critic_only"]:
            row.setdefault(c.get("severity") or "unrated", {"shared": 0, "critic_only": 0})["critic_only"] += 1
        row[OBSERVATION]["critic_only"] += len(m.get("observations_unmatched") or [])
        row["native_only"] += len(m["native_only"])
    return dict(sorted(table.items()))


def in_reach(j: dict, k: dict) -> bool:
    """Whether earlier review ``j``'s findings are within later review ``k``'s
    reach by work: ``j`` is earlier, and carries ``k``'s plan scope when ``k``
    has one — the half of ``prior_dispositions`` that is not the file test
    (``reraise_candidates`` applies that one, per finding). Pure."""
    if not (j.get("ts") and k.get("ts") and j["ts"] < k["ts"]):
        return False
    return k.get("scope") is None or j.get("scope") == k.get("scope")


def earlier_findings(fact: dict, state_of, native: "list[dict] | None", stage: str) -> dict:
    """What review ``fact`` leaves for a later one to re-raise: its Critic
    findings whose state (``state_of((review id, fid))``) is accepted or filed,
    and — a boundary run only, the one put to the builder — its native findings."""
    settled = []
    for c in (fact.get("body") or {}).get("findings") or []:
        state = state_of((fact.get("id"), c.get("fid")))
        if state in SETTLED_STATES:
            settled.append((c, state))
    return {
        "review_id": fact.get("id"),
        "settled": settled,
        "native_shown": list(native or []) if stage == "boundary" else [],
    }


def reraise_candidates(later: dict, earlier: list[dict]) -> list[dict]:
    """Each finding of ``later`` (``critic`` findings, ``native`` findings or
    ``None``) that names a file an earlier review's left-standing finding names,
    against the nearest such review (``earlier`` is nearest first, and already
    narrowed by :func:`in_reach`). An earlier finding is in reach only when it
    cites a file ``later`` changes (``files_changed``; absent, no file
    narrowing), as ``prior_dispositions`` reaches it. One candidate per
    finding, carrying EVERY such finding of that review — a file can hold
    several, and offering only the first would hide the one it repeats. Pure."""
    def files_of(f):
        return set(f.get("files") or ([f["file"]] if f.get("file") else []))

    changed = set(later["files_changed"]) if later.get("files_changed") is not None else None
    out = []
    for by, findings in (("critic", later.get("critic") or []), ("native", later.get("native") or [])):
        for f in findings:
            mine = files_of(f)
            hit = None
            for e in earlier:
                options = [(c, SETTLED_STATES[state]) for c, state in e["settled"]]
                options += [(n, "native") for n in e["native_shown"]]
                matched = [(c, kind) for c, kind in options
                           if mine & files_of(c) and (changed is None or changed & files_of(c))]
                if matched:
                    hit = (matched, e["review_id"])
                    break
            if hit:
                out.append({"by": by, "finding": f, "earlier": [c for c, _k in hit[0]],
                            "earlier_kind": "+".join(sorted({k for _c, k in hit[0]})),
                            "earlier_review": hit[1], "review": later.get("review_id")})
    return out


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
        native = event.get("native") if isinstance(event.get("native"), dict) else {}
        if event.get("event") != "native.review":
            continue
        review_id = native.get("critic_review_id")
        path = native_review.text_path(prawduct_dir, review_id)
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        pairs.append({
            "text_present": bool(text.strip()),
            "repo": str(repo),
            "review_id": review_id,
            "ts": event.get("ts"),
            "native_event": event,
            "native_findings": native_review.findings_detail(text) if text else None,
            "critic_fact": facts.get(review_id),
        })
    for pair in pairs:
        pair["critic_event"] = critic_events.get(pair["review_id"])
        pair["stage"] = stage_of(pair)
    return pairs


def stage_of(pair: dict) -> str:
    """The stage a pair's Critic review ran at — its fact's, else what the
    native run recorded, else ``boundary``: every run recorded before inner
    reviews paired was a boundary one."""
    fact_stage = ((pair.get("critic_fact") or {}).get("body") or {}).get("stage")
    native_stage = (pair["native_event"].get("native") or {}).get("stage")
    return fact_stage or native_stage or "boundary"


def reraises(repo: Path, pairs: list[dict]) -> "tuple[list[dict], dict]":
    """Every re-raise candidate in ``repo``'s comparable pairs, and per
    instrument how many findings were in a review that had an earlier one in
    reach to repeat (the rate's denominator)."""
    store = evidence.read_facts(repo)
    disp = dispositions.disposition_index(store)
    resolved = dispositions.resolution_detail_index(store)

    def state_of(key):
        return dispositions.finding_state(key, disp, resolved)

    facts = sorted((f for f in store.get("facts") or [] if f.get("kind") == "review" and f.get("ts")),
                   key=lambda f: f["ts"])
    paired = {p["review_id"]: p for p in pairs}

    def view(fact):
        return {"review_id": fact["id"], "ts": fact["ts"], "scope": (fact.get("body") or {}).get("scope")}

    candidates, exposed = [], {"critic": 0, "native": 0}
    for pair in pairs:
        k_fact = pair.get("critic_fact")
        if k_fact is None or not k_fact.get("ts"):
            continue
        k = view(k_fact)
        earlier = []
        for j_fact in reversed(facts):
            if j_fact["ts"] >= k["ts"]:
                continue
            j_pair = paired.get(j_fact["id"])
            offer = earlier_findings(
                j_fact, state_of, (j_pair or {}).get("native_findings"),
                (j_pair or {}).get("stage", (j_fact.get("body") or {}).get("stage") or "boundary"),
            )
            if (offer["settled"] or offer["native_shown"]) and in_reach(view(j_fact), k):
                earlier.append(offer)
        if not earlier:
            continue
        later = {"review_id": pair["review_id"],
                 "critic": (k_fact.get("body") or {}).get("findings") or [],
                 "native": pair.get("native_findings") or [],
                 "files_changed": (k_fact.get("body") or {}).get("files_changed")}
        exposed["critic"] += len(later["critic"])
        exposed["native"] += len(later["native"])
        candidates += reraise_candidates(later, earlier)
    return candidates, exposed


def unrecorded(repo: Path, recorded: "set[str]") -> "list[str]":
    """Review ids whose native run was dispatched (a sidecar exists) and never
    recorded — a wrapper that died, was refused, or is still running."""
    reviews = native_review.reviews_dir(gitstate.get_prawduct_dir(repo))
    return sorted(p.stem for p in reviews.glob("rev-*.json") if p.stem not in recorded)


def count_check(pairs: list[dict]) -> "tuple[int, list[str]]":
    """Whether this script's reading of each native text matches what the
    ledger recorded when the run landed — the two parse one text, so a mismatch
    is a parse change or a text edited since. Compared whenever either side
    could count: a run whose countability changed is exactly what a parse
    change looks like. Compared by WHICH findings (file and line), not how
    many. Not compared: a run neither side could count, and one whose text is
    not in this clone."""
    agree, disagree = 0, []
    for pair in pairs:
        native = pair["native_event"].get("native") or {}
        ledger_list = native.get("findings") if native.get("findings_parsed") else None
        text_list = (
            [{"file": f["file"], "line": f["line"]} for f in pair["native_findings"]]
            if pair["native_findings"] is not None else None
        )
        if not pair.get("text_present") or (ledger_list is None and text_list is None):
            continue
        if ledger_list == text_list:
            agree += 1
            continue
        ledger_n = "not countable" if ledger_list is None else len(ledger_list)
        text_n = "not countable" if text_list is None else len(text_list)
        differ = ", findings differ" if ledger_n == text_n else ""
        disagree.append(f"{pair['review_id']} (ledger {ledger_n}, text {text_n}{differ})")
    return agree, disagree


def model_mismatches(pairs: list[dict]) -> "list[str]":
    """Pairs whose native run and Critic review ran on different model
    families — the comparison assumes they did not. Compared by family, since
    the two record the model under different spellings."""
    out = []
    for pair in pairs:
        critic = model_tier.canonical_model(((pair.get("critic_event") or {}).get("actor") or {}).get("model"))
        native = model_tier.canonical_model((pair["native_event"].get("actor") or {}).get("model"))
        if critic and native and critic != native:
            out.append(f"{pair['review_id']} (critic {critic}, native {native})")
    return out


def _seconds(event: "dict | None") -> "float | None":
    if not event:
        return None
    from lib.review_dispatch import event_interval_seconds  # noqa: PLC0415

    return event_interval_seconds(event)


def blind_sheet(
    pairs: list[dict], matches: list[dict], seed: int = 0, reraised: "list[dict] | None" = None,
) -> "tuple[list[dict], dict]":
    """The verifier's sheet and its key. Each item is a proposed pair to confirm
    or reject — a match, or a re-raise candidate — or one unique finding to
    judge real or not, with its words and location and nothing that says which
    instrument raised it."""
    items, key = [], {}

    def critic_words(c):
        return {"files": c.get("files"), "text": f"{c.get('title', '')} — {c.get('recommendation', '')}"}

    def native_words(n):
        return {"files": [n.get("file")], "line": n.get("line"),
                "text": f"{n.get('summary') or ''} — {n.get('failure_scenario') or ''}"}

    def words(f):
        return native_words(f) if "file" in f else critic_words(f)

    for pair, m in zip(pairs, matches):
        for c, n in m["shared"]:
            a, b = critic_words(c), native_words(n)
            ref = {"critic_fid": c["fid"]} if c.get("fid") else {"critic_oid": c.get("oid")}
            items.append({"ask": "same defect?", "first": a, "second": b,
                          "_key": {"review": pair["review_id"], **ref}})
        for c in m["critic_only"]:
            items.append({"ask": "real defect?", "finding": critic_words(c),
                          "_key": {"review": pair["review_id"], "source": "critic", "fid": c.get("fid")}})
        for n in m["native_only"]:
            items.append({"ask": "real defect? and which goal?", "finding": native_words(n),
                          "_key": {"review": pair["review_id"], "source": "native"}})
    for r in reraised or []:
        items.append({"ask": "does it repeat one of the earlier findings?", "finding": words(r["finding"]),
                      "earlier": [words(e) for e in r["earlier"]],
                      "_key": {"review": r["review"], "reraise_by": r["by"],
                               "earlier_kind": r["earlier_kind"], "earlier_review": r["earlier_review"]}})
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
    matches = [
        match(p["critic_fact"]["body"].get("findings") or [], p["native_findings"],
              observations=p["critic_fact"]["body"].get("observations") or [])
        for p in joined
    ]

    missing = [i for repo in args.repos
               for i in unrecorded(repo.resolve(), {p["review_id"] for p in pairs})]
    print(f"paired reviews: {len(pairs)} recorded, {len(joined)} comparable "
          f"(a Critic fact in the store and a countable native text); "
          f"{len(missing)} dispatched and never recorded{': ' + ', '.join(missing) if missing else ''}")
    # #1130's stop counts boundary pairs, as it did before inner reviews paired.
    print(f"stop condition (#1130 step 7): "
          f"{stop_progress([p['ts'] for p in pairs if p['ts'] and p['stage'] == 'boundary'])}")
    print(f"inner pairs (#1166): {sum(1 for p in pairs if p['stage'] != 'boundary')}")
    agree, disagree = count_check(pairs)
    print(f"count check: {agree} of {agree + len(disagree)} countable run(s) agree with the ledger"
          + (": " + ", ".join(disagree) if disagree else ""))
    mismatched = model_mismatches(pairs)
    if mismatched:
        print(f"WARNING: {len(mismatched)} model mismatch(es): " + ", ".join(mismatched))
    moved = [p["review_id"] for p in joined if (p["native_event"].get("native") or {}).get("tree_moved")]
    if moved:
        # The native review reads source from the working tree; a fix landed
        # before it finished means it read something other than what the
        # Critic read.
        print(f"WARNING: {len(moved)} run(s) read a tree that moved before they landed: " + ", ".join(moved))
    print("\nper Critic goal — shared / Critic only / native only:")
    for goal, row in tally_by_goal(matches).items():
        print(f"  {goal}: {row['shared']} / {row['critic_only']} / {row['native_only']}")
    print("\nper stage and Critic severity — shared / Critic only:")
    for stage, row in tally_by_severity([(p["stage"], m) for p, m in zip(joined, matches)]).items():
        for severity, cell in row.items():
            if severity != "native_only":
                print(f"  {stage} {severity}: {cell['shared']} / {cell['critic_only']}")
        print(f"  {stage} native only: {row['native_only']}")

    def med(values):
        return f"median {sorted(values)[len(values) // 2]:.0f}s over {len(values)}" if values else "none clocked"

    print()
    for stage in sorted({p["stage"] for p in joined}):
        in_stage = [p for p in joined if p["stage"] == stage]
        critic_s = [s for s in (_seconds(p["critic_event"]) for p in in_stage) if s is not None]
        native_s = [s for s in (_seconds(p["native_event"]) for p in in_stage) if s is not None]
        print(f"wall clock, {stage} — Critic: {med(critic_s)}; native: {med(native_s)}")
    reraised, exposed = [], {"critic": 0, "native": 0}
    for repo in args.repos:
        repo = repo.resolve()
        found, seen = reraises(repo, [p for p in joined if p["repo"] == str(repo)])
        reraised += found
        exposed = {k: exposed[k] + seen[k] for k in exposed}
    by = {k: sum(1 for r in reraised if r["by"] == k) for k in exposed}
    print(f"\nre-raise candidates — native: {by['native']} of {exposed['native']} finding(s); "
          f"Critic: {by['critic']} of {exposed['critic']} (findings in a review with an earlier one "
          "in reach; the verifier confirms each)")
    if args.transcripts:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import fork_costs  # noqa: PLC0415

        levels = {
            p["native_event"]["native"].get("args", "").split(" ", 1)[-1]: p["native_event"]["native"].get("level")
            for p in joined
        }
        forks = [r for d in args.transcripts for p in sorted(d.glob("agent-*.jsonl"))
                 if (r := fork_costs.fork_row(p)) and r["target"].strip("`") in levels]
        tokens = {k: sum(r[k] for r in forks) for k in ("cache_create", "cache_read", "input", "output")}
        recipes: dict[str, int] = {}
        models: dict[str, int] = {}
        for r in forks:
            recipes[r["recipe"] or "unknown"] = recipes.get(r["recipe"] or "unknown", 0) + 1
            # One count per fork, so the tally sums to the fork count.
            model = "/".join(m for m in r["models"] if m != "?") or "unknown"
            models[model] = models.get(model, 0) + 1
        # The level asked is not always the level run (`medium` ran `high` in
        # 2.1.322), and the review runs on its caller's model, so both come from
        # each fork's own transcript — and a fork off the assumed level is named.
        print(f"native fork tokens over {len(forks)} fork(s): {tokens}; "
              f"recipes run: {recipes}; models: {models}")
        off: dict[str, int] = {}
        for r in forks:
            if r["recipe"] != levels.get(r["target"].strip("`")):
                off[r["recipe"] or "unknown"] = off.get(r["recipe"] or "unknown", 0) + 1
        if off:
            print("WARNING: {} fork(s) ran a recipe other than their run's recorded level: {}".format(
                sum(off.values()), ", ".join(f"{k} {v}" for k, v in sorted(off.items()))))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        items, key = blind_sheet(joined, matches, reraised=reraised)
        (args.out / "blind-sheet.json").write_text(json.dumps(items, indent=2))
        (args.out / "blind-key.json").write_text(json.dumps(key, indent=2))
        print(f"\nblind sheet: {len(items)} item(s) → {args.out / 'blind-sheet.json'} (key beside it)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
