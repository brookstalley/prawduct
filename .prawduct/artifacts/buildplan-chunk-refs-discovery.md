---
artifact: discovery
# scope intentionally empty: this is requirements for two backlog items, not a
# release; no plan scope is owned here (same opt-out as kernel-redesign-discovery.md).
scope:
status: discovery complete 2026-07-29 — §6 decision ruled by owner same day; next: planning
created: 2026-07-29
covers: [BLD-ZQ2V, BLD-5R7K]
depends_on: [build-plan-v3.2.0-golive.md]
---

# `verify-chunk-refs` — which chunk, and which refs

Requirements for **BLD-ZQ2V** (the gate inspects the earliest incomplete chunk,
not the one being worked on) and **BLD-5R7K** (the git-derived reading's
undocumented precondition and silent degradation). Both were `stage:
requirements`; both name `plugin/lib/buildplan_refs.py`. They are written
together because they share a fix surface and a symptom, and separately
resolved because — as BLD-ZQ2V records — neither closes the other.

Everything numeric below was **measured against the real gate functions** at
tree `02faf2f`, not replayed or estimated. The probe drives
`_parse_build_plan_chunk_refs` and `_verify_chunk_refs` directly, chunk by
chunk, exactly as `verify-chunk-refs` does.

## 1. Problem (observable, evidenced)

`verify-chunk-refs` reports `ok` while inspecting a chunk nobody is working on.

For the entire v3.2.0 release it resolves the current chunk to **Chunk 01** and
stays there:

    resolve_chunk_progress -> current_id='01' complete=2/11 git_derived=True
    _current_chunk_id_from_status -> '01'

Chunk 01 carries **one** ref, and it resolves. So the measured state is: **the
gate has been verifying exactly one file reference for the whole release**, and
reporting green. Chunks 02–09 — 49 further refs — were never inspected.

That is not hypothetical damage. It is how a bare `artifacts/…` path (which
should have been `.prawduct/artifacts/…`) reached the Chunk 05c body unflagged
on 2026-07-28; the Critic caught it by reading, and the gate was green
throughout.

**Root cause (BLD-ZQ2V, confirmed by reading `:396-423`).** `Chunk 01` is not a
wrong answer to the question asked — it is the right answer to the wrong
question. `_resolve_chunk_progress_from` selects the **first incomplete** item
(`:402`), and Chunk 01 (live verification, VRF-005/007/008) genuinely is
incomplete. Every consumer then reads that answer as **"the chunk being worked
on."** Those two questions diverge the instant work proceeds out of order —
which is exactly what happened: 05, 05b and 05c were built while 01 stayed open.

