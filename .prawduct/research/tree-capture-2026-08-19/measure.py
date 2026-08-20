#!/usr/bin/env python3
"""Derivations behind the tree-capture seeding change for #675.

Committed rather than run-and-discarded: a spike that throws its code away
leaves its numbers unfalsifiable, so every durable artifact cites THIS COMMAND
rather than the digits it prints.

    python3 .prawduct/research/tree-capture-2026-08-19/measure.py

Three questions, three sections.

A. Does seeding the temp index from a COPY of `.git/index` beat seeding it with
   `read-tree HEAD`? `read-tree` writes entries with ZEROED stat data, so every
   tracked file is a cache miss and `git add -A` re-hashes the whole working
   tree. The copy carries real stat data, so `add -A` skips files whose stat
   still matches. Timed on this repo's own tree, which is the tree every
   `critic-begin` here actually captures. The reported figure is a local-disk
   floor: the field report is a bind mount, where each skipped read also saves
   a mount round trip, so the real-world gap is wider than anything measurable
   here.

B. Do the two seeds agree on the tree they write? They must — this is a cost
   fix, not a semantic one. Asserted on the live working tree.

C. Does the copy have to preserve the index's MTIME? Yes, and this section is
   why. Git's stat cache skips a file whose size and mtime still match its
   entry; the racily-clean rule ("an entry whose mtime is not older than the
   index FILE's own may have changed in the same tick — re-read it") is the
   only thing that catches a same-second, same-size edit. A copy stamped with
   the current time destroys that signal. This section runs the race for real,
   many times, on a synthetic repo: `copyfile` loses edits at a rate that
   depends on the machine's speed; `copy2` never does. The deterministic
   version of this claim is pinned in tests/test_evidence_store.py
   (test_same_second_same_size_edit_is_still_captured).
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "plugin"))

from lib import evidence  # noqa: E402

TRIALS = 5
RACE_TRIALS = 200


def _git(cwd, *args, env=None):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, env=env, check=True
    ).stdout.strip()


def _capture(repo, seed):
    """One capture, timed, seeded the named way. Mirrors evidence.capture_tree
    closely enough to be a fair comparison and deliberately does NOT call it —
    the point is to time the seed that was replaced against the one that
    replaced it, and only one of them still exists in the code."""
    git_dir = pathlib.Path(_git(repo, "rev-parse", "--absolute-git-dir"))
    fd, tmp = tempfile.mkstemp(prefix="prawduct-measure-idx-")
    os.close(fd)
    os.unlink(tmp)
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = tmp
    started = time.monotonic()
    try:
        if seed == "read-tree":
            _git(repo, "read-tree", "HEAD", env=env)
        else:
            shutil.copy2(git_dir / "index", tmp)
        _git(repo, "add", "-A", env=env)
        tree = _git(repo, "write-tree", env=env)
    finally:
        for leftover in (tmp, tmp + ".lock"):
            try:
                os.unlink(leftover)
            except OSError:
                pass
    return time.monotonic() - started, tree


def section_a_and_b():
    print("A/B. seed cost and seed agreement, on this repo's live working tree")
    tracked = len(_git(REPO, "ls-files").splitlines())
    print(f"    tracked files: {tracked}")
    _capture(REPO, "read-tree")  # warm the filesystem cache for both
    _capture(REPO, "copy")
    results = {}
    for seed in ("read-tree", "copy"):
        samples = [_capture(REPO, seed) for _ in range(TRIALS)]
        times = sorted(s[0] for s in samples)
        trees = {s[1] for s in samples}
        results[seed] = (times[len(times) // 2], trees)
        print(f"    {seed:10s} median {times[len(times) // 2]:.3f}s  "
              f"min {times[0]:.3f}s  max {times[-1]:.3f}s")
    rt, cp = results["read-tree"][0], results["copy"][0]
    print(f"    speedup: {rt / cp:.1f}x (local disk; a bind mount pays more per skipped read)")
    all_trees = results["read-tree"][1] | results["copy"][1]
    print(f"    B. both seeds wrote {'the SAME tree' if len(all_trees) == 1 else 'DIFFERENT trees'}"
          f": {', '.join(sorted(all_trees))}")


def section_c():
    print()
    print("C. does the copy have to preserve the index mtime?")
    losses = {"copyfile": 0, "copy2": 0}
    for trial in range(RACE_TRIALS):
        base = pathlib.Path(tempfile.mkdtemp(prefix="prawduct-race-"))
        try:
            repo = base / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            (repo / "code.py").write_text("x = 1\n")
            _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
            _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c1")
            # Same byte length, written as fast as possible after the commit —
            # the same filesystem tick is exactly the window under test.
            (repo / "code.py").write_text("x = 9\n")
            for name, copier in (("copyfile", shutil.copyfile), ("copy2", shutil.copy2)):
                real = evidence.shutil.copy2
                evidence.shutil.copy2 = copier
                try:
                    tree = evidence.capture_tree(repo)["tree"]
                finally:
                    evidence.shutil.copy2 = real
                blob = _git(repo, "ls-tree", "-r", tree, "--", "code.py").split()[2]
                if _git(repo, "cat-file", "-p", blob) != "x = 9":
                    losses[name] += 1
        finally:
            shutil.rmtree(base, ignore_errors=True)
    for name, count in losses.items():
        print(f"    {name:9s} lost the edit in {count}/{RACE_TRIALS} races")
    print("    a lost edit means the captured tree carried the file's PREVIOUS")
    print("    content — a review vouching for a tree that never existed")


if __name__ == "__main__":
    section_a_and_b()
    section_c()
