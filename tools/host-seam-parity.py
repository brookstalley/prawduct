#!/usr/bin/env python3
"""Do two plugin versions' hooks answer identically on real governed repos?

#1037 moved every host payload read, root read and structured hook response into
`plugin/lib/host.py` and promised Claude's behaviour would not move (#928 R-3).
The goldens pin that on fixtures; this pins it on the repos the hooks actually
govern. For each repo it makes two copy-on-write copies, runs the same sequence
of hook events against one with the BASE plugin and the other with the HEAD
plugin, and compares stdout, stderr and the exit code of every step:

    tools/host-seam-parity.py --work /tmp/parity                 # sibling repos
    tools/host-seam-parity.py --work /tmp/parity ../foo ../bar   # named repos
    tools/host-seam-parity.py --work /tmp/parity --base develop --head HEAD

Both plugin trees are exported from git (`git archive`), so both are committed
code and neither is a working tree (which would put a provenance segment in
one banner only). Copies are made with `cp -cRp` (APFS clonefile, mtimes
kept), so a large repo costs metadata, not disk; the hooks write their state into the copies,
never the real repo. Two kinds of repo are skipped, and the report says which:
a linked worktree, whose git dir lives in another repo, so a copy would write
the Stop gate's evidence into the real one; and a repo over `--max-gb`.

Each step's output is compared after replacing four run facts, each a fact of
WHEN or WHERE a side ran rather than of what its code does:

- the copy path (each side's copy lives under its own parent);
- the plugin root;
- the working-tree id in the Stop gate's coverage line (`→ <12 hex>`). The
  hooks write second-resolution timestamps into `.prawduct/.session-start` and
  `.advisories.json`; in a repo whose `.gitignore` misses one of them, that
  untracked file is part of the tree, so two runs a second apart name two trees;
- the backlog snapshot's age (`snapshot just now` / `snapshot 1m old`).

A difference that survives is printed in full. Exit 0 means at least one repo
was compared and none differed; 1 means a difference; 2 means nothing was
compared (every repo skipped, or BASE and HEAD carry the same `plugin/` tree), which proves
nothing either way. Network: the Stop gate's
`gh pr list` and the briefing's backlog-cache refresh are reads, made once per
side. Nothing is sent anywhere else.
"""
from __future__ import annotations

import argparse
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent

_RUNNING_TURN = (
    "Working.\n\n---\n\n`STATE` — in progress.\n\n"
    "`RUNNING` — a review; if it never lands, re-run it.\n\n`DO NOT CLEAR` — in flight."
)

#: (label, argv relative to the plugin root, stdin payload or None). Ordered:
#: the orientation and Stop steps first, the destructive session boundary last
#: but one, then a Stop that reads what the boundary left.
STEPS: list[tuple[str, list[str], dict | None]] = [
    ("banner", ["hooks/banner.py"], None),
    ("digest", ["hooks/digest.py"], None),
    ("clear --brief-only", ["bin/prawduct-hook", "clear", "--session-start", "--brief-only"], None),
    ("stop {}", ["bin/prawduct-hook", "stop"], {}),
    ("stop running-turn", ["bin/prawduct-hook", "stop"], {"last_assistant_message": _RUNNING_TURN}),
    ("stop tasks", ["bin/prawduct-hook", "stop"],
     {"background_tasks": [{"type": "workflow", "name": "parity", "id": "wf_1"}]}),
    ("subagent-stop other", ["bin/prawduct-hook", "subagent-stop"],
     {"agent_type": "general-purpose"}),
    ("subagent-stop reviewer", ["bin/prawduct-hook", "subagent-stop"],
     {"agent_type": "prawduct:critic-reviewer"}),
    ("clear --session-start", ["bin/prawduct-hook", "clear", "--session-start"], None),
    ("stop after boundary", ["bin/prawduct-hook", "stop"], {}),
]


def _git(*args: str, cwd: Path = CHECKOUT) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True, timeout=120
    ).stdout.strip()


def export_plugin(ref: str, dest: Path) -> Path:
    """The plugin tree at `ref`, extracted under `dest`."""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref, "plugin"],
        cwd=str(CHECKOUT), capture_output=True, check=True, timeout=120,
    ).stdout
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="tar")
    return dest / "plugin"


def candidate_repos() -> list[Path]:
    """Every sibling of this checkout that a session would govern."""
    return sorted(p.parent for p in CHECKOUT.parent.glob("*/.prawduct") if p.is_dir())


def size_gb(repo: Path) -> float:
    out = subprocess.run(["du", "-sk", str(repo)], capture_output=True, text=True).stdout
    return int(out.split()[0]) / (1024 * 1024) if out else 0.0


def skip_reason(repo: Path, max_gb: float) -> str | None:
    git = repo / ".git"
    if git.is_file():
        return "linked worktree: its git dir is shared, so a copy would write into the real repo"
    if not git.is_dir():
        return "not a git repository"
    gb = size_gb(repo)
    if gb > max_gb:
        return f"{gb:.0f} GB, over --max-gb {max_gb:g}"
    return None


