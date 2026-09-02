"""Tests for v5 methodology and Critic updates.

Verifies that methodology files, Critic instructions, and cross-cutting concerns
are internally consistent and reflect v5 concepts.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
REPO_ROOT = Path(__file__).resolve().parent.parent


def read_file(rel_path: str) -> str:
    base = REPO_ROOT if rel_path.startswith(".prawduct/") else ROOT
    return (base / rel_path).read_text()


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def assert_inert_count_cap(text: str, path: str) -> None:
    """Both Critic protocol files cap a finding whose only subject is an inert
    count at NOTE, and both must carry it in the same place: INSIDE the NOTE
    entry of the severity legend.

    **Placement is the substance and is asserted, not assumed.** A reviewer
    resolving "what severity is this?" reads the legend entry for the severity
    it is weighing; a cap parked in its own paragraph is met either before
    there is a finding to apply it to, or not at all. This repo has shipped
    present-and-inert instruction twice with every artifact-measuring guardrail
    green — `SKILL.md`'s header, and the near-miss that drafted the
    verify-resolutions narrowing into `## Severity`, which sits below all three
    goal sections. The legend entry is the right home here for the opposite
    reason: it is a lookup, and it already owns the parent rule (record-only
    prose is a NOTE because rating it WARNING manufactures the next round).

    **The three components are the cap, not decoration.** A bare "rate it NOTE"
    still hands the builder a defect report, and a builder fixes defect
    reports — which is the commit that buys the next round. The finding has to
    say the number is *right to leave alone*, which takes all three: the true
    figure (or the builder cannot check the claim), that nothing reads it, and
    that no edit is wanted.
    """
    note_bullet = next(
        (
            ln for ln in text.split("\n")
            if ln.lstrip().startswith("- **NOTE**") and "ambiguous" in ln
        ),
        None,
    )
    assert note_bullet, f"{path} has no NOTE entry in its severity legend"
    assert "inert count" in note_bullet, (
        f"{path} states the inert-count cap outside the NOTE legend entry (or "
        "not at all) — a reviewer picking a severity reads the entry, not the file"
    )
    for component, why in (
        ("true figure", "the builder cannot check the claim without the number"),
        ("nothing reads it", "'stale' without 'inert' is just a defect report"),
        ("no edit is wanted", "the only clause that stops the fix commit"),
    ):
        assert component in note_bullet, f"{path}'s cap dropped {component!r} — {why}"


#: The ACTUAL token count of each budgeted file, as last measured. The per-file
#: `test_token_budget` assertions are *ceilings*; this is the reading, and one
#: test below pins it.
#:
#: **Why a table instead of a number in the accounting prose.** Each budgeted
#: file carries a comment narrating what an edit cost and what paid for it, and
#: those narratives kept going stale: on 2026-07-30 a single chunk shipped a
#: post-trim figure that was 4 tokens off, then took its *starting* figure from
#: the previous entry's ending figure — which two earlier chunks had already
#: invalidated by editing the file without updating it. A stale tally propagated
#: into a fresh tally that was wrong for a second reason.
#:
#: This is `record_lint`'s `suite-total-claim` rule applied one level in: do not
#: keep a prose copy of a figure a mechanism can own. The narratives stay (they
#: record *why* an edit was affordable, which no test can); the current reading
#: lives here, where a wrong number fails instead of misleading.
#: **The on-demand methodology guides carry a READING and no ceiling**
#: (decision 2026-08-19, #688; owner-selected from three framed options).
#:
#: #688's premise was wrong and the correction changed the answer. It said
#: `reflection.md` was "the only on-demand methodology guide with no entry" —
#: measured, `discovery.md` (4752) and `planning.md` (4301) were unbudgeted
#: too, and `discovery.md` is LARGER than budgeted `building.md`. So the real
#: state was that on-demand guides were unbudgeted **as a class** with
#: `building.md` the lone exception, which makes this a policy question rather
#: than a bookkeeping line — and answering it for one file would have left two
#: larger ones in the state the issue objected to.
#:
#: **Why a reading and not a ceiling.** The yield #688 names is *undeclared
#: growth*, and a reading delivers exactly that: change the file without
#: restating its size and the assertion below goes red carrying the number to
#: write. A ceiling is a different control — it blocks the growth itself — and
#: these files are the ones where growth is CHEAP. Their cost is opt-in, paid
#: only by a session that opens them, which is precisely why
#: `governance-surface-dedup` moved the standing block's full shape into
#: `reflection.md` rather than the always-injected digest. Pricing the cheap
#: destination would invert the incentive four chunks were spent building
#: (`reflection.md` went 3001 → 4529 in two days, and most of that was that
#: relocation working as designed).
#:
#: **How this discharges `nonfunctional-requirements.md` § Direction**
#: ("proportionality ratchets both ways — every new control must emit its yield
#: observably"). This is an **accounting** control, not a blocking one. It
#: cannot fire-and-annoy, because it never refuses a change — only an
#: unrecorded one — so the failure mode the norm targets (repeated firings, no
#: blocking yield) is unreachable by construction. Its yield IS its emission:
#: every entry below is dated, carries what caused the delta, and the whole
#: history is `git log -p` on this dict. Not a machine-readable fact stream,
#: and it does not need to be for a control that blocks nothing.
#:
#: **What would reverse this**, in either direction: an on-demand guide whose
#: growth is repeatedly recorded and never justified — that is a ceiling's
#: case, and the readings are what would prove it — or a measured session
#: opening a guide it did not need, which is an argument about *routing*, not
#: about size. What separates this class from the files that DO carry a ceiling
#: is not size but who pays: an on-demand guide costs only the session that
#: opens it, while `skills/critic/SKILL.md` is loaded by every Critic dispatch
#: whether or not anyone chose it — which is why that file's reading sits beside
#: a ceiling and these three do not.
#:
LAST_MEASURED_TOKENS = {
    # -1 on 2026-08-13: the evidence-model paragraph said a rebase/amend
    # "demands a fresh look", which the base-advance transfer falsified — the PR
    # gate can now close one case of that gap by computation. Narrowed to "opens
    # a gap", which is what stayed true, and which costs a word less than the
    # remedy it used to name.
    # -1 on 2026-08-13 (net): the comment policy gained the archaeology rule —
    # review/finding ids never ship, and a comment recounting history is a
    # deletion rather than a rewrite. Paid for entirely inside the file, and
    # a token over: the Blocking-findings paragraph restated the disposition
    # menu and the disagreement rule that "Resolve findings" already owns
    # (only "warnings and notes gate nothing" was its own), the Critic-review
    # step said "runs as a separate agent" a second time, and the seven goal
    # names were spelled out beside the pointer to the file that defines them.
    # -86 on 2026-08-19: a CUT, not a relocate. This file restated the whole
    # three-label standing-block shape -- the fenced block, the `---` rule, the
    # trigger, the three failure modes -- while `reflection.md` owns it and the
    # session digest injects it unconditionally. A reader of THIS file has
    # already been handed the shape by the digest before they open it, so the
    # copy here was a second authoritative statement of a fact with a home
    # (`artifacts/architecture.md` § Direction). What stays is the clause only
    # this file can make: `SAFE TO CLEAR` binds to ITS steps 1-7. The ceiling
    # was ratcheted down with the cut, so the standing trim-or-relocate rule is
    # enforced structurally here rather than asserted in prose.
    # +6 on 2026-08-19 (#687): the work-cycle limit was re-priced. It stated one
    # rule on TWO rationales with different expiry dates and a chunk count
    # proxying for both. The compaction half is CEDED (Principle 26 — the
    # cession itself is recorded in the change-log, which is where a re-pricing
    # belongs; purpose.md's responsibility ledger, its eventual home, is not
    # built); the review-scope half survives, re-justified on the reviewer's
    # ATTENTION rather than its window, which is why larger windows do not erode
    # it; the number retires in favour of the diff-size unit the roster rule
    # already uses. Paid for in place, NOT by a bump: the Modes section restated
    # what each of the four modes covers, three lines above its own pointer to
    # the file that defines them and that the reader is told to open. What it
    # keeps is the two facts a reader needs BEFORE opening it (`cumulative`
    # feeds the PR gate; `verify-resolutions` alone records resolutions), which
    # is the part a pointer cannot carry.
    #
    # The cut went FURTHER than the addition, which is why this reading is below
    # where the branch started: the Modes section named
    # `skills/critic/review-cycle.md` three times in five lines — once in the
    # gloss, once in a fail-safe sentence, once in a following aside — while the
    # first draft of the trim ADDED a fourth by pointing at a "per-mode table
    # below" that is not in this file. Merged to one pointer carrying both the
    # per-mode table and the fail-safe. CEILING RATCHETED 4730 -> 4718 with the
    # cut, per the standing rule: slack left behind is a loan the next edit
    # collects silently and green.
    # -53 then +40 on 2026-08-21 (net -13, 4774 -> 4761): the delegation guide's
    # pointer, funded by a CLASS rather than by words — rules the
    # always-injected `session-digest.md` states in full, restated here beyond
    # the part only this file owns. Checked per item, not assumed: (1) Exception
    # Handling's two language-syntax bullets and its "the general waiver
    # mechanism (`docs/waivers.md`)" sentence — the digest gives the pragma
    # string verbatim AND names `docs/waivers.md`, so what stayed is the part it
    # does not carry (when a broad catch is legitimate, that the comment goes on
    # the catch line, and the canary/Critic behaviour); (2) "Two session files,
    # two owners" — the digest owns both the ownership split and the
    # don't-write-there rule, so what stayed is the regeneration inputs and
    # `handoff preview`, which nothing else states; (3) the norm-departure
    # sentence's "never a silent divergence" and "Norms bind; descriptions
    # track" — the digest's own norms bullet, word for word. The TELL ("a norm
    # edited to bless your own code") is in that class too — the digest states
    # it — and was kept anyway, deliberately: it is the clause that makes the
    # tripwire fire, and this file is where a builder is standing when a norm
    # surfaces mid-build. A cut is a judgment about the reader's position, not
    # a rule that every duplicate goes.
    #
    # This is the audit the 4718 -> 4800 raise below skipped. That raise was
    # taken to buy the verification-ceiling rule's *why* without first asking
    # whether a removable class existed — and one did. The ceiling is ratcheted
    # with the cut (4800 -> 4775), so the 25 tokens the audit recovered are
    # given back rather than left as slack for the next edit to spend green.
    #
    # +3 on 2026-08-21 (Critic R-1, same chunk's second pass, 4761 -> 4764). The
    # permissive "also when chunks are independent and parallelizable" survived
    # the chunk built to replace it — and that is the line that was in force for
    # the whole 0.34% measurement, in the file a builder MUST read, while the
    # default lived only in an on-demand guide the pointer sold as "the
    # questions worth asking". A coordinator reading this file and stopping got
    # a permission where R18 says it needs a default. Now it states the default.
    # Paid for almost entirely in place: the override cases (clean context, large
    # main context) are content `delegation.md` owns canonically under this
    # plan's Module Boundaries, so restating them here was the duplication, and
    # the two paragraphs merged into one, dropping a second pointer lead-in.
    # +10 on 2026-08-21 (Chunk 02), 4764 -> 4774, ceiling untouched at 4775.
    # R6 names TWO placements and only one had landed: the delegation question
    # also arrives at a CHUNK CLOSE, and this file is the only surface a
    # coordinator reads there. Paid for in place, in the same bullet: "then the
    # combined suite and Critic" was a third statement of what "What stays in
    # the main agent" owns two paragraphs down, in this same section. The clause
    # carries the trigger ONLY — the why (a plan-time partition is a default,
    # re-checked against what the machine is actually doing) is `delegation.md`'s,
    # and the coordinator is told to open that before fanning out. ONE token of
    # headroom now, so the next addition trims.
    # 4774 -> 4773 on 2026-08-21 (Critic R-1, same chunk): the clause was in
    # the `**Parallel chunks:**` bullet, which addresses a coordinator already
    # fanning out — while the reader it exists for is the one whose plan says
    # serial. Moved to the section preamble, which is unconditional and already
    # states the default. It also got SHORTER there: "when load is finally
    # knowable" was the why, and `delegation.md` owns that ("a default, not a
    # commitment: re-check it at dispatch against what the machine is actually
    # doing") one sentence before the pointer telling you to open it.
    # -10 on 2026-08-21 (Chunk 04's cumulative, R-13), 4773 -> 4763, ceiling
    # ratcheted 4775 -> 4765 with the cut. The rationale is at the ceiling
    # assertion, which is where this file's cuts are narrated.
    # -3 on 2026-08-21, 4763 -> 4760, ceiling ratcheted 4765 -> 4762. A CUT that
    # made the rule simpler: `closed-by:` left the mutable-id exemption list.
    # It was there because the handle used to be allowed to be a chunk id, and a
    # bare chunk id names no plan -- it fails the very test Principle 13 states
    # one sentence later. With the handle required to name the work, the entry
    # needs no exemption and the sentence needs no clause.
    # -5 on 2026-08-21: the ad-hoc trigger reached the delegation section, and
    # paid for itself with room over. What funded it was the pointer's own table
    # of contents — "what overrides that default and what defeats it, what a
    # brief must say, and the anti-patterns each with its tell" enumerated the
    # headings of a file the same sentence tells the reader to open, which is
    # the removable class exactly. What replaced it is the discriminator a
    # reader actually needs to choose between the two files: the guide is the
    # judgment, this section is the mechanics. No prose moved between files —
    # delegation.md already owned every heading that clause listed.
    # NOT a general rule about enumerations: `skills/methodology/SKILL.md` keeps
    # (and grew) the same list, because its reader is choosing AMONG seven files
    # and has not picked one yet. What made the clause removable here is that
    # this reader has already decided to delegate, so the enumeration answers a
    # question they are no longer asking.
    # +/-0 on 2026-09-01 (#547): Boundary Investigation gained the INBOUND
    # direction -- read the producer's emitted signal sequence when you write a
    # consumer -- because Critic Goal 1 blocks on that mismatch in `chunk` mode
    # and nothing guided the builder toward it. PAID FOR IN PLACE, at the
    # ceiling rather than through it, and funded by the same class the delegation
    # pointer used: rules the always-injected `session-digest.md` states in full,
    # restated here beyond the part only this file owns. (1) the "pre-existing"
    # exception's enumeration ("tests, broad exceptions, stale artifacts,
    # anything: fix it, or flag it") -- the digest gives the list and the
    # flag-why clause verbatim, so what stayed is the binding this file owns:
    # every session starts clean; (2) "Never write Critic findings yourself" as
    # its own paragraph, folded into the sentence above it -- the digest carries
    # the rule AND its why ("the independence is the whole value"), and "if the
    # agent is slow, wait" was the neighbouring "Don't poll" a second time; (3)
    # Exception Handling's opening and closing sentences -- "catch specific
    # exceptions", the two syntax examples, and "no waiver can justify silencing
    # errors" are all the digest's bullet, so what stayed is when a broad catch
    # is legitimate, that the comment goes on the catch line, and the
    # canary/Critic behaviour; (4) the PR default's restatement of itself ("do
    # not create PRs proactively; only use /prawduct:pr when the user explicitly
    # requests it" says the heading sentence twice), leaving the heading plus the
    # preference that overrides it.
    # -4 on 2026-09-01 (#300): the dispatcher-side verification rule -- a
    # delegate's "Done" on a REMOVAL or a SWEEP is a claim, re-derived before
    # acceptance -- reached the Delegating section, and came in under what it
    # cost. Weak-model failures cluster here (premature "Done", over-broad
    # allowlists, 5-15% inventory undercounts, all already a learning in a
    # consuming product), and the guide said nothing about verifying a
    # subagent's report. Funded, again, by the digest-states-it-in-full class:
    # (1) the durable-prose rule's chunk-number instance and its bookkeeping
    # exception -- the digest carries both, so what stayed is the clause only
    # this file owns (review and finding ids never ship, history lives in
    # commits and the change-log) plus the worked example; (2) "ticking the LAST
    # box disarms the Stop hook's gates -- review first, tick after", which is
    # the digest's Status bullet word for word, leaving the Context block that
    # nothing else states; (3) "never silently *invent* a requirement any more
    # than you'd *drop* one", the digest's requirements bullet verbatim -- and
    # the digest already points AT this section for the tripwires, which are
    # what it does not carry and what stayed.
    # -4 on 2026-09-01 (#284): the mid-build assumptions checkpoint -- re-check
    # the plan's `[ASSUMPTION: ...]` entries as code reveals new facts. This was
    # the last of the item's four sub-items still open; the emphasis-escalation
    # half (CLAUDE.md's "STOP. Read this before writing ANY code" caps) and the
    # Foreign-API compression were discharged by the 2026-07 prose diet.
    # Assumptions were recorded at plan time by `planning.md` and never
    # checkpointed by anything afterwards, which is the shape the item names:
    # a decision taken on the user's behalf that, unrevisited, is never
    # confirmed.
    #
    # Funded in place again, and this time out of THIS file's own redundancy
    # rather than the digest's: (1) the opening sentence stated the work cycle
    # six lines above the definition that states it in full -- and stated it
    # INCOMPLETELY, stopping at verify where the real cycle runs through Critic
    # and reflect, so the shorter form was also the wrong one; (2) two Common
    # Traps restated the sections directly above them ("Uninvestigated
    # decisions" is Decision Research, "Tuning a mechanism you haven't read" is
    # the cheap-check gate), and both are prose-pinned by NAME, so what a trim
    # can remove is the restated body and not the entry.
    # +7 on 2026-09-01 (#299): two of the four weaker-model scaffolds, placed
    # where the judgement is actually made. (a) The 3-4-FILE TIEBREAK -- the
    # classification heuristic named 1-2 and 5+ and left the middle to taste,
    # which is a judgement offload with nothing behind it; the tiebreak turns on
    # blast radius (contract surface / dependency / state outliving the
    # process), not on taste. (b) The RED-BASELINE PROTOCOL -- "every test must
    # pass; fix any failures" told a builder what the state must be and nothing
    # about the commonest way it is not, and the expensive error is folding
    # someone else's failure into your own diff. It replaces the bare "All tests
    # pass, always. Diagnose and fix every failure", which it makes specific.
    #
    # Nearly self-funded. What paid: the Tests-never-weaken restatement of the
    # digest's contracts bullet; the guilt-pile argument, which
    # `reflection.md`'s Earn-the-backlog-entry rule owns in full; "never
    # silently drop a requirement", the digest again; a compression of the
    # CLAUDE.md-is-instructions paragraph; and one clause of Session Scope
    # Discipline that restated this file's own evidence-model section (nothing
    # expires by session). The other two scaffolds went to `discovery.md` and
    # `reflection.md`, which is where their judgements are made.
    # +/-0 net on 2026-09-01 (#164, then its revert): "The canary skips waived
    # lines" was deleted (-7) when #164 retired `_check_broad_exceptions`, and
    # RESTORED (+7) when the cumulative Critic found that retirement had outrun
    # its Direction precondition and it was reverted. The sentence is true again
    # because the check is back. Recorded as one entry rather than two so the
    # next reader sees a no-op, not a pair of unexplained swings.
    "methodology/building.md": 4754,
    # +26 on 2026-08-10: the Documentation-drift rule said "a pointer to a plan
    # resolves", which archival made false for the PATH form while leaving it true
    # for the scope form — a reviewer applying the old sentence waves through the
    # dangling citations that shipped. Paid for by stating only the distinction and
    # dropping the worked example. The narration lives HERE rather than in the file's
    # own budget comment: at 1 token of headroom the file cannot afford to carry one,
    # which is itself the honest reading of how tight this ceiling now is.
    # +45 on 2026-08-13, ceiling 3620 -> 3800: the tactical-efficiency pass adds
    # point-of-action rules to this file — prior_dispositions, the prose
    # severity ceiling and remedy constraint. The file had 1 token
    # of headroom and nothing left to dedupe — its own budget comment already
    # records that. Raising ONCE with the whole pass named beats three creeping
    # raises that each look local; the reading below still fails on any drift, so
    # the ceiling buys room while the pin keeps the accounting honest.
    # +135 on 2026-08-13: the prose severity ceiling and the three permitted
    # remedies, the pass's answer to comment/doc wording being the largest
    # category of finding volume. Spends the ceiling raised above for exactly
    # this, and pays 41 of it back in place: the model-override rule was stated
    # in both Assess and Dispatch (kept at Dispatch, where the Agent calls are),
    # and the drift bullet named the chunk-number case twice and re-derived
    # "archiving moves the file" from "archived, not deleted". The last 18 are
    # the floor clause — without it the ceiling silently outranks the
    # actively-misleading BLOCKING Goal 4 assigns explicitly, so a wrong
    # command ships as a WARNING that gates nothing. This file is now at ONE
    # token of headroom: the next addition trims or relocates, and there is no
    # third raise coming.
    # -128 on 2026-08-18: the uplevel pass. Six repeated shapes measured at 634
    # tokens; three were one property written many times and merged, one was a
    # check written twice, one was a bullet the preamble already owned, and one
    # was measured and deliberately kept. What merged: Goal 4's five drift
    # bullets plus changelog scope became "a description whose subject moved"
    # with the container named as incidental; Goal 5's three missing-rationale
    # bullets became "a decision without a recorded why";
    # `infrastructure_dependencies` was checked in Goal 2 AND Goal 4 and now has
    # one home, Goal 2; Signals lost its Files-changed bullet to the Work-size
    # scale that already implied it; and CLAUDE.md size no longer restates the
    # changeset scoping the History bullet now owns for every Goal 4 check.
    #
    # The first draft recovered 153 and was WRONG BY 31 of them, which is the
    # number worth carrying forward. Family SIZE was read as recoverable
    # redundancy, and two cuts turned out to be deletions: Signals' work-type
    # mapping (Feature -> spec compliance, Bugfix -> root cause, ...) was
    # redirected to "the selector cited above", which is the chunk `Type:`
    # selector -- a different axis this same file calls separate, and the real
    # home is a builder-side file no reviewer opens; and the flat stale-artifact
    # WARNING was folded under the prose ceiling, silently letting a stale
    # architecture.md grade NOTE. Both restored. A scan measures what a shape
    # COSTS; only rewriting it measures what it can give back, and the gap is
    # the checks that only look repeated.
    #
    # WHAT DID NOT MERGE, and why, so the next reader does not retry it. Goal
    # 2's declaration->obligation bullets (`Foreign API:`, `Exposed API:`,
    # `Visual change: yes`, 163 tokens) are literal string matches, each owing a
    # different thing. "A declaration creates an obligation" names neither the
    # string to find nor the thing owed, so merging them silently stops three
    # checks firing — the enumeration IS the trigger, which is the exception
    # framework-checks.md Check 7 requires be stated rather than left implicit.
    #
    # The Goal 4 `**Norms**` bullet DID go, and the trap below is retired with
    # it: test_project_preferences_blocking needs one line carrying both
    # "project-preferences" and "blocking", and the Normative-authority preamble
    # now carries them — the BLOCKING clause names the `project-preferences.md`
    # row or Direction statement the finding cites, which is where a reviewer
    # resolving jurisdiction already reads. The rule kept its only home; it did
    # not lose one.
    # +123 on 2026-08-18: a site-naming finding must answer instance-or-class,
    # and the remedy is graded — the `**Scope:**` slot in the finding template
    # plus its rule in the severity legend. Spends the 128 the uplevel pass
    # above recovered, which is what that pass was for; the ceiling stays at
    # 3800 and this file has 5 tokens of headroom. Nothing was paid back in
    # place because the uplevel already took everything there was — the payment
    # is the -128 entry directly above, not a second trim.
    #
    # This is the file's HALF of the rule, and the split is deliberate rather
    # than budgetary. `final`/`cumulative` reviewers (the single-pass fork and
    # all three coordinator subagents) read this file and write findings, so the
    # tell and the graded remedy live here. The reviewer that GRADES a fix reads
    # neither this file nor `review-cycle.md` — `verify-resolutions` is served by
    # `goals-1-3.md` and by the dispatch directives — so the withholding rule
    # went into `critic_consolidate.RESOLUTION_IS_A_CLAIM_DIRECTIVE`, which
    # already carried it in instance form ("a finding whose second site is in a
    # file this delta does not touch": a list of two where the property was
    # meant). `chunk` mode is UNCOVERED and explicitly so: `goals-1-3.md` has 2
    # tokens of headroom and the rule costs ~65, which is an owner ruling on
    # that ceiling, not a trim to slip into this chunk.
    # -9 on 2026-09-02 (learnings-v2 Chunk 04), 3799 -> 3790 across two edits
    # that net to a REFUND. The cutover repointed step 4's read list from one
    # file to "core.md plus the area files `learnings-files --for-diff` lists"
    # (+10), and the Learnings Cross-Check paragraph 100 lines below restated
    # that same list a second time. PAID FOR: that restatement, which now points
    # at step 4 instead (-13); the paragraph's "**`final`/`cumulative` only.**"
    # marker, which `## Modes` already declares of the whole file (-4); and
    # "This file is the Critic's complete instruction set" (-8), the identical
    # sentence `goals-1-3.md`'s entry below records cutting for the identical
    # reason -- the H1 says it, and "complete" stopped being true of this file
    # when `chunk`/`verify-resolutions` were split into `goals-1-3.md`.
    "skills/critic/review-protocol.md": 3790,
    # +71 on 2026-08-13, ceiling 2000 -> 2250: same pass, same reason. This file
    # is the one every chunk and verify reviewer reads, so it is where the
    # volume-cutting instructions have to live: prior_dispositions (don't
    # re-litigate an accepted finding), the prose severity ceiling, and the
    # pre-priced verify observations. Each is shorter than the review round
    # it prevents. Deduped first and found nothing: the file was squeezed to 2
    # tokens of headroom by its last edit.
    # +142 on 2026-08-13: the same two rules plus the floor clause (the
    # ceiling never lowers a severity another rule assigns explicitly), in chunk
    # mode's payload — the ceiling raised above named this addition. Nothing paid
    # it back here: the file was already deduped to 2 tokens of headroom by its
    # prior edit, so this is the raise being spent as declared, not fat traded.
    # +32 on 2026-08-13: the last of the three additions the raise above named —
    # verify-mode observations are delivered pre-priced (ACCEPT is the default,
    # fixing one costs a round, batch survivors). It goes in the sentence that
    # already defines what an observation IS, so it costs the rule and no
    # framing. The raise is now fully spent: 7 tokens of headroom, and the next
    # addition trims.
    # +6 on 2026-08-15: the `chunk-ref-missing no-subject` severity, which this
    # file must state because `chunk`/`verify-resolutions` read nothing else.
    # Paid inside the same two paragraphs: `prior_dispositions` restated
    # "already answered, don't recount" that the record-lint paragraph directly
    # below already owns, `chunk_graded`/`plan_graded` re-listed what they name
    # right after naming it, and the two false-blocker arguments (no-subject and
    # graded) were one sentence said twice. Ceiling 2250 untouched, 1 to spare.
    # +18 on 2026-09-01, ceiling 2250 -> 2280 (#644, #166): the raise is for a
    # NEW OBLIGATION, not for fat. #644 added the API-retention conformance
    # clause -- a `stable`/`deprecated` member removed against a `Retention:`
    # policy is a BLOCKING norm departure -- and this file must state it because
    # `chunk`/`verify-resolutions` read nothing else. #166's fold-in rule landed
    # beside it. Both were first funded by TRIMMING, and the trim took load-
    # bearing prose with it: the two causes of the `graded chunk` assumption
    # shape ("inferred from build-plan Status, or the plan from the
    # `active_build_plan` pointer"), which `test_record_lint.py` requires on
    # every reviewer surface precisely so a surface naming one cause cannot let
    # the other read as a clean grade. That clause is restored here and the +18
    # is what it costs. Deduping was NOT attempted a second time: the entry
    # directly above records this file already squeezed to 1 token of headroom,
    # and hunting a further trim under ceiling pressure is exactly what deleted
    # the clause the first time. Also deleted by that pass and NOT restored:
    # "You are a separate agent and have not seen the builder's reasoning --
    # that independence is the product." It survives in `agents/critic-reviewer.md`
    # for the dispatched roster, but the single-pass modes this file serves do
    # not read that file -- flagged for an owner ruling rather than re-added
    # under the same pressure that removed it.
    # +3 on 2026-09-02 (learnings-v2 Chunk 04), 2272 -> 2275: `learnings-over-budget`
    # joins `chunk-ref-missing` in the record-lint severity mapping. The budget
    # check runs at dispatch for EVERY mode, so a reviewer reading only this file
    # meets a BLOCKING finding with no severity unless the row is here too. Bought
    # at three tokens by folding it into the existing BLOCKING clause rather than
    # writing a second sentence; the ceiling is untouched.
    "skills/critic/goals-1-3.md": 2278,
    # +9 on 2026-08-13: the PR-gate section gained the base-advance transfer —
    # a computed pass the gate can now print, which a reader who only knows
    # "uncovered means run a cumulative" will otherwise re-review straight
    # through. Paid for three times over inside the section: the gate's span and
    # blocking-remedy mechanics were each stated a second time here after the
    # composition bullets above already owned them, and the selective-commit
    # routing a third.
    # -25 then +17 on 2026-08-15, 9599 -> 9574 -> 9591, ceiling untouched. The
    # demotion table gained the rule that its fallback is NAMED, not assumed --
    # `chunk`/`final` see only HEAD-tree -> working-tree, so a committed delta
    # demotes to `cumulative`. Paid inside the section: the anchoring paragraph
    # narrated both wrong readings of "the trees differ" as incidents and
    # `begin_review`'s comment already owns that derivation, and two more
    # history narrations became their rules. The property itself moved to
    # `SKILL.md` step 4 -- but that is a PLACEMENT decision (every mode reads
    # that file, only `final`/`cumulative` read this one, and the fact was
    # already stated there twice), NOT payment. Funding a budget by moving prose
    # into an unguarded file is the bump-wearing-a-trim's-clothing move this
    # file's own comment warns about, which is why `SKILL.md` is now measured
    # below and the relocation is no longer credited here.
    # +6 more on 2026-08-15 for the same severity rule, stated here at length
    # because this is the table `final`/`cumulative` grade against. Paid in the
    # block it landed in: "a severity with no remedy is a false blocker" was the
    # tail of the `graded` bullet and is now the lead sentence both it and the
    # new bullet lean on, and the BLOCKING bullet's provenance narration went.
    # -3 on 2026-08-24: the reconciliation NOTE template stopped stating WHEN the
    # archive call runs and now routes to the backlog skill, which owns that
    # timing and splits it by backend. Paid in the same sentence -- the template
    # was asserting a timing that is false on the Issues backend, so the routing
    # replaced prose rather than adding to it, and the "why" the routing would
    # have restated stayed at the owner where the reader is already being sent.
    # -9 on 2026-09-02 (learnings-v2 Chunk 04), 9599 -> 9590, and the two edits
    # that made it are worth separating. ADDED: the cross-check's read list is
    # now the resolver's answer (core.md plus the diff's area files, printed by
    # `learnings-files --for-diff`) instead of one file path, and R5's goal --
    # a rule added this cycle can be a duplicate, in the wrong area file, or
    # framework content that belongs upstream -- which is the only cross-check
    # output that is about the corpus rather than the code.
    #
    # PAID FOR, all of it from restatement rather than from a diet:
    # * The ordering paragraph and the "two different outputs" paragraph beneath
    #   it stated one conclusion twice -- "the later rule governs, do not
    #   escalate against a superseded rule", then "against the change: no
    #   finding". Merged into one paragraph carrying the rule and its two
    #   outputs once. (The merge also corrected a claim the cutover falsified:
    #   position orders rules WITHIN a file, and the corpus is now several.)
    # * "run two additional passes that `chunk` mode skips" -- the per-mode
    #   table's "Goals skipped" cell already names both cross-checks under
    #   `chunk`, so the sentence restated a row two screens up. The ownership
    #   clause, which the table does not carry, stayed.
    # * "Conversely, if a rule references patterns the changed code handles
    #   correctly, no finding is needed" -- an instruction to do nothing, in a
    #   pass whose default is already nothing.
    # * The record-lint table's closing sentence re-argued the thesis of
    #   "A re-review does not manufacture work" one clause after citing it.
    # * R5's own closing sentence ("it fires whether or not the cycle produced
    #   another finding") restated "get their own pass" in its own heading.
    "skills/critic/review-cycle.md": 9595,
    # First reading, 2026-08-15, taken because the demotion property landed here
    # and nothing was watching. This is the payload EVERY mode loads -- including
    # the fast `chunk` path whose whole reason for existing is to not read the
    # seven-goal protocol -- so growth here is the most expensive growth in the
    # skill and was, until now, the only growth nobody had to declare.
    # A ceiling sits with this reading (`TestCriticSkillRoutesByMode::
    # test_token_budget`), on that same argument: unconditional payload is where
    # growth is most expensive, so it is the one destination a relocation must
    # not be able to hide in.
    # -5 on 2026-08-19: the abandon-a-review parenthetical said the marker "is
    # swept at the next session boundary — `startup` or `/clear`", which the
    # TTL-gated sweep made false for BOTH sources it named, on the payload every
    # reviewer reads. Replaced by the predicate rather than a longer source list:
    # no session event releases a live marker, because none proves the reviewer's
    # process died. Stating the rule costs less than enumerating the exceptions
    # to it, which is why a correction that ADDED a reason still came in under.
    # -6 on 2026-08-19 (Critic R-4, CLASS): the marker paragraph asserted that
    # "while it is set `prawduct-hook clear` refuses to mutate session state
    # (from any context)". True only because the boundary used to sweep the
    # marker BEFORE mutating; gating that sweep falsified every copy of the
    # claim at once, and this file then taught the opposite of its own closing
    # paragraph. Narrowed to the act that still refuses -- a *bare* `clear`.
    # Paid for past the addition by cutting the file's second verbatim copy of
    # "otherwise it auto-expires after 30 min": the TTL stays where the reader
    # ACTS on it (the abandon-a-review paragraph), not in the data-plane gloss.
    # The boundary behaviour is deliberately NOT restated here -- that same
    # closing paragraph already owns it.
    #
    # +3 on 2026-08-19 (verify-resolutions): R-4 was closed at the two sites it
    # NAMED and the class was left open. Its own prescribed search still
    # returned three survivors, one of them the frontmatter comment 24 lines
    # above the fix -- which is injected verbatim into every Critic fork's
    # prompt, so the reviewer reading it had been handed the false claim while
    # reviewing the correction. Same narrowing applied there. Net for the
    # branch is still -3 (3406 -> 3403): the TTL cut above overpaid, and this
    # spends part of that rather than adding on top of it.
    #
    # +18 on 2026-08-19 (3403 -> 3421). Expiry stopped being sufficient grounds
    # to release the marker — a review whose reviewers have all reported is kept
    # at any age — so this file's abandon-a-review paragraph was stating a rule
    # an agent acts on and would now get wrong, relying on a boundary to release
    # a marker that a boundary keeps. Paid down from the first draft (+60) by
    # naming the state once ("a **complete roster**", the term the same
    # paragraph already uses two sentences later) instead of spelling out
    # "a review whose reviewers have all reported", and by cutting "so
    # restarting the session is not a way to clear it", which the sentence
    # before it already establishes. The remaining +18 is the condition itself:
    # it cannot be inferred from anything else the file says.
    # +24 on 2026-08-19 (3421 -> 3445). `critic-discard` became the Stop hook's
    # printed escape hatch, so the caveat that it degrades to DELETE when the
    # archive cannot be written is now load-bearing at the surface an operator
    # reaches for while wedged — the paragraph offered an undo with no failure
    # mode. Paid down from the first draft (+44) by pointing at the dispatch
    # sweep's identical caveat ("same degrade-to-delete caveat as the dispatch
    # sweep") instead of restating it, and by trimming the restore bound to
    # "the newest few" rather than naming the constant, which would be a second
    # carrier for a number `_ARCHIVE_KEEP` already owns.
    # +1 net on 2026-08-26: the exit-3 rule told the reader a `cumulative` /
    # `verify-resolutions` 3 means the gate is satisfied — true of the PR gate,
    # false of the Stop-hook one when the anchor left judgeable uncommitted work
    # outside the interval it graded, which is the case the refusal block now
    # names. A correctness fix on the payload every mode loads, so it was paid
    # for INSIDE the file rather than by a bump: the "waste this exit exists to
    # prevent" clause restated the two sentences above it, `run it anyway to be
    # safe` was quoted twice, "never add `--force` on your own initiative" is
    # step 4's rule stated in full at step 4, and "(it names the free files)"
    # had become wrong as well as costly — the block names more than those now.
    # The ceiling holds at 3450 untouched; the standing rule there is that the
    # next addition trims or relocates, and this one trimmed.
    # -11 on 2026-09-01 (#730): a REFUND, not a trim. #730's house grant form is
    # one line per command with the star attached; this file carried three spaced
    # stars and, for `classify-diff-risk`, the both-spellings PAIR the form
    # explicitly rules out. Collapsing the pair and attaching the stars removed a
    # duplicate grant line, so the saving is duplication going away rather than
    # any rule being shortened. (#160's +2 from the same burndown is included.)
    # +3 on 2026-09-02 (learnings-v2 Chunk 04): the `learnings-files` grant, in
    # the house form, one line. The fork runs the Critic's own cross-check and
    # `review-protocol.md` names the command it enumerates the read list with --
    # a mandate its reader cannot issue is either a permission prompt nobody can
    # answer or a silently skipped check, which is the gap
    # `test_mandated_hook_subcommands_are_granted_on_every_binding_surface`
    # exists to catch. Nothing paid: three tokens against a 3450 ceiling that
    # still holds, and the standing rule (the next addition trims or relocates)
    # is unchanged by a grant line that has no prose to trim. 2026-09-02: +7 for the
    # two `learnings-files` grants (hook and python3 twin) — same kind, nothing to trim.
    "skills/critic/SKILL.md": 3442,
    "skills/critic/framework-checks.md": 1116,
    # The on-demand class, first recorded 2026-08-19 (#688) — readings, no
    # ceilings; the block above this dict is the decision and its reasoning.
    # These three are baselines, not achievements: they record where the class
    # stood when the policy landed, so the NEXT edit is the first one that has
    # to say what it cost.
    #
    # `discovery.md` 4752 — grew 4189 → 4752 across the 2026-08-02 critic
    # burndown, then flat. `planning.md` 4301 — slowest mover of the three.
    # `reflection.md` 4529 — the fast one, 3001 → 4529 in two days: the
    # `governance-surface-dedup` relocation of the standing block's full shape
    # (3238 → 4083), then the clear-line verdict and its deadline (#687).
    # That growth is the design working, which is exactly why it is recorded
    # rather than capped.
    # +87 on 2026-09-01 (#298): the advisory obligation attached to DISCOVERY
    # START -- open with your read of the problem before the first question.
    # The tone half of advisor-first shipped in 2026-07 as the digest's stance
    # block, and #298's premise is that a stance living only in adjectives
    # decays under context pressure and on weaker models. So the obligation is
    # now attached at three checkpoints an agent already hits, in the surface
    # that owns each: here, `planning.md` at plan presentation, and CLAUDE.md's
    # Before-Building check. Unfunded by design -- the on-demand class carries a
    # reading and no ceiling (#688), and the always-injected surface (CLAUDE.md)
    # is where the same feature paid at a ceiling.
    # +311 on 2026-09-01 (#299): the domain-concern checklist, SEEDED BY THE
    # SIX STRUCTURAL CHARACTERISTICS. "Detect domain-specific concerns
    # dynamically, no hardcoded lists" is a judgement offload with no floor
    # under it -- on a weaker model, "dynamically" degrades to "from memory",
    # and what a hardcoded list was badly doing was guaranteeing a floor. The
    # seed table restores the floor without becoming the list: it is keyed to
    # characteristics the product already recorded, and the paragraph after it
    # says in terms that the table is the floor and the ceiling is the agent's.
    # Unfunded, and it is the on-demand class -- growth here is declared, not
    # blocked (#688), and paid only by a session that opens the guide.
    "methodology/discovery.md": 5150,
    # 4301 -> 4791 on 2026-08-21 (Chunk 02): `### Partition: Serial or
    # Delegated`, the plan-time half of the placement bet. The partition prompt
    # where chunk boundaries are drawn (R6), the `partition:` field the decision
    # is recorded in either way (R7), the disclosure a delegating plan owes when
    # it is presented (R8-R9), the four reasons to ask and the three standing
    # negatives as a CLOSED list (R10), and the offer that makes a yes durable
    # (R11).
    #
    # A READING, no ceiling, per the decision block above this dict — and the
    # growth here is the feature rather than an overrun. Guidance placed where
    # the coordinator already STOPS is the whole design; guidance in a file
    # someone might open is what produced 0.34% delegation across 31,220 tool
    # calls. No trim was owed and none was invented — and to be exact about
    # what that does NOT claim: two lines here (the plan-time question, and
    # serial-is-right-but-unexamined-is-not) ARE near-verbatim with
    # `delegation.md`, deliberately, because the guide is on-demand and this
    # section fires whether or not anyone opens it. Both copies are test-pinned
    # on both sides, so they cannot drift into disagreeing. What genuinely
    # stayed out is the rest: the wall-clock reasoning, the anti-patterns and
    # the brief contract, which this section points at instead of restating.
    # +60 on 2026-08-21 (Chunk 04's cumulative, R-7): two of the four
    # ask-for-approval reasons turned on delegation history that nothing in
    # `.prawduct/` records. The closed list exists because an agent resolving
    # vagueness asks defensively every time, so a trigger with no observable
    # behind it reintroduces the exact cost the closure buys — or invites an
    # agent to assert a precedent it never checked. What was added is the
    # observable, not a fifth reason: the `partition:` lines on live and
    # archived plans, and whether `project-preferences.md` carries a Delegation
    # row. NOT paid for in place, and this file has a reading rather than a
    # ceiling, which is exactly the on-demand class #688 decided to account for
    # without blocking — the cost is opt-in, paid by a session that opens the
    # guide. Recorded here rather than absorbed, because an unrecorded change is
    # the only thing a reading refuses.
    # +9 on 2026-08-24: the plan-retention pointer cited "/prawduct:pr merge-flow
    # step 7", which a step inserted into that flow turned into "Clean up evidence
    # file". Replaced with the step's NAME, which costs tokens and cannot rot --
    # a durable pointer must not ride on a position that renumbers.
    # +200 on 2026-08-27 (branch-claim-multiplicity, at the base sync): the
    # multi-claim precedence — sole claimant, then chunks left, then
    # `active_build_plan`, then path order — is written here and nowhere else,
    # and every other surface points at it, so it cannot be a pointer itself.
    # Paid down first rather than recorded whole: the pointer-clear rule kept its
    # RULE here and handed its WHY to `/prawduct:pr`'s Merge Flow step, which
    # states it at length, saving ~58 of the ~258 the merge brought in.
    # +303 on 2026-09-01 (#296): a `### Plan Shape` subsection -- one plan per
    # scope tag, split when the change types differ, a plan that will not ship
    # in ~3 sessions is a program (backlog items plus per-wave plans), and the
    # planner pushes back on a monolithic-plan request. NOT funded by a cut, and
    # the reason is the file rather than the size: `building.md`'s size ladder
    # was reading as an instruction to build ONE big chunked plan, and the
    # long-lived-plan frictions sat in `learnings.md` for weeks without ever
    # reaching the guide that would have prevented the next one. This is the
    # on-demand class -- planning.md carries a reading and no ceiling (#688), so
    # its growth is declared rather than blocked, and the cost is paid only by a
    # session that opens it. The pushback bullet is also #298's plan-creation
    # advisory obligation in its plan-shape form: the obligation is stated where
    # the decision is made, not in the digest's adjectives.
    # +103 on 2026-09-01 (#298): the advisory obligation attached to PLAN
    # PRESENTATION -- say what you would do differently before the chunks, and
    # "nothing, this is the right shape" is a fine answer; what is not an option
    # is a plan handed over with no position on it. Distinct from the Plan Shape
    # pushback above, which is one specific take (this plan is too big); this is
    # the general obligation that take is an instance of.
    "methodology/planning.md": 5466,
    # 4529 -> 4644 on 2026-08-19, and this is the new control's FIRST firing:
    # the assertion went red the moment the file changed without its reading,
    # carrying the number to write. Cause — Critic R-7, the unpriceable-ledger
    # branch on the live-review deadline. Recorded, not capped, which is the
    # decision above working as intended: the growth is a correction to an
    # instruction that could not be followed in a fresh clone.
    # 4644 -> 4702 on 2026-08-19 (Critic R-5): the deadline recipe named a
    # filter `review-stats` does not accept (it takes none — the figure is a row
    # of its `by role x model x mode` block), and stated the sample floor as "a
    # handful" one clause after citing `MIN_PRICED_SAMPLE`, which is 5. Both
    # were instructions an agent executes at every turn a review is live, so the
    # cost buys a recipe that runs instead of one that reads well.
    # 4702 -> 4885 on 2026-08-21 (+50 for the boundary step, +133 for the clear
    # paragraph): the work-cycle boundary gained REAPING as its first step, and
    # the clear verdict gained the test that generates it. The step states the
    # rule and POINTS for the argument: `delegation.md` already carried "never
    # as a mid-flow interrupt" with its reasoning, and the first draft here
    # restated that reasoning verbatim — two homes for one argument, in the
    # same commit that created the second. The placement itself stays, because
    # a step in a close sequence that does not say when it runs is not a step.
    # Reaping is placed at the boundary and nowhere else because a mechanism
    # that exists to protect focus must not become the thing that breaks it —
    # an interrupt-driven reap is the anti-pattern, so the placement IS the
    # rule and it costs a clause to say. The clear paragraph names the general
    # test (recovery cost — does a clear leave the work alone?) rather than
    # adding a second special case beside the live-review one: this repo got
    # that verdict wrong twice in one session, in opposite directions, and both
    # errors were reasoning from the special case because the principle was
    # never written down. A READING, no ceiling, per the decision block above
    # this dict — the cost is paid by a session that opens the guide.
    # +209 on 2026-09-01 (#299): the ROOT-CAUSE STOPPING RULE. "Stop when you
    # reach something you can change" is true and unusable under pressure --
    # every link in a why-chain is something someone could change, so the rule
    # licensed stopping at the first one. The replacement is three conditions
    # that must ALL hold (changeable here, would have prevented this instance,
    # would prevent instances that look different), plus the tell that the chain
    # stopped early: a terminal that restates the failure ("we were in a hurry",
    # "nobody reviewed it") rather than explaining it. Principle 16 is the norm;
    # this is the procedure that makes it checkable.
    "methodology/reflection.md": 5094,
    # First reading, 2026-08-21, taken at birth: a new on-demand guide, so it
    # joins the class above — a READING, no ceiling. `test_every_methodology_guide_is_accounted_for`
    # requires the entry; the decision block above this
    # dict is why it is not a ceiling. This guide is the cheap destination that
    # policy exists to protect: its whole cost is paid by a session that opens
    # it, and the reason it exists at all is that `building.md` could not hold
    # the content at any price.
    #
    # The first draft was 1041 and tripped `test_no_suite_total_claims` by
    # quoting the shape it was warning about — the measured pass counts of three
    # contended runs. Restated relationally (three different totals, none more
    # than about half of what the suite collects, all exiting 0), which costs 15
    # tokens and keeps the evidence: the numbers were never the point, the
    # divergence was.
    #
    # -3 in the same chunk's fix pass: the briefing-cost paragraph said the cost
    # "is a real constraint today", a time-anchor in durable prose against a
    # figure an open backlog item exists to move. Restated as the condition
    # ("while that is what one costs"), which is what stays true either way.
    #
    # 1053 -> 1415 on 2026-08-21, and NOT paid for in place: the guide answered
    # how to delegate well and never whether to delegate at all (owner review at
    # the plan's post-Chunk-01 checkpoint — it "leaps right into the weeds").
    # R18 and its ruling are in the discovery artifact. The addition is a
    # `## When to delegate` section leading the guide: the default, the cases
    # that override it, the cases that defeat it, the route to the project's own
    # policy, and the qualifier that a fanned-out plan is only faster once each
    # delegate's verification is bounded.
    #
    # No trim was owed and none was invented. This is an on-demand guide — a
    # READING, no ceiling — and the decision block above this dict says why:
    # growth here is the CHEAP growth, paid only by a session that opens the
    # file, and pricing the cheap destination inverts the incentive that put
    # this content outside `building.md` in the first place. What was paid in
    # place is the ~14 tokens of duplication the addition created: the
    # Considerations list asked "is briefing this delegate cheaper than doing
    # the work inline?", which the new section now answers as a decision rather
    # than re-asks as a question.
    #
    # +4 in the same pass, from a self-scrub the review did not have to catch:
    # the preamble promised "states the goal and supplies the considerations"
    # one screen above a section that states a RULE, so the guide contradicted
    # itself about its own nature — and the title still named only what a
    # delegate verifies, after the "when" became what leads the file.
    # +7 on 2026-08-21 (Chunk 02): "Record it either way" had no destination
    # until this chunk gave the decision one, so the guide now names the plan's
    # `partition:` field. Without it the guide asks for a record and leaves the
    # reader to invent where it goes, which is the gap between encouraged and
    # recorded that the chunk exists to close.
    # +44 on 2026-08-21 (Chunk 03): the unattributable-green anti-pattern had a
    # tell and no remedy, so a coordinator who caught themselves doing it had
    # nowhere to go — the record could not say a run was degraded. Now it can,
    # and the bullet names the flag that says so. Paid at the on-demand
    # destination for the same reason the entries above are: growth here is
    # read only by a session that opens the file.
    # +61 on 2026-08-21 (Chunk 04's cumulative, R-9 + R-13). Two fixes, both
    # about this file telling the truth about itself. R-9: the header promised
    # "nothing here names a command, a marker, a tier or a runner" while the
    # unattributable-green bullet four sections down names
    # `test-evidence record --degraded` — correctly, and pinned there by test.
    # The rule the tests actually encode is narrower than the sentence was:
    # no CONSUMER's runner, markers or a tier of prawduct's invention, while
    # prawduct's own commands are in bounds by ruling 9. The claim is relational
    # now, so it states the rule that holds. R-13: the brief contract is the
    # point where a verification ceiling is actually written, and it did not
    # reach for the `Delegate verification` row a project may already have
    # ratified — so a coordinator could invent a ceiling beside the owner's,
    # which is the retyping the whole feature exists to end. Reading, not
    # ceiling: growth here is paid by the session that opens the file.
    # +936 on 2026-08-21: the ad-hoc trigger — a tangent raised mid-chunk, or
    # work the agent was about to backlog — arrives when no partition was ever
    # drawn, so none of the plan-time framing above reaches it. What the section
    # adds is the three-way decision and its policy dial, the four-paths
    # requirements bar, the brief written into the worktree as the dispatch
    # record, the reapability bound, and six anti-patterns with tells. It is a
    # READING for exactly the reason stated above, and this is the growth that
    # rule was written for: nobody pays it who is not already about to delegate
    # a tangent. Two costs were cut rather than written — the diagnosis of WHY
    # scoping a tangent is expensive lives in the discovery artifact and reaches
    # the reader here as one anti-pattern tell, and two considerations that
    # restated rules stated a paragraph earlier were dropped rather than shipped
    # as a list that looks longer than it is.
    # +231 on 2026-08-22 (Chunk 04's cumulative, R-5 and R-13): the doctrine
    # named the brief and its path but never its writer or its moment, and the
    # mechanics file it defers to documents only harness-created isolation —
    # a tree the dispatcher cannot name before dispatch. So under the one
    # documented shape the brief had no author and the advisory that keys on it
    # was inert by construction. The section now says the coordinator creates
    # the worktree, writes the brief, then dispatches; and that reaping ends
    # with the worktree, because a brief left in a reused checkout raises a
    # delegate advisory about work nobody delegated. A READING, so the cost is
    # paid only by a session already about to delegate a tangent.
    # +68 on 2026-09-01 (#300): the anti-pattern half of the same rule -- the
    # Done taken on faith, with the tell that makes it fire (you accepted a
    # completion report on a removal or a sweep without re-deriving it). Not
    # funded by a cut here and deliberately so: this is the on-demand class, its
    # cost is paid only by a session that opens it, and the paired statement in
    # building.md WAS paid for in place against that file's ceiling. An
    # anti-pattern list is the shape a dispatcher scans at dispatch time, which
    # is the moment this rule has to fire.
    "methodology/delegation.md": 2766,
}


@pytest.mark.parametrize("rel_path", sorted(LAST_MEASURED_TOKENS))
def test_recorded_token_count_matches_the_file(rel_path):
    """A budgeted file's recorded size is the file's actual size.

    Fails the moment a budgeted file changes without its reading being updated,
    and the message carries the number to write — so the figure is never
    re-derived by hand, copied from an adjacent line, or predicted.
    """
    actual = estimate_tokens(read_file(rel_path))
    expected = LAST_MEASURED_TOKENS[rel_path]
    assert actual == expected, (
        f"{rel_path} is ~{actual} tokens; LAST_MEASURED_TOKENS says {expected}. "
        f"Update the entry to {actual} (and say in that file's budget comment "
        f"what paid for the change — the ceiling is not a budget to spend)."
    )


# =============================================================================
# The always-injected footprint
# =============================================================================

#: What a session pays BEFORE it does any work, grouped by session shape.
#:
#: **Why a total, when every one of these files could have its own ceiling.**
#: A per-file ceiling cannot see a NEW file. A digest variant added to save
#: tokens in one repo shape can put ~900 of them into every session of that
#: shape with every per-file assertion in this module still green, because none
#: of them watches the SET. That is the defect this total exists to catch, and
#: `test_every_injectable_digest_is_budgeted` below is the half that catches it
#: -- the numbers here only catch growth in files already known.
#:
#: **Why membership is by LOAD EVENT rather than by importance.** Ranking these
#: files against each other needs a weight nobody can derive, and a weighted
#: score would not have caught the defect above either. Grouping by *when the
#: cost is paid* needs no weight: frequency IS the weight, and it is readable
#: out of `hooks/digest.py` rather than assigned by opinion. These two shapes
#: are the unavoidable tier -- paid every session, no opt-out, before the first
#: useful token. The per-dispatch tier (the subagent briefing, the reviewer
#: payload x N reviewers) is deliberately NOT here: it is larger by two orders
#: of magnitude and owned by its own backlog item, and folding it in would let
#: a win there hide growth here.
#:
#: This generalizes `artifacts/nonfunctional-requirements.md` § Direction --
#: "unit-cost is the reviewer's payload, what a mode must load, per-mode and
#: reducible" -- from reviewer payloads to every injected surface.
INJECTED_SESSION_SHAPES = {
    # A framework-repo session: the always-loaded CLAUDE.md plus the one digest
    # `hooks/digest.py` emits for every governed repo.
    "framework": ("CLAUDE.md", "methodology/session-digest.md"),
    # A product session: the thin governance anchor `migrate_plugin` writes into
    # a governed repo's CLAUDE.md, plus the full digest every product receives.
    "product": ("<STATIC_ANCHOR>", "methodology/session-digest.md"),
}

#: The actual total per shape, as last measured -- the reading, not the ceiling.
#: Same contract as LAST_MEASURED_TOKENS: the assertion's message carries the
#: number to write, so a figure is never re-derived by hand or copied forward.
LAST_MEASURED_INJECTED_TOKENS = {
    # First reading, 2026-08-19, taken with the ceilings below.
    # framework 3455 -> 3315: the framework repo stopped receiving a digest
    # variant of its own and now takes the same one every product does, paid
    # for by trimming CLAUDE.md (-1188) to what that digest does not state --
    # its principles roster, its commit conventions, and the restatements of
    # rules the digest already carries. A CUT at the source of the duplication,
    # not a relocation: no prose moved between two members of this set. The
    # digest then gave back 18 more: the no-attribution rule regained the
    # clause stating it outranks a contrary harness default -- which only
    # CLAUDE.md had carried -- paid for in place by dropping a sentence that
    # restated "never blind-append" two lines after it was said.
    #
    # product 2256 -> 2238: the SAME digest trim, and the only reason this
    # entry moved. The digest is a member of BOTH shapes while CLAUDE.md is a
    # member of one, so a digest edit lands on every reading here and a
    # CLAUDE.md edit lands on one. An edit that updated only the shape being
    # worked on is what this pin caught.
    #
    # +5 on both shapes, 2026-08-19: the disposition labels became
    # `RUNNING`/`YOUR TURN`/`COMPLETE` on one axis (what produces the next turn)
    # and the findings-only clear rule landed. That is ~113 tokens of new rule
    # funded almost entirely IN PLACE -- the size/type table the digest restated
    # from `building.md`, a worked example of the stale-count rule, the stance
    # preamble's second argument for its own first sentence, and four
    # explanations of rules the same bullet had already stated. Net +5 is what
    # the trim could not reach; both ceilings still hold.
    #
    # -3 on both shapes, 2026-08-19 (#687): the standing block's CLEAR line
    # gained the binding it never had. The in-flight rule bound only the
    # DISPOSITION line, so `RUNNING` beside `SAFE TO CLEAR` was emittable --
    # and this repo emitted it three times with a Critic review live. A live
    # review now moves the verdict, and its copy carries a computed deadline
    # rather than only a reason, because the reader about to step away is
    # asking by WHEN to check back.
    #
    # Paid for in place and past the addition, by cutting a CLASS rather than
    # words: three section headings carried a parenthetical restating a fact
    # the preamble or their own body already stated -- `## Principles (apply
    # with judgment, not mechanically)` is verbatim the opening sentence,
    # `## Read on demand (plugin skills -- the full guides ship in the plugin)`
    # is the rest of it, and `## Enforcement (this is what makes governance
    # stick)` is the claim its two sentences go on to make. `(stance)` on the
    # fourth heading is a LABEL, not a restatement, and stays.
    #
    # +3 on both shapes, 2026-08-19 (Critic R-7): the deadline recipe told the
    # agent to compute an expected total and forbade a constant, while naming
    # no branch for the case where the ledger cannot price one — and the ledger
    # is gitignored, so it is EMPTY in every fresh clone and every newly
    # onboarded product. The digest now says "expected when priceable"; the
    # full rule (report elapsed and the roster, name the expectation
    # unavailable, and why a one-sample median is a missing number rather than
    # a small one) lives in `reflection.md`, which is the split this bullet
    # already uses. Three tokens rather than the eight a fuller phrasing cost:
    # the first draft spelled out "where the ledger can price one" and broke
    # the ceiling, which is the ceiling doing its job.
    #
    # +1 on `framework` only, 2026-08-19 (Critic R-8): CLAUDE.md was the FOURTH
    # member of the class three earlier commits narrowed — a surface asserting
    # the marker's guarantee without the *bare*-invocation qualifier. It sat
    # outside the earlier sweeps because those bounded the class by CONTAINER
    # (`plugin/**`) rather than by PROPERTY, and this file is at the repo root.
    # Closed by dropping the mechanism clause rather than qualifying it — the
    # sentence is already a pointer to `SKILL.md`, which owns the fact, so
    # restating it precisely would have been a more accurate second home. One
    # token is what a pointer costs over a claim.
    #
    # framework 3321 -> 3310, product 2243 -> 2236 (2026-08-21). `delegation`
    # joins both always-injected ROSTERS — the name only, never a rule: a
    # roster that omits a live topic is a false statement of fact on the one
    # surface an agent reads before it opens anything, and it is also the only
    # surface reaching an agent that opens no guide at all. The ruled-out thing
    # was a delegation *line* (guidance, priced every session forever); listing
    # the topic is not that, and the owner ruled for the listing.
    #
    # PAID FOR past the addition, by a class in each member. CLAUDE.md's guide
    # roster carried a per-topic when-to-read gloss ("before exploring a
    # problem", "before designing artifacts or a build plan") that
    # `skills/methodology/SKILL.md` owns and states more fully for all seven
    # topics — CLAUDE.md was restating three of them, and adding the sixth
    # guide would have meant writing a fourth. The digest's reader line said
    # "overview and the guide reader: pass a topic to open it" and then
    # demonstrated the form on the next line; the demonstration is the whole
    # instruction, so the sentence explaining it went.
    #
    # The ceilings are deliberately NOT ratcheted with this cut, which departs
    # from the standing slack-is-a-loan rule and says so rather than doing it
    # silently: the owner's ruling was explicitly "start this way and dogfood,
    # and promote to more tokens in CLAUDE.md if we need to". The headroom is
    # reserved for that promotion, and the load-bearing assumption it would
    # answer is recorded in `build-plan-delegation.md`'s Requirements
    # Confidence.
    # framework 3310 -> 3343, product 2236 -> 2269 (2026-08-21). Both shapes
    # move by the same +33, because every token of this change is in the digest.
    # Three edits. Stated as WORD deltas with the token figure derived, because
    # `estimate_tokens` truncates and per-string token deltas therefore do not
    # sum to the file's: the words do, and 1519 -> 1544 is the whole change.
    #
    #   trim across the two boundary bullets        -17 words   -22
    #   the standing block accounts for a delegate   +9 words   +12
    #   the mid-chunk tangent trigger               +33 words   +43
    #
    # THIS TABLE IS NOT THE ONLY BUDGET ON THE DIGEST, and that is the lesson
    # of this entry rather than any figure in it. `session-digest.md` is emitted
    # as SessionStart `additionalContext`, which Claude Code spills to a file
    # above 10,000 CHARACTERS — a hard harness threshold, pinned by
    # `tests/test_plugin_methodology_digest.py`'s two inline-limit assertions
    # and raisable by nobody. It had 216 characters free at this branch point;
    # this change wanted 228, and the first draft went 12 over while every
    # assertion in THIS module was green. The two budgets lived in two modules
    # with no reference between them, so a careful token accounting here could
    # not see the wall it was walking into. Check both. When the character
    # limit binds, the ceilings below are irrelevant — a ratchet is policy and
    # can be declared past, and 10,000 cannot.
    # THE TRIM IS REPORTED, NOT ASSUMED, and it came in under what the two
    # edits needed — which was the plan's stated assumption and is now a
    # number. What it recovered was one CLASS, not a rewrap (a word-count
    # estimator returns nothing for rewrapping): prohibitions restating what
    # the same bullet already requires positively. "Burying, padding or
    # collapsing it fail alike" forbade three things the bullet had already
    # required — "last, after every other word" is the anti-burying rule and
    # "three **separate paragraphs**" is the anti-collapsing one — so only
    # padding and the reason ("the bottom is all they read") survived, folded
    # into the opener. Same class in the handoff bullet's consequence clauses,
    # and `COMPLETE`'s gloss, which said "a blank slate" and "no next action to
    # propose" for one idea. This is an IN-PLACE dedup, the only kind that is
    # honest here: funding a digest cut against an on-demand guide is a
    # deletion for the reader who never opens one, and that reader is the whole
    # reason this surface exists (`learnings.md`, and the plan's `architecture`
    # disposition).
    #
    # The +12 was MANDATORY at any budget: the bullet said an unread background
    # agent is `RUNNING`, never `COMPLETE`, and said nothing about the clear
    # verdict, so an injected rule would otherwise have contradicted the feature
    # it now carries. Sought as a rewording and found one — the findings-only
    # sentence already said "not `SAFE TO CLEAR` until it is on disk", so the
    # delegate joins that clause instead of opening a second one.
    #
    # The +43 is a DECISION and the ceilings below are raised for it. It buys
    # the one moment nothing else in this plan reaches: a tangent arriving
    # mid-chunk, which an agent otherwise resolves silently by doing it inline
    # or dropping it. The backlog-skill prompt covers the second moment only,
    # and only when the instinct was already to file something. The
    # ready-to-build qualifier is load-bearing rather than decorative: an
    # unbounded prompt on a surface with no opt-out is the defensive-asking
    # failure this feature's own discovery names as its live risk, and the
    # qualifier is the same bar the backlog prompt fires on, so the two
    # triggers state one rule instead of two. Five of the 33 words are the
    # `Delegation: off` escape, which is not decoration either: this bullet
    # INSTRUCTS, and without the escape it would have an agent proposing
    # delegation in a repo whose preferences disabled it — the digest overriding
    # a project preference on the one surface that cannot be opted out of. It is
    # also the form the two neighbouring policy bullets already use, naming the
    # governing row inline rather than behind the pointer.
    # framework 3343 -> 3159, product 2269 -> 2085 on 2026-09-01 (#630): the
    # digest's stance block was RELOCATED, not cut. Its nine checkable bars now
    # live in `docs/principles.md` § Agent Stance -- reachable by the pointer the
    # block already carried and by `/prawduct:methodology principles` -- while
    # the digest keeps the lead position (the expert take leads, compliance
    # second) and the roster of nine names. That split is the classification
    # #630 asks for, applied to the one section where it is unambiguous: the
    # LEAD is what a thin-anchor repo is wrong without, and the bars are a
    # lookup a reader consults once they are checking themselves against one.
    # The obligations that the bars used to carry alone are separately being
    # attached to the checkpoints an agent already hits (#298), which is what
    # makes this relocation safe rather than a quiet demotion.
    #
    # THE CEILINGS ARE DELIBERATELY NOT RATCHETED IN THIS COMMIT, and this is
    # the declaration that stops the slack being a silent loan: #298's
    # `CLAUDE.md` line spends part of this relief, and the ratchet lands with it
    # in the next commit, at one over the reading it leaves. Ratcheting here
    # would have forced that commit to RAISE a ceiling to make room for an
    # addition this one had already paid for -- the accounting reading exactly
    # backwards from what happened.
    # framework 3159 -> 3197 on 2026-09-01 (#298): CLAUDE.md's Before-Building
    # check gained a fourth question -- "should it be built as asked?", leading
    # with the expert take. Charged to `framework` alone, since `product` takes
    # the static anchor rather than this file. SPENT OUT OF #630's RELIEF, in
    # the commit that relief's own entry above named: the two commits net to
    # framework 3343 -> 3197 and product 2269 -> 2085, and no ceiling was
    # raised at any point.
    #
    # Why this line is worth a surface with no opt-out. The check already fired
    # at the right moment and asked the right three questions -- and all three
    # are about the WORK, so an agent could answer them completely and never
    # form a view on whether the work should happen. That is the gap: the most
    # expensive failure available here is building the wrong thing well, and it
    # is invisible to a check that only interrogates scope.
    # 2026-09-02 (learnings-v2 chunk 05): CLAUDE.md repointed four learnings references
    # at .claude/rules/learnings/; paid by dropping the lookup-skill mention and the
    # "read learnings.md" instruction (the harness loads the rules now).
    "framework": 3194,
    "product": 2085,
}

#: Ceilings. HARD, like the per-file prose ceilings in this module and
#: unlike the advisory state-file size threshold in
#: `artifacts/nonfunctional-requirements.md` § Direction -- that norm governs
#: `.prawduct/` STATE files, these are shipped instruction payloads. Recorded as
#: a decision (owner ruling 2026-08-19) rather than assumed, because the norm's
#: wording would otherwise read as covering this: an advisory would not have
#: caught the defect above, since nothing was blocked when the set grew.
#:
#: The standing rule is the per-file one: THE NEXT ADDITION TRIMS OR RELOCATES,
#: IT DOES NOT BUMP -- with "relocates" meaning *into a file outside this set*,
#: never between two members, which buys nothing and is banned outright
#: (owner rule 2026-08-05: total footprint is the only number that matters).
INJECTED_FOOTPRINT_CEILINGS = {
    # Ratcheted with the readings they guard (3460 -> 3325, 2260 -> 2248): a
    # ceiling left at its old value after a cut silently re-funds the growth
    # the cut paid for -- the next addition trims or relocates, it does not
    # bump. Ratcheting with every cut is what that rule MEANS here, and it has
    # driven headroom to a token or two rather than to any target figure: the
    # 2026-08-19 entry below left 1 on `framework` and 2 on `product`. So a cut
    # that does NOT ratchet is a departure and has to say why, whatever the
    # resulting headroom happens to be. (This paragraph used to name "~10 by
    # design" as the target; two ratchets had already falsified it, and a
    # 2026-08-21 review reasoned from the stale figure to the wrong conclusion
    # about whether a departure had occurred.)
    #
    # Both shapes carry the digest, so a digest addition is charged twice and
    # both ceilings bind it; only a CLAUDE.md edit is charged to `framework`
    # alone.
    #
    # -3 on both, 2026-08-19: ratcheted with the readings again. The clear-line
    # binding cost less than the heading-parenthetical class that funded it, so
    # both readings landed BELOW where the branch started; leaving the ceilings
    # would have banked that difference as headroom for the next addition,
    # which is the re-funding this comment's first paragraph forbids.
    # 3322 -> 3344, 2245 -> 2270 on 2026-08-21. A DELIBERATE RAISE, +22 and
    # +25, and the first one this table has taken. The ratchet forbids
    # UNDECLARED growth, not declared growth, and this is the declaration: what
    # it bought is the mid-chunk tangent trigger, priced at +43 in the reading
    # above, against 22 tokens of trim and the headroom that was already
    # reserved for it.
    #
    # BEFORE YOU DECLARE THE NEXT ONE: this table is raisable and the digest's
    # other budget is not. It ships as SessionStart `additionalContext`, which
    # Claude Code spills to a file above 10,000 characters
    # (`tests/test_plugin_methodology_digest.py`), and no ruling buys a
    # character past that. This chunk left the digest at 9987 of 10,000 — so a
    # raise declared here is worth nothing unless the characters are there
    # first, and they very nearly were not. Check that limit BEFORE doing this
    # arithmetic, not after.
    #
    # The headroom was reserved on the record, which is why spending it is not
    # this comment's departure. The 2026-08-21 entry above notes the ceilings
    # were deliberately NOT ratcheted with the cut that funded delegation's
    # first digest mention, on the owner's ruling to "start this way and
    # dogfood, and promote to more tokens if we need to". This is that
    # promotion. What exceeds the reservation is the raise, and it is set to
    # exactly one over the reading — zero headroom, so the NEXT addition is
    # back under the standing trim-or-relocate rule with nothing banked.
    #
    # The counter-case, recorded because a raise that only argues for itself is
    # how the next one gets easier: 43 tokens are paid by every session of
    # every governed repo forever, the trigger fires on a judgement the agent
    # makes constantly, and its failure mode — asking defensively every time —
    # is the risk this feature's discovery flags as unprovable in advance. The
    # ready-to-build qualifier bounds it; whether that holds is a thing to
    # watch. Reverting it is a two-line cut, and the mandatory half alone lands
    # UNDER the ceilings this raise replaces — with room to ratchet down rather
    # than up. (Measured, not asserted; the figure is deliberately not written
    # here, because a revert target copied into prose goes stale the next time
    # either shape moves and reads as fact while it is wrong. Drop the bullet
    # and read what the assertion prints.)
    # 3344 -> 3198, 2270 -> 2086 on 2026-09-01 (#630 + #298, ratcheted here
    # because #630 deliberately deferred it one commit rather than force this
    # one to RAISE for an addition the previous commit had already funded).
    # Back to one over the reading -- zero banked, so the next addition is under
    # the standing trim-or-relocate rule with nothing to collect silently.
    #
    # The reserve #630 restored is NOT held here, and that is the point: this
    # table's unit is tokens and it is raisable by declaration, while the
    # reserve is characters against a harness threshold that no ruling buys past
    # (`tests/test_plugin_methodology_digest.py`'s DIGEST_HEADROOM_RESERVE).
    # Banking headroom in a raisable budget would have protected nothing.
    "framework": 3198,
    "product": 2086,
}


def test_every_methodology_guide_is_accounted_for():
    """No methodology guide sits outside the #688 answer — including new ones.

    THE HALF THAT MAKES THE DECISION A POLICY RATHER THAN THREE ENTRIES. The
    readings above only watch files someone remembered to add; this watches the
    DIRECTORY, which is what nothing was watching when `reflection.md`,
    `discovery.md` and `planning.md` all went unbudgeted and the issue reporting
    it named only one of them. Adding `methodology/onboarding.md` tomorrow and
    forgetting the table is precisely the mistake being guarded, and it is the
    same blind spot `test_every_injectable_digest_is_budgeted` closes one tier
    up.

    **Two ways to be accounted for, not one.** A guide is covered either by a
    per-file reading in `LAST_MEASURED_TOKENS` (the on-demand class) or by
    membership in an injected session shape, where the total is the budget and a
    per-file reading would be a second, staler copy of it. `session-digest.md`
    is the whole reason the check has to allow both: it is a `methodology/*.md`
    file that is deliberately absent from the readings table because
    `LAST_MEASURED_INJECTED_TOKENS` already prices it — twice, once per shape.

    Deliberately says nothing about ceilings. Whether a guide gets one is the
    decision recorded above this dict, and a test asserting the *absence* of an
    assertion would encode today's answer as structure — which is what makes a
    policy hard to revisit rather than easy to see.
    """
    injected = {m for members in INJECTED_SESSION_SHAPES.values() for m in members}
    guides = sorted(
        str(p.relative_to(ROOT))
        for p in (ROOT / "methodology").glob("*.md")
    )
    assert guides, "found no methodology guides at all — ROOT is wrong"
    unaccounted = [
        g for g in guides
        if g not in LAST_MEASURED_TOKENS and g not in injected
    ]
    assert not unaccounted, (
        f"methodology guide(s) with no size accounting: {unaccounted}. Every "
        "guide is either a per-file reading in LAST_MEASURED_TOKENS (the "
        "on-demand class — see the decision recorded above that dict) or a "
        "member of an injected session shape, where the shape total is the "
        "budget. Add the reading; the sibling assertion will tell you the "
        "number. Do NOT delete this check to make a new guide green."
    )


def _clear_line_guidance() -> str:
    """Just the standing block's CLEAR item from `reflection.md`.

    Pins about what the clear line must and must not say belong to that item,
    not to the whole guide -- a negative assertion run over a 200-line file
    goes red on edits that have nothing to do with it, and a pin that cries
    wolf gets deleted rather than investigated.

    Delimited by the numbered item's own start and the next unindented
    paragraph, because the item's continuation paragraphs are indented and its
    successor is not. Asserts it found both ends: a silently-empty slice would
    make every positive assertion below it fail for the wrong reason and every
    negative one PASS vacuously, which is the worse half.
    """
    text = read_file("methodology/reflection.md")
    opener, closer = "3. **Clear** —", "\n**Three ways to fail this"
    start, end = text.find(opener), text.find(closer)
    for label, found in (("opener", start), ("closer", end)):
        assert found != -1, (
            f"`_clear_line_guidance` cannot find the {label} it slices on "
            f"({opener if label == 'opener' else closer!r}) — `reflection.md`'s "
            "standing-block section was restructured. Re-point the delimiters; "
            "do not delete the pins that depend on this."
        )
    item = text[start:end]
    assert len(item) > 500, (
        "the clear-line slice came back too short to be the real item -- the "
        "delimiters in `_clear_line_guidance` no longer match `reflection.md`, "
        "and every negative assertion using it is now passing vacuously"
    )
    return item


def _injected_member_text(member: str) -> str:
    """One member of an injected set, resolved to its text.

    Two members are not plugin-relative files: the framework repo's own
    `CLAUDE.md` sits at the repo root, and the product anchor is a Python
    constant rather than a file at all. Reading the anchor from its definition
    rather than from a copy is the point -- a copy here would be exactly the
    second authoritative statement this whole plan deletes elsewhere.
    """
    if member == "<STATIC_ANCHOR>":
        from lib.migrate_plugin import STATIC_ANCHOR

        return STATIC_ANCHOR
    if member == "CLAUDE.md":
        return (REPO_ROOT / "CLAUDE.md").read_text()
    return read_file(member)


@pytest.mark.parametrize("shape", sorted(INJECTED_SESSION_SHAPES))
def test_recorded_injected_footprint_matches_the_files(shape):
    """A session shape's recorded total is what its members actually sum to.

    The reading half. Fails the moment any member changes without the total
    being restated, so the number in this module is never a stale copy of a
    measurement someone took once.
    """
    actual = sum(
        estimate_tokens(_injected_member_text(m))
        for m in INJECTED_SESSION_SHAPES[shape]
    )
    expected = LAST_MEASURED_INJECTED_TOKENS[shape]
    assert actual == expected, (
        f"the {shape} session injects ~{actual} tokens; "
        f"LAST_MEASURED_INJECTED_TOKENS says {expected}. Update the entry to "
        f"{actual} and say what paid for the change -- the ceiling is not a "
        f"budget to spend."
    )


@pytest.mark.parametrize("shape", sorted(INJECTED_SESSION_SHAPES))
def test_injected_footprint_under_ceiling(shape):
    """Every session pays this before it does any work. Hold it."""
    actual = sum(
        estimate_tokens(_injected_member_text(m))
        for m in INJECTED_SESSION_SHAPES[shape]
    )
    ceiling = INJECTED_FOOTPRINT_CEILINGS[shape]
    assert actual < ceiling, (
        f"the {shape} session injects ~{actual} tokens, over its {ceiling} "
        f"ceiling. Trim a member, or move the content OUT of the injected set "
        f"into an on-demand guide -- moving it to the other member of this same "
        f"set buys nothing, because this assertion sums them."
    )


def test_every_injectable_digest_is_budgeted():
    """Every digest `hooks/digest.py` can inject appears in a budgeted shape.

    THE HALF THAT CATCHES THE ACTUAL DEFECT. The totals above only watch files
    already known; this watches the SET, which is what nothing was watching the
    last time a digest variant was added. Derived from `digest.py`'s own
    `*_RELPATH` constants rather than from a list kept beside them, because a
    hand-kept list has the same blind spot as the per-file ceilings: adding a
    variant and forgetting the list is precisely the mistake being guarded.

    Positive counterpart to the ceilings, per the paired-assertion rule: a
    ceiling can be satisfied by deleting a surface, and a set-membership check
    can be satisfied by budgeting a surface at zero. Both must hold.
    """
    tree = ast.parse((ROOT / "hooks" / "digest.py").read_text())
    declared = set()
    for node in tree.body:
        # BOTH assignment forms and BOTH sequence literals. A check that read
        # only `x = (...)` was blind to `x: tuple[str, str] = (...)` and to a
        # list -- and the non-empty guard below still passed on the surviving
        # constant, so the blindness looked exactly like coverage. A variant
        # added in either shape is the defect this test exists to catch.
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, (ast.Tuple, ast.List)) or not value.elts:
            continue
        parts = [
            e.value
            for e in value.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        if len(parts) == len(value.elts) and parts[-1].endswith(".md"):
            declared.add("/".join(parts))
    assert declared, (
        "no module-level path sequences found in hooks/digest.py. This test reads "
        "the digest set out of the module's own constants; if the module stopped "
        "declaring them as tuples of string literals, this check has silently "
        "stopped watching anything and needs rewriting, not deleting."
    )
    budgeted = {
        m for members in INJECTED_SESSION_SHAPES.values() for m in members
    }
    unbudgeted = declared - budgeted
    assert not unbudgeted, (
        f"hooks/digest.py can inject {sorted(unbudgeted)}, which no session "
        f"shape in INJECTED_SESSION_SHAPES budgets. A digest variant added "
        f"without a shape is tokens in every session that nothing is watching "
        f"-- add it to a shape and record the total."
    )



# =============================================================================
# building.md
# =============================================================================


class TestBuildingMethodology:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("methodology/building.md")

    def test_work_scaled_governance(self):
        """Has governance model with size/type levels, no v4 phase references."""
        assert "Work-Scaled Governance" in self.content
        lower = self.content.lower()
        assert "current_phase" not in lower
        assert "phase transition" not in lower
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content
        for wtype in ["Feature", "Bugfix", "Refactor", "Optimization", "Debt", "hotfix"]:
            assert wtype.lower() in lower

    def test_investigated_changes(self):
        """Has boundary investigation, decision research, and research subagent."""
        assert "Investigated Changes" in self.content
        assert "boundary" in self.content.lower()
        assert "contract surface" in self.content.lower()
        assert "Decision Research" in self.content
        assert "lock-in" in self.content.lower()
        assert "research subagent" in self.content.lower() or "research subagent" in self.content

    def test_build_cycle_structure(self):
        """Has build cycle, test discipline, and common traps sections."""
        assert "Build Cycle" in self.content
        assert "Test Discipline" in self.content
        assert "Common Traps" in self.content
        assert "Uninvestigated decisions" in self.content
        assert "Boundary blindness" in self.content

    def test_resolve_findings_dispositions_rather_than_mandating_fixes(self):
        """The guide half of the disposition rule, pinned like the runtime half.

        `TestBatchFixDirective` in tests/test_critic_consolidate.py pins
        `_BATCH_FIX_DIRECTIVE`; nothing pinned this file's copy, and this
        surface took the regression twice on one branch — "Fix them ALL" in
        the runtime string, then "Fix them all in ONE commit" here — both
        caught by a reviewer, neither by a test. The defect is specifically a
        SELF-contradiction: the reflexive-fix instruction sits ~two paragraphs
        above the rule saying warnings and notes gate nothing, so both halves
        are asserted together and the pair is what fails.
        """
        assert "Disposition them ALL in ONE pass" in self.content
        assert "Warnings and notes gate nothing" in self.content
        # The exact phrasings the runtime's own comment records rejecting.
        assert "Fix them all in ONE commit" not in self.content
        assert "Fix them ALL" not in self.content

    def test_retrieval_over_generation_anchors(self):
        """The cheap-check gate and its Common Trap survive future token-diet
        trims — Principle 24's operational anchors, pinned so the newest prose
        isn't the silent casualty of the next compression pass."""
        assert "The cheap-check gate" in self.content
        assert "Retrieval Over Generation" in self.content
        assert "Tuning a mechanism you haven't read" in self.content

    def test_an_inert_count_is_not_written(self):
        """The BUILDER half of the contestable-count rule. The reviewer half is
        the NOTE cap in both Critic protocol files; this is the supply side, and
        it is the half that matters — a count that was never written cannot be
        corrected, re-reviewed, or argued about.

        It sits beside the self-contained-comments rule because they are one
        failure with two carriers: a durable artifact holding something that
        decays. A chunk number goes wrong when the plan is renumbered; a count
        goes stale on the next commit. Both cost a finding, a fix commit, and
        the round the commit buys. (The sibling rule used to say build ids
        dangle because plans are DELETED -- retired 2026-08-08 with the
        deletion; plans are archived, so the pointer resolves and only the id
        inside it drifts.)

        The pinned content is the TEST, not the prohibition. "Avoid counts"
        would also forbid thresholds, versions and limits, which must stay
        exact — so the rule turns on whether anything branches on the number,
        and that clause is what a trim must not quietly drop.
        """
        assert "a count nothing reads is not worth writing" in self.content
        assert "wrong by two" in self.content, (
            "the rule lost the test that separates an inert count from a "
            "load-bearing one — without it this reads as 'avoid numbers'"
        )
        assert "stay exact" in self.content, "the load-bearing exception is gone"
        # Reader model, not presence. A builder writes the count while INSIDE
        # the build cycle (change-log entry, plan prose, docstring), so the rule
        # has to be in that section — Common Traps sits at the end of the file
        # and is read, if at all, after the prose is already written. This repo
        # has shipped present-and-inert placement before (SKILL.md's header) with
        # every artifact-measuring guardrail green.
        cycle_at = self.content.index("## The Build Cycle")
        rule_at = self.content.index("a count nothing reads")
        next_section = self.content.index("\n## ", cycle_at + 1)
        assert cycle_at < rule_at < next_section, (
            "the count rule left The Build Cycle — a builder meets it after "
            "writing the prose it governs, which is presence without effect"
        )

    def test_references(self):
        """References subagent briefing, boundary patterns, learnings skill."""
        assert ".subagent-briefing.md" in self.content
        assert "boundary-patterns.md" in self.content
        assert "/prawduct:learnings" in self.content

    def test_goal_based_critic(self):
        """References goal-based Critic review."""
        assert "Nothing Is Broken" in self.content
        assert "Design Is Sound" in self.content

    def test_handoff_is_prepared_never_proposed(self):
        """After sustained work the handoff is PREPARED, not proposed.

        Asking "should I write handoff notes?" costs the user a round-trip and,
        if they stepped away while the work ran, replays a large context into a
        cold cache — the exact cost the handoff exists to prevent. Preparing
        unasked costs little and they may continue in place, so the asymmetry
        makes the default unconditional.

        Pinned on both surfaces because this must be framework behaviour a
        consuming product inherits, not a prawduct-local habit: building.md is
        read on demand, and session-digest.md is injected into every session of
        every governed repo, the framework repo included.
        """
        assert "never *ask* whether to prepare a handoff" in self.content
        # Whitespace-normalized, like the two sibling pins in this class. Both
        # carriers hard-wrap, so a raw substring makes the FILL WIDTH part of
        # the contract: a pure rewrap — no word added, removed or reordered —
        # split "never ask / whether to prepare" across two lines and turned
        # this red while the rule was intact. That is a false negative, and a
        # pin that cries wolf gets deleted, which costs more than it ever
        # caught. The phrase is what is pinned; where the line happens to break
        # is not.
        digest = " ".join(read_file("methodology/session-digest.md").split())
        assert "never ask whether to prepare" in digest
        # The why travels with the always-injected surface, not the on-demand one.
        assert "cold cache" in digest

    def test_standing_block_is_on_every_surface_that_claims_it(self):
        """State / Next / Clear, the in-flight rule, and one shared trigger.

        What this guards is COVERAGE: the shape has to reach an agent through a
        surface it actually reads. `reflection.md` is canonical and read on
        demand at the work-cycle boundary; the digest is injected into every
        session with no opt-out, which is what makes it the carrier that cannot
        be missed. Drop the rule from the digest and an agent that never opens
        a guide emits no block at all.

        `building.md` is deliberately NOT here (2026-08-19). It used to restate
        the whole shape, but its reader has already been handed that shape by
        the injected digest before they open the file, so the copy was a second
        authoritative statement of a fact with a home. It keeps the one clause
        only it can make — see
        `test_building_md_binds_the_clear_verdict_to_its_own_steps`, the
        positive half without which this narrowing could be satisfied by
        deleting too much. An earlier docstring here justified the pin as
        protecting a token trim "funded" by relocating this rationale INTO the
        digests; that accounting is disavowed (owner rule 2026-08-05 — moving
        prose between files reduces no total), and the pin stands on coverage.

        Also pins the trigger, which shipped undefined: "every stopping-place
        turn" appeared nowhere else in the plugin, and since every assistant turn
        hands control back, one reasonable reading was "every turn" — which
        appends the block to trivial Q&A and reproduces by volume the burying it
        exists to prevent.
        """
        surfaces = {
            "methodology/reflection.md": read_file("methodology/reflection.md"),
            "methodology/session-digest.md": read_file("methodology/session-digest.md"),
        }
        for name, text in surfaces.items():
            assert "standing block" in text, f"{name} no longer names the standing block"
            # The labels are backticked, not bolded: a code span is the only
            # coloured token near the bottom of a turn, so the eye finds it
            # without reading. Owner-requested 2026-07-31 — the block was
            # correct and complete and still scanned as prose.
            # The disposition and clear lines carry the VERDICT in the label,
            # not the topic: the labels are the only coloured tokens near the
            # bottom of a turn, so a label the reader must read past to learn
            # the answer has spent its colour on nothing.
            #
            # The disposition set is chosen on ONE axis -- what produces the
            # next turn: a machine event, a human utterance, or nothing. That
            # is what makes it exhaustive and mutually exclusive. `BLOCKED` is
            # deliberately absent: obstruction is a REASON, and this line owes a
            # verdict, so obstruction rides in the copy as one shade of
            # `YOUR TURN`. Two labels both meaning "you must speak" force a
            # choice an agent makes inconsistently at the boundary.
            for label in (
                "`STATE`",
                "`RUNNING`",
                "`YOUR TURN`",
                "`COMPLETE`",
                "`SAFE TO CLEAR`",
                "`DO NOT CLEAR`",
            ):
                assert label in text, f"{name} dropped the {label} label"
            # THE HALF A PRESENT-LABEL CHECK CANNOT SEE. A half-done rename
            # leaves BOTH vocabularies live on the same surface, which is worse
            # than either alone -- a reader meets two answers to one question
            # and an agent picks whichever it saw last. The positive loop above
            # passes throughout that state.
            for retired, absorbed_by in (
                ("`NEXT`", "`RUNNING`"),
                ("`BLOCKED`", "`YOUR TURN`"),
            ):
                assert retired not in text, (
                    f"{name} still carries the retired {retired} label; it was "
                    f"replaced by {absorbed_by}. Two live vocabularies for one "
                    "slot is worse than either alone."
                )
            # Deliberately NOT asserting `**State**` is absent. `reflection.md`
            # keeps a bolded "what each line owes" list that *explains* the
            # three lines rather than being the emitted shape, and forbidding
            # the string would delete useful structure to satisfy a proxy. The
            # positive assertion above already fails on a revert: drop the
            # backticked labels and it goes red.
            # The SHAPE is the deliverable, not only the words. Three answers
            # run together stop being separately findable, which is most of
            # what the block is for — so every surface has to say so.
            assert "separate paragraph" in text or "three paragraphs" in text, (
                f"{name} no longer requires the three lines to be separate "
                "paragraphs — without that they render as one run-on block"
            )
            # The `---` rule: the only horizontal break in the turn, so it
            # separates the block from the wall of text above before the reader
            # has parsed a word. Owner-requested 2026-07-31, and pinned on every
            # surface because the DIGESTS are what reach product sessions — a
            # rule that lived only in the on-demand guides would be a one-off
            # for this repo.
            assert "`---`" in text, (
                f"{name} dropped the `---` rule that precedes the block"
            )
            # NOT asserting the word "backtick". Every surface already shows the
            # labels backticked and the assertion above checks that literal, so
            # requiring the word too is a second statement of one fact — the
            # thing `architecture.md`'s one-home norm exists to stop, and it
            # would fail a surface that demonstrates the shape instead of
            # narrating it.
            # Asserted as the LABELS above, not as prose literals. The old
            # assertions pinned "Safe to `/clear`." / "Not safe to `/clear`
            # yet", which were the sentence the reader had to parse; pinning
            # them now would re-require the shape the change removed.
            # Outstanding includes work that is RUNNING, not merely unstarted —
            # the reported failure was signalling safe while reviewers were live.
            assert "in flight" in text, f"{name} dropped the in-flight rule"
            # One trigger, stated the same way, or the surfaces disagree about
            # when the block is owed.
            assert "work outstanding" in text, f"{name} states a different trigger"

    def test_a_live_review_moves_the_clear_verdict_on_every_carrier(self):
        """A live Critic review is `DO NOT CLEAR`, and the copy carries a deadline.

        THE GAP THIS CLOSES. The in-flight rule binds the *disposition* line
        only — "a dispatched review is `RUNNING`, never `COMPLETE`" — and
        nothing bound the line below it, so `RUNNING` beside `SAFE TO CLEAR`
        was a reachable emission. It is not a hypothetical: this repo emitted
        that pair three times on 2026-08-19 with a review live.

        **Asserted on the verdict, not on the mention.** A carrier that merely
        names a running review in the clear copy — "a review is in flight, but
        the work is committed" — satisfies any pin that greps for "review",
        while being exactly the copy-only phrasing this rule replaces. So the
        discriminating content is the verdict token adjacent to the live-review
        subject, plus the deadline the copy owes; both halves have to be there,
        because a verdict with no clock answers *may I clear* and leaves *by
        when must I check back* unanswered, and that second question is the one
        the person stepping away is actually asking.

        Pinned on both carriers for the same reason the shape is: the digest is
        injected with no opt-out, so an agent that never opens a guide gets the
        binding anyway, and `reflection.md` is where a reader sent by the
        digest's pointer arrives.
        """
        for name in (
            "methodology/reflection.md",
            "methodology/session-digest.md",
        ):
            # Normalized because the digest wraps mid-clause: the subject and
            # its verdict sit on different source lines there, and a raw
            # substring match would pin the line-breaking rather than the rule.
            text = " ".join(read_file(name).split())
            assert re.search(r"live (Critic )?review is (also )?`DO NOT CLEAR`", text), (
                f"{name} no longer states that a live review MOVES the clear "
                "verdict. Naming the review in the copy is not this rule — the "
                "pair `RUNNING` + `SAFE TO CLEAR` stays emittable under it."
            )
            # The clock. `DO NOT CLEAR` with a live review is a deadline, not
            # just a refusal, and the copy owes what it is computed from.
            assert "deadline" in text, (
                f"{name} dropped the deadline the `DO NOT CLEAR` copy owes — "
                "without it the line answers *may I clear* and leaves *by when "
                "must I check back* unanswered"
            )
            for input_name in ("elapsed", "roster"):
                assert input_name in text, (
                    f"{name} stopped naming {input_name!r} as an input to the "
                    "deadline. A deadline with no stated derivation invites the "
                    "constant this rule exists to keep out"
                )
        # The nuance lives on the canonical carrier alone, and is load-bearing:
        # the rule is NOT "`RUNNING` implies `DO NOT CLEAR`". Work a clear
        # leaves alone is legitimately both, and over-reading this into a
        # blanket implication would make the clear line a restatement of the
        # disposition line — which is the collapse the two-axis design exists
        # to prevent (see the "different axis" clause the shape pin guards).
        canonical = read_file("methodology/reflection.md")
        assert "for work a clear leaves alone it is correct" in canonical, (
            "reflection.md dropped the clause scoping the new binding to work "
            "a clear DESTROYS. Without it the rule reads as `RUNNING` implying "
            "`DO NOT CLEAR`, collapsing two lines that answer different axes."
        )

    def test_the_clear_line_answers_should_you_without_a_threshold(self):
        """*Should you clear* is answered, and answered without a number.

        #687 scopes every numeric threshold OUT until rebuild cost and
        per-turn growth are measured from real `/clear`s, and separately
        records why a context-fullness gate was rejected: an agent cannot
        reliably measure its own window, and a gate that fires routinely trains
        dismissal. So this pin has a positive and a negative half, and the
        negative is the one that matters — a later edit "helpfully" adding
        "clear when context passes 50%" ships the rejected design, and the
        positive half alone would stay green through it.

        `reflection.md` only: the digest carries the VERDICT binding in its
        shortest true form (and it is charged to both injected shapes, so a
        digest clause costs twice what a `CLAUDE.md` one does), while the
        reasoning belongs to the canonical carrier. Deliberately no headroom
        figure here: this docstring carried one that was wrong when written and
        wrong at every reading since, and a stale number in a docstring about
        budgets is read as guidance. `LAST_MEASURED_INJECTED_TOKENS` owns it.
        """
        clear_item = _clear_line_guidance()
        assert "*should you*" in clear_item, (
            "reflection.md's clear line no longer answers *should you* — it is "
            "back to answering only *can you*, which is the gap #687 names"
        )
        # Keyed to cost, not to a threshold: coverage survives a clear (so the
        # review argument is not the reason), and the read cost of NOT clearing
        # is what grows.
        assert "review-cycle.md" in clear_item, (
            "reflection.md stopped citing where review coverage's survival "
            "across sessions is defined; without it the cost argument reads as "
            "though clearing risks the accumulated reviews"
        )
        # Scoped to the clear line, not the file. A percentage elsewhere in
        # this guide is nobody's business here, and a whole-file ban would go
        # red on an unrelated edit -- a pin that cries wolf gets deleted, which
        # costs more than it ever caught.
        #
        # A regex rather than the literals a first draft listed ("50%",
        # "% full"): the rejected design is ANY numeric fullness trigger, and
        # banning today's phrasings invites tomorrow's 60%.
        threshold = re.search(r"\d+\s*%", clear_item)
        assert threshold is None, (
            f"reflection.md's clear guidance names a percentage "
            f"({threshold.group(0)!r} if matched) — #687 records the "
            "context-fullness trigger as REJECTED on grounds no later edit "
            "re-derives: the percentage proxies the risk rather than measuring "
            "it, and the agent cannot take the measurement anyway"
        )
        assert "context is full" not in clear_item, (
            "reflection.md's clear guidance gates on context fullness, which "
            "#687 rejects: the agent cannot reliably measure its own window"
        )

    def test_building_md_binds_the_clear_verdict_to_its_own_steps(self):
        """building.md drops the shape but keeps the binding only it can state.

        The clear verdict is not a free-standing judgement: it is owed against
        THIS file's chunk-close sequence, and no other surface enumerates those
        seven steps. So the trim above is bounded from below here — cut the
        pointer or the binding as well and this goes red, which is what stops
        "stop restating the shape" from sliding into "stop mentioning it".

        Asserted as the pointer PLUS the binding, not as either alone: a
        pointer with no binding sends the reader away for a rule that is not
        there, and a binding with no pointer leaves a reader who opened only
        this guide holding a verdict with no shape to put it in.
        """
        assert "standing block" in self.content
        assert "steps 1-7" in self.content
        assert "in flight included" in self.content
        # The shape itself is gone: no fenced example, and none of the labels
        # the carriers above pin. Negative and positive together are the
        # contract -- either alone is satisfiable by the change it exists to
        # prevent.
        for label in ("`STATE`", "`RUNNING`", "`YOUR TURN`", "`COMPLETE`"):
            assert label not in self.content, (
                f"building.md restates the standing block's {label} label; "
                "reflection.md and the injected digest own the shape"
            )
        # Where the reader is sent for the shape. Named, not implied -- a bare
        # "see reflection.md" would survive the section being renamed away.
        assert 'methodology/reflection.md` "Work cycle boundary"' in self.content

    def test_handoff_notes_are_reconciled_not_appended(self):
        """A handoff is reconciled against reality on every write, not grown.

        The failure this pins is second-batch accretion: a session prepares
        notes, the user keeps going instead of clearing, and the next close
        stacks a fresh section on top. The reader then has to guess which layer
        is live — and the layer that reads most current is usually the one the
        later work already discharged. Observed in this repo's own
        `.handoff-notes.md`, which carried three stacked sections, one of them
        annotated with a hand-written "still applies" comment because prose was
        doing the job the reconciliation should have done.
        """
        assert "reconcile" in self.content.lower()
        assert "Never blind-append" in self.content
        assert (
            "never blind-append"
            in read_file("methodology/session-digest.md").lower()
        )

    def test_a_findings_only_turn_must_persist_before_claiming_safe_to_clear(self):
        """The clear verdict is computed from disk and process state, so a turn
        whose whole output is analysis IN THE CONVERSATION scores as safe while
        clearing destroys everything it produced.

        Pinned for the DISCRIMINATING content, not the phrase. A deliverable of
        INSTRUCTIONS passes every size and word-presence check while having no
        effect on a reader, so the assertions below name the condition
        (findings-only => persist first) and the self-contradiction tell (a
        `SAFE TO CLEAR` whose stated reason cites the message a clear deletes).
        A rule that merely said "persist your findings" would satisfy a phrase
        check and leave the reader unable to recognise the case they are in.
        """
        for surface in ("methodology/reflection.md", "methodology/session-digest.md"):
            text = read_file(surface)
            # Whitespace-normalized because the phrases below span several
            # words, and both carriers hard-wrap. A pure RE-WRAP -- no word
            # added, removed or reordered -- split "citing the message" across
            # two lines and turned this pin red, which is a false negative: the
            # rule was intact and only the line breaks moved. Pinning prose on
            # raw substrings makes the fill width part of the contract.
            lowered = " ".join(text.lower().split())
            assert "findings-only" in lowered, (
                f"{surface} does not name the findings-only turn -- the reader "
                "cannot apply a rule to a case they cannot identify"
            )
            # The condition, not just the topic: persistence PRECEDES the claim.
            assert ".prawduct/.handoff-notes.md" in text, (
                f"{surface} states the findings-only rule without naming where "
                "the findings go, which leaves it unactionable"
            )
            # The self-contradiction tell. This is the half that models the
            # reader: it lets them catch the failure in their OWN draft, which
            # a bare instruction to persist does not.
            assert "cites the message" in lowered or "citing the message" in lowered, (
                f"{surface} dropped the tell -- a `SAFE TO CLEAR` whose reason "
                "points at the thing a clear deletes is the defect said aloud, "
                "and naming it is what makes the rule self-checkable"
            )

    def test_disposition_label_rules_carry_their_discriminating_content(self):
        """The label set differs from a rename by two rules; pin those, not the names.

        `test_standing_block_is_on_every_surface_that_claims_it` proves the
        three labels are present and the retired two are gone. That check passes
        for a pure rename -- which would leave the set no better than what it
        replaced. What makes it behave differently is the precedence rule (a
        human utterance outranks a running job, so the reader is never told to
        act when they cannot) and the refusal to PREDICT a human turn (an agent
        cannot know a running job will need a decision; it may answer its own
        question). Both are reasoning rules, so both are pinned by their
        substance.
        """
        for surface in ("methodology/reflection.md", "methodology/session-digest.md"):
            text = read_file(surface)
            lowered = text.lower()
            # The axis itself. Without it the three labels are just words and an
            # agent picks by vibe at every boundary.
            assert "what produces the next turn" in lowered, (
                f"{surface} no longer states the axis the labels are chosen on"
            )
            # Precedence: the human wins an overlap, and the copy carries what
            # is in flight -- otherwise that fact leaves the block entirely.
            assert "`YOUR TURN` even when" in text or "`YOUR TURN` even though" in text, (
                f"{surface} dropped the precedence rule -- without it a turn "
                "that needs the reader AND has work running has two defensible "
                "labels, and the choice gets made inconsistently"
            )
            # The no-prediction rule, which is the one an agent is most tempted
            # to break because forecasting feels helpful.
            assert "predict" in lowered, (
                f"{surface} dropped the no-prediction rule: a decision that will "
                "be needed only ONCE a running job lands is `RUNNING`, because "
                "the job may answer its own question"
            )

    def test_reaching_safe_to_clear_is_part_of_finishing_a_long_task(self):
        """The worst outcome in this space is caused by the agent, not the user.

        A multi-hour task lands while they are away and the turn still says
        `DO NOT CLEAR`: they return to a cold cache they pay full price to
        reload AND a session they cannot leave -- purely because bookkeeping
        trailed the work. Canonical guide only: the rule is about how the agent
        SEQUENCES a long task, which is the on-demand guide's subject, and the
        injected digest is budget-bound to the rules it must carry unconditionally.
        """
        text = read_file("methodology/reflection.md")
        lowered = text.lower()
        assert "before a long wait" in lowered or "before the wait" in lowered, (
            "reflection.md does not say WHEN to write the forward notes for a "
            "long-running task. 'Prepare it, don't ask' is silent on timing, and "
            "notes written after the wait leave an away-reader stranded during it"
        )
        assert "part of the task" in lowered, (
            "reflection.md no longer states that reaching `SAFE TO CLEAR` is part "
            "of finishing a long task rather than a report about it"
        )

    def test_handoff_notes_are_read_before_being_rewritten(self):
        """Reconciling requires READING first, and that had to be said.

        Only `/clear` consumes `.handoff-notes.md`, so within one session a
        second batch finds the first batch's notes still on disk. An agent
        told to "reconcile" but not to read goes straight to a write and
        deletes live items it never saw — the same loss the channel exists to
        prevent, arriving by the door the fix opened. The instruction to write
        these notes long predated any instruction to read them.
        """
        assert "read `.prawduct/.handoff-notes.md` before rewriting it" in self.content
        content = read_file("methodology/session-digest.md")
        assert "before rewriting it" in content
        # The why belongs on the injected surface, not the on-demand one.
        assert "/clear` consumes" in content

    def test_work_cycle_size_is_priced_on_diff_not_chunk_count(self):
        """The re-priced rule (#687) states the rationale that survived, in the
        unit that survived with it.

        The rule used to read "limit work cycles to 1-3 chunks — Critic quality
        degrades across a large diff, and long-session compaction can lose
        governance context." Two rationales, different expiry dates. The
        compaction half was ceded; the review-scope half was not, because a
        large diff is hard to review through the reviewer's ATTENTION, not its
        context window — so a bigger window does not ease it, and arguably makes
        it worse by removing the friction that was incidentally holding diffs
        small.

        Pinned on the DISCRIMINATING content, not on the absence of "1-3". A
        negative-only assertion passes against a sentence that names no unit at
        all, which is the likeliest way this decays: the count is easy to delete
        and the replacement unit is easy to never write. So this asserts the
        attention/window distinction (without which a future reader re-derives
        the ceded rationale and re-adds it) and that a diff-shaped unit is
        named.
        """
        assert "1-3 chunks" not in self.content, (
            "the chunk-count proxy retired with the rationales it stood for"
        )
        lowered = self.content.lower()
        assert "attention" in lowered and "window" in lowered, (
            "building.md no longer says WHY the review-scope rationale survives "
            "a larger context window — without the attention/window distinction "
            "the ceded compaction argument reads as still live"
        )
        assert "judgeable files" in self.content, (
            "the rule names no diff-shaped unit, so 'size by the diff' is "
            "unactionable — deleting the count is not the same as replacing it"
        )
        # Compaction's REAL invariant is untouched and must stay: what was ceded
        # is compaction as a reason to cap cycle length, not the rule that
        # unpersisted state dies at a compaction boundary.
        assert "must be written to a file first" in self.content, (
            "the ceded rationale took the persistence rule with it; only the "
            "cycle-length argument was ceded"
        )

    def test_chunk_close_routes_backlog_to_skill(self):
        """The chunk-close sequence routes backlog work through /prawduct:backlog
        (not hand-edits) — workflow wiring, Chunk 09. Guards the routing."""
        assert "/prawduct:backlog" in self.content

    def test_token_budget(self):
        # Lowered 4950 -> 4600 in prose-diet Chunk 02 (MET-3Q8V): the editorial
        # compression pass cut building.md to ~4173 est tokens; the ceiling is
        # post-diet +10% and exists to LOCK THE DIET IN. The bump-history
        # narrative that used to live here is in git; the standing posture is
        # unchanged: prefer trimming over bumping, place canonical detail in
        # the file that owns the concept (discovery.md for rigor, review-cycle
        # for per-mode behavior) and keep building.md to condensed pointers.
        # Norm-lifecycle Chunk 5 (GOV-7Q4N) added the "A Norm Surfaced
        # Mid-Build" tripwire and PAID FOR IT in place: the ceiling held at 4600
        # (the plan's "stay green without raising budgets" success line), the
        # addition offset by compressing the Delegating and Decision-Research
        # guidance (canonical norm detail lives in docs/norms.md). The
        # retrieval-over-generation cycle (2026-07-17, MET-4V8Q) added the
        # cheap-check gate + one Common Trap and PAID FOR THEM the same way:
        # pointer form (detectors live in docs/principles.md #24) plus an
        # editorial pass over redundant phrasing. The wait-side cache-warm
        # guidance (2026-07-20, CRT-8Q6R) qualified "don't check on it" so it
        # cannot be read as "go idle", and PAID FOR IT the same way: the full
        # cadence detail lives in review-cycle.md (the file that owns per-mode
        # behavior), the Resolve-findings step dropped a why that CLAUDE.md
        # already carries, and the "Test corruption" trap went — it restated
        # "Tests never weaken" verbatim, closing sentence included. The
        # session-continuity work (2026-07-27) added chunk-close step 7 (write
        # the forward notes) and rewrote the one sentence describing the /clear
        # hook into the two-files-two-owners paragraph, and PAID FOR BOTH the
        # same way — the additions funded entirely by in-file redundancy rather
        # than by cutting content: three Common Traps that restated
        # rules stated earlier in this same file. Surviving coverage checked per
        # item, not assumed: "Silent requirement dropping" -> Working With
        # Specs' closing line + the digest + CLAUDE.md's principle roster;
        # "Pre-existing dismissal" -> the clean-baseline paragraph + the
        # injected digest; "Ignoring the Critic" -> the Blocking-findings paragraph two
        # sections down, and nowhere else — the thinnest of the three, and the
        # first to restore if the ceiling is ever raised. Plus trailing sentences
        # restating their own bullet (multi-hop, PBT, verification theater) and
        # prose fat in the intro, worktree, PR and Critic-timing paragraphs.
        # The trims took it to 4590 — one token BELOW the 4591 the addition
        # found — and the review then required step 7 to say what to write when
        # there is nothing to add (silence there fires the next session's
        # no-forward-note notice on every clean close). That cost 5, paid down
        # from 8 by compressing the same paragraph. 4595 now. Headroom is a few
        # words BY DESIGN; the next addition trims or relocates first.
        #
        # 4600 -> 4660 (2026-07-28, OWNER RULING) — the same ruling that raised
        # review-protocol.md 3530 -> 3620; full rationale lives there, in
        # TestCriticSkill.test_token_budget. What landed here is the builder's
        # half of the same rule: once zero blocking findings remain, FILE the
        # rest rather than fixing them, and re-run the gate instead of
        # inferring another round from stale output.
        #   SUPERSEDED 2026-07-29 — filing-as-default was reversed the same
        #   week it landed. building.md now reads "fix, accept, or file; never
        #   file by default" and review-cycle.md makes FILE the narrowest
        #   disposition, requiring a named trigger. Kept as the budget's
        #   accounting history, NOT as guidance: open items went 50 -> 180 in
        #   26 days under the rule this paragraph records. The two halves are
        # demand-side (here) and supply-side (the Critic's severity contract);
        # landing only one leaves the other half of the loop running, which is
        # why this file could not simply point at review-cycle.md.
        #
        # The trim-or-relocate rule above stands — overridden once, on the
        # record. Headroom is again a few words by design.
        #
        # 2026-07-29 (coverage-perf Chunk 03) added the never-ask-whether-to-
        # prepare-a-handoff prohibition and PAID FOR IT by the trim-or-relocate
        # rule, ending BELOW where it started: 4655 -> 4639, headroom 5 -> 21.
        # The rule landed as a clause on the existing chunk-close header; its
        # *rationale* (a round-trip, and a cold-cache context replay if the user
        # stepped away) went to session-digest.md, which is always injected, so
        # every session carries the why without building.md paying for it. The
        # funding was step 7's "nothing beyond the plan is a valid answer"
        # sentence, which the injected digest already states verbatim in its
        # forward-notes bullet — checked, not assumed. That makes this a dedup
        # rather than a cut; a reader who never opens building.md still gets the
        # guidance, from a surface they cannot skip.
        #
        # 2026-07-30 (record-mechanization Chunk 04) restated the coordinator
        # roster rule on two lines — it is no longer a file count but "a risk
        # surface, or 12+ judgeable files". Measured chain, every figure from
        # estimate_tokens rather than from the line above it:
        # 4657 at branch HEAD (headroom 3) -> 4672 on the first wording, OVER
        # -> 4669 after tightening both restatements -> 4648 after the trim
        # below. Headroom 3 -> 12 at that point; a later commit in the same
        # branch removed the restatements entirely (they were false for any
        # undeclared product), landing where LAST_MEASURED_TOKENS records.
        # **That table is the current reading — this narrative is history and
        # must not be read as a live figure.**
        #
        # Note for the next editor: the 2026-07-29 entry above ends at "4639,
        # headroom 21", and this change did NOT start there — Chunks 02-03 of
        # record-mechanization edited this file without updating that figure.
        # The first draft of this note inherited 4639 and its arithmetic did
        # not close. **Measure the file; do not read the previous entry's
        # ending number as your starting one.**
        # PAID FOR by the trim-or-relocate rule, not a raise. The
        # funding was the cache-warming clause of "The Critic takes time"
        # ("don't go silent either, or your prompt cache expires…"), which
        # `critic_consolidate._CACHE_WARM_DIRECTIVE` emits verbatim into the
        # consolidate no-op the caller reads WHILE waiting — checked, not
        # assumed. So the guidance now reaches the reader from the runtime at
        # the moment it applies, instead of from a guide read hours earlier;
        # a relocate whose destination already existed. 4669 -> 4648,
        # headroom 21 -> 12.
        #
        # 2026-07-31 replaced the one-line "Safe to /clear" close with the
        # three-line standing block (State / Next / Clear) and added the
        # batch-fix clause. Owner report, and it reshaped the requirement
        # twice: the rule already existed, but agents were burying a correct
        # signal mid-summary, and what a user wants after a 30-120 minute wait
        # is not a safety verdict alone — it is state, the next action and who
        # owns it, then the verdict. PAID FOR by the trim-or-relocate rule, not
        # a raise: 4652 -> 4725 on the first draft, then back under budget with
        # room to spare (the live figure is in LAST_MEASURED_TOKENS above; this
        # chain deliberately stops short of it, because an endpoint written here
        # is a hand-maintained copy of a machine-held number and goes stale on
        # the next edit — which is what happened twice in this branch alone).
        # Fundings, each a
        # relocate to a surface the reader cannot skip rather than a cut:
        # (1) the block's RATIONALE (why three lines, the three failure modes,
        # what counts as "outstanding") went to reflection.md, which owns the
        # work-cycle boundary, and to BOTH digests, which are always injected —
        # this file keeps the three line-labels and a pointer; (2) the
        # fix-strategy detail (which writes stay free mid-review) went to
        # `critic_consolidate._BATCH_FIX_DIRECTIVE`, which the runtime emits
        # with the findings themselves, so this file keeps one clause;
        # (3) "Two session files" dropped the rescued-hop gloss that
        # session-digest.md states, and step 7 its blind-append gloss that both
        # digests state — checked, not assumed; (4) the evidence-model paragraph
        # condensed to a pointer at review-cycle.md, the file that owns it;
        # (5) the Verify/Code bullet dropped a parenthetical re-listing the
        # ingest flags named one clause earlier, and Persist-plans a clause
        # that line 11 already states. Two trims were REVERTED because tests
        # pinned them as contracts (the seven goal names, "Never blind-append")
        # — the funding was found elsewhere rather than the tests weakened.
        # One correction rode along and cost nothing: the Blocking/Warnings
        # paragraph said warnings "should be addressed", which review-cycle.md
        # § "The review loop terminates" names BY FILE as the cause of the
        # round pump — it now says warnings and notes gate nothing and are
        # dispositioned. The next addition trims or relocates — read the live
        # headroom off LAST_MEASURED_TOKENS against the assertion below rather
        # than from this narrative, which is history. A figure written here was
        # stale twice in one branch (4655 survived a trim to 4646, and this line
        # said "Headroom 5" above an assertion permitting 14) — the same
        # copy-forward this table was built to end.
        #
        # 2026-08-04 added the builder-side inert-count rule, from ZERO headroom
        # (+0, the tightest this file has ever started an edit), and PAID FOR IT
        # by the trim-or-relocate rule. Two Common Traps went, each checked
        # rather than assumed:
        #   "Gold plating" -> CLAUDE.md's always-loaded principle roster carries
        #   P12 verbatim, the session digest's stance line says "do what was
        #   asked - no more", and "Working With Specs" closes on it. Covered on a
        #   surface the reader cannot skip, which this file's own history calls a
        #   dedup rather than a cut.
        #   "Verification theater / mock-as-implementation" -> the Verify step in
        #   THIS file, both halves: "Launch it, call it, inspect output" and
        #   "mocks are not verification". A trap restating a rule stated earlier
        #   in the same file is the exact class three earlier traps were cut as.
        # Plus three micro-relocates: the Critic's per-mode wall-clock figures
        # (review-cycle.md owns per-mode behavior and its table has a Target
        # wall-clock row -- this file now points), the gloss on "signals" (the
        # same sentence already routes the reader to review-protocol.md for
        # definitions), and "resets nothing and" in the compaction paragraph,
        # which the session paragraph four lines above states of `compact`.
        # NOT cut, and worth recording because it was the obvious candidate: the
        # `changes_referenced`/`changes_unjudged` parenthetical. doctor/SKILL.md
        # points HERE for the evidence shape, so this file is its referenced
        # home, not a copy of one.
        # RAISED 4660 -> 4810 (2026-08-05, #594). Paid for by ACCEPTING the cost,
        # not by offsetting it, and the attempt to offset is why: the two
        # delegation hazards added here (a worktree-isolated subagent reads HEAD,
        # so uncommitted governing artifacts are invisible; a shared-worktree
        # subagent shares your git INDEX, so a pathspec-less commit takes its
        # staged work) are +146 against 3 tokens of headroom. Three candidate
        # trims were tried and reverted: the standing block and the
        # warnings-gate-nothing rule are both pinned by tests in this class —
        # and `test_standing_block_is_on_every_surface_that_claims_it` records
        # that an EARLIER budget trim was already funded by relocating that
        # rule's rationale, so the redundancy a fresh trim would harvest has
        # been spent once already. One trim DID land and is counted in the +146
        # net: the Modes section lost its restatement of the mode-inference rule
        # that line ~100 already owns. Recorded because "three trims tried and
        # reverted" understated what was harvested, and a budget note that
        # misreports its own accounting is the thing this table exists to stop.
        # Relocating prose to another file was rejected
        # outright: it moves cost between files without reducing the total
        # footprint, which is the only number that matters.
        # What the +146 buys: the shared-index hazard has already produced a
        # real commit that deleted three test files under a message asserting no
        # test was deleted, and the HEAD-snapshot hazard put a subagent's
        # governing artifact in contradiction with its own prompt.
        # Retiring the derived views (2026-08-08) had to land two changes here
        # and cost +1 net against a 3-token headroom: the Status paragraph gained
        # the tick-AFTER-review ordering, which is newly load-bearing now that
        # ticking the last box is what disarms this hook's gates, and the
        # self-contained rule was re-derived onto "an id that CHANGES" since
        # plans are archived rather than deleted. Paid for by relocating both
        # rationales to the digests, which are always-injected where this file is
        # read on demand -- the same funding move the +146 above was taken on.
        # #648 (2026-08-12) landed NET ZERO and so moved no number here. Making
        # agent worktrees durable falsified this file's flat claim that
        # `prawduct-hook` refuses a worktree subagent's `.prawduct/` write --
        # true only on the harness's scratch branch now, and a dispatcher reads
        # this line as a backstop. The qualification was funded by two trims in
        # the same pass, both pure restatement: "See Modes below" (the Modes
        # section already back-references the inference rule it follows) and
        # "; never file by default" (the very next clause states the same rule
        # positively, and better). Recorded because a self-funded change is the
        # one most likely to go unlogged -- the ledger is for what was spent
        # AND what paid, not only for movements in the total.
        # The suite-total rule (2026-08-14) landed NET ZERO — the file measures
        # 4806 before and after, so LAST_MEASURED_TOKENS did not move. The
        # addition is one clause on the Same-decay paragraph, which already owns
        # "a count nothing reads is not worth writing"; it names the instance
        # that outlived the generic rule, since ten governed products maintained
        # a hand-kept test count for a year under it. **Its first draft was a
        # separate bullet on the Verify step at +180, and it also tripped
        # `test_no_suite_total_claims`' count-slot guard by quoting the shape it
        # was forbidding** — both facts recorded because the rewrite that fixed
        # the second is what made the first affordable. Paid for by four trims,
        # each pure restatement or a second example of a point already made: the
        # comments rule's second inline example, the Confidence Check's
        # restatement of what its own `discovery.md` pointer implies,
        # consolidate's parenthetical about the SubagentStop trigger, and two
        # words apiece in the research-presentation and cheap-check lines.
        tokens = estimate_tokens(self.content)
        # LOWERED 4730 -> 4718 (2026-08-19, #687): the work-cycle re-pricing was
        # funded by collapsing the Modes section's three pointers to one, and the
        # cut exceeded the addition. Ratcheted in the same commit.
        # LOWERED 4810 -> 4730 (2026-08-19), the same commit that cut the
        # standing-block restatement. A cut that leaves its own slack behind is
        # a cut the next edit spends silently: the drift pin only asks the next
        # editor to update the READING, while this ceiling is the hard gate, so
        # 90 tokens of unratcheted headroom disarms it for the next 89. Every
        # other budgeted file in this module sits within ~1-34 tokens of its
        # ceiling; this restores building.md to that posture and keeps the
        # trim-or-relocate rule meaning what it says.
        # RAISED 4718 -> 4800 (2026-08-21, owner ruling, scoped to the delegation
        # feature; the standing prefer-trimming-over-bumping posture is unchanged).
        # The rule landed net-zero FIRST and the raise bought only its reason. The
        # delegation guidance replaced "run the full suite before and after" — the
        # instruction that had every parallel delegate racing a whole suite on one
        # box — with a narrowest-run ceiling, paid for in place: ownership of the
        # combined run had been stated three times and is now stated once, plus an
        # editorial pass over the section. What would not fit at 4718 was the rule's
        # *why* — a runner whose workers die under N racing suites typically neither
        # re-queues their tests nor fails the run, so the box reports a green that
        # skipped a part nobody can name. That sentence is what stops "never the full
        # suite" from reading as a rigor discount and being softened later, which is
        # exactly how the wrong instruction survived: nothing said what it was for.
        # Requirements and the sweep behind them:
        # .prawduct/artifacts/delegation-and-verification-cost-discovery.md.
        # RATCHETED 4800 -> 4775 (2026-08-21) by the delegation chunk that
        # spent the raise. The pointer to `methodology/delegation.md` was funded
        # by a class the raise had never been audited for — the accounting is in
        # LAST_MEASURED_TOKENS above — and the cut came in 13 tokens over the
        # addition. Slack left behind is a loan the next edit collects silently
        # and green, so the ceiling moves with the cut.
        # RATCHETED AGAIN 4775 -> 4765 (2026-08-21, Chunk 04's cumulative, R-13).
        # RATCHETED AGAIN 4765 -> 4762 (2026-08-21): `closed-by:` left the
        # mutable-id exemption list, which the reading's entry narrates.
        # The `How:` line had to reach for the `Delegate verification` row a
        # project may already have ratified — without it a coordinator writes a
        # brief inventing a ceiling beside the owner's, which is the retyping the
        # whole feature exists to end. Paid in place and then some: the *why*
        # above stays, but its MECHANISM (workers dying under N racing suites,
        # not re-queued, not failing the run) is `delegation.md`'s canonical
        # unattributable-green bullet, restated here in full. What this file
        # needs is that it fails SILENTLY; what it does not need is the retelling.
        # Net -10, and the ceiling moves with it rather than banking the slack.
        # RATCHETED AGAIN 4762 -> 4757 (2026-08-21): the ad-hoc delegation
        # pointer landed and the section got smaller anyway, because the
        # pointer's table of contents went with it. The ceiling moves by the
        # same -5 rather than banking it — unratcheted slack is a loan the next
        # edit collects silently and green.
        assert tokens < 4757, f"building.md is ~{tokens} tokens, should be <4757"


