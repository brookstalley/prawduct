#!/usr/bin/env python3
"""What would a cumulative review bounded to the delta have given away?

Run:  python3 tools/measure-repeat-cumulative-yield.py REPO [--source ledger|evidence|both]
          [--until 2026-09-22T23:59:59Z] [--json]

Read-only. This is the method behind the bounded-cumulative design's
§ Measured trade (`.prawduct/artifacts/bounded-cumulative-design.md`), kept as a
runnable script so its table can be re-derived instead of transcribed.

For every cumulative review in REPO's governance ledger (and/or the clone's
evidence store), it finds the newest EARLIER cumulative whose reviewed commit is
a strict ancestor of this one's: the review a bounded dispatch would have
started from. It then sorts this review's findings by the files they name:

* **delta**: names a file this review rated (`files_reviewed`) that changed
  since the earlier one. A bounded review would have had it as subject.
* **old_only**: names files, none of them in that delta subject set. A bounded
  review would not have had any of them as subject. Split further, for reading,
  into `changed_not_subject` (changed since the earlier review, but not a
  judgeable subject file: plans, change records), `prior_rated` (the earlier
  review rated it) and `outside` (neither).
* **no_files**: names no file. `files_unrecorded` counts the findings whose
  `files` key is absent rather than empty: the field was not written on early
  facts, so those are "unknown", not "about no file".

A repeat is **same base** when `base_reviewed` matches the earlier review's.
When it does not, and the earlier review's commit is already in the new base,
the earlier review was on a branch since merged: this is a new branch, counted
as **prior_in_base**, which no frontier could bound. The rest are
**base_advanced**: a repeat on one branch whose base moved, which the design runs
as a full span in v1 (Decision 4). For those it reports how many of the branch's
rated files the base advance also touched (Decision 4's v2 question).

For every old-only BLOCKING finding it replays the design's interaction sweep
(§ The interaction sweep, steps 2-3): the identifiers and string literals on the
delta's removed lines that appear nowhere in the delta's changed files at the
reviewed commit, then one `git grep -F` per token over that commit's tree. A
finding is `caught` when one of its files is hit by a token inside the token
budget whose site count is within the per-token cap (past the cap the design
relays "wide reach", not the sites). `caught_uncapped` drops both caps.
`hit_tokens_named_by_finding` keeps the hits whose token the finding's own text
names: a hit through an unrelated word reaches the file, not the defect.
`--phrase-words N` is a variant beyond the design's sweep: it also sweeps every
N-word run inside a removed literal, which survives a doc hard-wrapping the
sentence it quotes.

Choices that reproduce the 2026-09-22 reading, each checked against it:

* The prior must be a STRICT ancestor: a re-review of the very commit an earlier
  cumulative rated looks past it to the newest strictly-older one. Those rows
  are counted as `rereviews`, because the design's frontier condition 4 would
  run them as a full span and their old-only findings are then not losses.
* A row whose commits this clone no longer has (rebased away and pruned) is
  `unresolvable` and dropped, so an older reading can exceed today's.
* One deliberate departure: "changed" is `git diff --no-renames`, so a path the
  delta moved or deleted counts as changed under its old name too. The
  2026-09-22 script used git's default rename folding, so on a renamed path
  this reads one more delta file than that reading did.

What it cannot see: whether a bounded reviewer would have raised an old-only
finding anyway from the oracle, or missed a delta finding that needed the whole
bundle in view. Location is a proxy (design, § Limits of this measure).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

SEVERITIES = ("blocking", "warning", "note")
CLASSES = ("delta", "old_only", "no_files")
DEFAULT_MAX_TOKENS = 200
DEFAULT_MAX_SITES = 25
LEDGER_RELPATH = Path(".prawduct") / ".governance-ledger.jsonl"


# ---------------------------------------------------------------- git (read-only)

class Git:
    """Cached read-only git queries against one repository."""

    def __init__(self, repo: Path):
        self.repo = Path(repo)
        self._ancestors: dict = {}
        self._changed: dict = {}
        self._grep: dict = {}
        self._blobs: dict = {}

    def run(self, *args: str) -> "subprocess.CompletedProcess":
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True, errors="replace")

    def common_dir(self) -> "Path | None":
        out = self.run("rev-parse", "--path-format=absolute", "--git-common-dir")
        return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None

    def ancestors(self, commit: str) -> "set[str] | None":
        """Every commit reachable from ``commit``, itself included; None if absent."""
        if commit not in self._ancestors:
            out = self.run("rev-list", commit, "--")
            self._ancestors[commit] = set(out.stdout.split()) if out.returncode == 0 else None
        return self._ancestors[commit]

    def changed(self, a: str, b: str) -> "set[str] | None":
        key = (a, b)
        if key not in self._changed:
            out = self.run("diff", "--name-only", "--no-renames", "-z", a, b, "--")
            self._changed[key] = ({p for p in out.stdout.split("\0") if p}
                                  if out.returncode == 0 else None)
        return self._changed[key]

    def removed_lines(self, a: str, b: str) -> dict[str, list[str]]:
        out = self.run("diff", "-U0", "--no-renames", "--no-color", "--no-ext-diff", a, b, "--")
        removed: dict[str, list[str]] = collections.defaultdict(list)
        current = None
        for line in out.stdout.splitlines():
            if line.startswith("--- "):
                current = line[6:] if line.startswith("--- a/") else None
            elif line.startswith("-") and not line.startswith("---") and current:
                removed[current].append(line[1:])
        return removed

    def blob(self, commit: str, path: str) -> str:
        key = (commit, path)
        if key not in self._blobs:
            out = self.run("show", f"{commit}:{path}")
            self._blobs[key] = out.stdout if out.returncode == 0 else ""
        return self._blobs[key]

    def grep_files(self, commit: str, token: str) -> list[str]:
        key = (commit, token)
        if key not in self._grep:
            out = self.run("grep", "-F", "-l", "-I", "-e", token, commit, "--")
            prefix = f"{commit}:"
            self._grep[key] = sorted(line[len(prefix):] if line.startswith(prefix) else line
                                     for line in out.stdout.splitlines() if line)
        return self._grep[key]


# ---------------------------------------------------------------- reading

def _iter_json_lines(path: Path):
    """Yield parsed objects, or None for a line that is not a JSON object."""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            yield None
            continue
        yield obj if isinstance(obj, dict) else None


def _is_cumulative(mode) -> bool:
    return isinstance(mode, str) and mode.split(" ")[0] == "cumulative"


def _finding(raw: dict) -> dict:
    files = raw.get("files")
    return {
        "fid": raw.get("fid"),
        "severity": raw.get("severity"),
        "title": raw.get("title") or raw.get("summary") or "",
        "recommendation": raw.get("recommendation") or "",
        "files": [f for f in files if isinstance(f, str)] if isinstance(files, list) else None,
    }


def read_ledger(path: Path) -> tuple[list[dict], int]:
    rows, corrupt = [], 0
    if not path.is_file():
        return rows, corrupt
    for n, event in enumerate(_iter_json_lines(path)):
        if event is None:
            corrupt += 1
            continue
        if event.get("event") != "review.critic":
            continue
        review = event.get("review")
        if not isinstance(review, dict) or not _is_cumulative(review.get("mode")):
            continue
        fact_id = review.get("fact_id")
        rows.append({
            "id": fact_id if isinstance(fact_id, str) else f"ledger:{n}",
            "fact_id": fact_id if isinstance(fact_id, str) else None,
            "source": "ledger",
            "ts": event.get("ts") or "",
            "commit": review.get("commit_reviewed"),
            "base": review.get("base_reviewed"),
            "files_reviewed": [f for f in review.get("files_reviewed") or [] if isinstance(f, str)],
            "findings": [_finding(f) for f in review.get("findings") or [] if isinstance(f, dict)],
        })
    return rows, corrupt


def read_evidence(path: Path) -> tuple[list[dict], int]:
    rows, corrupt = [], 0
    if not path.is_file():
        return rows, corrupt
    for fact in _iter_json_lines(path):
        if fact is None:
            corrupt += 1
            continue
        body = fact.get("body")
        if fact.get("kind") != "review" or not isinstance(body, dict):
            continue
        if not _is_cumulative(body.get("mode")):
            continue
        rows.append({
            "id": fact.get("id"),
            "fact_id": fact.get("id"),
            "source": "evidence",
            "ts": fact.get("ts") or "",
            "commit": body.get("head_commit"),
            "base": body.get("base_reviewed") or body.get("base_commit"),
            "files_reviewed": [f for f in body.get("files_reviewed") or [] if isinstance(f, str)],
            "findings": [_finding(f) for f in body.get("findings") or [] if isinstance(f, dict)],
        })
    return rows, corrupt


def load_rows(repo: Path, git: Git, source: str) -> tuple[list[dict], dict]:
    """Cumulative rows in time order, plus corrupt-line counts per source.

    ``both`` takes every ledger row and adds the evidence facts no ledger row
    carries the id of: a review run in a since-deleted worktree wrote its
    ledger line there, but its fact to the clone-shared store.
    """
    corrupt: dict[str, int] = {}
    rows: list[dict] = []
    if source in ("ledger", "both"):
        ledger_rows, corrupt["ledger"] = read_ledger(repo / LEDGER_RELPATH)
        rows.extend(ledger_rows)
    if source in ("evidence", "both"):
        common = git.common_dir()
        store = common / "prawduct" / "evidence.jsonl" if common else None
        fact_rows, corrupt["evidence"] = read_evidence(store) if store else ([], 0)
        seen = {r["fact_id"] for r in rows if r["fact_id"]}
        rows.extend(r for r in fact_rows if r["fact_id"] not in seen)
    rows.sort(key=lambda r: r["ts"])  # stable: same-second rows keep file order
    return rows, corrupt


# ---------------------------------------------------------------- classification

def classify_finding(files, delta_subject: set, changed: set, prior_rated: set) -> tuple[str, str | None]:
    """(class, old-only sub-bucket) for one finding's ``files``."""
    if not files:
        return "no_files", None
    if any(f in delta_subject for f in files):
        return "delta", None
    if any(f in changed for f in files):
        return "old_only", "changed_not_subject"
    if all(f in prior_rated for f in files):
        return "old_only", "prior_rated"
    return "old_only", "outside"


