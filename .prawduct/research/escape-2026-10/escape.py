#!/usr/bin/env python3
"""Cross-repo rework metric: how much of each landed change a later landing rewrote.

Research tooling for the 2026-10 governance cost/benefit study, not a plugin feature.

A *landing* is one first-parent commit on the integration branch (a PR merge, or a direct
push). A landing's member commits are everything it brought in, so a fix made inside a PR
before it merged rewrites lines of the same landing and is NOT counted: that is a catch, not
an escape. A *rework edge* is a later landing whose diff modifies or deletes source lines that
`git blame` attributes to an earlier landing, within WINDOW_DAYS. Rework is style-neutral (it
reads diffs, not commit messages); whether an edge was a fix or planned evolution is judged
separately on a sample, because commit-message keywords measure each repo's commit style.

Each landing is bucketed by governance mode:
  none     - the tree has no .prawduct/project-state.yaml
  dormant  - onboarded, but no landing within ACTIVE_DAYS touched .prawduct/
  vX.Y     - onboarded and active; X.Y is the latest prawduct release on that date
             (consumers install with autoUpdate from main)

Usage: escape.py <clones-dir> <out.jsonl> [--branch owner/repo=BRANCH ...]
  Clones are bare, one <owner>_<repo>.git each. Each repo is analysed on develop or its default
  branch. --branch also analyses BRANCH (an integration branch that has not merged yet) and emits
  only its landings the main branch does not already contain, tagged with "branch"; rework is
  traced over BRANCH's whole first-parent history.
"""
import bisect
import datetime as dt
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

WINDOW_DAYS = 30
ACTIVE_DAYS = 7
DAY = 86400

# First release of each minor, from the prawduct repo's tags.
RELEASES = [
    ("2026-06-02", "2.0"), ("2026-06-10", "2.1"), ("2026-06-24", "2.2"), ("2026-07-05", "2.3"),
    ("2026-07-14", "3.0"), ("2026-07-17", "3.1"), ("2026-07-29", "3.2"), ("2026-08-10", "3.3"),
    ("2026-08-19", "3.4"), ("2026-09-12", "3.5"), ("2026-09-20", "3.6"), ("2026-10-02", "3.7"),
]
_REL_TS = [dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp() for d, _ in RELEASES]

SRC_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go", ".rs", ".swift", ".kt", ".java", ".rb",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".sh", ".sql", ".lua", ".php", ".scala", ".m",
    ".mm", ".vue", ".svelte", ".dart", ".ex", ".exs", ".ps1", ".psm1",
}
NON_SRC = re.compile(
    r"(^|/)(tests?|spec|__tests__|fixtures|testdata|docs?|vendor|node_modules|third_party)/"
    r"|(^|/)(test_[^/]*|[^/]*_test\.[a-z]+|[^/]*\.(test|spec)\.[a-z]+|conftest\.py)$"
    r"|^\.(prawduct|claude|github)/"
)
TRIVIAL_LINE = re.compile(r"^\s*($|#|//|/\*|\*|\"\"\"|'''|[{}()\[\];,]+\s*$)")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                          errors="replace", check=True).stdout


def is_src(path):
    return os.path.splitext(path)[1].lower() in SRC_EXT and not NON_SRC.search(path)


def version_at(ts):
    i = bisect.bisect_right(_REL_TS, ts)
    return "1.x" if i == 0 else RELEASES[i - 1][1]


def branch_of(repo):
    head = git(repo, "symbolic-ref", "--short", "HEAD").strip()
    try:
        dev = int(git(repo, "rev-list", "--count", "develop").strip())
        if dev >= int(git(repo, "rev-list", "--count", head).strip()):
            return "develop"
    except subprocess.CalledProcessError:
        pass
    return head


