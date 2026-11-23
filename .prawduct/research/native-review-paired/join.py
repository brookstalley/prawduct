#!/usr/bin/env python3
"""Join the blind verifier's answers to the blind key (#1130, #1197).

Usage:
    python3 -I join.py --key <blind-key.json> --answers <answers-*.json> [<more> ...] \
        --repo <repo> [--repo <repo> ...]

``compare.py --out`` writes ``blind-sheet.json`` (handed to the verifier) and
``blind-key.json`` (kept back). A verifier answers each sheet item by its ``id``.
This script joins the two by that id, never by position, and prints:

* per Critic goal, the verified-real findings: both raised / Critic only /
  native only, with the native share (of all verified-real) beside the
  non-minor native share (the same, over findings the verifier did not mark
  minor);
* per stage (boundary / inner) and per Critic severity the same tallies, and
  how many of the Critic's verified-real findings the native review also raised;
* the re-raise candidates, by instrument.

**Denominator.** Every rate is over the reviews the frozen sheet covers: the
distinct ``review`` ids in the key, not the reviews a live re-load of the repos
would pair now (a review paired after the sheet was cut is not in any rate). The
repos are read only to look up a Critic finding's goal, severity and stage by
(review id, finding id) — ``compare.load_pairs``. A key entry whose review the
repos no longer hold is counted under ``(unknown)`` and named in a warning. A
sheet id with no answer is named and counted in no tally.

**Minor.** A verifier's ``minor`` is per item. For a same-defect item it is true
only if every real finding is minor, so a pair is minor-for-both or not.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare  # noqa: E402

UNKNOWN = "(unknown)"
SEVERITIES = ("blocking", "warning", "observation", "unrated")


def critic_meta(repos: "list[Path]") -> "tuple[dict, dict]":
    """((review id, fid or oid) -> (goal, severity), review id -> stage) over the repos' pairs."""
    meta, stages = {}, {}
    for repo in repos:
        for p in compare.load_pairs(repo.resolve()):
            if p["critic_fact"] is None or p["native_findings"] is None:
                continue
            stages[p["review_id"]] = p["stage"]
            body = p["critic_fact"]["body"]
            for c in body.get("findings") or []:
                meta[(p["review_id"], c.get("fid"))] = (c.get("goal") or compare.NO_GOAL, c.get("severity") or "unrated")
            for o in body.get("observations") or []:
                meta[(p["review_id"], o.get("oid"))] = (o.get("goal") or compare.NO_GOAL, "observation")
    return meta, stages


def _cell():
    return collections.Counter()


def join(key: dict, answers: "list[dict]", meta: dict, stages: dict) -> dict:
    """Tally the answers against the key. Pure: ``meta`` and ``stages`` are inputs."""
    ans = {}
    for a in answers:
        ans[a["id"]] = a  # later files replace earlier ones for an id
    reviews = sorted({k["review"] for k in key.values()})
    out = {
        "reviews": len(reviews),
        "by_stage_reviews": collections.Counter(stages.get(r, UNKNOWN) for r in reviews),
        "answered": sum(1 for i in key if i in ans),
        "items": len(key),
        "missing": sorted(set(key) - set(ans)),
        "extra": sorted(set(ans) - set(key)),
        "unknown_reviews": sorted(r for r in reviews if r not in stages),
        "goal": collections.defaultdict(_cell),
        "stage": collections.defaultdict(_cell),
        "severity": collections.defaultdict(_cell),
        "verdicts": collections.Counter(),
        "reraise": collections.defaultdict(collections.Counter),
    }

    def tally(row_keys, kind, minor):
        """kind: both | critic_only | native_only; minor adds <kind>_minor."""
        for table, rk in row_keys:
            c = out[table][rk]
            c[kind] += 1
            if minor:
                c[kind + "_minor"] += 1

    for vid, k in key.items():
        a = ans.get(vid)
        if a is None:
            continue
        stage = stages.get(k["review"], UNKNOWN)
        if "reraise_by" in k:
            r = out["reraise"][k["reraise_by"]]
            r[f"repeats={a.get('repeats')}"] += 1
            r[f"real={a.get('real')}"] += 1
            continue
        minor = bool(a.get("minor"))
        if "first_source" in k:
            cid = k.get("critic_fid") or k.get("critic_oid")
            cgoal, csev = meta.get((k["review"], cid), (compare.NO_GOAL, "unrated"))
            c_side, n_side = ("first", "second") if k["first_source"] == "critic" else ("second", "first")
            c_real, n_real = a.get(f"{c_side}_real"), a.get(f"{n_side}_real")
            n_goal = a.get(f"{n_side}_goal") or cgoal
            same = a.get("same") == "yes"
            out["verdicts"][f"pair same={a.get('same')}"] += 1
            out["verdicts"][f"critic in pair real={c_real}"] += 1
            out["verdicts"][f"native in pair real={n_real}"] += 1
            if c_real == "yes":
                tally([("severity", csev)], "real", minor)
                if same and n_real == "yes":
                    out["severity"][csev]["also_native"] += 1
            if same and c_real == "yes" and n_real == "yes":
                tally([("goal", cgoal), ("stage", stage)], "both", minor)
            else:
                if c_real == "yes":
                    tally([("goal", cgoal), ("stage", stage)], "critic_only", minor)
                if n_real == "yes":
                    tally([("goal", n_goal), ("stage", stage)], "native_only", minor)
            continue
        src = k["source"]
        out["verdicts"][f"{src} unique real={a.get('real')}"] += 1
        if a.get("real") != "yes":
            continue
        if src == "critic":
            cgoal, csev = meta.get((k["review"], k.get("fid")), (compare.NO_GOAL, "unrated"))
            tally([("goal", cgoal), ("stage", stage)], "critic_only", minor)
            tally([("severity", csev)], "real", minor)
        else:
            tally([("goal", a.get("goal") or compare.NO_GOAL), ("stage", stage)], "native_only", minor)
    return out


