---
artifact: audit
scope: learning-system
status: DRAFT for owner review — no decisions taken; recommendations only
created: 2026-09-01
depends_on: [framework-efficiency-review-2026-07-02.md, program-purpose-and-cession.md, archive/build-plan-learnings-firing.md, collapse-map-learnings-firing.md]
---

# Learning System Audit — 2026-09-01

**Question asked:** is prawduct's learning system (learnings.md, learnings-detail.md,
learnings-history.md, `.session-reflected`, reflections.md, the `/prawduct:learnings` lookup, the
audit/retirement lifecycle, the reflection gate) maximizing ROI — and what should it become?

**Method.** Five parallel read-only surveys, synthesized here: (1) the plugin's mechanism map
(`plugin/lib`, `plugin/bin`, `plugin/hooks`, skills, methodology, tests); (2) the 19 governed
product repos under `~/source/` plus their worktrees and clones; (3) every surviving Claude Code
session transcript on this machine (241 sessions, 1,488 files incl. subagents, 2026-07-31 →
2026-09-02 — the retention window; older sessions are pruned, so all usage counts are floors and
describe August 2026 only); (4) the backlog (GitHub Issues cache + frozen `backlog.md`), the
change-log, and git history of the corpus; (5) the current documented state of Claude Code's own
memory. Where a number is cited, the appendix gives the command that recomputes it. Numbers here
are dated 2026-09-01; recompute rather than cite.

---

## 1. Verdict

**No. The learning system is not maximizing ROI, and the shape of the loss is specific: the write
side works, the read side barely registers, and the maintenance side consumes most of the budget.**

