# Backlog Service — Requirements

`status: draft v3.1 — owner review incorporated 2026-07-14; PRD independent-review pass fed back 2026-07-16 — four requirements discovered during PRD design written back here per Principle 6: CC5 (human-UI-edit drift reconciliation), PV4 (public-submission abuse handling), GV6 (label-taxonomy provisioning + existing-Issues coexistence), MG4 (one-time pre-migration scrub) · added: 2026-07-13 · source: discovery session · stage: requirements`

Predecessor spec for the current git-file system: `documentation/backlog-system-requirements.md` —
item *semantics* (metadata, stage routing, archive discipline) carry forward; its storage and
transport decisions are superseded here. Evidence below is from a 2026-07-13 sweep of all 16
local checkouts of the 8 backlog-bearing projects (prawduct, scriob, discodon, hallucinote,
cordyceps, trenchant, puzzles, metallm).

## Problem

The backlog is a markdown file in git, mutated by an LLM in a forked skill context. Portfolio
scale today: **8 active projects, ~604 open / ~1,055 total items, 16 checkouts.** Five observable
failure modes, ranked by evidence strength:

1. **Stale state / trust collapse** — the deepest pain. `stage: ready` items turn out 60–100%
   already shipped (hallucinote ×2 in one session, scriob ×4 in one scrub, a 3-item upstream
   report); one discodon item described a destructive *live* code path as permanently dead.
   Consumers now re-verify every item's premise in code before acting — discodon ran a 48-agent
   adversarial workflow just to re-establish trust in 39 items. Item text is treated as untrusted.
2. **Stale views across checkouts** — a live discodon worktree showed 66 closed items as Open and
   couldn't see 65 newer ones; a sibling clone holds one item that exists nowhere else. Copies
   diverge by staleness far more than by conflict (~98% of measured divergence). No single truth.
3. **Merge-conflict tax** — "every single merge conflicted on backlog.md" (prawduct learnings);
   discodon: 454 commits touched backlog.md, 47 merges, 38 conflict-mentioning commits. The UNION
   resolution rule had to be learned and documented as a project learning.
4. **Unsafe LLM-mediated mutation** — observed data loss (item deleted mid-crash, never
   reinserted), duplicated paragraphs (BKL-7M4Q); products now write bespoke deterministic repair
   scripts instead of trusting the skill. There is no programmatic API — all CRUD is prose
   interpreted by a model, with real latency and token cost per operation.
5. **Git/process coupling** — filing entangles with the checked-out branch; concurrency control is
   prose DO-NOT-TOUCH lists in build plans (discodon's burndown plan excludes ~49 contended items
   by hand); `closed-by:` SHAs chicken-and-egg on amend; upstream reports need a machine-local
   drop-box pointer (`incoming-bugs/`).

## Success

- An agent files or queries an item in one non-interactive call, p95 < 2s, zero model tokens on
  the CRUD path.
- Two agents in parallel worktrees plus a human in a browser mutate the backlog concurrently with
  no lost updates and no merge conflicts, ever.
- Every checkout, worktree, and branch of a project sees the same live backlog — the observed
  66-stale-open-items worktree becomes structurally impossible.
- A consumer product files an upstream item against prawduct with no local prawduct checkout and
  no drop-box configuration.
- discodon's 317 open items (~435 with archive) migrate with IDs preserved, and triage sweeps get
  cheaper, not costlier.

## Actors

- **Project agents** — Claude sessions working the project: file, query, pick, update, comment.
- **Consumer agents** — sessions in downstream products filing upstream (today's incoming-bugs flow).
- **Humans** — owner and collaborators: browse, prioritize, comment, decide.
- **Background workers** — unattended triage/dedup/consolidation jobs.

## Requirements

MUST unless marked SHOULD.

### Data model

- **DM1** Items carry today's structured metadata as first-class queryable fields, not body text:
  `status`, `stage`, `area`, `effort`, `impact`, `source`, `added`, `reviewed`, claim/assignee —
  plus arbitrary labels. Vocabularies are **per-project extensible with soft enums** — observed in
  the wild: scriob's `kind:` facet on 158 items, `owner:`, `reverted-by:`, stage values
  `discovery` and `built`. Validation is advisory (flag unknown values); it never rejects a write.
- **DM2** Two orthogonal state axes survive: **status** (workflow: submitted → open → in-progress
  → shipped/dropped) and **stage** (maturity: idea/research/requirements/design/ready). Stage is
  load-bearing — it is how `pick` enforces requirements-precede-code (Principle 6). Do not flatten
  them into one enum.
- **DM3** Relationship types: `related`, `closes`/`superseded-by` (dedup merges), `blocks`/
  `blocked-by` (dependencies), parent/child (splits). Dependencies must be queryable — "open items
  whose blockers are all closed" is the ready-work query `pick` wants.
- **DM4** Stable, human-readable IDs, unique per project and unambiguous across projects (e.g.
  `prawduct#BKL-7M4Q`). IDs never change; a merge leaves a permanent redirect from the superseded
  ID. The legacy-alias map must absorb today's high-cardinality hand-invented prefixes (27–58 per
  project; hallucinote has 31 prefixes used exactly once).
