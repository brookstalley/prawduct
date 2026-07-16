# Backlog Service — Non-Functional Requirements

`status: draft v1 — initial drill-down from PRD §16(2): turns §9's cost/ops/rate budgets and the AG5/§4 latency targets into testable NFRs. Centerpiece is the per-operation rate-budget table built on the Data Model's M5 write-cost split (only issue/comment creation spends the scarce ~500/hr content cap; every label/state/body edit + read spends the abundant 5k/hr core). Frames every target as floor (must hold in the cacheless online slice) vs accelerated (cache/App-gated), and pairs each with a measurement + verification owner (S2/S3/build probe). · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4 — esp. §4 success criteria, §9 NF1–3,
AG4/AG5, G2/G3/G4, S2/S3, O5/D8), and through it
`documentation/backlog-service-requirements.md`. Coheres with
`documentation/backlog-service-data-model.md` (the M5 write-cost split, the cache/ETag schema) and
`documentation/backlog-service-api-contract.md` (the operation surface each budget is charged against,
the `rate_limited`/`unavailable` codes). This doc **quantifies** what those describe; it does not
re-derive the encoding or the operation set.

**Risk profile (proportional — Principle 11).** A personal/small-portfolio backlog whose backend is
**GitHub itself**, at **$0/month**. Almost every classic NFR (capacity planning, server SLOs,
scaling tiers, DR) is **GitHub's problem, delegated**. The NFRs the *adapter* genuinely owns are the
handful where our code sits between the agent and GitHub: **the rate budget it spends**, **the latency
it adds or hides**, **how cleanly it degrades when GitHub is unreachable**, and **the freshness it
promises**. Those four get real numbers; the rest is a short "delegated, here's the test that proves it
stayed $0" (§2/§3).

**Testability discipline (the charter of this doc).** §16(2) asks for budgets "made testable." So every
target below is stated as a tuple — **Target · Measured by · Verified by · Status** — where *Status* is
one of **verified** (a fact confirmed against 2026 GitHub docs + the local `gh 2.86.0` probe),
**target** (a design goal to *measure* at build, not yet observed), or **unverified** (a number we do
**not** trust yet and must confirm before relying on it). Asserting a number without a measurement plan
is exactly the trap this doc refuses (the scriob "deferred" precedent, API contract §5).

**Floor vs. accelerated — the load-bearing split.** The PRD's architecture is a correct **cacheless
online slice** plus **optional layers** (§6, D5). NFRs inherit that split:
- **Floor** — must hold in the P0 cacheless slice, on the **user token** (O5), with no cache and no App:
  every read live (staleness 0), write p95 < 2 s, never-block degradation, $0, migration paced under the
  content cap.
- **Accelerated** — only reachable with an *optional* layer and therefore **not** a slice guarantee:
  warm read < 500 ms (needs the P1 cache), 48-reader sweep rate-safe (needs the cache — the M7 point),
  per-owner rate isolation (needs the App). Claiming a floor number that secretly needs the cache is the
  M7 defect this doc is built to not repeat.

---

## 1. NFR inventory (the map)

| # | Dimension | Owner | Governing req | Section |
|---|---|---|---|---|
| NFR-C | **Cost** — $0/month, O(1) in project count | delegated (GitHub free tier) | NF1, G4, §4 | §2 |
| NFR-O | **Operability** — near-zero; no server, no backup burden | delegated + one local artifact | NF2 | §8 |
| NFR-R | **Throughput / rate budget** — the real scarce resource | **adapter** | NF3, S2, S3 | §3 |
| NFR-L | **Latency** — CRUD p95, read, `pick`, session-start | **adapter** | AG5, §4 | §4 |
| NFR-F | **Freshness** — staleness bound, visible age | **adapter** | G3, D5 | §5 |
| NFR-A | **Availability / degradation** — never-block budget | **adapter** | AG4, G2 | §6 |
| NFR-S | **Capacity / scale** — portfolio size, concurrency | mixed | §4, TF3 | §7 |

The four **adapter-owned** dimensions (R/L/F/A) carry the design weight; C/O/S are largely delegated and
get a proof-of-delegation test rather than a budget.

## 2. Cost (NF1) — $0/month, no per-project cost

| Claim | Measured by | Verified by | Status |
|---|---|---|---|
| No billable service — Issues, labels, org Fields, one GitHub App are all **free** | inventory the deployment: assert no paid API, no hosted compute, no managed store | GitHub pricing (2026) | **verified** |
| Cost is **O(1) in project count** — adding a repo adds no recurring cost | onboard an Nth project; assert the recurring-cost delta is $0 | design (no per-project resource) | **verified** |
| The only local artifacts (cache, counts file) are **disk, not dollars** | assert they are local files, gitignored, rebuildable | Data Model §6 | **verified** |

**Visible non-dollar costs (Principle 9 — name them at design, not after deploy).** "$0/month" is true
in dollars and would be a lie if it hid the real scarce resources. They are: **(1) the rate budget**
(§3 — the actual ceiling on how fast the fleet can work), **(2) latency** of live reads (§4 — the price
of freshness-beats-latency), **(3) local disk** for the optional cache (bounded by portfolio size, §7),
and **(4) a sliver of ops** (§8 — the cache path must stay gitignored; a schema bump rebuilds it). None
is a bill; all are budgets a heavy workload can exhaust, so they are sized, not waved away.

*The GitHub App is free too* — it changes the *rate bucket* (§3), not the dollar cost; adopting it never
introduces a charge (G4/GV4).

## 3. Throughput & rate budget (NF3) — the adapter's real constraint

This is the NFR with teeth. GitHub gives generous budgets, but they are **not one pool**, and conflating
them is how a migration or a fleet sweep silently wedges. **Two budgets, and which one an operation
spends is the load-bearing fact (Data Model M5):**

### 3.1 The two budgets

| Budget | Ceiling | Spent by | 304 / conditional |
|---|---|---|---|
| **Core** (reads + non-creation writes) | **~5,000/hr** per identity | every read (`get`/`list`/`search`/`pick`); **label** add/remove; **state** open/close; **body** PATCH; assignee | an ETag **304 costs nothing** against it (M2) — revalidation is ~free |
| **Content-creation** (secondary, tight) | **80/min *and* ~500/hr** | **only** creating an **issue** or a **comment** | n/a (creation is never conditional) |
| **Search** (separate endpoint) | ~30/min general, ~10/min code-search; **semantic/hybrid ≈ ?** | `search --semantic` (P2) only — lexical/fulltext are cache-served | n/a |

All three: **verified** except the **semantic/hybrid search rate**, which is **unverified** (an earlier
"10/min" looked conflated with the code-search cap; §9). The core and content figures are confirmed
against 2026 docs + the local `gh` probe.

### 3.2 Which operation spends which budget (the M5 map, made per-op)

Charged against the API contract §2 surface:

| Operation | Budget | Cost | Note |
|---|---|---|---|
| `file` (create) | **content** (~500/hr) | 1 creation | the scarce path |
| `import` (migrate) | **content** | 1 creation **per item** | the burst — §3.3 |
| `split` | **content** | 1 creation **per child** | creates issues, like `file` |
| `file-upstream` | **content** | 1 creation | low-volume, moot (§3.3) |
| `comment` | **content** | 1 creation | why verification is **not** a comment (M6) |
| `get` / `list` / `pick` / `counts` / `search` / `rollup` | core | 1+ reads | 304-revalidatable; warm cache = **0** |
| `update` (body/labels) · `status` · `claim`/`unclaim` · `link`/`unlink` · `verify` · `merge` | core | 1–3 calls | **not** creations — label/state/body edits (incl. `merge`'s `superseded-by:` redirect) |
| `attach` | core (+ **?**) | release/git-data calls | whether **release creation** counts against the content cap is **unverified** — confirm at build (S5-adjacent) |

**The reclassification this table buys:** a **grooming sweep** (relabel / close / merge / verify N items)
is **core-bound** — 5,000/hr is abundant, so grooming is cheap *on writes*; its real cost is the
**reads** to find the candidates (§3.3). A **migration or split-heavy** run is **content-bound** — 500/hr
is scarce and it is the only thing that must pace across the clock. This is the opposite of the intuitive
"writes are expensive"; encoding it here keeps the build plan from pacing the wrong axis.

### 3.3 Workloads sized against the budgets

| Workload | Dominant cost | Binding budget | Fits the floor? |
|---|---|---|---|
| **Migration import** — discodon (317 open + a 1,754-line archive) | issue creation | **content ~500/hr** | **only if paced across time** — 317 creates alone is ~40 min at the cap; +archive can exceed 500/hr in one burst. The **MG4 scrub trims the archive** so it fits; the import is **resumable/idempotent** so a pause-and-resume is safe (S2 proves it). |
| **Grooming sweep** (relabel/close/merge N) | reads to find candidates | core 5k/hr | writes fit trivially; a large **cacheless** read-fan-out can approach 5k/hr → **cache-gated cheapness (M7)** |
| **48-agent read sweep** (TF3 mass grooming) | reads | core 5k/hr **per identity** | **NOT a floor guarantee** — cacheless, 48 agents share one user-token 5k/hr and can exhaust it; **warm-cache reads bypass GitHub entirely** → this workload is *why the cache exists*. The cacheless slice is rate-safe **only for low-fan-out use** (§4/§9, honest scope). |
| **Steady state** (~200 writes/day personal portfolio) | mixed | all caps | fits with wide margin — ~200/day ≈ 8/hr avg, far under 500/hr content |
| **Upstream / anonymous filing** | issue creation | content | **low-volume → moot**, even on the shared user bucket |

### 3.4 The bucket the budget lives in (O5/D8)

- **P0 slice = user token (O5).** All of the above spend the **human's personal bucket** — 5k/hr core,
  80/min + ~500/hr content. Tolerable for a personal portfolio; the **migration burst is the one stress
  point** (§3.3), which is exactly why the scrub trims write volume.
- **Optional App = per-owner bucket (accelerated).** A GitHub App installation gets its **own** bucket
  per owner — **5,000/hr baseline, +50/hr per repo and per user beyond 20, cap 12,500** (verified) — so
  each owned org's sweeps/grooming/migration are **isolated** from the human's quota. **But the ~500/hr
  content cap is a *secondary* limit that binds *inside every bucket*** — the App raises core headroom,
  **not** the content-creation ceiling. So the App helps the read-heavy 48-agent sweep; it does **not**
  relieve the migration burst.

### 3.5 What S3 must measure (turning NF3 into a test)

S3 is "mostly runtime tuning with one load-bearing constant" (PRD §11). Its job here is to **produce the
pacing constants** the build plan hardcodes:
1. A **cold cache sweep** of a real repo → observed **reads/sec sustainable** before core-limit backoff;
   sets prefetch batch size + backoff curve.
2. A **write-heavy grooming run** → confirms grooming is core-bound (writes cheap) and measures the
   read-to-find-candidates cost.
3. **Confirm the ~500/hr content cap** under a real creation burst (the S2 migration is the natural probe)
   → sets the migration pacing constant.
4. **Resolve the unverified semantic-search rate** (§3.1) → gates only the P2 `search --semantic` path.

Until S3 runs, the constants are **conservative defaults** (pace as if 500/hr content, 5k/hr core, back
off on the first `rate_limited`), never optimistic guesses — the never-block floor (§6) makes an
overrun degrade cleanly rather than hang.

## 4. Latency (AG5, §4)

**Freshness beats latency (G3)** — so these are *ceilings on the cost of being live*, not a mandate to
mirror for speed (the §13-2 adversarial correction; AG5 explicitly "does not mandate a mirror").

| Path | Target (p95) | Floor / Accel | Measured by | Status |
|---|---|---|---|---|
| **CRUD write** (`file`/`update`/`status`/`claim`) | **< 2 s** | **floor** | build probe: N ops, record p95 latency | target |
| **Online read** (`get`/`list`, cacheless slice) | **< 1.5 s** (one live round-trip) | **floor** | same probe, read path | target — **not** the <500 ms figure (no cache in the slice) |
| **Warm cache read** (`get`/`list` hit) | **< 500 ms** | **accel** (needs P1 cache) | cache-hit microbench | target (AG5) — an *accelerated* number, honestly not a slice guarantee |
| **`pick`** (list-then-fan-out) | **< 2 s** + O(candidates) reads | **floor** | **S2** measures fan-out at discodon scale (Data Model §4/open-Q4) | target — cost scales with candidate count, paced under core |
| **Session start / briefing** (GV2) | **network-independent** — reads the local `briefing_counts` file | **floor** | assert **no network call** on the start path; refresh is detached (D6) | design-guaranteed + testable |
| **Decision-driving revalidation** (304) | one conditional round-trip | accel | verify ETag/304 in S1/build (M2) | **verified** (304 costs nothing) |

**Two hard, testable assertions (not just p95 targets):**
- **Zero model tokens on the CRUD path (§4/G1).** The data plane is deterministic code; a test **counts
  model invocations on the `file`/`get`/`update`/`status` code path and asserts 0**. This is a
  pass/fail invariant, not a percentile.
- **One non-interactive call (§4/AG1).** File-or-query completes in a single CLI invocation with no
  prompt — assert the CLI never opens a TTY / never blocks on input (mechanized via
  `GH_PROMPT_DISABLED=1`, no pager, no inherited TTY — API contract §8, Security §1a).

*Measurement method for the p95 figures:* a **build-time latency probe** runs each path K times against a
real repo and records the distribution; p95 is reported, not assumed. Network variance means these are
**targets to observe**, not guarantees — the honest status is *target*, and the probe is the gate that
turns them green (or renegotiates them).

## 5. Freshness (G3, D5)

The project **exists to kill silent staleness**, so freshness is a first-class NFR with a hard bound, not
a soft "eventually."

| Guarantee | Bound | Floor / Accel | Measured by | Status |
|---|---|---|---|---|
| **Cacheless read** | **staleness = 0** — every read is live | floor | assert the slice issues a live fetch per read (no local store consulted) | **verified by construction** |
| **Cached read carries visible age** | age (`fetched_at`) present on **every** cache-served payload | accel | assert every cache read returns a non-null age in the envelope `warnings[]`/field | design + test |
| **Decision-driving read revalidates** | never older than **one conditional request** (ETag/304) | accel | assert a decision-path read issues a conditional request; 304 → reuse, 200 → refresh | **verified** mechanism (M2) |
| **Never silently stale** | no cache read is served past its validator without a revalidation option | accel | negative test: force a stale entry on a decision path → assert revalidation fires or age is surfaced | design invariant (G3/D5) |

The freshness NFR is therefore **strongest in the floor** (staleness literally 0 online) and **bounded,
never silent, in the accelerated cache** — the inversion that makes the optional cache safe to add
without reintroducing the pain it was built to kill.

## 6. Availability & graceful degradation (AG4, G2) — the never-block budget

Never-block is **never-hang / never-corrupt + graceful degradation**, explicitly **not** "always works
offline" (G2). That makes it an NFR with a **timeout budget** and a **degradation contract**, both
testable by fault injection.

| Property | Budget / contract | Measured by | Status |
|---|---|---|---|
| **Write never hangs** | a bounded connect+read **timeout T** on every `gh`/HTTP call → returns `unavailable` (retryable) within T, never blocks | inject an unreachable/slow backend → assert the call returns ≤ T with `unavailable`, never hangs | target (T set at build; conservative default e.g. a few s) |
| **Read degrades, never hangs** | cache-or-`unavailable` — warm cache serves (with age); else a clear `unavailable` + guidance | inject offline → assert warm read serves-with-age, cold read returns `unavailable` | design (AG4) |
| **Never corrupts on a crash** | a crash mid-write leaves a **valid, self-healing** state (idempotent `set-status`; merge redirect-before-close) | kill mid-transition → assert the item reads as a valid state and re-run completes idempotently | **verified by design** (Data Model §4/M5; API contract §2.3) |
| **Never retry-loops** | a caller degrades on *any* error and **does not** loop-until-success (the C3 correction) | assert gates/hooks tolerate `unavailable`/`validation`/`not_found` without a retry loop | design (API contract §4) |
| **Briefing never blocks start** | session start reads the local counts file; the network refresh is **detached** (D6) and skippable | assert start latency is network-independent (§4) | design (GV2/M3) |

**Degradation is modeled on the current briefing** (broad-caught → skipped): a backend failure fails
fast, is logged as retryable, and the session proceeds. There is **no availability SLA** — GitHub's
uptime is GitHub's; our contract is that *our layer never turns a GitHub blip into a hung or corrupted
session*. That is the whole of the availability NFR, and it is fully testable by fault injection.

## 7. Capacity & scale (§4, TF3)

Sized to the **actual portfolio**, not an imagined platform (Principle 11) — capacity numbers exist to
find the point where the cacheless floor stops sufficing and a layer earns its keep, not to plan servers.

| Dimension | Design point | Ceiling / note | Verified by |
|---|---|---|---|
| **Items per repo** | discodon ~**317 open** + a 1,754-line archive | GitHub Issues scales far past this; **our** limit is the read fan-out to sweep them (§3.3) | S2 |
| **Legacy prefixes absorbed per project** | **27–58** hand-minted PFX → alias labels | absorbed as `id:` labels; prawduct's own `BKL/ADR/ADV/MET/CRT…` is the multi-prefix stress case | S2 |
| **Dedup corpus** | **500+ items** (Q3) | lexical dedup is cache-served (read-your-writes); semantic is P2, hybrid-gated | build |
| **Concurrent actors** | 2 agents (parallel worktrees) + 1 human, up to a **48-agent** grooming sweep (TF3) | **correctness** (no lost updates) is CC2 optimistic-concurrency, *not* an NFR here; the **NFR ceiling is the shared read budget** — 48 cacheless readers exhaust one user bucket (§3.3), so high fan-out is **cache- or App-gated** | S3 |
| **Steady write rate** | ~**200 writes/day** | ≈ 8/hr avg — wide margin under 500/hr content | observed (PRD §9) |
| **Local cache disk** | O(portfolio size) — bodies + comments + FTS | bounded, rebuildable-from-GitHub, gitignored; not a dollar cost (§2) | build |

**The one scale cliff, stated plainly:** read-amplification (many agents × many items). Below it the
cacheless floor is correct and rate-safe; above it (the 48-agent sweep, mass grooming) the **cache is
required**, not optional-for-speed — the accelerated tier. This is the M7 honesty, carried into capacity
terms.

## 8. Operability (NF2) — near-zero, and what the sliver is

| Claim | Reality | Measured by | Status |
|---|---|---|---|
| **No server to run/patch/monitor** | GitHub hosts the store | assert no daemon/cron is required for **correctness** | **verified** |
| **No backup burden** | the store is GitHub; the local cache is **derived + rebuildable** | assert cache loss → rebuild-from-GitHub, no data loss (Data Model §7) | **verified** |
| **Backup/exit is free** | the G5/MG2 **export** doubles as backup, any time | run `export`; assert full-fidelity dump (incl. native graph) | design (G5) |
| **The operational sliver** | the cache path must **stay gitignored** (content-sensitive, Security §3/F5); a schema bump **rebuilds** it; the detached refresh is a subprocess, not a supervised daemon | `/prawduct:doctor` verifies the cache path is actually ignored; assert a `schema_version` mismatch triggers rebuild | design (Security §3, Data Model §7) |
| **Observability leaks nothing** | telemetry records **identities (login) + counts, never credentials** | assert no token in logs/telemetry/errors (structured errors, Security §4) | design (Security §4) |

Ops is genuinely near-zero, but **not** zero — the honest residue is (1) keeping the sensitive cache out
of git and (2) a rebuild on schema change. Both are `doctor`-verifiable, neither is a running service.

## 9. Measurement & verification plan (the testable throughline)

Consolidates *who proves what* — so no NFR is a bare assertion:

| Target | Owner | When |
|---|---|---|
| Content ~500/hr pacing constant; migration burst fits after scrub; ready-work fan-out cost | **S2** (migration dry-run — the slice's proving increment) | before widening the slice |
| Core reads/sec sustainable; grooming core-bound; cold-sweep batch/backoff constants; **semantic-search rate** | **S3** (rate limits under load) | when the read-heavy layer is built |
| CRUD p95 < 2 s; online read < 1.5 s; warm read < 500 ms; `pick` fan-out latency | **build-time latency probe** | at build, before "done" |
| Zero-model-tokens on CRUD; one-non-interactive-call; never-hang timeout T; crash-safe recovery; never-silently-stale | **Test Specs** (§16(5)) | the next drill-down consumes these as test cases |
| ETag/304 revalidation; content-vs-core budget facts; App bucket math | **verified** (2026 docs + `gh 2.86.0` probe) | done — carried from the PRD fact-check |
| Whether `attach` release-creation spends the content cap | **build** (`verify-api`) | when attachments are built (S5-adjacent) |

**Unverified, do-not-rely list (honest confidence):** the **semantic/hybrid search rate** (§3.1) and
**release-creation's budget class** (§3.2). Both are flagged, neither is load-bearing for the floor, and
both have an assigned owner above — the discipline is that an unverified number is *named as such*, never
silently trusted (the §5-versioning refusal, applied to NFRs).

## 10. Self-review (adversarial, 2026-07-16)

| # | Category | Finding | Disposition |
|---|---|---|---|
| N1 | honesty | AG5 "warm reads < 500 ms" reads as a slice guarantee; the cacheless slice has no cache | **Stated** — §4 marks it *accelerated*, gives the slice a separate < 1.5 s online-read floor; the floor/accel split (framing) exists for exactly this |
| N2 | correctness | Calling grooming "cheap" hides that its **reads** can exhaust the core budget | **Stated** — §3.3: grooming is cheap *on writes* (core-bound), but its read-fan-out is the cache-gated (M7) cost; 48-agent sweep is explicitly not a floor guarantee |
| N3 | over-claim | Are the latency p95 numbers real, or asserted? | **Refused to assert** — §4/§9: they are *targets* with a build-time probe as the gate; status is *target*, not *verified* |
| N4 | scope | Is a full NFR doc proportional for a personal $0 tool? | **Yes, bounded** — §framing delegates the classic NFRs to GitHub; only the 4 adapter-owned dimensions get budgets; C/O/S get a proof-of-delegation test, not a plan |
| N5 | gap | Concurrency "no lost updates" is a success criterion — is it an NFR here? | **Delimited** — §7: correctness is CC2 (Data Model §4), *not* re-litigated here; the NFR is only the shared-read-budget *capacity* ceiling |
| N6 | unverified | Leaning on an unverified semantic-search rate | **Quarantined** — §3.1/§9 name it unverified, assign S3, confirm it gates only the P2 path |
| N7 | testability | Do "made testable" claims have an actual method, or just a number? | **Method attached** — every target cites a measurement (probe/fault-injection/assertion) + an owner (§9); the pass/fail invariants (zero-tokens, never-hang, crash-safe) are called out as such |

*Independent review pending (Principle 14):* a fresh-eyes NFR/design critic + a GitHub-rate-fact
verifier should review this v1 before the Test Specs build on it — the same two-reviewer pattern the
Data Model / Security / API-contract drill-downs used. Confirmed findings fold into v2.

## 11. Traceability

**NF1**→§2 · **NF2**→§8 · **NF3**→§3 (two-budget model + per-op map + workloads + S3 plan) ·
**AG5**→§4 (latency budgets) · **AG4/G2**→§6 (never-block budget) · **G3/D5**→§5 (freshness bound) ·
**G4**→§2 ($0, App-free) · **§4 success criteria**→ p95<2 s §4, one-call §4, concurrency §7, migrate-with-IDs
§7/§3.3, $0 §2 · **TF3**→§7 (48-agent capacity) · **S2**→§3.3/§9 (migration burst, fan-out) ·
**S3**→§3.5/§9 (rate constants) · **O5/D8**→§3.4 (user-bucket floor, App-bucket accel).
**Coherence:** §3 per-op budget ↔ Data Model §1/M5 (write-cost split) + API contract §2 (op surface) ·
§3.1 `rate_limited`/§6 `unavailable` ↔ API contract §4 (error codes) · §5 ETag ↔ Data Model §6 (`etag`
column, M2) · §8 cache-sensitivity ↔ Security §3/F5 · §4 zero-tokens ↔ G1 (code in the data plane).
