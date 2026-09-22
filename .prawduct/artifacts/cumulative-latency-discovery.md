---
artifact: discovery
scope: cumulative-latency
drawn: 2026-09-22
status: findings — no fix chosen yet
---

# Cumulative Critic latency on discodon: what drives it

Investigation date: 2026-09-22, read-only, run by a delegated agent and reviewed by its coordinator. **The analysis scripts were ad hoc and were not kept**, so every number here is a dated reading, not a re-derivable one. The measured durations can be re-derived from each repo's `.prawduct/.governance-ledger.jsonl` via `lib.review_dispatch.event_interval_seconds`. The per-reviewer token and turn figures came from Claude Code session transcripts, which are machine-local and not re-derivable from the repo.
Labels: **[M]** measured (read directly from ledger, evidence fact, git or transcript timestamps), **[D]** derived (computed from measured values, e.g. a regression), **[I]** inferred (reasoning, not checked).

## Bottom line

A discodon cumulative review is slow for one main reason: the reviewer **generates far more output tokens**, most of them hidden thinking. It does not wait on tools. Across 56 reviewer transcripts from all three repos, `span ≈ 15 s per 1k output tokens − 59 s` fits with R² = 0.98 [D]. Tool execution takes 1.4–3.6% of span [M]. For discodon, the output volume comes from:

1. **The size of the span under review** on the two slow rows: 110 and 128 judgeable files, 5.5k and 6.4k changed lines. That is a long-lived campaign branch reviewed as one bundle against a fixed base, `9aa8135`.
2. **Serial dispatch by the coordinator**, which inlines the whole 110-file subject list into each reviewer prompt. The last reviewer starts up to 102 s after dispatch.
3. A smaller share from **larger context**: a briefing 31k tokens bigger, and 2–5x more tool output read. This lowers throughput somewhat and adds cost to each turn.

The single-reviewer discodon rows (400 s and 481 s, n=2) are **not** explained by diff size, since each covers 3–4 files. They are explained by reviewer exploration that emitted about 2x prawduct's output tokens. n=2 is too small to attribute this further.

## Corpus [M]

| ledger | review rows | measured (has `dispatched_at`) cumulative rows |
|---|---|---|
| discodon/.prawduct/.governance-ledger.jsonl | 1352 (301 cumulative) | **4** (+10 verify-resolutions) |
| wt-discodon-kairo | 130 (36 cumulative) | 0 |
| wt-discodon-webchat (only live worktree of discodon per `git worktree list`) | 3 | 0 |
| wt-discodon-housekeeping (worktree registration gone; git-common-dir unresolvable) | 3 | 0 |
| discodon/.claude/worktrees/agent-* (10 dirs) | no ledgers | 0 |
| bankmachine | 255 (70 cumulative) | **2** |
| prawduct | 1107 (235 cumulative) | **19** |
| prawduct-learning | 31 | 0 |

That is 8 ledgers read, with 25 measured cumulative rows (discodon 4, bankmachine 2, prawduct 19). Every row joined to its `review` fact in `<git-common-dir>/prawduct/evidence.jsonl`, which gives roster, tier, base/head trees and file lists. Line counts come from `git diff --numstat base_tree head_tree -- <files_reviewed>`. **Transcripts**: discodon runs in a devcontainer (`/opt/venv`, bind mount). Its Claude Code sessions are under `~/.claude-devcontainer/projects/-opt-venv/`, and prawduct and bankmachine sessions are under the host profiles. Reviewer and fork subagent transcripts were found for 24 of 25 rows (prawduct 127 s has none): 42 critic-reviewer transcripts and 7 single-pass fork segments. Every transcript entry is timestamped, and usage gives context and output tokens per turn.

