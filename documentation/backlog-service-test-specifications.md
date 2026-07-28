# Backlog Service — Test Specifications

`status: draft v3 — build-plan coherence sweep (2026-07-16, from the §16(6) Build-plan drill-down review): MIG-5 scrub restated — `search --like` demoted to a post-cache accelerator (not a slice dependency), model-surfaced dedup over `list` in the cacheless slice (API §2.5). Prior v3 — peer-doc coherence sweep closed (2026-07-16): the four §8 debts this drill-down filed are now resolved in the peers and the loop is closed here — CRASH-3 un-blocked and asserts full no-duplication against the `split-op:` key API §2.3 now pins; XP-1 asserts `file-upstream` retry-dedup against the `source-key:` marker API §2.4 now pins; §8 debts 1 (semantic-gate) + 4 (never-deletes) marked resolved against the API §12b/PRD §9 corrections. Prior v2 — independent-review fold (2026-07-16): a fresh-eyes test/design critic + a GitHub-platform-fact verifier reviewed v1 (the same two-reviewer pattern the Data Model / Security / API-contract / NFR drill-downs used). BLOCKING fixes — (1) coverage holes behind false traceability pointers closed: GV3 closed_by/drift-sweep (new GOV-1), F5 cache-gitignore/doctor (new SEC-8), NF1 cost-O(1) + operability design-guaranteed rows (new OPS-1..3), Q2 sync/cursor (new QRY-5), AU2 batch partial-success (new BATCH-1), XP1/XP2 file-upstream (new XP-1) — each was routed in v1 to a test that did not cover it; (2) CONTRACT-1 overclaim corrected — a shape-diff guards SHAPE drift only, behavioral fidelity (read-your-writes timing, the replication window, timeline ordering) is spike-verified-once + L5-guarded, not "what makes L1 trustworthy." FACT fixes — QRY-3 semantic branch re-grounded (semantic search is GA-on-by-default at 10/min, NO per-repo hybrid gate — the API-contract C5 rewording is itself inaccurate → peer-doc flag); QRY-1 "documented" replication window → "observed/undocumented, L2-owed"; ENC-6 pinned to the GraphQL MarkedAsDuplicateEvent.canonical shape (the REST issue-event carries no canonical field); dependency terms aligned to REST blocked_by/blocking. METHOD — CRASH-3 (split) marked blocked-on an upstream idempotency-key decision (API §2.3 "by link" is not a concrete matching key); "single seam" → "primary seam." Prior v1: initial drill-down from PRD §16(5) — five test layers, the transport-seam-fake isolation decision, the catalogue + coverage matrix. · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4 — §4 success criteria, §5 invariants G1–G5, §8 capabilities),
`documentation/backlog-service-nfr.md` (§9 target→owner map — the testable throughline),
`documentation/backlog-service-api-contract.md` (operation surface, §4 error vocabulary, §3 envelope),
`documentation/backlog-service-data-model.md` (§2 block parse, §4 set-status/decoder, §5 IDs/aliases),
`documentation/backlog-service-security-model.md` (threat table, F1–F7, structured-error control).
This doc specifies the **tests** those artifacts imply; it references their behaviors and rules rather
than restating them.

## 1. Charter & altitude

**What this doc is.** The testable contract for the Backlog Service: for every governing invariant,
capability, and NFR target the design owes, it names **the test(s) that prove it**, states **what each
test proves and how**, and cites **pass/fail** — so nothing the design promised is silently unproven
(Complete Delivery, P2). The completeness spine is §7's coverage matrix: every obligation the six design
docs raised (catalogued during this drill-down) maps to a test ID or an explicit anti-test.

**Altitude — spec, not code (the same line the API contract holds).** This doc pins **which tests exist,
what each asserts, the test layer, and the fixture/harness each needs** — **not** test-function names,
assertion syntax, or the specific mock-library calls (those are build-time, chosen by the Builder
against `project-preferences`). *The learning that bit the API contract bites here too:* a test that
exercises **only the core library must not be counted as proving the whole contract** — the system
exposes **three fronts over one core** (CLI, MCP, core lib; PRD §6), so §1.1 states which layer each
test targets and §7 flags where a front is covered only by inheritance.

### 1.1 The three fronts and where tests attach

- **Core library** (`lib/backlog/…`) — the bulk of the deterministic catalogue (§3) attaches here: the
  set-status primitive, the decoder, the alias resolver, the error builder, the envelope. Testing the
  core proves the *logic*; it does **not** prove the CLI/MCP adapters wire it correctly.
- **CLI** (`prawduct backlog …`) — a thin adapter over the core. Gets its own tests for the things only
  it owns: exit-code scheme, JSON-sole-stdout pipe safety, non-interactive subprocess env, argument
  normalization. Most core behaviors are proven at the core layer and **smoke-checked** once through the
  CLI (§5, live smoke) rather than re-tested per op.
- **MCP** (thin server) — experimental tier (API §7). **One smoke test** proves the error-shape mapping
  (`isError`) and that it delegates to the same core; deep behavior is inherited, not re-tested. §7 flags
  this as **intentional inherited coverage**, not a gap.

## 2. Test taxonomy & the isolation seam

The NFR §9 owner map already sorts obligations by **who proves them and when**. This doc turns that into
five test layers. The split is load-bearing: it keeps the CI-fast deterministic bulk honest without
pretending a one-time spike or a build-time number is a repeatable assertion.

| Layer | What it is | Runs | Produces | Owner map (NFR §9) |
|---|---|---|---|---|
| **L1 — Deterministic** | unit + integration against the **transport-seam fake** (§6); offline, hermetic, fast | every CI run | pass/fail | the "Test Specs (§16(5))" bundle |
| **L2 — Contract probe** | `verify-api` against a throwaway real repo — records the actual REST/GraphQL **shapes** the L1 fake asserts | on demand / pre-build / on GitHub-API drift | recorded shapes + a shape-diff | Data Model §8 open-Q1; API §11 |
| **L3 — Build measurement** | latency probe, rate probe — **numbers, not booleans** | at build, before "done" | measured p95 / rates vs a target | build-time latency probe; S3 |
| **L4 — Empirical spike** | S1/S2/S3/S5 — **one-time** proving increments, not repeatable CI | once, during the slice | a settled design fact | S1/S2/S3/S5 |
| **L5 — Live smoke + behavioral re-check** | round-trips **one real op per front** against a test repo, AND periodically re-checks the **behaviors** a shape-diff can't (read-your-writes timing, the 404 replication window, timeline-event ordering) | pre-release / nightly, gated | pass/fail (integration + behavioral confidence) | — |

### 2.1 The isolation seam — recorded decision: `test_isolation_approach`

**Decision.** The adapter's only egress is the **transport boundary** — it drives `gh` as a subprocess
(required transport, O5) and, on the optional fast path, raw HTTPS. That boundary is the **primary test
seam**: L1 tests inject a **fake transport** (an in-process fake GitHub implementing the subset of
issues / labels / `state_reason` / timeline / sub-issue / dependency behavior the adapter uses, §6) in
place of the real subprocess. No network, no credentials, fully deterministic — including
crash-injection (fail the *n*-th mutating call) and rate-injection (return `rate_limited`). Two narrower
seams exist and are named where used: a **function-level** seam for pure core logic (the decoder, the
alias resolver) and an injected **model-client** seam for INV-1 (assert zero invocations). The transport
boundary is the primary one because it is where GitHub's behavior enters.

**Why a fake and not just recorded cassettes.** Crash-recovery, idempotent re-run, and decoder self-heal
(the highest-value tests here) require **stateful** responses — the fake must remember the labels a
prior call set so the re-run sees them. A stateless cassette can't model "re-run converges." Recorded
cassettes (L2 output) still play a role: they seed the fake's response *shapes* so it can't drift from
GitHub's real JSON.

**The honesty mechanism — and its exact limit.** A fake is only as good as its fidelity to the real
API; a fake that lies makes green tests meaningless. Fidelity has **two parts, guarded differently, and
conflating them is a trap:**
- **Shape fidelity** (field names, types, enum values, envelope structure) is contract-tested against
  `verify-api`'s recorded real-GitHub shapes: a **shape-diff** (CONTRACT-1, §6) fails if the fake
  diverges. This is what keeps the L1 suite's *shape* assumptions from silently drifting when GitHub
  changes a payload — and it discharges the API contract's / Data Model's open `verify-api` question.
- **Behavioral fidelity** (read-your-writes *timing*, the 404-after-create replication window,
  timeline-event *ordering*, label-set *semantics*) is **NOT** shape-checkable — a shape-diff cannot see
  it. These behaviors are verified **once** by the L4 spikes (S1/S2) and re-checked periodically by the
  **L5 live-smoke** set; they are **not** regression-guarded by CONTRACT-1. So an honest statement of
  L1's guarantee is: *L1 green means the logic is correct given GitHub behaves as the spikes observed and
  the fake models — a behavioral drift in GitHub would pass CONTRACT-1 and must be caught at L5, not L1.*
  This is the residual trust boundary; §8 restates it as a known limit rather than hiding it.

## 3. Deterministic test catalogue (L1)

Format per test: **ID · Proves (→ parent) · Level · Setup · Action · Expected**. `Level` is `unit`
(core logic, fake at the function/model seam) or `integration` (through the CLI/core boundary, fake at
the subprocess seam). Concrete fixtures are named; §6 defines them.

### 3.1 The hard invariants (pass/fail, not percentile)

**INV-1 — Zero model tokens on the CRUD path** (→ G1/AG1, NFR §4 hard assertion)
- Level: unit
- Setup: inject a model client that **raises on any invocation** (a counter would also serve) into the
  `file` / `get` / `update` / `status` code paths; fake transport for GitHub.
- Action: drive each of the four CRUD ops with representative inputs.
- Expected: all four complete successfully; **zero** model invocations recorded. This is a pass/fail
  invariant — one model call on the data plane fails the test.

**INV-2 — One non-interactive call; never opens a TTY, never blocks on input** (→ AG1, API §8, Security §1a)
- Level: integration
- Setup: run the CLI with **stdin closed / no controlling TTY**; fake transport.
- Action: run a `file` and a `get`.
- Expected: both return within the process without blocking; the subprocess env passed to `gh` includes
  `GH_PROMPT_DISABLED=1`, `GH_NO_UPDATE_NOTIFIER=1`, `GH_PAGER=` (empty), non-interactive flags, and **no
  inherited TTY**; an auth-required condition returns the `auth` error (§3.6), never an interactive
  `gh auth login` prompt.

### 3.2 Crash-safety & idempotency (fault-injection via the seam)

The method throughout: the fake lets a test **fail the n-th mutating call**, then the test runs the
decoder / re-runs the op and asserts a valid state + idempotent completion. No real process-kill needed
— the canonical write-orders (Data Model §4, API §2.3) make each intermediate state deterministic.

**CRASH-1 — `set-status` partial-transition recovery** (→ CC1/M5, Data Model §4 B1, NFR §6 "crash-recovery test is owed")
- Level: unit
- Setup: an item `open ∧ status:in-progress`; target = `shipped` (a closed status). Canonical order for
  a **closed** target: (1) set closed + `state_reason` — **the authority**: the decoded status is correct
  from here on, whatever `status:` labels linger; (2) strip the stale open sub-state `status:` label(s).
  *(The generic B1 "add `status:target` before removing any other" applies only to an **open** sub-state
  target, whose sole encoding is the label — there is no `status:shipped`/`status:dropped` in the
  taxonomy (Data Model §4), and a closed `state_reason` is the authority, so a closed target has no
  zero-label window to guard.)*
- Action: for each cut point k ∈ {after step 1, after step 2}, run `set-status(shipped)` with the fake
  failing call k+1 (`unavailable`); then decode the item; then re-run `set-status(shipped)` to completion
  and once more. The **open sub-state** case (`submitted → in-progress`) — where add-before-remove is the
  window that matters — is asserted as a companion (fail the remove; the item still carries `status:
  in-progress`).
- Expected: at every cut point the decoder reads a **valid** status — a closed `state_reason` reads as
  `shipped` even while a stale `status:` label lingers, and the open-substate companion never opens a
  zero-`status:`-label window (the new label is added before the old is removed); the first completing
  re-run reaches `closed ∧ shipped`; a further re-run is a **no-op** (idempotent).

**CRASH-2 — `merge` redirect-before-close** (→ AU3/DM7, API §2.3 C2)
- Level: unit
- Setup: items A and B, both open.
- Action: run `merge A→B` with the fake failing the **close-of-A** call (after the `superseded-by:`
  redirect is written on A); then re-run to completion.
- Expected: after the injected failure, A reads **open-but-redirected** (a valid, resolvable state — a
  ref to A resolves to B); the re-run closes A with the redirect intact; the op **never closes-then-
  orphans**; a third run is a no-op. Both bodies preserved (DM7 — nothing hard-deleted).

**CRASH-3 — `split` recover-by-cleanup, keyed on the `split-op:` token** (→ AU3, API §2.3/§2.1)
- Level: unit
- Setup: parent item P; a split into children C1, C2. The call derives a stable `split-op:<token>` from
  *(P's canonical id, the ordered specs of C1,C2)* and stamps each child `split-op:<token>#<index>`
  (API §2.3, Data Model §5).
