# Backlog Service — API Contract

`status: draft v3 — build-plan coherence sweep (2026-07-16, from the §16(6) Build-plan drill-down review): §1 canonical CLI pinned to `prawduct-hook backlog` (one entry point, O5; `prawduct backlog` established as doc-shorthand); §2.5 MG4 scrub `search --like` demoted to a post-cache accelerator (not a slice dependency — model-surfaced dedup over `list` in the cacheless slice). Prior v3 — coherence touch-up (2026-07-16, §12b), folded from the §16(5) Test-Specs drill-down review: split idempotency pinned (`split-op:` token — was an undecidable "by link"); file-upstream idempotency pinned (`source-key:` marker — was "keyed" with no key); the v2 "semantic hybrid-search-enablement-gate" corrected (no such gate — semantic issue search is GA/on-by-default; `--semantic` `unsupported` is a capability probe); "never deletes issues" tightened to the load-bearing "never reuses numbers." Prior v2 — independent-review fold (2026-07-16): a fresh-eyes design critic + a gh/GitHub-fact verifier reviewed v1. Folded — C1: GV3 given a home (new §2.6) — closed_by is native-timeline-authoritative on close-on-merge, an optional handle on manual close, and the bidirectional drift sweep is a janitor workflow (coherence: closed_by added to Data Model §1.1 v3); C2: merge/split crash-safe recovery write-order specified (redirect-before-close, parallel to set-status); C3: retryable disentangled from the G2 never-block obligation (never-block = degrade on ALL errors, never retry-loop; retryable = orthogonal transient-vs-permanent hint for retry-drivers); C4: PV3/PV4 public-filing noted as native + delegated to Security §6; C5: "semantic pre-GA" corrected (semantic search is GA — the gate is per-repo hybrid-search enablement); C6: the "plugin semver IS the handle" claim scoped to the bundled CLI (MCP skew covered by its experimental tier); C7: verify/attach idempotency keys named; F2: list read-your-writes softened to strongly-consistent-in-practice; C10: gh exit 4 → auth mapping added; plus the offline-queue provisional-ID envelope state. The fact-verifier confirmed every load-bearing platform fact (80/min + ~500/hr caps, ETag/304, since-cursor, search-not-read-your-writes, MCP isError mapping, per-install lockstep, no-number-reuse). Prior v1: initial drill-down from PRD §16(4) — operation surface across three fronts + the two recorded decisions. · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4 — esp. AG1–6, G1–G5, O5/D8),
`documentation/backlog-service-data-model.md` (entities, `set-status`, ready-work fan-out, IDs),
`documentation/backlog-service-security-model.md` (auth, structured errors, BOLA/mass-assignment).
This doc designs the **programmatic surface** those two imply; it references their entities and rules
rather than restating them.

**Surface & altitude note.** The system exposes **three fronts over one core library** (PRD §6):
the `prawduct backlog` **CLI** (the primary agent contract), a thin **MCP** server, and the in-plugin
**core library** (`lib/backlog/…`). The `/prawduct:backlog` skill is a *consumer* of the CLI, not a
fourth contract (its UX is unchanged — GV1). This doc pins **which operations exist, what they act on,
their safety/idempotency, their I/O *shape*, the stable error vocabulary, and the two recorded
decisions** — **not** exact flag spelling or JSON field names (those are a build-time `verify-api`
probe, per the Data Model's altitude note). *The learning that bit here first:* the **common instance
(CLI) must not silently stand in for the whole contract** — every decision below is checked against all
three fronts.

**Two recorded decisions (framework-tracked).** `api_error_model_approach` (§4) and
`api_versioning_approach` (§5/§6) are *recorded decisions*, not silent defaults — the scriob precedent
(≈697/700 commits shipped on an unchallenged "versioning deferred" note → a coordinated
breaking-change retrofit) is exactly what §5 refuses to repeat. **Mirror both into
`project-state.design_decisions` when the build plan is authored** (deferred now, deliberately: the
feature is still in *design*, and `project-state.yaml` is flagged for compaction — recording them
there before the build plan would be premature; they are authoritative *here* until then).

---

## 1. Surface type & consumers

| Front | Surface type | Consumers | Stability |
|---|---|---|---|
| **Core library** `lib/backlog/…` | in-process Python (sync, return-value) | CLI + MCP only (internal seam, D7) | internal — *not* a stable external contract; the CLI is the contract |
| **CLI** `prawduct-hook backlog <op>` | commands + flags + exit codes + stdout/stderr | prawduct's own skill & gates; **adopter** agents (GV4); scripts | **stable public contract** |
| **MCP** server | tool calls over the same core | any MCP client (P2) | **experimental** |

**CLI invocation (O5).** The canonical command is **`prawduct-hook backlog <op>`** — a subcommand
group on the plugin's existing entry point, *not* a second binary (one entry point = one
platform-exposure/executable/PATH surface; the durable contract is the flags + JSON envelope +
on-GitHub encoding, not the binary name — §5). **`prawduct backlog` is used as readable shorthand
throughout the doc set** (PRD §6, Test Specs §1.1, this doc's prose).

**Consumers = both internal and external.** External raises the stakes: an adopter's agent parses the
CLI's JSON, so its output schema is a contract (§5). The canonical contract lives in **this doc + the
documented flag/output spec** (a CLI has no OpenAPI/SDL); the durable *cross-version* contract is the
on-GitHub encoding (Data Model §2/§3), not the CLI signature (§5).

## 2. Operations

Grouped by module. **Safe** = read-only (no mutation). **Idem** = re-running with the same arguments
converges to the same state (safe to retry). Priority tags (P0–P3) map to the PRD's importance ranking
(**not** release timing) so the build plan can cut the thin slice; they are orthogonal to the stability
tier (§7).

### 2.1 Item lifecycle
| Op | Acts on | Safe | Idem | Purpose | Parent |
|---|---|---|---|---|---|
| `file` (create) | new Item | – | **no** (unless keyed) | one-call create: `title`+`body` suffice, every other field defaultable; returns the ID **immediately**, dedup candidates **advisory-async** | AG2, AG3 |
| `get` / `show` | one Item | ✓ | – | fetch one item (live; or cache w/ visible age) | Q1, TF1 |
| `update` | one Item | – | field-wise | field-wise edit; **optimistic CAS** on state/`updated_at` → `conflict` for retry | CC2 |
| `status` (set) | one Item | – | **yes** | the crash-safe two-axis transition — maps to the Data Model's idempotent **`set-status`** primitive (re-run = no-op); a close also records **`closed_by`** (§2.6) | DM2, CC1, GV3 |
| `claim` / `unclaim` | Item assignee | – | **yes** | atomic take-and-verify; TTL-reap surfaces `claim_conflict` (non-fatal) | CC3 |
| `verify` | Item block+cache | – | **yes** (keyed on actor+date) | record "premise re-checked against code by <actor> on <date>" in one call — re-stamp same (actor,date) = no-op (the `verified` list is append-with-dedup, Data Model §1.1/§2) | TF2 |
| `comment` | Item comment | – | **no** | add a threaded, attributed comment | DM5 |
| `attach` | Item attachment | – | **cond.** | store a file (release-asset **or** attachments-branch, both no-PR); returns the stored URL. **Idempotent by content-hash on the attachments-branch path; name-keyed (so overwrite-or-skip) on the release-asset path** — the key depends on which S5 resolves | DM6 |

### 2.2 Query (read-only)
| Op | Safe | Purpose | Parent |
|---|---|---|---|
| `list` | ✓ | **structured** field/label filters + sort + paginate — runs **online off the REST list endpoint**, **strongly consistent in practice** (a just-written item appears immediately; a rare brief replication window exists — the documented 404-retry-after-create case — so it is not an absolute platform guarantee), no cache needed. `--untriaged` **inverts** the scope filter, returning only what `list` normally drops (the open members of the `counts` `untriaged` set); it **scans every page and REFUSES `--per-page`/`--page`** with a `validation` error, because untriaged issues are typically the newest and a first ascending page would answer "nothing to triage" while items waited on page 2 — and silently returning the whole set to a caller who asked for page 2 would be a confident wrong answer. Every other filter (`--assignee`, `--sort`, `--direction`, `--state`, the label facets) applies as usual | Q1-structured |
| `pick` | ✓ | stage-aware ready-work: `open ∧ stage:ready ∧ unassigned` (list filters), then "claim past TTL" per decoded item and a **dependency fan-out taken lazily in rank order, stopping at `limit`** (Data Model §4). Returns ranked candidate(s) + *why*; the *why* says **"no blockers recorded"** for an empty dependency read and "all N blockers closed" for a verified clear — these are different facts and the contract distinguishes them. An optional `--claim` does atomic take-and-verify (may return `claim_conflict` → caller re-picks) | GV1, DM3, CC3 |
| `search` | ✓ | **full-text** (`--text`) and **similar** (`--like`, lexical dedup) — served from the cache (GitHub search is **not** read-your-writes; §Sec/NF3); semantic (`--semantic`) is P2 — GitHub's improved/semantic issue search is **GA, on by default** (no per-repo gate; §4 `unsupported` only where the capability is genuinely absent) | Q1-fulltext, Q3 |
| `counts` | ✓ | per-project rollups derived **on read** (never persisted, except the GV2 briefing snapshot). Carries an **`untriaged`** count: issues on the backlog repo bearing neither a namespaced label nor a `prawduct:` block. They are counted in `total`/`by_status` (so the open figure reconciles against `gh issue list --state open`) and `untriaged` names them as a **subset, not an addend** — double-counting would err in the other direction. `untriaged` counts **open** issues only, while `total`/`by_status` span every state: a closed issue is already dispositioned, so it needs no triage, and this keeps the figure equal to what `list --untriaged` returns. Excluding them silently under-reported the backlog and hid exactly the items nobody had triaged | Q5 |
| `rollup` | ✓ | **cross-project** — query-side **fan-out + merge across owners** (NOT cache-served, NOT GitHub-native; Data Model §6) | Q4 |

### 2.3 Relationships
| Op | Idem | Purpose | Parent |
|---|---|---|---|
| `link` / `unlink` | **yes** | set/clear a typed edge: `blocks`/`blocked-by` (native deps), parent/child (sub-issues), `related` | DM3 |
| `merge` | **yes** | fold A→B: preserve both bodies, leave a **`superseded-by:` redirect** (nothing hard-deleted) | AU3, DM7 |
| `split` | **keyed** | create linked children from one item (idempotent on the `split-op:` token — §2.3) | AU3 |

**Merge/split are compound multi-issue ops — CC1 crash-safety, parallel to `set-status` (C2).** `merge`
touches two issues with no GitHub transaction, so it commits a **canonical write-order: write the
`superseded-by:` redirect on the source *before* closing it** — a crash then leaves the source
open-but-redirected (a valid, resolvable state), and a re-run completes idempotently; it **never
closes-then-orphans**. `split` has no single safe order, so it is **recover-by-cleanup, made keyed**: the
call derives a stable **`split-op:` token** = a digest of *(parent canonical id, the ordered child
specs)*, and stamps each created child `split-op:<token>#<index>`. A re-run with the same arguments
recomputes the token and, per index, **skips a child already stamped** — creating only the missing ones,
never a duplicate. (Recomputing the token from the call args is what makes it a concrete matching key,
not a bare "by link" — the gap the Test-Specs review surfaced; changing the child specs mints a new
token, i.e. a *new* split, correctly not a resume.) This is the M5 discipline the Data Model fixed for
status — §4 `set-status` — and the `id:PFX` skip-if-exists the importer uses — applied to the
relationship ops (marker field-home: Data Model §5).

