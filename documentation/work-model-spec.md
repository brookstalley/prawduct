# Work Model — Implementation Spec

> ⚠️ **HISTORICAL — the runtime leg described here was deleted in v3.3.2.**
> The `UserPromptSubmit` orphan-term nudge (`prawduct-hook user-prompt-submit`, `build-index`, and
> the derived vocabulary index) no longer exists: the owner ruled 2026-07-12 (#257) that its
> resolution was deletion rather than a further precision fix, after its noise desensitized the one
> signal it existed to carry. Requirements-precede-code enforcement moved to the review-time
> `scope-trace:` question in the Critic and PR protocols (CRT-5M9J, #293). What survives of this
> design is `prawduct-hook jurisdiction` and `lib/work_model_index.jurisdiction_candidates`.
> This document is kept as the record of what was built and why — read it as history, not as spec.

> Spec (the *how it lands*) for the kernel in [`work-model.md`](./work-model.md). Revised after an
> independent confidence-check (verdict: *proceed after fixing blockers*; full notes at the end).
> Structured by the **confidence gate**: ship what we have high confidence in; defer the rest with
> the specific evidence that would unlock it. **Confidence: Medium-High on the ship-now core;
> deferred items are explicitly unproven.** Hook contracts re-verified against installed Claude
> Code at build.
>
> **Superseded in part by the delta analysis ([`work-model-delta.md`](./work-model-delta.md)):**
> references below to `${CLAUDE_PLUGIN_DATA}` and the B0 `watchPaths` probe are corrected there — the
> index lives in **`.prawduct/.work-model-index.json`** (prawduct's per-repo-state invariant), and
> the two unverified platform probes are dissolved. The delta is the build-ready source of truth.

## Ship now (high confidence)

### Part A — Prose / governance edits (the cheap kernel)

**A1 · Principle 6 gains a mirror clause.** `CLAUDE.md` (principles list) + `docs/principles.md`:
> *Requirements are maintained, not passed once.* Never silently **invent** a requirement as you
> never silently **drop** one (Principle 2). Building or designing a capability with no documented
> parent requirement is a defect; a requirement surfacing mid-build sends you back to write it.
- **Accept:** principle text carries the no-silent-invent clause; the session digest references it.

**A2 · `methodology/building.md` — tripwire callout + Confidence Check extension.** A "A requirement
surfaced mid-build" callout: the five tripwires (kernel §3a) + the triggered response (stop · name ·
write/locate the parent · resume). Confidence Check gains one line: *new domain vocabulary
introduced mid-build is an undocumented requirement.*
- **Accept:** the five tripwires appear verbatim, marked **triggered, not always-on**.

**A3 · `methodology/discovery.md` — "Calibrate Rigor" continuity sentence.** Re-run stakes ×
knowledge × volatility when the domain expands mid-work; a scope expansion resets knowledge-
confidence for the new surface.
- **Accept:** the sentence is present.

### Part B — The two ship-now hooks (SessionStart + UserPromptSubmit)

New subcommands on the existing `bin/prawduct-hook` entrypoint (match the current Stop/SessionStart
idiom), wired via the plugin's `hooks/hooks.json`. *(Verify entrypoint subcommand structure at build.)*

**B0 · Version probe (gates the rest of B).** Before claiming any B accept criterion, verify
against the installed Claude Code that `${CLAUDE_PLUGIN_DATA}` is writable and `watchPaths` fires;
design a **SessionStart-only fallback** so the index degrades gracefully (a doc added mid-session is
simply invisible until next session) rather than failing.
- **Accept:** a probe step records which capabilities are present; the hook works with or without `watchPaths`.

**B1 · Vocabulary declaration + index builder** (`prawduct-hook build-index`). Artifacts may declare
frontmatter `vocabulary: [term, …]`; absent that, a **conservative** auto-extract (heading terms +
bold defined terms only). Tuned for **few false positives**. Builds
`${CLAUDE_PLUGIN_DATA}/work-model-index.json = { vocab:[…] }` on SessionStart (and on `watchPaths`
change if present).
- **Accept:** adding a requirement with a `vocabulary:` term updates the index (live if watchPaths, else next session).

**B2 · SessionStart — parent map (durable, capped).** Append to the existing SessionStart
`additionalContext` a compact registry: **one line of scope per *governing* doc only** (not the full
artifact list — it shares the 10k digest budget). Durable; re-injected on `/resume`.
- **Accept:** a fresh session lists the governing artifacts + scope; the addition is capped (≤ N lines).

**B3 · UserPromptSubmit — the orphan-term nudge (keystone).** Reads the index; lowercases/stems the
prompt's salient nouns; if any are absent from `vocab` (and not in a common-word stoplist), injects
`additionalContext`: *"⚠ Terms not in any requirement: [X]. If this introduces new behavior, locate
or write the parent before designing (tripwire #1)."* **Injects nothing when clean.**
- **Honest scope (the confidence-check's key finding):** this is an **unfamiliar-token tripwire**, not
  a concept tripwire. It reliably catches new jargon / proper nouns / technical terms absent from the
  artifacts; it is **weaker on new concepts phrased in common English** (the original failure —
  "belief," "lie," "source" — was partly the latter). The salience filter + stoplist must be defined
  concretely enough to run, and ship with **false-positive-rate instrumentation** as a deliverable,
  not an aspiration.
- **Accept (the decisive gate):** a **replay of the real scriob mid-build prompt** that introduced the
  new domain dimension **fires the nudge**. *If it does not fire on the real case, the deterministic
  nudge is insufficient and we escalate to the LLM classifier (Part C) — this replay is the evidence
  that decides it.* Plus: a fully-covered prompt yields **no** injection.

**B4 · Plugin wiring.** `hooks/hooks.json` registers SessionStart + UserPromptSubmit → `prawduct-hook
<subcommand>` via `${CLAUDE_PLUGIN_ROOT}`; index in `${CLAUDE_PLUGIN_DATA}`.
- **Accept:** installing the plugin in a test repo activates both hooks with no user config.

## Part C — Deferred (confidence-gated — each names the evidence that unlocks it)

Per the confidence gate, these are **not yet high-confidence fixes**, so we validate before pouring
high work in. Deferring an unproven fix is the correct move, not a shortcut.

- **LLM-in-hook classifier** (`type:prompt`, concept-level — catches plain-word new concepts the
  deterministic nudge misses). **Unlocked by:** B3's real-case replay *failing* (proves deterministic
  is insufficient). Cost to weigh then: a fast-model call every turn — an ongoing per-session Visible Cost.
- **PreToolUse parent-coverage floor (B5) + the `boundary-patterns.md` glob-table data contract.**
  **New** capability + new authoring surface; `boundary-patterns.md` is empty by default (this repo's
  own copy is 100% template), so the floor matches nothing until seeded. **Unlocked by:** a seeded
  registry of common surfaces (style guide → `components/**`, schema → `migrations/**`, …) *and*
  confidence in the `glob → doc → severity` contract shape. Build it *for real with seeding* (the
  high-work right thing) — not an empty no-op.
- **Critic pre-code plan / parent-coverage review (A4).** **New** capability — today all four Critic
  modes need a git diff of code; a diff-less plan review doesn't exist. **Unlocked by:** designing the
  no-diff invocation path (how the Critic scopes against a plan artifact + its parent).

**Won't build:** an assistant-prose scanner — unsupported by the hook surface (no hook reads generated
prose); the named residual gap (caught at first-file-touch or next user turn instead).

## Part D — Adversarial self-review (the floor, dogfooded)

The make-or-break risk, named honestly after the confidence-check corrected me: **B3 is a jargon
tripwire, and I first sold it as a concept tripwire.** The two error directions trade off directly
against a string-diff — aggressive stoplist → misses plain-word concepts (the original failure);
permissive → fires constantly → muted → worse than nothing. *Mitigation:* the real-case replay gate
(B3 accept) forces us to confront which side the motivating case falls on **before** building
anything downstream; the LLM escalation is pre-designed for when it fails. Secondary risks:
`watchPaths`/`${CLAUDE_PLUGIN_DATA}` unverified (→ B0 probe + fallback); parent-map budget pressure
(→ B2 cap).

## Part E — Build chunking (thin slice first)

1. **Chunk 1 (keystone):** A1–A3 prose + B0 probe + B1 index + B2 parent-map + B3 nudge. Its gate is
   the **real-scriob-prompt replay** — proving the *catch*, not just the plumbing. Critic mode: `final`.
2. **Deferred (Part C), each behind its named evidence:** LLM classifier · floor + glob-table · Critic
   plan-review. None build until unlocked.

## Revision notes — what the confidence-check changed

Verdict: *proceed after fixing blockers.* Held: apparatus gone, external-enforcement (B2-prior),
silent-when-clean (B3-prior), SDD honesty (B4-prior), Calibrate-Rigor/Confidence-Check labels.
Blockers fixed here:
- **The Critic "reuse" was false** — no diff-less plan mode exists → relabeled **new capability**,
  deferred until the no-diff path is designed.
- **"boundary-patterns strengthened" was false** — it's prose and empty by default → relabeled **new
  data contract**, floor deferred until seeded.
- **The keystone was oversold** — it's a jargon tripwire, not a concept tripwire → reframed honestly,
  gated on the real-case replay, with the LLM classifier pre-designed as the evidence-unlocked upgrade.
