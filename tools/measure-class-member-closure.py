#!/usr/bin/env python3
"""Is a class finding closed at the instance it named, often enough to grade members? (#847)

    tools/measure-class-member-closure.py
    tools/measure-class-member-closure.py --root ~/source --json
    tools/measure-class-member-closure.py --control-scope test-report-scope

Read-only. #847's D2 (a `fixed` resolution must cover every recorded member of
the finding it resolves) changes what a `fixed` claim lifts, so the issue builds
it only if this measurement clears a bar fixed before the data: **(b) of at least
3 per month across the fleet**. D1 and D3 are built regardless.

**Corpus.** Every clone under `--root` holding an evidence store, found by the
property (a `.git/prawduct/evidence.jsonl`) at any depth, not by a path depth.
Worktrees of one clone share that store, so each clone is read once. Facts come
through `lib.evidence.read_facts`, which dedupes within a store; this tool also
dedupes by fact id ACROSS stores, so two clones of one repo count once. Only
review facts stamped at or after `--since` (default 2026-08-04, the era split
#847 names) are read. Output is aggregate only: no repo is ever named.

**Class-framed.** A finding is class-framed when it says so, by any of:
- a recorded `scope: "class"` (D1's field, on facts written after #847);
- a `Scope: class` answer in its text, or a recommendation that opens with
  `class` (the `FINDING_SCOPE_DIRECTIVE` form);
- class vocabulary: `same class`, `this class`, `the class`, `member(s)`,
  `every site`, `closed at the ... site/instance`.
A finding labelled `instance` that nonetheless enumerates several sites is NOT
counted (see "What it cannot see").

**Sites (the members it names).** The `members[].site` values when D1 recorded
them; otherwise what the prose names: every backticked code span, every bare
path-like token, and `files[]`. A site is a **path** when it carries a `/` or
reads as `name.ext` with a file extension; otherwise it is an **identifier** (`ignore_glob`, `::`,
`target.parent.mkdir`). Trailing `:line`, `()` and whitespace are stripped.
Identifiers in `_GENERIC_SPANS` (severity words, `None`, `True`) are not sites.

**(a)** = class-framed findings naming >= 2 distinct sites, as a share of all
class-framed findings.

**(b)** = of (a), how many were followed — in a LATER review fact of the SAME
clone and the SAME `scope` — by a BLOCKING finding whose title,
recommendation or files name one of the sites the class finding listed. A
class finding counts at most once. Scope-less reviews are never matched.

Two readings of (b), and the decision reading was fixed before the data:
- `b_identifier`: matched on identifier sites only. **This is the decision
  figure.** A path match cannot tell the member left unfixed from another
  defect in the same file, and every multi-round branch produces those, so a
  path-inclusive count measures "the branch had another round", not "the
  member was skipped".
- `b_any_site`: matched on any site, paths included. An upper bound, reported
  beside it. If even this is under the bar, the no-go does not depend on the
  choice; if the two straddle the bar the report says so.

**Rate.** Per month = events / (window days / 30.44), the window running from
`--since` to the newest review fact read. Per calendar month (of the class
finding) is printed too.

**Positive control.** `--control-scope NAME` lists the (b) events for that
scope by fact id and fid. #847 names the 2026-09-19 `test-report-scope`
branch: its rounds 3-5 must show a class finding whose listed member a later
round raised BLOCKING (`_write` -> `mkdir`).

What it cannot see: a finding labelled `instance` that enumerates members
(the 2026-09-19 `ignore_glob` divergence was listed under an `instance` label),
so (b) is a floor on the incident shape; a member named in a later finding by a
paraphrase rather than its token; and whether the later finding was CAUSED by
the early closure, rather than coincident with it.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "plugin"))

from lib import evidence  # noqa: E402

#: #847's era split: review facts stamped before it are not read.
DEFAULT_SINCE = "2026-08-04"
#: #847's bar for building D2, fixed on the issue before the data.
BAR_PER_MONTH = 3.0
DAYS_PER_MONTH = 30.44

_SCOPE_LABEL = re.compile(r"\bscope\b\W{0,6}class\b", re.IGNORECASE)
_OPENS_CLASS = re.compile(r"^\W*class\b", re.IGNORECASE)
_CLASS_VOCAB = re.compile(
    r"\b(?:same|this|the) class\b|\bmembers?\b|\bevery site\b"
    r"|\bclosed at the (?:\w+ ){0,3}(?:site|instance)s?\b",
    re.IGNORECASE,
)
_CODE_SPAN = re.compile(r"`([^`\n]{1,200})`")
_BARE_PATH = re.compile(r"(?<![\w/`.-])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z]{1,6}\b")
_LINE_SUFFIX = re.compile(r"(?::\d+(?:-\d+)?)+$")
#: A bare ``name.ext`` is a path only for a file extension. Without the list,
#: a dotted identifier (``os.replace``, ``target.parent.mkdir``) read as a file
#: and fell out of the identifier reading: the positive control caught it.
_FILE_EXTENSIONS = frozenset(
    "py pyi md json jsonl yaml yml toml txt sh bash zsh js mjs cjs ts tsx jsx rs go java kt "
    "swift rb c h cc cpp hpp cs css scss html xml ini cfg conf lock csv sql proto gradle".split()
)
_NAME_DOT_EXT = re.compile(r"^[\w.-]+\.([A-Za-z0-9]{1,6})$")
_GENERIC_SPANS = frozenset({
    "none", "null", "true", "false", "fixed", "waived", "blocking", "warning",
    "note", "class", "instance", "scope", "findings", "resolutions",
})


def _instant(value: object) -> "dt.datetime | None":
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _text(finding: dict) -> str:
    return f"{finding.get('title') or ''}\n{finding.get('recommendation') or ''}"


def is_class_framed(finding: dict) -> bool:
    """The class-framing test the module docstring states."""
    if finding.get("scope") == "class":
        return True
    rec = finding.get("recommendation") or ""
    text = _text(finding)
    return bool(_SCOPE_LABEL.search(text) or _OPENS_CLASS.search(rec) or _CLASS_VOCAB.search(text))


def _normalize(site: str) -> str:
    site = site.strip().removeprefix("./")
    site = _LINE_SUFFIX.sub("", site)
    return site.removesuffix("()").strip()


def is_path(site: str) -> bool:
    if "/" in site:
        return True
    match = _NAME_DOT_EXT.match(site)
    return bool(match) and match.group(1).lower() in _FILE_EXTENSIONS


def is_code_shaped(site: str) -> bool:
    """An identifier site that reads as code, not as a word: it carries one of
    ``_ . ( : - =`` or a capital after its first letter (``ignore_glob``, ``::``,
    ``os.replace``, ``-x``, ``TestTheClassifier``). ``full`` or ``partial`` is a
    value a finding quotes, and matching on it counts vocabulary, not members."""
    return not is_path(site) and bool(re.search(r"[_.(:=-]|.[A-Z]", site))


def is_labelled_class(finding: dict) -> bool:
    """The strict half of :func:`is_class_framed`: the finding ANSWERED `class`
    (a recorded scope, a `Scope: class` label, or a recommendation opening with
    it), not merely used class vocabulary."""
    if finding.get("scope") == "class":
        return True
    return bool(_SCOPE_LABEL.search(_text(finding)) or _OPENS_CLASS.search(finding.get("recommendation") or ""))


def sites_of(finding: dict) -> set[str]:
    """The sites a finding names: D1's recorded members, else what its prose names."""
    members = finding.get("members")
    raw: list[str] = []
    if isinstance(members, list) and members:
        raw = [m.get("site") for m in members if isinstance(m, dict) and isinstance(m.get("site"), str)]
    else:
        text = _text(finding)
        raw.extend(_CODE_SPAN.findall(text))
        raw.extend(_BARE_PATH.findall(_CODE_SPAN.sub(" ", text)))
        raw.extend(f for f in (finding.get("files") or []) if isinstance(f, str))
    out = set()
    for site in raw:
        norm = _normalize(site)
        if len(norm) < 2 or norm.isdigit() or norm.lower() in _GENERIC_SPANS:
            continue
        out.add(norm)
    return out


def _names(later: dict, site: str) -> bool:
    haystack = _text(later) + "\n" + "\n".join(
        f for f in (later.get("files") or []) if isinstance(f, str)
    )
    return site in haystack


def collect(stores: "list[dict]", since: dt.datetime, control_scope: "str | None" = None) -> dict:
    """Tally (a) and (b) over the review facts of ``stores`` (one ``read_facts`` per clone)."""
    seen_ids: set = set()
    per_clone: list[list[tuple[dt.datetime, dict]]] = []
    newest: "dt.datetime | None" = None
    review_facts = findings = 0
    for store in stores:
        rows = []
        for fact in evidence.facts_of_kind(store, "review"):
            fid = fact.get("id")
            ts = _instant(fact.get("ts"))
            if fid in seen_ids or ts is None or ts < since:
                continue
            seen_ids.add(fid)
            rows.append((ts, fact))
            review_facts += 1
            findings += len((fact.get("body") or {}).get("findings") or [])
            newest = ts if newest is None or ts > newest else newest
        per_clone.append(rows)

    class_framed = enumerated = 0
    b_any: collections.Counter = collections.Counter()
    b_ident: collections.Counter = collections.Counter()
    b_strict: collections.Counter = collections.Counter()
    control: list[dict] = []
    for rows in per_clone:
        by_scope: dict = collections.defaultdict(list)
        for order, (ts, fact) in enumerate(rows):
            scope = (fact.get("body") or {}).get("scope")
            if isinstance(scope, str) and scope:
                by_scope[scope].append((order, ts, fact))
        for ts, fact in rows:
            body = fact.get("body") or {}
            scope = body.get("scope")
            for finding in body.get("findings") or []:
                if not isinstance(finding, dict) or not is_class_framed(finding):
                    continue
                class_framed += 1
                sites = sites_of(finding)
                if len(sites) < 2:
                    continue
                enumerated += 1
                if not (isinstance(scope, str) and scope):
                    continue
                month = ts.strftime("%Y-%m")
                labelled = is_labelled_class(finding)
                hit_any = hit_ident = hit_strict = None
                for _order, later_ts, later in by_scope[scope]:
                    if later_ts <= ts or later.get("id") == fact.get("id"):
                        continue
                    for lf in (later.get("body") or {}).get("findings") or []:
                        if not isinstance(lf, dict) or lf.get("severity") != "blocking":
                            continue
                        named = sorted(s for s in sites if _names(lf, s))
                        if not named:
                            continue
                        idents = [s for s in named if not is_path(s)]
                        if hit_any is None:
                            hit_any = (later, lf, named)
                        if idents and hit_ident is None:
                            hit_ident = (later, lf, idents)
                        code = [s for s in idents if is_code_shaped(s)]
                        if labelled and code and hit_strict is None:
                            hit_strict = (later, lf, code)
                if hit_any:
                    b_any[month] += 1
                if hit_ident:
                    b_ident[month] += 1
                if hit_strict:
                    b_strict[month] += 1
                if control_scope is not None and scope == control_scope and (hit_any or hit_ident):
                    hit = hit_ident or hit_any
                    control.append({
                        "class_finding": f"{fact.get('id')}/{finding.get('fid')}",
                        "raised_by": f"{hit[0].get('id')}/{hit[1].get('fid')}",
                        "members_named": hit[2],
                        "identifier_match": hit_ident is not None,
                        "strict_match": hit_strict[2] if hit_strict else None,
                    })
    return {
        "review_facts": review_facts,
        "findings": findings,
        "class_framed": class_framed,
        "enumerated": enumerated,
        "b_any_site": b_any,
        "b_identifier": b_ident,
        "b_strict": b_strict,
        "newest": newest,
        "control": control,
    }


def decide(per_month_identifier: float, per_month_any: float, per_month_strict: float) -> dict:
    """#847's rule: build D2 only if (b) is at least 3 per month across the fleet.
    The identifier reading decides; the decision is robust when the floor
    (``b_strict``) and the ceiling (``b_any_site``) fall on the same side."""
    go = per_month_identifier >= BAR_PER_MONTH
    robust = (per_month_strict >= BAR_PER_MONTH) == go == (per_month_any >= BAR_PER_MONTH)
    outcome = "go: build D2" if go else "no-go: stop at D1 + D3"
    if not robust:
        outcome += " (NOT robust: the floor and ceiling readings fall on different sides of the bar)"
    return {"bar_per_month": BAR_PER_MONTH, "go": go, "robust": robust, "outcome": outcome}


def build_report(stores: "list[dict]", since: dt.datetime, control_scope: "str | None" = None) -> dict:
    tally = collect(stores, since, control_scope)
    newest = tally["newest"] or since
    months = max((newest - since).total_seconds() / 86400, 1.0) / DAYS_PER_MONTH
    total_ident = sum(tally["b_identifier"].values())
    total_any = sum(tally["b_any_site"].values())
    total_strict = sum(tally["b_strict"].values())
    rate_ident = total_ident / months
    rate_any = total_any / months
    report = {
        "clones": len(stores),
        "since": since.date().isoformat(),
        "window_months": round(months, 2),
        "review_facts": tally["review_facts"],
        "findings": tally["findings"],
        "class_framed": tally["class_framed"],
        "a_enumerated": tally["enumerated"],
        "a_share": (tally["enumerated"] / tally["class_framed"]) if tally["class_framed"] else None,
        "b_identifier": total_ident,
        "b_any_site": total_any,
        "b_identifier_per_month": round(rate_ident, 2),
        "b_any_site_per_month": round(rate_any, 2),
        "b_strict": total_strict,
        "b_strict_per_month": round(total_strict / months, 2),
        "by_month": {
            m: {k: tally[k][m] for k in ("b_strict", "b_identifier", "b_any_site")}
            for m in sorted(set(tally["b_identifier"]) | set(tally["b_any_site"]))
        },
        "decision": decide(rate_ident, rate_any, total_strict / months),
    }
    if control_scope is not None:
        report["control"] = {"scope": control_scope, "events": tally["control"]}
    return report


def find_stores(root: Path) -> list[Path]:
    """Every clone under ``root`` with an evidence store, at any depth. A worktree's
    ``.git`` is a file, so each clone is found once, at its main checkout."""
    found = []
    for dirpath, dirnames, _files in os.walk(root):
        if ".git" in dirnames:
            if (Path(dirpath) / ".git" / evidence.STORE_SUBDIR / evidence.STORE_BASENAME).is_file():
                found.append(Path(dirpath))
            dirnames.remove(".git")
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".venv", "venv")]
    return sorted(found)


