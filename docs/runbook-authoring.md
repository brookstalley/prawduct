# Runbook Authoring — How to Write a Procedure Someone Can Actually Execute

This is the canonical guide for producing runbooks in a Prawduct product. It is written to be
read by an agent that is about to author or review one, for a product in any language, on any
substrate — web frontend, backend service, embedded device, data pipeline, mobile app, CLI.

**The artifact you produce is for a human.** You may be the one who writes it, and increasingly
you may be the one who executes it, but the runbook's reason for existing is that at 3 a.m. a
tired person who did not build this system has to make it work. Every rule below descends from
that reader.

**How to use this guide.** Read [Read this before you use any of the rest](#read-this-before-you-use-any-of-the-rest)
first — it is short, and it is the difference between a runbook people use and one they don't. Then
the [Invariants](#the-invariants), which hold regardless of technology. Then work in this order:

1. [Proportionality](#proportionality) — how much procedure this task actually warrants
2. [Choosing the execution form](#choosing-the-execution-form) — read-do or do-confirm
3. [Anatomy](#anatomy) — what goes in it
4. [Writing rules](#writing-rules) and [Branching](#branching-and-steps-that-cannot-be-undone) — the
   step-level craft, and what changes when a step cannot be undone
5. [How the runbook gets found](#how-the-runbook-gets-found) — naming, indexing, alert linkage
6. [Authoring protocol](#authoring-protocol--when-a-model-writes-the-runbook) — the parts specific to
   a model doing the writing, above all *derive commands, never generate them*

Before you call it done, run the [rejection criteria](#self-review--rejection-criteria) against your
own output. If you are short on time, the two rules that recover most of the value are: **every
verification step names an observed value**, and **every command is derived from the repository**.

---

## Read this before you use any of the rest

**This guide is a diagnostic set, not a checklist to satisfy.** It is long because it catalogues the
many ways procedures fail. The runbooks it produces must be **short**.

If you apply everything here to every procedure, you will produce a thorough, complete, exhaustively
cross-referenced document that **no tired human will read** — and you will have failed, while
appearing to succeed. That failure mode is not a hypothetical risk of over-application. It is the
single most strongly evidenced finding in the entire literature below:

> As a list grows, the probability of overlooking any given item rises, and length itself drives
> operators to skip the procedure or execute it poorly ✓. Observed crews facing a long checklist
> degraded it into a hurried read-through, destroying the very redundancy it existed to provide.

A runbook padded with sections that do not apply is not "comprehensive." It is **diluted** — every
unnecessary line lowers the odds that a necessary one is read.

### The budgets

Treat these as limits, not targets. Exceeding one is a defect that needs a reason, not a badge.

| | Budget |
|---|---|
| Steps in one runbook | **≤ 20.** More than that, split it and give each part its own entry condition |
| | *Note the real tension: one-action-per-step, a separate numbered precondition before each irreversible step, and a step for every checking command are each mandatory and together push a two-phase procedure to about 20. Landing near the ceiling is expected, not sloppy. Split when you pass it; do not merge actions to squeeze under it.* |
| Steps in one phase | **5–15** |
| Words per step | Aim under 25 for the action line. The command can be long; the sentence cannot |
| Rationale lines | Only where a reader might reasonably skip or improvise the step. Not on every step |
| Sections | Only those that apply. **Deleting an inapplicable section is correct**, not lazy |

Real production runbooks average roughly 3,000 tokens and 5–15 steps ✓. That is your reference
point — not this document's length.

### The subtraction pass

After drafting, before reviewing, do one pass whose **only** purpose is removal. For each line ask
the one question that governs everything in this guide:

> **Does this raise the odds that this reader finishes the task correctly?**

Not *is it true*. Not *is it interesting*. Not *would they miss it* — that one is rationalizable for
almost anything. Only: does it move them toward a correct finish. If not, cut it. Specifically cut:

- Background and architecture the reader does not need to execute the step
- **Tool education** — what a flag abbreviates, how the underlying system works, why the interface
  is shaped this way. (What a command will *do to the reader's world* is not education — that stays.
  "This flag discards unsaved work in place" earns its line; "this flag is the short form of
  `--long-name`" does not.)
- Anything present because it is interesting, or because it explains how things came to be this way
- Rationale on steps nobody would skip anyway
- Sections carried over from the template with nothing product-specific in them
- Warnings about things that cannot happen in this procedure
- Any restatement of something already said once

**A step you deleted cannot be misread.** When in doubt between a shorter runbook with excellent
verification steps and a longer one that covers more ground, choose the shorter one every time.

### What is actually non-negotiable

Everything else in this guide is conditional. These are not:

1. Every verification step names an **observed value** — not "check that it worked".
2. Every command is **derived from the repository**, or visibly marked unverified.
3. Every irreversible step is **marked**, with its abort criterion before it.
4. The reader is told **where to go when it fails** or stops applying.

A four-step runbook that does those things is a good runbook. Ship it.

### What good and short actually looks like

This is a complete runbook. Not an excerpt — the whole document. It satisfies all four
non-negotiables and would pass the self-review, and it is under a page.

```markdown
# DiskSpaceLow — payments-db

## When to use this
Pager fired `DiskSpaceLow` with `instance=payments-db`. Confirm before acting:
`df -h /var/lib/postgresql` reports ≥85% used.
Not this alert, or a different instance? → see the index; do not continue.

## Steps
1. Check what is consuming space:
   `sudo du -xh /var/lib/postgresql --max-depth=2 | sort -rh | head -20`
   **Expected:** you can name the largest directory.

2. If `pg_wal/` is the largest, check for a stuck replication slot:
   `psql -c "select slot_name, active, restart_lsn from pg_replication_slots;"`
   **IF a slot shows `active = f`:** that slot is pinning WAL → go to step 3.
   **IF all slots are active, or none exist:** → go to step 5.

3. ⚠️ **IRREVERSIBLE — dropping a slot loses its replica's position.**
   Proceed only if the replica is confirmed gone or being rebuilt (ask #db-oncall).
   Abort if anyone is unsure → go to step 5.
   `psql -c "select pg_drop_replication_slot('<slot_name>');"`

4. Confirm space is returning:
   `df -h /var/lib/postgresql`
   **Expected:** used% is falling, and below 85% within 10 minutes.
   **If not falling after 10 minutes:** → step 5.

5. Escalate to #db-oncall with the output of step 1.
   Wake the DBA on-call if used% is above 95% — the database stops writing at 100%.

## Done when
`df -h /var/lib/postgresql` reports under 85% used, and `DiskSpaceLow` has cleared.

## If this doesn't work
- Disk filling with no obvious consumer → this procedure does not apply; page #infra.
- Escalate to: #db-oncall, immediately if above 95%.
```

Count what it does: names the trigger verbatim, gives a confirmable entry condition and an exit,
five steps, every one with an observed value, one branch written condition-first, one irreversible
step marked with its abort criterion before it, an observable done-state, and a wake-someone-up
threshold stated explicitly.

Now count what it *omits*: no architecture background, no explanation of what WAL is, no blast-radius
table, no prerequisites block, no close-out (it changes no state that needs putting back), no
duration estimate, no rationale on steps nobody would skip. Every one of those omissions is
**correct**. Adding them would make the document longer, more complete-looking, and worse.

---

**Evidence markers.** This guide distinguishes what is known from what is merely repeated:

| Mark | Meaning |
|---|---|
| ✓ | Verified against the primary source by independent adversarial review — three refuters, majority required to kill |
| ○ | Sourced and quoted from a primary document by a single researcher, but not put through adversarial challenge. Directionally trustworthy; do not lean on its exact wording or figures |
| ◆ | Reasoned design guidance. No study supports it; it follows from the evidenced findings |

The [Evidence appendix](#evidence--what-is-known-vs-what-is-merely-repeated) also carries a list of
**refuted** claims — plausible, widely-repeated, and false. Read it. They are exactly what a model
regenerates from memory.

---

## The failure this guide prevents

Bad runbooks do not look bad. They look complete. They have numbered steps, code blocks, and a
confident tone, and they fail in one of four ways:

1. **The unmeasurable condition.** "Verify the service is healthy." The reader cannot tell whether
   this passed. In the largest study of real production runbooks, this defect class was the single
   most common ✓ — more common than a step being outright wrong.
2. **The invented command.** A step that could not have worked, because the flag, package, or
   endpoint does not exist. This is the characteristic failure of a machine-written procedure, and
   it is measurable ○.
3. **The stale procedure.** Correct when written, false now, because the system changed underneath
   it and nothing forced the document to move.
4. **The procedure that runs out.** The reader reaches a step, reality does not match, and the
   document has nothing to say. It never told them how to know it had stopped applying.

Each of these destroys trust in the whole document, not just the step. A reader who finds one
wrong command stops believing the other forty.

### The procedure itself is a documented cause of major outages

This is not hypothetical. In each case below the operator did what the document said, or the
document's own design created the opening ○:

| Incident | The procedural defect |
|---|---|
| **AWS S3, us-east-1, Feb 2017** | An authorized operator followed an *established playbook*. The playbook exposed a free-text capacity-removal argument with no bound — a typo removed far more capacity than intended. |
| **GitLab.com, Jan 2017** | The runbook did not document that the recovery tool blocks *silently with no output*. An engineer read normal behaviour as a hung process and intervened. Backup procedures were separately found non-functional. |
| **Cloudflare, Jul 2019** | The written SOP was listed among the causes: it *permitted* a non-emergency rule change to go straight to global production, bypassing the staged rollout. The procedure was followed correctly and was still the cause. |
| **Atlassian, Apr 2022** | The peer-review step for a deletion script inspected the *endpoint* but not the *class of identifiers* passed to it. 883 sites were deleted; recovery took weeks. |
| **Knight Capital, Aug 2012** | The SEC's order makes procedural absence a regulatory finding: no written deployment procedure required a second technician to confirm the code had reached *all* servers. One server was missed. |
| **Deepwater Horizon, Apr 2010** | The negative-pressure test — the one test that would have revealed the failed cement job — had no standard written procedure and no interpretation criteria. Two crews read the same reading differently. |
| **Texas City refinery, Mar 2005** | The written startup procedure lacked instructions the board operator needed and had no defined way to suspend and resume across a shift handover. 15 people died. |
| **Swissair 111, Sep 1998** | Official TSB findings name checklist design as a risk factor: the applicable smoke-of-unknown-origin checklist could take 20–30 minutes to complete — longer than the aircraft had. |

Read the pattern. These are not mostly "the operator ignored the runbook." They are: an unbounded
operand, an undocumented silent behaviour, a review step that checked the wrong property, a rollout
scope the procedure permitted, a missing verification that a change reached every target, absent
acceptance criteria, no suspend/resume path, and a procedure too slow for its own emergency. Most
are authoring defects, and most map onto a rule in this guide.

Be precise about the ones that do not. Knight Capital's defect — no procedure required confirming
the deploy had reached *all* targets — has no dedicated rule below; the closest is "Done when" naming
an observable end state, which does not by itself force per-target enumeration. Treat that as a gap
in this guide rather than evidence for it, and when your procedure fans out across targets, verify
the fan-out explicitly.

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

### How the runbook gets found

A procedure nobody can locate under pressure has failed, however well written. Aviation treats
selecting the right checklist as its own design problem, and its rules transfer cleanly ○:

**Name it by the symptom, not by the cause.** Regulators direct that emergency procedures be
organized and indexed by the *observable triggering condition* — the thing the operator actually
perceives — explicitly **not** by the subsystem that is probably at fault. The responder has a
symptom, not a diagnosis, at the moment of lookup. So: "Checkout latency above SLO", not "Redis
connection pool tuning".

**Make the title match the alert text exactly.** The dominant commercial-aviation standard is that
the procedure's title matches the alert wording word-for-word, precisely so the operator can confirm
they opened the right document ○. Identity of string *is* the confirmation mechanism. If your pager
says `KafkaConsumerLagHigh`, the runbook is titled `KafkaConsumerLagHigh`.

**Index under every symptom that can surface it.** Where one failure presents through several
indications, the guidance is to make the procedure reachable from *every* one of them — deliberate
duplicate index entries pointing at one document ○. Optimize the index for the responder's entry
vocabulary, not the author's taxonomy.

**Write runbooks for un-alerted symptoms too.** When a failure produces no matching named alert, the
responder must diagnose *before* they can select a procedure — and NASA found procedures are usually
not titled by symptom, leaving exactly this gap ○. Cover "requests timing out, nothing firing" as a
first-class entry point.

**Make the link exist by construction.** Google's stated practice is a 1:1 alert-to-playbook-entry
relationship created at alert-creation time ○. Better still, the most widely deployed Prometheus
alert library *mechanically derives* each alert's `runbook_url` from the alert name via a
pattern ○ — so the link cannot be forgotten, and a missing runbook shows up as a visible 404 rather
than a silently absent link.

> **Rule.** Title by the responder's entry point. **If a named signal triggers this procedure** —
> an alert, an error code, a device fault code, a store-review rejection reason — the title is that
> identifier, character-for-character, because string identity is how the responder confirms they
> opened the right document. **If there is no such signal**, title by the symptom as experienced
> ("checkout failing for some users, nothing firing"). Either way the title names *what the
> responder observes*, never the component you believe is at fault — and if your alert names are
> themselves component-shaped, fix the alert names too. Then index redundantly under every symptom
> that could surface it, and put a resolvable link inside the notification the responder actually
> receives — not in a wiki they must go searching for.

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
checklist**.

**And interruptions are far more destructive than their length suggests** ○. In controlled work on
procedural error, interruptions averaging just **4.4 seconds tripled sequence-error rates** on the
steps that followed. The cost shows up as *resumption lag*, roughly doubling normal step-to-step
time, and it grows with both the duration and the cognitive demand of the interruption. External
cues reduce that lag — but only if the reader has 6–8 seconds to encode one *before* being pulled
away, which in practice they usually do not get. Sleep deprivation attacks place-keeping
specifically, not merely via general sleepiness.

This is the single most actionable piece of reader-model evidence, and it produces a hard rule:

> **The reader's place must be recoverable from the page, never from memory.** Stable step numbers
> that never renumber, one action per step, short named blocks with an explicit state-checkpoint at
> each boundary, and a document a reader can re-enter mid-procedure and orient in seconds.

An on-call responder is interrupted constantly — by pages, by questions in the incident channel, by
someone asking for a status update. A forty-step unbroken wall of text is not a neutral formatting
choice; it is a document that loses its reader at the first interruption and gives them no way back.

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
cluster to be *missing action descriptions and **unquantifiable conditions*** ✓.

> **Rule.** A verification step names the specific observed value that means it worked — and that
> value must be visible in the output of the command the step has *already* told the reader to run.
> If the reader can satisfy the step without looking at anything, the step is broken. If they can
> only satisfy it by running something the step never told them to run, it is also broken.

**The `Expected:` line describes what the reader will see. Nothing else.** That one contract
settles six questions that otherwise get answered wrong, and getting them wrong is what turns a
clean-looking runbook into one that cannot actually be followed:

- **It never contains a command, and never an instruction.** If confirming the result needs a
  *different* command, that command is its own numbered step. `Expected: git status -sb shows no
  [behind]` is a second action wearing a label — it collides head-on with
  [invariant 5](#5-one-step-one-action), and the reader has to invent the typing you left out.
  The same goes for telling them what to *do* with the output: *"…and every line above the first
  tagged one belongs in this release"* is reading work, and reading work is a step. The line
  describes; it never directs.
- **It comes after the command, never before.** It describes that command's output. A reader who
  meets the expectation first has to carry it in memory while hunting for the thing that produces
  it — which is exactly the working-memory load you are trying not to impose.
- **It names something the terminal actually prints.** `Expected: exit 0` fails: a shell displays
  no exit status. Name the visible output instead, or make the invisible thing visible in the
  command itself (`… && echo OK`).
- **It is omitted when the step cannot fail without the reader noticing.** The test is *silent
  failure*, not authorship. Typing a value into a file needs no expectation — you can see you did
  it, and it cannot quietly not happen. Running a command that a hook, a lock, or an empty index
  can reject does need one, because the rejection is precisely what the reader must be told to look
  for. Manufacturing an expectation on an unfailable step produces a tautology that costs a read
  and proves nothing.
- **More than one thing to check is a list, not a sentence.** The reader is comparing their screen
  against yours item by item, which is checking, not reading. Two observations run together in
  prose get half-checked. Break them out and let each be ticked off.
- **Say whether *all* of them must hold or *any* of them will do.** `Already up to date.` **or** a
  fast-forward summary is a very different instruction from status `ok` **and** replicas matching,
  and prose blurs the two. This is the same discipline the guide already applies to
  [branch conditions](#branching-and-steps-that-cannot-be-undone) — never mix `AND` with `OR` in
  one statement, and past about four conditions use a list — arriving at expectations for the same
  reason: combined logic read under pressure is where people substitute the reading they expected
  for the one in front of them.
- **Quote the distinctive fragment, not a transcript.** Enough for the reader to match, never
  enough that they have to read. A wall of expected output is skipped exactly like any other wall
  of text, and a reader who cannot tell which part of it matters will settle for "looks about
  right" — which is the unmeasurable condition this whole invariant exists to prevent.

```diff
- 4. Verify the service is healthy.
- 5. Confirm the migration completed successfully.

+ 4. Run: `<health-check command>`
+    Expected — all of:
+    - status is `ok`
+    - `ready_replicas` equals `desired_replicas`
+    If not: still lower after 2 minutes → step 9 (Rollback).

+ 5. Run: `<migration status command>`
+    Expected — all of:
+    - the last row's state is `complete`
+    - `error_count` is 0
+    If not: any other state → stop and escalate. Do not re-run the migration.
```

This rule makes verification steps measurable; it does not make every step a verification step —
see the fourth bullet above, and [criterion 26](#self-review--rejection-criteria), which rejects any
step dischargeable by recording it rather than doing something observable.

This applies identically to a device (`the status LED is solid green, not blinking`), a frontend
(`the response header includes the new build hash`), and a data pipeline (`row count in the target
table equals the source count for the partition`).

### 2. Critical and irreversible steps go early

Aviation doctrine places the most critical items as close to the *beginning* of a procedure as
possible, because the probability of completing an item without interruption falls as the procedure
runs on ✓. The source explicitly ranks this above sequencing by system topology or by external dependency —
"in most cases where this occurs, this guideline should take precedence" — a rare case of a standard
adjudicating its own conflicting rules. Note it is guidance, and the authors say their guidelines
"are not specifications".

The source defines "critical" as *accident-causing if omitted*. For software, read that as: the
step whose omission silently corrupts the outcome. The classic shape is a pre-flight check that is
technically needed only later, and therefore drifts to the end, and therefore gets skipped.

> **Rule.** Front-load: preconditions, the "do we actually want to do this" confirmation, the
> backup that recovery will depend on, and the capture of current state needed for rollback. Order
> by consequence first, convenience second.

**Every condition that would make the irreversible step *wrong* is verified before it, in its own
step.** Work backwards from the point of no return and list what must be true for it to be
*correct* — not merely what must be true to run it. Each of those gets its own earlier check.

This is easy to miss because a precondition tends to get written where its *command* naturally sits
rather than where its *consequence* falls, and the draft reads fine forwards: every step correct,
only the ordering fatal.

> **Deleting a late failure branch is not the fix.** If you find an *If not* that amounts to *"what
> you already did was done under the wrong conditions"*, you have found a **missing early check**,
> not a surplus branch. Removing it moves the hazard from late to invisible, which is worse — the
> reader now meets a bare error message with nothing to tell them what it means or that they are
> already past the point where it mattered.

Two classes get missed almost every time, because they feel like facts about the *situation* rather
than conditions of the *step*:

- **Has this already been done?** Doing it twice is a different failure from doing it wrong, and it
  usually fails quietly — the second run looks like the first until something downstream disagrees.
- **Am I acting on the intended target?** The right operation against the wrong host, table, device,
  account, or identifier is the shape behind several of the incidents above.

Both are cheap to check and cost the entire procedure when skipped.

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

As a list grows, "there **may be** a higher probability of overlooking any given item", and length
"carries the risk" that operators skip the document or execute it poorly ✓ — the hedges are the
sources' own. No experiment manipulated procedure length; the support is a human-reliability
handbook's estimate, operator self-report, and field observation. Field observation found crews
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

A step that chains a second action ("restart the service **and then** clear the cache") creates
documented problems ○: the embedded action gets overlooked and goes unperformed, per-step check-off
no longer proves the work happened, and the chaining word gets confused with conditional logic.

(NRC human-factors guidance on emergency operating procedures states this rule explicitly — the
logic word `THEN` "should not be used at the end of an action to instruct the operator to perform
another action within the same step, because it runs actions together." Verification found the same
passage attributed to more than one document in the NUREG series and disagreed on whether two or
three consequences are named, so treat the *rule* as well-founded and do not cite a specific
document or count for it without checking.)

> **Rule.** One imperative action per step. If you wrote "and then", split it. Sequential UI
> navigation is the only routine exception (`Settings > Advanced > Reset`).

**A chain in your source is not a step boundary.** Deriving faithfully means the command *text* is
derived; the *step structure* is yours to author. A reference document showing two commands joined
on one line is showing you one line of *that document* — it was written for a reader who already
knows the system, and copying its shape into a procedure hides the failure your reader needed to
see between the two halves. Split them, and let each carry its own expectation.

Keep a chain only when the second command must not run if the first fails *and* the reader has
nothing to check in between — and when you keep one, say so, because a reader who sees two commands
and one expectation will otherwise assume you forgot something.

### 6. Say why, next to the step but out of its way

A controlled experiment found that adding a short `PURPOSE` statement to critical steps raised
**one of two adherence measures** — following the correct steps in the correct order — from 44% to
68%, **with no measurable time cost**, and shifted the dominant reason for deviation away from "my
own method is easier or better" (43% → 10%) toward ordinary slips ✓.

Read that precisely: the other adherence measures the study tracked (adherence to timed waits,
duration within bounds) did **not** improve, and the participants were 60 students on a simulated
rig, not industrial operators. Rationale buys you *sequence compliance* and defuses the
"I know better" deviation — it does not make people wait when they are impatient.

This is in direct tension with invariant 4 — rationale is more words, and length is a defect. The
resolution is typographic, not editorial ◆:

> **Rule.** Keep the imperative action on its own line. Put the *why* on an adjacent, visually
> distinct line (blockquote, italic, or a `Why:` prefix). The eye executing the procedure skips it;
> the eye that is confused finds it. Do not bury rationale *inside* the action sentence.

**Rationale earns its place by changing what the reader does now.** *"This value is the update cache
key, so skipping it ships nothing"* is rationale: it tells someone tempted to skip the step why not.
*"This was missed in two earlier releases and backfilled out of band"* is history — it justifies the
rule to a reviewer and does nothing for the person executing it at 3 a.m. Cut provenance, incident
numbers, ticket references, and "we added this because". **Test:** if the reader would do the step
identically without the sentence, the sentence is not rationale, it is a footnote you owe some other
document. Nobody executing a procedure is a curious passer-by.

The line runs between **consequence** and **education**, and it runs through the middle of sentences
about the same command. *"This discards any unsaved work in place"* is consequence — it may send the
reader to save first, so it changes the run. *"This option is the short form of the longer one"* is
education — the reader types the same characters either way. Keep the first, cut the second, and
notice that being *about the command you just gave them* does not by itself earn a line.

```markdown
3. In `plugin.json`, replace `version` `3.1.0` with `3.2.0`.
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

## Choosing the execution form

Whether the reader *performs then verifies*, or *reads then performs*, is a structural safety
property rather than a formatting preference ✓.

- **Do-confirm** — the operator configures the system from competence, then runs a short list to
  verify it. This preserves what the aviation literature calls *configuration redundancy*: two
  independent shots at the same state.
- **Read-do** — the document leads the operator step by step. This gives you exactly one shot, and
  the original analysis is blunt that with this form "a mistake can easily pass unnoticed once the
  sequence is interrupted."

A step-by-step script executed cold is therefore the **weaker** form, not the safer one. It feels
safer because it is more explicit, which is why teams reach for it by default.

**The selection rule** ○:

- **Do-confirm** for *routine, frequently executed* work. Note the deliberate design: the checklist
  is a **subset** of the full flow — only the critical, failure-prone items — not a transcription of
  everything. Write the full flow once for training; keep the operational list short.
- **Read-do** when the exact ordering *is* the value, when steps are irreversible, or when the
  procedure is rare or high-stress and the operator cannot be assumed to hold it in memory.

That maps to software directly. A weekly deploy your team knows cold deserves a short verification
checklist, not a thirty-step script nobody reads. A once-a-year restore from backup deserves the
full read-do script, because nobody has it in memory and the ordering matters.

### Memory items — steps taken before the document is open

Some actions must happen before anyone opens a runbook. Aviation doctrine is strict about these ○:
they should be **avoided where possible**; where unavoidable they are capped at **fewer than three**
and are **forbidden from containing conditional or decision logic**. The operative criterion is
**time-criticality, not importance** — an action qualifies only when there is insufficient time to
reference the document at all. Being critical is not enough.

Two honest caveats. NASA states plainly that the criteria for *which* items should be memorized are
**not scientifically established** ○ — aviation has no principled answer either, so do not claim one.
And counting understates the cost: across 239 memory items coded from eleven quick-reference
handbooks, most were challenge-response items, and embedded conditionals and waits are memorized
burden too ○.

> **Rule.** Fewer than three, no branches inside them, each justified individually by "would the
> delay of opening the document itself cause irreversible loss?" — and drilled, because an
> undrilled memory item is a wish.

---

## Anatomy

Header fields first, so the reader can decide in seconds whether they are in the right document.

A calibration note. AWS publishes a runbook template carrying seven header fields — ID, description
and desired outcome, tools used, special permissions, author, last updated, escalation contact ✓ —
and it is a useful starting shape. But AWS offers it as an *example*, and states its actual minimum
far lower: "at a minimum, they should consist of a step-by-step text document" ✓. No evidence
establishes that any particular field set improves outcomes. Treat the list below as a well-reasoned
default to apply proportionately, not as a checklist to satisfy ceremonially — a runbook with three
fields and excellent steps beats one with twelve fields and vague ones.

**Genuinely always** — these five are the minimal runbook:

- **Title** — names what the responder observes, not the mechanism you suspect: "Database
  connection pool exhausted", not "Pool tuning". Where a named signal triggers the procedure, the
  title is that signal verbatim — see [How the runbook gets found](#how-the-runbook-gets-found) for
  the full rule.
- **When to use this** — the trigger/entry condition, phrased so a reader can match it against what
  they are seeing. Include the alert name or error signature verbatim if there is one.
  **Make it checkable, not merely descriptive.** *"The queue is backed up and you want it drained"*
  restates the reader's intention back at them and confirms nothing; if a command can show them
  they are in this situation, that command belongs here, before step 1. Two different jobs are
  being done — *am I in the right document* (the title does that) and *should I proceed, given what
  is actually true right now* — and only the second protects a reader who is mistaken about their
  own situation.
- **Steps** — numbered, one action each.
- **Done when** — the observable end state. Not "the procedure is complete" but the value that
  proves it. **Checked at the end, never recalled from the middle.** A line reading *"step 17
  printed nothing"* is a memory, not an observation: it says something was true earlier, the world
  may have moved since, and a reader who was interrupted has no memory to consult in any case.
  Each item names what they can see *right now*, which usually means naming the command again.
- **If this doesn't work** — the escalation path *and* the exit for "reality does not match this
  document". On a solo project "escalate" may mean "stop and look at it tomorrow" — say so.

**Only when they apply.** Run the test, then delete what fails it — an unused section left as "N/A"
still costs the reader a read to discover it is empty. Whole sections not applying to a whole
product is normal, not a gap: a library with no deployment has no blast radius or close-out; a
frontend-only product has no physical prerequisites; a product with no alerting has no trigger
signal.

- **When NOT to use this** — *if* a neighbouring procedure could plausibly be confused with this one.
  Selecting the wrong procedure is a real failure mode; aviation treats checklist selection under
  ambiguity as its own design problem.

  Write each entry **condition first**, as one line the reader can match against their own
  situation and discard in a second: `**If <what you are seeing or doing>:** → <where to go>`.
  This is the same condition-first rule as [branching](#branching-and-steps-that-cannot-be-undone),
  and it applies here for the same reason — a reader must be able to reject an entry before
  reading its explanation. **Do not explain the other procedure, and never narrate a documentation
  defect.** "Doc A's step 1 contradicts doc A's section 4, and section 4 wins" is a paragraph the
  reader must parse to extract one instruction. Name what they would observe, say where to go, and
  put the diagnosis somewhere it belongs — a comment, an issue, or a fix to the other document.
- **Prerequisites** — access, credentials, tools (with versions), physical items and consumables,
  required authorization level, and network position. Written as a checkable list, because
  discovering a missing credential at step 8 costs the whole procedure. Military technical-manual
  standards mandate exactly this as an `INITIAL SETUP` block on *every* work package ○ — tools,
  materials and replacement parts, personnel and skill level, referenced documents, and required
  starting conditions — and the S1000D schema makes it structurally non-optional. Adopt the habit
  even where you skip the ceremony.

  **A prerequisite that is a *decision* carries the rule for making it.** "The version number,
  decided" is not something a newcomer can tick — "a small feature is a patch bump, not a minor" is.
  A checkbox the reader cannot satisfy without judgment they do not have is a gap wearing a
  tick-box, and it sits *before* step 1, where they have the least help.
- **Expected duration** — *if* "is it stuck?" is a real question here.
- **Blast radius** — *if* the reader must judge whether it is safe to start. **Tier 3 states it
  before step 1 regardless**, even where the reader has no choice in the matter: the stakes are
  what calibrate how carefully someone reads, and a reader who learns at step 17 that this reaches
  everyone irrevocably learned it too late to have read the first sixteen differently.
- **Ownership and last-verified date** — *if* anyone other than the author will ever run it. When it
  was last **executed or rehearsed**, never when the file was last edited.

**Tier 3 adds:** explicit abort criteria per irreversible step · named authority per consequential
step · rollback procedure (or an honest statement that there is none) · a rehearsal record.

**Deliberately not a field: "Description".** It becomes a place to put prose nobody reads. If it
matters, it belongs in *When to use this*.

---

## Writing rules

Step-level craft. The most thoroughly codified rules come from US nuclear emergency-operating-
procedure guidance ✓ — the most mature body of written-procedure design in existence — and they
agree with modern software documentation style guides on the essentials.

One honesty note about that pedigree, because it is easy to overstate and this guide was corrected
on exactly this point: NUREG-0899 is **guidance, not regulation**. It presents its rules "in terms
of goals, intent and importance, rather than as specific requirements," and its foreword states
that "compliance will not be required" ✓. Read the rules below as very well-considered
recommendations from a domain with catastrophic consequences — which is a strong reason to adopt
them, and not a claim that anyone is legally bound by them.

**Voice and grammar**
- Imperative mood, verb first: "Restart the worker", not "The worker should be restarted" or "You
  can restart the worker."
- State *where* before *what*: "In the admin console, click Revoke" — the reader orients, then acts.
- **Sound like a colleague, not a standards body.** Address the reader as "you", use plain words,
  let contractions fall where they naturally do. Precision and warmth are not in tension: "you'll
  see two rows here — that's expected" is both. This matters because register sets expectation —
  a document written like a regulation gets read like one, which is to say skimmed. The sources
  behind these rules are institutionally formal because they are legal instruments; yours is not.
  Do not import their register along with their rules.
- Short sentences, ordinary word order, concrete nouns.
- Ban vague adverbs of degree and frequency — "frequently", "slowly", "as needed", "shortly". Give a
  number or a condition.
- **Never hedge an instruction.** "You may want to", "it might be worth", "this usually works",
  "if appropriate" — a hedge announces that you were unsure and hands the decision to the reader at
  the moment they are least equipped to make it. Every hedge is one of three things wearing a
  disguise, and each has a real fix: a **missing branch** (write the `IF`), a **missing number**
  (derive it), or an **unmarked gap** (mark it `🚧 UNVERIFIED` and name who can close it). Hedging
  is what authors reach for *instead of* the gap marker, and it is strictly worse — it reads like
  guidance while carrying none, so the reader cannot even tell they are on their own.

  Note the deliberate asymmetry with the
  [evidence appendix](#evidence--what-is-known-vs-what-is-merely-repeated), which insists you
  preserve every hedge you find. That governs **claims about research**; this governs
  **instructions to a reader**. Hedge what you know. Never hedge what to do.

**Commands and values**
- Exact commands in code blocks, copy-pasteable, one command per block.
- Placeholders in a single obvious convention (`<region>`), with a note on where the value comes
  from. A placeholder the reader cannot resolve is a dead step.
- **Show every placeholder filled in, once, where it first appears** — `<region>` (for example,
  `us-west-2`); `vX.Y.Z` (for example, `v3.1.1`). A reader who has to infer that `X.Y.Z` means
  `2.3.4` has stopped executing and started decoding. Being *technically* resolvable is not the
  bar; being unmistakable at a glance is. Bind it at first use and then use it consistently, so
  the reader never meets the same placeholder twice with two different explanations.
- Never abbreviate a destructive command for readability.
- **A repeated edit needs its instance list and one worked example.** "Do this to every entry above
  line 745" is not executable: the reader cannot see how many there are, cannot tell when they are
  finished, and has no model of what a finished one looks like. Give them a command that enumerates
  the instances, and show one before-and-after. Sweeps are where the tired reader silently stops
  early, and a half-finished sweep usually looks exactly like a finished one.
- **An instruction to edit a file is held to the same standard as a command.** "Bump the version"
  is not something a reader can execute. Name the file, the field, and what it becomes: "In
  `VERSION`, replace `3.1.0` with `3.1.1`." If the edit can be expressed as a command, give the
  command instead — a reader who has to decide *how* to make your change is improvising inside a
  procedure.
- Show the *expected output*, not just the command, whenever the output is the verification.
- **Label it `Expected:`, and label the failure branch `If not:`.** Use those two words and no
  synonyms — not `OK:`, `Success:`, `Result:`, and above all not `Pass:`. A label sits where the
  reader's eye expects an instruction, so it must not be readable as one, and `Pass:` is: the first
  reading is the verb ("pass *what*?"), and the reader only recovers the intended sense from
  context. `Expected:` cannot be read as a command, and it is the word this guide already uses in
  prose for the same idea. One term, one meaning, across every runbook in the product.

**Both readers, one page**

The hardest constraint here: you cannot assume the reader knows what they are doing, and you cannot
assume they do not. The person covering for a colleague on sick leave and the person who runs this
monthly open the same document.

A pre-flight checklist is run by a pilot on their first day and on their ten-thousandth, and it is
the same checklist. That is the target, and aviation hits it two ways this guide already documents
separately: the [challenge–response form](#1-a-verification-step-reports-an-observed-value-not-an-acknowledgment)
is telegraphic (`Altimeters — 30.10`), and the checklist is deliberately a
[*subset*](#choosing-the-execution-form) of the full procedure rather than a transcription of it —
the full flow is written once, for training, and lives somewhere else.

So the resolution is not "explain more for the newcomer." It is that **a runbook is not where
anyone learns the system.** When you feel pressure to teach, that is usually a different document
asking to exist, and a link to it costs one line instead of a page.

Keep one disanalogy in view: a first-day pilot has been through ground school, and the person
covering for a sick colleague has had nothing. Where that gap is real, the answer is still one line
and a link — and sometimes the honest answer is that they should not be doing this alone, which is
what the escalation exit is for.

Do not write for the middle, and do not write more. Use **channel separation** — the thing
[invariant 6](#6-say-why-next-to-the-step-but-out-of-its-way) already found for rationale, which
generalizes to everything the unfamiliar reader needs.

> **Rule.** Whatever the newcomer needs beyond the action sits on an adjacent line the expert's eye
> skips. One line. Never a preamble, a glossary, or a paragraph. If it takes more than a line, you
> picked the wrong word in the action itself — fix that instead.

- **Change the word before you explain it.** "Set `main`'s tree to `develop`'s" costs no more than
  "tree-set" and needs no gloss. A term you explain is usually a term you could have avoided, and
  the explanation is length you chose.
- **An unfamiliar command gets one clause on what it does to the reader's world** — "this
  overwrites your working tree" — not a tutorial. Familiar commands get nothing.
- **Give confusion its own exit, not just failure.** One line: *if a step doesn't make sense, stop
  and ask — that's a defect in this document, not in you.* A reader who is lost with no sanctioned
  way to stop will guess instead.
- **Name what undoes the reversible part, once, at the checkpoint.** Irreversible steps already get
  a recovery path; the reversible majority — where a first-timer actually gets stuck — gets one
  line at the phase boundary. That line is also the suspend-and-resume cue whose absence the
  [Texas City](#the-procedure-itself-is-a-documented-cause-of-major-outages) row records as fatal.

**Warnings**
- **A sentence describing destruction *is* a warning, and takes warning formatting.** "This
  overwrites your working copy in place" set as ordinary prose inside a step is invisible to anyone
  skimming, and skimming is what confident readers do. If losing track of the sentence would cost
  the reader work or data, give it the visual weight of a warning rather than letting it read as
  commentary. The test is the consequence, not the author's tone.
- A warning immediately precedes the step it governs — never at the top of the document, never after.
- It must be readable without scrolling past the step ◆ (the print-era rule is "without a page turn";
  the web equivalent is "not collapsed, not behind a fold, not in a sibling tab").
- A warning contains hazard information only, **never an action** ✓ — meaning no work is performed
  from inside a warning. Naming the abort condition and where to go instead *is* hazard
  information, so an irreversible block's `Abort if: … → step N` belongs there; a command the
  reader types does not. If the reader must run something, that is a step.

**Structure**
- Numbered steps for anything order-dependent. Bullets only for genuinely unordered sets.
- **Step numbers are stable identifiers.** Never renumber on edit — insert `7a` rather than shifting
  every number below. A reader who was interrupted at "step 12" and returns to a renumbered document
  has lost their place, which is precisely the failure the interruption evidence warns about.
- Tables for parameter/value lookups, never for sequential logic.
- A diagram only if it shows topology or state transitions that prose cannot; the procedure must
  remain executable without it.
- **The page must be navigable without being read.** Someone returning after an interruption — or
  skimming on purpose, which confident readers do — has to locate their step number, tell at a
  glance what they type from what they read, and catch every warning, all before reading a word.
  Commands in blocks, step numbers where the eye lands, warnings carrying visual weight, no
  unbroken prose. **Anything that is only correct when read in full will be read in part.**

**Legibility** (WCAG gives testable minimums ○ — note these are Level AAA, i.e. good practice rather
than baseline conformance, which is exactly the right bar for an emergency document)
- Lines no wider than **80 characters**.
- **Ragged right, never justified** — justification creates irregular word spacing that promotes
  line-skipping.
- Line height at least **1.5×** the font size, with clear separation between blocks.
- Do not place a step's action and its expected result in separate places the reader must mentally
  join; keep them adjacent. (Cognitive-load theory calls this the split-attention effect, though
  that evidence base concerns *learning* rather than execution under stress ○ — treat it as
  reasoning, not proof.)

---

## Branching, and steps that cannot be undone

Branching is where text procedures break down, and it is under-treated in software writing guidance.
The mature conventions come from nuclear procedure standards and aviation quick-reference handbooks ○.

**Condition first, then action.** Begin the step with the condition, not the action:
`IF <condition>, THEN <action>`. The reader must be able to skip an inapplicable branch without
reading the action at all — reading an action you should not take is itself a documented error mode.

**Cap the logic.** Nuclear procedure guidance says `AND` "should not be used to join more than four
conditions" — beyond four, use a list format — and says the use of `AND` and `OR` together within
the same step "should be avoided", because such combined logic statements "can be confusing and
ambiguous" ✓. Adopt both limits.

**More than one failure mode is a lookup, not a sentence.** A single failure stays inline —
`**If not:** <what to do>`. Two or more become a keyed list, because the reader arrives holding a
symptom and *scans* for it. Run them together as prose and you have handed someone a paragraph to
parse at the exact moment they are least able to:

```markdown
   **Expected:** <what success prints>

   **If not:**

   `<the exact string they are looking at>`
   - <what it means, one line — omit when it is obvious>
   - **<what to do>**

   `<the next exact string>`
   - <what it means>
   - **<what to do>**

   - Anything else → <where to go>
```

Three things make it work. The **key is the observable** — the literal error text, code, or symptom
on their screen, set apart so the eye finds it without reading; never a description of the failure
in your words. The **action is the visually heaviest element**, because it is what they came for.
And the **catch-all is mandatory**: a reader whose failure is not on your list has been abandoned
mid-procedure unless you tell them where to go, which is
[invariant 7](#7-tell-the-reader-when-the-procedure-has-stopped-applying) arriving one step down.

**Make the branch visible in the layout.** Aviation quick-reference-handbook design names three
mechanisms as "the main ingredients" of an error-resistant layout ✓: an explicit condition-marker
symbol, lateral indentation grouping every action belonging to that conditional group, and adequate
spacing between phases and between conditional groups. The stated purpose is to prevent two specific
error modes — *omission of an action*, and *performance of an undue, irrelevant, or inadvertent
action*. That second one is the reason condition-first ordering matters: a reader must be able to
discard a branch before reading its actions. In Markdown:

```markdown
5. Check replication lag: `<command>`

   **IF lag is under 30s:**
   - 5a. Resume writes: `<command>`
   - 5b. Confirm: `write_errors` is 0 in `<command>` output.

   **IF lag is 30s or more:**
   - 5c. Do NOT resume writes.
   - 5d. Go to step 11 (Extended recovery).
```

**Confirm the branch before taking it.** In QRH practice, agreement of *both pilots* on the `If…`
conditions is required before any conditional step is performed ✓ — note that this is agreement on
*evaluating* the condition, which includes agreeing that a branch does **not** apply. (The related
practice of verifying each action's result before proceeding is stated in the same source as a
recommended reinforcement, not a requirement — do not cite it as mandated.)

The software analogue for Tier 3: state the observed value that put you on this branch before acting
on it — writing it into the incident channel is enough. Branch selection deserves the same
verification rigour as step execution, because choosing the wrong branch produces exactly the
"inadvertent action" error the layout rules exist to prevent.

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

The industries that live with irreversibility have converged on four rules worth stealing ○:

**Give the precondition check its own numbered step.** OSHA's lockout/tagout rule does not fold
verification into the isolation step — it mandates a *separate, named verification* immediately
before hazardous work begins. Applied here: `7. Verify the backup is restorable` is its own step
with its own observable evidence, never a clause inside `8. Drop the table`.

**Split verify from commit.** NIST's platform-firmware guidance requires that an update to critical
data "shall be validated … prior to committing" — validation is a *distinct phase*, and the thing
validated is the payload itself (signature, checksum, format, bounds, correct target device), not
merely the operator's intent. Any irreversible operation should be two steps: check the artifact,
then commit it.

**Name the recovery path before the first irreversible step.** RFC 9019 requires that IoT devices
"must not fail when a disruption, such as a power failure or network interruption, occurs during the
update process", and enumerates exactly two recovery shapes: fall back to a known-good artifact
already present on the target, or re-obtain the artifact. Decide which one you have *before* you
start, and write it down. "We'll figure it out" is not a recovery path.

**Classify each step explicitly.** The US DOE handbook gives a usable definition of a *critical
step*: one whose incorrect performance causes **irreversible** harm — "an immediate negative
consequence that cannot be reversed." Apply that test literally to every step and mark the result.

### Close out what the procedure introduced

This is the most commonly omitted section in software runbooks, and it is mandatory in the mature
standards ○. OSHA requires an explicit sequence *before* equipment returns to service: inspect the
work area for leftover artifacts, confirm the system is reassembled and intact, confirm all people
are clear. Military technical-manual and S1000D standards go further — the S1000D procedural schema
makes preliminary requirements and **close-out requirements structurally required elements**, so a
procedure is *invalid* without them.

> **Rule.** *Where a procedure leaves state behind*, end it with a close-out block executed before
> the system is handed back:
> remove or account for everything the procedure introduced (debug builds, feature flags flipped,
> scaled-up capacity, maintenance mode, temporary credentials, silenced alerts), confirm the system
> is in its intended steady state, and confirm the incident channel knows it is over. A silenced
> alert nobody un-silenced is the classic residue — and the next incident goes unnoticed. A
> procedure that leaves nothing behind needs no close-out; that is a judgment you record, not an
> omission you drift into.

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

### The same invariant, in five substrates

[Invariant 1](#1-a-verification-step-reports-an-observed-value-not-an-acknowledgment) is the one
most often written badly, and it is easy to assume it only makes sense for a service with a metrics
endpoint. It does not. The rule is identical everywhere; only the instrument changes.

```markdown
BACKEND   ✗ Verify the service recovered.
          ✓ Run: <health command>
            Expected: `ready_replicas` equals `desired_replicas`, and error rate is
            below <threshold from the alert definition> for 2 consecutive minutes.

FRONTEND  ✗ Confirm the fix is live.
          ✓ Load <URL> in a private window with cache disabled.
            Expected: the `<build-hash meta tag / asset filename>` matches the hash
            printed by the deploy step. A matching hash on YOUR machine does not
            mean users have it — see step N for the client-cache check.

EMBEDDED  ✗ Check the device is healthy after flashing.
          ✓ Observe the status LED for 30 seconds after reboot.
            Expected: solid green. Blinking amber = boot loop → recovery (step N).
            No light after 30s = do NOT re-flash; the device is in <state>,
            power-cycle once and re-observe. Second failure → RMA, do not retry.

DATA      ✗ Make sure the backfill worked.
          ✓ Run: <reconciliation query> for the affected partition range.
            Expected: target row count equals source row count AND null count in
            <key column> is 0. Record both numbers in the incident channel —
            a partition that is merely NON-EMPTY is not a verified partition.

MOBILE    ✗ Verify the rollout is safe to continue.
          ✓ In <console>, read crash-free-sessions for the new version only,
            at a minimum of <N> sessions.
            Expected: at or above <baseline from the previous release>. Below it:
            halt the rollout (step N) — and note that halting does NOT remove
            the build from users who already have it.
```

Each right-hand example does the same four things: names the instrument, names the observed value,
names what counts as success, and says where to go on failure. That is the whole rule, and it is
technology-independent.

Note what the embedded and mobile cases add that the backend case does not need: an explicit
"do **not** retry" branch, because the retry is what bricks the device or burns the release. When
your product's failure mode is irreversible, the failure branch carries more weight than the success
path — which is the reverse of the cloud habit.

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
document with exercise — Google's phrasing is that it relies on playbooks "in addition to" its
Wheel of Misfortune drills, which establishes that both are used rather than that either alone is
inadequate ✓ — and the practice of
feeding exercise findings back into the text is explicit. AWS names "you document your procedures,
but you never exercise them" as an anti-pattern of its game-day best practice ✓.

The single cheapest, highest-yield check — and AWS states it plainly ✓:

> **"Once your runbook is documented, validate it by having someone else on your team run it."**
> Give it to a teammate, watch, and fix everything they stumble on.

Nuclear procedure guidance goes further, holding that no single validation method suffices — "some
combination of these or other methods should be used" ✓. It singles out one objective as method-bound:
establishing that the procedure matches the actual plant — that referenced controls, equipment, and
indications exist, carry the same designations and units, and behave as written — *can only* be done
by physical walk-through, not by desk review. For confidence that the procedure actually works it
recommends an approach including simulation ("should", not "shall"). The software translation is direct: reading a runbook proves nothing. Executing it
against the real system, or a realistic copy, is the only validation that counts.

And the sharpest evidence in this whole area is a caution about mistaking the artifact for the
practice. When surgical safety checklists were adopted across **101 Ontario hospitals** and measured
at population scale — 109,341 procedures before adoption against 106,370 after — the mortality
benefit seen in the original pilot study **did not appear**: 0.71% versus 0.65% (OR 0.91, 95% CI
0.80–1.03, P=0.13), and complications were flat at 3.86% versus 3.82% (P=0.29) ✓. The complication
endpoint is common enough that the study had ample power to detect a real effect.

What that study measured was the *date a checklist came into force* — not whether it was used, or
used well. This is the most important negative result in the procedure literature, and the lesson
transfers exactly: **having a correct document is not the intervention.**

The follow-up work explains the gap and turns it into authoring rules ○:

- A causal analysis of a stepped-wedge trial isolates **implementation quality, not content**, as
  the thing that moves outcomes — benefit appears only when *all* parts are actually performed.
  Partial execution is not partial benefit.
- Pooled adherence is far below what the positive trials achieved: **73% compliance but only 51%
  completeness.** The procedure was invoked three times in four, and fully performed only half the
  time. That gap is the portion of your claimed coverage that is nominal.
- **62% of 300 studies covering 7.3 million operations record only *that* it was done**, never how.
  A completion record is not evidence of execution quality.
- Ethnographic work states the mechanism plainly: the benefit comes from the *behaviour the
  checklist calls for*, not from marking its items. In the system that produced the null result,
  practitioners describe the checklist being marked complete when only partly performed.

Two rules follow, and they are sharper than the usual "keep docs fresh" advice:

> **Write steps so they cannot be satisfied by attestation.** A step that can be discharged by
> recording it *will* be discharged that way. Name the action and the actor, not a state to be
> attested — which is the same rule as [invariant 1](#1-a-verification-step-reports-an-observed-value-not-an-acknowledgment),
> arriving from a completely different direction.

> **Never let completion status double as a compliance metric.** The moment "runbook followed" is
> used for accountability, it stops being a measurement and becomes a reporting obligation, and it
> will be reported. Keep the audit signal separate from the compliance signal.

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

Models still emit install and import references to packages that **do not exist**. A 2026
replication across five frontier models measured overall rates of **4.62% to 6.10%** ✓ — improved
over earlier cohorts, but nowhere near zero. And 127 package names were hallucinated by *all five
models tested* ✓, so cross-model agreement leaks: it is a weaker filter than it looks, not a
sound existence check. (Be precise about what that second figure does and does not show — the
all-five overlap is a small fraction of any one model's hallucinated set, so consensus filtering
would still catch most of them. It is evidence that consensus is unsound as a *guarantee*, not
evidence that it is useless.)

The same defect appears in operational commands specifically: when an agent generates a command on
the fly instead of invoking a stored exact template, the dominant failure modes are **instruction
drift** (rewriting the template it was given), **structural omissions** (silently dropping
sub-conditions), and **syntax errors** ✓.

The conclusion both lines support: verification must terminate at the authoritative system — the
registry, the repository, the running service — and never at a second model's agreement.

> **Rule.** Every command, path, flag, service name, environment name, and metric name in a runbook
> must be **derived from the repository or the running system**, not produced from knowledge of how
> such things usually look.

This binds read-only commands too. A helper you compose to make a step checkable — an `awk`
one-liner over a state file, a `jq` filter — is generated tooling however harmless it looks, and
it is where invention hides most easily, because nothing appears to be at stake. It is also
unreadable to the substitute you are writing for. Prefer a command the repo already ships.

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

**When two sources in the repo disagree and you pick one, say so in the step.** A reader cannot tell
a derived step from an adjudicated one, and the next author will either re-litigate your call or
quietly reverse it. One clause naming the conflict and which way you read it is enough. This is not
a gap marker — nothing is missing; a judgment was made, and it should be visible as a judgment.

A gap marker obeys the same economy as everything else. Name **what is unverified**, **what the
reader does about it right now**, and **who can close it** — and stop. Not the evidence that it is
a gap: which files you searched, which past change failed to touch it, how you concluded it was
stale. A marker reciting how you established the gap has become a research note sitting in the
middle of a procedure, and it lands on someone deciding whether it is safe to continue. Three lines
is generous.

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
machine-only formats create barriers for humans and complicate maintenance ✓.

Structure that helps you also helps the tired human: explicit conditions, one action per step,
stated expected values, unambiguous commands. Where the two genuinely diverge — verbose schema
markup, embedded machine directives — **the human wins.** The runbook's purpose is the 3 a.m.
reader.

### The measured failure modes, in one place

Pin identifiers literally rather than trusting recall — the evidence for why is unusually direct ○:

| Failure mode | What was measured |
|---|---|
| Invented package names | Across 2.23M package references from 16 models, 19.7% hallucinated; **43% of hallucinated names recurred across runs** — these are repeatable, not random noise, which is what makes them exploitable |
| Rare/internal APIs | On a low-frequency API benchmark, GPT-4o produced only **38.58%** valid invocations; supplying documentation raised it to 47.94% |
| Outdated syntax | Across 270 real API updates, only **42.55%** of generated examples were executable *even with the correct current spec in context* — memorized older syntax leaks through anyway |
| Underspecification | On 2,208 DevOps prompt variants, agents violated action boundaries in **55.8–67.8%** of runs when instructions were underspecified but benign |

That last row is the one to internalize: **ambiguity in a procedure does not produce a question from
an agent — it produces an invented answer.** Naming the target of every state-changing step
unambiguously (which host, which namespace, which cluster, which table) is therefore among the
highest-value things you can do while authoring.

The third row is the one that humbles the obvious fix: writing the correct current syntax into the
procedure is *necessary but demonstrably not sufficient*. Which is the argument for deriving from
the repo and for rehearsal, not for trying harder to remember.

### Gate steps by reversibility, not by difficulty

The convergent guidance from agent-safety work is to couple the review mechanism to
**reversibility** ○: actions reviewed only after the fact should be the reversible ones; irreversible
actions require authorization *before* they run. Anthropic's own agent harness implements this as a
default-deny architecture — read-only by default, explicit approval for anything state-changing, and
unmatched commands failing closed to manual approval rather than proceeding on a guess.

NIST's generative-AI profile names **confabulation** as a distinct risk requiring monitoring in
consequential decision-making, and warns that outputs may include confabulated logic or citations
that appear sound ○. The operational consequence: treat any rationale an agent produces during
execution as unverified. Go/no-go thresholds and the abort path must be **written before execution**,
not judged at runtime by the thing executing.

> **Rule.** Split every procedure into an **observe** phase (read-only: inspect, query, measure) and
> an **act** phase (state-changing), and require the observe phase to complete first. Mark each act
> step reversible or irreversible. Reversible steps may run and be logged for after-the-fact review;
> irreversible steps stop and require explicit human authorization. Anything unrecognized fails
> closed to a human.

### Know the ceiling on autonomous execution

On the current SRE incident-diagnosis benchmark, no frontier model reaches 50% accuracy, and longer
agent trajectories correlate with *worse* results, because over-investigating agents surface
co-occurring symptoms as false root causes ✓. That benchmark measures diagnosis only — it contains
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

Run this against your own draft before calling it done: six restraint checks, then 26 criteria.

Scope it by tier. The restraint checks and criteria 1–12, 19–22 and 23–26 apply to **every** runbook
including Tier 1. Criteria 13–18 (findability, interruption survival) apply from Tier 2 up. Within
the tier that applies, a "no" is a defect to fix, not a caveat to note — proportionality decides
*which* criteria bind, never how well you satisfy the ones that do.

**Restraint** — run these first; they delete work rather than adding it

R1. Is it **20 steps or fewer**? If not, split it.
R2. Did you do the **subtraction pass** — one read whose only purpose was deletion?
R3. Is there any section present that has nothing product-specific in it? Delete it — including
    any left as "N/A" or "None". An empty section still costs a read to discover it is empty.
R4. Did you *decide* each optional section against its include-test, rather than keeping it because
    you could fill it in? Whole sections not applying to a whole product is normal.
R5. Would a responder doing this routinely on a Tuesday find it *fast* to use, not just correct?
    Read a paragraph aloud: does it sound like a colleague talking them through it, or like a
    regulation? If nothing in it addresses the reader as "you", you have written the wrong document.
R6. Read it as someone with 30 seconds and a page alert. Can they start acting immediately?

**Executability**
1. Is every command derived from the repo or the running system — not generated? Can you name the
   file each came from?
2. Can a reader who has never seen this system execute every step without asking a question — *and*
   can a reader who does this monthly skip everything that newcomer needed? If the second one has
   to wade, you wrote a tutorial.
3. Is every placeholder resolvable from information the runbook itself provides, *and shown filled
   in with a real example where it first appears*? `vX.Y.Z` without a `v3.1.1` next to it fails.

**Verification**
4. Does every `Expected:` line describe **what this step's own command prints** — not a value the
   reader could only see by running something you never told them to run, and not an invisible
   exit status? Does it sit *after* that command? Walk each one literally: type only what the
   step says, and ask whether the expectation appears on screen. Then: does it *describe* rather
   than direct? Where it names two or more observations, are they a list saying **all** or **any**
   rather than a run-on? Is it the distinctive fragment rather than a transcript?
4a. Conversely, does any step carry an `Expected:` line that just restates the action you were
    told to take, on a step that cannot fail without you noticing? Delete those.
5. Search your draft for "verify", "check", "confirm", "ensure", "make sure", "looks good",
   "healthy", "working", "successful". Each hit is a suspected unmeasurable condition. Fix or
   justify every one. Then search for "may", "might", "should probably", "usually", "typically",
   "if needed", "as appropriate" — each of those is a missing branch, a missing number, or an
   unmarked gap. Resolve it into whichever it is.
6. Does "Done when" state an observable end state rather than "the procedure is complete" — and is
   every item checkable *right now*, rather than a recollection of what an earlier step printed?

**Safety**
7. Is every irreversible step marked, preceded by its abort criteria, and stated to be
   irreversible? Does each have its own separate, numbered precondition-verification step?
8. Does each warning sit immediately before its step, and contain no actions?
9. Does the reader know, at every branch, how to tell which branch they are on? Where a step has
    two or more failure modes, are they a keyed list rather than a run-on sentence — keyed on the
    exact text the reader sees, action in the heaviest type, and a catch-all for the failure you
    did not anticipate?
10. Is there an exit for "reality does not match this document"?
11. Is the recovery path named *before* the first irreversible step, and is it one you actually
    have?
12. *If* the procedure introduced state that must be put back — flags, silenced alerts, temporary
    capacity, maintenance mode — is there a close-out block that removes it? A procedure that
    changes no such state needs none, and the worked example above is one.

**Findability** (Tier 2+)
13. Does the title match the responder's entry point — the triggering signal verbatim if one exists,
    otherwise the symptom as experienced?
14. Is it indexed under every symptom that could surface it, including the un-alerted ones?
15. If a signal triggers it, does that notification carry a resolvable link to this document? (If
    nothing triggers it, say where a responder is expected to find it instead.)

**Interruption survival**
16. Can a reader who is pulled away for ten seconds find their place from the page alone?
17. Are step numbers stable across edits?
18. Are there checkpoints often enough that no unbroken run of steps is long?

**Structure**
19. One action per step — did you leave any "and then"?
20. Are critical and irreversible steps early rather than buried? Work backwards from the point of
    no return and list every condition that would make it *wrong*: is each verified in its own
    earlier step? A late failure branch means a missing early check — deleting the branch is not
    the fix.
21. Under ~20 steps, or split into phases with checkpoints?
22. Does the header let a reader confirm in seconds that they are in the right document — including
    when *not* to use it?

**Honesty**
23. Is every number derived rather than plausible?
24. Is every uncertain step visibly marked as uncertain?
25. Does the ownership/last-verified metadata reflect execution rather than editing? A runbook that
    has never been executed correctly carries `null` — the defect is a date that records an edit.
26. Can any step be satisfied by *recording* it rather than *doing* something observable? If so,
    rewrite it — that step will be discharged on paper.

**The final test — four postures, one document.**

Read your draft once as each. They fail it in different directions, and one that survives all four
is finished. None of them is curious: every one is trying to get work done.

*Paged at 3 a.m., not the usual owner, unfamiliar tooling, no attention left.* Can they tell where
to start, and see at a glance what to type versus what to read? A wall of prose is unread text.

*Twenty years on this system, runs it twice a week.* Can they go straight to the commands without
wading? If the document is slower than working from memory they will abandon it — then it rots, and
then it is not there for the 3 a.m. reader either.

*Confident, skimming, barely paying attention.* They **will** skip; assume it. Is everything that
must not be skipped impossible to skip — carrying visual weight, sitting in the path, never in a
parenthetical or a trailing clause?

*New, anxious, wants to do this well.* They will not admit confusion, and they will do more than you
asked in order to be safe. Have you told them where to stop, that stopping is allowed, and what not
to do?

Serve only the first two and you get a document that is either safe and slow or fast and dangerous.

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

### Verified in a second, targeted pass ✓

A dedicated verification pass re-checked 19 further claims against their primary sources, three
independent refuters each. **Confirmed:** aviation QRH branch typography · AWS peer-execution
validation and the game-day anti-pattern · Urbach et al. (*NEJM* 2014;370:1029–1038) null
replication · the Microsoft StepFly defect taxonomy, dual-compatibility requirement, and on-the-fly
generation failure modes · the troubleshooting-guide time-to-mitigate figure · the ITBench-AA
diagnosis ceiling.

**Eleven were killed, and every kill improved this document.** The pattern was almost never
fabrication — it was *hedge-hardening*, the exact failure this guide warns about:

| What was claimed | What the source says |
|---|---|
| NUREG-0899 "mandates" writing rules | Non-binding guidance; "compliance will not be required" |
| Google "requires" one action per step | "**In general**, use one step for each action" — with a stated exception |
| AWS "prescribes a minimum field set" | An *example* template; AWS's stated minimum is "a step-by-step text document" |
| QRH "requires" per-action result verification | A recommended reinforcement — "such as" — not a requirement |
| Rationale "raised adherence" | Raised **one of two** adherence measures; timed-wait adherence did not improve |
| 127 shared names "falsify model consensus" | The source argues attack surface, and notes the overlap is a small fraction of each model's hallucinations |

Two of those corrections were live defects in an earlier draft of this very guide. That is the
argument for the whole approach: the claims were plausible, well-sourced, directionally right, and
wrong in their strength.

### Sourced but not adversarially challenged ○

A further investigation covering eight lines — public postmortems, domain variation, aviation
selection rules and memory items, checklist implementation evidence, interruption and place-keeping
research, alert-to-procedure linkage, irreversible-operation standards, and agent-execution
safety — completed its research but was cut off before its adversarial challenge phase ran. Its
findings are quoted from primary documents (OSHA 29 CFR 1910.147, MIL-STD-40051-2A, S1000D Issue 5.0,
NIST SP 800-193, RFC 9019, DOE-HDBK-1028-2009, FAA AC 120-71B, NASA/TM-2014-218382, WCAG 2.2,
official postmortems from AWS/GitLab/Cloudflare/Atlassian, the SEC order on Knight Capital, TSB
A98H0003, the CSB Texas City report, and the Deepwater Horizon commission report), and every one is
marked ○ here.

Treat those as directionally sound and specifically unconfirmed. Given that the verification pass
corrected roughly half of what it examined — almost entirely by softening overstated modality — the
prudent reading is that these findings are *real but probably stated a little too strongly*. Before
quoting any of them as a mandate, check the source.

One further caveat disclosed by the researchers themselves: that investigation ran with its web
search budget exhausted, so it worked from primary documents it could reach directly and could not
run discovery searches. Absence of a finding there is not evidence of absence.

Genuinely unaddressed: regulated-environment procedure requirements (FDA/GxP, ISO 13485), a
systematic treatment of machine-vs-human documentation audiences, and any empirical evidence that a
particular runbook *field set* improves outcomes — that last one appears to be convention
everywhere, including here.

Raw research, verdicts, provenance, and resume instructions:
`${CLAUDE_PLUGIN_ROOT}/.prawduct/research/runbook-authoring/CHECKPOINT.md`.

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
- That cross-model agreement has been *shown* useless for detecting hallucinated dependencies. The
  study says the opposite in one respect — the all-five overlap is a small fraction of each model's
  hallucinated set. Consensus is an unsound guarantee, not a worthless filter.
- That NUREG-0899 or Google's style guide *require* anything. Both are explicitly non-binding.

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