def _find_prior(rows: list[dict], i: int, ancestors: set) -> tuple[dict | None, bool]:
    """Newest earlier row whose commit is a strict ancestor; and whether an even
    newer earlier row reviewed this very commit."""
    commit = rows[i]["commit"]
    rereview = False
    for prior in reversed(rows[:i]):
        pc = prior["commit"]
        if not pc or pc not in ancestors:
            continue
        if pc == commit:
            rereview = True
            continue
        return prior, rereview
    return None, rereview


def classify(rows: list[dict], git: Git) -> dict:
    repeats, unresolvable = [], 0
    for i, row in enumerate(rows):
        ancestors = git.ancestors(row["commit"]) if isinstance(row["commit"], str) else None
        if ancestors is None:
            unresolvable += 1
            continue
        prior, rereview = _find_prior(rows, i, ancestors)
        if prior is None:
            continue
        changed = git.changed(prior["commit"], row["commit"])
        if changed is None:
            unresolvable += 1
            continue
        subject = set(row["files_reviewed"])
        delta_subject = subject & changed
        prior_rated = set(prior["files_reviewed"])
        classes, buckets = {}, {}
        for n, f in enumerate(row["findings"]):
            key = f["fid"] or f"#{n}"
            classes[key], buckets[key] = classify_finding(f["files"], delta_subject, changed, prior_rated)
        same_base = bool(row["base"]) and row["base"] == prior["base"]
        rec = {
            "id": row["id"], "source": row["source"], "ts": row["ts"],
            "prior": prior["id"], "commit": row["commit"], "prior_commit": prior["commit"],
            "base": row["base"], "prior_base": prior["base"],
            "same_base": same_base, "rereview": rereview,
            "subject_files": len(subject), "delta_files": len(delta_subject),
            "classes": classes, "buckets": buckets, "row": row, "changed": changed,
        }
        base_anc = git.ancestors(row["base"]) if not same_base and row["base"] else None
        # The earlier review's commit is already in this one's base: it was on a
        # branch since merged, and this is a new branch, not a repeat on one.
        rec["prior_in_base"] = bool(base_anc) and prior["commit"] in base_anc
        rec["kind"] = ("same_base" if same_base else
                       "prior_in_base" if rec["prior_in_base"] else "base_advanced")
        if rec["kind"] == "base_advanced" and prior["base"] and row["base"]:
            advance = git.changed(prior["base"], row["base"])
            rec["advance"] = {
                "resolved": advance is not None,
                "forward": bool(base_anc) and prior["base"] in base_anc,
                "overlap": sorted(subject & advance) if advance is not None else None,
                "v2_subject": len(subject & (changed | advance)) if advance is not None else None,
            }
        repeats.append(rec)
    return {"repeats": repeats, "unresolvable": unresolvable}


