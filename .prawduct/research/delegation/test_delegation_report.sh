#!/bin/sh
# Known-answer test for delegation_report.py over the synthetic fixture in fixture/transcripts.
# Three dispatches inside the window (a fourth, in March, is outside it and must not count):
#   reviewer  critic-reviewer, background, runs `prawduct-hook critic-begin`, same message as research.
#   research  inline sidechain, model sonnet, no write tool; its Bash only MENTIONS the declared suite
#             command inside an echo string and a grep pattern, so it must NOT count as running it.
#             The echo string puts the command after a `;`, so the case fails if quoted text is
#             ever split into segments: a mention that merely follows `echo` passes either way.
#   build     isolation worktree, model opus, runs the declared suite (extra whitespace, trailing
#             flag), has one SendMessage follow-up.
# Exits non-zero on any mismatch.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
fx="$here/fixture/transcripts"
run() { python3 "$here/delegation_report.py" --source "$fx" "$@"; }

run --suite "fake-suite --all" --since 2026-01-01 --until 2026-01-31 --json | python3 -c '
import json, sys
r = json.load(sys.stdin)["overall"]
want = {
    "dispatches": 3,
    "roles": {"reviewer": 1, "research": 1, "build": 1, "integrate": 0, "unclassified": 0},
    "model_requested": {"opus": 1, "sonnet": 1, "haiku": 0, "other": 0, "none": 1},
    "isolation": {"worktree": 1, "none": 2},
    "mode": {"background": 1, "foreground": 2},
    "fan_out_width": {"1": 1, "2": 2, "3": 0, "4+": 0},
    "ran_suite": 1,
    "governance_command": 1,
    "followup_rounds": {"dispatches_with_followup": 1, "messages": 1},
}
for k, v in want.items():
    assert r[k] == v, (k, r[k], v)
assert r["wall_clock_s"] == {"n": 3, "median": 240.0, "p90": 540.0}, r["wall_clock_s"]
assert r["tokens"] == {"n": 2, "median": 220, "total": 440}, r["tokens"]
assert r["model_resolved"]["opus"] == 2 and r["model_resolved"]["sonnet"] == 1, r["model_resolved"]
print("known-answer counts: ok")
'

# With no suite patterns the suite number is never guessed.
run --since 2026-01-01 --until 2026-01-31 --json | python3 -c '
import json, sys
assert json.load(sys.stdin)["overall"]["ran_suite"] == "not assessed"
print("no patterns -> not assessed: ok")
'

# The human report labels every number, claims no wall-clock saving, and carries no fixture text.
out=$(run --suite "fake-suite --all" --since 2026-01-01 --until 2026-01-31)
echo "$out" | grep -q '\[measured\]'
echo "$out" | grep -q '\[heuristic\]'
echo "$out" | grep -q 'repo A'
! echo "$out" | grep -qi 'fake prompt\|outside window\|remember to run'
echo "report labels and privacy: ok"
echo "delegation_report.py known-answer test: ok"
