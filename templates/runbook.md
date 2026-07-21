<!-- Runbook Template
     Tier: 2 (Operational)
     Owner: whoever owns the system this procedure touches

     Usage: ONE FILE PER PROCEDURE. Copy to the product's runbook directory
     (commonly .prawduct/runbooks/ or docs/runbooks/) and name the file after
     the trigger, not the mechanism: `KafkaConsumerLagHigh.md`, not `kafka.md`.

     THE RULES BEHIND THIS TEMPLATE — and the evidence for them — live in
     `docs/runbook-authoring.md` in the prawduct plugin. Read it when you need
     depth: every section below carries a `Rules:` pointer to the exact part
     that governs it, so you can go from "what goes here" to "why, and what
     happens when you get it wrong" in one hop.

       Overview .............. docs/runbook-authoring.md
       The invariants ........ #the-invariants
       Proportionality/tiers . #proportionality
       Anatomy ............... #anatomy
       Writing rules ......... #writing-rules
       Branching + one-way ... #branching-and-steps-that-cannot-be-undone
       Finding it at 3am ..... #how-the-runbook-gets-found
       Per-substrate examples  #the-same-invariant-in-five-substrates
       Self-review ........... #self-review--rejection-criteria
       What's evidence vs not  #evidence--what-is-known-vs-what-is-merely-repeated

     Generate with /prawduct:runbook, which derives every command from this
     repo rather than producing plausible ones.

     ────────────────────────────────────────────────────────────────────
     START SHORT. THIS TEMPLATE IS A MENU, NOT A FORM TO COMPLETE.
     ────────────────────────────────────────────────────────────────────
     The most common way to ruin a runbook is to fill in every section.
     Length is the best-evidenced defect in the whole literature: as a
     procedure grows, readers skip it or execute it badly. A section with
     nothing product-specific in it does not add rigor — it dilutes the
     steps that matter.

     The minimal runbook is FIVE THINGS, and for most procedures it is the
     whole document:

         # <trigger>
         ## When to use this
         <the entry condition, matchable against what the responder sees>
         ## Steps
         1. <action>  →  Pass: <observed value>  →  If not: <where to go>
         ## Done when
         <the observable end state — the value that proves it, not "complete">
         ## If this doesn't work
         <escalation, and the exit for "this isn't my situation">

     EVERY OTHER SECTION IS A DECISION, NOT A DEFAULT.
     Do not ask "can I fill this in?" — you almost always can, and that is the
     trap. Ask the include-test below. If the answer is no, DELETE THE SECTION
     ENTIRELY. Do not leave it with "N/A", "None", or a restated generality:
     an empty section still costs the reader a read to discover it is empty.

       SECTION            INCLUDE ONLY IF...
       ─────────────────  ────────────────────────────────────────────────
       When NOT to use    a neighbouring procedure could plausibly be
                          confused with this one
       Prerequisites      a missing credential, tool, network position or
                          physical item would strand the reader mid-procedure
       Blast radius       the reader must judge whether it is safe to START
       Expected duration  "is it stuck?" is a real question here
       Authorization      the executor is not the person who decides
       Phases/checkpoints the procedure exceeds ~15 steps
       Irreversible block a step genuinely cannot be undone — NOT merely
                          "important" or "scary"
       Close-out          the procedure leaves state that must be put back
                          (silenced alerts, feature flags, scaled capacity,
                          maintenance mode, temp credentials)
       Maintenance        anyone other than the author will ever run this

     WHOLE SECTIONS WILL NOT APPLY TO WHOLE PRODUCTS, and that is expected:
       - A library or CLI with no deployment has no blast radius or close-out.
       - A frontend-only product has no physical prerequisites.
       - A solo project has no authorization and no escalation-by-role;
         "escalate" may just mean "stop and look at it tomorrow" — say that.
       - A product with no alerting has no trigger signal; title by symptom
         and say where the responder is expected to find the document.
       - A reversible-everything system needs no irreversible block at all.
     A product whose runbooks legitimately use five sections is not
     under-documented. Do not manufacture applicability.

     The FRONTMATTER is subject to the same test — drop `triggers:` if nothing
     fires, drop `tier:` if the product does not tier. Keep `owner:` and
     `last_verified:`; those earn their place everywhere.

     BUDGETS: ≤20 steps total, 5-15 per phase, action lines under ~25 words.
     Real production runbooks run ~5-15 steps. If yours is longer, split it.

     BEFORE YOU FINISH: do one pass whose only purpose is deletion. For every
     line ask "would a tired responder at 3am be worse off without this?"
     If not, cut it. A step you deleted cannot be misread.

     It must work for BOTH audiences: someone doing this routinely on a
     Tuesday, and someone doing it for the first time at 3am during an
     outage. Concision serves both. Padding serves neither.

     DELETE ALL OF THESE COMMENTS in the finished runbook. The reader is
     tired; they should see only what they must do.