def _table(repeats: list[dict]) -> dict:
    out = {"repeats": len(repeats),
           "subject_files": sum(r["subject_files"] for r in repeats),
           "delta_files": sum(r["delta_files"] for r in repeats)}
    for sev in SEVERITIES:
        out[sev] = {c: 0 for c in CLASSES}
    old_buckets = collections.Counter()
    for r in repeats:
        for n, f in enumerate(r["row"]["findings"]):
            key = f["fid"] or f"#{n}"
            cls = r["classes"][key]
            if f["severity"] in SEVERITIES:
                out[f["severity"]][cls] += 1
            if cls == "old_only" and f["severity"] == "blocking":
                old_buckets[r["buckets"][key]] += 1
    out["blocking_old_only_by_bucket"] = dict(old_buckets)
    return out


def base_advance_overlap(repeats: list[dict]) -> dict:
    rows = [r for r in repeats if "advance" in r and r["advance"]["resolved"]]
    branch = sum(r["subject_files"] for r in rows)
    overlap = sum(len(r["advance"]["overlap"]) for r in rows)
    return {
        "repeats": len(rows),
        "unresolved": sum(1 for r in repeats if "advance" in r and not r["advance"]["resolved"]),
        "non_forward": sum(1 for r in rows if not r["advance"]["forward"]),
        "branch_files": branch,
        "overlap_files": overlap,
        "overlap_rate": overlap / branch if branch else None,
        "repeats_with_overlap": sum(1 for r in rows if r["advance"]["overlap"]),
        "v2_subject_files": sum(r["advance"]["v2_subject"] for r in rows),
        "v2_transferred_files": sum(r["subject_files"] - r["advance"]["v2_subject"] for r in rows),
    }


