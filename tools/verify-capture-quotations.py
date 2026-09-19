#!/usr/bin/env python3
"""Check every quoted fragment in an MCP mining capture against its source tree.

The derivation behind `.prawduct/artifacts/mcp-mining/capture-quotation-verification.md`,
kept runnable so its numbers are falsifiable. Cite this command, never the digits.

    tools/verify-capture-quotations.py --self-test
    tools/verify-capture-quotations.py cordyceps bankmachine
    tools/verify-capture-quotations.py bankmachine --show-hits

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
* Line-leading comment markers (`///`, `#`, `>`, `--`) are stripped from BOTH sides before
  searching, so a quotation spanning two lines of a docstring resolves. A consequence: text
  that is only adjacent *because* a marker was removed can now be matched as continuous.
* It answers *does this string appear in the tree*, not *does it appear at the address
  the PROVENANCE line names*. A quote that matches somewhere else in the repo reads as
  RESOLVED here. Addresses were verified when these captures were written; this pass
  is the half that was not.
* `--show-hits` prints the matching file for each hit; without it only counts are
  reported, and a hit's LOCATION is not checked against the rule's provenance.
* Only the extensions in `TEXT_SUFFIXES` are searched. A quotation whose source file has
  an extension missing from that allowlist is reported as a miss and reads exactly like
  drift, so the allowlist is a limit on the audit rather than an implementation detail.

Exit codes are distinct on purpose — this instrument's own thesis is that a broken run must be
distinguishable from a run that worked:

* **0** — the audit ran and every selected fragment resolved, or a check passed.
* **1** — the audit ran and some fragment MISSED. A result, not a failure.
* **2** — a usage or environment refusal: nothing was audited (see `PINNED_REFUSALS`).
* **3** — a self-check failed (`--self-test`, `--counts`). The instrument is not trustworthy.
"""

from __future__ import annotations

import argparse
import ast
import os
import contextlib
import io
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import NoReturn

MIN_LENGTH_DEFAULT = 25
"""Shortest normalised fragment worth searching. Below this, a string matches everywhere
and the verdict is meaningless. One home: `--min-length` overrides it, and the controls
and `--counts` read it rather than each carrying a copy."""

#: Where the mined source repositories are checked out. Overridable, because three
#: records stake this audit's falsifiability on "cite the command, never the digits" —
#: and a command a second reader cannot run does not deliver that. `--source-root`, or
#: `MCP_CAPTURE_SOURCE_ROOT`, or this default.
DEFAULT_SOURCE_ROOT = Path.home() / "source"

REPO = Path(__file__).resolve().parent.parent
CAPTURES = REPO / ".prawduct" / "artifacts" / "mcp-mining"

# Each capture's source repo and the commit its provenance header declares. The SHA is
# the point of the exercise: a citation is relative to a commit and worthless without it.
SOURCES: dict[str, dict[str, object]] = {
    "cordyceps": {
        "capture": "cordyceps-server-structured.md",
        "repo_name": "cordyceps",
        "shas": ["f07eb79373cd84583a67ae0c6090c931c30ca7a6"],
        # This capture's header flags two gitignored files it cites, which are NOT at
        # the SHA. Searching the working tree as a secondary corpus is what lets a
        # citation to them resolve, labelled, instead of reading as drift.
        "working_tree_fallback": True,
    },
    "bankmachine": {
        "capture": "bankmachine-server-structured.md",
        "repo_name": "bankmachine",
        "shas": ["bf83e63329436e1189db1eb5a316ab8760100ffc"],
        "working_tree_fallback": False,
    },
}