- Action: run `split P → {C1,C2}` with the fake failing after C1 is created and stamped `…#0`; then
  re-run with the **same arguments** (→ same token); then once more.
- Expected: the re-run recomputes the token, finds C1 already stamped `#0`, and creates **only C2**
  (stamped `#1`) — **no duplicate C1**; final state has exactly two linked children; the third run is a
  no-op. A run with **changed** child specs mints a **new** token (a new split, correctly not a resume).
  *(v1 could only assert bounded-duplication because the parents pinned no matching key — API §2.3 now
  pins the `split-op:` token, so the full no-duplicate assertion is decidable.)*

**CRASH-4 — `import` resumable / idempotent** (→ MG1/M6, API §2.5)
- Level: integration
- Setup: a fixture `backlog.md` with M items carrying `PFX-XXXX` IDs (fixture `discodon-mini`, §6).
- Action: run `import` with the fake failing after N < M items are created + the checkpoint written;
  then re-run into the same repo.
- Expected: the re-run **skips** the N already-created (matched by `id:PFX-XXXX` alias label,
  skip-if-exists), completes the remaining M−N, creates **no duplicates**; a third run is a full no-op.
  No rollback is attempted (the design has none — recovery = re-run).

**CRASH-5 — `verify` append-with-dedup keyed on (actor, date)** (→ TF2, API §2.1 C7)
- Level: unit
- Setup: an item with no `verified` entries.
- Action: `verify` twice with the same (actor, date); once more with a different date.
- Expected: the first adds an entry; the same-(actor,date) re-stamp is a **no-op** (append-with-dedup);
  the different-date stamp adds a second entry. Idempotency is keyed, not blind.

**CRASH-6 — `claim` atomic take-and-verify → `claim_conflict`** (→ CC3/M11, API §2.1)
- Level: unit
- Setup: an unassigned item; simulate two claimants via the fake's ordering.
- Action: claimant A takes; claimant B takes; then A's take-and-verify read.
- Expected: exactly one holds the claim; the loser gets a **non-fatal** `claim_conflict`; the claim
  carries actor + timestamp; a claim past its TTL is surfaced as reap-eligible (auto-unclaim/flag) so
  `pick` cannot starve. (The residual double-take race is accepted by design — this test asserts the
  take-and-verify surfaces it, not that it is eliminated.)

### 3.3 Freshness & never-silently-stale (G3)

**FRESH-1 — Cacheless read is live (staleness = 0)** (→ G3/D5, NFR §5)
- Level: integration
- Setup: cache **off** (the thin-slice default).
- Action: `get` an item.
- Expected: the fake records a **live fetch per read**; no local store is consulted; the payload carries
  no stale-age warning because there is no cache.

**FRESH-2 — Cached read carries visible age** (→ G3, NFR §5, API §3)
- Level: unit
- Setup: cache **on**, warm with an entry stamped `fetched_at`.
- Action: `get` served from cache.
- Expected: the envelope carries a **non-null age** (a `warnings[]` entry or an age field); a cache read
  is never age-silent.

**FRESH-3 — Decision-driving read revalidates (304/200)** (→ G3, NFR §5, Data Model §6/M2)
- Level: unit
- Setup: cache on with an entry + its `etag`; a decision-path read (`pick`/`get` behind a decision). The
  revalidated read is the **REST** `get` (ETag/304 is a REST-only mechanism — GraphQL has no ETags, so a
  GraphQL fan-out revalidates by a fresh read, not a conditional one).
- Action: perform the read; fake returns 304 in one case, 200-with-new-body in another.
- Expected: the read issues a **conditional request** (If-None-Match with the stored `etag`); 304 →
  reuse (and, being authenticated, costs no primary-rate quota); 200 → refresh + restamp `fetched_at`.
  (The ETag/304 *mechanism* is a verified platform fact; this proves our decision path *uses* it.)

**FRESH-4 — Never silently stale (explicit negative)** (→ G3, NFR §5 negative test)
- Level: unit
- Setup: cache on; force a **stale entry past its validator** on a decision path.
- Action: perform the decision-driving read.
- Expected: **either** revalidation fires (conditional request issued) **or** the age is surfaced in the
  envelope — never a silent stale serve. Failing both is a test failure. This is the exact failure the
  project exists to kill (the "66 closed shown as open" observation).

### 3.4 Never-block / graceful degradation (G2 / AG4)

**BLOCK-1 — Write never hangs (subprocess-kill after T)** (→ G2/AG4, NFR §6)
- Level: integration
- Setup: fake transport that **stalls** (never returns) or is unreachable; bounded timeout T.
- Action: `file` / `update` / `status`.
- Expected: the call returns **≤ T** with `unavailable` (retryable), **never hangs**; mechanism is
  subprocess-kill-after-T for the `gh` path (no connect/read-timeout knob there), connect+read timeout on
  the optional raw-HTTP path.

**BLOCK-2 — Read degrades, never hangs** (→ G2, NFR §6)
- Level: integration
- Setup: offline (fake unreachable), two variants: cache absent, cache warm.
- Action: `get`.
- Expected: cache-absent → clear `unavailable` + guidance; cache-warm → **serve with visible age**
  (FRESH-2); neither hangs.

