# v3.2.0 Supported-Scenario Functional Audit

**Purpose.** The acceptance set for Chunk 09 done-when #8 — the owner's "GitHub Issues is working
great" release gate, sharpened 2026-07-28 to: *"all functional requirements working great. NFRs like
performance can lag to a later release. But we cannot be functionally broken for any supported
scenario."*

**Method.** Extracted the 55 requirement IDs from `documentation/backlog-service-requirements.md`,
mapped each to implementation (`plugin/lib/backlog/`, `plugin/bin/prawduct-hook`,
`plugin/skills/backlog/`) and to test references, then **read the code for every candidate gap**.
Grep-absence alone is not evidence — requirement IDs are not always cited in code, and two candidates
in this audit were dismissed on reading (see § Dismissed).

**Status:** first pass, 2026-07-28. `verify-api` has not run, so every "verified" below means
*verified against the in-process fake*, not against GitHub.

---

## The scenarios v3.2.0 supports

Per **MG3** as clarified by the owner 2026-07-28 — cutover is **atomic within a project, staged across
the fleet**:

| # | Scenario | In scope for v3.2.0 |
|---|---|---|
| S-A | **Stay on markdown** — repo has not migrated, may never | ✅ yes (MG3 binds the markdown read path until the *last* project cuts over) |
| S-B | **Migrate** markdown → Issues | ✅ yes (Chunks 05/06) |
| S-C | **Day-to-day use** on Issues after migrating | ✅ yes |
| S-D | **Onboard** a new product | ✅ yes (Chunk 03 closed ONB-3F9P) |
| S-E | **Export / backup** | ✅ yes (MG2) |
| S-F | **File upstream** into prawduct's repo | ❌ **no** — Chunk 08 deferred; `incoming-bugs/` remains the path |

---

## Findings

### F1 — `verify-api` has never run. The entire adapter is fake-verified. **[BKL-3N8Q, open]**

Affects **every** scenario. The L2 contract probe records the real REST/GraphQL shapes that the L1
fake asserts, and its shape-diff (CONTRACT-1) is the only mechanism that would catch the fake having
drifted from GitHub. It has not been run.

The suite's 2730 passing tests all execute against `tests/fakes/fake_github.py`. If any real payload
shape differs from the fake, the failure is **silent and confident**: `list_blocked_by` returning an
unexpected shape makes `pick` report blocked items as ready; `decode_item` drops facets to `None`
without warning. No test in the suite can see any of it.

**This is the single highest-value hour remaining in the release.** Operator-gated (needs a throwaway
repo and live `gh`).

### F2 — GV8 is unmet: three norm-lifecycle signals go dark at cutover

**GV8** states *"Norm-lifecycle signals survive cutover."* They do not — they retire. `norm_probes.py`
disables all three at `post_cutover(state)`:

- `revisit-due` (`:373`) — *"item liveness now lives on GitHub Issues; the file is frozen"*
- `dead-why` (`:413`) — *"dead/live can no longer be judged from the frozen file"*
- `stalled-transition` (`:459`) — *"item movement can no longer be judged from the frozen file"*

**Credit where due: this is a *documented* retirement, not a silent no-op** — each carries a comment
naming why. That is materially better than the GV7 silent-degradation failure mode, and an earlier
draft of this audit wrongly called it silent before reading the code.

But the requirement says *survive*, and restoration is **W1-gated** — BKL-4R7V records that resolving
`#N` to a live status "lands with the W1 cache under GV8, alongside the other post-cutover readers."
W1 is out of v3.2.0. So a migrated repo permanently loses three governance signals it had on markdown.

**Owner decision needed:** does an unmet GV8 block the gate, or does v3.2.0 ship with the retirement
declared in the release note? It is a *functional* requirement (governance integration), not an NFR,
so the functional-completeness ruling does not defer it on its own.

### F3 — GV9 is unmet: post-cutover item references are invisible. **[BKL-4R7V, open]**

**GV9** — *"Item references survive the identifier change."* After cutover the canonical id is
`owner/repo#number`, but every citation-consuming surface recognizes only the markdown-era
`[PFX-XXXX]` spelling. A post-cutover reference is **not mis-read — it is not seen at all**.

