---
artifact: research
scope: opus-55-prompt-audit
status: ruled 2026-09-28 — every fork, wave and bookkeeping item taken; waves not yet applied
created: 2026-09-28
depends_on: [framework-efficiency-review-2026-07-02.md, program-purpose-and-cession.md]
absorbs: ["#181 (prose half)", "#341", "#342 (prose half)"]
---

# Opus 5.5 prompt audit — keep/delete decisions for the batch-veto sitting

## What this is

This is a disposition list for prawduct's **prompt surface**, meaning every piece of text that
reaches a model as instructions. Each decision is re-priced against Anthropic's guidance for
Claude Opus 5.5. The owner picks decisions in one sitting. Each apply wave then gets its own plan
and a Critic review. Nothing here has been applied.

**Why now.** `program-purpose-and-cession.md` sorts what prawduct hedges into three piles, and
says the *runtime judgment* pile "depreciates via model releases". Opus 5.5 is such a release.
Anthropic's guidance for the Opus 5 generation names specific instructions that now degrade
behavior:

- telling the model to verify its own work;
- pushing it to delegate;
- emphasis that over-triggers;
- step-by-step scripts for judgment tasks.

The Opus 5.5 guide adds one more: Opus 5.5 ends turns early, by announcing the next step instead
of taking it, offering to continue, or listing decisions it could make itself.

## Result at a glance

There are **192 decisions** across five slices, and every quoted piece of evidence has been
checked verbatim against its file (see "Method").

