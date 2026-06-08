# Backlog System — Requirements

**Status:** Draft v0.2 (2026-05-28) — **Phase 2 lean core built and shipped in framework v1.7.0** (2026-05-29). Shipped: the structured item format + three-section file (§3), the forked `/backlog` skill with `add`/`list`/`find`/`update`/`pick`/`migrate` (§4), and the single `legacy-backlog-format` post-sync probe (§8.2) registered against the v1.6.0 advisory infrastructure. **Deferred on proportionality grounds** (filed into `.prawduct/backlog.md`, not dropped): the other three probes (`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`), `/backlog import` (§4.3/§8.4), `/backlog dedup` (§4.3), the janitor Step 2.5 triage (§6) incl. the Q2 archive-split, the four Critic checks C-B1–C-B4 (§7), the `/backlog dismiss-advisory` alias (§8.2), the build-plan hygiene-step doc (§5.3), and the prawduct-doctor setup-time external-file report (§8.3) — each added when a real product needs it.
**Scope:** Improve backlog management across all Prawduct products — creation, grooming, grouping, prioritization, and "pick what to do next" selection.
**Out of scope:** Build plan (separate deliverable, after these requirements are approved).
**Changes from v0.1:** §8.1 and §8.2 reconciled with the now-drafted `documentation/post-sync-advisory-spec.md` (v0.2). The previously hand-waved advisory mechanism is now concrete infrastructure; this doc references it rather than restating it. `/backlog dismiss-advisory` clarified as a per-feature alias for `/prawduct-advisory dismiss`. §12 dependency on advisory infrastructure points to the spec.
**v0.3 status:** BUILT on branch `feature/backlog-rework` (10 chunks, 2026-06-08) — parser substrate (`lib/backlog.py`), `accepted-by`/`stage`/`refs` fields, stage routing, dedup + triage method, Critic C-B1–C-B4 + PR R-1/R-2, the three probes, archive discipline + janitor Step 2.5, `/backlog import` + doctor report, workflow wiring. Ships in the next release. The v0.2-deferred items it subsumes are reconciled in `.prawduct/backlog.md` (BKL-2F7K/3R8P/5H9M/1V8J/6L3Q, CRT-3K9P, JNT-7T1W → shipped). Still deferred: BKL-4N6X (dismiss-advisory alias — pure ergonomics, no consumer yet).
**Changes from v0.2 (→ v0.3, 2026-06-08):** The "lean core" shipped in v1.7.0, then sat untouched while products accumulated usage. Real friction from `../scriob` (a multi-agent prawduct-consuming product) drives this revision — see §0. v0.3 (a) adds three capabilities the lean core never had (a per-actor **claim** field, a feature-**lifecycle stage** field that closes a requirements-precede-code hole, and a **doc-reference** field), (b) promotes the v0.2-deferred pieces (the four Critic checks, dedup, janitor Step 2.5, the three remaining probes, import) from "build when a product needs it" to "in scope now — a product needs it," (c) specifies a **structured parser substrate** (`lib/backlog.py`) the lean core skipped, and (d) **wires the skill into the work cycle** (the lean core left it self-serve). Two constraints fixed by the product owner: **claims do NOT auto-expire** (a durable claim is legitimate; stale-claim management is an out-of-scope process concern), and **migration/cleanup of existing projects is folded into triage** (the new fields are additive/optional; bringing a messy backlog up to standard is a triage operation, not a separate subsystem).

---

## 0. v0.3 release scope — the backlog rework

v0.3 is one batched, multi-chunk release. It is motivated by five concrete failures observed in `../scriob` plus the meta-observation that **the backlog sits beside the work cycle rather than wired into it** (nothing routes agents to `/prawduct:backlog`, so they hand-edit the markdown). The failures reduce to four root causes:

| Root cause | Observed failures it produces |
|---|---|
| **A. Not wired into the workflow** — nothing routes an agent to the skill | "agents aren't using `/backlog`"; completed work left stale; strikethrough instead of archive |
| **B. D4 (never infer status) is correct, but the compensating nudges were all deferred** (C-B1–C-B4, janitor triage, grooming probe) | completed items linger as `open` with no prompt to close them |
| **C. The format models *state* but not *who holds an item* or *what stage of thinking it is at*** | no claim/lock for multi-actor work; vague items default straight to code with no requirements |
| **D. No codified triage *method*** — every project reinvents grooming | duplicate/overlapping items; no doc-linking convention |

### 0.1 New capabilities (not in v0.2)

- **`accepted-by:` claim field (root cause C).** An optional metadata field naming the actor currently holding an item — a *soft, observable, durable* claim so a second agent/user doesn't double-pick. **Does not auto-expire** (product-owner decision): the claim persists until explicitly cleared or until `status`→`shipped`/`dropped` clears it. `/backlog pick`/`list` exclude claimed items by default; `/backlog update … accepted-by=@actor` sets it, `accepted-by=` (empty) clears it. **Honest limit:** markdown-in-git is eventually-consistent — in separate worktrees two actors won't see each other's claim until commit+pull. This makes double-picks *visible and recoverable*, NOT impossible; it is explicitly **not** a mutex. A real-time lock would need a shared mutable store (out of scope — see §11). This amends non-goal §2.2 (see §3, D10).

- **`stage:` lifecycle field + routing (root cause C — the keystone).** An optional field placing an item in the feature lifecycle: `idea → research → requirements → design → ready` (not every item visits every stage; many cleanup/bug items are born `ready`). The point is **changing the agent's default**: a vague item like *"stories need genre indicators and conventions"* is an **undocumented requirement** (Principle 6; the v2.0.13 work-model feature). Today the default is "write code." With `stage:`, `/backlog pick` surfaces the stage and routes early-stage (or **unspecified**) items to `/prawduct:discovery`/`/prawduct:planning` — **the next work for an `idea`/`requirements`-stage item is discovery, not implementation.** An item with no `stage:` is treated as *not yet ready to implement* (fail toward requirements, not toward code). See §5a.