def clone_copy(repo: Path, dest: Path) -> None:
    """Copy-on-write where the filesystem offers it (`cp -c`, APFS), else a
    plain copy, which costs the repo's size in disk."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for argv in (["cp", "-cRp"], ["cp", "-Rp"]):
        if dest.exists():
            shutil.rmtree(dest)
        result = subprocess.run([*argv, str(repo), str(dest)], capture_output=True, text=True)
        if result.returncode == 0:
            return
    raise RuntimeError(f"copy of {repo} failed: {result.stderr.strip()}")


def run_step(plugin: Path, copy: Path, argv: list[str], payload: dict | None) -> dict:
    env = dict(os.environ)
    env.pop("PRAWDUCT_HOST", None)
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin)
    env["CLAUDE_PROJECT_DIR"] = str(copy)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(plugin / argv[0]), *argv[1:]],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True, text=True, env=env, cwd=str(copy), timeout=600,
    )
    return {"exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


_TREE_ID = re.compile(r"(→ |to )[0-9a-f]{12}\b")
_SNAPSHOT_AGE = re.compile(r"snapshot (just now|\d+[smhd] old)")


def normalize(result: dict, copy: Path, plugin: Path) -> dict:
    def fix(text: str) -> str:
        for spelling in {str(copy.resolve()), str(copy)}:
            text = text.replace(spelling, "<REPO>")
        for spelling in {str(plugin.resolve()), str(plugin)}:
            text = text.replace(spelling, "<PLUGIN>")
        text = _TREE_ID.sub(r"\1<TREE>", text)
        return _SNAPSHOT_AGE.sub("snapshot <AGE>", text)

    return {k: fix(v) if isinstance(v, str) else v for k, v in result.items()}


def compare_repo(repo: Path, plugins: dict[str, Path], work: Path) -> dict[str, str]:
    """The differences between the two sides, by step label."""
    copies = {side: work / "copies" / side / repo.name for side in plugins}
    for copy in copies.values():
        clone_copy(repo, copy)
    diffs: dict[str, str] = {}
    for label, argv, payload in STEPS:
        results = {
            side: normalize(
                run_step(plugins[side], copies[side], argv, payload), copies[side], plugins[side]
            )
            for side in plugins
        }
        base, head = results["base"], results["head"]
        if base == head:
            continue
        lines = [f"  step `{label}`:"]
        for key in ("exit", "stdout", "stderr"):
            if base[key] != head[key]:
                if key == "exit":
                    lines.append(f"    exit {base[key]} -> {head[key]}")
                    continue
                delta = difflib.unified_diff(
                    str(base[key]).splitlines(), str(head[key]).splitlines(),
                    f"base {key}", f"head {key}", lineterm="",
                )
                lines.extend(f"    {line}" for line in delta)
        diffs[label] = "\n".join(lines)
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repos", nargs="*", type=Path, help="repos to sweep (default: siblings)")
    parser.add_argument(
        "--work", type=Path, required=True, help="scratch dir for plugins and copies"
    )
    parser.add_argument("--base", default=None, help="base ref (default: merge-base with develop)")
    parser.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    parser.add_argument("--max-gb", type=float, default=20.0, help="skip repos larger than this")
    parser.add_argument("--keep", action="store_true", help="keep the copies after the sweep")
    args = parser.parse_args()

    base = args.base or _git("merge-base", "develop", args.head)
    refs = {side: _git("rev-parse", "--short", ref) for side, ref in (("base", base), ("head", args.head))}
    if _git("rev-parse", f"{base}:plugin") == _git("rev-parse", f"{args.head}:plugin"):
        print(
            f"base {refs['base']} and head {refs['head']} carry the same plugin tree: the "
            "sweep would compare a plugin with itself. Pass --base and --head (after a merge, "
            "the default base is HEAD).",
            file=sys.stderr,
        )
        return 2
    plugins = {side: export_plugin(ref, args.work / "plugins" / side) for side, ref in refs.items()}
    print(f"base {refs['base']} vs head {refs['head']}, {len(STEPS)} steps per repo")

    repos = [p.resolve() for p in args.repos] or candidate_repos()
    same, differing, skipped = [], {}, {}
    for repo in repos:
        reason = skip_reason(repo, args.max_gb)
        if reason:
            skipped[repo.name] = reason
            print(f"SKIP  {repo.name}: {reason}")
            continue
        try:
            diffs = compare_repo(repo, plugins, args.work)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            skipped[repo.name] = f"could not run: {exc}"
            print(f"SKIP  {repo.name}: could not run: {exc}")
            continue
        finally:
            if not args.keep:
                for side in plugins:
                    shutil.rmtree(args.work / "copies" / side / repo.name, ignore_errors=True)
        if diffs:
            differing[repo.name] = diffs
            print(f"DIFF  {repo.name}")
            for diff in diffs.values():
                print(diff)
        else:
            same.append(repo.name)
            print(f"SAME  {repo.name}")

    print(
        f"\n{len(same)} identical, {len(differing)} differing, {len(skipped)} skipped "
        f"(of {len(repos)} repos; {len(STEPS)} steps each)"
    )
    if differing:
        return 1
    if not same:
        print("nothing was compared, so this run shows nothing either way", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
