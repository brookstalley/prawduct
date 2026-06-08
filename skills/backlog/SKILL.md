---
description: Manage the structured product backlog — pick what to work on next, add/find/list/update items, and migrate legacy items. Use when the user wants to triage, file, or choose backlog work, or says /prawduct:backlog.
argument-hint: "[pick|add|find|list|update|migrate] ... (e.g. `pick stop-hook stuff under an hour`, `add`, `find sync`, `list --area=critic`, `update STH-K7p2 status=promoted`)"
user-invocable: true
disable-model-invocation: false
context: fork
allowed-tools: Read, Edit, Write, Grep, Glob
---

You manage `.prawduct/backlog.md` — the product's structured backlog. You run in a forked context, so the full backlog never pollutes the main session. Read the file, do the operation, write it back, and return a concise result. **Never** delete items (archive instead) and **never** weaken existing content.

## The format you operate on

Each item:

```
- **[PFX-XXXX]** One-line title
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-29 · status: open`

  Optional free-form body (any length).
```

- **ID** `[PFX-XXXX]`: `PFX` = 2–3 uppercase letters naming the work-space, *derived from the item's area* — reuse an existing prefix when one fits so related items share it. Starter set (extend freely): `STH` stop-hook, `CRT` critic, `SYN` sync, `LLM` prompt/LLM, `BKL` backlog, `MIG` migration, `JNT` janitor, `MET` methodology, `DOC` docs, `TST` tests. If `backlog_prefixes:` is declared in `project-state.yaml`, prefer those. `XXXX` = 4 random base36 chars (`A–Z`,`0–9`); generate fresh and confirm it doesn't collide with an existing ID in the file.
- **Metadata bar**: one backticked dot-separated line. Required fields: `effort` (S/M/L), `impact` (S/M/L), `area`, `source` (builder|critic|reflection|janitor|user), `added` (YYYY-MM-DD), `status` (open|promoted|shipped|dropped). Optional: `related:` (related items), `closes:` (another backlog item this one supersedes — item→item), `closed-by:` (the chunk/release that shipped this item — item→release), `reviewed:`, `accepted-by:` (a soft claim — see below). Keep `closes:` and `closed-by:` straight — they point in opposite directions.
- **`accepted-by:` claim** — `accepted-by: @actor` marks that someone is working an item so others don't double-pick it (multi-actor products). It is a *soft, observable claim*, **not** a lock: backlog.md is eventually-consistent in git (two actors in separate worktrees won't see each other's claim until commit+pull), so it makes double-picks **visible and recoverable**, not impossible. It **does not auto-expire** — a durable claim (an area owner claiming weeks ahead) is legitimate; a stale claim is an out-of-scope process matter, not something the framework reaps. `pick` and `list` exclude claimed items by default.
- **`stage:` lifecycle** — `stage: idea | research | requirements | design | ready` records where the item sits in the feature lifecycle, so the framework can tell "this needs thinking" from "this is buildable." **Only `ready` is implementable.** An item with **no `stage:`** is treated as *not yet ready* — clarity has to be assessed before code. Bug/cleanup items are typically born `ready`; a vague feature idea is `idea`/`requirements`. `pick` uses this to route (see below). Advance an item with `update PFX-XXXX stage=...` as it matures.
- **`refs:` doc links** — `refs: requirements-x.md#section, arch-y.md` links an item to the governing artifacts (requirements / arch / design docs). Distinct from `related:` (item→item). Set it when an item's requirement/design gets written (often as a `stage:` advances), so triage can cluster items around the docs they touch and a reader can jump to the source of truth.
- **Sections**: `## Open` (pickable), `## Promoted` (in an active build plan), `## Archive` (shipped/dropped, kept for search). Items move between sections only via explicit `update` calls — never infer status from build plans or change logs.
- **Legacy items** (no metadata bar) are valid; treat them as `effort:? · impact:? · area:untagged · status:open` and rank them lower. Suggest `/prawduct:backlog migrate` if there are many.

