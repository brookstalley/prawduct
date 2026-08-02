---
description: Manage the structured product backlog — pick what to work on next, add/find/list/update items, and migrate legacy items. Use when the user wants to triage, file, or choose backlog work, or says /prawduct:backlog.
argument-hint: "[pick|add|find|list|update|migrate] ... (e.g. `pick stop-hook stuff under an hour`, `add`, `find sync`, `list --area=critic`, `update STH-K7p2 status=promoted`)"
user-invocable: true
disable-model-invocation: false
context: fork
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(prawduct-hook backlog file *), Bash(python3 plugin/bin/prawduct-hook backlog file *), Bash(prawduct-hook backlog get *), Bash(python3 plugin/bin/prawduct-hook backlog get *), Bash(prawduct-hook backlog status *), Bash(python3 plugin/bin/prawduct-hook backlog status *), Bash(prawduct-hook backlog update *), Bash(python3 plugin/bin/prawduct-hook backlog update *), Bash(prawduct-hook backlog comment *), Bash(python3 plugin/bin/prawduct-hook backlog comment *), Bash(prawduct-hook backlog list *), Bash(python3 plugin/bin/prawduct-hook backlog list *), Bash(prawduct-hook backlog pick *), Bash(python3 plugin/bin/prawduct-hook backlog pick *), Bash(prawduct-hook backlog counts *), Bash(python3 plugin/bin/prawduct-hook backlog counts *), Bash(prawduct-hook backlog claim *), Bash(python3 plugin/bin/prawduct-hook backlog claim *), Bash(prawduct-hook backlog unclaim *), Bash(python3 plugin/bin/prawduct-hook backlog unclaim *), Bash(prawduct-hook backlog link *), Bash(python3 plugin/bin/prawduct-hook backlog link *), Bash(prawduct-hook backlog unlink *), Bash(python3 plugin/bin/prawduct-hook backlog unlink *)
---

You manage the product's **structured backlog**. You run in a forked context, so the full backlog never pollutes the main session. The backlog has two backends — a markdown file, or GitHub Issues once the product has cut over — so **decide the backend first** (next section), then do the operation and return a concise result. **Never** delete items (archive instead) and **never** weaken existing content.

## Backend routing — decide this first

Read the top-level `backlog_service_repo` scalar from `.prawduct/project-state.yaml`:

- **Unset → markdown backend (pre-cutover).** `.prawduct/backlog.md` is the system of record. Everything in *this* file applies as written: Read the file, do the operation, write it back.
- **Set to `owner/repo` → GitHub Issues backend (post-cutover).** The markdown file is frozen history; the live backlog is GitHub Issues, reached through the `prawduct-hook backlog` adapter. **Follow `adapter-mode.md`** (this skill directory) for every operation — it maps each subcommand onto an adapter op and owns the envelope / exit-code / error discipline. Do **not** read or write `.prawduct/backlog.md` for live state in this mode — it is stale by construction, and showing it as live is the failure this routing prevents.

Resolve the backend once per invocation, then stay on that path; the two never mix.

**Direct reads of `.prawduct/backlog.md` — the rule every other reader follows.** This skill owns the
file; readers elsewhere in the framework (the Critic, the PR path, the janitor) do not, so one rule
governs them and it lives here:

- **Writes never bypass this skill**, on either backend.
- **Reads prefer the skill** — `/prawduct:backlog list` / `find` are backend-routed and therefore
  work on both sides of a cutover. Reach for them first.
- **A direct read of the file is permitted only after checking `backlog_service_repo` and finding it
  unset**, and only for detail the skill's views don't carry (full item bodies, for instance). Once
  the scalar is **set**, the file is frozen history and no reader may treat it as live state — every
  item archived at cutover still parses as open, so a direct read answers with the same confidence
  whether it is right or months stale.

