This repo is governed by **Prawduct** (installed as a plugin). Apply its principles with
judgment, not mechanically. This is a supplemental session-start reminder — the full
methodology lives in the plugin and is read on demand (see "Read on demand" below). It does
not replace the authoritative rules in CLAUDE.md; it reinforces them.

## How work is governed here

Every unit of work follows **understand → plan → build → verify → Critic → reflect**, scaled
by size (trivial → build + verify; small → + update artifacts; medium → + build plan + Critic
review; large → discovery + chunked build + Critic per chunk) and type (feature → coverage;
bugfix → root cause + regression test; refactor → behavior preservation; …).

**Before writing ANY code against a build plan: STOP and read the build cycle via
`/prawduct:building`.** Proceeding straight to code without it is the #1 governance failure.

## The hardest rules (these degrade at scale — hold them)

- **Tests are contracts.** Fix the code, never weaken the test. Write tests alongside code, not after.
- **There is no "pre-existing" exception.** If you find a problem — failing test, broad catch,
  stale artifact — fix it or explicitly flag why it can't be fixed now.
- **Never silently drop a requirement.** Implement it or explicitly descope it.
- **Invoke the Critic (`/prawduct:critic`) after medium+ work.** Never write Critic findings
  yourself — the independence is the whole value.
- **Catch specific exceptions.** Mark a genuinely necessary broad catch
  `# prawduct:ok-broad-except — reason`; never swallow errors silently.
- **Feature-branch medium+ work.** Don't create PRs unless asked — then use `/prawduct:pr`.
- **No attribution trailers by default.** Don't add `Co-Authored-By`, `Signed-off-by`, or
  "Generated with …" lines to commits or PRs. To opt in, set `Commit attribution` in
  `project-preferences.md`.

## Principles (apply with judgment, not mechanically)

- **Quality** — Tests Are Contracts · Complete Delivery · Living Documentation · Reasoned
  Decisions · Honest Confidence · Requirements Precede Code
- **Product** — Bring Expertise · Accessibility From the Start · Visible Costs · Clean Deployment
- **Process** — Proportional Effort · Scope Discipline · Coherent Artifacts · Independent Review ·
  Validate Before Propagating
- **Learning** — Root Cause Discipline · Automatic Reflection · Close the Learning Loop ·
  Evolving Principles
- **Judgment** — Infer, Confirm, Proceed · Structural Awareness · Governance Is Structural ·
  Challenge Gently, Defer Gracefully

## Enforcement (this is what makes governance stick)

At session end the plugin's **Stop hook** runs the Critic gate + reflection gate. They BLOCK
session end when code changed against an active build plan with no Critic review or reflection
captured. Governance is modeled as CI — a gate can legitimately block, and a block message names
the gate so it's never mysterious.

## Read on demand (plugin skills — the full guides ship in the plugin)

- `/prawduct:methodology` — overview, the full principles, and an index of the guides below
- `/prawduct:discovery` · `/prawduct:planning` · `/prawduct:building` · `/prawduct:reflection`
- `/prawduct:critic` · `/prawduct:pr` · `/prawduct:backlog` · `/prawduct:learnings` ·
  `/prawduct:janitor` · `/prawduct:doctor`
