"""Check that every decision's quoted evidence appears verbatim in the file it cites.

Usage (from the repo root): python3 .prawduct/artifacts/opus-55-prompt-audit-2026-09/verify_evidence.py .prawduct/artifacts/opus-55-prompt-audit-2026-09/slice-*.md
Exit 1 if any quote is missing. Runs a corrupted-quote control first, so a checker
that cannot fail never reports clean.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DECISION = re.compile(r"^### (\S+):", re.M)
LOCATION = re.compile(r"^- location: `([^`:]+)(?::[^`]*)?`", re.M)
EVIDENCE = re.compile(r'^- evidence: "(.*)"\s*$', re.M)


def norm(text):
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def found(path, quote):
    target = REPO / path
    if not target.is_file():
        return False, f"no such file {path}"
    body = norm(target.read_text(encoding="utf-8", errors="replace"))
    # Markdown emphasis in the source may have been dropped from the quote.
    stripped = norm(re.sub(r"[*`]", "", target.read_text(encoding="utf-8", errors="replace")))
    q = norm(quote)
    if q in body or norm(re.sub(r"[*`]", "", q)) in stripped:
        return True, ""
    return False, "quote not in file"


def decisions(slice_file):
    text = Path(slice_file).read_text(encoding="utf-8")
    starts = [m.start() for m in DECISION.finditer(text)] + [len(text)]
    for a, b in zip(starts, starts[1:]):
        block = text[a:b]
        did = DECISION.match(block).group(1)
        loc = LOCATION.search(block)
        ev = EVIDENCE.search(block)
        yield did, loc.group(1) if loc else None, ev.group(1) if ev else None


def main(files):
    ok, control = found("CLAUDE.md", "Prawduct turns product ideas into well-built software")
    bad, _ = found("CLAUDE.md", "Prawduct turns product ideas into badly-built software")
    if not ok or bad:
        print("CONTROL FAILED: checker cannot tell a real quote from a corrupted one")
        return 2
    failures = 0
    total = 0
    for f in files:
        for did, loc, ev in decisions(f):
            total += 1
            if not loc or not ev:
                print(f"{did}: MALFORMED (location={loc!r}, evidence present={ev is not None})")
                failures += 1
                continue
            good, why = found(loc, ev)
            if not good:
                print(f"{did}: {why} — {loc}: \"{ev[:80]}\"")
                failures += 1
    print(f"checked {total} decisions, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