# ---------------------------------------------------------------- the sweep replay

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_FLAG = re.compile(r"--[a-z][a-z0-9-]+=?|\b[a-z_][a-z0-9_]*=")
_LITERAL = re.compile(r'"([^"\\\n]{3,120})"|\'([^\'\\\n]{3,120})\'|`([^`\n]{3,120})`')


def line_tokens(line: str, phrase_words: int = 0) -> set[str]:
    """Identifiers, flags and string literals on one line.

    ``phrase_words`` > 0 also yields every run of that many words inside a
    literal. A whole sentence-long literal rarely matches a doc that quotes it,
    because prose is hard-wrapped and `git grep` matches within a line.
    """
    tokens = set()
    for m in _LITERAL.finditer(line):
        text = next(g for g in m.groups() if g is not None).strip()
        if len(text) >= 3:
            tokens.add(text)
        words = text.split()
        if phrase_words and len(words) > phrase_words:
            tokens.update(" ".join(words[i:i + phrase_words])
                          for i in range(len(words) - phrase_words + 1))
    for m in _IDENT.finditer(line):
        if len(m.group(0)) >= 4:
            tokens.add(m.group(0))
    for m in _FLAG.finditer(line):
        if len(m.group(0)) >= 4:
            tokens.add(m.group(0))
    return tokens


def _specificity(token: str) -> tuple:
    """Rank code-shaped tokens before plain words, longer first."""
    code = bool(re.search(r"[_.=\-/:]|[a-z][A-Z]|\d", token)) or " " in token
    return (0 if code else 1, -len(token), token)


def vanished_tokens(git: Git, a: str, b: str, phrase_words: int = 0) -> list[str]:
    """Tokens on the delta's removed lines that no changed file still holds at ``b``."""
    removed = git.removed_lines(a, b)
    candidates = set()
    for lines in removed.values():
        for line in lines:
            candidates |= line_tokens(line, phrase_words)
    if not candidates:
        return []
    texts = [git.blob(b, p) for p in sorted(git.changed(a, b) or ())]
    return sorted((t for t in candidates if not any(t in text for text in texts)), key=_specificity)