**BLOCK-3 — Callers never retry-loop** (→ G2, API §4 C3, NFR §6)
- Level: unit
- Setup: a gate/hook consumer of the backlog read path; fake returns `unavailable`, then `validation`,
  then `not_found`.
- Action: exercise the consumer against each error.
- Expected: the consumer **degrades gracefully** on every error and **does not loop-until-success**;
  never-block (degrade on all errors) is asserted as **distinct** from `retryable` (a transient-vs-
  permanent hint for an explicit retry-driver, not a mandate to loop). The `retryable` flag is present
  and correctly set, but its presence never forces a loop.

**BLOCK-4 — Offline write returns the queued/`unavailable` envelope, never a hang** (→ PRD §8.1, API §3)
- Level: integration
- Setup: offline; two variants: offline-queue layer present (optional P1) vs absent (slice default).
- Action: `file`.
- Expected: with the queue → `{"status":"queued","data":{"provisional_id":…}}`, later reconciled to the
  real `repo#number` on flush; without it → the `unavailable` error. **Never** a hang or a half-write.

**BLOCK-5 — Briefing / session start is network-independent** (→ GV2/M3, NFR §4 & §6)
- Level: integration
- Setup: the session-start / briefing path; fake transport instrumented to record any network call.
- Action: run session start.
- Expected: start reads the local `briefing_counts` file and issues **no network call** on the start
  path; the refresh is detached (D6) and skippable; start latency is network-independent. (One behavior,
  stated in both NFR §4 and §6 — one test discharges both.)

### 3.5 Two-axis encoding, block parse & decoder (DM1/DM2/CC5)

