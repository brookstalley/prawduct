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
paired review K may repeat an earlier finding E that names one of its files.
The Critic's E are exactly the prior dispositions ``critic-begin`` would have
handed K (``dispositions.prior_dispositions`` over the store as it stood before
K: its scope, file and size rules included). The native E are the findings of
earlier boundary runs, the ones put to the builder, under the same scope and
file rules; an inner run's never count. So the native review is measured
against what the Critic is handed, and the Critic, measured the same way, is
the baseline. The verifier judges whether each candidate repeats one of the
earlier findings listed with it.

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
#: One question for every unique finding, whichever instrument raised it.
UNIQUE_ASK = "real defect? and which goal?"
OBSERVATION = "observation"
SEVERITIES = ("blocking", "warning", OBSERVATION)
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
    """Whether earlier review ``j`` is within later review ``k``'s reach by
    work: ``j`` is earlier, and carries ``k``'s plan scope when ``k`` has one —
    ``prior_dispositions``' scope rule, applied to the earlier NATIVE findings
    it has no record of. "Earlier" is the store's append order (``seq``), never
    the timestamp: stamps have one-second resolution, and two reviews can land
    in one second. Pure."""
    if not (isinstance(j.get("seq"), int) and isinstance(k.get("seq"), int) and j["seq"] < k["seq"]):
        return False
    return k.get("scope") is None or j.get("scope") == k.get("scope")


def cites_a_changed_file(finding: dict, files_changed: "list[str] | None") -> bool:
    """``prior_dispositions``' file rule: a finding is in reach when it cites a
    file the later review changes — and every finding is, when the later
    review names no files at all."""
    changed = {f for f in files_changed or [] if isinstance(f, str) and f}
    return not changed or bool(changed & _files_of(finding))


def _files_of(f: dict) -> set:
    return set(f.get("files") or ([f["file"]] if f.get("file") else []))


def reraise_candidates(later: dict, earlier: list[dict]) -> list[dict]:
    """Each finding of ``later`` (``critic`` findings, ``native`` findings or
    ``None``) that names a file an earlier finding in reach names, against the
    nearest earlier review holding one. ``earlier`` is nearest first, each
    ``{"review_id", "options": [(finding, kind), ...]}``, already narrowed to
    what is in reach. One candidate per finding, carrying EVERY matching finding
    of that review — a file can hold several, and offering only the first would
    hide the one it repeats. Pure."""
    out = []
    for by, findings in (("critic", later.get("critic") or []), ("native", later.get("native") or [])):
        for f in findings:
            mine = _files_of(f)
            for e in earlier:
                matched = [(c, kind) for c, kind in e["options"] if mine & _files_of(c)]
                if matched:
                    out.append({"by": by, "finding": f, "earlier": [c for c, _k in matched],
                                "earlier_kind": "+".join(sorted({k for _c, k in matched})),
                                "earlier_review": e["review_id"], "review": later.get("review_id")})
                    break
    return out


