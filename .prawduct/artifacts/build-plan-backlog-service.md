---
artifact: build-plan
version: 2
scope: backlog-service-v1
depends_on:
  - artifact: product-brief          # documentation/backlog-service-prd.md (PRD v4)
  - artifact: requirements           # documentation/backlog-service-requirements.md
  - artifact: data-model             # documentation/backlog-service-data-model.md (v3)
  - artifact: nonfunctional-requirements  # documentation/backlog-service-nfr.md (v2)
  - artifact: security-model         # documentation/backlog-service-security-model.md (v2)
  - artifact: api-contract           # documentation/backlog-service-api-contract.md (v3)
  - artifact: test-specifications    # documentation/backlog-service-test-specifications.md (v3)
last_validated: 2026-07-16
---

# Backlog Service — Build Plan

`status: draft v2 — independent-review fold (2026-07-16): a fresh-eyes build/sequencing critic + a
coverage/traceability verifier reviewed v1 (the two-reviewer pattern the five sibling drill-downs
used). BLOCKING/MAJOR fixes folded — (1) security-negative coverage was unallocated: SEC-1/2/3 now
land in Chunks 01–02, SEC-5/6 in Chunk 04, and PV1/PV2 join the traceability table (Complete
Delivery); (2) `verify`/TF2 was fully dropped — now a roadmap row (Wv) carrying CRASH-5; (3) Chunk 06's
scrub silently depended on deferred `merge`/`search --like` — `merge` pulled into the slice (Chunk 05),
scrub restated to model-surfaced dedup over `list`; (4) two wrong-section Data-Model citations (§7→§6
cache/snapshot, §6→§1.6 attachments) corrected; CRASH-3 (split) mis-cited in Chunk 05 → CRASH-4. Chunk
01 de-loaded (raw-HTTP → W1; provision trimmed to minimal); SPIKE-S2 isolated to Chunk 06; Chunk 04
demoted to `chunk` mode (review-wall-clock). Owner decisions folded: `lib/backlog/` built from the
start (`lib/backlog.py` → `lib/backlog/legacy.py`); CLI home = `prawduct-hook backlog`; prawduct's own
briefing repoints at Chunk 06 (post-migration), not before. Three peer-doc coherence debts filed **and
swept the same session** (§ "Coherence debts" — API §1 CLI spelling, Data Model export-representation
pointer, API §2.5/MIG-5 scrub op-dependency). Prior v1: initial drill-down from PRD §16 item 6. · added: 2026-07-16 · source:
planning session · stage: design · **PROMOTED 2026-07-16** to the active build plan
(`active_build_plan → artifacts/build-plan-backlog-service.md`); the Stop-hook Critic gate is armed.
Chunk 01 (walking skeleton) built + committed; branch reconciled with develop (v3.0.4), offline suite green (1887 passed), Critic re-review clean (0 blocking). Live round-trip verified live 2026-07-17 (operator-verification VRF-004). **Design CONDITIONALLY signed off 2026-07-17** (owner) after pre-sign-off scenario tracing of the CC5/G2/rate seams (three parallel traces, verified in code): the design holds with no flaw; four build-completeness gaps filed (BKL-4W7H/8P2R/3K9N/6X5D). BKL-4W7H (PFX read-resolution + alias idempotency) and BKL-8P2R (safe briefing/gate wiring + real-slowness test) are folded into Chunk 06 as must-fix-before-done; BKL-3K9N (mid-import 429 Retry-After) recommended before the live run; BKL-6X5D is adopter-scale. **BKL-3K9N (rate-limit backoff) + BKL-7Q2N (bare-PFX resolution across all single-id mutators + merge) landed 2026-07-17** (857587d; offline, fake-transport-tested, Critic Goals 1-3 clean) — the pre-live de-risking is done. Remaining before/at cutover: BKL-8P2R (briefing/gate repoint — activate when prawduct's backlog is on Issues) and the BKL-6M4T live run (SPIKE-S2 → real migration → repoint → retire). Next: SPIKE-S2 on a throwaway repo (owner-in-the-loop).`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4) and, through it,
`documentation/backlog-service-requirements.md`. This plan is the **last level** of the layered
plan (PRD §16 item 6): it consumes the five sibling drill-downs and turns *what the system must do*
into *the order in which we build it and prove it*. It designs against their IDs (AG/CC/TF/Q/XP/
PV/AU/GV/MG/DM/NF and the test IDs INV/ENC/CRASH/ID/…), never restating them.

**Altitude — plan, not code.** This plan fixes *what to build in what order*, *which artifact each
chunk consumes*, and *which named test IDs each chunk's "done when" must satisfy* — **not** function
names, assertion syntax, or field layout (those are build-time, chosen by the Builder against
`project-preferences` and the Data Model). A chunk is specific enough when the Builder never has to
make a **technology** decision; the seams below are already decided upstream (transport = `gh`, O5;
errors = return-value envelope, API §4; isolation = transport-seam fake, Test Specs §2.1).

**Promotion — done 2026-07-16.** Authored during the design phase in `documentation/` alongside its
five siblings (`documentation/backlog-service-*.md`), this plan was **promoted** on completion of the
v2 fold + coherence sweep: moved here to `.prawduct/artifacts/build-plan-backlog-service.md` and
pointed at by `active_build_plan` (so the Stop-hook Critic gate arms on it). The five sibling design
docs stay in `documentation/`; this plan references them by section throughout. It remains a *design
artifact pending owner sign-off* — **Chunk 01 (the walking skeleton) is now built and reviewed**
(offline-verified, 0 blocking Critic findings; the live round-trip is verified — VRF-004) — and the
tooling treats it as the active plan. (PRD §16 item 6 named `.prawduct/artifacts/` as the destination; the design-phase copy in
`documentation/` graduated here.)

---

## Requirements Confidence

**Level:** High (for the slice) / Medium (for the post-slice roadmap).

**Why High for the slice.** The slice's problem, success criteria, and scope are each statable in
one sentence and are pinned by a coherent, independently-reviewed parent set:
- *Problem:* the backlog is a merge-prone markdown file an LLM edits by hand → stale-by-checkout,
  token-costly, conflict-prone (PRD §1, requirements doc).
- *Success:* one live view, zero merge conflicts, zero-token deterministic CRUD, online-consistent
  `pick`, and prawduct's own backlog migrated with IDs preserved (PRD §4, §6).
- *Scope:* the cacheless online CLI over GitHub + the prawduct-first migration; **not** the #1
  stale-*content* pain (that needs TF2/TF3 + the scrub, honestly out of the slice — PRD §6/B1).

No fast-moving or post-cutoff facts remain unverified: the load-bearing GitHub facts (number
non-reuse, the 80/min + ~500/hr write caps, read-your-writes on the REST list endpoint, native
deps/sub-issues GA dates, semantic-search GA) were verified during the NFR/API/Test-Spec drill-downs
and are pinned in those docs. Two once-only spikes (S1, S2) fold into the slice as `verify-api`/
dry-run steps rather than gating unknowns.

**Why Medium for the roadmap.** The post-slice layers (cache, search, verification/grooming,
cross-project, attachments, MCP, App identity) are specified at PRD altitude and deliberately **not**
chunked to code-level here — each is detailed when its layer is reached (proportional effort;
over-specifying deferred work is a named trap). S4 (cache protocol) and S5 (attachment
inline-on-private) are genuinely open and gate their layer, not the architecture.

**Resolved decisions (were v1 assumptions; ruled by the owner 2026-07-16):**
- **Package = `lib/backlog/` from Chunk 01.** `lib/backlog.py` (the markdown-backlog parser) moves to
  `lib/backlog/legacy.py`; its importers (`lib/briefing.py`, `lib/backlog_probes.py`) and their tests
  repoint to the new path in Chunk 01 so the suite stays green. The markdown-backlog *mutation workflow*
  is **not maintained** during the build (breaking it is accepted) and is retired when prawduct's own
  backlog cuts over (Chunk 06); but `legacy.py`'s **read-only `parse_backlog`** stays live afterward as
  the **shared plugin's markdown read path** (briefing counts + advisory probes for un-migrated portfolio
  repos), retired only at **portfolio-wide migration** (MG3/GV7) — not at any single repo's cutover. This
  makes the Data Model / API contract `lib/backlog/…` paths literally true from day one.
- **CLI home = `prawduct-hook backlog <op>`** — a subcommand group on the existing entry (matching the
  `sys.argv[1]` dispatch → a `lib/backlog/cli.py` runner, the `advisory`/`init-product` pattern), not a
  new `bin/` binary. Rationale: one entry point = one platform-exposure/executable/PATH surface (fewer
  places a platform quirk bites); lazy per-subcommand import means zero startup cost on other commands;
  the durable contract is the flags + JSON envelope + on-GitHub encoding, not the binary name (API §5).
  *Coherence debt filed:* the API contract §1 spells the surface `prawduct backlog` — reconcile to
  `prawduct-hook backlog` in the peer-doc sweep (see "Coherence debts").