- **DM5** Threaded, attributed, timestamped comments on items — the drill-down channel.
- **DM6** Attachments (screenshots, logs, repro files) on items and comments; size limit workable
  for log files (≥ 10 MB).
- **DM7** Nothing is hard-deleted by normal operation. Merge/split/drop preserve full bodies
  (today's archive discipline carries over).

### Agent ergonomics — the make-or-break

- **AG1** CRUD is deterministic code — CLI and/or MCP with flags, no interactive prompts, **no
  model in the loop**. Model judgment is reserved for triage decisions, never data plumbing. (Same
  doctrine as kernel v3: code, never a model, in the data plane.)
- **AG2** One-call create: `title` + `body` suffice; every other field is defaultable and
  backfillable later. Filing never blocks on classification. The zero-ceremony tier is a real
  user: metallm runs 5 items with no metadata at all; trenchant uses no stage/related/refs.
  Proportionality across a 5-item and a 435-item project is a requirement, not a nicety.
- **AG3** Dedup-on-create is advisory and asynchronous: create returns immediately with the new ID
  plus similar-item candidates; it never blocks or prompts. (Today it gates the add flow.)
- **AG4** Non-blocking under failure: unreachable service → writes queue locally and flush later;
  reads fall back to a local cache. A dead backlog service must never block a session, gate, or
  hook. The cache is **per project, shared across worktrees and clones** (git-common-dir keying,
  as the evidence store does) — never per-checkout, or the stale-view problem reappears. It also
  serves bulk reads: grooming fans out dozens of concurrent agent readers (48 observed in one
  discodon workflow) — those hit the local mirror, never the backend's rate limits.
- **AG5** Latency: p95 < 2s for create/update/query from a cold CLI; < 500 ms warm. (Numbers
  negotiable; order of magnitude firm.)
- **AG6** Machine-parseable (JSON) and human-readable output modes.

### Concurrency & integrity

- **CC1** Item mutations are atomic at the service; a crashed client can never leave a half-written
  item. (Kills BKL-7M4Q by construction.)
- **CC2** No lost updates: concurrent edits either merge field-wise or fail cleanly for retry;
  state transitions are check-and-set.
- **CC3** Claims are strongly consistent: claiming an item is an atomic take, visible immediately —
  upgrading today's advisory `accepted-by:`. Claims carry actor + timestamp; staleness is visible;
  reaping stays a policy/human call.
- **CC4** Every mutation records actor identity — which human, or which agent acting for whom, from
  which project/session — kept as per-item history. Git's free audit log gets replaced, not lost.
- **CC5** The adapter tolerates and reconciles **out-of-band human edits** made directly in the
  GitHub UI: a collaborator who removes a `stage:` label, closes an issue with no state-reason, or
  relabels an item must not corrupt the two-axis encoding (DM2). Drift is detected and either
  self-heals (labels re-derived from open/closed + state-reason where derivable) or is surfaced
  advisory — never silently mis-decoded. *Distinct from GV3* (item↔ship reconciliation): this is
  encoding↔direct-edit reconciliation, and it is a first-class feature (the human UI is a supported
  editing surface), not merely an error path.

### Truth & freshness

The evidence sweep ranks stale/wrong item state as the portfolio's #1 pain — above conflicts and
speed. Centralization alone fixes stale *views* (TF1); stale *content* needs TF2–TF3.

- **TF1** Single live view: one backlog per project; every checkout, worktree, branch, and agent
  reads the same current state. A cache serving stale data says so explicitly (age visible) —
  silent staleness is the observed failure, and it has misdirected real work.
- **TF2** Verification is first-class and cheap: recording "premise re-checked against code by
  <actor> on <date>" is one call, and staleness is queryable — "open items unverified in 90 days"
  is a standing triage query, and a `ready` item can carry evidence it is still real.
- **TF3** Mass grooming is a supported workload, not an abuse pattern: bulk re-stamp/close/update
  of dozens of items per pass (observed in one day: 25+ `reviewed:` stamps, 9 closes, 16 updates,
  2 promotions) without ceremony or rate-limit pain.

### Query

- **Q1** Server-side structured filters over all DM1 fields plus full-text over title/body/comments,
  with sort and pagination.
- **Q2** Changed-since cursor: cheaply enumerate items modified after a checkpoint — the primitive
  that makes background sweeps and local caches incremental instead of full-scan.
- **Q3** Similarity retrieval good enough for agent dedup at 500+ items: given a draft title/body,
  one call returns top-k plausible duplicates. Lexical is acceptable if precision holds; semantic
  is SHOULD.
- **Q4** Cross-project queries: one call across all my projects ("open governance items anywhere",
  "everything consumers filed against prawduct this month").
- **Q5** Counts and rollups derived on read, never persisted (the D14 discipline carries over).

### Cross-project flow

- **XP1** A consumer project's agent files an item against an upstream project's backlog directly —
  no upstream checkout, no drop-box pointer, no git.
- **XP2** Upstream submissions carry provenance (source product, version, session context) and land
  in a triage state (`submitted`), not straight into the working backlog.
- **XP3** (DESCOPED — owner, 2026-07-14) Submit-without-read on a *private* upstream is **not**
  required: filing into a private project may require access to that project's GitHub. Public
  projects expose anonymous filing instead (PV3). The drop-box's submit-without-read property is now
  a nice-to-have that must **not** drive the backend choice — its removal as a hard requirement is
  what reopens plain GitHub Issues (see Pushback 5).

### Privacy & access

- **PV1** Per-project visibility: a private project's backlog is readable/writable only by its
  contributors. Inherits repo access where the tracker is repo-adjacent; at minimum mappable to it.
- **PV2** Agents authenticate with real, scoped, revocable credentials per machine/agent — not a
  shared secret. Attribution (CC4) depends on this.
- **PV3** Public projects expose a public submission surface: **anonymous filing MUST work** for
  prawduct itself and for any public downstream repo. "Anonymous" means **no prior relationship with
  the repo owner** — requiring the filer to hold a GitHub account (or sign up on a self-hosted page)
  is acceptable friction (owner, 2026-07-14). Private projects need not accept anonymous filing (XP3).
- **PV4** Public submission surfaces (PV3) carry **abuse handling**: the anonymous-filing path must
  be rate-limitable and moderatable (spam/abuse triage), and its safety composes with the
  retro-governance path (`MET-6T4K`) that governs every out-of-band contribution before merge. PV3
  is per-project opt-in; enabling it depends on this. (Distinct from TF3, which is about *not*
  mistaking legitimate mass grooming for abuse; PV4 is about actual hostile submission.)

### Automation enablement

- **AU1** Events (webhooks) or cheap polling (Q2 cursors) let background workers react to new and
  changed items without full scans.
- **AU2** Batch operations: a triage sweep updates/labels/merges N items in few calls, idempotently.
- **AU3** Merge and split are first-class primitives, not conventions: merge preserves both bodies
  and leaves a redirect (DM4, DM7); split creates linked children.

### Governance integration (prawduct-side)

- **GV1** `/prawduct:backlog` keeps its UX contract (pick/add/find/list/update/dedup) as a thin
  wrapper over the service. `pick`'s stage-aware routing and build-plan awareness survive unchanged.
- **GV2** Session briefing reads counts from the local cache (AG4), refreshed asynchronously —
  session start never waits on the network.
- **GV3** Ship **traceability** replaces ship **atomicity**: closing an item still records
  `closed-by` (branch/PR/release handle), but the archive no longer rides in the closing PR — so a
  reconciliation sweep (janitor) must detect drift in both directions: items marked shipped whose
  PR died, merged work whose item is still open. This is the price of leaving git; pay it
  explicitly. (Native PR↔item linkage with close-on-merge, where the backend offers it, recovers
  most of the atomicity for the common path — better than today's manual archive discipline.)
- **GV4** Adopter-reproducible: prawduct is a plugin other people install. Whatever backend this
  prescribes must be something any adopter can stand up or sign up for — no backend that exists
  only on one person's machine.
- **GV5** Zero-cost provisioning: `/prawduct:onboard` (and `doctor`) provisions a project's
  backlog surface automatically. Eight projects today and there will always be more — per-project
  setup is one command or none.
- **GV6** Adoption **provisions and reconciles the label taxonomy** and **coexists with a repo's
  existing Issues**: `/prawduct:onboard`/`doctor` create prawduct's namespaced labels (`stage:`,
  `status:`, `kind:`, `id:` …) without colliding with labels or issues the repo already uses, keep
  the taxonomy consistent across repos, and never assume an empty tracker. A repo adopted mid-life
  already has Issues, labels, and milestones — the adapter treats non-prawduct items as
  out-of-scope, not as malformed backlog.
- **GV7** **Migration-required signal + shared read-path longevity.** While a project keeps a live
  markdown backlog and has not cut over (`backlog_service_repo` unset), a **warn-priority
  `backlog-service-migration-required` advisory** fires at session start — so a repo that adopts a
  plugin version past prawduct's own cutover is *told to migrate*, never silently degraded to a zeroed
  backlog count and lost grooming nudges. It is **distinct from `legacy-backlog-format`** (which nudges
  a *pre-structured* file toward the structured format): GV7 nudges a *structured* file onto the
  service, and retires on the same `backlog_service_repo` switch as the other markdown probes. Its
  prerequisite is MG3's shared read-path invariant — the plugin's markdown parser (today
  `lib/backlog/legacy.py`) is **retired only when the whole portfolio has migrated**, not at any one
  project's cutover; retiring it earlier is exactly the silent degradation GV7 exists to prevent.
- **GV8** **Norm-lifecycle signals survive cutover.** The three norm-lifecycle probes —
  `revisit-due` (a norm exception or stopgap whose expiry date has passed), `dead-why` (a norm whose
  stated rationale cites a shipped/dropped item), and `stalled-transition` (a `Status: in-transition`
  norm whose tracking item has not moved) — must keep firing after a project sets
  `backlog_service_repo`. Today each guards on `post_cutover` and returns nothing, so **a norm
  exception stops expiring visibly** — which is precisely the silent-departure failure the norm
  lifecycle exists to prevent (`docs/norms.md`, "Exceptions expire"). Losing them at cutover was a
  **side effect of the markdown-premise sweep, not a decision** (owner ruling, 2026-07-19).
  Three constraints shape the implementation:
  - **`revisit:` needs a home.** GitHub has no native slot for it, so it is a **block-authoritative,
    unmirrored** field in the `prawduct:` body block (Data Model §1.2), added under the
    additive-only-forever rule (§7).
  - **Probes must not touch the network.** They run at session start, where BLOCK-5/G2 forbid a
    blocking call, so the restored checks read a **local persisted store with visible age**,
    background-refreshed (the never-block pattern GV2 established for briefing counts).
  - **That store is the W1 cache — one persisted format, not a bespoke projection** (owner decision
    2026-07-19). GV8's readers join the other post-cutover backlog readers (Critic Backlog
    Reconciliation, PR `R-2`, janitor Backlog Health) behind the same cache rather than each minting
    its own. **GV8's restoration therefore lands with W1.**
  **Until W1 lands, degradation must be loud.** A guarded probe returning `[]`, and a skill reading
  the frozen markdown as if it were live, are both *silent* — the failure GV8 exists to prevent. In
  the interim every post-cutover backlog reader states plainly that the check is unavailable on the
  Issues backend. A missing check a reader is told about is recoverable; one it is not told about is
  the norm-exception hole again, one layer down.
