"""Read-only measurement for the #1247 design doc.

Reads the governance ledger (review.critic events) of the main checkout and the
build plans (live + archived) of the worktree. Writes nothing but stdout.
usage: python3 -I measure.py <ledger.jsonl> <repo_dir> [since]
"""
import collections
import json
import re
import statistics
import sys
from pathlib import Path

ledger, repo = sys.argv[1], Path(sys.argv[2])
since = sys.argv[3] if len(sys.argv) > 3 else ""

def mode_of(r):
    m = (r.get("mode") or "").split(" ")[0]
    return m

events = []
for line in open(ledger):
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        continue
    if e.get("event") != "review.critic":
        continue
    if since and e.get("ts", "") < since:
        continue
    events.append(e)

def sevs(r):
    c = collections.Counter((f.get("severity") or "").lower() for f in r.get("findings") or [])
    return c

print(f"window: since {since or 'start'}; review.critic events: {len(events)}; "
      f"first {events[0]['ts'] if events else '-'} last {events[-1]['ts'] if events else '-'}")

# 1. per mode
per = collections.defaultdict(list)
for e in events:
    per[mode_of(e["review"])].append(e)
print("\nmode | rounds | median min | total h | rounds w/ BLOCKING | rounds w/ WARNING | blocking findings")
for m, es in sorted(per.items()):
    d = [x.get("duration_seconds") or (x["review"].get("duration_seconds") or 0) for x in es]
    d = [v for v in d if v]
    b = sum(1 for x in es if sevs(x["review"])["blocking"])
    w = sum(1 for x in es if sevs(x["review"])["warning"])
    nb = sum(sevs(x["review"])["blocking"] for x in es)
    print(f"{m} | {len(es)} | {statistics.median(d)/60 if d else 0:.1f} | {sum(d)/3600:.1f} | {b} | {w} | {nb}")

# 2. plan chunk counts by scope
def plan_chunks(scope):
    for p in [repo / ".prawduct/artifacts" / f"build-plan-{scope}.md",
              repo / ".prawduct/artifacts/archive" / f"build-plan-{scope}.md"]:
        if p.is_file():
            ids = set(re.findall(r"^#{2,3} Chunk (\d+)", p.read_text(errors="replace"), re.M))
            return len(ids)
    return None

by_scope = collections.defaultdict(list)
for e in events:
    by_scope[e.get("scope") or "?"].append(e)

rows = []
for scope, es in by_scope.items():
    n = plan_chunks(scope)
    rows.append((scope, n, es))

def summarize(label, sel):
    modes = collections.Counter()
    mins = collections.Counter()
    blk = collections.Counter()
    for _s, _n, es in sel:
        for e in es:
            m = mode_of(e["review"])
            modes[m] += 1
            mins[m] += (e.get("duration_seconds") or 0) / 60
            if sevs(e["review"])["blocking"]:
                blk[m] += 1
    tot = sum(mins.values())
    print(f"\n{label}: scopes={len(sel)}")
    for m in sorted(modes):
        print(f"  {m}: rounds={modes[m]} minutes={mins[m]:.0f} ({100*mins[m]/tot if tot else 0:.0f}% of review minutes) rounds_with_blocking={blk[m]}")

known = [r for r in rows if r[1] is not None]
summarize("scopes with a plan of <=3 chunks", [r for r in known if r[1] <= 3])
summarize("scopes with a plan of >3 chunks", [r for r in known if r[1] > 3])
print(f"\nscopes with no plan file found: {sum(1 for r in rows if r[1] is None)} "
      f"(rounds {sum(len(r[2]) for r in rows if r[1] is None)})")

# 3. multi-chunk scopes that ran chunk-mode rounds: per scope detail
print("\n>3-chunk scopes that ran any `chunk` round:")
print("scope | plan chunks | chunk rounds (blocking rounds) | final | cumulative (blocking rounds) | verify | chunk min | boundary min | chunk BLOCKING goals")
for scope, n, es in sorted(known, key=lambda r: r[2][0]["ts"]):
    if n is None or n <= 3:
        continue
    c = [e for e in es if mode_of(e["review"]) == "chunk"]
    if not c:
        continue
    cu = [e for e in es if mode_of(e["review"]) == "cumulative"]
    fi = [e for e in es if mode_of(e["review"]) == "final"]
    vr = [e for e in es if mode_of(e["review"]) == "verify-resolutions"]
    goals = collections.Counter(
        f.get("goal") for e in c for f in e["review"].get("findings") or []
        if (f.get("severity") or "").lower() == "blocking")
    print(f"{scope} | {n} | {len(c)} ({sum(1 for e in c if sevs(e['review'])['blocking'])}) | {len(fi)} | "
          f"{len(cu)} ({sum(1 for e in cu if sevs(e['review'])['blocking'])}) | {len(vr)} | "
          f"{sum((e.get('duration_seconds') or 0) for e in c)/60:.0f} | "
          f"{sum((e.get('duration_seconds') or 0) for e in cu)/60:.0f} | {dict(goals)}")

# 4. chunk BLOCKING findings, all scopes: goal and file overlap with the scope's later cumulative
print("\n`chunk`-round BLOCKING findings (all scopes in window): goal distribution, and whether a later")
print("cumulative in the same scope reviewed the finding's files (necessary, not sufficient, for 'would have seen it')")
g = collections.Counter(); later_cov = 0; total = 0; no_later = 0
for scope, n, es in rows:
    cums = [e for e in es if mode_of(e["review"]) == "cumulative"]
    for e in es:
        if mode_of(e["review"]) != "chunk":
            continue
        for f in e["review"].get("findings") or []:
            if (f.get("severity") or "").lower() != "blocking":
                continue
            total += 1
            g[f.get("goal")] += 1
            later = [x for x in cums if x["ts"] > e["ts"]]
            if not later:
                no_later += 1
                continue
            files = set(f.get("files") or [])
            files = {x.split(":")[0] for x in files}
            if files and any(files & set(x["review"].get("files_reviewed") or []) for x in later):
                later_cov += 1
print(f"  total={total} goals={dict(g)} later_cumulative_reviewed_files={later_cov} no_later_cumulative_in_scope={no_later}")
