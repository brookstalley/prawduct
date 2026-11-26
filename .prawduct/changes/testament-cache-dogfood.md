---
schema: 1
type: chore
scope: testament-cache-dogfood
date: 2026-11-25
title: Evidence and review ids draw through one entropy owner, and the hook's mock-git tests run in-process
---
This repo fixes two of its own largest remaining test-cacheability blockers, as the owner ruled
on 2026-11-26 (test cacheability, ask 2; recorded in `owner-rulings.md` on
`docs/test-cacheability-patterns`). testament refuses to reuse a result that read randomness or
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
seed, the pid and a per-process draw count: no entropy is read, two draws in a process differ, and
two processes' draws differ. A value outside the seed's form is ignored. The in-process hook runner
leaves the draw count alone, so two calls in one test still mint distinct ids, as two children did.
`tests/test_entropy.py` pins the production default (real entropy, two mints differ), that the
suite's seed is in force in-process, through the runner and in a scrubbed child, and an inventory
of every direct randomness read left in the plugin, now none.

### The hook's behaviour tests run in-process
`run_plugin_hook` runs the hook through `tests/_hook_inproc.py`, which gains `stubs`: a fake
executable answered in-process, so the shell-script mock git and gh on PATH become Python twins
and no child starts. `TestMockGitParity` holds the twins equal to the scripts over every branch
and every argv the hook sends on a clear, a blocking stop and a deferred stop. Four tests that
prove the entry point stay real children through `run_plugin_hook_child`, declared uncacheable:
the briefing on stdout, the Stop gate's exit 2, the Stop payload through a real stdin pipe, and
the write-isolation invariant, which covers everything the hook process writes.

## Consumer note
none: test-suite and internal id-minting change; ids keep the same form and real entropy
