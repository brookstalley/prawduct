---
description: Manage the structured product backlog — pick what to work on next, add/find/list/update items, and migrate legacy items. Use when the user wants to triage, file, or choose backlog work, or says /prawduct:backlog.
argument-hint: "[pick|add|find|list|update|migrate] ... (e.g. `pick stop-hook stuff under an hour`, `add`, `find sync`, `list --area=critic`, `update STH-K7p2 status=promoted`)"
user-invocable: true
disable-model-invocation: false
context: fork
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(prawduct-hook backlog file *), Bash(python3 plugin/bin/prawduct-hook backlog file *), Bash(prawduct-hook backlog get *), Bash(python3 plugin/bin/prawduct-hook backlog get *), Bash(prawduct-hook backlog status *), Bash(python3 plugin/bin/prawduct-hook backlog status *), Bash(prawduct-hook backlog update *), Bash(python3 plugin/bin/prawduct-hook backlog update *), Bash(prawduct-hook backlog comment *), Bash(python3 plugin/bin/prawduct-hook backlog comment *), Bash(prawduct-hook backlog list *), Bash(python3 plugin/bin/prawduct-hook backlog list *), Bash(prawduct-hook backlog pick *), Bash(python3 plugin/bin/prawduct-hook backlog pick *), Bash(prawduct-hook backlog counts *), Bash(python3 plugin/bin/prawduct-hook backlog counts *), Bash(prawduct-hook backlog link *), Bash(python3 plugin/bin/prawduct-hook backlog link *), Bash(prawduct-hook backlog unlink *), Bash(python3 plugin/bin/prawduct-hook backlog unlink *), Bash(prawduct-hook backlog sync *), Bash(python3 plugin/bin/prawduct-hook backlog sync *), Bash(prawduct-hook backlog cache-query *), Bash(python3 plugin/bin/prawduct-hook backlog cache-query *), Bash(prawduct-hook backlog --help), Bash(python3 plugin/bin/prawduct-hook backlog --help)
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

