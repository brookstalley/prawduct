---
description: Author, review, or inventory operational runbooks — pre-written procedures for anticipated operational tasks (incident response, deploy/rollback, release, disaster recovery, maintenance, field service). Use when the user wants a runbook written or checked, or says /prawduct:runbook.
argument-hint: "[new <situation> | review <path> | list | survey] (omit to survey and propose)"
user-invocable: true
disable-model-invocation: false
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git log *), Bash(git ls-files *), Bash(git show *), Bash(ls *), Bash(cat *), Bash(find *), Agent
---

You author operational runbooks for this product. A runbook is a **pre-written procedure for an
anticipated operational task, executed under conditions worse than the ones it was written in** —
incident response, deploy and rollback, release, provisioning, disaster recovery, routine
maintenance, data backfill, device provisioning and field service.

**Not runbooks:** onboarding guides, architecture docs, API reference, tutorials, local dev setup.
If asked for a "runbook" for local dev setup, write a setup guide and say that is what it is.

## Read this first

**Read `${CLAUDE_PLUGIN_ROOT}/docs/runbook-authoring.md` before authoring or reviewing.** It is the
canonical guide — the invariants, the anatomy, the writing rules, branching, irreversible steps,
domain adaptation, and a 26-point self-review. It also carries an evidence appendix distinguishing
what is verified from what is convention, and a list of refuted claims you must not reintroduce.

Do not work from memory. This skill is the workflow; that document is the standard.

The blank artifact is `${CLAUDE_PLUGIN_ROOT}/templates/runbook.md`.

## Start short — the failure mode to avoid above all others

The guide is long because it catalogues how procedures fail. **The runbooks you write must be
short.** The most common way an agent ruins a runbook is by treating that guide as a checklist and
dutifully filling in every section — producing a thorough, complete document no tired human will
read. That is a failure that looks like success, and it contradicts the best-evidenced finding in
the whole literature: length itself drives people to skip a procedure or execute it badly.

**Default to the minimal shape.** For most procedures this is the entire document:

```markdown
# <trigger>
## When to use this
<entry condition, matchable against what the responder sees>
## Steps
1. <action> → Pass: <observed value> → If not: <where to go>
## If this doesn't work
<escalation, and the exit for "this isn't my situation">
```

Add a section only when the procedure actually needs it. **Budgets: ≤20 steps, 5–15 per phase,
action lines under ~25 words.** Real production runbooks run ~5–15 steps.

**Do a subtraction pass before you finish** — one read whose only purpose is deletion. Cut
background the reader doesn't need to act, rationale on steps nobody would skip, sections carried
from the template with nothing product-specific in them, and anything said twice.

It has to work for two readers: someone doing this routinely on a Tuesday who needs it to be *fast*,
and someone doing it at 3 a.m. for the first time who needs it to be *unambiguous*. Concision serves
both; padding serves neither. When choosing between a shorter runbook with excellent verification
steps and a longer one covering more ground, choose the shorter one.

## The rule that matters most

> **Derive every command from the repository. Never generate one.**

Models emit references to packages that do not exist at measured rates of 4.6–6.1%, and when an
agent generates an operational command on the fly instead of using a stored exact one, it drifts
from the template, drops conditions, and mangles escaping. A plausible invented command is worse
than a missing one: it makes a broken runbook look finished.

You have the repository. Use it. **Verification terminates at the authoritative system — the repo,
the registry, the running service — never at your own recall or another model's agreement.**

If you cannot derive something, mark it and leave the mark visible:

```markdown
> 🚧 **UNVERIFIED** — <what could not be confirmed> · confirm with <who/where> before relying on this.
```

## Operations

Route on the argument. With no argument, run **survey**.

### `survey` (default)

Propose which runbooks this product needs, ranked. Do not write one yet.

1. **Detect the substrate** — read `.prawduct/project-state.yaml` (structural characteristics), then
   the repo: languages, frameworks, deploy targets, whether it runs unattended, whether it touches
   hardware, whether it has a human interface. This decides what "verify" and "rollback" even mean here.
2. **Find what already exists** — glob for `runbook*`, `RUNBOOK*`, `docs/runbooks/`,
   `.prawduct/runbooks/`, plus `## Recovery Procedures` / `## Failure Recovery` sections in
   `.prawduct/artifacts/operational-spec.md` and
   `.prawduct/artifacts/unattended-operation/failure-recovery-spec.md`.
3. **Rank candidates on two axes** (the coverage rule from the guide):
   - **Frequency** — what actually happens, evidenced from git history, incident notes, alert
     definitions, `TODO`/`FIXME` around operational code.
   - **Recovery-criticality** — rare but catastrophic if absent. **Restore-from-backup is the
     canonical under-written one.** Also: credential/key rotation, the "everything is down" entry
     point, and for devices, recovery from a failed update.
