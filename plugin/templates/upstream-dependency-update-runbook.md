<!-- Upstream Dependency Update Runbook — FILLABLE TEMPLATE
     Tier: 2 (Operational)
     Owner: whoever owns this product's dependency intake

     WHAT THIS IS. Tier 3 of the enforcement model in
     `docs/upstream-dependency-policy.md` (in the prawduct plugin — not a path in
     this repo) is the agent-mediated procedure, and that spec is explicit that it
     "must be a procedure, not a prompt": guidance living only in an agent's
     instructions is the weakest form of the weakest tier. This is that procedure,
     pre-shaped so a product fills it in rather than inventing it.

     TWO DIFFERENT THINGS ARE CALLED "TIER" AND THEY ARE NOT RELATED.
       - The POLICY's tiers (1 declarative / 2 bot / 3 agent-mediated) grade how
         strongly a clause is enforced on a given intake surface.
       - The RUNBOOK's tiers (1 note / 2 standard / 3 controlled procedure) grade
         how much ceremony a procedure needs, per `docs/runbook-authoring.md`.
     A tier-3 POLICY expression is normally a tier-2 RUNBOOK. The frontmatter
     below is the runbook sense. Do not "fix" the mismatch.

     COPY IT, DO NOT CITE IT. Copy to your runbook directory (commonly
     .prawduct/runbooks/ or docs/runbooks/) and fill it in. A product that points
     at this file instead of copying it has a prompt again, not a procedure.

     THE RULES BEHIND THE FORM live in `docs/runbook-authoring.md`. The ones this
     template is most often broken by:
       - Verification reports an OBSERVED VALUE, never an acknowledgment.
         "Confirm the release is old enough" is broken; "read its publication
         time; Expected: a date at or before the cutoff" is not.
       - One step, one action. If you wrote "and then", split it.
       - Never hedge. "Usually", "if appropriate" is a missing branch, a missing
         number, or an unmarked gap — never a fourth thing.
       - Length is a defect. This template is already near the useful ceiling;
         fill in, then DELETE what your product does not have.

     DERIVE EVERY COMMAND FROM THIS REPO. The `<...>` placeholders are commands
     and values this template cannot know. Do not generate plausible ones — an
     invented command is a broken runbook that looks finished. Mark anything you
     cannot confirm:

         > 🚧 UNVERIFIED — <what could not be confirmed, and who can confirm it>

     WHY NO TOOL, REGISTRY OR MANIFEST IS NAMED ANYWHERE BELOW. The policy governs
     dependencies, not package managers, and its first stated requirement is that
     no policy statement may be phrased in terms of a named ecosystem. This
     template ships to products whose toolchains prawduct has never heard of, so
     naming one here would make the procedure read as inapplicable to everyone
     else. Your filled-in copy is the opposite: it is YOURS, and it should name
     your tools, your commands, and your surfaces exactly.

     WHAT TO DELETE WHEN YOU FILL IT IN:
       - "When NOT to use this" — keep it. The security fast path is the one
         genuinely confusable neighbour, and taking the wrong branch there means
         either sitting on a fix for a live exposure or waving a release through
         with no review at all.
       - "Before you start" — keep only lines that would strand you mid-procedure.
       - Any step whose surface your product does not have.
       - ALL OF THESE COMMENTS.
-->
---
runbook: routine upstream dependency update
tier: 2
owner: <team or role, never a single person's name alone>
last_verified: null        # date this was EXECUTED — not edited
verified_by: null
---

# Routine upstream dependency update

## When to use this

You are taking upstream releases into this product as ordinary maintenance —
whether prompted by an update bot, a scheduled sweep, or noticing you are behind.

This procedure applies to **every** intake surface this product records, not only
the ones a package manifest lists. Your recorded `surfaces` block names them.

## When NOT to use this

- **If you are patching a vulnerability this product is exposed to:** → this is
  the security fast path (clause 3), which is exempt from the minimum release age
  and adopted immediately on its merits. Do not wait out the age floor here — that
  converts a security control into a security regression. Record that you took it.