**Open assumptions / unknowns** (vetoable):
- [ASSUMPTION: this plan details the slice (Chunks 01–06) fully and the widening (W1–Wv) as a roadmap;
  the widening chunks are authored to code-level when their layer is picked up. | LOW impact | owner
  can override — e.g. ask for a fully-chunked P1 cache plan now.]
- [ASSUMPTION: SPIKE-S2 runs first against a **throwaway copy** of prawduct's own repo (Chunk 06 step 0),
  then the **real** prawduct migration executes; discodon follows post-slice as an operational re-run of
  the same importer. | LOW impact | owner can override the order/targets.]

**What would raise confidence:** N/A for the slice — the two former MED assumptions are now owner
rulings. The roadmap stays Medium by design until each layer's workload justifies building it.

## Status

- [ ] Chunk 01: Walking skeleton — package + `legacy.py` move, `gh` transport seam + fake, `file`, `get`, minimal `provision`, one real round-trip
- [ ] Chunk 02: Two-axis status + decoder + self-healing reconciliation (the CC1/M5 keystone)
- [ ] Chunk 03: Query & ready-work — `link`/`unlink`, `list`, `pick`, `claim`/`unclaim`, `counts`
- [ ] Chunk 04: Governance surface — `refresh-counts`, `reconcile-labels`, never-block floor, unattended security *(built 2026-07-17; `[ ]` until release per the views convention)*
- [ ] Chunk 05: Importer + alias machinery + minimal `merge` + `export` (mechanism, fixture-proven)
- [ ] Chunk 06: SPIKE-S2 dry-run + MG4 scrub + prawduct-first real migration (dogfood, cumulative-final)
- [ ] Roadmap (post-slice, lower resolution): W1 cache+sync · W2 search+dedup · Wv verify+grooming · W3 cross-project+automation · W4 attachments · W5 MCP · W6 App identity + offline queue · Wg GV3 janitor
Context: Draft v2 authored 2026-07-16 (v1 + two independent reviews folded; the 3 peer-doc coherence
debts swept the same session). Chunks 01–03 built + committed 2026-07-17: Chunk 01 the walking
skeleton (VRF-004 live-verified), Chunk 02 the two-axis status state machine (crash-safe `set-status`,
`update` with optimistic CAS + mass-assignment guard + block-preserving body edits, `comment`; live
status path queued as VRF-005), Chunk 03 query & ready-work (new `lib/backlog/query.py`: `list`/`pick`/
`counts` online off the REST list endpoint; `claim`/`unclaim` atomic take-and-verify + TTL-reap;
`link`/`unlink` native deps + sub-issues + block-list `related`; PROV-2; 404-after-create settle;
live `list`/`pick` queued as an L5 smoke). Chunk 04 governance surface built + committed 2026-07-17
(new `lib/backlog/snapshot.py`: the GV2 `briefing_counts` degenerate cache at
`<git-common-dir>/prawduct/backlog-counts.json` — atomic write, visible-age read, network-independent,
schema-versioned, disposable; new `lib/backlog/context.py`: unattended detection + the SEC-5 Actions
pwn-request guard, both env-resolved and pure; `refresh-counts` in `query.py` — derive+persist,
never-clobber-on-backend-down; `reconcile-labels` in `provision.py` — GV6 coexistence reconcile
(create-missing, foreign labels untouched, never-delete, idempotent); the SEC-5 write-withhold at the
CLI boundary + the SEC-6 `automated`/`worker` marker on unattended creates; the D6 detached-refresh
warm as `transport.spawn_detached` — the egress-discipline invariant kept subprocess in `transport.py`.
Data Model §2 gained the `automated`/`worker` block fields — closing the coherence gap where Security
§1a mandated the marker but no field home was pinned. Offline suite green (2085 passed, +36); Chunk 04
Critic (chunk mode) 0 blocking / 0 warning / 1 note — the note (fork-PR detection keyed off a
workflow-surfaced signal, not a native Actions var) resolved: renamed to `PRAWDUCT_PR_HEAD_REPO`,
documented the required wiring at the read site, filed **SEC-8R3K** for the Chunk-06 Actions wiring;
`verify-resolutions` clean. **L5 smokes queued** (live `gh`): `refresh-counts` against a throwaway
repo, and the SEC-5/6 behaviors under a real Actions context. Chunk 05 (importer + alias machinery +
minimal `merge` + `export`) built + committed 2026-07-17 (`final` mode): a new `lib/backlog/migrate.py`
— `import` (idempotent/resumable, keyed on the permanent `id:PFX` alias written **atomically in the
create** so a crash still converges via the label query; a durable `Checkpoint` accelerator; no
rollback — M6), the alias machinery in `ids.py` (`PFX-XXXX`→`id:PFX` label + `id_aliases` block +
`resolve_redirect`), a minimal `merge` (fold A→B, **redirect-before-close** — CRASH-2, block-authoritative
`superseded_by`, nothing hard-deleted), `export` (full-fidelity JSON dump incl. the native graph:
deps/sub-issues/timeline/assignees — layout pinned in Data Model §8), and a write-`Pacer` (content
budget 80/min+500/hr, injectable clock). Transport+fake gained `list_sub_issues`/`list_timeline`;
`encode.decode_item` now surfaces `superseded_by`; `import-key:` idempotency marker added for id-less
items (Data Model §5). CLI: `import`/`export`/`merge`. Offline suite green (2134 passed, +49; a
human-mode output-shadowing bug on `export` caught by driving the CLI at Verify and fixed + regression-
tested). Design decision: a *create* failure aborts import (content budget, resumable); a *status-
reconcile* failure defers to a warning (core budget, transient — the re-run converges). **L5 smokes
queued** (live `gh`): `import`+`export` round-trip, `merge`, and the Done-when-0 blocker check (link a
real blocker → `pick` excludes it — confirms the `blocked_by` read shape Chunk 03 built against the
fake only). The `[ ]` boxes above stay unchecked by design — `regen-views` flips them to `[x]` only at
release. Still a design artifact **promoted 2026-07-16**; owner sign-off pending. **Chunk 06 —
offline deliverables landed 2026-07-17** (the live migration is deferred, by owner decision, to an
owner-driven session after design sign-off; the chunk therefore stays `[ ]` — its acceptance requires
the live dogfood): the **MG4 scrub workflow runbook** (`skills/backlog/migration-scrub.md` + a `### scrub`
pointer in the backlog SKILL) — model surfaces stale/dup candidates from `list`, owner confirms, the
deterministic `status`/`merge`/`import` ops apply the cleaned set (the model is in the *decision*, never
the data plane — API §2.5); the **MIG-5 test** (`TestScrubDataPlaneBoundary`, 3 L1 cases — disposition
plan is data, nothing hard-deleted/DM7, disposal touches only named items, import op typed to consume a
concrete record set; module-level model-freedom stays INV-1's job); and the **SPIKE-S2 spike script**
(`tests/spikes/s2_migration.py`, L4 dev-only, `gh`-live, refuses without `--repo`+`--yes`, not collected
by CI — fidelity/aliases/relationships/resume/pick-latency/node_id-across-transfer). Offline suite green
(2144 passed, +3). **Deferred to the owner-run session (tracked, not dropped):** SPIKE-S2 live run,
the real prawduct migration, the briefing/gates repoint to the adapter, and the `legacy.py` +
`incoming-bugs/` retirement — filed as a backlog item and queued as **VRF-006**. Next: owner sign-off →
the live migration session (SPIKE-S2 → real migration → repoint → retire), which completes the chunk and
runs the single `cumulative` review that gates the slice PR. **BKL-8N5K (MG6 restructure pre-pass)
built 2026-07-17**: `lib/backlog/restructure.py` (fail-closed plan validation, apply through the
shared `issuefmt` composer, verbatim `original_*` preservation via `encode.format_text`), `import
--restructure` + offline `restructure-preview` (the aggregate owner-review artifact, rendered from
the same apply path the import consumes); the MG1/MG6 reconciliation folded into this plan, the
test specs (MIG-6), Data Model §2, API §2.5, and the scrub runbook (step 2b). Critic `final`
(0 blocking / 4 warn) + two `verify-resolutions` → clean; suite 2263. **BKL-8P2R built 2026-07-18**
(must-fix #2): the briefing's backlog rollup is cutover-aware on the `backlog_service_repo`
project-state scalar (API §2.4) — set: `snapshot.read` file-only + visible age + detached
`spawn_refresh` warm (never-block is structural; no sync network on the briefing path); unset:
markdown behavior unchanged. All six markdown-premise advisory probes (backlog trio + norm trio)
retire on the same switch; `encode.OPEN_STATUSES` derived from the status SoT; runbook step 5
"Cut over" is the switch's writer. Critic `final` (0 blocking / 5 warn) + `verify-resolutions` →
clean; suite 2276. **The live-session "repoint" leg now reduces to writing the one cutover key**
(the code is prebuilt behind the switch). **Both pre-migration transport blockers from the 2026-07-18 holistic review shipped 2026-07-18**:
BKL-2V6N (`_api_paged` explicit page loop replaces `gh --paginate` in labels/timeline/sub-issues)
and BKL-5T3J (raw pages from `list_issues`; terminators read raw length; PRs leave at
`encode.is_pull_request`/`is_prawduct_issue` + explicit guards on label-keyed lookups; `list`
gains raw-derived `has_more`, per_page clamped) — **both live-verified read-only against
brookstalley/prawduct** (multi-page label walk set-identical; 128 raw / 122 PRs walked fully; the
old filtered terminator demonstrably stopped at page 1 with 4 of 128). BKL-5R2K shipped in the
same chunk (`core.resolve_survivor` → `get` resolves_to + warning + human breadcrumb; `pick`
excludes open-but-redirected). Critic `final` (0 blocking / 5 warn) + two `verify-resolutions` →
0/0/0; suite 2300. **Owner-feedback pass 2026-07-18** (this session — four PRD/owner-review gaps closed
offline ahead of the live leg): the `--archive-scope {all,open}` lever (MG4b), `prawduct-hook version`
(XP2 provenance source), the `issuefmt` Env/version nudge (self-filed provenance), and the
`backlog-service-migration-required` advisory + the `legacy.py` retirement-gate correction (MG3/GV7).
Remaining before the chunk closes: the owner-driven live migration (scrub dispositions + restructure plan
+ import + cutover key per runbook step 5), and the `incoming-bugs/` drop-box retirement (MG5 lockstep) —
**`legacy.py` is NOT retired here** (MG3/GV7: it stays the shared markdown read path until portfolio-wide
migration).

## Scaffolding

### Project Initialization

No new project — the service is built **into the existing prawduct plugin repo** (Python 3.10+, the
established `bin/` + `lib/` + `tests/` layout). No new package manager, no new runtime. Dev deps are
already present (`pytest`, `pytest-xdist`, `pytest-timeout`, `pyyaml` via `pyproject.toml`). The one
external **runtime** dependency the slice adds is **`gh`** (the GitHub CLI) as the required portable
transport (O5, G4) — free, standard, `brew`/`apt`-installable, and already present in most adopter
environments; the adapter probes for it and degrades cleanly when absent (G2).

### Dependencies

- **Runtime:** `gh` (required transport, O5). Stdlib only otherwise — `subprocess` (list-form, no
  `shell=True`), `json`. The raw-HTTP fast path and `sqlite3` cache arrive with **W1**, not the slice.
  **No new third-party Python packages** in the slice.
- **Dev/test:** the existing pytest stack. The **transport-seam fake** (Test Specs §6) is first-party
  test code, not a dependency.

Rationale per the "no bespoke backend" invariant (G4) and the sync/no-asyncio, return-value
conventions (`project-preferences`). A dependency-manifest entry for `gh` is the one addition; if the
project adopts a formal `dependency-manifest.md`, `gh` is its first backlog-service row.

### Build & Test Configuration

The existing `pytest tests/ -v` runs everything; new tests live under `tests/` organized by
capability (`test_backlog_*.py`), with the five L-layers (Test Specs §2) mapped as:
- **L1 (deterministic)** — the CI-fast bulk; runs every `pytest` invocation against the transport-seam
  fake. Hermetic, offline, no `gh`, no network.
- **L2 (contract probe, `verify-api`)** — a **marked, opt-in** target (e.g. `-m verify_api`) that hits
  a throwaway real repo; **not** in the default CI run. Produces the recorded shapes CONTRACT-1 diffs
  the fake against.
- **L3 (build measurement, PROBE-LAT/PROBE-RATE)** — a marked measurement target run at chunk-close
  before "done"; emits numbers vs the NFR targets, not pass/fail.
- **L4 (spikes S1/S2)** — one-time scripts under `tests/spikes/`, run by hand during the slice; their
  output is a settled fact recorded in the plan/NFR, not a CI test.
- **L5 (live smoke + behavioral re-check)** — a marked, gated target (one real round-trip per front)
  run pre-release/nightly, never in the fast loop.

The default `pytest` run must stay **green with no `gh` and no network** — L2/L3/L4/L5 are all opt-in.
This is the honesty line Test Specs §2 draws: the deterministic bulk never depends on a live GitHub.

### Scaffold Verification

After Chunk 01: `pytest tests/test_backlog_*.py` passes offline against the fake **and** the existing
suite stays green after the `lib/backlog.py` → `lib/backlog/legacy.py` move (briefing + probes
repointed); one real `prawduct-hook backlog get <known-issue>` round-trips against a live throwaway
repo (the L5 smoke). All green = the layers connect and the rename didn't regress the framework.

### Verification Strategy

Each chunk is exercised **as an agent would drive it** — non-interactively through the CLI, parsing
JSON from stdout (INV-2: stdin closed, no TTY). Beyond the L1 suite:
- Every slice chunk adds a **one-real-op L5 smoke** through the CLI front against a throwaway repo,
  so "the adapter wires the core correctly" is proven per front, not assumed (Test Specs §1.1 — a
  core-only test does not prove the CLI).
- The **migration** chunks (05/06) are verified by the **SPIKE-S2 dry-run** (body-fidelity diff, ID
  aliasing, relationship reconstruction, resumability) and then by the **real prawduct migration**
  itself — the dogfood is the acceptance test (owner reviews the scrub dispositions and the migrated
  repo; **Visual change: yes**).
- **L3 probes** (PROBE-LAT, PROBE-RATE) run during Chunks 05/06 to promote the NFR latency/rate
  targets from `target` to measured. *Caveat (NFR §3.3):* the prawduct-first burst is **smaller** than
  discodon (that's why it goes first) — so it is a **lower bound** on the ~500/hr content-creation
  pacing constant; that constant stays `target`-grade until a larger burst (discodon, post-slice) runs.

Verification infrastructure (the fake, the spike scripts, the throwaway repo) is **dev-only** and
never ships in the plugin runtime (Principle 10).

## Project Structure

```
lib/backlog/                    # the service package (built from Chunk 01)
├── __init__.py
├── legacy.py                   # ← moved from lib/backlog.py (markdown parser; read path survives to portfolio-wide migration — MG3/GV7)
├── transport.py                # the only egress: gh-subprocess driver (raw-HTTP fast path → W1)
├── core.py                     # deterministic CRUD (G1); return-value envelope; the op implementations
├── encode.py                   # prawduct: body block, two-axis status decoder/encoder, soft-enum
├── ids.py                      # ID normalization, PFX alias resolution, redirects (D4)
├── query.py                    # list / pick / counts (structured, online off the REST list endpoint)
├── migrate.py                  # import (resumable/idempotent), export (full-fidelity graph), merge
├── provision.py                # namespaced label taxonomy + coexistence reconcile (GV5/GV6)
└── cli.py                      # the `prawduct-hook backlog <op>` runner (thin front over core)

bin/prawduct-hook               # +1 dispatch line: `backlog` → lib.backlog.cli.run
lib/briefing.py, lib/backlog_probes.py   # importers repointed to lib.backlog.legacy (Chunk 01)
tests/
├── test_backlog_*.py           # L1 bulk, per capability
├── fakes/fake_github.py        # the stateful transport-seam fake (Test Specs §6)
└── spikes/                     # L4 one-time spike scripts (S1, S2) — dev-only
```

### Module Boundaries

- **`transport.py` is the sole egress.** No other module shells out or opens a socket. This is the
  **primary test seam** (Test Specs §2.1): L1 injects `fakes/fake_github.py` here. Enforces O5 (gh
  required; raw-HTTP fast path deferred to W1) and subprocess safety (list-form, no `shell=True`).
- **`core.py` holds all CRUD logic; the CLI/MCP fronts are thin.** A test that exercises only `core`
  proves the logic, not the front (Test Specs §1.1) — hence the per-front L5 smoke.
- **The model client never touches the data plane (G1/INV-1).** No module under `lib/backlog/` imports
  or calls a model; the scrub's model-assisted step (Chunk 06) lives in the *skill/workflow* layer and
  hands `core`/`migrate` a concrete cleaned set, never a model call (MIG-5).
- **Return-value errors; exceptions only at the CLI boundary** (`cli.py` `run()`), per
  `project-preferences` "Error handling" and API §4.
- **`legacy.py` is inert (read-only) during the build.** After the Chunk 01 move it is imported only by
  `briefing.py`/`backlog_probes.py`/`norm_probes.py` (repointed) and its own tests; the
  markdown-backlog *mutation* workflow is not extended. Its read-only `parse_backlog` **survives Chunk 06**
  as the shared markdown read path for un-migrated portfolio repos (MG3/GV7); full retirement waits for
  portfolio-wide migration, not prawduct's own cutover.

## Build Chunks — the thin slice

> The slice is the PRD's buildable increment: **core lib → CLI → one GitHub round-trip → prawduct-
> first scrub + importer dry-run** (§16 item 6). Chunk 01 is a thin vertical through *every* layer;
> each later slice chunk widens one coherent capability. Every chunk commits before the next (the
> per-chunk-commit contract that scopes `chunk`-mode Critic reviews). Paths the chunk **creates** are
> prefixed `new`.

### Chunk 01: Walking skeleton — package move + `gh` seam + `file` + `get` + minimal `provision`

- **Description:** Prove the whole path end-to-end at its thinnest: file an item, read it back — CLI →
  `core` → `transport` → GitHub → back — with the L1 fake for the deterministic suite and **one real
  round-trip** for the L5 smoke. Establishes the load-bearing seams every later chunk builds on: the
  package (with the former `backlog.py` relocated to `legacy.py` and importers repointed), the `gh`-only
  transport driver, the stateful fake, the return-value envelope + error model + exit-code scheme, ID
  normalization, the `prawduct:` block parse/serialize, and a **minimal** `provision` (create the
  namespaced labels `file` needs, idempotent, no-collision — PROV-1 only; the GV6 drift-reconcile and
  PROV-2 list-ignore land later). Architecture-validation keystone.
- **Depends on:** none
- **Artifacts consumed:** API §2.1 (`file`,`get`), §2.5 (`provision`), §3–§4 (envelope + error model),
  §5 (versioning); Data Model §1.1 (Item), §2 (block), §3 (labels), §5 (IDs/aliases); Security §1/§1a
  (identity validated early, non-interactive), §5 (attribution off the API identity); Test Specs §2.1
  (seam), §3.6 (envelope), §3.7 (IDs), §3.5 (block parse), §3.9 (security-negative), §3.11
  (provisioning), §6 (fake).
- **Deliverables:** move the former `backlog.py` → new `lib/backlog/legacy.py` + repoint `lib/briefing.py`,
  `lib/backlog_probes.py`, and their tests (and `lib/norm_probes.py`, whose `.backlog` import arrived
  via the develop merge — repointed to `.backlog.legacy` in the merge reconciliation); new `lib/backlog/__init__.py`,
  new `lib/backlog/transport.py` (gh-only), new `lib/backlog/core.py` (`file`,`get`), new
  `lib/backlog/encode.py` (block + soft-enum), new `lib/backlog/ids.py`, new
  `lib/backlog/provision.py` (minimal), new `lib/backlog/cli.py`, the `backlog` dispatch line in
  `bin/prawduct-hook`, new `tests/fakes/fake_github.py` (stateful transport-seam fake).
- **Tests (L1 unless noted):** INV-1 (zero model on the CRUD path), INV-2 (one non-interactive call,
  no TTY); envelope JSON-sole-stdout / stderr-diagnostics (§3.6); ID normalization idempotence (ID-1,
  §3.7); the block-parse subset — soft-enum tolerance (ENC-1), last-block-wins (ENC-3), tolerant parse
  (ENC-4) — since `file`/`get` build the parser here; **SEC-1** (no token in any output — the envelope
  is built from known fields, never by echoing raw `gh` output, API §4); **SEC-3** (attribution off the
  API identity, not git-push — Security §5); `provision` idempotency + non-collision (PROV-1, §3.11).
  **L5 smoke:** one real `file`+`get` round-trip.
- **Acceptance criteria:** default `pytest` passes **offline, no `gh`, no network**, and the existing
  suite stays green after the `legacy.py` move; one live `prawduct-hook backlog file`/`get` round-trips
  against a throwaway repo; no token appears in any output path.
- **Critic mode:** final
  <!-- Override: this lands the transport-seam + fake + envelope + package-move keystone the entire
       plan rests on — full coherence review before widening. It is the heaviest chunk by design (a
       walking skeleton establishes every seam); de-loaded from v1 by deferring raw-HTTP (W1) and full
       provisioning (Chunks 03/04). -->
- **Foreign API:** gh CLI + GitHub REST/GraphQL
- **Exposed API:** prawduct-hook-backlog-cli (realizes the recorded `api_versioning_approach` +
  `api_error_model_approach` from API §4/§5 — the exit-code scheme aligned with `prawduct-hook`'s
  existing exit conventions)
- **Visual change:** yes — the CLI's JSON envelope + human-mode output format is a consumer contract;
  a human look at the output shape belongs before merge.
- **Done when:**
  0. **verify-api** — probe live `gh`/`api.github.com` for `file`/`get`/label-create/list; capture the
     real response shapes to seed the fake (CONTRACT-1). This step **absorbs SPIKE-S1's core-gating
     confirmations**: ETag/304 conditional-GET works, and issue **numbers are never reused** (M6). The
     cloud-proxy-reach question (raw-HTTP fast-path availability) is an **optimization**, deferred to W1.
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Two-axis status + decoder + self-healing reconciliation (the CC1/M5 keystone)

- **Description:** Land the state machine the whole system depends on: the idempotent **`set-status`**
  primitive (open/closed + `state_reason` + `status:` label across two axes), the **decoder** (fail-open
  precedence, tolerant of `duplicate`/human-UI drift — CC5), the **canonical write-order** + **idempotent
  self-healing reconciliation** (labels re-derived from open/closed + state-reason), plus `update`
  (optimistic CAS → `conflict`, CC2) and `comment`. This is where "a crashed client never half-writes"
  becomes real for compound transitions (M5).
- **Depends on:** Chunk 01
- **Artifacts consumed:** API §2.1 (`status`,`update`,`comment`), §3 (envelope); Data Model §1.1
  (`status`/`stage`/`closed_by` fields), §2 (the block the encoder writes), §4 (state machines —
  idempotent `set-status`); Test Specs §3.5 (encoding), §3.2 (crash-safety), §3.9 (security-negative);
  PRD §8.2 (CC1/CC2/CC5), M5.
- **Deliverables:** the two-axis decoder/encoder in `lib/backlog/encode.py`, `set-status` + `update` +
  `comment` in `lib/backlog/core.py`, the reconciliation routine (re-derive labels from state),
  fault-injection support in the fake (fail the n-th mutating call).
- **Tests (L1):** ENC-2 (two-axis round-trip), ENC-5 (torn-state decode), decoder self-heal on human-UI
  drift (§3.5); CRASH-1 (`set-status` partial-transition recovery: crash mid-transition → re-run
  converges, labels self-heal — §3.2); CC2 optimistic-CAS `conflict` on stale `updated_at`; **SEC-2**
  (mass-assignment guard — `update`/`status` write only the fields the caller named, never
  attacker-supplied extras, §3.9). **L5 smoke:** one real `status` transition round-trip.
- **Acceptance criteria:** a crash injected between the two axes of a status transition leaves a
  *resolvable* state and a re-run converges idempotently (no half-write survives); a human-made label/
  state edit is reconciled, not rejected; `update` cannot write an unnamed field.
- **Critic mode:** final
  <!-- Override: the state-machine keystone — its coherence must hold before Chunks 03–06 build on it. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Query & ready-work — `link`/`unlink`, `list`, `pick`, `claim`/`unclaim`, `counts`

- **Description:** Rescue the `/prawduct:backlog pick` UX in the slice, online and consistent. Build
  `list` (structured field/label filters, sort, paginate — **online off the REST list endpoint**,
  read-your-writes-in-practice), `pick` (ready-work: `open ∧ stage:ready ∧ unassigned` via `list`, then
  a **per-candidate fan-out** — implemented as a **batched-GraphQL** round-trip — for "no open blockers"
  + "claim past TTL"), `link`/`unlink` (native dependencies + sub-issues, so blockers are queryable —
  DM3), `claim`/`unclaim` (atomic take-and-verify + default staleness-TTL reap so `pick` can't starve —
  CC3/M11), `counts` (rollups derived on read), and PROV-2 (`list`/decode ignores non-prawduct issues
  as out-of-scope, except the anonymous-quarantine case).
- **Depends on:** Chunk 02
- **Artifacts consumed:** API §2.2 (`list`,`pick`,`counts`), §2.3 (`link`/`unlink`), §2.1 (`claim`);
  Data Model §4 (ready-work list-then-fan-out), §1.1/§1.4 (assignee/TTL); Test Specs §3.8 (query
  semantics), §3.2 (claim race — CRASH-6), §3.11 (PROV-2); PRD §8.3 (Q1-structured/M8), §8.2 (CC3/M11),
  §8.7 (GV1).
- **Deliverables:** `lib/backlog/query.py` (`list`,`pick`,`counts`), `link`/`unlink` + `claim`/`unclaim`
  in `core.py`, the ready-work batched-GraphQL fan-out, the claim-TTL reap policy, PROV-2 decode filter.
- **Tests (L1):** §3.8 query-semantics (structured filter/sort/paginate; the **observed** — not
  documented — 404-replication-window-after-create handled via the fake's replication-window mode, an
  L5-owed behavior); `pick` returns ranked candidates + *why* and honors blockers/TTL; CRASH-6 (claim
  double-take race → `claim_conflict`, non-fatal, §3.2); PROV-2 (non-prawduct issues ignored, §3.11).
  **L5 smoke:** one real `list`/`pick` round-trip.
- **Known forward dependency:** `pick`'s < 2 s latency floor assumes the **batched-GraphQL** fan-out
  (an N+1-REST-over-`gh` fan-out blows 2 s at 3–5 candidates, NFR §4 open-Q4). This chunk implements the
  batched path; its measured floor (PROBE-LAT, candidate-parameterized) is **pinned by SPIKE-S2** in
  Chunk 06 — noted here as a forward dependency, not a gate (correctness holds either way).
- **Acceptance criteria:** `prawduct-hook backlog pick` returns the correct ready-work set (blockers
  closed, unclaimed, `stage: ready`) online with no cache, matching the current skill's contract (GV1).
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Governance surface — `refresh-counts`, `reconcile-labels`, never-block floor, unattended security

- **Description:** Build the governance capability (tested, not yet wired to prawduct's own briefing —
  that repoint is Chunk 06, post-migration, when prawduct's backlog is actually on GitHub Issues).
  `refresh-counts` (the `briefing_counts` snapshot — a degenerate cache with visible age so session
  start never waits, GV2/M3), `reconcile-labels` (the GV6 label-drift/coexistence reconcile deferred
  from Chunk 01), the **never-block floor** (G2/AG4: a backend failure returns a clear retryable
  `unavailable`, gates/hooks tolerate it, nothing hangs or corrupts), and the **unattended security**
  behaviors (SEC-5 Actions-withhold, SEC-6 unattended-fail-clean).
- **Depends on:** Chunk 03
- **Artifacts consumed:** API §2.4 (`refresh-counts`), §2.5 (`reconcile-labels`); Data Model §6
  (`briefing_counts` snapshot — the P0 persisted-counts floor), §3 (label taxonomy/coexistence);
  Security §1a (unattended), §1b (Actions untrusted triggers); Test Specs §3.4 (never-block / graceful
  degradation), §3.3 (freshness / visible age), §3.9 (SEC-5/SEC-6), §3.11 (reconcile); PRD §8.7
  (GV2/GV5/GV6), §5 (G2/G3).
- **Deliverables:** `refresh-counts` + the detached briefing-refresh subprocess (D6 — sync core,
  subprocess warm, no asyncio), `reconcile-labels` in `provision.py`, degradation handling on the
  transport error path, the unattended-context guards.
- **Tests (L1):** §3.4 never-block (backend down → fail-fast retryable `unavailable`, no hang; gates
  tolerate it); §3.3 visible-age on any snapshot read; SEC-5 (Actions context withholds
  broad-token operations), SEC-6 (unattended failure is clean, never a hang or a half-write); GV6
  reconcile leaves existing non-prawduct labels untouched. **L5 smoke:** `refresh-counts` writes a
  snapshot against a live repo.
- **Acceptance criteria:** with GitHub unreachable, `prawduct-hook backlog` ops fail fast with a clear
  retryable error and a snapshot read still returns (with visible age) — never a hang, never a crash,
  never a corrupt write; label reconcile is drift-correcting and collision-free.
- **Critic mode:** chunk
  <!-- Demoted from v1's `final` (review-wall-clock is P0): nothing structurally builds on this chunk's
       coherence the way 02→03 does; cross-file coherence is caught by the Chunk-06 cumulative pass. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Importer + alias machinery + minimal `merge` + `export` (mechanism, fixture-proven)

- **Description:** Build the **highest-risk operation** and its exit, proven on fixtures (the live spike
  is Chunk 06). `import` (`backlog.md` + archive → issues): **idempotent, resumable**, keyed on the
  `id:PFX` alias (skip-if-exists), durable checkpoint, **no "rollback"** (GitHub never reuses numbers —
  recovery = re-run into the same repo, M6). The **alias machinery** (`PFX-XXXX` → permanent `id:PFX`
  alias label + body-block entry + redirects, D4/M4). A **minimal `merge`** (fold A→B: preserve both
  bodies, write the `superseded-by:` redirect **before** closing the source — the MG4 scrub in Chunk 06
  needs it to dispose duplicates; AU3/DM7). And `export` — full-fidelity dump serializing the **native
  graph** (deps, sub-issues, timeline, assignees), a cheap dump not lossless re-import (MG2/G5/M10).
  *`export` stays in this chunk with `import`* because the MIG-1 test is an `import`→`export`→diff
  round-trip — they are tested as a pair.
- **Depends on:** Chunk 02 (encoding), Chunk 03 (relationships for graph export + `link`)
- **Artifacts consumed:** API §2.5 (`import`,`export`), §2.3 (`merge`); Data Model §5 (`id:PFX` alias,
  checkpoint), §1.1/§1.3/§2 (what `export` serializes — the block + native graph), §8 open-Q5 (the
  on-disk export **layout** is a build-time decision here, bounded by the NFR §8 fidelity contract —
  resolved in the coherence sweep); NFR §3 (write pacing — 80/min + ~500/hr), §8 (export fidelity);
  Test Specs §3.10
  (MIG-1…MIG-4), §3.2 (CRASH-4 resumable import; CRASH-2 merge redirect-before-close); PRD §8.9, §11-S2.
- **Deliverables:** `lib/backlog/migrate.py` (`import`,`export`), the minimal `merge`, alias/redirect
  resolution in `ids.py`, the durable checkpoint, write-pacing (respect 80/min + ~500/hr).
- **Tests (L1):** MIG-1 (verbatim body/ID/section fidelity via the `import`→`export` round-trip —
  *the no-plan path; the issue-standard §5 owner decision later revised MG1 to "bodies
  restructured-to-standard when a confirmed MG6 plan says so, original preserved verbatim in
  `original_*` + the export backup" — IDs/sections still verbatim, and this round-trip still
  holds whenever no plan is supplied*),
  MIG-2 (multi-prefix absorption: every hand-minted `PFX` → permanent alias, no new PFX minted),
  MIG-3 (export serializes the native graph), MIG-4 (cache rebuild no-data-loss — scaffolded; full
  cache is W1); **CRASH-4** (crash mid-import → resume converges, no duplicates — *not CRASH-3, which is
  `split`/W3*); **CRASH-2** (merge writes the redirect before closing the source; a crash leaves a
  resolvable open-but-redirected source). **L3 PROBE-RATE:** the fixture import exercises write-pacing.
- **Acceptance criteria:** a clean `import` → `export` round-trip on `discodon-mini` preserves IDs,
  bodies, and sections verbatim; a crash-injected import resumes without duplicating; a merge never
  closes-then-orphans.
- **Critic mode:** final
  <!-- Override: the riskiest single op; its mechanism must be sound before the real dogfood migration
       in Chunk 06 builds on it. The live SPIKE-S2 is deliberately isolated to Chunk 06. -->
- **Foreign API:** GitHub REST/GraphQL (issue create, `state_reason`, native deps/sub-issues, timeline,
  `gh issue transfer` node_id)
- **Done when:**
  0. **verify-api** — record real shapes for the migration calls (create, label, dependency, sub-issue,
     timeline, transfer) to seed the fake and back CONTRACT-1. **Include the `blocked_by` *read* shape
     `pick`'s blocker fan-out parses** (Chunk 03 built `list_blocked_by` against the fake only; a
     live-shape mismatch would silently surface a blocked item as ready) — add one L5 smoke that links a
     real blocker and confirms `pick` excludes it.
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 06: SPIKE-S2 dry-run + MG4 scrub + prawduct-first real migration (dogfood)

- **Description:** Execute the real thing. First run **SPIKE-S2** (the live dry-run isolated from the
  Chunk-05 mechanism). Then build the **MG4 scrub workflow** — **model-surfaced** stale/dup candidates
  read from `list` output (the model reads the item list and proposes dispositions — *this is the
  model-in-the-decision; it needs no `search --like`, which is the post-cache accelerator, W2*) →
  **owner-confirmed** dispositions → the **MG6 restructure pre-pass** (issue-standard §5, built
  2026-07-17 as BKL-8N5K: model *proposes* a plan of ≤72 `area:`-titles + template bodies + `kind:`
  backfills, `restructure-preview` renders the aggregate before/after artifact, owner approves the
  batch; originals preserved verbatim in `original_*` block fields + the export backup; non-atomic
  items **flagged, never auto-split**) → `status`/`merge` on the cleaned set → deterministic
  `import [--restructure <plan>]` (honoring the owner-confirmed **`--archive-scope {all,open}`** lever —
  MG4b, chosen at scrub time; the model is in the *decision*, never the data plane — MIG-5/G1). Then **migrate prawduct's own backlog**
  (the bulk import), **repoint prawduct's briefing/gates** through the adapter, and **retire the
  `incoming-bugs/` drop-box in lockstep with its minimal
  same-repo replacement** (MG5 — `report-bug` files an `untriaged-upstream`-labeled issue via the adapter,
  **carrying the required `Found in: prawduct vX.Y.Z` body field sourced from `prawduct-hook version`, not
  model recall** — XP2 provenance; the receiving advisory counts labeled issues; the full XP1 cross-owner
  plane stays W3). **`lib/backlog/legacy.py` is NOT retired here** — as the shared plugin's markdown read
  path it stays live for un-migrated portfolio repos and retires only at portfolio-wide migration (MG3/GV7);
  prawduct's own cutover just stops *its* briefing from reading it. This is the slice's completion and its acceptance test.
- **Depends on:** Chunk 04 (governance read-path), Chunk 05 (importer, `merge`, `export`)
- **Artifacts consumed:** API §2.5 (scrub workflow over `list`/`status`/`merge`/`import`; `export` as
  the pre-migration backup); PRD §8.9 (MG4 scrub, prawduct-first, drop-box retirement + **MG5 minimal
  same-repo replacement**, **MG3 coexistence**), §4 (dogfood success criterion); Data Model §3 (label coexistence with prawduct's
  existing issues); Test Specs §3.10 (MIG-5 scrub keeps the model out of the data plane), §5 (SPIKE-S2).
- **Deliverables:** new `tests/spikes/s2_migration.py` (the live dry-run), the scrub workflow (a
  `/prawduct:backlog`-adjacent skill/workflow step + the deterministic `import` of the cleaned set), the
  real migrated prawduct backlog repo, the `briefing.py`/gates repoint to the adapter, removal of
  the `incoming-bugs/` drop-box (**`lib/backlog/legacy.py` stays** as the shared markdown read path —
  MG3/GV7 — retired only at portfolio-wide migration, not here), **and its minimal same-repo replacement (MG5):
  repoint `skills/report-bug` step 3 to file an `untriaged-upstream`-labeled GitHub issue into prawduct's
  own repo via the adapter's create path (in place of the `incoming-bugs/` file write), **preserving the
  template's required `Found in: prawduct vX.Y.Z` body field, sourced from `prawduct-hook version`** so the
  prawduct plugin version rides upstream reports deterministically (XP2 provenance, not model recall); and switch the
  `untriaged-upstream-reports` advisory's count from `incoming-bugs/*.md` to labeled open issues. The
  no-channel fallback (report-bug step 4: local capture + canonical-tracker pointer) is unchanged; the full
  XP1 cross-owner/foreign-identity plane stays W3.**
  <!-- RESOLVED (BKL-0QR1, owner sign-off 2026-07-17 → option c): the drop-box is retired IN LOCKSTEP with
       a minimal same-repo replacement (MG5, PRD §8.9), never before it — so no upstream-channel gap opens.
       Replacement = report-bug files an untriaged-upstream issue into prawduct's own PUBLIC repo via the
       adapter (fixed target, public-issue-create — no new auth); the full XP1 cross-owner/foreign-identity/
       private-target/XP2 surface stays W3. legacy.py retirement is unaffected. -->

- **Tests (L1):** MIG-5 (owner-confirmed dispositions; the `import` step receives a concrete cleaned
  set, not a model call; nothing hard-deleted — dispose via status/merge, DM7). **SPIKE-S2 (L4, step 0):**
  body-fidelity, ID aliasing, relationship reconstruction, archive volume/noise, resumability,
  **batched-vs-N+1 fan-out** (pins `pick`'s PROBE-LAT floor from Chunk 03), **node_id stability across
  transfer**. **Live dogfood:** the real prawduct migration is the acceptance evidence; **L5 smoke** on
  the two CLI round-trips the slice supports (`file`, `import`+`export` — MCP is W5, not a slice front).
- **Acceptance criteria:** prawduct's backlog is live on GitHub Issues with every `PFX` ID resolving as
  an alias; the scrub disposed stale/dup items with owner confirmation (no silent drops, nothing
  hard-deleted) and applied the **owner-confirmed `--archive-scope` choice** (MG4b); the briefing reads
  live counts through the adapter; the `incoming-bugs/` drop-box is retired **only after** its replacement
  is live — the briefing/gates read through the adapter, and `report-bug` files an `untriaged-upstream`
  issue into prawduct's own repo (verified end-to-end) **carrying `Found in: prawduct vX.Y.Z` from
  `prawduct-hook version`** — with the `untriaged-upstream-reports` advisory counting labeled issues; the
  no-channel fallback still degrades cleanly to local capture. **`legacy.py` is NOT retired at this cutover**
  (MG3/GV7 — it remains the shared markdown read path for un-migrated portfolio repos); a
  **`backlog-service-migration-required` advisory** fires for any repo whose structured markdown backlog
  has not cut over, so upgrade-before-migrate is a loud signal, never a silent zeroing.
- **Pre-sign-off conditions (folded 2026-07-17 — conditional design sign-off).** Verified-in-code
  scenario traces of the CC5/G2/rate seams before the irreversible migration found no design flaw but
  four build-completeness gaps; **two** are **must-fix before this slice is marked done** (not optional
  follow-ups), because they sit inside the acceptance criteria above. *(A third — `BKL-6X5D` part (b) —
  became a ratified **v3.2.0 release** blocker on 2026-07-20 when owner decision A1 chose
  `--archive-scope all`, making the unpaced close leg live for this migration rather than hypothetical.
  Whether it must also precede **this slice** is decision 6, builder-proposed and **sign-off owed**; if
  signed off the count here is three, and if declined it stays two while the release gate holds
  regardless. The count is deliberately the un-ratified figure — a number that has to move on a
  decision is that decision asserted in numeric form.)*
  - **BKL-4W7H (must-fix) — ✅ offline code + tests landed 2026-07-17.** The "every `PFX` ID resolving
    as an alias" read-path gap is closed: `core.resolve_ref` wires PFX→canonical alias resolution into
    `get` and `link` (against `--repo`); `migrate._find_by_key` gains a block `id_aliases` fallback
    skip-authority (`_AliasIndex`, lazily built once per run) that also **self-heals** the missing
    `id:PFX` label, so a human-deleted label can't turn a re-import into a permanent duplicate; and
    `reconcile-labels` re-derives a deleted alias from the block (`aliases_restored`). Delete-then-
    reimport + reconcile-restore + get/link-by-PFX tested. Coherence follow-up filed for PFX resolution
    in the remaining single-id mutators (`status`/`update`/`comment`/`claim`/`unclaim`) and the CC5
    decoder gaps. (Related: BKL-5R2K redirect-follow consumer — deliberately NOT folded in here.)
  - **BKL-8P2R (must-fix) — ✅ code landed 2026-07-18** (`status: shipped · closed-by: Chunk-06`).
    **As built** (three of four clauses): the briefing calls `snapshot.read` + detached
    `spawn_refresh`, **never** a synchronous `counts()` (which paginates at the 30 s transport default
    vs NFR §6's "few s"), and surfaces the snapshot age.

    *Two residuals, both open — do not read this bullet as full coverage before the live run:*
    (1) the live repoint against the migrated repo happens at runbook step 5, so the wiring is
    satisfied in build but not exercised end-to-end; (2) **the never-block test is not the shape the
    criterion asked for.** The criterion wanted real slowness injected (a stalling transport);
    `tests/test_briefing_functions.py::test_never_blocks_even_with_a_hanging_backend` instead pins
    fire-and-forget *structurally* — a recorder whose `wait` raises if touched, plus an elapsed bound.
    For the path **as written** that is the *stronger* guarantee, not a weaker one, and the backlog's
    shipped note says so: the transport is unreachable on the briefing path at all
    (`snapshot.read` is a local JSON read; the only backend reach is detached), so a slow backend
    structurally cannot cost the briefing anything. What the stalling-transport test would add is a
    **regression guard** — it would fail if a future edit reintroduced a synchronous `counts()`,
    where the structural test would keep passing. That is the residual: not a weaker proof of today's
    code, an absent guard against tomorrow's.
  - **BKL-3K9N (strongly recommended before the live run) — ✅ landed 2026-07-17**
    (`status: shipped · closed-by: Chunk-06`; matches this file's header at the top). Honors
    `Retry-After` / bounded backoff on a mid-import 429 and continues the same run, so shared-token
    contention during this chunk's repoint can't hard-stop the irreversible import.
  - **BKL-6X5D part (b) — a v3.2.0 release blocker (ratified); gating *this chunk* only if decision 6
    is signed off.** Keep the two apart: A1 (decision 5, owner-confirmed) makes part (b) block the
    **release**; whether it must also precede *this chunk's* bulk import is decision 6, which is
    builder-proposed and **awaiting owner sign-off**. If the owner declines, part (b) still blocks
    v3.2.0 but stops gating this chunk. *(The binary `--archive-scope {all,open}` lever —
    MG4b — landed in the owner-feedback pass; the quantified middle window (a recent-shipped N-month
    window) stays deferred.)* **Re-scoped 2026-07-20**, then **escalated the same day when owner
    decision A1 chose `--archive-scope all`** for this migration
    (`artifacts/migration-scrub-decisions.md` decision 5): under `all` every archived item costs a
    **paced create plus an unpaced close** — `Pacer.before_create` is the only paced call, and
    `_reconcile_status` → `core.set_status` takes no pacer — so this run *is* the half-metered
    create-then-close stretch part (b) exists to close. *Proposed* — decision 6, **owner sign-off
    owed**, not settled: it should land **before** the bulk import, not
    after, or the irreversible migration becomes part (b)'s own proof case. Part (a) — the
    re-attribution and the §8.9↔§9 circularity — closed 2026-07-20.

    *No count carries this gate.* An earlier revision justified it with discodon item counts; that
    evidence was withdrawn 2026-07-20 as too unstable to be load-bearing (four checkouts disagreed,
    and the canonical one moved between two reads) — see the BKL-6X5D backlog note. The gate stands
    on the structural ratio: one paced write and one unpaced write per archived item, whatever the
    volume.
- **Type:** cumulative-final
  <!-- Last slice chunk: its review IS the one `/prawduct:critic cumulative` against merge-base…HEAD,
       and the `/prawduct:pr create` gate for the slice PR. Commit first, run cumulative once. -->
- **Visual change:** yes — the owner reviews the scrub dispositions and the migrated repo; append a
  `.prawduct/operator-verification.md` entry (VRF) describing what to eyeball (a spot-check of migrated
  bodies/IDs, the disposition list, the live briefing counts).
- **Done when:**
  0. **SPIKE-S2** — run the live dry-run on a throwaway copy of prawduct's repo; record the settled
     facts (fan-out constant, node_id-across-transfer) back into NFR §4 / this plan
  1. Acceptance criteria **and the must-fix pre-sign-off conditions (BKL-4W7H, BKL-8P2R — plus BKL-6X5D part (b) *if decision 6 is signed off*; it blocks the v3.2.0 release regardless)** met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status; the slice branch is PR-ready (`/prawduct:pr create`)
- **SPIKE-S2 settled facts (2026-07-17 live dry-run — ~209 items into a throwaway repo, repos disposable):**
  - ✅ **Body/ID/section fidelity** preserved verbatim (`fidelity_ok: true`) — MG1 body-fidelity confirmed
    live. *(Settled pre-MG6, on the no-plan path. The MG1 contract was later revised — issue-standard §5:
    with a confirmed restructure plan, bodies are restructured-to-standard and the original preserved
    verbatim in `original_*`; the fact stands for what it tested and the real migration adds the plan.)*
  - ✅ **Aliasing (MIG-2):** 208 hand-minted `PFX`→`id:PFX` aliases; **zero new PFX minted** — existing IDs preserved.
  - ✅ **Resume idempotency (CRASH-4):** a full re-import created **0 duplicates** — skip-if-exists on the alias holds live.
  - ⚠️ **`pick` fan-out (PROBE-LAT):** ~**12.4 s**, **flat** across 1/3/5 candidates → NOT N+1 (fan-out is cheap/batched), but ~**6× the NFR <2 s target**, dominated by the `_all_issues` full-scan over paginated `gh` subprocesses. The <2 s floor needs the raw-HTTP/GraphQL fast-path (W1) or a scoped query, not the `gh`-subprocess path.
  - ⚠️ **`node_id` across `gh issue transfer`: NOT stable** (settles ID-4) — the node_id re-mints on transfer (it encodes the repo). Nothing may key on it as a cross-repo permanent identifier. Transfer is a W3 op → no slice impact, but the fact is pinned.
  - ℹ️ **Relationships:** `reconstructed: false` is **benign for this source** — prawduct's backlog uses soft `related:` (×132) and **zero** native `blocked_by`/`sub-issue` fields; the importer doesn't map `related:`→native (preserved in-body). **MIG-3 native-graph reconstruction is UNPROVEN, not failed** — a source with real sub-issue trees needs a separate test.
  - ℹ️ **Archive volume:** ~117 of ~209 created closed (dropped) — workable.
  - **Spike-script gap:** step-7's automated `check_node_id_transfer` left the destination empty (didn't transfer); the fact was settled by a manual probe. Fix before the script is reused.

## Post-slice widening — roadmap (lower resolution)

> These are the **optional P1/P2 layers** (PRD §6: "everything else earns its keep for a specific
> workload"). Each is specified at PRD/artifact altitude and **detailed to code-level when its layer is
> picked up** — not chunked here (proportional effort; deferred-work over-specification is a named
> trap). Every one is dependency-noted and mapped to its §8 capability, its artifact sections, and its
> test IDs, so nothing is silently dropped (Complete Delivery, P2).

| ID | Layer | Delivers (§8 / API) | Consumes | Key tests | Gated by |
|---|---|---|---|---|---|
| **W1** | Read-through cache + `sync` | cache (SQLite, per-clone, gitignored, visible age, revalidate-on-decision) + `sync` (changed-since cursor, Q2); the raw-HTTP fast path + cloud-proxy-reach optimization (S1 residual) | Data Model §6 (cache schema), §7 (schema versioning), NFR §3/§8, PRD §8.1/§8.3 (D5, Q2) | MIG-4 (rebuild no-loss), §3.3 (visible age/revalidate) | **S4** (cache freshness protocol) — travels with the cache, does not gate the slice |
| **W2** | Search + dedup | `search --text/--like` (cache-served, GitHub search not read-your-writes), dedup-on-create advisory-async (AG3), `--semantic` (P2, GA) | API §2.2, Data Model §6, NFR §9 | Q3 lexical/semantic, §3.8 | W1 (cache) for `--text`/`--like` |
| **Wv** | Verification & grooming | `verify` (record + query "premise re-checked", TF2) + stale-verification query + mass grooming sweep (TF3); the layer that (with the scrub) attacks the **#1 stale-content** pain | API §2.1 (`verify`), Data Model §1.1 (`verified` list), PRD §8.2 (TF2/TF3) | **CRASH-5** (`verify` append-with-dedup, keyed on actor+date) | W3 (`batch`) for mass grooming; W1 (cache) for the stale-verification query |
| **W3** | Cross-project + automation | `file-upstream` (XP1/XP2, public/foreign identity plane), `batch` (AU2), `merge`/`split` **full** (AU3, keyed idempotency — the slice built only minimal `merge`), `rollup` (Q4 cross-owner fan-out); **AU1** events/webhooks (the cheap-polling baseline is `sync`/W1; webhooks are the optional enhancement) | API §2.3/§2.4, Security §1/§2 (auth by target owner), Data Model §5 (`source-key:`/`split-op:` markers) | §3.13 (AU2/XP1-XP2), §3.9 (security-negative), CRASH-3 (split), §3.2 | user-token / public-plane auth (Security §1); PV3 anonymous gated on `MET-6T4K` |
| **W4** | Attachments | `attach` (release-asset **or** attachments-branch via git-data API, both no-PR) | API §2.1 (`attach`), Data Model §1.6, PRD §8.8 (D9) | DM6 attach idempotency (key TBD by S5) | **S5** (inline-render on private) — decides the idempotency key |
| **W5** | MCP surface | thin MCP server over the same core (experimental tier) | API §1/§7 | one smoke test (isError mapping, delegates to core — Test Specs §1.1) | none (thin) |
| **W6** | App identity + offline queue | GitHub App per-owner rate/attribution upgrade (optional), offline write-queue (P2, provisional-ID reconcile-on-flush) | Security §1/§7 (D8), API §3 (queued envelope state) | §3.9 identity, provisional-ID reconcile | App registration (owner); S3 rate tuning |
| **Wg** | GV3 reconciliation janitor | `closed_by` authority + bidirectional drift sweep (shipped-but-PR-died / merged-but-item-open) as a deterministic janitor workflow | API §2.6, Data Model §1.1 (`closed_by`), PRD §8.7 (GV3) | GOV-1 (§3.12) | none (rides the janitor) |

**Roadmap sequencing note.** W1 (cache) unblocks W2 (`--text`/`--like` search) and Wv's
stale-verification query. W3/W4/W5/W6/Wg are mutually independent and each cheap-ish; sequence them by
which workload bites first (grooming fan-out → W1/W2/Wv; consumer upstream filing → W3; screenshots →
W4). **discodon migration** (a PRD §4 success criterion — "~317 open items migrate with IDs preserved")
is a **post-slice operational re-run of the Chunk-05 importer** against discodon (after its own scrub),
not a new capability and not a dropped requirement. Each roadmap layer re-enters this plan for a
code-level chunk breakdown at pick-up, and re-runs its own independent review.

## Early Feedback Milestone

**Milestone chunk:** 01 — after the walking skeleton, the owner (and any agent) can
`prawduct-hook backlog file`/`get` against a real repo and see an item round-trip. The full slice value
(live `pick`, zero-conflict CRUD, migrated backlog) lands at Chunk 06.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes (per-chunk commit is what
scopes `chunk`-mode reviews; Chunks 01/02/05 override to `final` for keystone/risk coherence, Chunk 04
runs `chunk`). The slice ships as **one PR** — Chunk 06 is `cumulative-final`, so its
`/prawduct:critic cumulative` review is the `/prawduct:pr create` gate for the whole slice branch
(Principle 14 at the bundle level). Per `project-preferences`, PRs are created and merged only when the
owner asks (`wait_for_user`), merge strategy = merge-commit. **Review-count budget (P0 learning):** four
heavy reviews across the slice (01/02/05 `final` + 06 `cumulative`); Chunk 04 was demoted from v1's
`final` to keep the count honest.

- **After Chunk 01 (architecture validation):** does the transport-seam + fake + envelope actually
  prove the layers connect, and did the `legacy.py` move leave the framework green? Is the fake's
  fidelity honest (CONTRACT-1 seeded from real shapes)? The point to catch a wrong foundational seam.
- **After Chunk 02 (state-machine keystone):** does the two-axis decoder + reconciliation hold under
  crash injection and human-UI drift, and does mass-assignment (SEC-2) hold, before Chunks 03–06 build
  on it?
- **After Chunk 05 (migration mechanism):** is the importer resumable/idempotent, `merge` crash-safe,
  and `export` full-fidelity on fixtures before the live SPIKE-S2 and the real dogfood migration in 06?
- **After Chunk 06 (cumulative, slice complete):** full-bundle review; the slice is PR-ready. Confirm
  the honest scope held — the slice delivers stale-*views* + conflict-free + online `pick`, and the plan
  did **not** silently claim the #1 stale-*content* win (that is TF2/TF3 + the scrub — Wv/W-roadmap).

## Traceability — every slice P0 capability lands in a chunk

| §8 capability (P0 unless noted) | Chunk |
|---|---|
| Deterministic CRUD, one-call `file`, JSON+human (AG1/AG2/AG6, G1) | 01 |
| `provision` label taxonomy — minimal create (GV5) | 01 · full coexistence-reconcile (GV6) 04 · PROV-2 decode-ignore 03 |
| Envelope + error model + exit codes (API §3/§4) | 01 |
| Stable IDs, `PFX` aliases, redirects (DM4/D4) | 01 (normalize) · 05 (alias machinery) |
| Per-project visibility inherits repo access (**PV1** — Security §2, delegated) | 01 (structural — GitHub-delegated) |
| Real scoped/revocable credentials, not a shared secret (**PV2** — Security §1/§4) | 01 (inherits session `gh` auth, O5) |
| No token in output · attribution off API identity · mass-assignment guard (SEC-1/SEC-3/SEC-2) | 01 (SEC-1/3) · 02 (SEC-2) |
| Unattended fail-clean · Actions-context withhold (SEC-5/SEC-6, Security §1a/§1b) | 04 |
| Two-axis status, crash-safe transitions, reconciliation (DM2/CC1/CC5, M5) | 02 |
| No lost updates — optimistic CAS (CC2) · comments (DM5) | 02 |
| Structured `list` online + `pick` ready-work (Q1-structured/GV1, M8) | 03 |
| Relationships queryable (DM3) · claims + TTL reap (CC3, M11) | 03 |
| Counts + briefing snapshot, start never waits (Q5/GV2, M3) | 03 (`counts`) · 04 (`refresh-counts` snapshot) |
| Actor identity kept as per-item history (**CC4**, P1 — Security §5) | 01/02 (coverage by inheritance: native timeline `history` + attribution off API identity, SEC-3; named here for bookkeeping) |
| Never-block floor + graceful degradation (AG4/G2) · freshness/visible-age (TF1/G3) | 04 |
| One-shot resumable importer (MG1) · full-fidelity export (MG2/G5) · minimal `merge` (AU3, for the scrub) | 05 |
| Pre-migration scrub (`--archive-scope` lever, MG4b), prawduct-first, drop-box retirement, coexistence + migration-required advisory (MG3/GV7) | 06 |
| Adopter-reproducible backend shipped in the plugin (GV4/G4) | 01–06 (built in-plugin, `gh` transport) |

*P1/P2 capabilities (cache, full-text/semantic search, dedup-async, **`verify`/TF2 + grooming/TF3**,
`file-upstream`, `batch`, full `merge`/`split`, `rollup`, `AU1` events, attachments, MCP, App identity,
offline queue, GV3 sweep) map to the W1–Wg roadmap rows above — deferred by design, not dropped.*

## Coherence debts — filed and swept (2026-07-16)

Surfaced by the v2 independent review; **all three swept in the peer docs the same session** (P12 scope
discipline — the previous drill-downs filed and swept debts the same way). None blocked Promotion; each
was a wording/placement fix in a *sibling* doc. Recorded here for the audit trail:

1. **API contract §1 — CLI surface spelling.** ~~§1 wrote the public surface as `prawduct backlog
   <op>`.~~ **Resolved** — API §1 pins the canonical command to **`prawduct-hook backlog <op>`** (one
   entry point, O5) and establishes `prawduct backlog` as the doc-set shorthand, legitimizing the prose
   uses in PRD §6 / Test Specs §1.1 without churn.
2. **Data Model — the on-disk export representation.** ~~PRD §8.9/MG2 promised "§16 Data Model pins the
   on-disk representation," which the Data Model did not deliver.~~ **Resolved** — PRD §8.9/MG2's
   pointer corrected to name the real authorities (fidelity = NFR §8; serialized fields = Data Model
   §1.1/§1.3/§2); Data Model §8 gains open-Q5 stating the concrete on-disk **layout** is a build-time
   decision (this chunk, Chunk 05), *not* a queried lock-in schema since re-import is out of scope.
3. **API §2.5 / Test Specs MIG-5 — the scrub's op dependencies.** ~~Both described the MG4 scrub as
   needing `list` + `search --like`, an op the slice defers.~~ **Resolved** — API §2.5 and MIG-5 now
   name `search --like` as a **post-cache accelerator (W1/W2), not a slice dependency**; the cacheless
   slice scrub uses model-surfaced dedup over `list` + the minimal `merge` (Chunk 05). The P0 MG4 scrub
   is now buildable in the slice.

---

*Independent review folded (2026-07-16, Principle 14):* a fresh-eyes build/sequencing critic + a
coverage/traceability verifier reviewed v1 (the two-reviewer pattern the five sibling drill-downs used).
Confirmed findings are folded above and inline; the three residual peer-doc items were filed **and swept
the same session** (see "Coherence debts — filed and swept"). Next: owner sign-off on v2 → Promotion
to an active build plan (`.prawduct/artifacts/` + `active_build_plan`).