- **GV9** **Item references survive the identifier change.** After cutover the canonical id is
  `owner/repo#number` and **no new `PFX-XXXX` is ever minted** (Data Model §5;
  `lib/backlog/ids.py`) — the `id:PFX` alias exists so *migrated* items' old refs resolve forever,
  not as a continuing scheme. Every surface that **cites** an item must therefore recognize *both*
  forms: the PFX alias for migrated items, and `owner/repo#number` / `repo#number` for everything
  filed after cutover. Today several recognize only the first — e.g. `lib/norm_probes.py`'s
  `_BACKLOG_ID_RE` (`\b[A-Z]{2,4}-[A-Z0-9]{4}\b`), the Critic's C-B4 dangling-id check, PR review
  `R-2`'s `closes: PFX-XXXX` reconciliation, `closes:`/`closed-by:` in backlog metadata and
  change-log tags, and the deferred build-plan backlog-id verification
  (`lib/buildplan_refs.py`). A citation surface that recognizes only PFX does not error on a
  post-cutover reference — it **fails to see it**, which is the same silent degradation GV7 and GV8
  exist to prevent, one layer down: a dangling-id check that cannot parse the id reports a clean
  pass.
  - **Recognition is additive** (API contract: additive-first evolution). PFX matching is never
    narrowed or replaced; the native form is accepted *alongside* it, because both remain valid
    forever in any repo that migrated.
  - **Recognizing is not resolving.** Parsing a reference is local and cheap; answering "is
    `owner/repo#123` still open?" is a backlog read and therefore lands with the W1 cache under GV8.
    The parse-side work can ship well before the resolve-side, and should — a surface that can *see*
    a post-cutover reference but must say "status unavailable" is strictly better than one that
    silently treats it as absent.