# =============================================================================
# discovery.md, planning.md, reflection.md
# =============================================================================


class TestDelegationGuide:
    """`methodology/delegation.md` — the sixth `/prawduct:methodology` topic.

    The design is guidance, not mechanism (owner rulings, 2026-08-21;
    `.prawduct/artifacts/delegation-and-verification-cost-discovery.md` §6-7):
    prawduct states the goal and the considerations, and the coordinator — which
    can see the machine, the project and the moment's load — chooses how. The
    failure mode of a guidance feature is mechanism creeping back in as
    helpful-sounding prose, so the bar below is a NEGATIVE one as much as a
    positive one.
    """

    content = read_file("methodology/delegation.md")

    def _anti_pattern_bullets(self) -> list[str]:
        section = self.content.split("## Anti-patterns", 1)[1].split("\n## ", 1)[0]
        return [ln for ln in section.splitlines() if ln.startswith("- **")]

    def test_every_anti_pattern_carries_a_tell(self):
        """A tell is what makes an anti-pattern fire at the moment of the error.

        Without one it reads as true afterwards and changes nothing — the
        `learnings.md` preamble's "delivery is not descent". This is the check
        that keeps the section from decaying into a list of names, which is the
        cheapest way for it to look complete while doing nothing.
        """
        bullets = self._anti_pattern_bullets()
        assert len(bullets) >= 7, (
            f"the anti-pattern list has {len(bullets)} entries; the discovery "
            "sweep found seven, each observed in a real transcript"
        )
        tell_less = [b.split("**")[1] for b in bullets if "*Tell:*" not in b]
        assert not tell_less, (
            f"anti-pattern(s) with no tell: {tell_less}. A rule without one is "
            "read afterwards rather than fired at the moment of the error"
        )

    def test_the_guide_answers_whether_to_delegate_before_how(self):
        """R18. The guide as first written went straight to how — owner review,
        2026-08-21: it "leaps right into the weeds".

        The missing piece is a stated DEFAULT, and it is the one thing R3's
        questions-not-rules framing cannot supply: an agent with no default
        answers "should I delegate?" by not delegating, which is the measured
        0.34%. `building.md`'s permissive line was in place for that entire
        measurement, so a second permissive line is not the fix.

        Order is asserted, not just presence. A "when" section below the brief
        contract is met after the decision it governs has been made.
        """
        assert "## When to delegate" in self.content, "R18's section is gone"
        assert self.content.index("## When to delegate") < self.content.index(
            "## What a delegate is for"
        ), "the when-to-delegate default no longer leads the guide"
        lower = self.content.lower()
        assert "wall clock" in lower and "fight each other" in lower, (
            "the default posture no longer names its two terms (wall clock, and "
            "delegates not conflicting) — without both it reads as 'delegate more'"
        )
        assert "stay serial" in lower, (
            "the guide states a default with no cases that defeat it, which is "
            "how a default becomes a mandate"
        )
        assert "project-preferences.md" in self.content, (
            "the guide no longer routes to the project's own policy, so `off` "
            "and pre-approved have no way to reach the agent making the call"
        )

    def test_the_wall_clock_comparison_survives_plan_time(self):
        """The partition decision is drawn with chunk boundaries, before any
        brief exists — so a qualifier phrased in terms of briefs is unusable at
        the exact moment it applies. The first draft said "compare the plan as
        you will actually brief it", which is that defect.

        What makes it work is that the bound is a property of the CHUNK, and a
        chunk's deliverables are declared. Pinned on the plan-time form of the
        question, because that is the half a rewrite would drop.
        """
        section = self.content.split("## When to delegate", 1)[1].split("\n## ", 1)[0]
        assert "prove each chunk on its own" in section, (
            "the wall-clock qualifier no longer states its plan-time form, so it "
            "cannot be applied where the partition is actually decided"
        )
        assert "not scoped tightly enough" in section, (
            "the guide dropped what an unanswerable chunk MEANS — which is the "
            "qualifier's second yield and the more useful one"
        )

    def test_the_guide_states_the_goal_and_who_owns_integration(self):
        lower = self.content.lower()
        assert "nothing beyond it" in lower, "the goal sentence (R1) is gone"
        for owned in ("critic", "reflection", "merges"):
            assert owned in lower, (
                f"the coordinator's retained governance no longer names {owned!r} "
                "— a delegate that governs is one of the anti-patterns"
            )

    def test_the_brief_contract_is_qualitative_not_a_template(self):
        """R5: what must be SAID, not a template that says it.

        The tell of the wrong shape is a fill-in-the-blank form, so this pins
        both halves — the ceiling is named, and the guide disclaims the template.
        """
        assert "verification ceiling" in self.content
        assert "not a template" in self.content.lower(), (
            "the brief section no longer refuses to be a template, which is the "
            "one sentence stopping the next editor from writing one"
        )

    def test_the_guide_names_no_consumer_test_vocabulary(self):
        """§6 of the discovery artifact, and the easiest bar to violate while
        writing helpful prose: prawduct must not name a consumer's test command,
        runner, marker or tier. Consumers' regimes are not knowable in advance,
        and naming one is how a framework-defined taxonomy grows back.
        """
        lower = self.content.lower()
        forbidden = [
            "pytest", "vitest", "jest", "npm test", "maxworkers", "-n auto",
            "xdist", "testmon", "--maxprocesses", "makefile", "justfile",
        ]
        found = [f for f in forbidden if f in lower]
        assert not found, (
            f"delegation.md names a consumer's test toolchain: {found}. The "
            "guidance is qualitative; the project maps it to its own regime"
        )

    def test_the_unattributable_green_names_the_record_that_answers_it(self):
        """R16. Every other anti-pattern here is a tell and nothing more,
        because the remedy is a judgment the coordinator makes. This one is the
        exception: the record `.test-evidence.json` is prawduct's own artifact,
        it could not say a run was degraded, and no guidance to a coordinator
        fixes a record the framework owns (ruling 9). So the bullet carries the
        route, and this pins it TO THAT BULLET — the sentence is useless
        anywhere else in the file, because the reader it exists for has just
        caught themselves accepting a green they cannot attribute.

        The flag string is asserted against the hook that implements it, not
        just against the prose. A guide naming a flag nobody accepts is worse
        than one naming none.
        """
        bullet = next(
            (b for b in self._anti_pattern_bullets() if "unattributable" in b.lower()),
            None,
        )
        assert bullet is not None, "the unattributable-green anti-pattern is gone"
        assert "--degraded" in bullet, (
            "the anti-pattern states the tell and leaves the reader nowhere to "
            "go — the record can say a run was degraded, and this is the only "
            "place a coordinator catching themselves would learn it"
        )
        hook = read_file("bin/prawduct-hook")
        assert '"--degraded"' in hook, (
            "the guide names a flag the hook does not accept — the flag was "
            "renamed or removed without the guidance following it"
        )

    def test_the_guide_points_back_at_the_dispatch_mechanics(self):
        # The split is deliberate: judgment here, mechanics in building.md.
        # Restating either side is how the two drift apart.
        assert "/prawduct:methodology building" in self.content

    def test_building_md_reaches_the_guide(self):
        """A guide nothing reaches is not a deliverable.

        `building.md` § Delegating Work to Subagents is where a builder already
        is when the question arises, so the pointer has to be IN that section —
        a mention elsewhere in the file is met before there is a decision to
        make, or not at all.
        """
        building = read_file("methodology/building.md")
        section = building.split("## Delegating Work to Subagents", 1)[1]
        section = section.split("\n## ", 1)[0]
        assert "/prawduct:methodology delegation" in section, (
            "building.md's delegation section does not route to the guide"
        )