def shares(c: collections.Counter) -> "tuple[float, float]":
    """(native share, non-minor native share) of a row's verified-real findings.

    Non-minor drops a finding only when the verifier marked it minor; a row with
    no non-minor finding has share 0."""
    allr = c["both"] + c["critic_only"] + c["native_only"]
    nm_both = c["both"] - c["both_minor"]
    nm_all = nm_both + (c["critic_only"] - c["critic_only_minor"]) + (c["native_only"] - c["native_only_minor"])
    native = (c["both"] + c["native_only"]) / allr if allr else 0.0
    nm_native = (nm_both + c["native_only"] - c["native_only_minor"]) / nm_all if nm_all else 0.0
    return native, nm_native


def render(r: dict) -> str:
    n = r["reviews"] or 1
    lines = [
        f"reviews {r['reviews']} ({dict(r['by_stage_reviews'])}); answered {r['answered']} of {r['items']}; "
        f"missing {r['missing']}; unanswerable ids not in the key {r['extra']}",
    ]
    if r["unknown_reviews"]:
        lines.append(f"WARNING: {len(r['unknown_reviews'])} sheet review(s) not found in the given repos; "
                     f"their Critic findings are under {UNKNOWN}/unrated: {r['unknown_reviews']}")
    lines += ["", "verdicts:"] + [f"  {k}: {v}" for k, v in sorted(r["verdicts"].items())]

    def table(title, rows, per_review=True):
        lines.append("")
        lines.append(title)
        tot = collections.Counter()
        for name in sorted(rows):
            c = rows[name]
            ns, nm = shares(c)
            lines.append(
                f"  {name}: {c['both']} / {c['critic_only']} ({c['critic_only_minor']}) / {c['native_only']} ({c['native_only_minor']})"
                f"  native share {ns:.0%}; non-minor native share {nm:.0%}"
                + (f"; Critic-unique per review {c['critic_only'] / n:.2f}" if per_review else ""))
            tot.update(c)
        ns, nm = shares(tot)
        lines.append(f"  ALL: {tot['both']} / {tot['critic_only']} ({tot['critic_only_minor']}) / {tot['native_only']} "
                     f"({tot['native_only_minor']})  native share {ns:.0%}; non-minor native share {nm:.0%}")

    head = "both / Critic only (minor) / native only (minor)"
    table(f"per goal, verified real — {head}", r["goal"])
    table(f"per stage, verified real — {head}", r["stage"], per_review=False)
    lines += ["", "Critic's verified-real findings by severity — real (minor) / also raised by native (same defect)"]
    for s in SEVERITIES:
        c = r["severity"].get(s)
        if c:
            lines.append(f"  {s}: {c['real']} ({c['real_minor']}) / {c['also_native']}")
    lines += ["", "re-raise candidates, by instrument:"]
    for who, c in sorted(r["reraise"].items()):
        lines.append(f"  {who}: {dict(c)}")
    return "\n".join(lines)


def main(argv: "list[str]") -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--key", type=Path, required=True, help="blind-key.json beside the frozen blind-sheet.json")
    ap.add_argument("--answers", type=Path, nargs="+", required=True, help="the verifiers' answers-*.json files")
    ap.add_argument("--repo", type=Path, action="append", default=[], help="a governed repo (repeatable)")
    args = ap.parse_args(argv)
    key = json.loads(args.key.read_text())
    answers = [a for f in args.answers for a in json.loads(f.read_text())]
    meta, stages = critic_meta(args.repo)
    print(render(join(key, answers, meta, stages)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
