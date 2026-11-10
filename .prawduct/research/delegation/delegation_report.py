#!/usr/bin/env python3
"""Report how delegated (subagent) work went, from Claude Code session transcripts.

Research tooling for backlog item #1134, not a plugin feature. The host deletes transcripts
after about 30 days, so run it monthly and keep each run's counts (see README.md).

Input: one or more `--source TRANSCRIPT_DIR` (a Claude Code project directory holding
`<session>.jsonl` files). Each `--source` may be followed by `--repo GIT_REPO` (the repo the
transcripts belong to, for the branch/worktree counts) and any number of `--suite COMMAND`
(a declared suite command, matched as an exact prefix after whitespace normalisation). Subagent
transcripts are read from `<session>/subagents/agent-<id>.jsonl` and from inline sidechain
entries (`isSidechain` with an `agentId`) in the session file.

Output is counts against fixed vocabularies, built from counters only: no transcript string
(prompt, description, path, command, message) is ever passed through to the output. Repos print
as aliases ("repo A", "repo B", ...) unless --names asks for the directory names. Every number is
labelled [measured] (read directly from a record) or [heuristic] (inferred). Wall clock saved
versus serial is not observable and is never claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import string
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
DISPATCH_TOOLS = {"Agent", "Task"}
REVIEWER_TYPES = ("critic-reviewer", "pr-reviewer")
INTEGRATE_RE = re.compile(r"\b(merge|merging|integrat\w*)", re.I)
GOV_CMD_RE = re.compile(
    r"^(?:\S*python3?\s+\S*/)?(?:\S*/)?prawduct-hook\s+"
    r"(?:critic-begin|critic-consolidate|disposition|plan\s+retract)\b"
)
GOV_SKILLS = {"prawduct:critic", "prawduct:pr"}
ROLES = ("reviewer", "research", "build", "integrate", "unclassified")
MODELS = ("opus", "sonnet", "haiku", "other", "none")
RESOLVED = MODELS[:4] + ("not recorded",)

LABEL = {"measured": "[measured]", "heuristic": "[heuristic]"}


def model_family(name: object) -> str:
    s = str(name or "").lower()
    for fam in ("opus", "sonnet", "haiku"):
        if fam in s:
            return fam
    return "other" if s else "none"


def mask_quotes(cmd: str) -> str:
    """Blank out quoted strings and heredoc bodies so a command that only mentions another command
    in text (echo, grep, a commit message) does not look like an invocation."""
    cmd = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?.*?\n\s*\1\b", " ", cmd, flags=re.S)
    return re.sub(r'"[^"]*"|\'[^\']*\'', '""', cmd)


def segments(cmd: str) -> list[str]:
    out = []
    for seg in re.split(r"&&|\|\||;|\n|\|", mask_quotes(cmd)):
        seg = " ".join(seg.split())
        # drop leading env assignments and a leading `cd dir` is already its own segment
        seg = re.sub(r"^(?:\w+=\S*\s+)+", "", seg)
        if seg:
            out.append(seg)
    return out


def norm(s: str) -> str:
    return " ".join(s.split())


def ran_suite(commands: list[str], suites: list[str]) -> bool:
    pats = [norm(s) for s in suites if norm(s)]
    for cmd in commands:
        for seg in segments(cmd):
            if any(seg == p or seg.startswith(p + " ") for p in pats):
                return True
    return False


def ran_governance(commands: list[str], skills: list[str]) -> bool:
    if any(s in GOV_SKILLS for s in skills):
        return True
    return any(GOV_CMD_RE.match(seg) for cmd in commands for seg in segments(cmd))


def parse_ts(s: object) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_jsonl(path: Path) -> list[dict]:
    out = []
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    out.append(d)
    except OSError:
        pass
    return out


def summarise_sub(entries: list[dict]) -> dict:
    """Reduce a sub-transcript to the few facts the report uses. Strings kept here are only
    matched against patterns, never printed."""
    stamps = [t for t in (parse_ts(e.get("timestamp")) for e in entries) if t]
    s = {"wrote": False, "bash": [], "skills": [], "model": None, "tokens": None,
         "first": min(stamps) if stamps else None, "last": max(stamps) if stamps else None}
    seen_usage = False
    tokens = 0
    seen_msgs: set[str] = set()
    for e in entries:
        if e.get("type") != "assistant":
            continue
        m = e.get("message") or {}
        s["model"] = s["model"] or m.get("model")
        u = m.get("usage")
        mid = m.get("id") or e.get("uuid")
        if isinstance(u, dict) and mid not in seen_msgs:
            seen_msgs.add(mid)
            seen_usage = True
            tokens += int(u.get("input_tokens") or 0) + int(u.get("output_tokens") or 0)
        for c in m.get("content") or []:
            if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                continue
            inp = c.get("input") if isinstance(c.get("input"), dict) else {}
            if c.get("name") in WRITE_TOOLS:
                s["wrote"] = True
            elif c.get("name") == "Bash":
                s["bash"].append(str(inp.get("command", "")))
            elif c.get("name") == "Skill":
                s["skills"].append(str(inp.get("skill", "")))
    if seen_usage:
        s["tokens"] = tokens
    return s


def load_source(tdir: Path) -> list[dict]:
    """Return one record per dispatch found in the transcript directory."""
    dispatches: list[dict] = []
    for f in sorted(tdir.glob("*.jsonl")):
        entries = read_jsonl(f)
        by_agent: dict[str, list[dict]] = {}
        for e in entries:
            if e.get("isSidechain") and e.get("agentId"):
                by_agent.setdefault(str(e["agentId"]), []).append(e)
        calls: dict[str, dict] = {}
        sends: Counter = Counter()
        for e in entries:
            if e.get("isSidechain"):
                continue
            if e.get("type") == "assistant":
                m = e.get("message") or {}
                for c in m.get("content") or []:
                    if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                        continue
                    inp = c.get("input") if isinstance(c.get("input"), dict) else {}
                    if c.get("name") in DISPATCH_TOOLS:
                        text = f"{inp.get('description', '')} {str(inp.get('prompt', ''))[:300]}"
                        calls[c.get("id")] = {
                            "ts": parse_ts(e.get("timestamp")),
                            "msg": f"{f.name}:{m.get('id') or e.get('timestamp')}",
                            "type": str(inp.get("subagent_type") or ""),
                            "model": inp.get("model"),
                            "iso": inp.get("isolation"),
                            "bg": bool(inp.get("run_in_background")),
                            "integ_text": bool(INTEGRATE_RE.search(text)),
                            "agent": None,
                        }
                    elif c.get("name") == "SendMessage" and inp.get("to"):
                        sends[str(inp["to"])] += 1
            elif e.get("type") == "user":
                r = e.get("toolUseResult")
                cont = (e.get("message") or {}).get("content")
                if isinstance(r, dict) and isinstance(cont, list):
                    for c in cont:
                        if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                            k = calls[c["tool_use_id"]]
                            k["agent"] = r.get("agentId")
                            k["bg"] = k["bg"] or bool(r.get("background"))
        for k in calls.values():
            sub_entries = []
            if k["agent"]:
                p = f.with_suffix("") / "subagents" / f"agent-{k['agent']}.jsonl"
                sub_entries = read_jsonl(p) if p.exists() else by_agent.get(str(k["agent"]), [])
            k["sub"] = summarise_sub(sub_entries) if sub_entries else None
            k["followups"] = sends.get(str(k["agent"]), 0) if k["agent"] else 0
            dispatches.append(k)
    width = Counter(k["msg"] for k in dispatches)
    for k in dispatches:
        k["width"] = width[k["msg"]]
    return dispatches


def role_of(k: dict) -> str:
    if any(t in k["type"] for t in REVIEWER_TYPES):
        return "reviewer"
    if k["sub"] is None:
        return "unclassified"
    if not k["sub"]["wrote"]:
        return "research"
    return "integrate" if k["integ_text"] else "build"


def in_window(k: dict, since: date | None, until: date | None) -> bool:
    ts = k["ts"]
    if ts is None:
        return since is None and until is None
    d = ts.astimezone(timezone.utc).date()
    return (since is None or d >= since) and (until is None or d <= until)


def pct(vals: list[float], q: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def git_lines(repo: str, *args: str) -> list[str] | None:
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.splitlines() if r.returncode == 0 else None


def git_facts(repo: str, base: str) -> dict:
    allb = git_lines(repo, "branch", "--list", "worktree-agent-*", "--format=%(refname:short)")
    merged = git_lines(repo, "branch", "--list", "worktree-agent-*", "--merged", base, "--format=%(refname:short)")
    wt = git_lines(repo, "worktree", "list", "--porcelain")
    if allb is None or merged is None or wt is None:
        return {"assessed": False}
    left = sum(1 for ln in wt if ln.startswith("branch refs/heads/worktree-agent-"))
    return {"assessed": True, "merged": len(set(merged)), "unmerged": len(set(allb) - set(merged)),
            "worktrees": left}


def summarise(ds: list[dict], suites: list[str]) -> dict:
    """Aggregate dispatch records to counters. Output keys and values are fixed vocabulary or numbers."""
    roles = Counter(role_of(k) for k in ds)
    req = Counter(model_family(k["model"]) if k["model"] else "none" for k in ds)
    res = Counter(model_family(k["sub"]["model"]) if k["sub"] and k["sub"]["model"] else "not recorded" for k in ds)
    iso = Counter("worktree" if k["iso"] == "worktree" else "none" for k in ds)
    mode = Counter("background" if k["bg"] else "foreground" for k in ds)
    fan = Counter(min(k["width"], 4) for k in ds)
    durs = [(k["sub"]["last"] - k["sub"]["first"]).total_seconds() for k in ds
            if k["sub"] and k["sub"]["first"] and k["sub"]["last"]]
    toks = [k["sub"]["tokens"] for k in ds if k["sub"] and k["sub"]["tokens"] is not None]
    subs = [k for k in ds if k["sub"]]
    out = {
        "dispatches": len(ds),
        "with_sub_transcript": len(subs),
        "roles": {r: roles[r] for r in ROLES},
        "model_requested": {m: req[m] for m in MODELS},
        "model_resolved": {m: res[m] for m in RESOLVED},
        "isolation": {"worktree": iso["worktree"], "none": iso["none"]},
        "mode": {"background": mode["background"], "foreground": mode["foreground"]},
        "fan_out_width": {"1": fan[1], "2": fan[2], "3": fan[3], "4+": fan[4]},
        "wall_clock_s": ({"n": len(durs), "median": round(statistics.median(durs), 1),
                          "p90": round(pct(durs, 0.9), 1)} if durs else {"n": 0}),
        "tokens": ({"n": len(toks), "median": int(statistics.median(toks)), "total": sum(toks)}
                   if toks else {"n": 0}),
        "followup_rounds": {"dispatches_with_followup": sum(1 for k in ds if k["followups"]),
                            "messages": sum(k["followups"] for k in ds)},
        "governance_command": sum(1 for k in subs if ran_governance(k["sub"]["bash"], k["sub"]["skills"])),
    }
    out["ran_suite"] = (sum(1 for k in subs if ran_suite(k["sub"]["bash"], suites))
                        if suites else "not assessed")
    return out


def build(args: argparse.Namespace) -> dict:
    since = date.fromisoformat(args.since) if args.since else None
    until = date.fromisoformat(args.until) if args.until else None
    repos = []
    all_ds: list[dict] = []
    all_suites: list[str] = []
    for i, src in enumerate(args.sources):
        ds = [k for k in load_source(Path(src["dir"])) if in_window(k, since, until)]
        all_ds += ds
        all_suites += src["suites"]
        alias = f"repo {string.ascii_uppercase[i % 26]}" + (str(i // 26 + 1) if i >= 26 else "")
        if args.names:
            alias = Path(src["repo"] or src["dir"]).name or alias
        entry = {"repo": alias, **summarise(ds, src["suites"])}
        entry["git"] = git_facts(src["repo"], args.base) if src["repo"] else {"assessed": False}
        repos.append(entry)
    # An overall suite count is only meaningful if every source declared patterns.
    overall_suites = all_suites if all(s["suites"] for s in args.sources) else []
    overall = summarise(all_ds, overall_suites)
    return {"window": {"since": args.since or "unbounded", "until": args.until or "unbounded"},
            "overall": overall, "repos": repos}


def render(rep: dict) -> str:
    M, H = LABEL["measured"], LABEL["heuristic"]
    out = [f"Delegation report, window {rep['window']['since']} .. {rep['window']['until']}",
           "Labels: [measured] read from a record; [heuristic] inferred. Wall clock saved versus "
           "serial is not observable and is not reported.", ""]
    for title, d in [("overall", rep["overall"])] + [(r["repo"], r) for r in rep["repos"]]:
        out.append(f"== {title}")
        out.append(f"dispatches {M}: {d['dispatches']} (with a sub-transcript: {d['with_sub_transcript']})")
        r = d["roles"]
        out.append(f"role, reviewer {M}: {r['reviewer']}")
        out.append(f"role, research/build/integrate {H} (research = no write tool in the sub-transcript; "
                   f"integrate = build whose prompt/description mentions merge/integrat*): "
                   f"{r['research']}/{r['build']}/{r['integrate']}; unclassified (no sub-transcript): {r['unclassified']}")
        out.append(f"model requested {M}: " + ", ".join(f"{k} {v}" for k, v in d["model_requested"].items()))
        out.append(f"model resolved {M}: " + ", ".join(f"{k} {v}" for k, v in d["model_resolved"].items()))
        out.append(f"isolation {M}: worktree {d['isolation']['worktree']}, none {d['isolation']['none']}")
        out.append(f"mode {M}: background {d['mode']['background']}, foreground {d['mode']['foreground']}")
        out.append(f"fan-out width (dispatches per assistant message) {M}: "
                   + ", ".join(f"{k} wide {v}" for k, v in d["fan_out_width"].items()))
        w = d["wall_clock_s"]
        out.append(f"delegate wall clock s (first to last timestamp) {M}: "
                   + (f"n {w['n']}, median {w['median']}, p90 {w['p90']}" if w["n"] else "absent"))
        t = d["tokens"]
        out.append(f"tokens per delegate (input+output) {M}: "
                   + (f"n {t['n']}, median {t['median']}, total {t['total']}" if t["n"] else "usage absent"))
        out.append(f"ran a declared suite command {H}: {d['ran_suite']}")
        out.append(f"ran a governance command {H}: {d['governance_command']}")
        f = d["followup_rounds"]
        out.append(f"follow-up rounds (SendMessage to the agent) {M}: {f['messages']} messages over "
                   f"{f['dispatches_with_followup']} dispatches")
        if "git" in d:
            g = d["git"]
            out.append(f"delegate branches {M}: " + (
                f"merged into base {g['merged']} (includes branches with no commits of their own), "
                f"unmerged {g['unmerged']}, leftover agent worktrees {g['worktrees']}"
                if g["assessed"] else "not assessed (no repo given or git failed)"))
        out.append("")
    return "\n".join(out)


class SourceAction(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        ns.sources.append({"dir": values, "repo": None, "suites": []})


class AttachAction(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        if not ns.sources:
            parser.error(f"{option_string} must follow a --source")
        if option_string == "--repo":
            ns.sources[-1]["repo"] = values
        else:
            ns.sources[-1]["suites"].append(values)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.set_defaults(sources=[])
    ap.add_argument("--source", action=SourceAction, metavar="TRANSCRIPT_DIR", help="a Claude Code project transcript directory (repeatable)")
    ap.add_argument("--repo", action=AttachAction, metavar="GIT_REPO", help="git repo of the preceding --source")
    ap.add_argument("--suite", action=AttachAction, metavar="COMMAND", help="declared suite command of the preceding --source (repeatable)")
    ap.add_argument("--base", default="develop", help="base branch for merged/unmerged (default develop)")
    ap.add_argument("--since", help="YYYY-MM-DD, inclusive (UTC)")
    ap.add_argument("--until", help="YYYY-MM-DD, inclusive (UTC)")
    ap.add_argument("--names", action="store_true", help="print directory names instead of aliases")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.sources:
        ap.error("at least one --source is required")
    rep = build(args)
    print(json.dumps(rep, indent=2) if args.json else render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