- **Write side — positive.** 54% of governed August sessions wrote a reflection to
  `.session-reflected`; median 2,900 characters; substantive (expected/actual, root cause, "rule
  earned"). No boilerplate found in production sessions. 23% of sessions added or sharpened a rule.
  The 2026-09-01 burndown reflection is a good example: it produced a genuinely new rule (prose
  ceilings: pay from duplication or declare a raise, never trim) that landed in `learnings.md`.
- **Read side — near zero measured yield.** `/prawduct:learnings <topic>` ran in 23% of sessions
  (60 invocations, all assistant-initiated, none user-typed). 38% of those forked lookups never
  returned to the transcript. Of the ones that did, 58% were followed by silence — the next event
  is a file read, zero words spent on the rule — and 16% were visibly applied. A builder citing a
  rule as the reason for a decision appears in ~6% of sessions. The Critic's structurally required
  cross-check is where most citation happens (86 of 106 strict citations are in reviewer subagents).
- **Maintenance side — strongly negative.** ≈2,770 lines of plugin Python and 5,519 lines of tests
  (293 tests, ~5.7% of the suite) guard the subsystem. 38 backlog items have the learning system
  as their subject; 22 are the machinery's own defects, 11 of them filed in the four weeks after the
  lifecycle was extended. `learnings.md` in this repo has 301 commits, 153 in August alone. Five
  size interventions in five months; after every one the file returned to a new high within 4–6
  weeks and is now at its all-time high (103.5KB, 286 rules, 2.6× the nudge). Fleet-wide, the
  sentinel/supersession lifecycle that the 1,751-line `audit_learnings_cmd.py` implements is used
  by **one** entry.

The framework already diagnosed this correctly on 2026-07-29 ("the corpus does not have an
authoring problem, it has a delivery problem" — `archive/build-plan-learnings-firing.md`), and on
2026-07-02 ("reflections.md is write-heavy/read-never; converge the memory triple-track" —
efficiency review, backlog #295, still open with no design note). The diagnosis was right and the
response was more corpus and more machinery: rule count went 149 → 286 in the 31 days after the
"rules that fire" plan closed, and a third durable file was added on 2026-09-01.

**Every sub-mechanism is past Principle 25's third rework** (size control 5–7, retirement
lifecycle 6, handoff 5, reflection gate 3+, storage topology 3), and at least nine further reworks
landed after the principle was ratified on 2026-08-13. No change-log entry has posed the deletion
question for this system. This artifact poses it.

---

## 2. What the system is, as built (mechanism map, abridged)

| Surface | Writer → Reader | Cost / state (2026-09-01) |
|---|---|---|
| `.prawduct/learnings.md` | agent by hand → session briefing (count only), lookup fork, Critic `final` reviewers ×3, PR reviewer, doctor | 103.5KB, 286 `##` rules, **96% of bytes are headings**; median heading 343 chars (min 43, max 1,092); 83 of 286 start "When" |
| `.prawduct/learnings-detail.md` | agent → lookup fork only; nothing else in the plugin reads it | 350KB (was 558KB before today's history split) |
| `.prawduct/learnings-history.md` | `audit-learnings --apply` only → lookup fork on a miss | 216KB, 111 retired entries; exists only in the framework repo |
| `.prawduct/.session-reflected` | agent at work boundaries → Stop gate (≥50 chars), handoff generator, archive at `/clear` | gitignored; per-checkout |
| `.prawduct/reflections.md` | `/clear` archiver → **nothing** | gitignored, per-checkout: prawduct 2.16MB, discodon 1.47MB (18,650 lines), samsung 370KB, scriob 212KB, hallucinote 200KB + 583KB archive. Hallucinote's four clones each hold a different, unmergeable copy |
| `.prawduct/.subagent-briefing.md` | rewritten every SessionStart/resume/compact/fork → one conditional instruction site | 108KB, embeds all 286 rules verbatim; **read twice in 1,488 transcripts** |
| `/prawduct:learnings <topic>` | forked subagent reads learnings + detail (+ Direction sections, + history on a miss) | median 38KB (~9.5K tokens) ingested, p90 86KB, max 111KB; returns median 6.1KB (3× the SKILL's ≤500-token target). SKILL.md claims "~4K+ tokens" ingested — off by 10–25× |
| Critic learnings cross-check | each `final`/`cumulative` reviewer reads `learnings.md` | 207 reviewer transcripts read it in August (median 10.7KB, p90 28KB); the corpus's single largest consumer |
| `audit-learnings`, `check-learnings-pairing`, `learnings-obligation`, `record_lint` entry-shape | CLI / Critic dispatch | 1,751 + 356 + 152 lines; metadata on 3 of 286 rules (1 `sentinel=`, 0 `superseded-by=`) |
| Session-start injection | briefing + digest | ≈80–240 chars/session on learnings — **negligible**. The header's claim "topic headers shown in the session briefing" is stale |
| Telemetry | ledger records `review.critic` / `review.pr` only | **no event for a lookup, a reflection, or an audit run**; the loop is unmeasured by design |

Three ratified controls on the same file contradict each other and are all advisory:
the 40KB nudge (2026-06-10), the 400-char rule lint (2026-07-30, `record_lint.py`), and the
owner's 2026-07-31 ruling that a rule must carry its discriminating instances inline because the
detail file "is read on demand, not at the moment a rule has to fire." At 286 rules they cannot
all hold; the system resolves it with grandfathering (15 headings over cap) and a stream of
"trim into budget" commits (at least five in August).

---

## 3. Evidence, by question

### 3.1 Corpus growth and shape

| Date | Rules | learnings.md | detail | Event |
|---|---|---|---|---|
| 2026-03-30 | 18 → 10 | 16KB → 3.9KB | 15KB | first commit; janitor prune |
| 2026-05-08 | 10 | 3.9KB | 15KB | size limit + session-start load **dropped**; lean on lookup fork |
| 2026-06-06 | 50 | 62KB | — | |
| 2026-06-12 | 59 | 33KB | 91KB | **compaction 1** + 40KB nudge |
| 2026-07-21 | 113 | 58KB | — | **compaction 2** |
| 2026-07-31 | 157 | 35KB | 333KB | **compaction 3** "built to be the last" + 400-char lint |
| 2026-08-01 | 149 | ~35KB | — | collapse 1 (learnings-firing, 159 → 149) |
| 2026-08-15 | 263 | 89KB | 496KB | +108 rules in 14 days (~7.7/day) |
| 2026-08-17 | 250 | — | — | collapse 2 (17 → 3) |
| 2026-09-01 | **286** | **103.5KB** | **350KB** (+216KB history) | all-time high; total corpus 670KB ≈ 170K tokens, 21.6× March |

The growth mechanism is visible in the commit log: nearly every chunk close "pays for" one to
three rules ("the two rules Chunk 03 paid for", "the rule its blocker earned"). `reflection.md`
says "most cycles produce a reflection entry and no new learning"; the practice is the inverse.
Additions in August: ~130. Retirements, ever: two events (18 on 08-01, 4 on 08-18). The corpus
doubles roughly monthly and no curation mechanism runs at that rate.

Shape: the methodology's model rule is ~120 characters ("**Pydantic v2**: Never use
`@computed_field` in models with `extra="forbid"`…"). 254 of 286 headings exceed 120 chars; 60
exceed 400. The rule *is* the narrative, which is what the owner's 2026-07-31 ruling asks for and
what makes the detail file redundant for the reader the ruling describes.

Subject matter (heuristic keyword classification of this repo's 286 headings): 141 (49%) name a
prawduct-internal mechanism (Critic, gate, hook, build plan, backlog, digest, release…); 90 are
generic engineering discipline with no framework vocabulary; 55 neither. In the framework repo
half-framework is expected; the same skew in consumer repos is not (§3.5).

### 3.2 Do rules get used?

Transcript evidence (August 2026, 235 governed sessions):

| Signal | Sessions | Share |
|---|---|---|
| `/prawduct:learnings <topic>` invoked | 55 | 23% |
| …of 60 invocations, result returned to the transcript | 37 | 62% |
| …of returned, followed by zero assistant text | 17 | 46% |
| …judged fully applied (19 sampled) | 3 | 16% (partial 26%, silent 58%) |
| `learnings.md` opened by Read/`cat` in the main transcript (products) | 23 of 171 | 13% |
| A rule cited as the reason for a decision, builder side | 14 | 6% |
| Wrote a rule to `learnings.md` | 55 | 23% |
| Wrote a reflection | 126 | 54% |
| Twelve of 20 projects never invoked the lookup at all | | |

Repo evidence agrees. Commit messages "per learnings.md …" applying a rule: discodon ~27, samsung
5, hallucinote 1, swordfishing 1; **zero** in scriob, metallm, puzzles, cordyceps, trenchant,
scriob2. Change-logs: discodon 2 such phrases in 2MB; scriob/hallucinote/puzzles 0. The only
re-use counter ever shipped (`confirmations=`) lives in one plugin version (scriob: 73 marked, 12
confirmed twice, max 3) and its most-confirmed rules are prawduct friction.

The system's own record is harsher than the transcripts: two figure-verification rules filed
2026-07-29 "were violated the following day by the author who had read them" (change-log
2026-07-30); a discodon cycle hit "four false claims and twelve Critic rounds — every one already
covered by a rule in this file" (learnings-firing plan); "the learnings file had the disease it
was describing: seventeen instances, no construction" (2026-08-17). A discodon commit body: "it
was never a new learning — it was an existing rule I did not read."

**The structural cause of the read-side failure is delivery topology, not authoring.** The lookup
is a `context: fork` skill: its answer lands asynchronously as a task notification, frequently
mid-task, which is exactly the 38% non-return and the 46% silence. Meanwhile the one intervention
with a documented trigger — rules moved into code and printed at the moment of the action
(`_BATCH_FIX_DIRECTIVE`, `RESOLUTION_IS_A_CLAIM_DIRECTIVE`) — has no dependency on the file at all.

### 3.3 The size cap and the learnings / learnings-detail split

Both have failed at their stated purpose, and the failure is now a documented pattern in the
code itself (`record_lint.py:373-378`: "Compaction ran twice … the file regrew past its starting
size both times … the third sweep is already scheduled").

- The nudge is advisory and has fired every session for a month in this repo (and in discodon,
  144KB > 40KB) with no effect on behaviour. Every compaction "relieves" `learnings.md` by moving
  bytes to `learnings-detail.md`, which then became "an unbounded sink with no route out" (#350),
  which was relieved on 2026-09-01 by a third file. Topology 1 → 2 → 3 files plus two gitignored
  tracks.
- The split's premise — terse rule here, narrative there — was overruled by the owner on
  2026-07-31 for a good reason (a relocated instance is, for firing purposes, deleted). Once the
  rule carries its instances, the detail file has no reader: nothing in the plugin reads it except
  the lookup fork, which the transcripts show is itself barely consumed. 350KB of narrative, ~88K
  tokens, read only to be filtered away.
- `learnings-history.md` re-implements `git log -S`. "Nothing is ever deleted" is what version
  control provides; the forwarding-address feature (find the successor of a rule you remember)
  had, as far as the transcripts show, zero uses.

### 3.4 Session reflections vs learnings — different, and should they be?

They are different in kind and that is correct: a reflection is an *episode* (what happened,
expected vs actual, root cause); a learning is a *rule* (standing instruction). The methodology
gets this right. What is wrong is what happens to the episode:

- The archive is write-only. `reflections.md` has no reader anywhere in the plugin; the hook's
  own comment concedes it "has no history to mine." 2.16MB in prawduct, 1.47MB in discodon. The
  provenance-tag feature has 12 tests and feeds a file nobody opens.
- It is gitignored and per-checkout, so it fragments: hallucinote's four clones hold four
  different archives; a deleted worktree deletes its reflections. (Claude Code's auto-memory,
  by contrast, is keyed on the git root and shared across worktrees.)
- Thematic repetition is heavy because nothing consolidates: "mutation" in 39 discodon and 51
  samsung entries; "pre-existing" in 77 discodon entries; "grep" in 118. The same lesson is
  re-derived narratively, at ~3,000 chars a time, because the previous derivations are unreadable
  in practice.
- The gate is a 50-character floor and does not fire on the common case: #685 records "~7 hours
  of sessions produced no `.session-reflected` at all" on a planless clean repo. 46% of governed
  August sessions produced no reflection write; 51 of those ran ≥100 messages.
- `methodology/reflection.md` is 24KB, of which roughly 60% is the standing-block specification
  (`STATE` / `RUNNING` / `SAFE TO CLEAR`) — a session-hygiene rule that has nothing to do with
  reflection. The guide for the learning loop has become the home for unrelated ceremony, and it
  never mentions `learnings-history.md` or `audit-learnings` (#347: "four surfaces, three stale").

Are reflections acted on and incorporated? **Within the session, sometimes** — the 2026-09-01
reflection produced a rule the same day. **Across sessions, no**: the only consumer of an archived
reflection is a human who goes looking, and the only evidence of that is the 2026-07-02 efficiency
review, which mined them once and recommended retiring the archive. The conversion path
reflection → rule → structure (test, hook, Critic goal, methodology) exists on paper as the
lifecycle (provisional → confirmed → incorporated) and in code only as `sentinel=`, used once.

### 3.5 Across branches, worktrees, and sibling repos

**Branches and worktrees.** `learnings.md` is committed, so it merges; 13 merge commits touched it
here, 20 in discodon, with no recorded conflicts (every branch appends 1–3 rules; conflicts are
rare because appends land at different lines — unlike change-log, which needed a union driver).
Stranding is real but small: scriob has 7 learnings commits on an idle unmerged branch;
hallucinote 2. The nine orphaned `wt-discodon-*` directories are pruned worktrees (stale disk,
not lost rules — all 127 rule lines unique to them exist reworded on develop). The gitignored
tracks (`reflections.md`, `.session-reflected`) do not merge at all.

**Sibling repos.** Zero sharing by design, and the survey shows what that costs. Sampling ~55 rules
across discodon, hallucinote, scriob, samsung, metallm: **~40% product fact, ~45% generic
engineering discipline, ~15% prawduct-meta, <2% principle restatement.** Samsung's 94-rule file is
~90% portable epistemology about testing and almost nothing about Samsung Frame TVs. At least ten
lessons were learned independently in two to five repos each — "a mutation must be shown to have
applied" (discodon, samsung, hallucinote, all August 2026); "vacuous tests" (metallm, samsung,
cordyceps, scriob); "run the canonical full suite" (scriob ×2, metallm, puzzles, discodon);
"interface change means census every consumer" (hallucinote, scriob, discodon, metallm);
"retiring a claim is a repo-wide grep" (samsung, discodon, hallucinote, trenchant, swordfishing);
"pre-existing is not a pass" (metallm, discodon, scriob); "built-but-unconsumed is not done";
"test both directions"; "stated cause is a hypothesis"; "probe real output" (TangleClaw in March,
hallucinote in August). Backlog #343 already names the fix: "every onboarded product re-learns
from zero."

**Framework friction in product memory.** Rules naming Critic, prawduct-hook, gates, build plans or
the backlog: trenchant 74% (17/23), cordyceps 31%, scriob 17%, discodon 15%. These are bug reports
against prawduct filed where no framework session will read them (e.g. scriob: "`/prawduct:critic`
auto-targets the cwd repo's git diff — for work built in the `../3tears-scriob` worktree it reviews
the WRONG repo"). The `/prawduct:report-bug` channel exists; nothing routes a framework-shaped rule
into it.

**Five rule formats coexist** across the fleet (bold bullets; H2 + body; Date/Context/Rule/Why
blocks; metallm's 800-char bullets with transcript citations; paragraph-headings with a detail
link), none matching the terse contract every file's header promises. Format drift also breaks the
tooling ("audit-learnings pairs the two files by exact title" — hallucinote change-log).

### 3.6 Overlap with Claude Code's own memory

What Claude Code provides today (documented; details in the appendix): a per-repository
auto-memory directory keyed on the git root (shared across worktrees, machine-local, never
committed or shared with a team); a `MEMORY.md` index loaded fully at session start under a hard
cap (200 lines / 25KB); typed one-fact-per-file entries (user / feedback / project / reference)
read on demand; project `CLAUDE.md` committed and shared; `.claude/rules/*.md` with `paths:`
globs loaded on demand when matching files are read. Relevance-based recall of memories into
context is observable in this harness (recalled memories arrive as system-reminder blocks);
background consolidation has been announced but is not documented. Plugins have no memory API;
hooks can inject context at SessionStart / UserPromptSubmit.

What is on this machine: 17 non-empty memory dirs; hallucinote 66 files / 316KB (29 feedback,
34 project), discodon 34 / 172KB, prawduct 17 / 80KB. The boundary already leaks both ways:
prawduct-methodology feedback sits in hallucinote's Claude memory ("Critic cadence — skip
per-chunk for small chunks"; "PR/critic gates hardcode main, but repo is gitflow-on-develop") where
prawduct never sees it; swordfishing's only memory entry is a learnings-shaped rule; scriob's
memory records the routing rule "dev-process → learnings.md". Discodon's memory index carries a
project-state snapshot dated 2026-04-25 that duplicates `project-state.yaml` and is stale.

Where the two systems genuinely differ:

| | Claude Code auto-memory | prawduct learnings |
|---|---|---|
| Owner | the person + machine | the repo (team, every clone) |
| Loaded | index always (hard-capped), files on demand, recall by relevance | one line always; rest by explicit lookup (23% of sessions) |
| Curated by | the model, under a hard cap that forces it | nobody at the rate of growth; advisory nudges |
| Content it holds well | operator preferences, corrections, how-you-work | product facts a team must share; review cross-check inputs |
| Structure | typed one-fact-per-file + index — the tiering `learnings.md`/`-detail` hand-rolls | three files, five formats |

**Duplication:** operator preferences/feedback (prawduct's `project-preferences.md` and a slice
of rules) and project-state snapshots (the memory side is the redundant, stale one).
**Not duplicated:** committed, team-shared product knowledge; the Critic's cross-check; the
reflection habit as a principle. `documentation/purpose.md` names statelessness as a hedge that
"depreciates on the harness's schedule" and memory as one of prawduct's three durable roles. That
is consistent: the *role* stays, the *form* should cede whatever the harness now does at least as
well — and the harness now does the personal tier, the hard-capped index, and (emerging)
relevance recall.

---

## 4. Answers to the owner's questions, in one paragraph each

**Is the size cap and the learnings/learnings-detail split working?** No. Five compactions, five
regrowths to a new high; the cap is advisory and ignored; the split's premise was correctly
overruled on 2026-07-31 (instances must ride with the rule to fire), which leaves the detail file
with no reader. The three-file topology is the system fighting its environment (Principle 25).

**Do learnings really get used?** Marginally. 23% of sessions look up; 38% of lookups never return;
of those that return ~16% are visibly applied; 6% of sessions cite a rule as a reason. The place
rules reliably fire is the Critic cross-check (structurally required reading) and the two rules
moved into code paths. The corpus's own authors violate its rules the day after writing them.

**Are reflections different from learnings, and should they be?** Yes and yes — episode vs rule
is the right distinction. The defect is that the episode store is a 2MB gitignored file nothing
reads, fragmenting per checkout, with a 50-char gate that skips the common case.

**Are reflections acted on and incorporated into consuming projects?** In-session, sometimes
(a rule gets written). Cross-session, no — there is no consumer. Fleet-wide, the 2026-07-02 review
was the one time anyone mined them, and its recommendation (retire the archive) was not executed.

**Is it worth the complexity?** No. ≈8,300 lines of code and tests, 38 backlog items, 20+
reworks, and 153 commits to one file in one month, for a read-side yield measured in single-digit
percentages. The parts that demonstrably work — writing a reflection, the Critic cross-check,
rules delivered in code — are the cheap parts.

**Can we get the same or greater benefit more simply?** Yes — see §5–6. The benefit is not in
the corpus; it is in a small committed body of product knowledge that is always in context, a
portable discipline layer that is shipped once instead of re-learned per repo, and a short path
from reflection to structure.

**How do learnings work across branches, worktrees, siblings?** Committed rules merge fine and
rarely conflict; gitignored tracks fragment and are lost with the checkout; sibling repos share
nothing, so ~45% of every corpus is re-derivation of portable discipline and ~15% is prawduct bug
reports in the wrong inbox.

**Are we duplicating Claude's memory; should we cede?** Partly, and yes for two tiers: operator
preferences/feedback cede to Claude's user memory now; project-state snapshots should be kept
*out* of Claude's memory (prawduct's committed state is authoritative); and the retrieval problem
for product knowledge is the next cession candidate as the harness's recall matures. The
committed, team-shared tier and the reflection principle stay prawduct's.

---

## 5. North star — how learnings and reflection SHOULD work in prawduct

Stated as the design intent, not a description of current code (`feedback_artifacts_express_intent`).

**Purpose restated.** Prawduct's memory role exists so that a product team plus a stateless model
does not repeat a mistake or re-derive a fact that the repo already paid for. The unit of value is
*a behaviour that changed*, not a rule that was stored. Every mechanism below is judged by how
short it makes the path from an episode to a changed behaviour, and by how little it costs every
session that never needs it.

**Principle 1 — Tier by owner, not by file size.**
- *Product knowledge* (committed, `.prawduct/learnings.md`): facts about *this* product the model
  cannot know or derive — API quirks, invariants, environment constraints, consequences of ratified
  decisions. This is prawduct's durable asset: team-shared, versioned, reviewed. Terse, topic-
  grouped, one file, always in context.
- *Engineering discipline* (portable): not per repo. Shipped once with the plugin as a versioned
  discipline corpus (#343), curated by the framework from what the fleet keeps rediscovering, and
  delivered where the evidence says rules actually fire — in code at the moment of the action, in
  Critic goals, in the methodology guides. Products contribute upward; they do not re-learn.
- *Framework friction*: routed to prawduct's backlog through `/prawduct:report-bug` at the moment
  it is written, never stored as a product rule.
- *Operator preference* (how this person works): ceded to Claude Code's user/feedback memory and
  `~/.claude/CLAUDE.md`; prawduct's `project-preferences.md` keeps only preferences that bind the
  *repo* (merge strategy, delegation policy, attribution).

**Principle 2 — A hard budget is the curation mechanism.** The product-knowledge file has a hard
cap (proposal: 100 rules and 25KB — the same order as Claude's own `MEMORY.md` index, which
proves a model curates well under one). At the cap, adding a rule means merging or deleting one
in the same commit, and the choice is made by the *author with the episode in hand*, which is the
only time anyone has the context to make it. Advisory nudges are removed; the cap is a gate
(warnings are effectively blocking in this repo anyway). The known risk — an agent under a
ceiling trims load-bearing prose — is the 2026-09-01 reflection's own rule: pay from genuine
duplication or declare a raise with a reason, never trim to fit.

**Principle 3 — Always in context beats looked up.** At ≤25KB (~6K tokens) the product-knowledge
file is cheaper than one lookup (median 9.5K tokens) and reaches 100% of sessions instead of 23%.
The forked lookup subagent is deleted. As a follow-on, rules that are path-scoped can be emitted
as `.claude/rules/*.md` with `paths:` globs so the harness loads them only when the matching files
are touched — ceding retrieval to the runtime entirely.

**Principle 4 — Recurrence goes to structure, not to more rules.** The lifecycle
provisional → confirmed → incorporated becomes the only growth path: a rule violated a second time
becomes a test, a hook check, a Critic goal, or a methodology sentence, and is then deleted from
the file. "Incorporated" is the product; the file is the waiting room, and a small waiting room
is the point. Git is the history; a retirement is a deletion whose commit message is the
forwarding address.

**Principle 5 — Reflection is an input, not an archive.** The habit stays (Principle 17) and the
`.session-reflected` write stays, because it works. The archive goes. Reflections feed exactly two
consumers: the author, in-session, who turns them into a rule/test/upstream report before the
boundary; and a periodic consolidation pass (janitor/doctor) over a short rolling window that
proposes merges, retirements, promotions to the discipline corpus, and upstream reports. The
reflection gate fires on the common case (planless sessions, #685) and asks for content shape, not
50 characters.

**Principle 6 — Measure the loop or do not claim it.** Two ledger events (`learning.written`,
`learning.fired` — the latter emitted when the Critic escalates on a rule or a builder cites one)
so that a future audit reads a number instead of sampling transcripts.

---

## 6. Options and recommendation

**Option A — Patch again.** Raise caps, add a fourth compaction, more lint, keep the three files
and the lookup fork. *Rejected.* This is the sixth-plus rework of every sub-mechanism; the
evidence of five compactions is that the next one regrows too.

**Option B — Cede entirely to Claude Code memory + CLAUDE.md.** Delete the learning system;
let auto-memory hold everything. *Rejected as the whole answer.* It loses the committed,
team-shared product-knowledge tier (a consumer with a team gets nothing from a machine-local
store), loses the Critic cross-check input, and keeps the personal tier in a store prawduct
cannot review or reason about. It is the right answer for one tier (operator preference) now,
and a live candidate for retrieval later.

**Option C — Shrink to the product-knowledge tier; ship the discipline once; delete the rest.**
*Recommended.* Concretely:

Delete, whole (code, tests, docs, records together — `purpose.md` "deletion gets the same care"):
- `learnings-detail.md` and `learnings-history.md` as durable files (git is the history; narrative
  lives in the reflection and the commit message).
- `audit_learnings_cmd.py` (1,751 lines, 131 tests) — sentinel/supersession/confirmations
  lifecycle, used by one entry fleet-wide; `check-learnings-pairing`; `learnings_obligation.py`
  (356 lines to insert a paragraph); `record_lint` `learnings-entry-shape` (superseded by the cap).
- The `/prawduct:learnings` fork skill and its instruction sites (planning.md, building.md,
  pr/SKILL.md, review-cycle.md, doctor).
- The 40KB nudge for learnings.md (superseded by the gate).
- `reflections.md` archiving and provenance tagging (12 tests); the `.subagent-briefing.md`
  learnings embedding (read twice ever).
Net: ≈2,770 → ~300 lines of plugin Python; ≈5,500 → ~600 lines of tests.

Keep, and fix:
- `.session-reflected` + the reflection gate (fix #685; require shape, not length).
- The Critic learnings cross-check (it is where rules actually fire; it reads a 25KB file now).
- The descent-obligation idea, shortened to two sentences at the top of the file.
- `building.md:107` "reflect now" and the work-boundary cadence.

Build, small:
- The hard-cap gate on `learnings.md` (count + bytes), with "merge or delete in the same commit."
- Load `learnings.md` in full at SessionStart (it is ≤6K tokens by construction).
- A framework-shaped-rule detector at write time offering `/prawduct:report-bug` (routes the ~15%).
- The discipline corpus, seeded from §3.5's ten cross-repo duplicates plus this repo's 90
  generic-discipline headings, delivered through Critic goals / code directives / methodology, and
  versioned with the plugin.
- Two ledger events.
- A one-time fleet migration (`/prawduct:doctor` step): classify each repo's rules into the four
  tiers, trim tier 1 to cap, promote tier 2 to the corpus, file tier 3 upstream, delete the detail
  and archive files in one reviewable commit per repo.

Cede, now: operator preferences → Claude user memory; and add one line to the session digest telling
the harness's auto-memory *not* to store project state (`.prawduct/` is authoritative), which
removes the stale-snapshot duplication seen in discodon.

Re-price later (event-driven, per Principle 26): when the harness documents relevance recall and
consolidation for memory, re-evaluate whether tier-1 retrieval and the consolidation pass cede too.
Record the assumption now: *"the runtime does not yet load committed, team-shared, path-scoped
product knowledge by relevance."*

**Why this gets consumers better, faster.** Today a new product learns nothing from the fleet and
re-derives ~45% of its rules; a consumer that upgrades the plugin will receive the discipline the
fleet already paid for, in the surfaces that fire. Today product knowledge is in context in 23% of
sessions; it will be in 100%. Today a lesson's path to changed behaviour is reflection → 340-char
heading → (maybe) lookup → (maybe) read → (rarely) applied; it becomes reflection → rule in
context or test/hook/goal, with the corpus forced to stay small enough to be read.

---

## 7. Open questions for the owner

1. **The cap.** 100 rules / 25KB is a proposal calibrated to Claude's `MEMORY.md` index. Is a
   hard gate acceptable, given the trim-to-fit risk, or should the first cut be a blocking Critic
   finding rather than a Stop-hook block?
2. **The 2026-07-31 ruling** (instances ride with the rule) stands; it implies rules of 200–400
   chars. Under a 25KB cap that is ~80–100 rules. Is that the right number, or should the cap be
   count-only and let bytes float?
3. **Discipline corpus ownership.** Curated by hand from the fleet, or produced by a periodic
   framework pass over consumer repos' `learnings.md` (the "product feedback review" flow in
   CLAUDE.md that exists but has run once)?
4. **Consolidation pass cadence.** Per `/clear`, per release, or on demand via doctor?
5. **Migration risk for consumers.** Deleting `learnings-detail.md` in a product repo is a visible
   change to the onboarded-repo contract. One reviewable commit per repo via doctor, or opt-in?
6. **What to cede to Claude memory beyond operator preference** — nothing else now, or also
   the reflection *episode* store (machine-local is arguably fine for episodes)?

---

## Appendix A — Recompute the numbers

```
# corpus shape (this repo)
grep -c '^## ' .prawduct/learnings.md; wc -c .prawduct/learnings*.md
awk '/^## /{print length($0)-3}' .prawduct/learnings.md | sort -n | awk '{a[NR]=$1} END{print "median",a[int(NR/2)],"max",a[NR]}'
# growth at a date
s=$(git log -1 --format=%h --before="2026-08-01 23:59" -- .prawduct/learnings.md); git show $s:.prawduct/learnings.md | grep -c '^## '
# lifecycle adoption (fleet)
grep -c '<!-- prawduct-learning:' .prawduct/learnings.md; grep -rl 'sentinel=' ~/source/*/.prawduct/learnings.md
# code + test footprint
wc -l plugin/lib/audit_learnings_cmd.py plugin/lib/learnings_obligation.py tests/test_audit_learnings.py tests/test_learnings_pairing.py tests/test_learnings_obligation.py tests/test_reflection_provenance.py
# reflections archive (gitignored; main checkout)
wc -c ../prawduct/.prawduct/reflections.md; grep -c 'prawduct: version=' ../prawduct/.prawduct/reflections.md
# backlog
python3 plugin/bin/prawduct-hook backlog cache-query search learnings
# transcript usage: scripts in the session scratchpad (analyze.py, descent.py) — re-run against ~/.claude/projects/*/*.jsonl
```

## Appendix B — Sources consulted

- Plugin: `plugin/lib/{audit_learnings_cmd,learnings_obligation,record_lint,briefing,core,ledger,telemetry}.py`, `plugin/bin/prawduct-hook` (cmd_stop 2362-2428, cmd_clear 691-876, audit 6231-6348), `plugin/hooks/*`, `plugin/skills/{learnings,critic,pr,doctor,janitor}/`, `plugin/methodology/{reflection,building,planning,session-digest}.md`, `plugin/docs/principles.md`.
- Repo records: `.prawduct/change-log.md` (15 learning-mechanism headings, 2026-03-30 → 2026-08-27), `.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`, `kernel-redesign-discovery.md`, `archive/build-plan-learnings-firing.md`, `collapse-map-learnings-firing.md`, `program-purpose-and-cession.md`, `documentation/purpose.md`.
- Backlog: #4, #96, #154, #220, #237, #269, #273, #295, #302, #318, #323, #324, #328, #338, #339, #343, #345, #346, #347, #349, #350, #351, #369, #378, #439, #449, #560, #571, #573, #661, #683, #685, #688, #717, #720.
- Fleet: 19 product repos + worktrees/clones under `~/source/`; Claude Code memory dirs under `~/.claude/projects/*/memory/`.
- Transcripts: 241 sessions / 1,488 JSONL files, 2026-07-31 → 2026-09-02 (retention window).
- Claude Code memory behaviour: code.claude.com/docs/en/memory (auto-memory keyed on git root; MEMORY.md 200 lines / 25KB; `.claude/rules` `paths:` frontmatter; no plugin memory API). Relevance recall observed in-harness; consolidation announced, undocumented.

---

## 8. Addendum 2026-09-02 — is one always-loaded 25KB file realistic, or should rules be scoped to the work?

Owner's challenge: a sprawling product (discodon: backend, frontend, Python, TypeScript, UX, evals,
deploy) may not distill to 25KB; an agent on eval charts does not need deployment quirks. Measured
against discodon (161KB, the fleet's largest file; commands below recompute).

**8.1 How big is discodon's product-knowledge tier really?** The file is two formats: 30
topic-grouped sections (111KB, 216 bullets — the original format) plus 137 later paragraph-heading
rules with no section (48KB — the format the framework's 2026-07-31 ruling and 400-char lint
spread). Classifying the 30 sections by hand:

| Bucket | Bytes | Sections / examples |
|---|---|---|
| Product knowledge, path-scoped | 37KB | 19 — Eval, Storage ports, Music, Postgres, LLM, ZMQ, Discord, MCP, React, Design tokens, Supervisor… |
| Product knowledge, cross-cutting | 14KB | 9 — Pydantic, Enum comparisons, Env & Config, Architecture, Cache keys… |
| Portable discipline | 48KB | 4 — "Testing & Mocking" alone is 41KB / 80 bullets |
| Prawduct-meta | 14KB | 1 — "Governance Bookkeeping" |

The 137 paragraph rules by keyword: 43 prawduct-meta, 30 testing discipline, 22 generic, and 42
product-domain (19 eval, 8 web, 8 deploy, 4 LLM, 3 db ≈ 15KB). So the raw product tier is
≈66KB — 2.6× the proposed cap. Reading the Eval section closely, only ~5 of 22 bullets are facts
about *this* eval harness (drain window floors at 600s; tool-forcing is code-gated; `schema.ts`
pins the response shape by exact key); ~14 are eval-domain discipline (judges hallucinate, n=1 is
noise, p95 needs a decline rate) and ~3 generic. Applied fleet-wide that puts a strict facts-only
tier at 20–30KB after dedup — **at the cap, not comfortably under it, and only with the discipline
content removed**. The owner's concern is warranted: a single global cap either loses the
eval-domain discipline (which is the most valuable content in that section and applies to nothing
outside `discodon/eval`) or is blown.

**8.2 Does the work cluster enough for scoping to pay?** Discodon's domains map one-to-one onto
directories (`discodon/eval` + `web/src/eval-kit`, `discodon/music`, `discodon/storage`,
`discodon/discord`, `web/`…). Of 251 August PRs touching code, 23% touched one code area, 25%
two, 30% five or more. Rules co-change with their area: 224 commits to learnings.md since June,
58% alongside code, dominated by `web` (61) and `eval` (46). So for roughly half of sessions a
scope filter loads cross-cutting (~14KB) plus one or two areas (~3–8KB) instead of the whole
~66KB; for the 30% wide-scope sessions it loads most of it anyway. A 2–3× reduction for the
focused half, nothing for the rest.

**8.3 The filter already exists in the harness; prawduct must not build one.** Verified against
code.claude.com/docs/en/memory (2026-09-02): `.claude/rules/*.md` files are committed and
project-shared; a file with `paths:` frontmatter loads *when Claude reads a matching file*,
otherwise at launch alongside CLAUDE.md; user-level `~/.claude/rules/` layers underneath; no
documented cap on rules files. Not documented: whether rules reach subagents (the Critic must
keep reading the files explicitly, as it does now), and any plugin API for shipping rules. So
"categorize and filter to the current work" costs prawduct one directory layout — one file per
topic section, `paths:` on each — and zero retrieval machinery. Discodon's topic sections *are*
the categorization; the framework's paragraph-heading format is what regressed it.

**8.4 What this changes in §5–6.** The proposal shifts from *one file, one global cap* to
*a small always-loaded core plus scoped files, each with its own budget*:

- **Core** (`learnings.md`, or the un-scoped rules file): cross-cutting product facts only; hard
  cap stays and can be *tighter* — discodon's raw cross-cutting tier is 14KB. This is the file
  every session pays for, so it is the one that must be forced small.
- **Scoped** (`.claude/rules/<area>.md` with `paths:`): product facts *and* domain discipline for
  that area (eval methodology lives with `discodon/eval`, not in a fleet-wide corpus that
  non-eval repos would pay for). Per-file cap of the same order; an area file over cap is a
  curation signal for that area, not for the repo.
- **Portable engineering discipline** and **prawduct-meta** leave the product file as §5 already
  says (plugin corpus / upstream report). That is where 60% of discodon's bytes go and it is the
  step that makes any cap reachable; scoping does not substitute for it.
- The Critic cross-check reads core + every scoped file whose paths intersect the diff.

**8.5 Answer to "is the message just aggressive curation?"** Yes, with one free addition. Three
channels have evidence of firing: a rule in code at the moment of action, the Critic's required
cross-check, and a rule already in context. Everything else built to date (lookup fork, detail
and history files, sentinel lifecycle, audit tooling, reflection archive) has no measured
read-side yield. Harness-native path scoping is the one form of "filtering" that adds no
machinery, because the runtime does the retrieval — so it belongs in Option C. Anything beyond
it (a prawduct-side classifier, relevance ranking, a retrieval skill) is the same bet the lookup
fork lost. The cap's real job is not token savings — ~10K tokens a session is cheap — it is
forcing the author to curate while they still hold the episode; scoping lets that pressure be
applied per area, where an author can actually judge duplication.

**Open question added for §7:** 7. Per-scope budgets — one cap for core and one for each area
file, or a single total with the core weighted? And does the onboarded-repo contract move
learnings into `.claude/rules/` (harness-owned path) or stay under `.prawduct/` with prawduct
emitting the rules files?

```
# recompute (run in ~/source/discodon)
grep -c '^- \*\*' .prawduct/learnings.md; grep -c '^## ' .prawduct/learnings.md
# per-section bytes: split on '^## ', sum bullets per section
# PR area focus: git log --merges --since=2026-08-01 --format=%H | xargs -I{} git diff --name-only {}^1 {} | classify by discodon/<sub>|web|tests
# rules co-change: git log --since=2026-06-01 --format=%H -- .prawduct/learnings.md | xargs -I{} git diff-tree --no-commit-id --name-only -r {}
```

**8.6 Recommendation on the second half of Q7 (2026-09-02).** Move the learnings into
`.claude/rules/learnings/` as the single source of truth; do not keep `.prawduct/learnings.md`
and emit copies. Verified: rules subdirectories load recursively; `paths:` takes root-relative
globs (`discodon/eval/**`, brace expansion); scoped files trigger on Read only (Edit in this
harness requires a prior Read, so that is sufficient); committing/generated-file guidance is not
documented, which is fine — they are ordinary committed project files. Reasons: (1) one carrier
— an emitted copy is the file-sync pattern M4 deleted, and agents will hand-edit the copy they
read; (2) it is the cession `purpose.md` names — the harness owns loading and any future
relevance recall arrives for free; (3) every remaining prawduct job (cap gate, Critic
cross-check by glob ∩ diff, write-time obligation, report-bug routing, doctor migration) works
on any path. Layout: `learnings/core.md` (no `paths:`, always loaded, hard cap) plus one
`learnings/<area>.md` per scope with `paths:` in its frontmatter. The gate should budget the
whole always-loaded set under `.claude/rules/` — what loads is what costs, whoever wrote it —
with the ceiling per-repo configurable as today.

**8.7 Migration mechanics (2026-09-02).** Owner's constraints: doctor is never run
automatically and rarely by hand; advisories work but sit; two live modes are a cost.

*Evidence.* (a) Advisory dwell, fleet `.advisories.json`: active owner-decision advisories in
working repos are 37–68 days old (scriob `api-versioning` 68d, metallm 46d ×3, discodon 37d ×2);
of 35 resolutions on record, 4 were by action and 31 by `sync` (the condition went away). (b) The
backlog cutover is the dual-mode precedent: the migrate advisory shipped 2026-06-08, the
markdown read path is still live on 2026-09-02, 13 of 23 fleet repos are still on it (scriob,
scriob2, metallm, trenchant among the active ones), and keeping both modes coherent cost a
four-chunk plan (`skills-cutover-awareness`), dormancy NOTEs in three readers, a re-greppable
coherence test, and a `migration-required` probe that exists because the retirement is still
pending. That migration *needed* an owner decision — it creates real GitHub issues. (c) No
prawduct repair has ever auto-applied at SessionStart; every one (`lifecycle-repair`,
`norm-index-scaffold`, `plan-backfill`, `coverage-scaffold`) previews by default and doctor
says "offered, never applied". SessionStart writes only session markers. (d) 15 plugin files
name `learnings.md`; under Option C most are deleted, leaving ~6 readers (Critic and PR
protocols, reflection.md, record_lint, briefing, onboarding probes).

*Recommendation: hard cutover, agent-executed at first session, no owner gate, no dual mode.*

1. **The plugin version that ships the layout reads and writes only the new layout**, through
   one resolver (`learnings_files(product_dir)` → core + area files). The old path is not a
   second mode; it is a detected condition with one outcome.
2. **Old layout detected** (`.prawduct/learnings.md` present, `.claude/rules/learnings/` absent):
   the briefing's learnings line reads *"UNMIGRATED — not loaded"* and carries an `agent →`
   directive to migrate before other work. It is a directive, not a dismissable advisory: there
   is nothing for the owner to decide, because the relayout is local, lossless and
   git-revertible — the property the backlog cutover lacked. The Stop hook's floor: block
   session end while the old layout is present and code changed, the same gate-is-the-floor,
   directive-is-the-cadence pattern reflection uses.
3. **Two phases, only the first is the migration.** Phase 1, `prawduct-hook learnings-migrate
   --apply`, is mechanical and lossless: each `## Topic` section becomes
   `.claude/rules/learnings/<slug>.md`; the agent supplies the topic→glob map (the one judgment
   call, ~20 lines, proposed by the command from directory names and confirmed by the agent);
   unsectioned paragraph rules land in `core.md` under `## Unsorted`; `[detail](…)` links are
   stripped; `learnings-detail.md` / `-history.md` are deleted (git holds them). Refuses on a
   dirty learnings file. One commit, message naming the plugin version. Phase 2 — curation to
   cap, discipline out to the plugin corpus, framework friction upstream — is not a migration
   step; it is paced by the cap gate, which blocks *additions* to an over-cap file, never
   sessions, so an over-cap `core.md` on day one costs nothing until the next rule is written.
4. **The agent runs the command, not the hook.** A tracked-file rewrite that appears in the
   working tree at session start with no author is the failure mode doctor's stance guards
   against; the agent running it and committing it keeps the change attributable and the diff
   reviewable. The owner's control point is the migration commit, on the branch, not a
   pre-approval.
5. **The one mixed state is a repair, not a mode.** A feature branch that appended to the old
   file after `develop` migrated produces a modify/delete conflict — loud, one-time. If both
   layouts are present the briefing directs "fold `.prawduct/learnings.md` into the rules files
   and delete it"; the resolver never reads the old file.
6. **Adoption is per machine, not per repo**: the marketplace update reaches every repo on the
   machine at its next session, so the fleet converges in one round of sessions rather than the
   backlog's three months. Repos nobody opens stay unmigrated and lose nothing, because nothing
   reads them.

Rejected: an owner-decision advisory (dwell evidence above; the old layout would be silently
unread for the dwell); dual read paths (precedent above; and dual *write* is worse — the
methodology tells the author where to write, and two legal answers means both get written).

**8.8 Recommendations on the §7 open questions (2026-09-02).**

*Q1 — hard gate vs Critic finding.* Stop-hook gate, in `record_lint`, because rules are written
at work boundaries of every size and the Critic runs only on medium+. It fires when a file is
over budget **and grew this session**; the message carries the payment rule (pay from
duplication, or raise the budget with a reason). The raise is `learnings_budget_kb:` in
project-state, per file, reason required — the `oversized_file_threshold_kb` pattern. Trim-to-fit
is mitigated by the fact that the only way to add under a full budget is to delete or merge, and
merges/deletions are in the diff the Critic reads.

*Q2 / Q7 — count vs bytes, per-scope.* Bytes only, one number for every file (core and each area
alike), default **16KB**, per-repo raise with reason. Count is a proxy for the thing that
matters (tokens in context); a count cap lets bytes regrow (100 × 1KB = today's file) and a byte
cap lets count float harmlessly. 16KB ≈ 4K tokens ≈ 40 rules at the ruling's 400-char ceiling;
discodon's raw cross-cutting tier is 14KB, so the gate bites on its next addition there — the
intended pressure without a day-one cleanup. A two-area session loads ~48KB max (core + 2),
inside the envelope the harness itself uses for always-loaded context. The framework repo's core
will be over on day one; that is the point, and it blocks nothing until a rule is added.

*Q3 — discipline corpus ownership.* The framework repo owns it and curates it through its
ordinary build cycle; no periodic pass over consumer repos (that pass has run once in five
months, for the same reason doctor is not run). Intake is **push, not pull**: the write-time
detector (§5) that offers `/prawduct:report-bug` for framework-shaped rules also offers it for
portable-discipline-shaped ones, routing them to the framework's incoming inbox where the
existing `untriaged-upstream-reports` advisory already nudges. Seed once from §3.5's ten
cross-repo duplicates. Delivery is the three firing channels, never a file: a Critic goal, a
code directive at the action, or a methodology sentence — and for the residual, a line in the
session digest under its own budget. Plugins have no rules API (verified), and a large
plugin-shipped always-loaded corpus would recreate the defect one level up.

*Q4 — consolidation cadence.* No scheduled pass. The budget gate makes consolidation happen at
write time, by the author holding the episode. The fallback goes where rules are already read:
one Critic cross-check goal — *"rules added or changed this cycle: duplicate of an existing one,
wrong area file, or a discipline/framework rule that belongs upstream?"* — fires on every
medium+ cycle at zero marginal read cost. Janitor keeps an on-demand "learnings health" theme
for the rest; on-demand is acceptable for a fallback, not for the mechanism.

*Q5 — consumer migration.* Answered in §8.7.

*Q6 — cede beyond operator preference.* No. Episodes are consumed at the boundary (author →
rule/test/report; `.session-reflected` → handoff) and Claude's memory holds facts, not episodes;
the archive is deleted, not ceded. What *does* change: one session-digest line telling
auto-memory not to hold project state or product rules (`.prawduct/` and `.claude/rules/` are
authoritative), which closes the stale-snapshot leak seen in discodon's memory index. The
reverse leak (prawduct friction in a product's Claude memory) cannot be controlled and is
accepted.