A blanket "never read the file directly" was considered and rejected: it would retire the janitor's
full-body overlap read with no live replacement, which is exactly the bespoke per-reader projection
the read-through cache exists to avoid. The gate is the rule; each reader states it inline rather
than pointing here for it, so a reader that loads one file still gets the whole contract.

**Archive discipline.** "Done" has exactly one representation: `update status=shipped` (or `dropped`), which **moves the item to `## Archive`**. Never mark done by **strikethrough** (`~~…~~`) and never leave a shipped item inline in `## Open`/`## Promoted` — a struck item still costs context tokens every session and muddies the derived counts, while archiving preserves it for search. `migrate` includes a one-shot cleanup that converts existing struck/done-marked Open items into proper archived items.

**When to mark shipped — in the closing PR, not after it.** Archive an item *as part of the work that closes it*: on the feature branch, in the same PR as the change — markdown backend: `update <id> status=shipped closed-by=<scope>`; **Issues backend: `status <id> --to shipped` followed by `update <id> --closed-by <scope>`**, since a bare status change records no handle unless the close came from a merge — where `<scope>` is the branch/feature or chunk name — a handle that already exists on the branch, *not* a commit SHA or PR number that won't exist until later; see the `closed-by` rule under `update`. The archive then rides in that PR and is **atomic with the merge** — no separate after-merge bookkeeping commit/PR. This is still the explicit call D4 requires (not inferred from a view); doing it on the branch means an abandoned PR abandons the archive too, so the backlog can't drift. Backlog `shipped` = *the item's work is merged to the integration base* (the item's single terminal state) — distinct from a **change-log** entry's `status=shipped`, which means *released to consumers* (`main`) and legitimately batches at the `develop→main` release. Don't conflate them: the backlog archive belongs in the feature PR; the change-log `shipped` flip belongs to release-prep (gitflow) — or rides in the closing PR itself when the PR's base IS the release surface (trunk; `/prawduct:pr` create-flow Step 1d). Either way, no status change ever needs a post-merge commit on the integration branch.

**Archive split (Q2) — markdown backend only.** When `## Archive` grows past ~200 entries, move the oldest archived items into a sibling `backlog-archive.md` (same item format) to keep the working file lean — `find` already searches both, and git preserves history regardless. This is a `/prawduct:backlog` operation (the skill owns backlog.md writes); the janitor's Backlog Health step only *surfaces* when a split is due. Post-cutover there is nothing to split — Issues has no archive-file size limit, closed issues *are* the archive, and the janitor's Backlog Health step is dormant (`adapter-mode.md`, "Operations that don't apply post-cutover").

## The format you operate on

Each item:

```
- **[PFX-XXXX]** One-line title
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-29 · status: open`

  Optional free-form body (any length).
