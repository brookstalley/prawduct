# Backlog Service — GitHub Issue Structure Standard

`status: draft v1 — 2026-07-17. Web-researched (current-GitHub-verified) + owner-decided. prawduct AND
every consumer product create issues through this standard; issues must be clear, atomic, appropriately
labeled, and short by construction. Source: pre-sign-off research (Chunk 06 dry-run surfaced the need).
· stage: design`

**Parent:** PRD §8.9 (migration restructure pass) + the `file` creation path. This standard is a
**requirement** the `file` serializer, the migration serializer, and the linter all implement. It must
itself model the brevity it demands.

## Why

SPIKE-S2's live dry-run showed migrated titles taken verbatim from backlog bullets read as run-on
em-dash detail-dumps — simultaneously too verbose *and* under-informative. Root cause: the markdown
bullet conflates title with a one-line-carries-everything summary; GitHub issues want **title = handle,
body = detail**. prawduct and all consumers will create thousands of these, so the bar is *awesome
issues*: brevity, clarity, specificity.

## 1. Title

- **Budget ≤ 72 chars** (aim 50–70). Over budget is **blocking** per the §4 amendment once #614
  lands, advisory until then — the number is the same either way; only the posture changed. **Shape: `area: specific summary`** — lowercase area
  prefix, then a noun-phrase stating *what failed + where* (bug) or *what to do* (task).
- **One atomic problem — and atomicity is a property of the FIX, not of the sentence.** The test is
  one question: **would a single change close all of these?** If yes they are one issue written at
  too low an altitude; if no they are separate issues that happen to share a scene.
- **Splitting is the failure in one direction, and the standard used to name only that one.**
  - *Under-split* → a title joining two claims with **independent fixes** (`—`/`;` is the usual
    tell) → split (net-new) or flag for manual split (migration — see §5).
  - *Over-split* → sibling titles differing only in a noun that names an **instance of a category**
    → uplevel to the category. `personas crash on emoji` + `on unicode` + `on UTF-16` are one
    defect: `personas: crash on non-ASCII character encoding`. Three issues, one fix, three times
    the triage — and the root cause is stated nowhere.
  - Being wrong in this direction is the more expensive error: a split backlog looks *more*
    thorough, so nothing prompts a re-read, while an under-split one is loud the moment someone
    tries to close it.
- **Only the under-split direction is visible from a single title.** Over-splitting is a fact
  *between* issues, so no per-title lint can catch it. **Nothing screens for it today** — say this
  plainly rather than delegating to a mechanism that does not exist: the dedup/merge sweep
  (`skills/backlog/SKILL.md`) pairs on *title-keyword + body overlap*, which is a **duplicate**
  test, and the two come apart exactly here — `crash on emoji` and `crash on UTF-16` share a root
  cause and almost no keywords. Adding the shared-root-cause question to that sweep is the
  intended home and is **unbuilt**. Until it exists, over-splitting is caught by a human reading
  the backlog or not at all, and the migration scrub must therefore look across the corpus rather
  than rewriting items one at a time in isolation.
- ✅ `importer: PFX alias read-resolution unwired, breaks import idempotency` (69)
- ❌ vague (`Bug in the thing`), non-specific (`Fix backlog`), em-dash chains of ≥2 claims, or a
  family of near-identical titles that one fix would close.

## 2. Body

Fixed sections, per-section budget, **~175 visible words**; evidence over budget goes in a fenced block
or `<details>` (progressive disclosure). Original imported text is preserved out-of-band (§5), so
restructuring loses nothing.

**Bug:** Problem (≤25w, what+where) · Repro/input (≤5 lines) · Actual (≤2 lines) · Expected (≤2 lines)
· Evidence (`file:line`, log/stack in fence/`<details>`, ≤10 visible lines) · *(recommended)* Env (1 line
— **the product version it was found in** + any relevant environment, e.g. `prawduct v3.1.0 (plugin)`; a
self-filed bug that records its version is far cheaper to triage, so a bug with no Env line gets a
WARN-only lint nudge — never a block).

**Task/Feature:** Problem/motivation (≤25w, why + user-visible outcome) · Proposed change (≤4 bullets)
· Acceptance (verifiable `- [ ]`, ≤5) · Scope-out (≤2 lines) · *(opt)* Evidence/links.

## 3. Labels — already built, keep

The adapter already models the recommended taxonomy: `kind/area/effort/impact/source` open facets +
`stage`/`status` closed enums, each a `<facet>:value` namespaced label, one color per facet
(`lib/backlog/encode.py:70`, `lib/backlog/provision.py:30`). No redesign. Rules:

- **≤ ~5 loud scan labels:** `kind`, `area`, `stage`, `status`, `impact`. `effort`/`source` are
  filter-only (`source` lives in the `prawduct:` body block, not a visible label).
- **`kind:` is under-populated today** — the migration pre-pass and `file` going forward must assign it
  (bug/feature/task/chore/spike).
- Name is load-bearing, not color; a human may recolor freely.

## 4. Enforcement — two homes, one standard

**Amended 2026-08-06 (owner ruling) — the TITLE lints block; everything else stays WARN-only.**
This section previously read "WARN only, never blocks" for all lints. Owner: *"we need to enforce
on migration. fine if the agent has to rewrite. They must be EXCELLENT issue titles, always,
whether migrated or created new or modified."* The old posture and that directive cannot both
hold, and the directive supersedes: a WARN the migration path never even called is what let a
396-item corpus reach GitHub with titles up to 2319 characters.

