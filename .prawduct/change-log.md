# Change Log — Prawduct Framework

<!-- The LIVE change-log: release-pending entries, untagged entries, and the current release
     line. Append new entries at the top; each is a ## section followed by its prawduct tag line
     (an HTML comment carrying `type=` and `scope=`), and `scope=` with no `release=` IS the
     release-pending state — the release adds the tag.

     LIFECYCLE. Entries whose `release=` falls below the current minor line leave this file:
     `prawduct-hook archive-change-log` moves them whole into `.prawduct/change-log-history.md`,
     newest first, and refuses to write if any gate's answer would change. The release process
     runs it, so the live log stays bounded by release cadence rather than by anyone's diligence.
     History is a redirect, not a hole: nothing is deleted anywhere. (Entries before 2026-03-22
     were hand-moved into project-state.yaml under change_log_history before this lifecycle
     existed; that block is a relocation, not this mechanism.) -->

## 2026-09-10: the change-log gets a lifecycle

<!-- prawduct: type=feat | scope=change-log-lifecycle -->

Every other durable record here retires its entries somewhere — learnings to a history file, plans
to `archive/` — and the change-log had a header telling authors to append at the top and nothing
that ever took an entry out. It grew to 1.5 MB over six months, and every reader paid for it once
per session. The one archive that ever happened, hand-moving pre-March entries into
`project-state.yaml`, made that file's own oversized advisory fire; a relocation is not a
lifecycle.

**`prawduct-hook archive-change-log [--keep-minor X.Y] [--apply] [--json]`** selects entries whose
`release=` falls below the kept minor line and moves them whole into
`.prawduct/change-log-history.md`, newest first, append-only. The default line is read from the
version files the product's own `project-state.yaml` declares — never prawduct's layout, and a
declared-empty list is honoured as a declaration rather than a gap. **The safety invariant is the
deliverable:** before and after, the command computes the release-pending set, the unclassifiable
set and the tag-validation verdict over the live log, and if any differ it writes nothing and exits
non-zero naming what moved. An entry with no `release=` is never selected — that absence is the
release-pending marker, and dropping one unships work silently. Both files are written
all-or-nothing through one construction (`core.write_all_or_none`), so a failed second write rolls
back the first.

**The cut has been made.** 270 entries below v3.4.0 are in history; the live log holds the
release-pending set, the untagged entries and the v3.4.x line, and its header now states the
lifecycle — what stays, what leaves, what moves it, and that history is a redirect. The
releasability verdict was captured before the run and is identical after it.

**And it does not come back.** The release checklist (step 4, beside the plan sweep) and the
runbook now run the archiver — after `plan-backfill`, never before, because the sweep decides
"shipped" from the very `release=` tags the archiver moves out. And the size nudge gets a
ceiling this file can meet: `oversized_file_thresholds_kb:` in `project-state.yaml` gives one
governance file its own threshold (this repo sets the change-log's at 768KB, about a month of
entries with no release), a file with no entry keeps the repo-wide value, and the nudge's advice
names the archiver instead of telling the reader to delete old entries by hand. Both keys are
now documented in the template, which the repo-wide one never was. Two archiver defects the
cumulative review found ride along: a staying entry's pre-existing diagnostic no longer reads as
a new one when its line number moves (a refusal on a correct run), and every piece of the two
files is joined on a line boundary, so a live log with no trailing newline cannot glue history's
newest header onto its last line. `core.write_all_or_none` reads every prior before the first
write, refusing an unreadable file rather than deleting it on rollback, and rolls back on
`BaseException` so a Ctrl-C between the two replaces cannot leave the pair half-applied.

## 2026-09-10: an audit of develop, and the three findings that could not wait for the cut

<!-- prawduct: type=fix | scope=audit-followups -->

Twenty-three scopes were release-pending on `develop` since v3.4.0. Five independent read-only
auditors, one per cluster of related PRs, graded each scope's claims against its code, its tests
against `main`'s modules, its plan against its Status boxes, and its stated problem against what
actually ships. The report is `.prawduct/artifacts/audit-develop-since-v3.4.0.md`: five scopes
complete, sixteen complete with nits, two incomplete, none defective, and every scope's tests
confirmed red against v3.4.0. The recurring shape is the one worth naming — each fix closes the
instance it named and leaves the same class open one frame up, and the durable prose claims a
little more than the code carries. Three findings were fixed here because each would fail or
degrade the next release cut; the rest are filed as #776–#787, each citing the report, plus a
comment on #164 whose body still describes a retirement the burndown reverted.

**`file-upstream` filed an empty title or body without a warning, under every consent state.** The
skill composes both fields through `$(cat <path>)`, and a path the reader did not actually hold
reads as nothing: the flag is present, so the presence check passed; the `[prawduct]` prefix alone
cleared the title floor; and under `always-file` nothing later compares bytes. The 2026-09-08 entry
named this exact failure and closed it in skill prose. It is now refused in `check_payload_inputs`,
where every composition runs, on both arms — a whitespace-only title or body is a validation
error naming the flag, the component stays optional, and the transport sees no call. The skill
text and the test docstring that said "nothing downstream catches that" are corrected. One more
record correction rides here rather than being rewritten in place: that same entry said the
cross-call shell-variable pin "ships with a positive control that catches all six command lines
of the variable form". No such control exists — the pin scans the live skill and nothing else. The
pin is still the right one; the claim about it was not true.

**The release step would have refused to archive the review-loop-termination plan.** A v3.2.0
plan of the same scope already sat in `archive/` under the same filename, and `archive-plan`
refuses to overwrite an earlier plan — so `plan-backfill --apply` would have exited 1 at the cut.
The archived one now carries its release in its name. Scope resolution reads frontmatter, not
filenames, so nothing that looks the scope up changes its answer; a live plan beats an archived
one of the same scope, as before.

**branch-claim-multiplicity's Chunk 04 stays unticked, and the reason is now a finding instead of
a wait.** Its live half — a sibling repo actually running the develop track through the documented
`settings.local.json` recipe — became runnable when PR #658 merged on 2026-08-27 and was never
run; `operator_verification_required: false` means no gate was ever going to raise it. It was run
from an agent session on a governed sibling, and the recipe did not take: in print mode the
settings-declared marketplace was neither registered nor installed, and because the same block
disables the released plugin, that session ran with no prawduct governance at all. Whether an
interactive start registers it is what only an operator at a terminal can see, and VRF-017 now
says so, with the block left in place for that check. The cut's `plan-backfill` refusal therefore
stands, deliberately: ticking the box would say the track works, and nobody has yet seen it work.

## 2026-09-10: a build plan's chunk fields bind in the forms authors write

<!-- prawduct: type=fix | scope=critic-mode-field-parse -->

The plan-level `Critic mode:` override was read line-anchored and unbackticked, so two forms real
build plans use were invisible to it: the field sharing a line (`**Type:** doc-only · **Critic
mode:** final`) and a backticked value (``**Critic mode:** `chunk` ``). Neither raised anything —
`_unrecognized_mode_note` fires only for a token that matched and is not a mode, and a non-match
emits nothing — so a plan-mandated `final` ran as an inferred `chunk` with a rationale that never
mentioned the plan. That is the silent demotion the field's reader exists to prevent, reached
through a different door, and its blast radius is every build plan in every governed product,
where the symptom is a shallower review that looks like a normal one.

The read is now unanchored, with an optional backtick before the value, and bounded by position —
what counts as a declaration rather than a mention is the shared predicate described below. **The
whole chunk section is scanned**, and a valid token anywhere in it beats anything unhonorable above
it — answering on first sight would let a sentence *about* the field bury the declaration below it
and report the loss as a typo, pointing the author at the wrong line.

101 `**Critic mode:**` lines across this repo's 103 build plans are now a test corpus. The
hand-written form list can only contain forms someone thought of; that is what missed these for as
long as it did. Its oracle is built independently of the reader — text after the marker, first
word, punctuation stripped — because one built out of the reader's own regex can only agree with
it. Measured against the old anchored read, lines were being lost outright in every plan that
composes its chunk header — re-derive with the corpus walker rather than trusting a number here. The
`build-plan` prefixes join `suite_coupled_prefixes` as a consequence, spelled narrowly on purpose:
`.prawduct/artifacts/` would have taxed every Status-box tick with a four-minute suite re-run.

**The missing signal was the larger half of the defect.** A field carrying something no mode token
can be read out of — `**Critic mode:** (inferred — `chunk`)` — now earns the same one-line NOTE a
typo'd mode does, quoting the value verbatim and naming the plan line it sits on. Silence there said
*this chunk declares no mode*, and the author had written one. Absent and blank stay silent,
unchanged: they carry no intent to contradict.

**Reporting is anchored where binding is not, and the asymmetry is the design.** Binding a mode is
safe from anywhere on a line — only one of four words can win, and the plan's author wrote it.
Reporting is not: an unanchored report announces a Description sentence *discussing* the field as an
ignored declaration, which it did on ten chunk sections in this repo before the anchor went back on
the report alone. A note that fires on ordinary plans is not a warning, it is something its reader
learns to skip — and then skips on the chunk that needed it. The sections that still earn one are exactly
those carrying a real field-position value that names no mode. The token must also end at a delimiter now, so
`n/a (verification only — nothing to review)` is quoted whole rather than reported as the mode
`'n'`, a string appearing nowhere in the author's plan.

**`**Type:**` and `**Trivial because:**` carried the same defect and are fixed with it**, on the
owner's ruling — they are the same lines, since an author composing `**Depends on:** — · **Type:**
code · **Critic mode:** chunk` is writing every one of those fields mid-line. Nine live lines in
this repo's plans were losing their type outright; two chunk sections were running the full
protocol under the `code` default against a `doc-only` their author had declared and backticked.
This lever is the one that decides which plans qualify for a bounded gate, so it was held for a
ruling rather than folded into a bug fix: widening it can lighten a gate, not only restore one.

**Field position is read first here, and it is read differently, because what a wrong value costs
differs per field.** An unknown `Critic mode:` earns a note; an unknown `**Type:**` fails the
chunk, and `trivial` / `doc-only` / `designer-handoff` *buy* something — the last of them skips the
Critic gate outright. So the type reader takes a declaration in field position as final, typo
included, and a value there that no token can be read out of (`**Type:** n/a (docs only)`) is now
reported verbatim rather than defaulted: that was a real silence, and quoting the readable prefix
`n` would name a string appearing nowhere in the author's plan.

**What separates a declaration from a mention is POSITION, and it is one predicate now, shared.**
Searching a line for a field makes composed headers readable and makes every prose line a
declaration site — so a Description sentence naming `**Type:** designer-handoff` would have
switched review off, silently, in every governed product. A field declaration is one that opens its
line, follows a composition separator (`·`), or opens a sentence; anything else in front of the
marker is prose *about* the field. **All three field reads go through it**, and a source-scan test
says so rather than the prose alone — the `**Trivial because:**` fallback was written with a bare
`.search` and let a Description sentence supply the rationale that buys `Type: trivial` its bounded
review, on a section that declared none. A claim that a rule is shared is worth what enumerates it.

**Sentence-initial is the residual, and it is a real one.** A period separates composed fields in
this corpus as freely as a `·` does (`**Type:** doc-only. **Critic mode:** final`), so the
predicate has to accept it — and the cost is that a Description sentence *beginning*
`**Type:** designer-handoff chunks skip review…` still binds. Mid-sentence mentions, which is what
prose about a field overwhelmingly is, do not. The bound that remains is the author's:
`methodology/planning.md` now says not to open a LINE or a sentence with a field marker, and to
write about one by keeping the marker inside the sentence or dropping the asterisks. **Backticking
is not an escape** — the line-opening class allows it deliberately, because line-initial
``` `**Critic mode:** chunk` ``` is a live declaration form here, and a first draft of that guidance
recommended it anyway. Narrowing the predicate instead would cost the composed forms real plans
use, which is the defect this whole entry is about. Both readers bind through that predicate, and neither reports
from it — position is a heuristic, and a heuristic must not be the thing that fails someone's
chunk. The field grammar itself is now one factory in `buildplan_refs` rather than a shape copied
reader to reader, which is how the two delimiter sets had already come to disagree about `<br>`.

`**Trivial because:**` is two passes for a sharper version of the same reason: its capture runs
until the next field, so one permissive pass would start at a line *discussing* the field and hand
the gate that sentence instead of the rationale declared below it — a rationale silently ungraded,
which is worse than the missing-field block it was meant to prevent.

## 2026-09-09: the review loop gets a stopping rule

<!-- prawduct: type=feat | scope=review-loop-termination -->

Every control this plan shipped prices a review round, refuses a wasteful one, or shrinks what one
produces. None of them ever says *stop* — and the measurement this plan was built on says nothing
else will. Across 728 review facts in this clone's store, findings per full round **rise**: 13.5,
15.4, 15.5, 18.4, with 99% of them new rather than re-raised. A review loop has no natural fixed
point, so every "one more round" reads locally reasonable, and chains of twenty to thirty-four
rounds are the result.

**`review_round_budget` is the declared stop.** Six full rounds per build-plan scope — the unit is
the scope and not the branch, because a branch may carry two scopes and a trunk-based repo's
merge-base span is zeroed by every push. On by default in
every governed repo, `null` to disable. Off-by-default was rejected for the reason #716 reports
about `cost-of-commit` — a mechanism that works and that nobody knows exists. Six rather than four
because it sits above every chain in the store that ever produced a late BLOCKING finding, so it
costs close to nothing in missed defects while still catching the chains whose round count is
indefensible on any reading.

At the ceiling `critic-begin` exits **4** — a new documented sentinel, not an overload of exit 3,
because a 3 says the gate does not want this round and a 4 says the loop has run out while the gate
may still be unsatisfied, and the caller's next move differs. The refusal auto-ACCEPTs the
outstanding non-blocking findings with the budget as their recorded reason, renders the census, and
writes no session state.

**Two bounds carry the whole safety argument, and both are pinned by tests.** A
`verify-resolutions` pass is neither counted nor refused — it is how a BLOCKING finding clears, so a
ceiling that ate it would strand findings with no command that resolves them. And no BLOCKING
finding is ever swept, guarded twice: filtered in the sweep, and independently refused by
`dispositions.record`, which demands an owner ruling the automatic path never supplies. **The budget
can end a review loop and can never open a gate.** Its firings append a `guard-refusal` fact under
the sink the whole pre-dispatch-guard class already uses, which is what keeps the six falsifiable.

**`--fixed` closes the hole where the cheapest correct action sat.** A fix confined to non-judgeable
paths buys no round, so no verify pass runs, no resolution fact is written, and the census reported
it undispositioned forever — leaving "don't fix it" and "spend ten minutes" as the only visible
answers. `prawduct-hook disposition <review> <fid> --fixed <paths>` records it, and the paths are
checked at record time against the same predicate that prices the edit: a set holding anything
judgeable is refused, so nothing launders a judgeable fix past a gate. BLOCKING is refused too. The
census state is `fixed-unreviewed`, deliberately not `fixed` — both say the defect is gone, and only
one says a reviewer looked.

**The prose correction is the load-bearing half.** `review-cycle.md` asserted that by round 3 a pass
finds defects in the record of round 2 and that this is the signal to stop. The store says the
opposite. Shipping a budget while that stood would leave two stopping rules, and the false one is
the one an agent can check against the store and therefore learn to distrust — which is the
behaviour this whole plan exists to fix. Replaced with the measured rise, carried with its numbers.

**`agents/` becomes governance-protected**, closing the half Chunk 03 left open. A subagent's system
prompt is behavioural logic by exactly the argument that protects skill prose, and the reviewer's is
that argument's strongest case: it decides what an independent review looks at, so an unreviewed
narrowing there compounds across every review after it. `TestAgentsNoLongerSpecial` recorded the
omission as intentional when the pre-2.0 `agents/` tree was deleted; the tree came back, so its
premise is gone rather than overruled.

**And a refusal stops manufacturing the round it refuses.** `begin_review`'s "nothing to verify"
branch returned a bare error, surfacing as exit 1 — which `SKILL.md`'s exit table routes to
"re-dispatch per the demotion property", meaning a full `cumulative` on a bundle the gate already
reports satisfied. It is a no-review-needed and now takes exit 3.

Exercised end-to-end against this branch's real review history in a scratch clone: the refusal
fires at the ceiling, the census renders across all five of the scope's reviews, no BLOCKING finding
is swept, and the firing lands as a countable fact. The two WARNINGs Chunk 01 fixed for free are
recorded live as `--fixed`.

**Named gap, carried rather than built:** a fix that rode a *later* round-buying commit still has no
recordable answer against its own review — `--fixed` correctly refuses it and no verify pass was
ever anchored there. Closing it needs a join between a finding and a later review fact whose
interval contains the fixing commit, which is coverage-kernel work with its own lock-in question.

**What the cumulative review changed, because two of its findings were about the chunk's own thesis.**
The ordering was wrong: the budget was checked *above* the free-interval refusal, so on an exhausted
scope a records-only dispatch — the question the framework advertises as free — was answered with
exit 4 and an auto-ACCEPT of every outstanding finding. The two exits exist because "the loop is
over" and "there was nothing to review" are different answers; the budget now sits below the free
one. And the demotion table in `review-cycle.md`, the canonical explanation of `verify-resolutions`
anchoring, still priced the nothing-to-verify refusal at exit 1 and routed it as a demotion — the
manufactured round this chunk removes, shipping in the same commit.

Also from the review: eight active learnings had lost their narrative blocks in the base-advance
merge — present at both parents, absent at HEAD, every rule still citing a file that no longer held
them, and one merge short of propagating to develop. Restored, with the rule that found it.

## 2026-09-09: review eligibility stops being the negation of review cost

<!-- prawduct: type=fix | scope=review-loop-termination -->

The subject/oracle split shipped in August asked `is_judgeable_path` which files a finding could be
about. That predicate answers a different question — *does an edit here re-open the coverage gate?*
— and it had only ever been asked the cost question until the split gave it a second job. Its
exclusions were never re-vetted against the new one.

Two things fell through. A review subagent's own system prompt (`plugin/agents/critic-reviewer.md`)
is behavioural logic by exactly the argument that protects skill prose, and it classified as an
oracle — read, never rated. So did the norm, principle and waiver references under `plugin/docs/`.
Both are one directory each, and a longer path list would have closed both.

The general case is what a path list cannot reach, and it is not this repo's. For a governed product
whose **deliverable is markdown** — a docs site, a spec repo, a prompt library — every product file
is non-judgeable, so a single incidental `.py` in the interval defeated the all-prose floor and the
product's entire output became read-but-never-rated against all seven goals. `is_judgeable_path` is
not product-configurable, and this plan's `governed_by:` dispositions covered language-independence
but never this shape.

`coverage_algebra.is_review_subject` now owns eligibility as its own question: a **deliverable, or
prose that governs behaviour**, is a subject however the gate prices it; only a record *about* the
work (`.prawduct/**`) is an oracle. It fails closed toward subject — a path it cannot place is
reviewable, because over-inclusion costs reviewer attention while under-inclusion ships an unrated
deliverable, and only one of those is recoverable.

**It costs 4 points of the 36 the narrowing bought.** Measured over the 3,542 findings in this
clone's store that name files: the judgeable-only rule made 65% of them subjects, the classifier
makes 68%, and the 32% that are pure `.prawduct/` records — the bulk of what August removed — stay
out. What returns is `documentation/` (88 findings), `docs/` (29), `plugin/` prose (17), `README.md`
(9), `CHANGELOG.md` (2) and `agents/` (1).

A test fails if the two predicates are ever reunited, rather than only checking today's answers: a
future edit that re-derives one from the other would keep every other assertion green by coincidence
of the corpus. Chunk 02's own `test_the_subject_set_drops_non_judgeable_paths` asserted
`docs/guide.md` as an oracle and is rewritten to the corrected rule — the file moves INTO the subject
set, which is strictly more review.

Prose: the Records Pass in `review-cycle.md` taught eligibility as "is it judgeable" and now teaches
the rule, pointing at the classifier's docstring for the case rather than restating it. Its ceiling
rose 9980 → 10065, declared with that reason at the assertion.

The chunk's own review returned **0 blocking, 3 warning, 2 note**, and every actionable one was the
same class: prose that still taught the rule the code had stopped implementing. `review-protocol.md`
— the `final`/`cumulative` reviewer's own protocol — still said "findings-eligible, judgeable paths
only", so a reviewer reading it would have applied the removed rule; its ceiling rose 3995 → 4035
after paying down the first draft. Three comments in `critic_consolidate.py` asserted the
conflation, and **one had teeth**: the justification above `_scope_widened` claimed a fact's
`files_reviewed` IS the judgeable subset, which made the live re-narrowing of `prior_files` look
redundant. It is not — since the classifier, a subject set admits deliverables and behaviour-
governing prose that this cost-based threshold must not count, so dropping the call would inflate
the prior count and LOOSEN the widening bound, failing open and silently. Nothing pinned that path;
`TestWideningBoundCountsTheCostSubset` now does, asserting first that the two sets genuinely differ
so the pin cannot pass vacuously.

The review also caught that the plan recorded Chunk 04's `agents/` carry as discharged. It is
half-discharged: `plugin/agents/critic-reviewer.md` is now a review subject, but it stays
non-judgeable, so a commit touching only a review subagent's system prompt is still a free edge.
Eligibility and cost are different questions and this chunk answered only the first — deliberately.
The plan now states the residue and hands the second question to Chunk 04 rather than closing it on
paper.

## 2026-08-25: judgeability decides what a review RATES, not what it READS

<!-- prawduct: type=feature | scope=review-loop-termination -->

Non-judgeable files were 39% of every file-slot handed to a reviewer (5,869 of 14,860) and 36% of
every finding returned (1,372 of 3,826). Those findings are correct — the measured false-positive
rate across this class is zero — and almost none of them are worth what clearing one costs: a fix on
a record buys nothing at a gate, and a builder who fixes it anyway moves the tree and buys a round.

`critic-begin` now splits an interval into two sets. `files_reviewed` is the **subject** set —
judgeable paths only, the sole files a finding may be *about*. What it sheds rides as
`files_oracle`, delivered to every reviewer to read and rate by none.

**Only the subject role narrows, and the distinction is the whole design.** A non-judgeable file
plays two parts: it can be *wrong*, and it is the authority the code is judged *against*. Every spec
in this repo is non-judgeable — the build plan, every artifact, `project-preferences.md`,
`cross-cutting-concerns.md` — and the reviewer is sent to exactly those for Goal 2's
requirement-coverage check and Goal 3's norm-departure check, both of which rate BLOCKING. Narrowing
what a reviewer may *read* would have removed its oracle while looking, on every metric this change
is measured by, exactly like the narrowing working: fewer findings, less reader load. A guard test
now fails when the oracle is withheld, because the success metric cannot tell the two apart.

`coverage_algebra.review_edges` validates an edge by quantifying only over
`judgeable_files(files_changed)`, so a subject-set `files_reviewed` still covers every file an edge
asks about — re-verified against the code before a line changed, and pinned by a test in both
directions. The verify-resolutions scope-widening threshold now measures subject sets on both sides;
prose riding along on a fix can no longer demote a re-review.

**The window this opens has one cover: the Records Pass**, a third final-mode cross-check (the
`sustainability` role) that rates the excluded set against the two bars the severity contract
already defined — *it ships*, *it misleads into action* — and names the set it covered. Those bars
moved out of the builder-facing severity paragraph rather than being restated beside it: two
stopping rules where one is false is the failure this whole plan exists to fix. The review fact
records `files_oracle`, so an exclusion is auditable rather than indistinguishable from a reviewer
that simply found less.

Two items rode this commit rather than buying a round of their own. **The `fix_cost` FREE phrase is
now relational** — a finding's `files` is where the reviewer *saw* the problem, not where a remedy
lands, so the phrase prices an edit confined to the cited files, says so, and routes the real batch
to `cost-of-commit`. And **`governed-by-gap` now grades a frontmatter no parser can read**: this
plan's own YAML header was invalid for two commits and three regex-based readers passed it, which
presents as *more* governed than no header at all. There is no YAML dependency to reach for, so the
check grades the one structural break the line-based readers are blind to and reports nothing it
cannot see.

`## Directional Change Review` was cut from `review-cycle.md` — three bullets restating Goals 1, 4
and 5 under a trigger condition that is just `cumulative` mode, referenced by nothing.

**The chunk's own review corrected the rule it shipped, and the correction matters more than the
rule.** The subject restriction went out as an *absolute* — "a finding may only be about a
`files_reviewed` path" — while the protocol eleven lines below it still ordered `chunk-ref-missing`
to BLOCKING on a record, which is an oracle path by construction. The review proved it by producing
one: its single `record_lint` finding sits on `.prawduct/learnings.md`. A reviewer obeying the
absolute in `chunk` or `verify-resolutions` — modes with no Records Pass to route it to — would have
swallowed a machine-detected BLOCKING. Closed by construction rather than by a longer list: three
passes own oracle findings and are exempt (the record-lint relay, the Learnings Cross-Check, the
Records Pass), stated once in `review-cycle.md` with every other surface pointing at it.

**Record-only BLOCKING is still reachable, and that is now a decision rather than an oversight.** The
narrowing was justified from a table bucketed by finding count; the row of that same table measuring
severity cost was never disposed. **54 of 236 BLOCKING findings (23%) had a record as their only
subject**, and a Records Pass whose bars both read WARNING would have traded that class away in
silence. It has a third bar: an instruction that actively misleads — a wrong command, a deleted
config reference — is BLOCKING there, exactly as Goal 4 has always rated it.

**And the verify pass caught the fix's own regression, which is the sharpest thing in this entry.**
Widening what may follow a closing quote to admit flow punctuation (`,`, `]`, `}`) looked free: the
shapes it was meant for — a scalar inside a multi-line `[...]` — are already excluded by the marker
rule, because a flow continuation line carries no `- `/`key: `. But those characters are reachable
with a scalar **already open**, which is the break case. In `a: "one` / `b: ", two"` the unterminated
scalar swallows the next line and closes on its quote, stranding `, two"` — unparseable YAML that the
check reported before the fix and passed after it. A false negative on `governed-by-gap` is silent by
construction: it is the machine-answered channel a reviewer relays verbatim. The allowance is back to
`#` and `:`, and each of the three boundaries that moved now has a test that fails when it moves back.

Also from that review: `_scope_widened` counted through the all-prose floor and so reinstated the
prose it means to discount; the verify-resolutions arm rebuilt its oracle from the prior *subject*
set and dropped the plan a verify pass must be handed; `critic_mode` asserted `files_reviewed` holds
judgeable paths only, which is false of every fact written before this commit; and
`_frontmatter_break` reported three legal YAML shapes as broken (a quoted key, and continuation lines
of flow and plain scalars that begin with a quote).

## 2026-08-25: every finding says what acting on it costs

<!-- prawduct: type=feature | scope=review-loop-termination -->

The disposition menu is priced backwards from the intuition, and nothing said so at the point of
decision. ACCEPT is always free. FIX is free on a non-judgeable surface and costs a whole review
round on a judgeable one — coverage is keyed on the tree, so any judgeable edit re-opens the gate
that same round was run to close. A builder told to "fix anything cheap" reads *cheap* as *small*,
and the smallest fixes — a change-log sentence, a stale count — are exactly the ones where the
surface, not the size, sets the price.

Measured on this repo's evidence store: of 3,826 findings across 728 reviews, **1,372 cite only
non-judgeable files** and were free to fix all along, while 2,361 buy a round and 93 cite no file at
all. Nothing at the decision point told those three classes apart.

`.critic-findings.json` now carries a `fix_cost` on every finding. The predicate is
`coverage_algebra.is_judgeable_path` — the same one the gate charges by, so the price quoted to the
builder and the price charged at the gate cannot drift. It states only *whether* a round is bought;
`telemetry.round_price` still owns what a round costs and the record's `next_action` already carries
that sentence, so no figure is restated per finding.

**It fails closed toward charged.** A finding citing no file reads `unknown`, never `free` — a wrong
"free" is the reading that spends an unbudgeted round, while a wrong "charged" only declines a
saving. The key is additive and the schema validator checks required fields only, so no existing
reader breaks.
## 2026-09-09: `/prawduct:pr` Step 2 stops promising a saving it cannot always deliver

<!-- prawduct: type=docs | scope=gate-accuracy -->

Step 2 told the builder *"run the pass on the dirty tree, then commit it whole, and there is one
round instead of two."* Followed literally, it cost the round it promised: `verify-resolutions`
refused with exit 3, reported that it had graded committed HEAD rather than the working tree, and
named the uncommitted judgeable file as NOT REVIEWED.

**The guidance was not wrong — it was unconditional about a conditional outcome.** The pass may
instead anchor on a prior review and grade committed HEAD, in which case it refuses and names the
uncommitted judgeable files. There the order inverts: commit first, then run the pass over the delta
that appears — which is what the refusal itself says.

**The first attempt at this entry named a mechanism that does not exist**, and it is recorded here
because the retraction is the lesson. That draft claimed a `diff ⊆ scope` contract enforced in
`begin_review`'s verify arm and cited a symbol that is not defined; the arm's only refusal is
cardinality, which one unseen file never trips. It was written from a code comment rather than from
the handler. The shipped sentence therefore cites **no internal rule at all** — only what the
dispatcher observably does — which is the honest scope of what was verified, and it tells the reader
not to predict which case they are in, because dispatch is seconds and its own answer is
authoritative.

Nothing in the mechanism changed; it already behaved correctly and announced itself. Only the
instruction was incomplete.

## 2026-09-09: the freshness gate stops calling instruction prose untestable

<!-- prawduct: type=fix | scope=gate-accuracy -->

`affects_test_outcome` answers *can a change to this path change what the suite says*, and it
answered **no** for every non-governance-protected `.md`. That is false here and false in general:
`TestClosingKeywordClaims` sweeps `documentation/`, `test_no_governance_prose_cites_a_flow_step_by_NUMBER`
sweeps governance prose, and both predate by two weeks the design doc that merged failing them.

**The consequence was not theoretical.** Two `documentation/issues/*.md` files reached `develop` red;
`_test_evidence_tree_valid` classified them as *only non-judgeable paths changed*; `test-status`
reported day-old evidence as `current` over a tree whose suite was red; and the next branch to sync
the base inherited it. The repo already held the correct reasoning one file over — the CI workflow
refuses path filters in as many words, *"a docs-and-state change really can turn the suite red. A
filter that calls those paths untestable would hide exactly that class of break."* This predicate was
that filter.

**The roots are declared by the repo, not carried by the framework.** `suite_coupled_prefixes:` in
`project-state.yaml` names them and `core.suite_coupled_prefixes` reads them; the default is empty,
so an undeclaring product is byte-for-byte unchanged. Hardcoding `plugin/` and `documentation/` into
the shipped predicate was the first cut and it is wrong in both directions at once: no product repo
has a `plugin/` directory, so the rule would be inert exactly where it shipped, while any product
that happens to name a directory `documentation/` would start paying for prawduct's tests. Which
directories hold prose a test scans is a fact about one repo's layout, so it lives where the layout
does.

**Blanket `.md` was the other rejected design**, and it silently overturns two priced decisions: the
residual named under `TEST_COUPLED_STATE` (bookkeeping held out **on cost**, whose sound close is
hermetic tests, not a wider set) and the `README.md` / `docs/notes.md` line their tests pin. All
three pins stay green unedited.

**Review coverage did not widen, and keeping it that way took a deliberate choice rather than an
absence.** `coverage.check_pr_doc_only` consults `suite_coupled_files` too, so making the roots a
DEFAULT would have retired the doc-only fast path — a documentation-only PR would have started
buying a full cumulative Critic and PR reviewer, a cost nothing priced. The declaration is therefore
a parameter passed at the freshness call site and withheld at the review one: this says *re-run the
suite*, never *buy a review*. `is_judgeable_path` is untouched, so the batch-fix directive's promise
that `.prawduct/` and doc writes are free mid-review stays true.

**This is the docs half of `#238`** — *"gates: a doc-only PR can silently break a repo-coupled
test"* — which was closed when its state half shipped as `TEST_COUPLED_STATE`. The class stayed open
for prose, and the 2026-09-08 incident is that remainder arriving. Recorded rather than reopened: the
issue's own subject is now true again only in the residual below.

**Residual, named rather than closed:** `_governance_prose()` sweeps every tracked non-record `.md`,
which is wider still — `README.md`, `docs/*.md` and a live build plan can flip the suite while this
predicate calls them free. Closing that means overturning the priced exclusions above, which is an
owner cost decision, not a defect to fix in passing.

**Also true, and not fixable in code:** the two red commits were pushed **directly to `develop`**,
so no `/prawduct:pr` gate was ever reached and CI's failure on both pushes was read by nobody.
`develop` has no branch protection; 5 of the last 50 runs on it failed. That is a repo setting.

## 2026-09-09: the scratch path a reader holds, and the fix that read as working code

<!-- prawduct: type=fix | scope=upstream-report-bug -->

Third round on one defect class in `/prawduct:report-bug`'s step 2, and the third is the one worth
recording, because it was caused by the second.

Round one: the three composed fields went through the shell as literals, so a backticked prawduct
term ran as a command and a `$…` symptom expanded to nothing — the title filed with the defect's own
name deleted from it. Fixed by reading each from a file via `$(cat …)`, whose output is not
re-expanded. Round two: PR review found the file location was `<scratch>`, an undefined placeholder —
the one placeholder in the skill naming a value the reader did not hold, in a skill whose whole
subject is not writing into a governed product's tree. Round three is that fix: it named the
directory with `SCRATCH="$(mktemp -d)"`, **which reads as working code and is not.** The Bash tool
does not persist environment variables between calls, and the preview and the send are necessarily
separate ones, so by the send `$SCRATCH` is empty and every `$(cat …)` reads nothing. Nothing
downstream catches it — the flags are still present, `check_payload_inputs` bans only newlines and
prawduct fences, and standing consent never compares the digest — so the skill would file an
empty-bodied issue into a repo where it cannot be retitled or deleted.

**The fix was a worse failure than the bug.** `<scratch>` was visibly a blank to fill; `"$SCRATCH"`
looks like it works. `mktemp -d` now prints the path and the skill says to paste it, with the reason
stated where the next editor will read it: a path you paste is a value you hold, a variable is not.

**What the sibling test could not see, and now does.** The existing pin asserted that every composed
field arrives via `$(cat …)` — which the broken form satisfied, being a `$(cat …)` over a path that
does not exist. The new pin asserts the other half, that no such line carries a shell variable, and
it ships with a positive control: it catches all six command lines of the variable form and none of
the prose. A grep over `plugin/skills/`, `plugin/methodology/` and `plugin/templates/` finds no other
cross-call shell variable, so the class is swept rather than assumed.

## 2026-09-08: the upstream bug drop-box retires, and every surface still describing it stops

<!-- prawduct: type=refactor | scope=upstream-intake-repoint -->

With `untriaged-upstream-reports` counting filed issues, the channel it replaced is retired
(upstream-filing design §7.4). Reports about prawduct are GitHub issues; nothing routes one into a
local directory any more, and nothing shipped says otherwise.

**The retirement is one act per substrate, and the substrates do not take the same treatment.**
`lib/bug_inbox.py` — the resolver that picked the directory — is deleted, and so is
`templates/incoming-bug-report.md`, the scaffold for a report shape nothing produces. The
`bug-inbox` **subcommand** is not: it is human-callable, and the 2026-08-11 harness-only-removal
exception is scoped to subcommands the harness alone invokes, so
[[deprecation-requires-an-inert-retention-window]] governs and it becomes inert — a `WARNING:` on
stderr, exit 0, removal deferred to a major. It joins `regen-views` and `stamp-merged` in the
*announcing* tier rather than the silent one, because its caller is a person who can act on being
told to stop. Its exit code moves 1 → 0 deliberately: the 1 meant *no inbox is configured*, a
condition a caller could branch on, and nothing can be configured now.

**What is deliberately NOT deleted is an operator's `incoming-bugs/` tree.** It is gitignored, so
anything still sitting in one has no git copy and `rm -rf` is unrecoverable — an owner-approval
operation this build declined rather than sought approval for. Its `.gitignore` line stays,
re-commented alongside the retired `.prawduct/.bug-inbox` pointer, so a machine that used the channel
does not suddenly see untracked reports as git noise.

**The `.gitignore` propagation contract changed, and `RETIRED_GITIGNORE_ENTRIES` was declined
deliberately.** `.prawduct/.bug-inbox` leaves `core.GITIGNORE_ENTRIES` and its `prawduct-hook`
`_SESSION_GITIGNORED_PATHS` mirror, so a newly onboarded product never receives the line — but it is
NOT added to `RETIRED_GITIGNORE_ENTRIES`, which means an already-onboarded product keeps its line
forever, `update-gitignore` will not clear it, and `probe_gitignore_contract_drift` stays silent
about the difference (an entry in neither `MANAGED_FILES` nor the retired set is invisible to
`_contract_diff`). That asymmetry is the intended outcome, for the same reason this repo's own
`.gitignore` keeps the line one file over: retiring the entry would un-ignore a directory that
existing machines may still hold, turning an operator's archived reports into untracked git noise at
the exact moment the channel stops explaining itself. New products get a clean contract; old ones
get a harmless extra line. Recorded here because the two halves diverge silently otherwise, and the
next reader would re-derive the reasoning from an absence.

**A grep is the only thing that quantifies over the prose, so a grep is what pins it.** Removing a
mechanism requires removing its name too: a skill or guide that still says a report goes into a
directory routes the next model into writing one where nothing reads it, and every such surface
passes its own tests while doing so. The new sweep holds two rules of different shapes — write-path
machinery (the env knob, the resolver, the pointer, the write-target template, the report scaffold,
the archive destination) appears nowhere in the shipped tree, and the directory name appears in no
instruction surface at all, `CLAUDE.md` included. Code stays exempt from the second: the inert
subcommand names the directory to say the channel is over, which is a sentence addressed to a person.
Both legs carry a positive control, because every assertion in them is an emptiness check and a
corpus that silently came back empty would satisfy all of them.

**Three worked examples that had quietly become archaeology were repointed rather than left.** The
build-plan ref checker's "intentionally-gitignored managed path" example named the pointer file it no
longer knows about, its angle-bracket write-target example named `<inbox>/`, and the advisory
briefing's prerequisite-ordering docstring described the drop-box→migration edge in the present
tense. The first two now name live paths; the third keeps the example — the advisory spec
deliberately retains it as the only rendering of a prerequisite pair anyone has read — and states in
the past tense that both ends are retired.

**One requirement's expired clauses are corrected in place, not rewritten.**
`backlog-service-requirements.md` still listed the `untriaged-upstream-reports` probe among things
"to be removed" and called the drop-box "the interim supported path until the GitHub-issue path is
built". Both expired: the path is built, and the design chose to **repoint** the probe rather than
remove it, because the receiving side needs a nudge whatever the channel is. Recorded as a dated
divergence beside the original text, the way the design records its own — a requirement is the record
of what was asked for, and editing it to agree with the code is how the ask disappears.

**And Wave B's owed observation is discharged here rather than waiting for a commit that file
happens to get.** The egress test's docstring and assertion message still enumerated
`--title`/`--component` after `--body` joined the shell-literal class; the fix was deleting the
enumeration, not extending it. Its sibling test loses its carve-out in the same pass: it used to
allow the skill to *mention* the drop-box because untriaged reports were still sitting in one, and
with the channel retired the ban is total.

**The cumulative review (`rev-20260908T220843Z-9c210bc4`, Waves B + C over `40b772b2...b23a0ef6`)
returned 0 blocking, and its sharpest warning was about Chunk 01's code rather than this chunk's.**
`unstaged_items` answers `ok` for a store whose last sync FAILED — it carries the rows plus a
`sync_error` — so *readable* and *current* are different questions and the probe was asking only the
first. With rows behind a stalled feed it printed a bare count as if current; with none it went
silent, which is the false all-clear a triage nudge cannot emit and the exact shape the paragraph
above claims to have avoided. The reading is now two axes, and each branch uses the second in the
opposite direction: a stale count is stated as a **floor** (stale rows can only under-report), and a
stale **zero** gets its own candidate with its own evidence, so dismissing "the cache is unreadable"
does not also dismiss "the cache is stale". Three states, three advisory ids.

**One departure from the reviewer's own recommendation, taken deliberately.** It proposed carrying
`sync_error` into the trigger summary, correctly noting the text is free to vary. But that string is
a provider message relayed through `gh`, and advisory copy is rendered into the model's context at
session start — the one class of bytes this probe's whole posture keeps off that path. The advisory
says a sync is failing and never says what the provider said; the operator gets that by running the
sync, which is what the advisory tells them to do. A test sweeps every emitted field for a marker
seeded in the error.

**And the fix tripped a guard that exists for exactly this.** Hoisting the shared copy into module
constants put it out of reach of `test_advisory_actionability.py`, which reads advisory text
statically at each construction site and skips what it cannot read — the evasion that test was
written to make impossible rather than merely unlikely. The copy is inlined and duplicated on
purpose, waived and explained; the evidence string stays shared, because that is what makes the two
stalled shapes one thing to dismiss.

The other findings were cheap and all fixed: the drop-box sweep's instruction class is now derived by
**exclusion** from the code roots rather than enumerated (a shipped `agents/` prompt was already
outside the list, and a self-check over a list cannot see what the list omits); the framework
injected-footprint ceiling is ratcheted with the cut that moved its reading, and the
ceiling-is-reading-plus-one invariant is now **asserted** rather than remembered, since the assertion
that already existed watches growth above a ceiling and cannot see one left too high after a trim;
and the cross-cutting-concerns row for untrusted provider content names its fourth consumer, whose
treatment is a different shape from the three prose ones — count-only emission pinned by a
negative-content assertion, not a prose restatement — with the row's "what if a fourth surface
appears" gap restated as observed rather than anticipated.

## 2026-09-08: the intake nudge counts issues, and knows the difference between none and unknown

<!-- prawduct: type=feat | scope=upstream-intake-repoint -->

`untriaged-upstream-reports` counted `.md` files in a gitignored directory nothing writes to. It now
counts what the channel actually produces: open issues on prawduct's own tracker whose title carries
the `[prawduct]` convention and which nobody has staged (upstream-filing design §6). Until this
landed, issue-side triage was manual and the skill said so — a session that drained the drop-box
drained the channel that no longer grows.

**Three constants make the query and the probe spells none of them.** The target and the title
prefix come from `lib/backlog/upstream`, where the filing side composes them, and *untriaged* comes
from `cachequery.unstaged_items`, which already draws the line between an absent stage (nobody
looked) and an early one (somebody did). The two halves of the channel now cannot disagree about who
the receiver is: the same identity resolution that refuses to file *from* here is what agrees to
count *here*.

**Inert by identity, where the predecessor was inert by absence.** No product repo had an
`incoming-bugs/` directory, so the old probe was silent there for free. The intake set offers no such
silence — every post-cutover product has a readable cache holding nothing prefixed — so applicability
is keyed on this repo *being* the pinned upstream target. That buys something the old shape could not
have: in the one repo that does receive, an unreadable cache is reported as **unknown** rather than
as zero. Advice fails soft, and a triage nudge that vanishes when its data source breaks reads
exactly like one that found nothing to say.

**Nothing a filer wrote reaches the reader.** Filed issues are foreign-authored content arriving at
a governance surface, and advisory text lands in the model's context at session start — so the
candidate carries a count and its own fixed prose, and a test seeds a distinctive marker in a
report's title and body and asserts it appears in no emitted field. The security model's *untrusted
governance state is data, not instructions* norm has its first prawduct instance here, and it agrees
with D14's count-independent evidence rather than competing with it.

**The fixture composes the real outbound payload rather than spelling a title.** The intake set
exists only because `file-upstream` sends that title convention and no labels; a fixture that typed
them itself would keep passing after the payload stopped producing them. Filing side and counting
side are now pinned against each other. The probe version bumps to 2, which supersedes a live
drop-box advisory cleanly instead of leaving one asserting a count nothing maintains.

**Review caught two things the first cut got wrong, and one of them was a test that could not fail.**
The no-network assertion counted calls on a locally-built fake the probe never receives — it would
have held for an implementation that shelled out to `gh`, which is the exact false green the file's
own docstring says every case here avoids. The guard now sits on `subprocess` and forbids `gh`
specifically, because the probe legitimately spawns `git rev-parse --git-common-dir` to find the
clone-shared store; the interception is proved before it is relied on. Second, applicability resolved
through the filing side's identity resolver — `backlog_service_repo` **or** the `origin` remote —
while the cache read used the pinned target as its scope. A clone of prawduct whose backlog lives
elsewhere would have passed that gate, read a scope nothing syncs, and nagged every session with an
*unknown* nobody could clear. The gate now keys on the one scalar that selects the store it reads.
The two predicates are deliberately different and the code says why: breadth guards a fail-open in a
refusal, and here the failure runs the other way.

**And the replacement pin was broken in a second, better-hidden way, which the verify round caught.**
Forbidding the detached seam by patching `transport.subprocess.Popen` patches the *global*
`subprocess.Popen` — `transport` does `import subprocess`, so there is no per-module seam there — and
`subprocess.run` reaches `Popen` by module-global lookup, so the fall-through that was supposed to
let `git rev-parse` through raised instead. `git_common_dir` swallows that, the cache path resolves
to `None`, and the probe returns its *degraded* candidate — which an assertion counting candidates
accepts. Green, on the branch the test was written to avoid. The seam is now guarded by name
(`spawn_detached`), and the assertion is on the counted summary, which only the path under test can
produce. Two rounds on one test, and the fix each time was to name what the absence would have to
cross rather than to look at a proxy for it.

The gate and the query also stopped being able to select different stores by *spelling*: GitHub repo
names are case-insensitive so the gate folds case, while the cache keys its cursor and sync-health
row on the spec as declared, so the query passes it verbatim. Pinned as a contract test on the seam,
and the test says why it is one — `item` carries no scope column, so a canonicalized lookup returns
the same count through a fallback today and nothing downstream would go red.

The `prerequisite_of` edge to the backlog migration goes with it: it ordered incoming-bug triage
ahead of a migration that has since shipped, and an ordering constraint whose second term can no
longer fire is a dead edge. The advisory spec keeps the worked example, dated as the derivation —
a rule with its example deleted is a rule nobody can check.

Also corrected, because this chunk falsified them: `CLAUDE.md`'s product-feedback row and the
report-bug skill's receiving-side section (both said the advisory nudges the drop-box), and the two
`bug_inbox` docstrings whose stated retirement condition is now met. The drop-box paragraph now says
plainly that **nothing counts it** — look before assuming it is empty. Its retirement is the next
chunk.

## 2026-09-07: the cumulative round — a shipped preference that did nothing, and a shell that ate titles

<!-- prawduct: type=fix | scope=upstream-report-bug -->

Wave B's cumulative review: 0 blocking, 11 warnings, 3 notes. Thirteen fixed, one accepted.

**`always-file` was inert on its only consumer.** The skill branched on the consent state and
nothing could read it: the preview surfaces `never-file` through a refusal warning and `ask-user` is
what every unreadable path falls back to, but standing consent is inferable from nothing — so a
model asked for approval on every report, which is the one behaviour that preference exists to
remove. The preview now returns and prints the resolved `preference`, and the skill branches on that
line. It rides beside the payload and takes no part in the digest, asserted: moving the preference
must not invalidate an approval given for bytes that did not change.

**The skill's own command shape could mangle an irreversible title.** It reasoned carefully about
the body — write it once, pass `"$(cat …)"`, because retyping causes `approval-mismatch` — and then
passed `--title` and `--component` as double-quoted shell literals, in a step that had just told the
model to write both in prawduct's backticked vocabulary. `` `prawduct-hook version` `` runs; a
symptom naming `$CLAUDE_SKILL_DIR` expands to nothing. The title would be composed, digested,
approved and filed with the defect's own name deleted, into a repo where a non-collaborator cannot
retitle it. All three fields now come from files — on **both** command blocks, which is the half
this round's own review had to come back for.

**A transport failure at create was routed to the one action that makes it worse.** It is not a
refusal — whether the issue was written is unknowable from the caller's side — and the skill folded
it into "file by hand", which turns an ambiguous outcome into a duplicate in a public repo. The
adapter already solves this and the skill named none of it: `source-key` is stable across an
identical re-run and the dedup scan reads newest-first for exactly this window. The instruction is
now to re-run the identical send once, which either files or answers `already filed`.

**Three more the skill got wrong about the adapter.** `self-file` covers two situations, not one —
the second is a product with no `origin` remote, and the skill's "you are in prawduct's own
checkout" sent it to the product-backlog write the same skill forbids. The "mechanically guaranteed"
list promised a byte-match that standing consent waives, on the surface that exists to be honest.
And a successful send can carry `warning:` lines — including "filed without the idempotency check"
— that nothing told the model to relay, so a degraded filing read as a clean one.

**Two carriers of the falsified claim survived the sweep, which is the finding about the sweep.**
`architecture.md`'s Persistence Boundaries row still named `incoming-bugs/` as where products file
today (and called a gitignored directory "tracked"), and `prawduct-hook`'s `cmd_bug_inbox` docstring
still published the exit-code contract of a caller that no longer exists — instructing the local
capture the design forbids. Neither line names `file-upstream`, so the absence guard cannot see
them. Both were carriers of the *claim*, and the claim was cascaded one short.

**The refusal-code list in the skill is now pinned by construction.** It is a justified copy — a
model needs the codes to branch — but nothing kept it in step. The derivation that already reads
`send`'s AST for the preview arm now also asserts the skill names every refusal the preview cannot
predict, with the codes produced by calling the checks rather than typed out. Mutation-checked.

Also: the `never-file` remedy has an assertion on it (the message, not just the code — that
sentence was where submit-or-nothing had a second, contradicting home); the receiving side says
plainly that issue-side triage is manual until Wave C repoints the advisory, and names the intake
query; the PRD's MG5 bullet is marked superseded where the owner-approved design overrode it rather
than rewritten in place; and the owner-boundary row in `cross-cutting-concerns.md` gains this
bundle's two legs.

**The round's own review came back blocking, on the half of its own fix that did not land.** R-2
named two command blocks and the fix landed in one — step 5 kept its shell literals, two screens
after step 2 explained why they are unsafe, and this entry asserted the job was done. Under standing
consent the digest comparison is waived, so a title mangled there is filed rather than refused.
Both blocks now read from files, and a guard asserts it over **every** line of the skill rather than
the one that was wrong: `test_no_command_block_passes_a_composed_field_as_a_shell_literal`,
mutation-checked. The same round's milder carrier of the approval claim (the intro's unqualified
"what was approved is what is sent") is qualified too, and two assertions that had drifted into the
neighbouring test are back where their name says they belong.

**The verification round's own observation was dismissed on a false premise, and the check is
cheap.** It rated widening the new guard to `--body` as not worth a commit because "the body is
separately pinned by the digest". It is not: preview and send expand identically, so a mangled body
previews and sends as the same bytes, the digests agree, and the check passes on content nobody
wrote. `--body` is in the class for exactly the reason `--title` is, and the guard now covers it —
mutation-checked, with the mutation asserted applied first, after an earlier check on this same
guard passed only because its edit had silently failed to match.

Accepted, not fixed: the backlog-reconciliation note. It names no work owed here — #194 closes at
Wave C, and #234 is the lockstep guard whose replacement is now live and whose retirement is Wave C.

## 2026-09-07: `/prawduct:report-bug` stops writing a file on one machine and files an issue

<!-- prawduct: type=feature | scope=upstream-report-bug -->

Wave B, Chunk 02 of BKL-7Q4M. The skill is rewritten onto `file-upstream`: recompose the report in
prawduct's terms, preview the exact outbound payload, show a human those bytes, send on their
approval of the digest. Wave A built that data plane and nothing called it; this is the caller.

**Three things the old skill did that it must not do any more.** It resolved a machine-local
drop-box and wrote a file there — a report visible to one developer on one machine. It captured the
bug in the *product's* backlog when no channel was reachable, which is the local capture design §5
forbids by name: an upstream bug parked in a product's backlog reaches nobody who could fix it. And
it composed the `Found in:` version itself; the adapter now sources that from the running manifest,
so it is right on every filing rather than on a careful one.

**Submit-or-nothing has a second, quieter home that contradicted it.** `check_preference`'s
`never-file` refusal told the caller to "report this bug in your own backlog" — the exact fallback
the design removes, in the message a caller reads at the moment of decision. It now points at the
tracker. Found by walking the rewritten skill against the fake transport rather than by reading:
the refusal text is not something the skill's own prose could contradict visibly.

**The drop-box template is a trap while it survives, so it now says so.** `incoming-bugs/` and its
report template retire with Wave C, in lockstep with the advisory repoint — but three of that
template's fields (`Reporter`, "used from the `<product>` repo", a `## Context` section asking for
the host repo's particulars) are exactly what must not cross an owner boundary. They were safe when
the report stayed on one machine. A banner now says it is the drop-box shape, that nothing writes
it, and where the upstream payload is actually specified.

**Two mechanical assertions carry §7's lockstep from the replacement's side**
(`tests/preferences/test_no_upstream_content_egress.py`): the skill drives both arms of the op, and
it names no drop-box write machinery. Both mutation-checked. What is deliberately *not* asserted
mechanically — that the report carries no product content, that a human read the bytes, that a
blocked filing captures nothing — is judgment about prose, and a grep for it would pass on any text
with the right words in it. Those stay the Critic's.

**A pending operator verification, and an honest reason it is pending.** VRF-018 is design §9's
`[XP6 verify]`: what a non-collaborator can actually set on an issue they file. It needs a GitHub
account that is not a collaborator on this repo, and the owner is one — a lead-time item no session
can shorten. It gates the release rather than the build, because the payload is already label-less
and no answer changes a byte that gets sent; what it gates is Wave C's intake query, which is only
correct if a non-collaborator genuinely cannot apply a label.

**A declared token raise, not a trim.** The session digest and this repo's `CLAUDE.md` each carried
a sentence this commit made false — the digest said the channel "is inert when neither is
configured", which is a reason not to reach for a skill that now works. Correcting both costs +10
tokens on every governed session and +21 on a framework one. There was no duplication left between
those two files to pay it from, and the standing rule's other branch — trim whichever clause is
least defended — is how a correction gets funded by deleting something nobody was watching. So it
is declared, with the arithmetic and the character-budget check on the record.

Also: `bug_inbox.py`'s docstring no longer calls itself the report-bug channel, `adapter-mode.md`
no longer says the skill has not been rewritten, and `project-structure.md`'s tree line no longer
describes `incoming-bugs/` as where products file today.

## 2026-09-07: the consent preference becomes a row somebody can write

<!-- prawduct: type=feature | scope=upstream-report-bug -->

Wave B, Chunk 01 of BKL-7Q4M. The `Upstream filing` preference has been readable since Wave A and
authorable nowhere: `read_filing_preference` handles all three of design §4.1's states, and the only
one production could reach was the absent-file default. `templates/project-preferences.md` now ships
the row, so `init-product` writes it into every product it scaffolds, and `never-file` — the one
state §4.3 calls a hard mechanical guarantee — is now reachable by editing a line instead of by
writing a test fixture.

**The shipped row reads as `ask-user`, which is also what its absence reads as.** Two spellings of
one default, deliberately: an operator who deletes the row changes nothing, and the direction that
would cost something — a row landing on `always-file` — cannot be reached by deleting anything.

**This repo's own row stays at the default rather than `never-file`, and that is a decision.**
Prawduct is the pinned upstream target, so `file-upstream` refuses here on the no-self-file check
whatever the row says. Setting `never-file` would only *shadow* that refusal, because `send()`
consults the preference first — and `self-file` is the better diagnostic, since it names the remedy
(file it with `/prawduct:backlog add`). The mechanical guarantee is identical either way; only what
a developer in this checkout reads changes.

**The new test reads the shipped artifacts, not a fixture.** Both real inputs are pinned against the
reader: the template `init-product` copies, and this repo's own authored row. The second asserts only
that the row still *parses* — which state it names is the owner's to change, and a test asserting a
particular value would quietly turn a preference into a rule.

**The Local-first surface-vs-site clarification is ratified** (`architecture.md` § Direction). It was
recorded 2026-09-07 flagged for owner veto because the builder wrote it while the amendment it sits
under was the owner's; the veto was offered and withheld. Reverting it is now an ordinary amendment.

Also: three comments that anchored to a chunk number or to Wave B's tense — a chunk id names no plan
and renumbers, and "authored in Wave B" stopped being true in this commit.

## 2026-09-07: the review round that bought the merge — one blocking claim retracted

<!-- prawduct: type=fix | scope=upstream-filing-adapter -->

Round 10, spent on the one justification the coverage gate names: a merge. Six findings fixed.

**The blocking one was a guarantee the docs claimed and the code does not make.** A reconciliation
paragraph in `backlog-service-security-model.md` §1a had grown into asserting that the approval token
is *the mechanism* closing unattended cross-owner filing — which reverses the owner's dated §4.3
ruling (2026-07-23) that the gate is byte-pinned with an **honest limit** and does not detect a human.
The code sides with §4.3: nothing on the send path consults `context.is_unattended()`, and this
bundle's own test files with `--approve sha256:whatever` from a repo with no human in the call. §1a
now states the mechanical floor (a token is required in every preference state; `ask-user` is the
reachable default; `never-file` is the one hard guarantee) and names what is *not* mechanical — the
`report-bug` skill's obligation. XP4's honesty MUST is why this was a block and not a wording nit.

**A guard whose only test failed for the wrong reason.** `file-upstream`'s SEC-5 withhold was held in
place solely by a partition test whose failure text is about the counts cache — so dropping the op
from `_WRITE_OPS` had a suggested "fix" (delete a cache-map row) that re-opens the send arm under a
pwn-request trigger with the suite green. It now has a send-arm test that reads the seam, verified by
mutation.

**One framing outlived its norm in six places.** "Network reachability is keyed on
`backlog_service_repo`" was true until the same-day Local-first amendment and was copied into
`architecture.md` (twice), `project-preferences.md` (twice, including a norm citation one amendment
behind), `project-state.yaml` and `security-model.md`. All six now rest on the property that actually
holds — nothing reaches the network unless a person acts — since `file-upstream` reaches the pinned
upstream repo with that scalar unset.

**The Local-first statement now distinguishes a *surface* from an egress *site*.** The count of two
binds on paths by which product content leaves a product; the larger enumeration of sites (including
`cmd_stop`'s `gh pr list`, which does run on the Stop hook) keeps its single home. This states what
the count already meant and admits nothing new — flagged for owner veto, since the statement it
clarifies was amended by owner ruling the same day.

Also: XP-1's spec no longer requires the outbound payload to carry the `source:` + submitter pair the
minimization exists to strip, and `file-upstream` gets its own `### file-upstream` block in
`adapter-mode.md` instead of 1,400 characters buried in the write-discipline preamble.

## 2026-09-07: the egress norm reaches steady-state, and every live surface describes the contract

<!-- prawduct: type=feature | scope=upstream-filing-adapter -->

Wave A, Chunk 03 of BKL-7Q4M — the records half, no module changes. The owner ruled the plan's open
Local-first question **(a) amend**, which was this chunk's blocking input.

**The egress norm is amended `in-transition` → `steady-state`** (`security-model.md` § Direction).
The statement no longer says the upstream bug channel is filesystem-local — it says content leaves
only through a surface the plugin pins and the owner approves against the exact outbound bytes.
Amended toward the guarantee: the interim `Mechanism:` was a token scan asserting the surface did not
exist, and an absence proves nothing once one does; what replaces it is five checks that each refuse
independently and file nothing. Same file, same enforcement row — the mechanism was replaced in
place, so nothing moved house. The statement's third sentence is untouched, so the next cross-owner
surface is still a fresh owner decision and inherits no permission from this one.

**The Local-first norm admits a second network surface** (`architecture.md` § Direction), recorded as
a vetoable `[DECISION: …]`. Its prior scope sentence — "confined to backlog storage" — was literally
broken by `file-upstream`, which targets the plugin's pinned repo rather than the product's own and
is reachable with `backlog_service_repo` unset. The rejected alternative (gate the op on that scalar)
reads as the smaller change and is not: it re-introduces the `backlog_service_repo`-keyed fail-open
the filing design's own check-3 amendment removed. The `Why:` is repaired to rest on the guarantee
that actually holds — neither surface is reached without a person acting.

**`data-model.md` § Direction's title norm now says four write paths, not three**, with the ruling
recorded on the entry: `file-upstream`'s send arm refuses a non-conforming title, its preview arm
reports advisorily, and the upstream title convention takes the budget and placeholder rules but not
the area-prefix expectation. The code already conformed; the norm's text was describing the world
before the path existed.

**Coherence, all named by the design's §8:** api-contract §2.4 gains the two-call preview/`--approve`
contract and the five-check refusal set, and its error vocabulary gains `filing-disabled`,
`target-not-pinned`, `self-file` and `approval-mismatch`; the design security-model §1a gains the
attended-by-construction reconciliation (standing consent waives the digest comparison, never the
token, so an unattended call refuses) and §5 the trimmed-block one (minimization protects the sender
and says nothing about what a receiver may trust); design data-model §5's `source-key:` gains the
trimmed-block note and its digest inputs corrected to what the code computes; `project-state.yaml`'s
`egress_boundary` keeps its count of three and stops describing site 1 as only the backlog backend;
the preferences enforcement row stops citing the retired interim rule; and the PRD's "ships with the
migration" line becomes "is built", with the general cross-owner case still fenced to W3.

**Two claims that went stale at Chunk 01 are corrected, and one deliberately is not.**
`skills/backlog/SKILL.md` said an adapter-side pin existed "only in the design"; it is built, and the
sentence now says so while keeping its real warning intact — no migration path reaches a line of it.
`IMPLEMENTED_ADAPTER_GUARDS` **does not gain `target-pin`**, against the plan's expectation: the
mechanism narrowed rather than arrived. `upstream.py` does compare repo identity, but only for
`file-upstream`; `import`/`file`/`update` still reach none of it, so backing the name would let a
migration surface cite a safety net that does not cover it — this file's own defect, one op over.

**The wave's cumulative review found six things worth fixing, four of them in Chunk 02's code.**
0 blocking; these were warnings, and they were fixed rather than accepted because each is real and
the wave ships as one PR.

- **A well-formed `prawduct` fence in `--body` crossed upstream intact.** `encode.check_body_text`
  tolerates a *terminated* block on purpose — every in-repo caller pairs it with
  `encode.compose_body`, which strips and merges the paste, so guard and transform are one
  mechanism. `upstream.render_report` appends the body verbatim, so the guard was ported without
  the transform and a terminated fence arrived as a second parseable block carrying the `source:`
  field minimization exists to strip; the receiving side's first `merge_all_block_fields` would
  fold it into the canonical block permanently. Closed with `encode.check_body_text_strict` — no
  tolerance on the path that has no composer — and the escape the message names (indent the fence)
  is now pinned by a test asserting against the **parser**, not a substring count.
- **The `source-key:` dedup scan walked the whole tracker on every first-time filing.** Newest-first
  was costed for the retry, which is the rare case; a fresh report matches nothing and paid for the
  entire history, growing forever. Bounded to a 3-page window — and bounding it surfaced that the
  shared paginator *raises* at its cap by design, so a bare cap would have turned every first filing
  into a phantom transport failure. `transport.paginate` therefore gains `on_cap="stop"`, opt-in at
  the call site, with the loud default untouched and an unreadable page still raising under both.
- **The preview could not say which lint findings would refuse the send.** It hand-enumerated the
  refusals it could predict, so Chunk 02's title refusal never joined the list and reached the
  operator as an ordinary `lint:` line beside body budgets that never block. Replaced with one named
  set, `upstream.previewable_refusals`, plus a test that reads the send arm's own source so a sixth
  refusal cannot be added to one arm only.
- **`adapter-mode.md`'s refusal set read exhaustive and omitted the title refusal.**
- **`source-key:` is a confirmation oracle, and the design overclaimed.** Title and body are
  published verbatim beside the digest, so the submitter repo is the only unknown and is guessable
  by recomputation. The claim is corrected in place; the mechanism is not, and the reason is
  structural rather than an oversight — a keyed digest needs a per-submitter secret and the adapter
  deliberately manages none, so closing it means introducing secret storage. Filed rather than
  dropped.
- **Chunk 02's live-repo self-file criterion had no test.** Every case synthesized an identity under
  `tmp_path`, so the one configuration a maintainer is actually in went unexercised. Now asserted
  against the real checkout.

**Round 8 — the first review that actually covered this chunk — found eight more, two of them
defects this chunk introduced.** 0 blocking again; fixed for the same reason.

- **An unreadable `project-preferences.md` demoted `never-file` to `ask-user`.** §4.3 calls
  `never-file` a hard mechanical guarantee, and the fail-open left it enforced by the operator
  reading a warning that, on the send arm, rides out on the **success** envelope after the
  irreversible write. `read_filing_preference` now returns a distinct `PREF_UNREADABLE` that
  `check_preference` refuses. The absent-file and unrecognised-value branches keep their `ask-user`
  default deliberately: those establish that the row does not say `never-file`, and an unreadable
  file establishes nothing. The pre-existing test had asserted the fail-open its own docstring
  argued against.
- **The absence guard could not see the two surfaces it was written for.** `LIVE_SURFACES` omitted
  `skills/backlog/SKILL.md` — the instance named in the guard's own docstring — so re-introducing
  that exact sentence passed green. Both instruction surfaces added; the guard was re-falsified
  against the real regressed sentence rather than a paraphrase.
- **The dedup bound was applied to the mechanism and not to the claim.** Three prose sites still
  promised absolute retry-collapse after the scan became a window — the cascade-search-the-CLAIM
  failure `learnings.md` already names, since prose describing old behaviour shares no token with
  the code that changed. The guarantee is now relational at its home (api-contract §2.4), cited
  rather than restated elsewhere, and **pinned against `upstream.DEDUP_SCAN_PAGES`** so the next
  change to the window cannot strand the sentence. A fourth site outside the diff
  (`backlog-service-test-specifications.md`) is corrected too — it is what a future test is written
  from.
- **The `previewable_refusals` pin was the enumeration it claimed to replace** — it read the send
  arm's source only to confirm three remembered names. Now AST-derived, with exclusions carrying
  their reasons. The derivation immediately surfaced a call the hardcoded list had missed.
- **`paginate` refuses an unknown `on_cap`** rather than falling through to the safe default: a
  caller who typed `"Stop"` wanting a window would otherwise get an unexplained truncation.
- The design doc's governance header quoted the norm it governs, so the quotation outlived the
  amendment and contradicted §8 of its own file — now a citation by name, which the next amendment
  cannot strand. Its Call-2 snippet also omitted the `--title`/`--body` the shipped op requires.
- The title-refusal write-path enumerations in `cli.py` and `issuefmt.py` are relational; the
  `LintFinding` docstring now says to grep for the refusal sites rather than trusting a roster,
  because a roster there is what a maintainer greps *instead of* the code.

**Two findings declined on the evidence, not deferred.** `.prawduct/backlog.md` carries the retired
norm quotation, and its own header declares it FROZEN HISTORY, "deliberately allowed to diverge —
read as a snapshot of the moment of migration, never as live state"; correcting it is the one edit
that file exists to forbid. And `paginate`'s unreadable-page branch is unreachable through
`GhTransport`, which coerces a non-list to `[]` first — making it reachable would mean adding a
failure mode to enable a test for it.

**A Chunk 02 corpus defect surfaced here and is fixed rather than deferred.** `933cb290` added the
"Defence in depth costs a test PER LAYER" narrative to `learnings-detail.md` with a heading whose
casing did not prefix the index rule, so `check-learnings-pairing` had been red since that commit —
the detail was reachable only by grep while every lookup paid to read it. The heading is realigned,
per the finding's own prescribed remedy. It went unnoticed because the run that pronounced Chunk 02
green was read off a pipeline, so it reported `tail`'s exit rather than pytest's; that is now a
`learnings.md` rule, since the same mistake was repeated at this chunk's own baseline.

**A new guard replaces the grep the acceptance criteria asked for:** a live governing surface may no
longer describe `file-upstream` as unbuilt or deferred. Dated records are exempt by construction —
a line must carry a date *and* a record marker — and the exemption is exercised by the norm's own
birth-time inventory rather than by an exemption list that would grow until it meant nothing. Both
legs falsified before being trusted: the guard fires on an injected claim, and the record path is
reached by a real line.

## 2026-09-06: the `file-upstream` send path refuses on all five checks, and identity fails closed

<!-- prawduct: type=feature | scope=upstream-filing-adapter -->

Wave A, Chunk 02 of BKL-7Q4M, closing `#329` (BKL-4T9C). `file-upstream --approve sha256:<digest>`
sends, and refuses unless all five design §5 checks hold — each a distinct code, and every one of
them files nothing: `filing-disabled`, `target-not-pinned`, `self-file`, `approval-mismatch`, `auth`.
Chunk 01 shipped the two-signal identity resolver; this ships the check that consumes it, which is
what closes the fail-open the item describes.

**Check 3 is the one with the amendment, and the fail-closed leg is the one a naive implementation
gets backwards.** Identity resolves from **both** `backlog_service_repo` and the `origin` remote,
either match refuses, and an identity that resolves from *neither* refuses too — "we could not tell"
is a refusal, not a pass. The refusal **routes** rather than merely erroring: XP7 reads "never let
prawduct's own repo self-file upstream *(it routes to its own backlog)*", so the message names
`prawduct-hook backlog file` and the test asserts that on the prose a human reads, not only on the
code. The invariant behind the routing is worth keeping: this op's whole ceremony — recomposition,
verbatim review, digest approval, the visible-word ceiling — exists because content crosses an
*owner* boundary, and prawduct→prawduct crosses none, so minimizing prawduct's own bug reports would
lose fidelity to protect prawduct from prawduct.

**The send arm refuses a non-conforming title; the preview still only reports one.** `data-model.md`
§ Direction binds the issue standard's §1 title rules on **every** adapter write path and names
`file`/`update`/`import` — because `file-upstream` is the fourth and nobody had noticed. It binds
harder upstream: the write is irreversible and a non-collaborator filer cannot retitle afterwards.
The preview stays advisory because nothing is written there, and an advisory finding is exactly what
lets an author fix a title *before* approving it. The **rendered** title is what is linted, since
that is the string that lands; `[prawduct] <component>:` is not §1's `area: summary`, so `_split_area`
reads it as no prefix and the budget, placeholder and atomicity rules are what remain.

**`--approve` is the send trigger in every preference state; `always-file` waives only its value.**
Design §4.1 says standing consent "files directly (no per-report digest)" and §5 waives check 4
there, which left open whether a bare preview call *sends* under `always-file`. It does not: the
token is the only thing separating rendering a payload from filing one, and a caller that previews
must not discover it filed. So the presence of `--approve` is required always — an empty token is
refused — and under `always-file` its value is simply not compared. Recorded as a decision because
the design admits the other reading.

**Every refusal carries the advisory payload the success envelope carries.** The payload is composed
*before* the checks run, so `lint` findings and preference warnings ride out on all five refusals as
well as on the ok envelope, and the human-mode error branch prints them — `core.error` is a
different constructor from `core.ok` with no slot for either, which is how this repo has twice
shipped a field that vanished on the failure path. A refused filing is precisely the moment an
author is about to edit the report, so the findings are worth more there than on the success.

**Idempotency reads the list endpoint, and degrades rather than blocks.** The api-contract §2.4
`source-key:` marker makes a re-file return the existing issue instead of duplicating it; the lookup
scans issues newest-first for the marker rather than asking GitHub's search API, because the key
exists for retry safety and search is not read-your-writes — blind exactly in the seconds after a
create, which is the case that matters. A lookup that *cannot run* files anyway with a loud warning:
XP7 is submit-or-nothing and names a slow flow as what turns "submit" into "nothing", and the cost of
proceeding is a duplicate a maintainer can close. The five checks are the guarantees, and none of
them runs through that path.

**The review caught the one thing every test was blind to: the send arm never resolved a transport.**
`_run_file_upstream` was the only transport-consuming handler in `cli.py` that did not call
`_resolve_transport`, and production enters through `run(project_dir, argv)` with no transport — so
`None` reached `send`, died on `None.get_authenticated_user()`, and the CLI-boundary catch reported
the whole op as a retryable `unavailable`. Every send test injected a fake, which is exactly why the
suite was green over a deliverable that could not file at all. Resolution now happens **inside the
send branch**, not at the top of the handler where its seventeen siblings put it: at the top it would
construct a `GhTransport` on the preview path and dissolve the "the preview arm is handed no
transport" guarantee. Both halves are pinned by tests that drive `cli.run` with no transport at all.

Check 2 was likewise the one of five with no send-arm test — the CLI's pre-check short-circuits every
call routed through `cli.run`, so `send`'s own `check_target` leg was a mutation survivor. It now has
a class like the other four, plus one that asks `upstream.send` directly.

All five checks are mutation-verified — neutering each fails its own class and nothing else — as are
the title refusal, the advisory carry-through, the dedup lookup, and both halves of the transport
wiring. Two warnings landed in the same pass: an unreadable (as opposed to absent)
`project-preferences.md` now warns rather than silently downgrading a `never-file` standing no, and
the preview warns on `filing-disabled` as it already did on `self-file`, so nobody reviews bytes and
approves a digest for a send that was never going to happen. `--approve` had to be added to
`_VALUED_FLAG_NAMES`; the union guard caught it, which is the guard working. `transport.py` and
`tests/fakes/fake_github.py` were listed as deliverables and needed no change: `create_issue` and
`list_issues` are the seam already, and the fake is keyed per repo, so the pinned target is just
another repo to it.

## 2026-09-06: `file-upstream` previews the bytes that would cross the owner boundary

<!-- prawduct: type=feature | scope=upstream-filing-adapter -->

Wave A, Chunk 01 of BKL-7Q4M. The adapter gains one operation that writes into a **foreign, public**
repo — prawduct's own tracker — and this chunk lands only the half that sends nothing: the pinned
target, the exact outbound payload, its digest, and the contract test that replaces the interim
egress guard. Design: `documentation/backlog-service-upstream-filing.md` §2 and §5.

**The interim test and the surface it forbade had to land in one commit.**
`tests/preferences/test_no_upstream_content_egress.py` asserted that the token `file-upstream`
appears on no shipped surface and that `brookstalley/prawduct` appears nowhere in the backlog
adapter. Design §5 check 2 requires the pinned target to be a plugin constant *inside* the adapter,
so the keystone violates both assertions the moment it exists. The design's "the interim test stays
live until the contract test lands" is therefore a same-commit constraint rather than a chunk
ordering: splitting them leaves the suite red for the whole wave, and a red suite is what the
release gate reads. The file keeps its name and its enforcement-row identity in
`project-preferences.md`, and is rewritten to assert the contract. The swap is a strengthening,
which is the only direction the § Direction norm permits — an absence proves nothing about a
surface once the surface exists.

**Two of the five §5 checks are live; three land with the send path.** Asserted now: the target is
pinned (a `--repo` that disagrees is refused with `target-not-pinned`, and one that agrees changes
no rendered byte), and nothing files without an approval. The second is structural rather than
conditional — the handler takes no `transport` argument at all, so a preview cannot reach the seam
whatever a later edit does to its body. Both were mutation-checked: breaking the pin, and wiring the
handler to the seam, each fail the contract test. A contract test that cannot fail is the
vacuous-pass class this repo has already paid for.

**`source-key:` needs the running repo's identity, so the two-signal resolver landed here rather
than with check 3.** The api-contract §2.4 idempotency key digests *(submitter identity, title +
body)*, and the submitter is the filing repo — resolved from **both** `backlog_service_repo` and the
`origin` remote, because either alone is fail-open in the state that matters most
(`backlog_service_repo` is unset in every pre-cutover repo). Chunk 02's no-self-file check consumes
this resolver rather than writing a second one. Identity crosses the boundary only as an input to a
one-way digest; a GitLab or Enterprise `origin` resolves as no signal, which is the fail-closed
direction. The remote is read out of `.git/config` rather than by shelling out to `git remote
get-url`: `lib/backlog/`'s egress discipline gives `transport.py` the package's only subprocess, and
that invariant is what makes "the adapter reaches out in exactly one place" checkable — not worth
spending on a value sitting in a config file. The linked-worktree form (a `.git` *file* whose gitdir
names a shared `commondir`) is resolved too, because reading only the plain case would leave every
agent worktree with no identity signal, and a fail-closed check with no signal is a refusal nobody
can explain.

The remote URL is matched as a **host**, not searched for as a substring, and the difference is
reachable twice over: a prefix guard alone still accepts `https://evil.example.com/github.com/o/r`,
where `github.com` sits in the *path* of a host the caller chose. The pattern is anchored over the
whole URL — optional scheme, optional userinfo, then the host and nothing before it — and the test
asks the property (no URL that merely *contains* the host resolves) rather than pinning two
spellings. Git's config case-folding is honored on both halves of its own rule: case-insensitive on
the `remote` section name and the `url` key, exact on the `"origin"` subsection, because handling
only one half leaves a valid config silently yielding no identity at all.

**What the payload is, exactly.** `[prawduct] <component>: <symptom>`, the two sourced sections
(**Component**, **Found in**) ahead of the caller's L1-recomposed prose, and a `prawduct:` block
trimmed to `v:`, `found_in:` and `source-key:`. The in-repo block's `provenance: {source: <product>}`
is the product-name leak the trim exists to prevent, and it is absent by construction: the block is
composed from three values with no path to a fourth. `found_in:` is read from the plugin manifest at
call time and degrades to `(unknown)` on any unreadable manifest — never recalled, because a
recalled version drifts silently as the plugin updates and sends triage to the wrong code. A body
that opens an unterminated ```` ```prawduct ```` fence is refused, closing the same forgery route
`file` already closes on its own body.

**`--component` could forge the whole provenance block, and the guarding test could not see it.**
The CLI ran the fence guard on `--body` alone; `--component` was interpolated verbatim into the body
*ahead of* the marker, and `.strip()` removes surrounding whitespace, not an embedded newline. A
component of ``stop-hook\n```prawduct\nsource: acme/widget`` put `source: acme/widget` — the
product-name field the trim exists to strip — at the head of the parsed block, with the genuine
`v:`/`found_in:`/`source-key:` swallowed inside it, irreversibly, on a public tracker. The test that
should have caught it sliced the body with `rindex("```prawduct")`, so it inspected only the *last*
opener while the parser reads from the *first*: it reported a clean marker on a forged body. It now
asserts the fence appears exactly once and scans from the first.

The guard moved into `upstream.check_payload_inputs` — every caller-supplied string that lands in
the body, checked in the module that owns the bytes — and `build_payload` re-runs it and returns
`None` rather than documenting it as a precondition, because a precondition a caller can skip is
exactly what let this through. Title and component must also be single lines: both are structural
fields of the §2 convention, and forbidding the newline is strictly narrower than policing what a
value could spell once it reaches column 0. The shipped docstring claiming the block had "no path
that could reach a fourth field" was corrected — composing three fields does not guarantee three
arrive.

Three more from the same review. Owner/repo names now compare **case-insensitively**, as GitHub's
do: a case-sensitive compare produces divergent `source-key`s today and is fail-open in Chunk 02's
no-self-file check tomorrow, on an input the caller picks. Preview and send now compose through one
`upstream.render_preview`, because check 4 re-renders to validate `--approve` and two spellings of
that recipe would make every `ask-user` filing refuse with `approval-mismatch` — reading to the
operator as their own mistake. And a preview run *inside* the pinned target now warns that filing
would refuse with `self-file` and names the in-repo `file` route: handing over an approval digest
for a send that can only refuse is not a preview, it is a trap.

**Adding the op silently widened a permission grant, and that is now a rule rather than a fix.** The
backlog skill is model-invocable and granted `Bash(prawduct-hook backlog file*)` no-prompt. A Bash
grant is a prefix match, so the attached star — the house form, adopted because it covers the bare
call and every argument form at once — also conferred `file-upstream` the moment the op existed,
with every grant test green. The `file` grant is narrowed to `file --*` (no legitimate call is lost:
a bare `backlog file` is a validation error, and `--help` still matches), `file-upstream` joins
`IRREVERSIBLE_OPS` so the rail binds every model-invocable skill rather than this one, and a new
test asks the general question — no everyday-op grant may reach any *other* dispatched op — so the
next op named `list-…` or `sync-…` cannot reopen it. All three checks were mutation-verified against
the restored wildcard.

The payload is pinned **byte for byte** against a fixture rather than by shape. "Sent == previewed"
is the guarantee the digest exists to make, and a shape assertion passes unchanged while the bytes
drift underneath it. The digest covers the whole payload including the target, so a payload approved
for prawduct's tracker cannot be sent to a repo the reviewer never saw.

## 2026-09-02: four small backlog-adapter items, and two plans falsified by reading the code

<!-- prawduct: type=fix | scope=small-batch-2026-09-02 -->

Four S-sized items on one branch under one cumulative review. Three shipped as planned; **two of
the four had their premise falsified by reading the code before building**, which is the result
worth recording — in both cases the plan would have been buildable, passed its tests, and been
wrong.

**`#N` and a bare number now resolve (Chunk 01).** `normalize_id` accepted four ID spellings, none
of them the number an operator reads off a GitHub URL. `322` fell through every form to
"unrecognized ID spelling"; `#322` reached the short-form branch with an empty left side and
reported `malformed repo in '#322'`, naming a defect the input does not contain. A `default_repo`
is now threaded through `normalize_id`, and `cachequery.resolve` derives it from the store's own
`scope` — one derivation every caller inherits, rather than one each caller can forget. (The plan
had sited this at a `cli.py` call site; it shipped inside `cachequery.resolve` instead, and `cli.py`
is untouched by that chunk.) The previous session hand-spelled `prawduct#N` through an entire triage
pass to work around this.

A follow-up commit closed the other half of the same invariant, and it is recorded here because
nothing else states it outside code comments. `_build` now re-renders the number from
`int(number)`, so `#007` and `#7` — one issue — reach one canonical string instead of two, and
`_NUMBER` narrowed from `\d` to `[0-9]`, so non-ASCII decimal digits are a validation error rather
than a canonical id GitHub cannot resolve. Both restore the already-ratified ID-1 invariant rather
than minting a norm, and both are now stated in API contract §3/§8 and pinned by ID-1's setup.
`parse_provider_alias` requires `nid.canonical == ref.strip()` and therefore stops accepting a
padded stored alias — an intended consequence of one canonical form per item.

**A discarded block edit is reported instead of swallowed (Chunk 02) — and the planned fix was
descoped as wrong.** The plan inherited "mirror the three clearing flags, add `--superseded-by`"
from a handoff. `core.py`'s `_UPDATE_BLOCK` comment records `superseded_by` as *deliberately* not
writable — owned by link/unlink and merge, whose invariants (edge symmetry, redirect) a bare field
write would bypass. So the flag would have punched through a recorded invariant to settle an
ergonomics complaint. What the handoff had actually found was two problems, not one: a **silent
failure**, fixed here — `update --body` with a block line stripped returned `ok`, silently
re-serialized the field, and said nothing — and a **missing inverse for `merge`**, filed as `#751`
because it needs an `unmerge` that owns the invariant the way `merge` does. Only a *pasted* block
is reported; a body with no block at all cannot distinguish "I deleted it" from "I never included
it", so it stays silent rather than guessing.

**Quarantine ⊂ untriaged — both names stay (Chunk 03).** `#544` held that `list --untriaged` and
the anonymous-filing **quarantine** surface were one query under two names, forked across four
documents. They are not. Quarantine is defined by AUTHOR (Security §6/F7 — a *non-collaborator's*
unlabeled filing); `--untriaged` selects on LABEL alone, returning every unlabeled issue whoever
filed it, because no author or collaborator predicate exists on that path in `query.py`. Quarantine
is a strict subset presently served by its superset. Collapsing to one name would have deleted the
author boundary that makes quarantine a security concept rather than a hygiene one, so the
containment is stated on all four surfaces instead, the security model marks its own query
*specified, not yet implemented*, and the unbuilt predicate is filed as `#752`. The direction is
worth keeping: the standing query over-includes, so no anonymous filing is missed — a precision
gap, not a hole.

**A failing cache warm now leaves a durable record (Chunk 04).** `#625`.
`briefing._spawn_cache_warm` spawns the session-start sync detached with stderr to `DEVNULL`, and
only a *successful* sync stamps `coverage_confirmed_at` — so every `log_diag` on that path wrote
into a black hole and a warm that failed once was indistinguishable from one failing for a week.
`last_attempt_at` / `last_error` join the `cursor` table (SCHEMA_VERSION 7→8; a v7 store discards
and rebuilds, losing nothing), recorded at the sync boundary and surfaced under the age in human
mode. Three decisions are recorded on the chunk: record only against an **existing** cursor row
(row existence is what `cursor_scopes` reads as "ever synced", so minting one would make a
never-synced scope claim it had synced — and cold start is already covered by exit 6), record on
**both** sync exit paths, and put the stamp at the **sync boundary, not in the CLI**.

**Two defects the Critic caught, both in the same chunk.** R-1: a test written to prove an auth
failure takes the *raising* path raised `TransportError` with one argument where `__init__` takes
two, so a `TypeError` escaped, the test drove the exception branch, and the envelope branch it
existed to cover had **zero coverage while passing**. The rationale was backwards — `_revalidate`
catches `TransportError` and returns `from_transport_error(exc)`, so an auth failure is an
envelope. R-6/R-2: the health stamps were written by `cli._run_sync` alone while
`confirm_coverage` is written inside `sync`, so `pick`'s revalidating sync and the post-import warm
advanced the coverage stamp without clearing the failure beside it — a stale `SYNC FAILING` banner
outliving the sync that fixed it, printed under a newer `synced_at`. Two facts that must move
together now live at one seam.

`#609` was considered and dropped: its blocker (`constraints.txt` on the unmerged
`feature/upstream-dependency-policy`) was re-verified live and still holds.

Cumulative `rev-20260902T125809Z-fa56d43b` raised 3 blocking + 6 warnings;
`verify-resolutions` (`rev-20260902T133055Z-7f00a9b9`) confirmed all nine resolved, re-deriving
R-6's caller search independently rather than taking the fix on trust.

## 2026-09-01: backlog burndown — 57 items across ten parallel work groups

<!-- prawduct: type=feat | scope=backlog-burndown-2026-09 -->

A parallel burndown over the 202-item open backlog. One triage agent scrubbed and grouped; nine
implementation agents ran in isolated worktrees on mechanically-disjoint file sets (every path in
`git ls-files` tested against all nine ownership allowlists — zero paths matched two groups); the
integrating session held the branch, resolved conflicts and owned every full-suite run.

**Backlog: 202 → ~129 open.** 16 closed by triage (12 verified already-shipped with a file:line or
commit citation, 1 dropped, 3 merged as duplicates), the rest implemented here.

**The urgent one.** `#737` — `ac6bbb8b` had written five live `Stopgap:` fields into Direction
entries (the entry directly below this one) while `norm_probes.py` could not read the field: five
silent departures behind a clock nothing would fire. The probe now parses it, verified against
those five real entries rather than a fixture. Its twin `#738` found the norm-lifecycle silence
test resolved **0 of this repo's 47 norm citations** in CI and passed anyway — a test that could
not fail is what let `#737` sit.

**Salvage.** Nine branches were archived as tags earlier the same day with the note "intent captured
in the backlog." The intent was; the implementations were not — ~11,000 lines of already-reviewed
work. Two were recovered by owner decision: `#555`, and `#550`+`#564` (29 conflict hunks resolved by
hand, composing with develop's newer field handling rather than replacing it). The salvaged tests
caught a live defect: `cli._VALUED_FLAG_NAMES` omitted three new flags, so `--refs <value>` read its
value as a global flag. `--reviewed`/`mark_reviewed` was deliberately **not** salvaged — `#550`'s own
2026-08-07 scope reshape declares `reviewed` out, so it would add a write surface with no consumer.

**Tests removed, and what covers that ground now.** Three `TestCanaryWiring` cases in
`tests/test_waivers.py` were deleted when `#164` retired `_check_broad_exceptions` — and then
restored with the check itself (below). Net: no test removed. The `#728` change updated six tests
asserting `normalize_title`'s old verbatim contract; that contract is what `#728` changes, and the
new one (stash `original_title`, first writer wins) is asserted in their place.

**One norm departure, found by review and reverted.** `#164`'s retirement of the two `compliance.py`
checks shipped ahead of its own precondition. `architecture.md` § Direction (LNG-5W8R) and the
2026-09-01 owner Stopgap (`#732`) both hold that retiring them "cannot honestly precede configuring
ruff for prawduct itself, or coverage is lost rather than delegated" — and configured means
*running*. Ruff was declared in `pyproject.toml` but absent from the `dev` extra, unpinned, and
gated by no workflow, so broad-except was ungated rather than delegated. The retirement is reverted;
ruff is now installable and pinned as groundwork. Order is: migrate the 149 `prawduct:allow`
pragmas, gate the job, then retire. `#164` stays open.

**Test-suite caveat, unfiled.** The suite is nondeterministic under the repo's pinned
`-n 5 --dist loadfile`: two runs of an identical 5541-test selection disagreed, and an xdist
scheduler `INTERNALERROR` truncated another. "Suite green" was therefore not a usable acceptance
signal for the fleet, so agents graded on targeted serial (`-n0`) runs. Worth its own item.

## 2026-09-01: four stalled transitions get a bounded exception instead of a silent one

<!-- prawduct: type=fix | scope=norm-lifecycle-stopgaps -->

`#732`. Four `Status: in-transition` norm entries sat past the 30-day stall window, so
`test_no_norm_lifecycle_advisory_fires_here_today` was red. `docs/norms.md` § Transitions makes a
stall a forcing event with exactly three arms — accelerate, record a stopgap, or improvise a third
system silently — and the first was not available: each tracking item's *first* acceptance criterion
is a full enumeration sweep, a multi-chunk plan per item rather than a fix.

So the interim rules stand as recorded **bounded exceptions expiring 2026-12-01**, in a new
`Stopgap:` field carrying the owner-vetoable `[DECISION: …]` block and a rationale that engages each
norm's own why rather than the local convenience.

**Five entries, not four.** The advisory keys on `(artifact, tracking-id)`, and `architecture.md`
holds two distinct entries both tracking LNG-5W8R — the Python-agnosticism norm and the
guides-never-implements corollary. Editing the four rows the advisory printed would have left one
entry governing new work with no exception recorded.

**Why `Stopgap:` and not the existing `Live exception:` spelling.** `_FIELD_OR_ITEM_RE` admits a
single-word field name only, so `Live exception:` is not a field marker at all — it soft-wraps into
the logical line above it. That is harmless where it sits today (a `Decision:` line, which no probe
scans) but would be actively wrong after a `Status:` line, where `_extract_ids` would read the
exception's own citations as *additional tracking items* and manufacture advisory rows. `Stopgap:`
matches the marker regex, stands as its own logical unit, and is the noun the norms spec already
uses. Verified against `_direction_lines`/`_extract_ids` directly: every `Status:` line still cites
only its tracking id.

**The clock is a comment on each tracking item, and that is deliberate.** `docs/norms.md` puts an
exception's clock on a backlog item, but the Issues backend has no write path for `revisit:` —
`update` strips a caller-pasted `prawduct:` block and re-appends the existing one, and no op takes
the flag (`#564`). `probe_revisit_due` reads *dated* values off the frozen markdown model and is
dark post-cutover regardless. So the walker is the janitor's Norm Health sweep, exactly as it is for
the `#13`/`#13a` exception that set this precedent.

**Honest about why the advisory actually cleared.** The probe's contract claims a stopgap clears it;
no such code exists — `stopgap` appears in `norm_probes.py` only in comments and message strings.
The advisory cleared because recording the clock on each item moved `updated_at`, which is the
*touched* arm. A team that records a stopgap in the norm entry alone would watch the advisory keep
firing and be pushed toward touching the item to silence it, which is the silent departure the
Authority Rule forbids wearing compliance's clothes. Filed as `#737` rather than fixed here, to
keep this cycle prose-scoped.

Also filed, as `#738`: the target test passes **vacuously in CI**. The `backlog-cache-unreadable` exemption is
right for a fresh clone, but the cache is gitignored, so in CI the probe cannot reach the tracking
items at all and the assertion evaluates no norm — local and CI disagreed on the same commit. The
rule that generalises it is already in `learnings.md`: an exemption filter exempts *environments*,
not just conditions, and the exempted set here is exactly "every CI run".

## 2026-09-01: the headline nobody wrote, and the red suite nothing refused

<!-- prawduct: type=feat | scope=release-gate-blindness -->

Two failures met at one moment. The consumer-facing headline is a hand step and it gets forgotten:
**v2.1.6 was tagged and version-bumped with no digest section at all**, which left `develop` red on
`test_changelog_has_current_version_entry` from that release onward — so v2.1.6 shipped on a red
suite, and the redness was the only complaint anything made. It recurred at v3.0.4 and was
backfilled out of band. **v3.4.0 had its section and still led with the seed the previous cut
wrote**, so every upgrading repo was shown "Prerelease under test" as the news, after eight weeks of
good notes had accumulated underneath it. And nothing anywhere on the release path read a test
result.

Phase 0 now answers both. It prints the open section's first non-empty line back verbatim — that is
the line the version-delta banner shows every repo crossing this version, and the whole failure mode
is a line nobody looked at — and warns when there is none or when it is still the seed. It also
asks whether the saved suite run is green and current, and **refuses when it is not**.

**The two halves fail in opposite directions, and that is the architecture rather than a
preference.** The headline check is *coverage*: its subject is prose, and Phase 0 runs before the
step that writes the headline, so on a correct release it fires exactly once and is then fixed. A
refusal there would block a release for a condition the release is on its way to fixing. The suite
check is a *verdict* about whether the release may proceed at all, so it fails closed, on the
channel's existing blocking value — the same exit 1 every other refusal here uses, not a new code.

**What the suite check does NOT claim is written into its message and into the runbook.** It reuses
`gates.tests_are_current`, so the builder's `test-status`, the Stop hook and the release gate read
one record through one reader and a repo cannot be green for one and stale for another. That
predicate's first disjunct is session-freshness — it asks *when* a run happened, not which tree it
met. That is the honest bound at this phase rather than a weakness worked around: Phase 1 rewrites
four files after Phase 0, so **nothing checkable here can vouch for the tree the tag will carry**. A
green-suite check at the tagging moment would be a different control at Phase 2.

Four states reach the one refusal and the message names which: no evidence on disk, a run reporting
failures, a run predating the session that can no longer be matched to the tree, and a run that
reported itself `degraded`. The last is the one worth stating — a contended run exits 0 and reports
a plausible total, so nothing in the counts distinguishes it from a clean pass; a release has to
read it as "no run", never as "a green run".

**The verdict is reported at the top and returned at the bottom.** This repo's ordinary Phase 0 run
exits at `no-release-plan:` — the documented, expected first result — so a refusal wired only into
the final return would never be seen by the operator it is for. Printing it early also keeps the
property this gate holds elsewhere: every other check still runs, so one command reports every
problem instead of one per round trip.

Both digest questions now come from **one read of one section**. Reading the file twice would let
them answer about different states of it, and would double the degraded NOTE into two sentences
saying the same thing happened; that NOTE now names both consequences, because advice failing soft
is not advice failing silent. And both stay behind `_ships_the_plugin_tree`: the headline message
would have been the third `plugin/…` path printed at a repo that cannot have one.

## 2026-08-29: the release-pending scope that reaches the tag with nothing written about it

<!-- prawduct: type=feat | scope=release-gate-blindness -->

A release-pending scope could reach the tag with **zero** consumer-facing notes in
`plugin/CHANGELOG.md`, and no gate asked. It happened at the v3.4.0 cut:
`scope=tactical-efficiency` carried nine `release=v3.4.0` entries and no mention in the digest, and
the notes were hand-written at cut time because somebody happened to notice. **The failure is
asymmetric — a section full of good notes reads as finished, so the missing scope is invisible
exactly when the digest looks healthiest.**

Phase 0 now tests each release-pending scope against the open digest section and emits one WARNING
per scope it could not find, beside the existing `has no build-plan file` advisory. Both ask whether
the pending set is described somewhere a reader will look, and neither is a releasability verdict.

**It never touches the exit code, and that is a classification rather than a caution.** The subject
is prose and the instrument is a name match, so it is advice by construction; the authority gate
beside it refuses on state it cannot *evaluate*, and an unmentioned scope is not that — the release
stays perfectly evaluable, it may just ship under-described. The wording follows: *"could not find …
check the section"*, never *"is missing"*. An advisory that overstates its own certainty is how a
fuzzy check gets promoted to a blocking one, and promotion is what changes the price of its false
positives.

**Matching is bounded on both ends, and the hyphen is part of a name rather than a boundary.** A
plain substring test passes a short slug on any longer word containing it, and a plain word boundary
breaks on the hyphen — either way `adhoc-delegation`'s note would mark `delegation` covered. Both
errors run the wrong way: they report a scope as *covered* that the digest never mentioned, which is
the silent pass this check exists to prevent. A false alarm costs a reader ten seconds. The slug's
words count too (`manifest state diagnosis` covers `manifest-state-diagnosis`), because consumer
prose spells slugs out and a slug-only test would report nearly every scope as uncovered.

Coverage is read from the **topmost** section only — the digest states that convention itself, and a
whole-file search would let prose written for a version that shipped months ago read as this
release's coverage. The section boundary is `## ` plus any non-space, looser than a version match on
purpose: a stricter pattern would let a heading it cannot parse fail to *delimit*, merging the
section below into the open one. That is a false pass produced by the strictness itself.

Where the digest cannot be read or holds no section, the check emits a NOTE naming what went
unchecked **and what that costs** — *advice fails soft is not advice fails silent*, and a check that
skips itself quietly is indistinguishable from one that passed.

**That rule governs a check that ran and could not answer, not one that was never about this repo.**
The digest ships inside the plugin and never lands downstream, so every `plugin/…` path this module
prints names prawduct's own layout. A shared predicate now decides whether that layout is the repo's
subject at all: downstream the whole arm is suppressed rather than reworded, because a repo that
publishes no digest has none to be *missing*. The `no-version:` hint — the first member of that
class, fixed alone in R-4/R-12 — consumes the same predicate, so the question is asked once. And a run that finds
nothing still prints its denominator (`digest coverage: N of M`), because the only honest argument
for retiring this later is a run of it finding nothing, which requires it to have counted out loud.

**Measured on this repo: 13 of 14 release-pending scopes carry no note in the open
`## v3.4.1-dev.2` section.** Hand-checking all 13 found eleven genuine gaps and two false positives
— `branch-claim-multiplicity`, covered in prose under different words, which the plan predicted; and
`release-v3.4.0`, a release-mechanics scope that records the cut itself and will never have a
consumer note. That second one is a class, not an instance, and it is left visible rather than
suppressed: a suppression list is the sophistication this check deliberately does not have, and the
advisory posture is what makes carrying a ~15% false-positive rate the right trade.

## 2026-08-27: the release-pending entry that enumerated as nothing, and the branch that never counted

<!-- prawduct: type=fix | scope=release-gate-blindness -->

`check-releasability` enumerates *scopes*. A release-pending change-log entry carrying no `scope=`
contributes none, so it reached no row of the release plan's classification table, could be neither
shipped nor withheld, and Phase 0 certified `releasable` over work it had never seen. The code
already knew: the `if not pending:` branch named this blindness in a comment — "entries that carry
no `scope=` key at all and are therefore invisible to this gate" — and returned 0 anyway.

**The accounting existed in the branch where nothing was pending and was absent from the branch
where something was, and that asymmetry was the whole bug in one place.** The no-pending branch
printed its denominator (`N entries scanned, M tagged`) precisely because "0 pending" has several
causes and only some are a pass. The branch that did have pending work printed a verdict and never
said what it had looked at, so nothing it missed could be noticed. Both branches now account.

`release_pending_entries` holds the release-pending set as *entries*; `release_pending_scopes` is
that same set collapsed to its `scope=` values and now consumes it rather than re-deriving it, so
the two cannot drift apart — the gap between them is exactly what the reconciliation measures.
`unclassifiable_pending_entries` is that gap.

**It refuses, and the refusal runs before the no-pending return.** Refusing is what an authority
gate owes a releasability verdict over work that cannot be classified; the remedy is one `scope=`
per entry, and every offending entry is named with its title and change-log line so the fix is
mechanical. The placement is not cosmetic: when the scopeless entry is the only unreleased work,
the pending set is empty, so a check placed after that return would run on the one shape it exists
to catch and find nothing. Exit **1**, the value every other refusal here uses — not 3, which means
the gate's *subject* could not be read, and here the log parsed fine; it is the work that is
unclassifiable.

**Measured before landing: 364 entries, 343 tagged, 31 release-pending across 13 scopes, 0
unclassifiable** — so this repo's gate output is unchanged but for the new `scanned:` line. Thirty-nine
historical entries do carry no `scope=`, all of them stamped `release=`, and a release tag settles
the question scope-or-no-scope; refusing on those would fail every past release forever. The cost
falls on a consumer repo holding a legacy scopeless *pending* entry, whose release newly refuses —
accepted deliberately, with the veto route recorded in the build plan's open assumptions.

The one test that reads the real change log asserts the **invariant** (entries ≥ scopes; every
classified pending entry's scope is one the gate enumerates) and says which emptiness it rejects — a
log that parsed to nothing, never an empty pending set, which is what a just-tagged release looks
like. Six `TestAgainstTheReal*` guards died together at v3.3.0 for want of that distinction.

## 2026-08-27: the rc track that develop had already replaced, resolved rather than re-merged

<!-- prawduct: type=fix | scope=branch-claim-multiplicity -->

The branch sat 251 commits behind `develop`, and the sync was not a textual merge. Half of Chunk 04
— a develop track keyed on an **rc** prerelease — had been independently superseded: `develop`
shipped its own track on a deliberately narrower rule, `-dev` / `-dev.N` as the ONLY permitted
suffix, with `test_version_tuple_refuses_an_unpermitted_prerelease` asserting that `3.4.0-rc.1` must
**not** parse so the banner and the manifest guard keep answering one question about what a legal
version is. Taking this branch's general-semver parser would have meant deleting that test.

**Resolved in develop's favour, and the descope is recorded rather than inferred.** Every
version-carrying file — `plugin/VERSION`, `plugin.json`, `pyproject.toml`, `banner.version_tuple`
and both version test files — took develop's side; Chunk 04 carries a DESCOPED note naming what was
superseded and what survived. A release-candidate stage now exists in no form, which is a fresh item
designed against the `-dev` rule, not a resurrection of this chunk.

**The prose had to move with the code, and two places were actively wrong once it did.** The
dogfooding recipe still instructed maintainers to set `3.4.0-rc.1` — a version this tree's own tests
reject — and the runbook asserted the open changelog section is written under the FINAL number while
develop's step 10 opens it under the prerelease heading and renames it at the cut. Both restated in
`-dev.N` terms. Consumer notes for the `branch:` opt-in and the union-merge advisory went into the
OPEN `## v3.4.1-dev.2` section, not the shipped `## v3.4.0`, because this work is still
release-pending; the README bullet joined develop's combined 3.1–3.4 section rather than re-splitting
a 3.4 heading develop had already folded in.

**Where the two designs genuinely disagreed about `active_build_plan`, the branch's rule won**,
because it is the one its own code makes true: `core.resolve_branch_claim` falls back to the scalar,
so a pointer left aimed at a merged branch-declaring plan puts that finished plan back in force on
every branch with no plan of its own. Three cross-file references to "merge-flow step 7" — renumbered
to 8 on develop — were replaced with the step's NAME rather than a new number, so the next renumber
does not strand them again.

**Superseding one clause of this branch's own 2026-08-13 entry**, which ships in the same bundle and says "an rc bump does not owe a changelog entry for a version nobody ships": that reasoning belonged to the rc track and is now false in both halves — there are no rc bumps, and `test_changelog_has_current_version_entry` requires the section to be keyed by the EXACT manifest string, prerelease suffix included. The earlier entry is left standing as written (the log is append-only); this is the correction a reader needs.

Chunk 04's live half stays outstanding and is now visible as VRF-017: the recipe installs from
`ref: develop`, so no sibling repo can run the track until this merges and pushes.

## 2026-08-14: the derived-sentence defect, found twice, closed by enumeration

<!-- prawduct: type=fix | scope=branch-claim-multiplicity -->

The branch's cumulative review found the *same class* its predecessor did, surviving in a state the
first fix did not reach — and that recurrence is the finding, not the sentence.

Precedence step 3 reads "the pointer, when it names a claimant" in prose and `pointed in pool` in
code, and those differ exactly when the scalar names a claimant whose boxes are all ticked while
others are open. The code is right — live evidence outranks a stale scalar, and the pointer must not
resurrect a finished plan — but the `order` sentence then told an operator "`active_build_plan` names
none of them" about a repo whose scalar named one. The docstring now states the narrowing and why
it exists; the sentence derives its pointer clause the way it already derived its open-work count.

**The fix is enumeration rather than another correction.** Every state the `order` basis can be
reached in — pointer unset, pointer naming a non-claimant, pointer naming a ticked claimant, no
claimant open — is now a case in one test, so a fifth state cannot be added without a failing
assertion. Two spot fixes in two rounds is the signal that the states were never listed.

**Two guards this bundle added were themselves unpinned**, in the same round that fixed unpinned
prose. `_is_standalone_tag_line` feeds a release-gate warning over every governed repo's real change
log and only its positive case was asserted — both conditions now carry the corpus case that forces
them, and the repo's own 306-entry log is a fixture. The briefing's attributed swallow, which *was*
the fix for a prior review's silent `except: pass`, had nothing asserting it, so a refactor back to
`pass` would have restored the silence invisibly.

**The develop track gained the lifecycle it was missing.** Promotion sets the final version on
`main` — and on `develop`, which was promoted — so the two match and every dogfooding repo silently
resolves the released cache entry while believing it is on develop. The first work merged after a
release re-opens the next rc; until then there is nothing unreleased to dogfood, and the equality is
honest rather than a trap.

Also: the retention rule Chunk 02 reversed was still stated in the release process and its runbook,
one of them citing as authority the bullet that had changed; `planning.md` contradicted itself on
whether a branch-declaring plan has a pointer at all; the PR skill pointed at a command that does
not print the resolved plan in the modes that fire at PR close (`verify-records` does, in every
mode); and the precedence was restated in four places, two of them already partial — it now lives in
one, with the others pointing.

## 2026-08-13: develop becomes a track you can actually run on

<!-- prawduct: type=feature | scope=branch-claim-multiplicity -->

`develop` reaches consumers through nothing, which is correct and made it impossible to run
unreleased governance against real work before promoting it. It is now a track one repo of yours can
opt onto: a second marketplace entry (`prawduct-dev`, same repo, `ref: develop`) in that repo's
per-machine `.claude/settings.local.json`. Nothing is pushed to `main`, the repo's committed install
reference never changes, and the way back off is deleting the block.

**The version is the cache key, and that is what makes this work at all.** The plugin cache is one
directory per version (`~/.claude/plugins/cache/prawduct/prawduct/<version>/`), so a `develop` whose
version still matched the released string resolved to the *released* cache entry — you would
dogfood nothing while believing otherwise. `develop` now carries a prerelease of the version it is
heading for (`3.4.0-rc.1`), bumped as work lands.

**Which the repo's own tooling then rejected, in three places.** The manifest check demanded exactly
three numeric parts; the changelog check demanded a section named for the exact running version; and
`banner.version_tuple` parsed any suffix as "older than everything", so a dogfooding repo would have
seen no banner and the next real release would have replayed every headline in the file. All three
understand a prerelease now: it sorts below its own release, and it is satisfied by that release's
changelog section — an rc bump does not owe a changelog entry for a version nobody ships.

The consumer-facing narrative for the pass ships in `plugin/CHANGELOG.md` under `v3.4.0` — the two
surfaces a consumer actually meets are the new change-log union-merge advisory (what it is, that it
is advice, how to make it stop) and the `branch:` opt-in (what it buys, that nothing migrates, and
that several plans may claim one branch). `.prawduct/release-notes.md` was NOT touched: it is a
frozen archive of a retired derived view, and writing there would revive it.

## 2026-08-13: a merged-away change-log tag stops disappearing quietly

<!-- prawduct: type=fix | scope=branch-claim-multiplicity -->

The union-merge advisory told operators that a two-sided edit to one entry's tag line "is surfaced
downstream rather than silently believed," naming the release gate's tag validator as the catch.
Writing the test that was supposed to pin that claim disproved it.

`merge=union` concatenates whole **hunks**, so the second version of an edited tag line lands
*after* the first version's prose — not beside it. Entry parsing ends its tag block at the first
prose line, by design, so that second tag line was metadata to nobody: its pairs reached no `tags`
dict and no validator ever saw them. A `release=` stamped on one side while the other side edited
the same line could vanish in a merge, under a caveat asserting it would be caught.

Parsing now counts tag lines past the prose (`ChangeLogEntry.unconsumed_tag_lines`) and
`validate_change_log_tags` warns that they are read by nothing. Counted rather than merged,
deliberately: merging would let a merge driver decide which `release=` wins, and the failure worth
preventing is not that the value is wrong but that nothing says it is there.

The detector needs both of its conditions, and the corpus proves it — a tag line must *begin* its
line and parse to at least one real `key=value`. `TAG_LINE_RE` alone also matches a sentence
quoting the format, and this change log contains one, so the looser rule reports the file that
documents the format as malformed. Zero of 306 existing entries trip the strict form.

**The finding this chunk was written for did not exist.** The claim under review was that union
keeps duplicate whole entries; constructing the merge showed identical hunks are not conflicting, so
a twice-landed entry is kept once. The chunk was rescoped from fixing prose to pinning it — and the
pin is what found the real defect one layer down. Both shapes are now fixtures, alongside the
existing no-attribute conflict control.

## 2026-08-13: a branch-declaring plan retires by archiving alone

<!-- prawduct: type=fix | scope=branch-claim-multiplicity -->

`planning.md` and `/prawduct:pr` both promised that a merged branch-declaring plan "reads
live-but-inactive with no advisory to ignore." It did not, and this repo's own `develop` was the
counter-example: the gitflow RETAIN rule says to keep `active_build_plan` aimed at a merged plan, so
resolution fell through to the scalar and the archive-the-plan advisory fired exactly as before —
against a plan the same rule says to retain until the release. An advisory with no correct action.

The RETAIN bullet now splits on how the plan resolves. A plan that declares `branch:` gets its
pointer **cleared** at the closing merge: its branch is gone, so the declaration resolves for
nobody, the plan reads live-but-inactive, and the release still archives it by scope. A
pointer-resolved plan keeps the pointer, because clearing it is what makes governance blind. This
repo's own scalar is now unset, and the absence is annotated as the state rather than left to read
as an oversight.

## 2026-08-13: several plans may claim one branch

<!-- prawduct: type=fix | scope=branch-claim-multiplicity -->

Branch-scoped plan resolution shipped with a fail-closed refusal: a second live plan declaring the
same `branch:` stopped resolution entirely, on the reasoning that governing by the wrong plan looks
exactly like governing correctly. The reasoning was right and the proposition it guarded was false.
**A branch can legitimately carry several plans** — a `release/2-0` with a telemetry plan and a
documentation plan; a consumer repo carries three on one fix branch today. Refusing is the correct
posture when a control cannot know the answer, and the wrong one when the answer is "all of them,
and here is the one being worked."

Resolution now picks among the claimants by a stated precedence — sole claimant, then the one with
chunks left, then the plan `active_build_plan` names, then path order — and **names its choice and
what it passed over** in the session briefing. That is what answers the original concern: a choice
stops looking like the only possibility the moment the surface says what else claimed the branch.
The scalar gains a job rather than losing one — it is now the operator's tie-break *within* a
branch, instead of one product-wide singleton.

The sole-claimant step sits ahead of the chunks-left step deliberately: the unfinished signal goes
false the moment the last box is ticked, which happens *during* the closing PR, and a plan that
stopped governing between its final review and its merge would take the gates with it.

**Found by reading the feature against a consumer, not against its own tests.** That repo's plans
already carried `branch:` in frontmatter as human documentation, written months before the key had
meaning — three of them naming one branch, one of them holding prose (`feature/x (off develop)`)
that is not a branch name at all. The key was declared collision-free on a grep of *this* repo and
the shipped templates; the population it ships to was never asked. Its shapes are now a test.

**The attribution sentence is derived, because it is the whole replacement for the deleted
control.** Three reviewers independently found the same defect in it: the `order` basis is reached
from two opposite states — several claimants still holding open work (the shipped headline case: a
release branch with two live workstreams and no pointer set) and none of them holding any — and one
sentence covering both told half its readers their open plans were finished. The clause now counts
the claimants still holding open work, and ends with the act that decides it: point the scalar. Each
rendered reason is pinned by a test, including a three-claimant render; before, none of the three
wordings was asserted anywhere and any of them could have been falsified with the suite green.

**Attribution has one home: the session briefing.** The gates already name the plan they graded
(`record-lint`'s `plan_graded`), so what is missing at a gate is not the choice but the context for
it — which is session-scoped, arrives before any gate runs, and would be a fourth copy of one
sentence if every gate repeated it.

`AmbiguousPlanBranchError`, the hook's `main()` classifier and the `cmd_stop` probe that rendered
the refusal as the harness block code are **deleted** rather than left as handling for a condition
nothing can produce (Principle 25). Their tests are redirected, not dropped: each now pins that a
contested branch reaches the same gates an uncontested one does. `_scope_of_branch_claiming_plan`
stopped declining on the second claimant too — it asks the same resolver, so a dispatch's ledger
scope names the plan the gates actually graded.

**Two ripples the review caught, both outside the files the change was "about".** Three skill files
(`pr/SKILL.md`, `backlog/SKILL.md`, `backlog/adapter-mode.md`) still spelled a one-claimant
resolution rule in the same commit that declared multiplicity ordinary — and the PR one feeds
`archive-plan`, so an agent picking by eye on a contested branch could retire a sibling plan that is
still live work. They now point at the resolver rather than restating a rule with four steps. And
the briefing's contested-claim line sat inside a broad `except: … pass`, which — with the
fail-closed route deliberately gone — meant the only surface that ever says a branch is contested
could vanish with no output at all. It is attributed now: advice fails soft, not silent.
## 2026-08-27: the version-delta headline renders as one sentence

<!-- prawduct: type=fix | scope=silent-clear-checks -->

Every version-delta headline carried a stray `**` mid-sentence — *"Less waiting on the gates, fewer
rounds in review.`**` Gate checks stop timing out…"* — and had done since at least v3.3.2. It lands
on the single most-read line prawduct emits: the one every upgrading repo sees.

The cause is that a bullet and an emphasis marker share a character, so they cannot share a strip
set. `lstrip("-* ")` consumed the OPENING `**` of a bolded lead-in as though it were bullet
punctuation, leaving the closing marker with nothing to pair against. The discriminator is now the
FOLLOWING WHITESPACE — `* ` opens a list item, `*text*` and `**text**` open emphasis — and only
then is a matched leading pair unwrapped, longest marker first.

**Mid-sentence emphasis is preserved, and that is why this is a function rather than a wider strip
set.** A blanket `replace("**", "")` would have cleared the symptom by flattening the author's own
markup.

The acceptance criterion took two corrections during the build, both recorded. "No headline contains
`**`" would have demanded exactly that flattening. "Every marker is PAIRED" replaced it and was also
wrong — it is unachievable over this artifact, because changelog prose legitimately carries markers
that are not emphasis: a snake_case identifier makes the `_` count odd, and a shell glob inside a
code span (`~/.claude*/plugins/…`) makes the `*` count odd, and both fired on healthy entries. What
the stripper actually promises is narrower and is the reported symptom's exact inverse: **a stripped
headline does not begin with an emphasis marker.** That is what is asserted, against the live
`CHANGELOG.md` rather than a fixture.

Three items carried from the previous chunk ride this commit: two stale return annotations that
still said `str | None` after the error slot became a `{"title", "error"}` dict, an over-long
docstring line, and the last two subprocess tests inheriting `os.environ`. That last one did **not** close its class, and the
claim that it did was wrong: a sweep for `env=dict(os.environ)` missed four more helpers passing a
`cwd` and no `env` at all, two of which invoke WRITERS (`lifecycle-repair`, `archive-plan`) against
the real repository whenever the harness sets the pin. They pass today only because the variable is
unset here.

**So the class is closed by a construction rather than a fourth copy of the fix.** A session-scoped
autouse fixture removes `CLAUDE_PROJECT_DIR` from the environment for the whole test run, so no test
can inherit it — including tests not yet written. Three files had each grown a near-identical
pinned-env helper, and two write-command call sites were still open, because a convention protects
only the files whose author happened to know about it. A test that genuinely wants the pin still
sets it explicitly.

## 2026-08-27: a duplicate learnings heading is reported, and refuses a retirement

<!-- prawduct: type=fix | scope=silent-clear-checks -->

`_take_active_narrative` resolved a heading by exact title and took the **first** match. Two
same-titled blocks therefore meant a retirement cut one and archived it while its twin stayed in the
active section with no index entry pointing at it — prose kept, index lost — in a file whose stated
invariant is *never delete an entry here*. The function's own docstring warned about a *drifted*
title and guarded exactly that; a *duplicated* one was unguarded, and the two fail in opposite
directions: drift matches nothing and is a harmless no-op, duplication matches twice and loses an
entry.

It now scans every match and **refuses** on a second, naming both line numbers, and the refusal
returns before any cut is composed — so a rejected run leaves both files exactly as it found them
rather than half-moved. It deliberately does not de-duplicate: which of two identically-titled
blocks is the real one is not something it can know, and an automatic fix would delete an entry to
satisfy a check, in the one file that says never to.

A new `check-learnings-pairing` grades the same defect earlier, before a retirement is attempted,
and `/prawduct:doctor` reports it (Health Check #13a). Both exit **3** when the pair cannot be read,
per the standing third-outcome rule, and `audit-learnings --apply` exits **1** when it refuses — a
writer that wrote nothing.

**Review found the refusal was right and its delivery was not**, which is the half worth recording.
The refusal was appended to `errors` as a bare string where every other member of that list is a
`{"title", "error"}` pair — so the CLI renderer that reads `e['title']` would raise a `TypeError`
traceback across the boundary, which the api-contract forbids by name. The per-entry `applied` flag
stayed `true` while the top-level one was correctly walked back, and the renderer branches on the
per-entry one, so a refused run printed `retire[retired]` for entries still sitting in the active
file. And the refused run exited **0**, telling its caller the retirement happened. Three defects,
all on the delivery path, none of them reachable from a unit test of the cutter — which is why the
tests now drive `audit-learnings --apply` end to end.

**One half of the issue's ask was narrowed, deliberately and on evidence.** #717 also asked for
counterpart and ordering findings, on the stated invariant that the two files "mirror each other's
headings in the same order". Measured against this repo's own corpus *before* building to it, that
invariant does not hold and never did: 270 active index entries against 179 in the detail file, and
a detail heading is a truncated **prefix** of its index entry rather than a copy. Grading it would
have emitted ~117 findings on a corpus nobody considers broken — the misfiring probe `docs/norms.md`
names by its cost, which is that it teaches its reader to skip the one real catch. The counts ride
the result for anyone working the drift down; no finding is raised on them. Naming what the pairing
convention actually *is* has to come before anything can grade conformance to it.

## 2026-08-27: the verdict cache keys on the code that computed the verdict

<!-- prawduct: type=fix | scope=silent-clear-checks -->

`verdict_cache._key` folded in the plugin version because the cache outlives the plugin and the
verdict depends on `coverage_algebra.is_judgeable_path`. That is enough for an installed copy,
where the version string moves whenever the code does. It is not enough when prawduct runs from a
**git checkout** — developing prawduct itself — because the bundled `VERSION` does not change
between pushes to `develop`. Two different develop states therefore produced the same key *by
construction*, and a verdict computed under the older one was served as current. `_key`'s own
docstring already stated the invariant it was breaking: the key covers "every input the verdict is
a function of — including the CODE that computed it."

The key now folds in the checkout's plugin **tree** SHA, plus a fingerprint of any uncommitted edits
under that directory.

**Tree, not commit, and this was corrected at plan time rather than in review.** The first draft
keyed on the commit SHA; `data-model.md`'s tree-keying Direction says facts key by tree, and here
that is load-bearing rather than stylistic — two develop commits producing an identical plugin tree
*are* the same code, so commit-keying would miss the cache on every rebase, merge, empty commit, or
commit touching only files outside the plugin. Tree-keying invalidates when the code changes and
only then, which is the whole point.

**Degradation is toward coarser, never toward a false pass.** Not a checkout, or git cannot answer,
contributes the empty string — so an installed copy keys exactly as before and no user sees a mass
cache miss on upgrade. A coarser key makes entries collide and be replayed, and a replay can only
reproduce a verdict the store's own content fingerprint already vouches for. The probe is memoised
per process on a `None` sentinel rather than on falsiness, because `""` is a legitimate answer and
sentinel-on-falsiness would re-probe git on every lookup for exactly the users who gain nothing
from it — spending the saving this module exists to create.

## 2026-08-27: a verify pass cannot report the review over while a blocker it inherited stands

<!-- prawduct: type=fix | scope=silent-clear-checks -->

A `verify-resolutions` pass could discharge one finding by reference to another — *"R-12 is
implicitly closed by R-1's fix, same class"* — and write a resolution fact for R-1 only. Its own
counts were then 0 blocking, so it printed **THE REVIEW IS OVER**, and the operator relayed that.
The gate disagreed: R-12 had no resolution fact, and the gate reads facts. Worse, by the time that
surfaced R-12 sat on a superseded round no later verify pass would name, so the only remaining
route was a full `cumulative` — a whole review round of bookkeeping for a defect that had been
fixed and independently confirmed fixed two rounds earlier. That is what it cost when reported.

**Nothing parses the reviewer's prose, and that is the point.** The tempting fix is to read
"implicitly closed by" out of the summary and mint the missing fact from it. The phrasings are an
open set, so a parser that misses one fails silently in the bug's own direction — and
`data-model.md` forbids the result outright: a resolution fact requires a `verify-resolutions`
origin and a pre-existing target finding, so minting one from narration would record a judgment
nobody made. The pass instead loses the ability to *claim* it finished: consolidation now computes
the blocking findings it inherited and did not name, and the one sentence both the builder and the
reviewer read says the review is **not** over, names each finding, names the prose forms that
produce this, and says the deadline — act before a newer round supersedes them. That sentence
outranks the pass's own counts, including when it found blockers of its own: the ordinary blocking
line says "nothing else here does", which is false the moment a blocker was inherited, and a
builder who believes it fixes this round's findings and orphans the other onto a superseded round.

**The same rule is applied a second time, earlier, where it can still change the outcome.** The
consolidation check acts *after* `resolutions` is written — it can stop the pass claiming it
finished, but the round is already spent. So a verify dispatch now hands the reviewer a roll-call
of the exact finding ids the round it verifies left unresolved, each of which must come back with a
verdict. It sits between the two existing directives rather than after them: the roll-call sets the
agenda, and the standing "a resolution is a claim" warning keeps the last word, because it governs
the only reviewer output that can weaken a gate and a roll-call read last would push toward naming
every id on it. It is silent when there is nothing to account for — a directive that fires on every
dispatch trains its reader to skip the block it lives in.

Placing it also required moving `RESOLUTION_IS_A_CLAIM_DIRECTIVE`'s ~45-line `#:` documentation
block back against the constant it describes: the new function had been inserted between the two,
leaving the block reading as that function's documentation. Nothing builds Sphinx here, so the cost
was a maintainer editing a doc block about the wrong subject.

**The anchor is structural rather than a guess.** A verify pass reviews the delta from the prior
review, so its `base_tree` IS that review's `head_tree`. Matching on that link finds the anchor
without reading `.critic-findings.json` (a derived view no gate may read) and without trusting
"most recent review fact" — the evidence store is shared by every worktree of the clone, so that
rule would let a sibling branch's review supply this branch's blockers.

## 2026-08-27: an input that could not be read or recognised says so

<!-- prawduct: type=fix | scope=silent-clear-checks -->

Two instances of one rule — **a present input that yielded nothing must not read as absent.**

**The operator-verification gate was latently inert.** An entry is recognised only as a
`## VRF-<id>` heading; anything else parses as preamble, which is deliberate and is what lets a
trailing `## Notes` section coexist with real entries. That leniency is unchanged. What was wrong
sat downstream: the gate discarded the preamble and reported `pending: 0` for a file it had parsed
**zero** entries out of. A repo holding 32 entries as bullets under one `## Pending` heading was
told its queue was empty, and `/pr create` blocked on nothing while every entry sat unseen.

The fix is at the frame that actually discards. The parser was never the problem — it returns the
preamble intact and loses nothing; the gate was throwing that preamble away unread.

**Scope, stated honestly:** the discriminator reads the preamble, which is everything before the
first *recognised* entry. So a queue whose entries are ALL unrecognised is caught, which is the
reported failure and the one that makes a gate inert. A queue holding one good entry plus several
unrecognised ones is not — those land after the first entry, in the body of a block that did parse.
That is the same leniency that lets a trailing `## Notes` section coexist with real entries, and it
is deliberate: the alternative refuses files the format explicitly permits. A required gate that finds unrecognised content now
refuses with a distinct `unreadable` status, names the expected shape, and exits **3** — the
standing rule for a gate whose SUBJECT could not be read, now stated once in the api-contract
rather than as a list of gates that carry it. It still blocks (3 is non-zero), but not as exit 1:
that code already means "there are pending entries, drain or override the first one", and both
remedies are inapplicable to a file that yielded no entries, so reusing it would send the caller to
a fix that cannot work — ending at the queue file, which is the one move the refusal forbids.
Scoping it to `operator_verification_required: true` is what makes it safe: only a repo that opted
into the gate can be stopped by it, and there being stopped is correct.

**The override inherits the refusal, because it inherits the door.**
`accept-operator-verification` reads the same queue and would have reported the gate "already
satisfied" with `accepted_ids: []` — a recorded bypass covering entries nobody read. It refuses on
the same state, without touching the file it refused over. Fixing the check and leaving its sibling
would have been the instance, not the class.

**The refusal also forbids the obvious fix, because the obvious fix is worse than the bug.** An
agent meeting this block will reach for the queue file and reformat it — a silent rewrite of an
operator-authored record, performed to satisfy a gate, that nobody reviewed. The message says so in
the imperative. A refusal in front of an agent is an auto-fix unless it says otherwise.

**An unrecognised `Critic mode:` value now says so once.** Fail-open-to-inference is correct and
did not change — a typo'd mode must not block a review, and nothing is skipped. The ignore simply
stopped being silent, which had let an author believe a mode was pinned when it was not and file
the resulting surprise as a defect. Absent and blank stay silent: they carry no intent to
contradict. Where the value is a valid `Type:` — `cumulative-final` is the natural trap, since it
reads like a mode and lives on an orthogonal axis — the line names the right field, tested against
the real Type vocabulary rather than a copy of it.

## 2026-08-27: onboarding proves the plugin will load, or says it could not tell

<!-- prawduct: type=fix | scope=silent-clear-checks -->

A repo could be onboarded perfectly and still run **completely ungoverned**. Writing the install
reference into `.claude/settings.json` enables the plugin; it does not install it. The harness also
needs a `prawduct@prawduct` record whose `projectPath` is that repo, and without one the target
starts every session with no banner, no `/prawduct:*` skills and no Stop-hook gates — while its
`CLAUDE.md` states that enforcement is structural. The agent reads that stanza, believes it, and
builds ungoverned. This is the failure prawduct exists to prevent, happening to prawduct.

**The detector could not go where every other health check lives, and that is the design.** Probes
and `/prawduct:doctor` both run inside the repo's own session, and both are delivered *by* the
plugin that did not load — in the failing repo the probe never fires and the skill cannot be
invoked. So the check runs from **outside**: `/prawduct:onboard` now ends by asking
`prawduct-hook check-plugin-active --path <target>` about the repo it just set up, and does not
report success until the answer is `active`. `/prawduct:doctor` gets the residue it *can* see — a
stale install, and a SessionStart hook that never completed in this clone — and says plainly which
case it cannot reach.

**Three answers, not two, and the third gets its own exit code.** `installed_plugins.json` is a
harness-internal file prawduct is not entitled to rely on, so every read or shape failure yields
`unknown` — "could not verify" — and never `inactive`. Telling an operator their plugin is not
installed because a file would not parse sends them to reinstall something that was never broken.
`unknown` exits **3**, joining `check-released`'s *unverified* under one shared reason: both
foldings of "could not run" are wrong. Folded into 1 it reports a broken install off an unreadable
harness file; folded into 0 it reports a clean bill off a check that never ran — which is the
class this command exists to close, so spending it on the command's own error path would be the
joke writing itself. (The ratified *fail-open, exit 0* rule is a different case and still holds
where it applies: the plugin's own lib failing to import.) The manifest is read structurally rather
than by its `version`, so a harness release that bumps the number keeps working and one that
changes the shape declines to guess.

**The same status does not mean the same thing to both callers, so `--context` selects the
wording.** From onboarding, `inactive` means the repo will load nothing. From `/prawduct:doctor` it
cannot mean that — doctor IS a plugin skill, so the plugin demonstrably loaded, and the only
reading left is that the manifest names some other path: a worktree, or a moved, renamed or
symlinked checkout. Relaying the onboard consequence there would send an operator to reinstall a
working install, which is the false accusation the rest of the module refuses to make. Two
consequences, two messages, one home.

## 2026-08-26: a dispatch refusal names the tree it graded and the work it excluded

<!-- prawduct: type=fix | scope=verify-resolutions-exit3 -->

`verify-resolutions` anchors at committed HEAD once a commit lands that the prior review never
saw — the PR gate's target, and the fix for the inverse anchoring bug. Judgeable files still
sitting uncommitted are outside that interval by construction. When the interval then held no
judgeable file, dispatch returned exit 3 with `no judgeable file in <a>..<b>` and named nothing
else: a statement about the *interval* that every operator read as a statement about the *repo*.
The observed cost was two dispatches for one review — commit, discover the delta existed after
all, dispatch again.

**The refusal was right; its report was not.** Reviewing that interval would not have covered
those files either, so the predicate is untouched and exit 3 still means exactly what it meant.
What changed is that a refusal now names the tree it graded (`anchor`) and the judgeable
uncommitted files that tree does not contain (`excluded_wip`), on the result, on the CLI, and on
the guard-refusal fact — where `free_files` alone could not tell a refusal that left work outside
the interval apart from one over a clean tree.

**A check that could not run is not a clean bill.** `evidence.tree_diff` returns `None` when the
diff cannot be computed and never guesses; collapsing that into `[]` would have made the one
report written to catch work falling outside an interval answer "nothing fell outside" on the
strength of a check that never ran. `None` propagates instead — through the note, the result, the
fact and the yield query, which renders `excluded=?`.

**Ordering is behaviour here.** A reader of a multi-line block acts on the final imperative, and
above the exclusion notice that imperative is `--force` — which reviews the very interval that
already excluded these files. The notice prints last, and the "Nothing to do" line is withheld
whenever it would be an unearned all-clear. The refusal path also stopped discarding the
dispatch's own `notes`, which it wrote and then returned past — all but the dirty-tree note,
whose content the refusal block already delivers, so the fact reaches the operator exactly once.

`cumulative` gets the same treatment from the same helper: it has always anchored committed HEAD
and always noted a dirty tree without naming anything in it.

**Five prose sites promised working-tree coverage without the condition that makes the promise
true.** The `check-cumulative-critic` uncovered remedy and `skills/pr/SKILL.md` Step 2 both said
"commit that tree verbatim and no further pass is owed", which holds only when the pass anchored
the working tree. The same gate's *blocking* remedy promised a verify pass "reads the dirty tree"
unconditionally. `skills/critic/SKILL.md` told the reader a `cumulative`/`verify-resolutions`
exit 3 means the gate is satisfied — true of the PR gate, false of the Stop-hook gate in exactly
the excluded-WIP case. And `methodology/building.md` prescribed commit-then-verify, the ordering
that moves the anchor.

**The discriminator is a tree comparison, not a commit-set one** — and the first draft of this
fix got that wrong in two of those sites, which is the same class of error one level up. The
anchor moves when committed *content* differs from the tree the prior review saw; the commit that
materializes a reviewed dirty tree verbatim changes no content and moves nothing, so "did I
commit at all" is the wrong question. The two sites that state the test — the `uncovered`
remedy and `pr/SKILL.md` Step 2 — now say it that way and cite `review-cycle.md` rather than
restating the derivation; `tests/preferences/test_free_interval_prose.py` pins both halves. The
other three carry a different correct fact and need no citation. `begin_review`'s docstring
described the pre-#395 working-tree-only anchor and now describes the intent-aware one.

**Both budgeted files paid for their own correction.** `methodology/building.md` and
`skills/critic/SKILL.md` each grew past its ceiling and each came back under it by trimming rather
than bumping — a `prawduct-hook disposition` signature and a consolidate rule the session digest
already injects, in the first; four restatements inside the exit-3 paragraph, in the second, one
of which ("it names the free files") this change had just made wrong. `building.md`'s correction
came out at exactly its recorded size. Its ordering rule is a POINTER to `review-cycle.md`, not a
fifth restatement — which is the finding below, applied to itself.

**The refusal path was not the only return that walked past its own notes.** Every `error` return
did too, and `scope-widened` is the one that reaches its `return` with notes populated — it fires
exactly when the tree has grown enough that what the dispatch noticed about it is worth having.
The CLI now prints notes before the reason on that path as well.

The five carriers were corrected but not collapsed; **#723** carries the construction that would
make correcting this rule a one-file edit. Three reviewers independently landing on different
carriers of one rule is what says it is a class.

Upstream report: #722.

## 2026-08-26: a plan the deliverable check cannot grade says so at dispatch

<!-- prawduct: type=fix | scope=silent-governance-failures -->

Two plan shapes disabled the chunk deliverable check for a plan's whole life, and neither said
so where it happened. A plan declaring no frontmatter `scope:` reported
`chunk-ref-missing unchecked — …` into the dispatch manifest, which is real but reads as a pass
to anyone who does not also read the caveat line. A plan whose chunks are list items under a
`## Chunks` heading matched no heading pattern at all, so `_chunk_ref_findings` returned an empty
gap and the check reported **nothing** — not even `unchecked`.

Either cause is sufficient alone, which is why an earlier fix closing the heading-shape half left
the item open. Both are now named by `critic-begin`, on the existing `PRAWDUCT NOTE:` channel, at
the moment the remedy is three lines of plan frontmatter — rather than by `check-releasability` at
release, long after the blind reviews have run.

**Advisory, deliberately.** It rides `notes`, changes no exit code and refuses no dispatch: the
review is still worth running. What is not worth having is a review that silently grades nothing
while reporting cleanly.

**The check scans when nothing resolves, and that is the main path.** Asking the resolver for the
plan and grading only its answer misses the defect entirely — a plan declaring neither `scope:` nor
`branch:` does not resolve *because of* the gap being reported, so the resolver returns nothing and
the signal goes quiet exactly where it is needed. That was caught by running a real dispatch against
a real unparseable plan and seeing no note, not by reasoning about it. Discovery goes through
`plan_index`, which owns the recursive, archive-pruning rule — and through `iter_live_plan_files`
rather than `iter_scoped_plan_candidates`, since the latter yields plans that *declare* a scope,
which is precisely what a plan missing one cannot do. Plans are named by `display_path`, not
`Path.name`: recursion is what makes `build-plan.md` collisions across `plans/<id>/` reachable, so
the fix created the condition that helper exists for. An **unreadable** plan is reported here too —
`unreadable_candidates` covers it for the doctor, its only caller, and nothing on the dispatch path
calls that, so an undecodable plan under `artifacts/` had been reported to the operator by no one.

**Two readers, two channels.** The dispatch note tells the operator; `record_lint` carries the same
fact into the review, where the `chunk_id is None` branch had returned a null count that read like a
healthy plan. It now reports the gap — but only when the plan has neither a Status roster nor a
chunk heading. Every box ticked also yields "no current chunk", and that is grading being over
rather than disabled; a first draft keyed only on the missing heading and reported the healthy case
too.

## 2026-08-26: a sentinel is graded by the product's own runner, or not at all

<!-- prawduct: type=fix | scope=silent-governance-failures -->

`run_sentinel` hardcoded `sys.executable -m pytest`. In a product that does not use pytest,
every learnings sentinel came back **failing** with "No module named pytest" — against tests
that were green. That is worse than an inert mechanism. The audit's job is deciding which
learnings are structurally enforced, so a false-failing sentinel argues for retiring a rule
that is still enforced, on evidence it never gathered.

It was an uninventoried instance of the ratified "never be specific to Python" norm, whose
fail-visible clause it also inverted: the norm says an ungraded language is reported
*unchecked*, never silently passed, and this reported *failed*.

**The remedy is declaration, on the `release_version_files:` precedent.** A product declares
`sentinel_command:` with a `{sentinel}` placeholder for the file to grade —
`sentinel_command: npx vitest run {sentinel}`. It cannot reuse `test_command:`, which names
the whole suite and would grade every rule by the suite's verdict.

**No default survives.** A pytest fallback would be the same violation wearing a default's
clothes, so an undeclared sentinel is reported `ungraded` with a reason naming the knob, and
no rule is retired on a verdict nobody took. `passed` is now three-valued and callers must
branch on identity: `True` enforced, `False` genuinely failing, `None` ungraded. A launch
failure, a timeout, and a **path-shaped sentinel whose target file is gone** all grade `None` —
a command that never started, one that never finished, and a test that no longer exists each
returned no verdict about the rule. The last of those was live in this repo: a learning had
pointed at a suite deleted in the plugin migration, and the audit reported its rule as failing.
The path-shaped qualifier is load-bearing: a runner id that is not a filename
(`com.acme.BarTest#testX`) cannot be resolved, and prawduct will not claim a file is gone when it
cannot tell "gone" from "not a path".

**A third state is only real once its consumer can name it.** `doctor` is the sole reader of
`audit-learnings --json`, and it knew two sentinel verdicts — so an ungraded one, which raises
no `errors[]` entry by design, would have been relayed as *passing*: worse than the loud-false
error it replaced. Its relay now carries the third rendering, and the ungraded `notice:` goes
to **stderr**, where it reaches the `--json` path that a stdout line cannot.

That withdraws working behaviour rather than adding to it, which the additive-first norm
normally defers to a major. In-bounds here because the withdrawal fails *closed*: an ungraded
sentinel withholds a retirement and destroys nothing, where the norm's purpose is protecting
callers from breakage. Signalled rather than silent, per the same clause — the reason line
names the knob. Keeping a pytest default alive through a retention window would have preserved
exactly the Python-specificity the architecture norm forbids, so the two norms are answered
together rather than traded against each other.

## 2026-08-24: the evidence file can say which commit it read

<!-- prawduct: type=fix | scope=pr-evidence-reviewed-commit -->

The Update Flow's substantive-delta test says to diff from "the reviewed commit" — and nothing in a
PR-review evidence file recorded which commit that was. The caller had `timestamp` and
`commits_reviewed` to work from, and reconstructing a SHA from those is right exactly until a commit
lands *during* the review, which is the one case the test exists to catch. PR #709's evidence was
written at 12:05 claiming 16 commits while its 17th landed at 12:02, inside the reviewer's own
420-second window; the file looked complete and the branch was one judgeable commit past it.

**The fix is a field the reviewer captures, not one the caller computes.** `commit_reviewed` is
`git rev-parse HEAD` at the moment the reviewer resolves its diff — the only actor who knows what was
read. A caller stamping it before dispatch would record a commit the review may never have seen, and
a caller stamping it after would record commits that landed mid-run: both directions launder
unreviewed code into the reviewed set, which is why the protocol now says the field is never
rewritten and `pr_number` is the only field backfilled after the fact.

**Absent means substantive.** Evidence from an older reviewer has no field, and the honest reading of
that is "unknown", not "unchanged" — so the Update Flow re-runs rather than reconstructing. Create
Step 4 also checks the SHA is an ancestor of HEAD, which is what catches a rebase or amend having
moved the tree out from under a review that still looks valid.

This retires `@{u}..HEAD` as the stand-in. It answered a different question — what changed since the
last *push* — and the two diverge precisely when a mid-review commit is pushed before the caller
looks. A test pins that it does not come back.

## 2026-08-24: an issue close has no branch to ride

<!-- prawduct: type=fix | scope=pr-issues-backend-close -->

`/prawduct:pr` Step 1d opens by promising that every release tag, archive and Status tick "rides IN
this branch, atomic with the merge", and then lists the backlog archive among them. That atomicity is
a property of *being a commit*. On the markdown backlog backend the archive is a file edit and the
promise holds exactly as written. On the Issues backend closing an item is an API call with no branch
to ride, and the skill said nothing about the difference — so the step read as satisfied by a PR body
that said `Closes #676`, and the item was still open after the merge.

**`Closes #N` does not fire on a gitflow base.** GitHub honours closing keywords only for PRs merged
into the repository's *default* branch. This repo defaults to `main` and PRs base on `develop`, so
the keyword is inert here and always has been. It is still worth writing — it links the PR to the
issue, and it does fire on a trunk repo — but it closes nothing on the path this project actually
uses. What makes it costly is that it *looks* like bookkeeping: an independent PR reviewer read the
keyword and signed the item off as closed-by-the-merge, so the gap survived the review whose job was
to catch it.

**Deferring the close to merge is the deliberate answer, not the lazy one.** An API close made at
Step 1d lands immediately, so an abandoned PR leaves an item wrongly closed — invisible, because
nothing sweeps for items closed too early. The Merge Flow's *Close the backlog items this PR
resolves* step owns it, firing seconds after the merge
succeeds, and Step 1d says why it is the one item that waits. No commit is involved, so the standing
"never push a bookkeeping commit to the integration branch" rule is untouched.

The guard is written against the keyword family rather than the sentence that got it wrong: any live
instruction surface naming `Closes`/`Fixes`/`Resolves #N` must name the default-branch condition in
the same paragraph. Pinning the one sentence would have closed the instance and left the class open —
the failure mode `test_backlog_instruction_surface.py` was hardened against. The surface set is bounded
by the property (prose that instructs an agent) rather than by the `plugin/` container, so
`documentation/` runbooks are in scope and append-only records are not.

**The timing rule now has one owner, which is what the review round changed.** The first cut fixed
`/prawduct:pr` and left `skills/backlog/SKILL.md` — the rule Step 1d cites *by name* as its authority —
still asserting the falsified guarantee unconditionally, so an agent following the citation landed in
the unfixed twin and did the early close the fix exists to prevent. Two reviewers found it
independently under different goals, which is the tell that the fact had been distributed rather than
shared. `skills/backlog/SKILL.md` "When to mark shipped" now owns *when* the call runs and states the
split; `/prawduct:pr` Step 1d and the Critic's reconciliation template (`review-cycle.md`) route to it
instead of restating it. A guard closes the class rather than the sentence: no live instruction surface may
state WHEN the archive happens except the owner's own rule paragraph. That exemption took two
narrowings, each from a real miss — it started file-wide, which hid a live member three sections
below the rule in the owner's own file, and then keyed on the section NAME, which re-exempted that
member the moment it routed to the owner by name. It now keys on the rule's opening clause, which
only the rule carries. A guard whose exemption is broader than its subject is not a guard; it is a
list of what it happens to catch.

**The close moved ahead of the deletions.** It was numbered after the branch and evidence-file
cleanup while its own text said "before anything else" — and those deletions destroy the only local
artifacts recording that a close was owed. It is now the step immediately after the merge, and
references to it are by name rather than by number, because a durable pointer must not ride on a
position that renumbers. The renumber broke two cross-references outside the skill —
`plugin/methodology/planning.md` and `documentation/release-process.md` both cited "merge-flow
step 7", which the insert turned into *Clean up evidence file* — and the first cut of this entry
claimed the by-name sweep was complete when it had only been done inside `skills/pr/SKILL.md`.
Both now cite the step by name. That is the rule failing on the very commit that states it: a
pointer that rides a position rots the moment the position moves, and the sweep has to be
repo-wide or it is not a sweep.

**What this does not fix, stated rather than implied.** The close step is its own only detector: merge
through the GitHub UI, or end the session at the merge, and nothing notices it never fired. The
reconciliation sweep that would catch it is already prescribed by
`documentation/backlog-service-requirements.md` **GV3** — "merged work whose item is still open… this
is the price of leaving git; pay it explicitly" — and is unbuilt. The skill says so at the step rather
than implying coverage it does not have. Likewise the prohibition on advancing `commit_reviewed` is
prose: `git merge-base --is-ancestor` passes for every commit on the branch, so it cannot see a
laundered field. The Update Flow now cross-checks the evidence file against the `review.pr` ledger
event, whose `review` payload is an independent verbatim copy — a second witness, not enforcement.

## 2026-08-23: a nested checkout is not a misplaced test

<!-- prawduct: type=fix | scope=test-location-nested-checkout -->

`git worktree add ./devchk` inside the primary checkout turned the test-location preference red for
every session in the clone. The walk found `devchk/tests/**/test_*.py`, correctly observed they were
outside `tests/`, and reported them as silently-skipped tests. They are not this checkout's tests at
all, and `testpaths` skipping them is right — but the only way to get a green suite was to delete
another session's worktree, which is exactly what a session must not do.

**The exclusion list already had this bug once and was fixed by naming the path.** `.claude/` is on
it because a worktree-isolated workflow leaves a full duplicate `tests/` tree under
`.claude/worktrees/wf_*/` (TST-9K4W). That fix held until a worktree appeared under a different name,
which is the standing failure mode of a by-name exclusion: it closes the instance and leaves the
class open. The predicate is *does this directory carry its own `.git`* — a FILE for a linked
worktree, a directory for a clone or submodule, both meaning the tests below it belong to another
checkout. It now prunes all of them, including the ones nobody has thought of.

**The risk in this kind of fix is making the check blind, so that is what the new tests aim at.**
Three cases: a linked worktree at an arbitrary path, a nested clone or submodule, and — the one that
matters — a genuinely misplaced `test_oops.py` in an ordinary subdirectory, which must still be
caught. Pruning that keyed on depth or on "has a `tests/` child" would have passed the first two and
quietly disarmed the module.

## 2026-08-23: a wedged manifest says which kind of wedged it is

<!-- prawduct: type=fix | scope=manifest-state-diagnosis -->

An operator who met a dispatch manifest written by an older prawduct was told, by the surface that
refuses `critic-begin`: *"no readable dispatch manifest — a review set the marker but never recorded
what it was reviewing. Nothing here is worth keeping."* Every clause of that is false for the case
that produces it. The manifest is readable JSON. It **did** record what it was reviewing — in the
schema of the version that wrote it, `commit_reviewed` and all. And the partials beside it are real
reviewer output that `_archive_leftovers` deliberately archives rather than deletes, naming
`critic-restore` as it goes. The message told an operator to throw away exactly what the mechanism
one function over was carefully preserving.

**The interesting part is why it recurred.** `pending_roster_reading` exists precisely to stop this:
its docstring says two surfaces "must not differ in what they say the on-disk state IS. They did:
only one of them was taught the fact, and the untaught one sits at the more dangerous surface." That
had already been fixed once. It came back because the thing being shared was the **reading**, and a
reading cannot be shared for a distinction nobody had computed — so the Stop hook's backstop
computed "unreadable or schema-invalid" for itself, `restore_refusal` computed "no readable dispatch
manifest", and the dispatch refusal computed the false paragraph. Three surfaces, three answers, one
disk. The fix is therefore a **classifier**, not a fourth message: `manifest_condition` returns
`absent` / `corrupt` / `stale-schema` / `valid` plus the validation reason and the parsed record,
and all three surfaces read it.

**`pending_state`'s `"unreadable"` collapse deliberately stays.** For *deciding* — can this be
consolidated? — corrupt and stale-schema are one answer, and four callers branch on it. Widening
that vocabulary to fix a message would have made every one of them handle a case that changes none
of their decisions. The distinction is real only when *telling someone*, so it lives with the
telling. Pinned both ways: a test asserts the collapse holds, and a test asserts the three readings
are mutually distinguishable.

**The keep-or-discard verdict is a SECOND home, and finding that out took a second round.** The
first repair routed the *reading* through one place and left two of five surfaces authoring their
own tail — so a stale-schema manifest still printed "any partials beside it are real reviewer
output" and then, four lines later, "Nothing here is worth keeping". The swept-marker variant was
the worse of the two: the marker is gone, so that notice is the only report the operator ever gets,
and one told nothing was attached will not run `critic-restore` before the archive ring evicts the
partials. A verdict authored beside a shared sentence is not shared by being adjacent to it.

So `anything_worth_keeping` owns it, and the readings now describe **the manifest and nothing else**.
That separation is load-bearing rather than tidy: the manifest's condition and whether reviewer
output exists are two independent facts, and any sentence answering both from one of them is wrong
whenever they disagree — an orphaned partial set with no manifest is exactly that disk, and so is a
stale manifest sitting alone. The first cut of the *repair* reintroduced the contradiction one layer
in, and the test written to catch it did.

**The pin took two goes to become falsifiable, which is the part worth recording.** The first
version asserted "no message says both things at once" and composed three *library* surfaces —
neither of the two hook boundary notices the finding was actually about. Worse, once the readings
stopped making keep/discard claims, "says both" became *unreachable* at those notices: reverting one
to its hardcoded "Nothing recoverable was attached" passed the contradiction test cleanly. A pin
that cannot fail is decoration, and one that names a class while covering a disjoint set is worse
than none, because it reads as coverage.

The property with teeth is not internal consistency but **agreement with the disk**: every
verdict-bearing surface must carry the exact clause `anything_worth_keeping` returns for the disk it
is describing, and must not carry the one it would return for the opposite disk. Both notices are
loaded in-process and composed under absent/corrupt/stale-schema × {0, 2 partials}; both mutations
that restore the old tails now go red.

**#676's other two acceptance criteria were already discharged and are recorded as such rather than
re-fixed.** A branch in an agent worktree has had a route to a recorded review since #648 —
`is_ephemeral_worktree` classifies by branch identity, so a named-branch agent worktree is a peer
checkout you review in place (pinned in `test_ephemeral_worktree.py`). Two agents already hold
reviews concurrently across worktrees: `.critic-active` lives in each worktree's own `.prawduct/`,
and the shared evidence store takes concurrent appends through a single `O_APPEND` write. What is
**not** covered, and is deliberately left alone, is several agents sharing one checkout with no
worktrees — per-actor governance state is a large change to serve a configuration a worktree already
solves.

**The report's headline claim was tested rather than believed, and did not hold.** A stale-schema
manifest with no marker does not wedge dispatch: `begin_review`'s in-flight guard fires on a live
marker or a complete roster, and this is neither, so it archives the leftovers under a recoverable
`unmanifested-<ts>` name and proceeds. Reproduced end to end before any code was written; a test now
pins it, because if that ever goes red the defect is a real wedge and a message fix is the wrong
repair. What the reporter experienced as a wedge was the marker, which expires on its own TTL.

**Round 6 found the widening one surface short of the defect it was named for.** R-7 widened
`json.JSONDecodeError` to `ValueError` inside `manifest_condition` so an undecodable manifest is
classified rather than thrown — and `active_dispatch_refusal`, the surface #676 was actually filed
against, was still hand-reading the file under the narrow clause to get its `id`. A binary or
truncated manifest under a live marker therefore tracebacked out of `critic-begin` instead of
printing the refusal. The regression test for the widening composed three surfaces on that disk and
not this one, which is how a construction stops one site short of its own class and its pin agrees.
The refusal now takes the classifier's already-parsed record, not a `valid` verdict.

The same shape twice more, both taken rather than dispositioned because the file's whole thesis is
that a verdict has one home: the guarded `anything_worth_keeping` call was copy-pasted at four
notices (now `_keep_verdict`, and its degraded form names the exception and an inspection command
instead of an unactionable "could not tell"), and `MANIFEST_UNKNOWN` had no production reader while
`cmd_stop` spelled the literal under a comment claiming the opposite. Plus `short_detail`'s hard cap
— the property the function exists for — was executed by every stale-schema test and asserted by
none, so deleting the branch shipped green.

A fourth of the same shape, from the same round: `cmd_stop`'s absent-manifest branch was the one of
four that asserted a CAUSE ("a dispatch crashed before writing") instead of deriving a verdict —
false on the disk `_archive_leftovers` documents, where a late reviewer re-creates the partials
directory after consolidation and the partials are all there is. The cause is now hedged to what is
known and the branch takes the shared clause. Third recurrence of this concern in this subsystem,
so it finally gets a row in `cross-cutting-concerns.md`: what keeps being shared is the PROSE, and
the fact behind it stays distributed.

**The verify round refused to mark one warning resolved, and it was right.** R-5 was scoped CLASS —
a shared read for the manifest's `id` — and the fix had closed only the site that hurt, leaving two
hand-reads standing; the review checked rather than took the claim. `manifest_review_id` is now that
read, with `MANIFEST_ID_UNAVAILABLE` as the single excuse, and the hook's wrapper adds one sentence
only for the case the lib itself cannot be loaded — a different fact, not a second copy. The
ordering hazard the review flagged alongside it turned out to be **latent**: at
`_forced_live_sweep_notice` the id read ran first inside the same `try`, but `state` there only
selects a branch that a valid manifest is a precondition for, so no disk could show the difference.
Established by mutation, recorded in the comment, and deliberately left unpinned — a test for an
unreachable difference passes either way, which is the standard this bundle keeps applying to
itself.

**And the round after that found the class still had two members, both worse than the one it was
named for.** Enumerating the sites R-5 listed is not closing a class; re-running its search is.
`_archive_leftovers` read the manifest raw for the archive directory's name — under the narrow
`except`, on the disk that is the only reason the sweep runs at all — so `critic-begin` and
`critic-discard` tracebacked on an undecodable manifest: #676's headline failure, alive one
function over from where three rounds had been fixing it. `consolidate` had the same tuple on a
path the SubagentStop hook drives, turning an exit-1 refusal into a hook crash. Both now share the
classifier's parse, and both are pinned — the totality test composes them on the planted binary
disk instead of trusting a site list, which is what let this survive two rounds.

**The round after THAT found a fourth, and it ends the site-by-site repair.** `restore_review`
matched no `manifest_path(` search because it builds its path from the archive root — and the file
it reads is the very binary manifest the previous fix taught the sweep to preserve, reached through
`critic-restore`, the undo both `critic-begin` and `critic-discard` print by name. It tracebacked
*after* the all-or-nothing copy completed, so the files were back with no verdict and the retry met
the "another review is in the way" refusal. The repair is the construction the reviewer asked for
three rounds ago: `classify_manifest_file` takes a PATH, `manifest_condition` is its
`prawduct_dir` form, and a caller holding a path now has somewhere to bring it instead of opening
the file. One read is deliberately left outside it — `consolidate` needs the raw record to tell its
two exit-1 refusals apart — so this is one CLASSIFIER, not literally one `json.loads`.
The two look-alike reads in the same file (findings cache, partials) were widened with it — not
because the byte sequence can arise there, but because leaving the narrow shape in place is what
re-seeded this class three times.

**The spanning review closed the class and found the notice one layer out.** Three reviewers landed
independently on the same site: `_forced_live_sweep_notice` derived its preservation clause from
the shared verdict but still interpolated the id into `prawduct-hook critic-restore <id>`
unconditionally — so on the disk that clause newly admits (partials present, nothing naming them)
the only recovery handle offered was the words "id unavailable". An operator copying it gets a
refusal, the two handles that DO work go unmentioned, and the partials the sentence above promises
are preserved age out of the archive ring unread. A predicate over the two excuse constants now
gates that line at both notices that interpolate an id — the second one is unreachable today, and
took the gate anyway because it reads the id from a different read than the state it relies on.
The unusable branch names the bare listing instead. The wrapper's own excuse
stopped naming a channel too: its `except` spans the lazy import AND the classify call, so blaming
the plugin install was a guess wearing a fact's clothes.

**And the round-by-round provenance came out of the shipped comments.** `review-protocol.md` makes
a comment narrating review ids or round numbers a deletion finding — a bare `R-6` is a dangling
pointer, since every review has one — and this branch had taken the count from 3 to ~12 while
fixing the very defects it was narrating. The reasons stay; the ids and the "first cut / first
repair" framing go wherever this branch put them, tests included. Lines that predate the branch
still carry the shape — in files this diff touches as well as in ones it does not — and sweeping
those is not this branch's job; the entry says so rather than implying a clean repo-wide grep.
Also: a manifest holding non-object JSON was being diagnosed as "written by an OLDER PRAWDUCT",
which is a provenance claim about a file no prawduct ever wrote; it classifies CORRUPT now.

## 2026-08-23: eleven instruction surfaces stop misdescribing the runtime

<!-- prawduct: type=fix | scope=instruction-surface-truth -->

A batch of backlog items selected under one lens rather than by area: **a surface that tells a
reader something false or unresolvable about this system**. Skill frontmatter, skill prose, adapter
docs, a process doc, a contract artifact, test comments. The lens is the point — each defect is
individually trivial and the class is not, because every one of these surfaces is read by an agent
as licence to act, and a wrong instruction is obeyed rather than noticed.

**The largest was a bound with no referent.** `adapter-mode.md` told the model "you never invent a
mutation path — the adapter exposes exactly the ops in the usage table", and no reachable usage
table existed: a per-op table lived in the CLI but only on an error path, printed to stderr, while
`--help` itself exited 2 as an unknown flag. That fails in the worst direction. A model that cannot
find the table does not stop; it falls back to its own notion of the op set. `--help` now prints
usage on stdout at exit 0 for every op, answered before dispatch and before flag parsing, and the
sentence cites something that resolves. The same surface gained a retry budget whose numbers are
traceable to the transport rather than chosen — the 5+ minutes a forked skill once spent retrying a
run of 503s was never the adapter's doing, it was prose that failed to bound the caller.

**Prose that reads a variable it cannot expand.** `${CLAUDE_PLUGIN_ROOT}` substitutes into hook
commands and only there. Eleven skill-prose reads through it handed the agent a path that does not
resolve — worst in doctor's install-reference check, which either declines or silently grades
against the inline list its own text forbids using. A test asserted the broken spelling, so it
pinned the defect rather than the contract; its proposition is unchanged and now checked against a
form that works.

**Two sentences that disagreed with each other.** The `pr` skill told a doc-only PR to skip four
steps and then to jump past a fifth, so whether a STOP gate ran depended on which half the model
read. And `adapter-mode.md` claimed a close records `closed_by` when the op parses only two flags,
dropping the scope in silence while the code's own docstring recorded the deferral honestly.

**Claims that decayed because a set grew under them.** The API contract artifact never mentioned a
surface its own build plan declares Exposed, so the question "what does prawduct expose, and under
what promise?" got a confidently incomplete answer. The critic skill body — payload every review
mode loads — carried no growth ceiling, and two test comments asserted that no unbudgeted payload
file remained. Both were false, both had been corrected once before and re-asserted, and a third
ceiling would have made the sentence true only until a sixth file appeared. They now state the
mechanism that survives the set growing rather than a census of it.

**Three results this batch owes as reports rather than as code.**

*The stale-step-reference closure.* The broad query returns 32 hits and cannot reach empty. The
exempt paths, named rather than skipped: `.prawduct/backlog.md` (the frozen migration snapshot,
banner-marked as deliberately allowed to diverge), `.prawduct/artifacts/archive/`,
`migration-restructure-plan.json` (whose hits are verbatim quotations of filed issues — rewriting
them would falsify the quotes), and the rest of `change-log.md`. All are bookkeeping that records
past work. Excluding them, the query returns **six hits across two files**, both under
`documentation/issues/622-*.md` — the unit is hits, as it is above, and reporting a file count there
was the same slip this batch exists to correct. Both files describe steps issue #622 would *create*
— forward specs against an open `stage:design` item, not citations of current state. Named rather
than left implied, because **both** predict `6b/6c/6d` (`622-design.md` in its file table,
`622-requirements.md` in prose), which is exactly the lettered-sub-step shape the item warns about: it is a requirements record for unbuilt work, describing an intended runbook rather than pointing at the current one, and it is exempt on that ground. If #622 ships without those letters, the record is wrong about its own outcome and is corrected there, not here. Every live citation is name-anchored.

*The Exposed-API sweep.* Four `**Exposed API:**` declarations across live and archived build plans.
One — the backlog CLI — was missing from the contract artifact and is added. One names
`backlog file-upstream`, whose chunk never shipped (its Status box is unticked and the op is absent
from the CLI), so documenting it as exposed would be the mirror defect. Two are already covered.
No live build plan carries a declaration. The item's hypothesis is confirmed: nothing links the
declaration to the artifact — the Goal-2 check verifies only that the two recorded decisions exist,
never that the artifact describes the named surface. That gap is filed, not fixed here.

*The norm-index roster.* Closed as a **roster row per unrostered pin**, never as a restatement of
the rule — a rule with two homes is a rule with one wrong one. The count in the report was low:
three pins were enforced in CI without the index knowing, not one. The closure condition is now the
set difference between `tests/preferences/test_*.py` and the paths the Enforcement table cites
being empty, which is checkable, rather than a number, which is true of any prefix of the real set.

**The batch's own lesson, earned twice.** Every one of the eleven items was partly stale and two
were wholly stale — line numbers drifted, counts undercounted, a cited precedent had been deleted,
and the runbook whose stale step references were the subject renumbered *again* during the work.
Fixes were made against the tree, never against the report; where an item turned out already
shipped it is recorded as such rather than claimed. The stale-reference item is closed by a query
whose exempt paths are named, not by a count — a count is unfalsifiable, being true of any prefix
of the real set.

## 2026-08-22: an abandoned delegate worktree is not silent

<!-- prawduct: type=feature | scope=adhoc-delegation -->

A delegated tangent hands back a branch plus an integration debt, and the agent that incurred the
debt is — by the very reason it delegated, a full context — not the one who will pay it. A debt
held only in a coordinator's context evaporates at the next `/clear`, leaving an unmerged branch
and a worktree nobody remembers creating. A session-start advisory now names that state:
`[delegation] delegate branch X is unintegrated`, with what it owes and how to settle it.

**The dispatch record is the trigger, so nothing new had to be invented.** The brief already had
to exist, and it is written into the delegate's own worktree at `.prawduct/.delegate-brief.md`
(gitignored, so it can only be there because a dispatch actually happened). Its presence plus an
unmerged tip is the whole signal — no registry, no schema, no lease, no slot accounting. It also
makes the probe **inert by absence**: a repo that has never delegated sees nothing, and so does one
whose worktrees are ordinary feature checkouts.

**Both of R12's resolutions are the same observable state that triggered it.** Merge the branch and
its tip becomes reachable from HEAD — or from the integration base, which is what keeps a
long-shipped delegate quiet after the coordinator has moved on. Remove the worktree and the brief
goes with it. Either way the next sync flips the advisory to `resolved`. The third path, abandoning
it deliberately, is a dismissal carrying its reason, kept per-clone and indefinitely — which is
also the answer to the proportionality norm's emission arm: the store records that this control
fired and which way the decision went, so it can be retired on evidence rather than defended on
principle.

**Two things it deliberately does not do.** It never reads the brief — presence is the entire
signal, and the worktree it points at belongs to another session. And it does not consolidate:
one advisory per worktree, keyed on the branch, because two abandoned delegates are two decisions
and dismissing the first must not silence the second.

**One change reaches every governed product, not just this feature:
`prawduct-hook advisory show` now prints an advisory's `alternative_actions`.** The field had been
set by five probes and rendered by nothing — the briefing prints one action per advisory by design,
and the drill-down did not print them at all. `show` is where an alternative belongs, so the field
is now live everywhere rather than being deleted from the probes that set it. One cosmetic
consequence: the norm-health advisory's Health Check #14 route was moved into its `trigger_summary`
back when the field was inert, so `show` prints that route twice until one copy goes.

## 2026-08-22: the backlog instinct gets a third option

<!-- prawduct: type=feature | scope=adhoc-delegation -->

The delegation question has two moments. The first is a tangent arriving mid-chunk, which the
always-injected digest now names. The second is quieter and much more common: an agent has decided
some work is not this cycle's and reaches for the backlog. `/prawduct:backlog add` is the one
stopping point that already fires at exactly that instant, so it is where the question goes —
**delegate it, do it now, or backlog it**, said out loud, with the delegate's cost attached (a
branch plus an integration debt, and how many ad-hoc branches are already awaiting integration).
Filing becomes the third answer instead of the default. The judgment stays in
`methodology/delegation.md`; the skill carries the trigger and a pointer.

**The bound is the feature.** The prompt fires only when the item describes work **in this repo
that is ready to build** — the same bar the digest's mid-chunk trigger uses, deliberately, so the
two prompts state one rule rather than two. Everything earlier files silently and unchanged: a
one-line idea, a research question, anything at an earlier `stage:`, and anything with no `stage:`
at all. So does work you cannot open a worktree on, and any non-interactive machine call — the
Critic files findings, it does not dispatch. This is not caution about scope creep; it is the
feature's own discovery naming defensive asking as its live risk. A prompt that fires on every
`add` is a prompt people route around, and a routed-around prompt is worse than no prompt, because
it also teaches the reader to skim the ones that matter. `Delegation: off` in
`project-preferences.md` silences it entirely, named inline rather than left behind the pointer:
this step instructs, and a skill that never reads the guide would otherwise propose delegation in a
repo that had declined it.

**A gap found by reading the surface as its own reader.** The prompt needs to know whether an item
is ready to build, and `add` could not tell it: `stage:` was a canonical field that `import`
inferred and triage backfilled, while the one path that *creates* items never set it and did not
even accept `--stage=`. Every item `add` filed was therefore born not-ready — including one the
agent had just judged ready enough to offer delegating, which `pick` would then refuse to present
as buildable. The adapter's `file` op had taken `--stage` all along; only this prose omitted it.
`add` now accepts the flag and stamps the field the way `import` already infers it, leaving it
unset when genuinely unclear.

**One prompt, two `add` procedures — the half the first draft missed.** `SKILL.md`'s `### add` is
the markdown-backend path; once `backlog_service_repo` is set, `adapter-mode.md` carries its own
end-to-end `### add` that *replaces* it rather than adding to it — it re-states the dedup step for
itself, which is the tell. So the offer as first written was silent on the backend this repo
actually runs, which is precisely where the acceptance criterion pointed. There is still exactly one
statement of it: `SKILL.md` now declares step 2 backend-independent (the question is about the work,
not about where the item lands) and the adapter path routes to it, translating only the two halves
that are spelled differently there — `--stage`, and an in-flight mark that is
`status --to in-progress` plus `--working-branch` rather than `accepted-by:`.

Guarded by eight cases pinned beside the doctrine's own, not in a backlog module — the shared bar is
a fact *between* carriers, and a guard reading one of them cannot see them drift apart. They assert
placement rather than wording: the offer sits after the dedup and before the append, because before
the dedup it proposes delegating work already tracked, and after the append the item exists and the
reflex has already won. Each was mutated red against the real files before being believed — one
passed its first mutation and was tightened: `ready to build` appeared twice in the region it read,
so stripping the bar out of the offer left the assertion satisfied by a neighbouring sentence.

## 2026-08-21: the clear verdict accounts for a delegate

<!-- prawduct: type=feature | scope=adhoc-delegation -->

An ad-hoc delegate dies with the session that dispatched it. Its branch is unfinished, its report
unread, and nothing regenerates it but re-running the work — so the standing block's clear verdict
had to account for it, and the always-injected digest said the opposite: an unread background agent
was `RUNNING`, never `COMPLETE`, and nothing at all about whether you could clear beside it.

**The rule is stated on the test, not as a blanket.** `RUNNING` alongside `SAFE TO CLEAR` is
legitimate, and for work a clear leaves alone it is correct — the earlier draft of this rule
over-blocked by making every in-flight thing `DO NOT CLEAR`, which would forbid clearing beside any
regenerable background job. What both cases actually answer is **recovery cost: does a clear leave
the work alone?** A background job it does; a delegate it does not. So an unreaped delegate is
`DO NOT CLEAR`, a reaped one is `SAFE TO CLEAR` the moment its integration debt is recorded, and
the record — not the reaping — is what buys the clear. `reflection.md` now names the general test
rather than only the live-review special case it used to carry, which is the gap that let this repo
get the verdict wrong twice in one session, in opposite directions.

**Reaping is a boundary step, and that placement is the rule.** It joins the work-cycle close as
its first item, ahead of persisting decisions, because the debt is one of the things that then gets
persisted. It is deliberately not an interrupt: a mechanism that exists to protect focus must not
become the thing that breaks it.

**The digest budget, measured rather than assumed.** The plan required the trim to run first and
report what it recovered. It recovered **17 words / 22 tokens**, against 42 words / 55 tokens of
additions, for a measured net of **+33** on both injected shapes — so the shortfall is a
**declared raise**, +22 on the framework ceiling and +25 on the product one, the first this table
has taken.

What the trim cut was a class, not a rewrap (a word-count estimator returns nothing for rewrapping):
prohibitions restating what the same bullet already requires positively. "Burying, padding or
collapsing it fail alike" forbade three things the bullet had already required — "last, after every
other word" *is* the anti-burying rule and "three separate paragraphs" *is* the anti-collapsing one
— so only padding and the reason survived, folded into the opener. That is an in-place dedup, the
only kind that is honest on this surface: funding a digest cut against an on-demand guide is a
deletion for the reader who never opens one, and that reader is why the digest exists.

Of the additions, +12 was mandatory at any budget (the digest's own rule contradicted the feature)
and was found as a rewording — the delegate joins the findings-only clause, which already said
"not `SAFE TO CLEAR` until it is on disk", rather than opening a second one. The +43 is the
decision: a mid-chunk tangent trigger, the one moment nothing else in this plan reaches, since the
backlog prompt only fires when the instinct was already to file something. Its ready-to-build
qualifier is the guard against becoming the prompt people route around, and it is the same bar the
backlog prompt will fire on, so the two state one rule. The counter-case is recorded at the
ceiling: 43 tokens are paid by every session of every governed repo forever, and reverting is a
three-line cut that lands back under the old ceilings.

**The token ceiling was never the binding budget, and finding that out is the durable part.** The
digest is emitted as SessionStart `additionalContext`, which Claude Code spills to a file above
**10,000 characters** — a hard harness threshold, not a policy ratchet, and raisable by nobody. It
had 216 characters free at this branch point; this change wanted 228, and the first draft went 12
over while every assertion in the token-budget module was green. The two budgets lived in separate
test modules with no reference between them, so a careful accounting against one could not see the
wall it was walking into. The additions were shaved to fit and the token-budget table now says so
at the top, because the next editor will do this arithmetic against the same blind spot. Real
headroom after this chunk is 12 characters and, by the ratchet, zero tokens.

**One test was fixed rather than satisfied.** A pure rewrap — no word added, removed or reordered —
split `never ask / whether to prepare` across two lines and turned its pin red. The pin was matching
raw substrings, which makes the fill width part of the contract; two sibling pins in the same class
already normalize whitespace for exactly this reason. Normalized, with the reason at the assertion.

## 2026-08-21: the delegation question, for work no plan anticipated

<!-- prawduct: type=feature | scope=adhoc-delegation -->

The delegation guide answered one trigger: a partition drawn while a build plan is being written.
The other one is an interrupt — a tangent the user raises mid-chunk, or work you were about to
propose backlogging — and it arrives when no plan exists to partition. `/prawduct:methodology
delegation` now carries both.

**The reframe that makes it more than a spawn mechanism.** Under the rule that the coordinator owns
integration, a delegated tangent is never *done*: what comes back is a branch plus an integration
debt, and the reason you delegated — this context is full, or nearly — guarantees the agent that
incurred the debt is not the one who will pay it. So coordination has to be a role recorded on
disk rather than an agent held in memory. A debt living only in the dispatching agent's context
evaporates at the next `/clear`, leaving an unmerged branch and a worktree nobody remembers
creating.

What the section states: the decision is three-way and made once, out loud — do it now, delegate
it, or backlog it, sorted by *would you integrate this today if it came back green?* Delegation is
offered first, and that default is a policy setting, so `project-preferences.md`'s `Delegation` row
still governs and `off` means the proposal is never made. Requirements come first absolutely, by
exactly four paths and no fifth, and a delegate's own drafted requirements come back marked
**proposed** — a branch's existence is not ratification. The brief is written into the delegate's
worktree, which makes the artifact that had to exist anyway the dispatch record, with no registry,
schema or lease added. And nothing is dispatched that this session cannot reap.

**`building.md`'s delegation section got smaller while gaining the trigger.** What funded it was
the pointer's own table of contents: it enumerated the headings of a file the same sentence tells
you to open. What replaced it is the discriminator a reader actually needs — the guide is the
judgment, that section is the mechanics.

## 2026-08-21: a `closed-by` handle names the work, not its slot in a plan

<!-- prawduct: type=fix | scope=backlog-metadata -->

`closed-by: Chunk 04` names no plan and means nothing to a reader a year out; `closed-by:
eval-system-rebuild` still says what shipped the item. Principle 13 already stated the governing
test — *will this reference still resolve, and mean the right thing, once the thing it names has
moved?* — and licensed a form that fails it one sentence apart. The bare chunk id is now
non-conforming across all four surfaces that carried it: the norm's home in `docs/principles.md`,
the backlog skill's metadata-bar spec and its `update` rule, and the ship-in-the-closing-PR
instruction. `building.md`'s mutable-id exemption list loses `closed-by:` entirely — once the
handle has to name the work, there is nothing left to exempt.

**Consumers who already wrote `closed-by: Chunk NN` handles have non-conforming ones.** Nothing
rewrites them and no gate rejects them; they are stale references that will not resolve, and the
repair is to re-point each at the work (a feature scope, a branch name, a release) the next time
its item is touched.

## 2026-08-21: one place knows what a finding's title is called

<!-- prawduct: type=fix | scope=delegation -->

The same sentence travels a review pipeline under three keys — `name` in a reviewer's partial,
`title` once consolidation writes the review fact, `summary` again in the derived
`.critic-findings.json` a human reads. Every reader downstream of a rename re-derived that chain
itself, and five comments pointing at each other were the only thing carrying the contract. That is
a countdown, not a redundancy: the reader that forgets writes `title: null` into the record a
disposition is checked against, which had already happened once.

`evidence.finding_title()` is now the one place the aliases are known, and the three readers in
`dispositions.py` and `critic_consolidate.py` call it. **Deliberately additive.** Keeping the key
stable at the projection would have been the deeper repair, but `.critic-findings.json`'s `summary`
is a published shape with consumers outside the module, so the accessor closes the alias class
without moving anything a consumer reads.

Found by the Chunk 04 cumulative review (R-8) rather than by the delegation work itself; it ships
here because that is the review that caught it.

## 2026-08-21: a project can say how it delegates, in its own words

<!-- prawduct: type=feature | scope=delegation -->

The delegation guide states one default and a set of considerations, and stops there on purpose:
prawduct cannot know a consumer's test regime, so it does not invent one. That leaves a gap the
sweep measured exactly — the right rule was stated by the owner three times, in three sessions, and
never became durable anywhere. `project-preferences.md` now has the three rows it should have
landed in, and `/prawduct:doctor` has the route from a practice a repo already runs to a row the
next session reads.

**The rows are prose, not a schema.** `Delegation` says how much this project wants fanned out and
what for — `off` is a complete answer, honoured without ceremony. `Delegate verification` says what
a delegate here may run to prove its own change and what it must leave to the coordinator's
integration run, in the project's own words. `Delegation approval` is where a durable yes lands, and
it is what stops the partition ask returning with every plan.

**The proposal is derived from the repo or it is not made.** Health Check #18 reads what the repo
already encodes about running part of its suite rather than all of it, quotes the repo's own names,
and says which file each came from — so the owner checks a claim instead of trusting a summary.
Where it finds nothing it proposes nothing: a proposal that fires everywhere carries no information,
and `docs/norms.md` already names the cost from this repo's own orphan-term hook — a probe that
misfires trains its reader to ignore the one real catch. Run against three real repos while
building it, the same check produced a staged runner's own stage names in one, CI jobs that run
subsets in another, and silence in the third.

**It grades nothing, and that is the design rather than an omission.** A project is free to run on
the framework default, so an absent policy is not a defect; a check that reported `degraded` until
you delegated would have mandated delegation through the grading system, which is out of scope by
ruling. Check #17 is the standing precedent for a recommendation that never touches the
classification.

**The rows are written for repos that already exist, not only for the next onboard.**
`project-preferences.md` is scaffolded once and never regenerated, so a template addition reaches a
repo that onboards after it and no other — the same reach gap that put Health Check #14 in this
file. The promotion flow adds the rows when they are absent, which is what an already-onboarded repo
has.

**Doctor now has two flows that write, and the sentences saying it had one are corrected rather than
left true-sounding.** The count was never the invariant. What survives verbatim, and is now stated
as the skill-level rule both flows obey: doctor writes only what the owner confirmed, only into
`.prawduct/` governance state, never product code. One confirmation covers the whole set — per-row
prompting is refused here for the same reason Lifecycle Convergence refuses it, because
confirmation fatigue is itself a safety regression.

**No Enforcement row ships with the template.** That table is the product's norm index and it ships
empty by design: a populated row is a homed norm, so shipping one would claim a registry every new
product has ratified nothing into. A filled delegation row takes `Critic` (prose policy is
judgment-required, so nothing mechanical can grade it) with `janitor` as its audit home, and gets
its row when the owner ratifies it.

## 2026-08-21: the record can say a run was degraded

<!-- prawduct: type=feature | scope=delegation -->

`.prawduct/.test-evidence.json` could record a green for a run that silently dropped part of its
suite. A test worker that dies under contention is typically not re-queued and does not fail the
run: the process exits 0 and reports a plausible total, so nothing in the counts separates it from
a clean pass and every gate downstream believes it. The evidence record now has the vocabulary to
say otherwise — an optional **`degraded`** field carrying the reason, set by
`test-evidence record --degraded "<what did not report>"`.

**The record carries the observation; it does not derive it.** A JUnit report has a *reported*
count and no notion of what was *collected*, so the comparison that would catch this is not
available from the report. Comparing against the last recorded count is noisy on every legitimate
test-count change, and parsing a runner's summary text needs per-runner knowledge the framework
deliberately refuses to hold. The coordinator can see the box; it supplies what it saw. This is the
boundary the design draws throughout: everything touching a consumer's test system stays guidance,
and the record prawduct owns is inside the line — no guidance to a coordinator can fix a record the
framework owns.

**Presence is the flag**, so a degraded record cannot exist without saying why, and a blank reason
is refused by the schema rather than ignored — a reader that skipped it would read the run as
clean, which is the outcome the field exists to prevent. An ordinary record omits the key entirely
(never `false`), which is what keeps every record written before the field existed behaving exactly
as it did.

Both evidence readers refuse a degraded record, in one shared body: a run that dropped part of its
suite is not evidence for "may this session stop re-running the suite" and not evidence for "did a
run ever meet this tree" either, so session-freshness and the base-advance transfer have to agree,
and refusing in the prologue they share is what makes them. `--no-rerun` **carries the flag
forward** — a restamp reuses the prior counts and so inherits what they failed to cover; without
that, one command that runs nothing would launder a degraded record clean. Only a real run clears
it, which is also the escape that keeps the field from being a trap.

**A degraded record is schema-valid and gate-refused**, which is the sharpest place those two
verdicts part company: `validate-evidence` accepts it — it is a schema check, and rejecting a
well-formed record would answer a question nobody asked — but names the flag in its output so no
caller reads the record as healthy. The `record` summary line does the same, because counts print
identically whether or not the run covered the suite, and that typographic identity is the surface
the flag exists to correct.

`plugin/methodology/delegation.md`'s **unattributable green** anti-pattern now carries the route.
It was the one anti-pattern in that list whose remedy was not a judgment call, and a coordinator
who caught themselves accepting an unattributable green had nowhere to go.

## 2026-08-21: the delegation question arrives where the coordinator already stops

<!-- prawduct: type=feature | scope=delegation -->

Guidance-only is what already failed — `building.md` has said "when chunks are independent and
parallelizable" the whole time, and delegation ran at 0.34% of 31,220 tool calls. So the question
moves to where the coordinator is **already stopping**, which is the load-bearing bet of this whole
design and is falsifiable: re-run the transcript sweep in a few build cycles and it answers
directly.

`plugin/methodology/planning.md` gains **`### Partition: Serial or Delegated`**, inside Build
Planning, because chunk boundaries are the last moment before any brief exists at which the whole
partition is visible at once. Its plan-time form of the question is *what would prove this chunk on
its own?* — the verification bound is a property of the chunk rather than of a brief, and a chunk
nobody can answer for is not scoped tightly enough to hand to anyone, which is a finding about the
chunk and worth more than the estimate it replaces.

The decision is **recorded either way**, in a new plan-level `partition:` frontmatter field that
`plugin/templates/build-plan.md` now carries filled in. "Serial, because X" is an answer; what the
field catches is not serial work but *unexamined* work.

**Disclosure and consent are deliberately asymmetric**, because informing is cheap and asking costs
a round-trip. A plan that will delegate discloses how many delegates, isolated worktrees or the
shared one, what each touches and what they will not do — carrying what varies between plans,
since a disclosure that could be copy-pasted from the last one stops being read. Approval is asked
only on one of **four enumerated reasons**, against three standing negatives, and absent a listed
reason the plan discloses and proceeds. The closure is the point: an agent resolving a vague
condition asks defensively every time, which is the cost the asymmetry exists to avoid. On a yes,
the offer to promote it to a `project-preferences.md` row lands at the one moment the answer is
fresh.

`building.md` takes the second placement the requirement names — a **chunk close** — since it is
the only file a coordinator reads there. Its delegation section re-raises the partition question
and names the field; the *why* stays in the guide it already points at. Paid for in place: "then
the combined suite and Critic" was a third statement of what "What stays in the main agent" owns
two paragraphs down. The ceiling did not move, and the file is back to one token of headroom.

## 2026-08-21: delegation becomes a guide an agent can reach

<!-- prawduct: type=feature | scope=delegation -->

`plugin/methodology/delegation.md`, which `/prawduct:methodology delegation` opens. It leads with **when to
delegate**: the default is to delegate when the same work finishes in less wall clock and the
delegates will not fight each other, with the cases that override it, the cases that defeat it, and
the route to the project's own policy. Then what a delegate is for (it verifies what proves its own
change and nothing beyond it; the coordinator owns integration and all governance), the
considerations as questions, seven anti-patterns each with the tell that makes it fire, and what a
brief must say.

**The default is the part that had to exist**, and it arrived by owner review rather than by
design: the guide as first built answered *how* to delegate and never *whether*, and
`building.md`'s permissive "when chunks are independent and parallelizable" — in force for the
entire measurement that found delegation running at 0.34% of 31,220 tool calls — is now that
default instead. An agent with no default answers "should I delegate?" by not delegating, which is
the one thing a list of questions cannot fix. It states **no mechanism**: no lease, no slot accounting, no
framework-defined test tiers, and it names no consumer's command, runner or marker — the
coordinator can see the machine, the project and the moment's load, and a framework distributed to
every governed repo cannot. Rulings and the transcript sweep behind them:
`.prawduct/artifacts/delegation-and-verification-cost-discovery.md` §6-7.

Routing lands at all four sites of `skills/methodology/SKILL.md` at once — the frontmatter
description, the argument-hint, the topic list and the overview's phase list — because a
three-of-four edit is the predictable miss and each omission fails differently and quietly. A test
now asserts the four per topic rather than searching the file for the word.

**The budget note is the part worth reading.** `building.md`'s ceiling had been raised 4718 → 4800
earlier on this branch, to buy the verification-ceiling rule its *why*, without first auditing for a
removable class — which the standing learning requires ("cut the class, not the words; what looks
unaffordable is usually history"). The audit was run here and found one: rules the always-injected
session digest states in full, restated in `building.md` beyond the part only that file owns. Three
instances, checked per item rather than assumed, gave back 53 tokens; the pointer to the new guide
spent 40. The ceiling is **ratcheted 4800 → 4775** with the cut, because slack left behind is a loan
the next edit collects silently and green.

## 2026-08-20: v3.4.0 is cut, and develop reopens on 3.4.1-dev

<!-- prawduct: type=chore | scope=release-v3.4.0 -->

v3.4.0 shipped: fourteen release-pending scopes, all of them, no pruning — `main`'s tree is
`develop`'s and `check-released v3.4.0` reports 3 of 3 verified. The version decision (minor rather
than the norm's default patch) and the classification table are in
`.prawduct/artifacts/release-plan-v3.4.0.md`; this entry records the cut, not the reasoning.

**Two things in the cut were judgement rather than procedure, and both are worth the next cutter's
attention.**

The prerelease section still carried its seeded `**Prerelease under test …**` placeholder as its
first non-empty line, which is the exact line `banner.py` shows every upgrading consumer. Phase 1
step 10 says to replace it; it had accumulated eight weeks of notes underneath and nobody had. The
step is doing its job — but the failure mode is silent, because a section full of good notes reads
as a finished section.

The headline took three drafts and **each rewrite fixed a different defect**, which is why it is
worth recording as three rather than as one.

*Draft 1* led with the measurement (29–120 s per call, nine calls, the 2-minute ceiling) — the
release plan's framing, which is an argument for *cutting* addressed to the maintainer. **The release
plan's "why cut this" and the CHANGELOG's "what you get" are different documents for different
readers, and copying the first into the second is the default mistake.**

*Draft 2* — "Governance gets out of your way. The review gates are 57× faster" — was the more
expensive error, and it was **factually wrong in the direction that flatters the release**. 57× is
the *gate check*, the question "does this need a review". The review itself costs exactly what it
did. The owner caught it against lived experience: reviews are still slow, so the sentence promises
something the consumer will immediately find untrue. A benefit framing does not license a wider
claim than the measurement supports, and the tell was that no number in the release could be
attached to the sentence actually written.

*Draft 3* names the check rather than "the gates", states *the review itself is unchanged* inline,
and drops to `benefit, because reason` bullets. **Residual, stated rather than left to be
discovered:** draft 2 shipped in the tag's tree for the window between publish and correction, so
any repo that installed inside it sees the over-promise once in its banner. The Releases page was
edited, and `develop`'s digest carries draft 3, so every later reader crossing 3.4.0 gets the
corrected text — but a published banner line cannot be recalled, only outlived.

Also taken here rather than deferred: `tactical-efficiency` — nine change-log entries, the
verdict cache and the base-advance transfer, the release plan's own stated reason to cut — had **no
consumer-facing notes at all** in `plugin/CHANGELOG.md`. The rolling-notes model accumulates what
someone remembers to write during the cycle, and nothing checks the accumulated set against the
shipping scope list at the cut. `check-releasability` enumerates the scopes; nothing asks whether
each one reached the public digest. That is a real gap, filed rather than fixed mid-cut.

Reopened on `3.4.1-dev` — low guess by the runbook's rule, since every possible next cut is then a
forward move for a develop-pinned consumer.

## 2026-08-19: the escape hatch stops recommending the deletion this release guards against

<!-- prawduct: type=fix | scope=critic-reliability | release=v3.4.0 -->

The Stop hook's abandoned-review blocker prints an escape hatch for the case where a review
genuinely cannot finish this session. It said:

```
rm .prawduct/.critic-active
rm -rf .prawduct/.critic-partials
```

**The states that print that string are the states holding reviewer output.** There are four —
`consolidation failed`, `incomplete`, `not completed (no manifest)` and `unreadable manifest` —
reached through **three** `+ _escape` sites, since the `else` serves both of the last two. On
`consolidation failed`, every reviewer has reported and the set is one deterministic consolidation
from being recorded; the Stop hook's own backstop runs that step. The recipe deleted it, unarchived,
and said nothing about what was lost. (`none` is the exception, and it is the argument for one safe
recipe rather than two: there may be nothing on disk to lose, and the operator cannot tell which
state they are in from the message alone.)
That is precisely the loss `boundary_sweep`'s roster question and `write_marker`'s guard were built
this cycle to prevent — so the release was about to ship the protection and the contradicting advice
together, which is worse than shipping neither, because the operator now has reason to trust the
mechanism.

The hatch names `prawduct-hook critic-discard` instead. It reaches the same end state — marker
cleared, partials out of the way, next dispatch unblocked — and archives rather than deletes,
printing the `critic-restore <id>` that brings the review back **as itself**. The deferred worry
that it might not survive the wedged states does not hold: `_archive_leftovers` reads the manifest
raw *because* it must also work when the manifest is unreadable, and falls back to an
`unmanifested-<stamp>` name. All four states archive.

**Pinned as a class, because the defect is one.** Say why it broke in one sentence — *one shared
escape string is appended to four branches, each reached only when reviewer output exists* — and
that sentence names the string, not any branch. A per-branch assertion would leave the next branch
someone adds free to reintroduce the recipe. `TestTheEscapeHatchNeverDestroys` drives all four
wedged states and asserts the property on whatever each emits: names `critic-discard`, contains no
hand-delete of either file, and still names the waiver (the hatch has two halves, and only one of
them changed). A sweep of the plugin, docs and runbooks confirms the escape hatch was the class's
only remaining home.

**Two assertions were deleted, and that is a correction rather than a relaxation.** The old test
asserted `rm .prawduct/.critic-active` and `rm -rf .prawduct/.critic-partials` were present — it
pinned the defect, exactly as `test_resume_still_sweeps_a_stale_critic_marker` once pinned the
sweep this cycle removed. Checked by reverting the recipe: both new pins fail against the shipped
v3.3.4 string and pass against the fix, so they discriminate rather than pass vacuously.

**The review found the class had no construction, and that is the durable half.** Guidance
sanctioning the bare delete has now been fixed at three surfaces in three commits this cycle — the
marker-refusal remedy, `lib/critic_marker`'s own prose, and this `_escape` string — each pinned only
where it was found, so each fix left the next surface free. `TestNoShippedSurfaceSanctionsTheBareDelete`
derives its subject from the tree instead: every shipped file under `plugin/`, matched on the act
rather than a spelling, failing on a surface nobody has thought of. One exemption, `plugin/CHANGELOG.md`,
because a release record quotes what was removed and that is not advice — and a second test asserts
that exemption stays one file, since a growing list is how the class would quietly reopen. The pin
caught this entry's own consumer-facing twin on its first run, which is the behaviour wanted.

**`critic-discard` stops reporting success on the one path where it destroys something.**
`_archive_leftovers` returns `None` for three outcomes, one being *an `OSError` hit mid-archive, so
I degraded to delete* — and the command read that single `None` and printed `nothing to discard (no
partials on disk)`. The three are worth naming, because two look alike and cost opposite things:
nothing was there; the directory could not be *read*, so nothing is archived **and** nothing is
deleted; or the archive's `mkdir`/`rename` failed, which degrades to delete and completes it. Only
the last destroys anything. Tolerable while this was a command you went looking for; making it the printed
remedy in states that hold reviewer output is what promoted it. A `had_partials` read taken BEFORE
the attempt separates the no-op from the loss; each failure path says what it actually cost —
deleted-with-nothing-to-restore for the degrade, still-on-disk-fix-the-permissions for the
unreadable dir — read off the POST-state rather than guessed from a return value that cannot tell
them apart; and the underlying diagnostic names the command the operator actually ran instead of
hardcoding `critic-begin`. The clean path also states the restore window — an undo with an unstated
eviction bound is one you learn about too late.

**That guard's first cut held for one function and not for the path, which the review caught.**
`_archive_leftovers` stopped raising on an unreadable directory; `remove_partials` ran the identical
unguarded listing one line later, so every input reaching the new guard hit an unhandled raise
immediately after it — and did so *after* the caller announced the partials were deleted and
*before* the marker was cleared. Strictly worse than the bug it replaced: told the destructive thing
happened, still wedged. Every `iterdir`/`glob` over the partials and archive directories now sits
inside an `OSError` guard, and the pin drives `critic-discard` against a `chmod 000` directory
rather than unit-testing either function, because either passes alone while the path is broken.

Also here: `tests/test_session_boundary_events.py`'s two stale prose claims, which the previous
cycle deliberately deferred to the next commit touching `tests/` — this one. It named `rm` as one
of the marker's three recoveries (the third is an explicit named act: `critic-end`,
`critic-discard`, `clear --force`), and its module docstring still stated the TTL-alone sweep rule
that `boundary_sweep` replaced with a two-question one.

## 2026-08-19: an expiring Critic marker announces itself, and never discards a self-heal

<!-- prawduct: type=fix | scope=critic-reliability | release=v3.4.0 -->

Two field reports in one mechanism, both created by making the 30-minute TTL the **sole**
liveness verdict at a session boundary.

**The session boundary was throwing away finished reviews.** The Stop hook's abandoned-review
backstop does not merely block on the `.critic-active` marker — it *consolidates* a review whose
reviewers have all reported, keyed on raw marker presence with no TTL at all. An expired marker is
exactly the state that reaches it, and the boundary sweep deleted that marker first. The longer a
review ran, the likelier it was to lose its own findings. `boundary_sweep` now asks two questions
instead of one: the TTL answers *is the dispatching process gone*, and the roster answers *is there
anything left to finish*. A complete roster is retained at any age. The two halves each passed on
their own while the pair was broken, so the pin is a multi-hop one —
`test_a_complete_roster_kept_by_the_boundary_still_self_heals` drives the boundary and then the
Stop hook that has to still find it.

**And the sweep no longer happens in silence.** Sweeping is the branch that destroys something, and
it destroys the only handle any later gate has on the review — so after it, nothing else will ever
raise the subject. The notice is therefore the whole signal rather than a courtesy on top of one:
it names the review by id, says what was on disk, and says plainly that the abandoned-review
blocker will not fire for it again. A retention was already announced; the destructive branch was
the quiet one.

**Sharing a reading means it has to be true at the surface that just acted.** Both notices compose
through `pending_roster_reading()`, the one home for what a pending roster MEANS — and the
`incomplete` reading said "a `/clear` retains the marker; it does not release it", true of every
surface that existed when it was written and false at the one added here. Read as an operator, the
sweep notice said *waiting is safe* three lines above *the marker is gone*. The clause now names its
condition. This was found by running the announcement, not by reading it.

**The TTL was NOT re-priced, and the reason is the deliverable.** #692 asks for a value grounded in
the review-stats distribution. That grounding is unavailable: `duration_seconds` is self-reported by
the reviewing agent and a coordinator review records `max()` across its partials, while marker
wall-clock age — the quantity the TTL governs — spans dispatch + every reviewer + consolidation +
coordinator turn latency, so it is strictly longer than any self-report. No recorded review exceeds
the TTL and that margin is *not* evidence; it is an artefact of comparing two different quantities.
The derivation is committed at `.prawduct/research/critic-liveness-2026-08-19/measure.py` — cite the
command, never its digits. The reasoning now sits at the constant itself, where anyone reaching for
that re-price will land. What makes the number tolerable is that expiry no longer decides alone.

`write_marker`'s docstring claimed an over-running review could "renew its own protection". Nothing
renews a marker mid-review — `critic-begin` is the only writer, so the timestamp is a dispatch time
and the TTL is a deadline, not a rolling window. The claim is reconciled to the code and pinned
structurally, because a prose claim about how many writers exist stops being true the day someone
adds one.

**The rule had a second home, and the review found it.** `boundary_sweep` was taught to keep a
complete roster; `review_active` went on unlinking an expired marker as a side effect of
*answering*, so a bare `prawduct-hook clear` — the invocation the guard exists for, and the one a
reviewer subagent actually ran in the incident behind it — destroyed exactly the review the
boundary now protects. `review_active` is a pure predicate now: asking is free and changes nothing,
one function decides whether a marker may go, and both surfaces that meet one without forcing share
that call and its notices. Removal otherwise happens only by name — `critic-end`, `critic-discard`,
a successful consolidation, `--force`. Two reviewers found this independently from opposite goals,
which is the argument for the enumeration below rather than against it: the inventory NAMED the
site and pointed it at a test covering only the live case.

**One sanctioned `rm` survives, deliberately.** The Stop hook's escape hatch still prints
`rm .prawduct/.critic-active` / `rm -rf .prawduct/.critic-partials`, and it is reached from the
consolidation-FAILED branch — the complete-roster state this entry exists to protect. Swapping that
recipe for `critic-discard` needs the command verified against the wedged states first, so it is
deferred to **#604** rather than changed blind here; recording the residue in the narrative, not
only in a commit body, is what keeps it from reading as an oversight. `tests/test_session_boundary_events.py`
still names `rm` among the marker's recoveries for the same reason and rides the next `tests/` commit.

**The readers are enumerated rather than argued safe.** Twice, a change here was reasoned safe from
the `clear` guard alone and twice the reader that broke was outside the session. A test now scans
the plugin for every site that calls the marker API or names either file, and fails on any site the
inventory does not list together with the test that exercises it — 26 sites, `briefing`'s findings
summary among them. Adding a reader costs one line and one test, which is the point.

## 2026-08-19: tree capture stops re-hashing the world

<!-- prawduct: type=fix | scope=critic-reliability | release=v3.4.0 -->

`capture_tree` seeded its temporary index with `read-tree HEAD`, whose entries carry **zeroed stat
data**. Every tracked file was therefore a cache miss and `git add -A` re-hashed the entire working
tree on every single capture. On a local disk that is waste; on the bind-mounted tree #675 reports
it is fatal — each read pays mount latency, the capture blows through its budget, `critic-begin`
fails, and with it the PR gate becomes structurally unsatisfiable, because no review can record.

The seed is now a copy of the repo's own `.git/index`, whose stat data lets `add -A` skip the files
that did not change; `read-tree HEAD` stays as the fallback when no index can be copied (a clone
that has never staged, a concurrent git mid-rename, a copy that died part-way). The cost and the
seed-agreement claims are measured, not asserted:
`.prawduct/research/tree-capture-2026-08-19/measure.py` — cite the command, never its digits.

**The copy has to preserve the index's MTIME, and that is the sharpest thing this change learned.**
Git's stat cache skips a file whose size and mtime still match its entry; the only thing that
catches a same-tick, same-size edit is the racily-clean rule — *an entry whose mtime is not older
than the index FILE's own may have changed since it was recorded, so re-read it.* A copy stamped
with the current time makes every entry look comfortably older than its index, silences the rule,
and lets `add -A` skip the re-hash — so the captured tree carries the file's PREVIOUS content and
the review vouches for **a tree that never existed**. That is a fail-open in the evidence store,
strictly worse than the timeout it would have been traded for. It surfaced as a 1-in-25 suite flake
and was chased to cause rather than re-run; `shutil.copy2` is the fix and
`test_same_second_same_size_edit_is_still_captured` is the pin, with every timestamp forced so the
race is not left to the machine's speed.

**No degraded path is silent**, which is the other thing the review sharpened. A fallback to
`read-tree` produces exactly the original symptom — a slow capture that times out on the
filesystem this change exists for — so an operator would raise the budget, get a working capture,
and close #675 while the fix never engaged. The capture result now reports which seed it used and
a fallback says so on stderr. A refused `PRAWDUCT_GIT_TIMEOUT` is announced once per process for
the same reason: it fails *every* `run_git`, and two advisory callers (`coverage`, `record_lint`)
correctly read a nonzero rc as "no answer" and go quiet — right for a git failure, wrong for a typo
in the operator's own environment.

Every route into the slow seed reports through one place, so none of them can be the quiet one —
including the git-dir lookup failing, which was the last silent branch and would have made the
chunk's own "no degraded path is silent" criterion false. The message names the seed that
ACTUALLY replaced the copy: on an unborn HEAD nothing is re-hashed, and claiming a full `read-tree`
there would be a scarier lie than the truth.

Two smaller repairs at the same site. `PRAWDUCT_GIT_TIMEOUT` now overrides the 15-second budget,
read per call so an operator on a slow filesystem can raise it without a restart; a malformed value
is **refused**, never silently replaced by the default, because someone who set the variable wanted
a different budget and quietly restoring 15s hands them back the timeout they were trying to escape.
And a capture that is killed mid-`add` no longer leaves its lock file behind.

**A correction to the report, recorded rather than quietly re-scoped.** #675 attributes a wedged
repo to a stale `.git/index.lock`. It cannot come from here: `capture_tree` runs every git call
under `GIT_INDEX_FILE`, git takes its lock next to the index it was given, and a killed `git add -A`
was observed to leave `<tempdir>/prawduct-idx-XXXX.lock` and no `.git/*.lock` at all — with exactly
one `git add` call site in the plugin, no other prawduct path produces one either. The leak closed
here is temp-directory litter. Whatever wedged the reporter's repo has another cause, and a future
reader of #675 should not believe this fix addressed it.

## 2026-08-19: the test suite stops taking the whole machine

<!-- prawduct: type=chore | scope=clear-cadence | release=v3.4.0 -->

pytest-xdist is pinned to **5 workers** instead of `-n auto` (owner ruling). `auto` takes every
core, so a full-suite run owned the developer's machine for its whole duration — observed at a load
average of 24 on a 10-core box with a run in flight. Worker count is now a **developer-ergonomics**
setting rather than a throughput one, which is why it is a fixed number and not a fraction of
`auto`.

**Routed as a norm amendment, not a config tweak.** `Parallelization` is a `project-preferences.md`
norm with a test enforcing it, so editing `pyproject.toml` alone would have left the norm
contradicting the tree — doc-drift-to-sync, which this repo forbids. The preference row carries the
ruling, its date and its why; the test pins the new value **and** asserts `auto` is gone, since a
revert is the regression and a check for "some `-n` value" sails through it.

**CI inherits it and is therefore oversubscribed by one worker** on a 4-core runner — accepted
deliberately, not overlooked, and named at all three sites rather than denied at one. Overriding it
in `tests.yml` would put a pytest flag in a workflow that carries none by norm, and no CI timing was
measured that would justify amending *that* norm; a first attempt did exactly this, tripped the
norm's test, and was reverted rather than the norm amended. If runs begin timing out under
contention, the fix is an environment-driven count *with* that evidence.

## 2026-08-19: two tools stop losing what they were asked to record

<!-- prawduct: type=fix | scope=clear-cadence | release=v3.4.0 -->

Both found by *using* the governed path rather than by reading it, and each has a reproduction in
this branch's own history.

**`backlog` silently discarded metadata in FOUR places.** It began as a filing bug: filing writes a
fresh `prawduct:` block onto the caller's body — and the caller's body is where a filer declares
`related:`, because the docs tell them to. The two were *appended*, and parsing is last-block-wins,
so the filer's fields were dropped. The only signal was a warning that reads cosmetic: *"issue body
carries 2 prawduct blocks; using the last and ignoring the earlier one(s)."* Three items filed on
2026-08-19 (#690, #691, #692) lost their `related:` edges that way, and nothing failed.

**The class was wider than the bug, and three sweeps bounded it wrong before one bounded it right.**
The property is *a writer that persists a body's block*; the trap is `parse_block` (last-block-wins)
paired with `strip_block` (removes them all) in a writer that emits exactly one — which discards an
earlier block's fields **and** destroys the multi-block warning that was the loss's only signal.
Found at four sites: `compose_body` (filing), `upsert_block_field`, `core._body_update_preserving_block`
— where `backlog update --body` was permanently dropping an earlier block's `id_aliases`, the
alias-loss footgun that function's own docstring names — and `_related`, whose read-modify-write
computed its new list from a last-block read and wrote it over a merged one. All four now route
through `encode.merge_all_block_fields`, the property's one home. Bounding the class by *module*
rather than by property is what left the last two standing; the closure was verified by enumerating
every `parse_block` call site in the package, not by re-checking the sites the findings named.

Precedence: the caller's fresh fields win a key collision, and the attribution stamps
(`automated`/`worker`) are stripped from an embedded block in both directions — a body must not be
able to launder a background sweep into looking human, nor a human's filing into looking automated.

**`test-evidence record --no-rerun` restamped a count it had not checked.** A restamp is an operator
*assertion* that the tree's test-relevant content is unchanged since the last real run. Nothing
verified it, so a restamp taken after tests were added reused the older run's counts — a three-test
gap — and printed them as `recorded: N passed`, typographically identical to a fresh measurement.

The check is deliberately **not** a content hash (that mechanism was removed pre-v1.4 for chronic
false positives and is not back). It is the judgeable-path comparison the gates already trust, asked
against the tree the prior record ran on. Where the assertion is false the restamp is now **refused**
rather than warned — because a restamp also rewrites `evidence_tree` to the current tree, so
permitting one makes stale counts vouch for a tree they never ran against, and no downstream gate
can catch it afterwards. Where the prior record carries no `evidence_tree` (the `--from-counts`
on-ramp records none by design) nothing can be checked, and it says so instead of passing quietly.

**A capability is withdrawn, and is named rather than buried:** the documented cheap refresh after a
rename or force-add is refused whenever the prior record came from a real run, because a rename is a
judgeable path change. The escape is to run the suite or ingest a report — which is what makes the
evidence sound in the first place.

The output line was the defect surface, so it changed too: a restamp now prints `restamped: …
[REUSED from the run of <timestamp> — nothing was run]`.

## 2026-08-19: the on-demand methodology guides get size accounting, not size limits

<!-- prawduct: type=feature | scope=clear-cadence | release=v3.4.0 -->

`discovery.md`, `planning.md` and `reflection.md` now carry entries in `LAST_MEASURED_TOKENS`, and
deliberately **no ceilings**. `skills/critic/SKILL.md` was already a reading without a ceiling, so
this applies an existing shape to a class rather than inventing a control.

**The premise of the request was wrong, and the correction changed the answer.** It named
`reflection.md` as the only unbudgeted on-demand guide; measured, `discovery.md` (4752) and
`planning.md` (4301) were unbudgeted too, and `discovery.md` is *larger than* budgeted
`building.md`. So the question was about the class, and answering it for one file would have left
two larger ones in the state being objected to.

**The distinction that settled it:** a **reading** catches undeclared growth; a **ceiling** blocks
growth itself. The stated yield was undeclared growth, so the reading discharges it in full — while
these are precisely the files where growth is *cheap*, paid only by a session that opens them.
Pricing them would invert the incentive four chunks of `governance-surface-dedup` were spent
building, when the standing block's full shape was moved into `reflection.md` rather than the
always-injected digest. (`reflection.md` went 3001 → 4529 in two days as that worked.)

This is an **accounting** control, not a blocking one, which is how it discharges the proportionality
norm: it never refuses a change, only an *unrecorded* one, so "repeated firings, no blocking yield"
is unreachable by construction, and each dated entry stating its cause is the emission.

Made self-enforcing for guides that do not exist yet: `test_every_methodology_guide_is_accounted_for`
walks `methodology/*.md` and requires each to be covered by a per-file reading or by injected-shape
membership (how `session-digest.md` is priced — by shape total, twice). Nothing watched the
*directory* before, which is the blind spot that produced the request.

## 2026-08-19: a live review moves the clear verdict, and the line answers *should you*

<!-- prawduct: type=feature | scope=clear-cadence | release=v3.4.0 -->

The turn-closing standing block's in-flight rule bound only the **disposition** line — a dispatched
review is `RUNNING`, never `COMPLETE`. Nothing bound the line below it on the surface that reaches
every session, so `RUNNING` beside `SAFE TO CLEAR` was emittable, and this repo emitted that pair
three times in one day with a coordinator review live. A live Critic review now moves the **clear
verdict** to `DO NOT CLEAR`.

**The copy owes a clock, not only a reason.** Someone about to step away is not asking *may I
clear* — they are asking *by when must I check back*, which is a deadline. It is computed, never
quoted: elapsed from `.critic-active`'s `started_at`, the roster from the per-role started markers,
the expected total from `prawduct-hook review-stats` for the `critic` role and the review's mode.
Being computable is what makes this a verdict rather than a caveat, and a constant written into a
guide would be stale the moment the ledger it came from grew.

**The line also answers *should you*.** Clearing costs nothing in review coverage — the evidence
store records trees, so a plan's accumulated reviews span sessions untouched — while *not* clearing
compounds, because every turn re-reads the whole prefix and a session's read cost therefore grows
with the square of its turns. Cadence is the only control that keeps it linear. Deliberately **no
threshold and no context-fullness gate**: an agent cannot reliably measure its own window, and a
prompt that fires every turn trains the reader to skip the one turn it mattered on. That rejected
design is recorded so it is not re-proposed as-is.

**Paid for in place, and the ceilings ratcheted down.** The always-injected payload had five tokens
of headroom and is charged to both session shapes. The funding was a *class*, not a word-trim: three
section headings carried a parenthetical restating what the preamble or their own body already said.
The cut ran past the addition, so both readings finished below where the branch started and both
ceilings moved down with them — a ceiling left at its old value after a cut silently re-funds the
growth the cut paid for.

Alongside, from the review: the boundary retained-marker notice and `critic-begin`'s in-flight
refusal now share **one owner** for what a pending roster means, so two surfaces can differ on the
remedy but never on the state; and `--force` announces a live marker it sweeps — naming the review
and `critic-restore` — instead of being the one destructive path that printed nothing.

## 2026-08-19: `/clear` stops deleting a Critic review's liveness marker

<!-- prawduct: type=fix | scope=clear-cadence | release=v3.4.0 -->

A session boundary swept `.critic-active` unconditionally. What licenses deleting a marker someone
else wrote is that **the process that dispatched the review is gone** — and the boundary/continuation
split sorts `SessionStart` sources on a different question: *was the transcript restored?*

Those agree at `startup`. They come apart at **`/clear`**, which discards the transcript **without
ending the process** — so a review subagent dispatched before it may still be running. `compact` and
`fork` were excluded from the sweep for exactly this reason; `clear` was missed because it *passes*
the transcript test the other two fail.

**What went wrong when it fired.** Deleting a live marker disarms two things at once: the guard that
stops an independent reviewer clobbering the session it is reviewing, and the Stop hook's
abandoned-review backstop — which does not merely block, it **consolidates** a review whose
reviewers all reported. So a wrongly-swept marker destroyed a recovery, not just a signal.

**The fix keys on the marker, not the source.** A boundary now sweeps only a marker the 30-minute
TTL has already released. That answers the real question at every source and needs no finer matcher
— `startup` and `/clear` share one hook entry and are indistinguishable to the command. The
crashed-Critic rescue the sweep exists for is unchanged. `--force` stays unconditional wherever a
sweep is licensed: it is the operator's escape from a marker the TTL has *not* released, which is
the one case it serves.

**What retention costs, stated honestly because it is not free.** Two readers hold different
liveness predicates. A dispatch refusal keys on the TTL and is *not* `--force`-overridable, so a
dead-but-fresh marker blocks the next `/prawduct:critic` until it expires; the Stop backstop reads
raw presence and has **no TTL** at all. Both are loud and recoverable by a command the refusal
prints. That is the trade: sweeping a live marker fails *silently*, retaining a dead one fails
*loudly*.

**A new session is now told when a marker was kept** — the session that most needs telling, since
`/clear` just discarded the context in which the review was dispatched. The remedy it offers is
conditional on the roster, because the wrong one is destructive: a complete roster is routed to
`critic-consolidate`, never to `critic-end`, which would discard a finished review's findings.

## 2026-08-19: the work-cycle limit is re-priced, and a rationale is formally ceded

<!-- prawduct: type=refactor | scope=clear-cadence | release=v3.4.0 -->

`building.md` said: *"Limit work cycles to 1-3 chunks for medium+ work — Critic quality degrades
across a large diff, and long-session compaction can lose governance context."* One rule, two
rationales, **different expiry dates** — and a chunk count proxying for both.

**What is ceded (Principle 26).** *Long-session compaction can lose governance context.* The
mechanism carried a runtime assumption about context windows, the runtime changed, and the honest
response is to re-price rather than let it ride. This is a cession, not a deletion: the rule was
correct when written, and what retired it is a change in the world, not a defect in the reasoning.
Recorded here because **it has nowhere else to go** — `documentation/purpose.md` names a
*responsibility ledger* as the instrument for exactly this act and says outright it is not yet built
(Cycle 3 of the cession program). Filed, so the gap is tracked rather than implied.

**What survives, re-justified on one reason instead of two.** *Critic quality degrades across a
large diff* — and this half does **not** erode, because the binding constraint is the reviewer's
**attention**, not its context window. A larger window arguably makes it *worse*, by removing the
friction that was incidentally keeping diffs small. So the rule stands with one rationale, which is
stronger than standing with two when only one is load-bearing.

**The number retires.** `1-3 chunks` was a proxy for both halves and is now a proxy for neither. The
honest unit is the one the coordinator roster rule already keys on — a risk surface, or 12+
judgeable files — so cycle size is priced on the diff its review must cover. A second site carried
the same retiring number (*"when you've completed 2-3 chunks"*); it went in the same pass, because
sweeping the instance and leaving its sibling is how a retired rule comes back.

**What was NOT ceded, and the distinction matters.** Compaction's real invariant is untouched:
anything that must survive — plans, decisions, rationale — is written to a file first. What was
ceded is compaction as a reason to *cap cycle length*, not compaction as a hazard. The replacement
invariant #687 proposes is sharper than either: the risk is not "context got full", it is
**unpersisted state**.

**It funded itself, and then some.** The addition was paid by a cut in the same commit: the Modes
section restated what each of the four Critic modes covers, three lines above its own pointer to the
file that defines them. It keeps the two facts a reader needs *before* opening that file
(`cumulative` feeds the PR gate; `verify-resolutions` alone records resolutions) — the part a
pointer cannot carry. **The cut ran past the addition**, so `building.md` finished *below* where the
branch started and the ceiling **ratcheted down**, 4730 → 4718. That direction is the precedent
worth taking from this entry: a re-pricing that overpays ratchets the ceiling with the reading,
because a ceiling left at its old value after a cut silently re-funds the growth the cut paid for.

**Still open, deliberately.** The cadence question — *should* you clear, and by when — is not
answered here; it belongs to the standing block's clear paragraph, and putting it in two places is
the failure this release already spent four chunks fixing. And no numeric threshold ships until
rebuild cost and per-turn growth are measured from real `/clear`s.

## 2026-08-19: the turn-closing block answers whose move it is

<!-- prawduct: type=refactor | scope=governance-surface-dedup | release=v3.4.0 -->

The standing block's middle line offered `NEXT` / `BLOCKED` / `COMPLETE`, which mixed two questions
into one slot: *is there a problem?* (`BLOCKED`) and *what comes next?* (`NEXT`). Neither got
answered cleanly. The tell was in the spec itself — the injected digest had to **gloss** its own
label (*"Outstanding includes work in flight: a dispatched review … is `NEXT`"*), and when a spec
must translate its label to make it land, the translation is the better label.

One variable does the whole job: **what produces the next turn?** `RUNNING` — a machine event
will, so the reader can walk away. `YOUR TURN` — only a human utterance will; the session is inert
until they speak. `COMPLETE` — nothing needs to.

**`BLOCKED` retires because it was a reason wearing a verdict's clothes.** This block's own rule is
that the label is the verdict and the copy is the reason; obstruction is a reason. It now rides as
one of three shades of `YOUR TURN` — *just go*, *decide*, *unblock* — which the copy distinguishes
by leading with the ask and its cost. Two labels both meaning "you must speak" would force a choice
an agent makes inconsistently at the boundary.

**A premise the earlier design rested on was simply false, and correcting it is what unlocked the
set.** It held that every turn end waits for the user, so waiting could not discriminate — which is
why an earlier draft had narrowed `BLOCKED` rather than fixing the axis. Machine-resumed turns are
common: this branch's own reviews, monitors and background suites all resumed sessions with no
human input. Turn-ownership discriminates precisely because that is true.

**Two rules make this more than a rename, and both are pinned by their substance.** *Precedence:* a
human utterance outranks a running job, so a turn needing the reader is `YOUR TURN` even when work
is in flight, with the copy naming what runs. *No prediction:* a turn where something runs and a
decision may be needed **once it lands** is `RUNNING` — the agent cannot know the decision will be
needed, since the job may return "option 1 is clearly correct". This line reports what **is**, never
what might be.

**`COMPLETE` gained the scope it never had.** "Complete of what?" had no answer, so a finished chunk
inside an unfinished plan attracted the rarest label. It now means a **blank slate** — no next
action to propose. Ending a plan while knowing a PR is the obvious next step is `YOUR TURN`.

**The original ask (#683) landed alongside it.** The clear verdict is computed from disk and process
state, so a turn whose whole output is analysis *in the conversation* scored as safe while clearing
destroyed everything it produced. A findings-only turn now persists to `.prawduct/.handoff-notes.md`
before claiming `SAFE TO CLEAR`, and the self-contradiction tell is named so a reader can catch it
in their own draft: a `SAFE TO CLEAR` whose stated reason **cites the message itself** points at the
thing a clear deletes.

**The sequencing rule is the operationally sharp half.** The worst outcome in this space is a
multi-hour task landing while the reader is away and the turn still saying `DO NOT CLEAR` — they
return to a cold cache they pay full price to reload *and* a session they cannot leave, purely
because bookkeeping trailed the work. So: write the forward notes **before** a long wait, not after
it, and treat reaching `SAFE TO CLEAR` as part of finishing a long task rather than a report about
it. The existing "never ask whether to prepare a handoff — prepare it" rule was silent on *when*.

**It funded itself, which was the plan's closing argument.** ~113 tokens of new rule against ~10
tokens of headroom, paid almost entirely in place: the digest was restating `building.md`'s
size/type table, carrying a worked example of the stale-count rule, arguing the stance preamble's
own first sentence a second time, and explaining four rules the same bullet had already stated. Net
+5 on each shape — framework 3320/3325, product 2243/2248.

**`building.md` needed no edit at all.** Chunk 02 had already collapsed its standing-block copy to a
pointer, so it never carried the labels — the payoff that chunk predicted, arriving on schedule.
`plugin/CHANGELOG.md` keeps `NEXT`/`BLOCKED`: it is history, and history is not renamed.

**The pins model the reader, not the vocabulary.** A present-label check passes throughout a
half-done rename — the worst state, since both vocabularies are live and an agent picks whichever it
saw last — so the pin also asserts the retired labels are **gone**. And because a rename would
satisfy every name check while changing nothing, the axis, the precedence rule and the
no-prediction rule are each pinned by their discriminating content. All four assertions were
mutation-checked red before shipping.

## 2026-08-19: one digest for every repo, and a CLAUDE.md trimmed to what it does not say

<!-- prawduct: type=refactor | scope=governance-surface-dedup | release=v3.4.0 -->

The framework repo received a digest variant of its own. The reasoning was sound and the fix was
applied to the wrong artifact: this repo's always-loaded `CLAUDE.md` duplicated 40-50% of the full
digest, so a **slim** digest was shipped in the plugin to avoid paying for the overlap here. That
traded one repository's duplication for a second shipped artifact every framework session carried,
a branch in `hooks/digest.py`, and five must-agree pins holding the two variants in step —
permanent, framework-wide cost to serve exactly one repo. Trimming the local file instead removes
the duplication at its source.

`session-digest-slim.md` is deleted, `hooks/digest.py` reduced to one digest with no shape
selection, and `CLAUDE.md` cut from ~2,527 to ~1,339 estimated tokens. The framework session's
always-injected footprint goes **3,455 → 3,315** and the product session's **2,256 → 2,238**, with
both ceilings ratcheted to ~10 tokens of headroom (3,325 and 2,248).

**The digest is a member of both session shapes; `CLAUDE.md` is a member of one.** So the digest
trim below moved *both* readings while the `CLAUDE.md` trim moved only one — and the drift pin
caught an edit that updated just the shape being worked on. That asymmetry is now stated where the
ceilings are set, because it decides what a future addition costs: a token added to the digest is
charged twice.

**Both halves had to land together.** Deleting the variant without the trim re-creates the
duplication the variant existed to remove; trimming first opens a gap in `CLAUDE.md` that nothing
yet fills. Neither is separately shippable, which is why they are one chunk.

**The largest cut is the principles roster, and it was decided on evidence rather than estimate.**
`CLAUDE.md` carried all 26 principles with one-line glosses (~698 tokens) while the injected digest
carries the same roster as bare grouped names (~148). Checking the glosses one by one: 13 of 26 are
already stated by the digest in *point-of-action* form, which is the form that actually fires — and
the 13 that are not are the situational ones (accessibility, operational cost, clean deployment,
structural awareness) that matter when work touches them, which is what an on-demand file is for.
So the roster became a pointer at `docs/principles.md`, and nothing lost a carrier: the roster's
own test pins it against `docs/principles.md`, never against `CLAUDE.md`. `## Commit Conventions`
went the same way — the digest carries both rules, including the never-silently-downgrade-to-
`--squash` clause. One clause did **not** survive the move and had to be restored: the deleted
section said the no-attribution rule "overrides any harness default to the contrary", and the
digest's bullet had no precedence clause. That is not decoration — the Claude Code harness injects
a contrary `Co-Authored-By` instruction, so the clause is the only thing standing between the
default and every commit made under it. It now lives on the digest, paid for in place.

**What stayed is what only this file can say**: the framework-repo routing table, the two Critic
bindings the skill does not restate (fix blocking findings before the next chunk; reflect
immediately), the reflection *cadence*, the local file map, and the compaction instructions. The
requirements-clarity check stayed too, with its trigger made explicit — it fires when the user says
"build X", which is before a plan exists and therefore before `building.md` is read.

**The measurement came before the ceiling, not after.** The plan made the trim step 0 and the
number a reading, because the estimate that motivated the chunk (~1,350 tokens) was section-level
arithmetic rather than an edit. The edit came in at 1,188 — enough to win, and 162 short of the
prediction, which is exactly the gap that would have shipped as a wrong ceiling had the number been
promised instead of measured.

**A win worth stating honestly: the token saving is ~122 tokens per framework session, about 3.5%.**
This change earns its place structurally, not numerically — one carrier per fact, one shipped
digest instead of two, a hook branch and a repo-shape classifier deleted, and five must-agree pins
collapsed to single-surface assertions.

**The pins were collapsed, not dropped.** Every rule that was asserted on the slim variant is still
asserted on the surviving one, and `TestDigestReachesEveryRepoShape` now exercises **both** repo
shapes — a framework fixture and a product fixture — where the old suite ran the framework path and
inferred the product one. It also asserts the two are *identical and non-empty*, so the collapse
cannot be satisfied by both shapes agreeing on nothing. `is_framework_repo` and its three
manifest-location fixtures exited with the branch that consumed them.

## 2026-08-19: the standing block collapses to the surfaces that carry it

<!-- prawduct: type=refactor | scope=governance-surface-dedup | release=v3.4.0 -->

Four prose surfaces restated the turn-closing standing block in full: `reflection.md`, which owns
it, both injected digests, which reach a session whether or not it opens a guide, and
`building.md`, which is read on demand. The fourth copy was redundant **for its own reader** — an
agent that opens `building.md` has already been handed the shape by the digest injected at
session start, so the restatement was a second authoritative statement of a fact that has a home
(`architecture.md` § Direction).

**One clause there was load-bearing and stays.** `SAFE TO CLEAR` is not a free-standing
judgement; it is owed against `building.md`'s own chunk-close steps 1-7, and no other surface
enumerates those steps. So the file keeps the pointer and the binding, and loses the fenced
shape, the `---` rule, the trigger and the three failure modes — 4806 → 4720 estimated tokens.

**The trim is bounded from below by a paired positive assertion.** A negative pin ("no longer
restates the shape") passes just as well when the pointer is deleted too, which would leave a
reader who opened only this guide holding a verdict with no shape to put it in.
`test_building_md_binds_the_clear_verdict_to_its_own_steps` asserts the pointer, the binding, and
the absence of the labels together; both directions were mutation-checked red before shipping.

**The surviving pin was re-justified, not merely narrowed.** Its docstring had defended the rule
as protecting a token trim "funded" by relocating the rationale *into* the digests — accounting
the 2026-08-05 owner rule disavowed, since moving prose between files reduces no total. What the
pin actually guards is **coverage**: the shape has to reach an agent through a surface it really
reads, and dropping it from a digest means an agent that never opens a guide emits no block at
all.

**The ceiling was ratcheted down with the cut** (4810 → 4730), which the Critic raised
independently and is the difference between a win and a loan. The drift pin only asks the next
editor to update the *reading*; the ceiling is the hard gate, so 90 tokens of unratcheted slack
would have let the next 89 tokens of prose ship green and hand this trim straight back. Every
other budgeted file in the module sits within ~1-34 tokens of its ceiling.

## 2026-08-19: a token budget that can see a new file

<!-- prawduct: type=feature | scope=governance-surface-dedup | release=v3.4.0 -->

Every token budget in this framework is asserted per-file, and a per-file ceiling cannot see a
**new** file. That is not a hypothetical: `session-digest-slim.md` was added to save tokens in
the framework repo, put roughly 928 of them into every framework session, and every one of the
five per-file prose ceilings stayed green — because none of them was watching the *set*. The
budget regime was also inverted, which is what made the gap survive: the files with hard ceilings
and a measured-drift pin are the **on-demand** ones a session may never open, while the surfaces
paid unconditionally before the first useful token had only a loose character limit and a ratio.

**The set is defined by load event, not by weight.** Ranking governance files against each other
needs an importance score nobody can derive — and a weighted score would not have caught the
defect above either, since the new file's weight was never assigned at all. Grouping by *when the
cost is paid* needs no weight: frequency **is** the weight, and it is readable out of
`hooks/digest.py` rather than assigned by opinion. `INJECTED_SESSION_SHAPES` carries the two
shapes of the unavoidable tier — a framework session (`CLAUDE.md` + the slim digest) and a
product session (the `STATIC_ANCHOR` governance anchor + the full digest).

**The two shapes are separate rather than one flat set, and that is a departure from the plan's
own Deliverables** — recorded in the plan's `governed_by`, per the architecture norm that
prescribed method is advice while goals and verification bind. `digest.py` *selects* between the
variants, so a session never loads both; summing them would assert a ceiling on a total no
session has ever paid, which is a fiction dressed as a budget.

**The half that catches the original defect is the membership check, not the numbers.** The
totals only watch files already known. `test_every_injectable_digest_is_budgeted` reads the
injectable set out of `digest.py`'s own module-level path tuples via `ast` — so it holds for a
variant named outside any convention, and it fails loudly rather than narrowing silently if the
module stops declaring them that way. Red-verified both ways before shipping.

**Ceilings are HARD**, matching the five existing per-file prose ceilings rather than the
advisory state-file size threshold — that norm governs `.prawduct/` state, and an advisory would
not have caught this, since nothing was blocked when the set grew. Owner ruling, recorded as a
decision against the norm rather than assumed past it.

The per-dispatch tier — the subagent briefing and the reviewer payload, larger by two orders of
magnitude — is deliberately excluded and left to its own item. Folding it in would let a win
there hide growth here, which is the failure this control exists to prevent.

## 2026-08-18: the turn-closing block puts the answer in the label, not beside it

<!-- prawduct: type=feature | scope=standing-block-expressive-labels | release=v3.4.0 -->

Owner report, and it names a gap the block's own rationale already implied without acting on it.
`reflection.md` argues that the backticked labels are the only coloured tokens near the bottom of
a turn, "so the eye finds them without reading" — but `NEXT` and `CLEAR` named a **topic**. The
token the eye landed on said which question was being answered; the answer was in the sentence
after it. So the reader still had to read, which is the cost the colour was spent to avoid.

**Two changes, one principle.** The second line is now one of `NEXT` / `BLOCKED` / `COMPLETE`;
the third is `SAFE TO CLEAR` / `DO NOT CLEAR` with the reason as the copy.

**The axis is what makes the second line exhaustive: what happens if the reader walks away.**
`NEXT` — work continues without them, on an external event (a dispatched review, a background
agent); name it. `BLOCKED` — work stops here until they supply something only they can: a
decision, an answer, a name, or simply the go-ahead. `COMPLETE` — stopped and finished. A first
draft scoped `BLOCKED` as "cannot proceed without user interaction" and the owner corrected it to
include the routine ask ("user picks product name"), which is what forced the axis: under the
looser reading every turn qualifies, because a turn-based CLI always ends waiting, and the
loudest label becomes the default one. Under the walk-away reading the three are mutually
exclusive and `NEXT` acquires a specific meaning it did not have before — *nothing needs you.*

**`BLOCKED` is now the common case and that is the honest reading**, not a regression: the user
usually is the gate. The signal moved into `NEXT`, which now means the reader can leave.

**[DECISION — `STATE` gives up its verdict vocabulary.]** Beyond the reported scope, and taken
deliberately. `STATE` read "done / blocked / waiting" — the same three words the new line 2 now
owns, so the block would have stuttered ("STATE: done… COMPLETE: nothing left"). It now carries
only evidence: what changed, committed or not, suite green or not. That also prices a risk the
change introduces — `COMPLETE` is an agent self-assessment, and making it a loud coloured token
raises its authority, so a confidently wrong one misleads harder than the quiet "NEXT: nothing"
it replaces. Splitting evidence (line 1) from claim (line 2) is what keeps `COMPLETE` earned.

**The in-flight rule survives the retaxonomy, which was the main hazard**, but the first draft
only thought it did — both halves were fixed on the Critic's findings and both are worth
recording, because they are the same mistake in two costumes: *a rule that was unambiguous under
the old shape, carried forward verbatim into a shape that gave it a second reading.*

- **"Takes the second line" stopped being an instruction.** It was exact when the second line had
  one label; with three it names a location and no longer a verdict — while the entry advertises
  `BLOCKED` as the common case, so the cheap default under ambiguity pointed at the wrong label.
  Now bolted to the label itself: in-flight work is `NEXT` when it is only waiting on the event,
  `BLOCKED` when you also owe them something, **never `COMPLETE`**.
- **The precedence rule contradicted its own worked example — BLOCKING.** It read "when two are
  true the earlier label wins", and the declared order is `NEXT`, `BLOCKED`, `COMPLETE` — so the
  general rule resolved to `NEXT` while the example beside it said `BLOCKED`. An agent applying
  the stated rule emits *nothing needs you* on a turn where the user is the gate: the exact
  failure the in-flight rule exists to prevent, reintroduced by the fix for it. Restated
  relationally — **`BLOCKED` wins any overlap** — which drops the ordinal that made an ordering
  incidental to the taxonomy load-bearing for its semantics, and is also right for the
  `BLOCKED`-vs-`COMPLETE` case the ordinal got right by accident.

`test_v5_methodology` pins the string "in flight" on all four surfaces, so a silent drop goes red.
It does not pin the precedence rule, which is prose about a judgement call — the reason that one
had to be caught by review rather than by the suite.

**Blast radius: four surfaces, and they must not disagree** — `building.md`, `reflection.md` and
both session digests, two of which are always injected. Two budgets had to absorb it, both funded
inside their own file per the standing order (dedupe, then raise, never relocate):

- `building.md` sits at 4806 tokens against a 4810 ceiling. Its four-failure-mode sentence took
  the tighter form `session-digest.md` already used. Net zero — still 4806, so
  `LAST_MEASURED_TOKENS` is unchanged.
- `session-digest.md` was at **9983 of 10000 chars emitted — 17 of headroom** (the file is a
  char longer than what the hook emits; the assertion measures the emitted text), and this is a *hard*
  limit, not a self-imposed one: over it Claude Code spills the digest to a file instead of
  injecting it, so the always-injected surface stops being always-injected. The first draft
  landed at 10083 and the suite caught it. Funded by three cuts — the "label answers whose it
  is" gloss (`reflection.md` states it in full), one of three in-flight examples, and a
  handoff-notes gloss calling the file "the session channel that carries your intent across a
  `/clear`" that the same bullet already explains at length two sentences later. Now 9962, so
  the change hands back **more headroom than it took**.
- A **third** budget absorbed it unremarked until the Critic named it:
  `test_slim_budget_at_most_half_of_full` compares the two digests, so trimming the full one
  while growing the slim one moves both sides at once — its headroom fell by roughly a third.
  Still green. No endpoint is written here on purpose: this bullet exists to warn the next edit
  that the budget tightened, and a hand-copied figure goes stale against a number both sides move
  (it already did once inside this branch — read it live off the test, not off this line).

The test contract moved with it: the old assertions pinned the literals "Safe to `/clear`." and
"Not safe to `/clear` yet", which *were* the sentence-you-had-to-parse. Pinning them now would
re-require the shape this change removed, so they are replaced by label assertions.

## 2026-08-18: the change-log gate stops calling session metadata "code"

<!-- prawduct: type=bugfix | scope=change-log-gate-predicate | release=v3.4.0 -->

Reported from a consuming repo, verified here, and already on the backlog as **#245** — whose
title is literally the remedy. On a branch whose diff is only `.prawduct/*.json` plus `.md`, the
two gates at the same PR boundary answered oppositely:

```
check-pr-doc-only       -> exit 0  "none judgeable, gates may be skipped"
check-change-log-entry  -> exit 1  "branch changes code (.prawduct/corpus-state.json)"
```

`check_change_log_entry` classified with an inline `not f.endswith(".md")` and never called
`coverage_algebra.is_judgeable_path` — the predicate whose own docstring calls it *THE predicate
(CRT-5D8Q fix)*, introduced to end a three-way disagreement between `cmd_stop`,
`_pr_diff_is_doc_only` and `_record_covers_head`. **CRT-5D8Q consolidated three classifiers and
this was a fourth that was never folded in** — the same shape the rest of this release is about,
and the second consumer to hit it (an earlier report was archived 2026-06-13).

**Worse than a spurious block, which is the part worth keeping.** The gate's remedy text is
executable advice, and here it was *wrong* advice. The `.prawduct/corpus-state.json` on the
blocked branch was another session's corpus refresh riding along on a cherry-pick, so obeying the
gate would have produced a change-log entry describing someone else's work as the author's own —
a gate demanding a false provenance record. A gate that blocks costs a minute; a gate that
instructs you to falsify a record costs the record.

**[DECISION 2026-08-18 — the REL-6C3W loosening is taken deliberately, not inherited.]** Routing
this gate through `judgeable_files` means a branch touching only `.prawduct/` metadata now needs
**no change-log entry at all**. That is a real narrowing of REL-6C3W's guarantee and it was
flagged by the reporter as a decision rather than a detail, so it is ruled on here rather than
absorbed by the refactor: **session metadata is not shippable work.** The change log describes
what a release delivers to consumers, and `.prawduct/` state never reaches one — it is gitignored
in products, regenerated by the runtime, and reconstructed at release from the entries that
*do* describe shipped work. An entry for a corpus refresh or a pointer fix would be noise in the
one document a release reads. The guarantee REL-6C3W actually needs — *no code ships without an
entry* — is unchanged, because `is_judgeable_path` is the same predicate the coverage gates use
to decide what counts as code.

**The same line TIGHTENS in the other direction, and that half is the more surprising one.**
`is_judgeable_path` rates governance-protected prose judgeable — `skills/`, `methodology/`,
`templates/`, root `CLAUDE.md` — because skill prose is behavioral logic, not documentation. So a
branch changing only `plugin/skills/pr/SKILL.md` goes from exit 0 to **exit 1**: it now needs a
change-log entry it previously did not. That is `#245`'s other half, which the item calls "a
REL-6C3W-class hole", and it is deliberate: a change to how the Critic or the PR flow *behaves*
is shipped work by any reading, and it reached releases unrecorded for as long as the `.md` test
stood. Both directions are pinned, and a maintainer blocked on a prose-only branch should read
this paragraph rather than the one above it.

**A FIFTH classifier turned up when the class was actually swept, and a sixth site of the prose.**
Removing the fourth code classifier triggered a `grep` for the shape rather than for the file, and
it found `critic_mode.py`'s `if not any(not f.endswith(".md") for f in delta)` — wrong in the same
direction, suppressing the `verify-resolutions` suggestion for a committed delta of only
governance-protected prose. Two more prose sites in `skills/pr/SKILL.md` asserted the same wrong
rule about what must land before a cumulative run. All are routed or reworded to cite the
predicate. The by-shape sweep is `grep -rn 'endswith(".md")' plugin/lib plugin/bin`, which
returns only `coverage_algebra`'s own definition, three comments describing this history, and two
predicates asking genuinely different questions (`record_lint.is_record`, which lints governance
records and classifies no language, and `plan_index`'s filename glob).

**And the by-shape sweep was itself bounded by shape, which the next round caught.** Two more
members carried the wrong rule in *prose that contains no `endswith`* — `_rule_postfix_fix_fires`'
own docstring, directly above the line this branch changed, and the comment above
`_pr_diff_is_doc_only`'s call site in `prawduct-hook`. A grep for the idiom cannot see a sentence,
so the class needed a second sweep by *claim* rather than by token. That is the third time in this
release that a class was bounded by the thing easiest to search for.

The new pins are the defect and its shape: one reproduces the consumer's exact diff, and the
other asserts the two gates **agree**, rather than pinning each one's verdict separately —
because the defect was the disagreement, and independently-pinned verdicts are what let them
drift apart in the first place. Both fail against the old inline classifier.

## 2026-08-18: the cumulative review's two warnings close by construction, and both were class-shaped

<!-- prawduct: type=fix | scope=instance-vs-class | release=v3.4.0 -->

`rev-20260818T175424Z-bd5c4bf5` returned 0 blocking, 2 warning, 10 note over
`bbc31edeabf2...437e7b9a`. **Every finding carried the `Scope:` slot the same bundle added**, and
both warnings graded themselves `class` — the first live evidence the rule fires.

**A normalizer written against the old grammar keeps typechecking against the new one.**
`_normalize_chunk_id` trimmed leading zeros with `lstrip("0")` on the whole id, but chunk ids grew
dot-separated components: `"0.2"` lost the zero of its *first* component and returned `".2"`,
truthy enough that the `or "0"` fallback could not fire, and `_chunk_sort_key` then evaluated
`int("")`. That ValueError is not in `unticked_committed_chunk_notice`'s `(OSError,
SubprocessError)` except-set and two of its three callers are unguarded, so a plan numbering
`Chunk 0.1` tracebacked exactly where `api-contract.md`'s error model promises a diagnostic.
Fixed by making the one normalizer total — the zero trim is per *component*, because that is what
the grammar makes it — and by routing the two inline copies through it, which is what makes its
docstring's "the only chunk-id normalizer in the tree" true rather than aspirational. Both sides
of the `unticked & committed` intersection had carried the same inline trim, so they agreed on a
wrong answer, and agreement reads as corroboration.

**A cross-module coupling on a prose substring has nothing that fails when the prose is
reworded.** `cmd_stop` recognized an unparseable-heading report by `"do not parse as one" in
type_error` and its sibling by `startswith("unknown type:")` — two literals produced in a module
that does not know they are load-bearing, both inside long narrative messages rewritten whenever
the parser's advice improves. Rewording either silently disabled the only session-end surfacing of
a plan heading nothing can parse, leaving the author of the broken plan with no line number.
`buildplan_refs` now owns the discriminator (`UNPARSED_HEADING_MARKER`, `UNKNOWN_TYPE_PREFIX`) and
exports one predicate, `is_reportable_type_error`, that answers both members — because they are
one question, and a caller asking it twice is a caller that can come to answer it once. The pin
feeds the predicate output *produced by the real producers*: a test that hand-writes the sentence
it expects re-creates the coupling one layer up, going green against a producer that has drifted
because the fixture drifted with the assertion.

Also fixed, riding the same commit: the reflection provenance stamp computed `archived` inside the
version read's `try`, so a manifest failure degraded a date that touches no disk and cannot fail —
`archived=unknown` for the one field the corpus query this stamp exists for would group by.

**A 3.4.0-dev version bump was built here and then reverted, which is the more useful record.** It
was made on request, and the verify pass found that `fix/release-cut-checklist@73b30688` already
carries it — same three version files, same two banner defects, a *different* implementation.
Theirs admits `-dev`/`-dev.N` only and ranks `-dev.N`; this one accepted any semver prerelease and
deliberately did not rank. Theirs is the owner's recorded decision (2026-08-18) and is the one the
`#668` campaign needs, so this branch reverted its copy rather than shipping a divergent duplicate
into a semantic merge conflict in `banner.py` and `test_plugin_manifest.py`. The consumer-facing
`## v3.4.0-dev` section in `plugin/CHANGELOG.md` stays — it is additive content, not a competing
mechanism. **The finding under the finding:** two branches independently fixed the same two banner
defects within hours, which is the branch-level shape of this bundle's own subject — the second
author could not see the first, because a class member outside your diff is invisible whether it
sits in another file or another branch.

Two `.prawduct/` notes closed for free (they move no coverage): 14 blank-line runs left by the
learnings consolidation, and four retired rules whose `learnings-detail.md` sections still read as
live. The four were found the way the finding said to find them — diff the `## ` headings at the
merge-base against HEAD and intersect with the detail file, a query rather than a list — and each
now carries a `**Superseded by** <survivor>` line. Headings are unchanged, so the
`[[an untested governance bound rots silently across a migration]]` wikilink still resolves.

Four notes accepted with reasons recorded as facts: a deliberate plan-wide parser refusal, a
registry row that should wait for the #667 audit so it states audited coverage rather than a
week-old snapshot, a `building.md` sentence that is true while its label no longer resolves, and a
Goal 4 legibility risk that would spend `review-protocol.md`'s last 5 tokens.

**One process finding for the operator, from the coordinator rather than a goal:** the design
reviewer self-reported violating its no-execution contract — it ran `python3` to import
`buildplan_refs` and call `_unparsed_chunk_headings` while checking a regex's blast radius.
Read-only and pure, and it states no finding rests on the result, but `critic-reviewer`'s
allow-list grants `Read`/`Grep`/`Write` and a fixed set of `git` subcommands, and a bare `Bash`
call was not anticipated by it. Whether that should be structurally impossible rather than
prose-forbidden is a decision, not a defect to patch here.

## 2026-08-18: a finding says whether it is an instance or a class, and the remedy is graded

<!-- prawduct: type=chore | scope=instance-vs-class | release=v3.4.0 -->

Three times in one session on `fleet-feedback-661`, a finding named a site, the builder fixed
that site, and the class survived — caught by a reviewer each time. `update-gitignore` fixed
and `coverage-scaffold` missed; those two fixed and `migrate-plugin` + `init-product` missed,
both mutating on `--dry-run`. The reviewers had the knowledge; nothing asked them to write it
down, so what reached the builder was a list of sites.

**The tell is mechanical, which is the half that makes this more than a longer list.** State
why it broke in one sentence. If that sentence does not name the site you found, the finding is
a **class** and the sentence bounds it — say what to search, and expect members outside the
diff. The motivating sentence was *"the `"--flag" in argv` idiom reads an unknown token as
absent"*: it names an idiom, not a command, so grepping the idiom bounds the class. **And the
remedy is graded.** An instance closes by fixing it; an unbounded class closes only by a
construction — one owner every member passes through, or a check derived from the source of
truth — never by a longer list of names. Six existing learnings rules independently record that
the naive search under-reports, which is why an enumeration is not a reliable resolution even
when attempted in good faith.

`review-protocol.md` carries both halves — the rule in the severity legend, where a reviewer
looks while rating, plus a `**Scope:** instance | class — <why it broke>` slot in the finding
template, because a template is filled every time and a paragraph is re-read never. That serves
`final` and `cumulative`: the single-pass fork and all three coordinator subagents read this
file. Cost 123 tokens against the 128 the uplevel pass below recovered — no ceiling raised,
which is what that pass was for.

**The plan's deliverable list was itself instance-shaped, and the rule caught it.** It named
`review-protocol.md` and `review-cycle.md`. The class is *every surface a reviewer reads while
writing or grading a site-naming finding*, and `review-cycle.md` is not one — the file records
that fact about itself, where it notes fix-by-fudging's workaround leg "was rated only here, in
a file this mode's reviewer is forbidden to open." So the grading half went to
`critic_consolidate.RESOLUTION_IS_A_CLAIM_DIRECTIVE`, printed at `verify-resolutions` dispatch,
the last moment before the reviewer writes the one output that weakens a gate. It already
carried the rule in instance form — *"a finding whose second site is in a file this delta does
not touch"*, a list of two where the property was meant — and now names the class, the act
(re-run the finding's own reason as a search) and the withholding (a longer list of names is not
a resolution, so the finding stays out of `resolutions`). That directive was the framework's
designated overflow route precisely because it was uncapped; it is capped now, at 280 against
400, by the edit that spent it.

**`chunk` mode is uncovered, and explicitly.** `goals-1-3.md` — the only payload `chunk` and
`verify-resolutions` read — sits at 2247 against a `< 2250` ceiling, and the compressed rule
costs ~65 tokens. That is an owner ruling on that ceiling, or its own uplevel chunk, not a trim
to slip into the chunk that adds the rule. All three observed instances came from modes that
are covered (`cumulative` and `verify-resolutions`), and a `chunk`-mode finding still meets the
rule one round later, at the verify pass that grades its fix.

**And the rule found a third surface when applied to this diff.** The justification for the slot
— a template is filled every time, a paragraph is re-read never — names no file, so by the rule's
own tell it is a class. Its other two members are `review-cycle.md`'s `## Per-Chunk Output
Format`, the same four-field shape with no `**Scope:**`, and `goals-1-3.md`'s prose report
contract. Both live in the two budget-blocked files above, so one funding decision covers the
whole remainder instead of leaving a second item to rediscover.

Applied retrospectively to all three findings, the tell fires on each and names the same class:
the reason sentence names the `argv` idiom rather than any command, the class is unbounded
because new subcommands keep arriving, and the resolution is the pre-dispatch guard every
subcommand passes through — which is what eventually shipped, two rounds later than necessary.
The third finding's reviewer had already done this unprompted ("I found them by re-running the
class scan rather than the two names"); the change converts that initiative into instruction.

Prose, not a schema field, and the escalation trigger is stated rather than left to judgment: if
a review after this ships produces a site-naming finding that does not answer
instance-or-class, prose has failed and the answer becomes machine-checkable — cheapest form is
a lint on findings whose `files` array has ≥2 entries. Two guardrails model the reader rather
than the artifact: one asserts the rule sits *in the legend* and keeps all four load-bearing
components, the other that the directive names the class, the act and the withholding. The
first draft of the legend guard matched Goal 5's `**Scope pressure-test:**` bullet — a
file-wide scan for a bold "Scope" — and passed while asserting nothing about placement. Bounding
a class by the container instead of the property, inside the change that forbids it.

## 2026-08-18: the Critic's protocol pays for its next rule by upleveling, not by raising a ceiling

<!-- prawduct: type=chore | scope=instance-vs-class | release=v3.4.0 -->

Chunk 01 needs room in `review-protocol.md`, whose budget comment has said for five edits
running that the next addition trims or relocates. A measured scan found 634 of 3799 tokens
sitting in six repeated shapes; **128** of them proved recoverable, the ceiling is untouched at
3800, and the file now sits at 3671 with real headroom for the first time in months.

The discriminator is the substance, not the saving. **A class uplevels when the general form
is actionable without the enumeration, and stays enumerated when the enumeration IS the
trigger.** Four merged: Goal 4's five drift bullets plus changelog scope became *a description
whose subject moved*, with artifact, comment, docstring, README and renamed term named as
containers rather than as five checks; Goal 5's three missing-rationale bullets became *a
decision without a recorded why*; `infrastructure_dependencies` was being checked in both Goal
2 and Goal 4 and now has one home; and `CLAUDE.md size` stopped restating the changeset
scoping that now governs every Goal 4 check at once.

**128 and not the 153 the first draft claimed, and the gap is the finding.** A scan measures
what a shape *costs*; only rewriting it measures what it gives back, and the difference is the
checks that merely look repeated. Two of the first draft's cuts were deletions wearing a
merge's clothes, both caught by this chunk's own acceptance criterion — walk each removed
bullet and name the surviving sentence that carries it. Signals' work-type mapping (Feature →
spec compliance, Bugfix → root cause + regression, …) was redirected to "the selector cited
above", which is the chunk `Type:` selector — a *different* axis this same file calls separate,
whose real home is `methodology/building.md`, a builder-side file no reviewer is told to open.
And Goal 4's flat `stale artifact → WARNING` was folded under the prose ceiling, so a stale
`architecture.md` that no gate reads would have quietly graded NOTE. Both restored; the drift
bullet now carries two severity arms because artifacts and prose genuinely differ. Closing the
remaining 22 tokens would mean shaving load-bearing prose — the trade this file has refused
five times running.

One was measured and deliberately kept. Goal 2's declaration→obligation bullets (`Foreign
API:`, `Exposed API:`, `Visual change: yes`) are literal string matches, each owing a
different thing — "a declaration creates an obligation" names neither the string to find nor
the thing owed, so merging them stops three checks firing while reading as a tidy-up. That is
the vacuous guard shipped into the reviewer, and `framework-checks.md` Check 7 requires the
reason for a non-merge be stated rather than left implicit. It is stated in the budget
comment, which is maintainer-facing — putting it in the payload every reviewer loads would
have spent the tokens the pass just recovered.

Two upleveled rules now bind wider than their predecessors, deliberately: the concept-ripple
check said *for framework changes* and the id-anchoring check said *product* artifact, and a
renamed term or a dangling chunk number strands a reader identically on either side of that
line. The id-anchoring case also loses its own explicit `WARNING` and inherits the drift
severity rule — a dangling pointer is load-bearing by construction, since someone follows it.

The Goal 4 `**Norms**` bullet went with them, which two previous editors tried and reverted:
`test_project_preferences_blocking` needs one line carrying both `project-preferences` and
`blocking`, and that bullet was the only line that had it. Both editors deleted the duplicate
and left the contract unhomed. The rule now lives once, in the Normative-authority preamble,
whose BLOCKING clause names the `project-preferences.md` row or Direction statement a finding
cites — better for the reviewer, who reads that line while resolving jurisdiction. The trap
comment in `tests/test_v5_methodology.py` is retired and replaced with the general form: **a
test pinning prose pins WHERE a rule lives; move the rule before deleting its only carrier.**

## 2026-08-17: seventeen learnings rules become three, and the corpus stops burying its own general rule

<!-- prawduct: type=chore | scope=instance-vs-class | release=v3.4.0 -->

`fleet-feedback-661` produced three instances of one defect: a fix lands at the site a finding
named and the class survives. The corpus already had the rule — eight times, in eight
vocabularies, one of them (`A fix lands at the instance a review named`) well-worded and
general. None fired. The learnings file had the disease it was describing: seventeen
instances, no construction.

Seventeen rules across three families become three, and the split is the substance rather
than the trimming. **A** — the fix has relatives (7 folded in; the survivor keeps its heading
verbatim because it is a live `[[wikilink]]` target, and gains the one thing none of the seven
said outright: the other members sit OUTSIDE your diff, which is the mechanical reason they
stay invisible). **B** — the search under-reports (6 folded in), deliberately NOT merged into
A: A says the class exists, B says your grep for it lies, in four distinct ways. **C** — bound
the class by the property, not the container (3 folded in).

An earlier read of this corpus called the whole set "~12 restatements of one rule" and would
have deleted B and C. That was a keyword match reported as an analysis — an instance of C,
committed while surveying for C, which is why the count in this entry is 17 and not 12.

Every retired rule is preserved verbatim in `learnings-detail.md` under its family. Verified
rather than asserted: 264 rules to 250, `learnings-entry-shape` 0, descent-obligation ok, and
dangling wikilinks 15 before / 15 after / **0 newly broken** — the one retired rule that was a
link target still resolves because its text moved rather than being deleted.

The Critic's own review of this change then produced a **fourth** instance of the same defect:
the dotted-id widening reached `_CHUNK_COMMIT_RE` but not the `key=int` sort consuming it, so
`int('1.2')` was newly reachable and would traceback two callers that promise a
`cannot-verify:` line. Fixed with the widening's own sort key, and the comment that warranted
`int` — "every key here is a digit string" — deleted rather than reworded, because this bundle
is what made it false.

**Two more, both in this file, both found rather than recalled.** The pin written for the
dotted-id fix above was **vacuous**: one case called the sort helper directly (green either
way) and the other asserted `int("1.2")` raises — a property of the stdlib, not of this repo —
so the pair could not fail on this defect. (One of the two did carry a real assertion — that
`1.2` sorts before `1.10` — which is restored; calling both vacuous overclaimed.) A vacuous
guard for the vacuous-guard class,
inside the branch that exists to fix it. Replaced with a pin that drives
`unticked_committed_chunk_notice` end-to-end, and falsified: reverting the fix turns it red.

And an airgapped consumer reported that `--chunk "Chunk 01"` — the string the plan's own
heading prints — never matched, because the matcher captures a bare id. The failure is
CLOSED: record-lint rates an unrunnable deliverable check BLOCKING, so a correct plan with
every deliverable present bought a full extra review round, twice in one session on two
unrelated plans. The leading-zero tolerance made it worse by looking forgiving. The walk now
strips a leading `Chunk` label, so the flag accepts what the heading prints.


**And once more, one commit later.** The label strip landed in the section walk only, while
the same id is used again to join against completed chunks through `_normalize_chunk_id` —
which still only trimmed zeros. The membership test could never be true for a label, so a
completed chunk's `new \`path\`` forward-ref exemption never expired and the deliverable check
reported zero refs while reporting that it ran. The file's own docstring had said it: this is
**the only chunk-id normalizer in the tree — widen this one rather than adding a second**, and
a second is exactly what the previous commit added. Folded in; the section walk now calls it.

## 2026-08-17: four defects an external fleet report found, and the one shape they share

<!-- prawduct: type=bugfix | scope=fleet-feedback-661 | release=v3.4.0 -->

Issue #661 analysed ~840 reflection and learning entries across ten governed repos and returned
four still-live defects. Each was re-verified here before any code moved — three by reading the
mechanism, the chunk parser by running its regex against the inputs that fail. **Three of the four
are the same defect wearing different clothes: a check that could not run reads as a check that
passed.** That is the vacuous-guard class this methodology already teaches against, which is why
they were fixed as one scope rather than filed as four items.

**The chunk parser was worse than reported, and the report's own framing understated it.**
`_CHUNK_HEADING_RE` rejected dotted ids (`Chunk 1.2` — `(\w+)` excludes `.`) and a leading
checkbox. The report's complaint was that such a chunk yields zero deliverables, and zero reads as
"nothing to check". True but secondary. `_chunk_section_lines` ends a section at the next
*matching* heading, so an unparseable heading never closes the section before it: baselining a plan
carrying all five heading forms, chunk `A` returned **10 body lines instead of 3**, claiming
deliverables belonging to the two unparseable chunks that followed it. The check then *runs*,
verifies another chunk's files, and **passes**. A silent wrong answer outranks a silent empty one,
because empty at least looks like nothing. Both matchers were widened together (the module's own
comment block records why one-sided widening of that pair is a new defect), and the loud signal
scans the whole plan rather than firing at lookup time — the corrupted answer belongs to a
*different, parseable* chunk, so a lookup-time signal never reaches it.

**A flag nothing could receive.** `cmd_update_gitignore` took no `argv` parameter at all, so
`--dry-run` was not discarded by arg parsing — there was no arg parsing, and the reconcile ran. A
user reached a live `.gitignore` mutation by typing `--help`. The fix is at the dispatch site, on
the precedent `_check_binary_skew` already set there ("before dispatch, so it covers every
command"), because a per-command fix misses whichever command nobody thought of. `update-gitignore`
also gained the real `--dry-run` its siblings taught users to expect; it still repairs by default,
because `/prawduct:doctor` calls it as a repair step. **`api-contract.md` had claimed the
repo-lifecycle commands were "all dry-run-by-default where they mutate"** — so the artifact
documented a contract the code never honoured, and a reader who believed it got the opposite. That
is the more interesting half of this defect and it is now stated as the exception it is.

**An install that looks like it worked.** Enabling the plugin starts the hooks, and the hooks fill
`.prawduct/` with runtime state — so a repo that never ran `/prawduct:onboard` shows a version
banner, a populated directory and firing advisories. One fleet repo has been in that state for
weeks. Three advisories fired there and **none of them contained the word "onboard"**: prawduct
detected three downstream consequences and never named the cause, which is worse than silence
because visible activity reads as confirmation. The new probe fires only on the unanimous absence
of every marker that `/prawduct:onboard` or `/prawduct:migrate` writes, so a repo that was
onboarded and merely drifted stays silent and keeps getting told to repair rather than install. It
sits alongside the consequences rather than suppressing them, ranked `urgent` so it renders above
them — suppression would trade a misleading briefing now for a surprising one later.

Deliberately *not* counted as onboarding markers: `learnings.md`, `backlog.md` and
`project-preferences.md`. The runtime nudges each into existence without any onboard, so counting
them would have silenced the probe on exactly the trajectory the field repo took.

**Reflections now carry the version that produced them.** Nothing stamped it, so grouping the
corpus by release was archaeology — the reporter could attribute 35.6% of 839 entries and the rest
is an honest `unknown`. `.session-reflected` has no code write site, but its archive into
`reflections.md` does, so one statement at the session boundary covers the whole corpus. The header
reuses the tag idiom `lib/change_log.py` already parses, because a prose line would carry the same
words unparseably and repeat the gap at lower cost. Every resolution failure degrades to
`version=unknown` — never an omitted header, which is indistinguishable from an unstamped block,
and never a raise, which would escape the archive's handler and make the stamp a new way to lose a
reflection.

**What the new guard caught on its first run, which is the part worth keeping.**
`test_verify_chunk_refs_cli_reports_rather_than_tracebacks` invoked
`verify-chunk-refs --chunk 01`. The id is positional; `--chunk` is `verify-records`' spelling, and
dispatch was recording the literal string `--chunk` as the chunk id. The assertion passed anyway,
because an undecodable plan fails at the read before any id is used — so the test exercised its
contract through an invocation that never existed and would have stayed green if the real form
broke. A guard built for silently-ignored arguments found a test silently passing one. The
invocation is corrected; the assertions are untouched.

Considered and not done: making `/prawduct:doctor` preview before it reconciles. The report ranked
the doctor-reads-as-read-only framing first, and `--dry-run` now makes it a one-line change — but
it alters a skill's behaviour rather than fixing a defect, so it is the operator's call. Filed as
`#666` rather than left in prose.

**The flag fix took three rounds, and the reason is the most transferable thing here.** Round one
fixed `update-gitignore`. The cumulative Critic found `coverage-scaffold` and `coverage-status`
still reading unknown tokens as absent — and `coverage-scaffold` MUTATES, so `--apply --dry-run`
wrote 5 stub artifacts while the caller believed they had asked for a preview. That is the same
defect, in the command this entry's own first draft held up as the well-behaved sibling. Round two
fixed those two. The verify round then found `migrate-plugin` and `init-product` — the plugin
cutover and the repo scaffolder, the two most destructive commands on the surface. Measured against
the pre-change binary rather than argued: `migrate-plugin --apply --dry-run` performed the cutover,
and `init-product --apply --dry-run` scaffolded an entire repo.

Twice fixed by naming the commands someone had thought of; twice wrong. `learnings.md` has said to
prefer sweeping **by construction** over sweeping by enumeration since long before this branch, and
reading that rule did not prevent either enumeration. So the coverage is now asserted structurally:
`tests/test_hook_argument_shape.py::test_every_argv_taking_command_refuses_what_it_cannot_read`
derives the argv-taking set from `_dispatch`'s own source and fails for any member carrying neither
a guard nor a recorded reason. It immediately surfaced seven more commands nobody had looked at.

**Two defects the pin found in itself.** Its exemption list first shipped seventeen confident
one-line reasons written from names and comments; running bare-vs-unknown-token on each returned ten
verified, nine inconclusive (a bare invocation already errors, so the probe cannot separate a refusal
from that), and one ignoring the token by documented design. The nine are recorded as **NOT AUDITED**
in the test and in `api-contract.md`, with `#667` carrying the audit — an honest gap beats a confident
allowlist inside a test whose purpose is stopping unchecked assertions. And `migrate-plugin` was
listed in that dict as a courtesy to the reader, which exempted it from the scan: deleting its guard
left the test green. A vacuous guard inside the guard written to stop vacuous guards, caught only by
falsifying it.

The `api-contract.md` sentence added mid-branch — "checked before dispatch, for every subcommand",
with three carve-outs named as "the only ones" — was false for two mutating commands when it shipped.
Corrected, including which nine remain unverified. A written contract that overstates coverage is the
same defect class as a check that cannot run: both read as assurance.
## 2026-08-18: the reopen version is guessed LOW, and that is a correctness rule

<!-- prawduct: type=fix | scope=release-cut-checklist | release=v3.4.0 -->

The spanning cumulative (`rev-20260818T192844Z-d7391015`) blocked on the reopen step telling the
operator to guess the next **minor**, on two independent grounds, and the second is the one that
would have bitten.

**A high guess breaks the banner for the exact audience the step exists to serve.** A prerelease
sorts just below its own release, so `3.4.0-dev` = `(3,4,0,0,0)` sits ABOVE `3.3.5` = `(3,3,5,1)`.
A develop-pinned consumer that meets a patch cut therefore moves *backwards* — and
`highlights_in_range` and `new_gates_in_range` are both empty on a downgrade, so they get a
version move with no release notes and no gate announcement. From a low guess every possible next
cut is a forward move, which makes the conservative number and the safe number the same number.
`develop` now carries **3.3.5-dev**, and the rule reads "next patch" at all three sites.

**It was also a norm departure written into a procedure.** `operational-spec.md` § Direction
ratifies conservative versioning — *a minor bump is a recorded decision, not a reflex* — and a
runbook defaulting to a minor writes the reflex in. The `-dev` number is squarely inside that
norm's own rationale, being the handle a develop-pinned consumer reads all cycle. A minor `-dev`
now needs the recorded decision a minor release needs.

**The pruned promotion path never reached Phase 3 at all.** `promote-a-pruned-release.md` replaces
Phase 2 and says everything *before* Phase 2 is unchanged — Phase 3 is after, so it was neither
replaced nor covered, and nothing sent the operator back. Phase 1 has already bumped `develop` to
the bare release number by then, and the pruned completion test is the path partition rather than
the five-file diff, so nothing detects the omission either: on the shape used for v3.1.1 and
v3.1.2, the defect this branch removes came back silently. That runbook now points at Phase 3 and
says why it is easy to lose.

**A NOTE that this branch itself falsified.** `release_readiness._resolve_version` told the
operator the `plugin/VERSION` fallback was "the PREVIOUS release". After Phase 3 it is a `-dev`
marker that is not any release — no tag or plan will ever carry that name — so an operator
resolving `no-release-plan: no release-plan-v3.3.5-dev*.md` by creating that file damages the
artifact set. The message now says so, and its test asserts the **property** (the NOTE says the
fallback is not the thing being graded) rather than the old spelling, which is what let a pinned
sentence stay green while becoming false.

Two more claims corrected where they were made rather than where they were noticed: Phase 3
credited "step 7" with overwriting three files that steps 7-9 overwrite, and
`test_plugin_manifest.py`'s comment still carried the `check_version_files`-prevents-it framing
the runbook had already retracted.

## 2026-08-18: the reopen step gets the three blockers its first review found

<!-- prawduct: type=fix | scope=release-cut-checklist | release=v3.4.0 -->

The branch's first cumulative review (`rev-20260818T185932Z-a1b20a37`) returned **3 blocking, 4
warning, 4 note**. All three blockers were the same shape — a step added at one site while the
claims and checks that depend on it stayed where they were.

**Phase 3 falsified the runbook's own completion test.** Step 22 advances `develop` one commit
past the content-identity Phase 2 establishes, and the `Done when` bullet asking
`git diff --stat origin/main origin/develop` to print *nothing* sits below it — so on a correct
release it could never pass again. A check that always fails is worse than no check: the operator
learns to expect the failure and stops reading it. The bullet now expects exactly the reopen
commit's files, and says to run the strict form before step 22. `operational-spec.md` carried the
same claim in its own words and was swept with it — the second site is why this was blocking
rather than a stale-artifact warning, because `learnings.md` already warns that sweeping for the
identifier is not sweeping for the claim.

**Step 22, followed literally, shipped a red suite.** It said "commit with a change-log entry",
which reads as `.prawduct/change-log.md`; `test_changelog_has_current_version_entry` requires a
`## v<plugin.json version>` section in the **public** digest. This branch satisfied that by hand,
so the gap was invisible here and would have fired on whoever ran the step next. The mirror gap
was at the other end: Phase 1 step 10 said to *add* a `## vX.Y.Z` section, which leaves the `-dev`
section in place forever and gives a consumer two highlights for one release. It now says to
**rename** the open prerelease section.

**The new prerelease ordering had no test.** `version_tuple`'s trailing-sentinel scheme and the
widened `_SEMVER_HEADER` shipped with zero direct assertions — covered only incidentally by a test
whose coverage *evaporates at every cut*, when the version is bare again, so the released plugin
carried this path untested by construction. Five pins now cover it: the ordering in both
directions, `-dev.N` ranked numerically (`-dev.10` above `-dev.2`), the refusal of any suffix
`test_version_is_semver` would reject, the heading capture keeping its suffix, and the end-to-end
highlight selection. Four of the five fail against the pre-change implementation.

Two claims corrected rather than reworded around. The runbook credited `check_version_files`'
tag comparison with keeping a `-dev` suffix out of a cut; it runs `git show <tag>:...`, so it is a
post-publish **detector** — step 7 is the only preventive control, and is now named as such. And
the public CHANGELOG said cached verdicts "never cross a plugin change"; the cache keys on the
version *string*, which is static across a cycle, so it separates prerelease from release and not
one develop push from the next. Stated plainly, with `-dev.N` named as the unbuilt remainder.

The reopen step also reached the two other documents enumerating the release checklist —
`documentation/release-process.md` (as step 10) and `operational-spec.md` — which is the same
one-site-of-three defect the blockers were, caught in the same review.

## 2026-08-18: develop identifies itself as a prerelease

<!-- prawduct: type=feature | scope=release-cut-checklist | release=v3.4.0 -->

Between releases, develop carried the released version string. Harmless until the verdict
cache keyed on that string: successive develop pushes all claiming `3.3.4` can replay
`covered` verdicts across a judgeability change, and a consumer pinned to the `develop` ref
cannot tell from the banner which plugin it is running. The three version files now carry a
`-dev` suffix; the runbook gains Phase 3 (reopen develop at the next `-dev` after every cut);
`test_version_is_semver` admits exactly `-dev`/`-dev.N` and nothing else, by owner decision
2026-08-18. Releases stay bare because step 7 overwrites the version files at the cut.

**Three claims in the paragraph above were corrected by this branch's own later entries, and
they are named here rather than edited out** — the change log is append-only, and a reader who
meets this entry first should not have to reach the correction by luck. The version files read
`3.3.5-dev`, not `3.4.0-dev`: guessing the next *minor* was blocked as both a conservative-
versioning norm departure and a downgrade hazard. `check_version_files` does not *refuse* a
`-dev` residue — it runs `git show <tag>:…` and is a post-publish detector, so step 7 is the only
preventive control. And the `-dev` suffix does not separate one develop push from the next: the
verdict cache keys on the version string, which is static across a cycle, so what it buys is the
release boundary. `-dev.N` is what would buy the rest, and it is permitted but not yet produced.

## 2026-08-18: purpose.md stops claiming the responsibility ledger exists

<!-- prawduct: type=bugfix | scope=release-cut-checklist | release=v3.4.0 -->

`documentation/purpose.md` described the responsibility ledger in the present tense; it is
Cycle 3 of the cession program and unbuilt. Pre-release audit finding (2026-08-18). The line
now says "planned" and names the cycle — the doc-vs-reality shape this repo polices elsewhere.

## 2026-08-15: a plan-less scope is an absence, not a check that failed

<!-- prawduct: type=bugfix | scope=scope-widened-demotion | release=v3.4.0 -->

Record-lint rates `chunk-ref-missing unchecked — …` BLOCKING, by string and not by judgment, because
a deliverable check that could not run is indistinguishable from one that passed. One shape reached
that prefix without deserving it: a dispatch whose scope no build plan declares. That is the ordinary
condition of a **framework-only fix**, which `building.md` says needs no build plan at all — so the
finding had no remedy. Not a `--chunk` to supply, not an edit to the diff that clears it. The only
exits were inventing a retroactive plan or departing from the rule, and **three consecutive reviews
on this branch took the second**, each recording the departure and moving on. A rule whose correct
response is "ignore it, with reasons" is training people to ignore the prefix that blocks.

The fix is a discriminator rather than a demotion, because the two shapes that reach here are not
alike. A **typo'd or stale** scope names nothing anywhere, and grading must not go quiet on it. A
**real, deliberately plan-less** scope is declared in the change-log — a record that already exists
by review time, since `check-change-log-entry` refuses a code branch at the PR boundary unless it
ADDS an entry, and the `scope=` tag on that entry is what the release flow reads to enumerate
unshipped work. When the change-log declares the scope, the entry now arrives as
`chunk-ref-missing no-subject — …` and rates NOTE; otherwise it is `unchecked` and still BLOCKING.

**What that is worth, stated precisely.** The PR probe requires the *entry*, not the *tag*, so a
builder writing `scope=` is still declaring something rather than having it forced out of them. The
gain over the two alternatives — a `--scope-has-no-plan` flag on dispatch, or an allowlist key in
`project-state.yaml` — is therefore not unforgeability. It is that the declaration is durable, is
read by the release flow for an unrelated purpose, and shows up in the diff a reviewer reads; a
transient flag on one dispatch is none of those. The typo case, which is what actually has to be
separated here, is declared nowhere by construction.

Considered and not done: making `check-change-log-entry` require the `scope=` tag, which would close
the gap properly. It changes a gate's behavior for every consuming repo, including those whose
existing entries carry no tag, so it is not a ripple of this fix.

Fails closed at every edge: an absent change-log, an unreadable one, or a parse failure all keep the
blocking read, since a witness that cannot be consulted proves nothing.

## 2026-08-15: the widened-scope demotion names a mode that can see the delta

<!-- prawduct: type=bugfix | scope=scope-widened-demotion | release=v3.4.0 -->

`critic-begin --mode verify-resolutions` refuses when the delta since the prior review outgrows the
prior surface, and told the reviewer to "run a full review" — which the skill spelled `final`,
unconditionally. `final`'s interval is HEAD-tree → working-tree, the *uncommitted* diff. So an
interval refused for being **too wide** was replaced by one that is strictly **narrower**, and a
widening made of commits demoted to the one mode that cannot see a commit.

Observed on a product repo: 95 files widened the scope (a base-branch merge plus the chunk's own fix
commit, already landed). The demoted `final` reviewed the two untracked files the working tree
happened to hold — a devcontainer script and a build plan belonging to another scope — and that was
recorded as the chunk's review. Nothing caught it: both dispatches succeeded, the manifest was
internally consistent, and the reviewer reported exactly what it was handed. Only a clean working
tree would have tripped `final`'s own "empty diff — already committed? a committed bundle is
cumulative's scope" refusal, which routes correctly; two strays were enough to swallow it.

**Where the delta lives now picks the mode, in code.** `begin_review` has already computed whether
committed content moved since the prior review, so the refusal carries a `fallback_mode` and names
it in the message: `cumulative` when the widening includes committed work, `final` when the drift is
all uncommitted — which is exactly that interval, and the case the old advice was accidentally right
about.

`cumulative` is deliberately **not** described as a superset of what widened, because it is not one:
a base-branch merge moves the merge-base forward, so merge-base…HEAD *excludes* the merged-in files
that inflated the delta. That is the right answer rather than a shortfall — those files were reviewed
on the base branch, and what the branch owes is its own work, which is exactly that span. The first
draft of this fix sold it as a superset; the review caught the claim, and a wrong claim about
coverage is the same class of defect as the one being fixed.

Two guards keep the recommendation from repeating the defect one level up, since recommending a mode
that would itself refuse at dispatch is the same failure: when no merge-base resolves, or when HEAD
*is* the merge-base, `cumulative`'s interval is empty or unavailable, so the message falls to `final`
and says plainly that it sees only the uncommitted part rather than claiming coverage it lacks.

The prose was read correctly — it was wrong — so the fix moves the decision out of prose. `SKILL.md`
and `review-cycle.md` now say to re-dispatch in the mode the refusal names and never to assume
`final`; the reasoning they carry is the one already written into the exit-3 qualifier one section
away, which had the interval-narrowness insight and was never generalized to exit 2.

**Stated as a property, not as one table row.** The first draft fixed only the exit-2 row, and the
review found the generalization independently from two directions: the exit-**1** demotions ("no
usable prior review") still said `chunk`/`final` unconditionally, and two of their triggers —
undiffable prior tree, anchor not an ancestor of HEAD — arise *precisely* because committed history
moved. Worse, the reviewing agent hit a third instance while reviewing this very commit: dispatching
`final` against a clean committed tree returns the empty-diff refusal, whose SKILL row said "report
the stderr reason and stop" while the refusal text itself correctly named `cumulative`. So the rule
is now stated once, as **the demotion property**, at the head of the exit table in `SKILL.md`, and
every row leans on it — including exit 3's qualifier, which had been carrying its own copy.

Deliberately not extended: the exit-1 refusals do not yet *compute* a fallback mode the way exit 2
does. Two of the four have no prior fact to compare trees against, so `committed_differs` is not
derivable there and a different signal would be needed. The property now covers those rows in prose
and the empty-diff refusal remains the backstop; the code extension is filed rather than built here,
because it is a design question about what a first review of committed work should anchor to, not a
ripple of this fix.

## 2026-08-14: the retired test count now announces itself

<!-- prawduct: type=feature | scope=test-tracking-advisory | release=v3.4.0 -->

Removing `build_state.test_tracking` shipped with two entry points and one gap: **both need someone
to decide to run them.** `/prawduct:doctor` repairs an already-onboarded repo and the cutover
removes it from one crossing over, but nothing told any owner there was anything to run — and the
correct route differs per repo. Measured the day the removal shipped: nine repos still carried the
block, four of which needed `migrate` rather than `doctor`. Expecting each owner to work that out
unprompted is not a plan.

A post-sync advisory probe now fires at session start when the block is present. It **recommends and
never writes**: unlike `.gitattributes`, `project-state.yaml` *is* inside the plugin's permitted
write set, so the write-set norm would allow an automatic strip — what forbids it is the
operation-level approval rule, because a framework silently deleting from a product's hand-authored
state file is the trust breach that rule exists for.

**The message leads with the instruction, not the diagnosis, and that is the whole design.** This
block's harm was never its bytes; it is that an agent meeting a stale count in a product's source of
truth is *obliged* to correct it, and each correction buys a review round. "Retired — do not
maintain it" reaches the agent before it edits anything, so the advisory does most of its work on
the first session whether or not the repair is ever run. A nudge that merely reported the condition
would leave the treadmill turning until someone acted.

Scoped to this block alone. `views_enabled` and `scope_rollups` are the other retired state keys and
are deliberately excluded: nobody maintains them, so they carry no behavioural cost, and doctor's
health check already covers their cleanup — an ambient nudge about inert residue is the control
`nonfunctional-requirements.md` says to remove by default.

Detection delegates to `lifecycle_repair.state_removals`, making this its third caller after the
doctor repair and the cutover; the key name and span have one home. The probe self-resolves — the
trigger and the resolution are the same observable state — and its evidence deliberately carries no
count or size, because these files are edited by their own sessions and evidence that moved with the
contents would re-issue the advisory under a new id, silently un-dismissing one the owner had
already decided about.

Verified end to end against a copy of a real product's state: the advisory fires unprompted, its
recommended command previews and applies, the advisory returns zero on the next probe, and
`source_root` survives.

A preferences test caught the module's first name. `plugin/lib/test_tracking_probes.py` starts with
`test_`, which reads as a test file to pytest's collector and would be silently skipped under
`testpaths=["tests"]`; it is `retired_state_probes.py`.

## 2026-08-14: the test count ten products maintain and nothing reads

<!-- prawduct: type=fix | scope=test-tracking-treadmill | release=v3.4.0 -->

`build_state.test_tracking` is a hand-maintained copy of a fact the evidence store already holds
per tree. Nothing in the runtime reads it, no template scaffolds it, and prawduct's own state file
has never carried it. It is nonetheless live in ten governed products, because the field is *in*
the state file — and the state file is a product's source of truth, so Living Documentation obliges
every agent that meets a stale number there to correct it. Each correction is a commit, each commit
extends HEAD, and that is how a record defect buys a review round; the mechanism is the one
`lib/record_lint.py` already documents, and one of the four examples it names is a test-count claim
corrected three times.

The cost is visible rather than theoretical. In the worst repo the field's provenance comment had
grown to a single YAML line of ~52,000 characters — about a third of the file — nesting its own
correction history, including a note recording that three successive edits had used the wrong basis.
Running the repair over a copy of that file removed roughly 80 KB (measured 2026-08-14).

**Those figures are a dated snapshot and are deliberately not stated as exact, which this entry owes
an explanation for, because the exactness is what the entry is about.** The first draft recorded a
precise before/after pair. It was true when taken and had stopped reproducing within ninety minutes
— that repo's own session edited the file mid-measurement, trimming ~52 KB from inside the very
block under discussion. A second party re-measuring found different numbers and correctly refused to
write the pair it had been handed. So the *fact* here is what the repair does, not what one file
weighed on one afternoon; re-derive the current figure rather than trusting this sentence:

```
python3 - ../SOME-PRODUCT/.prawduct/project-state.yaml <<'PY'
import sys, shutil, tempfile; from pathlib import Path
sys.path.insert(0, 'plugin'); from lib import lifecycle_repair as lr
tmp = Path(tempfile.mkdtemp()); (tmp/'.prawduct'/'artifacts').mkdir(parents=True)
shutil.copy(sys.argv[1], tmp/'.prawduct'/'project-state.yaml')
sp = tmp/'.prawduct'/'project-state.yaml'; before = sp.stat().st_size
lr.apply_repair(tmp, lr.plan_repair(tmp)); print(before, '->', sp.stat().st_size)
PY
```

(It copies first and never touches the product's own file. Run from this repo's
root, since it imports the plugin's `lib` from a relative path.)

A durable record carrying a live measurement is the same defect as the field this change removes,
one level up — which is why the correction is a re-derivation command and not a fresher number.

**The block goes whole, which is a decision the survey forced.** Measured across every governed
product: `test_tracking` sits under `build_state` in 10 of 10 that carry it, and the field the
backlog item was named for is the *sole* member in exactly one. The other seven carry
`assertion_count`, `test_files`, and a `history` of per-chunk `tests_added` entries — the same
bookkeeping, so removing only `test_count` would fully clean one product and leave the treadmill
running in seven, guaranteeing a second pass. Nothing in `lib/` or `bin/` reads `build_state` or any
member; `source_root`, which is read in ten places, is a *sibling* under `build_state` and is never
touched, so the parent is never left empty. This supersedes the earlier acceptance criterion on
**#633** — "does not touch a `test_tracking` block carrying other keys" — which was written from the
ruling's framing before the block was measured.

**Two entry points, one definition.** `lifecycle-repair` converges repos that onboarded before the
removal existed; the plugin cutover removes the same keys on the way through. The division is by
*when*, not by *what* — `migrate_plugin` calls `lifecycle_repair` and a test asserts it holds no
live string naming any retired key, so the two can never disagree about what one is. The removal is
nested where the module's existing two are column-0, so it needed an enclosing-parent predicate and
a depth-aware span; everything downstream — ordering, preview, the atomic write, the line-ending
contract — is shared.

**A test that pinned a misclassification was corrected, not weakened.** The cutover suite asserted
that `views_enabled` survives migration and called it a "pre-existing product key". It is not one:
it is retired *framework* residue, which is the entire reason `lifecycle_repair` exists. That
assertion obliged the one act that deletes every other framework file to carry framework residue
forward — which is how these keys reached the plugin era in ten products. The contract now reads on
the axis that matters: product keys survive byte-for-byte, retired framework keys go, the marker is
appended.

Prawduct has removed this field once before, through `strip_test_tracking()` in the file-sync
engine, retired in M4/v2.0.3 — and it came back. So the deletion ships with a tripwire rather than
alone; that half is the same scope's second chunk.

**The tripwire: record-lint now sees the state file.** `is_record()` classified only `.md`, so the
suite-total check swept the plugin's markdown clean while the claim that actually survived sat in
YAML. It now also accepts YAML **directly under a `.prawduct/` directory** — scoped to governance
state, never to YAML generally, because a product's CI config and lockfiles are its data and grading
them would put this control in the wrong business. **The pattern is unchanged**: it already matched
the worst real line many times over, so the fix was the file-type gate alone. The three
markdown-specific checks are unaffected and now pinned that way — each already selected its own
inputs by filename or by build-plan name rather than trusting the record set to be markdown.

`tests/test_record_lint.py` asserted `.prawduct/project-state.yaml` was *not* a record. That
assertion is inverted here, deliberately and on the owner's decision: the pinned behaviour is what
was re-decided, not an assertion relaxed to let code pass.

**The check found two false positives in this repo's own prose within a minute of existing, and
both were the prose's fault.** The build plan quoted a matching fragment as evidence, and a
quotation of a defect is indistinguishable from the defect to anything that scans text; its
acceptance criteria wrote backticked paths that `chunk-ref-missing` correctly read as declared
deliverables. Both were reworded — a record should carry the command that re-derives a claim, not a
copy of it. Neither check was weakened.

**And the methodology now names the instance.** `building.md` already said a count nothing reads is
not worth writing; it did not say that a suite total is the one that keeps coming back, which is why
the instance outlived the rule. One clause **on that same paragraph** — not on the Verify step,
where it was first drafted as a separate bullet at +180 tokens that broke the file's budget and
tripped the count-slot guard by quoting the shape it was forbidding. The rewrite satisfying both
put it where the concept already lives, and landed **net zero** against the budget, paid for by
four trims of pure restatement.

**The cutover's line-ending and decode contracts were fixed in the same scope**, both surfaced by
the cumulative review and both older than this change. `record_distribution` read and rewrote the
state file with universal newlines, so appending one key to a CRLF product file rewrote every line
in it — and it runs immediately after the removal that had just preserved them. And
`core.read_str_yaml_key`/`read_bool_yaml_key` document themselves as failing soft on an unreadable
file while catching only `OSError`; `UnicodeDecodeError` is a `ValueError`, so an undecodable state
file aborted the whole cutover before any later step reached its own guard — including guards a
recorded disposition in this scope's build plan rested on. All three now fail soft, and the sum of
those soft failures is reported — for **both** failure modes — rather than left to look like
"nothing needed".

That last qualifier was earned the hard way, and it is the entry worth remembering. The guard
written to report the silent half-cutover *first covered only the decode error*, so a
permission-locked state file still produced exactly the silence it existed to prevent: the guard
had reproduced, one level up, the same too-narrow-catch defect it was reporting. The verify pass
caught it. Both modes are now distinguished in the message, because they send an operator to
different fixes — re-encode the file, or fix its permissions — and the dry run says the same thing
the apply will do, rather than promising an edit the apply declines.

## 2026-08-13: the change log recommends its own merge driver

<!-- prawduct: type=feature | scope=tactical-efficiency | release=v3.4.0 -->

On both forced base syncs measured on a consumer repo, **100% of the merge conflicts were
prawduct's own record files**, led by this one. Every branch writes its entry at the TOP of the
change log, so two branches always edit the same first lines and merging an advanced base conflicts
there every single time — a manual resolution and a reconcile commit for a file whose two sides
never actually disagree.

A post-sync advisory now recommends `.prawduct/change-log.md merge=union` when the committed log
resolves no such gitattribute, and self-resolves once it does. It **recommends and never writes**:
`.gitattributes` is not in the plugin's write set, and unexpected framework writes to a repo's
committed configuration are the trust breach that set exists to prevent. The advisory surface is
the one that runs every session; `/prawduct:doctor` lists the same check as the secondary surface,
where it is a recommendation and does not grade a repo degraded — a repo is free to decline advice.

**The recommendation is verified, not assumed.** Two branches prepending tagged entries conflict
without the attribute and merge cleanly with it, each entry's `<!-- prawduct: … -->` line still
under its own header, because the union driver concatenates whole hunks and never crosses them. The
trade it makes is real and stated where the probe lives: union never conflicts, so a genuine
two-sided edit to the *same* line survives as both versions rather than as a conflict — caught
downstream by the release gate's tag validator, which errors on one key set two ways.

**Three answers, not two, at the git boundary.** `git check-attr` returning nothing and git being
unaskable are the same empty answer unless the code keeps them apart, so `gitstate` gained a
tri-state pair (`git_merge_attribute`, `git_path_is_tracked`) that returns `None` for "could not
ask". The probe raises no advisory on `None` — nagging a repo that may already be fixed is the
wrong error — and prints a `NOTE` naming what went unchecked when the log is committed, which is
when the harm is live. Where git cannot be asked at all it stays fully quiet: nothing that cannot
merge can conflict.

Also here, riding the commit rather than a later round: the ~dozen docstrings that still described
active-plan resolution as "the `active_build_plan` pointer" now say "this repo's active build plan"
and point at the function that owns the rule, so the precedence has one home instead of a ninth
copy that goes stale on the next change.

## 2026-08-13: the plan declares its branch

<!-- prawduct: type=feature | scope=tactical-efficiency | release=v3.4.0 -->

Which build plan is active is **branch state**, and it was stored in `active_build_plan:` — one
scalar, at product level, in a file both of two concurrent branches edit. Two branches therefore
guarantee a same-line conflict every time, and after the merge exactly one plan wins the line while
the other becomes invisible to every surface that resolves through it: the briefing, mode
inference, chunk-ref verification, the Stop gate.

**The pointer is inverted.** A build plan may declare `branch: <name>` in its frontmatter, and
`core.resolve_build_plan_path` now resolves in precedence order: the live plan claiming the
checked-out branch, then the scalar, then the conventional default. Nothing migrates — a repo whose
plans declare no `branch:` resolves exactly as before, and the scalar keeps working as the fallback
it now is. Archiving a plan ends its claim, because the scan prunes `archive/` at directory level,
so for a branch-declaring plan the archive move is the whole retirement with no pointer left over.

**Two live plans claiming one branch is a refusal, not a coin-flip.** Either could be the one its
author meant, and governing a session by the wrong plan looks exactly like governing correctly, so
resolution raises rather than picking the one that sorts first. Authority inherits that by
propagating it — a refused gate is a blocked gate, and the hook prints the refusal and its remedy
instead of a traceback. Advice inherits it by reporting: the briefing names both plans at the top
of the session, and is still produced.

**The chunk's own acceptance criterion named two consumers that were observably broken**, and one
of them needed more than the resolver. `critic-begin` derives its ledger scope by matching the
branch NAME against declared scopes — `feat/tactical-efficiency-pass` matches the scope
`tactical-efficiency` under no rule, so every dispatch from this branch recorded scope `(none)`,
which in turn left the disposition work-scope filter shipped earlier in this pass inert. Scope
inference now consults the plan's `branch:` declaration first. It is the only route there that is
not a guess, so neither narrowing applies to it: not the name-candidate rules, and not the
liveness check that rejects a fully-ticked plan — that check exists to stop a *guess* attributing
work to a plan that shipped, and it opens a window at exactly end-of-plan, when the `cumulative`
review and the last gate run happen.

**Session start got faster, not slower.** The branch resolution adds a walk of `artifacts/` — the
one the scope map already pays for — but it also asks git for the current branch, and the briefing
asks five times. Measured on this repo the briefing went 197 ms → 494 ms, which is not a cost this
pass gets to ship. `gitstate.current_branch` now reads git's `HEAD` file directly and shells out
only when it cannot answer, which is a fast path for every one of its callers rather than for the
new one: 215 ms, +18 ms over baseline for the walk the feature actually needs. The reader is
worktree-aware because that is where it runs most — a linked worktree's `HEAD` is its own, and
reading the shared common dir would have reported the primary checkout's branch to every gate,
silently.

**The review found the refusal failing OPEN at the one gate that matters, and both blockers were
that.** `main()` rendered every refusal as exit 1 — but `stop` is a harness hook, and the recorded
error model gives its row exactly two outcomes: 0 clean, 2 block. Exit 1 is neither, so on a repo
with two plans claiming the branch the session would have ended **clean**, with the reflection,
coverage and PR gates never having run: the precise inverse of the posture the feature documents,
reachable only through the state the feature invents. `cmd_stop` now probes resolution once, before
any gate and before the background-work deferral (which returns 0, and which no amount of background
work could ever clear), and renders a refusal as a BLOCKED report at 2. Guarding the individual call
sites was tried first and only moved which line raised — three of them resolve independently, which
is the finding's own point: every gate resolves a plan.

The same review caught the new "plan claims a branch this repo does not have" advisory firing across
the whole gitflow merged-but-unreleased window — recommending the one action `/prawduct:pr` forbids
there, and falsifying two doc paragraphs added in this same commit. It now fires only for a plan with
an **unfinished** chunk, which is the case with yield: the author believes their plan governs this
work and it silently resolves for nobody. A finished plan claiming a deleted branch is the documented
end state, and says nothing.

**A dead mirror was deleted rather than duplicated into.** `bin/prawduct-hook` carried an inline
copy of the resolver for an import-light hot path. Its last caller went away when `staleness_scan`
moved into `lib/briefing.py` and was rewritten onto the canonical resolver, after which the only
thing invoking it was its own parity test — and the import-light claim was void, since that path
reaches the resolver through `lib.briefing` and pays for `core` anyway. Extending it would have
meant duplicating a directory walk and a git subprocess into code nothing calls, on its fourth
rework (Principle 25). The scalar reader beside it stays: it has four live callers, and its parity
cases are unchanged.

Two prose corrections carried from the previous chunk ride here, both deliberately held back so
that chunk could commit a verify-vouched tree verbatim: `gates.py`'s `uncovered` remedy still told
a builder whose verify fact anchored the working tree to "commit (or stash) the WIP and re-run",
and the corrected half of `critic-consolidate`'s twin had no test pinning it.

Not in scope, and stated so the next reader does not go looking: removing the scalar, migrating
consumer repos, and the release-side scope enumeration (already pointer-free).

## 2026-08-13: the batch-fix golden path, stated at the point of action

<!-- prawduct: type=feature | scope=tactical-efficiency | release=v3.4.0 -->

Five consecutive 0/0/0 verify passes on one branch, 1,270 seconds, each one bought by the builder
electing to fix the previous pass's demoted observations. The discipline that prevents this already
existed in `building.md` and in `critic-consolidate`'s output — but neither is open at the moment
the decision gets made. The builder is reading a gate's stderr, or a verify report, or the PR
update step, and all three said less than they needed to.

**The PR/Stop gates' blocking remedy now prescribes the whole golden path**, not just the command:
fix ALL of them in the working tree, do not commit between fixes, run ONE `verify-resolutions`
(it reads the dirty tree), and commit that verified tree verbatim. The failure mode it names is
fix-commit-verify per finding — each commit extends HEAD, so each one buys a fresh round whose
demoted observations tempt the next fix. Superseded-blocker routing is untouched: the spanning
review still leads when every blocker is one, since that is a routing question and this is a
batching one.

**Verify-mode observations arrive pre-priced.** `goals-1-3.md` now delivers them with the
disposition attached — ACCEPT is the default, fixing one re-opens the gate and costs a round,
batch any survivor into an already-planned commit. Placement is the point: the builder decides
while reading the report, so the price has to be in the report. It spends the last of the ceiling
raise this pass declared for exactly this addition, leaving 7 tokens.

**`/prawduct:pr` Update defines "substantive"** — at least one judgeable path in the delta since
the reviewed commit — and gives a command for each non-substantive shape rather than leaving it to
the eye: `cost-of-commit` for a records-only delta, `check-cumulative-critic` for a base sync that
exits 0 by transfer. **It closes half the observed 520-second re-review, not all of it**, and says
so: the `.prawduct` records are non-judgeable, but a CI workflow is config, so a comment-only edit
to it stays judgeable. The content-equivalence exception that would close the rest was built and
reverted as unsound (COV-3M8Q) — the rule states its limit instead of overreaching to match the
evidence that motivated it.

The chunk's review caught a fail-open in its own new rule, and it is the reason the `cost-of-commit`
bullet is as long as it is. `cost-of-commit` with no arguments — or with a directory — prices the
**working tree**, and at that point in the Update flow the working tree is clean because the delta
is already pushed. It returns an empty `judgeable` list having examined none of the delta, and an
agent testing only for that emptiness skips the independent PR review entirely. The paths are now
passed explicitly, "not substantive" requires a non-empty priced set as well as an empty judgeable
one, and an unreadable or empty result is substantive: unknown is never free.

One consequence of the golden path reached further than the three surfaces. `critic-consolidate`'s
dirty-tree note told the builder the gate would read `uncovered` "until you commit (or stash) the
fix **and re-run verify-resolutions**" — the extra round the new remedy exists to remove, and
wrong besides: a verify pass over a dirty tree vouches for that tree, so committing it verbatim
carries the very tree the pass vouched for and the gate composes with nothing further. The note now
says so, and names the actual exception — a selective or further-edited commit.

Two things were analyzed and deliberately not built, both from the parent analysis: a sincerity
flag (`--im-really-done`), which cannot catch an error that is not insincerity, and refusing verify
dispatch when the delta is "only fixes", which is unsound because the fixes live in judgeable files
and refusing would strand the gate uncovered.

## 2026-08-13: prose findings priced honestly

<!-- prawduct: type=feature | scope=tactical-efficiency | release=v3.4.0 -->

Comment and doc wording is 42% of finding volume, and the mechanism that produced it was a gap
between two rules. Goal 4 rated any comment/code contradiction WARNING; the NOTE ceiling for
record prose covered change-logs and plans but not code comments. Nothing constrained the
*remedy*, so "update the narration" was a legal recommendation — which is how one wall-time figure
became nine findings across five rounds on three branches, the tenth edit missing and buying the
round after that.

**Prose is NOTE unless load-bearing** — a test or a gate reads it, or the reviewer names the
concrete wrong action a maintainer takes because of it. That is the existing WARNING bar, now
applied to comment, docstring and doc wording, counts and phrasing rather than only to record
prose. **Stale prose gets one of three remedies**: delete the claim, make it relational, or pin it
with a test. The list is closed — rewording the narration is what ships the sentence the next
round finds stale. And **review history never enters a shipped comment**: ids dangle, so a comment
recounting history is a deletion rather than a correction, since a corrected id goes stale too.
`building.md` carries the builder-side half — history's one home is commits and the change-log.

The ceiling has a floor, which the chunk's own review caught missing: **it never lowers a severity
another rule assigns explicitly.** Without that clause a rule written to suppress findings also
suppresses promoted ones — Goal 4 rates an actively misleading README instruction BLOCKING, and a
reviewer who dutifully named that wrong action would have landed on WARNING, which gates nothing,
shipping the wrong command.

The policy is stated on all three severity surfaces rather than pointed at from two, because their
audiences are disjoint: `goals-1-3.md` is chunk mode's payload, `review-protocol.md` is the
final/cumulative payload, and the PR reviewer reads neither. `test_prose_severity_ceiling.py` pins
all three — the rule's own second remedy, applied to itself, on files under standing pressure to be
trimmed.

**No ceiling was raised.** The `review-protocol.md` and `goals-1-3.md` additions spend the raises
this pass declared in advance; `review-protocol.md` paid 41 tokens of that back by deleting a
model-override rule stated in both the Assess and Dispatch steps. `building.md` had 3 tokens of
headroom and funded the whole addition in place, landing a token *below* where it started: its
Blocking-findings paragraph restated the disposition menu that "Resolve findings" already owns,
the Critic step said "runs as a separate agent" twice, and the seven goal names were spelled out
beside the pointer to the file that defines them.

Not added: any new control. This is a ceiling and a remedy constraint on findings that already
exist, so it is net-subtractive and the observable-yield obligation does not attach.

## 2026-08-13: the cumulative's eight warnings, resolved

<!-- prawduct: type=fix | scope=tactical-efficiency | release=v3.4.0 -->

The branch cumulative (`rev-20260813T174223Z-0cc2fd49`) returned 0 blocking and 8 warnings. Three
were real defects in what had already shipped, and all three came from the same place — a claim
that was true when written and stopped being true later in the same bundle.

**Condition 3 asked about the wrong tree at the PR gate.** `suite_vouches_for_current_tree`
compared saved evidence against the *working* tree, but `check_cumulative_critic` vouches for
`HEAD^{tree}`. With uncommitted judgeable edits the gate could print `satisfied (… suite current)`
for a HEAD tree no suite run had met. It is now `suite_vouches_for_tree(project_dir, target_tree)`
and each gate passes the tree it actually vouches for; the Stop gate's default stays the working
tree, which is its own target.

**The verdict memo's key omitted the code that computed the verdict.** It covered both trees and
the store, but the verdict also depends on `coverage_algebra.is_judgeable_path`, and the cache
persists in `.git/prawduct/` across plugin upgrades — so widening judgeability in a release would
replay `covered` entries the new rules would not grant. `CACHE_SCHEMA` was the intended guard and
is a hand bump nothing enforces; a maintainer changing judgeability has no reason to open a cache
module. The plugin version is now in the key, derived rather than remembered.

**A read path grew a store write.** `_merge_base_verdict` → `record_transfer_grant` appends a fact,
and `session_review_verdict` has two callers: the Stop gate (authority, session end) and the
session-start briefing (advice), which wraps it in a broad `except`. From the briefing the append
was silent, its fail-soft attribution swallowed, filed under a gate that had not run — and it moved
the store fingerprint at session start, evicting the memo the previous chunk had just built.
Recording is now opt-in (`record_grants=`), taken only by the authority path. Advice observes and
writes nothing, pinned by a test.

Also: the `prior_dispositions` instruction was reachable only from Goal 2's section, so two of the
three coordinator reviewers were never told about it — Chunk 03's own mechanism, unreachable for
two thirds of its audience. It moved to `agents/critic-reviewer.md`, which every reviewer reads.
`review-cycle.md` contradicted itself eleven lines apart on whether a rebase demands a fresh
review. Both design artifacts still said only the PR gate transfers, which `243c7761` falsified in
the same bundle. The memo now attributes its degraded states — an inert cache and a failed flush
were both silent, and the symptom is every gate call back on the cold path with nothing to point
at. Chunk 06's acceptance criterion was amended: it named "the scalar left pointing at the
purpose-and-cession plan", which this branch's own pointer flip would have made pass vacuously.

## 2026-08-13: accepted findings stop being re-litigated, and one defect reads as one

<!-- prawduct: type=feat | scope=tactical-efficiency | release=v3.4.0 -->

**Dispositions have been facts for a while; nothing put one where a REVIEWER could see it.** A
cumulative dispatched after an `--accept` handed its reviewers a diff and no memory, so they found
the same true thing again — measured on one consumer branch, round 9 re-raised six of round 7's
findings verbatim, several already accepted.

`critic-begin` now writes a `prior_dispositions` block into the dispatch manifest: findings already
accepted or filed, with their reasons. Only the live answer appears (re-disposition appends, so a
finding can carry a superseded predecessor); truncation is reported, never silent; a failed join
says `unavailable` rather than reading as "no priors". Both reviewer protocol files carry the
instruction, mirroring the existing `record_lint` "already answered, don't recount" pattern.

**Scoping it by cited file alone did not work, and the measurement is the reason it changed.** That
first cut carried 92 entries on a live dispatch — **22,703 of 25,001 manifest bytes (91%), ~5,700
tokens, 2.7× the protocol file the block exists to shorten** — because a repo's hottest files are
cited by nearly every finding it has ever recorded, so the filter was weakest exactly where reviews
concentrate. A control that costs more attention than it saves is not a control. The block is now
scoped by build-plan **scope** as well as by cited file (answers about *this* body of work, which is
what "already answered" always meant), and the entry limit dropped 40 → 15. Re-measured on the next
dispatch: 8,412 of 12,263 bytes (69%).

**Caveat, because the two fixes are not equally proven:** `scope_chosen_by` was `not-resolved` on
that dispatch, so the re-measured drop comes from the limit alone — the scope axis is built and
tested but does not engage until a dispatch resolves a scope, which is what Chunk 06's branch-scoped
plan resolution supplies. A review recorded with no scope matches nothing rather than everything:
an unscoped fact cannot claim to be about this work, and an advisory block whose failure mode is
drowning the review should fail toward carrying less.

**The grouping that was supposed to catch a triplicate reported `[]`.** Three reviewers filed one
defect on one file (R-1/R-5/R-11) and `likely_duplicate_groups` grouped none of them. Cause: Jaccard
divides by the union, so a terse title wholly contained in a verbose one scores low while sharing
every word it has — exactly what happens when three reviewers describe one defect at three levels
of detail. Added a second qualifying path: identical file attributions plus overlap coefficient
(the length-insensitive form of the same question) ≥ 0.6. A floor of 3 significant words on the
shorter title stops the degenerate case a one-word title would create — caught by a test before it
shipped, not after.

Consolidation now also **renders** each group as one defect line with every fid named. The count
already said "~N distinct"; the list is what gets worked, and three separately-worded findings read
as three jobs whatever the count claimed. Presentation only — `merge_findings` still keys exactly
and every finding survives in the fact and the derived view, so a wrong group costs one confusing
line and can never hide a finding. That asymmetry is what lets the bar sit low.

Both budgeted protocol files hit their ceilings. Raised once with the whole pass named
(`goals-1-3.md` 2000→2250, `review-protocol.md` 3620→3800) rather than three creeping raises across
Chunks 03–05; deduping was attempted first and found nothing — the last edit had already squeezed
both to 1–2 tokens of headroom, which their own budget comments record.

## 2026-08-13: syncing a base no longer clears the PR gate and blocks at session end

<!-- prawduct: type=fix | scope=tactical-efficiency | release=v3.4.0 -->

**Two gates asked the same composition question and only one could answer it by transfer.**
`/prawduct:pr` Step 1 prescribes syncing the base before the review gates; that span passes the PR
gate by base-advance transfer, and the *same tree* was then blocked at session end — sending the
builder to run exactly the cumulative round the transfer exists to remove. The Stop gate's
merge-base fallback (`gates.session_review_verdict` → `_merge_base_verdict`) now attempts the same
transfer under the same three conditions.

**Which span, and why only that one.** The Stop gate's own span is the session base tree → the
working tree, and its start node is the tree HEAD sat at when the session opened — no base sync
moves it, and after a sync the diff across it *is* the advance rather than the branch's own work,
so the transfer's first condition could not hold. The merge-base span is the PR gate's span with
the working tree in place of HEAD's tree, which is the shape the diagnosis was written for. The
substitution costs nothing in soundness — uncommitted judgeable work lands in the required diff, so
no reviewed span matches it and the transfer denies with no special case — and condition 3
(`suite_vouches_for_current_tree`) lands more squarely here than at the PR gate, because it asks
about the working tree, which is this gate's target. Attempted on `uncovered` only: a `blocked`
span is owed a blocker and no transfer discharges it. Every unverifiable condition still denies.

**The near miss now reaches the builder.** This gate has no stderr of its own — the Stop hook
renders its verdict — so the "byte-identical, only the suite is stale, run it and re-run" sentence
rides on the verdict's `reason`, and is carried onto whichever verdict is returned. Without that
the fallback's verdict is discarded whenever the primary one already blocks, dropping the cheapest
remedy on exactly the sessions that need it.

**A granted transfer now emits its yield.** The standing norm is that a control names the yield it
expects AND emits that yield observably; the transfer's justification is a measured claim about
review rounds saved, and a yield claim nothing can falsify is not a yield claim. Both gates now
append a `guard-refusal` fact under guard `base-advance-transfer` — the same sink and the same
norm as `critic-begin`'s free-interval refusal — surfaced by
`prawduct-hook evidence list --kind guard-refusal`. No new fact kind, no schema change.

**Why the record is keyed and not timestamped.** `verdict_cache` keys the composed verdict on a
content hash of the whole evidence store, and the gates are polled several times a session, so a
record per *poll* would evict every memoized verdict on every poll and hand back the ~17 s cold
path the memo was built to remove. `evidence.append_guard_refusal` gained an optional `dedupe_key`:
the id becomes a digest of `(guard, key)` with no timestamp and no uuid, a second observation
returns `duplicate` and writes nothing, and the store stays byte-identical across repeated gate
calls (pinned by test at both gates). The probe reads the caller's already-parsed facts rather than
re-opening a 7 MB store — the same one-read/one-moment pairing `VerdictCache.for_read` makes
structural. The residual, stated: the *first* grant does append, so the poll after it recomputes
cold — once per transferred span, against a review round saved.

The key is the span (`base_tree`, `head_tree`, `prior_base`, `prior_head`) and deliberately not the
gate, which rides in the body instead. When the two gates coincide on one span they describe one
base sync that one cumulative would have paid off, and counting it twice would inflate the yield of
the control the record exists to audit — `count_branch_rounds` states the same preference for the
same reason. Recording is fail-soft like its sibling and never silent: a store failure is
attributed on stderr and the correct verdict stands.

## 2026-08-13: the PR gate answers in constant time

<!-- prawduct: type=perf | scope=tactical-efficiency | release=v3.4.0 -->

**Asking whether a review was needed cost more than some reviews.** Nine `check-cumulative-critic`
invocations in one consumer session ran 29–120 s each; two hit the 2-minute Bash ceiling (one
`Exit code 143`) and the agent resorted to `timeout 200`. Profiled on this repo before building
anything: `read_facts` is 0.06 s and merge-base resolution 0.07 s, while
`coverage_algebra.coverage_verdict` is **17.4 s cold and 0.01 s with the per-invocation key cache
warm** — the whole cost is the free-edge search keying every tree the store mentions, one
`git ls-tree` each (701 trees here, and the store only grows).

`verdict_cache.VerdictCache` memoizes the composed verdict, keyed on a content hash covering every
input: both endpoint trees and a SHA-256 of the entire evidence store. Measured end to end on this
repo: **20.0 s → 0.35 s.** The three call sites that need a composed verdict — the span itself,
the fix-churn diagnosis and the base-advance transfer — now share one cache; both diagnoses take a
`verdict_fn` in place of the `diff_fn`/`key_fn` pair they only ever used for that call.

**Why this is a memo and not a second home for a fact** (`data-model.md`: *derived views are
disposable and never authoritative*): the key covers every input the verdict is a function of, so
a hit replays a computation whose inputs are provably unchanged. Miss, unreadable cache, corrupt
entry, foreign schema or unreadable store all recompute. **And a cached verdict can never be a
false PASS:** git objects are immutable and content-addressed, so they are not in the key and do
not need to be — `coverage_verdict` grants `covered` only through review edges (from facts, which
ARE keyed) and free edges (tree-key equality), and a missing object makes `key_fn` return `None`,
which denies a free edge and can never manufacture one. Git-side degradation therefore moves the
verdict only toward denial. The residual, stated rather than implied: an `uncovered` computed while
an object was transiently unreadable is replayed until the store's next append.

The flush is unconditional (a `try/finally` wrapper), because the gate has four exit paths, three
of them failures — and polling happens most when the gate is *not* passing, so a memo that only
persisted on success would leave exactly its motivating case uncached. Cache lives beside the
evidence store in the per-clone `.git/prawduct/` area, bounded at 64 entries.

One test changed rather than being added to: the pin that `diagnose_fix_churn`'s injected functions
carry no defaults now names `verdict_fn`, which carries both properties a forgotten argument would
cost. Same contract, same direction, applied to the parameter that now holds it.

## 2026-08-13: a clean base sync no longer voids review coverage

<!-- prawduct: type=feat | scope=tactical-efficiency | release=v3.4.0 -->

**A base advance moved the PR span's start node, so a branch whose own diff had not moved a byte
read `uncovered` and bought a full re-review.** Measured in the busiest consumer repo (which merges
its base ~20×/day): two of three cumulative rounds on one branch existed only for this reason, and
the round after a sync re-raised six of the previous round's findings verbatim — ~30 of 60 review
minutes on a 6-fix branch were base tax. In both observed forced syncs, every merge conflict was in
prawduct's own non-judgeable record files.

`check-cumulative-critic` now attempts a computed **transfer** before reporting `uncovered`
(`coverage.diagnose_base_advance_transfer`): a span already covered transfers to the required one
when the two spans' judgeable changed-file sets are identical, every one of those files is
byte-identical on both ends, and a saved suite run has met the resulting tree. Computed, never
stored — the free-edge philosophy. Any condition unverifiable denies the transfer and today's
remedy stands, because authority fails closed.

**The third condition is `gates.suite_vouches_for_current_tree`, deliberately stricter than
`tests_are_current`.** That function is a disjunction whose first clause asks only *when* a run
happened — the right question for "should this session re-run the suite", and the wrong one here: a
suite at 09:00, a base merged at 11:00 and a gate at 11:05 satisfies session-freshness while no run
has ever seen the merged tree, which is precisely the exposure condition 3 exists to price. Only
the tree-validity clause counts for a transfer, and evidence carrying no `evidence_tree` (the
`--from-counts` on-ramp) denies rather than falling back to timing.

`evidence.tree_diff` gained an optional pathspec, and a path this function REPORTS must be one it
can be asked back about — the transfer feeds the returned list straight back in as a pathspec. Two
git conventions break that round trip, and both are answered at the boundary. **`-z`, because
`--name-only` honours `core.quotepath`:** a non-ASCII filename came back C-quoted
(`"caf\303\251.py"`, quotes included), matched nothing as a pathspec, and the empty answer read as
agreement — a genuine fail-OPEN that granted a transfer over an *edited* branch file, caught by the
verify pass and now pinned by a fixture that fails loudly without `-z`. (`core.quotepath=false` is
insufficient: names holding `"` or `\` stay quoted regardless.) **`:(literal)` on each pathspec,**
because pathspecs are wildmatch patterns. Measured rather than assumed: git compares literally as
well, so a path does select its own spelling — but `x[a].py` also selects `xa.py`, letting an
unrelated file answer a question asked about this one. That direction is a silent spurious denial
rather than a wrong pass; `:(literal)` removes the class instead of resting on git's match order.

**The soundness boundary is byte equality ACROSS contexts, not content equivalence WITHIN one** —
the 2026-07-29 ruling (COV-3M8Q) is untouched, and any edit at all to a branch file, comments
included, denies the transfer. Candidates are selected by content rather than commit ancestry, which
is what makes the rebase case work at all: rebasing rewrites the very commits a branch's facts
anchor to while leaving the trees they vouch for identical. The one new exposure — a reviewed diff
meeting advanced context in disjoint files — is what the test-evidence condition prices, and a
transfer denied ONLY by stale evidence says so, naming a suite run rather than a review round.

Riders: `/prawduct:pr` Step 1 now syncs the base BEFORE the review gates (#565's ordering fix), and
the Update flow states that a base-sync merge introducing no judgeable authored content is not
substantive and does not re-run the PR reviewer.

## 2026-08-13: a model floor, and a frontier coherence pass over every cycle

<!-- prawduct: type=docs | scope=purpose-and-cession | release=v3.4.0 -->

Owner decision 2026-08-13: **Sonnet is the minimum model for any prawduct work**, main session or
subagent — Haiku-class models are never used — and any cycle whose substantive stages ran below
Fable closes with a **Fable final-coherence pass** over the whole result before it lands. Scaling
cost down is legitimate for mechanical stages, but sub-frontier models miss exactly the
cross-cutting incoherence prawduct exists to catch.

Both are **session-level operator choices**, which is why the Enforcement row reads *Session
config / user-observed* rather than Test: the runtime cannot observe which model it is, and a
mechanical selector would reopen the "no intelligent model switching" pin. Reviewers still inherit
the session model. Recorded in `project-preferences.md`; the per-cycle mapping for Cycles 2–4 is in
`program-purpose-and-cession.md`.

## 2026-08-13: the four-cycle program gets a durable home

<!-- prawduct: type=docs | scope=purpose-and-cession | release=v3.4.0 -->

**The parent requirement document for Cycles 2–4 lived only in a gitignored file that `/clear`
regenerates.** `.prawduct/.handoff-notes.md` carried the owner-ratified program — the #181
deletion-pass framing and its constraints, the responsibility-ledger design, the sibling-first
telemetry plan, the prose-test taxonomy, the disposition seed rows, and an open learnings-rule
candidate — and `build-plan-purpose-and-cession.md` cited it four times as its parent source.
That plan is committed; the file it pointed at is not, and was consumed at the next `/clear`.

`.prawduct/artifacts/program-purpose-and-cession.md` is now that home, following the
`framework-efficiency-review-2026-07-02.md` precedent (a committed parent requirement document
for a multi-wave program). The build plan's four references are repointed. Purpose and
principles are referenced, never restated — `documentation/purpose.md` and
`plugin/docs/principles.md` keep their one-home ownership, as does `project-preferences.md` for
the model-floor norm; this file carries only the per-cycle model mapping.

## 2026-08-13: principles 25 and 26 — the moving-target posture, codified

<!-- prawduct: type=docs | scope=purpose-and-cession | release=v3.4.0 -->

New `## Evolution` section in `plugin/docs/principles.md` (owner decision 2026-08-12, per
Principle 19): **#25 Third Rework Is a Deletion Signal** (proposed by the 2026-07-02 efficiency
review, unadopted until now; four recorded supporting cases) and **#26 Graceful Cession**
(mechanisms carry the assumptions that justify them; a broken assumption forces a re-price).
Cascade: roster test 24→26, CLAUDE.md roster + purpose pointer (paid by cutting the
Sessions/Work-Cycles copy building.md owns and the duplicate principles pointer; 148 lines),
session-digest roster line (paid in-file; net −2 chars).

## 2026-08-13: the framework records its own purpose

<!-- prawduct: type=docs | scope=purpose-and-cession | release=v3.4.0 -->

**Prawduct required every product to record its vision and never recorded its own** — verified
against full git history: nothing purpose-shaped ever existed, and six artifact frontmatters
pointed the product-brief slot at "README.md + CLAUDE.md", neither of which states a purpose.
`documentation/purpose.md` is now the one home (architecture.md "every fact has one home");
those six comments now reference it.

**The content is an owner decision, not agent inference** — ratified 2026-08-12 in session,
recorded here so the authority lives outside the documents it authorizes: the value proposition
(build on today's runtimes to close the gap to what consumers need; cede what the rising
baseline absorbs and move higher — the gap never closes because requirements arrive late, which
is human nature, not tooling immaturity), the three-hedge taxonomy with distinct depreciation
schedules, the durable core (mandate + record + audit), continuous fractional drift over step
functions, deletion with the same care as addition, and directional-by-construction telemetry.
This entry's cycle precedes the #181 (GOV-6D4Q) deletion-only pass deliberately: the pass's
"why" belongs on disk before the pass runs. Principles 25 and 26 land in this same scope's
second chunk.

## 2026-08-12: an agent worktree on a real branch is not disposable

<!-- prawduct: type=fix | scope=durable-agent-worktrees | release=v3.4.0 -->

**The Critic gate was unsatisfiable for any branch worked in an agent worktree, with no
workaround.** `is_ephemeral_worktree` classified from the directory name alone — anything under
`.claude/worktrees/agent-*` was disposable — and returned before ever reading the branch. A
worktree holding `fix/gate-integrity` was therefore refused every `.prawduct/` write, `critic-begin`
included, with a message whose stated reason ("discarded when it merges") was false for exactly
that tree. The only route left was evicting the worktree to check the branch out in the clone.
Reported from a product repo running four concurrent agents (brookstalley/discodon#2213); a full
review ran, produced four substantive warnings, and recorded nothing.

**The discriminator is what carries the write out, not where the tree sits.** #594's defect is a
*separation*: an `isolation: "worktree"` agent's code commit returns while its `.prawduct/` write
dies at the merge, so the write strands and the agent is told it succeeded. That separation is a
property of the harness's own `worktree-agent-<hex>` scratch branch. On a real named branch there
is nothing to separate — the branch is what lands, so the whole tree is carried; and if the branch
is discarded the code goes with it, leaving nothing silently ungoverned.

**That inseparability is assumed, not measured.** Verifying it against the harness's actual
disposal policy means dispatching a probe agent, which this session was asked not to do. The
falsifier is precise, and it is recorded in `is_ephemeral_worktree`'s docstring and the hook's
guard header so it outlives this entry: if the harness ever merges a code commit *off* a named
branch while discarding that branch, the separation exists after all and #594's silent strand
returns for that case.

So the branch is now a second conjunct for `agent-` paths. `wf_` stays path-only, because a
workflow stage gets no named branch and there the path IS the identity. A detached or unreadable
HEAD stays disposable — the restrictive side, so a failing git probe can never become a way to
unlock the guard.

**This makes concurrent agent worktrees work without any new arbitration.** `.prawduct/` already
resolves per-worktree (STH-4K7N), so once the classification is right, N agents each get their own
state, their own critic marker, and their own test evidence. The upstream report also described
`.test-evidence.json` as a shared single slot that concurrent lanes overwrite; it is not shared,
and the overwriting was a symptom of this same guard funnelling every lane into the clone. A test
pins that (`TestConcurrentLanesDoNotCollide`), which is what closes it rather than an argument.

Evidence facts now record `actor.branch`, omitted rather than null when HEAD is detached. Without
it the historical reader and the live predicate would disagree about the same path — and
`evidence status` would print "the review cost was spent, the coverage was not gained" over
precisely the durable reviews this change enables. Facts written before the field keep exactly the
reading they had.

## 2026-05-09: Requirements Precede Code — visible/assessed requirements clarity (v1.3.15)

**Why:** Recurring quality issues across products using Prawduct trace to a common root: both user and agent get excited and start design/code before requirements are clear. The previous framework had no friction at the right boundary — Critic and PR review fire *after* code exists, by which point design is committed. Discovery was treated as a one-time phase, with each new feature implicitly skipping its own micro-discovery. The agent had no trigger to pause when the user said "build X." The cure couldn't be heavy gates (too straitjacketing) or pure principle (history shows judgment alone won't interrupt momentum) — it needed light, distributed friction that surfaces requirements clarity at multiple places without blocking.

**What:** Six interlocking changes, all in service of the same idea: make requirements clarity a visible, assessed property at every appropriate boundary.

1. **New Quality principle: Requirements Precede Code (#6).** "Code built on unclear requirements is debt the moment it's written." Sits beside Honest Confidence (#5): one is about what you know; this is about whether you understand the problem. Old principles 6-22 renumbered to 7-23; active by-number references swept across `methodology/`, `templates/`, learnings, registry, and test scenarios in both "Principle N" and "(#N)" forms. Historical files (changelog, reflections, change_log_history) left frozen per the framework's existing rule.

2. **Requirements Confidence field on build plans.** `templates/build-plan.md` now has a required section between YAML frontmatter and Status: Level (High | Medium | Low), Why (one sentence), Open assumptions / unknowns, What would raise confidence. The field is honest self-assessment, not a gate. `methodology/planning.md` documents the semantics under Build Planning.

3. **Pre-build readiness check.** `methodology/building.md` gains a "Before You Build: Confidence Check" section before The Build Cycle — three questions in one sentence each (problem, success, out-of-scope), three response options when unclear (close the gap, sketch and confirm, proceed knowingly).

4. **Recursive discovery framing.** `methodology/discovery.md` promotes "Discovery Recurs" from a buried trailing paragraph to a top-of-file section. Distinguishes initial discovery (project foundation) from feature-level discovery (the same three questions at smaller scale, captured in the Confidence field).

5. **Agent-side trigger in CLAUDE.md.** Both framework `CLAUDE.md` and `templates/product-claude.md` now have "Before Building: Requirements Clarity" sections that fire when the user says "build X" / "implement Y" / "let's add Z." Three questions, cheap close, don't interrogate (pairs with Principle 20 — Infer, Confirm, Proceed).

6. **Critic Goal 2 checks.** `agents/critic/SKILL.md` and `templates/critic-review.md` Goal 2 (Nothing Is Missing) gain two new checks: (a) acceptance criteria as observable behavior, not implementation ("function X exists" is implementation; "user can submit form and see confirmation" is behavior) → WARNING; (b) Requirements Confidence field present, with open assumptions listed if Medium/Low → WARNING. Catches overstated confidence after the fact, creating downstream pressure on the upstream framing.

**Bootstrap demonstration:** the build plan for this work itself used the new Requirements Confidence field before Chunk 02 codified it (declared "High" with an Open Assumption about exact prose for new Critic bullets). That uncertainty held: the prose got refined under token-budget pressure during Chunk 04. Useful proof that the field surfaces unresolved bits without blocking progress.

**Behavioral notes:**
- The check sits before methodology, not as a gate. No stop-hook or other enforcement blocks low-confidence plans. The forcing function is honest self-assessment plus downstream Critic visibility.
- "Don't interrogate" disclaimer in both CLAUDE.md sections explicitly pairs the check with Principle 20 (Infer, Confirm, Proceed). One inference to confirm > five questions.
- Discovery's existing closing paragraph (which mentioned recurrence) was reduced to a pointer at "Discovery Recurs" earlier in the file, avoiding duplication.
- Two token-budget bumps: `methodology/building.md` 4100 → 4250 (Before-You-Build section, ~100 tokens after aggressive trim); `templates/product-claude.md` block 2900 → 3050 (Before-Building section, ~110 tokens). Both bumps documented in test rationale matching prior bump pattern.
- `templates/skill-critic.md` is a thin launcher pointing at `.prawduct/critic-review.md`; product Critic instructions reach product repos through `templates/critic-review.md` (already updated). No edit needed there.

**Files:**

- `docs/principles.md`: new Principle 6 inserted after Honest Confidence; principles 6-22 renumbered to 7-23
- `CLAUDE.md`: inline-numbered Quality list gains entry at 6; Product/Process/Learning/Judgment clusters renumbered; new "Before Building: Requirements Clarity" section between Sessions and Methodology
- `methodology/building.md`: new "Before You Build: Confidence Check" section before The Build Cycle; principle-by-number references updated (Principle 11 → 12, 22 → 23)
- `methodology/discovery.md`: new "Discovery Recurs" section after Risk Calibration; trailing recurrence paragraph reduced to pointer; principle-by-number references updated (Principle #6 → #7, 7 → 8, 8 → 9)
- `methodology/planning.md`: new "Requirements Confidence" subsection under Build Planning
- `templates/build-plan.md`: new "Requirements Confidence" section between frontmatter and Status; principle-by-number reference updated (Principle #9 → #10)
- `templates/build-governance.md`: condensed mirror of the readiness check before the Build Cycle steps
- `templates/product-claude.md`: new "Before Building: Requirements Clarity" section in framework-managed block; Quality principle list gains "Requirements Precede Code"
- `agents/critic/SKILL.md`: Goal 2 (Nothing Is Missing) gains two bullets — acceptance criteria as observable behavior, Requirements Confidence field present
- `templates/critic-review.md`: matching dense-paragraph form for product Critic instructions
- `.prawduct/cross-cutting-concerns.md`: principle-by-number references updated (Principle 7 → 8, 9 → 10); new "Requirements clarity" row added with full pipeline coverage
- `.prawduct/learnings.md`, `.prawduct/learnings-detail.md`: `(#N)` references swept (#21→#22, #17→#18, #16→#17, #14→#15, #13→#14, #12→#13, #10→#11, #9→#10)
- `tests/scenarios/family-utility.md`, `background-data-pipeline.md`, `terminal-arcade-game.md`: principle-by-number references updated (Principle 7→8, 10→11, 22→23)
- `tests/test_v5_methodology.py`: building.md token budget 4100 → 4250 with rationale
- `tests/test_v5_templates.py`: product-claude.md block budget 2900 → 3050, total 3500 → 3650, with rationale; TestProductClaudePrinciples parametrize updated to enumerate all 23 principles (adds Principle 6, shifts subsequent)
- `README.md`: four occurrences of "22 principles" → "23 principles"
- `docs/project-structure.md`: two occurrences of "22 principles" → "23 principles"
- `.prawduct/backlog.md`: token-budget-bumps item promoted from Queue to "Active — next up" (third bump trigger fired this release)
- `VERSION`: 1.3.14 → 1.3.15
- `.claude/settings.json`: banner v1.3.14 → v1.3.15

**Post-/critic-final fixes:** the README/project-structure/test-parametrize/cross-cutting-row/backlog-promotion edits in this list landed in response to three warnings and one note from `/critic final`. The Critic catching the "22 principles" drift in user-facing docs and the test-contract drift in the principles parametrize was a clean illustration of why final-mode is needed: chunk-mode reviews scope to changed files; final-mode reads cross-cutting summaries (README, registry, test enumerations) that drift silently when a sweep misses them.

## 2026-05-08: Stale-clean detection auto-resolves false-edit syncs (v1.3.14)

**Why:** When a product repo gitignores `sync-manifest.json` (the convention for several large client projects), every fresh clone bootstraps the manifest from current on-disk hashes. After a few framework releases, those hashes drift from what current templates would produce — so `template`-strategy files look "locally edited" to sync, even when no human ever touched them. Empirically: 5 of 6 currently-stale files across `discodon` and `discodon-brooks2` were stale-clean, hiding the one file with a real edit under `--force` advice noise. The conservative skip behavior was hostile to upgrade UX precisely when the framework released improvements.

**What:** Sync now detects stale-clean files via historical template render. When a `template`-strategy file's hash doesn't match the manifest's stored hash AND doesn't match the current rendered template, sync walks the framework's git history of that template (with `--follow` for renames, capped at 100 commits, with per-sync render caching). If any historical render matches the current file content, the file is framework-produced from an older version → safe to overwrite without `--force`. Auto-resolved files emit `Auto-resolved {file} (stale-clean from {short_sha})`. Files matching no historical render fall through to the existing skip-with-`--force` behavior — no change in handling for genuine local edits.

The same classification powers `prawduct-doctor`'s `framework_currency` check, which now reports per-file class (`stale-clean` / `local-edit` / `missing`) with an action-oriented detail string and recommends the appropriate next step.

**Behavioral notes:**
- Stale-clean detection runs *before* the `--force` fallback. When a file is both stale-clean and `--force` is set, the action label is `Auto-resolved` (truer to what happened) rather than `Force-updated`. The user's `--force` intent is preserved for genuine local edits, where it's still required.
- `block_template` files (CLAUDE.md) and `always_update` files always overwrite on sync per their existing strategy — doctor classifies any drift as `stale-clean` for those. This piggybacks on the v1.3.13 marker contract change (framework owns content inside `PRAWDUCT:BEGIN/END`).
- Briefing's `Drifted templates` header renamed to `Place-once template advisories` to clarify it's about the place-once template set (project-preferences, boundary-patterns, change-log, backlog, conftest.py) — files the user owns where the framework template has evolved. Distinguishes from doctor's `framework_currency` lens, which covers the managed file set sync actively maintains.

**Files:**

- `tools/lib/sync_cmd.py`: new `_HISTORICAL_RENDER_DEPTH_CAP = 100` constant. New `_match_historical_render(fw_dir, template_rel, target_hash, subs, cache=None)` helper — walks `git log --follow --format=%H --name-only` and pairs each historical SHA with the file's path at that commit, so renamed templates are findable via `git show <sha>:<historical-path>`. Cache keyed by `(sha, historical_path)`. `run_sync()` `template`-strategy branch declares a per-sync `historical_render_cache` and calls the helper between the existing autofix and the local-edits skip.
- `tools/lib/__init__.py`, `tools/prawduct-setup.py`: re-export `_match_historical_render` and `_HISTORICAL_RENDER_DEPTH_CAP` for the legacy importlib test surface.
- `tools/lib/validate_cmd.py`: `framework_currency` refactored to classify each stale file as `stale-clean` / `local-edit` / `missing`. Detail string format: `"<N> files differ — <K1> auto-resolve on next sync (X, Y); <K2> have local edits (Z — review diff or sync --force); <K3> missing (W — sync will create)"`. Recommendations are action-oriented per class. Restart files only listed when they will actually change.
- `tools/product-hook`: briefing label renamed `Drifted templates` → `Place-once template advisories`.
- `VERSION`: `1.3.13` → `1.3.14`.
- `.claude/settings.json`: banner string `Built with Prawduct v1.3.13` → `v1.3.14`.
- `tests/test_prawduct_sync.py`: new `TestMatchHistoricalRender` (7 tests covering HEAD/mid-history match, no-match, --follow across renames, no-git fallback, depth-cap, cache hit). New `TestStaleCleanDetection` (6 tests covering auto-resolve happy path with manifest refresh, genuine-edit skip preservation, --force still works for genuine edits, stale-clean precedence over --force, mixed-batch per-file outcome, per-sync cache populated).
- `tests/test_product_compat.py`: new `TestDoctorClassification` (4 tests covering stale-clean classification, local-edit classification, mixed-class aggregation, happy path unchanged).

## 2026-05-08: `block_template` — framework owns content inside markers

**Why:** Discodon sync from v1.3.5 → v1.3.13 reported `Skipped CLAUDE.md — block has local edits` even though the local block had no user customization — it was just stale framework content from the previous sync. Investigation showed the same false-edit signal would fire on every framework upgrade for repos that gitignore `sync-manifest.json` (which bootstraps fresh per clone, recording on-disk hashes that don't match what the current template renders). The marker convention already promises "framework-owned region" (the `<!-- PRAWDUCT:BEGIN -->` / `<!-- PRAWDUCT:END -->` markers exist for exactly that purpose) but sync was treating in-block content as co-edited shared space.

**What:** `block_template` strategy now always overwrites content between the markers on sync. Content **outside** the markers (before/after) is preserved verbatim, as it always was. The `--force` flag is now a no-op for `block_template` (kept on the CLI for `template`-strategy files).

**Backwards-compat note:** Product repos with hand-edited content **inside** the markers will lose those edits on the next sync. The marker convention has always implied this contract; this change aligns sync behavior with the convention. User customization should live outside the markers.

**Files:**

- `tools/lib/sync_cmd.py`: `block_template` branch simplified from ~90 to ~50 lines. Removed the `stored_hash != product_block_hash` skip-and-`--force` codepath and the separate "Restored" drift-repair branch (those cases now collapse into a single always-overwrite splice).
- `tests/test_prawduct_sync.py`: `test_skips_user_edited_block` → `test_overwrites_user_edits_inside_block`; `test_user_edited_block_skipped` → `test_user_edits_inside_block_overwritten`; `test_force_overwrites_user_edited_block` → `test_force_flag_no_op_for_block_template`; `test_restores_drifted_block` updated to match the unified action label.
- `tests/test_coverage_gaps.py`: `test_block_template_force_overwrites` → `test_block_template_overwrites_user_edits`; `test_drifted_block_restored` updated to match the unified action label.
- `README.md`: sync section now distinguishes whole-file template behavior (skip + `--force`) from block-template behavior (always overwrite inside markers, customize outside).
- `.prawduct/backlog.md`: added two follow-ups for the `template`-strategy false-edit problem (stale-clean detection via historical render; sync skip-summary line counts + `--diff` preview). Removed the now-obsolete `block_template` 3-way merge item.

## 2026-05-08: Proportional Critic — `chunk` and `final` modes (v1.3.13)

**Why:** Per-chunk Critic reviews were redoing repo-wide checks (Coherence, Design, Learnings Cross-Check, Backlog Reconciliation, README/docs scan, Framework-Specific Checks 7-10) on every chunk of a multi-chunk build plan, each taking 4-10 min on large repos. A 5-chunk plan paid 25-50 minutes of Critic time, then `/pr` invoked the PR reviewer to do most of the same checks again over the full diff. Most of that work was redundant: chunk-local correctness (Goals 1-3) catches the high-frequency failures (fix-by-fudging, dropped requirements, broad exceptions) and is cheap; the cross-cutting goals need the full session diff to do their job and belong at end-of-cycle, not on every chunk.

**What:** Two named Critic modes, declared per chunk in the build plan:

- **`chunk`** — Goals 1-3 only, single-pass, scoped to the chunk's uncommitted diff. Skips coordinator pattern, Learnings Cross-Check, Backlog Reconciliation, README scan, Framework-Specific Checks. Target 1-2 min.
- **`final`** — all 7 goals + cross-checks + Framework-Specific Checks. Coordinator pattern eligible for medium/large work. Target 4-10 min.

**Caller-side / persisted-side split:** The slash-command argument and build plan field use the short token (`chunk` / `final`) for ergonomics. The `mode` field persisted in `.prawduct/.critic-findings.json` uses the verbose form (`"chunk (lighter pass, not ready for push)"` / `"final (full review, ready for push)"`) so session briefings, gate WARNINGs, and anyone reading the JSON sees the implication without consulting docs. The hook validator rejects bare short tokens in the persisted form so writer drift surfaces immediately.

**Files:**

- `agents/critic/SKILL.md`, `templates/critic-review.md`: new `## Modes` section, mode-aware activation steps, JSON schema example with verbose `mode`.
- `agents/critic/review-cycle.md`: `## Mode Selection` and `## Per-Mode Behavior` sections; updated "When Review Is Required" matrix.
- `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`: `argument-hint: chunk | final` in frontmatter; `$ARGUMENTS` parsing in body; default-to-`final` rule.
- `templates/build-plan.md`: chunk template adds `**Critic mode:** [pick one: chunk or final]`; standard Done-When step 2 reads `/critic <mode>`; Governance Checkpoints adds `**Commit & PR cadence:**`.
- `methodology/planning.md`: new `### Critic Mode Per Chunk` subsection (heuristic, per-chunk-commit contract, fail-safe default).
- `methodology/building.md`: build-cycle Critic step reads `Critic mode:`; new `### Modes` subsection under `## The Critic`; new "Skipping `final` mode" Common Trap.
- `templates/build-governance.md`: build-cycle Critic step references the mode field for product repos.
- `tools/product-hook`: module-level constants `_CRITIC_MODE_CHUNK`, `_CRITIC_MODE_FINAL`, `_CRITIC_MODE_VALUES`. `validate_critic_findings()` accepts records with verbose `mode` (chunk or final) or no mode field; rejects bare short tokens, unknown strings, non-string values. New `_count_build_plan_chunks(prawduct_dir)` helper. New `_critic_session_satisfies_gate(prawduct_dir)` helper — returns `(False, reason)` when a multi-chunk plan has all chunks `[x]` but the latest review was chunk-mode. `cmd_stop` wires the helper as Gate 2.5 (advisory NOTE on stderr, not blocking).
- `VERSION`: `1.3.12` → `1.3.13`.
- `tests/preferences/test_critic_skill_structure.py`: new file with 27 structure tests across `TestCriticModeDocumentation`, `TestCriticVerboseModeStrings`, `TestCriticSkillEntryPoints`, and `TestProportionalCriticMethodology`.
- `tests/test_product_hook.py`: new `TestCriticModeGate` class (15 tests covering the satisfies-gate helper, `validate_critic_findings` mode validation, and end-to-end stop-hook advisory output).
- `tests/test_v5_methodology.py`: SKILL.md token budget bumped 3500 → 3700; building.md token budget bumped 3900 → 4100. Both with in-line rationale comments and a "prefer trimming next time" reminder.

**Verification:** 894 → 937 tests passing, 0 failed (43 new). All three chunks of the proportional-Critic build plan shipped under the new modes (Chunks 01-02 used `chunk` mode at 3-4 min each; Chunk 03 will use `final` mode for end-of-cycle synthesis). The mode contract is self-applied: this build plan declared `Critic mode:` per chunk before the field was formalized in the template, and the template change in Chunk 02 retroactively conformed.

**Backwards-compat note:** Existing product repos see no breakage. Build plans without a `Critic mode:` field default to `final` (fail-safe to thoroughness). Legacy `.critic-findings.json` records without a `mode` key are still valid (the validator continues to accept them; the gate helper treats them as final). Slash-command invocation `/critic` (no argument) still works — the Critic agent defaults to `final` when `$ARGUMENTS` is empty or unrecognized. The advisory gate is non-blocking, so even product repos that miss the mode contract entirely continue to pass governance — they just won't get the speedup.

## 2026-05-05: Test-evidence schema validator + field rename `test_command` → `command` (v1.3.12)

**Why:** `tests_are_current()` in `tools/product-hook` reads `.prawduct/.test-evidence.json` via `.get()`, so writer typos like `ran_at` for `timestamp` or `num_passed` for `passed` parsed silently as "no failures, no timestamp" — failing the freshness check for the wrong reason and burying the actual bug. A discodon-brooks2 build session (commit `3403d23`) added a schema validator to its local product-hook to catch this loud, then asked for the change to be upstreamed so the framework's per-session sync would stop reverting it. Audit also surfaced a documentation/code split: `templates/build-governance.md` documented the field as `test_command`, but the validator (and 3 of 4 sampled real product repos) used `command`. Reconciled to `command`.

**What:**
- `tools/product-hook`: new `_EVIDENCE_REQUIRED_FIELDS` table (`timestamp: str`, `passed: int`, `failed: int`, `skipped: int`, `duration_seconds: int|float`, `command: str`) and `_validate_evidence_schema()` helper. Wired into `tests_are_current()` between the JSON-parse check and the existing fail/timestamp checks, so `test-status` surfaces missing-field and wrong-type errors by name. New `validate-evidence` subcommand exposes the schema check standalone for CI / pre-commit usage; exit 0 = `valid`, exit 1 prefixes stderr with `missing:` / `unreadable:` / `invalid:` / "evidence is not a JSON object" depending on the failure mode. Missing-field check returns before wrong-type check so a single fix-it pass addresses higher-priority repairs first.
- `templates/build-governance.md`: JSON example renamed `test_command` → `command`. New "Required vs. recommended" sentence distinguishes validator-required fields from recommended metadata (`git_sha`, `total`) and free-form extras (`chunk`, `branch`, `notes`) which remain allowed.
- `tests/test_product_hook.py`: existing `TestTestStatus` fixtures updated to include `skipped`, `duration_seconds`, `command` (the new strict schema rejects evidence missing any of them). New `test_schema_violation_surfaces_in_test_status` confirms the schema check fires before the freshness fallback. Two new classes — `TestValidateEvidenceSchema` (8 cases: full-valid, extra-fields-allowed, float duration, single missing field, multiple missing fields sorted+joined, single wrong type, multiple wrong types semicolon-joined, missing-takes-precedence-over-wrong-type ordering) and `TestValidateEvidenceSubcommand` (5 cases: missing file, unreadable JSON, non-dict root, schema-invalid, valid). Helper `_valid_evidence()` produces a fully-schema-valid baseline so tests construct the violation case rather than the whole dict.
- `VERSION`: `1.3.11` → `1.3.12`.

**Verification:** 880 → 894 tests passing, 0 failed (14 new). Smoke tests pass: a `.test-evidence.json` with `"ran_at"` (typo) instead of `"timestamp"` → `python3 tools/product-hook test-status` exits 1 with `stale: evidence missing required field(s): timestamp`; the framework's own freshly-written `.test-evidence.json` validates clean via `validate-evidence`.

**Backwards-compat note:** Product repos with an existing `.test-evidence.json` written under the old documented schema (`test_command` instead of `command`) will report stale on the first session post-upgrade because `command` is now required. Recovery is one re-run of the test suite — no migration tooling is shipped because the cost is low and the alternative (auto-rewriter at sync time) adds permanent surface for a one-time event. Products that already use `command` (verified: discodon, discodon-evals, discodon-brooks2) see zero impact.

## 2026-05-01: Structured Framework Freshness briefing block + anti-conflation guidance

**Why:** A discodon session (running against this prawduct dir) was asked "is prawduct updated?" and produced a wrong answer: it claimed `last_sync 2026-04-23 predates v1.3.10 (committed 2026-04-21)` (logically inverted), and conflated commit-level drift (today's unversioned commit `5885600`) with version-level drift (which didn't exist — discodon already had v1.3.10). Three independent facts (last_sync timestamp, framework version, template advisory) got synthesized into one wrong narrative. The briefing's existing `Advisories: 1 template(s) have new content` line gave the agent only enough information to improvise — and it improvised badly.

**What:** The fix has two parts that reinforce each other:

(1) **Structured freshness facts in the session briefing** — replaces the one-line advisory with a `Framework freshness:` block that pre-computes and presents:
- Framework HEAD short SHA + date + version
- Last-sync commit + date + version (read from manifest)
- Commit delta (computed via `git rev-list --count last_sync_commit..HEAD`, or "unknown" for legacy manifests without `framework_commit`)
- Version delta (when versions differ)
- Drifted templates with their causing commit, date, and subject

The agent now reads facts, doesn't derive them. Surfaces only when there's drift to reason about (commits behind, version delta, or drifted templates) — silent when in sync.

To support this, sync now records `framework_commit` (short SHA of fw HEAD) in `sync-manifest.json` at sync time. Old manifests will populate the field on next sync. Template-drift advisories are enriched with `last_changed_commit`, `last_changed_date`, and `last_changed_subject` via `git log -1 -- <template>` against the framework dir. All git lookups degrade gracefully — when fw_dir isn't a git repo or git is unavailable, fields are empty strings or None, and the briefing renders an "unknown" delta or falls back to the simple advisory list.

(2) **Anti-conflation section in `templates/product-claude.md`** — a new `Framework Freshness` subsection names the three drift dimensions (version / commit / template) explicitly and warns against synthesizing them into "on/off latest". Adds ~50 tokens; required bumping the block budget from 2,800 to 2,900 (deliberate revision, documented inline in the test).

**Verification:** 851 → 880 tests passing, 0 failed. 17 genuinely new tests + 12 inherited reruns (the two new sync test classes inherit `TestRunSyncPlaceOnce`'s 6 setup-validation tests, matching the existing `TestRunSyncTemplateDrift` pattern):
- `TestComputeFrameworkFreshness` (4 new) — manifest extraction, legacy-manifest handling, malformed-JSON guard
- `TestBriefingFreshnessBlock` (6 new) — in-sync silence, commit delta, version delta, drifted-template rendering with commit info, legacy fallback, no-freshness fallback
- `TestSyncRecordsFrameworkCommit` (2 new + 6 inherited) — manifest field written when fw is git, omitted when not
- `TestAdvisoryEnrichment` (2 new + 6 inherited) — last-changed-commit fields populated when fw is git, empty when not
- `TestProductClaudeFreshnessSection` (3 new) — section present, names three dimensions, warns against synthesizing

**Known gap caught during build:** Initial pass missed three early-return paths inside `try_sync` that still returned 2-tuples; subprocess-based hook tests caught it via `ValueError: not enough values to unpack`. Fix was mechanical — converting all returns to 3-tuples — but the lesson is that signature changes need a grep-the-callsites step that's local to the function being changed, not just at import boundaries.

## 2026-05-01: Project-preferences enforcement framework — first generators (batches 1 + 2)

**Why:** Project preferences quietly become aspirational when nothing checks them. Audited prawduct's own `project-preferences.md` against the codebase, found drift (overstated `__future__` rule, stale test-mirroring example, missing Workflow / Parallelization / Testing-strategies fields, no `tools/lib/` mention). After updating the file to current reality, built the first eight enforcement artifacts in two batches to validate the four-mechanism model (Test / Linter / Critic / Session config) on a diverse set of preference shapes.

**What:**
- Updated `.prawduct/artifacts/project-preferences.md`: corrected drifted claims; added Workflow / Parallelization / Testing-strategies fields; expanded File organization to call out `tools/lib/`; sharpened the Error-handling preference with concrete "boundary" examples for Critic adjudication; added explicit Subprocess safety preference (no `shell=True`) under Tooling; added explicit public-function coverage expectation under Testing; added an Enforcement section that maps each preference to its mechanism (Test / Linter / Critic / Session config).
- Added `tests/preferences/` with six tier-2 enforcement tests (13 test cases total) spanning six different shapes:
  - `test_future_annotations.py` — every implementation file in `tools/` and `tests/` begins with `from __future__ import annotations`. Shims auto-detected via the `Backward-compat shim` docstring marker; `__init__.py` and `tests/conftest.py` are explicit exceptions. Self-guards by asserting exception list still references real files. *Shape: AST first-statement check.*
  - `test_parallelization_config.py` — verifies `pyproject.toml` addopts contain `-n auto` and `--dist loadfile`, plus `tests/conftest.py` defines `pytest_collection_modifyitems` and applies `xdist_group` markers. *Shape: TOML/text presence check.*
  - `test_sync_only_architecture.py` — no `async def`, no `import asyncio` anywhere in `tools/` or `tests/`. *Shape: AST recursive walk.*
  - `test_subprocess_safety.py` — no `subprocess.{run,check_output,check_call,call,Popen}(..., shell=True)`. Security-relevant. *Shape: AST call-pattern (Attribute func + keyword args).*
  - `test_test_location.py` — no `test_*.py` files outside `tests/`. Catches files that pyproject's `testpaths` would silently skip. *Shape: file-tree walk.*
  - `test_public_function_coverage.py` — every public function in `tools/lib/` is referenced in at least one test. Exemption list (currently `log`, `load_json`, `strip_test_tracking`, `generate_sync_manifest`) for transitively-tested helpers, with documented resolution path. *Shape: cross-file consistency check.*
- Added matching Enforcement section stub to `templates/project-preferences.md` so new product repos inherit the discipline.
- Critic-enforced preferences (naming, error-handling, class-based grouping, etc.) live in the body of `project-preferences.md` and are adjudicated via the existing Critic Goal 4 (Project Preferences) check.

**How mechanisms were chosen:**
- Tier 1 (Linter) — naming. Prawduct has no linter configured; classifier escalates these to Critic rather than generating a weak AST test that mimics ruff `N` rules. Demonstrates the refusal path.
- Tier 2 (Test) — six preferences spanning six AST/filesystem shapes (above). The `test_public_function_coverage.py` test was tightened mid-implementation after the Critic flagged identifier-bag heuristics as a false-confidence trap; final detection requires `Attribute.attr` or `Name` in `Call.func` position only, with explicit limitations documented in the test docstring. Demonstrates the framework's own guardrail biting back during validation.
- Tier 3 (Critic) — error handling, naming, class-based grouping. "Boundary" / "appropriate" / "sensible grouping" require judgment.
- Tier 4 (Session config) — Workflow values (Branching, PR creation, PR merge) read by `building.md` / `/pr` at decision points. Not test-enforced because they govern session behavior, not code shape.

**Verification:** `python3 -m pytest tests/` → 851 passed, 0 failed (838 baseline + 13 new across `tests/preferences/`). `tools/product-hook test-status` → exit 0.

**Out of scope / backlog:**
- Audit public-function coverage exemptions (4 entries) — decide rename-to-private vs add-direct-test for each.
- Lift "assign a mechanism per preference" pattern from the artifact + template into `methodology/discovery.md` / `planning.md`.
- Workflow values are documented but lack a schema/validator (e.g., allowed values for `Branching`).

## 2026-04-21: Self-heal stale product_name on every sync + Critic/Janitor state-machine guidance (v1.3.10)

**Why:** Two separate issues.

(1) v1.3.9 fixed bootstrap but not ongoing sync — legacy manifests (bootstrapped before v1.3.9, or whose `product_identity.name` was renamed after init) kept the wrong cached `product_name` forever because `run_sync` read from the manifest and never re-consulted the committed `project-state.yaml`. Old clones that pulled v1.3.9 still saw banner churn on every sync. The manifest had two sources of truth for the product name (the cache and the committed identity block) with no reconciliation.

(2) Cross-product reflection surfaced a recurring anti-pattern: Claude repeatedly implements state-based problems (phases, modes, lifecycle stages, views, connection status, workflow steps) through interdependent booleans and scattered conditionals without making the states, transitions, or invariants explicit — producing code where invalid combinations are reachable and recovery paths have no known-good condition to return to. The framework had no check for this.

**Changes:**
- `tools/lib/sync_cmd.py` — `run_sync` now computes `product_name` as `infer_product_name(product) or manifest.get("product_name") or product.name`, making `project-state.yaml` the source of truth and the manifest cache a fallback for legacy manifests without an identity block. When the cache diverges from the committed identity, sync overwrites the manifest entry and emits an action so the correction is visible and persisted.
- Three regression tests in `tests/test_prawduct_sync.py`: self-heal corrects divergence, no-op when manifest and identity agree, fallback to manifest when identity is absent.
- `agents/critic/SKILL.md` and `templates/critic-review.md` — Goal 7 (The Design Is Sound) gains an **Unmodeled state-based problems** bullet. Framed around recognizing when a problem is inherently state-based (discrete conditions govern valid operations; correctness requires every reader to agree on the current condition) and what must be explicit (enumerated conditions, valid/invalid transitions, single source of truth for "what condition are we in"). Implementation-agnostic — enum, class, protocol, reducer, type, schema, or doc all qualify. Severity thresholds: BLOCKING when invalid combinations are reachable and cause correctness/safety failures, WARNING when ≥3 interdependent state signals span multiple call sites with no central model, NOTE for borderline cases (backlog candidates).
- `.claude/skills/janitor/SKILL.md` — Code Health theme gains a parallel bullet for surfacing these patterns during periodic maintenance.
- `methodology/building.md` — pulled back under its 3900-token budget (4062 → 3877) by removing a redundant "no pre-existing exception" paragraph (the same rule is stated in the Clean Baseline bullet, Test Discipline section, and Common Traps entry), tightening Context Compaction, Session Scope Discipline, and Critic-section prose. No rule removed; same meaning in fewer words. The budget overflow had been shipping since v1.3.8 and was surfacing as a test-suite failure across product repos.

**Blast radius:** `tools/lib/sync_cmd.py`, `tests/test_prawduct_sync.py`, `agents/critic/SKILL.md`, `templates/critic-review.md`, `.claude/skills/janitor/SKILL.md`, `methodology/building.md`. 838 tests pass, 0 failing.

## 2026-04-19: Fix banner churn across repo clones with different directory names (v1.3.9)

**Why:** Users working in multiple clones of the same product repo (e.g. `my-app` and `my-app-feature`) saw `.claude/settings.json` get rewritten to a different product-name banner on every session start, producing a permanent dirty diff that had to be ignored or repeatedly reverted. Root cause: `.prawduct/sync-manifest.json` is gitignored, so bootstrapping ran on every fresh clone; the bootstrap product-name parser scanned for a top-level `product_name:` key that never existed in the template (the actual layout is `product_identity.name:`), so it silently fell back to the directory name and baked that into the `{{PRODUCT_NAME}}` banner substitution.

**Changes:**
- `_bootstrap_manifest` in `tools/lib/sync_cmd.py` now calls the existing `infer_product_name()` helper, which correctly reads `product_identity.name` from the committed `project-state.yaml`. Directory-name fallback is preserved for repos missing the identity block.
- Updated `test_bootstrap_infers_product_name_from_state` to use the real `product_identity.name` layout with a regression comment; the product dir and identity now deliberately differ so the test pins the fix.

**Blast radius:** `tools/lib/sync_cmd.py`, `tests/test_prawduct_sync.py`. 832 tests pass.

## 2026-04-17: Session-timestamp freshness + lag warning for stale product-hooks (v1.3.8)

**Why:** Two related session-start staleness defenses. (1) The old fingerprint system (HEAD SHA + dirty file content hashes) caused chronic false positives: any commit — even metadata-only — invalidated test evidence, wasting cycles on re-runs and "benign fingerprint drift" warnings. (2) Discodon session today showed `fingerprint drift (55ae5158c4e1 -> b27c1100a6db)` despite the framework having replaced fingerprints — the product was pinned at v1.3.7 and its local `tools/product-hook` was the old code, but nothing warned about it. Product repos can silently run stale hook code when the session-start auto-sync doesn't apply.

**Changes:**
- **Trust-the-cycle freshness check** — Removed `compute_test_fingerprint()`, `hashlib` import, and ~70 lines of hashing logic from `tools/product-hook`. Evidence is current if it was recorded during the current session with all tests passing. 10 doc/template files updated to teach the new model; 3 moot backlog items removed.
- **Bidirectional framework version check** — `_check_framework_version` in `tools/product-hook` now also warns when the framework's `VERSION` is *newer* than the manifest's `framework_version` (previously it only warned in the stale-framework direction). Message names both versions and prints the exact `prawduct-setup.py sync` command so the fix is copy-paste. Fires when auto-sync at session start didn't apply for any reason (sync failed, framework unreachable, manifest not updated).
- **Test** — `test_product_lags_framework_warns` in `tests/test_coverage_gaps.py` covers the new direction using a no-op sync script so the manifest stays stale, mirroring the existing `test_stale_framework_warns` pattern.

**Blast radius:** `tools/product-hook`, `tests/test_product_hook.py`, `tests/test_coverage_gaps.py`, 10 doc/template files. 832 tests pass.

## 2026-04-15: Shift reflection cadence to work boundaries (v1.3.7)

**Why:** Product sessions were hitting friction when the user said "ready to /clear" — Claude almost always replied "wait a minute, let me write the reflection" and kept the user waiting. The old cadence ("reflect before session end") also produced rushed reflections written under time pressure.

**Changes:**
- `methodology/reflection.md` — "When to Reflect" reframed around work boundaries (chunk-end after Critic, bug fix, error recovery, judgment call, PR merge). Session-end becomes synthesis, not from-scratch. Capture step now distinguishes `.session-reflected` (per-cycle narrative) from `learnings.md` (durable rules).
- `methodology/building.md` — Build cycle "Reflect" step says "now, not at session end." Session Scope Discipline checklist step 6 is "reflection synthesis" over a file that's already populated.
- `CLAUDE.md` — Learning Loop section leads with the work-boundary cadence.
- `tools/product-hook` — Reflection-missing blocker message teaches the new cadence.
- Templates (`templates/product-claude.md`, `templates/build-governance.md`) — same reframing propagated to product repos via sync.

Hook behavior is unchanged — it already checked `.session-reflected` exists with ≥50 chars. The fix is methodological: when reflection happens at chunk boundaries, the file is already populated by the time the user asks for `/clear`, and handoff becomes fast.

**Blast radius:** 5 framework files + 2 product templates. 832 tests pass. Token-budget tests caught bloat twice and enforced tighter prose.

## 2026-04-15: Fix chronic "stale test evidence" false positive (v1.3.6)

**Why:** 8+ product sessions reported the Critic almost always warning "stale test evidence SHA — expected timing". Root cause: `compute_test_fingerprint()` hashed every dirty path from `git status --porcelain` without filtering framework/session metadata. Between the Verify step (fingerprint written) and the Critic step (fingerprint re-checked), the builder routinely touches `.prawduct/.critic-findings.json`, `.prawduct/backlog.md`, `.prawduct/artifacts/build-plan.md`, `.claude/settings.json`, etc. — normal build-cycle churn that has no bearing on test results. The fingerprint changed, the Critic flagged it, every time.

**Changes:**
- `compute_test_fingerprint()` in `tools/product-hook` now skips paths matching `_is_metadata_path()` (the same filter already used by `git_has_session_changes()` and `_session_changes_are_doc_only()`). Prefixes: `.prawduct/`, `.claude/settings.json`, `.claude/skills/`, `tools/product-hook`.
- New regression test `test_metadata_changes_do_not_invalidate_fingerprint` in `tests/test_product_hook.py` asserts identical fingerprints for (src-only dirty) vs (src + multiple metadata files dirty).

**Blast radius:** 2 files (product-hook, test file). 832 tests pass.

## 2026-04-13: Property-based testing guidance + template drift advisory system (v1.3.5)

**Why:** Property-based testing guidance was orphaned in a single test scenario file — no PBT knowledge flowed to product repos through templates, sync, or governance. Separately, the framework had no mechanism to notify existing products when place-once templates improved (test-specifications, project-preferences, conftest.py were fire-and-forget).

**Changes:**
- PBT guidance added to synced templates (build-governance, critic-review, Critic SKILL) — NOTE-level check in Goal 1, domain-conditional guidance in build cycle
- PBT content added to place-once templates (test-specifications Property-Based Tests section, project-preferences Testing strategies field, conftest.py Hypothesis config block)
- Template drift advisory system: place-once template hashes tracked in sync manifest, drift detection on each sync, advisories surfaced in session briefing
- Janitor skill: new Template Currency investigation theme, framework health pre-check, hash-update guidance after review, `templates` scope shorthand
- Methodology: discovery surfaces domain-driven testing strategies, building.md "Test strategies match the domain" principle, cross-cutting concerns updated
- Place-once mapping constants extracted to core.py (PLACE_ONCE_TEMPLATES, PLACE_ONCE_COPY)

**Blast radius:** 18 files. Templates (6), tools (3), tests (5), methodology (2), agents (1), cross-cutting concerns (1). 43 new tests, 831+ total.

## 2026-04-07: Doc-only gates, gate waivers, test fingerprint, defensive untrack, worktree awareness (v1.3.4)

**Why:** Four user-reported friction points: (1) docs-only sessions were tripping the Critic and PR gates even though there was no code to review; (2) tests were being re-run unnecessarily by builders, the Critic, and the PR reviewer because saved evidence used `git_sha` alone, which can't track uncommitted edits; (3) `.session-handoff.md` and other session files were causing merge conflicts in product repos when they had been accidentally committed before being gitignored — sync had a fix but only on next sync; (4) agents working in git worktrees reported that `git_has_code_changes()` ignored the session baseline and that the hook was not surfacing worktree state.

**Changes:**
- **Doc-only skip + waivers:** `cmd_stop` now skips Critic and PR gates when all changed files are `.md` (using the existing `_session_changes_are_doc_only`). Agents can also write `.prawduct/.gates-waived` (JSON: `{"critic": "reason", "pr": "reason", "reflection": "reason"}`) to declare a gate N/A for the current session. Empty reasons are rejected as a guardrail. The file is auto-deleted on `cmd_clear` so waivers never carry across sessions. The hook prints `GATE WAIVERS:` and the reason for each skipped gate in stderr.
- **Test fingerprint:** `compute_test_fingerprint()` returns sha256 of (HEAD SHA + sorted dirty file paths + each dirty file's content hash). `.prawduct/.test-evidence.json` gets a new `fingerprint` field. New subcommand `python3 tools/product-hook test-status` prints `current` (exit 0) or `stale: <reason>` (exit 1) — single source of truth for builders, the Critic, and the PR reviewer to decide whether re-running the suite is necessary. Falls back to git_sha-only comparison for older evidence as long as the working tree is clean.
- **Defensive untrack:** `cmd_clear` now runs `_untrack_session_files()` on every session start, mirroring `untrack_gitignored_files()` from `tools/lib/core.py`. This means product repos that have an accidentally-committed session file get cleaned up at session start regardless of whether sync ran. List is duplicated in `_SESSION_GITIGNORED_PATHS` (product-hook is intentionally standalone); a parity test in `test_coverage_gaps.py` keeps the two lists in sync.
- **Worktree fixes:** `git_has_code_changes()` now delegates to `git_has_session_changes()` so it consults the session baseline and skips pre-existing dirty state — previously it treated every non-`.prawduct/` line as a "code change" since session start, which fired the Critic gate against pre-existing dirt. New `_detect_worktrees()` helper inspects `git worktree list --porcelain` and surfaces a "Worktrees:" line in the session briefing when more than one worktree is attached, naming the active branch+path and listing the others. Agents are warned that gates only see the active worktree.
- **Docs:** `templates/build-governance.md`, `templates/critic-review.md`, `templates/pr-review.md`, `agents/critic/SKILL.md`, `agents/pr-reviewer/SKILL.md`, `templates/skill-critic.md`, and `.claude/skills/pr/SKILL.md` updated to teach the `test-status` check and the waiver pattern.
- **Tests:** Added `TestDocOnlySkipsCriticGate`, `TestGatesWaived`, `TestTestStatus`, `TestDefensiveUntrackOfSessionFiles`, `TestGitHasCodeChangesUsesBaseline`, `TestWorktreeBriefing`, plus `TestProductHookGitignoreMirror` (parity guard).

## 2026-04-04: Fix overzealous stop hook and build plan git tracking (v1.3.3)

**Why:** The stop hook was firing the Critic gate against completed plans (all `[x]` chunks) and against housekeeping changes that shouldn't trigger a code review. Build plans were also tracked in git despite being ephemeral working artifacts, causing merge conflicts when multiple branches each wrote to the same path.

**Changes:**
- Gitignored `build-plan.md` in this repo and all product repos via `GITIGNORE_ENTRIES` — build plans are ephemeral working artifacts, not permanent specs
- Stop hook Critic gate now checks for *active* (incomplete) chunks instead of file existence — completed plans (all `[x]`) and housekeeping changes no longer trigger false blocks
- Added `_has_active_build_plan_file()` helper; updated both clear and stop hook gate checks
- Updated tests to use plans with real Status sections; added `test_completed_build_plan_skips_critic`
- VERSION bump was missed in the original commit (a4696d6) and is backfilled here

## 2026-04-03: Stop tracking test counts as static artifacts (v1.3.2)

**Why:** Test count is derived data — it changes every time a test is added or removed. Storing it in static artifacts (project-state.yaml, CLAUDE.md, learnings.md) creates constant reconciliation work: the Critic flags discrepancies, and developers spend real time updating numbers that have no value over the hook's dynamic count.

**Changes:**
- Removed "test counts" from the artifact-update guidance in `methodology/building.md` and `build-governance.md` (template + instance)
- Removed "test counts" from the Critic's bidirectional freshness check (`agents/critic/SKILL.md`)
- Removed "update test count" from the janitor's task list (`.claude/skills/janitor/SKILL.md`)
- Removed `build_state.test_tracking` from the framework's own `project-state.yaml`
- Added `strip_test_tracking()` migration step to `tools/lib/migrate_cmd.py` — removes stale `test_tracking` from existing product repos on next migrate/sync

## 2026-04-01: Embed Critic review in build plan chunks (v1.3.1)

**Why:** Critic review was being skipped or offered as optional despite explicit behavioral instructions in CLAUDE.md. Behavioral instructions degrade under context pressure; the build plan — which Claude actively follows step by step — had no Critic step at all.

**Changes:**
- Build plan template: each chunk now has "Done when" steps (acceptance + `/critic` + commit)
- Removed "do not ask, do not offer" behavioral instructions from CLAUDE.md, product-claude.md, build-governance.md
- Replaced with plan-following instruction: "Follow the plan — the Critic step is there"
- Stop hook blocker message now references the build plan's "Done when" steps
- Build governance step 9 ties chunk `[x]` marking to "Done when" completion

## 2026-03-30: Extracted lib modules, framework version tracking, reflection gate improvements (v1.3.0)

**Why:** The monolithic setup script was difficult to test and maintain. Framework version tracking was needed so product repos can detect when they're out of sync. The mandatory reflection gate was blocking exploratory/Q&A sessions that had no build work to reflect on.

**Changes:**
- Extracted `tools/lib/` modules (core, init, migrate, sync, validate) from monolithic setup script
- Framework version tracking — sync records `framework_version` in manifest; session start warns if `../prawduct` is stale relative to last sync
- Reflection gate is now advisory (not blocking) when no build plan is active — exploratory/Q&A sessions no longer require mandatory reflection
- Comprehensive test coverage for all user onboarding journeys (750 tests)
- V4_GITIGNORE_ENTRIES now matches GITIGNORE_ENTRIES (adds `.session-handoff.md`, `.test-evidence.json`, `.pr-reviews/`)
- Critic changelog scope — only checks entries from current changeset, not historical entries
- Gitignore hygiene — sync removes managed files from .gitignore if incorrectly added
- Deprecation warnings when migrating v1/v3/partial repos

**Classification:** structural

## 2026-03-28: Structural Critic tool restrictions, test evidence, and auto-invocation (v1.2.9)

**Why:** The Critic repeatedly ran the full test suite (10K+ tests) despite instructions not to — behavioral constraints lose to safety goals when the agent has unrestricted Bash access. Additionally, builders treated Critic review as optional, offering it as a user choice rather than running it automatically.

**Changes:**
- Critic is now a proper Claude Code skill (`.claude/skills/critic/SKILL.md`) with `allowed-tools` that structurally prevent running tests, builds, or executables. Uses `context: fork` for independent review.
- Test evidence mechanism: builder records results to `.prawduct/.test-evidence.json` during Verify; Critic reads evidence instead of re-running tests.
- Strengthened Critic invocation language: "Run `/critic` now — do not ask the user, do not offer it as an option."
- Stop hook skips reflection gate for doc-only (.md) changes.

**Classification:** governance

## 2026-03-22: Make project-state.yaml merge-friendly

**Why:** Multiple agents/developers working in parallel branches frequently conflict on project-state.yaml. Agents resolve by taking "ours," losing other branches' progress.

**Changes:** Branch-scoped WIP (keyed by git branch name), change_log split to separate .prawduct/change-log.md, test_count computed instead of tracked, merge conflict guidance added.

**Classification:** structural

## 2026-03-22: Consolidate init/migrate/sync into unified prawduct-setup.py

**Why:** Three scripts with importlib cross-imports, a 6-step prose detection algorithm in CLAUDE.md, no post-setup validation, and no health check tool.

**Changes:** Unified into one script with subcommands (setup, sync, validate). Added /prawduct-setup skill. Old scripts replaced with import-safe backward-compat shims. 725 total tests.

**Classification:** structural