- **If you are adding a dependency that is new to this product:** → clause 6
  governs it twice: the version must satisfy the age floor like any other, *and*
  the package identity must be verified to be the one you decided about. A name
  that resolves is not a name that was verified.

## Before you start

**Blast radius:** <what breaks if a bad release lands — CI only, or shipped users>
**Expected duration:** <so you can tell "slow" from "stuck">

**Prerequisites** — check every line before step 1:

- [ ] Read access to whatever publishes each upstream artifact, so publication
      times can be read rather than guessed
- [ ] This product's recorded intake policy in front of you — the values, the
      trusted register, and the per-surface tier record
- [ ] <any credential, network position or tool your surfaces need>

---

## Steps

1. Enumerate every intake surface this product has, from the `surfaces` record —
   not from a list of filenames.

   > *Why: a filename list under-enumerates by construction. The surfaces that
   > carry the sharpest exposure — upstream code running with the repository's
   > credentials, referenced by a mutable tag — appear in no manifest at all.*

2. For each surface, list the updates currently available.

   ```
   <the command that lists available updates for this surface>
   ```

   **Expected:** a list of candidates, each with the version you would move to.
   **If not:** the surface has no mechanism that answers this — go to step 3 and
   read the published versions directly from wherever that upstream publishes.

3. For each candidate, read its **publication time** from the authority that
   published it.

   ```
   <the command or query that returns a publication timestamp>
   ```

   **Expected:** a timestamp per candidate.
   **If not:** you cannot classify this candidate under the age floor. Treat it as
   *not yet eligible* and say so in step 8 — never as eligible-by-default.

4. Compute your cutoff: the current date minus this product's recorded
   `minimum_release_age`.

   **Expected:** one date, written down, used for every candidate in this run.

   > *Why: computing it per candidate is how a long run silently applies two
   > different floors.*

5. Sort each candidate into exactly one of three outcomes.

   **IF the publisher is in your trusted register:**
   - 5a. Eligible now. The age floor does not apply to trusted parties.

   **IF the publisher is not trusted, and the publication time is at or before the
   step-4 cutoff:**
   - 5b. Eligible now.

   **IF the publisher is not trusted, and the publication time is after the
   cutoff:**
   - 5c. Hold. Record the date it becomes eligible; do not take it in this run.

6. For any candidate that is **new** to this product, verify its identity before
   adopting it: confirm the source repository, the publication history, and the
   maintainer are the ones your decision was about.

   **Expected:** all three match what you intended to depend on.
   **If not:** stop. Do not adopt it. A plausible name that resolves is exactly
   the failure clause 6 exists to catch.

7. Apply the eligible updates.

   ```
   <the command that applies an update on this surface>
   ```

   **Expected:** each applied candidate now reports the intended version.

8. Re-pin and commit the resolved set, so what you just verified is what installs
   everywhere.

   ```
   <the command that regenerates or updates this product's committed resolution>
   ```

   **Expected:** the committed resolution names the versions from step 7, and
   nothing else moved.
   **If not:** something re-resolved beyond what you adopted. Do not commit it —
   find what moved first, or clause 5 stops holding for every actor downstream.

9. Run this product's test suite against the applied set.

   ```
   <this product's test command>
   ```

   **Expected:** <the passing line this product's runner prints>
   **If not:** revert to the previous committed resolution and treat the failure
   as the update's, until shown otherwise.

## Done when

- Every candidate from step 2 is in exactly one recorded outcome: adopted, held
  with an eligibility date, or blocked on unverified identity.
- The committed resolution matches what was tested, and installs elsewhere
  reproduce it without re-resolving.
- Any fast-path adoption taken during this run is recorded as a deliberate act.

## If this doesn't work

- **If a held candidate is blocking work:** decide it as a policy question, not as
  an exception in passing — either it qualifies for the fast path, or the recorded
  age floor is wrong for this product and gets changed with a why.
- **If a surface came back unclassified:** you could not determine on what terms
  upstream enters there. That is a finding, not a blank — name it, and do not
  report this run clean.
- **Escalate to:** <role> via <channel>, after <how long / what condition>