Interval semantics [M]: none of the rows carries `review_written_at`, so the interval runs from `dispatched_at` to the ledger `ts`. The ledger `ts` falls 0–11 s before the slowest reviewer's final transcript entry, because consolidation fires on the last partial written. **Measured seconds ≈ max over reviewers of (dispatch offset + reviewer span)**. Rows reproduce within 7 s: 102+856 ≈ 953 and 46+972 ≈ 1011.

## Every measured cumulative row

"slowest unit" means the reviewer transcript (roster 3) or the single-pass fork segment from `critic-begin` to consolidate (roster 1) that finished last. "out tok" is output tokens, thinking included (thinking text is redacted in the transcripts). The self-reported column is shown only to show how unreliable it is.

| repo | ts (UTC) | measured s | roster | tier | judgeable files | judgeable +/- lines | oracle files | model | findings | slowest unit: span s / out tok / turns | self-reported s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| discodon | 2026-09-21 22:22 | 953 | 3 | escalate | 110 | +4931/-618 | 28 | claude-opus-5 | 21 | 856 / 60k / 87 | 1500 |
| discodon | 2026-09-22 00:37 | 1011 | 3 | escalate | 128 | +5750/-663 | 34 | claude-opus-5 | 19 | 972 / 66k / 129 | 1260 |
| discodon | 2026-09-22 03:35 | 481 | 1 | standard | 3 | +21/-1 | 1 | claude-opus-5 | 5 | 481 / 34k / 16 | 520 |
| discodon | 2026-09-22 12:17 | 400 | 1 | standard | 4 | +377/-5 | 3 | claude-opus-5 | 3 | 400 / 30k / 32 | 560 |
| bankmachine | 2026-09-21 20:29 | 187 | 3 | standard | 25 | +1154/-116 | 9 | claude-opus-5 | 13 | 160 / 15k / 21 | 420 |
| bankmachine | 2026-09-21 20:58 | 81 | 1 | standard | 1 | +1/-1 | 4 | claude-opus-5 | 0 | 82 / 7k / 19 | 420 |
| prawduct | 2026-09-19 04:08 | 573 | 3 | escalate | 10 | +437/-37 | 3 | claude-opus-5 | 11 | 543 / 41k / 59 | 900 |
| prawduct | 2026-09-19 14:04 | 549 | 3 | escalate | 14 | +482/-40 | 6 | claude-opus-5 | 10 | 509 / 39k / 41 | 660 |
| prawduct | 2026-09-19 14:54 | 498 | 3 | escalate | 15 | +1728/-15 | 3 | claude-opus-5 | 12 | 465 / 35k / 46 | 840 |
| prawduct | 2026-09-19 15:49 | 637 | 3 | escalate | 15 | +2128/-15 | 4 | claude-opus-5 | 11 | 603 / 42k / 51 | 960 |
| prawduct | 2026-09-19 17:08 | 635 | 3 | escalate | 14 | +703/-23 | 5 | claude-opus-5 | 19 | 615 / 48k / 54 | 1080 |
| prawduct | 2026-09-20 19:09 | 752 | 3 | escalate | 11 | +815/-12 | 4 | claude-opus-5 | 20 | 732 / 48k / 40 | 1500 |
| prawduct | 2026-09-21 01:48 | 430 | 3 | escalate | 7 | +371/-7 | 3 | claude-opus-5 | 14 | 426 / 34k / 33 | 640 |
| prawduct | 2026-09-21 16:07 | 464 | 1 | standard | 4 | +549/-1 | 1 | claude-opus-5 | 6 | 464 / 35k / 26 | 620 |
| prawduct | 2026-09-21 18:21 | 106 | 3 | escalate | 7 | +212/-45 | 1 | claude-opus-5 | 5 | 88 / 8k / 18 | 240 |
| prawduct | 2026-09-22 11:28 | 127 | 1 | standard | 6 | +393/-39 | 2 | claude-opus-5 | 3 | n/a (no transcript) | 420 |
| prawduct | 2026-09-22 12:14 | 22 | 1 | standard | 4 | +10/-4 | 1 | claude-opus-5 | 0 | 23 / 2k / 7 | 180 |
| prawduct | 2026-09-22 13:07 | 138 | 3 | escalate | 4 | +425/-19 | 1 | claude-opus-5 | 7 | 131 / 13k / 16 | 420 |
| prawduct | 2026-09-22 13:57 | 300 | 3 | escalate | 15 | +998/-75 | 2 | claude-opus-5 | 13 | 279 / 28k / 27 | 720 |
| prawduct | 2026-09-22 16:39 | 369 | 1 | standard | 4 | +31/-4 | 1 | claude-opus-5 | 4 | 368 / 30k / 52 | 337 |
| prawduct | 2026-09-22 17:47 | 268 | 3 | escalate | 10 | +299/-24 | 2 | claude-opus-5-5 | 6 | 243 / 23k / 36 | 600 |
| prawduct | 2026-09-22 18:32 | 168 | 1 | standard | 4 | +96/-24 | 1 | claude-opus-5-5 | 4 | 168 / 17k / 24 | 330 |
| prawduct | 2026-09-22 19:07 | 362 | 3 | escalate | 17 | +1660/-33 | 8 | claude-opus-5-5 | 16 | 336 / 34k / 47 | 660 |
| prawduct | 2026-09-22 19:37 | 195 | 3 | escalate | 4 | +42/-3 | 1 | claude-opus-5-5 | 9 | 187 / 18k / 33 | 420 |
| prawduct | 2026-09-22 20:42 | 45 | 1 | standard | 4 | +4/-4 | 1 | claude-opus-5-5 | 2 | 45 / 4k / 9 | 240 |

