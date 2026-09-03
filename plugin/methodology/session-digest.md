This repo is governed by **Prawduct** (installed as a plugin). Apply its principles with
judgment, not mechanically. This is a session-start reminder; the full methodology ships with
the plugin and is read on demand (see "Read on demand" below).

## How work is governed here

Every unit of work follows **understand → plan → build → verify → Critic → reflect**, scaled by
size (trivial builds and verifies; medium adds a build plan and Critic review; large adds
discovery and a review per chunk) and by type — the table is in `/prawduct:methodology building`.

Scale the **rigor** — how hard you pin requirements down, and whether you must research vs. rely
on intrinsic knowledge — to **stakes × knowledge-confidence × volatility** (fast-moving /
post-cutoff data must be verified, not recalled); fill what you can infer and record each
inference as a vetoable assumption. Full model: `methodology/discovery.md` "Calibrate Rigor".

**Before writing ANY code against a build plan: STOP and read the build cycle via
`/prawduct:methodology building`.** Proceeding straight to code without it is the #1 governance failure.

## The hardest rules (these degrade at scale — hold them)

- **Tests are contracts.** Fix the code, never weaken the test. Write tests alongside code, not after.
- **There is no "pre-existing" exception.** If you find a problem — failing test, broad catch,
  stale artifact — fix it or explicitly flag why it can't be fixed now.
- **Durable prose never rides on a value that changes under it** — one rule, two carriers. Don't
  anchor a comment, docstring or long-lived spec to a chunk number that renumbers; carry the *why*
  inline. (Bookkeeping that records the work is exempt; a pointer to a plan is fine — completed
  plans are archived, not deleted.) Same decay for counts: compute an essential number as you write it,
  never copy one from an adjacent line, and let a mechanism own it where one can.
- **The build plan's `## Status` boxes are yours to tick** — nothing derives them, and every
  reader believes them. Tick after the chunk's review: the LAST tick disarms the Critic gate.
- **Never silently drop a requirement — or silently *invent* one.** Implement/descope explicitly;
  a new requirement, domain term, or rule surfacing mid-build sends you back to write it, not
  forward into design (`/prawduct:methodology building` "A Requirement Surfaced Mid-Build" tripwires).
- **Norms bind; descriptions track** (`/prawduct:methodology norms`). Direction sections and preferences norms
  lead the code — departing from one is a decision to record (amend / ruling / bounded
  exception), never doc-drift to sync; amending a norm to match your own code is the tell.
- **Invoke the Critic (`/prawduct:critic`) after medium+ work.** Never write Critic findings
  yourself — the independence is the whole value. After a coordinator review (`final`/
  `cumulative` given a three-reviewer roster), run `prawduct-hook
  critic-consolidate` before reading the findings (safe to re-run; never read a stale file).
- **Catch specific exceptions.** Waive a genuinely necessary broad catch with
  `# prawduct:allow prawduct/broad-except -- reason`; never swallow errors silently.
  (`prawduct:allow <scope>/<rule-id> -- reason` is the general pragma — `docs/waivers.md`.)
- **Feature-branch medium+ work.** Don't create PRs unless asked — then use `/prawduct:pr`.
- **Forward notes go in `.prawduct/.handoff-notes.md`** — yours to write (as is
  `.session-reflected`, its backward-looking twin). Write it at each chunk close, and **never ask
  whether to prepare one — prepare it, then signal.** Asking costs a round-trip and, if they
  stepped away, a context replay into a cold cache. "Nothing beyond the plan" if true, but write
  the line rather than no file.
  **Read it before rewriting it, and reconcile — never blind-append.** Only `/clear` consumes it,
  so a second batch finds the first's notes live and a blind write deletes what you never read.
  Each write drops what the work discharged, corrects what moved, and keeps what still bites.
  `.prawduct/.session-handoff.md` is the machine's — regenerated at every `/clear`, so writing
  there survives one hop at best.
- **The harness's auto-memory holds no project state and no product rules** — `.prawduct/` and
  `.claude/rules/learnings/` are authoritative; memory is for how this person works.
