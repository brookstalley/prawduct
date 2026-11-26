---
schema: 1
type: chore
scope: testament-cache-dogfood
date: 2026-11-25
title: Evidence and review ids draw through one entropy owner, and the hook's mock-git tests run in-process
---
This repo fixes two of its own largest remaining test-cacheability blockers and measures the gain,
as the owner ruled on 2026-11-26 (`owner-rulings.md`, "2026-11-26 (test cacheability)", ask 2). testament refuses to reuse a result that read randomness or
started a child other than a vouched-for git. Two of the causes `testament cacheability` ranked
highest were the `uuid4` token in evidence fact ids and `tests/test_plugin_runtime.py`'s
`run_plugin_hook`, which ran the hook as a `python3` child.

### One owner for id randomness
`plugin/lib/entropy.py` now owns the random token at the end of every minted id, the way
`lib/clock.py` owns "now": the session-start, stop-block, test-run and guard-refusal facts
(`lib/evidence.py`), the Critic's review id (`lib/critic_consolidate.mint_review_id`), and the
hook's chunk-imported and chunk-retracted facts. In a consumer's repository it reads `os.urandom`,
as `uuid4` did, so ids stay unique across clones and worktrees. `PRAWDUCT_TEST_ONLY_ENTROPY_SEED`,
which `tests/conftest.py` sets beside the frozen clock, replaces it with a SHA-256 sequence over the
seed, the pid and a per-process draw count, taken under a lock: an id token reads no entropy, two
draws in a process differ, even from two threads, and two processes' draws differ. A value outside the seed's form is ignored. The in-process hook runner
leaves the draw count alone, so two calls in one test still mint distinct ids, as two children did.
`tests/test_entropy.py` pins the production default (real entropy, two mints differ), that the
suite's seed is in force in-process, through the runner and in a scrubbed child, and an inventory
of every direct randomness read left in the plugin, now none. The inventory counts a randomness API
called or passed uncalled (`default_factory=uuid.uuid4`) and a seeded `random.Random`, which
testament counts as a draw too. It covers direct reads only: a stdlib call that draws on its own,
such as `tempfile`'s name generator under an atomic write, is outside it, and testament may still
count one.

### The hook's behaviour tests run in-process
`run_plugin_hook` runs the hook through `tests/_hook_inproc.py`, which gains `stubs`: a fake
executable answered in-process, so the shell-script mock git and gh on PATH become Python twins
and no child starts. `TestMockGitParity` holds the twins equal to the scripts over every branch
and every argv the hook sends on a clear, a blocking stop and a deferred stop. Four tests that
prove the entry point stay real children through `run_plugin_hook_child`, declared uncacheable:
the briefing on stdout, the Stop gate's exit 2, the Stop payload through a real stdin pipe, and
the write-isolation invariant, which covers everything the hook process writes. A stubbed
executable refuses a stream it cannot model (output to a file or descriptor, a `stdin=` stream)
rather than drop it, and hands `input=` bytes on unchanged. #1225 had expected these mock-git
children to stay children; the stubs and the parity test are what let them move in-process.

### The gain, measured
testament's cacheability snapshot of the default suite, before (this branch's base plus the
patterns change, tree `c87708bd`) and after (this branch synced with develop, tree `d8898006`):

| | before | after |
|---|---|---|
| tests | 13,997 | 13,980 |
| cacheable | 10,788 | 10,979 |
| uncacheable | 3,150 (22.5%) | 2,934 (21.0%) |
| declared uncacheable | 59 | 67 |

The causes that left the ranking are `run_plugin_hook`'s subprocess (frees 101), the entropy in
`evidence.append_stop_block` (frees 69) and `evidence._append_guard_fact` (frees 45). The clock in
`host._store_scan` (frees 33) is not fixed: it was the twentieth cause, and the new twentieth also frees
33, so it fell below the list's cutoff on a tie. The ranking lists 20 causes, so the ones that entered it were below
that line before, not new: the top one is the wall clock in `critic_consolidate.mint_review_id`
(136), which stays on real time on purpose and is #1225's first item. Re-derive after a full run
with `testament cacheability --offline --project prawduct --suite default --json`: these numbers
are its `snapshots[].row.counts` and `snapshots[].row.causes`.

## Consumer note
none: test-suite and internal id-minting change; ids keep the same form and real entropy