For today's date when stamping `added:`/`reviewed:`, use the current date from your environment context.

## Subcommands

Parse `$ARGUMENTS`: the first token is the subcommand (default to the no-arg summary if empty). Everything after is arguments — accept both `--flag=value` form (for machine callers like the Critic or reflection) and natural-language prose (for humans).

### (no args) — summary + menu
Read the file, then print: counts per section (`N open · N promoted · N archived`), the top 3 `area:` tags by item count, a count of stale items (`status: open` and `added`/`reviewed` >90 days ago), and the action menu (`pick`, `add`, `find`, `list`, `update`, `dedup`, `migrate`). All counts are **derived on read** — never persist a count to any file (a stored count drifts and becomes a sync liability; re-deriving is cheap).

### add
File a new item. Accepts flags (`--title=`, `--body=`/`--body-file=`, `--area=`, `--effort=`, `--impact=`, `--source=`, `--prefix=`) or interactive prompts for anything missing.
1. **Dedup first.** Search existing items whose `area:` matches or whose title keywords overlap. If any exist, show the top ~3 (`[ID] title — status, added`) and ask: continue, update one of them, or cancel. (When called with complete flags by a machine caller, skip the prompt but still note overlaps in your result.)
2. On confirm, derive a prefix, generate a non-colliding `[PFX-XXXX]`, build the metadata bar (`source` defaults to the caller; `added` = today; `status: open`), and append the item under `## Open`.
3. Return the new ID and a one-line confirmation.

### find <query>
Plaintext + tag search across title, metadata, and body of **all** sections (and `backlog-archive.md` if it exists). Return matching `[ID] title — one-line summary`, most-relevant first. Keep it tight (a handful of results).

