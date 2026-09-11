# Work Model — Delta vs. Current Prawduct (ship-now core)

> ⚠️ **HISTORICAL — the runtime leg described here was deleted in v3.3.2.**
> The `UserPromptSubmit` orphan-term nudge (`prawduct-hook user-prompt-submit`, `build-index`, and
> the derived vocabulary index) no longer exists: the owner ruled 2026-07-12 (#257) that its
> resolution was deletion rather than a further precision fix, after its noise desensitized the one
> signal it existed to carry. Requirements-precede-code enforcement moved to the review-time
> `scope-trace:` question in the Critic and PR protocols (CRT-5M9J, #293). What survives of this
> design is `prawduct-hook jurisdiction` and `lib/work_model_index.jurisdiction_candidates`.
> This document is kept as the record of what was built and why — read it as history, not as spec.

> The diff between the spec's **ship-now core** ([`work-model-spec.md`](./work-model-spec.md) "Ship
> now") and current prawduct, file by file. This is the bridge to the build plan. Deferred items
> (LLM classifier, PreToolUse floor, Critic plan-review) are out of scope here until their evidence
> unlocks them. **Fix-everything-where-confident:** every delta below is rated; the high-confidence
> ones are build-ready.

## Corrections the delta surfaced (spec assumptions that don't survive the architecture)

Grounding the spec against the real codebase corrected three things — and *raised* confidence by
deleting two unverified platform dependencies:

1. **Index home: `${CLAUDE_PLUGIN_DATA}` → `.prawduct/.work-model-index.json` (gitignored).**
   Prawduct's load-bearing invariant (`hooks/digest.py` docstring; v2.0.0 design §2): *the plugin
   ships immutable, read-only code; ALL mutable per-repo state lives in
   `${CLAUDE_PROJECT_DIR}/.prawduct/`.* The vocab index is derived from **this repo's** artifacts —
   per-repo state — so it belongs in `.prawduct/` alongside `.critic-findings.json`, built by a
   `prawduct-hook` subcommand. The spec's plugin-data choice violates the invariant. **Corrected.**
2. **B0's `watchPaths` / `${CLAUDE_PLUGIN_DATA}` probe → dissolved.** Because the index is cheap
   per-repo state rebuilt by our own hook, we rebuild it on SessionStart (and refresh-if-stale on
   UserPromptSubmit) — **no dependency on the unverified `watchPaths` or `${CLAUDE_PLUGIN_DATA}`
   platform features.** Two unknowns removed → the ship-now core is *more* confident, not less.
3. **Parent-map (B2) cannot live in the static, budget-bound digest.** `methodology/session-digest.md`
   is plugin-bundled, immutable, and **token-budget-pinned** (`tests/test_v5_methodology.py::test_token_budget`
   = 3120). The parent-map is *dynamic per-repo* content → it must be injected by a hook that reads
   the repo's registry and appends to `additionalContext` (extend `hooks/digest.py`), **not** added
   to `session-digest.md`. The static one-liners (A1/A2) *do* count against the 3120 budget → fit by
   trimming (the test's own guidance: "prefer trimming over raising").

Two hard requirements every new hook inherits from the existing ones (`digest.py`, `banner.py`,
`cmd_stop`): **(a) gate on `.prawduct/` existence** (the plugin is user-scoped — fires in every repo;
ours must stay silent in non-prawduct repos) and **(b) fail-soft** — wrap in try/except so a hook
error never breaks session start or prompt submission (the `prawduct:allow prawduct/broad-except`
waiver pattern, `digest.py:81`).

## Per-item delta

| Item | Current state | Target | Delta | Confidence |
|---|---|---|---|---|
| **A1** Principle 6 mirror clause | `docs/principles.md §6` (line 24) + `CLAUDE.md` §6; Principle 2 (the mirror) exists at §2 | §6 gains no-silent-invent clause; 1-line ref in the digest | edit principles.md §6 + CLAUDE.md §6 + 1 line in `session-digest.md` (**budget-fit ≤3120**) | **High** |
| **A2** Tripwire callout + Confidence Check | `building.md` "Before You Build: Confidence Check" (L37–45); no tripwire callout | callout w/ 5 tripwires + triggered response; +1 line in Confidence Check; +1 digest line | edit `building.md` + `session-digest.md` (budget-fit) | **High** |
| **A3** Calibrate Rigor continuity | `discovery.md` "Calibrate Rigor…" section | +1 sentence (re-run on scope expansion) | edit `discovery.md` | **High** |
| **B1** Vocab decl + index builder | artifacts carry frontmatter (`artifact/version/scope`); no `vocabulary`; no index; `bin/prawduct-hook` dispatches subcommands via `lib/` | optional `vocabulary:`/`governs:` frontmatter; new `prawduct-hook build-index` → **`.prawduct/.work-model-index.json`** (gitignored); conservative auto-extract fallback | new `lib/work_model_index.py` + subcommand; gitignore the index; document frontmatter in artifact templates | **High** (mechanism); efficacy gated by B3 replay |
| **B2** SessionStart parent-map | `digest.py` injects static budget-bound digest; reads only plugin root | append a **dynamic, capped** parent-map (governing docs + 1-line scope) read from the repo registry (`.prawduct/artifacts/` + `project-state.yaml`) | extend `digest.py`: read repo registry, append ≤N lines to `additionalContext`, gate on `.prawduct/`, fail-soft | **High** |
| **B3** UserPromptSubmit nudge (keystone) | **no UserPromptSubmit hook** in `hooks.json` | new hook → `prawduct-hook userpromptsubmit`: read index, diff prompt nouns vs vocab, inject nudge only on orphan terms, silent when clean, gate on `.prawduct/`, fail-soft, refresh index if stale | new `hooks.json` entry + subcommand + `lib/` logic; **real-scriob-replay test as the gate**; FP instrumentation | **High** (plumbing); catch-efficacy gated by replay |
| **B4** Plugin wiring | `hooks.json`: SessionStart (banner, digest, `clear`) + Stop | + UserPromptSubmit entry; index build on SessionStart (extend `clear` or add a build-index hook) | edit `hooks.json` | **High** |

**Confirmed deferred (not in this delta):** the PreToolUse floor — `.prawduct/artifacts/boundary-patterns.md`
is prose with an empty "## Contract Surfaces" (verified), so the floor would match nothing until seeded.

## New test coverage (mirror existing patterns)

- `build-index`: index correctness, auto-extract conservatism, writes to `.prawduct/` (not plugin),
  `.prawduct/`-gating. Mirror `tests/test_plugin_methodology_digest.py`.
- UserPromptSubmit nudge: orphan term → nudge; clean prompt → **no** injection; non-prawduct repo →
  silent; hook error → fail-soft (no exception escapes).
- **The real-scriob-prompt replay** — the decisive value test (does the nudge fire on the actual
  motivating case?).
- Parent-map cap + `session-digest.md` budget (`test_token_budget` stays green after A1/A2).

## Resulting build plan (→ `.prawduct/artifacts/archive/build-plan-work-model.md`)

- **Chunk 1 (keystone, Critic `final`):** B1 index (in `.prawduct/`) + B2 parent-map + B3 nudge +
  A1–A3 prose, gated on the **real-scriob-replay** + the budget test. Proves the catch end-to-end.
  *(B0 probe dissolved — no platform-feature spike needed.)*
- **Deferred, each behind its named evidence:** LLM classifier · PreToolUse floor + seeded
  boundary-patterns · Critic plan-review.

## Confidence summary

The delta **raised** confidence on the ship-now core: relocating the index to `.prawduct/` removed the
two unverified platform dependencies the spec leaned on, and the path it uses (`prawduct-hook` writing
`.prawduct/`) is the framework's established, tested write surface. Every ship-now delta is now
**high-confidence and build-ready**, except B3's catch-efficacy — which is, by design, gated on the
real-case replay rather than assumed.
