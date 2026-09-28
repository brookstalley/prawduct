import json, collections, statistics, sys
# usage: rounds_per_pr.py [since] [until]  (ISO stamps; until is exclusive)
since = sys.argv[1] if len(sys.argv) > 1 else ""
until = sys.argv[2] if len(sys.argv) > 2 else "9999"
pr = collections.defaultdict(list); crit = collections.defaultdict(int); scope_of_branch = {}
for line in open(".prawduct/.governance-ledger.jsonl"):
    try: e = json.loads(line)
    except ValueError: continue
    if not (since <= e.get("ts","") < until): continue
    if e.get("event") == "review.pr":
        br = e["review"].get("branch") or e.get("scope")
        pr[br].append(e); scope_of_branch[br] = e.get("scope")
    elif e.get("event") == "review.critic":
        crit[e.get("scope")] += 1
prr = [len(v) for v in pr.values()]
cr = [crit.get(scope_of_branch[b], 0) for b in pr]
tot = [a+b for a,b in zip(prr,cr)]
def s(x): return f"n={len(x)} mean={statistics.mean(x):.2f} median={statistics.median(x)} max={max(x)}"
print("since", since or "all", "until", until if until != "9999" else "now")
print("PR-review rounds per PR branch:", s(prr))
print("Critic rounds per PR branch (by scope):", s(cr))
print("All review rounds per PR branch:", s(tot))
print("PR branches with >1 PR round:", sum(1 for x in prr if x>1))