### Migration & exit

- **MG1** One-shot importer for existing `backlog.md` (+ `backlog-archive.md`): IDs, metadata bars,
  bodies, and sections preserved verbatim. Existing IDs stay valid — change-logs, learnings, and
  commit messages cite them.
- **MG2** Full-fidelity export to plain files, scriptable, at any time. The backlog is never
  hostage to a vendor or a server; export doubles as backup.
- **MG3** Per-project adoption: projects migrate independently; file-based and service backlogs
  coexist across the portfolio during transition (never within one project). Because the adapter
  ships in the **shared plugin**, portfolio coexistence binds the plugin's **markdown read path**
  (briefing counts + the markdown-premise advisory probes) to keep working for every un-migrated repo
  until the *last* project cuts over — no single project's cutover (prawduct's own included) may
  retire it (GV7).
- **MG4** Migration supports a **one-time pre-migration scrub** so stale, obsolete, and duplicate
  items are *not* carried into the new store (garbage-in-garbage-out would re-seed the #1
  stale-content pain the project exists to kill — the moment you touch every item is the moment to
  groom). The scrub: (a) grooms live items (close dead-premise / already-shipped, merge duplicates);
  (b) decides **archive scope** as an **explicit owner-confirmed choice surfaced at scrub time**, not
  a silent default — `open` (migrate only the live/open set as issues; the historical archive stays as
  the MG2 export file, minting no closed issue per ancient item) or `all` (import the full archive as
  closed issues, the pre-scrub behavior). The importer honors the chosen scope through an
  `--archive-scope` selector (AG1 — a deterministic lever, not a model inference). `open` also
  **reduces the total write volume** of a large migration (fewer creates) — but the write-*rate*
  ceiling is enforced by the Pacer, **not** by this lever; crediting the archive window as the
  rate-budget keeper is the mis-attribution **BKL-6X5D** was filed to correct (NF3). A quantified *recent-shipped
  window* between the two poles (migrate the last N months of archive, drop older) is the adopter-scale
  refinement tracked by **BKL-6X5D** — its window is deliberately not yet quantified; (c) **disposes, never hard-deletes**
  (DM7) — scrubbed items are closed/dropped-with-reason in the file backlog (git preserves them) or
  live in the export; (d) is **model-assisted, human-confirmed** (candidates surfaced via TF2
  stale-verification + Q3 similarity; the owner confirms dispositions; deterministic import then runs
  on the cleaned set, AG1). prawduct's own backlog runs the scrub for real (dogfood); adopters get an
  **optional advisory pre-scan** (flag likely-stale/dup candidates, skippable — we can surface but
  not groom their data).