Affects S-C. BKL-4R7V notes the cheap half ships independently: widening the regexes is pure syntax
and does **not** need W1. Only *resolving* `#N` to a live status is W1-gated. **Recommend taking the
parsing half in v3.2.0.**

### F4 — No declared terminal-markdown state. **[BKL-8W2M, open]**

Affects **S-A**, and the MG3 clarification sharpens rather than removes it. MG3 keeps the markdown
read path alive indefinitely, but there is no way for a repo to *declare* it will never migrate — so
`backlog-service-migration-required` nags it forever, routing it toward a migration it will never
perform. The repo has a supported configuration; it has no way to say so.

### F5 — CC5 out-of-band reconciliation gaps. **[BKL-9J3F, open]**

Affects S-C. **CC5** — *"the adapter tolerates and reconciles out-of-band human edits made directly in
the [GitHub UI]."* Known gaps: closing an issue as duplicate **in the GitHub UI** silently drops
`superseded_by` (the redirect is read only from the block, never the timeline); a deleted soft-facet
label decodes to `None` with no warning. Both are silent-wrong-data, the class F1 exists to catch.

### F6 — No retry budget on a `retryable: true` envelope. **[BKL-4H8P, open]**

Affects S-B and S-C. Observed live: a forked skill burned 23 attempts over 5+ minutes against GitHub
503s. A hang, not wrong data — but during a paced ~900-issue migration it is the difference between a
slow run and an apparently-wedged one (compounds with **BKL-8K2N**, the unbuilt progress heartbeat).

### F7 — `--help` exits 2. **[BKL-2D8N, open]**

Affects S-C and S-D discoverability. Minor, cheap, and the only source of truth for a subcommand's
flags is currently `adapter-mode.md` plus the source.

---

## Ruled out of the gate (recorded so they are not re-litigated)

| Item | Why it does not gate |
|---|---|
| **BKL-2K8V** — `pick` ~12.4 s at 209 issues, ~6× the NFR §4 floor | **NFR.** Owner ruling 2026-07-28 defers performance. W1 stays out. **Release-note obligation:** state the number so a dogfood session does not rediscover it as a surprise. |
| **AG4** — no local write queue | **NFR-A** (availability/degradation) per the NFR doc; owner ruled it lags. Verified absent — the `queue`/`flush`/`offline` matches in `plugin/lib/backlog/` are a text formatter, the migration checkpoint writer, and the offline review artifact. **Release-note obligation:** in a migrated repo a GitHub outage means no backlog at all — no reads, no writes, no fallback. |
| **MIG-3** — native-graph reconstruction unproven live | Not reachable from any supported scenario. The importer maps `related:` to no native edge, and markdown cannot express native relationships, so no migration path exercises it. Export fidelity (MG2) is separately covered. |
| **ID-4** — `node_id` across transfer | `transfer` is a W3 op, not in the slice. |
| **XP1–XP7, PV3/PV4** | S-F is out of scope (Chunk 08 deferred). |

## Dismissed on reading (grep said gap; the code said otherwise)

- **GV8's probes are not a silent no-op.** All three carry explicit `post_cutover` guards with
  explanatory comments. The gap is that they *retire* rather than *survive* — a different, smaller,
  and honestly-documented defect. Recorded because the first pass of this audit got it wrong.
- **`backlog_probes` markdown reads are not a cutover bug.** They are MG3's required behaviour — the
  markdown read path must keep working for un-migrated repos.

---

## Recommended gate-2 acceptance set

1. **`verify-api` runs green** against a throwaway repo, with the shape-diff recorded (F1). ⟵ *the one
   that actually changes what we know*
2. **Chunk 01 VRFs** drained (VRF-005/007/008).
3. **Chunk 06** migration + VRF-006: `get`/`list`/`pick` resolve real ids, counts reconcile, a re-run
   creates no duplicates.
4. **F3's parsing half** shipped — `owner/repo#number` recognized by the citation surfaces.
5. **Owner ruling on F2** (GV8 retirement: block, or declare in the release note).
6. **F4, F5, F6, F7** dispositioned — each either fixed or explicitly accepted with a release-note
   line. None is currently scheduled in any chunk.
7. **Dogfood period** on prawduct's own migrated backlog with no markdown fallback.