class TestAdHocDelegation:
    """`delegation.md` § Work no plan anticipated — the OTHER trigger.

    The parent feature governs a partition drawn at plan time. This one covers
    work that arrives when no plan anticipated it: a tangent raised mid-chunk,
    or work the agent was about to propose backlogging. Requirements R1-R9 and
    R13, `.prawduct/artifacts/adhoc-delegation-discovery.md` §4-5.

    **Why the bar here is placement and completeness rather than wording.** The
    sibling class above already holds the negative bar this section inherits
    unchanged (no consumer test vocabulary, no template, no mechanism creeping
    back as prose) — it reads the whole file, so nothing needs restating. What
    this class adds is what the ad-hoc trigger alone can get wrong: a rule that
    silently drops one of the four permitted requirements paths, an anti-pattern
    list that decays into names, or a section that states the decision without
    the debt that makes it different from plan-time delegation.
    """

    content = read_file("methodology/delegation.md")
    HEADING = "## Work no plan anticipated"

    def _section(self) -> str:
        assert self.HEADING in self.content, "the ad-hoc section is gone"
        return self.content.split(self.HEADING, 1)[1]

    def _anti_pattern_bullets(self) -> list[str]:
        section = self._section().split("### Anti-patterns, ad-hoc", 1)[1]
        # Bounded, though the list is last in the file today: an unbounded scan
        # silently absorbs the bullets of whatever section is appended next, and
        # the count assertion below would then pass on somebody else's list.
        section = section.split("\n## ", 1)[0]
        return [ln for ln in section.splitlines() if ln.startswith("- **")]

    def test_the_section_comes_after_the_contract_it_extends(self):
        """Placement is the substance, same as the sibling class's ordering
        check. The ad-hoc section says "everything above binds unchanged" — a
        reader who meets that claim BEFORE the brief contract and the
        verification ceiling has been handed a reference to prose they have not
        read, and the sentence that keeps this feature from restating the parent
        is exactly that reference.
        """
        assert self.content.index("## What a brief must say") < self.content.index(
            self.HEADING
        ), (
            "the ad-hoc section now precedes the brief contract it defers to, so "
            "its 'everything above binds unchanged' points at nothing yet"
        )

    def test_the_decision_is_three_way_and_the_policy_dial_is_reachable(self):
        """R1, R2. Two failure modes, one test.

        A section that offers only *delegate or not* turns every tangent into a
        binary and loses the answer that is usually right — backlog it. And a
        default with no dial is a mandate: `off` is a complete answer the owner
        can give, and it only reaches the agent if the guide names where it is
        written.
        """
        section = self._section()
        lower = section.lower()
        for option in ("do it now", "delegate it", "backlog it"):
            assert option in lower, (
                f"the three-way decision no longer offers {option!r} — a tangent "
                "with fewer than three answers is a decision the guide has "
                "already made for the reader"
            )
        assert "project-preferences.md" in section and "`off`" in section, (
            "the delegation-first default no longer routes to the project's own "
            "policy row, so a repo that has said `off` cannot be heard"
        )

    def test_the_requirements_bar_states_all_four_paths(self):
        """R4. The bar is absolute and the paths are a CLOSED list — the owner's
        ruling was four and no fifth. A guide that drops one path pushes the
        reader to invent it, and the path most easily dropped is the one that
        costs the coordinator nothing to skip: the delegate stopping and
        demanding requirements.
        """
        lower = self._section().lower()
        paths = {
            "stated in the brief": "state them in the brief",
            "an artifact referenced": "reference an artifact",
            "drafted by the delegate": "drafts them as its first deliverable",
            "the delegate refuses": "stops and demands them",
        }
        missing = [name for name, phrase in paths.items() if phrase not in lower]
        assert not missing, (
            f"the requirements bar no longer offers: {missing}. Four paths and "
            "no fifth was the ruling; a reader who cannot find their path "
            "invents one, which is the un-ratified requirement anti-pattern"
        )

    def test_drafted_requirements_come_back_proposed(self):
        """R5, and the sharp edge of path three. A delegate drafting
        requirements is doing discovery, and discovery output that arrives
        already implemented reads as ratified — the branch's existence standing
        in for approval. The word `proposed` is what stops that, so it is
        pinned rather than left to phrasing.
        """
        lower = self._section().lower()
        assert "proposed" in lower, (
            "drafted requirements no longer come back marked proposed, so a "
            "delegate's discovery arrives pre-ratified by the branch it sits on"
        )
        assert "ratif" in lower, (
            "the section names no ratification step, which leaves the debt "
            "path three creates with nobody owed it"
        )

    def test_the_integration_debt_and_who_cannot_pay_it_are_stated(self):
        """The reframe the whole feature rests on. A delegated tangent is not
        finished work, and the trigger that produced it — a context that is full
        — guarantees the agent that incurred the debt is not the one who pays.
        Without that sentence the section reads as a spawn mechanism, which is
        the design the discovery artifact rejected.
        """
        lower = self._section().lower()
        assert "integration debt" in lower, (
            "the section no longer names what comes back as a debt, so a "
            "delegated tangent reads as done"
        )
        assert "on disk" in lower and "held in memory" in lower, (
            "the section dropped WHY the debt has to be recorded — a debt "
            "living only in the dispatching agent's context evaporates at the "
            "next /clear, and that is the whole reason the record exists"
        )

    def test_the_brief_is_the_dispatch_record_at_a_named_path(self):
        """R8. The brief was always required; writing it INTO the worktree is
        what makes it the dispatch record, and what makes an abandoned worktree
        detectable from the filesystem without inventing state.

        The path is pinned because a probe depends on it. The negative half is
        pinned too: the discovery artifact rules out a registry, schema or lease
        (§6), and the prior design collapsed for proposing exactly those.
        """
        section = self._section()
        assert ".prawduct/.delegate-brief.md" in section, (
            "the brief has no named location, so nothing can find an abandoned "
            "delegate worktree without a registry — which is the design that "
            "was ruled out"
        )
        lower = section.lower()
        for refused in ("registry", "schema", "lease"):
            assert refused in lower, (
                f"the section no longer refuses a {refused}, which is the "
                "sentence stopping the next editor from adding one"
            )

    def test_dispatch_is_bounded_by_whether_this_session_can_reap_it(self):
        """R9. The worst outcome available is not a bad delegate — it is an
        unreapable one: compute spent, no result read, a worktree orphaned. The
        comparison that prevents it (expected runtime against remaining useful
        context) has to be in the guide, because nothing measures it for you.
        """
        lower = self._section().lower()
        assert "reap" in lower, "the section states no reapability bound"
        assert "backlog" in lower, (
            "the reapability bound names no alternative, so 'cannot reap' has "
            "no answer and the reader dispatches anyway"
        )
        assert "work-cycle boundary" in lower, (
            "reaping lost its timing — a reap that fires mid-flow is the "
            "focus-protecting mechanism breaking focus"
        )

    def test_every_ad_hoc_anti_pattern_carries_a_tell(self):
        """The same bar the parent list holds, applied to the list this feature
        adds. The sibling class's check splits on the FIRST `## Anti-patterns`
        and stops at the next `##`, so it never reaches these bullets — a fact
        worth stating, because a reader assuming coverage would leave the new
        list ungraded.
        """
        bullets = self._anti_pattern_bullets()
        assert len(bullets) >= 6, (
            f"the ad-hoc anti-pattern list has {len(bullets)} entries; the "
            "discovery sweep found six, each traced to a cost the design exists "
            "to hold down"
        )
        tell_less = [b.split("**")[1] for b in bullets if "*Tell:*" not in b]
        assert not tell_less, (
            f"ad-hoc anti-pattern(s) with no tell: {tell_less}. A rule without "
            "one is read afterwards rather than fired at the moment of the error"
        )

    def test_buildings_delegation_section_names_the_ad_hoc_trigger(self):
        """R13. `building.md` carries a pointer, not the doctrine — but a
        pointer that mentions only plan-time partition is met by a builder mid
        chunk and answers a question they are not asking.

        Asserted on the SECTION, not the file, for the sibling's reason: a
        mention elsewhere is met before there is a decision to make, or not at
        all.
        """
        building = read_file("methodology/building.md")
        section = building.split("## Delegating Work to Subagents", 1)[1]
        section = section.split("\n## ", 1)[0]
        lower = section.lower()
        assert "tangent" in lower or "backlog" in lower, (
            "building.md's delegation section frames the question as plan-time "
            "only, so work arriving mid-cycle never reaches the guide"
        )