**ENC-1 — Soft-enum: unknown value flagged, never rejected** (→ DM1, Data Model §1.1, PRD §7)
- Level: unit
- Setup: a write carrying an undeclared `stage:` / `kind:` value (fixture models scriob's `kind:` on 158
  items; hallucinote's one-off prefixes).
- Action: `file` / `update` with the unknown value.
- Expected: the write **succeeds**; the unknown value is surfaced as a `warnings[]` advisory, **not** a
  `validation` error. A fail-closed validator here would be a latent fail-close — negative-asserted.

**ENC-2 — Two axes never flattened** (→ DM2, Data Model §4)
- Level: unit
- Setup: items exercising all `status:` × `stage:` combinations that co-occur.
- Action: encode then decode each.
- Expected: `status` and `stage` round-trip **independently**; no combination collapses one axis into the
  other. (Property-based candidate — §6.)

**ENC-3 — Exactly-one prawduct block; last-block-wins** (→ Data Model §2/m5; the BKL-7M4Q origin)
- Level: unit
- Setup: an issue body with **two** fenced `prawduct` blocks (a doubled/misplaced block — plausible from
  the BKL-7M4Q duplicated-paragraph origin + a CC5 human edit).
- Action: parse.
- Expected: the parser takes the **last** block deterministically and **flags** the earlier one
  (`warnings[]`); it never silently merges or errors.

**ENC-4 — Block-tolerant parse: unknown keys preserved, missing keys default** (→ Data Model §2/§7)
- Level: unit
- Setup: a block with an unknown key and an absent optional key.
- Action: parse then re-serialize.
- Expected: the unknown key is **preserved verbatim** (forward-compat round-trip); the missing key takes
  its default; no key is dropped or repurposed (additive-only). (Round-trip property — §6.)

**ENC-5 — Decoder precedence & self-heal (torn / multi-label states)** (→ Data Model §4, CC5)
- Level: unit
- Setup: (a) an open issue carrying **two** `status:` labels; (b) a **closed** issue still carrying a
  `status:` label (a human closed it in the UI); (c) an open issue with a removed `stage:` label.
- Action: decode each; then run a reconciling write.
- Expected: (a) highest-precedence wins (`in-progress > submitted > none`) and reconciliation **removes
  the losers**; (b) `state_reason` is authoritative for a closed issue and the stray `status:` label is
  **stripped**; (c) the missing `stage:` is surfaced advisory (CC5), never mis-decoded. A crash
  mid-transition always reads valid and self-heals on the next write.

**ENC-6 — `state_reason: duplicate` fail-open decode** (→ Data Model §4/m3, PRD §7)
- Level: unit
- Setup: an issue closed by a human "as duplicate" (`state_reason: duplicate`) + a `MarkedAsDuplicateEvent`
  timeline event; and separately, an issue with an **unknown** future `state_reason`.
- Action: decode both.
- Expected: `duplicate` decodes to `dropped` + `superseded_by` — where `superseded_by` is read from the
  **GraphQL `MarkedAsDuplicateEvent.canonical`** field (the **REST** issue-event carries no canonical
  pointer, only actor/event/created_at — so the fake and CONTRACT-1 pin the GraphQL shape, §6); an
  unknown `state_reason` **fails open** (decodes to a safe default + a warning), never rejects.

### 3.6 Error model & envelope (API §3–§4)

**ERR-1 — Error-code vocabulary, each code → a case** (→ API §4 vocabulary table)
- Level: unit (core builder) + integration (CLI exit code)
- Setup: conditions that trigger each code.
- Action: provoke each of: `validation`, `not_found`, `ambiguous_id`, `alias_collision`, `conflict`,
  `claim_conflict`, `auth` (incl. `gh` exit-4 → `auth`, C10), `unavailable`, `rate_limited` (80/min or
  ~500/hr content, or the 900-pts/min burst), `unsupported` (fulltext without a cache; `--semantic`
  where the capability is genuinely absent — see QRY-3).
- Expected: each yields its code in the envelope and a **stable non-zero exit class** at the CLI aligned
  with `prawduct-hook` conventions (the exact integers are a build-time coherence check, API §11);
  crucially, an **unknown soft-enum is NOT `validation`** (ENC-1) — negative-asserted here too.

**ERR-2 — JSON is the sole stdout content; diagnostics to stderr (pipe-safety)** (→ AG6, API §3/§8)
- Level: integration
- Setup: run any op with `--json`, piped to a strict JSON parser.
- Action: capture stdout and stderr separately.
- Expected: **stdout parses as JSON with nothing else**; all progress, warnings, deprecation notices go
  to **stderr**; a `| jq` never chokes. A deprecation warning specifically must not appear on stdout.

**ERR-3 — Envelope shape (ok / error / warnings[]) uniform across three fronts** (→ API §3/§4, §12 A7)
- Level: unit + one MCP smoke
- Setup: an ok result, an error, and a self-heal (a warning).
- Action: observe the return value (core), the CLI envelope + exit code, and the MCP error shape.
- Expected: `{"status":"ok","data":…,"warnings":[…]}` / the error form / the `queued` form are identical
  in structure across the return-value, CLI, and MCP fronts (mapped into MCP `isError`), **from the first
  slice** — not deferred. The MCP case is one smoke test (inherited coverage, §1.1).

**ERR-4 — warnings[] is advisory, never fatal** (→ API §3, DM1/CC5/G3)
- Level: unit
- Setup: results carrying an unknown soft-enum, a CC5 self-heal, and a stale-age note.
- Action: read each.
- Expected: each is a **`warnings[]` entry on an `ok` envelope**, never an error; the caller's success
  path is unaffected.

**ERR-5 — `null` vs absent field semantics** (→ API §8; *implied-not-named in source docs — named here*)
- Level: unit
- Setup: an `update` with a field **absent**, and the same field explicitly **`null`**.
- Action: apply each.
- Expected: absent = "use default / leave unset"; explicit `null` = "**clear** this field"; `[]` and
  absent both mean "none." A fail-closed reader that conflates them would re-create the tolerated-variant
  bug — negative-asserted.

**ERR-6 — Boundary exceptions caught, logged with context, never swallowed** (→ API §4, project convention)
- Level: unit
- Setup: the fake raises an unexpected `OSError` / `JSONDecodeError` from the transport.
- Action: drive an op through it.
- Expected: the exception is **caught at the boundary**, mapped to `unavailable`/`validation` with
  context logged, and **never silently swallowed** (no bare `except: pass`). (Aligns with the repo's
  broad-except discipline.)

### 3.7 IDs, aliases & redirects (DM4/D4)

**ID-1 — Four spellings normalize to canonical** (→ D4, API §3/§8)
- Level: unit
- Setup: the four accepted spellings of one ID: `owner/repo#number`, `repo#number`, `repo-number`,
  `repo/number`.
- Action: normalize each.
- Expected: all four → the same canonical `owner/repo#number`; a short `repo#number` resolves same-owner
  only. (Property candidate.)

**ID-2 — `ambiguous_id` under federation** (→ D4, API §4; *implied-not-named in source docs — named here*)
- Level: unit
- Setup: a short `repo#number` that matches under two owners in a federated context.
- Action: resolve it.
- Expected: `ambiguous_id` error with the candidate set surfaced, never a silent pick of one.

**ID-3 — Alias-collision guard (ref resolution can't be hijacked)** (→ Data Model §5, Security §5/F3, API §4)
- Level: integration
- Setup: an existing item holding `id:PFX-0007`; a second item asserts the **same** `id:PFX-0007` label.
- Action: import/create the second; then resolve `PFX-0007`.
- Expected: the second is **rejected/flagged** (`alias_collision`); an `id:PFX` alias resolves to
  **exactly one** live item; a forged `id:` label cannot hijack resolution.

**ID-4 — Redirect on merge / transfer** (→ DM4/M4, Data Model §5)
- Level: unit
- Setup: item A merged into B (CRASH-2 covers crash-safety); separately, an item that underwent
  `gh issue transfer` (renumber → the destination assigns a new number, next = max+1).
- Action: resolve the old ID after each.
- Expected: the superseded/old ID resolves **forever** via the redirect / `id_aliases` entry; on
  transfer, the `superseded-by:` redirect is written and the `node_id` is stored as the transfer-stable
  fallback. (Whether `node_id` survives transfer is **genuinely undocumented** → **L4/S2 proves it**;
  this L1 test asserts our handling *given* the fixture's recorded behavior, flagged in §7 — it must not
  be upgraded to an asserted fact.)

### 3.8 Query semantics (Q1–Q5)

**QRY-1 — `list` structured, online, strongly-consistent-in-practice + the 404-after-create edge** (→ Q1-structured/M8, API §2.2)
- Level: integration
- Setup: fake models the REST list endpoint (read-your-writes in practice — a verified fact) and, in one
  variant, an **observed (undocumented) eventual-consistency edge** where a just-created item 404s
  momentarily.
- Action: `file` then immediately `list` / `get`.
- Expected: the just-written item appears immediately in the normal case; in the edge variant, the
  adapter performs a bounded **404-retry-after-create** and then sees it — the edge is handled
  defensively, not assumed away. **This edge is observed, not a documented GitHub guarantee** (the REST
  docs attribute a 404 to auth); its existence/timing is **L5-owed**, not asserted here as platform fact.

**QRY-2 — `pick` list-then-fan-out correctness** (→ GV1/DM3/CC3, Data Model §4, API §2.2)
- Level: unit
- Setup: candidates `open ∧ stage:ready ∧ unassigned`; some with open blockers (via the native
  dependencies API — REST `blocked_by` / `blocking`, GA 2025-08-21), some with a claim past TTL,
  including a **cross-repo** blocker.
- Action: `pick`.
- Expected: only candidates with **all blockers closed** and **no live claim** are returned, ranked, with
  a *why*; a candidate whose blocker is cross-repo is judged from a **live** read (a per-clone cache can
  misjudge it — negative-asserted: a stale cache must not let a blocked item be picked). `--claim` may
  return `claim_conflict` → re-pick. (Fan-out **latency** is L3/S2, not here — this proves correctness.)

**QRY-3 — `search` cache-served; `--semantic` capability-probed** (→ Q1-fulltext/Q3, API §2.2)
- Level: unit
- Setup: cache on with `item_fts`; a just-written item **not** yet in GitHub's search index. Two
  `--semantic` variants: the capability **present** (GitHub.com — improved/semantic issue search is GA,
  on by default, ~10 req/min) and the capability **absent** (e.g., a GHES instance without it, or the
  search endpoint returning a capability error).
- Action: `search --text` and `search --like` (lexical); then `search --semantic` in both variants.
- Expected: `--text`/`--like` are **cache-served** (so they see the just-written item that GitHub search
  would miss — GitHub search is not read-your-writes); `--semantic` where the capability is **present**
  runs and returns results (rate-limited by the 10/min budget → `rate_limited` if exceeded, **not**
  `unsupported`); `--semantic` where the capability is **absent** → `unsupported` (a **capability probe**,
  not a per-repo hybrid-search enable-gate — that gate does not exist). With no cache, `--text` →
  `unsupported` (needs the cache). *(This corrected the API contract's earlier "semantic … hybrid-search
  enablement-gated" wording — no such per-repo gate exists; semantic search is GA-on-by-default. The peer
  is now fixed: API §2.2/§4/§7 + §12b/K3 — see §8 debt 1, resolved.)*

**QRY-4 — `counts` derived on read; `rollup` cross-owner fan-out** (→ Q5/Q4, API §2.2)
- Level: unit
- Setup: a project with a known item distribution; a portfolio spanning two owners.
- Action: `counts`; `rollup`.
- Expected: `counts` are computed **on read**, never persisted (except the GV2 `briefing_counts`
  snapshot); `rollup` **fans out and merges across owners** (not cache-served, not GitHub-native) and
  matches the sum of per-project counts.

**QRY-5 — `sync` idempotent incremental warm via the changed-since cursor** (→ Q2/AU1, API §2.4, Data Model §6)
- Level: integration
- Setup: cache on; a warmed cache with a stored `cursor`; then three new/changed items since the cursor;
  a second variant with the cache **off**.
- Action: `sync`; then `sync` again with no further changes; then `sync` with the cache off.
- Expected: the first `sync` fetches only the **changed-since** delta (not a full scan), advances the
  cursor, and warms exactly those items; the repeat `sync` is a **no-op** (idempotent); with the cache
  off, `sync` is a no-op (cheap-polling baseline; webhooks are an optional AU1 enhancement, not tested
  here).

### 3.9 Security-negative (Security Model F1–F7)

**SEC-1 — No token in any output; structured-error primary + scrub backstop** (→ F2/N4, Security §4, API §4)
- Level: unit
- Setup: the fake emits raw `gh`/HTTP output **containing a planted token** of each class:
  `gh[opsu]_…`, `github_pat_…`, `ghr_…`, a bare JWT `eyJ…`, a URL-embedded cred `://u:p@…`, and the App
  private key.
- Action: force each into an error path and a normal path; capture stdout, stderr, cache, export,
  telemetry.
- Expected: errors are built from **known fields** (never by echoing raw output — the primary control);
  **no token pattern appears** in any sink; the denylist scrub catches any that reach the backstop; the
  cloud literal `proxy-injected` is never emitted. (Each pattern is a case — property-style over the
  pattern set, §6.)

**SEC-2 — Mass-assignment guard** (→ Security §2, API §9)
- Level: unit
- Setup: a `create`/`update` request that tries to set `history`, `node_id`, `automated:`, or another
  actor's GitHub-native attribution.
- Action: apply it.
- Expected: the write **binds only documented item fields**; the protected/native fields are **ignored or
  rejected**, never set from request input; attribution comes only from the API identity.

**SEC-3 — Attribution off the API identity, resolved once per process** (→ CC4/N3, Security §1)
- Level: unit + integration
- Setup: a bulk sweep of K mutations; the git-push identity differs from the `gh api user` identity.
- Action: run the sweep.
- Expected: every mutation records the **API identity** (`gh api user`) as actor, never the git-push
  identity, and surfaces a mismatch as advisory; the identity is resolved **once per process** (exactly
  one `gh api user` read for the whole sweep — not one per mutation against the 5k/hr core budget).

**SEC-4 — Fetch-time vs read-time cache authorization** (→ F4, Security §3, Data Model §6; *implied-not-named in source docs — named here*)
- Level: integration
- Setup: two identities — **broad** (access to `owner/repo-A` and foreign `x/repo-B`) and **narrow**
  (`repo-A` only). Broad fetches a `repo-B` item into the cache.
- Action: the **narrow** identity reads the `repo-B` entry.
- Expected: the narrow reader is **not** served the broad-fetched `repo-B` entry; a cross-repo cache entry
  **revalidates on read** (a re-fetch **404s** under the narrow token → not reused). Cache access is
  scoped to the fetching identity's repo-access set.

**SEC-5 — Actions untrusted-trigger: writes withheld** (→ F1, Security §1b)
- Level: integration
- Setup: simulate a workflow env with an untrusted trigger (`pull_request_target` / fork-PR /
  `issue_comment`) and a **non-collaborator** triggering actor.
- Action: attempt a write path and a read-only report.
- Expected: the **write path refuses** (the unattended-write capability is withheld) absent an explicit
  triggering-actor authorization check; **read-only reporting is allowed**. (Defends the pwn-request
  escalation — load-bearing.)

**SEC-6 — Unattended never prompts, fails clean, marks automated** (→ Security §1a, N1/N2)
- Level: integration
- Setup: an unattended run (no TTY) hitting an auth failure; and a retried/overlapping scheduled `file`.
- Action: run each.
- Expected: no interactive prompt (INV-2 mechanism); auth failure **fails fast** with a retryable logged
  error, reads fall back to cache-or-`unavailable`; every unattended mutation carries `automated: true` +
  a worker marker; a general unattended `create` is **not** idempotent unless **keyed** (a retried job
  without a key would duplicate — asserted so the design's single-flight/idempotency-key requirement is
  visible), and no unattended anonymous/foreign filing occurs.

**SEC-7 — PV3 anonymous-filing enable-gate + quarantine** (→ F6/F7, Security §6, API §9; enable-gate *implied-not-named in source docs — named here*)
- Level: integration
- Setup: (a) attempt to **enable** anonymous filing with `MET-6T4K` **not** configured, then **with** it
  configured; (b) a non-collaborator opens an unlabeled issue.
- Action: run the enable path; then the `submitted`-intake `list` query.
- Expected: (a) the enable path **refuses** without MET-6T4K (a structural gate, not a documented "don't")
  and **succeeds** with it; (b) the unlabeled non-collaborator issue is the **quarantine** state,
  surfaced to triage by the intake query — a non-collaborator **cannot** set labels/assignees (so cannot
  self-promote out of `submitted` or forge a `source:`/`id:` label), and **no mutation runs under the
  filer's identity**.

**SEC-8 — Cache stays gitignored; `doctor` catches an un-ignored cache (content-borne-secret defense)** (→ F5, Security §3, NFR §8)
- Level: integration
- Setup: a repo where the cache path is **not** effectively ignored — variant (a) the pattern is missing
  from `.gitignore`; variant (b) a differing global ignore or an `add -f` has staged it.
- Action: run `/prawduct:doctor`'s cache-ignore check.
- Expected: `doctor` **flags** the un-ignored/committed cache in both variants (gitignore is **not**
  enforcement — this is the check that makes it one); the defense targets the content-borne-secret threat
  (a pasted `.env`/log in an issue body would otherwise reach a committed cache). Negative variant: a
  correctly-ignored cache passes clean.

### 3.10 Migration guard-sweep (MG1–MG6)

**MIG-1 — Verbatim body/ID/section fidelity** (→ MG1, PRD §8.9)
- Level: integration
- Setup: fixture `discodon-mini` (a representative `backlog.md` slice + archive lines).
- Action: `import` then `export`; diff the round-trip.
- Expected: IDs, metadata bars, bodies, and sections are preserved **verbatim** *on the no-plan path*;
  existing `PFX-XXXX` IDs stay valid as `id:PFX-XXXX` aliases; change-logs/learnings/commit refs that
  cite old IDs still resolve. *(MG1 revision — issue-standard §5, owner decision 2026-07-17: with a
  confirmed MG6 restructure plan, bodies are restructured-to-standard and the original preserved
  verbatim in `original_title`/`original_body` + the export backup; IDs/sections still verbatim.
  The plan path is specified by MIG-6 below.)*

**MIG-6 — Restructure pre-pass: preserve, fail-closed, never auto-split** (→ MG6, issue-standard §5,
Data Model §2)
- Level: unit + integration (`tests/test_backlog_restructure.py`)
- Setup: `discodon-mini` records + a v1 restructure plan (titles/kinds/sections/non-atomic flags).
- Action: `restructure.parse_plan` + `apply`; `import --restructure`; `restructure-preview`.
- Expected: validation is **fail-closed** (typo'd PFX / unknown key / bad kind refuses the whole run
  *before* the data plane; nothing is created); a changed title/body stashes `original_title`/
  `original_body` **verbatim-recoverable** (JSON-string block encoding survives fenced content); an
  identical rewrite leaves no `original_*` residue; bodies compose through the shared
  `issuefmt.render_body` templates; `kind:` backfills (relabel warns); non-atomic items are **flagged,
  never split**; the preview renders from the same `apply` result the import consumes; re-run with a
  plan stays idempotent (skip-if-exists — an existing issue is never rewritten).

**MIG-2 — Multi-prefix absorption stress** (→ DM4, Data Model §5, NFR §7)
- Level: unit
- Setup: prawduct's own `BKL/ADR/ADV/MET/CRT…` prefix set + a synthetic 27–58-prefix spread (hallucinote
  has 31 prefixes used exactly once).
- Action: import.
- Expected: every hand-minted prefix maps to a **permanent** `id:PFX` alias; no new PFX is minted;
  collisions are caught (ID-3); resolution of any old ref succeeds.

**MIG-3 — Export full-fidelity native graph** (→ MG2/G5/M10, API §2.5, NFR §8)
- Level: integration
- Setup: items with dependencies (native `blocked_by`/`blocking`), a sub-issue tree, timeline/events
  (audit, CC4), and assignee history.
- Action: `export`.
- Expected: the dump serializes the **native graph** (deps, sub-issues, timeline, assignees) — not just
  the body block; it is a cheap **dump** (the test asserts fidelity of the dump, **not** lossless
  one-liner re-import into a non-GitHub backend — that is explicitly out of scope, §8).

**MIG-4 — Cache rebuild / schema-bump: no data loss** (→ Data Model §7, NFR §8/§3.3)
- Level: integration
- Setup: a warm cache; then a `schema_version` mismatch (a bumped schema).
- Action: read after the bump; and separately, delete the cache entirely and read.
- Expected: a schema mismatch **triggers rebuild-from-GitHub**; a deleted cache **rebuilds**, with **no
  data loss** (the cache is derived — a rebuild is always safe, never a data-loss migration); the rebuild
  is a **paced** bounded read burst (O(portfolio), under the core budget — pacing is L3/S3, correctness
  here).

**MIG-5 — Scrub workflow keeps the model in the decision, not the data plane** (→ MG4/G1, API §2.5)
- Level: integration
- Setup: a corpus with stale/obsolete/duplicate candidates.
- Action: run the scrub workflow (`list` + **model-surfaced dedup** surface [`search --like` is a
  post-cache accelerator, W1/W2 — not a slice dependency, API §2.5] → owner-confirm → `status`/`merge` →
  `import` the cleaned set).
- Expected: candidate surfacing and disposition are **owner-confirmed**; the **import step is
  deterministic** (no model in the data plane); **nothing is hard-deleted** (dispose via status/merge,
  DM7). (The model-in-decision boundary is asserted structurally: the import op receives a
  concrete cleaned set, not a model call.)

### 3.11 Provisioning & coexistence (GV5/GV6)

**PROV-1 — Namespaced labels never collide** (→ GV6, Data Model §3, Security §6)
- Level: integration
- Setup: a repo with **pre-existing** non-prawduct labels and issues (never an empty tracker).
- Action: `provision` / `reconcile-labels`.
- Expected: prawduct's `<facet>:`-namespaced labels are created **without colliding** with existing
  labels; the taxonomy is consistent across repos; existing non-prawduct labels are untouched.

**PROV-2 — Non-prawduct issues are out-of-scope, not malformed** (→ GV6, Data Model §3, Security §6/F7)
- Level: unit
- Setup: a repo mixing prawduct-marked items and plain issues carrying no `stage:`/`id:` marker.
- Action: `list` / decode the repo.
- Expected: the adapter **ignores** non-prawduct issues as out-of-scope (not malformed backlog) — **except**
  the anonymous-quarantine case (SEC-7): an **unlabeled non-collaborator filing** is the quarantine
  state, surfaced to triage, not silently ignored.

### 3.12 Governance reconciliation (GV3)

**GOV-1 — `closed_by` authority + bidirectional drift sweep** (→ GV3, API §2.6, Data Model §1.1 v3)
- Level: unit (authority resolution) + integration (the sweep)
- Setup: (a) an item closed **on merge** (a GitHub `closed` timeline event carrying the closing PR/commit
  ref) and, separately, an item **manually** closed with an explicit `--closed-by <handle>`; (b) a corpus
  seeded with two drift cases — an item marked `shipped` whose PR was **closed unmerged** (shipped-but-
  PR-died), and a **merged** PR whose linked item is still **open** (merged-but-item-open).
- Action: read `closed_by` on both closes; run the janitor drift sweep (a periodic `list` + timeline
  scan, deterministic — no model).
- Expected: (a) `closed_by` is read from the **native** timeline event on a merge-close, and from the
  `prawduct:`-block `--closed-by` handle on a manual close (the case a bare `status`→shipped would
  otherwise lose); (b) the sweep detects **both** drift directions and surfaces them to triage; being
  deterministic, it invokes **no model** (G1). This is the explicit price of trading git's ship-atomicity
  for traceability.

### 3.13 Automation & cross-project (AU2 / XP1-XP2)

**BATCH-1 — `batch` per-item partial success; not transactional; safe to re-run** (→ AU2/TF3, API §2.4)
- Level: integration
- Setup: a batch of N idempotent mutations where the fake returns `ok` for some and `rate_limited` for
  others (real partial success).
- Action: run `batch`; then re-run the same batch.
- Expected: `batch` returns a **per-item result array** (some `ok`, some `rate_limited`) — it is **not
  transactional** (a mid-batch failure does not roll back the successful items); the re-run is
  **idempotent** (already-applied items converge, the previously-rate-limited ones now apply); the mass
  grooming workload (TF3) is paced under the write caps (pacing constants are L3/S3, correctness here).

**XP-1 — `file-upstream` provenance + submitted-landing + auth-by-target-owner + `source-key:` dedup** (→ XP1/XP2, API §2.4, Security §1)
- Level: integration
- Setup: a target project owned by a **different owner**; the caller has no local checkout of it.
- Action: `file-upstream` into the target; then **re-file the same source item** (same submitter + source
  digest → same `source-key:`), simulating a retry; then a distinct source item.
- Expected: the item is filed with **no upstream checkout and no drop-box**; it carries stamped
  **provenance** (`source:` + submitter identity) and a **`source-key:<digest>`** marker (API §2.4, Data
  Model §5), and lands in **`submitted`** (a triage state, not the working backlog); auth **resolves by
  the target owner** (owned repo → session identity; foreign repo → user token, Security §1). The **retry
  returns the existing upstream item** (matched by `source-key:`) rather than creating a duplicate; the
  distinct source item creates a new one. Distinct from SEC-7 (the *anonymous/non-collaborator* path;
  this is *authenticated* cross-project filing) and from AG3 advisory dedup (this is deliberate
  retry-safety, not a similarity hint).

### 3.14 Cost & operability (NF1 / NF2 — design-guaranteed §16(5) rows)

These discharge the NFR §2/§8 rows explicitly folded into the "Test Specs (§16(5))" bundle by NFR §9
("every design-guaranteed row in §2/§8"). They are cheap proof-of-delegation assertions, not load tests.

**OPS-1 — Cost is O(1) in project count** (→ NF1/G4, NFR §2)
- Level: integration
- Setup: an onboarded portfolio; onboard an **Nth** project.
- Action: assert the recurring-cost surface.
- Expected: onboarding the Nth project adds **no recurring resource** (no per-project server, queue, or
  paid resource) → the recurring-cost delta is **$0**; cost does not scale with project count.

**OPS-2 — Local artifacts are disk, not dollars** (→ NFR §2, Data Model §6, Security §3)
- Level: integration
- Setup: a warmed cache + a `briefing_counts` file.
- Action: enumerate the local artifacts.
- Expected: the only local artifacts are **files** (cache, counts) — **gitignored** (SEC-8) and
  **rebuildable** (MIG-4); no artifact is a recurring paid resource.

**OPS-3 — No server required for correctness** (→ NF2, NFR §8)
- Level: integration
- Setup: run the full CRUD + query + `pick` surface with **no daemon/cron** running.
- Action: exercise the surface.
- Expected: correctness holds with **no supervised process** (the detached refresh is a subprocess, not a
  daemon; a janitor/drift sweep is a periodic *workflow*, not a service required for correctness). Backup
  is the `export`/`import` pair (MIG-3), not an operational burden.

## 4. Build-time measurement probes (L3) — numbers, not booleans

These produce **measured values against a target**; the honest status of each target is `target` (per
the NFR discipline), and the probe is the gate that promotes it. They are **not** CI pass/fail.

| Probe | Measures | Target (NFR) | Gate |
|---|---|---|---|
| **PROBE-LAT** | p95 latency: CRUD write, online read, warm read, `pick` fan-out | < 2 s write · < 1.5 s online read · < 500 ms warm · `pick` **W1-gated, not slice-native** (settled 2026-07-28) | at build, before "done" |
| **PROBE-RATE** | which limit each op decrements (creation-vs-edit granularity); core reads/sec sustainable; grooming core-bound; 500/hr + 900 pts/min under a real creation burst | the §3.1/§3.2 rate model | `verify-api` + S3 |

~~`pick`'s < 2 s floor **assumes** a batched-GraphQL fan-out~~ — **settled 2026-07-28: the batched path
was never built** (no GraphQL in `lib/backlog/`), so `pick` runs N+1 REST over `gh`. S2 pinned the
constant at ~12.4 s / ~209 issues, dominated by the `_all_issues` full-scan rather than the
per-candidate reads; the < 2 s floor is **W1-gated**, not slice-native. Note the trap this probe fell
into: it was **candidate-parameterized against a fan-out that ignored the candidate count**, because
`limit` was applied after the fan-out had already run over every eligible issue — so its flatness was
read as evidence of batching when it was evidence of nothing. Chunk 05b bounded the fan-out by `limit`,
which makes the parameterization meaningful for the first time. PROBE-RATE's creation-vs-edit granularity is `target`-grade (GitHub does not document it —
the probe watches which limit each call actually decrements).

