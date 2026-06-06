<!-- ───────────────────────────────────────────────────────────────────────────
  SUPERSEDED — v1 apparatus, preserved as history of the exploration.
  The live model is the kernel in ./work-model.md. This version was cut after the
  independent review (./work-model-review.md) returned "do not proceed — rework to the
  kernel": it re-derived existing Prawduct machinery and added an always-on per-change
  locate step that would have been rubber-stamped and could not fire on an enchanted agent.
  Kept verbatim because the diagnosis (§1) and the exploration are worth the record.
──────────────────────────────────────────────────────────────────────────── -->

# The Work Model — How Prawduct Should Govern Any Change

> **Status: draft requirements model — not yet ratified, not yet diffed against the
> current methodology.** This is the "how it should work" view, captured so we can
> research it, review it independently, and *then* diff it against prawduct's existing
> principles and methodology guides. It is the parent artifact the eventual framework
> changes will trace to. Confidence: **Medium** — see "Requirements Confidence" at the end
> (this document is pre-research and pre-independent-review by its own standard).

---

## 0. Locate decision for *this* document (dogfooding)

Before anything else, the model demands we locate the change this document represents —
"rework prawduct to embody the work model" — on its own ladder. We do that here, in the
open, as the first act:

| Rung | State | What the model demands |
|---|---|---|
| **0 · Vision** | check-against | One explicit pass: does this *serve* prawduct's purpose, or quietly redefine it? Flag if it sharpens the vision rather than just implementing it. |
| **1 · Requirements** | **modify — entry altitude** | This document *is* the requirements statement. → **research-biased** + **isolated-independent check** before propagating. |
| 2 · Spec | modify (later) | How it lands: which methodology files, which principles, the session briefing, the hooks, whether "locate" becomes a skill/checklist. |
| 3 · Plan | modify (later) | Chunked build plan for the framework changes. |
| 4 · Implementation | modify (later) | Edit the files; per-chunk Critic. |

**Entry altitude: Requirements.** Two facets are owed *before* we descend toward spec/edits,
and an earlier draft of this plan skipped both — the discipline caught its own author:

1. **Research (bias-on).** Stakes are high (this reshapes the framework; everything will
   trace to it; over-building is a live risk) and producer knowledge-confidence is *medium*.
   This is almost certainly a partially-solved problem, and "don't reinvent the solved thing"
   is the exact lesson that motivated this model. Research splits along the knowledge/volatility
   seam: **canon mapping** (V-model, stage-gate, requirements traceability, progressive
   elaboration, design-rationale capture, shift-left, Cynefin — largely intrinsic) and
   **volatile/web** (how AI coding agents are governed in 2025–2026 — post-cutoff, mandatory).
2. **Independent review.** The producer of this model is maximally invested in a fluent,
   compelling, in-chat design — the textbook highest-independence case, where self-review is
   worthless.

**Corrected order:** capture (this doc) → research (both flavors) → independent review →
vision check-against → diff against prawduct → plan → implement with per-chunk Critic.

---

## 1. The problem this solves

In a real session (the `scriob` product), an agent was deep in **build mode** — executing
chunk 1 of a ratified build plan. The user introduced a genuinely new domain dimension
mid-build (modeling belief vs. truth, lies, conflicting multi-party claims, in-world vs.
canonical sources). The agent responded *well in substance* — it did not charge into code,
it held the build and launched research — but the real miss was subtler and more instructive:

**It performed a full domain-model design in conversation — fluently — and would have flowed
it straight into implementation, with no requirements artifact in between.** Requirements were
being invented and consumed in the same breath. And it was the *user*, three times over, who
raised the new dimension, pumped the brakes, and finally named the failure: *"I've led us into
bad process. None of this should be ad hoc, all of this should be documented requirements."*
The framework rode along approvingly each time. It never originated the "stop — these are
undocumented requirements" move, which is one of its core promises.

Why the framework didn't fire it:

- **Requirements-first was a one-time entry gate with no return edge.** The build cycle flows
  strictly forward (baseline → spec → tests → implement → verify → Critic → reflect). A
  requirements-shaped signal arriving mid-cycle had nowhere to route except *into* the chunk
  already underway. There was no edge from BUILD back to DISCOVER.