class TestAdHocDelegationBacklogPrompt:
    """R14 — the ad-hoc trigger's second moment, in `skills/backlog/SKILL.md`.

    The guide above is where the judgment lives; nobody reads it who was not
    already about to delegate. This class covers the surface that catches the
    other half: an agent whose instinct was to *file* something, at the one
    stopping point that already fires for it.

    **Why this class lives beside the guide's and not in a backlog module.**
    The bar the prompt fires on is shared with the session digest's mid-chunk
    trigger, deliberately — two prompts stating one rule. A guard that reads
    only one of the two carriers cannot see them drift apart, and the only
    module that already reads both is this one.
    (`.prawduct/artifacts/adhoc-delegation-discovery.md` §5 R14, §8.3.)

    **The skill has two `add` procedures, and the first draft only pinned one.**
    `SKILL.md`'s `### add` is the markdown-backend path; once
    `backlog_service_repo` is set, `adapter-mode.md` carries its own end-to-end
    `### add` that *replaces* it — it re-states the dedup step for itself, which
    is the tell. So a prompt living only in `SKILL.md` never fires on the
    backend this repo actually runs. The fix keeps ONE statement of the offer
    and has the adapter path route to it; the assertions below therefore read
    three carriers, not two.

    **The bar here is placement and boundedness, not wording.** A prompt in the
    wrong step of `add` is decoration, and an *unbounded* one is worse than
    absent: §8.3 names defensive asking as this feature's live risk, and a
    prompt that fires on every `add` is a prompt people route around.
    """

    skill = read_file("skills/backlog/SKILL.md")
    adapter = read_file("skills/backlog/adapter-mode.md")
    digest = read_file("methodology/session-digest.md")

    #: The qualifier both carriers fire on. Shared on purpose — see the class
    #: docstring. Rewording it is legitimate; rewording it in ONE carrier is
    #: what this pins, so re-pin here and change both together.
    QUALIFIER = "ready to build"

    def _add_step(self) -> str:
        """The `add` subcommand's body, bounded at the next subcommand.

        Unbounded, the scan absorbs `pick`'s stage-aware routing, which names
        every term below for its own reasons — the assertions would then pass
        with the `add` path carrying nothing at all.
        """
        assert "### add\n" in self.skill, "the `add` subcommand is gone"
        body = self.skill.split("### add\n", 1)[1]
        return body.split("\n### ", 1)[0]

    def test_the_prompt_precedes_the_write_and_follows_the_dedup(self):
        """Placement is the substance (the reader test, not a word test).

        Two orderings make the prompt inert. Before the dedup, it offers to
        delegate work an existing item already tracks. After the append, the
        item exists and the decision has been made by default — which is the
        exact reflex R14 exists to interrupt.
        """
        step = self._add_step()
        dedup = step.lower().index("dedup first")
        write = step.index("append the item under `## Open`")
        offer = min(
            (step.index(o) for o in ("delegate it", "Delegate it") if o in step),
            default=-1,
        )
        assert offer != -1, (
            "`add` no longer offers to delegate, so the backlog instinct has "
            "two options again and the third is never said out loud"
        )
        assert dedup < offer < write, (
            "the delegation offer moved out of its slot in `add` (dedup at "
            f"{dedup}, offer at {offer}, append at {write}): before the dedup "
            "it proposes delegating work already tracked; after the append the "
            "item is filed and the reflex has already won"
        )

    def test_the_offer_is_three_way_and_names_the_delegate_cost(self):
        """R1 and R3 (Visible Costs), at the moment the offer is made.

        A two-way offer is not the doctrine's decision, and an offer with no
        price attached is the "delegation as a way to say yes" anti-pattern
        with the framework's own voice behind it. Outstanding branches are
        part of the price: a fifth is a different proposal from a first.
        """
        step = self._add_step()
        lower = step.lower()
        for option in ("do it now", "delegate it", "backlog it"):
            assert option in lower, (
                f"`add`'s offer no longer includes {option!r} — the three-way "
                "decision has collapsed back into a binary"
            )
        assert "integration debt" in lower, (
            "`add` offers a delegate without naming what comes back with it; a "
            "branch presented as finished work is the debt this feature exists "
            "to keep visible"
        )
        assert "await integration" in lower or "awaiting integration" in lower, (
            "`add`'s offer no longer discloses how many ad-hoc branches are "
            "already outstanding, so every proposal reads like the first one"
        )

    def test_the_prompt_is_bounded_by_the_bar_the_digest_fires_on(self):
        """§8.3's guard, and the one-rule-two-carriers property.

        The qualifier is what keeps this from becoming the defensive-asking
        failure. It is asserted on BOTH carriers because a bar reworded in one
        of them is two bars for one decision, which is the drift no single-file
        guard can see. Both must also state the quiet side explicitly — the
        `stage:` lifecycle in the skill, since "everything earlier files
        silently" is the half a reader acts on most often.
        """
        step = self._add_step()
        assert self.QUALIFIER in step.lower(), (
            f"`add`'s prompt no longer bounds itself to {self.QUALIFIER!r}, so "
            "it fires on idea-stage capture too — an unbounded prompt on the "
            "backlog's own front door is what trains people to route around it"
        )
        assert self.QUALIFIER in self.digest.lower(), (
            f"the digest's mid-chunk trigger no longer says {self.QUALIFIER!r}. "
            "It and `add`'s prompt state ONE bar on purpose; re-pin QUALIFIER "
            "and reword both, or the two triggers have quietly diverged"
        )
        assert "stage:" in step, (
            "`add`'s prompt no longer names the `stage:` lifecycle it reads to "
            "decide whether to fire, so nothing tells a reader which items stay "
            "silent"
        )

    def test_add_stamps_the_stage_its_own_prompt_reads(self):
        """The gap that made the qualifier inoperable, found while re-reading
        `add` as the agent who runs it.

        `add` filed every item stageless — the field was canonical, `import`
        inferred it, triage backfilled it, and the one path that creates items
        never set it. So the bar above had no input, and worse, an item the
        agent had just judged ready enough to offer *delegating* landed as one
        `pick` would refuse to present as buildable. The adapter's `file` op
        already took `--stage`; only this prose omitted it.
        """
        step = self._add_step()
        write = step.index("append the item under `## Open`")
        stamp = step.lower().find("stamp `stage:`")
        assert stamp > write, (
            "`add` no longer stamps `stage:` when it writes the item, so every "
            "item it files is born not-ready and the ready-to-build prompt "
            "above reads a field nothing sets"
        )
        assert "`--stage=`" in self.skill, (
            "`add` no longer accepts `--stage=`, so a machine caller cannot "
            "supply the one field that decides whether an item is buildable"
        )

    def test_the_prompt_carries_the_off_switch_inline(self):
        """R2, and the reason it is not left behind the pointer.

        This step INSTRUCTS. A reader of `add` who never opens the guide would
        otherwise propose delegation in a repo whose preferences disabled it —
        a skill overriding a project policy it did not read. The digest's
        neighbouring policy bullets name their governing row inline for the
        same reason.
        """
        step = self._add_step()
        assert "project-preferences.md" in step and "Delegation: off" in step, (
            "`add`'s prompt no longer carries the `Delegation: off` escape "
            "inline; a repo that declined delegation gets offered it anyway by "
            "the one path that never reads the guide"
        )

    def test_the_prompt_points_at_the_doctrine_instead_of_restating_it(self):
        """One home, N pointers — the architecture this whole feature is built
        on. A skill that grows its own copy of the judgment is the second home,
        and the copy is the one that goes stale, because the guide is what a
        reader of the *other* trigger is sent to.
        """
        step = self._add_step()
        assert "/prawduct:methodology delegation" in step, (
            "`add`'s prompt no longer routes to the guide that owns the "
            "judgment, so the offer is made with no way to reason about it"
        )
        # The four requirements paths and the anti-pattern list are the guide's.
        # Their tells are distinctive enough to catch a copy without catching a
        # legitimate one-line reference.
        for owned in ("no fifth", "four paths", "*Tell:*"):
            assert owned not in step, (
                f"`add` has started restating the guide's own material "
                f"({owned!r}); the pointer exists so this surface stays a "
                "trigger and the doctrine keeps one home"
            )

    def _adapter_add(self) -> str:
        """`adapter-mode.md`'s own `### add`, bounded at the next op."""
        assert "### add\n" in self.adapter, "adapter-mode's `add` op is gone"
        return self.adapter.split("### add\n", 1)[1].split("\n### ", 1)[0]

    def _adapter_offer(self) -> str:
        """The one paragraph of that op which hands over to `SKILL.md` step 2.

        Bounded to the paragraph rather than the section, and the reason is a
        mutation that stayed green: `ready to build` also appears in the
        neighbouring `--stage` paragraph, so a section-wide scan passed with the
        bar stripped out of the offer itself. A substring assertion is only as
        precise as the region it reads.
        """
        paras = [q for q in self._adapter_add().split("\n\n") if q.strip()]
        hits = [q for q in paras if "step 2" in q.lower() and "SKILL.md" in q]
        assert len(hits) == 1, (
            "`adapter-mode.md`'s `add` no longer has exactly one paragraph "
            f"handing over to `SKILL.md` step 2 (found {len(hits)}); either the "
            "handover is gone or it has been split into copies that can drift"
        )
        return hits[0]

    def test_the_offer_reaches_the_post_cutover_path_too(self):
        """The gap the first draft shipped: one prompt, two `add` procedures.

        `adapter-mode.md` replaces `SKILL.md`'s steps rather than adding to
        them, so an offer written only in `SKILL.md` is silent on every repo
        that has cut over to Issues — this one included. The routing is
        asserted rather than a second copy: the adapter names the offer, its
        bar, and where the statement lives, and `SKILL.md` says which of its
        steps survives the handover.
        """
        lower = self._adapter_offer().lower()
        assert self.QUALIFIER in lower, (
            f"the adapter's `add` no longer names the {self.QUALIFIER!r} bar, so "
            "a reader on that path cannot tell when the offer applies"
        )
        for option in ("do it now", "delegate it", "backlog it"):
            assert option in lower, (
                f"the adapter's `add` names the offer without {option!r}; a "
                "reader who never opens `SKILL.md` gets a pointer with no idea "
                "what it points at"
            )
        assert "step 2 is backend-independent" in self.skill.lower(), (
            "`SKILL.md`'s `add` no longer says which of its steps survives the "
            "handover to `adapter-mode.md`, so the next editor has no way to "
            "know the offer is not markdown-only"
        )

    def test_the_adapter_translates_the_two_markdown_specific_halves(self):
        """A pointer that hands over untranslatable instructions is worse than
        none — the reader follows it, finds `accepted-by:`, and invents a
        field. Both halves the offer depends on have a different spelling here:
        the stage it reads, and the in-flight mark it writes.
        """
        adapter_add = self._adapter_add()
        assert "--stage" in adapter_add and "stageless" in adapter_add.lower(), (
            "the adapter's `add` no longer tells the agent to infer and pass "
            "`--stage`, so items are filed stageless and the ready-to-build bar "
            "has nothing to read"
        )
        assert "in-progress" in adapter_add and "--working-branch" in adapter_add, (
            "the adapter's `add` no longer translates the in-flight mark; a "
            "reader following the pointer would try to write `accepted-by:`, "
            "which does not exist on this backend"
        )