| | Count |
|---|---|
| By action | 150 rewrite · 25 remove · 5 move · 4 add · 8 flag |
| By confidence | 45 high · 138 medium · 9 low |
| Duplicated facts (#342): the decision names the other copy | 39 |
| Depends on Opus-5-class capability (`model_dependent`) | 32 |
| Touches text a test or parser reads (`machine_read`) | 49 |

The slices, one file each, are in `opus-55-prompt-audit-2026-09/`:

- **A**: the always-on surface (session digest, root `CLAUDE.md`, `principles.md`, learnings
  rules, and text that hooks and gates print).
- **B**: methodology guides and templates.
- **C**: the Critic, the PR reviewer and their agent definitions.
- **D**: the operational skills.
- **E**: the plugin's reference docs.

Four findings carry most of the value:

1. **Nothing always-loaded tells Opus 5.5 not to stop early** (A-1). `session-hygiene.md` step 1
   says "do it — do not end the turn", but the digest (the one surface every session reads)
   leaves that step out. Three methodology lines go further and license the stop (B-9, B-16,
   B-35).
2. **The builder is told to re-check work that Opus 5+ already checks, and that an independent
   reviewer is checking at the same time.** For example, `building.md:201` says "deep-scrub your
   own changes while it runs" (B-1). `core.md` carries nine separate "falsify your claim before
   writing it" rules (A-8).
3. **Several surfaces make delegation the default.** For example, `delegation.md:67` says
   "Delegation is offered first" (B-13). Anthropic's Opus 5 guidance says to remove "delegate
   more" guidance, because this generation already over-delegates.
4. **One reviewer prompt filters before it reports.** `pr/review-protocol.md` says to flag
   oversize "only if splitting is cheap" and to file "what a maintainer would genuinely want
   changed" (C-1). Anthropic's guidance says this pattern depresses recall on Opus 5+. The Critic
   prompts already rate every finding and are clean on this.

The largest single token saving is C-8. About 6,200 of the ~8,700 words in `review-cycle.md` are
builder and maintainer material, yet every `final` or `cumulative` reviewer loads the whole file.
Splitting it saves roughly 8k tokens per dispatched reviewer. That figure is estimated from word
counts, not measured.

## Rulings (owner, 2026-09-28)

The owner ruled all 18 items in one sitting on the review page
(https://claude.ai/artifact/YHf1VEC3SFVX1dBZu7yTDa, db collection `rulings`). Every item is
**take**. Where a recommendation was split (F5, the release plan), take means the recommendation
as written. Two rulings carry notes that change how the waves apply:

- **F1: take, with a note.** The owner's note: "Sonnet 5.5 shipped today, and be aware it may be
  used as a subagent, but it will rarely/never be the main agent." This is consistent with the
  model-floor norm, which allows Sonnet for a subagent, so nothing needs amending. It retargets
  the probes:
  - **Floor probes run on Sonnet 5.5**, not Sonnet 5.
  - **Weight them by who reads the surface.** Surfaces only the main agent reads (the digest, root
    `CLAUDE.md`, hook and gate text) are probed on the session model. Surfaces a subagent reads
    (reviewer prompts and agent definitions in W3, and the parts of `building.md`,
    `delegation.md` and the templates a delegate follows in W4) get the Sonnet 5.5 probe.
- **F4: take, with a note.** The owner's note: "Fine to not be the default, but delegation should
  be used when it will accelerate wall clock without materially creating conflict." The owner's
  criterion replaces "sizeable" as the test in A-21, B-13 and B-15. Their replacement text in the
  slice files now says so, and each is marked `owner amendment`. Size stays in B-15 only as the
  proxy for wall-clock gain.
- **F5: take the recommendation.** Apply B-23, B-25 and B-26. **B-21 and B-22 stay held** until a
  Sonnet 5.5 discovery probe, which W4's plan carries.
- **F2, F3, F6 and F7: take.** F6 carries its measurement: compare `review-stats` rounds per PR
  before and after W3.
- **W1–W6: take.** They run in order, W1 first, one plan and one feature branch each.
- **#181 bookkeeping: take every row.**
  - Close #297 and #318 as not planned.
  - Record "retire" on #301, which stays open as mechanism-half work.
  - Record "do" on #303.
  - Close the three moot deferrals on the record in #181's thread.
  - **Archive `release-plan-backlog-service-golive.md`.** Its VRF rows were never its to keep:
    VRF-005 and VRF-007 are `pending` in `.prawduct/operator-verification.md`, where #183's
    2026-09-01 drain disposition awaits the owner's `accept-operator-verification` signature.
    VRF-008 is already `accepted`. Archiving the plan leaves that queue as the one place they are
    owed.

## Found while applying (W1, 2026-09-28)

These came up while applying W1 and were not enumerated by the audit. None is filed:
Cycle 2 of #181 adds no new backlog items (§ How this honors #181's constraints), and the
fix-don't-file preference covers the rest. They are recorded here, where the owner reads.

- **A-16 reaches new scaffolds only (awaiting the owner's ruling).** `core.md` is scaffold-once. Product repos
  onboarded before W1 keep the old "name the rule and say what it changes… or that it does not
  apply" header, which is the narration A-16 set out to stop. They still lint clean, because the
  header is excluded by grammar and a test pins that. There are three options:
  - **Leave it.** The cost is narration in older repos, and the owner can re-scaffold any repo by
    hand.
  - **Put one line in the digest** telling the model not to narrate rules that don't apply. The
    digest reaches every repo, but the line would contradict what an old header says.
  - **Add a repair** that replaces a byte-identical old header. This is a new write into product
    files, which architecture's "the plugin writes nothing into a governed repo except…" norm
    would need to admit.

  **Recommendation: leave it.** The harm is verbosity, not a wrong action.
- **A-18's shout survives on two carriers.** `plugin/skills/methodology/SKILL.md:11` belongs to W5,
  which should apply A-18's wording there. The thin product anchor (`anchor_repair.ANCHOR_V4`,
  `migrate_plugin`) would need a new anchor version pushed to every product repo. It is recorded,
  not proposed.
- **A-1 and `session-hygiene.md`'s chunk-boundary stop disagree until W4 lands.** Slice-B:443
  owns the fix, so W4 should follow W1 closely.
- **Short-plan review inference cannot reach `cumulative`** while the tick rule holds every box
  until review. `critic_mode._mid_plan_start` counts 2 or more unticked boxes as mid-plan, and on
  a short plan that answers `deferred`. W1 dispatched `cumulative` explicitly. Fixed on `fix/short-plan-tick-deadlock`, stacked on W1, with the owner-confirmed
  direction: a short plan's earlier chunks are ticked at commit.

## Decisions for the owner

These are the real decisions, the ones that change a policy, a principle or something the owner
built deliberately. Everything outside this section is bulk-confirmable (§ Apply waves). Each
fork below gives a recommendation.

### F1 — Target model, and whether `model_dependent` decisions ship

`project-preferences.md` § Model floor makes Sonnet the floor for every consumer. 32 decisions
remove text that a Sonnet-class model might still need.

**Recommendation: ship them, with one behavioral probe per wave on Sonnet 5.** Anthropic's
Sonnet 5 guidance says it will "run self-verification loops more readily" and follows instructions
literally. So the self-check and delegation cuts point the same way on the floor model. The
exception is the discovery scaffolding in F5, which is where the floor could plausibly regress.

A probe here means a fresh session using the changed guidance on a real task, per the authoring
rule "Before recommending changes to guidance material, have a fresh agent USE it on a real
task".

### F2 — Consolidate the learnings rules (A-8 to A-16, A-31 to A-38)

This consolidation touches three layers:

- **`core.md` goes from 38 rules to 17.** Nine claim-falsification rules become two. The
  class-vs-instance, enumerate-by-query, update-what-describes-it, open-what-you-cite and handoff
  clusters each merge. Four rules that duplicate the digest or a principle are deleted. A-15 is the
  per-rule index.
- **The area files merge the same clusters.** `authoring.md`, `tests.md`, `hook-surface.md` and
  `reviews.md` each drop duplicates of `core.md`.
- **The header obligation goes.** Each file's header currently requires the agent to name each
  applicable rule and say what it changes. That becomes "apply where it bears; cite where it
  changed what you did" (A-16).

A-38 keeps the one-line-plus-Tell format but strips issue ids and incident specimens from inside
the rules. This fork overlaps #908 ("decide whether the reflection gate earns its cost").

**Recommendation: take it.** The format is sound, and the defect is accretion. Nine rules restating
one principle is the "patch accretion" row of Anthropic's audit method, and those nine are mostly
self-verification that Opus 5+ does unprompted.

### F3 — Stop telling the builder to re-check its own work

- **A-22** renames the stance bar "verify your own work before "done"" to "show evidence for
  "done"". This changes a principle's wording (`principles.md:119-120`), so it counts as
  *Evolving Principles*.
- **B-1**: no self-scrub while the Critic runs.
- **B-19**: no five-perspective self-review between artifact phases.
- **B-36**: no separate "verify artifacts are current" step.
- **E-5**: the runbook guide's three re-read passes become the rubric only.
- **D-40**: drop the migration eyeball-check that the `verify-migration` gate supersedes.
- **B-10, B-11 and B-12**: a delegate's "Done" arrives with its evidence, so the coordinator
  reads that evidence instead of repeating the sweep.

**Recommendation: take all of them.** The independent Critic and the PR reviewer are untouched,
and the output contract ("show evidence for done") still binds.

### F4 — Stop making delegation the default

- **A-21**: the digest's tangent bullet lists delegation last and scopes it to sizeable tracks.
- **B-13**: "Delegation is offered first" goes.
- **B-14**: `building.md`'s third copy of the default goes.
- **B-15**: independent chunks must also be *sizeable* to count as "the ordinary yes".
- **D-26**: `/prawduct:backlog add` stops listing delegation first.
- **B-2**: no mandated subagent for a consumer grep.
- **D-59**: the methodology index's delegation line is trimmed.

`delegation.md` itself calls "offered first" "a *policy* setting". The owner's `Delegation` row
still overrides every one of these.

**Recommendation: take all of them.**

### F5 — The Wave 3 "weaker-model scaffolding" shipped in #299

- **B-26 (red-baseline protocol).** As written, it says "not yours; record it" four lines above
  "There is no 'pre-existing' exception". The rewrite keeps both commitments and says how they
  fit. **Take it**: it fixes a contradiction.
- **B-23 (root-cause stopping rule).** It keeps the criterion and drops the meta-framing. **Take it.**
- **B-25 (3–4 file tie-break).** The risk property becomes the classifier, and the count stays a
  proxy. **Take it.**
- **B-21 (domain-concern table) and B-22 (numeric question and search quotas).** **Hold both**
  until a Sonnet 5 discovery probe. Discovery quality on the floor model is where removing a
  checklist could regress, and no evidence here says it would not.

### F6 — Reviewer prompts

This fork touches the owner's "review wall clock is P0" and "never skip the PR reviewer" rulings.

- **C-1**: the PR reviewer reports every release-readiness defect at its severity and leaves
  disposition to the builder. Reporting more could mean more findings. It should not mean more
  rounds, because ACCEPT is the default disposition and costs no round.
- **C-22**: drop "do not invent findings", which leans toward under-reporting.
- **C-23**: drop the work-size review-depth coaching.
- **A-29**: drop three "spend this on…" closers from the reviewer directives.
- **C-17**: "CRITICAL" and three repeats of "never create without the reviewer" become one plain
  sentence. The rule stays, and Step 4 still enforces it mechanically.

**Recommendation: take them all, and compare `review-stats` rounds-per-PR before and after.**
That measurement is the one that answers the wall-clock question.

### F7 — Scope bookkeeping for #181, #341 and #342

- **#341 closes with wave 4.** B-17, B-18 and B-19 complete its enumeration. Its acceptance
  criterion ("a builder who finds a better route takes it and records why") is exactly what their
  rewrites say.
- **#181.** This pass is its prose half. Its mechanism half has not been enumerated: the change
  log, the archive-plan advisory and gate code (§ #181 bookkeeping). **Recommendation: keep #181
  open, with its body updated to say the prose half shipped here**, rather than filing anything
  new.
- **#342.** This pass enumerated 39 duplicated *prose* facts on the prompt surface. It did not
  address #342's other criterion (the four single-purpose mechanisms should become references to
  the general norm) or duplicated *derivations* in code. The unmerged branch `docs/one-home-per-fact`
  holds a 212-line requirements draft for that remainder. **Recommendation: keep #342 open for it.**

## Apply waves (bulk-confirmable)

Each wave is one plan and one feature branch. Each wave lowers the token ceilings it trims under,
in the same commit, and edits the tests that pin the old text per the prose-test taxonomy (§ Binding
norms). Fork-dependent decisions ride the wave that owns their file.

| Wave | Files | Decisions (fork-dependent in brackets) |
|---|---|---|
| **W1 Always-on** | digest, root `CLAUDE.md`, `principles.md`, learnings | A-1, A-2, A-3, A-4, A-17, A-18, A-19, A-20, A-23, A-24, A-25, A-26, A-39 · [F2: A-8–A-16, A-31–A-38] · [F3: A-22] · [F4: A-21] |
| **W2 Hook and gate text** | `lib/critic_consolidate.py`, `lib/gates.py`, `lib/briefing.py`, `bin/prawduct-hook`, their tests | A-5, A-6, A-7, A-27, A-28, A-30 · [F6: A-29] |
| **W3 Review machinery** | `skills/critic/*`, `skills/pr/*`, `agents/*` | C-2 to C-16, C-18 to C-21, C-24; also the Critic goal files' "where ratified norms exist" wording, aligned to `norms.md` § Severity (slice E's outside-slice note) · [F6: C-1, C-17, C-22, C-23]. The two `move` decisions are structural, with test re-pointing, and could be their own plan. |
| **W4 Methodology and templates** | `methodology/*` (except the digest), `templates/*` | B-3 to B-9, B-16, B-17, B-18, B-20, B-24, B-27 to B-35, B-37 to B-40 · [F3: B-1, B-10–B-12, B-19, B-36] · [F4: B-2, B-13–B-15] · [F5: B-23, B-25, B-26]. Closes #341. |
| **W5 Operational skills** | `skills/*` except `critic` and `pr` | D-1 to D-25, D-27 to D-39, D-41 to D-58, D-60, D-61; also the runbook skill's copies of the overstated length claim and the dated hallucination rates (slice E's outside-slice notes) · [F3: D-40] · [F4: D-26, D-59] |
| **W6 Reference docs** | `plugin/docs/*` | E-1 to E-4, E-6 to E-19 · [F3: E-5] |

