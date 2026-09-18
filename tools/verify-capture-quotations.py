#!/usr/bin/env python3
"""Check every quoted fragment in an MCP mining capture against its source tree.

The derivation behind `.prawduct/artifacts/mcp-mining/capture-quotation-verification.md`,
kept runnable so its numbers are falsifiable. Cite this command, never the digits.

    tools/verify-capture-quotations.py --self-test
    tools/verify-capture-quotations.py cordyceps bankmachine discodon
    tools/verify-capture-quotations.py discodon --show-hits

Why it exists: `hallucinote-verification.md` found 19 of 202 quotations wrong and 1
absent in one capture **with every address clean**. A `PROVENANCE:` line invites a
reader to believe the quote was checked because the address was. The two errors that
mattered drifted *toward the generalisation the corpus wants*, which is why reading
does not catch them — a paraphrase that sharpens a rule reads better than the source.

WHAT THIS INSTRUMENT CANNOT SEE, stated rather than glossed:

* A quotation **stitched** from two non-adjacent sentences with no ellipsis marked
  shows up as a long prefix match. The script narrows the set a human must read; it
  does not empty it. Every miss still has to be opened.
* A fragment shorter than ``--min-length`` is not searched, because short strings
  match everywhere and the verdict would be meaningless. Skipped fragments are
  COUNTED and reported, never silently dropped.
* Normalisation strips markdown emphasis, backticks and smart quotes so a capture's
  formatting does not read as drift. A quotation that differs from its source ONLY in
  emphasis is therefore reported as matching. That is deliberate: the corpus is prose,
  and `**bold**` added around a true sentence is not a false claim.
* It answers *does this string appear in the tree*, not *does it appear at the address
  the PROVENANCE line names*. A quote that matches somewhere else in the repo reads as
  RESOLVED here. Addresses were verified when these captures were written; this pass
  is the half that was not.
* `--show-hits` prints the matching file for each hit; without it only counts are
  reported, and a hit's LOCATION is not checked against the rule's provenance.

Exit 1 if any fragment misses, 2 on a usage or environment error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from dataclasses import dataclass, field as dc_field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAPTURES = REPO / ".prawduct" / "artifacts" / "mcp-mining"

# Each capture's source repo and the commit its provenance header declares. The SHA is
# the point of the exercise: a citation is relative to a commit and worthless without it.
SOURCES: dict[str, dict[str, object]] = {
    "cordyceps": {
        "capture": "cordyceps-server-structured.md",
        "repo": Path.home() / "source" / "cordyceps",
        "shas": ["f07eb79373cd84583a67ae0c6090c931c30ca7a6"],
        # This capture's header flags two gitignored files it cites, which are NOT at
        # the SHA. Searching the working tree as a secondary corpus is what lets a
        # citation to them resolve, labelled, instead of reading as drift.
        "working_tree_fallback": True,
    },
    "bankmachine": {
        "capture": "bankmachine-server-structured.md",
        "repo": Path.home() / "source" / "bankmachine",
        "shas": ["bf83e63329436e1189db1eb5a316ab8760100ffc"],
        "working_tree_fallback": False,
    },
    "discodon": {
        "capture": "discodon-consumer-structured.md",
        "repo": Path.home() / "source" / "discodon",
        # HEAD moved during that read; the header names both ends and says citations
        # were re-checked against the far one. A fragment matching ONLY at the end SHA
        # is reported as such rather than counted clean.
        "shas": [
            "9d54e8f8f6d364f0c4c4c40a36f559ff48c54266",
            "77d104432dfcb8348a6d1ef5755b574ca330a8ed",
        ],
        "working_tree_fallback": False,
    },
}

RULE_MARKER = "**RULE:**"
_FIELD_RE = re.compile(r"^([A-Z][A-Z -]{2,20}):\s*(.*)$")
_ITALIC_QUOTE_RE = re.compile(r'\*"([^"]+)"\*')
_PLAIN_QUOTE_RE = re.compile(r'"([^"]+)"')
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_ELLIPSIS_SPLIT_RE = re.compile(r"\s*(?:\.\.\.|…)\s*")
_EMPHASIS_RE = re.compile(r"[*_`]")
_WS_RE = re.compile(r"\s+")

TEXT_SUFFIXES = {
    ".py", ".cs", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".sh", ".sql", ".html", ".css", ".csproj", ".props", ".xml",
    ".example", ".gitignore", ".j2", ".jinja", ".rst",
}


def normalize(s: str) -> str:
    """Whitespace, case, emphasis and punctuation-insensitive form.

    Emphasis is stripped so a capture's own formatting does not read as drift; see the
    module docstring for why that is deliberate and what it costs.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("‑", "-")
    s = _EMPHASIS_RE.sub("", s)
    s = _WS_RE.sub(" ", s)
    return s.strip().strip(".,;:!?-— ").casefold()