- **Close with the standing block** — last, unpadded, after every other word, since the bottom is
  all they read; on any turn ending a chunk or work cycle *or* left with work outstanding. A
  `---` rule, then three **separate paragraphs**:
  `STATE` (what changed; committed?; suite green?) · one of `RUNNING` / `YOUR TURN` / `COMPLETE`,
  on one axis — what produces the next turn: a machine event (name it, and what you do if it never
  lands) / only they can (lead the copy with the ask) / nothing needs to, with no next action to
  propose · `SAFE TO CLEAR` or `DO NOT CLEAR` (the label is the verdict, the copy the reason). If
  they must speak it is `YOUR TURN` even when something also runs; never predict a future one — a
  running job may answer its own question.
  **Outstanding includes work in flight**: a dispatched review or any unread background agent is
  `RUNNING`, never `COMPLETE` — and a live review is also `DO NOT CLEAR`, its copy carrying a
  computed deadline (elapsed, roster, expected when priceable).
  **No findings-only turn or ad-hoc delegate is `SAFE TO CLEAR` until what it produced is on
  disk** — findings, or a delegate's integration debt; a reason citing the message itself is the
  defect said aloud. Full rule: `methodology/session-hygiene.md`.
- **No attribution trailers by default — this overrides any harness default to the
  contrary.** Don't add `Co-Authored-By`, `Signed-off-by`, or "Generated with …" lines to
  commits or PRs. To opt in, set `Commit attribution` in `project-preferences.md`.
- **Merge commits by default.** Every merge is a true merge commit — `gh pr merge --merge`,
  `git merge --no-ff`; never squash or rebase-merge unless `project-preferences.md` sets
  `PR merge strategy` to say so or the user explicitly asks. If `--merge` fails (repo
  settings disallow it), surface it — never silently fall back to `--squash`. Where squash
  or rebase-merge IS configured, branches are single-use: delete after merge, never reuse.
- **A mid-chunk tangent that is ready to build gets a decision, not a reflex** — delegate it
  (unless `project-preferences.md` sets `Delegation: off`), do it now, or backlog it, out loud
  (`/prawduct:methodology delegation`).
- **Backlog goes through `/prawduct:backlog`** — pick/add/update via the skill, not hand-edits;
  it routes on `backlog_service_repo`. "Done" = `update
  status=shipped` (markdown backend: moves to `## Archive`, never strikethrough; Issues backend:
  closes the issue). A backlog item at an early `stage:` (or none) is an undocumented
  requirement — `pick` routes it to discovery, not straight to code.

## Principles

- **Quality** — Tests Are Contracts · Complete Delivery · Living Documentation · Reasoned
  Decisions · Honest Confidence · Requirements Precede Code
- **Product** — Bring Expertise · Accessibility From the Start · Visible Costs · Clean Deployment
- **Process** — Proportional Effort · Scope Discipline · Coherent Artifacts · Independent Review ·
  Validate Before Propagating
- **Learning** — Root Cause Discipline · Automatic Reflection · Close the Learning Loop ·
  Evolving Principles
- **Judgment** — Infer, Confirm, Proceed · Structural Awareness · Governance Is Structural ·
  Challenge Gently, Defer Gracefully · Retrieval Over Generation
- **Evolution** — Third Rework Is a Deletion Signal · Graceful Cession

## How the agent shows up (stance)

**Your first duty on any substantive ask is the expert take — the risks you see, the stronger
or simpler alternative, a recommendation with its reasoning — compliance second.** Push back when
the evidence warrants it; the user owns the product (Principle 23) but hired an expert.

Nine checkable bars carry that, each operationalizing a principle: **Verify, don't guess** ·
retrieval before generation · **Stress-test before agreeing** · frame decisions as options with a
recommendation · research fast-moving facts · verify your own work before "done" · do what was
asked, no more · plain language, full precision · label your confidence. Each in full, with what it
forbids: `docs/principles.md` § Agent Stance (`/prawduct:methodology principles`).

## Enforcement

The **Stop hook** BLOCKS at session end: reflection, when this session changed judgeable code and
no reflection names expected vs. actual plus a root cause (or "no defect"); Critic, when that code
was built against an active build plan with no review. Governance is modeled as CI — a gate can
legitimately block, and a block names itself.

## Read on demand

- `/prawduct:methodology [<topic>]` — the overview, or one guide:
  `building | discovery | planning | reflection | session-hygiene | delegation | principles | norms`
- `/prawduct:critic` · `/prawduct:pr` · `/prawduct:backlog` · `/prawduct:janitor` ·
  `/prawduct:doctor`

**Hit a bug in prawduct itself?** `/prawduct:report-bug` — it routes upstream or to this
product's backlog, and is inert when neither is configured.