def _pct(x: "float | None") -> str:
    return "n/a" if x is None else f"{x:.0%}"


def render(report: dict) -> str:
    lines = [
        f"CORPUS  {report['clones']} clones  ·  {report['review_facts']} review facts since "
        f"{report['since']} ({report['window_months']} months)  ·  {report['findings']} findings",
        f"CLASS-FRAMED  {report['class_framed']}",
        f"(a) naming >= 2 sites  {report['a_enumerated']}  ({_pct(report['a_share'])} of class-framed)",
        f"(b) later same-scope BLOCKING naming a listed member",
        f"    floor: labelled class, code-shaped sites  {report['b_strict']}  = {report['b_strict_per_month']}/month",
        f"    identifier sites (decision)  {report['b_identifier']}  = {report['b_identifier_per_month']}/month",
        f"    any site, paths included     {report['b_any_site']}  = {report['b_any_site_per_month']}/month",
    ]
    for month, row in report["by_month"].items():
        lines.append(f"    {month}  floor {row['b_strict']}  identifier {row['b_identifier']}  any {row['b_any_site']}")
    d = report["decision"]
    lines.append(f"DECISION  bar {d['bar_per_month']}/month  ->  {d['outcome']}")
    if "control" in report:
        c = report["control"]
        lines.append(f"CONTROL  scope={c['scope']}  events {len(c['events'])}")
        for e in c["events"]:
            lines.append(f"    {e['class_finding']}  ->  {e['raised_by']}  named {e['members_named']}"
                         f"  floor {e['strict_match']}")
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Measure class findings closed short of their members (#847).")
    parser.add_argument("--root", type=Path, default=Path.home() / "source",
                        help="directory holding the governed clones (default: ~/source)")
    parser.add_argument("--since", default=DEFAULT_SINCE, help=f"ISO date (default {DEFAULT_SINCE})")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip a clone whose directory name is this (repeatable); never printed")
    parser.add_argument("--control-scope", default=None, help="list the (b) events of this scope")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    since = _instant(args.since if "T" in args.since else args.since + "T00:00:00+00:00")
    if since is None:
        sys.exit(f"unparseable --since {args.since!r}")
    repos = [r for r in find_stores(args.root.expanduser()) if r.name not in set(args.exclude)]
    stores = []
    for repo in repos:
        store = evidence.read_facts(repo)
        if store.get("status") == "ok":
            stores.append(store)
    if not stores:
        sys.exit(f"no readable evidence store under {args.root}")
    report = build_report(stores, since, args.control_scope)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