### list [--filter=...]
Tabular view: `ID · title · effort · impact · area · status`. **Default filter: `status=open` AND `added` within 90 days** (so a 200-item backlog doesn't dump). `--all` overrides; filter on any metadata field (`--area=`, `--status=`, `--effort=`, etc.). Sort by status then recency. **Claimed items** (non-empty `accepted-by:`) are excluded by default; show them with `--include-claimed`, and when shown, display the claim holder in the row.

### update PFX-XXXX <field=value> [...]
Change metadata or body of one item. Common: `status=promoted|shipped|dropped` (moves the item to the matching section — `promoted`→`## Promoted`, `shipped`/`dropped`→`## Archive`), `area=`, `effort=`, `reviewed=`. On `status=shipped`, accept an optional `closed-by=<change-log tag or chunk id>` and write it into the **metadata bar** as `closed-by: <ref>` (not the body) for traceability. Always set `reviewed:` to today on any touch. Confirm the item exists first; if the ID isn't found, say so and suggest `/prawduct:backlog find`.

**Claims (`accepted-by`):** `update PFX-XXXX accepted-by=@actor` records a claim; `accepted-by=` (empty value) clears it. When you set `status=shipped` or `status=dropped`, **auto-clear** `accepted-by` (a finished item is not claimed) — the work is over, the claim is moot. Never auto-clear on any other transition (a `promoted` or still-`open` item may legitimately stay claimed). Do not touch a claim you didn't set unless the user explicitly asks — reassignment is a human call, not the skill's.

### pick [filters / free-text]
Return **1–3 ranked candidates** with a one-line rationale each — the answer to "what should I work on right now?" Most invocations carry context; the bare call is the fallback.

**Parse the request (you are the parser — no rigid grammar).** Map the user's words to three optional filters:
- **area** — any tag the project uses (`sync`, `critic`, `stop-hook`, …).
- **budget** — how much time, mapped to `effort`: `15m`/`30m`/`under an hour`/`quick` → prefer `S`; `a couple hours`/`this afternoon` → `S`–`M`; `half-day`/`big` → up to `L`.
- **type** — `quick-win` (high `impact`, low `effort`), `warmup` (low-stakes, context-loading — small/legacy/cleanup items), `focus` (larger items, `effort: L`, needs uninterrupted attention).

Accept flag form for machine callers (`--area=sync --budget=30m --type=quick-win`) and prose for humans (`pick stop-hook stuff under an hour`, `something I can do in 15 minutes`, `a warmup task`, `anything sync-related`).

**Confirm-back ceiling (Q3).** If the query carries constraints beyond area/budget/type, or your interpretation is uncertain, echo the filter you parsed and ask before running — e.g. *"I read this as: area=stop-hook, budget≈1h. Continue, or refine?"* Don't silently guess on ambiguous input.

**Ranking.**
1. **Exclude** `status: promoted` (already in flight), archived items, and **claimed items** (non-empty `accepted-by:` — someone else is on it) by default.
2. **Apply** the parsed filters as the candidate pool. If filters empty too small a pool, widen and say so.
3. **Score** each candidate: `impact / effort` (map `S=1, M=2, L=3`; missing → treat as `2`, i.e. unknown-middle), nudged up by recency (newer `added`/`reviewed` ranks slightly higher) and **down** for untagged/legacy items (no metadata bar). This is a deliberately simple heuristic — don't over-engineer it before there's usage data to tune it.
4. **Return** the top 1–3 as `[ID] title` + a one-line *why* (e.g. *"high-impact sync fix, ~2h, no dependencies"*).

**Build-plan-aware (Q6) — the primary mid-work case.** Before ranking, read `active_build_plan` from `.prawduct/project-state.yaml`. If it points to a plan, read that plan and infer its scope/area focus (its `scope:` tag, chunk areas, the files it touches). Then **prioritize open items whose `area:` or subject overlaps the active plan**, framed as *"related to what you're working on"* — knocking out an adjacent item while the context is loaded is the highest-value pick. Show overlapping candidates first; if fewer than the requested count, fill from the general ranking. `--standalone` disables this and deliberately suggests context-switch work instead. If no plan is active, skip straight to the general ranking.

**Stage-aware routing (the requirements-precede-code guard).** Before presenting any candidate as buildable, read its `stage:`. This is what stops the backlog from being a side-door around Principle 6 (a vague item like *"stories need genre indicators and conventions"* is an undocumented requirement, not a coding task):
- `stage: ready` (and bug/cleanup items, which are born ready) → present as buildable; proceed to the normal build cycle.
- `stage: idea | research | requirements` → **do not present as buildable.** Surface it framed as *"this needs <stage> work next"* and route to **`/prawduct:discovery`** — advancing the stage (writing the requirement, doing the research) *is* the work. The agent updates `stage:` (and adds a `refs:` link to the doc it produces) via `update` as the item matures.
- `stage: design` → route to **`/prawduct:planning`** (requirements clear; architecture/detailed design pending).
- **No `stage:`** → treat as *not yet ready*: don't present it as directly buildable; prompt to assess clarity first (fail toward requirements, not toward code). This is the safe default for the large existing backlog whose items predate the field.

This routing is advisory, not a hard gate — surface the stage and the recommended next step; the user may still choose to override. Don't silently let an early-stage item flow into implementation.

**Worked examples** (parsed filter → behavior):
- `pick stop-hook stuff under an hour` → `{area: stop-hook, budget: S–M}` → open stop-hook items, effort S/M, top 2–3 by score.
- `pick a warmup task` → `{type: warmup}` → small/legacy/cleanup items, low stakes, recency-weighted.
- `pick` (bare, plan active) → no filters → build-plan-overlapping open items first, then general `impact/effort` ranking.
- `pick something quick and high-impact` → `{type: quick-win}` → high-impact + low-effort items.

### migrate
Convert legacy unstructured items to the structured format and fold the old sections into Open/Promoted/Archive. **Idempotent** (only touches items lacking a metadata bar) and **never destructive** (bodies are preserved verbatim; items are never deleted). Run it when a repo carries unstructured legacy items (the `pick`/list views flag these). (The `legacy-backlog-format` post-sync advisory that used to nudge this was retired with the file-sync engine in M4; re-adding it as a plugin-native probe is tracked in the backlog.)

1. Read `.prawduct/backlog.md`. Identify legacy items — top-level bullets with no `effort: … · status: …` metadata bar. If there are none, report "already migrated" and stop.
2. Walk them in **batches of ~10**. For each item show its title + first ~2 lines of body and your **inferred metadata**:
   - `source` from existing parenthetical markers (`(critic)`/`(reflection)`/`(builder)`/`(migrated)` → the matching source; else `user`).
   - `area` inferred from title/body keywords; reuse tags already present in the file.
   - a derived `[PFX-XXXX]` id (prefix from the area; fresh non-colliding suffix).
   - `effort`/`impact` left as `?` when not inferable — don't invent them.
   Present the batch and let the user accept as-is, edit inline (e.g. supply `effort impact`), or skip individual items. When run non-interactively, apply your inferences and report what you assumed.
3. On accept, rewrite each item to the structured shape (id + metadata bar + original body unchanged), placing it in the section matching its `status` (default `open`).
4. **Fold sections**: map legacy headings onto the canonical three — `## Active — next up` and `## Queue` → `## Open` (use judgment if "Active" items were truly in-flight → `## Promoted`); preserve any already-`[RESOLVED]`/shipped items by moving them to `## Archive` with `status: shipped`. (`/prawduct:backlog migrate --sections` does only this heading conversion without re-touching item metadata.)
5. **On completion** (all legacy items structured + sections folded), write `backlog_format_version: 2` as a top-level key in `.prawduct/project-state.yaml`. This records — as a committed, shared fact — that the backlog is on the structured format (and is the resolution-condition a future plugin-native `legacy-backlog-format` probe would consult). If migration is partial (user skipped items), do **not** set it yet — say how many remain.
6. Report: items migrated, sections folded, whether `backlog_format_version` was set, and how many (if any) remain legacy.

### dedup
Surface likely-duplicate / overlapping items and propose merges. Idempotent and **never destructive** (bodies preserved; nothing deleted — a merge archives the superseded item via `closes:`).
1. Group `## Open` (and `## Promoted`) items by `area:`; within each group, find candidate pairs by title-keyword + body overlap. (The `add` subcommand already does dedup-on-create; this is the after-the-fact sweep.)
2. Present each candidate pair/cluster with both titles + IDs and a one-line "why these look related." Ask which to merge, keep separate, or skip.
3. On a confirmed merge: pick the surviving item, fold the other's body into it (preserve both — append the merged-in body under a `— merged from PFX-XXXX —` marker), set `related:`/`refs:` as appropriate, and `update <superseded> status=dropped` with `closes: <survivor>` recorded on the survivor. Report what merged.

## Triage method

GREAT triage so each project doesn't reinvent it. Run periodically (the janitor's Backlog Health step automates the surfacing). The moves, in order:
1. **Converge duplicates/overlaps** — run `dedup`; merge or cross-link (`related:`) near-duplicates so one canonical item carries the work.
2. **Link to the source of truth** — for any item whose requirement/arch/design is written down, set `refs:` to that doc; for item→item relationships, set `related:`/`closes:`. A linked backlog is navigable; an unlinked one is a pile.
3. **Set the stage** — give each item a `stage:` (a vague item without one defaults to *not-ready* and won't be picked for implementation). Backfill `stage: ready` on bug/cleanup items, early stages on feature ideas. This is the single highest-value backfill on an existing backlog.
4. **Staleness review** — for `status: open` items unmoved >90d, decide: re-confirm (touch `reviewed:`), update with current context, or `status=dropped`. Aging out is fine; silting is not.
5. **Reconcile shipped work** — move items whose work actually shipped to `status=shipped` (Archive). Never infer this from build plans/change-logs (D4) — it's an explicit human/agent call; the Critic/PR checks only *surface* candidates.

Triage is also how an existing project adopts new format features: the new fields are additive, so `migrate` (legacy→structured + strikeout cleanup) plus the steps above bring a messy backlog up to standard — no separate migration subsystem.

$ARGUMENTS