def sweep_hits(git: Git, commit: str, tokens: list[str], *, max_tokens: int, max_sites: int) -> dict:
    hits = {}
    for token in tokens[:max_tokens]:
        files = git.grep_files(commit, token)
        wide = len(files) > max_sites
        hits[token] = {"sites": len(files), "wide": wide, "files": [] if wide else files}
    return hits


def replay_sweep(git: Git, rec: dict, finding: dict, *, max_tokens: int, max_sites: int,
                 phrase_words: int = 0) -> dict:
    tokens = vanished_tokens(git, rec["prior_commit"], rec["commit"], phrase_words)
    targets = set(finding["files"] or ())
    capped = sweep_hits(git, rec["commit"], tokens, max_tokens=max_tokens, max_sites=max_sites)
    hit_tokens = sorted(t for t, h in capped.items() if targets & set(h["files"]))
    uncapped = [t for t in tokens if targets & set(git.grep_files(rec["commit"], t))]
    # A hit through a token the finding never mentions (a common word that left
    # the delta) points the reviewer at the file but not at the defect.
    text = f"{finding['title']}\n{finding['recommendation']}"
    return {
        "vanished_tokens": len(tokens),
        "tokens_swept": len(capped),
        "wide_tokens": sum(1 for h in capped.values() if h["wide"]),
        "sites_read": sum(len(h["files"]) for h in capped.values()),
        "caught": bool(hit_tokens),
        "hit_tokens": hit_tokens,
        "hit_tokens_named_by_finding": [t for t in hit_tokens if t in text],
        "caught_uncapped": bool(uncapped),
        "uncapped_hit_tokens": sorted(uncapped, key=_specificity)[:20],
    }


# ---------------------------------------------------------------- driver

def measure(repo: Path, *, source: str = "ledger", since: str | None = None,
            until: str | None = None, sweep: bool = True,
            max_tokens: int = DEFAULT_MAX_TOKENS, max_sites: int = DEFAULT_MAX_SITES,
            phrase_words: int = 0) -> dict:
    repo = Path(repo)
    git = Git(repo)
    rows, corrupt = load_rows(repo, git, source)
    rows = [r for r in rows if (not since or r["ts"] >= since) and (not until or r["ts"] <= until)]
    result = classify(rows, git)
    repeats = result["repeats"]
    unrecorded = sum(1 for r in repeats for f in r["row"]["findings"] if f["files"] is None)

    old_only_blocking = []
    for rec in repeats:
        for n, f in enumerate(rec["row"]["findings"]):
            key = f["fid"] or f"#{n}"
            if f["severity"] != "blocking" or rec["classes"][key] != "old_only":
                continue
            entry = {"id": rec["id"], "fid": f["fid"], "ts": rec["ts"],
                     "kind": rec["kind"], "same_base": rec["same_base"], "rereview": rec["rereview"],
                     "bucket": rec["buckets"][key], "files": f["files"], "title": f["title"]}
            if sweep:
                entry.update(replay_sweep(git, rec, f, max_tokens=max_tokens, max_sites=max_sites,
                                          phrase_words=phrase_words))
            old_only_blocking.append(entry)

    public = [{k: v for k, v in r.items() if k not in ("row", "changed")} for r in repeats]
    return {
        "repo": repo.name,
        "source": source,
        "window": {"since": since, "until": until},
        "corrupt_lines": corrupt,
        "cumulatives": len(rows),
        "unresolvable": result["unresolvable"],
        "rereviews": sum(1 for r in repeats if r["rereview"]),
        "files_unrecorded": unrecorded,
        "tables": {
            "all": _table(repeats),
            "same_base": _table([r for r in repeats if r["kind"] == "same_base"]),
            "base_advanced": _table([r for r in repeats if r["kind"] == "base_advanced"]),
            "prior_in_base": _table([r for r in repeats if r["kind"] == "prior_in_base"]),
        },
        "base_advance": base_advance_overlap(repeats),
        "sweep_caps": ({"max_tokens": max_tokens, "max_sites": max_sites, "phrase_words": phrase_words}
                       if sweep else None),
        "old_only_blocking": old_only_blocking,
        "repeats": public,
    }


def _pct(part, whole) -> str:
    return f"{(part - whole) / whole:+.0%}" if whole else "n/a"


