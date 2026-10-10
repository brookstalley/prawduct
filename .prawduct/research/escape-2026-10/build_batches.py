#!/usr/bin/env python3
"""Build the classifier input batches for the study's three classification passes.

Each subcommand writes text batches that a workflow prompt reads (wf-*-classification.js,
wf-retro-review.js catch class). Seeds, caps and cut-offs are the ones the 2026-10 study used.

  build_batches.py edges <clones> <landings.jsonl> <out-dir> <key.json>
      Sample rework edges (gap >= 24h, landed by CUTOFF) per mode, at most PER_REPO per repo,
      and write batches of BATCH edges with the earlier subject, the later messages and diff.
  build_batches.py catch <edges-dir> <key.json> <fixclass_results.json> <out-dir>
      The edges labelled "fix" (Sonnet), split into two files, with the label's reason appended.
  build_batches.py cause <edges-dir> <key.json> <fixclass_results.json> <out-dir>
      The edges labelled "evolution" or "unclear", shuffled into 10 files.
"""
import collections
import datetime as dt
import glob
import json
import os
import random
import subprocess
import sys

# Local midnight 2026-09-10 on the study machine (UTC-6), 30 days before the run; pinned to
# that instant so a rebuild in any timezone reproduces the sample.
CUTOFF = dt.datetime(2026, 9, 10, 6, tzinfo=dt.timezone.utc).timestamp()
PER_MODE, PER_REPO, BATCH, MIN_GAP_H = 60, 12, 15, 24
DIFF_LINES, MSG_CHARS = 180, 2500
DIFF_EXCLUDES = [":(exclude).prawduct", ":(exclude).claude", ":(exclude)*.md", ":(exclude)*test*"]


def mode(bucket):
    if bucket in ("none", "dormant"):
        return "none"
    return "early" if bucket == "1.x" or bucket.startswith("2.") else "3x"


def git(clones, repo, *args):
    path = os.path.join(clones, repo.replace("/", "_", 1) + ".git")
    return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True,
                          errors="replace").stdout


def edges(clones, landings, out_dir, key_path):
    pool = collections.defaultdict(list)
    for line in open(landings):
        r = json.loads(line)
        if r["src_added"] < 1 or r["ts"] > CUTOFF:
            continue
        for e in r["reworked"]:
            if e["gap_h"] >= MIN_GAP_H:
                pool[mode(r["bucket"])].append((r["repo"], r["sha"], e["by"], e["lines"]))
    rnd = random.Random(20261010)
    sample = []
    for m, pooled in pool.items():
        rnd.shuffle(pooled)
        per, picked = collections.Counter(), []
        for e in pooled:
            if per[e[0]] >= PER_REPO:
                continue
            per[e[0]] += 1
            picked.append(e)
            if len(picked) == PER_MODE:
                break
        sample += [dict(mode=m, repo=a, intro=b, fixer=c, lines=d) for a, b, c, d in picked]
    rnd.shuffle(sample)
    for i, s in enumerate(sample):
        s["id"] = f"e{i:03d}"
    os.makedirs(os.path.dirname(os.path.abspath(key_path)), exist_ok=True)
    json.dump(sample, open(key_path, "w"), indent=0)
    os.makedirs(out_dir, exist_ok=True)
    for b in range(0, len(sample), BATCH):
        blocks = []
        for s in sample[b:b + BATCH]:
            subject = git(clones, s["repo"], "log", "-1", "--format=%s", s["intro"]).strip()
            parent = git(clones, s["repo"], "rev-parse", s["fixer"] + "^1").strip()
            msgs = git(clones, s["repo"], "log", "--format=- %s%n%b", f"{parent}..{s['fixer']}")[:MSG_CHARS]
            diff = git(clones, s["repo"], "diff", "-U2", "-w", parent, s["fixer"], "--", ".", *DIFF_EXCLUDES)
            diff = "\n".join(diff.splitlines()[:DIFF_LINES])
            blocks.append(f"=== EDGE {s['id']}\nEARLIER change (subject): {subject}\n"
                          f"LATER change rewrote {s['lines']} source lines of the earlier one, \n"
                          f"LATER change commit messages:\n{msgs}\nLATER change diff (truncated):\n{diff}\n")
        with open(os.path.join(out_dir, f"batch-{b // BATCH:02d}.txt"), "w") as f:
            f.write("\n".join(blocks))


def _blocks(edges_dir):
    out = {}
    for path in sorted(glob.glob(os.path.join(edges_dir, "batch-*.txt"))):
        for b in open(path).read().split("=== EDGE ")[1:]:
            out[b.split("\n", 1)[0].strip()] = "=== EDGE " + b
    return out


def _sonnet_labels(results_path):
    res = json.load(open(results_path))
    return {e["id"]: e for r in res if r["model"] == "sonnet" for e in r["edges"]}


def catch(edges_dir, key_path, results_path, out_dir):
    labels, blocks = _sonnet_labels(results_path), _blocks(edges_dir)
    ids = sorted(i for i, e in labels.items() if e["label"] == "fix")
    half = (len(ids) + 1) // 2
    os.makedirs(out_dir, exist_ok=True)
    for n, part in enumerate([ids[:half], ids[half:]]):
        with open(os.path.join(out_dir, f"catchclass-{n}.txt"), "w") as f:
            f.write("\n".join(blocks[i] + f"\n(Classifier summary of the defect: {labels[i]['reason']})\n"
                              for i in part))


def cause(edges_dir, key_path, results_path, out_dir):
    labels, blocks = _sonnet_labels(results_path), _blocks(edges_dir)
    ids = [i for i, e in labels.items() if e["label"] in ("evolution", "unclear")]
    random.Random(3).shuffle(ids)
    per = -(-len(ids) // 10)
    os.makedirs(out_dir, exist_ok=True)
    for b in range(10):
        part = ids[b * per:(b + 1) * per]
        if part:
            with open(os.path.join(out_dir, f"batch-{b:02d}.txt"), "w") as f:
                f.write("\n".join(blocks[i] for i in part))


if __name__ == "__main__":
    {"edges": edges, "catch": catch, "cause": cause}[sys.argv[1]](*sys.argv[2:])