### Non-functional

- **NF1** Cost ≤ ~$10/month **total across the whole portfolio** (owner ceiling, 2026-07-14) —
  **not** per project. A backend priced per-project, per-workspace, or per-seat-multiplied-by-projects
  fails at 8+ projects (the owner explicitly rules out $10 × 8). Per-*seat* pricing on a single
  shared workspace is acceptable only while it stays one seat. $0 remains strongly preferred: under
  GV4 every adopter inherits whatever cost model prawduct prescribes, so a paid backend taxes the
  entire ecosystem, not just the owner. A knowable ceiling as usage grows (Principle 9).
- **NF2** Ops burden near zero. If self-hosted: one boring always-on process, trivial backup (MG2).
- **NF3** Rate-limit headroom: ~200 write-ops/day/project plus sweep queries must clear any
  third-party backend's limits by 10×. Read amplification (concurrent grooming agents) is served
  from the local cache (AG4) — the backend budget is spent on writes and sync only.

## Out of scope

- Sprint/velocity ceremonies, time tracking, roadmapping — a backlog, not a PM suite.
- Moving change-log, learnings, or build plans — they stay in git; items link to them via refs.
- Notification-heavy collaboration; real-time presence.
- The triage intelligence itself — AU1–AU3 enable it; the workers are separate prawduct work.

## Pushback on the initial sketch

1. **"Not coupled to PRs" — half right.** Decouple the *mechanics* (no git commit to edit an item),
   but today's archive-rides-in-the-closing-PR exists for a reason: an abandoned PR abandons the
   archive, so backlog state can't drift from shipped reality. Leaving git trades that atomicity
   away. GV3 replaces it with traceability + reconciliation rather than losing it silently.
2. **"Supports background processing to triage/merge/split" — reframed.** That's not a tracker
   feature, it's tracker *primitives* (AU1–AU3). The triage workers are prawduct-side follow-on
   work, deliberately out of scope here.
3. **Your state list flattens two axes.** "Submitted, in review, backlog, won't-fix, in-progress,
   complete" mixes workflow with maturity. Prawduct's `stage:` axis is a governance mechanism (it's
   what stops a vague idea being picked as buildable), not just metadata — DM2 keeps both axes.
4. **"Query for similar items" — split.** Structured + lexical search is a MUST; *semantic*
   similarity is a SHOULD (Q3). Don't buy embedding infrastructure before lexical retrieval plus
   agent judgment on the candidates proves insufficient.
5. **"Follow github repo privacy" — sharpened, then relaxed.** The subtle case was XP3,
   submit-without-read: a private upstream backlog that consumers can file into but not browse.
   Plain GitHub Issues on a private repo cannot do this — non-collaborators can't file at all.
   **The owner descoped this on 2026-07-14** (filing into a private project may require repo access),
   which *removes* the single requirement that most argued against plain GitHub Issues. Public
   projects keep anonymous filing via public issues (PV3), which GitHub does natively.