## 5. Empirical spikes (L4) — one-time proving increments

Named here for traceability; **designed in PRD §11 / NFR §3**, not re-designed. Each settles a design
fact, not a repeatable assertion.

- **SPIKE-S1** — cloud-proxy transport reach (does the proxy intercept arbitrary HTTPS or only `gh`?);
  confirm ETag/304; confirm the **issue-number-non-reuse** fact M6 leans on. *(Coherence flag,
  §8: "GitHub never deletes issues" is false — a repo admin / org owner **can** permanently delete an
  issue; the load-bearing half is "never **reuses** numbers" — the per-repo counter skips a deleted
  number, never re-issues it — which holds; the migration tests lean only on the no-reuse half.)*
- **SPIKE-S2** — migration dry-run on discodon (317 open + 1,754-line archive): body-fidelity, ID
  aliasing, relationship reconstruction, archive-as-closed-issues volume/noise, rollback-free resume,
  **batched-vs-N+1 fan-out** (pins the `pick` floor), **node_id stability across transfer** (ID-4's open
  fact). Run **prawduct-first** (dogfood) and after the scrub.
- **SPIKE-S3** — rate limits under load: cold sweep reads/sec; write-heavy grooming confirms core-bound;
  500/hr + 900 pts/min burst under a real creation burst; per-op granularity via `verify-api`.