- **`refs:` doc-reference field (root cause D).** An optional field linking an item to the artifacts that govern it — `refs: requirements-X.md#section, arch-Y.md`. Distinct from `related:` (item→item). Lets a `requirements`-stage item point at the requirements doc once written, and lets triage cluster items around the docs they touch.

- **`lib/backlog.py` parser substrate (enabling foundation).** The lean core has *no* structured backlog parser (unlike the change-log's `lib/views.py`); the only runtime reader is a textual line-count in `lib/briefing.py`. A real parser — items (ID, metadata bar, sections, body), tolerant of legacy/unstructured items — is the substrate every capability below needs (claim-filtering, stale detection, dedup, stage-aware pick, the probes). This is the thin-vertical-slice first chunk.

### 0.2 Promoted from v0.2-deferred (now in scope)

- The four Critic checks **C-B1–C-B4** (§7) — NOTE-level, per D1.
- **PR-reviewer backlog reconciliation** (NEW surface, §7a) — the PR boundary is the natural "a branch of finished work is merging — did you update the items it closed?" checkpoint; the v0.2 design only put reconciliation in the Critic.
- **`/backlog dedup`** (§4.3) and **janitor Step 2.5 backlog triage** incl. the Q2 **archive-split** (§6).
- The three remaining probes — **`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`** (§8.2).
- **`/backlog import`** (§4.3) + the prawduct-doctor setup-time external-file report (§8.3).
- **Archive discipline + strikeout cleanup** (NEW, §5b): "done" = `status=shipped`/`dropped` → **move to `## Archive`**, never strikethrough and never left inline in `## Open`. A one-shot cleanup sweep (part of `/backlog migrate`/triage) converts existing strikethrough items. Resolves observed failure #3 (token growth from struck-out items).

### 0.3 Workflow wiring (root cause A — cross-cutting)

Methodology routes agents to the skill rather than hand-editing: `methodology/building.md` chunk-close (update affected items via `/backlog update`), `methodology/reflection.md` (capture via `/backlog add`), `methodology/planning.md`/`discovery.md` (select via `/backlog pick`, and an early-`stage:` pick routes to discovery). The Critic/PR checks above make non-canonical edits (strikethrough, stale items) **visible**. Per the original design's S6 (watch for governance fatigue) and Principle 11, this is **route + flag, not hard-gate** — no new blocking gate; the nudges are NOTE/WARNING and advisory. A framework-default behavior change that must reach already-onboarded repos rides `methodology/session-digest.md` (the only universally re-read surface — see learnings "framework-level default behavior").

### 0.4 Migration / cleanup for existing projects (= triage)

The new fields are additive and optional, so every existing backlog (structured or legacy) remains valid with zero forced change. Bringing an existing project up to the v0.3 standard is a **triage operation**, not a migration subsystem: `/backlog migrate` (legacy→structured, already shipped) gains the strikeout-cleanup sweep; janitor Step 2.5 surfaces stale/dup/unstaged items; `/backlog import` covers projects with an external `TODO.md`/`BACKLOG.md`. No auto-rewrite of existing items' `stage:`/`accepted-by:` — those are backfilled opt-in during triage.

---

## 1. Problem & motivation

### What exists today

Each Prawduct product has a single flat markdown file at `.prawduct/backlog.md`. Items are appended as bullets by four sources: `builder`, `critic`, `reflection`, `janitor`. Two sections exist by convention: `## Active — next up` and `## Queue`. Items range from one line to multi-paragraph analyses. No IDs, no metadata, no grouping by topic, no effort/impact estimates, no automatic linking to build plans or change logs.

### Pain points observed in flight

Reading the flagship product (this repo, 43 items, ranging from May 2026 back to early 2026):

- **Pick-next requires re-reading the whole file.** No filter for "items I could do in 30 minutes."
- **Items don't group themselves.** Multiple items about the Critic, the stop hook, sync, methodology — interleaved by arrival time rather than by area.
- **Dedup is manual.** Adding a new item requires scanning 43 entries to avoid restating one already present.
- **Stale items don't surface.** Items from January remain in the same section as items from May with no signal about which is still relevant.
- **Promotion is invisible.** When a chunk fixes a backlog item, the item stays in the file unless someone manually deletes it.
- **Rich items lose value.** Multi-paragraph analyses are valuable (fix-shape, open questions, file paths) but get buried with one-line items.
- **No cross-reference.** When working in area X, finding related backlog items requires text search by guessing.

### Why solve this

Prawduct products accumulate institutional knowledge in their backlogs. A friction-free backlog with good triage is the difference between knowledge compounding (items get picked up, shipped, learned from) and knowledge silting (items live forever as guilt).

The user-facing test: **can someone with 30 free minutes pick a high-value item from the backlog and ship it, without first spending 15 minutes triaging?**

---

## 2. Goals & non-goals

### Goals

1. Adding an item to the backlog is fast and structured enough that subsequent retrieval works.
2. "What should I work on in this spare moment" is answerable in <30 seconds.
3. Related items group themselves through tagging — no manual section maintenance.
4. The system scales gracefully to 200+ items per product.
5. Markdown remains the source of truth (humans read it directly; merge-friendly; version-controlled).
6. Migration of existing items is opt-in, batch-friendly, and never destructive.
7. New projects with their own existing backlog files (TODO.md, BACKLOG.md, ROADMAP.md) can adopt Prawduct without losing prior work.

### Non-goals

1. Not an issue-tracker replacement. Production user-facing bugs belong in real trackers (GitHub Issues, Linear, Jira) — this is internal-development backlog only.
2. Not a project management system. No sprints, no Gantt anything. **(Amended in v0.3 — see D10):** a single optional `accepted-by:` *claim* is allowed — a "don't double-pick this" marker for multi-actor work — but it is NOT PM-style assignment: no assignment workflow, no notifications, no reassignment rules, no auto-expiry. It is a soft, observable claim, nothing more.
3. Not a synchronization target. Backlog stays local to the product repo. No cross-repo aggregation, no central server.
4. Not a productivity-pressure tool. Items aging out is fine and expected — the system surfaces them, it doesn't shame them.

---

## 3. Decisions locked from prior discussion

These were debated and decided; documenting here so the requirements don't re-litigate them.

| # | Decision | Rationale |
|---|---|---|
| D1 | Metadata is soft (Critic NOTE, not BLOCKING) on new items | Add-site friction kills filing; existing items survive without metadata |
| D2 | Grouping is via `area:` tags + tool views, NOT file sections | Sections drift; tags + tools are flexible |
| D3 | `/backlog` is one skill with subcommands (matching `/pr` precedent) | Namespace cleanliness; subcommand discoverability via skill description |
| D4 | Status transitions happen via explicit `/backlog update` calls by agents, NOT by framework inference from build-plan or change-log content | Agent knows what actually shipped; framework can't reliably infer; build-plan declarations of intent are not statements of outcome |
| D5 | Existing free-form items remain valid until explicitly migrated | No forced migration; users adopt structure at their pace |
| D6 | Onboarding never auto-imports external backlog files | Detection-and-advisory; user explicitly invokes `/backlog import` |
| D7 | Item shape: `[PFX-XXXX]` ID (2-3 letter prefix + 4-char random alphanumeric) + one-line metadata bar + free-form body of any length | Random IDs eliminate cross-branch collisions; prefix carries work-space context; body length is author's call (one line to multi-paragraph) |
| D8 | Migration surfaces via post-sync advisories (general infrastructure) | Not behind `prawduct-doctor` — automatic, discoverable, opt-in |
| D9 | Backlog hygiene is a strongly-advised step in build plans (the agent updates affected items based on what actually got shipped) | Agent has full context post-implementation; mechanical scanning of plans/change-logs cannot match that judgment |
| D10 (v0.3) | A single optional `accepted-by: @actor` claim field is allowed; it does **NOT** auto-expire and is **NOT** PM assignment | Multi-actor products (../scriob) double-pick items with no claim signal. A durable claim (an area owner may claim weeks ahead) is legitimate; a stale claim is an out-of-scope process problem. Amends non-goal §2.2. Soft/observable, not a mutex (markdown-in-git is eventually-consistent) |
| D11 (v0.3) | An optional `stage:` field (`idea→research→requirements→design→ready`) places an item in the feature lifecycle; an item with no `stage:` (or an early stage) is treated as **not yet ready to implement** | Closes a requirements-precede-code hole (Principle 6 / work-model): a vague item must route to discovery, not default to code. Proportional — the field is optional, the vocabulary is tiny, and it only changes behavior for early/unspecified items |
| D12 (v0.3) | The backlog gets a real structured parser (`lib/backlog.py`), mirroring `lib/views.py` for the change-log | Every v0.3 capability (claim-filter, stale-detect, dedup, stage-routing, probes) needs to parse items, not regex markdown. The lean core's textual line-count is insufficient |
| D13 (v0.3) | Workflow wiring is **route + flag, not hard-gate** — methodology routes agents to the skill; Critic/PR/probes flag drift at NOTE/WARNING/advisory level; no new blocking gate | Preserves D4 (never infer status — flag, don't auto-update) and S6 (avoid governance fatigue, Principle 11). The lean core left the skill self-serve; v0.3 makes it the documented path without forcing it |
| D14 (v0.3) | **Derived counts/aggregates are NEVER persisted — always re-derived on read.** No backlog count (open/pending/promoted/archived/stale) is written to any file; `lib/backlog.py` returns lists and callers count on demand. Only true *facts that cannot be re-derived* are persisted: the `backlog_last_groomed_at` **timestamp**, `backlog_format_version`, `backlog_external_imports` | Prawduct history: an active-test count stored in ~4 places drifted constantly, ~half of Critic reviews pivoted on one copy being wrong, and large effort went into keeping them in sync. A persisted count is a sync liability with no benefit — the count is cheap to re-derive and useless when stale. Applies to every count-bearing surface: the briefing (`len(pending_items())` live), the skill summary (`N open · N promoted`), the grooming probe (counts at probe-run time), the janitor Backlog Health block. A timestamp is an event marker, not a derivable aggregate, so it is exempt |

---

## 4. User-visible behavior

### 4.1 Item shape

Every new backlog item follows this structure:

```
- **[STH-K7p2]** Stop-hook structural loop counter (defense-in-depth)
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-23 · status: open`

  v1.5.2 (2026-05-23) shipped the discoverability piece: all four blocker stderr messages
  now name `.gates-waived`, the JSON shape, and `build-governance.md`. The structural piece
  is still open. Pathology: even with the escape hatch named in blocker text, an agent can
  ignore it and continue re-firing the same gate. Defense-in-depth fix-shape: track
  stop-hook fire count per session in a new `.prawduct/.stop-fire-count` file...

  **Open questions:** per-blocker counter or session-wide? what counts as "progress"?
```

Required prefix:
- **ID format:** `[PFX-XXXX]` where:
  - `PFX` is a 2-3 letter uppercase prefix indicating the work-space the item lives in (e.g. `STH` for stop-hook, `CRT` for Critic, `SYN` for sync, `LLM` for prompt/LLM concerns, `BKL` for backlog meta, `MIG` for migration, `JNT` for janitor, `MET` for methodology). Prefixes are free-form per project — conventions emerge over time, matching how area tags work. The prefix records *where the work was filed from* and stays stable even if the area later evolves.
  - `XXXX` is a 4-character random alphanumeric (base36 — `[A-Z0-9]` or mixed case). Random IDs eliminate cross-branch collision risk; ~1.7M combinations per prefix is more than any realistic project will exhaust.
- Bold one-line title.

Required metadata line (one line, backticked, dot-separated):
- `effort: S | M | L` — S = <30 min, M = hours, L = multi-chunk
- `impact: S | M | L` — S = cosmetic, M = quality-of-life, L = user-felt or structural
- `area: <tag>` — free-form topic tag; not constrained, but reuse existing tags to enable grouping
- `source: builder | critic | reflection | janitor | user`
- `added: YYYY-MM-DD`
- `status: open | promoted | shipped | dropped`

Optional metadata (extend the same line):
- `related: PFX-XXXX, PFX-XXXX` — explicit cross-references (item → item)
- `closes: PFX-XXXX` — when this item supersedes another (item → item)
- `closed-by: <chunk-id|tag>` — what shipped this item, set on `status=shipped` (item → release)
- `reviewed: YYYY-MM-DD` — last-touched timestamp (auto-set on any update)
- **`accepted-by: @actor` (v0.3)** — soft claim that `@actor` is working this item; `pick`/`list` exclude claimed items. Does **not** auto-expire (D10); cleared by `accepted-by=` (empty) or automatically on `status`→`shipped`/`dropped`. An optional ISO timestamp may follow for information only — it does **not** drive expiry or filtering.
- **`stage: idea | research | requirements | design | ready` (v0.3)** — where the item sits in the feature lifecycle (D11). Absent or early-stage ⇒ **treat as not-yet-implementable**: `pick` routes it to discovery/planning, not building. `ready` ⇒ requirements are clear enough to implement. Bug/cleanup items are typically born `ready`; a vague feature idea is `idea`/`requirements`.
- **`refs: <doc#section>, <doc>` (v0.3)** — links to the governing artifacts (requirements/arch/design docs). Distinct from `related:` (which is item→item).

Body: free-form markdown of any length. May be a single sentence ("BL-trivial: rename `foo` to `_foo`") or multi-paragraph analysis with file refs, fix-shape proposals, open questions, and code blocks. The agent and user choose what fits the item. Brevity is fine; richness is fine; the framework doesn't constrain either.

Legacy items (no metadata) remain valid. Tools treat them as `effort: ? · impact: ? · area: untagged · source: ? · status: open` and rank lower in pick suggestions.

### 4.2 File structure

`.prawduct/backlog.md` keeps three top-level sections:

```markdown
# Backlog — <product>

<!-- top-of-file conventions and source markers -->

## Open
<items here>

## Promoted
<items currently in an active build plan>

## Archive
<shipped and dropped items, kept for searchability>
```

Items move between sections via explicit `/backlog update PFX-XXXX status=...` calls. The framework does NOT auto-promote based on build-plan or change-log content scanning — see §5 for the rationale and how the backlog-hygiene step in build plans handles this in practice.

No `## Active — next up` / `## Queue` distinction — replaced by metadata-driven `/backlog pick` filtering.

### 4.3 The `/backlog` skill

One skill, one SKILL.md, subcommand-dispatched (matching `/pr`).

**No-args behavior:** summary + menu.
```
$ /backlog
47 open · 3 promoted · 28 archived (12 this month)
Top areas: critic (8), stop-hook (5), sync (4)
Stale (>90d unmoved): 6 items

Actions:
  /backlog pick [--budget=Xm] [--type=quick-win|warmup|focus]
  /backlog add
  /backlog find <query>
  /backlog list [--filter=...]
  /backlog migrate
  /backlog import <path>
  /backlog dedup
  /backlog update PFX-XXXX <changes>
```

**Subcommands:**

#### `/backlog pick [filters and free-text constraints]`

Returns 1-3 ranked candidates with rationale.

**The filter case is primary.** Most invocations specify context — area, effort budget, type. Pick accepts:
- Flag form: `--budget=30m --area=sync --type=quick-win`
- Natural-language form: `/backlog pick stop-hook stuff under an hour`, `/backlog pick something I can do in 15 minutes`, `/backlog pick anything LLM-related`, `/backlog pick a warmup task`
- Voice-mode friendly: the skill parses the user's prose into filter constraints

Common filter dimensions:
- Budget: `15m`, `30m`, `1h`, `half-day`, or natural language ("under an hour")
- Type: `quick-win` (high impact / low effort), `warmup` (low-stakes, context-loading), `focus` (larger items requiring uninterrupted attention)
- Area: any tag the project uses

**Heuristic fallback (no context given):** when `/backlog pick` is invoked bare, fall back to `impact_score / effort_score` weighted by recency, with a penalty for `untagged`/legacy items. This is intentionally a simple fallback — most real invocations carry filter context, and the framework should not over-engineer the heuristic before there's data to tune it.

Output shows ID, title, one-line rationale per candidate: "STH-K7p2 — high-impact stop-hook fix, ~2h, would address the open-loop defense-in-depth concern."

#### `/backlog add`

Guided creation. Prompts for title, body, metadata (one-shot interactive or argument-driven). Before writing:
1. Searches existing items by title-keyword overlap and `area` similarity.
2. Surfaces top 3 similar items if any exist: "Possibly related: BL-012, BL-038. Continue, update an existing item, or cancel?"
3. On confirm, assigns next `PFX-XXXX`, writes to `## Open`, appends to file.

Argument-driven form for use from other skills (Critic, reflection): `/backlog add --area=critic --source=critic --effort=S --impact=S --title="..." --body="..."`. No interactivity when arguments complete.

#### `/backlog find <query>`

Plaintext substring + tag search across title + metadata + body. Returns matching IDs, titles, one-line summaries.

#### `/backlog list [--filter=...]`

Tabular view. **Default filter: `status=open AND added_within=90d`** to avoid dumping all 200 items on first call. `--all` to override. Filterable on every metadata field.

#### `/backlog update PFX-XXXX <field=value> [...]`

Updates metadata or body. Common cases: `status=promoted`, `effort=L`, `area=...`, `reviewed=2026-05-27`. Updates `reviewed` automatically on any touch.

#### `/backlog migrate`

Walks legacy items (those lacking metadata), batches them ~10 at a time, asks user to fill effort/impact/area for each. Optional — items can stay legacy indefinitely.

#### `/backlog import <path>`

Imports an external file (`TODO.md`, `BACKLOG.md`, etc.). Heuristically converts each bullet/list item into a `[PFX-XXXX]` entry with status `open`, source `user`, area inferred where possible. Always asks for confirmation before writing.

#### `/backlog dedup`

Janitor-adjacent — groups items by area, surfaces likely duplicates (title similarity + body keyword overlap), proposes merges. User confirms each merge. Idempotent.

### 4.4 Behavior in other surfaces

- **Critic add-time:** when the Critic files an item (NOTE-level), it emits the structured form with metadata already filled.
- **Reflection capture:** when reflection produces a backlog item, the capture template prompts for the metadata one-line inline.
- **Janitor:** existing janitor flow gains an explicit "backlog triage" step (see §6).
- **Build-plan chunks:** plans should include a **backlog-hygiene step** (see §5.3) at chunk close. The agent assesses what actually shipped versus what was intended and makes explicit `/backlog update` calls for each affected item.
- **Change-log entries:** release prep includes its own backlog-hygiene pass — the agent reviews what shipped in the release and updates affected items.

---

## 5. Lifecycle & backlog hygiene

### 5.1 States and the explicit-update contract

```
       /backlog add
       (or critic /         /backlog update           /backlog update
        reflection /          status=promoted           status=shipped
        agent)
  ──────► open ─────────────────────► promoted ──────────────────────► archived (shipped)
              │                            │
              │ /backlog update            │ /backlog update
              │ status=dropped             │ status=dropped (rare)
              ▼                            ▼
        archived (dropped)
```

**All status transitions happen via explicit `/backlog update` calls — by a human, by an agent, or by a skill acting on behalf of either.** The framework does NOT scan build-plan content, chunk titles, or change-log entries to infer status changes.

Why: a build-plan chunk declaring `Closes STH-K7p2` is a statement of *intent*, not *outcome*. The implementation may close the item fully, partly close it, take a different approach that leaves the original item still relevant, or close it as a side effect while not naming it in the plan at all. Only the agent that just built the chunk has the full context to judge — and that context exists at chunk-close time, not at plan-authoring time.

### 5.2 The agent's judgment at chunk close

After a chunk's acceptance criteria pass and the Critic runs, the agent (in its backlog-hygiene step — §5.3) reviews open items that are plausibly affected and decides for each:

- **Did this chunk fully close the item?** → `/backlog update PFX-XXXX status=shipped` (with reference to the change-log entry / chunk ID).
- **Did this chunk partly address it?** → leave `status: open`, optionally update body with current state ("Chunk Y addressed the discoverability half; the structural half is still open"). Or split: archive the original and file a narrower follow-up.
- **Was this item touched but not really progressed?** → leave open as-is.
- **Is this item now obsolete because the chunk took a different approach?** → `/backlog update PFX-XXXX status=dropped reason=...`.

The agent owns this call. The framework doesn't second-guess.

### 5.3 The backlog-hygiene step in build plans

Build plans **strongly should** include a backlog-hygiene step as part of each chunk's Done-when (or equivalent close-out section). The methodology and template guidance call this out — but the step is advisory, not structurally enforced. A chunk that omits it is not blocked, but its author has accepted that affected backlog items will lag reality until someone else does the update.

Recommended step content (template-level guidance):

> **Backlog hygiene.** Before marking this chunk done, review open backlog items whose `area:` overlaps this chunk's scope. For each that this work plausibly affects, decide: shipped (close it), partly addressed (note + leave open), unaffected (leave alone), or obsolete (drop). Make the updates via `/backlog update`.

Janitor and Critic provide safety nets (§6, §7) — they surface neglected hygiene, but they don't substitute for it.

### 5.4 Promotion (open → promoted)

Explicit: `/backlog update PFX-XXXX status=promoted`. Typically called by an agent when starting work on an item — e.g., when a chunk in an active build plan is going to address it.

Why this matters: `/backlog pick` filters out `promoted` items by default to avoid suggesting work that's already in flight.

### 5.5 Shipping (promoted → archived)

Explicit: `/backlog update PFX-XXXX status=shipped [closed-by=<ref>]`. Typically called by the agent during its backlog-hygiene step at chunk close, or during release prep.

On ship: item moves to `## Archive`, `status: shipped`, retains body for later search. The optional `closed-by` field records the change-log tag or chunk ID for traceability.

### 5.6 Dropping (any → archived)

Explicit: `/backlog update PFX-XXXX status=dropped [reason=<text>]`. Item moves to archive with rationale preserved.

### 5.7 What never happens automatically

- Items are never deleted, only archived. Searchability of past decisions matters.
- Status changes never come from framework inference — no scanning of plans, change-logs, or commit messages.
- The framework does not pattern-match on `Closes PFX-XXXX` text in code, plans, or any other artifact. References to backlog IDs in those places are documentation, not instructions to the framework.

---

## 5a. Lifecycle stage & requirements-precede-code routing (v0.3 — D11)

The keystone of v0.3. A backlog item is often a *requirement-shaped thing at an unknown stage of clarity*. Today an agent that picks *"stories need genre indicators and conventions"* defaults to writing code — bypassing the requirements-precede-code governance (Principle 6) the framework otherwise enforces. The `stage:` field makes the item's clarity explicit and **changes the default**.

**Stage vocabulary** (ordered; an item enters at whatever stage fits and may skip stages):
- `idea` — a one-line spark; problem/success/scope all unstated.
- `research` — problem understood; needs investigation (prior art, volatility, options) before requirements.
- `requirements` — being scoped; problem/success/scope are being written down.
- `design` — requirements clear; architecture/detailed-design pending.
- `ready` — requirements and any needed design are clear enough to implement. **Only `ready` items are implementable.**

**Routing behavior in `/backlog pick`:**
- An item with `stage: ready` (or a bug/cleanup item, which is born ready) → pick presents it as buildable; normal build cycle.
- An item with `stage: idea|research|requirements|design` → pick surfaces the stage and **routes the next action to the matching guide** (`idea`/`research`/`requirements` → `/prawduct:discovery`; `design` → `/prawduct:planning`), framed as *"this item needs <stage> work next, not implementation."* Advancing the stage is itself the work; the agent updates `stage:` via `/backlog update` as the item matures (and adds a `refs:` link to the requirements/arch doc once written).
- **An item with NO `stage:` is treated as not-yet-`ready`** — pick does not present it as directly buildable; it prompts the picker to assess clarity first (fail toward requirements, not toward code). This is the safe default and the behavioral fix for the observed failure.

This is proportional (D11): the field is optional, the vocabulary is five words, and it only diverts behavior for early/unspecified items — a `ready` cleanup item is unaffected. It ties the backlog into the work-model nudge: a vague item is an undocumented requirement, and the framework now routes it to where requirements get written.

## 5b. Archive discipline & strikeout cleanup (v0.3)

"Done" has exactly one representation: `status=shipped` (or `dropped`) **and the item moved to `## Archive`** via `/backlog update`. Three things are explicitly wrong and the skill/methodology say so: (1) **strikethrough** (`~~…~~`) to mark done — it leaves the item inline in `## Open` growing the file's token cost while the briefing's count silently ignores it; (2) leaving a shipped item in `## Open`/`## Promoted`; (3) deleting an item outright (archive preserves searchability — unchanged from v0.2 §5.7). A one-shot **cleanup sweep** (part of `/backlog migrate` and janitor Step 2.5) converts existing strikethrough/done-marked items in `## Open` into proper `status=shipped` archived items, preserving their bodies. Archive growth past the threshold splits to `backlog-archive.md` (§6, the Q2 decision).

## 6. Janitor integration

The existing `/janitor` flow already mentions backlog triage in passing ("triage `.prawduct/backlog.md`"). This requirement formalizes it as **Step 2.5: Backlog Triage**, between Survey and Reconcile.

Step contents:

1. **Group by `area:`** — for each tag with >2 items, produce a section in the janitor's findings report.
2. **Surface dedup candidates** — title similarity + body overlap → suggested merges (operator confirms).
3. **Flag stale items** — `status: open` AND `reviewed > 90d` (or `added > 90d` if never reviewed). Janitor proposes one of: re-confirm relevance (touch `reviewed`), update with current context, drop.
4. **Surface neglected hygiene** — items in `## Promoted` whose owning chunk shipped (per change-log timestamps and `closed-by` traces on adjacent items) but status was never updated. Surface as "should this be shipped, or did the chunk take a different approach?" The agent then decides per §5.2.
5. **Surface unstructured items** — count legacy items, propose `/backlog migrate` if many.

Output: a `Backlog Health` block in the janitor's findings report. Triage actions become part of the janitor's build plan.

---

## 7. Critic interaction

The Critic gains a small, soft-gated set of checks (NOTE-level only — never BLOCKING):

- **C-B1: Missing metadata on a new backlog item** — if a new item appears in the diff without metadata, NOTE with the suggested format.
- **C-B2: No dedup search evidence on a new item** — if a new item appears and its area has ≥3 existing items, NOTE: "Consider checking [PFX-W, PFX-X, PFX-Y] for overlap before filing this." (Detection: area tag matches existing items; not enforcing actual search.)
- **C-B3: Missing backlog-hygiene step at chunk close** — if a chunk's diff appears to touch areas with open backlog items but the chunk's Done-when has no backlog-hygiene step (or equivalent), NOTE: "Open items in this area exist — consider whether any are affected and update status before closing the chunk."
- **C-B4: Reference to an ID that does not exist** — if a build plan, change-log entry, or chunk body mentions `PFX-XXXX` and no such ID exists in the backlog, NOTE (not BLOCKING — could be a typo, or could be a forward reference to an item that will be filed later).

The Critic does not run any backlog-specific reasoning beyond inspecting the diff and the backlog for these four signals. It does not adjudicate whether a chunk's implementation "really" closed an item — that judgment belongs to the agent doing the hygiene step (§5.2).

## 7a. PR-reviewer backlog reconciliation (v0.3)

The v0.2 design put reconciliation only in the Critic (per-chunk / cumulative). v0.3 adds it at the **PR boundary** — the natural "a branch's worth of finished work is about to merge; were the items it closed updated?" checkpoint, where the reviewer already reads the full `merge-base...HEAD` diff, the build plan, and the change-log. Two checks, both respecting D4 (flag, never infer/auto-update):

- **R-1 (resolution candidate):** for each `## Open`/`## Promoted` item whose `area:` overlaps the branch's changed files, NOTE: *"branch work appears to resolve `[PFX-XXXX]` — verify and `/backlog update status=shipped`, or explain why it stays open."*
- **R-2 (reference disagreement, WARNING):** if a change-log entry or commit on the branch references `closes: PFX-XXXX` / `closed-by:` but that item is still `status=open`, WARNING — this is a pure *data inconsistency* (the change-log and backlog disagree), not an inferred status, so flagging it does not violate D4.

The PR reviewer never writes the backlog; it surfaces the gap for the agent's explicit call.

---

## 8. Migration & onboarding

### 8.1 Post-sync advisory mechanism — shared infrastructure

This feature uses the shared post-sync advisory infrastructure specified in `documentation/post-sync-advisory-spec.md`. Concretely:

- **Storage**: `.prawduct/.advisories.json` (gitignored, per-clone — the "nag log") plus resolution-condition facts in `.prawduct/project-state.yaml` (committed, shared — the "answer store"). See advisory-spec §3.5.
- **Lifecycle**: probe triggers + resolution conditions + idempotent re-runs across syncs. See advisory-spec §4.
- **Session-briefing format**: groups advisories by feature; this feature's entries appear under `[backlog]`. See advisory-spec §5.
- **Probe versioning + supersession**: handled by the infrastructure when this feature refines its probes. See advisory-spec §3.2 (`probe_version`) and Q1.

The backlog feature does NOT define its own advisory storage, lifecycle, or CLI — it implements probes against the advisory-spec API and reuses the shared mechanism.

### 8.2 Backlog-specific probes

These probes register against the shared infrastructure (advisory-spec §7) and produce advisories under `feature: "backlog"`:

| Probe `type` | Trigger condition | Resolution condition (project-state.yaml) | Recommended action |
|---|---|---|---|
| `legacy-backlog-format` | `.prawduct/backlog.md` exists with >5 items, none carrying `[PFX-XXXX]` ids | `backlog_format_version: 2` (or whatever value indicates migration complete) | `/backlog migrate` |
| `external-backlog-detected` | Foreign file in repo root or `.github/`: `TODO.md`, `BACKLOG.md`, `ROADMAP.md`, `IDEAS.md` | Either the file is gone OR `backlog_external_imports: [...]` records it as audited | `/backlog import <path>` |
| `legacy-section-schema` | `## Active — next up` / `## Queue` headings present in `.prawduct/backlog.md` (older schema convention) | Sections converted; resolution recorded as part of `backlog_format_version` | `/backlog migrate --sections` |
| `backlog-overdue-grooming` | No `/backlog` command run in >90 days AND backlog has >20 open items | A `/backlog list` or `/backlog pick` invocation updates `backlog_last_groomed_at` in project-state | `/backlog list` |

**Trigger thresholds** (e.g., >5 items, >20 items, 90 days) are documented here as the v1 starting point. The build plan tunes them against real projects before ship.

**Dismissal** is the per-feature alias for the unified command:
- `/backlog dismiss-advisory <id>` → delegates to `/prawduct-advisory dismiss <id>`, scoped to `feature: "backlog"` (errors if the id belongs to a different feature).
- Power users can use `/prawduct-advisory dismiss <id>` directly.

See advisory-spec §6 for the full CLI surface.

### 8.3 New-project onboarding

On `prawduct-doctor` initial setup:
- Detects candidate external backlog files in repo root and `.github/`.
- Reports them in the doctor's setup output as candidates.
- Does NOT auto-import. User invokes `/backlog import <path>` explicitly.
- Fresh `.prawduct/backlog.md` is always created from the place-once template (already happens).

### 8.4 Migration command behavior in detail

`/backlog migrate`:
1. Reads existing `.prawduct/backlog.md`.
2. Identifies items lacking the metadata line.
3. Batches them in groups of ~10.
4. For each batch, presents:
   - Item title + first 2 lines of body
   - Inferred metadata from context (source tag from existing parenthetical markers, area inferred from title keywords)
   - Effort/impact left as `?` if not inferable
5. User accepts batch (with optional inline edits) → tool writes metadata, assigns `PFX-XXXX` if missing.
6. Idempotent — re-runnable; only touches unstructured items.

`/backlog import <path>`:
1. Reads the source file.
2. Identifies items by structure (markdown bullets, headings, GitHub issue template fields, etc.).
3. For each, drafts a `[PFX-XXXX]` entry with `source: user`, `status: open`, inferred area.
4. Shows preview, user confirms or edits, tool writes.
5. Optionally creates a `## Imported from <path> on <date>` comment block at the top of the appended section for traceability.

---

## 9. Success criteria

The feature is successful if:

| # | Criterion | How measured |
|---|---|---|
| S1 | Picking next-work in any product takes <30 sec | Time `/backlog pick` end-to-end on the flagship product |
| S2 | New items get metadata 80%+ of the time within first month | Tag the cohort of items added post-feature; sample |
| S3 | Janitor's backlog-health output is actionable (≥1 dedup/stale finding per run on a typical product) | Run janitor on flagship product and on one onboarded product; count actionable findings |
| S4 | Migration of 50 legacy items completes in <30 min user time | Time the flagship product's migration |
| S5 | `/backlog find` returns relevant items for a topic query in <3 results | Sample 5 topic queries; measure precision |
| S6 | Critic's backlog NOTEs don't trigger user fatigue (no complaints, no waiver requests) | Watch first 4 weeks post-launch; track waiver count |
| S7 | Backlog-hygiene step happens at chunk close on most chunks that touch open items | Audit first 20 chunks across flagship + onboarded projects; confirm hygiene step ran |

---

## 10. Open questions

Decision-grade questions that are not yet locked. These need user input before build-plan work begins.

### Q1: Prefix vocabulary — emergent vs. project-declared

Prefixes (`STH`, `CRT`, `LLM`, etc.) are free-form per project. Should the framework provide a starter list as suggestions in the skill prompt, or stay fully emergent? And should the project optionally declare its prefix vocabulary in `project-state.yaml` so the skill can validate / autocomplete?

Lean: ship a starter list as informational examples in the skill prompt; do not require declaration. Allow projects to declare a vocabulary in `project-state.yaml` if they want validation; the framework treats it as optional.

### Q2: Archive growth

After 2 years of a busy product, `## Archive` could have thousands of entries. Does it stay in `backlog.md` or split to `backlog-archive.md`?

Lean: split when archive exceeds some threshold (e.g., 200 entries), via janitor action. Search still spans both files.

### Q3: Natural-language `/backlog pick` parsing — robustness ceiling

The skill parses prose like "stop-hook stuff under an hour" into filter constraints. Where's the parsing complexity ceiling — i.e., what kinds of queries does the framework promise to handle versus what it just punts on?

Lean: handle (area + budget + type) combinations expressed in prose; punt on more complex constraints by surfacing the parsed filter back and asking confirmation ("I read this as: area=stop-hook, budget=1h. Continue, or refine?"). The skill prompt's examples define the supported surface.

### Q4: Cross-area discovery

"Related items" via `related:` field is explicit. Should there also be implicit related-item suggestions (semantic similarity of body)?

Lean: not in v1. Tag-based grouping is enough; semantic search would need an embedding pipeline that's overkill for a backlog tool.

### Q5: Skill prompt budget

The `/backlog` SKILL.md will be long (subcommands, examples, format spec, ranking heuristic). Skill prompts cost tokens. Is the right architecture:
- **(a)** One large SKILL.md with all subcommand docs inline
- **(b)** A thin SKILL.md that dispatches to per-subcommand modules

Lean: (a) for v1 — single source of truth. Revisit if the skill exceeds ~10K tokens.

### Q6: How does `/backlog pick` interact with a user who already has a build plan in progress?

If the user invokes `/backlog pick` mid-build, should it warn/refuse, or suggest items that complement the active work?

Lean: warn ("active build plan in progress — pick will suggest standalone items, not extensions to current work") and proceed.

### Q7: External backlog detection scope

For onboarding, do we scan deeper than repo root? `.github/ISSUE_TEMPLATE/`? `docs/`? Subdirectories named `backlog/`?

Lean: repo root + `.github/` only for v1. Subdirectory backlogs are unusual; user can explicitly import.

---

## 11. Out of scope (deferred)

Items considered and explicitly deferred:

- **Semantic-similarity search.** Embeddings + vector search would be powerful but heavy. Tag-based + plaintext is sufficient.
- **Cross-product backlog aggregation.** "What's open across all my Prawduct products?" — interesting but premature.
- **GitHub Issues sync.** Two-way sync to GH Issues is a separate, larger feature.
- **Effort/impact auto-estimation.** Could in principle infer from history; not worth the complexity for v1.
- **`/backlog graph` visualization.** Topic clusters, age distribution, etc. Cool, not essential.
- **Per-user assignment.** Out of scope (non-goal §2).
- **Backlog item templates.** Could enforce body sections (fix-shape, open questions). Decided against — preserves richness of current items.

---

## 12. Dependencies on other in-flight work

- **Post-sync advisory infrastructure** is specified at `documentation/post-sync-advisory-spec.md` (v0.2). Per its §13 build order, the advisory infrastructure ships in Phase 1 (no-op release with empty probe roster); this backlog feature ships in Phase 2 and registers its four probes (§8.2) against the existing infrastructure. The backlog feature does NOT need to build advisory storage, lifecycle, or CLI — those are shared.
- **`project-state.yaml` schema extension** — the backlog feature adds resolution-condition fields: `backlog_format_version: int`, `backlog_external_imports: list`, `backlog_last_groomed_at: ISO-8601`. Per advisory-spec §3.5, this committed file is the shared answer store; teammates' actions writing these fields auto-resolve advisories for everyone on next sync.
- **Build-plan template guidance** for the backlog-hygiene step — small update to `templates/build-plan.md` and methodology prose recommending the step. No structural enforcement; documentation only.
- **`lib/backlog.py` parser substrate (v0.3 — D12)** — new module mirroring `lib/views.py` (the change-log parser). Parses items (ID, metadata bar including the new `accepted-by`/`stage`/`refs` keys, the three sections, body), tolerant of legacy/unstructured items. Consumed by `lib/briefing.py` (replacing the textual line-count), the new probes, and the `/backlog` skill's read paths. No new committed project-state facts beyond v0.2's `backlog_format_version` / `backlog_external_imports` / `backlog_last_groomed_at` — the claim/stage/refs data lives in the item metadata bar, not the answer store.

---

## Appendix A: Example interaction transcripts

### A.1 Pick during a meeting break

```
$ /backlog pick stop-hook stuff under an hour
Parsed: area=stop-hook, budget=1h
2 candidates:

  [BLP-9aXm] Backfill Done-when blocks on Chunks 05-14 of v1.4 build plan
    effort: S · impact: S · area: build-plan
    Why: trivial cleanup, no risk, completes a documented inconsistency.

  [SYN-2kQp] Remove dead `if rel_path in ("CLAUDE.md",)` lines in sync_cmd.py
    effort: S · impact: S · area: sync
    Why: 2-line cleanup, flagged by Critic 19 days ago, no dependencies.

  [SYN-7Wfn] Fix inline-comment asymmetry in enable_v1_4_views
    effort: S · impact: M · area: sync
    Why: silent no-op bug; tiny fix; pairs with a learning from Chunk 10.
```

### A.2 Adding a new item from reflection

```
$ /backlog add --source=reflection --area=stop-hook --effort=M --impact=M \
    --prefix=STH \
    --title="Stop-hook structural loop counter (defense-in-depth)" \
    --body-file=/tmp/reflection-snippet.md

Searching for related items in `stop-hook` area...
Possibly related:
  [STH-K7p2] (already exists) — Stop-hook structural loop-detection counter
    Status: open, added 2026-05-23

Continue, update [STH-K7p2], or cancel?
> update
Opening [STH-K7p2] for edit. Current body:
  v1.5.2 (2026-05-23) shipped the discoverability piece...
[editor]
```

### A.3 Backlog-hygiene step at chunk close

```
$ # Agent invokes after chunk acceptance + Critic pass:
$ /backlog list --filter=area:stop-hook status:open
4 open items in area=stop-hook:
  [STH-K7p2] Stop-hook structural loop counter (defense-in-depth)
  [STH-M3Qx] Waiver-counter telemetry surface
  [STH-9bWp] Refactor gate-3 stderr emission
  [STH-2nFk] (legacy, no metadata) revisit fire-count cap

# Agent reviews chunk diff, judges each:
$ /backlog update STH-K7p2 status=shipped closed-by=v1.5.3-chunk-04
$ /backlog update STH-M3Qx body-append="Chunk 04 added counter writes; reporting surface still pending."
# STH-9bWp untouched — not affected by this chunk
# STH-2nFk untouched — pre-existing legacy item, not in chunk scope
```

### A.4 Migration walkthrough

```
$ /backlog migrate
47 unstructured items detected. Migrating in batches of 10.

Batch 1 of 5:
─────────────────────────────────────────────────────────
[1] Stop-hook structural loop-detection counter — v1.5.2 (2026-05-23)...
    Inferred: source=reflection · area=stop-hook · added=2026-05-23
    Suggested prefix: STH (stop-hook). Generated ID: STH-K7p2
    Effort: ? · Impact: ?
    Enter values [SML/SML or 'skip']: M M

[2] `scope: null` in build-plan frontmatter does not suppress change-log...
    Inferred: source=critic · area=sync · added=2026-05-23
    Suggested prefix: SYN. Generated ID: SYN-9bX4
    Effort: ? · Impact: ?
    Enter values: S M
[...continues...]

Apply batch? [y/N]: y
✓ Wrote 10 items. 37 remaining. Continue? [y/N]:
```
