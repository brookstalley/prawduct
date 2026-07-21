# Work Model — Prior Art Record

> Research note feeding [`work-model.md`](./work-model.md). Answers its biggest open question:
> *how much of this is already named prior art we should adopt rather than reinvent?*
>
> **Status:** canon-mapping arm complete (intrinsic knowledge — stable, pre-cutoff SE/PM
> theory). **Volatile/web arm pending** — how AI coding agents are governed in 2025–2026 is
> post-cutoff and fast-moving; those claims are listed under "To verify via web," not asserted
> from memory.

## Construct-by-construct mapping

| Our construct | Closest named prior art | Verdict |
|---|---|---|
| **The 5-altitude ladder** (vision→requirements→spec→plan→code) | The **V-model** (left arm = decomposition by abstraction level); RUP/iterative phase structure | **Adopt the framing.** This is the left arm of the V. We are not inventing the ladder. |
| **Traceability backbone** ("does it have a parent one rung up?") | **Requirements traceability** / the Requirements Traceability Matrix (RTM); bidirectional traceability in DO-178C, ISO/IEC 29148 | **Adopt the vocabulary.** "Trace to a parent" is the established term. Our "parent test" is a lightweight RTM check. |
| **Every produce-rung paired with a check** (vertical + horizontal) | The **V-model's right arm** (each level has a corresponding verification); **shift-left** testing | **Adopt.** The V-model already pairs each abstraction level with its own verification. |
| **Research dial, biased on; knowledge vs. volatility** | The Agile **"spike"** (timeboxed research task); **set-based / last-responsible-moment**; the distinction maps loosely to **Cynefin** (clear→complex needs probing) | **Adapt.** Spikes are the named unit; our knowledge-vs-volatility split (reason vs. web) is a sharpening, not in the canon verbatim. |
| **Rigor scaled to stakes × knowledge × volatility** | **Cynefin** (Snowden) — match response to domain complexity; risk-based / **risk-driven** development (Boehm's spiral); tailoring in PMBOK | **Adopt the principle.** "Match rigor to risk" is spiral/Cynefin. Our 3-factor formula is a concrete tailoring rule. |
| **Independence spectrum** (self → adversarial → shared → isolated) | **Inspection/review hierarchy** (Fagan inspections; walkthrough < review < inspection); **independent V&V (IV&V)**; ATAM (independent architecture evaluation) | **Adopt + sharpen.** The review-rigor hierarchy is classic; our explicit 4-point spectrum with an *adversarial-self-review floor* and the "isolation is the value" rationale is a useful concretization. |
| **The locate function** (per-change rung-vector; enter at altitude) | **Progressive elaboration / rolling-wave planning** (PMBOK); **process tailoring** per change; **change-impact analysis** | **Adapt.** Impact analysis answers "what does this touch"; our contribution is making it a *mandatory, always-run, vetoable* front-step that outputs an altitude. |
| **The return edge** (ascend-repair-redescend; non-waterfall loop) | **Iterative/incremental** development; **feedback loops** in spiral; the whole anti-waterfall tradition (Royce's *own* point) | **Adopt the principle, own the trigger.** "Go back up" is iterative dev 101. What's *not* in the canon: the concrete **tripwires** for an agent to *notice* it must ascend. |
| **"The decision is the deliverable / no silent skips"** | **Design rationale** capture (IBIS, QOC); **Architecture Decision Records (ADRs)**; "definition of done" | **Adopt + extend.** ADRs record decisions made; our extension is recording the decision *not* to act ("no doc needed, and that's fine") — the null result. Less common in practice. |
| **size × type as a scalar proxy** (prawduct today) | Process tailoring by project class | (Internal — the thing we're replacing with the vector.) |

## What this means

**Most of the skeleton is named, established prior art — and we should adopt its vocabulary
rather than mint our own.** The ladder is the V-model's left arm; "parent test" is
traceability; paired checks are the V-model's right arm; "match rigor to risk" is
spiral/Cynefin; the independence spectrum is the inspection hierarchy + IV&V; ascending is
just iterative development. Renaming these in prawduct's voice while *citing* the canon will
make the framework more credible and less likely to be seen as reinvention.

**The genuinely novel contribution is agent-specific and narrow — and it's the valuable part:**

1. **Design-in-chat blindness.** The canon assumes design produces *artifacts* that reviews can
   inspect. None of it anticipates a fluent agent producing a complete, compelling design *as
   conversational prose* that trips no artifact-based gate. Naming this failure mode — and
   treating chat-design as a produce-event subject to the parent test — appears to be ours.
2. **Concrete ascent tripwires for an autonomous agent.** Iterative dev says "loop"; it does not
   say *how an agent notices, in the middle of building, that it has silently left its altitude.*
   The tripwire list (new domain noun, no traceable parent, taxonomy-in-chat, 2–3× churn,
   "are-we-sure" signals) is the operational novelty.
3. **The continuous altitude invariant in an LLM loop** — unifying locate (prospective) and the
   return edge (continuous) as *one* maintained property, rather than discrete phase gates,
   fits an agent's turn-by-turn loop better than stage-gate's discrete checkpoints.

> **Bottom line for the model:** we are *not* reinventing the process model — adopt the canon's
> names. We *are* contributing a small, sharp, agent-specific layer (chat-design blindness +
> ascent tripwires + the continuous invariant). Research has done its job: it shrinks our
> "novel" surface to exactly the part that's actually new, and prevents us from re-deriving
> traceability and the V-model under house names.

## Relationship to Spec-Driven Development — the key web finding

The volatile arm surfaced the single most important fact for positioning this model:
**the agent-era incarnation of our ladder already exists, is named, and is mainstream.** It is
**Spec-Driven Development (SDD)**, and as of mid-2026 it has a dominant tool — **GitHub Spec
Kit** (launched Sept 2025, ~90k stars, 30+ agent integrations), plus AWS **Kiro** and planning
modes in JetBrains/Cursor. Spec Kit's four gated phases — **Specify → Plan → Tasks →
Implement** — are *our ladder minus Vision*, and its thesis ("specifications do not serve code;
code serves specifications") is our traceability backbone. **We must position relative to SDD
and adopt its vocabulary where it fits — not mint a parallel one.**

But the *more* important finding is what practitioners say SDD gets **wrong** — because our three
genuinely-novel pieces map almost exactly onto SDD's three biggest published criticisms. This is
the strongest possible validation: independent critics complaining about SDD are describing the
holes our model fills.

| SDD's published weakness (2025–2026) | The work-model piece that fixes it |
|---|---|
| **Overhead for small changes** — "a single-line bug fix should not trigger a full spec generation pipeline." A mandatory phase pipeline over-taxes small tasks. | **The locate function + D2.** Enter at altitude; a trivial change is a *recorded null note*, not a full pipeline. Variable-altitude entry is precisely the cure. |
| **Rigid for evolving requirements** — "for exploratory development with evolving requirements, context-driven approaches adapt better." SDD is phase-forward and waterfall-ish. | **The return edge + continuous altitude invariant.** Non-waterfall by construction; ascend-repair-redescend when a lower rung teaches a higher one. |
| **Spec drift** — "specs drift because everyone can update them, but nobody reconciles." | **Coherence / re-cascade + the through-line.** Changes cascade down on re-descend; the decision (incl. the null result) is always recorded. (Still our weakest answer — see open questions.) |

> **Revised positioning:** the work-model is **"SDD plus the three things SDD is criticized for
> lacking"** — variable-altitude entry, continuous re-entry, and anti-drift coherence — *plus*
> the Vision rung SDD omits. That is a far stronger and more honest framing than "a new model."

## Independence — web confirms D4 and adds a sharper reason

The builder/validator split is **standard practice** for code review (Greptile, codex-auto-
review, multi-agent critic panels with a deduplicating coordinator — which is *already*
prawduct's Critic-coordinator pattern). Two findings sharpen our rationale:

- **"A reviewer that wrote the code is always fighting its own context"** / the validator
  "receives only the diff… no knowledge of the original task framing." → verbatim support for
  *isolation is the value* and the isolated-independent rung.
- **A deeper reason than we had:** "criticizing code sharply requires contradicting itself,
  which most models are architecturally inclined to avoid." There is an *architectural* bias in
  LLMs against self-contradiction. This strengthens both the **adversarial-self-review floor**
  (self-critique is hard precisely because the model resists it, so it must be *forced*) and the
  case for genuine independence at stakes. Worth adding to `work-model.md` §2B.

What is *not* yet standard, so our contribution holds: applying the independence spectrum to the
**upper rungs** (independent review of *requirements/spec*, not just code), and —

## Design-in-chat blindness — appears genuinely unnamed

SDD's motivating villain is **"vibe coding"** (loosely-prompted, code-first generation). That is
*not* our failure mode. Our failure — a fluent agent producing a complete, compelling *design*
as conversational prose that produces no artifact and trips no gate — was **not found named** in
this pass. (Honest caveat: a targeted 4-search pass, not exhaustive; absence of evidence ≠
proof.) Provisional verdict: **this specific framing is our contribution**, and it's worth
checking once more in the independent-review/deep-research step.

## Confidence on the web arm

**Medium.** This was a proportional targeted pass (4 searches, search-summary depth, no deep
source reads). It is enough to *sharpen and reposition* the model now; it is **not** enough to
*ratify* it. Before ratification, the independent-review step should deep-read the primary
sources (Spec Kit's `spec-driven.md` and constitution mechanism; Martin Fowler's SDD-3-tools;
the arXiv "Code to Contract" paper) and confirm the design-in-chat gap.

**Sources:**
[GitHub Spec Kit](https://github.com/github/spec-kit) ·
[Spec Kit four-phase process (GitHub Blog)](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) ·
[Thoughtworks — SDD unpacking 2025](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices) ·
[Martin Fowler — Kiro, spec-kit, Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) ·
[The Limits of Spec-Driven Development (Isoform)](https://isoform.ai/blog/the-limits-of-spec-driven-development) ·
[Why SDD Breaks at Scale (Arcturus Labs)](http://arcturus-labs.com/blog/2025/10/17/why-spec-driven-development-breaks-at-scale-and-how-to-fix-it/) ·
[SDD: From Code to Contract (arXiv)](https://arxiv.org/pdf/2602.00180) ·
[Builder/validator & multi-agent review (MindStudio)](https://www.mindstudio.ai/blog/automated-code-review-multiple-ai-agents)