```

- **ID** `[PFX-XXXX]`: `PFX` = 2–3 uppercase letters naming the work-space, *derived from the item's area* — reuse an existing prefix when one fits so related items share it. Starter set (extend freely): `STH` stop-hook, `CRT` critic, `SYN` sync, `LLM` prompt/LLM, `BKL` backlog, `MIG` migration, `JNT` janitor, `MET` methodology, `DOC` docs, `TST` tests. If `backlog_prefixes:` is declared in `project-state.yaml`, prefer those. `XXXX` = 4 random base36 chars (`A–Z`,`0–9`); generate fresh and confirm it doesn't collide with an existing ID in the file.
- **Metadata bar**: one backticked dot-separated line. Required fields: `effort` (S/M/L), `impact` (S/M/L), `area`, `source` (builder|critic|reflection|janitor|user), `added` (YYYY-MM-DD), `status` (open|promoted|shipped|dropped). Optional: `related:` (related items), `closes:` (another backlog item this one supersedes — item→item), `closed-by:` (what shipped this item — a chunk id, the branch/feature *scope* name, or a release tag; item→release — a handle that exists *before* the commit recording it, never a bare commit SHA), `reviewed:`, `accepted-by:` (a soft claim — see below), `stage:` (lifecycle maturity — see below), `refs:` (links to governing docs — see below), `revisit:` (norm-exception/stopgap expiry — see below). Keep `closes:` and `closed-by:` straight — they point in opposite directions.
- **`accepted-by:` claim** — `accepted-by: @actor` marks that someone is working an item so others don't double-pick it (multi-actor products). It is a *soft, observable claim*, **not** a lock: backlog.md is eventually-consistent in git (two actors in separate worktrees won't see each other's claim until commit+pull), so it makes double-picks **visible and recoverable**, not impossible. It **does not auto-expire** — a durable claim (an area owner claiming weeks ahead) is legitimate; a stale claim is an out-of-scope process matter, not something the framework reaps. `pick` and `list` exclude claimed items by default.
- **`stage:` lifecycle** — `stage: idea | research | requirements | design | ready` records where the item sits in the feature lifecycle, so the framework can tell "this needs thinking" from "this is buildable." **Only `ready` is implementable.** An item with **no `stage:`** is treated as *not yet ready* — clarity has to be assessed before code. Bug/cleanup items are typically born `ready`; a vague feature idea is `idea`/`requirements`. `pick` uses this to route (see below). Advance an item with `update PFX-XXXX stage=...` as it matures.
- **`refs:` doc links** — `refs: requirements-x.md#section, arch-y.md` links an item to the governing artifacts (requirements / arch / design docs). Distinct from `related:` (item→item). Set it when an item's requirement/design gets written (often as a `stage:` advances), so triage can cluster items around the docs they touch and a reader can jump to the source of truth.
- **`revisit:` expiry** — `revisit: YYYY-MM-DD` (machine-fired: a past date raises an advisory while the item is open) or `revisit: <event trigger text>` (walked by the janitor Norm Health sweep, never probe-fired). It is the expiry clock on a norm **exception** or **stopgap** per `/prawduct:methodology norms` (§ Exceptions expire) — a temporary non-application of a live norm files a backlog item carrying `revisit:`, so the exception expires *visibly* instead of persisting silently.
- **Sections**: `## Open` (pickable), `## Promoted` (in an active build plan), `## Archive` (shipped/dropped, kept for search). Items move between sections only via explicit `update` calls — never infer status from build plans or change logs.
- **Legacy items** (no metadata bar) are valid; treat them as `effort:? · impact:? · area:untagged · status:open` and rank them lower. Suggest `/prawduct:backlog migrate` if there are many.

For today's date when stamping `added:`/`reviewed:`, use the current date from your environment context.

## Subcommands

Parse `$ARGUMENTS`: the first token is the subcommand (default to the no-arg summary if empty). Everything after is arguments — accept both `--flag=value` form (for machine callers like the Critic or reflection) and natural-language prose (for humans).

### (no args) — summary + menu
Read the file, then print: counts per section (`N open · N promoted · N archived`), the top 3 `area:` tags by item count, a count of stale items (`status: open` and `added`/`reviewed` >90 days ago), and the action menu (`pick`, `add`, `find`, `list`, `update`, `dedup`, `import`, `migrate`). All counts are **derived on read** — never persist a count to any file (a stored count drifts and becomes a sync liability; re-deriving is cheap).

### add
File a new item. Accepts flags (`--title=`, `--body=`/`--body-file=`, `--area=`, `--effort=`, `--impact=`, `--source=`, `--prefix=`) or interactive prompts for anything missing.
1. **Dedup first.** Search existing items whose `area:` matches or whose title keywords overlap. If any exist, show the top ~3 (`[ID] title — status, added`) and ask: continue, update one of them, or cancel. (When called with complete flags by a machine caller, skip the prompt but still note overlaps in your result.)
2. On confirm, derive a prefix, generate a non-colliding `[PFX-XXXX]`, build the metadata bar (`source` defaults to the caller; `added` = today; `status: open`), and append the item under `## Open`.
3. Return the new ID and a one-line confirmation.

