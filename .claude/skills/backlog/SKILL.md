---
description: Manage the structured product backlog — pick what to work on next, add/find/list/update items, and migrate legacy items. Use when the user wants to triage, file, or choose backlog work, or says /backlog.
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
- **Metadata bar**: one backticked dot-separated line. Required fields: `effort` (S/M/L), `impact` (S/M/L), `area`, `source` (builder|critic|reflection|janitor|user), `added` (YYYY-MM-DD), `status` (open|promoted|shipped|dropped). Optional: `related:` (related items), `closes:` (another backlog item this one supersedes — item→item), `closed-by:` (the chunk/release that shipped this item — item→release), `reviewed:`. Keep `closes:` and `closed-by:` straight — they point in opposite directions.
- **Sections**: `## Open` (pickable), `## Promoted` (in an active build plan), `## Archive` (shipped/dropped, kept for search). Items move between sections only via explicit `update` calls — never infer status from build plans or change logs.
- **Legacy items** (no metadata bar) are valid; treat them as `effort:? · impact:? · area:untagged · status:open` and rank them lower. Suggest `/backlog migrate` if there are many.

For today's date when stamping `added:`/`reviewed:`, use the current date from your environment context.

## Subcommands

Parse `$ARGUMENTS`: the first token is the subcommand (default to the no-arg summary if empty). Everything after is arguments — accept both `--flag=value` form (for machine callers like the Critic or reflection) and natural-language prose (for humans).

### (no args) — summary + menu
Read the file, then print: counts per section (`N open · N promoted · N archived`), the top 3 `area:` tags by item count, a count of stale items (`status: open` and `added`/`reviewed` >90 days ago), and the action menu (`pick`, `add`, `find`, `list`, `update`, `migrate`).

### add
File a new item. Accepts flags (`--title=`, `--body=`/`--body-file=`, `--area=`, `--effort=`, `--impact=`, `--source=`, `--prefix=`) or interactive prompts for anything missing.
1. **Dedup first.** Search existing items whose `area:` matches or whose title keywords overlap. If any exist, show the top ~3 (`[ID] title — status, added`) and ask: continue, update one of them, or cancel. (When called with complete flags by a machine caller, skip the prompt but still note overlaps in your result.)
2. On confirm, derive a prefix, generate a non-colliding `[PFX-XXXX]`, build the metadata bar (`source` defaults to the caller; `added` = today; `status: open`), and append the item under `## Open`.
3. Return the new ID and a one-line confirmation.

### find <query>
Plaintext + tag search across title, metadata, and body of **all** sections (and `backlog-archive.md` if it exists). Return matching `[ID] title — one-line summary`, most-relevant first. Keep it tight (a handful of results).

### list [--filter=...]
Tabular view: `ID · title · effort · impact · area · status`. **Default filter: `status=open` AND `added` within 90 days** (so a 200-item backlog doesn't dump). `--all` overrides; filter on any metadata field (`--area=`, `--status=`, `--effort=`, etc.). Sort by status then recency.

### update PFX-XXXX <field=value> [...]
Change metadata or body of one item. Common: `status=promoted|shipped|dropped` (moves the item to the matching section — `promoted`→`## Promoted`, `shipped`/`dropped`→`## Archive`), `area=`, `effort=`, `reviewed=`. On `status=shipped`, accept an optional `closed-by=<change-log tag or chunk id>` and write it into the **metadata bar** as `closed-by: <ref>` (not the body) for traceability. Always set `reviewed:` to today on any touch. Confirm the item exists first; if the ID isn't found, say so and suggest `/backlog find`.

### pick / migrate
Documented in their own sections below (added in later chunks). If invoked before they exist here, say the subcommand isn't available yet.

$ARGUMENTS