- **SPIKE-S5** — attachment inline-render on private (release-asset URL vs attachments-branch raw URL) —
  decides `attach`'s idempotency key (content-hash vs name-keyed), which parameterizes attach idempotency
  (deferred until S5, §8).

## 6. Fixtures, doubles & harness

**The transport-seam fake ("fake GitHub").** An in-process implementation of the **subset** of GitHub the
adapter uses: issue create/get/update; label add/remove; `state_reason` set (valid values
`completed`/`reopened`/`not_planned`/`duplicate`/`null`); the timeline events the decoder reads — over
**GraphQL** for `MarkedAsDuplicateEvent.canonical` (the REST issue-event carries no canonical pointer)
and the `closed` event (carrying the closing PR/commit ref for GV3); native **sub-issue** edges and
native **dependency** edges (REST `blocked_by` / `blocking`, GA 2025-08-21); the REST list endpoint
(read-your-writes-in-practice, with an optional 404-replication-window mode); ETag/304 conditional
responses on the REST get. It is **stateful** (remembers labels/state across calls — required for re-run
convergence) and supports **fault-injection** (fail the n-th mutating call; return `rate_limited`; stall
past T; emit raw output with a planted token).

**CONTRACT-1 — the fake's *shapes* match real GitHub** (L2) — **and what it does not cover**
- The `verify-api` probe records real `api.github.com` REST/GraphQL responses for each call the adapter
  makes (against a throwaway test repo); a **shape-diff** asserts the fake's response **shapes** match
  (field names, types, enum values, envelope structure). A shape divergence (GitHub changed a payload)
  **fails CONTRACT-1** — this is what keeps the L1 suite's *shape* assumptions from going stale, and it
  discharges Data Model §8 open-Q1 / API §11.
- **It does not guard behavior.** Read-your-writes *timing*, the 404-after-create window, timeline-event
  *ordering*, and label-set *semantics* are invisible to a shape-diff. Those are verified once by the L4
  spikes and re-checked by the **L5 live-smoke** set — a behavioral drift in GitHub passes CONTRACT-1 and
  must be caught at L5 (§2.1, §8).

**Recorded fixtures.**
- `discodon-mini` — a representative `backlog.md` slice + archive lines (drives MIG-1/CRASH-4).
- `multi-prefix` — prawduct's `BKL/ADR/ADV/MET/CRT…` + a synthetic 27–58-prefix spread (MIG-2).
- `torn-states` — issues in each partial/torn label state (ENC-5, CRASH-1).
- `token-bait` — raw outputs seeded with one token of each scrub class (SEC-1).
- `two-identity` — the broad/narrow identity pair + a cross-repo item (SEC-4).
- `drift-corpus` — the two GV3 drift cases: shipped-but-PR-died, merged-but-item-open (GOV-1).

**Live test repo (L5).** A throwaway GitHub repo for `verify-api` (L2), the live smoke set (one real
round-trip per front: `file` via CLI, one MCP call, one `import`+`export`), and the **periodic behavioral
re-checks** (read-your-writes, the replication window, timeline ordering) that CONTRACT-1 cannot see —
plus the S1/S2/S3/S5 spikes.

**Property-based candidates** (per `project-preferences` lib): ENC-2 (two-axis round-trip), ENC-4 (block
round-trip fidelity), ID-1 (ID-spelling normalization idempotence), SEC-1 (scrub over the token-pattern
set). Round-trip and invariant-preservation properties — see the template's property section.

## 7. Coverage matrix — every obligation → its test

The completeness spine (Complete Delivery, P2). Left column = the obligation clusters catalogued from all
six design docs; right = the test(s) or the explicit reason it is **not** an L1 test. Cross-doc
duplicates (the same behavior stated in 4–5 docs) collapse to one row.

