#!/usr/bin/env python3
"""Draw review windows: ~300-500 merged source lines from one landing, per item.

The unit is merged code (a landing's diff against its first parent), never a single commit,
so a defect a review caught and fixed inside its PR is not counted against that repo. Big
landings contribute a random subset of their source files, so each item stays reviewable and
results normalise to defects per kLOC merged.

Usage: sample_windows.py <clones> <landings.jsonl> <spec.json> <out.jsonl>
  spec: {"strata": [{"name": ..., "buckets": [...], "repos": [...] | null,
                     "since": "YYYY-MM-DD", "until": "YYYY-MM-DD", "n": N, "per_repo": K,
                     "lo": L, "hi": H}],   (lo/hi optional: window size, default 300/500)
         "seed": S, "exclude_shas": [...]}   (exclude_shas optional: landings already sampled)
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from escape import is_src  # noqa: E402

LO, HI = 300, 500


def ts(d):
    return dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()


def numstat(repo, sha):
    p = subprocess.run(["git", "-C", repo, "rev-parse", sha + "^1"], capture_output=True, text=True).stdout.strip()
    out = subprocess.run(["git", "-C", repo, "diff", "--numstat", "-w", p, sha], capture_output=True,
                         text=True, errors="replace").stdout
    files = []
    for line in out.splitlines():
        a, _, path = line.split("\t", 2)
        if a.isdigit() and int(a) > 0 and is_src(path):
            files.append((path, int(a)))
    return files


def window(rnd, files, lo=LO, hi=HI):
    rnd.shuffle(files)
    picked, total = [], 0
    for path, n in files:
        if n > hi and picked:
            continue
        picked.append(path)
        total += n
        if total >= lo:
            break
    return picked, total


def main():
    clones, landings, spec_path, dest = sys.argv[1:5]
    spec = json.load(open(spec_path))
    rnd = random.Random(spec["seed"])
    rows = [json.loads(l) for l in open(landings)]
    exclude = set(spec.get("exclude_shas", []))
    with open(dest, "w") as out:
        for st in spec["strata"]:
            pool = [r for r in rows if r["bucket"] in st["buckets"] and r["src_added"] >= 50
                    and ts(st["since"]) <= r["ts"] < ts(st["until"])
                    and (not st.get("repos") or r["repo"] in st["repos"])]
            rnd.shuffle(pool)
            per, got = {}, 0
            for r in pool:
                if got == st["n"]:
                    break
                if per.get(r["repo"], 0) >= st["per_repo"]:
                    continue
                repo = os.path.join(clones, r["repo"].replace("/", "_", 1) + ".git")
                files, total = window(rnd, numstat(repo, r["sha"]), st.get("lo", LO), st.get("hi", HI))
                if total < 50 or total > max(1500, 2 * st.get("hi", HI)) or r["sha"] in exclude:
                    continue
                per[r["repo"]] = per.get(r["repo"], 0) + 1
                got += 1
                out.write(json.dumps({"stratum": st["name"], "repo": r["repo"], "sha": r["sha"],
                                      "bucket": r["bucket"], "files": files, "lines": total}) + "\n")
            print(f"{st['name']}: {got}/{st['n']} from {len(pool)} candidates, {per}", file=sys.stderr)


if __name__ == "__main__":
    main()