Plugin version: the discodon rows ran plugin **3.6.1-dev.1** (evidence `actor.plugin`) [M]. `discodon/.prawduct/.prawduct-version` says `3.5.1-dev` and is stale. The prawduct rows span 3.5.1-dev.1 to 3.6.1-dev.4. Plugin version does not separate the repos.

## Wall-clock structure (candidate 4) [M]

For every roster-3 row, the three reviewers run in parallel and the row time equals the dispatch offset of the last-finishing reviewer plus that reviewer's span. No serial coordinator work comes after the partials: consolidation is triggered by the last partial, and the ledger `ts` lands 0–11 s before the reviewer's own final entry.

Before the reviewers, the coordinator emits the three `Agent` calls **one after another**:

| repo/row | Agent calls at (s after dispatch) | chars per reviewer prompt |
|---|---|---|
| discodon 953 | 47, 73, 102 | 7315 / 7390 / 7969 |
| discodon 1011 | 46, 76, 107 | 8444 / 8592 / 8577 |
| bankmachine 187 | 13, 21, 29 | ~2.6k |
| prawduct (13 rows) | first 8–23, last 17–41 | ~1.4–2.7k |

Discodon's prompts are 3–4x longer because the coordinator pastes the full subject-file list (118 files) into each one. At about 70 output tokens/s, each prompt takes about 30 s to generate, against about 7 s on prawduct [D]. In row 953 the **last-dispatched reviewer (sustainability, +102 s) was the last to finish**, so the whole lag sat on the critical path [M].

## Per-reviewer anatomy [M unless marked]

| | discodon roster-3 slowest (n=2) | prawduct roster-3 slowest (n=13) | bankmachine roster-3 (n=1) | discodon single (n=2) | prawduct single (n=5) |
|---|---|---|---|---|---|
| span s (median) | 914 | 426 | 160 | 440 | 168 |
| output tokens | 63.1k | 34.2k | 14.9k | 32.2k | 16.5k |
| turns | 108 | 40 | 21 | 24 | 24 |
| tool seconds | 19.5 | 6 | 5 | 13 | 6 |
| out tok/s (model time) | 70.6 | 79.5 | 96.1 | 75.4 | 102.1 |
| first-turn context | 78k | 47k | 10.7k | 121k | 89k |
| mean context | 208k | 116k | 60k | 161k | 116k |
| tool-result chars read (per reviewer) | 275k–543k | 55k–300k | 93k–190k | — | — |

