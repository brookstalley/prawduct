#!/usr/bin/env python3
"""Re-derive the computed numbers in governance-roi-study-2026-10.md from the study's data directory.

Two figures in the artifact are not computed and so are not printed: "0 of 8 known escapes caught"
(a reading of each calibration item's findings against its known fix) and the agent-run count
(from the workflow logs).

Usage: stats.py <data-dir>
  data-dir holds landings.jsonl, fast_landings.jsonl, the pilot/wave2 keys and results,
  fixclass_key.json, fixclass_results.json, wave1_results.json (its catchclass) and
  causeclass_results.json.
"""
import collections
import datetime as dt
import json
import math
import os
import sys
import time

# Same instant as build_batches.CUTOFF: landings after it have no full 30-day window.
CUTOFF = dt.datetime(2026, 9, 10, 6, tzinfo=dt.timezone.utc).timestamp()
RECENT = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc).timestamp()
# Review strata are named in the private keys: "gov-…" are governed, "known-escape" are calibration
# items, everything else is ungoverned. Repo F, the anonymised fast ungoverned repo, is named only in
# <data>/repo_f.txt, so this public file never identifies it.


def jl(path):
    return [json.loads(l) for l in open(path)]


def version_group(bucket):
    if bucket in ("none", "dormant", "1.x"):
        return bucket
    if bucket.startswith("2."):
        return "2.x"
    return "3.0-3.3" if int(bucket.split(".")[1]) <= 3 else "3.4-3.5"


def mode(bucket):
    if bucket in ("none", "dormant"):
        return "none"
    return "early" if bucket == "1.x" or bucket.startswith("2.") else "3x"


def review_items(d):
    rows = []
    for wave, res_name, key_name in (("wave1", "wave1_results.json", "pilot_key.jsonl"),
                                     ("wave2", "wave2_results.json", "wave2_key.jsonl")):
        key = {k["item"]: k for k in jl(os.path.join(d, key_name))}
        for r in json.load(open(os.path.join(d, res_name)))["reviews"]:
            k = key[r["item"]]
            if k["stratum"] == "known-escape":
                continue
            verdicts = {v["index"]: v for v in (r["verdicts"] or [])}
            real = [verdicts[i]["severity"] for i in range(len(r["defects"] or []))
                    if verdicts.get(i, {}).get("verdict") == "real"]
            rows.append({"group": "gov" if k["stratum"].startswith("gov") else "ungov",
                         "repo": k["repo"], "lines": k["lines"], "real": len(real),
                         "high": real.count("high"), "reported": len(r["defects"] or []), "wave": wave})
    return rows


def section1(d):
    rows = review_items(d)
    print("## 1. Defect density (blind retro-review)")
    agg = {}
    for g in ("ungov", "gov"):
        rs = [r for r in rows if r["group"] == g]
        L, D = sum(r["lines"] for r in rs), sum(r["real"] for r in rs)
        agg[g] = (L, D)
        print(f"  {g:5} items {len(rs)} kLOC {L / 1000:.1f} verified {D} (high {sum(r['high'] for r in rs)})"
              f" reported {sum(r['reported'] for r in rs)} items>=1 {sum(r['real'] > 0 for r in rs)}"
              f" per kLOC {1000 * D / L:.2f}")
    (Lu, Du), (Lg, Dg) = agg["ungov"], agg["gov"]
    rr, se = (Du / Lu) / (Dg / Lg), math.sqrt(1 / Du + 1 / Dg)
    n, p = Du + Dg, Lu / (Lu + Lg)
    one_sided = sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(Du, n + 1))
    print(f"  rate ratio {rr:.2f}, 95% CI {rr * math.exp(-1.96 * se):.2f}-{rr * math.exp(1.96 * se):.2f},"
          f" two-sided p ~ {min(1, 2 * one_sided):.2f}")
    repo_f = open(os.path.join(d, "repo_f.txt")).read().strip()
    for label, repo in (("repo F", repo_f), ("prawduct", "brookstalley/prawduct")):
        u = [r for r in rows if r["group"] == "ungov" and r["repo"] != repo]
        g = [r for r in rows if r["group"] == "gov" and r["repo"] != repo]
        a = sum(r["real"] for r in u) / sum(r["lines"] for r in u)
        b = sum(r["real"] for r in g) / sum(r["lines"] for r in g)
        print(f"  without {label}: ratio {a / b:.2f}")
    w1 = [r for r in rows if r["wave"] == "wave1"]
    print("  wave 1 alone: " + ", ".join(
        f"{g} {1000 * sum(r['real'] for r in w1 if r['group'] == g) / sum(r['lines'] for r in w1 if r['group'] == g):.2f}"
        f" (n={sum(r['group'] == g for r in w1)})" for g in ("ungov", "gov")))
    f = [r for r in rows if r["repo"] == repo_f]
    print(f"  repo F alone: {sum(r['real'] for r in f)} in {sum(r['lines'] for r in f) / 1000:.1f} kLOC")