@dataclass
class Fragment:
    source: str
    rule_no: int
    rule_head: str
    field: str
    form: str          # italic-quote | plain-quote | code-span
    raw: str
    norm: str
    verdict: str = ""
    matched_in: str = ""
    hit_path: str = ""
    divergence: str = ""


@dataclass
class Corpus:
    label: str
    blobs: list[tuple[str, str]] = dc_field(default_factory=list)  # (path, normalized text)

    def find(self, needle: str) -> str:
        for path, text in self.blobs:
            if needle in text:
                return path
        return ""

    @property
    def size(self) -> int:
        return sum(len(t) for _, t in self.blobs)


def _is_text(name: str) -> bool:
    p = Path(name)
    return p.suffix.lower() in TEXT_SUFFIXES or p.name in {"Dockerfile", "Makefile"}


def load_tree(repo: Path, sha: str) -> Corpus:
    """Materialise a commit's text files via `git archive` — read-only on the source."""
    corpus = Corpus(label=sha[:12])
    with tempfile.TemporaryDirectory(prefix="capture-audit-") as td:
        proc = subprocess.run(
            ["git", "-C", str(repo), "archive", sha],
            capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise SystemExit(f"error: git archive failed for {repo} {sha}: "
                             f"{proc.stderr.decode('utf-8', 'replace')[:300]}")
        tf = Path(td) / "t.tar"
        tf.write_bytes(proc.stdout)
        with tarfile.open(tf) as tar:
            for member in tar.getmembers():
                if not member.isfile() or not _is_text(member.name):
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                try:
                    corpus.blobs.append((member.name, normalize(fh.read().decode("utf-8"))))
                except UnicodeDecodeError:
                    continue
    return corpus


def load_working_tree(repo: Path) -> Corpus:
    corpus = Corpus(label="working-tree")
    out = subprocess.run(["git", "-C", str(repo), "ls-files"],
                         capture_output=True, text=True, check=False).stdout.split("\n")
    for rel in out:
        if not rel or not _is_text(rel):
            continue
        p = repo / rel
        try:
            corpus.blobs.append((rel, normalize(p.read_text(encoding="utf-8"))))
        except (OSError, UnicodeDecodeError):
            continue
    return corpus


def iter_rule_blocks(text: str):
    """Yield (rule_no, rule_head, {field: text}) for each `**RULE:**` block.

    Fields WRAP across lines — a continuation line belongs to the field above it — and
    quotations are not confined to EVIDENCE. Both were checked against the files rather
    than assumed; a field-per-line reading silently truncates cordyceps' evidence.
    """
    blocks = text.split(RULE_MARKER)[1:]
    for i, block in enumerate(blocks, 1):
        fields: dict[str, list[str]] = {}
        current = "RULE"
        head = ""
        for line in block.splitlines():
            m = _FIELD_RE.match(line)
            if m:
                current = m.group(1)
                fields.setdefault(current, []).append(m.group(2))
            else:
                fields.setdefault(current, []).append(line)
            if current == "RULE" and not head and line.strip():
                head = line.strip()
        yield i, head[:70], {k: " ".join(v).strip() for k, v in fields.items()}


def extract(source: str, capture: Path, min_length: int) -> tuple[list[Fragment], int]:
    frags: list[Fragment] = []
    skipped = 0
    text = capture.read_text(encoding="utf-8")
    for rule_no, head, fields in iter_rule_blocks(text):
        for fname, fvalue in fields.items():
            spans: list[tuple[str, str]] = []
            italics = _ITALIC_QUOTE_RE.findall(fvalue)
            for s in italics:
                spans.append(("italic-quote", s))
            remainder = _ITALIC_QUOTE_RE.sub(" ", fvalue)
            for s in _PLAIN_QUOTE_RE.findall(remainder):
                spans.append(("plain-quote", s))
            for s in _BACKTICK_RE.findall(fvalue):
                # Bare symbols and paths are address-class and were already checked when
                # these captures were written; only multi-token code lines are claims of
                # the same kind as a prose quotation. Reported as a separate class.
                if " " in s.strip():
                    spans.append(("code-span", s))
            for form, raw in spans:
                for piece in _ELLIPSIS_SPLIT_RE.split(raw):
                    norm = normalize(piece)
                    if len(norm) < min_length:
                        skipped += 1
                        continue
                    frags.append(Fragment(source, rule_no, head, fname, form, piece, norm))
    return frags, skipped


def longest_prefix(corpus: Corpus, needle: str) -> int:
    """Longest prefix of `needle` present in the corpus, by binary search."""
    lo, hi = 0, len(needle)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if corpus.find(needle[:mid]):
            lo = mid
        else:
            hi = mid - 1
    return lo


def audit(source: str, min_length: int, show_hits: bool) -> tuple[list[Fragment], int]:
    cfg = SOURCES[source]
    capture = CAPTURES / str(cfg["capture"])
    if not capture.is_file():
        raise SystemExit(f"error: no such capture: {capture}")
    repo = Path(str(cfg["repo"]))
    if not (repo / ".git").exists():
        raise SystemExit(f"error: source repo not found: {repo}")

    frags, skipped = extract(source, capture, min_length)
    corpora = [load_tree(repo, str(s)) for s in cfg["shas"]]  # type: ignore[arg-type]
    if cfg["working_tree_fallback"]:
        corpora.append(load_working_tree(repo))
    if not corpora or not corpora[0].blobs:
        raise SystemExit(f"error: empty corpus for {source} — the search would pass vacuously")

    for f in frags:
        for c in corpora:
            hit = c.find(f.norm)
            if hit:
                f.matched_in = c.label
                f.hit_path = hit
                f.verdict = "RESOLVED" if c is corpora[0] else (
                    "WORKING-TREE-ONLY" if c.label == "working-tree" else "MOVED-IN-WINDOW")
                break
        else:
            n = longest_prefix(corpora[0], f.norm)
            f.verdict = "MISS"
            f.divergence = (f"matched {n}/{len(f.norm)} chars; diverges at: "
                            f"…{f.norm[max(0, n - 30):n]}»»{f.norm[n:n + 40]}")
    return frags, skipped


def counts() -> int:
    """Per capture: what each extraction reads, and what the line-based recipe cannot see.

    `mcp-mining/README.md` recorded the instrument as extracting the `*"..."*` runs. That
    recipe has TWO independent defects and this table shows both:

    * it reads only the italic form, so every plain-quoted fragment is unaudited;
    * run as `grep -oE`, it is LINE-BASED, so a quotation that wraps is invisible — and
      these captures wrap prose at ~95 chars.

    The `grep` column is computed the way the README says to compute it, so the claim
    that it equals the single-line subset is checked here rather than asserted.
    """
    print(f"{'source':12} {'grep -oE':>9} {'single-line':>12} {'WRAPPED':>8} "
          f"{'italic total':>13} {'plain':>7} {'code-span':>10}")
    ok = True
    for source, cfg in SOURCES.items():
        cap = CAPTURES / str(cfg["capture"])
        text = cap.read_text(encoding="utf-8")
        spans = _ITALIC_QUOTE_RE.findall(text)
        # Reproduce the README's line-based recipe exactly.
        grep_n = sum(len(_ITALIC_QUOTE_RE.findall(line)) for line in text.splitlines())
        single = sum(1 for s in spans if "\n" not in s)
        wrapped = len(spans) - single
        frags, _ = extract(source, cap, 25)
        by = {}
        for f in frags:
            by[f.form] = by.get(f.form, 0) + 1
        print(f"{source:12} {grep_n:>9} {single:>12} {wrapped:>8} {len(spans):>13} "
              f"{by.get('plain-quote', 0):>7} {by.get('code-span', 0):>10}")
        if grep_n != single:
            print(f"  FAIL {source}: line-based grep ({grep_n}) != single-line subset ({single})")
            ok = False
        if by.get("plain-quote", 0) == 0:
            print(f"  NOTE {source}: no plain-quote fragments — widening bought nothing here")
    print("\ncheck:", "PASS — the line-based recipe reads exactly the non-wrapping subset"
          if ok else "FAIL")
    return 0 if ok else 1


def self_test() -> int:
    """The three controls, as code that runs rather than prose that claims.

    A scan nobody has falsified has measured nothing. Control 3 is the one the recipe
    recorded in `mcp-mining/README.md` never had: it proves the search DISCRIMINATES,
    not merely that it runs.
    """
    print("self-test: loading a real corpus (bankmachine)…")
    cfg = SOURCES["bankmachine"]
    corpus = load_tree(Path(str(cfg["repo"])), str(cfg["shas"][0]))  # type: ignore[index]
    ok = True

    # Control 0 — the subject is a non-empty SET. A green scan over nothing is not green.
    if corpus.blobs and corpus.size > 100_000:
        print(f"  PASS corpus non-empty: {len(corpus.blobs)} files, {corpus.size:,} chars")
    else:
        print(f"  FAIL corpus too small: {len(corpus.blobs)} files"); ok = False

    # Control 1 — a nonsense string must return zero. The search is not matching everything.
    nonsense = normalize("zzqx wibble frobnicate the quantum albatross of Tuesday")
    if not corpus.find(nonsense):
        print("  PASS nonsense string returns 0 hits")
    else:
        print("  FAIL nonsense string matched — the search matches everything"); ok = False

    # Control 2 — a large known-good set must return hits. The search is not dead.
    frags, _ = extract("bankmachine", CAPTURES / str(cfg["capture"]), 25)
    sample = frags[:120]
    hits = sum(1 for f in sample if corpus.find(f.norm))
    if hits > 0:
        print(f"  PASS known-good set returns hits: {hits}/{len(sample)} of the first sample")
    else:
        print("  FAIL no fragment matched — the search is dead"); ok = False

    # Control 3 — a CORRUPTED real fragment must miss. This is the discriminator.
    matched = next((f for f in sample if corpus.find(f.norm) and len(f.norm.split()) > 6), None)
    if matched is None:
        print("  FAIL no matching multi-word fragment available to corrupt"); ok = False
    else:
        words = matched.norm.split()
        words[len(words) // 2] = "frobnicated"
        corrupted = " ".join(words)
        if not corpus.find(corrupted):
            print(f"  PASS corrupted fragment misses (mutated word {len(words)//2} of {len(words)})")
        else:
            print("  FAIL corrupted fragment still matched — cannot detect drift"); ok = False

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="*", choices=[*SOURCES, []], help="captures to audit")
    ap.add_argument("--self-test", action="store_true", help="run the instrument's controls and exit")
    ap.add_argument("--counts", action="store_true",
                    help="show what each extraction reads, and what the line-based recipe misses")
    ap.add_argument("--min-length", type=int, default=25, help="skip fragments shorter than this (default 25)")
    ap.add_argument("--forms", default="italic-quote,plain-quote",
                    help="comma-separated forms to audit (default: prose quotations only)")
    ap.add_argument("--show-hits", action="store_true", help="print the matching file for each hit")
    args = ap.parse_args(argv[1:])

    if args.self_test:
        return self_test()
    if args.counts:
        return counts()

    sources = args.sources or list(SOURCES)
    wanted = {f.strip() for f in args.forms.split(",") if f.strip()}
    total_miss = 0
    for source in sources:
        frags, skipped = audit(source, args.min_length, args.show_hits)
        sel = [f for f in frags if f.form in wanted]
        by_verdict: dict[str, int] = {}
        for f in sel:
            by_verdict[f.verdict] = by_verdict.get(f.verdict, 0) + 1
        by_form: dict[str, int] = {}
        for f in frags:
            by_form[f.form] = by_form.get(f.form, 0) + 1
        print(f"\n===== {source} =====")
        print(f"  fragments audited {len(sel)} (forms: {sorted(wanted)}); "
              f"skipped under {args.min_length} chars: {skipped}")
        print(f"  all extracted forms: " + " · ".join(f"{k} {v}" for k, v in sorted(by_form.items())))
        print("  verdicts: " + " · ".join(f"{k} {v}" for k, v in sorted(by_verdict.items())))
        for f in sel:
            if f.verdict == "RESOLVED" and not args.show_hits:
                continue
            print(f"  [{f.verdict}] rule {f.rule_no} {f.field} ({f.form})")
            print(f"      quote: {f.raw[:150]}")
            if f.hit_path:
                print(f"      hit:   {f.matched_in}:{f.hit_path}")
            if f.divergence:
                print(f"      {f.divergence}")
        total_miss += by_verdict.get("MISS", 0)
    print(f"\nTOTAL MISSES: {total_miss}")
    return 1 if total_miss else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