Decomposition of the roster-3 gap [D]: 914/426 = 2.15x, which is 1.84x more output tokens times 1.13x lower output rate. In log terms, output volume accounts for about 80% of the gap and rate for about 20%. On top of that, dispatch lag adds 46–102 s against 21–41 s on prawduct.

## Drivers, ranked by evidence

### 1. Size of the reviewed span, which makes reviewers generate 1.8x the output over 2.7x the turns (roster-3 rows): strong
- Evidence [M]: the two slow rows review 110 and 128 judgeable files and +4.9k/+5.8k lines. prawduct's roster-3 rows review 4–17 files and at most +2.1k lines. The slowest reviewer emitted 60k and 66k output tokens over 87 and 129 turns, against a prawduct median of 34k over 40. Across all 56 units, span is linear in output tokens (R² 0.98) [D]. Output correlates with reviewed lines at r = 0.67 and with files at 0.62 [D]. In prawduct alone (n=19 rows), measured seconds correlate with changed files at r = 0.65, reviewed files 0.63 and reviewed lines 0.55 [D].
- The response is sublinear [D]. discodon has 8x prawduct's median file count but only 1.84x the output (481 output tokens per reviewed file against 2483). A bigger span costs more, but not proportionally.
- Cause [M]: 3 of the 4 discodon rows use the same `base_reviewed` `9aa8135`. The campaign bundle is re-reviewed whole: 110 files at chunk 11, 128 at chunk 11c (+16% files, +6% time).
- Would falsify it: a discodon roster-3 cumulative over fewer than 20 files that still takes more than 800 s, or a prawduct review over more than 100 files that finishes near 430 s.
- Fix direction: bound a cumulative review's span, for example by reviewing only what changed since the last cumulative that covered the branch.

### 2. Serial reviewer dispatch that grows with file count: moderate and well measured, but small
- Evidence [M]: the last reviewer starts 102–107 s after dispatch on discodon, against 17–41 s on prawduct. Discodon prompts are 7.3–8.6k chars against about 2k, because the whole subject list is inlined. The three `Agent` calls are spaced about 30 s apart, against about 7 s. This is 5–10% of a discodon row, and it landed on the critical path in row 953.
- Would falsify it: `Agent` calls with long prompts that are not spaced by prompt length. Here they are.
- Fix direction: point reviewers at the manifest's `files_reviewed` instead of pasting the list into each prompt.

### 3. Larger context, from a bigger briefing and more tool output read: weak to moderate, confounded
- Evidence [M]: the harness auto-loads instructions into every reviewer. On discodon that is `CLAUDE.md` (35k chars), `.claude/rules/learnings/core.md` (134k chars) and `MEMORY.md` (17k chars), 185k chars in total. prawduct loads 115k chars and bankmachine 3k. First-turn context is 78k tokens for a discodon reviewer, 47k for prawduct and 10.7k for bankmachine. For the single-pass fork it is 119–124k against 74–93k. Mean context over a discodon reviewer run is 208k, against 116k.
- Effect on time [D]: output rate falls as mean context grows (unit level r = −0.64; rate ≈ 110 − 0.21·ctx_k tok/s, R² 0.41). But at the turn level, big turns in the same 100–200k context band run at 76 tok/s on discodon and about 80 on prawduct. The confound is date: prawduct's 2026-09-22 turns ran at 107 tok/s against about 80 on 09-19 to 09-21 at similar context. So some of the rate gap is service-side variance, not the repo. The per-turn context term fitted at about 0.016 s per 1k tokens per turn. 31k extra briefing tokens × about 100 turns is about 50 s per reviewer, roughly 5% [D].
- Would falsify it: same-hour discodon and prawduct reviews at equal context and equal output rate. The one near-simultaneous pair (discodon 400 at 12:10Z, 77 tok/s at 169k mean context; prawduct 138 at 13:05Z, about 103 tok/s at about 70k) supports the effect but is n=1.
- Fix direction: cut what every reviewer auto-loads. Discodon's 134k-char `core.md` and 35k-char `CLAUDE.md` load into every subagent.