**Order and partition.** Run W1 first: it has the highest leverage and the fewest lines. W2
through W6 touch disjoint prose files but share test files (`tests/test_v5_methodology.py`
especially). So they run serially, or in parallel only with one integrator owning the shared test
files.

**Verification per wave:**

- The suite passes, with ceilings lowered.
- `verify_evidence.py` still resolves every *untaken* decision.
- One fresh-session behavioral probe on the wave's surface, on Sonnet 5 wherever the wave carries
  `model_dependent` decisions.

**Before the last wave lands:** the Fable final-coherence pass (§ Binding norms).

### Flagged, not proposed (low confidence; recorded, not filed)

These stay as records under #181's "anything not deletable is left" rule. None becomes a backlog
item.

- **A-40**: a progress cadence tied to elapsed time while reviewers run.
- **A-41**: whether the digest's manual `critic-consolidate` step is still needed.
- **A-42**: `reviews.md` loads on skill-file reads, not on running a review.
- **B-41**: the three clarity questions live in two guides.
- **C-25**: a wait budget for the builder during boundary reviews.
- **C-26**: the Records Pass drops sub-bar defects at the boundary.
- **C-27**: wall-clock targets inside reviewer payloads.
- **C-28**: a prohibition naming a field absent from the schema.
- **C-29**: the Update Flow's legacy-evidence branches.