- **The framework governs artifacts and code — it is blind to design performed in
  conversation.** The Critic reviews files; the Stop hook gates on code-vs-findings. Nothing
  watches an agent inventing a taxonomy in chat. And this is the sharpest point: *a highly
  capable agent's failure mode isn't skipping design — it's doing brilliant design in chat,
  which feels like helpfulness and trips no gate.* The better the agent, the more seductively
  this hides.
- **Rigor calibration was front-loaded to discovery and never re-evaluated when scope
  expanded.** The signals (high stakes, low knowledge-confidence on a specialist domain,
  "isn't this a solved problem") all screamed research-before-design — but that trigger lives
  at the *start* of work, and a scope expansion mid-build never reset it.

The root asymmetry: the framework forbids silently *dropping* a requirement (Complete
Delivery) and enforces it hard. **There is no counterpart forbidding silently *inventing*
one** — building or designing a capability whose requirements were never written. It detects
requirement *loss* but not requirement *absence*.

> **The compact statement:** Prawduct treats requirements as a gate you pass through once on
> the way into building, not as a property you continuously maintain — and it governs
> artifacts and code, not the conversation where a fluent agent does its most seductive
> ungoverned design.

---

## 2. The model

Three dimensions, bound together by one through-line.

### 2A. The ladder — five altitudes

Every change lives somewhere on a hierarchy of abstraction. Each rung is *justified by and
consistent with* the rung above it:

| Altitude | Produces | "Research" facet | "Check" facet |
|---|---|---|---|
| **0 · Vision** | the product thesis: who, why, what "good" means | scan the problem space / analogues | does this still serve the vision? |
| **1 · Requirements** | what it must do — behavior, constraints, qualities | prior art, "is this solved?", standards | complete? consistent with vision? |
| **2 · Spec** | the *how*: architecture, data model, tech choices, interfaces | tech research, benchmarks, cautionary tales | satisfies the requirements? |
| **3 · Plan** | chunked build plan, sequence, acceptance criteria | — | covers the spec? thin-slice-first? |
| **4 · Implementation** | code + tests | boundary / decision investigation | Critic — does the code meet the chunk? |

Each rung has three facets — **produce**, **research**, **check**. "Research X / document X"
pairs collapse into one rung where **research is a rigor mode of producing that rung, not a
separate rung** — and when engaged it emits a persisted artifact (a research note / prior-art
record) that feeds the produce step.

Two load-bearing properties:

- **Traceability is the backbone.** Code traces to a chunk traces to spec traces to a
  requirement traces to vision. The artifacts are not bureaucracy — they are the *links*. This
  gives a sharp test for "is documentation needed?", far better than "is it big?":
  **does this change have a parent one rung up?** "Make the button blue" has a parent (the
  button exists for a documented reason) → no new doc. "Model belief/lies/truth" has *no parent
  requirement* → a new rung-artifact is mandatory.
- **Every produce-rung is paired with a check.** The check is always two things —
  **vertical** (consistent with the rung above) and **horizontal** (complete and coherent
  within itself). This generalizes Independent Review and Validate-Before-Propagating up the
  *whole* ladder, not just code.

### 2B. Depth — a vector, two dials

Depth is **per rung, not global** (a Postgres→graphdb migration is deep at Spec but light at
Requirements; the belief model is deep at Requirements then standard below). And it is two
dials, not one:

**Research depth** — driven by **knowledge-confidence × volatility.**
- Low confidence → reasoning/canon research. High volatility (fast-moving / post-cutoff) →
  *web* research, mandatory (intrinsic knowledge is stale there by construction).
- **Biased ON (D1):** default toward research under *any* doubt, or when stakes merit it —
  where "stakes" explicitly includes wasted time, data loss, **and over-building** (research is
  often what *prevents* gold-plating, not just what costs effort).

**Review depth** — a 4-point **independence spectrum**, cheapest → most expensive:
1. Self-review — re-read your artifact against the rung above.
2. **Adversarial self-review** — actively try to *refute* your own design. The **floor**:
   every check is at least this (D4). Near-zero cost, surprising yield.
3. Independent, shared context — a reviewer who didn't produce it but can see the thread.
4. Independent, isolated context — forked agent, fresh context, restricted tools (the Critic).