RULE_MARKER = "**RULE:**"
# LINE-INITIAL only. Splitting on the bare marker also catches it mentioned in prose —
# these captures' headers discuss the marker itself — which shifts every rule id after
# the header and makes citations in the report unresolvable. This regex is the same
# anchor as the corpus's own counting command, `grep -c '^\*\*RULE:\*\*'`, so the ids
# here and the counts recorded in `mcp-mining/README.md` cannot disagree.
_RULE_SPLIT_RE = re.compile(r"^\*\*RULE:\*\*", re.M)
_FIELD_RE = re.compile(r"^([A-Z][A-Z -]{2,20}):\s*(.*)$")
_ITALIC_QUOTE_RE = re.compile(r'\*"([^"]+)"\*')
# Escape-aware: these captures embed JSON (`{\"accountId\": 1}`), and a naive
# `"([^"]+)"` terminates on the BACKSLASH-ESCAPED quote, yielding a truncated fragment
# that ends in `\` and misses on its last character — a truncation that presents as
# tail-rewrite drift rather than as a broken pattern.
_PLAIN_QUOTE_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_ELLIPSIS_SPLIT_RE = re.compile(r"\s*(?:\.\.\.|…)\s*")
_EMPHASIS_RE = re.compile(r"[*_`]")
_WS_RE = re.compile(r"\s+")
# Line-leading comment and continuation markers. A quotation that spans two lines of a
# C# `///` docstring normalises to `…no liveness /// feature` unless these are stripped,
# so the fragment misses on its last word and reads as drift. Measured: this alone
# accounted for most of cordyceps' apparent misses — the captures quote docstrings, and
# a docstring wraps. Stripping can only DELETE characters, so it cannot invent a match
# that the corrupted-fragment control would not still catch.
_LINE_MARKER_RE = re.compile(r"^[ \t]*(?:///?|#+|>+|--(?!-)|<!--|-->)[ \t]*", re.M)

TEXT_SUFFIXES = {
    ".py", ".cs", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".sh", ".sql", ".html", ".css", ".csproj", ".props", ".xml",
    ".example", ".j2", ".jinja", ".rst",
}
"""Text extensions searched. This allowlist is a LIMIT on the audit, not a neutral
detail: a quotation whose source file has an extension missing here is reported as a
miss, and reads exactly like drift. Note the shape trap: `Path('.gitignore').suffix` is
`''`, not `'.gitignore'`, so a dotfile cannot be admitted by adding it to this set.
Extensionless names are matched by NAME in `_is_text`, whose set is `{"Dockerfile",
"Makefile"}`."""

# Derived, not a second hand-maintained copy: a form added to `extract` and not here
# would be unselectable, and two hand-kept copies of one list drift apart silently.
FORM_ITALIC, FORM_PLAIN, FORM_CODE = "italic-quote", "plain-quote", "code-span"
KNOWN_FORMS = frozenset({FORM_ITALIC, FORM_PLAIN, FORM_CODE})

#: Every refusal this module can make. A refusal is what stands between a broken run and a
#: vacuous pass, so an UNPINNED one is the same defect class as an unpinned guard.
#: `--self-test` asserts this roster covers every `die(` site in the file, so adding a
#: refusal without deciding how it is pinned goes red.
PINNED_REFUSALS = (
    "git-archive-failed",       # load_tree: the source commit could not be read
    "no-such-capture",          # audit: the capture file is absent
    "no-source-repo",           # audit: the sibling repo is absent
    "no-corpora",               # audit: nothing to search at all
    "empty-corpus",             # audit: ANY corpus empty, primary or secondary
    "unknown-forms",            # main: --forms names a form that does not exist
    "vacuous-selection",        # main: the run would audit zero fragments
)
PROSE_FORMS = (FORM_ITALIC, FORM_PLAIN)


def die(message: str, code: int = 2) -> NoReturn:
    """Environment/usage failure. Exit 2, distinct from 1 (a real miss result).

    `raise SystemExit("...")` prints the string but exits **1**, which is the code a
    genuine miss uses — a broken run must not be indistinguishable from a run that
    worked and found drift. The distinction matters most for the vacuous-corpus guard,
    whose whole job is to refuse a pass nothing was searched for.
    """
    print(message, file=sys.stderr)
    raise SystemExit(code)


def normalize(s: str) -> str:
    """Whitespace, case, emphasis and punctuation-insensitive form.

    Emphasis is stripped so a capture's own formatting does not read as drift; see the
    module docstring for why that is deliberate and what it costs.
    """
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("‑", "-")
    s = s.replace('\\"', '"').replace("\\'", "'")
    s = _LINE_MARKER_RE.sub("", s)
    s = _EMPHASIS_RE.sub("", s)
    s = _WS_RE.sub(" ", s)
    return s.strip().strip(".,;:!?-— ()[]{}'\"\\").casefold()


