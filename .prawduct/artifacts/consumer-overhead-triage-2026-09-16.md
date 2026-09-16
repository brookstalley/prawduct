# Consumer overhead triage — 2026-09-16

Question: which backlog work most reduces consumer wall clock — repeated Critic rounds, test re-runs,
other governance overhead? Inputs: 167 open issues (brookstalley/prawduct), code spot-checks at
develop `c8a2ff09`, and governance ledgers + reflections from 7 active consumer repos since 2026-08-01.

## Evidence (consumer ledgers, since 2026-08-01)

| Repo | Reviews | Hours | verify-resolutions runs (hours) |
|---|---|---|---|
| discodon | 651 | 96.1 | 403 (41.6h) |
| samsung-frame-art-loader | 256 | 35.4 | 167 (17.1h) |
| bankmachine | 247 | 28.2 | 138 (10.7h) |
| hallucinote | 156 | 20.1 | 92 (7.8h) |
| swordfishing | 85 | 13.2 | 47 (4.2h) |
| puzzles | 87 | 10.8 | 43 (3.2h) |
| cordyceps | 15 | 1.8 | 8 (0.6h) |

~205 Critic hours across seven repos in ~6.5 weeks. verify-resolutions is 55–66% of runs and 35–50% of
hours, with low yield (0.14–0.65 findings/review) in 5 of 7 repos. Much of this predates v3.5.0
(2026-09-12), which shipped a review stopping rule — the new baseline is not yet measured.

Recurring patterns (repos affected):
1. Commits after a review — including taking NOTE-class findings — reopen coverage and buy another round (6/7). Worst: 16 rounds / ~150 min on one swordfishing chunk; 10 rounds / 65+ min bankmachine.
2. A round finds a defect in the previous round's fix; 3–4-round chains (5/7).
3. Coverage lost on amend / merge-conflict / file-set change forces a full cumulative (~14–17 min, up to ~1h) (3/7 + #672 reports).
4. Suite re-runs: `test-evidence record` re-running a just-run suite, branch switch / `/clear` invalidating a single evidence slot (~7 min per discodon branch) (4/7).
5. False-positive / misattributed gates and advisories that re-fire every session (4/7 + external reports).

## Ranked recommendations

| # | Work | Issues | Effort | Why |
|---|---|---|---|---|
| 0 | **Cut v3.5.1** | #814, #817 already merged | release | #814 (accept observations on the record; clean verify close states branch coverage) targets pattern 1 directly and is unreleased; consumers still run v3.5.0. Check #782 — the 3.5.1-dev CHANGELOG section does not mention #814/#817. |
| 1 | **Pre-dispatch guards in `begin_review`** | #167 + #724 (stale-evidence refusal) + #815 (tally at dispatch) + #776 (budget dead on trunk-based) | S–M, designs exist | Attacks the verify-resolutions cascade (patterns 1–2), the dominant cost. One plan: same function, shared exit-code table (#724's exit 4 now collides with budget-exhausted). Open: does a refused round leave the PR gate `uncovered`? |
| 2 | **Merge learnings-v2** | #744 (closes #652, #685) | wave-3 docs left | ~30–50k tokens off every subagent/reviewer dispatch (briefing inlines 119KB learnings.md). Branch is 81 ahead / 19 behind develop. |
| 3 | **Failing-test ids in evidence** | #792 (+ #680 residue) | S | Saves a full re-run on every red run. Best ratio in the backlog. Close #680 as mostly fixed. |
| 4 | **Blast-radius prompt before fix commit** | #731 (+ #694) | S | Pattern 2: fix-caused cascades that #1 doesn't catch. Carry it in `next_action_line`. |
| 5 | **Content-keyed coverage** | #672 half 2 + wording chunk first; then #768 + #334 leg 2 + #672 half 1 | S then L | Pattern 3: prose-only merge conflicts wipe coverage → 1h cumulative. Re-observe #768 on current code (`carried_blocking` may have shrunk it). |
| 6 | **Multi-slot test-run evidence** | #653 + #679 + #767(b) | M/L, one design | Pattern 4: re-runs on already-green trees after branch switch / `/clear`. Don't ship #767 option (a) (strict tree match) before #653 — it would add re-runs. |
| 7 | **False-positive sweep** | #813, #818, #762 detect-only slice, #809, #765, #811(c), #301 decision | S each | Pattern 5: nags every session, hand-edits at PR time, false Stop blocks. Batchable. |

Deferred for overhead purposes: #292 (defer per-chunk reviews — biggest per-plan saving but an owner
trade-off; wait for #291 data), #771/#816 (decide whether governance records are review subjects —
decision before build), #791/#221 (wrong-branch reviews; real but narrower), #181/#342/#191 (L, indirect).

## Triage housekeeping

- #818 is the only untriaged item (no labels). Proposed: `kind:bug area:governance effort:S impact:S source:user stage:design`.
- #746 appears implemented (`dispositions.py` has `FIXED`, CLI `--fixed`) — close candidate.
- #680 mostly stale (`--from-junit` / `--no-rerun` work with a declared `test_command`); residue is #792.
- #810 was closed as a duplicate of #767, not fixed; #767 is live (`gates.py:210-211`).
- Swordfishing: stop-gate canary reported "no test files modified" while listing a SwiftPM test file — not filed.
- puzzles: `unticked-committed-chunk` briefing warning matches a chunk number across two plans — not filed.
