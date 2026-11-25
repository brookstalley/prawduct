"""Read-only: attribute each verify-resolutions round to the nearest earlier non-verify
round in the same scope (chunk / final / cumulative). usage: verify_attrib.py <ledger> <repo> <since>"""
import collections
import json
import re
import sys
from pathlib import Path

ledger, repo, since = sys.argv[1], Path(sys.argv[2]), sys.argv[3]


def n_chunks(scope):
    for p in [repo / ".prawduct/artifacts" / f"build-plan-{scope}.md",
              repo / ".prawduct/artifacts/archive" / f"build-plan-{scope}.md"]:
        if p.is_file():
            return len(set(re.findall(r"^#{2,3} Chunk (\d+)", p.read_text(errors="replace"), re.M)))
    return None


by = collections.defaultdict(list)
for line in open(ledger):
    e = json.loads(line)
    if e.get("event") == "review.critic" and e["ts"] >= since:
        by[e.get("scope")].append(e)
for label, pred in (("<=3", lambda n: n is not None and n <= 3), (">3", lambda n: n is not None and n > 3)):
    cnt = collections.Counter()
    mins = collections.Counter()
    for s, es in by.items():
        if not pred(n_chunks(s)):
            continue
        prev = None
        for e in sorted(es, key=lambda x: x["ts"]):
            m = e["review"]["mode"].split(" ")[0]
            if m == "verify-resolutions":
                k = prev or "none"
                cnt[k] += 1
                mins[k] += (e.get("duration_seconds") or 0) / 60
            else:
                prev = m
    print(label, {k: (cnt[k], round(mins[k])) for k in cnt})