### 2.4 Cross-project & automation
| Op | Idem | Purpose | Parent |
|---|---|---|---|
| `file-upstream` | **keyed** | file into **another project's** backlog — no upstream checkout; stamps provenance; lands **`submitted`**; auth resolves by **target owner** (Security §1). **Keyed on a `source-key:` marker** = a digest of *(submitter identity, source item ref / title+body digest)*; a re-file with the same key **returns the existing upstream item, never a duplicate** (the A3/N2 retry-safety made concrete — distinct from the AG3 *advisory* dedup; marker field-home: Data Model §5) | XP1, XP2 |
| `batch` | **per-item** | apply N idempotent mutations in few paced calls; **not transactional** — returns a **per-item result array** (partial success is real: some `ok`, some `rate_limited`); safe to re-run | AU2, TF3 |
| `sync` | **yes** | warm the optional cache via the **changed-since cursor** (Q2); no-op when the cache is off | Q2, AG4 |
| `refresh-counts` | **yes** | write the `briefing_counts` snapshot (degenerate cache, visible age) so session start never waits | GV2 |

*Briefing/gate consumption (the GV2 consumer contract, BKL-8P2R):* the product's cutover to the
service is recorded as a flat `backlog_service_repo: owner/repo` scalar in
`.prawduct/project-state.yaml`, written by the migration session at cutover. **Set:** the session
briefing reads `snapshot.read` (file-only — the never-block "few s" bound is structural: no network
call exists on the briefing path, and any timeout tuning belongs to the *detached*
`snapshot.spawn_refresh` child it fires after reading) and surfaces the snapshot's **visible age**;
the seven markdown-premise advisory probes retire on the same switch — the backlog quartet
(`legacy-backlog-format`, `backlog-service-migration-required`, `legacy-section-schema`,
`backlog-overdue-grooming`) and the norm trio that judges item liveness from the same file
(`revisit-due`, `dead-why`, `stalled-transition`);
a frozen file must not generate nudges, and `external-backlog-detected` keeps its independent
premise. Retirement is not silence — `backlog-checks-dormant` starts firing at the same switch,
naming every backlog check left without an Issues-backend path (full retirement table:
post-sync-advisory-spec §8.2; shared predicate `backlog_probes.post_cutover`). **Unset:** the briefing parses
`.prawduct/backlog.md` exactly as pre-service (coexistence — MG3).