-->
---
runbook: <trigger-signal-or-symptom>
tier: 2
owner: <team or role, never a single person's name alone>
last_verified: null        # date this was EXECUTED or rehearsed — not edited
verified_by: null
triggers:                  # every signal that should lead a responder here
  - <alert name / error code / fault code / symptom>
---

# <Trigger signal, verbatim — or the symptom as the responder experiences it>

<!-- Rules: #how-the-runbook-gets-found — titling, indexing, alert linkage.
     If a named signal triggers this (alert, error code, device fault code),
     the title IS that identifier, character for character: string identity is
     how a responder confirms they opened the right document. If nothing
     triggers it, title by the observed symptom ("checkout failing for some
     users, nothing firing"). Never title by the component you suspect. -->

## When to use this

<!-- The entry condition, written so a responder can match it against what they
     are actually seeing. Quote the alert text or error signature verbatim.
     A responder must be able to confirm or reject this procedure BEFORE
     step 1. -->

## When NOT to use this   <!-- OPTIONAL — only if a neighbouring procedure could be confused with this -->

<!-- The neighbouring procedures this is confused with, and where to go
     instead. Selecting the wrong procedure is a real failure mode; this
     section is the defence. -->

## Before you start          <!-- OPTIONAL — keep only the lines that matter -->

<!-- Rules: #anatomy — the field set and why "Description" is deliberately absent. -->

**Blast radius:** <what is affected while this runs; whether users can see it>
**Expected duration:** <so the reader can tell "slow" from "stuck">
**Authorization:** <who must approve; delete for Tier 2 if nobody must> <!-- TIER 3 -->

**Prerequisites** — check every line before step 1:

- [ ] <access / role / credential>
- [ ] <tool + version, or the exact install command>
- [ ] <network position: VPN, bastion, physical presence, cable>
- [ ] <consumables, spare parts, or hardware — for field procedures>
- [ ] <state the system must be in for this to be safe>

<!-- Discovering a missing credential at step 8 costs the whole procedure.
     This block is mandatory in military and S1000D procedure standards for
     exactly that reason. -->

---

## Steps  <!-- or "Phase 1 — <name>" if you genuinely need phases -->

<!-- Rules: #writing-rules (voice, commands, warnings, legibility) and
     #4-length-is-a-defect-decompose-into-phases (why phases exist at all).
     Group steps into named phases of roughly 5-15 steps with a checkpoint
     between them. Under ~20 steps total, or split into separate runbooks.
     Order by consequence: preconditions, the state capture that rollback will
     need, and anything irreversible go EARLY — probability of completing a
     step without interruption falls as a procedure runs on.

     STEP RULES
       - One action per step. If you wrote "and then", split it.
       - Imperative, verb first. Say where before you say what.
       - Exact commands in code blocks, copy-pasteable.
       - Step numbers are stable identifiers: never renumber on edit, insert
         `3a` instead. A reader interrupted at "step 12" must be able to
         return to the same step 12.
       - Rationale goes on its own adjacent line, never inside the action
         sentence — the executing eye skips it, the confused eye finds it.
       - `**Pass:**` / `**If not:**` is the verification form EVERYWHERE. Inside
         a conditional it attaches to the branch's own sub-step (`3b.`), but the
         labels never change. Do not invent a second syntax. -->

1. <Imperative action.>

   ```
   <exact command, derived from this repo — never invented>
   ```

   **Pass:** <the specific observed value that means success>
   **If not:** <step number to go to, or escalate>

   > *Why: <one line — only where a reader might reasonably skip or improvise.>*

2. <Imperative action.>

   **Pass:** <observed value>

<!-- VERIFICATION IS THE RULE THIS TEMPLATE EXISTS TO ENFORCE.
     Rules: #1-a-verification-step-reports-an-observed-value-not-an-acknowledgment
     Worked examples for backend, frontend, embedded, data and mobile:
     #the-same-invariant-in-five-substrates
     A step the reader can satisfy without looking at anything is broken.
       ✗ "Verify the service is healthy."
       ✓ "Run `<cmd>`. Pass: `ready_replicas` equals `desired_replicas`."
     This holds in every substrate — an LED colour, a build hash, a row count,
     a crash-free-sessions percentage. Name the instrument, the observed
     value, what passes, and where to go on failure. -->

### Checkpoint              <!-- OPTIONAL — only where you genuinely have phases -->

<!-- State what must be true before Phase 2. This is the resumption cue for a
     reader who was interrupted — interruptions of a few seconds measurably
     wreck place-keeping, so their place must be recoverable from the page. -->

---

## Phase 2 — <name>          <!-- OPTIONAL — phases only past ~15 steps -->

<!-- Rules: #branching-and-steps-that-cannot-be-undone
     CONDITIONAL STEPS: condition first, so a reader can discard a branch
     without reading its actions. Group a branch's steps by indentation and
     separate branches with whitespace. Never mix AND with OR in one
     condition; beyond four ANDs use a list. -->

3. Check <what>: `<command>`

   **IF <condition A>:**
   - 3a. <action>
   - 3b. **Pass:** <observed value>

   **IF <condition B>:**
   - 3c. Do NOT <the thing that seems natural but is wrong here>.
   - 3d. Go to step <N>.

<!-- IRREVERSIBLE STEPS — the block below is mandatory before any step that
     cannot be undone. Give the precondition check its own numbered step;
     never fold it into the destructive one. Split verify from commit. -->

<!-- Rules: #3-state-the-abort-criteria-before-the-point-of-no-return- -->

> ⚠️ **IRREVERSIBLE — step 5 cannot be undone.**
> **Proceed only if:** <precondition verified in step 4, with its observed value>
> **Abort if:** <the condition that means stop> → go to step <N>
> **Cost of aborting:** <so the reader can weigh it>
> **Recovery after this point:** <the named forward path — "fall back to the
> known-good artifact already on the target" or "re-obtain and re-apply".
> "We'll figure it out" is not a recovery path.>

4. Verify <the artifact / precondition itself>: `<command>`

   **Pass:** <checksum, signature, count, target identity — the payload, not your intent>

5. <The irreversible action.>

---

## Done when

<!-- The observable end state. Not "the procedure is complete" — the value
     that proves it. -->

- <observed value 1>
- <observed value 2>

## Close-out                 <!-- OPTIONAL — only if this changed state that must be put back -->

<!-- Rules: #close-out-what-the-procedure-introduced
     Required WHENEVER this procedure left state behind, and executed BEFORE
     handing the system back. This is the most commonly omitted section in
     software runbooks and is a hard requirement in OSHA lockout/tagout and
     S1000D. If the procedure introduced nothing, delete this section. -->

- [ ] Re-enable anything this procedure disabled (alerts, monitors, health checks)
- [ ] Remove what this procedure introduced (feature flags, scaled capacity,
      maintenance mode, temporary credentials, debug builds, physical jumpers)
- [ ] Confirm the system is in its intended steady state: `<command>` → `<expected>`
- [ ] Record the outcome where the next responder will look
- [ ] Tell the incident channel it is over

<!-- A silenced alert nobody un-silenced is the classic residue — and the
     next incident goes unnoticed. -->

## If this doesn't work

<!-- Escalation by ROLE, not by person, with how to reach them. Also: the
     exit for "reality does not match this document" — a procedure with no
     exit invites the reader to force reality to match it. -->

- **If <symptom> instead:** this procedure does not apply → <where to go>
- **Escalate to:** <role> via <channel>, after <how long / what condition>
- **Wake someone up if:** <the condition that justifies it — say it explicitly,
  because a responder who is unsure will wait too long>

---

## Maintenance               <!-- OPTIONAL — only if anyone other than the author will run this -->

<!-- Rules: #maintenance--a-runbook-is-only-as-good-as-its-last-rehearsal -->

**Last executed or rehearsed:** <date> by <who>
**Validated by:** <someone other than the author running it end to end — this
is the single highest-yield check available, and it is the AWS-prescribed one>

<!-- A runbook that exists, is accurate, and is never practiced is closer to
     no runbook than to a good one: when surgical checklists were adopted
     across 101 hospitals and measured, the benefit seen in the original trial
     did not appear — what was measured was that a checklist existed.
     Re-verify after any change to the system this touches. -->

<!-- UNVERIFIED CONTENT: if any step could not be derived from this repo or
     confirmed with an owner, mark it inline and leave it visible:

     > 🚧 UNVERIFIED — <what could not be confirmed, and who can confirm it>

     A visible gap is a working runbook with a hole. A plausible invented
     command is a broken runbook that looks finished, and it is far more
     expensive. -->