class TestPlanTimePartition:
    """The plan-time half of the placement bet — `planning.md` and the template.

    `building.md` has said "when chunks are independent and parallelizable" the
    whole time and delegation ran at 0.34% (31,220 tool calls, 106 dispatches).
    The design's answer is placement, not machinery: the question arrives where
    the coordinator is ALREADY stopping — when chunk boundaries are drawn, and
    at a chunk close. This class holds the first of those two, plus the field
    the decision lands in.

    Requirements R6-R11,
    `.prawduct/artifacts/delegation-and-verification-cost-discovery.md` §4.5-4.6.
    """

    content = read_file("methodology/planning.md")

    HEADING = "### Partition: Serial or Delegated"

    def _section(self) -> str:
        assert self.HEADING in self.content, "the partition section is gone"
        return self.content.split(self.HEADING, 1)[1].split("\n### ", 1)[0]

    def test_the_question_fires_where_chunk_boundaries_are_drawn(self):
        """R6, plan-time half. Placement is the substance: a partition section
        parked outside Build Planning is read after the boundaries are drawn,
        which is after the decision it governs has been made.
        """
        build_planning = self.content.split("\n## Build Planning", 1)
        assert len(build_planning) == 2, "Build Planning section is gone"
        assert self.HEADING in build_planning[1].split("\n## ", 1)[0], (
            "the partition section left Build Planning — it now arrives after "
            "the chunk boundaries it is supposed to be drawn with"
        )

    def test_the_plan_time_form_of_the_question_is_the_chunk_not_the_brief(self):
        """R18's qualifier, which only works because the verification bound is a
        property of the CHUNK. At plan time no brief exists, so a question
        phrased in terms of briefs is unusable at the exact moment it fires.
        The second yield is the more useful one and is pinned with it: a chunk
        nobody can answer for is a finding about the chunk.
        """
        section = self._section()
        assert "prove this chunk on its own" in section, (
            "the partition prompt no longer asks the plan-time question, so it "
            "cannot be answered where the partition is actually decided"
        )
        assert "not scoped tightly enough" in section, (
            "dropped what an unanswerable chunk MEANS — a finding about the "
            "chunk, which is worth more than the estimate it replaces"
        )
        assert "/prawduct:methodology delegation" in section, (
            "the section no longer routes to the guide that owns the default, "
            "so planning.md would have to restate it and the two would drift"
        )

    def test_the_decision_is_recorded_either_way(self):
        """R7. "Serial, because X" is an answer; silence is not — and silence is
        what a plan produces when nothing asks for the line. The field is named
        so the record has somewhere to go rather than being encouraged.
        """
        section = self._section()
        assert "`partition:`" in section, (
            "the section no longer names the field the decision is recorded in"
        )
        assert "serial" in section.lower() and "unexamined" in section.lower(), (
            "the section no longer says WHICH case the field catches — serial "
            "is very often right, and a rule read as anti-serial gets ignored"
        )

    def test_the_disclosure_names_the_four_things_that_vary(self):
        """R8-R9. Disclosure is the cheap half of the asymmetry, so it is
        unconditional — and it carries what varies between plans, because a
        disclosure that could be copy-pasted from the last one is boilerplate.
        """
        section = self._section().lower()
        for owed in (
            "how many delegates",              # the count
            "isolated worktrees or the shared one",  # where they write
            "what each touches",               # the ownership boundary
            "what they will *not* do",         # what stays with the coordinator
        ):
            assert owed in section, (
                f"the disclosure no longer says {owed!r} — a delegation the "
                "user cannot picture is the surprise this rule exists to prevent"
            )
        assert "boilerplate" in section, (
            "the disclosure lost the rule that keeps it informative; a "
            "boilerplate disclosure satisfies the letter and is never read"
        )

    def test_the_ask_condition_is_a_closed_list(self):
        """R10, and the half that decides whether this costs or saves.

        An OPEN condition is worse than no condition: an agent resolving
        vagueness asks defensively every time, which is the round-trip the
        asymmetry exists to avoid. So the four reasons are enumerated, the
        prose says the list is closed, the three standing negatives are stated,
        and the section carries no hedge that would reopen it.
        """
        section = self._section()
        numbered = [
            ln for ln in section.splitlines()
            if re.match(r"^\d+\. ", ln.strip())
        ]
        assert len(numbered) == 4, (
            f"the ask-condition list has {len(numbered)} enumerated reasons; "
            "the discovery sweep named four, and a fifth added without a "
            "ruling reopens what the closure is for"
        )
        assert "closed" in section.lower(), (
            "the list no longer SAYS it is closed, so a reader treats it as "
            "examples and the defensive asking returns"
        )
        for negative in ("already approved", "pre-approved", "without further interruption"):
            assert negative in section, (
                f"standing negative {negative!r} is gone — each one names a "
                "case where asking is pure cost"
            )
        hedges = [
            h for h in ("such as", "for example", "e.g.", "among others",
                        "including but", "and so on", "etc.")
            if h in section.lower()
        ]
        assert not hedges, (
            f"the ask-condition section hedges: {hedges}. An enumerated list "
            "with an open tail is an open condition wearing a list's clothes"
        )
        assert "disclose and proceed" in section.lower(), (
            "the section no longer says what happens ABSENT a listed reason, "
            "which is the case that governs almost every plan"
        )

    def test_a_yes_can_be_made_durable(self):
        """R11. Without this the same question returns with every plan — the
        unnecessary-asking failure wearing a seatbelt — and the one moment the
        answer is fresh is the moment it is given.
        """
        section = self._section()
        assert "project-preferences.md" in section, (
            "an approval can no longer be promoted to a preference row, so the "
            "ask repeats every plan"
        )

    def test_the_section_names_no_consumer_test_vocabulary(self):
        """§6 of the discovery artifact, applied to the surface this chunk adds.

        Same bar as `TestDelegationGuide`, and it has to be repeated per surface
        rather than stated once: the failure mode of a guidance feature is
        mechanism creeping back in as helpful-sounding prose, and it creeps into
        whichever file is being written at the time.
        """
        lower = self._section().lower()
        forbidden = [
            "pytest", "vitest", "jest", "npm test", "maxworkers", "-n auto",
            "xdist", "testmon", "--maxprocesses", "makefile", "justfile",
        ]
        found = [f for f in forbidden if f in lower]
        assert not found, (
            f"the partition section names a consumer's test toolchain: {found}. "
            "The guidance is qualitative; the project maps it to its own regime"
        )

    def test_the_template_carries_the_field_and_it_round_trips(self):
        """R7's other half: a field nothing writes is a field nothing records.

        Read back through `_frontmatter_scalar` — the private helper is the
        point, not a shortcut. Its docstring says why it is the ONE value-level
        reader: two readers over the same block let a later fix to quoting or
        comment handling land on one key and not the other. A test that parsed
        the line itself would be exactly that second reader.

        `scope:` and `branch:` are asserted alongside it because the regression
        that matters is the neighbours: a new key is the cheapest way to break
        a block that was parsing fine.
        """
        from lib.plan_index import (  # noqa: PLC0415 - lib import is path-dependent
            _frontmatter_scalar,
            frontmatter_lines,
            parse_build_plan_frontmatter_branch,
            parse_build_plan_frontmatter_scope,
        )

        template = read_file("templates/build-plan.md")
        fm = frontmatter_lines(template)
        assert fm is not None, "the template's frontmatter no longer parses"

        present, value = _frontmatter_scalar(fm, "partition")
        assert present, "the template has no `partition:` field to fill in"
        assert value, (
            "`partition:` is present but empty — a blank field records nothing, "
            "and the whole point is that serial is an ANSWER"
        )
        assert "serial" in value.lower(), (
            "the filled example no longer demonstrates the serial case, which "
            "is the one a reader is most likely to be writing"
        )
        assert parse_build_plan_frontmatter_scope(template) == (True, "pantry-v1")
        assert parse_build_plan_frontmatter_branch(template) is None, (
            "the template's `branch:` is deliberately commented out — a "
            "placeholder branch is one no repo has"
        )

    def test_building_md_fires_the_question_at_a_chunk_close(self):
        """R6's SECOND placement, and the one `planning.md` cannot serve.

        A plan-time partition is a default, not a commitment: what the machine
        is actually doing is knowable only at dispatch. `building.md` is the
        only file a coordinator reads at a chunk close, so the trigger lives in
        its delegation section — the why stays in the guide it points at.
        """
        building = read_file("methodology/building.md")
        section = building.split("## Delegating Work to Subagents", 1)[1]
        section = section.split("\n## ", 1)[0]
        # PLACEMENT, not presence. The first draft put this inside the
        # `**Parallel chunks:**` bullet, which opens "launch independent chunks
        # as separate subagents" — so it reached only a coordinator ALREADY
        # fanning out. The reader R6's second placement exists for is the
        # opposite one: a plan that recorded `partition: serial` and whose load
        # at a chunk close now justifies delegating. That reader has no parallel
        # chunks and never reaches the bullet. A whole-section search cannot
        # tell the two apart, so the preamble is asserted explicitly.
        preamble = section.split("\n**How:**", 1)[0]
        assert "chunk close" in preamble, (
            "the chunk-close re-check left the section preamble — wherever it "
            "went, it now reaches only readers who are already delegating"
        )
        assert "`partition:`" in preamble, (
            "the chunk-close re-check no longer names the field it re-checks"
        )