### 4. Reviewer exploration on single-pass rows: plausible, n=2, not attributable
- Evidence [M]: discodon's single-pass rows ran 481 s over 3 files (+21/−1) and 400 s over 4 files (+377/−5). They emitted 34k and 30k output tokens, against a prawduct single-pass median of 16.5k. In the 481 s run, six model turns of 22–65 s each carried 4–7k output tokens. The reviewer also probed the live container (`du -sh /home/vscode/.vscode-server`, mounted-volume checks) for a devcontainer change, read change-log archives and ran 5 backlog queries. None of this scales with diff size. prawduct also has single-pass rows at 369 s and 464 s, so discodon's single rows are inside prawduct's range, just at its top.
- Would falsify it: more discodon single-pass rows clustering near prawduct's 148 s median.

### Not drivers (tested)
- **Tool-level latency (candidate 6)**, measured and falsified as a material driver. Tool time is 8–31 s per discodon reviewer (2.2% of span) against 3–9 s on prawduct (1.4%). Slowest single calls: `grep -rn` across the bind mount at 8–11 s, and `critic-consolidate` at 32 s in one verify run. `test-status`, `verify-coverage`, `learnings-files` and `backlog cache-query` each took under 1–4 s. The bind mount makes discodon tools about 3x slower, but the total is still under 35 s.
- **Model (candidate 5)** [M]: every discodon reviewer ran `claude-opus-5`, as did 14 of the 19 prawduct rows. It does not separate the repos.
- **Roster as such (candidate 1)** [M/D]: both slow discodon rows are roster-3, as are 13 of the 19 prawduct rows (median 430 s). Roster-3 on discodon is forced by 106–118 judgeable files, far past the 12-file threshold, so declaring or removing `risk_surfaces` would not change it. Discodon has no `risk_surfaces:`, so derived defaults apply. Reviewers run in parallel, so roster-3 costs the slowest of three plus dispatch lag, not 3x. Inside prawduct, roster-3 has a median of 430 s against 148 s for roster-1 (r = 0.47), but roster moves together with file count and tier, so this data cannot separate it.
- The **findings count** correlates at r = 0.79 with prawduct duration [D]. That is an effect of review depth, not a cause.

## What could not be determined
- **What the reviewers were thinking about.** Thinking text is redacted (`THINK 0ch`), so time is attributable to output tokens but not to a topic, such as the learnings cross-check against a 134k `core.md` versus reading the diff.
- **Whether the lower discodon output rate is caused by the repo or by timing.** Discodon has only 4 rows (2 roster-3, 2 single) and no same-hour twins. Service throughput visibly varied by day (prawduct 80 vs 107 tok/s).
- **A clean counterfactual.** No discodon review of a large span ran with a small briefing, or the reverse, so drivers 1 and 3 are separated only by regression.
- **The 297 older discodon cumulative rows.** They carry only the self-reported `duration_seconds`, which here runs 0.9–8.2x the clock (median 1.8x; discodon: 1500 vs 953, 1260 vs 1011), so they were excluded.
- **Per-partial timestamps from the evidence store.** Review facts do not carry them, and `.critic-partials-archive/` keeps only manifests. Per-reviewer timing here comes only from transcripts.
- **Sample size.** n=4 for discodon and n=2 for bankmachine. Every discodon-specific number here is indicative, not established.
- **Provenance of the interval function.** `event_interval_seconds` and `_extract_row` were imported from the working tree of `fix/measured-round-price`, whose edits to `review_dispatch.py` and `telemetry.py` touch neither function's lines, and the intervals match `ts − dispatched_at` computed by hand.
