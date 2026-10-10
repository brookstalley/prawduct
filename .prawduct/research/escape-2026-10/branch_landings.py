#!/usr/bin/env python3
"""List an unmerged integration branch's recent landings as review-sampling candidates.

The study's retro-review sampled repo F's fast work from two integration branches that had not
merged to develop. escape.py follows only develop or the default branch, so this produces those
landings: first-parent commits since SINCE that the main branch does not contain, with source
lines added, in the landings.jsonl shape and with no rework traced (they were too recent to have
any). For rework on such a branch, use `escape.py --branch` instead.

Usage: branch_landings.py <bare-clone.git> <owner/repo> <since YYYY-MM-DD> <bucket> <main> <branch>...
  The study ran: <clone> <repo F> 2026-10-01 none-fast develop <its two integration branches>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from escape import is_src  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                          errors="replace").stdout


def main():
    clone, name, since, bucket, main_branch, *branches = sys.argv[1:]
    lines = set()
    for b in branches:
        lines.update(filter(None, git(clone, "log", "--first-parent", f"--since={since}",
                                      "--format=%H %ct %P", b, "--not", main_branch).split("\n")))
    for line in sorted(lines):
        sha, ct, *parents = line.split()
        numstat = git(clone, "diff", "--numstat", "-w", parents[0], sha)
        added = sum(int(a) for a, _, p in (x.split("\t", 2) for x in numstat.splitlines())
                    if a.isdigit() and is_src(p))
        print(json.dumps({"repo": name, "sha": sha, "ts": int(ct), "bucket": bucket,
                          "src_added": added, "merge": len(parents) > 1, "reworked": []}))


if __name__ == "__main__":
    main()