class TestDelegationPolicyAndPromotion:
    """R12-R14 — where a project records what it decided, and how it gets there.

    §2.3 of the discovery artifact is the failure this chunk answers: the right
    rule was stated by the owner three times, in three sessions, and never became
    durable anywhere. So policy needs a home in the project's own words
    (`project-preferences.md`), and there has to be a one-step route from a
    practice the repo already runs to a row the next session reads
    (`/prawduct:doctor`).

    `.prawduct/artifacts/delegation-and-verification-cost-discovery.md` §4.7.
    """

    prefs = read_file("templates/project-preferences.md")
    doctor = read_file("skills/doctor/SKILL.md")

    ROWS = ("Delegation", "Delegate verification", "Delegation approval")

    #: The rows Health Check #18 may branch on. NOT `ROWS`: `Delegation
    #: approval` ships a default, so it is never unset, and including it makes
    #: every freshly scaffolded repo a mixed state — one filled row beside two
    #: blank ones — which reads as "recorded" and silently turns the check off
    #: for exactly the repos the template reaches.
    TRIGGER_ROWS = ("Delegation", "Delegate verification")

    def _workflow(self) -> str:
        """The Workflow section, bounded by whichever comes first — the next
        `## ` heading or the `---` rule.

        Bounding on `---` alone was wrong and mutation caught it: the rule sits
        several headings down, so a row relocated into a section of its own was
        still inside the slice and the placement assertion passed on prose it
        was meant to reject.
        """
        assert "\n## Workflow\n" in self.prefs, "the Workflow section is gone"
        rest = self.prefs.split("\n## Workflow\n", 1)[1]
        ends = [i for i in (rest.find("\n## "), rest.find("\n---")) if i != -1]
        return rest[:min(ends)] if ends else rest

    def _check(self) -> str:
        """The delegation-policy health check, anchored on its TITLE.

        Not on its number: checks renumber when one is removed, and an anchor
        that renumbers turns a passing guard into a silent one. The file itself
        cross-references by number, which is right for prose a reader is
        scanning; a test picking the same handle inherits the decay for nothing.
        """
        marker = "**Delegation policy unrecorded"
        assert marker in self.doctor, (
            "the delegation-policy health check is gone — nothing in doctor "
            "looks at delegation policy, so R13's detection has no surface"
        )
        return self.doctor.split(marker, 1)[1].split("\nClassify and report:", 1)[0]

    def _flow(self) -> str:
        heading = "## Delegation Policy Flow"
        assert heading in self.doctor, "the promotion flow is gone"
        return self.doctor.split(heading, 1)[1].split("\n## ", 1)[0]

    def test_the_three_policy_rows_are_in_the_workflow_section(self):
        """R12. Placement is the substance again: these are read by a session
        about to draw a plan, and the sections above Workflow are about how code
        is written. A row parked outside Workflow is read by nobody deciding a
        partition.
        """
        workflow = self._workflow()
        for row in self.ROWS:
            assert f"- **{row}**:" in workflow, (
                f"the `{row}` row left the Workflow section of "
                "project-preferences.md — R12's policy has nowhere to be written"
            )

    def test_off_is_a_complete_answer_and_says_so(self):
        """`off` stays supported and ceremony-free — §6 rules out mandating
        delegation, and a setting that is honoured but still nagged about is
        mandate with extra steps. Asserted on BOTH surfaces: the row has to
        offer it, and the check has to stop on it.
        """
        assert "`off`" in self._workflow(), (
            "the Delegation row no longer offers `off`, which §6 requires stay "
            "a supported setting"
        )
        check = self._check()
        assert "off` ends the check" in check or "off` ends this check" in check, (
            "Health Check #18 no longer stops on `off` — a repo that declined "
            "delegation now gets nudged about it, which is mandating it slowly"
        )

    def test_a_durable_yes_has_a_row_and_the_flow_lands_it_there(self):
        """R11/R14's other half. An approval that cannot be recorded is
        re-asked with every plan, which is `planning.md`'s ask wearing a
        seatbelt — so `pre-approved` needs a home AND a writer.
        """
        assert "pre-approved" in self._workflow(), (
            "no row records a durable approval, so the partition ask returns "
            "with every plan"
        )
        flow = self._flow()
        assert "pre-approved" in flow, (
            "the promotion flow no longer lands a durable yes anywhere"
        )
        assert "planning.md" in flow, (
            "the flow no longer says WHAT a durable yes stops — without the "
            "consequence, `pre-approved` reads as a label rather than a lever"
        )

    def test_the_proposal_is_derived_from_evidence_not_emitted_unconditionally(self):
        """The load-bearing property of R13, and the one that decides whether
        this check is worth its line.

        A proposal that fires in every repo carries no information; `norms.md`
        names the cost from this repo's own orphan-term hook. So the check must
        say the found-nothing case propose nothing, and must require the
        proposal to quote what the repo actually says about itself.
        """
        check = self._check()
        lower = check.lower()
        assert "found nothing" in lower and "propose nothing" in lower, (
            "Health Check #18 no longer says what to do when the repo encodes "
            "nothing — and the silent default is to invent a policy, which is "
            "the unconditional proposal this check is shaped to avoid"
        )
        assert "the repo's own names" in check, (
            "the proposal is no longer required to quote the repo's own "
            "vocabulary, so it can be assembled from prawduct's instead"
        )
        assert "naming the file each came from" in check, (
            "the proposal no longer has to cite where each item came from — an "
            "owner who cannot check the claim can only rubber-stamp it"
        )

    def test_the_check_grades_nothing(self):
        """A missing delegation policy is not a defect. Check #17 is the
        precedent and says why in its own words: grading optional advice makes
        it behave like the install contract. Here the stakes are higher —
        `Mandating delegation` is out of scope by ruling, and a check that
        reports `degraded` until you delegate has mandated it.
        """
        check = self._check()
        assert "a recommendation, not a conformance check" in check, (
            "Check #18 lost the label that keeps it out of the classification"
        )
        assert "never degrade the repo on this" in check.lower(), (
            "Check #18 can now degrade a repo for having no delegation policy, "
            "which mandates delegation through the grading system"
        )
        classify = self.doctor.split("\nClassify and report:", 1)[1].split("\n## ", 1)[0]
        assert "delegation" not in classify.lower(), (
            "the classification block now mentions delegation — whatever it "
            "says there, a grade is being assigned to an optional policy"
        )

    def test_the_flow_writes_rows_that_are_absent_not_only_blank(self):
        """The reach gap, and it is the whole difference between shipping this
        feature and shipping it to new repos only.

        `project-preferences.md` is scaffolded once at onboard and never
        regenerated, so the template rows added in this chunk reach a repo that
        onboards AFTER them and no other. Every already-onboarded repo has no
        such rows at all. This is Health Check #14's bug exactly — "the fix
        reached new onboards and nothing else" — and this flow is the only path
        by which an existing repo gets the rows.
        """
        flow = self._flow()
        lower = flow.lower()
        assert "absent" in lower, (
            "the flow no longer distinguishes a blank row from a missing one, "
            "so on every already-onboarded repo it has nothing to fill and "
            "silently does nothing"
        )
        assert "never regenerated" in lower or "scaffolded once" in lower, (
            "the flow no longer says WHY the rows are missing; without the "
            "reason the instruction reads as an edge case and gets trimmed"
        )

    def test_the_flow_is_one_step_and_one_confirmation(self):
        """R14 — one step, not an interview. The Norm Ratification Flow is the
        heavy path and it is the wrong shape here: three rows do not need
        surface-by-exception, and per-row prompting is the confirmation fatigue
        `security-model.md` § Direction calls a safety regression in itself.
        """
        flow = self._flow()
        assert "One confirmation covers the set" in flow, (
            "the flow no longer commits to a single confirmation, so it can "
            "grow back into the interview R14 exists to replace"
        )
        assert "per-row prompting is forbidden" in flow.lower(), (
            "per-row prompting is no longer refused — 'discouraged' has never "
            "held anywhere else in this file either"
        )

    def test_a_row_the_evidence_does_not_support_is_not_drafted(self):
        """The asymmetry that makes a proposal safe to accept: a blank row is
        honest, a guessed row is a decision the next session reads as the
        owner's.
        """
        flow = self._flow()
        assert "only the rows the evidence supports" in flow.lower(), (
            "the flow can now draft all three rows regardless of what it found, "
            "which puts prawduct's guess in the owner's voice"
        )

    def test_doctors_write_rule_survives_the_second_writing_flow(self):
        """This chunk gives doctor a SECOND flow that writes, and two sentences
        said there was one. The count was never the invariant — what the owner
        confirmed, into `.prawduct/` state, never product code, is. Pinned
        because a skill that quietly grows write paths is exactly what makes
        running prawduct an unsafe trust decision.
        """
        assert "one doctor flow that writes" not in self.doctor, (
            "the skill still claims a single write path while shipping two — "
            "a reader who believes it will not look for the second"
        )
        assert "Doctor's write rule" in self.doctor, (
            "the skill-level write rule is gone; without it the constraint "
            "lives only inside whichever flow happens to restate it"
        )
        rule = self.doctor.split("Doctor's write rule", 1)[1].split("\n\n", 1)[0]
        for owed in ("only what the owner confirmed", "never product code"):
            assert owed in rule, (
                f"the write rule dropped {owed!r} — the clause is the rule; "
                "what is left is a description of where doctor happens to write"
            )

    def test_the_enforcement_row_is_assigned_a_mechanism_and_stays_a_handle(self):
        """Two project norms meet here. Every preference is assigned a mechanism
        at birth or it becomes aspirational — and prose policy is
        judgment-required by construction, so it is `Critic` with `janitor` as
        its audit home (`advisory` needs a named mechanical hook, and there is
        none). And an index entry is a name, not a copy: the row points at the
        policy rather than restating it, or the two drift.
        """
        assert "takes `Critic`" in self.prefs, (
            "a filled delegation row no longer has an assigned mechanism, so it "
            "is a preference nothing grades"
        )
        assert "audit home `janitor`" in self.prefs, (
            "the audit home is unassigned — the rule for adding a preference "
            "requires both, and `advisory` would need a hook nobody built"
        )
        flow = self._flow()
        assert "a handle, not a second copy" in flow, (
            "the Enforcement row the flow writes may now restate the policy, "
            "which is the duplication `one home per fact` exists to refuse"
        )

    def test_the_shipped_enforcement_table_still_has_no_rows(self):
        """The reason no Enforcement row ships with the template, asserted here
        rather than only in `test_norm_probes.py`: a populated row is a HOMED
        NORM, so shipping one claims a norm registry every new product has
        ratified nothing into. This chunk's rows are written at ratification
        instead. Read the real template, per the rule this repo learned the hard
        way when hand-written fixtures agreed with each other and disagreed with
        the shipped file.
        """
        index = self.prefs.split("| Preference / norm | Mechanism |", 1)
        assert len(index) == 2, "the norm index table is gone"
        body = index[1].split("\n\n", 1)[0]
        data_rows = [
            ln for ln in body.splitlines()
            if ln.strip().startswith("|") and not re.match(r"^\|[\s:|-]+\|$", ln.strip())
        ]
        assert data_rows == [], (
            f"the norm index ships {len(data_rows)} populated row(s): {data_rows}. "
            "It must ship empty — a row here is a ratified norm, and the "
            "delegation rows get theirs from /prawduct:doctor, not from onboard"
        )

    def test_the_trigger_set_excludes_the_row_that_ships_filled(self):
        """The state the template actually ships is the one the check must not
        misread, and nothing else in this class can see a regression here.

        `Delegation approval` ships `ask-on-reason` **filled** while the other
        two ship `(unset — …)`. A check that reads all three together meets a
        mixed state on every newly scaffolded repo, and the reading that says
        "rows are filled, report recorded" turns the check off for precisely
        the population the template reaches. Every other assertion in this
        class — `off` ends it, found-nothing proposes nothing, it grades
        nothing — stays green through that regression, which is why this one
        exists.
        """
        check = self._check()
        for row in self.TRIGGER_ROWS:
            assert f"`{row}`" in check, (
                f"the check no longer reads the `{row}` row, so a policy the "
                "owner can state has no detector"
            )
        assert "not in the trigger set" in check, (
            "`Delegation approval` is back in the trigger set (or the exclusion "
            "stopped being stated) — it ships a default, so it is never unset, "
            "and reading it alongside the other two recreates the mixed state "
            "that reads as `recorded` and silently disables the check"
        )
        # The template is the other half of the claim: this test is only true
        # while `Delegation approval` really does ship filled. Read the real
        # file rather than trusting the sentence above it.
        workflow = self._workflow()
        assert "- **Delegation approval**: ask-on-reason (default:" in workflow, (
            "`Delegation approval` no longer ships filled — the exclusion above "
            "was justified by that fact, so if it now ships unset the reasoning "
            "has to be redone rather than the assertion relaxed"
        )
        for row in self.TRIGGER_ROWS:
            assert f"- **{row}**: (unset" in workflow, (
                f"`{row}` no longer ships unset, so it can no longer be the "
                "thing the check detects as missing"
            )

    def test_the_check_branches_per_row_not_on_the_set(self):
        """Branching collectively is what made the mixed state unreadable — a
        set is either "filled" or "unset" and a repo's rows are neither.
        """
        check = self._check()
        assert "branch per row rather than on the set" in check, (
            "the check went back to branching on the row set as a whole, so a "
            "repo with one row filled and one blank has no defined behaviour"
        )
        assert "a blank one beside it is still a candidate" in check, (
            "the check no longer says what happens to a blank row sitting next "
            "to a filled one, which is the mixed state itself"
        )

    def test_neither_surface_invents_a_test_vocabulary(self):
        """§6, applied to this chunk's two surfaces — and scoped differently for
        each, which is the point.

        The **template row** is guidance to a project about what to write, so it
        is held to the same bar as the guide: no runner, no tier, no command.
        The **doctor check** is the opposite job — it READS a consumer's repo,
        so naming the kinds of file it opens is its function, not a violation.
        What it may not do is arrive with a taxonomy of its own, so the ruled-out
        tier names are what is asserted there.
        """
        workflow = self._workflow().lower()
        runners = [
            r for r in ("pytest", "vitest", "jest", "npm test", "xdist",
                        "-n auto", "maxworkers", "testmon", "go test", "cargo test")
            if r in workflow
        ]
        assert not runners, (
            f"the delegation rows name a consumer's toolchain: {runners}. The "
            "project writes its own regime; prawduct does not supply one"
        )
        tiers = [
            t for t in ("`focused`", "`adjacent`", "`whole`", "`live`",
                        "contention class", "tier")
            if t in self._check().lower()
        ]
        assert not tiers, (
            f"Health Check #18 arrives with a framework tier vocabulary: "
            f"{tiers}. §6 rules those out by name — the proposal is assembled "
            "from what the repo says, not from a taxonomy prawduct brought"
        )