def edge_rates(d):
    """Rework edges (gap >= 24h) per kLOC by mode, over landings with a full window."""
    acc = collections.defaultdict(lambda: [0, 0])
    for r in jl(os.path.join(d, "landings.jsonl")):
        if r["src_added"] < 1 or r["ts"] > CUTOFF:
            continue
        a = acc[mode(r["bucket"])]
        a[0] += r["src_added"]
        a[1] += sum(1 for e in r["reworked"] if e["gap_h"] >= 24)
    return {m: 1000 * n / added for m, (added, n) in acc.items()}


def section0(d):
    repos = {r["repo"] for r in jl(os.path.join(d, "landings.jsonl"))}
    print(f"## Scope: {len(repos)} repos")


def pilot(d):
    """Sonnet against Opus on the pilot's calibration items, and Sonnet on the main items.

    Whether any finding was the KNOWN escape (the study's "0 of 8") is a judgment made by reading
    each item's findings against its known fix; it is not computed here."""
    key = {k["item"]: k for k in jl(os.path.join(d, "pilot_key.jsonl"))}
    real = collections.Counter()
    for r in json.load(open(os.path.join(d, "pilot_results.json"))):
        verdicts = {v["index"]: v for v in (r["verdicts"] or [])}
        cal = key[r["item"]]["stratum"] == "known-escape"
        for i, finding in enumerate(r["defects"]):
            if verdicts.get(i, {}).get("verdict") == "real":
                real[(finding["model"], "calibration" if cal else "main")] += 1
    print(f"## Pilot: verified-real on calibration items, Opus {real[('opus', 'calibration')]}"
          f" vs Sonnet {real[('sonnet', 'calibration')]}; Sonnet on the 20 main items {real[('sonnet', 'main')]}")


def section2(d):
    print("## 2. Rework lines per kLOC (gap >= 24h, landed by cutoff)")
    acc = collections.defaultdict(lambda: [0, 0])
    for r in jl(os.path.join(d, "landings.jsonl")):
        if r["src_added"] < 1 or r["ts"] > CUTOFF:
            continue
        a = acc[version_group(r["bucket"])]
        a[0] += r["src_added"]
        a[1] += sum(e["lines"] for e in r["reworked"] if e["gap_h"] >= 24)
    for g in ("none", "1.x", "2.x", "3.0-3.3", "3.4-3.5"):
        if acc[g][0]:
            print(f"  {g:8} {1000 * acc[g][1] / acc[g][0]:.0f}")
    per_repo = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in jl(os.path.join(d, "landings.jsonl")):
        if r["src_added"] < 1 or r["ts"] > CUTOFF:
            continue
        a = per_repo[r["repo"]][version_group(r["bucket"])]
        a[0] += r["src_added"]
        a[1] += sum(e["lines"] for e in r["reworked"] if e["gap_h"] >= 24)
    largest = max(per_repo, key=lambda rp: sum(v[0] for g, v in per_repo[rp].items() if g not in ("none", "dormant")))
    print("  largest governed repo: " + " -> ".join(
        f"{1000 * per_repo[largest][g][1] / per_repo[largest][g][0]:.0f}"
        for g in ("none", "1.x", "2.x", "3.0-3.3", "3.4-3.5") if per_repo[largest][g][0]))
    key = {k["id"]: k for k in json.load(open(os.path.join(d, "fixclass_key.json")))}
    res = json.load(open(os.path.join(d, "fixclass_results.json")))
    son = {e["id"]: e for r in res if r["model"] == "sonnet" for e in r["edges"]}
    print(f"  edges labelled by Sonnet: {len(son)} of {len(key)}")
    opus = {e["id"]: e for r in res if r["model"] == "opus" for e in r["edges"]}
    both = [i for i in opus if i in son]
    print(f"  Opus/Sonnet agreement {sum(son[i]['label'] == opus[i]['label'] for i in both)}/{len(both)}")
    for m in ("none", "early", "3x"):
        ids = [i for i in son if key[i]["mode"] == m]
        fixes = sum(son[i]["label"] == "fix" for i in ids)
        print(f"  fix share {m}: {fixes}/{len(ids)}; escapes per kLOC ~ {edge_rates(d)[m] * fixes / len(ids):.1f}")