| Obligation (source cluster) | Discharged by |
|---|---|
| G1/AG1 zero-model-tokens on CRUD | **INV-1** |
| AG1 one-non-interactive-call / no TTY | **INV-2**, SEC-6 |
| CC1/M5 crash-safe two-axis transition | **CRASH-1** |
| AU3 merge redirect-before-close | **CRASH-2** |
| AU3 split recover-by-cleanup, keyed | **CRASH-3** (full no-duplicate — `split-op:` key pinned in API §2.3) |
| MG1/M6 import resumable/idempotent | **CRASH-4**, MIG-1 |
| TF2 verify keyed idempotent | **CRASH-5** |
| CC3/M11 claim take-and-verify / TTL reap | **CRASH-6** |
| G3/D5 cacheless staleness=0 | **FRESH-1** |
| G3 cached read visible age | **FRESH-2** |
| G3/M2 decision read revalidates (304, REST) | **FRESH-3** |
| G3 never silently stale (negative) | **FRESH-4** |
| G2/AG4 write never hangs (timeout T) | **BLOCK-1** |
| G2 read degrades never hangs | **BLOCK-2** |
| G2/C3 never retry-loops; retryable distinct | **BLOCK-3** |
| PRD §8.1 offline queued/`unavailable` envelope | **BLOCK-4** |
| GV2/M3 briefing never blocks start | **BLOCK-5** |
| DM1 soft-enum flag-not-reject | **ENC-1** |
| DM2 two axes never flattened | **ENC-2** |
| Data Model §2 last-block-wins (BKL-7M4Q) | **ENC-3** |
| Data Model §2/§7 tolerant block parse | **ENC-4** |
| Data Model §4 / CC5 decoder precedence + self-heal | **ENC-5** |
| `state_reason: duplicate` / fail-open decode (GraphQL canonical) | **ENC-6** |
| API §4 full error-code vocabulary | **ERR-1** |
| AG6 JSON-sole-stdout pipe safety | **ERR-2** |
| API §3 envelope uniform across 3 fronts | **ERR-3** |
| API §3 warnings advisory-not-fatal | **ERR-4** |
| API §8 null-vs-absent *(implied-not-named)* | **ERR-5** |
| boundary exceptions caught not swallowed | **ERR-6** |
| D4 ID four-spelling normalization | **ID-1** |
| D4 ambiguous_id *(implied-not-named)* | **ID-2** |
| DM4/F3 alias-collision guard | **ID-3** |
| DM4/M4 redirect on merge/transfer | **ID-4** (node_id fact → S2) |
| Q1-structured/M8 list read-your-writes + 404 edge | **QRY-1** (404 edge L5-owed) |
| GV1/DM3/CC3 pick list-then-fan-out correctness | **QRY-2** |
| Q1-fulltext/Q3 search cache-served; semantic capability-probed | **QRY-3** |
| Q5/Q4 counts-on-read; rollup fan-out | **QRY-4** |
| Q2/AU1 sync changed-since cursor | **QRY-5** |
| F2/N4 no token in output; scrub patterns | **SEC-1** |
| Security §2 mass-assignment guard | **SEC-2** |
| CC4/N3 attribution off API identity, once/process | **SEC-3** |
| F4 fetch-time cache auth *(implied-not-named)* | **SEC-4** |
| F1 Actions untrusted-trigger withhold *(implied-not-named)* | **SEC-5** |
| Security §1a unattended: no-prompt/fail-clean/automated/idempotency-narrow | **SEC-6** |
| F6/F7 PV3 enable-gate + quarantine *(enable-gate implied-not-named)* | **SEC-7** |
| F5 cache-gitignored / doctor-verifies *(dropped in v1 — added)* | **SEC-8** |
| MG1 import fidelity (verbatim no-plan path; §5-revised plan path preserves originals) | **MIG-1**, MIG-6 |
| MG6 restructure pre-pass (restructure, preserve, no split) | **MIG-6** |
| DM4 multi-prefix absorption | **MIG-2** |
| MG2/G5/M10 export native-graph fidelity | **MIG-3** |
| Data Model §7 cache rebuild / schema-bump no-loss | **MIG-4** |
| MG4/G1 scrub model-in-decision | **MIG-5** |
| GV5/GV6 namespaced labels no-collision | **PROV-1** |
| GV6/F7 non-prawduct issues out-of-scope | **PROV-2** |
| GV3 closed_by authority + bidirectional drift sweep *(dropped in v1 — added)* | **GOV-1** |
| AU2/TF3 batch per-item partial success *(mis-routed in v1 — added)* | **BATCH-1** |
| XP1/XP2 file-upstream provenance/submitted/auth-by-owner *(mis-routed in v1 — added)* | **XP-1** |
| NF1/G4 cost O(1) in project count *(dangling pointer in v1 — added)* | **OPS-1** |
| NFR §2 local-artifacts-disk-not-dollars | **OPS-2** |
| NF2 no-server-for-correctness | **OPS-3** |
| AG5 latency p95 targets | **PROBE-LAT** (L3 — number, not CI) |
| NF3 rate model / per-op granularity | **PROBE-RATE** (L3) + S3 |
| S1/S2/S3/S5 empirical facts | **SPIKE-S1/2/3/5** (L4 — one-time) |
| the L1 fake's *shape* fidelity to GitHub | **CONTRACT-1** (L2 — shape only) |
| the L1 fake's *behavioral* fidelity | **L5 live smoke + spikes** — NOT shape-checkable (§2.1/§8) |
| MCP deep behavior | inherited (ERR-3 smoke) — **intentional**, §1.1 |
| CC2 no-lost-updates *correctness* | **out of scope here** — CC2 optimistic-concurrency, §8 |
| XP3 submit-without-read on private upstream | **anti-test** — descoped, §8 |
| Security "not defended" list | **anti-tests** — §8 |

**Deferred (named, not yet an L1 test — honest gaps):** `attach` idempotency (key is S5-dependent —
becomes concrete once SPIKE-S5 resolves); the exact CLI exit-code integers (build-time coherence check vs
`prawduct-hook`, API §11); `~200 writes/day` steady-state (an owner estimate → telemetry, not a test,
§8); the `discodon` marooned-item / stale-snapshot rescue (SOL-K3PN) — an S2 migration observation, not
an L1 case. Each is listed so it is **visibly owed**, not silently dropped. *(The v1 `split` and
`file-upstream` idempotency-key gaps have since been **resolved** — the keys are pinned in API §2.3/§2.4,
so CRASH-3/XP-1 assert them fully; see §8 debts 2–3.)*

## 8. Out of scope / anti-tests, and known limits

Stating what is **deliberately not tested** (Scope Discipline, P12; honest coverage boundary):

- **The Security "not defended" list** — GitHub itself compromised; a trusted repo-write collaborator
  acting maliciously; nation-state; the owner's laptop compromised. Explicit non-goals; **no test**
  because no defense is claimed.
- **CC2 concurrency *correctness* (no lost updates)** — proven by optimistic-concurrency/CAS at the
  `update` op (ERR-1 covers the `conflict` code); the *capacity* ceiling of concurrent readers is L3/S3.
  This doc does **not** re-litigate lost-update correctness as an NFR — it is a success criterion owned
  by CC2.
- **XP3 (submit-without-read on a private upstream)** — descoped by owner decision; an **anti-requirement**.
- **Lossless one-liner re-import into a non-GitHub backend** — export is a cheap *dump* (MIG-3); full
  reconstruction into a foreign backend is explicitly not a fidelity claim (G5/M10).
- **L3 numbers as CI pass/fail** — latency/rate targets are `target`-grade, promoted by a build probe,
  **not** asserted green in the fast loop (asserting a p95 in CI would be flaky and dishonest).
- **`~200 writes/day`** — an owner estimate to be **confirmed by telemetry**, not a test.

**Known limit (not a gap — an honest boundary):** L1 green is conditional on the fake's **behavioral**
fidelity, which CONTRACT-1's shape-diff cannot guarantee (§2.1, §6). A GitHub behavioral drift
(read-your-writes timing, the 404 window, timeline ordering) passes CONTRACT-1 and is caught only at L5.
This is stated, not hidden — the alternative (pretending a shape-diff proves behavior) is the exact
over-claim this doc's discipline forbids.

**Peer-doc coherence debts filed here — all four RESOLVED in the 2026-07-16 sweep** (the peers were
touched-up right after this drill-down; recorded here as the close-the-loop trail):
1. **Semantic-search gating framing** — the API contract's "semantic … hybrid-search-gated" / "hybrid-search
   enablement" wording was inaccurate: improved/semantic issue search is **GA, on by default** (~10/min),
   with **no per-repo hybrid gate**. **Resolved** — API §2.2/§4/§7 reframe `--semantic`'s `unsupported` as a
   capability probe (API §12b/K3); NFR §7 + PRD §9 corrected. QRY-3 already encodes this.
2. **`split` idempotency/matching key** — was "detect already-created children **by link**," not a concrete
   key. **Resolved** — API §2.3 pins the **`split-op:<token>#<index>`** key (Data Model §5); CRASH-3 now
   asserts full no-duplication.
3. **`file-upstream` `keyed` idempotency** — API §2.4 marked it `keyed` with no key. **Resolved** — API §2.4
   pins the **`source-key:`** marker (Data Model §5); XP-1 now asserts retry-dedup.
4. **"GitHub never deletes issues"** — false (admins can permanently delete). **Resolved** — API §2.5 + PRD
   §9/§11/§13 lean only on the load-bearing "never **reuses** numbers" (delete is an admin-only destructive
   action; a deleted number is retired, not recycled); SPIKE-S1 confirms.

## 9. Self-review (adversarial, 2026-07-16)

