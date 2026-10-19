#!/bin/sh
# Known-answer test for escape.py: a four-landing synthetic repo with one edge it must find
# and two it must not. Exits non-zero on any mismatch.
#   L0 adds a() and b().
#   L1 is a PR merge whose branch adds c() and then fixes it before merging. The in-PR fix is a
#      catch, not an escape, so it must not count.
#   L2, 5 days after L0, rewrites a line of a(): exactly one edge, L0 <- L2, 1 line, 120h.
#   L3, 40 days after L1, rewrites c(): outside the 30-day window, so no edge.
# Plus an unmerged branch "integ" cut after L2, read with --branch: B1 adds d(), and B2, 3 days
# later, rewrites it. Exactly two rows come back for it, B1 with one edge (1 line, 72h) and B2 with
# none, both tagged branch=integ. Its share of main's history is not emitted twice.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/src" "$tmp/clones"
cd "$tmp/src"
git init -q -b main .
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
c() { export GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1"; git add -A; git commit -q -m "$2"; }
printf 'def a():\n    return 1\n\ndef b():\n    return 2\n' > m.py; c "2026-09-01T10:00:00" L0
git checkout -q -b f1
printf 'def c():\n    return 30\n' > n.py; c "2026-09-02T10:00:00" add-c
printf 'def c():\n    return 3\n' > n.py; c "2026-09-02T11:00:00" fix-in-pr
git checkout -q main
export GIT_AUTHOR_DATE="2026-09-02T12:00:00" GIT_COMMITTER_DATE="2026-09-02T12:00:00"
git merge -q --no-ff f1 -m merge-f1
sed 's/return 1/return 11/' m.py > m.tmp && mv m.tmp m.py
mkdir -p tests; echo 'x=1' > tests/test_m.py; c "2026-09-06T10:00:00" L2
git checkout -q -b integ
printf 'def d():\n    return 4\n' > d.py; c "2026-09-07T10:00:00" B1
sed 's/return 4/return 44/' d.py > d.tmp && mv d.tmp d.py; c "2026-09-10T10:00:00" B2
git checkout -q main
sed 's/return 3/return 33/' n.py > n.tmp && mv n.tmp n.py; c "2026-10-12T10:00:00" L3
git clone -q --bare . "$tmp/clones/x_synth.git"
python3 "$here/escape.py" "$tmp/clones" "$tmp/out.jsonl" --branch x/synth=integ 2>/dev/null
python3 - "$tmp/out.jsonl" <<'EOF'
import json, sys
all_rows = [json.loads(l) for l in open(sys.argv[1])]
rows = [r for r in all_rows if "branch" not in r]
branch = [r for r in all_rows if r.get("branch") == "integ"]
assert len(all_rows) == 6, len(all_rows)
assert [[(e["lines"], e["gap_h"]) for e in r["reworked"]] for r in branch] == [[(1, 72.0)], []], branch
got = [[(e["lines"], e["gap_h"]) for e in r["reworked"]] for r in rows]
want = [[(1, 120.0)], [], [], []]
assert [r["merge"] for r in rows] == [False, True, False, False], rows
assert got == want, f"edges {got} != {want}"
print("escape.py known-answer test: ok")
EOF
