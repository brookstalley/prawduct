# Backlog Service — Requirements

`status: draft v2 — evidence-sharpened, awaiting owner review · added: 2026-07-13 · source: discovery session · stage: requirements`

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
- **XP3** Submit-without-read: submission rights are grantable without full backlog visibility — a
  consumer allowed to file must not thereby see the entire private backlog. (The drop-box's one
  genuinely good property — keep it.)

### Privacy & access

- **PV1** Per-project visibility: a private project's backlog is readable/writable only by its
  contributors. Inherits repo access where the tracker is repo-adjacent; at minimum mappable to it.
- **PV2** Agents authenticate with real, scoped, revocable credentials per machine/agent — not a
  shared secret. Attribution (CC4) depends on this.
- **PV3** Public projects MAY expose a public submission surface; per-project choice.

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

### Migration & exit

- **MG1** One-shot importer for existing `backlog.md` (+ `backlog-archive.md`): IDs, metadata bars,
  bodies, and sections preserved verbatim. Existing IDs stay valid — change-logs, learnings, and
  commit messages cite them.
- **MG2** Full-fidelity export to plain files, scriptable, at any time. The backlog is never
  hostage to a vendor or a server; export doubles as backup.
- **MG3** Per-project adoption: projects migrate independently; file-based and service backlogs
  coexist across the portfolio during transition (never within one project).

### Non-functional

- **NF1** Cost ≈ $0/month at current scale (one operator, a handful of projects, several agents);
  a knowable ceiling if it grows (Principle 9).
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
5. **"Follow github repo privacy" — sharpened.** The subtle case is XP3, submit-without-read: a
   private upstream backlog that consumers can file into but not browse. Plain GitHub Issues on a
   private repo cannot do this — non-collaborators can't file at all. This single requirement does
   a lot of work in the adopt-vs-build decision.
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

- Verified (2026-07-13 sweep): all backlog-bearing projects live on GitHub, split across at least
  two owners — `pacepace` (scriob, discodon) and `brookstalley` (hallucinote, prawduct).
  `[ASSUMPTION: this two-owner GitHub split is the durable shape — future products land under one
  of these or another GitHub owner | MED impact | affects the org-fields vs labels design fork]`
- `[ASSUMPTION: single-operator scale today, but prawduct's plugin distribution makes
  adopter-reproducibility (GV4) a hard requirement | HIGH impact | if prawduct is effectively
  personal tooling, GV4 relaxes and self-hosting gets much easier]`
- `[ASSUMPTION: learnings.md and change-log.md stay in git — only the backlog moves | MED impact]`
- `[ASSUMPTION: AG5 latency numbers are the right order of magnitude | LOW impact]`

## Open questions

1. **Who else runs this?** Is the backlog service for you alone, or part of what prawduct offers
   every adopter? GV4 assumes the latter; it dominates adopt-vs-build more than any feature row.
2. **Hosting stance** — rank your tolerance: (a) GitHub-native (no new infra; rate limits and the
   XP3 gap), (b) hosted SaaS (fastest to adopt; lock-in, $, privacy), (c) self-hosted service (full
   control; you become an operator), (d) local-first/replicated (no server; weaker centrality and
   cross-project queries).
3. **How anonymous is upstream filing?** Must XP1 work for consumers with *no* upstream access
   relationship at all (true third parties), or only for products you also own?

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
- **Linear** — best-in-class agent ecosystem (official hosted MCP, agents as non-seat teammates,
  OpenAI's Symphony uses it as an agent control plane). But: **no custom fields, ever** (stage/
  effort/impact become labels), no self-host, privacy is manual workspace convention, free tier
  caps at 250 issues (< discodon today), $120/yr solo. Runner-up.
- **Jira** — verified anti-fit: ADF JSON comment format, documented stale-read search ("may
  return outdated data"), unpublished token rate limits, multi-second latency complaints.
- **Self-hosted** (Gitea/Forgejo, GitLab, Plane, Huly) — Gitea/Forgejo is the best power-to-weight
  (single binary, no rate limits, attachment API, official MCP) but no custom fields and it means
  running a second forge — privacy inheritance only works if the code actually lives there.
  GitLab gates custom fields + MCP behind Premium. Plane gates custom fields behind Pro even
  self-hosted, 60 req/min. Huly has no stable API. All fail NF2 (you become an operator) or GV4.

## Build / Adopt / Buy

**Buy (hosted SaaS — Linear, Hiveship):** fails on portfolio fit. Linear misses DM1 (no custom
fields) and PV1 (manual mapping), and per-workspace pricing scales badly across "we always will
have a lot of projects." Hiveship is category-correct but survival-risk; three of its nearest
neighbors died within the last year.

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
   portfolio needs nothing extra; third-party consumers file against the public prawduct repo.
   XP3 (submit-without-read on *private* upstreams) is deferred — revisit if it ever materializes.
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