### find <query>
*(Markdown backend. Post-cutover, full-text search is unavailable — `adapter-mode.md` returns a NOTE and points at `list` filters.)* Plaintext + tag search across title, metadata, and body of **all** sections (and `backlog-archive.md` if it exists). Return matching `[ID] title — one-line summary`, most-relevant first. Keep it tight (a handful of results).

### list [--filter=...]
Tabular view: `ID · title · effort · impact · area · status`. **Default filter: `status=open` AND `added` within 90 days** (so a 200-item backlog doesn't dump). `--all` overrides; filter on any metadata field (`--area=`, `--status=`, `--effort=`, etc.). Sort by status then recency. **Claimed items** (non-empty `accepted-by:`) are excluded by default; show them with `--include-claimed`, and when shown, display the claim holder in the row.

**Grooming timestamp:** `list` and `pick` both stamp `backlog_last_groomed_at: <today>` (top-level scalar) in `project-state.yaml` on invocation — this is the fact that resolves the `backlog-overdue-grooming` advisory. It's a *timestamp*, not a count (counts are always re-derived, never persisted — D14).

### update PFX-XXXX <field=value> [...]
Change metadata or body of one item. **The `field=value` spellings in this section are the markdown backend's**; on the Issues backend they are flags and the storage differs — see the flag paragraph below, and don't carry the markdown wording across. Common: `status=promoted|shipped|dropped` (markdown: moves the item to the matching section — `promoted`→`## Promoted`, `shipped`/`dropped`→`## Archive`; Issues: `status --to`, which sets state + `state_reason`), `area=`, `effort=`. On `status=shipped`, accept an optional `closed-by=<ref>` — a chunk id, the branch/feature scope name, or a release/change-log tag — recorded for traceability in the **metadata bar** on markdown (not the body) and in the `prawduct:` **block** on Issues, where the block *is* the body and there is no metadata bar. The handle must exist *before* the commit that records it: a **bare commit SHA is wrong** — a commit can't contain its own final SHA, and a `--amend` that folds the archive into the ship commit rewrites that SHA so the ref dangles. For standalone work with no chunk id (a refactor/chore committed directly), use the **branch/scope name** — not a SHA, and not a PR number that isn't assigned until the PR opens. If a caller passes a bare SHA, record the branch/scope name instead and note the substitution in your result. Confirm the item exists first; if the ID isn't found, say so and suggest `/prawduct:backlog find`.

**On the Issues backend these are flags, not `field=value` args**, and only these block fields are writable: `--refs`, `--revisit`, `--closed-by` (each takes a value; an **empty** value clears it, so an expired `revisit:` can be removed rather than blanked) and `--reviewed`. Everything else in the `prawduct:` block is import-only or owned by another op — `related` by `link`/`unlink`, `superseded_by` by `merge`, `claimed_at` by `claim`/`unclaim`, and `added` by nothing at all, since GitHub's `created_at` already answers it unforgeably. **A `--body` edit carrying an edited block is silently discarded** (the existing block is re-appended verbatim, by design, so a naive body replace cannot drop permanent aliases) — so editing the block through `--body` reports success and changes nothing. Use the flags.

**`--reviewed` takes no value and is never implied.** It stamps *today*, meaning "I re-read this item and it still holds" — a backdated re-confirmation is unfalsifiable, so the only honest claim is now. And it is deliberately **not** stamped by other edits: native `updated_at` already records that an item was touched, so auto-stamping would make `reviewed:` a forgeable copy of it and destroy the one thing it uniquely says. Stamp it when you have actually re-read the item — which is what the staleness sweep in Triage below is asking about.

**Claims:** on the **Issues backend** a claim is `claim <id>` / `unclaim <id>` — not a field write. The op takes the issue's native `assignee` atomically (the resolved API identity, never a caller-supplied name) and stamps the block's `claimed_at` for visible staleness, so `pick` can reap a claim orphaned by a died agent. There is no `accepted-by` flag and there should not be one: a self-asserted claimant is forgeable, while the assignee is the backend's own record. On the **markdown backend** the same idea is the metadata bar's `accepted-by:` field, set to an actor handle and cleared with an empty value, which is why it survives on migrated items — there it is history, not a live write target.

Either way: when an item reaches `status=shipped` or `status=dropped`, **release the claim** (a finished item is not claimed — `unclaim` on Issues, clear `accepted-by:` on markdown). Never release on any other transition; a `promoted` or still-`open` item may legitimately stay claimed. Do not touch a claim you didn't set unless the user explicitly asks — reassignment is a human call, not the skill's.

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
- `stage: idea | research | requirements` → **do not present as buildable.** Surface it framed as *"this needs <stage> work next"* and route to **`/prawduct:methodology discovery`** — advancing the stage (writing the requirement, doing the research) *is* the work. The agent updates `stage:` (and adds a `refs:` link to the doc it produces) via `update` as the item matures.
- `stage: design` → route to **`/prawduct:methodology planning`** (requirements clear; architecture/detailed design pending).
- **No `stage:`** → treat as *not yet ready*: don't present it as directly buildable; prompt to assess clarity first (fail toward requirements, not toward code). This is the safe default for the large existing backlog whose items predate the field.

This routing is advisory, not a hard gate — surface the stage and the recommended next step; the user may still choose to override. Don't silently let an early-stage item flow into implementation.

**Worked examples** (parsed filter → behavior):
- `pick stop-hook stuff under an hour` → `{area: stop-hook, budget: S–M}` → open stop-hook items, effort S/M, top 2–3 by score.
- `pick a warmup task` → `{type: warmup}` → small/legacy/cleanup items, low stakes, recency-weighted.
- `pick` (bare, plan active) → no filters → build-plan-overlapping open items first, then general `impact/effort` ranking.
- `pick something quick and high-impact` → `{type: quick-win}` → high-impact + low-effort items.

### migrate
Convert legacy unstructured items to the structured format and fold the old sections into Open/Promoted/Archive. **Idempotent** (only touches items lacking a metadata bar) and **never destructive** (bodies are preserved verbatim; items are never deleted). Run it when a repo carries unstructured legacy items (the `pick`/list views flag these). The `legacy-backlog-format` post-sync advisory (`lib/backlog_probes.py`) nudges this automatically at session start when `.prawduct/backlog.md` has >5 items none carrying a `[PFX-XXXX]` id — so a repo that adopts a new prawduct version with an unmigrated backlog is prompted to run `migrate`.

1. Read `.prawduct/backlog.md`. Identify legacy items — top-level bullets with no `effort: … · status: …` metadata bar. If there are none, report "already migrated" and stop.
2. Walk them in **batches of ~10**. For each item show its title + first ~2 lines of body and your **inferred metadata**:
   - `source` from existing parenthetical markers (`(critic)`/`(reflection)`/`(builder)`/`(migrated)` → the matching source; else `user`).
   - `area` inferred from title/body keywords; reuse tags already present in the file.
   - a derived `[PFX-XXXX]` id (prefix from the area; fresh non-colliding suffix).
   - `effort`/`impact` left as `?` when not inferable — don't invent them.
   Present the batch and let the user accept as-is, edit inline (e.g. supply `effort impact`), or skip individual items. When run non-interactively, apply your inferences and report what you assumed.
3. On accept, rewrite each item to the structured shape (id + metadata bar + original body unchanged), placing it in the section matching its `status` (default `open`).
4. **Fold sections**: map legacy headings onto the canonical three — `## Active — next up` and `## Queue` → `## Open` (use judgment if "Active" items were truly in-flight → `## Promoted`); preserve any already-`[RESOLVED]`/shipped items by moving them to `## Archive` with `status: shipped`. (`/prawduct:backlog migrate --sections` does only this heading conversion without re-touching item metadata.)
4b. **Strikeout cleanup sweep.** While migrating, also convert any **struck** (`~~…~~`) or otherwise done-marked items still sitting in `## Open`/`## Promoted` into proper archived items: rewrite to `status: shipped` (preserve the body), move to `## Archive`. This is idempotent and non-destructive (bodies kept) and brings a hand-edited backlog up to the archive discipline. Run it on `migrate` even when there are no *legacy* (metadata-less) items — strikeouts can exist on otherwise-structured items.
4c. **Legend refresh.** The header legend (the `<!-- … -->` comment block at the top of `backlog.md`) is authored once at scaffold time, so a backlog onboarded before a format field existed documents an *older* schema — items get backfilled (e.g. `stage:`) while the legend never mentions the new field, leaving a reader without the key. Reconcile it: ensure the legend documents the **current canonical field set** (every field described above in "The format you operate on" — including `stage:`, `refs:`, `accepted-by:`, and `revisit:`); add a one-line description for any canonical field the legend is missing. **Additive and non-destructive** — never remove or rewrite a project-local field's documentation (a repo may legitimately document its own extension, e.g. a `kind:` facet); you are filling gaps, not overwriting. Idempotent (a legend already covering the canonical set is left untouched). Like the strikeout sweep, run this even when there are no legacy items.
5. **On completion** (all legacy items structured + sections folded + strikeouts cleaned + legend refreshed), write `backlog_format_version: 2` as a top-level key in `.prawduct/project-state.yaml`. This records — as a committed, shared fact — that the backlog is on the structured format, and is the resolution-condition the plugin-native `legacy-backlog-format` probe (`lib/backlog_probes.py`) consults to clear its advisory for everyone on next sync. If migration is partial (user skipped items), do **not** set it yet — say how many remain.
6. Report: items migrated, sections folded, whether the legend was refreshed (and which fields it gained), whether `backlog_format_version` was set, and how many (if any) remain legacy.

### import <path>
Convert an external backlog file (`TODO.md`, `BACKLOG.md`, `ROADMAP.md`, `IDEAS.md`, a GitHub issue export, etc.) into structured items. **Always confirm before writing.**
1. Read the source file. Identify items by structure (markdown bullets, headings, issue-template fields).
2. For each, draft a `[PFX-XXXX]` entry: `source: user`, `status: open`, `area:` inferred from content, `stage:` inferred where possible (a vague one-liner → `idea`; a clearly-scoped bug → `ready`; leave unset if unclear → treated as not-ready). Effort/impact `?` when not inferable.
3. Show the preview; user confirms or edits. On confirm, append under `## Open` (optionally beneath a `<!-- Imported from <path> on <date> -->` marker), and **record `<path>` in the top-level `backlog_external_imports` fact** in `project-state.yaml` — this resolves the `external-backlog-detected` advisory for everyone on next sync.
4. Do not delete the source file (the user decides whether to remove it); recording it as imported is what stops the nag.

### dedup
Surface likely-duplicate / overlapping items and propose merges. Idempotent and **never destructive** (bodies preserved; nothing deleted — a merge archives the superseded item via `closes:`).
1. Group `## Open` (and `## Promoted`) items by `area:`; within each group, find candidate pairs by title-keyword + body overlap. (The `add` subcommand already does dedup-on-create; this is the after-the-fact sweep.)
2. Present each candidate pair/cluster with both titles + IDs and a one-line "why these look related." Ask which to merge, keep separate, or skip.
3. On a confirmed merge: pick the surviving item, fold the other's body into it (preserve both — append the merged-in body under a `— merged from PFX-XXXX —` marker), set `related:`/`refs:` as appropriate, and `update <superseded> status=dropped` with `closes: <survivor>` recorded on the survivor. Report what merged.

### scrub (migration to GitHub Issues)
The **owner-confirmed cleanup** run once when a project moves its markdown backlog onto GitHub Issues through the backlog service (`prawduct-hook backlog <op>`). It surfaces stale/duplicate items *before* they become live issues (model proposes → owner confirms → the deterministic `status`/`merge`/`import` ops apply the cleaned set; the model is in the decision, never the data plane — MG4/G1). Distinct from `dedup`/`migrate` above, which edit `.prawduct/backlog.md` in place; this drives the service CLI and requires `gh`. **Full runbook: `migration-scrub.md`** (in this skill directory).

The scrub's high-consequence adapter ops — `import` (bulk-creates 100–250 issues), `merge`, `provision`, `reconcile-labels` — are **deliberately absent from this skill's `allowed-tools` grant**. The grant lists only the everyday ops (`file`/`get`/`status`/`update`/`comment`/`list`/`pick`/`counts`/`claim`/`unclaim`/`link`/`unlink`), so a scrub op surfaces a permission prompt at the moment it would write. That prompt is *defense-in-depth* on the one-time, owner-confirmed migration — the primary guard is **the runbook's own Step 0 target-repo selection + owner confirmation**, which every later step binds to — not the tools list (a skill `allowed-tools` is a no-prompt allow-list, not a hard cap). Do not "fix" the prompt by re-widening the grant.

**There is no adapter-side target guard, and you must not assume one.** `lib/backlog/` performs no repo-identity comparison anywhere: `ids.parse_repo` is *shape-only* (two clean segments — no allowlist, no owner constraint, no same-repo check) at all ten of its call sites, and no adapter op consults `backlog_service_repo` to validate a `--repo`. So `import --repo <any-valid-slug>` will write to whatever repo it is handed. The confirmation step **is** the guard; nothing beneath it will catch a wrong target. *(An adapter-side pin exists only in the `file-upstream` design — a different op, governing cross-owner **upstream filing**, not this migration.)*

## Triage method

GREAT triage so each project doesn't reinvent it. Run periodically (the janitor's Backlog Health step automates the surfacing). The moves, in order:
1. **Converge duplicates/overlaps** — run `dedup`; merge or cross-link (`related:`) near-duplicates so one canonical item carries the work.
2. **Link to the source of truth** — for any item whose requirement/arch/design is written down, set `refs:` to that doc (Issues backend: `update <id> --refs <doc>`, or `file --refs <doc>` to land it at creation); for item→item relationships use `link`/`unlink` (`related`) and `merge` (supersession), not a field write. A linked backlog is navigable; an unlinked one is a pile.
3. **Set the stage** — give each item a `stage:` (a vague item without one defaults to *not-ready* and won't be picked for implementation). Backfill `stage: ready` on bug/cleanup items, early stages on feature ideas. This is the single highest-value backfill on an existing backlog.
4. **Staleness review** — for `status: open` items unmoved >90d, decide: re-confirm (Issues: `update <id> --reviewed`, only after actually re-reading it), update with current context, or `status=dropped`. Aging out is fine; silting is not. Judge staleness by `reviewed:` rather than the native `updated_at` — a label fix bumps `updated_at` without anyone having looked at the item, which is exactly the false "recently handled" signal this step exists to see through.
5. **Reconcile shipped work (fallback)** — the primary path is archiving an item *on the branch that closes it*, so it ships in that PR (see "When to mark shipped" above); this step is the catch-net for items whose work shipped but were never archived. Move them to `status=shipped` (Archive). Never infer this from build plans/change-logs (D4) — it's an explicit human/agent call; the Critic/PR checks only *surface* candidates.

Triage is also how an existing project adopts new format features: the new fields are additive, so `migrate` (legacy→structured + strikeout cleanup + legend refresh) plus the steps above bring a messy backlog up to standard — no separate migration subsystem. The legend refresh is what keeps the documented schema from lagging the backfilled items (a backlog that gains `stage:`/`refs:`/`accepted-by:` on its items but never in its legend).

$ARGUMENTS