## #181 bookkeeping dispositions

### The four Wave 2/3 items still open (8 of 12 have shipped)

| Item | Proposed | Why |
|---|---|---|
| #297 first-class home for review and research output | **drop** | The convention already works in practice. Research lives in `.prawduct/artifacts/`, and backlog bodies cite it in `refs:`: #181 → `framework-efficiency-review-2026-07-02.md`, and this artifact → its parents. The unbuilt remainder is a `pick` feature, which is new mechanism, and Cycle 2 forbids new mechanism. |
| #301 trivial gate: waiver key and radius, or retire | **retire** | The item names the lens itself: its sibling trivial fast-path already proved "fileset as detector" unsound (built, then retired), and principle #25 treats a third rework as a deletion signal. This is mechanism work, part of #181's other half. |
| #303 hard-remove inert `stamp-merged`, `regen-views` and retired tag keys | **do** | Pure deletion of inert code. |
| #318 `active_program` pointer for multi-plan programs | **drop** | New mechanism. The failure it cites is not routing a new session to the planned next item. `.prawduct/.handoff-notes.md`, which each session reads at start, now carries that. |

### The four deferrals that cited a review that did not exist

The source is the `.prawduct/change-log-archive/2026-07.md` entry "An allow-list cannot fence an
op the skill can reach through an interpreter" (2026-07-28). It deferred four fixes because "a
simplification review is open against exactly that", and no such review existed.

