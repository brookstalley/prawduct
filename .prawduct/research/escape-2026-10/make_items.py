#!/usr/bin/env python3
"""Build blind review items from sampled landings.

Each item is a neutral directory `item-NN/` holding `tree/` (the source at the landing) and
`change.diff` (the landing's diff against its first parent). Governance files are left out of
both, and the repo name, commit messages and dates appear nowhere in the item. Which item is
which lives only in the key file, written outside the items directory.

Usage: make_items.py <clones-dir> <sample.jsonl> <items-dir> <key.jsonl>
  sample.jsonl rows need: repo ("owner/name"), sha, optionally files (limit the diff to them),
  and anything else to carry into the key.
"""
import json
import os
import subprocess
import sys

EXCLUDE = [".prawduct", ".claude", "CLAUDE.md", "AGENTS.md", "CHANGELOG.md", "CHANGES.md"]


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True, **kw).stdout


def main():
    clones, sample, items, keyfile = sys.argv[1:5]
    os.makedirs(items, exist_ok=True)
    rows = [json.loads(l) for l in open(sample)]
    with open(keyfile, "w") as key:
        for n, row in enumerate(rows, 1):
            repo = os.path.join(clones, row["repo"].replace("/", "_", 1) + ".git")
            item = os.path.join(items, f"item-{n:02d}")
            tree = os.path.join(item, "tree")
            os.makedirs(tree, exist_ok=True)
            pathspec = ["--", "."] + [f":(exclude){p}" for p in EXCLUDE]
            tar = git(repo, "archive", row["sha"], *pathspec[1:])
            subprocess.run(["tar", "-x", "-C", tree], input=tar, check=True)
            parent = git(repo, "rev-parse", row["sha"] + "^1", text=True).strip()
            # A window reviews only its sampled files; the whole tree stays readable for context.
            scope = ["--", *row["files"]] if row.get("files") else pathspec
            diff = git(repo, "diff", "--no-color", parent, row["sha"], *scope)
            with open(os.path.join(item, "change.diff"), "wb") as f:
                f.write(diff)
            key.write(json.dumps({"item": f"item-{n:02d}", **row}) + "\n")


if __name__ == "__main__":
    main()
