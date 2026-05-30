# Governance-Tax Reduction — Deferred Follow-ups

Status: **proposals, not committed work.** These came out of the 2026-05-30
governance-tax reduction effort (branch `feat/reduce-governance-tax`). They were
deliberately *not* filed as pickable `.prawduct/backlog.md` items — each changes
a product-facing contract or is a new subsystem, so it needs an explicit owner
decision before it becomes work (this is the anti-reinflation rule from that same
effort: don't let observations auto-inflate the backlog). Pull one into the
backlog only when you decide to do it.

---

## 1. Collapse the Critic's 4 modes → 2 (compat-sensitive — needs approval)

**Observation (gate/Critic ceremony audit).** The Critic has four modes —
`chunk`, `final`, `cumulative`, `verify-resolutions` — selected by an inference
cascade (`tools/lib/critic_mode.py`) plus an override stack, persisted with a
"two-form verbose string" rule the stop hook validates. But:
- `chunk` and `verify-resolutions` both run Goals 1–3.
- `final` and `cumulative` both run all 7 goals; the only real difference is diff
  scope (working tree vs `merge-base...HEAD`) — a *parameter*, not a mode.

So the space is really **{light, full} × {scope}**. `verify-resolutions` is the
highest complexity-per-value: a whole mode + a `compute-verify-resolutions-scope`
CLI + a demotion-threshold formula + a separate stop-hook subset gate, purely to
save minutes on a localized re-review — and it's the mode implicated in CRT-2M5P
(the Critic corrupted the tree during a verify-resolutions pass).

**Proposed shape.** Two modes (`scoped` = Goals 1–3, `full` = all 7) + an optional
`--base` scope parameter for the PR bundle. Removes the inference cascade's
rules 1–2, the two-form verbose rule, most of `critic_mode.py`, and the
verify-resolutions gate + helper.

**Why deferred — compat.** Product repos (war-castle, hallucinote, discodon) have
build-plans that may set `Critic mode: verify-resolutions` / `cumulative`, and
`infer-critic-mode` returns these strings to the stop hook and `/pr`. Collapsing
modes is a breaking change to a synced contract; it needs a migration (alias old
mode names → new) and a deprecation window. **Decision required from the owner**
before this becomes work. (Source: gate-ceremony audit; CRT-2M5P context.)

## 2. Artifact-drift auto-detection (new subsystem)

**Observation (hallucinote review + Critic Goal 4).** Coherence — docs/artifacts
matching code — is detected today by the Critic *reading* artifacts and comparing
by hand. There's no automated drift check, so for large changes it's
labor-intensive and drift can survive if an artifact isn't read. hallucinote's
learnings call this out ("Link, don't summarize" — restated facts drift).

**Proposed shape.** A `product-hook check-artifact-drift` (or a Critic
sub-routine) that flags prose summaries of facts that live structurally elsewhere
(version numbers, file inventories, config tables) when the source changed but the
summary didn't. Needs design on the detection heuristic (string-match is noisy;
AST/structured-fact extraction is heavier).

**Why deferred.** New subsystem, non-trivial heuristic design, no acute pain
today. Build when a product hits real drift the Critic missed. (Source:
hallucinote rough-edges review.)

## 3. Session-start sync: kill the 30s-timeout false positive (small, compat-adjacent)

**Observation (sync-friction audit).** `try_sync` shells out to
`prawduct-setup.py sync` with a **30s** timeout. `run_sync`'s slow paths —
`_try_pull_framework` (git pull/fetch) and per-stale-file 100-commit history
walks — can exceed 30s on a cold cache or large framework. On timeout the
subprocess is killed, the manifest isn't bumped, and the next session nags
"sync didn't apply" even though nothing is wrong. (Chunk B made the version-NOTE
outcome-aware, which *reduces* this, but the timeout itself remains.)

**Proposed shape (pick one).**
- Pass `--no-pull` on the session-start sync so the slow framework-pull +
  history walks don't run — pull is a framework-maintainer concern, not a
  per-session product one. **Compat note:** this changes auto-update semantics
  (manifests default `auto_pull: true`); products may rely on session-start pull
  to receive framework updates. Worth a `project-preferences.md` toggle.
- Or simply raise the session-start subprocess timeout (e.g. 30s → 60s) — purely
  reduces false positives, no behavior change, but can make a slow session-start
  wait longer.

**Why deferred.** The `--no-pull` option touches auto-update semantics (compat);
the timeout bump trades one friction for another. Small but wants an owner call.
(Source: sync-friction audit, Chunk B reflection.)

## 4. (Owner decision) Backlog burn-down — archive the 24 self-nag items

**Observation (backlog audit).** ~47% of the pre-effort 51-item backlog was the
framework's own Critic/reflection nitpicking framework internals (10 `CRT-` items,
several Critic-about-Critic). The Chunk-D anti-reinflation rule stops *new* ones;
the *existing* 24 self-nags are still in `## Open`.

This effort deliberately did **not** mass-archive them — declaring 24 of the
owner's items WONTFIX is the owner's call (Principle 23), and the every-session
*dump* that made them hurt is already fixed (Chunk C → one count line). The audit's
candidate WONTFIX list (ratify or trim, then `/backlog` archive):

`CRT-6T1V, CRT-4W8M, CRT-1B6Q, CRT-5N3F, CRT-8D2W, CRT-2H8K, CRT-3K9P` (Critic
proposing new Critic checks / Critic-accuracy R&D), `MET-8N2C, MET-1T5W, MET-2D9K,
MET-4K8Z, MET-9K4R, MET-3P7B, MET-7H2D` (methodology prose-tightening), `BLD-0G6V,
BLD-7A2E, BLD-3X9M, BLD-5V8F` (bookkeeping about past framework builds), `DOC-9J4B`
(a chore in *another* product's repo), `BKL-2F7K, BKL-5H9M, BKL-1V8J, BKL-4N6X`
(deferred backlog-feature scope, inert with no external-backlog consumer).

The ~18 "real-but-minor" refactor/test items (`SYN-*`, `TST-*`, `STH-*`, etc.)
could move to a `## Parked` section so they stop counting against the active
working set without being closed.