6. **Requirements you didn't list that matter most:** no-model-in-the-loop CRUD (AG1 — this is
   most of "slow"), offline queue (AG4 — governance must never block on the network), strong claims
   (CC3), mutation history (CC4 — git's audit log was free; replace it), changed-since cursors
   (Q2), cross-project rollups (Q4 — your goal statement implies it, the sketch never says it),
   adopter-reproducibility (GV4 — prawduct is distributed; the backend can't be bespoke to you),
   and exit/export (MG2).
7. **The sketch's framing undersold the deepest problem.** "Slow, conflicts, git coupling" are
   real, but the portfolio evidence ranks *state trust* first: stale and outright wrong items
   misdirect work (one described a destructive live code path as dead), and every serious
   consumer has stopped trusting item text. Hence the Truth & freshness group (TF1–TF3) — no
   tracker satisfies TF2/TF3 out of the box; they drive the adapter design as much as the
   offline cache does.

## Assumptions (vetoable)

Owner review 2026-07-14 **confirmed** the load-bearing one, and it binds harder than first written:
prawduct is distributed, GV4 is a hard requirement, and the backend must work for adopters in
**private repos the owner cannot access** and for **anonymous filers** (see Owner decisions). That
closes the escape hatch the old HIGH-impact assumption held open.

- **CONFIRMED (owner, 2026-07-14):** GV4 is hard and binds to adopters the owner has no relationship
  with — private-repo adopters and anonymous filers included. Any backend that only the owner can
  provision, pay for, or grant access to is disqualified as the *prescribed* backend. (Was:
  `[ASSUMPTION: … if prawduct is personal tooling, GV4 relaxes and self-hosting gets easier]` — the
  owner explicitly declined that relaxation.)
- Verified (2026-07-13 sweep): all backlog-bearing projects live on GitHub, split across at least
  two owners — `pacepace` (scriob, discodon) and `brookstalley` (hallucinote, prawduct).
  `[ASSUMPTION: this two-owner GitHub split is the durable shape — future products land under one
  of these or another GitHub owner | MED impact | affects the org-fields vs labels design fork]`
- `[ASSUMPTION: learnings.md and change-log.md stay in git — only the backlog moves | MED impact]`
- `[ASSUMPTION: AG5 latency numbers are the right order of magnitude | LOW impact]`

## Owner decisions (2026-07-14)

The three open questions are resolved:

1. **Who else runs this?** Every adopter — not the owner alone. It **must work for adopters in
   private repos the owner cannot access** (GV4 confirmed hard). This dominates adopt-vs-build: any
   backend the owner must host, pay for, or grant access to cannot serve those adopters.
2. **Hosting stance.** The owner is **equally comfortable with (a) GitHub-native, (b) hosted SaaS,
   and (c) self-hosted** for their *own* operation; (d) local-first is not preferred. Operational
   tolerance no longer eliminates (b)/(c) — but decision (1) plus the cost ceiling (NF1) and
   anonymous filing (3) still select **(a) GitHub-native** as the only option satisfying the whole
   set at $0 with zero per-project scaling. (b)/(c) work for the owner's own portfolio but fail the
   adopter case.
3. **Anonymity of filing.** Filing **may require access to the project's GitHub.** Public repos are
   therefore *truly* no-relationship: anyone with a GitHub account can file, which is acceptable
   friction (a required account/signup is fine; a prior relationship with the owner is not). Private
   repos require access — so **XP3 (private submit-without-read) is descoped.** Anonymous filing MUST
   work for prawduct and public downstream repos; it need not for private ones.

## Prior art (researched 2026-07-13, live sources)

Two research passes: purpose-built agent-native trackers, and mainstream trackers' 2026 agent
story. Full agent reports available on request; what matters for the decision:

### Agent-native tier

- **beads** (Yegge, 25k★, v1.1.0 Jul 2026) — the only OSS tool with nearly our whole list:
  atomic claims, ready-work dependency queries, `bd duplicates --auto-merge`, cross-repo filing
  with provenance, Postgres/shared-server modes, MCP + JSON CLI. But: storage layer rewritten
  twice in 9 months (JSONL→SQLite→Dolt), a documented H1-2026 backlash (invasive hooks/daemons,
  bloat — spawned multiple "simpler beads" forks), and increasing gravity toward the Gas Town
  orchestration ecosystem. Adopting it means absorbing an opinionated, fast-churning dependency.
- **Backlog.md** (6.2k★, releases weekly) — healthiest simple option: file-per-task markdown
  (kills most single-file merge conflicts), CLI + MCP, web UI. But still git-coupled, per-repo,
  no cross-project filing, no claims. Fixes our conflict problem, not our coupling problem.
- **ticket / beans / ait / backloghq** — each proves a competent dev can build the minimal core
  in weeks (SQLite or files + JSON CLI + claims + ready-query). None has centralized
  multi-project or upstream filing. Micro-communities (2–900★).
- **Hiveship** (hiveship.app) — hosted, agent-first, MCP-native, agents as assignees; exactly our
  category. Early-access closed SaaS, unknown backing, no self-host. The same market segment
  killed Height (dead 9/2025, data deleted), Tegon (archived), and Bloop (shut down 4/2026) —
  betting the portfolio's backlog on a young closed SaaS fails MG2/NF1 risk tolerance.

### Mainstream tier (what changed in 2025–26)

- **GitHub Issues closed almost every historical gap**: sub-issues + issue types GA 4/2025;
  dependencies (blocked-by) GA 8/2025; **semantic + hybrid issue search GA 4/2026** (REST/GraphQL,
  org-scoped); **typed custom Issue Fields GA 7/2026, free** — org-owned repos only; `gh` CLI
  v2.94+ has one-call create with type/parent/blocked-by + JSON out; MCP server incl. fields and
  duplicate detection; Claude agents assignable to issues. Rate limits clear NF3 (5k/hr core;
  tightest: 80 writes/min, 10 semantic searches/min — sweeps must pace). **One real gap: no public
  API for issue attachments** (workaround: release assets or orphan branch, both API-supported).
  Privacy: issues inherit repo visibility — the only candidate where PV1 is structural, free.
  *(Correction, verified 2026-07-16: the write cap is 80 content-creations/min **and ~500/hr** — a
  secondary limit; migration especially must pace across time, not just per-minute.)*
- **Linear** — best-in-class agent ecosystem (official hosted MCP, agents as non-seat teammates,
  OpenAI's Symphony uses it as an agent control plane). **Per-seat, not per-workspace** (Basic
  $10/user/mo, verified 2026-06): one workspace holds all teams/projects with unlimited issues on
  paid — the free tier's **2-team / 250-issue** caps (< discodon today), not any per-project fee,
  are what force the upgrade. But: **no custom fields, ever** (stage/effort/impact become labels),
  no self-host, privacy is manual workspace convention, and **human collaborators each cost a seat**
  (agents don't). Runner-up — viable solo, unreproducible for adopters (GV4).
- **Jira** — verified anti-fit: ADF JSON comment format, documented stale-read search ("may
  return outdated data"), unpublished token rate limits, multi-second latency complaints.
- **Self-hosted** (Gitea/Forgejo, GitLab, Plane, Huly) — Gitea/Forgejo is the best power-to-weight
  (single binary, no rate limits, attachment API, official MCP) but no custom fields and it means
  running a second forge — privacy inheritance only works if the code actually lives there.
  GitLab gates custom fields + MCP behind Premium. Plane gates custom fields behind Pro even
  self-hosted, 60 req/min. Huly has no stable API. All fail NF2 (you become an operator) or GV4.

## Build / Adopt / Buy

**Buy (hosted SaaS — Linear, Hiveship):** economics reconsidered (2026-07-14), verdict unchanged.
Linear is **per-seat, not per-workspace** (Basic $10/user/mo): one workspace holds all 8 projects
as teams with unlimited issues, and a solo owner pays a single ~$10/mo seat — which *meets* the
corrected NF1 for the owner's own portfolio (the free tier's 2-team / 250-issue caps, not per-project
fees, are what force paying). So the owner's "per-workspace pricing scares me" is unfounded; the
real per-seat sting is **human collaborators** (each a full seat — agents are non-seat). Linear still
loses as the **prescribed** backend on Owner decision (1): under GV4 every adopter would need their
own workspace and their own paid seat — prawduct cannot prescribe "sign up and pay Linear," and
private-repo adopters the owner can't reach are unreachable. It also has no native anonymous
public-filing surface (Owner decision 3), no custom fields (DM1), manual privacy (PV1), and no
self-host / weaker export (MG2). **Net: genuinely viable for a solo owner in isolation — wrong for a
distributed plugin.** The only scenario that flips this is relaxing GV4 (prawduct as personal
tooling, adopters keep files), which the owner declined. Hiveship is category-correct but
survival-risk; three of its nearest neighbors died within the last year.

**Build (our own tracker):** the 2024-era gap that justified building — structured metadata +
agent-speed API + privacy inheritance — was closed by GitHub's 2025–26 shipping cadence. The
minimal-tracker tier (ticket, ait) proves the core is a few weeks' work, but GV4 cuts against it:
every prawduct adopter would have to run our bespoke service, and we'd own uptime, auth, backup,
and migration forever. Building the *tracker* buys nothing GitHub doesn't now give away.

**Adopt (GitHub Issues as system of record) + build the thin adapter — recommended.** The
requirements GitHub can't satisfy alone are exactly prawduct-shaped glue, and they're the same
"code, never a model" data-plane doctrine as kernel v3:

| Gap | Adapter answer |
|---|---|
| AG4/GV2 offline + never-block | local cache, `since`-cursor reconciliation, queued writes |
| AG3/Q3 dedup-on-create | GitHub duplicate detection + semantic search, paced at 10/min |
| XP2 provenance | issue-body template + `source:<product>` labels stamped by the adapter |
| CC3 claims | assignee check-and-verify convention (GitHub has no CAS on assignment — accepted residual race, far smaller than today's) |
| DM4 ID continuity | importer preserves `[PFX-XXXX]` as an aliased field/label; adapter resolves old refs |
| DM6 attachments | wrap the release-asset upload pattern |
| AU2 pacing | batch ops throttled under 80 writes/min |
| TF2 verification stamps | structured "verified-against-code" facts (marker comment or field) + staleness queries |
| DM1 soft per-project vocabularies | label conventions (`stage:ready`, `kind:implement`) — labels are per-repo and free-form |

### Recommendation

1. **Adopt GitHub Issues** as the per-repo system of record; **Projects v2** only for the
   cross-repo rollup board (Q4 also served by org-scoped semantic/lexical search).
2. **Labels are the baseline encoding; Issue Fields are an enhancement layer.** Fields and Types
   are **org-only**, and the portfolio already spans two owners (`pacepace`, `brookstalley`
   — personal accounts get no fields), so the adapter must run label-only (`stage:ready`,
   `effort:M`, `kind:implement`) everywhere and use org Fields where a repo's owner provides
   them. Labels also fit the observed soft, per-project vocabularies better than 25-per-org
   shared field definitions. Deciding whether to consolidate repos under one org is a design-time
   question, not a blocker.
3. **Build `prawduct backlog` adapter** (deterministic CLI in the plugin, no model in the loop)
   implementing the table above; `/prawduct:backlog` keeps its UX as a thin wrapper (GV1).
4. **Replace the incoming-bugs drop-box** with direct cross-repo filing (XP1) — same-owner
   portfolio needs nothing extra; third-party and anonymous consumers file against the **public**
   prawduct repo (a GitHub account is the only barrier — Owner decision 3). XP3 (submit-without-read
   on *private* upstreams) is **descoped**, not merely deferred — the owner accepts that filing a
   private project requires access to it.
5. **Phase it:** (a) 1-day spike — `gh` p95 latency, label-encoding round-trip, org-fields check,
   importer dry-run on a small repo (puzzles or metallm); (b) adapter + migrate one mid-size
   project (cordyceps); (c) migrate discodon (317 open + the 1,754-line `backlog-archive.md`) and
   scriob, retire the drop-box; file-backlog products coexist meanwhile (MG3). The importer
   targets each project's **canonical checkout only** — the five stale snapshot copies found in
   the sweep (scriob2, hallucinote-2, discodon-offline/-evals/-ts, two still on the pre-v2 legacy
   format) are dead views to ignore, plus one item marooned in discodon-brooks2 (SOL-K3PN) to
   rescue by hand.
6. **Borrow beads' semantics, not beads:** ready-work query, claim conventions, duplicate links,
   provenance fields are proven designs to copy into the adapter.

Why this best serves prawduct *and its consumers* (GV4): every adopter whose repo is on GitHub
already has the backend — no new account, no server, no cost; privacy inheritance is automatic;
and the adapter ships inside the plugin they already install. Exit stays cheap (MG2: API export
to files is trivial; the format is the industry's most portable).

### Assign-to-agent: a primitive to use, an autopilot to gate

"Claude agents assignable to issues" (Mainstream tier, above) is **two capabilities**, and prawduct
wants them on opposite terms:

- **Assignee-as-claim (adopt).** Native issue assignment — to a human *or* a named agent identity —
  is exactly the **CC3** claim primitive and **CC4** attribution, for free. The adapter should model
  "who holds this item" on top of native assignment rather than inventing a parallel `accepted-by:`
  convention. Linear offers the same (agents as non-seat teammates); it is a point for mainstream
  trackers over a bespoke build, not a GitHub exclusive.
- **Autonomous issue→PR execution (gate).** GitHub's coding-agent path (`@claude` via
  `anthropics/claude-code-action`, or org-enabled assign-to-agent) will take an issue and open a PR
  unattended. Powerful, but it **bypasses the prawduct build cycle** — no stage/requirements gate
  (Principle 6), no Critic, no reflection. It is safe only for `stage: ready`, well-scoped items,
  and even then human/CI still gates the merge (the agent cannot self-approve — some independent-review
  posture survives, but not the Critic specifically). **Doctrine:** the governed cycle stays the
  default; assign-to-agent is an opt-in fast lane for ready items, and where used it should invoke
  the prawduct cycle *inside* the action, not raw code-and-PR. This is an adapter workflow-design
  question, not a backend-selection one — both GitHub and Linear expose this autopilot.

The three mitigations — an **assignment-time gate** (`stage: ready` + linked requirement only), the
**cycle-in-CI** wrapper above, and a **retro-governance path** that reconciles *any* out-of-band PR
(agent autopilot, a hand-coded branch, or an external/anonymous contributor's fork) against the
cycle before merge — are captured as backlog item `MET-6T4K` and treated as adapter-phase work. The
retro-governance path is the general case and likely the keystone: it extends **GV3**'s
reconciliation from item↔ship drift to *cycle-compliance* drift, and it is precisely what makes the
anonymous/third-party filing invited by **PV3** safe to accept — every out-of-band contribution
gets governed on the way in, not waved through. Retro-governance is a large enough topic to warrant
its **own spec later** — it also underpins **onboarding an existing, ungoverned repo** (the same
retroactive-cycle problem at repo scale) — so it is only *referenced* here, not designed (`MET-6T4K`
parks it).