@dataclass
class Fragment:
    source: str
    rule_no: int
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
    #: Files skipped for decode/IO reasons. NOT cosmetic: a source file that failed to
    #: load makes every quotation from it read as drift, so the count is reported.
    dropped: list[str] = dc_field(default_factory=list)

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
            die(f"error: git archive failed for {repo} {sha}: "  # refusal: git-archive-failed
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
                    corpus.dropped.append(member.name)
    return corpus


def load_working_tree(repo: Path) -> Corpus:
    """Working-tree corpus INCLUDING gitignored files — which is the only reason it exists.

    `git ls-files` lists TRACKED files only, so the fallback added for cordyceps' two
    flagged gitignored citations could never see them: those citations landed in the
    "not in the tree at all" bucket, indistinguishable from drift. `--cached --others`
    lists tracked plus every untracked file, ignored ones included (`--exclude-standard`
    is deliberately NOT passed — it is what would filter them back out).
    """
    corpus = Corpus(label="working-tree")
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "--cached", "--others"],
                         capture_output=True, text=True, check=False).stdout.split("\n")
    for rel in out:
        if not rel or not _is_text(rel):
            continue
        p = repo / rel
        try:
            corpus.blobs.append((rel, normalize(p.read_text(encoding="utf-8"))))
        except (OSError, UnicodeDecodeError):
            corpus.dropped.append(rel)
    return corpus


def iter_rule_blocks(text: str):
    """Yield (rule_no, {field: text}) for each `**RULE:**` block.

    Fields WRAP across lines — a continuation line belongs to the field above it — and
    quotations are not confined to EVIDENCE. A field-per-line reading silently truncates
    any evidence field that wraps, which cordyceps' routinely do.
    """
    blocks = _RULE_SPLIT_RE.split(text)[1:]
    for i, block in enumerate(blocks, 1):
        fields: dict[str, list[str]] = {}
        current = "RULE"
        for line in block.splitlines():
            m = _FIELD_RE.match(line)
            if m:
                current = m.group(1)
                fields.setdefault(current, []).append(m.group(2))
            else:
                fields.setdefault(current, []).append(line)
        yield i, {k: " ".join(v).strip() for k, v in fields.items()}


def extract(source: str, capture: Path, min_length: int) -> tuple[list[Fragment], int]:
    return extract_from_text(source, capture.read_text(encoding="utf-8"), min_length)


def extract_from_text(source: str, text: str, min_length: int) -> tuple[list[Fragment], int]:
    """Extraction proper, on TEXT — so a control can pin it against an inline fixture.

    Three of this instrument's five known defects lived HERE, in the extractor, while
    every search-side control stayed green: the non-escape-aware quote regex, the
    line-based reading that missed wrapped quotations, and the rule split that counted a
    marker discussed in prose. A guard with no control is one a later edit deletes
    silently, so `--self-test` exercises this function directly.
    """
    frags: list[Fragment] = []
    skipped = 0
    for rule_no, fields in iter_rule_blocks(text):
        for fname, fvalue in fields.items():
            spans: list[tuple[str, str]] = []
            italics = _ITALIC_QUOTE_RE.findall(fvalue)
            for s in italics:
                spans.append((FORM_ITALIC, s))
            remainder = _ITALIC_QUOTE_RE.sub(" ", fvalue)
            for s in _PLAIN_QUOTE_RE.findall(remainder):
                spans.append((FORM_PLAIN, s))
            for s in _BACKTICK_RE.findall(fvalue):
                # Bare symbols and paths are address-class and were already checked when
                # these captures were written; only multi-token code lines are claims of
                # the same kind as a prose quotation. Reported as a separate class.
                if " " in s.strip():
                    spans.append((FORM_CODE, s))
            for form, raw in spans:
                for piece in _ELLIPSIS_SPLIT_RE.split(raw):
                    norm = normalize(piece)
                    if len(norm) < min_length:
                        skipped += 1
                        continue
                    frags.append(Fragment(source, rule_no, fname, form, piece, norm))
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