| Deferral | Proposed | Why |
|---|---|---|
| The v3.2.0 go-live plan's norm dispositions | **close as moot** | The plan is archived (`.prawduct/artifacts/archive/build-plan-v3.2.0-golive.md`), and archived plans are history. |
| Chunk 05's `verify-api` step | **close as moot** | The foreign API (`gh` issues) has been in production since the 2026-08-01 cutover, and this session read it successfully. That is live verification, not a fake. |
| The runbook's chunk-number coupling | **owner decision** | `release-plan-backlog-service-golive.md` is still a *live* artifact. Its "Naming hazard" paragraph exists only because two plans share chunk numbers, and it still lists VRF-005/007/008 as "still open, still unblocked". Either those verifications are owed (and then the owner names where they now live) or the release plan is archived. |
| ONB-3F9P's status pointer | **close as moot** | ONB-3F9P is #363, which shipped. |

### Mechanism rows already named by earlier artifacts (not enumerated by this pass)

| Mechanism | Named by | Proposed |
|---|---|---|
| The change log (essay entries duplicating git, plans and reflections; `lib/change_log.py`; the scope-pairing release gate) | `program-purpose-and-cession.md` seed row 1, where the owner called it "a bane" | Owner decision, in #181's mechanism half |
| The archive-plan advisory (false positives on release-pending plans) | `program-purpose-and-cession.md` seed row 2 | Owner decision, in #181's mechanism half |
| The framework's narrative house style (long historical docstrings that consumers imitate) | `tactical-efficiency-analysis-2026-08-13.md` deferred capture 5 | Prose instances are covered by the archaeology decisions (for example C-7, D-9–D-14, E-9). Docstrings in `plugin/lib` are code, so they belong to the mechanism half. |