| # | Category | Finding | Disposition |
|---|---|---|---|
| T1 | altitude | Is this test-code masquerading as a spec? | **Held to spec altitude** — §1 pins spec-not-code; each test names what/how/pass-fail + a fixture, never function names or assertion syntax (parallels the API contract's altitude line). |
| T2 | honesty | Do any "tests" secretly assert an unmeasurable/one-time thing as if repeatable? | **Separated** — L3 (numbers) and L4 (one-time spikes) are pulled out of the L1 pass/fail bulk (§2); §8 states L3 is not CI-green. |
| T3 | completeness | Did the drill-down drop an obligation? | **§7 matrix** maps every catalogued cluster to a test or an explicit anti-test/deferral; the previously **implied-not-named** obligations (split-cleanup, null-vs-absent, ambiguous_id, F4 cache-auth, F1 withhold, PV3 enable-gate) are named tests. **v2 closed six coverage holes the independent review caught** (GV3, F5, batch, file-upstream, sync, cost/operability) that v1 had routed to non-covering pointers. |
| T4 | trust | Can the L1 suite go false-green if the fake lies? | **Named as a bounded limit, not overclaimed** — CONTRACT-1 guards **shape** only; **behavioral** fidelity is spike-verified-once + L5-guarded (§2.1/§8). v1's "CONTRACT-1 makes L1 trustworthy" was an over-claim — corrected. |
| T5 | crash-testing realism | Is "kill mid-transition" actually testable deterministically? | **Yes** — the canonical write-orders make each intermediate state deterministic; the fake fails the n-th call and the test decodes + re-runs (CRASH-1/2/4). **CRASH-3 (split)** was v2's exception (no upstream matching key); the 2026-07-16 sweep pinned the `split-op:` key in API §2.3, so CRASH-3 now asserts full no-duplication (§8 debt 2 resolved). |
| T6 | coherence | Does a test lean on a false platform fact? | **Four flagged and corrected/filed** (§8): semantic-search gate (fixed in QRY-3), the 404-window "documented" claim (softened in QRY-1), the duplicate-canonical transport (ENC-6 pinned to GraphQL), and "never deletes issues" (SPIKE-S1 note). |
| T7 | proportionality | Is a full test-spec proportional for a personal $0 tool? | **Yes, bounded** — depth tracks the **governance** stakes (this backend underpins prawduct's own backlog); most tests are cheap L1 unit tests against one fake; the expensive layers (L4 spikes) already existed as §11 spikes; the cost/ops tests (OPS-1..3) are one-line delegation assertions. |
| T8 | front-coverage | Does testing the core stand in for the whole contract? | **Guarded** — §1.1 attaches each test to a front; CLI-only concerns (exit codes, pipe safety, non-interactive env) get their own tests; MCP is one smoke + inherited (flagged intentional, not a gap). |

*Independent review folded (2026-07-16, Principle 14):* a fresh-eyes test/design critic + a
GitHub-platform-fact verifier reviewed v1 — the same two-reviewer pattern the Data Model / Security /
API-contract / NFR drill-downs used. Confirmed findings are folded below and inline.

### 9a. Independent review (test/design critic + GitHub-fact verifier, 2026-07-16) — folded into v2

| # | Sev | Finding | Disposition in v2 |
|---|---|---|---|
| C-GV3 | blocking | GV3 (closed_by + bidirectional drift sweep) silently dropped behind a §10 pointer to MIG-1/§8 that covered neither | **Folded** — new **GOV-1** (§3.12) + matrix + traceability rows |
| C-CONTRACT | blocking | CONTRACT-1 claimed to make L1 "trustworthy," but a shape-diff cannot see behavioral fidelity (read-your-writes timing, replication window, timeline ordering) — a false-green hole | **Folded** — §2.1/§6 split shape-vs-behavior fidelity; behavioral fidelity routed to L4 spikes + a new L5 periodic behavioral re-check; §8 states the residual limit |
| C-F5 | major | F5 cache-must-stay-gitignored / doctor-verifies (the content-borne-secret defense) dropped behind a MIG-4/SEC-1 pointer covering neither | **Folded** — new **SEC-8** (§3.9) |
| C-NF1 | major | NF1 cost-O(1) + the NFR §2/§8 design-guaranteed rows routed to a location (§4/§8) that contained nothing | **Folded** — new **OPS-1..3** (§3.14) |
| C-Q2 | major | Q2 `sync`/changed-since cursor + AU1 polling entirely absent | **Folded** — new **QRY-5** (§3.8) |
| C-AU2 | major | AU2 `batch` per-item partial-success routed to ERR-1, which tests only the `rate_limited` code | **Folded** — new **BATCH-1** (§3.13) |
| C-XP | major | XP1/XP2 `file-upstream` (a PRD §4 success criterion) routed to SEC-7, a different (anonymous) front | **Folded** — new **XP-1** (§3.13); `keyed`-idempotency gap filed (§8) |
| C-SPLIT | major | CRASH-3 (split) asserts "no duplicate C1" against a matching key the design never pins ("by link") | **Folded** — CRASH-3 narrowed to bounded-duplication + marked blocked; upstream key-gap filed (§8) |
| C-SEAM | minor | "single test seam" contradicted by INV-1's model-client seam + §3's two-seam preamble; MCP "per surface class" vs one smoke | **Folded** — "single" → "primary" seam, narrower seams named (§2.1); MCP wording aligned to one smoke (§1.1) |
| F-SEM | over-claimed | `--semantic → unsupported` on a per-repo hybrid-search gate that does not exist (semantic search is GA, on by default, 10/min) | **Folded** — QRY-3 re-grounds `unsupported` on a genuine capability-absence probe; rate cap → `rate_limited`; peer-doc wording flagged (§8) |
| F-404 | over-claimed | QRY-1 called the 404-after-create replication window "documented" — it is observed/undocumented | **Folded** — "documented" struck; reframed observed + L5-owed |
| F-DUP | transport-nuance | ENC-6 reads `superseded_by` from "the timeline event," but only **GraphQL** `MarkedAsDuplicateEvent.canonical` carries it (REST issue-event does not) | **Folded** — ENC-6 + §6 fake pin the GraphQL shape |
| F-ETAG | coherence | ETag/304 is REST-only; a GraphQL fan-out has no conditional request | **Folded** — FRESH-3 specifies the revalidated read is the REST `get` |
| F-DEP | coherence | native dependency REST terms are `blocked_by`/`blocking` (draft said "blocks") | **Folded** — QRY-2/MIG-3/§6 aligned |
| F-facts | confirm | rate caps (80/min, 500/hr, 900 pts/min), ETag-304-free, sub-issues+dependencies GA, `gh` env knobs, transfer-renumber, no-number-reuse | **Confirmed** — no change; verifier cited 2026 docs |

## 10. Traceability

Every §3 test cites its parent; the reverse for the invariants/capabilities this doc proves:
**G1/AG1**→INV-1 · **AG1/§8**→INV-2 · **G2**→BLOCK-1..5 · **G3**→FRESH-1..4 · **G5/MG2**→MIG-3 ·
**CC1/M5**→CRASH-1 · **CC2**→ERR-1(`conflict`)+§8 · **CC3**→CRASH-6/QRY-2 · **CC4**→SEC-3 · **CC5**→ENC-5 ·
**DM1**→ENC-1 · **DM2**→ENC-2 · **DM3**→QRY-2 · **DM4**→ID-3/ID-4/MIG-2 · **DM5**→(comment; ERR-3 envelope) ·
**DM6**→attach (deferred, S5) · **DM7**→CRASH-2/MIG-5 · **TF1**→FRESH-2 · **TF2**→CRASH-5 · **TF3**→
BATCH-1/MIG-5 · **Q1-struct**→QRY-1 · **Q1-full/Q3**→QRY-3 · **Q2**→QRY-5 · **Q4**→QRY-4 · **Q5**→QRY-4 ·
**XP1/XP2**→XP-1 · **XP3**→§8 anti-test · **AU1**→QRY-5 (polling baseline) · **AU2**→BATCH-1 · **AU3**→
CRASH-2/CRASH-3 · **GV1**→QRY-2 · **GV2**→BLOCK-5 · **GV3**→GOV-1 · **GV5/GV6**→PROV-1/PROV-2 · **MG1**→
CRASH-4/MIG-1 · **MG2**→MIG-3 · **MG3**→(per-project coexistence — PROV/OPS-1) · **MG4**→MIG-5 ·
**MG6**→MIG-6 · **PV2**→
SEC-2/SEC-3 · **PV3/PV4**→SEC-7 · **NF1**→OPS-1/OPS-2 · **NF2**→OPS-3 · **NF3**→PROBE-RATE · **AG5**→
PROBE-LAT · **F1**→SEC-5 · **F2**→SEC-1 · **F3**→ID-3 · **F4**→SEC-4 · **F5**→SEC-8 · **F6/F7**→SEC-7/
PROV-2 · **S1/S2/S3/S5**→SPIKE-* · **verify-api / Data Model §8 open-Q1 / API §11**→CONTRACT-1 (shape) +
L5 (behavior). **Coherence:** §3 fixtures ↔ Data Model §5 (aliases) + Security §4 (scrub patterns); §7
matrix ↔ NFR §9 owner map (L1/L3/L4 split mirrors the Test-Specs/build-probe/S-spike owners); §8
anti-tests ↔ Security §8 (not-defended) + PRD §14 (out of scope); §8 peer-doc debts ↔ API §2.2/§2.3/§2.4
+ NFR §10a.