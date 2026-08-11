# The Work Model — Catching Undocumented Requirements

> ⚠️ **HISTORICAL — the runtime leg described here was deleted in v3.3.2.**
> The `UserPromptSubmit` orphan-term nudge (`prawduct-hook user-prompt-submit`, `build-index`, and
> the derived vocabulary index) no longer exists: the owner ruled 2026-07-12 (#257) that its
> resolution was deletion rather than a further precision fix, after its noise desensitized the one
> signal it existed to carry. Requirements-precede-code enforcement moved to the review-time
> `scope-trace:` question in the Critic and PR protocols (CRT-5M9J, #293). What survives of this
> design is `prawduct-hook jurisdiction` and `lib/work_model_index.jurisdiction_candidates`.
> This document is kept as the record of what was built and why — read it as history, not as spec.

> **Status: kernel (v2).** Supersedes the v1 apparatus — preserved verbatim at
> [`work-model-v1-archive.md`](./work-model-v1-archive.md) — after a research pass
> ([`work-model-prior-art.md`](./work-model-prior-art.md)) and an independent adversarial review
> ([`work-model-review.md`](./work-model-review.md)) returned *"do not proceed — rework to the
> kernel."* The review caught the v1 author scaling the fix to the *emotional weight* of the
> failure rather than its *causal surface*. This is that rework. **The fix is small, and almost
> nothing in Prawduct changes** — see the reconciliation table (§4).

## 1. The problem (the part that survived review)

In a real session, an agent deep in build mode met a new domain dimension the user raised
mid-build. It did a full, fluent domain-model *design in conversational prose* and would have
flowed it straight into code — with no requirements artifact in between. The *user*, not the
framework, caught it three times over.

Two things made the framework blind to this:

- **It governs artifacts and code, not the conversation** where a fluent agent does its most
  seductive ungoverned design. Inventing a taxonomy in chat *feels like helpfulness* and trips
  no gate.
- **It polices requirement *loss* but not requirement *absence*.** Complete Delivery (Principle
  2) forbids silently *dropping* a requirement and is enforced hard. There is no mirror clause
  forbidding silently *inventing* one — building or designing a capability whose requirement was
  never written.

> **The compact statement:** Prawduct treats requirements as a gate you pass through once on the
> way into building, not a property you maintain — and it governs artifacts and code, not the
> conversation where the most seductive ungoverned design happens.

**The failure is narrow and local** — one missing principle clause and no external trigger — not
a missing governance framework. Scaling the fix beyond that *is itself* the gold-plating the
framework exists to prevent (Principle 11).

## 2. Why "more process" is the wrong fix

The first attempt (v1) built a 5-altitude ladder, two depth dials, and a per-change "locate"
step that ran on *every* change. The independent review killed it for reasons worth keeping
visible, because they constrain the real fix:

- It **re-derived machinery Prawduct already has** (size×type, Calibrate Rigor, the Confidence
  Check, the 4-tier independence) under new names, without saying what it *retired* — two
  overlapping governance systems.
- Its **always-on check would be rubber-stamped.** A check that always passes teaches the
  checker to stop looking — manufacturing the *exact* "rode along approvingly" reflex of the
  original failure.
- It **wouldn't have fired.** A self-administered locate relies on the agent *noticing* — and an
  agent enchanted enough to invent a taxonomy in chat is not, in that same turn, in a state to
  honestly check it. **The fix must be externally enforced, not self-administered.**

So the real fix has exactly two requirements: **minimal** (add only what's missing) and
**external** (caught by something other than the producing agent's goodwill).

## 3. The kernel — three changes

### 3a. Close the asymmetry (one principle clause + tripwires)

Give Principle 6 / Complete Delivery a mirror clause:

> **Never silently *invent* a requirement, as you never silently *drop* one.** Building or
> designing a capability that has no documented parent requirement is a defect. Requirements are
> *maintained*, not passed once — a requirement surfacing mid-build sends you back to write it,
> not forward into design.

Operationalize it with **tripwires** (a `building.md` callout) — the agent-specific part, and
the one piece with no clean prior-art name. When any fires, *stop, name it, write or locate the
parent requirement before designing against it*:

1. A user message introduces a **noun / rule / entity the current artifacts don't contain.**
2. You're about to produce code or design you **can't trace to a line one rung up.**
3. You catch yourself **designing in chat** — a taxonomy, data model, or category set that lives
   in no artifact.
4. You've **revised the same thing 2–3×** (churn = unstable parent).
5. The user says **"are we sure / is this solved / solid ground / don't want to reinvent."**

This is *triggered*, not always-on — that's what keeps it proportional (Principle 11).

### 3b. The external check — a tiered plan-critic (the enforcement surface)

Tripwires still rely on the agent noticing. The reliable catch for an *enchanted* agent is
external eyes on one question: **does this change have a parent it should be honoring?** Run it
as two tiers so it is cheap by default and expensive only when it pays:

- **Floor — mechanical parent-coverage detection (every change, near-zero cost).** A
  deterministic lookup, *not* a judgment: does a governing artifact exist for this change's
  surface? It reads `boundary-patterns.md` / the artifact registry / known doc locations (style
  guide, design brief, schema, API contract…). Output: candidate parent(s), or "this surface is
  ungoverned."
  Because it's a lookup it **can't be rubber-stamped** (the property a self-check lacks), it
  costs almost nothing, and it's **external** to the producing reasoning.
  *Example — "make the button blue":* the floor checks for a style guide / design system. Found
  → consult it (or escalate to check the change against it). None → proceed, and record that the
  surface is ungoverned.
- **Escalation — adversarial judgment (only when triggered).** Fires when the floor finds a
  candidate parent (does the plan actually honor it?), when a tripwire fired, or when
  stakes / lock-in / blast-radius warrant. This **adds a new pre-code plan / parent-coverage
  review goal to the Critic** — today all four Critic modes are scoped to git diffs of *code*, so
  a diff-less plan review is **new capability**, not a reuse (it extends the Critic rather than
  inventing a separate reviewer, but it is not free). *Confidence-gated — deferred until the
  no-diff invocation path is designed; see the spec.*

**Resolved design decision (vetoable assumption):** detection is **mechanical**, judgment is the
**escalated LLM** pass. The split is deliberate — mechanical detection satisfies "external +
non-rubber-stampable + cheap"; the costly independent judgment is spent only where a parent
actually exists or stakes demand. The floor's quality ceiling is whatever `boundary-patterns.md`
knows about — and that registry is **empty by default**, so the floor is **confidence-gated and
deferred** until seeding earns it (the UserPromptSubmit nudge ships first and alone).

**The detection layer is implemented as Claude Code hooks** — the actual external enforcement
surface (resolves §5). The harness, not the agent, runs them: a **UserPromptSubmit** hook injects
a pre-turn nudge *only when* the prompt contains a term no artifact covers (signal, not an
always-passing check); a **PreToolUse** hook surfaces the governing doc when a write targets a
governed surface; a **SessionStart** hook injects the durable "parent map." Full design and the
honest residual gap (no hook reads the assistant's own prose): [`work-model-enforcement.md`](./work-model-enforcement.md).

### 3c. Adopt the canon's vocabulary; don't reinvent

The research pass showed the skeleton is established prior art — adopt its names, cite them, and
do not mint parallel ones:

| What we were tempted to invent | Its established name |
|---|---|
| the altitude ladder | the **V-model** left arm |
| the "parent test" | **requirements traceability** |
| rigor = stakes × knowledge × volatility | **spiral / Cynefin** (already Prawduct's *Calibrate Rigor*) |
| the independence spectrum | the **Fagan-inspection / IV&V** hierarchy (already the *Critic*) |
| the agent-era ladder as a whole | **Spec-Driven Development** (GitHub Spec Kit / Kiro) |

The **only** novel claim we keep is the agent-specific layer: **design-in-chat blindness**, the
**tripwires**, and **external parent-coverage enforcement.** (Honest caveat: "design-in-chat
blindness" was not found named in a targeted web pass — not proof it's unnamed.)

## 4. Reconciliation — what changes vs. what stays

The B1 demand, and the proof the kernel is small. Almost everything is unchanged.

| Existing Prawduct construct | Disposition |
|---|---|
| **Principle 2 — Complete Delivery** | **Unchanged** — it's the mirror we cite. |
| **Principle 6 — Requirements Precede Code** | **Extended** — add the no-silent-invent clause + "requirements are maintained, not passed once." |
| **size × type classification** (`building.md`) | **Unchanged** — the v1 "rung-vector" replacing it is dropped. |
| **Calibrate Rigor** (stakes × knowledge × volatility) | **Unchanged** — this *is* the depth dial; one added sentence that it re-runs when scope expands mid-build. |
| **Confidence Check** (3 questions, `building.md`) | **Extended** — add the tripwire callout + "new domain vocabulary mid-build = an undocumented requirement." |
| **Decision Research / Boundary Investigation** | **Unchanged.** |
| **The Critic** | **Extended (new capability)** — gains a pre-code plan/parent-coverage review goal; today all four modes are git-diff-scoped, so a diff-less plan review is new. *Confidence-gated → deferred.* |
| **`boundary-patterns.md`** | **New data contract** — gains a machine-readable `glob → doc → severity` table (today it's prose; empty by default → must be seeded). The floor's quality ceiling. *Confidence-gated → deferred until seeded.* |
| **4-tier independence** (already in `discovery.md` / the Critic) | **Unchanged** — applied to the plan-critic. |
| **Claude Code hooks** (SessionStart · UserPromptSubmit · PreToolUse) | **New** — the external enforcement surface: parent-map injection · vocab-diff nudge · parent-coverage floor ([`work-model-enforcement.md`](./work-model-enforcement.md)). |
| v1's 5 rungs · 2 dials · rung-vector · always-on locate · null-note | **Dropped.** |

Net: one principle clause **extended**, two existing checks **extended** (Calibrate Rigor,
Confidence Check). **Ships now (high-confidence):** the prose edits + two deterministic hooks
(SessionStart parent-map · UserPromptSubmit nudge). **Confidence-gated → deferred** until evidence
earns them: the PreToolUse floor + the new `boundary-patterns.md` data contract, the Critic's new
plan-review capability, and the LLM-in-hook upgrade. v1's apparatus **dropped**. Nothing is
retired except our own over-build.

## 5. Open questions / deferred

- **Floor reach.** How much can `boundary-patterns.md` realistically cover? That's the floor's
  quality ceiling and the honest limit of the mechanical approach.
- **Floor as hook vs. pre-flight.** *Resolved: hooks.* The deterministic parts run as Claude Code
  UserPromptSubmit / PreToolUse / SessionStart hooks (external, harness-run) — see
  [`work-model-enforcement.md`](./work-model-enforcement.md). The residual limit: no hook reads
  the assistant's own prose, so a single-turn pure-prose design is caught at first-file-touch or
  next user turn, not mid-prose.
- **Re-check this kernel.** v2 still owes at least an adversarial self-review + a quick
  independent pass on the reconciliation table before the spec/diff step — *without* repeating
  the v1 over-build.

## 6. Next step

Spec altitude — see [`work-model-spec.md`](./work-model-spec.md): the exact edits (Principle 6
text, the `building.md` tripwire callout + Confidence Check extension, Calibrate Rigor's
scope-expansion sentence, the Critic's plan-mode fronting) **plus** the `hooks/` design (the three
scripts, their JSON contracts, the artifact-vocabulary/governed-surface data contract, and
`${CLAUDE_PLUGIN_DATA}` state) — then plan → implement with per-chunk Critic.