## How this honors #181's constraints

#181 (Cycle 2 of the purpose-and-cession program) rejects a conventional audit. This pass keeps
its constraints:

- **No new backlog items.** The output is decisions with replacement text, not findings. The
  flags above are records, not filings.
- **Burden of proof on the text.** For prose, "yield" means a failure the text prevents that still
  reproduces on the target model. Anthropic's documented Opus 5+ behavior is the evidence that a
  given class no longer reproduces.
- **One sitting.** The owner vetoes in batch; nothing is applied before that.
- **Not a re-derivation of the 2026-07-02 diagnosis.** That diagnosis predates Opus 5. What is new
  here is the runtime it is re-priced against.

## Assumptions and binding norms

- `[ASSUMPTION: the target is Opus 5.5 for prawduct's own sessions, and Sonnet 5 is the floor every consumer-facing surface must still work on (project-preferences § Model floor) | HIGH impact | owner can correct, see F1]`
- **Model floor and coherence pass** (`project-preferences.md`). The enumeration ran on Opus 5.5,
  which is above the Sonnet floor but below Fable. So this cycle **owes a Fable final-coherence
  pass** before it lands. The Cycle 2 plan also names Fable for the disposition sitting. Both are
  session choices made with `/model`.
- **Prose-test taxonomy** (`program-purpose-and-cession.md` § Standing decisions). A doc test may
  pin budgets, resolvable references, interface tokens and single-sourced render consistency. It
  never pins a sentence. Tests that pin prose die with the prose they pin, as descoped
  requirements.
- **Token budgets.** A trim under a pinned ceiling lowers that ceiling in the same commit.
- **Keep list.** The independent Critic and PR reviewer, verification structure that constrains the
  output contract, exact scripts for fragile operations, machine-read text, and skill
  `description:` routing text. Every slice worked under this list (`BRIEF.md`).

## Method

- **Sources.**
  - [Prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5):
    it says Opus 5 prompts carry over, and points back to the Opus 5 patterns.
  - Anthropic's prompt-audit method, and the Opus 5 and Opus 5.5 behavioral-shift sections, as
    bundled with Claude Code's `claude-api` skill (v2.1.282). These are the rubric every decision
    cites. Excerpts were given to the auditors and are not committed (`BRIEF.md`).
- **Execution.** Five auditors read disjoint slices of the surface in full, on Opus 5.5, under
  one brief (`opus-55-prompt-audit-2026-09/BRIEF.md`).
- **Evidence check.** Every decision quotes its evidence verbatim, and a checker confirms each
  quote appears in the cited file. The checker includes a corrupted-quote control, so it cannot
  report clean without being able to fail. Re-run it from the repo root:
  `python3 .prawduct/artifacts/opus-55-prompt-audit-2026-09/verify_evidence.py .prawduct/artifacts/opus-55-prompt-audit-2026-09/slice-*.md`.
  It passed 192 of 192 on 2026-09-28. Expect failures as waves land, because a taken decision's
  quote is gone by design.
- **Spot-checks.** The consolidator re-derived eight of the load-bearing claims before writing
  this summary: A-1, the digest budget, A-25, B-26, C-1, C-8, D-15 and E-1.
