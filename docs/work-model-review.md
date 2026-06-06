# Work Model — Independent Review (isolated context)

> **Note:** this reviewed what is now the **v1 apparatus**, archived at
> [`work-model-v1-archive.md`](./work-model-v1-archive.md); the live kernel
> [`work-model.md`](./work-model.md) is the rework this review produced. Section/line
> references below point at the v1 archive.
>
> Adversarial review of [`work-model.md`](./work-model.md) + [`work-model-prior-art.md`](./work-model-prior-art.md),
> run in a fresh isolated context with a refute-it mandate. This is the check facet of the
> Requirements rung for the framework change — and per the model's own rule, the author
> (maximally invested) could not be the one to run it. Captured verbatim-faithful so the
> rework traces to it.

## Verdict: **DO NOT PROCEED — rework to the kernel**

The *diagnosis* (§1 — design-in-chat trips no artifact gate; the drop/invent asymmetry) is the
strongest part. The *solution* is a 5-rung, 2-dial, vector-valued, always-on-locate apparatus
that (a) re-derives machinery Prawduct already has (size×type, Calibrate Rigor, the Confidence
Check, the independence ladder) without stating what it retires, and (b) adds a per-change
"locate" ceremony that Principles 11/12 exist to prevent. The valuable kernel is ~3 paragraphs.
**Extract the kernel; kill the apparatus.**

**Vision check-against: distorts (mildly), trending toward redefine.** D2 ("locate always runs,
even trivial, emit a null note") is a *new always-on habit* — the exact "depth varies, the
habits don't" shape, applied to a per-change step the framework currently doesn't impose. Shifts
the center of gravity from "judgment, lightly governed" to "a standing per-change protocol."

## Blockers

- **B1 — States no retirements → two overlapping governance systems.** The only mention of
  existing machinery is one dismissive line calling size×type "a crude scalar proxy." Need an
  explicit reconciliation table: for each of size×type, Calibrate Rigor, the Confidence Check,
  Decision Research, the existing 4-tier independence — mark *retired / renamed / unchanged*. If
  the honest answer is "mostly renamed," the fix is a patch to existing files, not a new parent
  artifact.
- **B2 — Would not have fired at the moment of failure.** The model's answer to "the agent
  didn't notice" is "here's a list of things to notice" — circular. Locate is self-administered;
  the tripwires are self-observed; §1 already says a fluent agent's self-design "trips no gate."
  An agent enchanted enough to invent a taxonomy in chat is not in a state to run an honest
  adversarial check on that same taxonomy in the same turn. **Nothing enforces D2's "always
  runs" — no hook, no separate context, no external observer.** The Critic and Stop hook work
  *because* they are external. Name the enforcement surface or admit this is a prompt/principle
  intervention and size it accordingly.
- **B3 — Always-on locate (incl. null notes) is net-negative and contradicts 11/12.** Fixed
  per-change cost on a population that's overwhelmingly parented + trivial. Either a real token/
  latency tax or — worse — rubber-stamped: a check that always passes teaches the checker to
  stop looking, manufacturing the *exact* "rode along approvingly" reflex of the original
  failure. Signal lives only in the small fraction of parentless changes. **Make locate
  triggered, not always-on; delete the null-note.**
- **B4 — The "SDD plus three fixes" positioning is motivated; Spec Kit already ships two of the
  three.** Spec Kit has a project **constitution** (= vision + anti-drift) and **cross-artifact
  analysis** (= coherence check). So "anti-drift coherence" and "the Vision rung SDD omits" are
  largely already in the benchmarked tool. Drop "SDD plus three fixes"; keep "SDD's vocabulary +
  one agent-specific layer (chat-design blindness + tripwires)."

## Warnings / notes
- **W5** — "research is a dial not a rung" contradicts "research emits a persisted artifact"
  (this very pass produced a standalone prior-art file). Pick one; define who checks a research
  artifact.
- **W6** — {modify / check-against / skip} under-covers: *create* (no parent entry exists yet —
  the scriob case), *invalidate* (a lower rung proves a higher one wrong), *defer* (→ backlog).
  The worked-examples table leaks undefined substates ("check-against deep", "light-modify").
- **W7** — Ignores operational cost: who maintains/garbage-collects the new always-on artifacts
  (the model's own outputs invite the spec-drift it criticizes); per-turn token cost of locate
  in an autonomous loop; interaction with the Stop hook / Critic modes / gate waivers.
- **N8** — §0 dogfooding is performative self-justification; cut to two sentences.
- **N9** — "draft / Medium / pre-research / pre-review" is honest — and means it cannot yet be a
  parent everything traces to. Take that at face value as evidence *for* "do not proceed."

## Strongest steelman against adopting the model at all
Prawduct already has every mechanism needed. The failure was the **asymmetry**: Principle 6 +
Complete Delivery forbid silently *dropping* a requirement but not silently *inventing* one. The
minimal proportional fix: (1) one clause on Principle 6 / the Confidence Check — *new domain
vocabulary mid-build is an undocumented requirement; stop and write it before designing against
it* — plus the 5-item tripwire list as a building.md callout; and (2) optionally an external
Stop-hook/canary heuristic, since external enforcement is the only thing that reliably catches an
enchanted agent. ~30 lines across two existing files; retires nothing; coherent with Calibrate
Rigor. Standing up the apparatus to deliver that is the over-engineering Principle 11 names.

## Author blind spots (named by the reviewer)
1. **Scaled the fix to the *emotional weight* of the miss, not its *causal surface*.** The
   failure *felt* deep, so the fix feels like it must be deep. The mechanism that failed is
   narrow and local — one missing tripwire on one principle.
2. **N=1 positive experience of the ceremony, zero experience of the tax.** §0 felt illuminating
   to write once; run 400× on "make the button blue" it's friction that gets rubber-stamped.
3. **Already half-conceded the verdict.** The prior-art "Bottom line," the "weakest answer"
   admission, and the pre-review caveat all say *the delta is small and the apparatus is
   borrowed* — and the response was to keep the apparatus and reposition it, rather than shrink
   the deliverable to the delta.