def analyse(repo, branch=None):
    name = os.path.basename(repo).removesuffix(".git").replace("_", "/", 1)
    br = branch or branch_of(repo)
    rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct %P", br).split("\n")
    landings = []
    for r in filter(None, rows):
        sha, ct, *parents = r.split()
        landings.append({"sha": sha, "ts": int(ct), "parents": parents})
    owner = {}  # commit sha -> landing index
    for i, L in enumerate(landings):
        owner[L["sha"]] = i
        if len(L["parents"]) > 1:
            for c in git(repo, "rev-list", f"{L['parents'][0]}..{L['sha']}").split():
                owner.setdefault(c, i)

    onboarded_cache = {}
    for i, L in enumerate(landings):
        p = L["parents"][0] if L["parents"] else None
        names = git(repo, "diff", "--name-only", p, L["sha"]).split("\n") if p else \
            git(repo, "ls-tree", "-r", "--name-only", L["sha"]).split("\n")
        L["touches_prawduct"] = any(n.startswith(".prawduct/") for n in names)
        L["src_files"] = [n for n in names if n and is_src(n)]
        onboarded_cache[i] = bool(git(repo, "ls-tree", L["sha"], ".prawduct/project-state.yaml").strip())

    gov_ts = [L["ts"] for L in landings if L["touches_prawduct"]]
    out = []
    for i, L in enumerate(landings):
        added = 0
        p = L["parents"][0] if L["parents"] else None
        if p and L["src_files"]:
            for line in git(repo, "diff", "--numstat", "-w", p, L["sha"], "--", *L["src_files"]).splitlines():
                a, _, _ = line.split("\t", 2)
                added += int(a) if a.isdigit() else 0
        if not onboarded_cache[i]:
            bucket = "none"
        else:
            j = bisect.bisect_left(gov_ts, L["ts"] - ACTIVE_DAYS * DAY)
            active = j < len(gov_ts) and gov_ts[j] <= L["ts"] + ACTIVE_DAYS * DAY
            bucket = version_at(L["ts"]) if active else "dormant"
        out.append({
            "repo": name, "idx": i, "sha": L["sha"], "ts": L["ts"], "bucket": bucket,
            "merge": len(L["parents"]) > 1, "src_files": len(L["src_files"]), "src_added": added,
            "reworked": {},  # later landing idx -> lines of this landing it rewrote
        })

    # Rework edges: blame every old-side line a later landing changes, at that landing's parent.
    for i, L in enumerate(landings):
        p = L["parents"][0] if L["parents"] else None
        if not p or not L["src_files"]:
            continue
        diff = git(repo, "diff", "-U0", "-w", "--no-renames", p, L["sha"], "--", *L["src_files"])
        ranges, cur = {}, None
        for line in diff.splitlines():
            if line.startswith("--- "):
                cur = line[6:] if line.startswith("--- a/") else None
            elif cur and (m := HUNK.match(line)):
                start, n = int(m.group(1)), int(m.group(2) or 1)
                if n:
                    ranges.setdefault(cur, []).append((start, start + n - 1))
        for path, rs in ranges.items():
            args = ["blame", "--porcelain", "-w"]
            for s, e in rs:
                args += ["-L", f"{s},{e}"]
            try:
                blame = git(repo, *args, p, "--", path)
            except subprocess.CalledProcessError:
                continue
            sha = None
            for bl in blame.splitlines():
                if re.match(r"^[0-9a-f]{40} ", bl):
                    sha = bl.split()[0]
                elif bl.startswith("\t") and sha:
                    if TRIVIAL_LINE.match(bl[1:]):
                        continue
                    k = owner.get(sha)
                    if k is not None and k < i and L["ts"] - landings[k]["ts"] <= WINDOW_DAYS * DAY:
                        d = out[k]["reworked"]
                        d[str(i)] = d.get(str(i), 0) + 1
    if branch:
        on_main = set(git(repo, "rev-list", branch_of(repo)).split())
        out = [dict(r, branch=branch) for r in out if r["sha"] not in on_main]
    for row in out:
        row["reworked"] = [
            {"by": landings[int(j)]["sha"], "lines": n, "gap_h": round((landings[int(j)]["ts"] - row["ts"]) / 3600, 1)}
            for j, n in row["reworked"].items()
        ]
    return out


def main():
    clones, dest, extra = sys.argv[1], sys.argv[2], sys.argv[3:]
    jobs = [(os.path.join(clones, d), None) for d in sorted(os.listdir(clones)) if d.endswith(".git")]
    while extra:
        flag, spec, extra = extra[0], extra[1], extra[2:]
        if flag != "--branch" or "=" not in spec:
            sys.exit(f"unknown argument: {flag} {spec}")
        repo, branch = spec.split("=", 1)
        jobs.append((os.path.join(clones, repo.replace("/", "_", 1) + ".git"), branch))
    with open(dest, "w") as f, ProcessPoolExecutor(max_workers=8) as ex:
        for (repo, _), rows in zip(jobs, ex.map(analyse, *zip(*jobs))):
            for r in rows:
                f.write(json.dumps(r) + "\n")
            print(f"{os.path.basename(repo)}: {len(rows)} landings", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
