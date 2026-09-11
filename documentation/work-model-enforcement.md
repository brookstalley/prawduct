# Work Model — Enforcement Surface (Claude Code hooks)

> ⚠️ **HISTORICAL — the runtime leg described here was deleted in v3.3.2.**
> The `UserPromptSubmit` orphan-term nudge (`prawduct-hook user-prompt-submit`, `build-index`, and
> the derived vocabulary index) no longer exists: the owner ruled 2026-07-12 (#257) that its
> resolution was deletion rather than a further precision fix, after its noise desensitized the one
> signal it existed to carry. Requirements-precede-code enforcement moved to the review-time
> `scope-trace:` question in the Critic and PR protocols (CRT-5M9J, #293). What survives of this
> design is `prawduct-hook jurisdiction` and `lib/work_model_index.jurisdiction_candidates`.
> This document is kept as the record of what was built and why — read it as history, not as spec.

> Research note feeding [`work-model.md`](./work-model.md). Answers the kernel's open question
> *"floor as hook vs. agent pre-flight?"* — and review-finding **B2** (*"name the external
> enforcement surface, or admit this is a prompt intervention"*). Source: Claude Code specialist
> pass against installed **v2.1.154** (features through ~v2.1.166). **Confidence: Medium** — exact
> contracts/version-gates to be re-verified at build time.

## The reframe

The kernel needs checks that fire **externally and deterministically**, not by the producing
agent's goodwill (the v1 failure). Claude Code **hooks** are precisely that: guaranteed
lifecycle points, structured JSON in/out, run by the harness — not the model. So the kernel's
enforcement is **hooks**, and the prose tripwires become a *backstop*, not the mechanism.

## Capabilities that matter (verified against current docs)

| Hook | What it gives us | Contract highlight |
|---|---|---|
| **UserPromptSubmit** (pre-turn) | Inspect the user's prompt **before** the model sees it; inject `additionalContext` for that turn; optionally block. **Conditional on prompt content.** | `{hookSpecificOutput:{additionalContext}}`, ≤10k chars, 30s budget |
| **PreToolUse** | See `tool_name`+`tool_input` (Write/Edit target path **and** content); `deny`/`ask`/`allow`; inject reason; scope by matcher. | `permissionDecision: ask\|deny` + `additionalContext` |
| **SessionStart** | **Durable** `additionalContext` (re-injected on `/resume`); `watchPaths` to re-scan on file change; `reloadSkills`. | durable; v2.1.152+ for watchPaths |
| **`type:"prompt"` hook** | A hook can **be a fast-model call** — "LLM-in-a-hook" — and inject its verdict. | `{type:"prompt", model, timeout≤30}`, billed, non-recursive |
| **Plugin hooks** | Prawduct ships all of the above via `hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}` scripts, `${CLAUDE_PLUGIN_DATA}` persistent state. | all events; same trust as user hooks |

**Hard limit (defines our residual gap):** *no* hook reads the **assistant's generated prose**
into the transcript or can block on it (`MessageDisplay` is display-only, can't block). So pure
design-in-chat — a taxonomy invented in prose that touches no file — cannot be caught
*in the same turn* deterministically.

## Layered design (mapped to the kernel)

- **L0 · SessionStart — the parent map (durable).** Extend the existing briefing to inject a
  compact registry of governing artifacts: each vision/requirements/spec doc, its one-line
  scope, and its declared vocabulary/surface. Parents become **ambient from turn 1**.
  `watchPaths: [.prawduct/artifacts/]` keeps it live as docs are added.
- **L1 · UserPromptSubmit — the locate nudge (the user's idea, made real).** A script diffs the
  prompt's salient nouns against the maintained artifact-vocabulary index. **Only when** it finds
  unmatched salient terms does it inject: *"⚠ Terms not in any requirement: [belief, lie,
  sincerity]. If this is new behavior, locate/write the parent before designing (tripwire #1)."*
  Fires on the **prompt**, before any file is touched. **Silent when clean** → dodges the B3
  rubber-stamp critique (it's signal, not an always-passing check).
  - *Precision layer (review-fixes Chunk 2, 2026-06-09):* live use showed the bare vocab-diff
    fired on ordinary English ("thanks, looks good") and harness notifications, training the
    model to ignore the one real catch. Three shipped refinements (`lib/work_model_index.py`):
    a **common-English frequency floor** (`lib/common_words.py` — top-4,000 words never flag),
    a **firing threshold** (`should_fire` — requirement-shaped prompt, or ≥ 2 orphans; bare
    questions/acks/harness-injected content never fire), and a **widened corpus** (CLAUDE.md,
    `docs/`, `methodology/` feed the index alongside `.prawduct/artifacts/`). Accepted recall
    trade: a requirement phrased entirely in floor words ("add payment support") stays silent —
    the documented gap the optional upgrade below would close.
  - *Optional upgrade (`type:prompt`):* a fast-model hook asks "does this introduce a concept not
    in the attached artifact summary?" — the "light LLM floor," now **external** (in the hook),
    not self-administered. Gate it behind the cheap keyword pre-filter to bound cost.
- **L2 · PreToolUse on Write/Edit — the mechanical parent-coverage floor.** When a write targets
  a surface `boundary-patterns.md` marks governed (e.g. a UI component when a style guide exists)
  with no evidence the parent was consulted → `permissionDecision:"ask"` + reason. This is the
  *button-blue* case: editing the button triggers the style-guide check. Deterministic, external,
  non-rubber-stampable (it's a lookup).
- **L3 · Stop — existing Critic/reflection gate** (unchanged), optionally a soft session-end
  audit ("new vocabulary introduced this session that never reached a requirement?") via the
  v2.1.166 *additionalContext-without-block*.

**State:** maintain the vocab index / parent map in `${CLAUDE_PLUGIN_DATA}`, rebuilt by a hook on
`watchPaths` change — so per-turn injection is a cheap read, not a full re-parse (respects the
30s/10k budgets).

## Proportionality — what to actually build (resisting a second over-build)

- **Build now (high confidence):** L0 parent-map + L1 deterministic nudge — both cheap, signal-only.
  Note the honest scope: L1 is an **unfamiliar-token** tripwire (catches new jargon), weaker on
  plain-word new concepts; ship it gated on the real-case replay.
- **Deferred — confidence-gated (each unlocked by named evidence):** L2 PreToolUse floor (unlocked
  by a *seeded* `boundary-patterns.md`); the L1 `type:prompt` **LLM upgrade** (unlocked by the
  real-case replay showing the deterministic nudge insufficient).
- **Don't build:** an assistant-prose scanner — unsupported by the hook surface, and would be noisy.

## The honest residual gap

Deterministic enforcement catches the new requirement **(a)** when it appears in the user's
prompt (L1) and **(b)** the moment it touches a governed surface (L2). The irreducible miss is a
**single turn of pure-prose design** the agent originates itself and never persists — caught at
*first-file-touch* (L2) or *next user turn* (L1), but not mid-prose. That is the limit of the
current hook surface, and it is a far smaller window than v1's "rely on the agent noticing."
