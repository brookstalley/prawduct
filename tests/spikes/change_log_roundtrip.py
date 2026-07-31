"""Change-log ledger equivalence oracle — the derivation behind the ledger design's spike.

Committed rather than discarded because the figures it produces are counts over a
corpus that grows: every one of them is stale the moment another entry lands.
Prose that transcribes them goes wrong silently (it already did, twice). Run this
instead of citing a number.

    python3 tests/spikes/change_log_roundtrip.py            # working tree
    python3 tests/spikes/change_log_roundtrip.py 4e08a6c    # any git ref

What it answers, in one pass:

  * Can a per-change fact (YAML frontmatter + prose body) round-trip every real
    change-log entry, both structurally (what consumer queries Q1-Q7 read) and
    byte-for-byte (what a `regen-views --check` cutover gate would assert)?
  * How large is the one-time normalization that byte-identity requires, and is
    the key-order set disjoint from the blank-layout set?
  * Do release records reconstruct from the existing tags without partition
    violations?

Not a pytest test: it measures a living corpus, so it has no fixed expected
value to assert. It is a measuring instrument, deliberately kept runnable.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "plugin"))

from lib import views  # noqa: E402

# Canonical rendering order. Not the only order in the corpus — measuring how far
# the corpus departs from it is half this script's job.
TAG_ORDER = ["type", "scope", "chunks", "release", "status"]
H2 = re.compile(r"^## (\d{4}-\d{2}-\d{2}): (.+)$")
TAG = re.compile(r"<!--\s*prawduct:\s*(.+?)\s*-->")


def load(ref: str | None) -> str:
    path = REPO / ".prawduct" / "change-log.md"
    if ref is None:
        return path.read_text()
    out = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{ref}:.prawduct/change-log.md"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def slug(title: str) -> str:
    s = re.sub(r"`([^`]*)`", r"\1", title.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def yaml_scalar(v: str) -> str:
    if v == "" or re.search(r'^[\s`"\'\[\]{}&*!|>%@#]|[:#]\s|\s$', v):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def split_entries(content: str):
    """Yield (entry, raw_block) for every H2 entry, trailing blanks stripped."""
    lines = content.splitlines()
    entries = views.parse_change_log(content)
    starts = sorted(e.line_number - 1 for e in entries)
    for e in entries:
        start = e.line_number - 1
        nxt = [s for s in starts if s > start]
        block = lines[start: nxt[0] if nxt else len(lines)]
        while block and not block[-1].strip():
            block.pop()
        yield e, block


def convert(block: list[str]):
    """Change-log entry -> (fact, release-membership, body, layout).

    `layout` is presentation state (blank counts, observed key order). It is
    NOT part of the proposed fact schema — it exists here only so the oracle can
    separate "the format loses data" from "the format renders it differently."
    """
    m = H2.match(block[0])
    if not m:
        return None
    date, title = m.group(1), m.group(2)

    j, blanks_before = 1, 0
    while j < len(block) and not block[j].strip():
        blanks_before += 1
        j += 1

    tags: dict = {}
    order: list[str] = []
    n_tag_lines = 0
    while j < len(block):
        tm = TAG.search(block[j])
        if not tm:
            break
        for pair in tm.group(1).split("|"):
            k = pair.split("=")[0].strip()
            if k and k not in order:
                order.append(k)
        tags.update(views.parse_tag_line(tm.group(1)))
        n_tag_lines += 1
        j += 1

    blanks_after = 0
    if n_tag_lines:
        while j < len(block) and not block[j].strip():
            blanks_after += 1
            j += 1

    fact = {
        "id": f"{date}-{slug(title)}",
        "date": date,
        "title": title,
        "type": tags.get("type"),
        "scope": tags.get("scope"),
        "chunks": tags.get("chunks"),
    }
    release = {"release": tags.get("release"), "status": tags.get("status")}
    layout = {
        "blanks_before": blanks_before,
        "blanks_after": blanks_after,
        "order": [k for k in order if k in TAG_ORDER],
        "n_tag_lines": n_tag_lines,
    }
    return fact, release, block[j:], layout


def emit(fact: dict, body: list[str]) -> str:
    out = ["---"]
    for k in ("id", "date", "title", "type", "scope", "chunks"):
        v = fact.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            out.append(f"{k}: [" + ", ".join(yaml_scalar(x) for x in v) + "]")
        else:
            out.append(f"{k}: {yaml_scalar(str(v))}")
    return "\n".join(out + ["---"] + body) + "\n"


def reparse(text: str):
    fl = text.split("\n")
    end = fl.index("---", 1)
    fact: dict = {}
    for ln in fl[1:end]:
        k, _, v = ln.partition(": ")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            fact[k] = [x.strip().strip('"') for x in inner.split(",")] if inner else []
        elif v.startswith('"') and v.endswith('"'):
            fact[k] = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        else:
            fact[k] = v
    return fact, fl[end + 1:]


def render(fact: dict, release: dict, body: list[str], layout: dict, order: list[str]) -> list[str]:
    out = [f"## {fact['date']}: {fact['title']}"] + [""] * layout["blanks_before"]
    tags = {
        "type": fact.get("type"),
        "scope": fact.get("scope"),
        "chunks": ",".join(fact["chunks"]) if fact.get("chunks") else None,
        "release": release.get("release"),
        "status": release.get("status"),
    }
    keys = [k for k in order if tags.get(k)] + [
        k for k in TAG_ORDER if tags.get(k) and k not in order
    ]
    if keys:
        out.append("<!-- prawduct: " + " | ".join(f"{k}={tags[k]}" for k in keys) + " -->")
        out += [""] * layout["blanks_after"]
    return out + body


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else None
    content = load(ref)
    label = ref or "working tree"

    n = tagged = struct_ok = pres_ok = canon_ok = 0
    order_bad = layout_bad = both = clean = multi = 0
    lead: Counter = Counter()
    seqs: Counter = Counter()
    releases: Counter = Counter()
    pending = partition_bad = 0
    failures: list[tuple[str, list[str]]] = []

    for entry, block in split_entries(content):
        n += 1
        got = convert(block)
        if got is None:
            continue
        fact, release, body, layout = got

        if layout["n_tag_lines"] == 0:
            r = release.get("release"), release.get("status")
        else:
            tagged += 1
            multi += layout["n_tag_lines"] > 1
            known = layout["order"]
            lead[known[0] if known else "(none)"] += 1
            seqs[tuple(known)] += 1
            ob = known != sorted(known, key=TAG_ORDER.index)
            lb = layout["blanks_after"] != 1
            order_bad += ob
            layout_bad += lb
            both += ob and lb
            clean += not ob and not lb
            rel, st = release.get("release"), release.get("status")
            if rel and st == "shipped":
                releases[rel] += 1
            elif not rel and not st:
                pending += 1
            else:
                partition_bad += 1

        fact2, body2 = reparse(emit(fact, body))
        r_pres = render(fact2, release, body2, layout, layout["order"])
        r_canon = render(fact2, release, body2, layout, TAG_ORDER)
        for r in (r_pres, r_canon):
            while r and not r[-1].strip():
                r.pop()

        pa = views.parse_change_log("\n".join(block) + "\n")[0]
        pb = views.parse_change_log("\n".join(r_pres) + "\n")[0]
        struct_ok += (pa.title, pa.tags) == (pb.title, pb.tags)
        pres_ok += r_pres == block
        canon_ok += r_canon == block
        if r_pres != block and len(failures) < 3:
            failures.append((entry.title[:60], [
                x for x in difflib.unified_diff(block, r_pres, lineterm="", n=0)
                if x.startswith(("+", "-")) and not x.startswith(("+++", "---"))
            ][:6]))

    print(f"change-log @ {label}: {n} entries ({tagged} tagged, {n - tagged} untagged)")
    print()
    print("ROUND-TRIP")
    print(f"  parse_change_log structure identical      : {struct_ok}/{n}")
    print(f"  byte-identical, each entry's own key order: {pres_ok}/{n}")
    print(f"  byte-identical, one canonical key order   : {canon_ok}/{n}")
    for title, diff in failures:
        print(f"    ! {title}")
        for d in diff:
            print(f"      {d[:96]}")
    print()
    print("NORMALIZATION REQUIRED FOR BYTE-IDENTITY")
    print(f"  already canonical (untouched) : {clean}")
    print(f"  non-canonical key order       : {order_bad}")
    print(f"  non-canonical blank layout    : {layout_bad}")
    print(f"  in BOTH sets (overlap)        : {both}")
    print(f"  total touched                 : {order_bad + layout_bad - both}")
    print(f"  closes against tagged total   : "
          f"{clean + order_bad + layout_bad - both} == {tagged} "
          f"{'OK' if clean + order_bad + layout_bad - both == tagged else 'MISMATCH'}")
    print(f"  leading key                   : {dict(lead)}")
    print(f"  distinct key sequences        : {len(seqs)}")
    print(f"  entries with >1 tag line      : {multi}")
    print()
    print("RELEASE RECORDS")
    print(f"  releases reconstructed        : {len(releases)}")
    print(f"  release-pending (statusless)  : {pending}")
    print(f"  partition violations          : {partition_bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