def audit(source: str, min_length: int = MIN_LENGTH_DEFAULT,
          _corpora_out: list | None = None,
          source_root: Path = DEFAULT_SOURCE_ROOT) -> tuple[list[Fragment], int]:
    cfg = SOURCES[source]
    capture = CAPTURES / str(cfg["capture"])
    if not capture.is_file():
        die(f"error: no such capture: {capture}")  # refusal: no-such-capture
    repo = source_root / str(cfg["repo_name"])
    if not (repo / ".git").exists():
        die(f"error: source repo not found: {repo}. This audit reads the mined source "  # refusal: no-source-repo
            f"repositories from {source_root}; point --source-root (or "
            f"MCP_CAPTURE_SOURCE_ROOT) at the directory holding your clones.")

    frags, skipped = extract(source, capture, min_length)
    corpora = [load_tree(repo, str(s)) for s in cfg["shas"]]  # type: ignore[arg-type]
    if cfg["working_tree_fallback"]:
        corpora.append(load_working_tree(repo))
    # Every corpus, not just the first. A silently-empty SECONDARY corpus (cordyceps'
    # working tree, or a capture's end-of-read SHA) cannot be distinguished from "nothing matched
    # there", so it degrades a verdict without ever failing.
    if not corpora:
        die(f"error: no corpus for {source} — the search would pass vacuously")  # refusal: no-corpora
    for c in corpora:
        if not c.blobs:
            die(f"error: empty corpus '{c.label}' for {source} — "  # refusal: empty-corpus
                f"the search against it would pass vacuously")

    if _corpora_out is not None:
        _corpora_out.extend(corpora)
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


def line_based_reads_non_wrapping(text: str) -> tuple[int, int, int]:
    """(line-based count, single-line spans, wrapped spans) for one capture's text.

    Factored out of :func:`counts` so a control can drive it with a synthetic input and
    check it distinguishes a wrapped span from a non-wrapping one — which is the property
    the whole line-based/wrapped distinction rests on.
    """
    spans = _ITALIC_QUOTE_RE.findall(text)
    grep_n = sum(len(_ITALIC_QUOTE_RE.findall(line)) for line in text.splitlines())
    single = sum(1 for s in spans if "\n" not in s)
    return grep_n, single, len(spans) - single


def dropped_warnings(corpora: "list[Corpus]") -> list[str]:
    """One warning line per corpus that could not read some of its files.

    Factored out of :func:`main` for the same reason: a source file that failed to load
    makes every quotation from it read as drift, so the report is load-bearing and needs
    a control that can drive it.
    """
    lines: list[str] = []
    for c in corpora:
        if c.dropped:
            names = ", ".join(c.dropped[:4]) + (" …" if len(c.dropped) > 4 else "")
            lines.append(f"  WARNING corpus {c.label}: {len(c.dropped)} file(s) unreadable "
                         f"and NOT searched — quotations from them will read as misses: {names}")
    return lines


def counts(min_length: int = MIN_LENGTH_DEFAULT) -> int:
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
        grep_n, single, wrapped = line_based_reads_non_wrapping(text)
        # single + wrapped IS the span total by definition. Do not reconstruct it from
        # `grep_n`: that agrees only while grep_n == single, which is every state except
        # the one the FAIL branch below exists to report — so such a column would be
        # wrong precisely where it is being read.
        spans_total = single + wrapped
        frags, _ = extract(source, cap, min_length)
        by = {}
        for f in frags:
            by[f.form] = by.get(f.form, 0) + 1
        print(f"{source:12} {grep_n:>9} {single:>12} {wrapped:>8} {spans_total:>13} "
              f"{by.get('plain-quote', 0):>7} {by.get('code-span', 0):>10}")
        if grep_n != single:
            # Under today's `_ITALIC_QUOTE_RE` this cannot fire: `[^"]+` crosses newlines,
            # so a per-line scan finds exactly the non-wrapping spans. It is a guard
            # against a future regex change that would break that equivalence, not a
            # condition this corpus can reach — stated so the green is not read as a
            # measurement.
            print(f"  FAIL {source}: line-based grep ({grep_n}) != single-line subset ({single})")
            ok = False
        if by.get("plain-quote", 0) == 0:
            print(f"  NOTE {source}: no plain-quote fragments — widening bought nothing here")
    print("\ncheck:", "PASS — the line-based recipe reads exactly the non-wrapping subset"
          if ok else "FAIL")
    return 0 if ok else 3