4. **Present a short ranked list** with a one-line justification each, marking which are Tier 3
   (irreversible steps / user-visible / run by someone who does not know the system). Ask which to
   write. Recommend one.

### `new <situation>`

Author one runbook. Work in this order — **derivation before drafting.**

**Step 1 — Establish the trigger.** What does the responder observe? Find the exact alert name,
error string, exit code, or fault code. Grep alert definitions (`*.rules.yaml`, monitor configs,
`runbook_url` annotations), error constants, and log strings. The title will be that identifier
verbatim; if nothing triggers it, the title is the symptom as experienced.

**Step 2 — Derive the mechanics.** Do not draft yet. Collect, in this order of authority:

1. **CI/CD config** (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.) — deploy, migrate,
   rollback and release jobs. Most reliable, because it is executed.
2. **Task runners** — `Makefile`, `package.json` scripts, `justfile`, `tox.ini`, `pyproject.toml`,
   `scripts/`.
3. **Deployment/infra manifests** — real service names, replica counts, environment names, resource
   identifiers.
4. **Alert and monitor definitions** — exact alert names and thresholds; use these thresholds in
   verification steps rather than inventing numbers.
5. **Prawduct artifacts** — `operational-spec.md`, `observability-strategy.md`,
   `failure-recovery-spec.md`. These state *intent*; the repo states *fact*. Where they disagree the
   repo wins and the artifact is stale — say so (Principle 3).
6. **Tests**, especially integration and smoke tests — they encode real invocation and real
   expected output.

Record where each command came from. You will need it for the self-review.

**Step 3 — Classify.** Assign a tier (reversibility × blast radius × executor distance). Mark every
step reversible or irreversible using the operative test: *if performed wrong, can the initiating
action be reversed to restore the original condition?* Decide read-do vs do-confirm — routine
frequent work gets a short do-confirm verification list; rare, irreversible, or order-critical work
gets the full read-do script.

**Step 4 — Draft from the template.** Copy `templates/runbook.md`. Write to the product's runbook
directory (create `.prawduct/runbooks/` if none exists; follow existing convention if one does).
Name the file after the trigger.

Non-negotiables while drafting:
- Every verification step names the instrument, the observed value, what passes, and where to go on
  failure. **Never** "verify X is healthy."
- One action per step. Stable step numbers — insert `3a`, never renumber.
- Critical, irreversible, and state-capturing steps early.
- Every irreversible step: its own preceding numbered precondition-verification step, an abort
  criterion, and a named recovery path.
- Rationale on its own adjacent line, not inside the action sentence.
- A close-out block that removes what the procedure introduced — especially silenced alerts.
- Under ~20 steps, or split into phases with checkpoints.

**Step 5 — Subtract, then self-review.** First the deletion pass: remove every line a tired
responder would not miss, and every section with nothing product-specific in it. Then run the
guide's rejection criteria — start with the **Restraint** block (19a–19e), because those delete work
rather than adding it. The two highest-yield checks: every verification step names an observed
value, and every command traces to a file you can name. Fix, don't annotate.

If the draft exceeds 20 steps, do not ship it long — split it into separate runbooks, each with its
own entry condition.

**Step 6 — Report honestly.** Tell the user: what you derived and from where, what you could not
derive and marked `🚧 UNVERIFIED`, the tier, and — plainly — that **the runbook is not validated
until someone other than its author executes it.** Offer to enqueue that in
`.prawduct/operator-verification.md` if the product tracks operator verification.

### `review <path>`

Review an existing runbook. Do not rewrite it silently.

Run the 26 criteria. Then check the things only repo access can check:
- Does every command still exist? Grep each against the repo. Flag any that reference a deleted
  script, renamed service, or removed flag.
- Do thresholds still match the alert definitions they came from?
- Is `last_verified` a date it was *executed*, and how stale?

Report findings grouped **blocking / warning / note**, each with the file:line and a concrete fix.
Apply fixes only if the user asks.

### `list`

Inventory existing runbooks: trigger, tier, owner, last verified. Flag any never executed, any
stale beyond a year, and any alert in the repo with no runbook behind it.

## Proportionality

Principle 11 binds here, and it is the principle most at risk in this skill. A reversible,
small-radius task run by its author needs a few lines, not the full template. Do not push a family
app toward nuclear-grade procedure standards — the guide's tiering and budgets exist to prevent
exactly that.

The guide's four non-negotiables are the floor, and for many procedures they are also the ceiling:
observed-value verification, derived commands, marked irreversible steps, and a stated exit. **A
four-step runbook that does those things is a good runbook.** Ship it, and resist the urge to make
it look more thorough.

## Governance

Authoring runbooks is documentation work: no Critic gate unless it accompanies code changes. But if
you *discover* an operational gap while writing one — no backup exists, no rollback path exists,
an alert fires with nothing behind it — that is a finding. File it with `/prawduct:backlog add`
rather than papering over it with prose. A runbook that documents a procedure nobody can actually
perform is worse than no runbook.
