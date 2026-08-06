---
artifact: discovery
scope: backlog-import-title-boundary
source: incoming-bugs/backlog-import-aborts-whole-run-on-one-oversized-title.md (discodon, 2026-08-06)
last_validated: 2026-08-06
---

# Backlog import: the title boundary, and the two guardrails that should have contained it

## 1. The problem, observed

A 396-item markdown→Issues migration in **discodon** created 27 issues in 55 seconds and then
died at item 28 with a GitHub **422**, and **no amount of resuming advances it** — the failure is
deterministic and position-ordered. The run is permanently pinned at 7%.

Two layers, and the loud one is not the real defect:

- **Layer 1 (the blocker).** GitHub caps issue titles at 256 characters. The importer passes
  titles through unbounded and treats a per-item 422 as fatal for the *entire* migration.
- **Layer 2 (the cause).** `legacy._parse_title_line` has **no title boundary at all**. It strips
  `~~` and `**` and returns the whole bullet line. Where a product authors title and body prose on
  one line, the "title" is title + provenance + areas + the entire body paragraph.

## 2. What the numbers actually say — measured, not inferred

The report could not characterise 342 of 396 lines and explicitly warned against trusting its
regex. Re-derived here against both real corpora:

| | pending | titles >256 | max title | median |
|---|---|---|---|---|
| discodon | 401 | **55** | **2319** | 148 |
| prawduct (this repo) | 197 | **6** | 336 | 155 |

**This repo has the same defect latent** — 6 of its own items would be rejected by GitHub today.

**But this repo's long titles are genuine.** `MET-4P9C`'s 336 characters are one authored
statement, not prose bleeding in. discodon's are not. There is therefore **no single
authored-title boundary across products**, and any rule that truncates on length alone would
damage the working shape to fix the broken one.

## 3. The boundary rule, derived from the data

discodon's line shape is:

```
- **[CI-L0SB]** (orig #980, pr-reviewer 2026-05-10) Move activity token-generation into
  `activity/package.json` build script. [areas: ci, frontend, deploy] The v2.1.0 ranch deploy…
```

The title ends at the **`[areas: …]` marker**. The rule is: strip the leading `[ID]`, strip a
leading `(orig …)` / `(from …)` provenance parenthetical, and cut at an inline `[areas:|tags: …]`
marker if one is present. Otherwise leave the line alone.

Measured effect:

| | >256 before | >256 after | max before | max after |
|---|---|---|---|---|
| discodon | 55 | **1** | 2319 | 260 |
| prawduct | 6 | 6 | 336 | 325 |

`CI-L0SB` — the exact item that killed the run — goes **1055 → 73 characters**:
`Move activity token-generation into `activity/package.json` build script.` That matches the
authored title the reporter measured at 72.

**The rule repairs the shape that carries the marker and does not touch the shape that does
not**, which is the property that makes it safe to ship to a fleet whose authoring conventions
differ. `[areas:` appears on 100 of discodon's 401 items and **0** of prawduct's.

## 4. The correctness question that gates the whole fix — resolved

Changing a title changes the *record*, so the first question is whether it changes the
**idempotency key** and turns a resumed import into a duplicating one.

`ImportRecord.key_label()` (`migrate.py:559-567`) answers it:

- An item **with a PFX** keys on `ids.alias_label(self.pfx)` — the `id:PFX` label.
  **Title-independent.** Fixing the title cannot change the key.
- An item **without a PFX** falls back to `import-key:<sha256(title + body)>` —
  **title-dependent.** For those, fixing the parser would silently mint a new key and duplicate.

**Measured: 0 of 401 discodon items and 0 of 197 prawduct items lack a PFX.** The duplicate
hazard is real in the schema and **absent from the live data**, so the fix is safe to ship — but
it must be guarded by a test rather than left to luck, because a PFX-less item is legal.

`_find_by_key` searches `state="all"` (`migrate.py:1048-1054`), so the **27 already-created,
now-closed** issues *are* matched. That answers the report's worry about a silent 27-item
coverage gap: they will be skipped, not duplicated — which is exactly what makes the owner's
recorded ruling (**retitle-in-place on skip**) the repair path for their polluted titles, without
needing the delete permission the operator structurally cannot hold on a user-owned repo.

## 5. Scope

**In scope**, in dependency order:

1. **The boundary rule** in `legacy.py` — the actual repair. Must not change `BacklogItem.title`'s
   meaning for existing consumers without checking them; prefer a derived value the import path
   reads, so the briefing's display string is a separate decision.
2. **A length cap with overflow to the body** — 1 discodon item and 6 prawduct items still exceed
   256 after the boundary fix. Truncation must move the remainder into the issue body, never
   discard it.
3. **Pre-flight validation** — report every over-length item *before* the first write, so a bad
   corpus fails in the first second with a list rather than 7% in with issues already created.
4. **Per-item failure isolation** — a 422 records that item and continues. One malformed row must
   never end a 396-row migration.
5. **Retitle-in-place on skip** (owner ruling) — repairs issues already written with polluted
   titles, including closed ones.

**Out of scope, recorded not forgotten:**

- The rollback/run-manifest design from the report's companion defect (`import --rollback`,
  digest-key release, permission pre-check). Real, and a separate decision — it changes the
  import's data model.
- The three smaller observations in the report (progress counter disagreeing with item count,
  unexplained `1 collision(s)`, the stale advisory count frozen at first-seen).

## 6. Open assumptions

- `[areas:` / `[tags:` is the only inline end-of-title marker in the fleet. Verified against two
  corpora; **not** verified against the other ~24 sibling repos. A third corpus should be sampled
  before this is called general.
- The single remaining discodon title at 260 characters is assumed to be a genuinely long
  authored title rather than a second unhandled shape. Not individually inspected.