def section3(d):
    print("## 3. Catch class of genuine defects")
    key = {k["id"]: k for k in json.load(open(os.path.join(d, "fixclass_key.json")))}
    cc = [c for c in json.load(open(os.path.join(d, "wave1_results.json")))["catchclass"] if c["is_defect"]]
    print(f"  all ({len(cc)}): {dict(collections.Counter(c['earliest_catch'] for c in cc))}")
    for m in ("none", "early", "3x"):
        print(f"  {m}: {dict(collections.Counter(c['earliest_catch'] for c in cc if key[c['id']]['mode'] == m))}")


def section4(d):
    print("## 4. Causes of non-fix rework")
    key = {k["id"]: k for k in json.load(open(os.path.join(d, "fixclass_key.json")))}
    res = json.load(open(os.path.join(d, "causeclass_results.json")))
    son = {e["id"]: e for r in json.load(open(os.path.join(d, "fixclass_results.json")))
           if r["model"] == "sonnet" for e in r["edges"]}
    rates = edge_rates(d)
    for m in ("none", "early", "3x"):
        ids = [i for i in son if key[i]["mode"] == m]
        evolution = rates[m] * sum(son[i]["label"] != "fix" for i in ids) / len(ids)
        es = [e for e in res if key[e["id"]]["mode"] == m]
        c = collections.Counter(e["cause"] for e in es)
        yes = sum(e["avoidable_by_discovery"] == "yes" for e in es)
        print(f"  {m} ({len(es)}): " + ", ".join(f"{k} {100 * v / len(es):.0f}%" for k, v in c.most_common())
              + f"; discovery-avoidable {100 * yes / len(es):.0f}%")
        late = sum(e["cause"] == "late_requirement" for e in es) / len(es)
        print(f"    per kLOC: late-requirement edges {evolution * late:.2f},"
              f" discovery-avoidable edges {evolution * yes / len(es):.2f}")


def section5(d):
    print("## 5. Merged source kLOC per active day since 2026-09-01")
    acc = collections.defaultdict(lambda: [0, set()])
    for name in ("landings.jsonl", "fast_landings.jsonl"):
        for r in jl(os.path.join(d, name)):
            if r["ts"] < RECENT:
                continue
            a = acc[("gov" if r["bucket"][0] == "3" else "ungov", r["repo"])]
            a[0] += r["src_added"]
            a[1].add(time.strftime("%Y-%m-%d", time.gmtime(r["ts"])))
    pooled = collections.defaultdict(lambda: [0, 0])
    for (g, repo), (added, days) in sorted(acc.items(), key=lambda x: -x[1][0]):
        if added < 2000:
            continue
        pooled[g][0] += added
        pooled[g][1] += len(days)
        if added > 100000:
            print(f"  {g:5} {'repo F' if repo == open(os.path.join(d, 'repo_f.txt')).read().strip() else 'a large repo'}:"
                  f" {added / 1000 / len(days):.1f}")
    for g, (added, days) in pooled.items():
        print(f"  pooled {g}: {added / 1000 / days:.1f}")


if __name__ == "__main__":
    for section in (section0, pilot, section1, section2, section3, section4, section5):
        section(sys.argv[1])
