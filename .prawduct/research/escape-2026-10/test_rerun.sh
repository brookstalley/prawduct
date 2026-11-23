#!/bin/sh
# Known-answer test for rerun.py (#987). Exits non-zero on any mismatch.
#   Synthetic rows, with "now" fixed at 2026-11-10T00:00Z, so a window is open after 2026-10-11T00:00Z:
#   - before CUTOFF (2026-09-01): out of scope, never counted.
#   - repo F, 2026-09-20, 2000 src lines, edges at 30h and 10h: scored, 1 edge (gap >= 24) -> 0.50/kLOC.
#   - ungoverned, 2026-09-25, 1000 lines, one 48h edge -> 1.00/kLOC.
#   - governed (bucket 3.6), 2026-09-30, 4000 lines, one 72h edge -> 0.25/kLOC.
#   - governed, 2026-10-20: window still open, so counted as a landing and not scored.
#   - governed, 2026-09-28, 0 src lines: scoreable but adds no kLOC.
# Then the same file with one row appended twice must make rerun.py refuse (non-zero, no scores).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
echo "acme/fast" > "$tmp/repo_f.txt"
python3 - "$tmp/rows.jsonl" <<'EOF'
import json, sys, datetime as dt
ts = lambda s: int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())
rows = [
    {"repo": "acme/old", "sha": "s0", "ts": ts("2026-09-01T00:00"), "bucket": "none", "src_added": 500,
     "reworked": [{"lines": 1, "gap_h": 99}]},
    {"repo": "acme/fast", "sha": "s1", "ts": ts("2026-09-20T00:00"), "bucket": "none", "src_added": 2000,
     "reworked": [{"lines": 3, "gap_h": 30.0}, {"lines": 1, "gap_h": 10.0}]},
    {"repo": "acme/plain", "sha": "s2", "ts": ts("2026-09-25T00:00"), "bucket": "dormant", "src_added": 1000,
     "reworked": [{"lines": 2, "gap_h": 48.0}]},
    {"repo": "acme/gov", "sha": "s3", "ts": ts("2026-09-30T00:00"), "bucket": "3.6", "src_added": 4000,
     "reworked": [{"lines": 5, "gap_h": 72.0}]},
    {"repo": "acme/gov", "sha": "s4", "ts": ts("2026-10-20T00:00"), "bucket": "3.7", "src_added": 900,
     "reworked": [{"lines": 9, "gap_h": 50.0}]},
    {"repo": "acme/gov", "sha": "s5", "ts": ts("2026-09-28T00:00"), "bucket": "3.6", "src_added": 0,
     "reworked": []},
]
with open(sys.argv[1], "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
EOF
now=$(python3 -c 'import datetime as d; print(int(d.datetime(2026,11,10,tzinfo=d.timezone.utc).timestamp()))')
python3 - "$here" "$tmp/rows.jsonl" "$tmp/repo_f.txt" "$now" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import rerun
got = rerun.main([sys.argv[2], sys.argv[3], "--now", sys.argv[4]])
f, u, g = got["repo F"], got["ungoverned excl. F"], got["governed"]
assert (f["landings"], f["window_open"], f["scoreable"], f["edges"], f["rate_per_kloc"]) == (1, 0, 1, 1, 0.5), f
assert (u["landings"], u["edges"], u["rate_per_kloc"]) == (1, 1, 1.0), u
assert (g["landings"], g["window_open"], g["scoreable"], g["src_added"], g["edges"], g["rate_per_kloc"]) \
    == (3, 1, 2, 4000, 1, 0.25), g
EOF
tail -n 1 "$tmp/rows.jsonl" >> "$tmp/rows.jsonl"
if python3 "$here/rerun.py" "$tmp/rows.jsonl" "$tmp/repo_f.txt" --now "$now" > "$tmp/dup.out" 2>&1; then
    echo "rerun.py scored a file with a duplicated (repo, sha) row; it must refuse" >&2
    exit 1
fi
grep -q "appear more than once" "$tmp/dup.out" || { cat "$tmp/dup.out" >&2; exit 1; }
if grep -q "rate/kLOC" "$tmp/dup.out"; then echo "refusal still printed scores" >&2; exit 1; fi
echo "rerun.py known-answer test: ok"