**When to mark shipped — the timing rule lives here, and it splits by backend.** Archive an item *as part of the work that closes it*, with `update <id> status=shipped closed-by=<scope>` (`<scope>` names the *work*, not its position in a plan — a handle that already exists on the branch, *not* a commit SHA or PR number that won't exist until later; see the `closed-by` rule under `update`). **When** that call runs depends on what the archive physically IS, because the atomicity the convention promises is a property of **being a commit**, not a property of the archive — which is why it was once stated unconditionally and was false for half the products running it (#697).

- **Markdown backend — on the feature branch, in the same PR as the change.** The archive is a file edit, so it rides in that PR and is genuinely **atomic with the merge**: no separate after-merge bookkeeping commit/PR, and an abandoned PR abandons the archive too, so the backlog can't drift.
- **Issues backend (`backlog_service_repo` is set) — at the merge, not on the branch.** `status --to shipped` closes the issue over the API the moment it runs: an immediate remote side effect with no branch to be abandoned with. Run on an unmerged branch it leaves the item **wrongly closed** if the PR is abandoned or reworked — the same drift in the opposite direction, and the one bookkeeping error nothing later sweeps for (#697 records #687 and #688 as instances). So the call is deferred to the merge itself: `/prawduct:pr`'s Merge Flow **"Close the backlog items this PR resolves"** step, which fires seconds after the merge succeeds. A `Closes #N` in the PR body does **not** stand in for it — GitHub fires closing keywords only for PRs merged into the repository's **default** branch, so on a gitflow base the keyword is inert.

Either way the call is **explicit** — D4 requires it, never inferred from a view — and **no status change ever needs a post-merge commit on the integration branch**: the markdown archive rides the PR, and the Issues close is an API call that touches no branch at all. Backlog `shipped` = *the item's work is merged to the integration base* (the item's single terminal state) — distinct from a **change-log** entry's `status=shipped`, which means *released to consumers* (`main`) and legitimately batches at the `develop→main` release. Don't conflate them: the backlog archive belongs in the feature PR; the change-log `shipped` flip belongs to release-prep (gitflow) — or rides in the closing PR itself when the PR's base IS the release surface (trunk; `/prawduct:pr` create-flow Step 1d).

**Archive split (Q2) — markdown backend only.** When `## Archive` grows past ~200 entries, move the oldest archived items into a sibling `backlog-archive.md` (same item format) to keep the working file lean — `find` already searches both, and git preserves history regardless. This is a `/prawduct:backlog` operation (the skill owns backlog.md writes); the janitor's Backlog Health step only *surfaces* when a split is due, and it still does — on this backend. Post-cutover there is nothing to split (Issues has no archive-file size limit, closed issues *are* the archive), so that one check alone stands down while the rest of the janitor's Backlog Health block runs off the backlog cache (`adapter-mode.md`, "Operations that don't apply post-cutover").

## The format you operate on

Each item:

```
- **[PFX-XXXX]** One-line title
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-29 · status: open`

  Optional free-form body (any length).
```

- **ID** `[PFX-XXXX]`: `PFX` = 2–3 uppercase letters naming the work-space, *derived from the item's area* — reuse an existing prefix when one fits so related items share it. Starter set (extend freely): `STH` stop-hook, `CRT` critic, `SYN` sync, `LLM` prompt/LLM, `BKL` backlog, `MIG` migration, `JNT` janitor, `MET` methodology, `DOC` docs, `TST` tests. If `backlog_prefixes:` is declared in `project-state.yaml`, prefer those. `XXXX` = 4 random base36 chars (`A–Z`,`0–9`); generate fresh and confirm it doesn't collide with an existing ID in the file.
- **Metadata bar**: one backticked dot-separated line. Required fields: `effort` (S/M/L), `impact` (S/M/L), `area`, `source` (builder|critic|reflection|janitor|user), `added` (YYYY-MM-DD), `status` (open|promoted|shipped|dropped). Optional: `related:` (related items), `closes:` (another backlog item this one supersedes — item→item), `closed-by:` (what shipped this item — the branch/feature *scope* name or a release tag; item→release — a handle that exists *before* the commit recording it, never a bare commit SHA and never a bare chunk id, which names no plan), `reviewed:`, `accepted-by:` (a soft claim — see below), `stage:` (lifecycle maturity — see below), `refs:` (links to governing docs — see below), `revisit:` (norm-exception/stopgap expiry — see below). Keep `closes:` and `closed-by:` straight — they point in opposite directions.
- **`accepted-by:` claim** — `accepted-by: @actor` marks that someone is working an item so others don't double-pick it (multi-actor products). It is a *soft, observable claim*, **not** a lock: backlog.md is eventually-consistent in git (two actors in separate worktrees won't see each other's claim until commit+pull), so it makes double-picks **visible and recoverable**, not impossible. It **does not auto-expire** — a durable claim (an area owner claiming weeks ahead) is legitimate; a stale claim is an out-of-scope process matter, not something the framework reaps. `pick` and `list` exclude claimed items by default.

  **This is the markdown backend's field, and the Issues backend has a different one.** Post-cutover, taking an item is `working-branch: owner/repo@branch` (`adapter-mode.md`) — the same *concept* on a substrate where a branch is the honest activity signal and there is no file to be eventually-consistent about. The two are deliberately not unified: `working-branch` requires a **pushed** ref and a named repo, which a local-only repo or a shared-trunk team cannot supply, and `accepted-by:` costs those products nothing. One field per backend, each native to its substrate; the import maps neither to the other, so a migrating product's open claims are not carried and should be re-recorded as working branches.
- **`stage:` lifecycle** — `stage: idea | research | requirements | design | ready` records where the item sits in the feature lifecycle, so the framework can tell "this needs thinking" from "this is buildable." **Only `ready` is implementable.** An item with **no `stage:`** is treated as *not yet ready* — clarity has to be assessed before code. Bug/cleanup items are typically born `ready`; a vague feature idea is `idea`/`requirements`. `pick` uses this to route (see below). Advance an item with `update PFX-XXXX stage=...` as it matures.
- **`refs:` doc links** — `refs: requirements-x.md#section, arch-y.md` links an item to the governing artifacts (requirements / arch / design docs). Distinct from `related:` (item→item). Set it when an item's requirement/design gets written (often as a `stage:` advances), so triage can cluster items around the docs they touch and a reader can jump to the source of truth.
- **`revisit:` expiry** — `revisit: YYYY-MM-DD` (machine-fired: a past date raises an advisory while the item is open) or `revisit: <event trigger text>` (walked by the janitor Norm Health sweep, never probe-fired). It is the expiry clock on a norm **exception** or **stopgap** per `/prawduct:methodology norms` (§ Exceptions expire) — a temporary non-application of a live norm files a backlog item carrying `revisit:`, so the exception expires *visibly* instead of persisting silently.
- **Sections**: `## Open` (pickable), `## Promoted` (in flight — in an active build plan, or handed to an ad-hoc delegate, which by construction belongs to no plan), `## Archive` (shipped/dropped, kept for search). Items move between sections only via explicit `update` calls — never infer status from build plans or change logs. A delegate-held item closes when its branch is integrated (`update PFX-XXXX status=shipped`) or when the delegate is abandoned (back to `status: open`, claim field cleared) — nothing derives that from the branch, and the janitor's `## Promoted` sweep looks for a shipped owning *chunk*, which a delegate item does not have.
- **Legacy items** (no metadata bar) are valid; treat them as `effort:? · impact:? · area:untagged · status:open` and rank them lower. Suggest `/prawduct:backlog migrate` if there are many.

For today's date when stamping `added:`/`reviewed:`, use the current date from your environment context.

## Subcommands

Parse `$ARGUMENTS`: the first token is the subcommand (default to the no-arg summary if empty). Everything after is arguments — accept both `--flag=value` form (for machine callers like the Critic or reflection) and natural-language prose (for humans).

### (no args) — summary + menu
Read the file, then print: counts per section (`N open · N promoted · N archived`), the top 3 `area:` tags by item count, a count of stale items (`status: open` and `added`/`reviewed` >90 days ago), and the action menu (`pick`, `add`, `find`, `list`, `update`, `dedup`, `import`, `migrate`). All counts are **derived on read** — never persist a count to any file (a stored count drifts and becomes a sync liability; re-deriving is cheap).

### add
*(Markdown backend for the write mechanics — post-cutover `adapter-mode.md` owns those. **Step 2 is backend-independent**: the question it asks is about the work, not about where the item lands, so adapter-mode cites it rather than keeping a second copy.)*
File a new item. Accepts flags (`--title=`, `--body=`/`--body-file=`, `--area=`, `--effort=`, `--impact=`, `--stage=`, `--source=`, `--prefix=`) or interactive prompts for anything missing.
1. **Dedup first.** Search existing items whose `area:` matches or whose title keywords overlap. If any exist, show the top ~3 (`[ID] title — status, added`) and ask: continue, update one of them, or cancel. (When called with complete flags by a machine caller, skip the prompt but still note overlaps in your result.)
2. **Is filing it the right answer?** When the item describes work **in this repo that is ready to build** — the `stage: ready` this add is about to stamp, or a bug/cleanup item born ready — the instinct to file is one of three options, and it gets said out loud: **delegate it, do it now, or backlog it** — filing is the third answer, not the default. Offer the delegate with its cost attached (a branch plus an integration debt, and how many ad-hoc branches already await integration); the judgment behind the offer is `/prawduct:methodology delegation` § Work no plan anticipated, not restated here. Then honour the answer: *backlog it* files as normal; *delegate it* files the item **and** marks it in flight — `status: promoted`, plus the backend's own claim field (`accepted-by:` on markdown; on Issues `--working-branch`, once the branch is pushed) — because a delegate's debt has to outlive its worktree; *do it now* needs no item — the commit is the record — unless the work outgrows the tangent.
   **The ready-to-build bound is the guard, not a detail.** Everything earlier files silently and unchanged: a one-line idea, a research question, anything at `stage: idea|research|requirements|design`, and anything with **no `stage:`** (which this format already treats as not-ready). So does work you cannot open a worktree on — an upstream prawduct bug captured in this product's backlog is not a delegation candidate — and so does any non-interactive machine call: the Critic files findings, it does not dispatch. **And so does filing at a work-cycle boundary** — the chunk-close sweep that files what this cycle deliberately left out. That is the highest-volume `add` path there is, and it is the one moment `delegation.md` answers *no* before you ask: dispatch is session-bounded, and *would you integrate this today if it came back green?* is a standing no at a close. Offering N delegates for N deferred items there is the defensive asking this trigger exists to avoid. Like the digest's twin trigger, this one is for work that arrives **mid-chunk**. A prompt that fires on every `add` is a prompt people route around.
   Silent entirely where `project-preferences.md` sets `Delegation: off`.
3. On confirm, derive a prefix, generate a non-colliding `[PFX-XXXX]`, build the metadata bar (`source` defaults to the caller; `added` = today; `status: open`), and append the item under `## Open`. **Stamp `stage:`** — as given, else inferred the way `import` infers it (a clearly-scoped bug or cleanup → `ready`; a vague one-liner → `idea`), and left unset when genuinely unclear, which this format already reads as not-ready. An item born stageless is one `pick` will never present as buildable, so the field is decided here or backfilled by hand later.
4. Return the new ID and a one-line confirmation.

### find <query>
*(Markdown backend. Post-cutover, `adapter-mode.md` routes this to the local cache's full-text index — `cache-query search`.)* Plaintext + tag search across title, metadata, and body of **all** sections (and `backlog-archive.md` if it exists). Return matching `[ID] title — one-line summary`, most-relevant first. Keep it tight (a handful of results).

### list [--filter=...]
Tabular view: `ID · title · effort · impact · area · status`. **Default filter: `status=open` AND `added` within 90 days** (so a 200-item backlog doesn't dump). `--all` overrides; filter on any metadata field (`--area=`, `--status=`, `--effort=`, etc.). Sort by status then recency. **Claimed items** (non-empty `accepted-by:`) are excluded by default; show them with `--include-claimed`, and when shown, display the claim holder in the row.

**Grooming timestamp:** `list` and `pick` both stamp `backlog_last_groomed_at: <today>` (top-level scalar) in `project-state.yaml` on invocation — this is the fact that resolves the `backlog-overdue-grooming` advisory. It's a *timestamp*, not a count (counts are always re-derived, never persisted — D14).

### update PFX-XXXX <field=value> [...]
Change metadata or body of one item. Common: `status=promoted|shipped|dropped` (moves the item to the matching section — `promoted`→`## Promoted`, `shipped`/`dropped`→`## Archive`); on markdown also `area=`, `effort=`, `reviewed=`. On `status=shipped`, accept an optional `closed-by=<ref>` — the branch/feature scope name or a release/change-log tag — **and what happens to it depends on the backend, so say which one you are on before you promise the caller anything.** *Markdown backend:* write it into the **metadata bar** as `closed-by: <ref>` (not the body) for traceability. *Issues backend:* `status <id> --to shipped` records no handle by itself, so follow it with `update <id> --closed-by <ref>`, which stores it in the adapter-owned `prawduct:` block as a queryable field. **Never hand-write a `prawduct:` block to carry it**: that block is adapter-owned and a hand-written one is merged away. The handle must exist *before* the commit that records it: a **bare commit SHA is wrong** — a commit can't contain its own final SHA, and a `--amend` that folds the archive into the ship commit rewrites that SHA so the ref dangles. A **bare chunk id is equally wrong**: it names no plan, so it means nothing to a reader a year out — `Chunk 04` against `eval-system-rebuild`. Always use the **branch/scope name** — not a SHA, and not a PR number that isn't assigned until the PR opens. If a caller passes a bare SHA, record the branch/scope name instead and note the substitution in your result. On the markdown backend, always set `reviewed:` to today on any touch (the Issues block carries `reviewed:` from the import but has no write path for it). Confirm the item exists first; if the ID isn't found, say so and suggest `/prawduct:backlog find`.

**On the Issues backend these are flags, not `field=value` args**, and only these block fields are writable: `--affected`, `--working-branch`, `--refs`, `--revisit`, `--closed-by` (each takes a value; an **empty** value clears it, so an expired `revisit:` can be removed rather than blanked), plus the multi-valued `--tags`. Everything else in the `prawduct:` block is import-only or owned by another op — `related` by `link`/`unlink`, `superseded_by` by `merge`, and `added` by nothing at all, since GitHub's `created_at` already answers it unforgeably. **A `--body` edit carrying an edited block is silently discarded** (the existing block is re-appended verbatim, by design, so a naive body replace cannot drop permanent aliases) — so editing the block through `--body` reports success and changes nothing. Use the flags.

**Claims (`accepted-by`) - markdown backend only.** On markdown, `update PFX-XXXX accepted-by=@actor` records a claim; on markdown `accepted-by=` (empty value) clears it. On the Issues backend the equivalent is `--working-branch` (see above). When you set `status=shipped` or `status=dropped`, **auto-clear** `accepted-by` (a finished item is not claimed) — the work is over, the claim is moot. Never auto-clear on any other transition (a `promoted` or still-`open` item may legitimately stay claimed). Do not touch a claim you didn't set unless the user explicitly asks — reassignment is a human call, not the skill's.

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
   - **An item missing *both* fields scores `2/2 = 1.0`** — the same as a genuine `M`-impact/`M`-effort item, and *above* anything whose impact is honestly lower than its effort (`S/M` = 0.5, `S/L` = 0.33). So the default is not neutral: it ranks an unassessed item ahead of an assessed but unattractive one. The legacy-item penalty above is what keeps that from dominating, and it only applies to items with no metadata bar at all — an item carrying a bar but leaving `effort:`/`impact:` blank gets the 1.0 with no penalty. Treat a cluster of 1.0 scores as *unassessed*, not as *medium value*, and prefer filling the fields over trusting the rank.
4. **Return** the top 1–3 as `[ID] title` + a one-line *why* (e.g. *"high-impact sync fix, ~2h, no dependencies"*).

**Build-plan-aware — the primary mid-work case.** Before ranking, resolve the active plan the way governance does — a live plan under `.prawduct/artifacts/` claiming the checked-out branch with `branch:`, else `active_build_plan` from `.prawduct/project-state.yaml`; several plans may claim one branch, and `methodology/planning.md` states which wins. Reading only the scalar loses the ranking entirely on a repo that has adopted `branch:` and left the scalar unset. If a plan resolves, read it and infer its scope/area focus (its `scope:` tag, chunk areas, the files it touches). Then **prioritize open items whose `area:` or subject overlaps the active plan**, framed as *"related to what you're working on"* — knocking out an adjacent item while the context is loaded is the highest-value pick. Show overlapping candidates first; if fewer than the requested count, fill from the general ranking. `--standalone` disables this and deliberately suggests context-switch work instead. If no plan is active, skip straight to the general ranking.

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

### decline-migration <reason>
Permanently record that this product is staying on the **markdown** backlog (#197/TM1) — a product
with no GitHub remote, on another forge, air-gapped, or whose owner simply does not want an Issues
tracker. Without this, `backlog-service-migration-required` nudges every session toward a migration
that is never going to happen, and a signal nobody can act on is one a reader learns to skip.
**Requires a reason**; if none is given, ask for one rather than writing the field with no rationale.

1. **Precondition.** Read `backlog_service_repo` from `.prawduct/project-state.yaml`. If it is
   already set, this product has cut over — say so and stop; there is nothing to decline.
2. **Write.** Add, as a top-level scalar in `.prawduct/project-state.yaml` (create the field if
   absent; if it is already `markdown`, report "already declined" and stop):

   ```yaml
   # <reason, verbatim from the caller> — recorded <today's date>
   backlog_backend: markdown
   ```

   The comment directly above the field is the record of *why* — the same convention this file
   already uses above `backlog_service_repo` once a product cuts over. Do not invent a reason the
   caller did not give.
3. **Report.** Confirm the field was written and that `backlog-service-migration-required` will no
   longer fire. Say explicitly that `legacy-backlog-format`, `legacy-section-schema` and
   `backlog-overdue-grooming` are **unaffected** and keep running: the product is staying on the
   file, so that file's format, schema and grooming hygiene matter more, not less.

**Reversing it** is a normal, unceremonious edit to a committed file — delete the `backlog_backend`
line, or set `backlog_service_repo` if the product does decide to migrate, which wins outright. There
is deliberately no `undecline-migration` verb.

### import <path>
Convert an external backlog file (`TODO.md`, `BACKLOG.md`, `ROADMAP.md`, `IDEAS.md`, a GitHub issue export, etc.) into structured items. **Always confirm before writing.**
1. Read the source file. Identify items by structure (markdown bullets, headings, issue-template fields).
2. For each, draft a `[PFX-XXXX]` entry: `source: user`, `status: open`, `area:` inferred from content, `stage:` inferred where possible (a vague one-liner → `idea`; a clearly-scoped bug → `ready`; leave unset if unclear → treated as not-ready). Effort/impact `?` when not inferable.
3. Show the preview; user confirms or edits. On confirm, append under `## Open` (optionally beneath a `<!-- Imported from <path> on <date> -->` marker), and **record `<path>` in the top-level `backlog_external_imports` fact** in `project-state.yaml` — this resolves the `external-backlog-detected` advisory for everyone on next sync.
4. Do not delete the source file (the user decides whether to remove it); recording it as imported is what stops the nag.

### dedup
*(Markdown backend — the grouping below walks `## Open`/`## Promoted` sections. Post-cutover,
`adapter-mode.md` routes the candidate scan to `cache-query search` per area cluster; steps 1b–3 are
backend-independent and still apply.)*
Surface likely-duplicate / overlapping items and propose merges. Idempotent and **never destructive** (bodies preserved; nothing deleted — a merge archives the superseded item via `closes:`).
1. Group `## Open` (and `## Promoted`) items by `area:`; within each group, find candidate pairs by title-keyword + body overlap. (The `add` subcommand already does dedup-on-create; this is the after-the-fact sweep.)
1b. **Then ask the altitude question of every group: "would a SINGLE change close all of these?"** This is a *shared-root-cause* test, not the duplicate test step 1 just ran, and the two come apart exactly where it matters: `crash on emoji` and `crash on UTF-16` share one cause and almost no keywords, so keyword overlap will never pair them. Over-splitting is a first-class failure alongside under-splitting (issue-standard §1) and this sweep is **the only place it can be caught** — no per-title lint can see it, because it is a fact *between* issues. It is also the more expensive direction: a split backlog looks more thorough, so nothing prompts a re-read. When the answer is yes, propose the **upleveled** item (`personas crash on character encoding`) as the survivor and fold the symptoms into it, rather than cross-linking them as relatives.
2. Present each candidate pair/cluster with both titles + IDs and a one-line "why these look related." Ask which to merge, keep separate, or skip.
3. On a confirmed merge: pick the surviving item, fold the other's body into it (preserve both — append the merged-in body under a `— merged from PFX-XXXX —` marker), set `related:`/`refs:` as appropriate, and `update <superseded> status=dropped` with `closes: <survivor>` recorded on the survivor. **On an ALTITUDE merge (1b), also `update <survivor> title=<upleveled title>`** — the survivor arrived carrying one symptom's title, so leaving it unchanged files the root cause under the name of one instance and re-creates the split the merge just closed. That retitle goes through the §1 refusal like any other, so the upleveled title must itself conform. Report what merged, and name any title changed.

### scrub (migration to GitHub Issues)
The **owner-confirmed cleanup** run once when a project moves its markdown backlog onto GitHub Issues through the backlog service (`prawduct-hook backlog <op>`). It surfaces stale/duplicate items *before* they become live issues (model proposes → owner confirms → the deterministic `status`/`merge`/`import` ops apply the cleaned set; the model is in the decision, never the data plane — MG4/G1). Distinct from `dedup`/`migrate` above, which edit `.prawduct/backlog.md` in place; this drives the service CLI and requires `gh`. **Full runbook: `migration-scrub.md`** (in this skill directory).

The scrub's high-consequence adapter ops — `import` (bulk-creates 100–250 issues), `merge`, `provision`, `reconcile-labels` — are **deliberately absent from this skill's `allowed-tools` grant**. The grant lists only the everyday ops (`file`/`get`/`status`/`update`/`comment`/`list`/`pick`/`counts`/`link`/`unlink`), so a scrub op surfaces a permission prompt at the moment it would write. That prompt is *defense-in-depth* on the one-time, owner-confirmed migration — the primary guard is **the runbook's own Step 0 target-repo selection + owner confirmation**, which every later step binds to — not the tools list (a skill `allowed-tools` is a no-prompt allow-list, not a hard cap). Do not "fix" the prompt by re-widening the grant.

**There is no adapter-side target guard, and you must not assume one.** `lib/backlog/` performs no repo-identity comparison anywhere: `ids.parse_repo` is *shape-only* (two clean segments — no allowlist, no owner constraint, no same-repo check) at all ten of its call sites, and no adapter op consults `backlog_service_repo` to validate a `--repo`. So `import --repo <any-valid-slug>` will write to whatever repo it is handed. The confirmation step **is** the guard; nothing beneath it will catch a wrong target. *(An adapter-side pin exists only in the `file-upstream` design — a different op, governing cross-owner **upstream filing**, not this migration.)*

## Triage method

GREAT triage so each project doesn't reinvent it. Run periodically (the janitor's Backlog Health step automates the surfacing). The moves, in order:
1. **Converge duplicates/overlaps** — run `dedup`; merge or cross-link (`related:`) near-duplicates so one canonical item carries the work.
2. **Link to the source of truth** — for any item whose requirement/arch/design is written down, set `refs:` to that doc (Issues backend: `update <id> --refs <doc>`, or `file --refs <doc>` to land it at creation); for item→item relationships use `link`/`unlink` (`related`) and `merge` (supersession), not a field write. A linked backlog is navigable; an unlinked one is a pile.
3. **Set the stage** — give each item a `stage:` (a vague item without one defaults to *not-ready* and won't be picked for implementation). Backfill `stage: ready` on bug/cleanup items, early stages on feature ideas. This is the single highest-value backfill on an existing backlog.
4. **Staleness review** — for `status: open` items unmoved >90d, decide: re-confirm (touch `reviewed:`), update with current context, or `status=dropped`. Aging out is fine; silting is not.
5. **Reconcile shipped work (fallback)** — the primary path is archiving an item as part of the work that closes it, at whichever moment "When to mark shipped" above specifies for the live backend; this step is the catch-net for items whose work shipped but were never archived. Move them to `status=shipped` (Archive). Never infer this from build plans/change-logs (D4) — it's an explicit human/agent call; the Critic/PR checks only *surface* candidates.

Triage is also how an existing project adopts new format features: the new fields are additive, so `migrate` (legacy→structured + strikeout cleanup + legend refresh) plus the steps above bring a messy backlog up to standard — no separate migration subsystem. The legend refresh is what keeps the documented schema from lagging the backfilled items (a backlog that gains `stage:`/`refs:`/`accepted-by:` on its items but never in its legend).

$ARGUMENTS