What independence buys (the inputs to the judgment):
- It closes the **"I saw it but the artifact doesn't say it"** gap — the author knows what they
  *meant*; an independent reader sees only what's *there*.
- **No sunk-cost / commitment bias** — a reviewer with no ego in the artifact kills it more
  readily.
- **Isolated context can't import the same blind spot** — shared context = shared assumptions
  = shared gaps. The isolation *is* the value.
- **Models are architecturally biased against self-contradiction** (web-confirmed): "criticizing
  code sharply requires contradicting itself, which most models are inclined to avoid." This is
  *why* the adversarial-self-review floor must be forced rather than assumed, and why genuine
  independence earns its cost at stakes — a reviewer that wrote the artifact is fighting its own
  context.

The signals that climb the dial: **lock-in / reversibility / blast-radius**, **how much will be
propagated onto this artifact**, **how invested/iterated the producer is**, **how long the
producing context has run**. And the **counterintuitive rule that should drive it:**

> Independence matters *most* exactly when the producer is most confident and most invested —
> which is precisely when self-review is *least* trustworthy. A boring mechanical change
> self-reviews fine; a fluent, compelling, self-generated design is the *highest*
> independence-priority, not the lowest. Self-review is trustworthy on the dull and
> treacherous on the inspired.

### 2C. Locate + the return edge — one continuous invariant

This is the dimension whose absence caused the failure.

**The locate function** runs for *every* change, before doing anything, and computes a **vector
over the rungs** — each rung in one of three states — plus a research-depth and review-depth on
each non-skip rung:

- **modify** (produce/update this artifact) · **check-against** (constraint only) · **skip**

Two decisive rules:
1. **A change enters at its altitude — the highest rung it modifies — not the rung you're
   currently standing on.** The failure was standing at Implementation when a Requirements-level
   change arrived, and processing it where you stood.
2. **Bias to glance upward, because the asymmetry is brutal.** Ascending is cheap (write a
   paragraph of requirements); discovering mid-build that you're building something with no
   parent is the expensive thrash. So the upward glance runs *every* time.

**Locate always runs — even for trivial changes (D2).** For a trivial change the output is a
recorded note, *including the null result*: *"button color wasn't specified in the spec, and
it's fine not to specify it."* The locate output is **surfaced and vetoable** (infer-confirm-
proceed): *"I read this as a Requirements-altitude change — it has no parent requirement today,
so I want to document that before we design against it. Veto?"* That one sentence is precisely
what was needed at the moment of failure — and it is a *natural output of the locate function*,
not a special "stop" gate bolted on.

**The return edge** is the same invariant, mid-flight. The ladder is not a waterfall — a lower
rung constantly teaches you about a higher one. When it does, you ascend. The hard part is the
**trigger**, because the failure is precisely *not noticing*. Concrete tripwires:

- A user message introduces a **noun/rule/entity the current artifacts don't contain**. New
  domain vocabulary ≈ new requirement.
- You're about to produce code or spec whose justification you **can't point to a line one rung
  up.**
- You catch yourself **designing in chat** — inventing a taxonomy, data model, or category set
  that lives in no artifact.
- You've **revised the same thing 2–3×** (churn = unstable parent).
- The user says **"are we sure / is this solved / solid ground / don't want to reinvent."**

The mechanic, proportional not dramatic:
1. **Suspend** the current rung.
2. **Locate the highest implicated rung.**
3. **Ascend and repair top-down** — fix the parent first.
4. **Re-descend / re-cascade** — does the existing spec/plan/code still hold? (Changes cascade.)
5. **Record the round-trip.**

Two reframes that make this natural rather than heavyweight:
- **The ascent is usually cheap** — "pause, write a paragraph, confirm, resume," not "restart
  the project." An agent that experiences ascent as *failure* resists it; one that treats it as
  **normal craft** does it reflexively.
- **Locate and the return edge are not two mechanisms.** They are one invariant — *am I at the
  right altitude?* — asked prospectively before a change and continuously while working.

### The through-line — the decision is the deliverable

Across all of the above, the rule is never "do the heavy thing." It is:

> **Always make the judgment, and always record it — even when the judgment is "nothing more
> is needed here."** Silence is the enemy. An unstated skip is the failure mode; a visible
> "I considered X and chose not to, because Y" is governance.