def self_test(min_length: int = MIN_LENGTH_DEFAULT,
              source_root: Path = DEFAULT_SOURCE_ROOT) -> int:
    """Every control, as code that runs rather than prose that claims.

    A scan nobody has falsified has measured nothing. Control 3 is the one the recipe
    recorded in `mcp-mining/README.md` never had: it proves the search DISCRIMINATES,
    rather than merely that it runs. From Control 4 onward each one pins a specific guard,
    because a guard with no control is one a later edit deletes silently. Stated
    relationally because the list keeps growing and a range here would go stale first.

    No count is stated here on purpose: the list grows, and a number in this docstring
    would be the first thing to go stale.
    """
    def _refuses(call, marker: str, what: str) -> bool:
        """True iff `call` refuses with exit 2 AND the refusal is the one named.

        Asserting the exit CODE alone is not enough: every refusal in this module exits
        2, so a control whose fixture never reaches its subject catches an unrelated
        refusal — a missing source repo, say — and prints PASS. That is the
        environment-shaped hole, and it is what this helper exists to close.
        """
        buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(buf):
                call()
        except SystemExit as exc:
            text = buf.getvalue()
            if exc.code != 2:
                print(f"  FAIL {what} exited {exc.code}, want 2"); return False
            if marker not in text:
                print(f"  FAIL {what} refused, but NOT on its own subject — got: "
                      f"{text.strip()[:110]}"); return False
            print(f"  PASS {what} refuses the run (exit 2, on its own subject)")
            return True
        print(f"  FAIL {what} did not refuse at all"); return False

    print("self-test: loading a real corpus (bankmachine)…")
    cfg = SOURCES["bankmachine"]
    corpus = load_tree(source_root / str(cfg["repo_name"]), str(cfg["shas"][0]))  # type: ignore[index]
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
    frags, _ = extract("bankmachine", CAPTURES / str(cfg["capture"]), min_length)
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

    # Control 4 — rule ids must agree with the corpus's own counting command, or every
    # citation this instrument emits points at the wrong rule. Splitting on the bare
    # marker instead of a line-initial one shifted ids past each capture's header, which
    # is invisible in the output and fatal in a durable record.
    for source, source_cfg in SOURCES.items():
        cap = CAPTURES / str(source_cfg["capture"])
        body = cap.read_text(encoding="utf-8")
        n = len(list(iter_rule_blocks(body)))
        canon = sum(1 for line in body.splitlines() if line.startswith(RULE_MARKER))
        if n == canon:
            print(f"  PASS {source} rule ids reconcile with grep -c '^**RULE:**' ({n})")
        else:
            print(f"  FAIL {source} rule-block count {n} != canonical {canon}"); ok = False

    # Control 5 — the working-tree fallback must actually SEE gitignored files, which is
    # its only reason to exist. `git ls-files` alone lists only TRACKED files, under which
    # the citations this fallback exists for land in "not in the tree at all" and read
    # like drift. A silently-empty secondary corpus degrades a verdict without failing.
    cordy = SOURCES["cordyceps"]
    repo = source_root / str(cordy["repo_name"])
    wt = load_working_tree(repo)
    ignored = repo / ".prawduct" / "reflections.md"
    if not wt.blobs:
        print("  FAIL working-tree corpus is empty"); ok = False
    elif not ignored.is_file():
        # A SKIP is indistinguishable from a PASS in a summary, so this FAILS. The probe
        # file is gitignored, which is the property under test — if it is absent, the
        # control cannot reach its subject and must say so rather than stay quiet.
        print(f"  FAIL working-tree fallback control cannot reach its subject: "
              f"{ignored} is absent, so the gitignored-visibility claim is untested")
        ok = False
    elif not [l for l in ignored.read_text(encoding="utf-8").splitlines()
              if len(l.strip()) > 80]:
        print(f"  FAIL {ignored} has no line over 80 chars to probe with")
        ok = False
    else:
        long_lines = [l.strip() for l in ignored.read_text(encoding="utf-8").splitlines()
                      if len(l.strip()) > 80]
        probe = normalize(long_lines[len(long_lines) // 2])[:90]
        at_sha = load_tree(repo, str(cordy["shas"][0]))  # type: ignore[index]
        if wt.find(probe) and not at_sha.find(probe):
            print(f"  PASS working-tree fallback sees gitignored files "
                  f"({len(wt.blobs)} files; probe absent at the SHA, as it must be)")
        else:
            print("  FAIL working-tree fallback cannot see the gitignored files it exists for")
            ok = False

    # Control 6 — the every-corpus non-empty guard, BOTH halves, as separate cases.
    # They must be separate: emptying `load_tree` also empties `corpora[0]`, so a single
    # case built that way is satisfied by the weaker `if not corpora[0].blobs` check and
    # cannot tell it from the every-corpus loop it is meant to pin. Only emptying a
    # SECONDARY corpus discriminates the two.
    for label, target in (("primary", "load_tree"), ("secondary", "load_working_tree")):
        real = globals()[target]
        try:
            globals()[target] = (lambda repo, sha=None, _l=label:
                                 Corpus(label=f"{_l}-emptied"))
            if not _refuses(lambda: audit("cordyceps", source_root=source_root),
                            "empty corpus", f"an empty {label} corpus"):
                ok = False
        finally:
            globals()[target] = real

    # Control 7 — `die` exits 2, distinct from 1 (a genuine miss result). The whole point
    # of the code split is that a broken run is distinguishable from a run that worked.
    try:
        die("control: expected")
        print("  FAIL die() returned instead of exiting"); ok = False
    except SystemExit as exc:
        if exc.code == 2:
            print("  PASS die() exits 2, distinct from a miss result's 1")
        else:
            print(f"  FAIL die() exited {exc.code}, want 2"); ok = False

    # Control 8 — KNOWN_FORMS must cover exactly what `extract` emits. A form the
    # extractor produces but the selector rejects is unauditable and silently so.
    emitted_frags, _ = extract("cordyceps",
                               CAPTURES / str(SOURCES["cordyceps"]["capture"]),
                               min_length)
    emitted = {f.form for f in emitted_frags}
    if emitted and emitted <= KNOWN_FORMS:
        print(f"  PASS every emitted form is selectable ({len(emitted)} forms)")
    else:
        print(f"  FAIL forms emitted but not selectable: {sorted(emitted - KNOWN_FORMS)}")
        ok = False

    # Control 9 — the EXTRACTOR, pinned against an inline fixture. Controls 0-8 all target
    # the SEARCH, yet three of this instrument's five known defects lived in extraction and
    # left every search-side control green. This fixture carries one of each: a quotation
    # that WRAPS a line (the field-join), an embedded JSON sample with ESCAPED quotes (the
    # escape-aware regex), and the rule marker discussed IN PROSE (the line-anchored split).
    fixture = (
        "Header prose that mentions the **RULE:** marker mid-sentence.\n"
        "\n"
        "**RULE:** A rule whose evidence wraps.\n"
        "FIRE-SITE: somewhere.\n"
        "LAYER: L1\n"
        "KIND: pattern\n"
        'EVIDENCE: measured — *"a quotation that wraps across\n'
        'two lines of the capture"* and a sample "{\\"accountId\\": 1, \\"since\\": null}" and\n'
        '"a plain quotation long enough to survive the length floor".\n'
        "PROVENANCE: `x.py` `sym`\n"
    )
    blocks = list(iter_rule_blocks(fixture))
    fx, _ = extract_from_text("fixture", fixture, min_length)
    got = {f.raw for f in fx}
    # The field join collapses the wrap to a space — that IS the join's behaviour, and
    # pinning the joined form is what makes removing the join go red.
    wrapped = "a quotation that wraps across two lines of the capture"
    json_frag = '{\\"accountId\\": 1, \\"since\\": null}'
    plain = "a plain quotation long enough to survive the length floor"
    problems = []
    if len(blocks) != 1:
        problems.append(f"rule split saw {len(blocks)} blocks, want 1 "
                        f"(a marker in prose must not split)")
    if wrapped not in got:
        problems.append("the wrapped italic quotation was not extracted whole "
                        "(the cross-line field join)")
    if json_frag not in got:
        problems.append("the escaped-quote JSON sample was not extracted whole "
                        "(the escape-aware quote regex)")
    if plain not in got:
        problems.append("the plain quotation was not extracted")
    if problems:
        for pr in problems:
            print(f"  FAIL extractor: {pr}")
        ok = False
    else:
        print(f"  PASS extractor pins wrap-join, escaped quotes and the prose marker "
              f"({len(fx)} fragments from the fixture)")

    # Control 10 — main()'s two refusals, each of which prevents a vacuous pass: an
    # unknown `--forms` value, and a selection that would audit nothing.
    root_args = ["--source-root", str(source_root)]
    for argv, marker, what in (
        (["x", *root_args, "--forms", "no-such-form", "cordyceps"],
         "unknown --forms", "unknown --forms"),
        (["x", *root_args, "--forms", FORM_ITALIC, "--min-length", "100000", "cordyceps"],
         "0 fragments selected", "a selection that audits nothing"),
    ):
        # The vacuous-selection refusal fires after the audit runs, so its ordinary
        # report would land in the middle of the control output. Swallow it.
        def _run(a=argv):
            with contextlib.redirect_stdout(io.StringIO()):
                main(a)
        if not _refuses(_run, marker, what):
            ok = False

    # Control 11 — the roster covers every refusal the module can make. A `die()` added
    # without a decision about how it is pinned is the unpinned-guard class, and this is
    # the construction that catches it rather than a list somebody remembers to extend.
    # Compares NAMED IDS, not a count: a count is satisfied by any seven refusals, so it
    # could not tell a renamed or replaced one from the roster it claims to cover. Each
    # production `die()` carries a `# refusal: <id>` tag and the two sets must be equal.
    source_text = Path(__file__).read_text(encoding="utf-8")
    tagged = set(re.findall(r"#\s*refusal:\s*([a-z0-9-]+)", source_text))
    tree = ast.parse(source_text)
    # Scope: PRODUCTION refusals. `self_test` calls `die()` itself to pin the exit-2
    # contract, and counting that would make the roster grow with its own controls.
    production = [n for n in tree.body
                  if not (isinstance(n, ast.FunctionDef) and n.name == "self_test")]
    die_sites = sum(
        1 for top in production for node in ast.walk(top)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "die"
    )
    roster = set(PINNED_REFUSALS)
    if tagged == roster and die_sites == len(roster):
        print(f"  PASS every refusal is tagged and on the roster ({sorted(roster)[0]} …, "
              f"{len(roster)} ids)")
    else:
        if tagged != roster:
            print(f"  FAIL roster/tag mismatch — only on roster: "
                  f"{sorted(roster - tagged)}; only tagged: {sorted(tagged - roster)}")
        if die_sites != len(roster):
            print(f"  FAIL {die_sites} die() site(s) vs {len(roster)} roster ids — a "
                  f"refusal was added without deciding how it is pinned")
        ok = False

    # Control 12 — the two FAIL emitters, which a die()-only roster cannot reach. A
    # refusal and a FAIL are both ways this instrument reports it cannot be trusted, so
    # both halves need pinning.
    wrapped_fixture = 'a *"one line"* and *"a quotation that\nwraps"* here'
    grep_n, single, wrapped = line_based_reads_non_wrapping(wrapped_fixture)
    # Exactly two conjuncts, each independently falsifiable: a wrapped span exists, and
    # the line scan does not count it. Deliberately no third comparing span totals —
    # given these two, any such clause is implied and so can never fail, and a conjunct
    # no input can falsify reads as coverage while providing none. The span-total
    # formulas cannot be discriminated by any input either (`grep_n == single` holds by
    # construction under today's regex — see the note in `counts`).
    if wrapped >= 1 and grep_n == single:
        print(f"  PASS the line-based check sees a wrapped span it cannot count "
              f"(grep {grep_n}, wrapped {wrapped})")
    else:
        print(f"  FAIL line-based check did not detect the wrap "
              f"(grep {grep_n}, single {single}, wrapped {wrapped})"); ok = False

    # Driven through `main()`, not through the formatter alone: calling
    # `dropped_warnings` directly pins the string and leaves BOTH the loaders that
    # populate `Corpus.dropped` and main's render loop unreached, so deleting that loop
    # would keep the control green. A control that pins a formatter while claiming to
    # pin a pipeline is the failure this whole self-test exists to prevent, so the
    # control takes the long way round.
    real_tree = globals()["load_tree"]
    try:
        def _one_file_with_a_drop(repo, sha):
            c = Corpus(label=f"{sha[:12]}")
            c.blobs = [("probe.md", normalize("a quotation long enough to clear the floor"))]
            c.dropped = ["unreadable-a.py", "unreadable-b.py"]
            return c
        globals()["load_tree"] = _one_file_with_a_drop
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                main(["x", "--source-root", str(source_root), "bankmachine"])
        except SystemExit:
            pass
        rendered = buf.getvalue()
        if "2 file(s) unreadable" in rendered and "unreadable-a.py" in rendered:
            print("  PASS unreadable files reach the report through main(), not swallowed")
        else:
            print("  FAIL the unreadable-file warning did not reach main()'s output")
            ok = False
    finally:
        globals()["load_tree"] = real_tree

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 3


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="*", choices=[*SOURCES, []], help="captures to audit")
    ap.add_argument("--self-test", action="store_true", help="run the instrument's controls and exit")
    ap.add_argument("--counts", action="store_true",
                    help="show what each extraction reads, and what the line-based recipe misses")
    ap.add_argument("--min-length", type=int, default=MIN_LENGTH_DEFAULT,
                    help=f"skip fragments shorter than this (default {MIN_LENGTH_DEFAULT})")
    ap.add_argument("--forms", default=",".join(PROSE_FORMS),
                    help="comma-separated forms to audit (default: prose quotations only)")
    ap.add_argument("--show-hits", action="store_true", help="print the matching file for each hit")
    ap.add_argument("--source-root", type=Path,
                    default=Path(os.environ.get("MCP_CAPTURE_SOURCE_ROOT",
                                                str(DEFAULT_SOURCE_ROOT))),
                    help=f"directory holding the mined source clones (default {DEFAULT_SOURCE_ROOT})")
    args = ap.parse_args(argv[1:])

    if args.self_test:
        return self_test(args.min_length, args.source_root)
    if args.counts:
        return counts(args.min_length)

    sources = args.sources or list(SOURCES)
    wanted = {f.strip() for f in args.forms.split(",") if f.strip()}
    # A misspelled form otherwise selects nothing and the run exits 0 having audited
    # nothing — the shape of a green that measured no set at all.
    unknown = wanted - KNOWN_FORMS
    if unknown or not wanted:
        die(f"error: unknown --forms value(s): {sorted(unknown) or '(empty)'}; "  # refusal: unknown-forms
            f"known forms are {sorted(KNOWN_FORMS)}")
    total_miss = 0
    for source in sources:
        corpora_used: list = []
        frags, skipped = audit(source, args.min_length, corpora_used, args.source_root)
        sel = [f for f in frags if f.form in wanted]
        by_verdict: dict[str, int] = {}
        for f in sel:
            by_verdict[f.verdict] = by_verdict.get(f.verdict, 0) + 1
        by_form: dict[str, int] = {}
        for f in frags:
            by_form[f.form] = by_form.get(f.form, 0) + 1
        print(f"\n===== {source} =====")
        if not sel:
            die(f"error: {source} — 0 fragments selected for forms {sorted(wanted)} at "  # refusal: vacuous-selection
                f"--min-length {args.min_length}; nothing was audited, so a clean result "
                f"would be a pass over the empty set")
        print(f"  fragments audited {len(sel)} (forms: {sorted(wanted)}); "
              f"skipped under {args.min_length} chars: {skipped}")
        print(f"  all extracted forms: " + " · ".join(f"{k} {v}" for k, v in sorted(by_form.items())))
        for warning in dropped_warnings(corpora_used):
            print(warning)
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
