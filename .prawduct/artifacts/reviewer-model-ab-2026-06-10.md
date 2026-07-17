# Reviewer Model A/B/C — sonnet vs opus vs fable (2026-06-10)

> **PAUSED 2026-07-14.** Reviewer-model tiering was removed (emergency patch —
> reviewers now run on the session model; see change-log `reviewer-session-model`)
> because `escalate` fired for nearly any declared risk surface, escalating to
> Fable constantly. This A/B remains the evidence base for the planned **restore**
> of tiering — retained, not superseded. Its "reviewers default to opus" / "the
> evidence base to revisit" claims describe the paused mechanism, not current
> behavior.

Chunk 01 deliverable of `build-plan-reviewer-model-tiering.md`. Three general-purpose agents
were spawned **in parallel** (one message, three Agent calls — wall clock = slowest run, not
the sum), differing ONLY in the `model` parameter, each given the identical prompt below
against the identical tree (gate-soundness bundle, `ed2dcb6...HEAD` at `1d876f8`).

## Captured input (verbatim; `{MODEL}` was the only variation)

```
You are an independent quality reviewer (the "Critic") for the prawduct framework repo at
/Users/brookstalley/source/prawduct. This is a MODEL-COMPARISON TEST RUN of the review process
— perform a completely genuine, thorough review; do not cut corners because it is a test.

Setup:
1. Read /Users/brookstalley/source/prawduct/skills/critic/review-protocol.md and follow its
   seven prioritized goals (Nothing Is Broken / Missing / Unintended; Everything Is Coherent;
   Decisions Were Deliberate; The System Can Be Understood; The Design Is Sound).
2. The review scope is the full branch bundle: `git diff ed2dcb6...HEAD` in that repo (a
   4-chunk feature branch implementing "gate-soundness": coverage-gate reconciliation,
   test-evidence config knobs, tracked build plans, cumulative-gate ordering guidance). Read
   the build plan at .prawduct/artifacts/build-plan-gate-soundness.md to know what was
   intended, and review the diff plus the changed files in full.

HARD CONSTRAINTS (test integrity):
- READ-ONLY: do not run pytest, builds, or any executable other than read-only git commands
  (git diff/log/show/status/ls-files/rev-parse/merge-base).
- Do NOT write, edit, or create ANY file. Do NOT run any `prawduct-hook` command (especially
  not critic-begin/critic-end — the real session's review markers must not be touched).

Output (your final message IS the deliverable — return it as text, do not write it anywhere):
A JSON code block with: {"findings": [{"severity": "blocking|warning|note", "goal": <1-7>,
"summary": "...", "files": ["..."]}], "summary": "...", "files_reviewed_count": N}
followed by a one-paragraph overall assessment.
```

Reproduction: same prompt, `Agent(model=<tier>)`, against any commit range. The official fable
cumulative review of the same bundle (run via `/prawduct:critic cumulative` earlier the same
session, findings at `commit_reviewed: b14f7b9`) serves as a reference run.

## Results

| | sonnet | opus | fable |
|---|---|---|---|
| Wall clock | 5m 27s | **1m 53s** | 8m 08s |
| Subagent tokens | 100,549 | **74,126** | 121,644 |
| Tool calls | 93 | **23** | 30 |
| Findings | 1 W + 2 N | 2 N | 2 W + 6 N |
| **Novel, real findings** | 0 | 1 | 6 |
| Re-reports of already-filed items | 1 (TST-3E8V) | 1 (acknowledged as filed) | 0 |

**Sonnet (1W+2N, nothing novel):** its warning re-flagged TST-3E8V (already filed in the
backlog it read); its notes were a cosmetic shadowing nit and a soft discovery-surfacing
suggestion. Most tool calls (93 — heavy trial-and-error navigation), most expensive of the
three per insight.

**Opus (2N, one novel):** found a genuinely new silent-corruption edge — `test_command` is read
by the `#`-comment-stripping YAML scalar reader, so a literal `#` in the command truncates it
before shlex — which the official fable cumulative had ALSO missed. Plus an accurate
on-the-record note about the producer/consumer asymmetry. Fastest, cheapest, fewest tool calls.

**Fable (2W+6N, six novel):** two real pre-merge warnings — (1) JUnit parsing read only the
first `<testsuite>`, silently undercounting multi-suite runners that the new `test_command`
knob explicitly invites; (2) the `init_product` unignored presentation layer (the exact seam
that absorbed two Critic warnings during the build) shipped untested — plus four real notes
(test-name overselling, two stale-prose catches, a backlog data error, and the parallel-plans
single-slot design gap, filed as BLD-7W2J). All six led to changes. Slowest and most expensive.

## Reading

- **Sonnet is below the floor for this work**: at HIGHER cost than opus it produced zero novel
  findings — it re-reports the known. Ruled out.
- **Opus is the efficiency frontier**: ~60% of fable's tokens, ~25% of its wall clock, and it
  caught a real edge even fable's official run missed. Adequate for the high-frequency tiers
  (chunk-mode goals 1-3, verify-resolutions) and a defensible default everywhere.
- **Fable demonstrably earns its cost at the bundle boundary** *in this n=1*: both of its
  warnings were real, reachable defects in code that had already passed an official cumulative
  review. If review depth at the last line of defense matters more than ~6 min and ~2× token
  cost per PR, the cumulative tier is where to spend it.
- The session's wall-clock pain is dominated by the **re-review treadmill** (every non-`.md`
  fix after a cumulative forces a full re-run), not by any single review. The ch.4 sequencing
  rule attacks the count of runs; the model default attacks the unit cost.

**Decision (user, 2026-06-10):** independent reviewers default to **opus** — Critic fork
(all modes), Critic coordinator subagents, PR reviewer. Restoring a higher tier for cumulative
is a one-line frontmatter/prose change if bundle-boundary misses recur; this artifact is the
evidence base to revisit. n=1 caveat recorded in the plan.