class TestOtherMethodology:
    def test_discovery_continuous(self):
        content = read_file("methodology/discovery.md")
        lower = content.lower()
        assert "continuous" in lower or "isn't a phase" in lower
        for char in ["human interface", "unattended", "programmatic interface",
                      "multiple party", "sensitive data"]:
            assert char in lower

    def test_planning_continuous(self):
        content = read_file("methodology/planning.md")
        lower = content.lower()
        assert "not a one-time phase" in lower or "isn't a one-time phase" in lower or "continuous" in lower
        assert "/prawduct:learnings" in content

    def test_discovery_operationalizes_coverage_expectation(self):
        # Recording structural characteristics is tied to the strategy-class
        # coverage chain — the methodology must not drift from the mechanism.
        content = read_file("methodology/discovery.md")
        lower = content.lower()
        assert "classification.structural" in content
        assert "coverage" in lower
        assert "coverage-scaffold" in content  # the one-act stub helper is named
        assert "not relevant" in lower  # a stub satisfies coverage (the decision)

    def test_planning_cross_references_coverage(self):
        content = read_file("methodology/planning.md")
        assert "strategy-artifact-missing" in content  # the ambient detector
        assert "coverage-scaffold" in content
        assert "/prawduct:doctor" in content

    def test_reflection_learning_lifecycle(self):
        content = read_file("methodology/reflection.md")
        assert "Learning Lifecycle" in content
        for stage in ["Provisional", "Confirmed", "Incorporated"]:
            assert stage in content
        assert "Recurrence escalation" in content or "recurrence escalation" in content
        assert "phase transition" not in content.lower()
        assert "learnings.md" in content
        assert "learnings-detail.md" in content


# =============================================================================
# Methodology prose hygiene (prose-diet Chunk 02)
# =============================================================================


class TestMethodologyProseHygiene:
    """Methodology guides teach the method; implementation narration belongs in
    git history. Two classes the prose-diet removed and this test keeps out:
    internal bug-ID citations (CRT-/STH-/TST-style tags meaningless to product
    builders) and set-theory glyphs weaker models parse unreliably. Scope is
    methodology/*.md only — skills/critic may keep operational IDs where a gate
    message names them (e.g. the CRT-4J8W chain)."""

    METHODOLOGY_GUIDES = [
        "methodology/building.md",
        "methodology/discovery.md",
        "methodology/planning.md",
        "methodology/reflection.md",
    ]

    @pytest.mark.parametrize("rel_path", METHODOLOGY_GUIDES)
    def test_no_bug_id_citations(self, rel_path: str):
        import re
        content = read_file(rel_path)
        hits = re.findall(r"\b(?:CRT|STH|TST|MET|STN|PRW|REL)-[0-9A-Z]{4}\b", content)
        assert not hits, f"{rel_path} carries internal bug-ID citations: {hits}"

    @pytest.mark.parametrize("rel_path", METHODOLOGY_GUIDES)
    def test_no_set_theory_glyphs(self, rel_path: str):
        content = read_file(rel_path)
        glyphs = [g for g in ("∪", "⊇", "⊆", "∈", "∅") if g in content]
        assert not glyphs, f"{rel_path} carries set-theory glyphs: {glyphs}"


# =============================================================================
# SKILL.md (Critic)
# =============================================================================


class TestCriticSkill:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("skills/critic/review-protocol.md")

    def test_an_inert_count_is_capped_at_note(self):
        """The `final`/`cumulative` half of the sink-side cap.

        Both protocol files carry it because both are read by a reviewer that
        can raise the finding, and neither reads the other. `TestCriticGoals13`
        holds the `chunk`/`verify-resolutions` half against the same helper, so
        the two copies cannot drift into disagreeing about the cap.
        """
        assert_inert_count_cap(self.content, "review-protocol.md")

    def test_a_site_naming_finding_must_answer_instance_or_class(self):
        """The rule and the slot are BOTH asserted, and so is where each sits.

        The defect this screens for was observed three times in one session on
        one branch: a finding named two commands, the builder fixed those two,
        and the class — every subcommand reading an option with `"--flag" in
        argv` — survived twice more, caught by a reviewer each time. The
        reviewers had the knowledge; nothing asked them to write it down, so the
        builder received a list of sites instead of a bounded class.

        **Placement is the substance, same as `assert_inert_count_cap`.** The
        rule goes in the severity legend because that is the lookup a reviewer
        performs while rating the finding in front of it; the slot goes in the
        finding template because a template is filled every time and a paragraph
        is re-read never. A version of this rule parked in its own section would
        satisfy any word-presence check and change no finding.

        **The three components are the rule, not decoration.** "Say instance or
        class" alone is a coin flip: the tell has to be mechanical (a
        one-sentence reason that does not name the site names a class), the
        members have to be located outside the diff (or the reviewer searches
        the delta and finds nothing), and the remedy has to be graded (or an
        enumeration of the named sites reads as a resolution, which is the
        observed defect exactly).
        """
        # Scoped to the legend SECTION, not to the file. Goal 5 carries a
        # `**Scope pressure-test:**` bullet — a different axis entirely — and a
        # file-wide scan for a bold "Scope" matches it, passes, and asserts
        # nothing about where this rule sits. Bounding the search by the section
        # that a reviewer actually reads while rating is the placement claim.
        section = self.content.split("## Severity Levels", 1)
        assert len(section) == 2, "the Severity Levels section is gone"
        legend = [
            ln for ln in section[1].split("\n## ", 1)[0].split("\n")
            if ln.lstrip().startswith("- **") and "Scope" in ln
        ]
        assert legend, (
            "review-protocol.md has no Scope entry in its severity legend — a "
            "reviewer picking a severity reads the legend, not the file"
        )
        rule = legend[0]
        for component, why in (
            ("one sentence", "without a mechanical tell the answer is a coin flip"),
            ("outside the diff", "else the reviewer searches the delta and clears it"),
            ("construction", "the only remedy that closes an unbounded class"),
            ("longer list", "naming the wrong remedy is what shipped the defect"),
        ):
            assert component in rule, (
                f"review-protocol.md's Scope rule dropped {component!r} — {why}"
            )

        template = self.content.split("## Output Format", 1)
        assert len(template) == 2, "the Output Format section is gone"
        finding_block = template[1].split("### Summary", 1)[0]
        assert "**Scope:**" in finding_block, (
            "the finding template has no **Scope:** slot, so the answer depends "
            "on the reviewer remembering a paragraph rather than filling a field"
        )
        assert "instance | class" in finding_block, (
            "the slot no longer offers the two answers, so it reads as free "
            "prose and collects a restatement of the finding title"
        )

    def test_signals_and_work_scaling(self):
        """Has signals section and work size/type guidance."""
        assert "Signals That Guide Your Review" in self.content
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content
        assert "Feature" in self.content
        assert "Bugfix" in self.content

    def test_goal_based_structure(self):
        """All seven goals present."""
        for goal in [
            "Nothing Is Broken", "Nothing Is Missing", "Nothing Is Unintended",
            "Everything Is Coherent", "Decisions Were Deliberate",
            "System Can Be Understood", "Design Is Sound",
        ]:
            assert goal in self.content

    def test_severity_and_output(self):
        """Severity levels, findings JSON, signals in output, goal key."""
        assert "BLOCKING" in self.content
        assert "WARNING" in self.content
        assert "NOTE" in self.content
        assert ".critic-findings.json" in self.content
        assert "### Signals" in self.content
        assert '"goal"' in self.content
        assert "independent" in self.content.lower()

    def test_quality_checks(self):
        """Security, documentation, design, coordinator pattern, preferences."""
        lower = self.content.lower()
        assert "injection" in lower
        assert "hardcoded secrets" in lower or "credentials" in lower
        assert "auth" in lower
        assert "documentation drift" in lower or "doc" in lower
        assert "encapsulation" in lower
        assert "coupling" in lower
        assert "coordinator" in lower
        assert "correctness reviewer" in lower
        assert "design reviewer" in lower
        assert "sustainability reviewer" in lower
        assert "project-preferences.md" in self.content
        assert "boundary-patterns.md" in self.content or "contract surface" in lower
        assert "alternatives considered" in lower

    def test_note_severity_semantics(self):
        """NOTE severity indicates genuine ambiguity."""
        for line in self.content.split("\n"):
            if line.startswith("- **NOTE**"):
                assert "ambiguous" in line.lower() or "unsure" in line.lower() or "genuinely" in line.lower()
                break

    def test_project_preferences_blocking(self):
        for line in self.content.split("\n"):
            if "project-preferences" in line.lower() and "blocking" in line.lower():
                break
        else:
            pytest.fail("project-preferences compliance should be BLOCKING")

    def test_readme_and_changelog_scope(self):
        """Critic checks README and scopes changelog review to current changeset.

        Both halves assert on the LINE carrying the rule, not on the file. The
        README half used to accept a bare "read the" anywhere in the file, which
        a `record_lint` sentence four sections away satisfied — so the check
        passed for a release in which the README rule had been merged away.

        `\\bread\\b` and not `"read" in line`: "README".lower() CONTAINS "read",
        so the substring form is entailed by the line naming README at all, and
        the guard reads as two conditions while being one. The word boundary is
        the whole assertion — it fails the moment an editor trims the reading
        instruction and leaves README sitting in the container list.
        """
        readme_line = next(
            (ln for ln in self.content.split("\n")
             if "README" in ln and re.search(r"\bread\b", ln.lower())),
            None,
        )
        assert readme_line, "no line tells the reviewer to read the project's README"
        scope_line = next(
            (ln for ln in self.content.split("\n")
             if "hangelog" in ln and ("history" in ln.lower() or "changeset" in ln.lower())),
            None,
        )
        assert scope_line, "no line scopes changelog review to the current changeset"

    def test_framework_specific_checks(self):
        assert "Framework-Specific Checks" in self.content
        assert "Generality" in self.content
        assert "Instruction Clarity" in self.content

    def test_token_budget(self):
        # The ceiling is the number this test asserts, and nothing else restates
        # it — a second copy here went stale at the raise below and shipped as
        # fact. This file is the `final` / `cumulative` payload, and the
        # prose-diet audit found it LEAN -- every goal bullet is a specific,
        # severity-mapped check, so there is no slack to reclaim by rewording.
        #
        # The standing rule, and the only part of this comment that decides
        # anything: THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP.
        # Raising the ceiling requires showing the framework is provably better
        # for the raise AND that no headroom remains in upleveling -- cutting
        # detail, dates, worked examples, and definitions the reader never
        # applies. The ceiling has been raised exactly once, by owner ruling,
        # for a rule that removes more review work than it costs; every other
        # addition has been funded in place.
        #
        # Three cuts that funded real additions, kept because they generalize:
        # a definition another file owns and the reader is told to open is not
        # worth restating here (Framework-Specific Checks now names the four
        # checks and points at framework-checks.md); a message the reviewer can
        # compose is not worth quoting verbatim; and history -- what a mechanism
        # USED to do -- is never worth carrying in an instruction payload.
        #
        # The trap that caught two editors is gone, and how it was retired is
        # the reusable part: Goal 4's `**Norms**` bullet read as a restatement of
        # the Normative-authority preamble but was the only LINE carrying both
        # "project-preferences" and "blocking", which
        # test_project_preferences_blocking contracts on. Both editors deleted
        # the duplicate and left the contract unhomed. It is now satisfied at the
        # rule's real home -- the preamble's BLOCKING clause names the
        # `project-preferences.md` row the finding cites -- so the duplicate
        # could go. A test pinning prose pins WHERE the rule lives; move the rule
        # before deleting its only carrier.
        #
        # 3599 -> 3611 (2026-08-02) -- the coordinator prompt template gained
        # the reviewer's FIRST-action liveness marker (`<ROLE>.started`), the
        # signal that stops "no partial yet" reading as reviewer death. Paid by
        # keeping the template line to the bare imperative; the rationale and
        # full instruction live in agents/critic-reviewer.md, which every
        # dispatched reviewer loads anyway. 9 tokens of headroom remain.
        #
        # 3611 -> 3612 (2026-08-04) -- the reviewer must relay consolidate's
        # `NEXT-ACTION:` line, the only carrier of the loop-termination rule
        # with a reader in the BUILDER role. Paid in full by the fourth application of
        # this comment's own first rule: the `resolutions` schema arm was
        # restated here for a mode that does not read this file, and where
        # emitting one FAILS consolidation -- so it was not merely redundant,
        # it invited a fail-closed error.
        #
        # 3612 -> 3589 (2026-08-04) -- the inert-count NOTE cap, funded with room
        # to spare by RELOCATING "Extending This Skill" to review-cycle.md. Fifth
        # application of this comment's own first rule, and the cleanest: that
        # section tells a MAINTAINER how to grow the Critic, and a reviewer never
        # extends the skill while reviewing. Maintainer-facing rationale inside a
        # per-review payload is the same class the goals-1-3.md budget comment
        # records cutting twice. Relocated, not deleted -- review-cycle.md is the
        # maintainer's companion file, which is the audience that section serves.
        #
        # 3589 -> 3611 (2026-08-05) -- a partial is now bound to the review that
        # dispatched it, not to the commit alone, so the coordinator template
        # carries the review id and the two rendezvous paths, and the single-pass
        # schema carries `dispatch_id`. Two trims paid part of it, both this
        # comment's own first rule: "the coordinator never resumes to aggregate"
        # was the parenthetical form of step 3's own heading, and "never compose
        # the paths yourself" is a REVIEWER instruction whose home is
        # agents/critic-reviewer.md.
        #
        # NOT paid in full, and deliberately so. The obvious remaining cut is
        # step 2's `model:` restatement -- and it must not be taken: that prose
        # is an emergency patch against reviewer-model tiering, pinned by
        # tests/preferences/test_reviewer_model_dispatch_prose.py, and buying
        # tokens by thinning a safety instruction is the wrong trade at any
        # exchange rate. 9 tokens of headroom remain, which is the intended
        # state, not an oversight: the next addition trims or relocates.
        #
        # 3611 -> 3612 (2026-08-07) -- the dormancy-era backlog gate here said
        # "when set, skip the walk", which the read-through cache made false: it
        # is the file every coordinator reviewer reads, so a sustainability
        # reviewer stopping here would skip the restored walk on every cut-over
        # product. Caught by the cumulative review, NOT by the suite -- the
        # tripwire asserted a substring of the old sentence that stayed true
        # while the clause around it inverted, so that assertion now pins the
        # direction of the gate instead of a prefix of it. The replacement was
        # drafted 10 tokens heavier and trimmed to +1 rather than bumped: the
        # backend condition and the query list live in cache-reads.md, and this
        # file needs only the route and the exit-6 rule. 8 tokens of headroom.
        # -19 on 2026-08-08: the derived-views bullet went with the views. No
        # replacement Status check was written HERE on purpose -- "Done when"
        # puts the Critic before the tick, so an unticked box during a chunk
        # review is the correct state and a check for it would false-positive on
        # every correctly-sequenced chunk. The PR reviewer's protocol carries it
        # instead, where the sequencing is finished.
        tokens = estimate_tokens(self.content)
        assert tokens < 3800, f"review-protocol.md is ~{tokens} tokens, should be <3800"


# =============================================================================
# goals-1-3.md — the chunk / verify-resolutions payload
# =============================================================================


class TestCriticGoals13:
    """`chunk` and `verify-resolutions` read this file INSTEAD of
    review-protocol.md + review-cycle.md.

    Why the split exists, measured over all 267 review facts carrying a
    duration: `chunk` missed its 1-2 min target in 30 of 30 recorded runs and
    `verify-resolutions` in 148 of 155, while `final` — loading the same
    protocol for more than twice the goals — sat INSIDE its target 85% of the
    time. The 96 smallest verify runs (<=5 changed files) still took a median
    240s, so the floor is not diff size; it is what gets loaded before a single
    changed line is read.
    """

    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("skills/critic/goals-1-3.md")
        self.protocol = read_file("skills/critic/review-protocol.md")

    def test_payload_at_most_half_the_full_protocol(self):
        """The chunk's acceptance criterion, pinned: measured payload for these
        modes drops by at least half.

        Compared against what these modes loaded BEFORE — review-protocol.md
        plus review-cycle.md, which the protocol pointed at eight times, so a
        reviewer following its pointers read both. SKILL.md is common to every
        mode and cancels out of the comparison."""
        cycle = read_file("skills/critic/review-cycle.md")
        before = estimate_tokens(self.protocol) + estimate_tokens(cycle)
        after = estimate_tokens(self.content)
        assert after * 2 <= before, (
            f"goals-1-3.md is ~{after} tokens against a ~{before}-token predecessor "
            f"({100 * after // before}%) — the split must at least halve the payload"
        )

    def test_token_budget(self):
        # The ceiling is the number this test asserts, and nothing else should
        # restate it. This file is the chunk / verify-resolutions payload and
        # orders its reader to open nothing else, so every pointer-chase it
        # would cause has to be inlined here instead -- which is why it is long,
        # and why the ceiling is the thing that governs rather than a line count.
        #
        # The standing rule, and the only part of this comment that decides
        # anything: THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP. A
        # check belonging to goals 1-3 is funded by compressing prose here,
        # never by dropping a check and never by raising the ceiling. Raising it
        # requires showing the framework is provably better for the raise AND
        # that no headroom is left in upleveling -- cutting detail, dates,
        # worked examples and definitions the reader never applies.
        #
        # Two cuts that paid for real additions, kept because they generalize:
        # a definition the machine already emits is not worth restating (the
        # reviewer is told to read `record_lint`'s own message and raise it), and
        # neither is a rationale explaining why this file is short, addressed to
        # a maintainer, inside the file whose purpose is minimum reviewer
        # payload.
        #
        # Standing trim candidates when the next editor needs room: the
        # normative-authority block, the longest passage that is not a
        # per-finding severity. (The chunk-`Type:` paragraph was the other
        # standing candidate and has now been spent — see below.)
        #
        # 1960 -> 1992 (2026-08-04) -- the reviewer must relay consolidate's
        # `NEXT-ACTION:` line, the only carrier of the loop-termination rule
        # with a reader in the BUILDER role: measured on a released version, one
        # consumer branch ran ten Critic rounds while the rule sat in two files
        # that branch never opened and in a directive that printed into seven
        # reviewer forks and zero builder contexts. Bought at 32 tokens rather
        # than ~160 by having CODE own the wording (`next_action_line`) and the
        # prose only order the relay -- the ceiling held without a bump, which
        # is this comment's standing rule.
        #
        # Paid twice, because the first version of the relay order sat where the
        # no-findings shorthand swallowed it -- dropping the carrier in exactly
        # the clean-pass case it exists for -- and making it unconditional cost
        # more than the order itself. Funded by compressing the chunk-`Type:`
        # paragraph, and by cutting a regrown instance of the very clause this
        # comment already records cutting once: a rationale addressed to a
        # MAINTAINER ("following a pointer at review time is the payload this
        # file exists to remove") inside the file whose purpose is minimum
        # reviewer payload.
        #
        # 1992 -> 1994 (2026-08-04) -- `verify-resolutions` rates new findings
        # BLOCKING only, so a re-review cannot manufacture the non-blocking work
        # that supplies the next round. Bought at 17 words for the same reason
        # the NEXT-ACTION relay was bought at 32: the worked instances live in
        # CODE (`VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`, printed at dispatch) and
        # this file carries only the rule. Funded by the standing candidate
        # above -- "Judge jurisdiction yourself; applicability is recorded,
        # never assumed", the most abstract sentence in the normative-authority
        # block and the only one that assigns no verdict -- plus the opening
        # "The complete instruction set for these two modes", which the H1 and
        # the self-contained clause on the same line both already say.
        #
        # It sits in the PREAMBLE, not in `## Severity`, and that is a budget
        # fact as much as a design one: Severity is below all three goal
        # sections, so the cheap placement would have been read after every
        # severity it governs -- paying 17 words for nothing. Ordering beats
        # presence (`test_the_protocol_carries_it_before_any_severity_is_assigned`).
        #
        # 1994 -> 1990 (same day, that chunk's review): the narrowing needed two
        # more clauses to be TRUE, and both were funded with room left over.
        # "record-lint entries included" (+2) resolves a specific-over-general
        # conflict -- the record-lint paragraph 20 lines below assigns WARNING
        # and NOTE imperatively, inside the one mode that records neither, and
        # this is the only protocol file that mode may open. "no observations"
        # (+2) stops the report contract's clean-pass line instructing "No
        # issues found" from a pass that demoted three observations, which
        # would have defeated the cost-bound the whole narrowing rests on.
        # PAID BY the `## Severity` BLOCKING legend's example list (-8):
        # "(broken tests, dropped requirements, security vulnerabilities,
        # unlisted deps)" restates four checks stated in full above it, in the
        # legend that DEFINES the severity -- the definition is "must fix before
        # proceeding" and the examples were a fourth restatement. Generalizes
        # with the two cuts recorded above: a legend that re-lists its own
        # section's contents is paying twice for one instruction.
        #
        # NOTE for the next editor: the two normative-authority blocks (here and
        # review-protocol.md) diverged for the first time with the trim above,
        # and nothing measures the seam. Mandatory in BOTH: every claim that
        # assigns a verdict (what binds, the departure -> BLOCKING/NOTE rule,
        # the stale-registry NOTE). Droppable HERE first: claims that assign
        # none. That is the rule the divergence was chosen under.
        #
        # 1990 -> 1994 (2026-08-04) -- the inert-count NOTE cap, plus dropping
        # `numeric counts` from the doc-only Goal 1 target list (a REMOVAL that
        # part-funds its own addition: the protocol stops asking for the finding
        # the cap then has to rate). Funded the rest by the `## Record your
        # judgment` sentence enumerating what `critic-consolidate` does (appends
        # the fact, regenerates the cache, anchors the ledger, clears the
        # marker) -- mechanism the reviewer neither verifies nor uses; the
        # actionable half ("run it yourself", "You write nothing else") stayed.
        #
        # **The trim tried FIRST was rejected by a guard, and that is the entry
        # worth reading.** The `graded chunk` record-lint entry spells out both
        # guess-paths (chunk inferred from build-plan Status, plan from
        # `active_build_plan`), twenty lines under this file's own instruction
        # that each entry "carries its own explanation - raise it, don't restate
        # it" -- so the surrounding prose appeared to argue for the cut, and it
        # was taken. `test_both_unchecked_shapes_are_graded_on_every_reviewer
        # _surface` in tests/test_record_lint.py failed, and its docstring names
        # this exact edit as the predicted casualty of a token-diet pass on this
        # file. Naming only ONE guess-path leaves the other readable as a clean
        # grade, which is how the assumption shape gets read as BLOCKING -- a
        # false blocker no `--chunk` can clear. The generalization is already in
        # learnings and now has a second instance: prose that reads as redundant
        # may be the only witness to a contract. Uplevel aggressively, then run
        # the suite; the guards decide what was redundant, not the reading.
        #
        # The cap sits in the `## Severity` NOTE legend and the narrowing does
        # NOT, which is not an inconsistency: the narrowing governs whether to
        # report at all, decided continuously while reading the goals, so it had
        # to precede them; a severity cap is a LOOKUP made once at write-up, and
        # the legend entry already owns its parent rule (record prose is a NOTE
        # because rating it WARNING manufactures the next round). Both placements
        # are asserted, not assumed -- `assert_inert_count_cap` requires the cap
        # INSIDE the legend entry, and the ordering pin keeps the narrowing above
        # goal 1.
        #
        # 1994 -> 1998 (2026-08-05) -- +4 across two passes: the
        # write path now points at the manifest's `rendezvous` entry instead of
        # a literal filename, and the schema gained `dispatch_id`. Paid by two
        # cuts of this comment's own kind, and the record here is the SECOND
        # attempt, kept because the first is the more useful lesson.
        #
        # The first attempt funded the addition by compressing the closing
        # "**Either way** your last line is consolidate's `NEXT-ACTION:` ... the
        # clean pass is where it matters most" down to one word. It looked like
        # de-duplication -- the relay order IS stated 30 lines above -- and it
        # was not: `test_goals_1_3_relay_survives_the_clean_pass_shorthand`
        # exists precisely because that sentence's job is to stop the
        # no-findings shorthand swallowing the relay, and it pins "Either way"
        # for that reason. THE LESSON: a sentence that restates a nearby rule in
        # the one place a reader is about to shortcut it is not a copy, it is
        # placement -- and a guard that names a phrase is naming a function.
        # Reverted in full.
        #
        # What paid instead: "read the manifest's `record_lint`, never re-derive
        # it" carried an imperative that the very next sentence carries WITH its
        # reason attached ("never recount what it counted: that is how a record
        # defect buys a review round"), and Goal 2's record-checks bullet ended
        # "raise them at the severities given there" -- a pointer to severities
        # the preamble had already assigned, eight lines up.
        #
        # The +4 is the cumulative review's R-9, paid at face value: the
        # `dispatch_id` / `resolutions[].review_id` disambiguation had landed in
        # agents/critic-reviewer.md, whose reader never writes `resolutions`.
        # THIS file is the only surface whose reader writes both, and they sat
        # eight lines apart with no cue. Three words in the schema example.
        #
        # 2265 -> 2272 (2026-09-02) -- the budget gate's two findings are graded
        # here because an ungraded record-lint check reaches a reviewer with no
        # verdict, which is how `learnings-entry-shape` shipped. Spent from
        # headroom, not paid: one clause, two check names and a severity, and
        # the rule behind it lives with the check in `review-cycle.md`.
        #
        # 2275 -> 2278 (2026-09-02) -- the `unchecked` rule became RELATIONAL
        # ("one step below the check it names") because it was an enumeration of
        # prefixes: every new BLOCKING check landed silently in the NOTE default,
        # so a check that could not run read as advisory -- the state the
        # `chunk-ref-missing unchecked` bullet exists to prevent. PAID FOR: the
        # four per-severity sentences merged into three (the merge seam had
        # graded `learnings-over-budget` BLOCKING twice in consecutive
        # sentences), and "Every other entry is a NOTE you must still state"
        # became "State every entry" -- the severity is now the rule's, not the
        # sentence's. Net +3, carrying one added check name.
        tokens = estimate_tokens(self.content)
        assert tokens < 2280, f"goals-1-3.md is ~{tokens} tokens, should be <2280"

    def test_is_self_contained(self):
        """No follow-the-pointer reads at review time — the acceptance criterion
        the line count was traded for. A reviewer in these modes reads this file
        and stops.

        The rule is about *directives*, not the strings: the file names the two
        protocol files precisely once, to forbid opening them, and a concrete
        prohibition instructs better than "don't read the others." So every line
        mentioning one must be that prohibition — which also means a future edit
        cannot smuggle a read-directive back in under the same filename."""
        pointers = ("review-protocol.md", "review-cycle.md", "framework-checks.md")
        offenders = [
            ln for ln in self.content.split("\n")
            if any(p in ln for p in pointers) and "do not open" not in ln
        ]
        assert not offenders, f"goals-1-3.md sends the reviewer elsewhere: {offenders}"

    def test_no_check_from_goals_1_3_was_dropped(self):
        """The distillation must lose no check. Every check in the protocol is
        severity-mapped, so a dropped one shows up as a missing verdict — this
        counts them rather than trusting the prose, and anchors the named checks
        that a recount alone would not catch.

        **This test is also what makes the duplication safe.** Goals 1-3 now
        exist in two files, which is real duplication and the obvious objection
        to the split. It is deliberate and policed rather than tolerated: the
        count invariant below is directional (`got >= src`), so adding a check
        to review-protocol.md's goals 1-3 without adding it here FAILS — the two
        copies cannot drift apart in the direction that matters, which is a
        check the chunk-mode reviewer never sees.

        The alternative considered and rejected: delete goals 1-3 from
        review-protocol.md and have `final`/`cumulative` read both files. That
        removes the duplication outright, but it re-splits the seven-goal
        payload across two files to fix a problem this test already closes, and
        the plan scopes `final`/`cumulative` to keep the full protocol. Revisit
        if the anchor list below starts needing maintenance every time a goal
        changes — that would mean the coupling had become the cost.
        """
        goals = self.protocol[
            self.protocol.index("### 1. Nothing Is Broken"):
            self.protocol.index("### 4. Everything Is Coherent")
        ]
        # Compare goal section to goal section. Counting the WHOLE of
        # goals-1-3.md against a protocol *slice* silently bought slack: the
        # inlined record-lint table, the normative-authority preamble and the
        # `## Severity` legend all carry verdicts of their own and have no
        # counterpart inside the slice, which left room for two unmirrored
        # WARNING checks — and WARNING is the modal severity here. Slack in a
        # drift detector is indistinguishable from the drift it is watching for.
        mine = self.content[
            self.content.index("## 1. Nothing Is Broken"):
            self.content.index("## Severity")
        ]
        for sev in ("BLOCKING", "WARNING", "NOTE"):
            src = goals.count(f"**{sev}**")
            got = mine.count(f"**{sev}**")
            assert got >= src, (
                f"goals-1-3.md's goal sections carry {got} {sev} verdicts against the "
                f"protocol's {src} — a check was added to one copy and not the other"
            )
        for anchor in (
            "test-status", "verify-coverage", "missing-coverage:", "pre-existing",
            "exact-match", "property-based", "injection", "hardcoded secrets",
            "trust boundaries", "explicitly descoped", "observable behavior",
            "Requirements Confidence", "record_lint", "project-preferences.md",
            "accessibility", "infrastructure_dependencies", "Foreign API",
            "Exposed API", "api_error_model_approach", "operator-verification",
            "unlisted dependencies", "undocumented architectural", "broad exception",
            "prawduct:allow", "Trivial because",
        ):
            assert anchor.lower() in self.content.lower(), f"goals-1-3.md dropped check anchor {anchor!r}"

    def test_carries_what_the_pointers_used_to_fetch(self):
        """Self-containment is only real if the inlined content is here. These
        are the four pointer-chases the old payload forced."""
        assert "chunk-ref-missing" in self.content and "governed-by-gap" in self.content
        assert "unchecked" in self.content            # record-lint's not-a-pass rule
        assert "designer-handoff" in self.content     # the chunk `Type:` selector
        assert "Normative authority" in self.content  # Goal 3's binding preamble
        assert '"resolutions"' in self.content        # the verify-resolutions schema arm

    def test_an_inert_count_is_capped_at_note(self):
        """The `chunk`/`verify-resolutions` half of the sink-side cap — same
        helper as `TestCriticSkill`, so the two copies cannot disagree."""
        assert_inert_count_cap(self.content, "goals-1-3.md")

    def test_the_doc_only_selector_no_longer_hunts_counts(self):
        """The source side: the protocol stopped ASKING for count findings.

        The doc-only row aimed Goal 1 at "prose and numeric counts", which made
        the contestable-count finding an *instruction* rather than an accident —
        roughly one finding in eleven across the measured window was
        count-shaped. Removing the direction is the cheaper half of R4 and the
        only half that acts before a reviewer has formed an opinion; the NOTE
        cap above only limits the damage once one has.

        Asserted on BOTH carriers because the row exists twice — here (what a
        chunk / verify-resolutions reviewer reads) and `review-cycle.md`'s
        selector table (what every other reader consults). Dropping it from one
        leaves the other instructing the opposite, which is worse than leaving
        both: a reviewer that finds the surviving copy has an explicit mandate.
        """
        doc_only = next(ln for ln in self.content.split("\n") if "`doc-only`:" in ln)
        assert "numeric counts" not in doc_only, (
            "goals-1-3.md still directs doc-only Goal 1 at counts"
        )
        assert "Goal 1 prose only" in doc_only
        row = next(
            ln for ln in read_file("skills/critic/review-cycle.md").split("\n")
            if ln.startswith("| `doc-only`")
        )
        assert "numeric counts" not in row, (
            "review-cycle.md's Per-Chunk Type selector still asks for counts — "
            "the two carriers now instruct opposite things"
        )

    def test_the_narrowing_covers_the_record_lint_entries_below_it(self):
        """A specific-over-general conflict inside one file, and the clause that
        resolves it is unpinned prose until this test exists.

        The record-lint paragraph twenty lines below the narrowing assigns
        **WARNING** and **NOTE** imperatively (`governed-by-gap` → WARNING, and
        so on). In `verify-resolutions` those severities are not findings at
        all, and this is the only protocol file that mode may open — so a
        reviewer reading the specific instruction after the general one records
        exactly the work the narrowing exists to stop. The clause has to be in
        the narrowing, and it has to come FIRST, for the same reason the
        narrowing itself sits in the preamble.
        """
        rule_at = self.content.find("only **BLOCKING** is a finding")
        assert rule_at != -1, "the narrowing is gone — see the ordering pin"
        clause_at = self.content.find("record-lint entries included")
        assert clause_at != -1, (
            "the narrowing no longer says it covers record-lint entries, and "
            "the record-lint paragraph below still assigns WARNING and NOTE "
            "imperatively inside the one mode that records neither"
        )
        assert rule_at < clause_at < self.content.index("`record_lint`"), (
            "the coverage clause moved out of the narrowing or below the "
            "record-lint paragraph it has to govern"
        )

    def test_the_clean_pass_shorthand_does_not_swallow_observations(self):
        """`verify-resolutions` demotes findings into prose, so "no findings" and
        "nothing to report" stopped being the same thing.

        The report contract's shorthand ("No issues found.") is keyed on the
        `findings` array. Left keyed there, a pass that demoted five
        observations reports silence — and the entire cost argument for the
        narrowing is that the builder still READS them. The first real use of
        the rule demoted five, so this is not hypothetical.
        """
        closing = self.content[self.content.index("Then report to the user"):]
        assert "No findings, no observations" in closing, (
            "the clean-pass shorthand is keyed on findings alone again — a pass "
            "that demoted observations now reports 'No issues found', which "
            "deletes the only channel the demotion leaves them"
        )

    def test_never_runs_anything(self):
        """The no-execution rule is load-bearing and must survive distillation."""
        lower = self.content.lower()
        assert "never run tests" in lower or "do not run tests" in lower

    def test_does_not_carry_the_final_only_payload(self):
        """The split is only worth its cost if the seven-goal content is gone —
        a copy that regrew into the full protocol would pass every test above."""
        for absent in (
            "Everything Is Coherent", "Decisions Were Deliberate",
            "The Design Is Sound", "Coordinator Pattern",
            "Framework-Specific Checks", "Backlog Reconciliation",
        ):
            assert absent not in self.content, f"goals-1-3.md regrew {absent!r} — that is final-mode payload"