### 2.5 Migration, exit & provisioning
| Op | Idem | Purpose | Parent |
|---|---|---|---|
| `import` (migrate) | **yes, resumable** | `backlog.md`(+archive) → issues; keyed on the `id:PFX` alias (**skip-if-exists**), durable checkpoint; **no "rollback"** — GitHub **never reuses issue numbers** (a deleted number is *retired*, not recycled; deletion itself is an admin-only destructive action, not an ordinary op), so recovery = re-run into the same repo. `--restructure <plan.json>` applies the owner-confirmed **MG6 restructure plan** (issue-standard §5) to the parsed records **before** the data plane — fail-closed validation (typo'd PFX / unknown key refuses the whole run before anything is written), originals stashed verbatim (`original_title`/`original_body` block fields, Data Model §2), applied **at create only** (an existing issue is skipped, never rewritten). A **rate-limited status reconcile** pauses and retries the whole idempotent record like any other 429; any *other* reconcile failure still defers so a long run continues, and lands in **`status_unreconciled`** (carried in `data` and in both resumable-cut `details`, counted on the human summary line) — those items exist on the target at the wrong status, which is what `verify-migration` reports as `status_mismatch` | MG1, MG6 |
| `verify-migration` | **yes** (read-only) | the completeness gate between an import and a cutover: re-parses the source exactly as `import` does (`collect_records` → `apply_archive_scope`, so source and create sets cannot drift) and compares it against the target's `id:` aliases **and each covered item's decoded status**. **Exit 4** on any of `missing` (parsed but never created), `unaliasable` (no usable PFX in the source — derived from the source parse alone, so no issue-side action can clear it), `collisions`, `status_mismatch` (present and correctly keyed but at the **wrong status** — a deferred status reconcile, so coverage alone reads as complete; same remedy as `missing`, since a re-run reconciles the status axis on already-migrated items), or `duplicate_alias` (**two target issues** record one id at disagreeing statuses — looks like `status_mismatch`, recovers like `collisions`: a re-import writes to neither, so the remedy is a target-side `merge`, and the branch says *do not re-run*). Coverage is necessary but not sufficient: `source_items == aliased` and exit 4 is the expected reading for the last two, not a contradiction. Human mode **names** the stranded items rather than counting them; the remedy for `unaliasable` is unactionable without them. Fails closed on transport error, alias-scan truncation and scope mismatch | MG1 |
| `restructure-preview` | **yes** (offline) | the MG6 owner-review artifact: parse the source(s) exactly as `import` would, apply the plan, write the deterministic before/after markdown the owner approves **in aggregate** — generated from the same code path the import consumes, so what is reviewed is what gets written; needs no transport and touches nothing on GitHub | MG6 |
| `export` | **yes** | full-fidelity dump to plain files: body block **plus** the native graph (deps, sub-issues, timeline, assignees) — cheap *dump*, not lossless one-liner re-import | MG2, G5 |
| `provision` / `reconcile-labels` | **yes** | create/reconcile prawduct's namespaced label taxonomy without colliding with the repo's existing labels/Issues; the primitive `/prawduct:onboard`/`doctor` call | GV5, GV6 |

*The MG4 **scrub** is a model-assisted, owner-confirmed **workflow** over these ops (`list` +
**model-surfaced dedup** to surface stale/dup candidates → owner confirms → `status`/`merge`/`import`
on the cleaned set), not a single deterministic op — the model is in the *decision*, never the data
plane (G1/AG1). The **MG6 restructure pre-pass** rides the same pattern: the model *proposes* a plan
(titles/template bodies/`kind:` per issue-standard §5), `restructure-preview` renders the aggregate
before/after artifact, the owner approves the batch, and `import --restructure` applies it
deterministically. `search --like` is a **post-cache accelerator** (W1/W2 in the build plan), **not a
slice dependency**: lexical similarity is cache-served (§2.2), so in the cacheless slice the model
surfaces dup candidates by reading `list` output directly.*

### 2.6 Governance reconciliation (GV3)

A close via `status`→shipped/dropped records **`closed_by`** — **native** where the close rides a merge
(GitHub's `closed` timeline event carries the closing PR/commit ref, queryable like `history`/CC4),
plus an **optional `--closed-by <handle>`** stamped in the `prawduct:` block for a **manual** close
(which carries no native handle — the case a bare `status`→shipped would otherwise lose). The
**bidirectional drift sweep** GV3 requires — *shipped-but-PR-died* and *merged-but-item-open* — is a
periodic `list`+timeline scan run as a **janitor workflow** (deterministic, no model), not a single op:
the explicit price of trading git's ship-atomicity for traceability (GV3, PRD §8.7). *(Coherence: the
`closed_by` field is defined in Data Model §1.1 (v3) — this review surfaced that GV3's handle had no
field home.)*

## 3. Inputs & outputs

**Item shape = the Data Model entity** (§1.1), not restated here. Contract-level rules:

- **Inputs.** Only `title`+`body` are required to `file` (AG2); every other field is optional and
  backfillable. IDs accept `owner/repo#number` · `repo#number` · `repo-number` · `repo/number` and
  **normalize** to canonical (D4). Soft-enum values (`stage:`,`kind:`,…) are **advisory** — an unknown
  value is *flagged, not rejected* (DM1); the hard reject is reserved for genuine ambiguity (unknown
  *status*, malformed ID). A digit-suffix token (`ADR-12`) matches both `repo-number` and the
  migrated-PFX alias grammar; precedence is fixed (Data Model §5): with `--repo` present the
  uniqueness-checked alias wins when it exists, the `repo-number` reading stands when it doesn't,
  and the `#` spellings never enter the alias path (the unambiguous escape hatch).
- **Outputs.** Two modes (AG6): **JSON** (machine) and **human**. **JSON goes to stdout as the sole
  content**; all diagnostics, progress, and deprecation warnings go to **stderr** — so a piped `| jq`
  never chokes. Human mode prints the payload to stdout, narration to stderr.
- **Envelope.** Every JSON response is one envelope: `{"status":"ok","data":…,"warnings":[…]}` or the
  error form (§4). `warnings[]` carries the *advisory-but-not-fatal* signals — unknown soft-enum
  values, a human-UI drift the reconciler self-healed (CC5), a stale cache read's visible age — that
  must never be an error (DM1). A **resumable** error (a mid-run `import` cut) also carries top-level
  `warnings[]`, so a self-heal audit line from an already-completed record is not lost — it can't be
  re-emitted on resume (the restored alias label makes the record skip the fast path).
- **Issue standard on `file`** (issue-standard §1/§2/§4; `lib/backlog/issuefmt.py`). `file` emits the
  §1 title shape (prepends the `area:` prefix, idempotently) and **audits** the created issue against
  the §4 thresholds. Findings ride in a **separate** top-level `lint` field —
  `"lint":[{"rule","message","severity":"warn"}]` — a distinct category from operational `warnings[]`,
  and the same structured shape the migration reuses as an audit-only pass. **WARN-only: `lint`
  findings never affect `status` or the exit code** (the create was never a blocking gate). The body
  is model/human-authored (the composer `render_body` assembles §2 sections for callers that want it,
  and the migration pre-pass); the linter guards whatever is authored.
- **Collections** (`list`,`search`,`batch`) paginate by **cursor** (the Q2 changed-since primitive,
  not offset), with a max page size; `batch` returns a **per-item** result array, never all-or-nothing.
- **Async/advisory.** `file` returns the new ID **before** dedup runs; candidates arrive on a second,
  advisory channel (a follow-up field/call), never blocking the create (AG3).
- **Queued (optional offline layer).** When the offline write-queue (P2) is present, a create made
  while GitHub is unreachable returns a **third envelope state** — `{"status":"queued","data":{"provisional_id":…}}`
  — reconciled to the real `repo#number` on flush (the one real cost of GitHub-assigns-the-ID, PRD §8.1).
  Absent that layer, an offline create is the `unavailable` error (the G2 fail-fast floor), never a hang.

## 4. Error model   <!-- recorded → api_error_model_approach -->

**One philosophy across three boundaries: return-value internally, structured envelope + exit code at
the CLI, mapped into MCP's error shape.** This is the project's established convention (internal `lib/`
functions return `status`/`reason` dicts; exceptions escape only at boundaries and are caught there),
extended to the two outer fronts.

- **Core library** — returns `{"status": "ok"|"error", …}`; on error a **stable `code`** + human
  `message` + structured `details`. **No raising inside governance internals**; unexpected
  `OSError`/`JSONDecodeError` are caught at the boundary, logged with context, never swallowed.
- **CLI** — the JSON error envelope on stdout:
  `{"status":"error","error":{"code":<vocab>,"message":…,"retryable":<bool>,"details":{…}}}`, plus a
  **stable exit-code scheme** (0 = ok; a small fixed set of non-zero *classes* — validation / not-found
  / conflict / auth / unavailable — **aligned with the existing `prawduct-hook` exit conventions**, a
  build-time coherence check). Human mode prints the message to **stderr** and sets the same exit code.
- **MCP** — maps the same core result to MCP's `isError` + content, reusing the identical `code`
  vocabulary.

**Two distinct obligations, never conflated (C3).** (a) **Never-block (G2)** is a *caller* obligation
to **degrade gracefully on _any_ error** — a gate/hook reading backlog state tolerates `validation` and
`not_found` as calmly as `unavailable`, never hangs, and **never retry-loops** (a retry-until-success
loop is the *opposite* of never-hang). (b) **`retryable`** is a separate, orthogonal
**transient-vs-permanent hint** telling a *retry-driver* (`batch`, `sync`, an unattended worker)
whether re-attempting *this class* can succeed: `unavailable`/`rate_limited` → **yes** (backoff hint in
`details`); `conflict`/`claim_conflict` → retry only **after a re-read**;
`validation`/`not_found`/`ambiguous_id`/`alias_collision`/`auth`/`unsupported` → **no**. Never-block
governs the caller's *degradation*; `retryable` governs a driver's *re-attempt* — they are not the same
axis.

**Stable `code` vocabulary (the contract — not free-text):**

| `code` | Meaning | retryable | Parent |
|---|---|---|---|
| `validation` | malformed input (an *unknown soft-enum* is **not** this — it is a `warning`, DM1) | no | DM1 |
| `not_found` | no such item / alias | no | – |
| `ambiguous_id` | short `repo#number` resolves to >1 under federation | no | D4, DM §5 |
| `alias_collision` | a second item claims an existing `id:` alias — rejected so refs can't be hijacked | no | DM §5, Sec §5/F3 |
| `conflict` | optimistic CAS failed (state/`updated_at` moved) → re-read & retry | caller-retry | CC2 |
| `claim_conflict` | assignee take lost the race — non-fatal, caller re-picks | caller-retry | CC3 |
| `auth` | identity/scope problem (missing scope, `proxy-injected` w/o `gh`); the adapter maps `gh`'s own **exit 4 = auth-required** onto this (C10) | no | Sec §1 |
| `unavailable` | backend unreachable — the G2 floor, degrade to cache-or-"unavailable" | **yes** | G2, AG4 |
| `rate_limited` | hit 80/min or the ~500/hr content cap | **yes** (backoff) | NF3 |
| `unsupported` | op needs an absent layer (fulltext w/o cache; `search --semantic` where the capability is **genuinely absent** — e.g. a GHES instance without semantic issue search). On GitHub.com semantic search is **GA and on by default**, so this is a **capability probe, not a per-repo enable-gate** (that gate does not exist); exceeding the ~10/min budget is `rate_limited`, not this | no | §6 |

**Security binding (Security §4).** Errors are built from **known fields, never by echoing raw
`gh`/subprocess/HTTP output** — that is how a token leaks into an error string; the denylist scrub is
only the backstop. Tokens, auth state, and the cache path are **never** in any output (§9).

**Decision status: active.** The model is uniform across all three fronts from the first slice — not
deferred.

## 5. Versioning   <!-- recorded → api_versioning_approach -->

There are **two version surfaces with different lock-in**, and conflating them is how the scriob tax
happens. Naming them separately *is* the recorded decision:

**5.1 Data-format version — the real cross-version contract (active, `v: 1`).**
Everything interoperates through **GitHub Issues + the `prawduct:` block + the label taxonomy**. Two
different plugin versions meet *only* there: a consumer product on plugin vX filing upstream (XP1) into
a project whose adapter is vY; a human editing in the GitHub UI between two adapter versions. This is
the genuine multi-consumer wire, and it is **already versioned and governed additive-only-forever**
(Data Model §7): a key's meaning is never redefined in place; a real semantics change **mints a new key
and deprecates the old**, never a `v:1→v:2` reinterpretation. **This is where a version handle earns
its keep** — status **active**.

**5.2 CLI/MCP command + JSON-output surface — lockstep-with-plugin, tolerant-reader additive
(active decision, not a deferral).**
The CLI is **delivered by the plugin the consumer installs**, so there is no independent skew between
"the CLI I call" and "the CLI I have" — **the plugin semver *is* the version handle.** Decision:
**no per-command `/v1`-style handle**; instead the JSON output is a **tolerant-reader additive
contract** — new keys added, existing keys never removed or repurposed, unknown enum values tolerated
(the same rule as the block). Granularity: **whole-surface** (the plugin version), with per-command
**stability tiers** (§7). A breaking output change rides a **plugin major bump + a deprecation window**
(§6). *No envelope `schema` field by default* (the plugin version is the handle); add one only if a
**non-plugin** consumer ever appears — noted, not built (§11).

*Scope of the lockstep claim (C6):* this no-independent-skew reasoning is the **bundled CLI**'s — it is
**per-installation, not fleet-wide** (§5.1 already routes cross-plugin-version interop through the
data-format wire). The **MCP** front can serve an **external client not shipped with the plugin**, so
skew *is* possible there; its compatibility is bounded not by lockstep delivery but by its
**experimental** tier (§7, "may break within a minor"). "The plugin semver is the handle" is precise
for the CLI, not a blanket over the whole surface.

**This is a real decision, recorded — explicitly not "deferred."** The failure mode being avoided is
precisely a one-word "versioning later" note that ships an unversioned surface for a year and then pays
a coordinated retrofit.

## 6. Deprecation & compatibility   <!-- part of api_versioning_approach -->

- **Evolution rules (what keeps new versions rare):** additive-only; tolerant reader; never remove or
  repurpose a flag / output key / exit-code meaning; tolerate unknown enum values (DM1). Identical to
  the Data Model's block rule — one discipline, two surfaces.
- **Deprecation signalling:** a deprecated flag/field emits a **stderr** warning (never stdout — keeps
  JSON clean) and is recorded in the plugin change-log; the MCP/library surface uses the language's
  deprecation marker. **Support window:** a deprecated surface survives **≥ one plugin minor cycle**;
  **removal only on a major.**
- **Compatibility commitment per tier (§7):** *stable* cannot break without a major bump + the window;
  *experimental* may break within a minor; *deprecated* is scheduled for removal.

## 7. Surface inventory & stability tiers

Preventing "improper inventory management" (the CLI analogue of a zombie endpoint) — every surface is
tiered, none is undocumented-but-live.

- **Stable (public contract):** the §2.1 item lifecycle, §2.2 `list`/`pick`/`counts`, the **JSON
  envelope + `code` vocabulary** (§4), the ID-normalization inputs (§3). Adopter agents depend on these.
- **Experimental (may break within a minor):** the **MCP** front; `search --semantic` (capability-probed
  — absent only where the instance lacks semantic search); **attachments** (`attach` mechanism gated on
  S5); `rollup` cross-owner fan-out.
- **Internal (not a contract):** the **core library** functions (return-value seam — the CLI is the
  external contract), the cache tables (Data Model §6), the detached `sync` subprocess.
- **Deprecated:** none yet. The `incoming-bugs/` drop-box is retired *by* `file-upstream` (XP1), not a
  deprecated op on this surface.

## 8. Conventions

Small choices expensive to reverse once consumers depend on them:

- **IDs (D4):** canonical `owner/repo#number`; short `repo#number` **same-owner only** (else
  `ambiguous_id`). Accept the four spellings (§3), normalize on the way in.
- **Timestamps:** **ISO-8601, UTC** — matches the Data Model's `claimed_at` / `verified.on`.
- **Enums:** named string values, never magic ints; **soft** (unknown → `warning`, not reject; DM1).
- **null vs. absent:** absence = "unset / use default"; explicit `null` = "clear this field." A
  fail-closed reader here would re-create the tolerated-variant bug — `[]`/absent both mean "none."
- **Output discipline:** JSON is the **sole stdout content**; diagnostics/warnings/progress →
  **stderr**. Non-interactive **always** (AG1): the CLI never prompts, and drives `gh` with
  `GH_PROMPT_DISABLED=1`, no pager, no inherited TTY (Security §1a) — nothing to hang on.
- **Subprocess (how the adapter calls `gh`, project preference):** args as a **list**, never
  `shell=True`; the token is `gh`'s to hold (`~/.config/gh`), never re-emitted (Security §4).

## 9. API-design security (on top of the Security Model)

Authn/authz live in the Security Model; this names the **API-boundary** failure modes:

- **BOLA / object-level authz.** The adapter acts with the **caller's own inherited token** (O5) — so
  GitHub enforces per-object access; **no shared/service token** is ever introduced (PV2). Two carve-outs
  the caller must not overread: **Actions** runs as the bot (Security §1b), and the **cache** can serve
  across the fetch-time boundary (Security §3/F4).
- **Mass assignment.** `file`/`update` bind **only documented item fields**; a request can never set
  `history`, `node_id`, or another actor's **native** attribution. *But `prawduct:`-block fields are body
  text — self-set and forgeable by any write-capable actor* (Security §5/F3): the API treats them as
  **untrusted self-assertion**, trustworthy only insofar as the acting API identity is.
  `update` writes `title`, `body`, the soft-enum facets, and the four **editorial** block fields
  `--refs`/`--revisit`/`--closed-by` (valued; empty clears) and `--reviewed` (presence-only, stamps
  today); `file` additionally accepts `--refs`. Every other block field is import-only or owned by
  the op holding its invariant (Data Model §1.2) and is **rejected by name**, never silently ignored,
  so a typo and a mass-assignment attempt are equally visible.
  **The allowlist binds keys; a second guard binds values.** Block values are body text in a
  line-based format, so a value carrying any `str.splitlines()` separator injects sibling fields —
  reaching the very keys the allowlist just rejected. Such values are rejected at the op boundary,
  by a predicate derived from the parser rather than an enumerated separator set.
- **Excessive data exposure.** JSON returns **item fields only** — never tokens, auth state, or the
  cache path (§4).
- **Resource / rate bounds.** Caller-drivable cost is bounded: `batch`/`import` **pace under the 80/min
  + ~500/hr caps** (NF3); attachment size routes ≥10 MB through the release-asset wrap (DM6).
- **Input validation at the boundary.** ID normalization rejects malformed IDs (`validation`); the
  alias-uniqueness guard rejects a forged `id:` collision (`alias_collision`, Security §5/F3).
- **Public-submission surface (PV3/PV4) — no dedicated op (C4).** Anonymous filing rides **native
  GitHub issue creation** (a GitHub account is the only barrier); a non-collaborator can't apply labels,
  so the filing lands **unlabeled = quarantined** and is surfaced by a `submitted`-intake `list` query,
  not by a bespoke endpoint. Abuse handling (PV4) is **native GitHub controls + the quarantine**, gated
  structurally on the governed-intake path. The mechanism and trust boundary are the **Security Model's
  (§6/F6/F7)** — this surface only exposes the `list` triage query over it.

## 10. Conditional patterns

- **Async / long-running.** `file`'s dedup is **advisory-async** (returns the ID first, AG3);
  `import`/`export` are long-running → **resumable checkpoint** streaming progress to stderr, never a
  held-open blocking call.
- **Concurrency / consistency.** `update` is **optimistic compare-and-set** on state/`updated_at` →
  `conflict` for clean retry (CC2); the optional cache revalidates a decision-driving read via
  **conditional request (ETag)** (G3, Data Model §6/M2); `claim` is **take-and-verify** with a
  documented residual race (CC3), not a mutex.
- **Events / callbacks.** Baseline is **cheap polling** via the `sync` changed-since cursor (Q2);
  webhooks are an *optional* enhancement (AU1), not required for the slice.
- **Consumer correlation (CC4).** Every mutating response carries the resolved **API identity** as the
  actor (never the git-push identity — Security §1); the unattended path additionally stamps
  `automated: true` (a self-assertion, audit-only — Security §1a).

## 11. Open questions (build / `verify-api`, not altitude blockers)

1. Exact flag spelling + JSON field names — **`verify-api` probe** before writing handlers (Data Model
   §8 open-Q1, same discipline).
2. Exact non-zero **exit-code integers** — align with the existing `prawduct-hook` scheme at build.
3. **MCP** protocol error mapping specifics (how `retryable`/`code` ride MCP content) — settle when the
   P2 MCP front is built.
4. Whether `pick --claim` (atomic pick+take convenience) is worth the extra surface vs. `pick` then
   `claim` — a small design call, decide at build with the CC3 race data.
5. Envelope **`schema` marker** — add only if a **non-plugin** consumer appears (§5.2); until then the
   plugin version is the handle.

## 12. Self-review (adversarial, 2026-07-16)

| # | Category | Finding | Disposition |
|---|---|---|---|
| A1 | over-scope | 20+ ops looks heavy for a "thin slice" | **Intended** — the contract specs the *whole* system (PRD altitude: spec the whole, build a slice); P0/P-tags in §2 let the build plan cut the slice. Not a re-scope. |
| A2 | correctness | `batch` implying transactional all-or-nothing would be a lie (GitHub has no multi-issue transaction) | **Stated** — §2.4/§3: `batch` is **per-item**, partial success is real, idempotent-so-safe-to-re-run |
| A3 | correctness | `file` idempotency — a retried unattended create duplicates (Security §1a/N2) | **Surfaced** — §2.1 marks `file` non-idempotent *unless keyed*; §2.4 `file-upstream` keyed; the idempotency key is the N2 requirement made API-visible |
| A4 | seam | `set-status` is a Data-Model internal primitive — is it a CLI op? | **Resolved** — the CLI op is **`status`**, which *maps to* the idempotent `set-status`; generic `update` handles other fields (§2.1). The crash-safe primitive stays internal; the contract exposes the intent |
| A5 | coherence | pick as read vs. claim as write — does `pick` mutate? | **Resolved** — `pick` is **safe** (ranked read); `claim` mutates; optional `pick --claim` is the only atomic combo, and it can return `claim_conflict` (§2.2) |
| A6 | versioning | the scriob trap — an unversioned surface on a "deferred" note | **Refused** — §5 records a *real* decision (data-format `v:` active + CLI lockstep/tolerant-reader), not a deferral; §12-none-of-this-is "later" |
| A7 | colonization | letting "CLI" stand in for the whole contract (the named-but-narrowed learning) | **Guarded** — §1 enumerates three fronts; §4 error model spans all three; MCP tiered experimental, not forgotten |
| A8 | never-block | is G2 actually expressible at the API boundary, or just asserted? | **Expressible, then refined (C3, §12a)** — never-block = the caller degrading on the `unavailable` code (and every other error); `retryable` is the *orthogonal* retry-driver hint, **not** the never-block primitive (v1 conflated the two) |

*Independent review folded (2026-07-16, Principle 14):* a fresh-eyes design critic + a gh/GitHub-fact
verifier reviewed v1; confirmed findings are folded below and inline.

### 12a. Independent review (design critic + gh/GitHub-fact verifier, 2026-07-16) — folded into v2
| # | Sev | Finding | Disposition in v2 |
|---|---|---|---|
| C1 | major | GV3 `closed_by` + bidirectional drift sweep had no op, no field, no descope (gap spanned this doc + Data Model) | **Folded** — new §2.6 (native close-ref + optional manual handle + janitor sweep); `closed_by` added to Data Model §1.1 (v3) |
| C2 | major | `merge`/`split` tagged idempotent but no crash-safe recovery order — the CC1 defect M5 fixed only for status | **Folded** — §2.3 canonical write-order (redirect-before-close; split recover-by-cleanup) |
| C3 | major | `retryable` framed as *the* never-block primitive — conflates a retry hint with degrade-on-any-error, invites a retry-loop | **Folded** — §4 splits the two obligations; A8 refined |
| C4 | minor | PV3/PV4 public-filing had no note/trace on the surface doc | **Folded** — §9 note (native + quarantine), delegated to Security §6; §13 trace |
| C5 | minor | `unsupported` "semantic pre-GA" contradicts PRD "semantic GA 4/2026" | **Folded (v2), re-corrected (v3, §12b)** — v2 reworded to "hybrid-search *enablement*-gated," but the Test-Specs fact-verifier found **that gate does not exist** (semantic issue search is GA, on by default); v3 reframes `unsupported` as a **capability probe** (§2.2/§4) |
| C6 | minor | "plugin semver IS the handle" over-reaches to the external-client MCP front | **Folded** — §5.2 scoped to the bundled CLI; MCP skew covered by the experimental tier |
| C7 | minor | `verify`/`attach` idempotency depends on unspecified keying | **Folded** — §2.1 names the keys (verify: actor+date; attach: content-hash / name-keyed, S5-dependent) |
| F2 | minor | `list` "read-your-writes" stated as absolute; it's strongly-consistent in practice | **Folded** — §2.2 caveat (rare replication window; search-lag is the real contrast) |
| C10 | minor | `gh` has a documented exit-code scheme (0/1/2/4=auth) | **Folded (enhancement)** — §4 maps `gh` exit 4 → `auth` |
| F1 | minor | PRD §9 "10 semantic searches/min" looks conflated with code-search 10/min | **Folded (v2), since resolved** — v2 softened PRD §9 to "unverified, confirm at build"; the NFR fact-check then **verified** it (10/min, GA 2026-04-02, independent of code-search, NFR §9), and PRD §9 is updated to match (v3 coherence touch-up) |
| — | — | offline-queue provisional-ID had no envelope state | **Folded** — §3 `queued` third envelope state |

*Fact-verifier result:* every load-bearing platform fact **confirmed** against current (2026) docs + a
local `gh 2.86.0` probe (the 80/min + ~500/hr caps, ETag/304-costs-nothing, the `since` cursor,
search-not-read-your-writes, the MCP `isError` mapping, per-installation plugin/CLI lockstep, no
issue-number reuse, no multi-issue transaction). No fact error was load-bearing.

### 12b. Coherence touch-up (2026-07-16, v3) — folded from the Test-Specs drill-down review

The §16(5) Test-Specs drill-down's fact-verifier + design-critic surfaced four coherence debts this
surface owns. Folded here:

| # | Finding | Fix in v3 |
|---|---|---|
| K1 | `split` tagged "idem: no / recover-by-cleanup **by link**" — "by link" is not a concrete matching key, so a resumed split's "no duplicate" was undecidable | §2.3 pins a **`split-op:<token>#<index>`** key (token = digest of parent + ordered child specs); split is now **keyed-idempotent** (§2.1 row updated) |
| K2 | `file-upstream` marked "keyed" with **no key specified** | §2.4 pins a **`source-key:`** marker (submitter identity + source digest) → a re-file returns the existing item; the A3/N2 retry-safety made concrete |
| K3 | the v2 C5 rewording "semantic … **hybrid-search enablement**-gated" is **itself inaccurate** — no such per-repo gate exists (semantic issue search is GA, on by default) | §2.2/§4/§7 reframe `--semantic`'s `unsupported` as a **capability probe** (absent only where the instance lacks the feature); rate → `rate_limited` |
| K4 | "GitHub never **deletes**/reuses numbers" is false on the delete half (admins can permanently delete) | §2.5 `import` leans only on the load-bearing **never-reuses-numbers** (a deleted number is retired; deletion is an admin-only destructive action) |

*(Coherence: K1/K2 marker field-homes added to Data Model §5; K3 also touched NFR §3.5 and PRD §9; K4
was first flagged in NFR §10a. The Test-Specs CRASH-3/XP-1 tests are un-deferred against K1/K2.)*

## 13. Traceability

Every §2 op cites its parent requirement; the reverse holds for the agent-ergonomics / query / flow
requirements this surface owns: **AG1**→§8 (non-interactive) · **AG2**→`file` · **AG3**→`file`
advisory-async · **AG4**→`unavailable`/`sync` · **AG5**→(NFR doc, not here) · **AG6**→§3 JSON+human ·
**CC1/DM2**→`status`(set-status) · **CC2**→`update` CAS/`conflict` · **CC3**→`claim`/`claim_conflict` ·
**CC4**→§10 actor identity · **CC5**→§3 `warnings[]` self-heal · **TF2**→`verify` · **TF3**→`batch` ·
**DM1**→§3/§8 soft-enums · **DM3**→`link`/`pick` · **DM4/D4**→§8 IDs/`ambiguous_id` · **DM5**→`comment` ·
**DM6**→`attach` · **DM7**→`merge` · **Q1-structured**→`list` · **Q1-fulltext/Q3**→`search` ·
**Q2**→`sync` · **Q4**→`rollup` · **Q5**→`counts` · **XP1/XP2**→`file-upstream` · **AU2**→`batch` ·
**AU3**→`merge`/`split` · **GV1**→`pick` · **GV2**→`refresh-counts` · **GV3**→§2.6 (`closed_by` + the
janitor drift sweep) · **GV5/GV6**→`provision` · **MG1**→`import` · **MG2/G5**→`export`. **G1/AG1**→§2.5
note (model in the *decision*, not the data plane). **O5/D8**→§9 caller-token BOLA. **PV3/PV4**→§9
(native filing + quarantine, **delegated to Security §6** — no dedicated op). **Coherence:** §4 codes ↔
Data Model §5 (alias) + Security §4 (scrub); §5 versioning ↔ Data Model §7 (block `v:` additive-forever);
§9 ↔ Security §2 (BOLA/mass-assign); §2.6 `closed_by` ↔ Data Model §1.1 (GV3 field home).