def render(data: dict) -> str:
    out = [f"repo: {data['repo']}   source: {data['source']}   window: "
           f"{data['window']['since'] or '-'} .. {data['window']['until'] or '-'}",
           f"cumulative reviews: {data['cumulatives']}   corrupt lines skipped: {data['corrupt_lines']}   "
           f"unresolvable (commit not in this clone): {data['unresolvable']}",
           f"findings with no `files` recorded: {data['files_unrecorded']}   "
           f"re-reviews of an already-reviewed commit: {data['rereviews']}", ""]
    head = (f"{'':14} {'repeats':>7}  {'subject -> delta files':<24}  "
            f"{'blocking delta/old-only/no-files':<34}  warning delta/old-only/no-files")
    out.append(head)
    for name, label in (("all", "all repeats"), ("same_base", "same base"),
                        ("base_advanced", "base advanced"), ("prior_in_base", "prior in base")):
        t = data["tables"][name]
        files = f"{t['subject_files']} -> {t['delta_files']} ({_pct(t['delta_files'], t['subject_files'])})"
        b, w = t["blocking"], t["warning"]
        out.append(f"{label:14} {t['repeats']:>7}  {files:<24}  "
                   f"{b['delta']:>5} / {b['old_only']:>4} / {b['no_files']:<4}{'':17}  "
                   f"{w['delta']:>5} / {w['old_only']:>4} / {w['no_files']}")
    out.append("")
    out.append("prior in base: the earlier review's commit is already in this one's base, so this is a new")
    out.append("branch, not a repeat a frontier could bound (design condition 2 declines it).")
    out.append(f"blocking old-only by bucket (all repeats): {data['tables']['all']['blocking_old_only_by_bucket']}")
    ba = data["base_advance"]
    rate = f"{ba['overlap_rate']:.1%}" if ba["overlap_rate"] is not None else "n/a"
    out += ["", "Decision 4: base-advanced repeats (the earlier review's commit is not in the new base)",
            f"  repeats: {ba['repeats']} (unresolved base: {ba['unresolved']}, base not a forward move: {ba['non_forward']})",
            f"  branch rated files: {ba['branch_files']}   also touched by the base advance: "
            f"{ba['overlap_files']} ({rate})   repeats with any overlap: {ba['repeats_with_overlap']}",
            f"  v2 per-file split: subject {ba['v2_subject_files']}  transferred {ba['v2_transferred_files']}"]
    if data["old_only_blocking"]:
        caps = data["sweep_caps"]
        out += ["", "Old-only BLOCKING findings" + (
            f" (sweep: {caps['max_tokens']} tokens, {caps['max_sites']} sites per token, "
            f"phrase words {caps['phrase_words'] or 'off'})" if caps else "")]
        for e in data["old_only_blocking"]:
            sweep = ""
            if "caught" in e:
                sweep = (f" sweep={'CAUGHT' if e['caught'] else 'missed'}"
                         f"{' (uncapped: caught)' if e['caught_uncapped'] and not e['caught'] else ''}"
                         f" tokens={e['vanished_tokens']} sites={e['sites_read']}"
                         f" hits={','.join(e['hit_tokens'][:5]) or '-'}"
                         f" named-by-finding={','.join(e['hit_tokens_named_by_finding'][:5]) or '-'}")
            flags = e["kind"] + (" rereview" if e["rereview"] else "")
            out.append(f"- {e['ts'][:10]} {e['id']} {e['fid']} [{flags}; {e['bucket']}]{sweep}")
            out.append(f"    files: {', '.join(e['files'] or [])}")
            out.append(f"    {e['title'][:200]}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", type=Path)
    parser.add_argument("--source", choices=("ledger", "evidence", "both"), default="ledger")
    parser.add_argument("--since", help="ISO timestamp; rows before it are not read")
    parser.add_argument("--until", help="ISO timestamp; rows after it are not read")
    parser.add_argument("--no-sweep", action="store_true", help="skip the Decision 2 replay")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--max-sites", type=int, default=DEFAULT_MAX_SITES)
    parser.add_argument("--phrase-words", type=int, default=0,
                        help="also sweep every N-word run inside a removed literal (0: off, the design's sweep)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = measure(args.repo, source=args.source, since=args.since, until=args.until,
                   sweep=not args.no_sweep, max_tokens=args.max_tokens, max_sites=args.max_sites,
                   phrase_words=args.phrase_words)
    print(json.dumps(data, indent=2) if args.json else render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