def tally_by_goal(matches: list[dict]) -> dict:
    """``{goal: {shared, shared_observation, critic_only, native_only}}`` over
    many reviews' matches. ``shared`` and ``critic_only`` count the Critic's
    findings; a native finding matched to one of its observations counts apart,
    in ``shared_observation``, because the observations it did not match are no
    one's ``critic_only`` — folding them into ``shared`` alone would overstate
    the overlap. A native-only finding has no Critic goal until the verifier
    names one, so it counts under :data:`NO_GOAL`."""
    table: dict[str, dict[str, int]] = {}

    def bump(goal, key):
        table.setdefault(goal or NO_GOAL, {"shared": 0, "shared_observation": 0,
                                           "critic_only": 0, "native_only": 0})[key] += 1

    for m in matches:
        for c, _n in m["shared"]:
            bump(c.get("goal"), "shared_observation" if c.get("severity") == OBSERVATION else "shared")
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
    instrument how many findings were in a review that had an earlier finding
    in reach to repeat (the rate's denominator).

    The Critic's earlier findings in reach are exactly what ``critic-begin``
    would have handed it: ``dispositions.prior_dispositions`` over the store as
    it stood before the later review (its scope rule, file rule and limit
    included), never a re-derivation of it. Earlier native findings, which no
    disposition records, take the same scope and file rules; only a boundary
    run's count, since only those were put to the builder."""
    store = evidence.read_facts(repo)
    all_facts = store.get("facts") or []
    index = evidence.findings_index(store)
    reviews = [(i, f) for i, f in enumerate(all_facts) if f.get("kind") == "review" and f.get("id")]
    seq = {f["id"]: i for i, f in reviews}
    scope_of = {f["id"]: (f.get("body") or {}).get("scope") for _i, f in reviews}
    shown = {p["review_id"]: p.get("native_findings") or [] for p in pairs if p.get("stage") == "boundary"}

    candidates, exposed = [], {"critic": 0, "native": 0}
    for pair in pairs:
        k_fact = pair.get("critic_fact")
        if k_fact is None or k_fact.get("id") not in seq:
            continue
        body = k_fact.get("body") or {}
        k = {"review_id": k_fact["id"], "seq": seq[k_fact["id"]], "scope": body.get("scope")}
        groups: dict[str, list] = {}
        before = {**store, "facts": all_facts[:k["seq"]]}
        for entry in dispositions.prior_dispositions(before, body.get("files_changed"), scope=k["scope"]).get("entries") or []:
            finding = index.get((entry["review_id"], entry["fid"]))
            if finding is not None:
                groups.setdefault(entry["review_id"], []).append((finding, f"critic-{entry.get('action')}"))
        for j_id, natives in shown.items():
            if j_id in seq and in_reach({"seq": seq[j_id], "scope": scope_of[j_id]}, k):
                options = [(n, "native") for n in natives if cites_a_changed_file(n, body.get("files_changed"))]
                if options:
                    groups.setdefault(j_id, []).extend(options)
        if not groups:
            continue
        earlier = [{"review_id": rid, "options": groups[rid]}
                   for rid in sorted(groups, key=lambda rid: seq.get(rid, -1), reverse=True)]
        later = {"review_id": pair["review_id"], "critic": body.get("findings") or [],
                 "native": pair.get("native_findings") or []}
        exposed["critic"] += len(later["critic"])
        exposed["native"] += len(later["native"])
        candidates += reraise_candidates(later, earlier)
    return candidates, exposed


def outside_interval(pairs: list[dict]) -> dict:
    """Per stage, ``(native findings on a file outside the Critic's
    files_changed, native findings)``. The native review reads source beyond
    the diff, so some are expected; a high share at the inner stage says it
    reviewed more than the Critic's interval (its recipe can add ``git diff
    HEAD`` on a dirty tree)."""
    out: dict[str, list[int]] = {}
    for p in pairs:
        changed = set(((p.get("critic_fact") or {}).get("body") or {}).get("files_changed") or [])
        row = out.setdefault(p["stage"], [0, 0])
        for n in p.get("native_findings") or []:
            row[1] += 1
            row[0] += bool(changed) and n.get("file") not in changed
    return {stage: tuple(v) for stage, v in sorted(out.items())}


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
    instrument raised it: every unique finding gets one question, and a pair's
    order is shuffled, with the key saying which side came first. Each item also
    names the repo and the trees its review read, so the verifier reads the code
    as reviewed and not a later fix of it."""
    items, key = [], {}
    rng = random.Random(seed)

    def where(pair):
        native = (pair.get("native_event") or {}).get("native") or {}
        place = {"repo": pair.get("repo"), "base_tree": native.get("base_tree"),
                 "head_tree": native.get("head_tree")}
        # The native review reads the working tree; when a reviewed file moved
        # before it landed, the code at head_tree is not quite what it read. Said
        # of every item of that review, so it names no instrument.
        if native.get("tree_moved"):
            place["tree_moved"] = True
        return place

    at_review = {p.get("review_id"): where(p) for p in pairs}

    def critic_words(c):
        return {"files": c.get("files"), "text": f"{c.get('title', '')} — {c.get('recommendation', '')}"}

    # No `line`: only native findings carry one, so it would tell the verifier
    # which instrument raised what. The verifier finds the site from the file
    # and the words.
    def native_words(n):
        return {"files": [n.get("file")],
                "text": f"{n.get('summary') or ''} — {n.get('failure_scenario') or ''}"}

    def words(f):
        return native_words(f) if "file" in f else critic_words(f)

    for pair, m in zip(pairs, matches):
        at = at_review[pair.get("review_id")]
        for c, n in m["shared"]:
            a, b = critic_words(c), native_words(n)
            first = "critic"
            if rng.random() < 0.5:
                a, b, first = b, a, "native"  # the key's `first_source`; the sheet's `first` holds words
            ref = {"critic_fid": c["fid"]} if c.get("fid") else {"critic_oid": c.get("oid")}
            items.append({"ask": "same defect?", "first": a, "second": b, **at,
                          "_key": {"review": pair["review_id"], "first_source": first, **ref}})
        for c in m["critic_only"]:
            items.append({"ask": UNIQUE_ASK, "finding": critic_words(c), **at,
                          "_key": {"review": pair["review_id"], "source": "critic", "fid": c.get("fid")}})
        for n in m["native_only"]:
            items.append({"ask": UNIQUE_ASK, "finding": native_words(n), **at,
                          "_key": {"review": pair["review_id"], "source": "native"}})
    for r in reraised or []:
        items.append({"ask": "does it repeat one of the earlier findings?", "finding": words(r["finding"]),
                      "earlier": [words(e) for e in r["earlier"]],
                      **at_review[r["review"]],
                      # The earlier findings were raised against their own review's code.
                      "earlier_head_tree": (at_review.get(r["earlier_review"]) or {}).get("head_tree"),
                      "_key": {"review": r["review"], "reraise_by": r["by"],
                               "earlier_kind": r["earlier_kind"], "earlier_review": r["earlier_review"]}})
    rng.shuffle(items)
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
    print("\nper Critic goal — shared / shared with an observation / Critic only / native only:")
    for goal, row in tally_by_goal(matches).items():
        print(f"  {goal}: {row['shared']} / {row['shared_observation']} / {row['critic_only']} / {row['native_only']}")
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
    for stage, (outside, total) in outside_interval(joined).items():
        print(f"native findings on a file outside the Critic's interval, {stage}: {outside} of {total}")
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