class TestCriticSkillRoutesByMode:
    """SKILL.md step 2 selects the payload; without this the new file exists and
    nothing reads it."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("skills/critic/SKILL.md")

    def test_token_budget(self):
        # Ceiling 3450 against a reading of 3445 (`estimate_tokens`, recorded in
        # LAST_MEASURED_TOKENS above): four tokens of slack under the strict
        # `<`, and deliberately tighter than any sibling ceiling in this module.
        # This is the one payload EVERY mode loads -- the skill body a reviewer
        # reads before step 1 has told it which protocol file it needs -- so a
        # token added here is paid by the fast `chunk` path whose whole reason
        # for existing is to not read the seven-goal protocol, and paid again by
        # each coordinator reviewer on a `final`/`cumulative`. Unconditional
        # payload is therefore the most expensive place in the skill to grow and
        # the worst available relocation target, not an exempt one; the ceiling
        # is what stops it being the cheap destination instead. Same standing
        # rule as every other budget comment here: THE NEXT ADDITION TRIMS OR
        # RELOCATES, IT DOES NOT BUMP.
        #
        # It lives in this class because this class owns SKILL.md; the mode
        # routing it asserts around it is the reason the ceiling is this tight.
        tokens = estimate_tokens(self.content)
        assert tokens < 3450, f"SKILL.md is ~{tokens} tokens, should be <3450"

    def test_step_2_names_both_payloads(self):
        line = next(ln for ln in self.content.split("\n") if ln.startswith("2. "))
        assert "goals-1-3.md" in line
        assert "review-protocol.md" in line
        for mode in ("chunk", "verify-resolutions", "final", "cumulative"):
            assert mode in line, f"SKILL step 2 does not route {mode}"

    def test_header_scopes_every_final_only_file_it_names(self):
        """The header is the FIRST instruction in the skill body, so it beats
        step 2 on reading order — an agent obeys it before it knows its mode.

        It used to say `review-protocol.md` "(read this first)" and not mention
        `goals-1-3.md` at all, so a chunk-mode review loaded the entire
        10,519-token predecessor payload before step 2 told it not to. The split
        was correct on disk and inert on the instruction path, and every
        size-measuring guardrail stayed green through it.

        Asserting the class, not that one instance: pinning the literal string
        "read this first" would pass the moment someone reworded the directive.
        Every header bullet naming a final-only file must scope itself to the
        modes that read it, which no rewording escapes."""
        header = self.content.split("## Structural Constraints", 1)[0]
        assert "goals-1-3.md" in header, "the header omits the fast-mode protocol file"
        assert "after step 1" in header.lower() or "only after" in header.lower(), (
            "the header must state that the protocol read follows mode resolution"
        )
        # The file-list BULLETS are the routing; the surrounding prose is not
        # (one line names `review-cycle.md` as an example of resolving a bare
        # sibling path, which is a rule about where files live, not an
        # instruction to read one).
        unscoped = [
            ln.strip()[:110] for ln in header.split("\n")
            if ln.lstrip().startswith("- ")
            and any(f in ln for f in ("review-protocol.md", "review-cycle.md", "framework-checks.md"))
            and not any(m in ln for m in ("final", "cumulative"))
        ]
        assert not unscoped, f"header lists a final-only file without scoping it: {unscoped}"

    def test_the_single_pass_bullet_never_cites_a_final_only_file(self):
        """The single-pass roster bullet is the fast path's write-up
        instruction, and everything it needs is in goals-1-3.md.

        This is its own test because a line-level check cannot police it: the
        bullet permanently contains the words "small `final`/`cumulative`" (it
        describes when small final reviews go single-pass), so any rule that
        excuses a line for mentioning `final` excuses THIS line unconditionally
        — and it is the exact line that carried the `(schema: review-protocol.md
        …)` pointer a blocking round was spent removing. Zero citations here."""
        bullet = next(
            ln for ln in self.content.split("\n")
            if 'Roster `["reviewer"]`' in ln
        )
        for cited in ("review-protocol.md", "review-cycle.md"):
            assert cited not in bullet, (
                f"the single-pass bullet cites {cited} — that read is the payload "
                f"the split removed, and goals-1-3.md already carries it"
            )

    def test_fast_path_steps_never_send_the_reviewer_to_a_final_only_file(self):
        """Steps 1-7 run in EVERY mode, so an unqualified citation there is a
        read a chunk-mode reviewer will make.

        Judged per *clause*, not per line: a qualifier anywhere on a long line
        used to excuse a citation elsewhere on it.

        **No line-level exemptions.** The coordinator bullet used to be skipped
        wholesale — legitimate in itself (that roster only exists in
        `final`/`cumulative`) but an escape hatch excusing anything later
        appended to that line, which is the same shape as the defect this test
        was written to catch. Its prose now qualifies its own citation
        (`the final/cumulative "Coordinator Pattern" in review-protocol.md`), so
        the skip was deleted rather than documented."""
        steps = self.content.split("## Getting Started", 1)[1]
        offenders = []
        for ln in steps.split("\n"):
            for clause in re.split(r"(?<=\.)\s|[;()]", ln):
                if "review-protocol.md" not in clause and "review-cycle.md" not in clause:
                    continue
                if any(q in clause for q in ("final", "cumulative", "goals-1-3.md")):
                    continue
                offenders.append(clause.strip()[:110])
        assert not offenders, f"fast-path steps cite a final-only file unqualified: {offenders}"

    def test_the_per_mode_scope_line_carries_the_severity_narrowing(self):
        """SKILL.md is the FIRST file the fork reads, and its per-mode scope
        line exists so that no mode has to open `review-cycle.md` for scope.
        The narrowing IS scope, so a summary omitting it is an incomplete
        description of the mode — and this is the only carrier of the rule with
        no other guard.

        Without this pin the next token trim of that already-long line removes
        the narrowing from the fork's first read with CI green, which is the
        plan's own Verification Strategy applied to itself: *prose changes to a
        fork-read protocol are pinned by test, because nothing else can observe
        them.*
        """
        line = next(
            (ln for ln in self.content.split("\n") if "Per-mode scope" in ln), None
        )
        assert line is not None, "SKILL.md no longer summarises per-mode scope"
        assert "BLOCKING only" in line, (
            "SKILL.md's per-mode scope line no longer states that "
            "verify-resolutions rates new findings BLOCKING only — the fork "
            "reads this before its protocol, so the omission is read as "
            "'this mode rates everything'"
        )

    def test_review_cycle_table_records_the_routing(self):
        """`review-cycle.md` owns per-mode behavior, so the routing is recorded
        there too — a reader who checks the mode table must not learn a
        different answer from the one SKILL.md acts on."""
        cycle = read_file("skills/critic/review-cycle.md")
        row = next((ln for ln in cycle.split("\n") if "Protocol read" in ln), None)
        assert row is not None, "review-cycle.md's per-mode table has no protocol-read row"
        assert row.count("goals-1-3.md") == 2, "chunk and verify-resolutions both read goals-1-3.md"
        assert row.count("review-protocol.md") == 2, "final and cumulative both read review-protocol.md"


# =============================================================================
# review-cycle.md
# =============================================================================


class TestReviewCycle:
    def test_token_budget(self):
        # Ceiling 9600. It exists because the absence of one was being SPENT:
        # `review-protocol.md`'s relocated "Extending This Skill" and the
        # verify-narrowing argument both landed here justified by "review-cycle
        # carries no ceiling", while the ceiling test one file over passed on a
        # token DROP. Relocation across an unguarded boundary is a bump wearing
        # a trim's clothing -- the P0 wall-clock norm is about the payload a
        # reviewer loads, and `SKILL.md` lists this file as part of it (
        # `test_payload_at_most_half_the_full_protocol` counts it too).
        #
        # The ceiling is deliberately loose relative to its siblings: this file
        # is ~2.6x review-protocol.md and a tight bound would force an immediate
        # diet that nothing has argued for. It exists to make the NEXT growth a
        # decision, not to relitigate the current size. Same standing rule as
        # every other budget comment here: THE NEXT ADDITION TRIMS OR RELOCATES,
        # IT DOES NOT BUMP.
        #
        # A ceiling binds ONE file, so nothing written here can be true of the
        # skill as a whole -- and "'relocate to the unbudgeted file' is no
        # longer an available move anywhere in this skill" is the sentence this
        # comment must never carry. That is a claim about a SET THAT GROWS: the
        # next payload file added falsifies it silently while it goes on reading
        # as settled fact to the maintainer deciding where to put prose, and a
        # third ceiling would only make it true until the sixth file.
        #
        # State the mechanism instead, which survives the set growing: every
        # accounted payload file has a reading in `LAST_MEASURED_TOKENS`, and
        # `test_recorded_token_count_matches_the_file` turns an undeclared
        # change red wherever it lands -- so a relocation out of this file has
        # to be declared at its destination. Whether that destination also
        # carries a CEILING is a separate per-file decision, stated at that
        # file's own assertion and nowhere else.
        #
        # 9471 -> 9532 (2026-08-05) -- the manifest key list gained `rendezvous`
        # and the consolidation contract gained the `dispatch_id` binding. Not
        # paid by a trim, and the reason is this file's own role: it is the
        # maintainer's companion and the one home for the manifest's key list,
        # so a key that exists and is not listed here has no home at all. The
        # additions are two clauses on lines that already existed. The last +2
        # is the cumulative review's R-13: the entry called `rendezvous` "the
        # one home for those filenames", which it is not -- `partial_path` and
        # `started_path` own the shape and every reader recomputes from them.
        # A key list that misdescribes what it records is worse than a long one.
        #
        # 9532 -> 9586 (2026-08-06) -- the "close coverage" block now answers the
        # question it raises: dispatch itself refuses a round the gate would not
        # require (exit 3), so a builder standing at that decision asks instead
        # of reasoning about judgeability. This is the decision point the
        # measured waste came from -- 62 of 492 reviews spent on free intervals
        # -- so the file that owns the close-coverage rule is where it belongs.
        # PAID FOR, not spent: the "do not retry in another mode" clause came
        # back out, because SKILL.md's exit-3 step already owns it and that is
        # the surface that reads the exit code. Net of both, +54.
        #
        # 9586 -> 9596 (2026-08-06) -- the cumulative's R-11: the exit-3 answer
        # had been hung on the gate's FAILING branch, the one branch where a
        # refusal cannot fire (an `uncovered` verdict entails the span is not
        # free) -- the same false implication this bundle withdrew a sibling
        # deliverable for. Moved to the post-fix `verify-resolutions` decision,
        # where free deltas genuinely occur, and the correction itself now rides
        # the existing "if it passes" sentence rather than adding one. +10.
        #
        # 9596 -> 9578 (2026-08-07) -- Backlog Reconciliation came off the frozen
        # markdown file and onto the backlog cache, and the restored walk is
        # SMALLER than the dormancy notice it replaced. What paid for it was a
        # RELOCATION, not a trim: the query mechanics the walk needs are the same
        # ones the PR reviewer and the janitor need, so stating them here would
        # have been the first of three copies -- and drift between exactly those
        # three copies is what `tests/test_cutover_prose_coherence.py` exists to
        # catch. They live in `skills/backlog/cache-reads.md` and this file routes
        # to it, keeping only what is specific to this walk: which queries it
        # asks, and the NOTE it emits when the store cannot answer. The addition
        # that did land is the per-check yield line the proportionality norm
        # requires of a re-added control. Net -18.
        #
        # +14 (2026-08-07): C-B1's trigger was WRONG, not merely terse -- it read
        # "a new item in the diff", and post-cutover a new item is an Issue that
        # never appears in a diff, so the check could not fire on the backend the
        # walk was restored for. `created-since` was already built and listed in
        # the walk's query set with nothing reaching it. Paid for by stating the
        # reason in one clause rather than the paragraph the first draft carried:
        # a correction to an instruction that cannot fire is not spending the
        # ceiling, but the explanation of it would have been.
        #
        # 9591 -> 9599 (2026-09-02) -- the budget gate's two rows. An ungraded
        # record-lint check reaches a reviewer with no verdict, which is how
        # `learnings-entry-shape` shipped, so a row is not optional. PAID FOR:
        # the standalone line-scoping sentence named "the suite-total tripwire"
        # and read as a property of the whole pass -- which the budget check,
        # reading file sizes on a diff that changed no record, contradicts. It
        # folded into the two rows that own the scope, where a reader meets it
        # beside the check instead of as a claim two of six rows deny. Net +8.
        #
        # 9590 -> 9591 (2026-09-02) -- the same relational `unchecked` rule, plus
        # the `learnings-area-dead` row. PAID FOR three ways, all of them things
        # this change made wrong or spare: the record set's "(markdown; the
        # archive excluded)" gloss had been wrong since YAML under `.prawduct/`
        # joined the set and is wrong a second way now that two rows read
        # neither; the `no-subject` bullet's "there is no deliverable set to
        # grade" restates "deliberately plan-less" one clause earlier; and the
        # retired-checks example named two checks that no longer exist, which is
        # history a reviewer never acts on -- the rule it illustrated stays, and
        # `record_lint.py` carries the instance where a re-adding author reads.
        # Net +5.
        content = read_file("skills/critic/review-cycle.md")
        tokens = estimate_tokens(content)
        assert tokens < 9600, f"review-cycle.md is ~{tokens} tokens, should be <9600"

    def test_framework_checks_token_budget(self):
        # Ceiling 1150. This file is `final`/`cumulative` payload: SKILL.md's
        # header bullets route those reviewers here for the four
        # Framework-Specific Check definitions, and `review-protocol.md` names
        # the file rather than restating them. A relocation is only honest while
        # its destination is bounded, and this ceiling is what bounds this one.
        # It says nothing about any other file -- which payload files carry a
        # ceiling is stated at each one's own assertion, because no comment here
        # can speak for a set that grows.
        #
        # Small file, so the ceiling is proportionally looser than its siblings'
        # few-token headroom: the point is that the NEXT addition is a decision,
        # not to force a diet on 87 lines nothing has argued are too many. Same
        # standing rule: THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP.
        content = read_file("skills/critic/framework-checks.md")
        tokens = estimate_tokens(content)
        assert tokens < 1150, f"framework-checks.md is ~{tokens} tokens, should be <1150"

    def test_structure(self):
        content = read_file("skills/critic/review-cycle.md")
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in content
        assert "goal-based" in content.lower() or "Goal" in content
        assert ".critic-findings.json" in content

    def test_backlog_hygiene_checks_present(self):
        """The four backlog-hygiene checks (CRT-3K9P) must stay in Backlog
        Reconciliation — guards against a silent trim deleting them (the same
        regression-guard pattern as the PR-reviewer dropped-goal test)."""
        content = read_file("skills/critic/review-cycle.md")
        for check in ("C-B1", "C-B2", "C-B3", "C-B4"):
            assert check in content, f"review-cycle.md missing backlog check {check}"

    def test_the_per_mode_table_records_the_severity_narrowing(self):
        """`review-cycle.md` owns per-mode behavior, so the table is where a
        maintainer looks up what a mode rates.

        The reviewer never reads this file (`goals-1-3.md` forbids it), so
        nothing here reaches the actor — which is exactly why it must not
        contradict what does. This pins the row that says `verify-resolutions`
        rates BLOCKING only against the same claim in the reviewer's protocol.
        """
        content = read_file("skills/critic/review-cycle.md")
        row = next(
            (ln for ln in content.split("\n") if "New findings rated" in ln), None
        )
        assert row is not None, (
            "the per-mode table no longer says what each mode rates — a "
            "maintainer reading it learns nothing about the narrowing"
        )
        assert "BLOCKING only" in row, (
            "the table's verify-resolutions cell no longer records the "
            "narrowing the reviewer is actually instructed to apply"
        )
        # Three modes rate everything; only one is narrowed. A row that said
        # "BLOCKING only" everywhere would pass a presence check and describe a
        # framework nobody built.
        assert row.count("Every severity") == 3, (
            "the table no longer distinguishes the narrowed mode from the "
            "three that rate every severity"
        )

    def test_the_supply_side_section_states_the_cost(self):
        """A rule that removes review output has to name what it gives up, or
        the next maintainer re-derives the tradeoff from scratch and reverses it
        on the strength of the risk alone.

        Asserting the parts of the argument, not its wording: the rule, the
        carve-out that keeps it safe, and the admission that an observation is
        not a recorded fact.
        """
        content = read_file("skills/critic/review-cycle.md")
        heading = "### A re-review does not manufacture work"
        assert heading in content, (
            "review-cycle.md no longer carries the supply-side section the "
            "per-mode table points at"
        )
        # Split on the HEADING, not the phrase — the per-mode table cites the
        # section by name, so a phrase split lands in the table and every
        # assertion below then reads the wrong text.
        section = content.split(heading, 1)[1].split("\n### ", 1)[0]
        assert "OBSERVATION" in section, "the section never names where a demoted finding goes"
        assert "fix-by-fudging" in section, (
            "the section states the narrowing without its carve-out — the "
            "classes that stay BLOCKING are what make it safe"
        )
        assert "not a recorded fact" in section or "cannot be" in section, (
            "the section sells the benefit without stating the cost: a demoted "
            "observation leaves no trace in the evidence store"
        )

    def test_the_verify_step_no_longer_rates_a_workaround_warning(self):
        """Per-Chunk Cycle step 3 used to rate "a workaround instead of root
        cause" **WARNING** — inside the one mode that now records no warnings.

        Two things were wrong with it and only one is the contradiction. A
        WARNING gates nothing, so it was also the wrong instrument: when a fix
        works around a root cause the finding named, the honest verdict is that
        the finding is *unresolved*, which is expressed by withholding the
        resolution and fails closed.
        """
        content = read_file("skills/critic/review-cycle.md")
        step = next(
            ln for ln in content.split("\n") if ln.startswith("3. **If BLOCKING")
        )
        assert "workaround instead of root cause (**WARNING**)" not in step, (
            "step 3 rates a fix-by-fudging class WARNING inside "
            "verify-resolutions, which records no warnings — the reviewer is "
            "told two different things by two files it may read in either order"
        )
        assert "resolutions" in step, (
            "step 3 no longer routes fix-by-fudging to the mechanism that "
            "actually holds the gate shut — withholding the resolution"
        )


# =============================================================================
# Cross-cutting concerns
# =============================================================================


class TestCrossCuttingConcerns:
    def test_content(self):
        content = read_file(".prawduct/cross-cutting-concerns.md")
        assert "Boundary coherence" in content
        assert "Subagent governance" in content
        assert "Goal" in content
        assert "Nothing Is Broken" in content or "Nothing Is Missing" in content
        assert "boundary-patterns.md" in content
        assert "subagent-briefing.md" in content
        assert "compliance canary" in content.lower() or "canary" in content.lower()


# =============================================================================
# Cross-file consistency
# =============================================================================


class TestMethodologyConsistency:
    """Verify methodology files reference each other correctly."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.building = read_file("methodology/building.md")
        self.reflection = read_file("methodology/reflection.md")
        self.critic = read_file("skills/critic/review-protocol.md")

    def test_cross_references(self):
        """Key cross-references between methodology files."""
        # building.md points readers to the Critic protocol — now the plugin's
        # bundled skills/critic/review-protocol.md (was .prawduct/critic-review.md
        # under file-sync; repointed in the v2.0.0 Chunk-14 docs sweep).
        assert "review-protocol.md" in self.building
        assert ".subagent-briefing.md" in self.building
        assert "boundary-patterns.md" in self.critic
        assert "project-preferences.md" in self.critic
        assert "learnings-detail.md" in self.reflection

    def test_no_old_check_names(self):
        """v5 uses goal names, not check names."""
        for content in [self.building, self.critic]:
            assert "### Check 1:" not in content
            assert "### Check 2:" not in content
            assert "### Check 3:" not in content


# =============================================================================
# Property-based testing across methodology
# =============================================================================


class TestMethodologyPBT:
    """Verify PBT guidance flows through discovery, building, and cross-cutting concerns."""

    def test_discovery_mentions_domain_driven_testing_strategies(self):
        """Discovery methodology mentions testing strategies tied to domains."""
        discovery = read_file("methodology/discovery.md")
        assert "property-based" in discovery.lower()
        assert "test-specifications" in discovery.lower()

    def test_building_has_test_strategies_principle(self):
        """Building methodology has 'test strategies match the domain' principle."""
        building = read_file("methodology/building.md")
        assert "Test strategies match the domain" in building

    def test_building_pbt_in_test_discipline(self):
        """PBT is mentioned in Test Discipline section."""
        building = read_file("methodology/building.md")
        td_start = building.index("## Test Discipline")
        critic_start = building.index("## The Critic")
        td_section = building[td_start:critic_start]
        assert "property-based" in td_section.lower()

    def test_cross_cutting_concerns_updated(self):
        """Cross-cutting concerns registry reflects PBT pipeline coverage."""
        ccc = read_file(".prawduct/cross-cutting-concerns.md")
        lower = ccc.lower()
        assert "pbt" in lower or "property-based" in lower
        assert "testing strategies" in lower


# =============================================================================
# docs/principles.md — the 26 principles (canonical source)
# =============================================================================


class TestPrinciplesDoc:
    """All 26 principles are present, named, and numbered in the canonical source.

    Before M4 this contract was held by `test_v5_templates.py::TestProductClaudePrinciples`
    against the file-sync `product-claude.md` template *copy*. Chunk 4 deleted that
    template (and its test) as file-sync residue; this re-anchors the contract to the
    real source of truth — `docs/principles.md` — so an accidental drop or rename of a
    principle fails loud (M4 cumulative-Critic NOTE 1).
    """

    PRINCIPLES = [
        (1, "Tests Are Contracts"),
        (2, "Complete Delivery"),
        (3, "Living Documentation"),
        (4, "Reasoned Decisions"),
        (5, "Honest Confidence"),
        (6, "Requirements Precede Code"),
        (7, "Bring Expertise"),
        (8, "Accessibility From the Start"),
        (9, "Visible Costs"),
        (10, "Clean Deployment"),
        (11, "Proportional Effort"),
        (12, "Scope Discipline"),
        (13, "Coherent Artifacts"),
        (14, "Independent Review"),
        (15, "Validate Before Propagating"),
        (16, "Root Cause Discipline"),
        (17, "Automatic Reflection"),
        (18, "Close the Learning Loop"),
        (19, "Evolving Principles"),
        (20, "Infer, Confirm, Proceed"),
        (21, "Structural Awareness"),
        (22, "Governance Is Structural"),
        (23, "Challenge Gently, Defer Gracefully"),
        (24, "Retrieval Over Generation"),
        (25, "Third Rework Is a Deletion Signal"),
        (26, "Graceful Cession"),
    ]

    @pytest.mark.parametrize("num,name", PRINCIPLES, ids=[f"{n}-{name}" for n, name in PRINCIPLES])
    def test_principle_present_and_numbered(self, num: int, name: str):
        principles = read_file("docs/principles.md")
        assert f"### {num}. {name}" in principles, (
            f"docs/principles.md is missing the `### {num}. {name}` heading — "
            "the 26 principles are the framework's foundation; a drop or renumber must fail loud."
        )

    def test_exactly_26_numbered_principles(self):
        """No principle is added/removed without updating this contract.
        24 (Retrieval Over Generation) added 2026-07-17 — MET-4V8Q, per Principle 19.
        25 (Third Rework Is a Deletion Signal) and 26 (Graceful Cession) added
        2026-08-13 — owner decision 2026-08-12, per Principle 19; the framing they
        codify is documentation/purpose.md (framework repo)."""
        import re
        principles = read_file("docs/principles.md")
        headings = re.findall(r"^### (\d+)\. ", principles, re.MULTILINE)
        assert [int(h) for h in headings] == list(range(1, 27)), (
            f"expected principle headings 1..26 in order, found {headings}"
        )
