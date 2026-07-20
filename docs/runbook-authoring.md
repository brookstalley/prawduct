# Runbook Authoring — How to Write a Procedure Someone Can Actually Execute

This is the canonical guide for producing runbooks in a Prawduct product. It is written to be
read by an agent that is about to author or review one, for a product in any language, on any
substrate — web frontend, backend service, embedded device, data pipeline, mobile app, CLI.

**The artifact you produce is for a human.** You may be the one who writes it, and increasingly
you may be the one who executes it, but the runbook's reason for existing is that at 3 a.m. a
tired person who did not build this system has to make it work. Every rule below descends from
that reader.

**How to use this guide.** Read the [Invariants](#the-invariants) before authoring — they are the
rules that hold regardless of technology. Then apply [Proportionality](#proportionality) to decide
how much procedure this task warrants, [Anatomy](#anatomy) for what goes in it,
[Writing rules](#writing-rules) for the step-level craft, and the
[Authoring protocol](#authoring-protocol-when-a-model-writes-the-runbook) for the parts that are
specific to a model doing the writing. Before you call it done, run the
[rejection criteria](#self-review-rejection-criteria) against your own output.

**Evidence markers.** This guide distinguishes what is known from what is merely repeated:

| Mark | Meaning |
|---|---|
| ✓ | Adversarially verified against the primary source during this research |
| ○ | Sourced and quoted, but the verification pass had not adjudicated it when this was written — see [Evidence](#evidence-what-is-known-vs-what-is-merely-repeated) |
| ◆ | Reasoned design guidance. No study supports it; it follows from the evidenced findings |

The [Evidence appendix](#evidence-what-is-known-vs-what-is-merely-repeated) also carries a list of
**refuted** claims — plausible, widely-repeated, and false. Read it. They are exactly what a model
regenerates from memory.

---

## The failure this guide prevents

Bad runbooks do not look bad. They look complete. They have numbered steps, code blocks, and a
confident tone, and they fail in one of four ways:

1. **The unmeasurable condition.** "Verify the service is healthy." The reader cannot tell whether
   this passed. In the largest study of real production runbooks, this defect class was the single
   most common ○ — more common than a step being outright wrong.
2. **The invented command.** A step that could not have worked, because the flag, package, or
   endpoint does not exist. This is the characteristic failure of a machine-written procedure, and
   it is measurable ○.
3. **The stale procedure.** Correct when written, false now, because the system changed underneath
   it and nothing forced the document to move.
4. **The procedure that runs out.** The reader reaches a step, reality does not match, and the
   document has nothing to say. It never told them how to know it had stopped applying.

Each of these destroys trust in the whole document, not just the step. A reader who finds one
wrong command stops believing the other forty.

---

## What a runbook is

> A **runbook** is a pre-written procedure for an *anticipated* operational task, executed under
> conditions that are worse than the ones it was written in.

Three parts of that definition do work:

- **Pre-written** — it exists before it is needed. A procedure invented during the incident is not
  a runbook, it is improvisation with a paper trail.
- **Anticipated** — you knew this could happen. That is what makes writing it possible.
- **Worse conditions** — the reader is more tired, more rushed, and less familiar with the system
  than you are right now. This is the governing design constraint.

**In scope:** incident response and on-call diagnostics · deploy and rollback · release · provisioning
and decommissioning · disaster recovery and restore · routine and scheduled maintenance · data
backfill and correction · device provisioning and field service.

**Out of scope** (these are different documents with different failure modes): onboarding guides ·
architecture documents · API reference · tutorials · local development setup · postmortems.

If someone asks for a "runbook" for local dev setup, write them a setup guide and say so. The rules
here are calibrated for consequence, and applying them to `npm install` is the over-engineering
that Principle 11 warns about.

### Which procedures to write first

You cannot write procedures for every situation, and attempting exhaustive coverage produces a
large, stale, distrusted corpus. NIST's rule is the right one ✓ — coverage is driven by two
independent axes:

1. **Frequency** — the things that happen most often.
2. **Recovery-criticality** — "particularly important processes that may be urgently needed during
   emergency situations", their example being redeployment of the primary authentication platform.

The second category is the one teams systematically under-write, *precisely because it is rare*.
The restore-from-backup procedure is the canonical example: almost never needed, catastrophic when
needed and absent.

Do not write a runbook for a task that is already fully automated and reliably self-healing. Write
one for what happens when that automation fails.

---

## The reader you are writing for

Design for a specific, degraded reader. The honest evidence:

**Fatigue is the strongest quantitative anchor** ✓. Performance declines about 0.74% per hour
between the 10th and 26th hour of wakefulness; at **17 hours awake, performance impairment matches
0.05% blood alcohol**, and at 24 hours it matches roughly 0.10% BAC (Dawson & Reid, *Nature* 388:235,
1997; independently replicated by Williamson & Feyer, *OEM*, 2000). Your on-call reader at 3 a.m. is,
functionally, impaired. Write for that person.

**Stress impairs working memory, but less than folklore claims** ✓. Meta-analytically the effect is
small (g+ = -0.197) and concentrated where cognitive load is already high (g+ = -0.303 under high
load; effectively absent otherwise). The operational reading is not "the reader becomes stupid" — it
is **that the damage is load-dependent, so the load your document imposes is the variable you
control.** Notably, that high-load moderation weakens to marginal significance once study precision
is controlled; do not overstate it.

**Surprise costs place-keeping specifically** ✓. Startle and surprise are documented to leave an
operator unable to recall the current procedure or to **lose track of where they were in a
checklist**. This is a direct argument for numbered steps, one action per step, and a document that
makes "where am I" answerable at a glance.

**The reader deviates more than you think, and usually on purpose.** Users self-report deviating
from written procedures at roughly 1.5× the rate the procedure's own authors estimate, and where
authors attribute this to carelessness, users report *intentional* deviation — most often because
the document is wrong ✓ (small single-industry study; treat the direction as informative and the
magnitude as indicative).

The synthesis: **you are not writing for the person who wrote the system. You are writing for
someone who is tired, interrupted, possibly wrong about what is happening, and who will abandon
your document the moment it stops matching reality.**

---

## Proportionality

Prawduct's Principle 11 applies with force here. Rigor is set by consequence, not by taste. Grade
the task on three axes, then pick a tier:

| Axis | Question |
|---|---|
| **Reversibility** | If this step is wrong, can it be undone? In how long? |
| **Blast radius** | Who is affected — one dev, one tenant, every user, physical hardware? |
| **Executor distance** | Is the executor the author, a teammate, a stranger, or an agent? |

**Tier 1 — Note.** Reversible, small radius, executed by the author. A few lines in the relevant
doc. Do not build a ceremony around restarting a dev container.

**Tier 2 — Standard runbook.** Reversible-with-effort, team-visible radius, executed by any
teammate. The full [anatomy](#anatomy) minus the heavyweight fields. This is the common case.

**Tier 3 — Controlled procedure.** Irreversible steps, user-visible or data-affecting radius, or
executed by someone who does not know the system. Everything in Tier 2 plus explicit abort
criteria, per-step verification, named authority, and a rehearsal requirement.

A runbook is allowed to be short. A Tier 2 runbook of six well-formed steps is better than a
Tier 3 imitation with thirty vague ones — and length is itself a defect (see below).

---

## The invariants

These hold for every product, language, and substrate. If you remember nothing else, enforce these.

### 1. A verification step reports an observed value, not an acknowledgment

This is the most strongly evidenced rule in the entire literature ✓, and it converges from two
independent directions: aviation human factors, and the largest empirical study of real software
runbooks.

Aviation checklist doctrine names responses like "checked", "set", and "completed" as a failure
mode, because — quoting the incident report that motivated the guideline — they "can be said too
easily without any sound verification." The prescribed form states the actual value: `Altimeters —
30.10`, not `Altimeters — checked`. The FAA reaffirmed this 26 years later.

Independently, the Microsoft study of 92 production troubleshooting guides found the top defect
cluster to be *missing action descriptions and **unquantifiable conditions*** ○.

> **Rule.** Every verification step must name (a) what to run or look at, and (b) the specific
> observed value that means "pass". If the reader can satisfy the step without looking at anything,
> the step is broken.

```diff
- 4. Verify the service is healthy.
- 5. Confirm the migration completed successfully.

+ 4. Run: `<health-check command>`
+    Pass: status is `ok` AND `ready_replicas` equals `desired_replicas`.
+    If `ready_replicas` is lower after 2 minutes, go to step 9 (Rollback).

+ 5. Run: `<migration status command>`
+    Pass: the last row's state is `complete` and `error_count` is 0.
+    Any other state — stop and escalate. Do not re-run the migration.
```

This applies identically to a device (`the status LED is solid green, not blinking`), a frontend
(`the response header includes the new build hash`), and a data pipeline (`row count in the target
table equals the source count for the partition`).

### 2. Critical and irreversible steps go early

Aviation doctrine places the most critical items as close to the *beginning* of a procedure as
possible, because the probability of completing an item without interruption falls as the procedure
runs on ✓. This guideline is explicitly ranked *above* sequencing by system topology or by external
dependency — a rare case of a standard adjudicating its own conflicting rules.

The source defines "critical" as *accident-causing if omitted*. For software, read that as: the
step whose omission silently corrupts the outcome. The classic shape is a pre-flight check that is
technically needed only later, and therefore drifts to the end, and therefore gets skipped.

> **Rule.** Front-load: preconditions, the "do we actually want to do this" confirmation, the
> backup that recovery will depend on, and the capture of current state needed for rollback. Order
> by consequence first, convenience second.

### 3. State the abort criteria before the point of no return ◆

The procedure must tell the reader, *before* an irreversible step, what would mean "stop". A
reader who is mid-procedure and surprised is a reader whose working memory is already degraded ✓ —
that is not the moment to expect them to derive a stopping rule.

> **Rule.** Every irreversible step is immediately preceded by: what makes it safe to proceed, what
> means abort, and what abort actually costs. Mark it visually. After it, say plainly that rollback
> is no longer available and name the forward-recovery path.

```markdown
> ⚠️ **IRREVERSIBLE — step 7 cannot be undone.**
> Proceed only if: the backup from step 2 verified (`<verify cmd>` reported `OK`),
> and traffic is confirmed drained (`active_connections` is 0).
> If either is false: STOP. Go to step 12 (Restore service, no data change).
> After step 7, rollback is unavailable; recovery is forward-only via step 13.
```

### 4. Length is a defect; decompose into phases

As a list grows, the probability of overlooking any given item rises, and long procedures push
operators either to skip the document or to execute it poorly ✓. Field observation found crews
degrading a long checklist into a hurried read-through, sacrificing the very redundancy the
checklist existed to provide.

The remedy is not to delete content but to **chunk it** — task-scoped blocks, visually separated,
anchored to natural pause points. The WHO Surgical Safety Checklist is the reference shape: 19
items across *three* blocks, each at a moment where the team stops other activity ✓.

> **Rule.** Group steps into named phases with an explicit checkpoint between them. Prefer 5–15
> steps per phase. If a runbook exceeds roughly 20 steps, split it — and give each part its own
> entry condition, because a reader may enter at part two.

Note the honest counterweight, which the source itself raises: decomposition costs you the signal
that the *whole* procedure is complete. Add an explicit final "done when" so that signal is not lost.

### 5. One step, one action

A step that chains a second action ("restart the service **and then** clear the cache") creates three
documented problems ○: the embedded action gets overlooked, per-step check-off no longer proves the
work happened, and the chaining word gets confused with conditional logic.

> **Rule.** One imperative action per step. If you wrote "and then", split it. Sequential UI
> navigation is the only routine exception (`Settings > Advanced > Reset`).

### 6. Say why, next to the step but out of its way

A controlled experiment found that adding a one-line rationale to each critical step raised
adherence from 44% to 68%, **with no measurable time cost**, and shifted deviations away from
"my own method is better" ○.

This is in direct tension with invariant 4 — rationale is more words, and length is a defect. The
resolution is typographic, not editorial ◆:

> **Rule.** Keep the imperative action on its own line. Put the *why* on an adjacent, visually
> distinct line (blockquote, italic, or a `Why:` prefix). The eye executing the procedure skips it;
> the eye that is confused finds it. Do not bury rationale *inside* the action sentence.

```markdown
3. Bump `version` in `plugin.json` and the `VERSION` file.
   *Why: `version` is the update cache key — a release that forgets this does not ship.*
```

The benefit is conditional on the reader being able to understand the explanation ○ — pitch it to
the actual on-call audience, not to the system's author.

### 7. Tell the reader when the procedure has stopped applying

Operators face a genuine double bind ✓: rigidly following a procedure when the situation has
diverged produces bad outcomes, and improvising without full knowledge also produces bad outcomes.
Tightening enforcement does not dissolve this — it may worsen it.

You cannot resolve the bind, but you can stop pretending it does not exist.

> **Rule.** State the runbook's assumptions where the reader can check them, and give an explicit
> exit: "If you observe X, this procedure does not apply — go to Y / escalate to Z." A procedure
> with no exit invites the reader to force reality to match the document.

### 8. Encode who decides, not just what to do

For major incidents, PagerDuty's doctrine centralizes remediation authority in an Incident
Commander who explicitly is *not* required to be the deepest technical expert and who performs no
repairs; subject-matter experts propose, the IC authorizes ✓. This binds for major incidents with
an established IC — it does not bind for routine work.

> **Rule.** For Tier 3 procedures, each consequential step names who authorizes it. Assume the
> executor and the decision-maker are different people.

---

## Anatomy

Header fields first, so the reader can decide in seconds whether they are in the right document.
Field sets by tier — the metadata set is industry convention rather than measured ○, so apply it
proportionately rather than ceremonially.

**Always:**

- **Title** — states the *situation*, not the mechanism: "Database connection pool exhausted", not
  "Pool tuning". The reader arrives with a symptom.
- **When to use this** — the trigger/entry condition, phrased so a reader can match it against what
  they are seeing. Include the alert name or error signature verbatim if there is one.
- **When NOT to use this** — the neighbouring procedures this gets confused with, and where to go
  instead. Selecting the wrong procedure is a real failure mode; aviation treats checklist selection
  under ambiguity as its own design problem.
- **Prerequisites** — access, credentials, tools, physical items, and VPN/network position. Written
  as a checkable list, because discovering a missing credential at step 8 costs the whole procedure.
- **Expected duration** — so the reader can tell "slow" from "stuck".
- **Blast radius** — what is affected while this runs, and whether users see it.
- **Steps** — numbered, phased, one action each.
- **Done when** — the observable end state. Not "the procedure is complete" but the value that
  proves it.
- **If this doesn't work** — the escalation path, by role, with how to reach them.
- **Ownership and last-verified date** — who owns it, and when it was last *executed or rehearsed*,
  not when the file was last edited.

**Tier 3 adds:** explicit abort criteria per irreversible step · named authority per consequential
step · rollback procedure (or an honest statement that there is none) · a rehearsal record.

**Deliberately not a field: "Description".** It becomes a place to put prose nobody reads. If it
matters, it belongs in *When to use this*.

---

## Writing rules

Step-level craft. The strongest codified rules come from nuclear emergency operating procedure
standards ○, which are the most mature written-procedure standards in existence, and they agree with
the software documentation style guides on the essentials.

**Voice and grammar**
- Imperative mood, verb first: "Restart the worker", not "The worker should be restarted" or "You
  can restart the worker."
- State *where* before *what*: "In the admin console, click Revoke" — the reader orients, then acts.
- Short sentences, ordinary word order, concrete nouns.
- Ban vague adverbs of degree and frequency — "frequently", "slowly", "as needed", "shortly". Give a
  number or a condition.

**Commands and values**
- Exact commands in code blocks, copy-pasteable, one command per block.
- Placeholders in a single obvious convention (`<region>`), with a note on where the value comes
  from. A placeholder the reader cannot resolve is a dead step.
- Never abbreviate a destructive command for readability.
- Show the *expected output*, not just the command, whenever the output is the verification.

**Warnings**
- A warning immediately precedes the step it governs — never at the top of the document, never after.
- It must be readable without scrolling past the step ◆ (the print-era rule is "without a page turn";
  the web equivalent is "not collapsed, not behind a fold, not in a sibling tab").
- A warning contains hazard information only, **never an action** ○. If the reader must do something,
  that is a step.

**Structure**
- Numbered steps for anything order-dependent. Bullets only for genuinely unordered sets.
- Tables for parameter/value lookups, never for sequential logic.
- A diagram only if it shows topology or state transitions that prose cannot; the procedure must
  remain executable without it.

---

## Branching, and steps that cannot be undone

Branching is where text procedures break down, and it is under-treated in software writing guidance.
The mature conventions come from nuclear procedure standards and aviation quick-reference handbooks ○.

**Condition first, then action.** Begin the step with the condition, not the action:
`IF <condition>, THEN <action>`. The reader must be able to skip an inapplicable branch without
reading the action at all — reading an action you should not take is itself a documented error mode.

**Cap the logic.** Nuclear procedure standards limit conditions joined by AND to four before
requiring a list format, and forbid mixing AND with OR in a single step because the result is
genuinely ambiguous ○. Adopt both limits.

**Make the branch visible in the layout.** Aviation QRH design uses three mechanisms together ○: an
explicit condition marker, lateral indentation grouping every step belonging to that condition, and
whitespace separating conditional groups. In Markdown:

```markdown
5. Check replication lag: `<command>`

   **IF lag is under 30s:**
   - 5a. Resume writes: `<command>`
   - 5b. Confirm: `write_errors` is 0 in `<command>` output.

   **IF lag is 30s or more:**
   - 5c. Do NOT resume writes.
   - 5d. Go to step 11 (Extended recovery).
```

**Confirm the branch before taking it.** Aviation requires explicit two-person agreement that a
condition holds before any conditional step executes ○. The software analogue for Tier 3: state the
observed value that put you on this branch before acting on it — writing it into the incident channel
is enough. Branch selection deserves the same verification rigour as step execution.

**Irreversible steps** get the treatment in [invariant 3](#3-state-the-abort-criteria-before-the-point-of-no-return-),
and they change the shape of the whole procedure. Where a cloud runbook can lean on "try it and roll
back", these cannot:

- device firmware flashing, fuse burning, secure-boot key provisioning
- a released mobile binary (you can halt a rollout; you cannot recall installs)
- destructive data operations, and anything past a retention boundary
- physical field service, where recovery may mean an RMA

For these, the pre-flight verification *is* the procedure. Budget most of the document to
establishing that conditions are right, and treat the irreversible action itself as one short,
heavily-guarded step.

---

## Domain adaptation

The invariants do not change. What changes is what "verify", "rollback", and "blast radius" mean.
Fill this table for the product before writing.

| | Verification signal | Rollback mechanism | Characteristic trap |
|---|---|---|---|
| **Backend / distributed** | metrics, health endpoints, log queries | redeploy previous version; drain and shift traffic | verification hits a cached or stale replica and passes falsely |
| **Frontend / web** | build hash in response, synthetic check, error-rate telemetry | feature flag; CDN purge; previous bundle | clients keep running broken code after the server is fixed — cache and service workers |
| **Embedded / device** | on-device indicator, telemetry heartbeat, physical observation | often none — recovery mode, A/B partition, or RMA | no remote shell; power loss mid-write; the fix must survive a device you cannot reach |
| **Data pipeline** | row counts, checksums, reconciliation against source | re-run *if* idempotent; restore partition; backfill | re-running a non-idempotent job doubles the damage; downstream consumers already read bad data |
| **Mobile release** | staged-rollout metrics, crash-free rate | halt rollout; forced update — never a true recall | store review latency means the fix is hours-to-days out; you must mitigate without shipping |
| **Regulated** | as above, plus recorded evidence | as above, under change control | the *execution record* is itself a deliverable — an unsigned step may be a finding |

**Invariant across all of them:** the reader is degraded; a verification step must yield an observed
value; irreversible actions need pre-flight checks and stated abort criteria; a procedure that
cannot be executed by someone other than its author is not finished.

---

## Maintenance — a runbook is only as good as its last rehearsal

Written procedures rot for a structural reason, not a moral one ✓. Rules written for the worst case
do not match everyday work, that mismatch generates pressure to deviate, and deviation quietly
becomes the norm. In software the mirror image dominates: the *system* moves while the document
stands still.

This is why deviation should be read first as a **document defect signal**. A review of the
violation literature found seven properties *of the rule itself* — hard to understand, hard to
comply with, violation needed to get the job done, outdated, conflicting without stated priority,
written by someone who does not know the actual work, and simply too many rules — all positively
correlated with the tendency to violate ✓.

> **When someone skips your runbook, the first hypothesis is that your runbook is wrong.**

**Rehearsal is the completion criterion, not authorship.** Both major software authorities pair the
document with exercise rather than treating the document as sufficient ✓, and the practice of
feeding exercise findings back into the text is explicit. AWS names "you document your procedures,
but you never exercise them" as the first anti-pattern of its game-day guidance ○.

The single cheapest, highest-yield check ○:

> **Have someone who did not write it execute it, and fix everything they stumble on.** Nuclear
> procedure standards go further — desk review is explicitly insufficient; correspondence between
> procedure and reality requires a physical walk-through, and confidence that it works requires
> simulation ○.

And the sharpest evidence in this whole area is a caution about mistaking the artifact for the
practice: when the WHO surgical checklist was rolled out across 101 hospitals and measured at
population scale, the mortality and complication benefits seen in the original study **did not
appear** ○. What was measured was the *date a checklist came into force* — not whether it was used
well. Having a correct document is not the intervention. Using it is.

**Practical cadence.** Link the runbook from the alert or dashboard that triggers it. Re-verify on a
schedule proportional to tier, and *always* after a change to the system it touches. Record when it
was last executed, not last edited.

**Progressive automation.** Automate steps that are deterministic and frequently executed, starting
with short, frequently-used procedures ○. Two cautions: automation removes the human verification
that made the step meaningful ◆ — carry the check into the automation rather than dropping it — and
even heavily automated environments still assume human-executed recovery exists ○. Keep the
human-readable procedure.

---

## Authoring protocol — when a model writes the runbook

This section is the part that is specific to you. It exists because machine-written procedures fail
in a characteristic, measurable way that human-written ones do not.

### Derive commands; do not generate them

**This is the highest-leverage rule in this guide.**

Models emit references to packages that do not exist at rates of roughly 4.6–6.1% even in the 2026
frontier cohort ○. Worse for the obvious mitigation: 127 package names were invented *identically by
all five models tested* ○ — so agreement between models is not evidence of existence. Verification
must go to the authoritative system, never to a second opinion. Independently, when an agent
generates operational commands on the fly rather than executing a stored template, the dominant
failure modes are instruction drift, dropped conditions, and syntax errors ○.

> **Rule.** Every command, path, flag, service name, environment name, and metric name in a runbook
> must be **derived from the repository or the running system**, not produced from knowledge of how
> such things usually look.

Derive from, in order of preference:

1. **CI/CD configuration** — the deploy, migrate, and rollback jobs. This is the most reliable
   source of the real command, because it is executed.
2. **Task runners and scripts** — `Makefile`, `package.json` scripts, `justfile`, `tox.ini`,
   `pyproject.toml`, `*.sh` in `scripts/`.
3. **Infrastructure and deployment manifests** — service names, replica counts, env names, resource
   identifiers.
4. **Alert and monitor definitions** — the exact alert names and thresholds that will be the
   runbook's trigger, plus the metric names to use in verification steps.
5. **The product's own Prawduct artifacts** — `operational-spec.md`, `observability-strategy.md`,
   and for unattended products `failure-recovery-spec.md`. These state intent; the repo states fact.
   Where they disagree, the repo wins and the artifact is stale (Principle 3).
6. **Existing tests**, especially integration and smoke tests, which encode real invocation and real
   expected output.

**If you cannot derive it, do not invent it.** Write an explicit gap marker and surface it:

```markdown
6. Restart the ingest worker.
   > 🚧 **UNVERIFIED — command not found in repo.** No restart target exists in CI config,
   > Makefile, or deployment manifests. Confirm the exact command with the service owner and
   > replace this line before this runbook is relied upon.
```

A visible gap is a working runbook with a hole. A plausible invented command is a broken runbook
that looks finished — and it is the more expensive of the two by a wide margin. Prawduct's Principle
5 (Honest Confidence) is not a style preference here; it is the difference between a document that
degrades gracefully and one that fails silently.

### Do not fabricate specificity

Precise-sounding numbers are the tell of a generated procedure: "wait 30 seconds", "if latency
exceeds 200ms", "retry 3 times". If the number is not derived from configuration, an SLO, an alert
threshold, or measurement, do not state it as though it were. Either derive it, or write the
condition qualitatively and mark it for an owner to pin down.

### Write for both audiences — do not optimize for yourself

When Microsoft researchers built agent execution over real runbooks, they explicitly **rejected**
converting them into a machine-oriented DSL, requiring that procedures "remain accessible and
comprehensible to human SREs, not exclusively optimized for automated agents", on the grounds that
machine-only formats create barriers for humans and complicate maintenance ○.

Structure that helps you also helps the tired human: explicit conditions, one action per step,
stated expected values, unambiguous commands. Where the two genuinely diverge — verbose schema
markup, embedded machine directives — **the human wins.** The runbook's purpose is the 3 a.m.
reader.

### Know the ceiling on autonomous execution

On the current SRE incident-diagnosis benchmark, no frontier model reaches 50% accuracy, and longer
agent trajectories correlate with *worse* results, because over-investigating agents surface
co-occurring symptoms as false root causes ○. That benchmark measures diagnosis only — it contains
no remediation — so it is not evidence that agents can safely *execute* operational steps.

> **Rule.** Write runbooks assuming a human authorizes consequential and irreversible steps. Mark
> each step as agent-safe or human-required. A step that is destructive, irreversible, or
> user-visible is human-authorized by default — an assumption a product may relax deliberately and
> in writing, never silently.

### Confidence, honestly

Mark what you inferred. If you derived a threshold from an alert definition, say so. If you guessed
the deploy command from convention, say that louder. A runbook that admits two uncertain steps is
trusted on the other thirty; a runbook that hides them is abandoned on first contact with the one
that fails.

---

## Self-review — rejection criteria

Run this against your own draft before calling it done. Any "no" is a defect to fix, not a caveat
to note.

**Executability**
1. Is every command derived from the repo or the running system — not generated? Can you name the
   file each came from?
2. Can a reader who has never seen this system execute every step without asking a question?
3. Is every placeholder resolvable from information the runbook itself provides?

**Verification**
4. Does every verification step name a specific observed value that means "pass"?
5. Search your draft for "verify", "check", "confirm", "ensure", "make sure", "looks good",
   "healthy", "working", "successful". Each hit is a suspected unmeasurable condition. Fix or
   justify every one.
6. Does "Done when" state an observable end state rather than "the procedure is complete"?

**Safety**
7. Is every irreversible step marked, preceded by its abort criteria, and stated to be
   irreversible?
8. Does each warning sit immediately before its step, and contain no actions?
9. Does the reader know, at every branch, how to tell which branch they are on?
10. Is there an exit for "reality does not match this document"?

**Structure**
11. One action per step — did you leave any "and then"?
12. Are critical and irreversible steps early rather than buried?
13. Under ~20 steps, or split into phases with checkpoints?
14. Does the header let a reader confirm in seconds that they are in the right document — including
    when *not* to use it?

**Honesty**
15. Is every number derived rather than plausible?
16. Is every uncertain step visibly marked as uncertain?
17. Does the ownership/last-verified metadata reflect execution rather than editing?

**The final test.** Read your runbook as someone woken at 3 a.m. who did not build this system. At
every step, ask: *do I know exactly what to type, and exactly how I will know it worked?* If the
answer is ever no, that step is not finished.

---

## Evidence — what is known vs. what is merely repeated

This research adversarially verified extracted claims with independent refutation votes, and
**killed roughly a third of them**. That kill rate is why this section exists.

### Well-evidenced ✓

Aviation human factors, surgical safety, and industrial safety science. Chiefly: Degani & Wiener,
*Human Factors* 35(2):28–43 (1993) and NASA CR-177549 (1991) — observed-value responses, critical
items first, checklist length, execution method. Dekker, *Applied Ergonomics* 34:233–238 (2003) —
practical drift and the double bind. Hale & Borys, *Safety Science* 55:207–221 (2013) — the seven
rule-related properties correlated with violation. Shields, Sazma & Yonelinas, *Neurosci. Biobehav.
Rev.* 68:651–668 (2016) — stress and working memory. Dawson & Reid, *Nature* 388:235 (1997) —
fatigue/BAC equivalence. NIST SP 800-61r3 §2.3 — procedure coverage prioritization.

**The domain-transfer caveat is load-bearing.** None of these studied software runbooks. The
mechanisms are generic to human procedure execution and Degani & Wiener explicitly sanction
cross-industry application, but every application here is analogical extrapolation, not a measured
finding about IT operations. Treat the mechanism as transferable and the magnitude as not.

### Influential doctrine, not evidence

Cite these as practice, never as measurement:

- **Google SRE's "~3x improvement in MTTR" from playbooks** is asserted with no data, sample size,
  time period, or methodology anywhere in the source ✓, and is undercut by Google's own later work
  arguing MTTR statistics are unsuited to incident decision-making. The SRE Workbook separately
  calls step-by-step playbooks internally "contentious".
- **NIST's claim that playbook formatting improves usability** carries no study or citation ✓, and
  its modality is "can improve".
- **PagerDuty's "an untested alert is equivalent to not having an alert at all"** is aphorism, not
  finding ✓ — and it is about alerts; extending it to runbooks is inference.

### Pending verification ○

Sourced and quoted, but not yet adversarially adjudicated when this was written: NUREG-0899 writing
and branching rules · aviation QRH layout and branch-confirmation conventions · Google developer
style guide procedure rules · AWS Well-Architected runbook metadata, peer execution, and progressive
automation · Cao, Chan & Elkamel (*Safety* 2019, 5(2):19) rationale experiment · Urbach et al.
(*NEJM* 2014) null replication · Microsoft StepFly defect taxonomy and dual-compatibility
requirement · Nissist TTM figure · package-hallucination rates · ITBench-AA ceiling.

Raw research, provenance, and resume instructions:
`.prawduct/research/runbook-authoring/CHECKPOINT.md`.

### Refuted — do not reintroduce ✗

These were killed by adversarial verification. They are plausible, circulate widely, and a model
will regenerate them from memory. **Do not use them.**

- The WHO checklist producing a "36.6% reduction in post-surgical deaths" in Scotland.
- Elling's Dutch-railway procedure figures (3% use them often, 79% say too many rules, …).
- Embrey's 400-respondent chemical-industry percentages (62% could not finish in time, …).
- The Delta 1141 "under one second between challenge and response" as *measured* evidence of hollow
  verification.
- NIST SP 800-61r3 recommending procedures be periodically tested to verify accuracy.
- PagerDuty requiring every alert to link a runbook as a hard gate.
- Dekker's "procedural deviation does not discriminate safe from unsafe outcomes."
- Dekker's "enforcement pressure is counterproductive."
- Startle halting action for a measurable 100 ms–10 s window.
- Visual short-term memory capacity falling with arousal.

**Modality drift was the most common failure** across all of them: "should where possible" hardening
into "must", "can improve" into "improves", "diminishes" into "monotonically", correlation into
causation. When you cite anything here, preserve the hedge.

---

## Related

- `templates/operational-spec.md` — Failure Recovery; the operational context a runbook serves
- `templates/observability-strategy.md` — "What You Get" scenarios are runbook triggers
- `templates/unattended-operation/failure-recovery-spec.md` — Recovery Procedures
- `docs/principles.md` — Principles 3 (Living Documentation), 5 (Honest Confidence),
  11 (Proportional Effort), 24 (Retrieval Over Generation)
