# Issue #1063 — governance: an Evidence transport preference so a product can opt out: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-10-31 · source: critic (PR review of feature/1052-evidence-transport) · issue: https://github.com/brookstalley/prawduct/issues/1063`

Related: #1050 (evidence transport), #1052 (review facts travel as git notes), #1061 (transport polish), `plugin/methodology/building.md` ("Opinionated defaults without configuration").

## Problem

Review facts travel between clones on `refs/notes/prawduct`. Four places touch that ref and none can be switched off:

| Site | What it does | Where |
|---|---|---|
| `/prawduct:pr create` / `update` | `prawduct-hook evidence sync` (fetch, merge, ingest, **push**) | `plugin/skills/pr/SKILL.md` |
| `/prawduct:onboard` | `evidence configure --apply` (notes fetch refspec, `notes.rewriteRef`) | `plugin/skills/onboard/SKILL.md` |
| doctor check #25 | recommends `evidence configure --apply` | `plugin/skills/doctor/SKILL.md` |
| SessionStart | `_session_start_ingest` → `evidence_notes.ingest(bound=True)` | `plugin/bin/prawduct-hook` |

A product whose remote admits pushers it does not trust for governance has facts arriving that its verdicts will compose over (inbound), and pushes review history it may not want to publish (outbound). Today its only recourse is "do not run those steps by hand", which cannot cover the automatic ones (session-start ingest, the PR skill's steps). `building.md` says a workflow-affecting feature that could reasonably work two ways is a `project-preferences.md` preference with a safe default.

## Goals

- G1. One switch, in `project-preferences.md`, that turns evidence transport off for the product.
- G2. Default is unchanged: absent row, absent file, and `on` behave exactly as today.
- G3. `off` means no read from and no write to `refs/notes/prawduct` by prawduct, and no git config written on its behalf.
- G4. Local evidence is unaffected: the store, verdicts and gates compose over this clone's own facts exactly as they do for a repo with no remote.

## Non-goals

- Per-step granularity (sync on, ingest off). One switch only.
- Filtering inbound notes by author — no filtered ingest exists; separate decision.
- Removing an existing notes ref or already-ingested facts when the row flips to `off`.
- Changing what transport carries.

## Requirements

- R1. **The row.** `- **Evidence transport**: on | off (default: on — …)` under `## Workflow` in `plugin/templates/project-preferences.md`, in the house style of its neighbours. Values `on`/`off`, case-insensitive.
- R2. **One reader.** A single function maps `read_preference_row(project_dir, "Evidence transport")` (`plugin/lib/core.py`) to a boolean, and every site in R3–R6 calls it. Parsing the row anywhere else is a defect (the reader docstring already states this for consent gates).
- R3. **Fail-safe on the unreadable cases.** Absent row / absent file → `on` (G2). Unreadable file, or a value that is neither `on` nor `off` → **`off`** for the *write* side (sync push, configure) and a visible note; the direction of the failure is toward not publishing. Open question Q2 covers the read side.
- R4. **Session start.** With `off`, `_session_start_ingest` returns before touching git and prints nothing, or one line `evidence transport: off (project-preferences.md) — notes not ingested` so the absence of the "N evidence fact(s) ingested" line is explained (Q3).
- R5. **Sync and ingest commands.** `prawduct-hook evidence sync`, `evidence ingest` and `evidence configure --apply` with `off`: exit 0, change nothing, print that transport is off and name the row. They are guarded in the library, not only in skill prose, so a hand-run or a stale skill cannot bypass the switch. (A skill-prose-only guard is the weakest form: it must be recalled at the right moment.)
- R6. **Skills.** `pr` (Create Step 5 and Update), `onboard` and doctor #25 each state the row, say they skip the step when it is `off`, and report the skip in one line rather than silently. Doctor #25 under `off` reports "transport off by preference" and is not a finding.
- R7. **Security model.** The security-model override clause for inbound trust names `Evidence transport: off` as the switch. Open question Q1: the clause is not in `plugin/templates/security-model.md` or any `plugin/docs/` file in this checkout — locate it (likely the evidence-transport build plan or #1050's design) before editing, or this requirement adds the clause where the model is defined.
- R8. **Onboard/doctor preferences.** The onboard preference interview offers the row only when a remote exists (no remote, nothing to transport); it is not asked of every product.
- R9. **Tests, each red-verified against current code:**
  - (a) `off`: `pr` sync path pushes no `refs/notes/prawduct` (assert on a bare remote's refs).
  - (b) `off`: session start with a notes ref present ingests zero facts and does not call `evidence_notes.ingest`.
  - (c) `off`: `evidence configure --apply` writes no config keys.
  - (d) absent row and `on`: behaviour identical to today (existing tests stay green, unmodified).
  - (e) unreadable preferences file → write side skipped, per R3.
  - (f) a docs-agreement test: every file naming `evidence sync` / `evidence configure` also names the row (the mechanical form of "the three skills' prose names the row").

## Acceptance (from the issue, tightened)

- [ ] With `off`, a PR create pushes no notes ref and a session start reads none (R4, R5, R9a–b).
- [ ] The pr, onboard and doctor skills name the row (R6, R9f).
- [ ] The security-model override clause points at the row (R7).
- [ ] Default behaviour is byte-for-byte unchanged (R9d).

## Open questions for the owner

- Q1. Where does the security-model override clause live? Not found under `plugin/` here; confirm the home before R7 is built.
- Q2. Unparseable value: fail to `off` on both sides (strictest — a typo silences transport and the product loses cross-clone facts without noticing) or to `on` on the read side (today's behaviour, but an operator who meant `off` is ingesting)? Recommendation: `off` both sides plus a doctor finding, because the row exists to protect a trust boundary.
- Q3. Should `off` at session start print its one-line explanation every session, or stay silent? Recommendation: silent, with doctor #25 as the one place that reports state, to avoid a line per session for a deliberate setting.
- Q4. Does flipping to `off` after facts were ingested need a purge? Recommendation: no (non-goal); ingested facts are already in the local append-only store and are indistinguishable by trust.

## Next step

On Q1–Q4, write the design: the transport-enabled helper's home (`core.py` next to `read_preference_row`), the guard placement in `evidence_sync.sync` / `configure` / `evidence_notes.ingest_cmd`, and the doctor/onboard prose edits.