**Scope of the amendment, deliberately narrow.** Blocking applies to the four **§1 title** checks
(`title-too-long` / `-too-short` / `-placeholder` / `-non-atomic`) on all three write paths
(`file`, `update`, `import`). The **body** lints — `body-too-long`, missing sections, the Env
nudge — stay WARN-only: a title is the handle every later reader triages by and is cheap to
rewrite, while a body budget blocking an edit to an unrelated field is the confirmation-fatigue
shape `security-model.md`'s approval norm already rejects. **Not yet built** — tracked as **#614**,
which also carries the co-shipping constraint (the shared-root-cause check in the dedup sweep must
land with it, or enforcing ≤72 alone entrenches an over-split backlog; §1).

> **Implemented (programmatic home):** `lib/backlog/issuefmt.py` — `normalize_title` (§1),
> `render_body` (§2 composer, shared with migration), and `lint` (§4). **`lint` is WARN-only in
> code today** — `issuefmt.py` says so by construction and no caller blocks on it. The 2026-08-06
> amendment below makes the title checks blocking as a *ruling*; wiring it is **#614**. This
> blockquote states what is built, so it must not borrow the amendment's tense. Wired into the
> `file` path (`core.file_item`): the title is normalized on create and the result is audited, with
> findings in the envelope's `lint` field (advisory today; blocking for title findings once
> #614 lands). The **MG6 migration pre-pass (§5) is
> implemented** — `lib/backlog/restructure.py` (fail-closed plan validation, application through
> the shared composer, `original_*` preservation per Data Model §2) + `import --restructure` +
> the offline `restructure-preview` owner-review artifact. Issue Forms (consumer-UI home,
> BKL-7F3D) remain to build.

- **`file` CLI + migration (programmatic):** a standard-aware **serializer** emits the title + section
  contract; the linter audits — **title findings block, body findings warn** once #614 lands
  (advisory on every path today). Issue *Forms* do NOT gate programmatic creation.
- **Consumers filing via the GitHub UI:** ship **YAML Issue Forms** (`.github/ISSUE_TEMPLATE/`, one per
  variant; required `textarea`s = the sections, `dropdown`s pin `kind/area/stage/impact`). Forms require
  labels to pre-exist — `provision` already creates them.
- **Linter — §1 title checks BLOCK per the 2026-08-06 ruling (wiring: #614); all other lints WARN
  only:** title > 72 / < 15 / placeholder; title joins ≥2 claims **→ blocking**. Missing or empty required
  section; > ~175 visible words (`issuefmt.BODY_MAX_WORDS` — the one implementation constant, §2's
  number and this threshold are the same budget); unwrapped evidence > 30 lines; no `kind:`/`area:`; > ~6 labels;
  acceptance prose without `- [ ]`; a `kind:bug` issue with **no Env line** (`bug-missing-env` — the
  product-version-provenance nudge; recommendation, not a mandate).

## 5. Migration application (owner decision 2026-07-17 → "restructure, preserve, no split")

A **single LLM pre-pass**, part of the MG4 scrub, **before the deterministic import (no model in the
data plane)**. Per item:

1. Propose a ≤72 `area:`-prefixed **title** and a template-structured **body**; assign `kind:` if missing.
2. **Preserve the original verbatim** — `original_title:` / `original_body:` in the `prawduct:` block,
   *plus* the MG2 export backup. Nothing is lost; a bad rewrite is recoverable.
3. **Do NOT auto-split.** A non-atomic (multi-claim) item is **flagged for owner manual split** as a
   scrub decision (splitting deliberately mints new IDs). This keeps **1 PFX = 1 issue** (MG1/MIG-2).
4. Owner reviews the restructured set **in aggregate** (a representative sample + the full before/after
   diff artifact), approves the batch — **not** per-item HITL (does not scale to hundreds).
5. Deterministic import writes the **confirmed** set.

**MG1 contract revision:** "bodies preserved verbatim" → **"bodies restructured to this standard;
original preserved verbatim in `original_body` + the export backup."** IDs/sections still preserved.

## 6. Native features (verified GA) — structure *between* issues

- **Sub-issues** (GA 2025, ≤100/parent, 8 levels; portable): use for genuine parent→child decomposition,
  not subtasks-in-a-body.
- **Issue dependencies** (blocked-by/blocking, via `gh` CLI 2026): use for true ordering blockers; keep
  soft `related:` as-is. *(Exact GA date unpinned — verify before building on it.)*
- **Native issue types/fields** are a better model but **org-gated / non-portable** to personal-account
  consumer repos → **namespaced labels remain the interoperable baseline**; org consumers MAY additionally
  promote `kind:`→native type. *(Portability call is synthesis, not a GitHub prescription.)*

## Confidence ledger

- **GitHub-documented fact:** issue-forms field types + label-preexistence; sub-issue GA/limits; issue
  type/field GA + org-scope; dependency CLI availability.
- **Synthesis / judgment (not a GitHub spec):** the 72-char title budget (git-subject convention +
  observed list truncation); the section/word budgets; labels-over-native for portability; lint thresholds.
- **Not a causal claim:** "shorter issues resolve faster" — evidence supports *element presence*
  (repro/stack), not brevity itself. Brevity's justification here is **scan/triage cost + atomicity.**

Sources: GitHub best-practices discussion #147722 · Evolving Issues GA #154148 · gh CLI changelog
2026-06-10 · issue-forms syntax + template-config docs · sub-issues / issue-types / issue-fields docs ·
SE-EDU labels guide · Sane GitHub Labels · bug-report-elements (Springer s10664-020-09882-z; QRS2016).