This is what makes "built without requirements" *impossible to do quietly* — the actual fix.

---

## 3. Decisions settled

- **D1 — Research is a dial, biased ON.** Default toward research under any doubt or when
  stakes merit it; stakes include wasted time, data loss, and over-building.
- **D2 — Locate always runs**, even for trivial changes; the output is a recorded note,
  including the null result.
- **D3 — The check facet always happens**; independence is an option chosen by judgment and
  recorded.
- **D4 — Independence is the full 4-point spectrum with a non-negotiable floor**: every check
  is at least adversarial self-review. The model climbs and records the climb (and why it
  stopped where it did).

---

## 4. Worked examples

Each change is a vector over the rungs, produced by the *same* locate function:

| Rung | "Button blue" | "Postgres → graphdb" | "Model belief/lies/truth" |
|---|---|---|---|
| Vision | skip | check-against | check-against |
| Requirements | check-against (trivial) | check-against **deep** (do non-functionals still hold?) | **modify — research-deep** ← enters here |
| Spec | code-only / light-modify | **modify — research-deep** ← enters here | modify — standard |
| Plan | skip | modify | modify |
| Implementation | **modify — light** ← enters here | modify | modify |

Independence calls on the check facet:

| Change | Check rung | Independence call |
|---|---|---|
| Button blue | code | **Self-review** (≥ adversarial floor). Reversible, local, no propagation. |
| Postgres → graphdb | spec | **Isolated independent.** Lock-in + data-loss + everything builds on the data layer. |
| Belief/lies model | requirements (+ spec) | **Isolated independent** — novel, low-confidence, the arch spine, *and* freshly invented in chat by an enchanted producer. The textbook case. |

Prawduct's existing **size × type** classification is a crude scalar proxy for this
rung-vector — it answers "how much rigor" with one number, where the real answer is a vector
over altitudes with two depth dials each.

---

## 5. Requirements Confidence & open questions

**Confidence: Medium.** By this model's own standard, a high-stakes, novel-domain requirements
artifact is not trustworthy until it has been researched and independently reviewed. This
document is **pre-research and pre-independent-review.** Treat every claim as a vetoable
assumption until those steps complete.

Open questions to resolve (and where they stand):

- **Research as rung vs. dial** — *resolved: dial* (emits an artifact when engaged).
- **Locate floor** — *resolved: always runs*, null result recorded.
- **Independence binary vs. spectrum** — *resolved: spectrum*, floored at adversarial
  self-review.
- **Vision check-against — mandatory on every change, or above a threshold?** Leaning "a cheap
  glance always, a real pass above a stakes threshold." Not yet settled.
- **Does the upper-rung *check* need to be isolated-independent above some altitude, or is the
  judged spectrum enough?** The failure suggests upper-rung reviews are exactly where
  independence pays — but that is also where it is most expensive. Left to the spectrum + the
  counterintuitive rule for now.
- **How much of this is already named prior art we should adopt rather than reinvent?** —
  *resolved by [`work-model-prior-art.md`](./work-model-prior-art.md).* The skeleton is
  established SE/PM canon (V-model, traceability, spiral/Cynefin, inspection hierarchy, ADRs)
  and its agent-era form is mainstream **Spec-Driven Development** (GitHub Spec Kit / Kiro). The
  revised positioning: this model is **"SDD plus the three things SDD is published-criticized for
  lacking"** — variable-altitude entry (fixes small-change overhead), continuous re-entry (fixes
  rigidity for evolving requirements), and anti-drift coherence — plus the Vision rung SDD omits.
  Genuinely ours: **design-in-chat blindness** (not found named), the **ascent tripwires**, and
  the **continuous altitude invariant**. Confidence: Medium (proportional pass; deep-read pending
  at independent review).

## 6. Next steps

1. **Research** — canon mapping (intrinsic) + volatile/web (AI-agent governance, 2025–2026).
2. **Independent review** of this model + the research, in an isolated context.
3. **Vision check-against** — does this serve prawduct's purpose or sharpen it?
4. **Diff against prawduct** — the spec-altitude question: what in the principles, methodology
   guides, session briefing, and hooks actually changes.
5. **Plan → implement** with per-chunk Critic.