The `[ ]`-until-release checkbox convention is **contributory, not causal**. The
git-aware reading is active here (`git_derived=True`), so the union rule at
`:270-278` answered and still returned 01: Chunk 01's box never flips, and its
completing work landed in a prior merge (PR #137, behind the base), so neither
leg of the union can mark it complete. `_git_aware_progress`'s docstring
anticipates this precise failure — *"a commit-only reading resolves 'current'
back to an already-shipped Chunk 01"* — and says the union prevents it. Under
`[ ]`-until-release the checkbox leg contributes nothing and the union collapses
to the commit-only reading it exists to avoid.

## 2. The fix is THREE parts, not two — the third was not previously recorded

BLD-ZQ2V states the fix is two parts (current-chunk resolution + a plugin-root
fallback for `_verify_chunk_refs`). Measurement finds a third defect class, and
corrects the scale of the second.

Across all 11 chunks: **50 refs extracted, 21 missing.**

| Class | Count | Chunks | Fixable by |
|---|---|---|---|
| **(a)** plugin-relative shorthand — `lib/gates.py`, `skills/backlog/SKILL.md`, `.claude-plugin/plugin.json` … resolve under `plugin/`, not from the repo root | **17** | 02, 03, 05, 05c, 07, 08, 09 | a plugin-root fallback |
| **(b)** GitHub repo slugs and issue refs in prose — `brookstalley/prawduct`, `brookstalley/prawduct-s2-dryrun-20260724`, `owner/repo`, `owner/samsung-frame-art-loader#12` | **4** | 02, 05, 05c, 08 | a carveout in `_looks_like_file_path` |
| residual | **0** | — | — |

**Class (b) is new and cannot be fixed by the fallback.** `_looks_like_file_path`
(`:614-661`) admits any token containing `/` unless it matches one of six
carveouts (slash-command, glob, angle-bracket, URL, git-ref prefix). The
`owner/repo` shape matches none of them, so a repo slug written in prose is
classified as a file path. Verified directly:

    'brookstalley/prawduct'              looks_like_path=True
    'owner/repo'                         looks_like_path=True
    'owner/samsung-frame-art-loader#12'  looks_like_path=True

No plugin-root fallback helps these — they name no file anywhere. Left
unfixed, they would block **permanently** on Chunks 02, 05, 05c and 08.

**Correction to the recorded scale of class (a).** BLD-ZQ2V carries the Critic's
estimate of "~8 literal tokens" across Chunks 03/05c/07/08, and explicitly flags
that count as not independently established. Measured: **17 tokens across seven
chunks** (02, 03, 05, 05c, 07, 08, 09) — more than double, and including three
chunks the estimate did not name. The direction and the coupling the Critic
identified were right; the magnitude was understated.

## 3. The ordering constraint — the load-bearing requirement

**Parts (a) and (b) MUST land before or with the current-chunk fix.**

Today the gate inspects one clean ref, so all 21 misses are invisible. Correcting
current-chunk resolution alone converts a silent gate into one that **blocks on
21 refs across seven chunks** — including Chunk 09, the release ceremony. That is
a release-blocking regression manufactured by a bug fix, and it is the single
most important thing this document records.

BLD-ZQ2V anticipated this in the two-part case ("landing only the first turns a
silent gate into a blocking one"). Measurement makes it sharper: the exposure is
twice the recorded size and spans a third defect class the item does not name.

## 4. Success criteria (verifiable)

1. `verify-chunk-refs` inspects the chunk whose refs the at-hand work touches,
   not merely the earliest incomplete one, under out-of-order execution.
2. A plugin-relative ref that resolves under `plugin/` does not report missing.
3. An `owner/repo` or `owner/repo#N` token in prose is not classified as a file
   path.
4. Against `build-plan-v3.2.0-golive.md` at the tree where the fix lands, the
   gate reports **zero** missing refs across **all** chunks — the falsifying
   command is the § 2 probe, re-run, asserting `residual=0` with chunk-scoping
   removed.
5. Genuine regressions still fail: a deliberately-broken path in any chunk is
   reported, and the `new`-qualifier forward-ref exemption still suppresses it.
6. **(BLD-5R7K)** The `Chunk NN` + conventional-scope commit precondition is
   documented where plan authors meet it, and a `git_derived=False` degradation
   is announced on a deliberately-invoked surface rather than failing quiet.

## 5. Out of scope

- Symbol (`path::symbol`) and backlog-ID verification — already deferred, unchanged.
- The `[ ]`-until-release checkbox convention itself. It is contributory, not
  causal (§1), and it is load-bearing for this release's change-log discipline.
- Merging BLD-ZQ2V and BLD-5R7K. They land coherently; neither closes the other.
- Rewriting the plan's plugin-relative shorthand to be root-relative. The
  shorthand is idiomatic across this repo's plans and matches how the plugin
  ships; the gate should learn the convention, not 17 prose sites change to suit
  the gate.

## 6. Design options for part 1 — recommendation, and the one open decision

BLD-ZQ2V records three fix directions and notes only (1) addresses out-of-order
execution. Measurement admits a fourth that the item did not consider, and it is
the one I recommend.

**Recommended — delete the chunk-scoping from this consumer.** `verify-chunk-refs`
asks "do the file refs in this build plan resolve?" That question is not
inherently chunk-scoped; scoping was noise control. Verify **every** chunk and
the "which chunk is current" question disappears for this consumer entirely — no
new resolver, no heuristic, strictly less machinery. It is a deletion, which
also suits the release's stated deletion-only simplification direction rather
than adding to the governance load the narrowing was called to reduce.

The measurement is what makes this viable rather than merely elegant: with
classes (a) and (b) fixed, the residual across all 11 chunks is **0**, so
full-plan verification is noise-free on the real plan *today*. It also strictly
dominates a better current-chunk resolver — full coverage cannot inspect the
wrong chunk.

"Which chunk is current" remains a real question for *other* consumers (critic
mode inference, the stop hook, the handoff). Those have different needs and
should not be conflated with this gate; whether they need direction (1) is
separate work and is **not** resolved here.

- `[ASSUMPTION: full-plan verification is acceptable on OTHER products' build
  plans, not just this one | MED impact | user can veto]` — this repo's plan
  reaches residual 0, but a product carrying stale refs in long-closed chunks
  would see them all surface at once. Mitigations, in preference order: report
  non-current chunks as **warn** rather than **blocking**; or scope to
  unshipped chunks. Untestable here — prawduct is the only repo with plans of
  this depth.

**The decision (owner) — RULED 2026-07-29: option (ii).** The question put was
whether the gate should (i) block on every chunk, (ii) block on the current
chunk and warn on the rest, or (iii) stay chunk-scoped and get a
working-diff-derived resolver (direction (1), materially more machinery).

**Ruling: (ii) — verify every chunk; block on the current one, warn on the
rest.** This is the recommended option and the rationale stands as written: full
coverage immediately, the gate cannot inspect the wrong chunk, and the §6
assumption's blast radius on adopting products degrades to a warning rather than
a wall — which is what makes the assumption safe to hold rather than merely
declared.

Two consequences for planning:

- **"Current chunk" still has to be resolved**, because it now selects *severity*
  rather than *scope*. But the requirement on it is far weaker: a wrong answer
  mislabels a finding warn-vs-block, where today it hides 49 refs outright. The
  existing first-incomplete reading is therefore an acceptable starting point,
  and direction (1)'s working-diff resolver becomes an optional later refinement
  rather than a prerequisite. This is the main reason (ii) beats (i) and (iii)
  on cost as well as safety.
- **Warn is not a severity this gate currently has — adding it IS part of the
  work.** Checked rather than assumed (`prawduct-hook:2596-2646`):
  `cmd_verify_chunk_refs` is a binary exit-code gate, `0` or `1`, with no
  non-blocking channel. It already distinguishes two *messages* at exit 1 —
  `cannot-verify:` (the check could not run) versus `missing-ref:` (a named
  deliverable is absent), deliberately, so a can't-parse exit is not dismissed
  as noise and masking a real one (BLD-5J8N). A third, non-blocking `warn-ref:`
  line reporting non-current chunks at **exit 0** extends that existing
  vocabulary rather than inventing a mechanism, and it is the one genuinely new
  piece of surface option (ii) requires.

  Also noted while reading: `PRAWDUCT_VERIFY_CHUNK_ID` (`:2613`) already
  overrides current-chunk resolution from the environment. That is a ready-made
  seam for testing per-chunk severity without driving the resolver.

## 7. Rigor calibration

Medium stakes, low volatility, high post-measurement confidence. The mechanism
was read (`:257-306`, `:396-423`, `:614-661`, `:1000-1037`) rather than recalled,
and every quantity was measured rather than inherited — which is what caught
both the third defect class and the 2× understatement in class (a). No research
gap: the domain is this repo's own code. The one genuine unknown is the
cross-product blast radius (§6), which is unverifiable from here and is
therefore surfaced as a decision rather than an assumption to bury.
