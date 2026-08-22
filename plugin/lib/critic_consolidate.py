"""Deterministic Critic data plane — dispatch manifest + consolidation (D8).

Both ends of the ``.prawduct/.critic-partials/`` contract live here: the
begin side (``begin_review`` — code derives the roster from mode, captures
the reviewed trees, and writes the dispatch manifest) and the consolidate
side (``consolidate`` — merges reviewer partials against that manifest,
appends the review fact to the evidence store, and regenerates the derived
findings cache). Models hand judgment to this data plane as *content* (the
partials), never as file-format authorship.

Two defect families die here rather than being patched:

- **Model-authored persistence** (CRT-W2NV, CRT-J4PM(1)): the v2 coordinator
  hand-wrote ``manifest.json`` (omitting keys) and single-pass reviews
  hand-wrote ``.critic-findings.json`` itself. In v3 ``critic-begin`` writes
  the manifest and ``consolidate`` writes everything downstream — the only
  model-written input is the per-role partial (the judgment payload),
  validated fail-closed.
- **Fork-resume loss** (critic-persistence-redesign, Option A): Claude Code
  v2.1.198 made ``Agent`` subagents background-by-default, so a coordinator
  that persisted findings after dispatch silently never did. Persistence is
  decoupled: reviewers write partials; consolidation is a pure function of
  on-disk state, idempotent, triggered per-reviewer by ``SubagentStop`` and
  floored by the session-end backstop.

**On-disk contract** (all under ``.prawduct/.critic-partials/``, gitignored):

- ``manifest.json`` — written by ``critic-begin`` (code, never a model). The
  single source of truth for the pending review: the fixed review ``id``
  (CRT-4B7X idempotency key), verbose ``mode`` + ``mode_chosen_by``, the
  code-derived ``roster`` + ``roster_chosen_by``, the reviewed interval
  (``base_commit``/``base_tree`` → ``head_tree``/``head_commit``, D3 tree
  keying via ``evidence.capture_tree``), the ``files_changed`` snapshot
  (``git diff`` between exactly those trees, so the recorded set and the
  D6 edge-validity check agree by construction), ``files_reviewed``,
  ``rendezvous`` (each role's resolved partial + started paths — see below),
  and telemetry/attribution (``tier``, ``scope``, ``chunk``).
- One partial per roster role, written by that reviewer, at the path
  :func:`partial_path` owns and the manifest's ``rendezvous`` records — keyed
  by review id, so two reviews in one worktree never contend for one name and
  a straggler cannot satisfy a roster it never reviewed. Carries the
  reviewer's findings, the ``dispatch_id`` binding it to the review that
  dispatched it, and — for a verify-resolutions dispatch only — its
  ``resolutions`` judgments (D5). The filename SHAPE is deliberately not
  spelled anywhere but :func:`partial_path`, this sentence included.

**Consolidation is idempotent and fail-closed.** It persists ONLY when every
roster role has reported a schema-valid partial at the manifest's dispatch
commit. Anything else is a no-op naming the missing roles (still in flight)
or a hard error (malformed / inconsistent / off-protocol). Success appends
the review fact (skipped when the id already exists — the CRT-4B7X race dies
here), appends any resolution facts, regenerates ``.critic-findings.json``
as a derived cache carrying its source ``fact_id`` (D7), anchors the ledger,
clears the critic-active marker, and removes the partials so every repeat
call is a clean no-op.

**No staleness refusal (v3 posture change).** The v2 consolidate refused to
persist when the dispatch commit no longer covered HEAD. A review fact is a
true statement about the tree the reviewers saw — it is appended regardless;
whether that tree still suffices is the gate-time coverage composition's
question (design D6), not the writer's. Refusing was the "evidence dies on
staleness" defect class this plan deletes.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import critic_marker, evidence, gitstate, ledger
from .core import atomic_write_text

PARTIALS_DIRNAME = ".critic-partials"
MANIFEST_NAME = "manifest.json"

# Severity vocabulary + ranking (highest wins on dedup). The stop-hook and PR
# gate key on "blocking"; restricting the partial vocabulary here means a typo'd
# severity fails partial validation rather than silently downgrading a blocker.
_SEVERITY_RANK = {"blocking": 3, "warning": 2, "note": 1}

# Caller-side short token → persisted verbose string (the two-form rule;
# values match gates._CRITIC_MODE_VALUES — pinned by test).
MODE_TOKEN_TO_VERBOSE = {
    "chunk": "chunk (lighter pass, not ready for push)",
    "final": "final (full review, ready for push)",
    "cumulative": "cumulative (bundle review, ready for merge)",
    "verify-resolutions": "verify-resolutions (delta review, prior findings only)",
}
_VERBOSE_VERIFY_RESOLUTIONS = MODE_TOKEN_TO_VERBOSE["verify-resolutions"]

# Roster config (D8): protocol roles per execution shape. chunk and
# verify-resolutions are always single-pass; final/cumulative go coordinator
# when the change touches a risk surface, or when it is large in JUDGEABLE
# files.
#
# **Risk first, size second — established by replay, not assumed.** Scoring
# every candidate rule against all 82 final/cumulative review facts in the
# evidence store (35 blocking findings) by the blockers it would have sent to a
# single reviewer:
#
#   current: total files >= 5            80% coordinator,  2 blockers demoted
#   judgeable files >= 12                40% coordinator, 19 blockers demoted
#   judgeable files >= 5                 56% coordinator, 19 blockers demoted
#   risk surface OR judgeable >= 12      78% coordinator,  1 blocker  demoted
#
# Recomputable: `python3 tests/spikes/roster_rule_replay.py`.
#
# That "blockers demoted" column scores every rule the same way — blocking
# findings in reviews the rule would send single-pass — which is what makes the
# rows comparable. The ACTUAL change from the previous rule is smaller than its
# row suggests: 8 reviews move from coordinator to single-pass, and they carried
# 0 blocking and 27 warning findings between them. R3's single scored blocker
# sits in a review that already ran single-pass and found it anyway.
#
# The intuition this refutes — that record files inflate the count, so a
# record-heavy diff is a small diff paying triple review — is backwards. The
# slice it targets (>= 5 files, < 5 judgeable) is 20 reviews carrying 17
# blocking findings, 13 of which point at CODE. Record-heavy diffs are
# governance diffs, and governance diffs are where the blockers are: reviews
# touching the gate kernel yield 0.96 blocking findings each against 0.22 for
# everything else, a 4.4x discriminator that no size cut approaches (blocker-
# bearing and clean reviews overlap across 0-206 and 0-60 judgeable files).
#
# The conflation to avoid re-introducing: ``coverage_algebra.is_judgeable_path``
# answers "does this change need review COVERAGE" — a gate question, and THE
# predicate there. It does not answer "how much review DEPTH does this
# deserve." Depth is a risk question, so the roster asks a risk predicate.
#
# Size is kept only as an escalator, at the one threshold the data supports:
# 5-11 judgeable files with no risk surface touched is 13 coordinator reviews
# with ZERO blocking findings, so it demotes; 12+ escalates on volume alone.
SINGLE_PASS_ROSTER = ("reviewer",)
COORDINATOR_ROSTER = ("correctness", "design", "sustainability")

# **Scope of that replay, and the fallback it forces.** Every figure above came
# from THIS repo's evidence store, where the derived risk surfaces match 77% of
# reviews. An onboarded product is the opposite case: the derived defaults are
# framework-shaped, the `project-state.yaml` template ships no `risk_surfaces:`,
# and the `boundary-patterns.md` template yields no parseable paths — so the
# risk predicate would never fire and the rule would collapse to "judgeable >=
# 12" ALONE, which is precisely row 2 of the table (54% of blockers demoted),
# replacing a rule that gave that product a coordinator at 5 files.
#
# So the risk-keyed rule applies only where there IS a risk signal. A repo that
# has declared none keeps the previous file-count escalator unchanged — no
# behaviour change where there is no evidence to justify one. This repo opts in
# by declaring `risk_surfaces:` in its own project-state.yaml, which is also
# what makes the replay above describe the rule that actually runs here.

#: Judgeable-file count at which volume alone buys the coordinator, with no
#: risk surface touched. Below it the replay shows an empty blocking record.
COORDINATOR_JUDGEABLE_THRESHOLD = 12

#: The pre-2026-07-30 rule, retained as the conservative fallback for repos that
#: have declared no risk surfaces. NOT the primary rule any more — see
#: ``_derive_roster``.
COORDINATOR_FILE_THRESHOLD = 5

# Background reviewers run for minutes after the dispatching fork returns, so
# an early consolidate correctly finds zero partials — a silence the parent
# session can misread as "the reviewers died with the fork" and re-dispatch a
# duplicate roster (observed 2026-07-20: both rosters ran, doubling review
# cost, while the first trio was alive the whole time). The incomplete no-op
# therefore states the dispatch age and whether silence is still the normal
# in-flight state; past this grace window it flips to advising critic-end +
# re-dispatch, since indefinite waiting on genuinely dead reviewers is the
# opposite failure.
#
# Sizing, stated honestly: the guide's nominal range is 4-10 minutes, but the
# 2026-07-20 incident measured reviewers running 5-15. So 15 is the observed
# CEILING with no slack above it, not the "nominal plus slack" it may look
# like — a run at the top of the observed range can tip past the window and be
# advised to abandon while alive. That bias is deliberate: the cost of a late
# abandon-and-re-dispatch is one duplicate review, while the cost of waiting
# past a genuine death is a session that never finishes. Widen it if real runs
# start landing past 15, and prefer widening over telling the caller to wait
# forever.
_INFLIGHT_GRACE_MINUTES = 15

# A session waiting on in-flight reviewers issues no model requests, so its
# prompt cache ages out and the next turn re-reads the entire prefix — the
# token replay adopters hit when a long review finally lands. A brief readout
# on this cadence keeps the prefix warm by making a request against it.
#
# Deliberate stopgap, and the interval is the weak part: it assumes the
# 5-minute prompt cache every current adopter runs on, which nothing here can
# observe (longer-lived caches exist, and on those this cadence buys nothing).
# Sized just under 5 so a slow turn still lands inside the window.
_CACHE_WARM_INTERVAL_MINUTES = 4

#: Appended to the wait-side variants only. Past the grace window the advice is
#: to stop waiting, so warming the cache there would prolong the wrong state.
_CACHE_WARM_DIRECTIVE = (
    " While waiting, print a one-line progress note (what you are waiting on,"
    f" elapsed time) at least every {_CACHE_WARM_INTERVAL_MINUTES} minutes"
    " rather than idling silently — an idle session lets its prompt cache"
    " expire and re-reads its whole context when the partials land."
)

#: Appended wherever a caller meets a review that HAS findings — the moment the
#: fix strategy is chosen, and the only moment at which stating it changes what
#: happens next.
#:
#: The pump it closes is measured and cross-repo (CRT-3W6P): fixing findings one
#: at a time and committing each fix moves the tree per fix, so every commit
#: reopens the coverage gap and buys another 5-10 minute delta round — and each
#: round then reviews the prose the previous round's fix wrote. Observed at four
#: rounds on a ~40-line change here, and independently at four rounds in a
#: consuming repo on v3.2.1, where 100% of rounds 2-3's new findings were
#: self-inflicted by the fixing.
#:
#: It ships from the runtime rather than from a guide because the guide is read
#: hours earlier if at all: on the coordinator path the reviewing fork never
#: writes a findings summary, so `critic-consolidate` output plus
#: `.critic-findings.json` is the ONLY surface the builder is guaranteed to meet.
#: Same reasoning as :data:`_CACHE_WARM_DIRECTIVE`.
#:
#: **Disposition, not "fix everything."** Only unresolved BLOCKING findings gate
#: anything (``coverage_algebra.unresolved_blocking``); warnings and notes gate
#: nothing and are the builder's to fix, accept or file. An earlier draft said
#: "Fix them ALL", which on the common ``0 blocking, 9 warning, 16 note`` review
#: instructed exactly the reflexive fixing that ``methodology/building.md`` and
#: ``skills/critic/review-cycle.md`` tell the builder to stop — a contradiction
#: landing on the surface with the most authority at the decision moment. The
#: verify pass is likewise stated as a *coverage consequence*, not an
#: obligation: a review with nothing blocking and no judgeable fix needs no
#: second pass at all.
#:
#: The free-write list restates ``coverage_algebra.is_judgeable_path`` and would
#: drift from it silently, so ``TestBatchFixDirective`` in
#: ``tests/test_critic_consolidate.py`` parses the backticked path tokens out of
#: this string and drives its assertions from the text — drift in EITHER
#: direction fails (a predicate change, or an edit to this list alone).
#:
#: **It makes no positional cross-reference, and cannot.** There are two
#: emission sites and they print different things after it: :func:`consolidate`
#: follows with the ``NEXT-ACTION:`` line, while
#: :func:`_already_consolidated_note` follows with nothing at all — and that is
#: the coordinator path's normal case, where the reviewing fork has already
#: returned. A clause pointing at "the line below" is therefore true on one path
#: and a dangling pointer on the other, which is worse than the hardcoded
#: "5-10 minute rounds" it briefly replaced. Anything this text needs the reader
#: to have must be inside it.
_BATCH_FIX_DIRECTIVE = (
    " Disposition them ALL in ONE pass — land every fix you are going to make in"
    " ONE commit, and accept or file the rest. Only unresolved BLOCKING findings"
    " gate anything; if that commit touches judgeable files, ONE"
    " `/prawduct:critic verify-resolutions` re-covers it. A fix-commit-verify"
    " cycle per finding multiplies whole review rounds, and each round reviews the"
    " prose the previous fix wrote. Free to write at any time (they do not move"
    " coverage): everything under `.prawduct/` — change-log, backlog,"
    " project-state and build plans — plus"
    " `.claude/settings.json` and `.md` files OUTSIDE `skills/`,"
    " `methodology/`, `templates/` and a root `CLAUDE.md`. Everything else"
    " moves the tree and must land BEFORE the verify pass: code, config, data,"
    " tests, and those governance-protected `.md` files (a comment-only edit to"
    " a code file counts)."
)


#: Carried by EVERY zero-blocking variant, including the clean pass.
#:
#: "The review is over" and "you may merge" are different claims, and only the
#: first is this function's to make: a clean `chunk` mid-plan still owes a
#: `final`/`cumulative` at end of cycle (`review-cycle.md`'s table, and the
#: advisory `_critic_session_satisfies_gate` fires for exactly that case), and
#: `check-cumulative-critic` still needs spanning coverage. Omitting it from
#: the clean branch let two code-owned surfaces assert opposite things in one
#: session, with the newer one saying "stop" — so it is a constant rather than
#: a phrase each branch remembers to repeat.
_COVERAGE_IS_A_SEPARATE_QUESTION = (
    " (Whether the PR gate is satisfied, and whether the work cycle still owes a"
    " final/cumulative, are separate questions about coverage — ask them by"
    " running the gate, not by reviewing again.)"
)


#: The route the fix/accept/file trio was missing, carried by BOTH arms.
#:
#: Fixing now buys a round; accepting and filing buy none. What was never on
#: offer is the option that costs *nothing extra*: when the plan has further
#: judgeable chunks, a small fix carried into the next chunk's commit rides a
#: round that was going to be bought anyway. A builder weighing "fix now or
#: accept" reaches for one of two answers because those are the two the message
#: names.
#:
#: Stated with its condition, because it is not always right — a fix that
#: changes what the bundle claims to ship belongs in the bundle, and a branch
#: with no further judgeable work has nothing to ride. And stated with its
#: failure mode: an unwritten deferral is a drop, not a deferral, so the route
#: names where to write it.
#:
#: **It must distinguish itself from the deferral the blocking arm warns
#: against**, or it reads as the message contradicting itself one sentence
#: later. The two are genuinely different and the difference is the whole
#: point: deferring a finding to a later ROUND buys a second round, while
#: riding a commit that is being made anyway buys none. A reader who cannot
#: see that distinction resolves it by ignoring one of the two sentences, and
#: there is no telling which.
_RIDE_ALONG_ROUTE = (
    " If this branch has more judgeable work coming, there is a third route:"
    " carry the fix into the NEXT chunk's commit. That is NOT the deferral"
    " warned against above — deferring to a later ROUND buys a second round;"
    " riding a commit that is being made anyway buys none. Write it where that"
    " chunk will meet it (the build plan or `.prawduct/.handoff-notes.md`), or"
    " it is not a deferral, it is a drop."
)


def next_action_line(
    fact_id: "str | None",
    blocking: int,
    warning: int,
    note: int,
    price_sentence: "str | None" = None,
) -> str:
    """The one sentence the BUILDER needs, computed from the fact's own counts
    and written into ``.critic-findings.json`` by :func:`fact_to_cache_record`.

    **Why this field exists at all.** Every other carrier of the
    loop-termination rule is a *pull* carrier, and the builder that most needs
    it is the one least likely to pull. ``methodology/building.md`` states the
    rule under "Resolve findings", but a builder reaches it only by entering a
    build plan — and a branch with no plan (an ordinary framework fix, an
    ad-hoc lane) never does. ``skills/critic/review-cycle.md`` states it more
    fully and is read by nobody in the builder role. :data:`_BATCH_FIX_DIRECTIVE`
    is the runtime carrier and *cannot reach the builder on the single-pass
    path*: ``verify-resolutions`` and ``chunk`` are always single-pass, so the
    reviewing fork runs ``critic-consolidate`` itself and the directive prints
    into the reviewer's context, not the builder's. The docstring above
    :data:`RESOLUTION_IS_A_CLAIM_DIRECTIVE` already records that reasoning for
    its own sake; this is the same gap answered where it can be closed.

    Measured on a released version (v3.2.3), one consumer branch: ten Critic
    rounds, of which rounds five onward were the builder fixing WARNINGs that
    gated nothing. The transcript contains zero reads of either prose carrier
    and zero occurrences of the batch-fix directive, against seven occurrences
    inside reviewer forks. The builder did read the findings — so the findings
    file is the carrier that had a reader and no message.

    ``.critic-findings.json`` is a derived VIEW (D7): no gate reads it, so a
    line here can never weaken one. It is advice delivered where the decision
    is made.

    ``price_sentence`` is :func:`telemetry.format_round_price`'s output, passed
    in rather than derived here so this stays a pure function of its arguments
    and the ledger read happens once per consolidation. **Both arms carry it.**
    The blocking arm used to say only that deferring "turns one review into
    several" — a rule, not a price, which is the first of the five failures a
    v3.2.4 consumer reported after reading these carriers and running six rounds
    anyway. For the same reason the blocking arm now also names the accept
    route: it already orders the builder to decide the WARNING/NOTE findings in
    the same pass, and the command for the cheapest of those decisions lived
    only in the arm the builder does not reach when something is blocking."""
    ref = fact_id or "<review-id>"
    price = f" {price_sentence}" if price_sentence else ""
    if blocking:
        return (
            f"{blocking} BLOCKING finding(s) gate this work — nothing else here does."
            " Fix them, land EVERY fix you are going to make in ONE commit, then run"
            " ONE `/prawduct:critic verify-resolutions`. Decide the WARNING/NOTE"
            " findings in that SAME pass (fix / accept / file) — deferring them to a"
            " later round is what turns one review into several. Accept is the"
            " default for anything nobody will realistically action:"
            f' `prawduct-hook disposition {ref} <fid> --accept "<reason>"` needs no'
            " review and moves no tree."
            + _RIDE_ALONG_ROUTE
            + price
        )
    if not (warning or note):
        return (
            "0 blocking, 0 other findings — THE REVIEW IS OVER and there is nothing"
            " to disposition. Nothing in THIS review requires another round."
            + _COVERAGE_IS_A_SEPARATE_QUESTION
        )
    return (
        f"0 blocking — THE REVIEW IS OVER. The {warning} warning + {note} note"
        " finding(s) gate NOTHING: no gate reads them, so nothing in THIS review"
        " requires another round."
        + _COVERAGE_IS_A_SEPARATE_QUESTION
        + " Disposition each finding instead of reflexively fixing it —"
        " accept is the default for anything nobody will realistically action:"
        f' `prawduct-hook disposition {ref} <fid> --accept "<reason>"`, which needs'
        " no review and moves no tree. If you do choose to fix some, batch them into"
        " ONE commit — and re-cover with ONE `/prawduct:critic verify-resolutions`"
        " ONLY if that commit touched judgeable files. `prawduct-hook cost-of-commit"
        " <paths>` answers that for the exact batch BEFORE you commit it; a batch it"
        " prices `free` moves no coverage and needs no pass at all. AFTER committing,"
        " you no longer have to judge it either: dispatch asks the same predicate and"
        " exits 3 (`no review needed`, under a second, no session state written) rather than"
        " spending a reviewer on a free interval — so asking costs nothing, and a"
        " refusal is the answer, not a reason to retry in another mode."
        " Do NOT start another round to 'close coverage' before committing, and do"
        " not infer that you need one from gate output printed before your fix —"
        " commit, then re-run the gate and let it answer."
        + _RIDE_ALONG_ROUTE
        + price
    )


#: Delivered at `verify-resolutions` DISPATCH — before the reviewer judges each
#: prior finding, not after it has.
#:
#: Public because its print site is ``cmd_critic_begin`` in ``bin/prawduct-hook``;
#: it lives here so the two directives the review data plane emits are read and
#: edited together.
#:
#: **Why dispatch and not consolidation.** The obvious slot is beside
#: :data:`_BATCH_FIX_DIRECTIVE` in :func:`consolidate`, on a "this review
#: recorded resolutions" trigger. That slot is downstream of the claim on every
#: path that can carry one. ``verify-resolutions`` is always single-pass
#: (:func:`_derive_roster` returns :data:`SINGLE_PASS_ROSTER` for it
#: unconditionally), so the reviewing fork writes its ``resolutions`` into the
#: partial and THEN runs consolidate itself — the directive would reach
#: an agent that has already made the claim and is one step from exiting. Nor
#: does it carry to the builder: the Critic skill is ``context: fork``, and the
#: fork's report-back instruction (``skills/critic/goals-1-3.md``) enumerates
#: findings and a summary, not the consolidator's stdout. Dispatch is the same
#: reader in the same review, one step earlier, and upstream of the claim.
#:
#: **Why the rule is worth a directive at all.** A resolution is the only
#: reviewer output that WEAKENS a gate: ``coverage_algebra.resolution_index``
#: admits both ``fixed`` and ``waived``, and either one lifts a blocking finding
#: out of ``unresolved_blocking`` with nothing downstream re-checking it. It is
#: also the judgment most cheaply made from memory — the reviewer read the fix
#: commit minutes ago and remembers it landing.
#:
#: The no-execution clause is not filler. The Critic cannot run the suite (its
#: ``allowed-tools`` grant no test runner — CRT-3X9D), so "the test passes now"
#: is a resolution rationale it structurally cannot have verified;
#: ``TestResolutionIsAClaimDirective`` pins every command this text names
#: against that grant so a future edit cannot instruct the impossible.
#:
#: **Every clause after the general statement is the descent, and it is
#: load-bearing.** An upleveled rule earns its durability by being general and
#: loses all of its effect there: a reader agrees with "a resolution is a claim"
#: and writes the same unchecked ``fixed`` it was going to write, because
#: nothing made it recognize THIS disposition as an instance. So the general
#: sentence is followed by the act to perform ("name the evidence you read"),
#: instances concrete enough to pattern-match against, and an explicit
#: instruction to spend it on the case in hand — aimed at the finding the
#: reader is surest about, which is the one a general rule never reaches.
RESOLUTION_IS_A_CLAIM_DIRECTIVE = (
    "PRAWDUCT: a resolution is a claim about the tree, and it WEAKENS a gate —"
    " `fixed` and `waived` BOTH lift a blocking finding out of"
    " `unresolved_blocking`, and nothing downstream re-checks either. For each"
    " prior finding, name the evidence you read before writing the disposition:"
    " the search that comes back empty, the `git show` of the hunk, the file and"
    " line you opened — not that the fix commit looked right, and not that you"
    " are confident. You cannot run the suite from here, so \"the test passes"
    " now\" is never something you verified. A finding you could not settle from"
    " the tree is LEFT OUT of `resolutions`: omitting it keeps it blocking,"
    " which is the answer that fails closed. Two that read as resolved and are"
    " not — a diff read instead of the file it changed, and a finding that named"
    " a CLASS but was closed at the sites it happened to name: re-run the"
    " finding's own reason as a search before you write `fixed`, because the"
    " members that survive are the ones outside this delta, and a longer list of"
    " names is not a resolution. Spend this on the"
    " finding you feel surest about: a rule you agree with and do not apply to"
    " the disposition actually in front of you has done nothing."
)


#: Delivered at `verify-resolutions` DISPATCH, immediately before
#: :data:`RESOLUTION_IS_A_CLAIM_DIRECTIVE` — same reader, same moment, and the
#: other half of what makes a re-review terminate. That one governs the
#: `resolutions` array; this one governs `findings`.
#:
#: **The pump it closes.** A verify pass exists to answer one question: were the
#: prior findings resolved? It also walks the fix delta at full severity, and
#: the WARNING/NOTE findings it records there are round N+2's supply — the
#: builder fixes them, the fix moves the tree, the moved tree reopens coverage,
#: and the next pass reviews the prose the last fix wrote. Measured at ten
#: rounds on one consumer branch (CRT-3W6P), where rounds five onward were
#: entirely non-gating findings the previous round's fixing had created.
#:
#: **The argument for the narrowing is NOT restated here.** It lives in
#: ``skills/critic/review-cycle.md`` § "A re-review does not manufacture work" —
#: why this mode and not the others, what it does not cost (only
#: ``unresolved_blocking`` is read by any gate), what it does cost (an
#: observation is not a recorded fact), the escalation history, and the
#: half-emitted yield. Both audiences are maintainers and both copies were
#: full-length, which is the shape ``architecture.md``'s one-home norm names: on
#: the next change to the argument — #585 landing makes "yield is half-emitted"
#: false — the loser is whichever reader met the stale copy.
#:
#: What stays here is what an editor of THIS STRING needs and that section does
#: not own:
#:
#: **The demotion binds on severity, not on class membership.** The list ADDS to
#: what the protocol blocks and never narrows it. Stating it the other way round
#: made "everything else" take the five classes as its antecedent, which
#: literally demoted BLOCKING-rated classes the enumeration happens to omit —
#: test failures in evidence, ``missing-coverage:`` lines, cross-component
#: contract breaks, unlisted dependencies, norm departures. On the carrier the
#: reviewer reads last before rating, that reading is the expensive one.
#:
#: **Two of the five classes are an ESCALATION and this text must keep saying
#: so.** ``goals-1-3.md`` rates *auth/authz on new endpoints* and
#: *known-vulnerable dependencies* WARNING and does not rate fix-by-fudging at
#: all, so for this mode the rating exists nowhere but here — dropping the
#: wording demotes those classes by silence, and claiming they are "already
#: BLOCKING-rated" (an earlier draft did) is circular as well as false.
#: ``test_the_escalated_carve_out_classes_are_named_as_escalations`` pins both
#: halves, per clause rather than per line.
#:
#: **The structural destination is part of the string, not decoration.**
#: ``goals-1-3.md``'s report contract enumerates findings and a summary with no
#: slot for anything else, so "in prose" was not enough — the text names an
#: `### Observations` heading and asks for a count, and both are pinned.
#:
#: **The descent is load-bearing, for the reason
#: :data:`RESOLUTION_IS_A_CLAIM_DIRECTIVE`'s docstring gives at length.** A
#: reviewer agrees that re-reviews should not manufacture work and then records
#: the WARNING in front of it, because nothing made it recognize THIS finding as
#: the instance. So the general sentence is followed by the act, by instances
#: concrete enough to pattern-match against, and by an instruction to spend it
#: on the finding the reader is surest about — which is the one a general rule
#: never reaches.
VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE = (
    "PRAWDUCT: this pass answers ONE question — were the prior findings"
    " resolved? A NEW finding here is BLOCKING, or it is not a finding."
    " **The test is the SEVERITY you would assign, never membership in any"
    " list.** Anything you would rate below BLOCKING — including a record-lint"
    " entry the manifest rated below BLOCKING — goes in your report under an"
    " `### Observations` heading, in prose, and NOT into `findings`: a name you"
    " would have chosen differently, prose that could be tighter, a test you"
    " would have structured another way. Everything the protocol rates BLOCKING"
    " stays BLOCKING, with no exceptions and no list to check. Five classes are"
    " BLOCKING *in this mode whatever they are rated elsewhere*, because they"
    " are what a fix delta actually gets wrong and demoting one is the only way"
    " this rule could lose something real: a test weakened or deleted to make"
    " the fix pass; a requirement dropped in the rewrite; changed behavior with"
    " no test; anything security-relevant in the changed code — including the"
    " auth/authz and known-vulnerable-dependency cases the protocol rates"
    " WARNING; and fix-by-fudging — the spec edited to match the implementation,"
    " or a workaround where the finding named the root cause, which is equally"
    " grounds to leave that finding OUT of `resolutions`. This list only ADDS to"
    " what the protocol blocks; it never narrows it. Then say how many"
    " observations you demoted, in one line, so a rule that fired can be told"
    " apart from a reviewer that found nothing. The demotion is not politeness:"
    " a WARNING recorded here becomes a fix commit, the commit moves the tree,"
    " the moved tree reopens coverage, and the next pass reviews the prose this"
    " fix just wrote — measured at ten rounds on one branch, where rounds five"
    " onward were entirely self-inflicted. The builder still reads your"
    " observations and can act on them; they are simply not work the record"
    " demands."
    " **BLOCKING means the tree must not move again without this fix — not"
    " merely that the fix is owed.** The two come apart on RECORD gaps: a"
    " registry row, a doc table, an artifact that lags the code it describes."
    " Those are real and they are owed, but nothing is wrong with the TREE"
    " until they land, so if the chunk has a commit still coming they ride it"
    " — say so under Observations and name where the builder must write it"
    " (the build plan or `.prawduct/.handoff-notes.md`), which is the"
    " ride-along route their own NEXT-ACTION advertises. Rating a one-row doc"
    " gap BLOCKING spends a commit and a full round on it, which is the round"
    " this rule exists to prevent; and it is the failure mode to watch for,"
    " because a reviewer who has just reasoned 'this rides the commit already"
    " owed' and then rates it BLOCKING has contradicted itself, and the gates"
    " read the severity, not the sentence. The five classes above are exempt"
    " and stay BLOCKING: each of them means the tree is ALREADY wrong. A record"
    " gap met while the chunk is CLOSING, with no further commit to ride,"
    " blocks that close — rate it BLOCKING and say so."
    " Apply all of this to the one you are surest deserves a WARNING: that"
    " finding is the next round's first item, and demoting it is the whole"
    " point."
)

_REVIEW_ID_TS = re.compile(r"^rev-(\d{8}T\d{6}Z)-")


def mint_review_id() -> str:
    """The review id, minted in ONE place so the liveness verdict can read the
    dispatch time back out of it.

    The embedded stamp is not decoration: :func:`dispatch_age_minutes` parses it
    to decide whether missing partials mean "still in flight" or "reviewers
    died". A format change here that :data:`_REVIEW_ID_TS` cannot parse does not
    fail loudly — age silently becomes ``None``, the past-grace branch stops
    being reachable, and the no-op advises waiting forever on dead reviewers.
    Producer and consumer therefore stay adjacent, with a round-trip test.
    """
    return "rev-{}-{}".format(
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8]
    )

_RESOLUTION_DISPOSITIONS = frozenset({"fixed", "waived"})

# verify-resolutions scope-widening demotion threshold (unchanged from v2's
# canonical helper): a delta this much larger than the prior surface means a
# partial re-review would mislead — fall back to a full review.
def _scope_widened(delta_count: int, prior_count: int) -> bool:
    return delta_count > 2 * prior_count + 5


def _widened_fallback_mode(
    project_dir: Path, committed_head_tree: str, committed_differs: bool
) -> tuple[str, str]:
    """Which full-review mode actually COVERS the delta that just widened.

    "Run a full review" meant `final`, unconditionally — and `final`'s interval
    is HEAD-tree → working-tree, the *uncommitted* diff. So a delta that widened
    because commits landed since the prior review demoted to the one mode that
    cannot see them: the refused interval was too wide, and its replacement was
    strictly NARROWER. Observed 2026-08-15 on a 95-file widening (a base-branch
    merge plus the chunk's own fix commit): the demoted `final` reviewed the two
    untracked strays the working tree happened to hold and reported them as the
    chunk's review. Nothing caught it, because both dispatches succeeded.

    Where the delta LIVES decides the mode, and `begin_review` has already
    computed that. Returns ``(mode, why)``; ``why`` ships in the refusal so the
    reader can tell a recommendation from a default.

    ``cumulative`` is not a superset of what widened, and must not be sold as
    one: a base-branch merge moves the merge-base forward, so merge-base…HEAD
    EXCLUDES the merged-in files that inflated the delta. That is the right
    answer rather than a shortfall — those files were reviewed on the base
    branch, and what this branch owes is its own work, which is exactly the
    span.

    ``committed_head_tree`` is spelled out because the caller's own ``head_tree``
    at this point is the ANCHOR head, which may be the working tree — and
    committed-vs-working is the exact distinction this function exists to keep
    straight. Comparing the merge-base against the wrong one of the two would
    reintroduce the defect inside its own fix.
    """
    if not committed_differs:
        return "final", (
            "every change since the prior review is uncommitted, which is "
            "exactly `final`'s HEAD-tree → working-tree interval"
        )
    from . import coverage  # noqa: PLC0415 — lazy; coverage pulls git helpers

    resolved = coverage.resolve_merge_base_tree(project_dir)
    # Both guards below keep this from recommending `cumulative` where it would
    # refuse for want of a span — recommending a mode that cannot run being the
    # very failure fixed here. `final` is then the remaining full review rather
    # than the covering one, and says so; on a clean tree it too refuses (empty
    # diff), which is the honest end state when no mode's interval holds the
    # committed remainder. The coverage gate is where that remainder surfaces.
    if resolved["status"] != "ok":
        return "final", (
            "the delta includes committed work, but no merge-base resolves "
            f"({resolved['reason']}), so `cumulative` cannot dispatch — `final` "
            "sees only the uncommitted part"
        )
    if resolved["tree"] == committed_head_tree:
        # TREE equality, and the message says so. "HEAD is at the merge-base" is
        # the common cause but not the condition: a branch that commits and then
        # reverts sits far ahead of the merge-base with an identical tree, takes
        # this path correctly, and would be told something false about itself.
        return "final", (
            "the delta includes committed work, but HEAD's tree matches the "
            "merge-base's, so `cumulative`'s interval is empty — `final` sees "
            "only the uncommitted part"
        )
    return "cumulative", (
        "the delta includes committed work, which `final`'s HEAD-tree → "
        "working-tree interval cannot see; `cumulative` spans merge-base…HEAD — "
        "the work this branch owes, and the PR gate's own span"
    )


def partials_dir(prawduct_dir: Path) -> Path:
    return prawduct_dir / PARTIALS_DIRNAME


def manifest_path(prawduct_dir: Path) -> Path:
    return partials_dir(prawduct_dir) / MANIFEST_NAME


def _path_component_safe(value: str) -> bool:
    """True when ``value`` can be used as ONE filename component.

    Both halves of a rendezvous filename — the role and the review id — arrive
    from the manifest, and the manifest is a file on disk. Neither was
    constrained before, because a role was the only interpolated component and
    it came straight from a fixed roster; adding the review id widens the
    surface, so both are checked at the one place that can still refuse
    (:func:`validate_manifest`) rather than at the paths themselves, where a
    raise would turn a malformed record into a crash instead of a verdict.
    """
    return bool(value) and "/" not in value and "\\" not in value and ".." not in value


def partial_path(prawduct_dir: Path, role: str, review_id: str) -> Path:
    """Where ``role``'s partial lives for the review ``review_id`` dispatched.

    **Keyed by the review, not by the role alone**, and that is load-bearing.
    A role-only name is one rendezvous shared by every review the worktree ever
    runs: two dispatches contend for it, the loser's only signal is a failed
    write with nothing in the protocol saying what that means, and a straggler
    from an abandoned review lands in a later review's directory where it is
    schema-valid, commit-valid at an unchanged HEAD, and satisfies a roster it
    never reviewed. Keying by review id makes all three unrepresentable: each
    review has its own names, so a straggler can neither overwrite a live
    partial nor be mistaken for one.

    Nothing outside this module builds this name. The resolved paths ride the
    manifest (``rendezvous``), so the instruction surfaces that tell reviewers
    where to write reference that entry instead of spelling the shape — one
    home for the fact, and a future change to it needs no doc edit.
    """
    return partials_dir(prawduct_dir) / f"{role}.{review_id}.json"


def started_path(prawduct_dir: Path, role: str, review_id: str) -> Path:
    """The per-role liveness marker a coordinator-dispatched reviewer writes as
    its FIRST action. Its mtime is the signal (reviewers have no clock tool —
    their toolset is read-only file/git plus Write); the content is irrelevant.
    Without it, "no partial yet" and "reviewer never started" are the same
    on-disk state for the reviewer's whole multi-minute run, and callers infer
    death from the silence (the observed double-dispatch failure).

    Keyed by review id for the same reason as :func:`partial_path`: an abandoned
    review's marker sitting under a shared name would age into a later review's
    liveness verdict and report a reviewer that never started as one at work."""
    return partials_dir(prawduct_dir) / f"{role}.{review_id}.started"


def _rendezvous(project_dir: Path, prawduct_dir: Path, roster: list[str],
                review_id: str) -> dict[str, dict[str, str]]:
    """The per-role write paths recorded in the manifest.

    Project-relative where possible, because the manifest is read from more than
    one place — the coordinator composing dispatch prompts, the reviewer reading
    its own entry, a human inspecting the file — and an absolute path bakes in
    the worktree that wrote it, which is wrong the moment the clone moves. An
    absolute fallback covers the case where ``.prawduct/`` does not resolve under
    the project dir; a wrong path is worse than a long one.

    **The relative form is NOT usable verbatim by a reviewer, and saying so is
    part of the contract.** A reviewer writes with the ``Write`` tool, which
    requires an absolute path. ``agents/critic-reviewer.md`` is the one place
    that says to resolve it — the reviewer is the actor that writes, so the rule
    is a reviewer instruction, and it belongs where "never compose the filenames
    yourself" already lives rather than being restated in the coordinator's
    dispatch template. That resolution used to happen anyway, silently, because a
    coordinator would absolutize without being told to; an unstated
    transformation the mechanism depends on is exactly the class this module's
    review-identity work removes elsewhere, so it is written down rather than
    relied upon.
    """
    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(project_dir))
        except ValueError:
            return str(p)

    return {
        role: {
            "partial": _rel(partial_path(prawduct_dir, role, review_id)),
            "started": _rel(started_path(prawduct_dir, role, review_id)),
        }
        for role in roster
    }


def started_age_minutes(prawduct_dir: Path, role: str, review_id: str) -> float | None:
    """Minutes since ``role``'s started marker was written, or None when the
    marker is absent/unreadable. Clamped at zero for clock skew."""
    try:
        mtime = started_path(prawduct_dir, role, review_id).stat().st_mtime
    except OSError:
        return None
    age_s = datetime.now(timezone.utc).timestamp() - mtime
    return max(age_s, 0.0) / 60.0


#: An unconsolidated predecessor's manifest + partials move here instead of
#: being deleted, so a re-dispatch cannot erase the only evidence the first
#: review ever ran (observed 2026-08-02: a premature death verdict led to a
#: re-dispatch that clobbered the first manifest — the first review became
#: unreconstructable from disk). Newest :data:`_ARCHIVE_KEEP` kept.
ARCHIVE_DIRNAME = ".critic-partials-archive"
_ARCHIVE_KEEP = 3


def archive_dir(prawduct_dir: Path) -> Path:
    return prawduct_dir / ARCHIVE_DIRNAME


def had_partials(prawduct_dir: Path) -> bool:
    """Was there reviewer output on disk *before* an archive attempt?

    The one thing :func:`_archive_leftovers`' ``None`` cannot say. Read it
    BEFORE calling that function: together they separate "there was nothing to
    archive" from "there was something and archiving it failed", which is the
    difference between a no-op and a destroyed review.
    """
    pdir = partials_dir(prawduct_dir)
    if not pdir.is_dir():
        return False
    try:
        return any(c.is_file() for c in pdir.iterdir())
    except OSError:
        # Unreadable is not empty. Claiming "nothing was there" off a failed
        # read is the same false reassurance this function exists to prevent.
        return True


def _archive_leftovers(prawduct_dir: Path, caller: str = "critic-begin") -> Path | None:
    """Move a pending review's files aside rather than deleting them.

    Returns the archive directory the files landed in, or None when there was
    nothing to archive (or archiving failed — the caller falls through to
    :func:`remove_partials` either way, so a failed archive degrades to
    exactly the old delete behavior, never to a blocked dispatch).

    ``caller`` names the command in the degraded-archive diagnostic. It is a
    parameter rather than a constant because the two callers reach this by
    opposite routes — a dispatch sweeping someone else's leftovers, and an
    operator deliberately discarding their own review — and an operator who ran
    ``critic-discard`` cannot act on a line that says ``critic-begin``.

    **A None return is three outcomes, and only the middle one is benign.**

    1. Nothing was there to archive.
    2. The directory could not be READ — nothing is archived and, because
       :func:`remove_partials` cannot list it either, nothing is deleted. The
       partials survive, unreachable until the permission is fixed.
    3. An ``OSError`` hit mid-archive (the ``mkdir``/``rename``): this degraded
       to delete, and the caller's ``remove_partials`` finishes the job.

    (An unsafe manifest id is not among them — it falls through to the
    ``unmanifested-`` name and still archives.)

    Only 3 destroys anything, so a caller that reports "nothing was there" on
    it tells the operator their partials are safe on the one path where they are
    gone. :func:`had_partials` separates 1 from 2-and-3; the stderr diagnostic
    printed here is what distinguishes 2 from 3, and it names its ``caller``.

    Named after the abandoned review's id when its manifest is readable, else
    a timestamp — partials can outlive their manifest (a late reviewer writing
    into an already-consolidated review re-creates the directory)."""
    pdir = partials_dir(prawduct_dir)
    if not pdir.is_dir():
        return None
    try:
        children = [c for c in pdir.iterdir() if c.is_file()]
    except OSError as exc:
        # An unreadable partials dir must degrade like any other archive
        # failure, not traceback. This function is the escape hatch's
        # prescribed remedy for a wedged review, so raising here strands the
        # operator in the state the remedy exists to clear — with a stack
        # trace instead of the marker they came to release.
        print(
            f"{caller}: cannot read {pdir} ({exc}) — falling back to delete",
            file=sys.stderr,
        )
        return None
    if not children:
        return None
    name: str | None = None
    mpath = manifest_path(prawduct_dir)
    if mpath.is_file():
        try:
            raw = json.loads(mpath.read_text())
            candidate = raw.get("id") if isinstance(raw, dict) else None
            # Same gate as the rendezvous paths, for the same reason: this id
            # comes off disk and becomes a directory name, so `../../x` walks up
            # and `/tmp/x` replaces the base outright. Unlike those paths there
            # is no validator upstream — this reads the manifest raw, precisely
            # because it must also work when the manifest is unreadable — and an
            # archive failure degrades to DELETE, so getting it wrong here loses
            # the evidence silently. Falls through to the timestamp name.
            if (isinstance(candidate, str) and candidate.strip()
                    and _path_component_safe(candidate.strip())):
                name = candidate.strip()
        except (OSError, json.JSONDecodeError):
            name = None
    if name is None:
        name = "unmanifested-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir(prawduct_dir) / name
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for child in children:
            child.rename(dest / child.name)
    except OSError as exc:
        # Name the reason before degrading — a silent fallback would make
        # "why is the archive empty?" undiagnosable after the fact.
        print(
            f"{caller}: leftover archive failed ({exc}) — "
            "falling back to delete",
            file=sys.stderr,
        )
        return None
    # Prune to the newest _ARCHIVE_KEEP by mtime — best-effort, an unprunable
    # archive must not fail the dispatch.
    try:
        entries = sorted(
            (d for d in archive_dir(prawduct_dir).iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        for stale in entries[_ARCHIVE_KEEP:]:
            shutil.rmtree(stale, ignore_errors=True)
    except OSError:
        pass
    return dest


def archived_reviews(prawduct_dir: Path) -> tuple[list[str], str]:
    """The archived sets :func:`restore_review` can bring back, newest first.

    The names :func:`_archive_leftovers` wrote: a review id when the archived
    manifest was readable, ``unmanifested-<stamp>`` when it was not. The list is
    the WHOLE truth about what is restorable — :data:`_ARCHIVE_KEEP` bounds it,
    so a caller that names an older review is not being told "not found" about a
    review that still exists somewhere. The not-found refusal and the bare
    invocation both render it for that reason, rather than leaving the reader to
    `ls` a dot-directory for names nobody memorised.

    **An unreadable archive is not an empty one, and the two must not render
    alike.** An absence-claim is evidence only when the place it read actually
    resolved: a permission error or a non-directory at that path would otherwise
    produce the identical empty list, and the caller — an operator deciding
    whether an unconsolidated review's findings are gone — would be told they
    are and act on it. So the reason rides along with the list, and every
    renderer says which case it is.

    Returns ``(names, problem)`` where ``problem`` is empty when the directory
    was read (including when it simply does not exist, the normal case) and
    names the fault otherwise.
    """
    adir = archive_dir(prawduct_dir)
    if not adir.exists():
        return [], ""
    if not adir.is_dir():
        return [], f"{adir} exists but is not a directory"
    try:
        entries = sorted(
            (d for d in adir.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
    except OSError as exc:
        return [], f"the review archive at {adir} could not be read ({exc})"
    return [d.name for d in entries], ""


def archive_listing(available: list[str], problem: str) -> str:
    """The "here is what you could restore" tail, rendered once.

    Both places that report a review they could not find append this, and both
    would otherwise have to remember that an empty list is only an absence-claim
    when the directory actually resolved. One home for that distinction.
    """
    if problem:
        return (
            f"\n  Cannot list what IS restorable: {problem}. That is not the same"
            " as the archive being empty — fix the read before concluding a"
            " review's findings are gone."
        )
    if available:
        return "\n  Restorable now: " + ", ".join(available)
    return "\n  The archive holds nothing to restore."


def restore_refusal(prawduct_dir: Path, present: list[str], active: bool) -> str:
    """Why a restore is refused, and the ONE command that clears the way.

    Restoring writes an archived review's manifest and partials into the
    partials directory. Doing that over files already there merges two reviews
    into one directory — precisely the mis-attribution review-id keying exists to
    make impossible — so restore refuses instead of writing.

    **The remedy is chosen by what is on disk, and one function owns the whole
    message** so no call site can lead with advice that does not reach the state.
    `critic-end` clears the MARKER only: naming it while files are present would
    send the caller straight back to an identical refusal, which is the
    failure mode the sibling dispatch refusal was rewritten to avoid. So files
    present ⇒ consolidate (when the roster is complete and the work is worth
    recording) or discard (otherwise); marker only ⇒ `critic-end`.
    """
    if not present:
        return (
            "refusing — a Critic review is active in this worktree, and restoring\n"
            "  would put a second review's files where that one's belong.\n"
            "  No partials are on disk yet, so clearing the marker is enough:\n"
            "    prawduct-hook critic-end"
        )
    state, missing = pending_state(prawduct_dir)
    if state == "complete":
        remedy = (
            "  On disk: every reviewer has reported. That review is FINISHED and needs\n"
            "  only consolidation — record it first, then restore:\n"
            "    prawduct-hook critic-consolidate"
        )
    else:
        if state == "incomplete":
            waiting = f" still waiting on {', '.join(missing)}"
        else:
            # Same one-fact-many-carriers defect the long reading carried
            # (#676), in miniature: "no readable dispatch manifest" was printed
            # for an ABSENT manifest and for a stale-schema one that parses
            # fine. This surface wants a phrase, not a paragraph, so it derives
            # a short one from the same classifier rather than re-deciding.
            condition, _detail, _m = manifest_condition(prawduct_dir)
            waiting = {
                MANIFEST_STALE_SCHEMA: " a dispatch manifest from an older prawduct",
                MANIFEST_CORRUPT: " a dispatch manifest that is not valid JSON",
            }.get(condition, " no dispatch manifest")
        remedy = (
            f"  On disk:{waiting}. To set that review aside — archived, never deleted\n"
            "  outright — and free the directory:\n"
            "    prawduct-hook critic-discard\n"
            "  (`critic-end` clears the marker only; these files would still be here.)"
        )
    live = " (a review is also still marked active)" if active else ""
    # Says what is THERE, not whose it is. The obvious phrasing — "files from
    # another review" — is false in the path a caller reaches most often: an
    # operator re-running restore to check it worked, or retrying after a
    # consolidation that fail-closed, meets this message about the very files
    # they just restored. The remedy is right in that path either way; the
    # headline was the only part that was not.
    return (
        f"refusing — {len(present)} file(s) are already in the partials\n"
        f"  directory{live}. Restoring on top would put two reviews' files in one\n"
        "  directory, which is the mis-attribution restoring by id exists to avoid.\n"
        "\n"
        + remedy
    )


def restore_review(prawduct_dir: Path, review_id: str) -> dict:
    """Copy an archived review's manifest + partials back so it can consolidate
    AS ITSELF. The inverse of :func:`_archive_leftovers`, and adjacent to it so
    the write and its undo stay in one place.

    **Restores the review as itself, and that is the whole point.** The recovery
    this replaces copied an archived review's partials into the CURRENT review's
    directory; a partial bound only to the commit it reviewed was schema- and
    commit-valid against whatever manifest was there, so one review's findings
    were recorded under another's id. That copy is now inert — correctly, because
    it was always a mis-attribution — and the honest replacement brings the
    manifest back alongside the partials. The same keying that makes the
    mis-attributing copy impossible is what makes this round trip lossless: a
    restored set is self-identifying.

    **Copies, never moves.** The archive is the last trace an unconsolidated
    review ever ran (:func:`_archive_leftovers` exists for exactly that). A
    restore that consumed it would mean a restored-then-swept review leaves
    nothing at all.

    Returns ``{"status": "ok", ..., "consolidatable", "blocked_reason"}`` or
    ``{"status": "error", "kind", "reason"}`` — ``kind`` is ``pending``
    (something is in the way), ``unknown`` (no such archived set), ``unusable``
    (the set is there but holds nothing readable) or ``write-failed`` (the
    destination refused the copy). A successful restore whose set predates this
    hook is ``status: ok`` with ``consolidatable: False``: the files ARE back,
    which is the operation asked for, and the thing that cannot happen next is
    named rather than discovered. Per project convention the failure is a return
    value, not an exception; the CLI renders it.
    """
    pdir = partials_dir(prawduct_dir)
    try:
        present = sorted(p.name for p in pdir.iterdir() if p.is_file())
    except OSError:
        present = []
    # Asking only. `review_active` cannot remove a marker, so refusing here can
    # never also decide that a crashed review is over — which matters because the
    # Stop hook's abandoned-review branch is gated on that marker.
    active, _age = critic_marker.review_active(prawduct_dir)
    if present or active:
        return {
            "status": "error",
            "kind": "pending",
            "reason": restore_refusal(prawduct_dir, present, active),
        }

    available, archive_problem = archived_reviews(prawduct_dir)
    # Same gate the archive's own directory name goes through, for the same
    # reason: this id arrives from a caller and becomes a path segment, so
    # `../../x` walks out of the archive and an absolute one replaces the base.
    src = archive_dir(prawduct_dir) / review_id
    if not _path_component_safe(review_id) or not src.is_dir():
        return {
            "status": "error",
            "kind": "unknown",
            "reason": (
                f"no archived review named {review_id!r}."
                + archive_listing(available, archive_problem)
            ),
        }

    try:
        children = sorted(c for c in src.iterdir() if c.is_file())
    except OSError as exc:
        return {
            "status": "error",
            "kind": "unusable",
            "reason": f"the archived set {review_id!r} is unreadable ({exc}).",
        }
    if not children:
        return {
            "status": "error",
            "kind": "unusable",
            "reason": f"the archived set {review_id!r} holds no files to restore.",
        }

    # All-or-nothing. A copy that dies halfway leaves files in the partials
    # directory, and every subsequent restore reads those as "another review is
    # in the way" and refuses — a failure that converts itself into the refusing
    # state. Nothing re-runs this transition on the caller's behalf, so it has to
    # undo its own leavings rather than rely on a retry that would meet a
    # different refusal than the one that fired.
    written: list[Path] = []
    try:
        pdir.mkdir(parents=True, exist_ok=True)
        for child in children:
            dest = pdir / child.name
            shutil.copy2(child, dest)
            written.append(dest)
    except OSError as exc:
        for path in written:
            try:
                path.unlink()
            except OSError:
                pass
        return {
            "status": "error",
            "kind": "write-failed",
            "reason": (
                f"could not restore {review_id!r} ({exc}) — the partially copied "
                "files were removed, so the archive is still the only copy."
            ),
        }
    # **Whether the restored set can actually be recorded, decided here rather
    # than left to the caller to discover.** Filename presence is not the
    # question — a manifest can be present and still unconsolidatable, and the
    # reachable case is the upgrade this release IS: a set archived by v3.2.6
    # carries no ``rendezvous``, so `consolidate` fail-closes on it. Telling an
    # operator "run critic-consolidate" and letting them meet that refusal would
    # hand them a remedy that cannot reach the state — the exact failure this
    # subsystem's refusals were rewritten to stop producing.
    #
    # Asked by running the consolidator's OWN validator rather than re-deriving
    # the shape here, so this never becomes a second opinion about what a usable
    # manifest is.
    restored_manifest = pdir / MANIFEST_NAME
    if MANIFEST_NAME not in {c.name for c in children}:
        usable, why = False, "the archived set carries no dispatch manifest"
    else:
        try:
            usable, why = validate_manifest(json.loads(restored_manifest.read_text()))
        except (OSError, json.JSONDecodeError) as exc:
            usable, why = False, f"its manifest is unreadable ({exc})"
    return {
        "status": "ok",
        "id": review_id,
        "source": str(src),
        "restored": [c.name for c in children],
        "consolidatable": usable,
        # Advice fails soft, not silent: when the set cannot be recorded the CLI
        # says WHY and what the files are still good for, rather than implying a
        # consolidation is waiting.
        "blocked_reason": "" if usable else why,
    }


#: The keys :func:`_mark_cache_superseded` owns. Named once so the marker is
#: re-stamped rather than stacked when a re-dispatch marks an already-marked
#: record, and so a reader can strip them mechanically.
_SUPERSEDED_KEYS = ("superseded_by", "superseded_at", "superseded_notice")


def _mark_cache_superseded(prawduct_dir: Path, review_id: str) -> bool:
    """Stamp the derived findings view as PREDATING the review being dispatched.

    The partials half of this is solved by :func:`_archive_leftovers`: a
    review's working files are moved aside at dispatch, so nothing from the
    previous review is left where the current one's belong. The derived view
    got no such treatment — it survived every dispatch carrying nothing that
    marked it stale, so between ``critic-begin`` and the consolidation that
    regenerates it a reader met the PREVIOUS review's findings in a file that
    looked exactly like the current one's. That file is the one surface the
    builder is guaranteed to meet (see :data:`_BATCH_FIX_DIRECTIVE`), which is
    what made the ambiguity expensive: the framework answered it procedurally,
    by asking the builder to reason about whether what it was holding was
    current.

    **Mark, never delete.** Deleting at dispatch is the obvious fix and it is
    wrong: :func:`_prior_review_fact` reads this file's ``fact_id`` to anchor a
    ``verify-resolutions`` delta. The steady-state sequence would survive
    (begin reads, deletes; consolidate regenerates), but a review WAIVED or
    ABANDONED before consolidating would leave the next verify with no anchor
    at all — where today it correctly anchors to the last completed review. So
    deletion trades a cosmetic ambiguity for a lost anchor. Everything except
    the marker keys is preserved byte-for-byte.

    **The marker states a fact about the record, not a liveness claim.**
    "A review is in flight" would go false on its own: a dispatched review
    expires by TTL and is swept at a session boundary thereafter, and neither
    path passes through here to retract anything. "Review X was dispatched after this
    record was written, so this is not X's result" stays true forever, and a
    reader that meets it after an abandoned review learns exactly why the
    newest record is older than it expected. Consolidation rewrites the whole
    record from the fact, so the keys clear themselves on the normal path.

    Fail-soft in every direction — the view is advisory, and a dispatch must
    never be blocked by it. Returns whether the marker was written.
    """
    cache = prawduct_dir / ".critic-findings.json"
    try:
        # ValueError covers JSONDecodeError AND the UnicodeDecodeError a
        # byte-truncated cache raises from read_text() — same pair
        # `critic_findings_note` reads this file behind.
        record = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # No cache yet (first review in this repo), or one nothing can parse.
        # Either way there is no record to make honest and nothing to lose.
        return False
    if not isinstance(record, dict):
        return False
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prior_id = record.get("fact_id") or "an earlier review"
    marker = {
        "superseded_by": review_id,
        "superseded_at": now,
        "superseded_notice": (
            f"SUPERSEDED — review {review_id} was dispatched at {now}, AFTER"
            " this record was written. Everything below (findings, summary,"
            f" next_action) is the EARLIER review {prior_id} and is NOT"
            f" {review_id}'s result. Run `prawduct-hook critic-consolidate`"
            " once that review's reviewers have reported; it regenerates this"
            " file and these keys disappear. If it was abandoned instead, this"
            f" record is still the newest completed review — {prior_id} is a"
            " live fact_id either way."
        ),
    }
    # Marker keys FIRST: a reader meets them before the findings and the
    # `next_action` they qualify. Rebuilt from the record with any previous
    # marker dropped, so a re-dispatch re-stamps rather than stacks.
    rest = {k: v for k, v in record.items() if k not in _SUPERSEDED_KEYS}
    try:
        # Same form consolidate writes this file in, so a marked record and a
        # regenerated one differ only by the marker keys.
        atomic_write_text(cache, json.dumps({**marker, **rest}, indent=2))
    except OSError as exc:
        # Name the reason before degrading — a silent skip makes "why does the
        # stale view look current?" undiagnosable after the fact, which is the
        # very question this marker exists to answer.
        print(
            f"critic-begin: could not mark {cache.name} superseded ({exc}) — "
            "it still holds the PREVIOUS review's findings",
            file=sys.stderr,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Dispatch (critic-begin) — code writes the manifest; the model never does.
# ---------------------------------------------------------------------------


def _derive_roster(
    mode_token: str, files_changed: list[str], prawduct_dir: Path
) -> tuple[list[str], str]:
    """The roster this dispatch requires, plus the rationale (Q7 debugging).

    Risk surface first, judgeable volume second — see the roster config block
    for the replay that ordered them that way.
    """
    if mode_token in ("chunk", "verify-resolutions"):
        return list(SINGLE_PASS_ROSTER), f"mode={mode_token} is always single-pass"

    from . import coverage_algebra, risk  # noqa: PLC0415 — lazy; keeps the import graph flat

    touched, why = risk.paths_touch_risk_surface(prawduct_dir, files_changed)
    if touched:
        return list(COORDINATOR_ROSTER), (
            f"mode={mode_token}, risk surface touched: {why} — coordinator"
        )

    nj = len(coverage_algebra.judgeable_files(files_changed))
    if nj >= COORDINATOR_JUDGEABLE_THRESHOLD:
        return list(COORDINATOR_ROSTER), (
            f"mode={mode_token}, no risk surface, {nj} judgeable file(s) >= "
            f"{COORDINATOR_JUDGEABLE_THRESHOLD} — coordinator"
        )

    # "No risk surface matched" means low risk only if this repo HAD a signal to
    # give. With no declaration it means we learned nothing — and falling
    # through on judgeable volume alone would silently adopt the rule the replay
    # rejected. Keep the previous escalator until the repo says where its risk
    # lives.
    if not risk.has_product_risk_declaration(prawduct_dir):
        n = len(files_changed)
        if n >= COORDINATOR_FILE_THRESHOLD:
            return list(COORDINATOR_ROSTER), (
                f"mode={mode_token}, no declared risk surfaces, {n} file(s) >= "
                f"{COORDINATOR_FILE_THRESHOLD} — coordinator (prior rule retained)"
            )
        return list(SINGLE_PASS_ROSTER), (
            f"mode={mode_token}, no declared risk surfaces, {n} file(s) < "
            f"{COORDINATOR_FILE_THRESHOLD} — single-pass (prior rule retained)"
        )

    return list(SINGLE_PASS_ROSTER), (
        f"mode={mode_token}, {why}, {nj} judgeable file(s) < "
        f"{COORDINATOR_JUDGEABLE_THRESHOLD} — single-pass"
    )


def _prior_review_fact(project_dir: Path, prawduct_dir: Path) -> tuple[dict | None, str]:
    """The review fact a verify-resolutions pass anchors to, located via the
    derived cache's ``fact_id`` pointer (D7 — this is what the pointer is
    for). Returns ``(fact, "")`` or ``(None, reason)`` — the caller fails
    loud and the skill demotes to chunk/final.

    **The anchor must be an ancestor of HEAD.** The single-slot cache survives a
    branch switch, and a sibling branch's anchor still *resolves* in the shared
    object store — so without this the pass would anchor to a tree off this
    lineage and diff across the divergence, producing phantom findings over work
    this branch never touched. Fails closed: not-an-ancestor and any git failure
    both refuse, because an anchor we cannot place is one we cannot trust.
    """
    cache = prawduct_dir / ".critic-findings.json"
    try:
        data = json.loads(cache.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"no readable prior findings cache ({exc})"
    fact_id = data.get("fact_id") if isinstance(data, dict) else None
    if not isinstance(fact_id, str) or not fact_id.strip():
        return None, (
            "prior findings cache carries no fact_id — it predates the "
            "evidence store (a fresh review re-establishes coverage)"
        )
    store = evidence.read_facts(project_dir)
    for fact in evidence.facts_of_kind(store, "review"):
        if fact.get("id") != fact_id:
            continue
        body = fact.get("body") or {}
        # A dirty-tree review records no `head_commit`; its `dispatch_commit` is
        # the commit it was dispatched from, and that is the anchor to place.
        anchor = body.get("head_commit") or body.get("dispatch_commit")
        if isinstance(anchor, str) and anchor.strip():
            from . import critic_mode  # noqa: PLC0415 — lazy; avoids an import cycle

            if not critic_mode._commit_is_ancestor(project_dir, anchor):
                return None, (
                    f"prior review fact {fact_id!r} anchors at {anchor[:12]}, "
                    "which is not an ancestor of HEAD — it belongs to another "
                    "lineage (a branch switch, or rewritten history), so the "
                    "delta from it would span the divergence"
                )
        return fact, ""
    return None, f"prior review fact {fact_id!r} not found in the evidence store"


def begin_review(
    project_dir: Path,
    mode_token: str,
    chosen_by: str | None = None,
    chunk: str | None = None,
    scope: str | None = None,
    tier: str | None = None,
    force: bool = False,
) -> dict:
    """Derive and write the dispatch manifest for one review. All code.

    Returns ``{"status": "ok", "id", "roster", "path", "notes": [...],
    "cleared_leftovers": bool, "manifest": {...}}`` or ``{"status": "error",
    "reason", "kind"?}`` where ``kind == "scope-widened"`` tells the CLI to
    exit 2 (the skill's demote-to-a-full-review signal), or ``{"status":
    "no-review-needed", "reason", "free_files"}`` when the interval holds no
    judgeable file and no finding this mode could resolve — the CLI exits 3.
    That is a NO-OP, not a failure: the coverage gate already composes such an
    interval as a free edge, so the review would record a fact nothing needs.
    ``force=True`` dispatches anyway. A ``scope-widened`` result also carries
    ``fallback_mode`` — the full-review mode that covers the widened delta,
    named in ``reason`` so the re-dispatch does not have to guess it.

    Per-mode interval (design D8, chunk-03 refinements):

    - ``chunk``/``final`` — base = ``HEAD`` (the uncommitted diff), head =
      the captured working tree (D3 temp-index capture; non-mutating).
    - ``cumulative`` — base = merge-base(resolve-base, HEAD), head = ``HEAD``
      (the committed bundle; a dirty working tree is noted, not reviewed).
    - ``verify-resolutions`` — base = the prior review FACT's ``head_tree``,
      head = the captured working tree. Tree keying makes a dirty-tree
      verify sound (the v2 "commit first, then verify" rule dissolves).

    ``files_changed`` is uniformly ``git diff --name-only <base_tree>
    <head_tree>``, so the recorded snapshot and the D6 edge-validity check
    agree by construction.
    """
    verbose = MODE_TOKEN_TO_VERBOSE.get(mode_token)
    if verbose is None:
        return {
            "status": "error",
            "reason": (
                f"unknown mode token {mode_token!r} — expected one of "
                f"{sorted(MODE_TOKEN_TO_VERBOSE)}"
            ),
        }
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)

    # IN-FLIGHT GUARD — refuse rather than displace a review that is still live.
    # First, because everything below derives state that a refusal would waste,
    # and because the mutation this protects (`_archive_leftovers` + the manifest
    # overwrite, further down) is the single most destructive act against another
    # review. `active_dispatch_refusal` carries the full failure story.
    #
    # Two independent conditions, and the second is the one the observed
    # incidents needed:
    #
    #   (a) a live critic-active marker — reviewers are plausibly still running.
    #   (b) a COMPLETE roster on disk, at ANY age — finished work. Age tells you
    #       whether more reviewers are coming; it says nothing about whether
    #       already-written findings are worth keeping. The review destroyed in
    #       the 2026-08-05 report had all three partials written and was swept a
    #       minute later; a purely time-based guard would still have swept it had
    #       the dispatching agent waited the window out first.
    #
    # Keyed on the MARKER, not on the manifest's age, and that is load-bearing:
    # the standing contract (`test_begin_clears_leftover_partials`) is that an
    # orphaned partial from a waived or stale-failed review IS swept, and that
    # test writes its leftovers fresh — so file age cannot tell orphaned from
    # live, while the marker can. It is also why `_INFLIGHT_GRACE_MINUTES` is NOT
    # reused here despite #171 asking for it: that constant grades per-role
    # `.started` ages on the consolidate side, and the marker already carries its
    # own documented TTL for precisely this question. Reusing the number while
    # changing the signal would CREATE the second notion of "live" rather than
    # avoid it.
    # Refusing a dispatch is not the moment to decide a crashed review is over:
    # the Stop hook's abandoned-review branch is gated on `marker_present` and is
    # what prints the manual-recovery remedy, so a read that deleted on the way
    # past would strip that advice out of the subsystem at the first refused
    # dispatch past the TTL. `review_active` only asks; removal has one home
    # (`critic_marker.boundary_sweep`) and the explicit end/discard acts.
    active, age_s = critic_marker.review_active(prawduct_dir)
    roster_state, _missing = pending_state(prawduct_dir)
    if active or roster_state == "complete":
        return {
            "status": "error",
            "kind": "review-in-flight",
            "reason": active_dispatch_refusal(prawduct_dir, age_s, active),
        }

    # Which plan this review is OF. An unbounded `active_build_plan` has
    # attributed the manifest, the review fact and the ledger event to an
    # unrelated plan — with the pointer *correct* every time, which is why this
    # resolves around it rather than asking anyone to repoint it. Derived here,
    # in code, rather than left to the dispatching agent to read off the
    # pointer: that read is where the misattribution enters.
    from . import buildplan_refs  # noqa: PLC0415 — lazy; pulls the plan readers

    scope = (scope or "").strip() or None
    scope_chosen_by = "explicit-args" if scope else None
    if scope is None:
        scope = buildplan_refs.resolve_branch_plan(project_dir, prawduct_dir).scope
        scope_chosen_by = "branch-name" if scope else "not-resolved"

    capture = evidence.capture_tree(project_dir)
    if capture.get("status") != "ok":
        return {
            "status": "error",
            "reason": f"tree capture failed: {capture.get('reason', 'unknown')}",
        }
    dispatch_commit = capture.get("head_commit")
    if not dispatch_commit:
        return {
            "status": "error",
            "reason": "no HEAD commit — nothing to anchor a review to "
            "(commit an initial state first)",
        }

    notes: list[str] = []
    base_reviewed = None
    files_reviewed: list[str] | None = None
    # Findings a THIS-mode review could still resolve. Only verify-resolutions
    # records resolution facts, so it is the only mode that can carry a nonzero
    # value; for every other mode there is nothing outstanding that running it
    # would clear. Read by the free-interval refusal below, where it is the
    # conjunct that keeps the gate from deadlocking.
    pending_actionable = 0

    if mode_token in ("chunk", "final"):
        base_commit = dispatch_commit
        base_tree = capture["head_tree"]
        head_tree = capture["tree"]
        head_commit = dispatch_commit if capture["clean"] else None
    elif mode_token == "cumulative":
        from . import coverage  # noqa: PLC0415 — lazy; coverage pulls git helpers

        resolved = coverage.resolve_merge_base_tree(project_dir)
        if resolved["status"] != "ok":
            return {"status": "error", "reason": resolved["reason"]}
        base_commit = resolved["merge_base"]
        base_tree = resolved["tree"]
        head_commit = dispatch_commit
        head_tree = capture["head_tree"]  # the committed state, not the dirty tree
        base_reviewed = base_commit
        if not capture["clean"]:
            notes.append(
                "working tree dirty at cumulative dispatch — uncommitted "
                "changes are NOT in the reviewed scope"
            )
    else:  # verify-resolutions
        prior, reason = _prior_review_fact(project_dir, prawduct_dir)
        if prior is None:
            return {"status": "error", "reason": f"no prior review to verify: {reason}"}
        prior_body = prior.get("body") or {}
        base_tree = prior_body.get("head_tree")
        if not isinstance(base_tree, str) or not base_tree:
            return {
                "status": "error",
                "reason": f"prior review fact {prior.get('id')!r} records no head_tree",
            }
        base_commit = prior_body.get("head_commit")

        # Intent-aware head anchor (CRT-7H2W). verify-resolutions serves two gate
        # targets that DIVERGE once the working tree is dirty: the PR gate
        # composes to COMMITTED HEAD, the Stop-hook gate to the WORKING tree. A
        # single working-tree anchor left the PR gate ``uncovered`` whenever a
        # committed fix carried along a stray judgeable uncommitted file. Read
        # intent from git: if the builder COMMITTED content that differs from the
        # reviewed tree (the post-cumulative-fix / PR-gate case), anchor the
        # review edge at committed HEAD so it composes to the PR gate's target
        # and note-and-exclude any WIP, exactly like the cumulative branch.
        # Otherwise (fix-in-progress in a dirty tree) keep the working-tree
        # anchor so the Stop-hook gate composes and the PR gate legitimately
        # stays pending until the fix is committed — preserving CRT-4J8W
        # dirty-tree verify.
        #
        # Intent is TREE inequality, not the commit set. The two disagree in
        # exactly the case that bites: a review of a dirty tree vouches for the
        # commit that materializes it verbatim (`review-cycle.md` says so), and
        # that vouching commit makes a commit-set diff non-empty while the trees
        # are identical. The anchor then moved to committed HEAD, the delta
        # computed EMPTY, and the refusal below announced "nothing changed since"
        # over a working tree holding unreviewed work — a message that reads as
        # "everything is reviewed" while meaning "everything I chose to look at
        # is reviewed". A commit that changes no content is not a change of
        # intent, and now nothing treats it as one.
        #
        # Tree inequality has a SECOND reading, and it is the mirror image of the
        # one above rather than another instance of it. "The committed tree
        # differs from the tree the prior review saw" is true when a commit
        # landed AFTER that review (the anchor is BEHIND — the case this branch
        # was written for), and equally true when the prior review vouched for a
        # DIRTY tree and nothing has been committed since (the anchor is AHEAD).
        # The second is not an edge case: it is the ordinary shape of a
        # `chunk`-mode review, whose fact records `head_commit: null` and a
        # `head_tree` matching no commit. Read as a committed delta it INVERTS
        # the edge — base becomes the dirty snapshot that is ahead, head the
        # committed tree that is behind — so `files_changed` describes the fix
        # being deleted, `record_lint` grades pre-fix content, and, load-bearing,
        # the resolution facts are persisted against a tree in which none of the
        # fixes exist. Resolutions lift BLOCKING findings, so that is unsound
        # rather than merely noisy.
        #
        # The discriminator was already in the prior fact and simply not read: a
        # fact carrying no `head_commit` vouched for a working tree, and if HEAD
        # still stands where that review dispatched, nothing has been committed
        # since. (The fact spells the dispatch anchor `dispatch_commit`; the
        # manifest spells the same value `commit_reviewed`.)
        prior_dispatch = prior_body.get("dispatch_commit")
        anchor_is_ahead = (
            prior_body.get("head_commit") is None
            and isinstance(prior_dispatch, str)
            and bool(prior_dispatch)
            and prior_dispatch == dispatch_commit
        )
        committed_differs = capture["head_tree"] != base_tree and not anchor_is_ahead
        if committed_differs:
            head_tree = capture["head_tree"]  # committed HEAD — the PR-gate target
            head_commit = dispatch_commit
            if not capture["clean"]:
                notes.append(
                    "working tree dirty at verify-resolutions dispatch — anchored "
                    "to committed HEAD (a committed delta exists since the prior "
                    "review); uncommitted changes are NOT in the reviewed scope"
                )
        else:
            head_tree = capture["tree"]  # working tree — the Stop-hook target
            head_commit = dispatch_commit if capture["clean"] else None
            if not capture["clean"]:
                from . import coverage_algebra  # noqa: PLC0415 — lazy
                wip = (
                    evidence.tree_diff(project_dir, capture["head_tree"], capture["tree"])
                    or []
                )
                if coverage_algebra.judgeable_files(wip):
                    notes.append(
                        "working tree dirty with judgeable uncommitted files and no "
                        "committed delta since the prior review — this fact vouches "
                        "for the WORKING tree, but the cumulative/PR gate targets "
                        "committed HEAD, so it reads `uncovered` until you commit. "
                        "Commit this tree VERBATIM and no further pass is needed: the "
                        "commit carries the very tree this one vouched for. Only a "
                        "selective or further-edited commit leaves a gap to close"
                    )
        delta = evidence.tree_diff(project_dir, base_tree, head_tree)
        if delta is None:
            return {
                "status": "error",
                "reason": (
                    f"cannot diff prior reviewed tree {base_tree[:12]} against "
                    "the current tree (rewritten history?) — anchor unreliable"
                ),
            }
        prior_files = [
            f for f in (prior_body.get("files_reviewed") or []) if isinstance(f, str)
        ]
        if _scope_widened(len(delta), len(prior_files)):
            fallback, why = _widened_fallback_mode(
                project_dir, capture["head_tree"], committed_differs
            )
            return {
                "status": "error",
                "kind": "scope-widened",
                "fallback_mode": fallback,
                "reason": (
                    f"scope-widened: {len(delta)} files changed since the prior "
                    f"review of {len(prior_files)} — a partial re-review would "
                    f"mislead. Re-dispatch as `{fallback}`: {why}."
                ),
            }
        prior_counts = prior_body.get("counts") or {}
        actionable = (prior_counts.get("blocking") or 0) + (
            prior_counts.get("warning") or 0
        )
        pending_actionable = actionable
        if not delta and not actionable:
            # Name the tree that was compared. Under the tree-inequality anchor
            # above, an empty delta means the working tree AND committed HEAD
            # both hold exactly the reviewed content — so this really is
            # "nothing changed". The message says which tree it read anyway,
            # because the previous wording was true of the anchor and false of
            # the repo, and nothing in it let a builder tell the difference.
            anchored = "committed HEAD" if committed_differs else "the working tree"
            return {
                "status": "error",
                "reason": (
                    "nothing to verify: the prior review has no blocking/warning "
                    f"findings, and {anchored} ({head_tree[:12]}) is the same tree "
                    f"it reviewed ({base_tree[:12]})"
                ),
            }
        files_reviewed = list(prior_files)
        for f in delta:
            if f not in files_reviewed:
                files_reviewed.append(f)

    files_changed = evidence.tree_diff(project_dir, base_tree, head_tree)
    if files_changed is None:
        return {
            "status": "error",
            "reason": f"cannot diff {base_tree[:12]}..{head_tree[:12]}",
        }
    if not files_changed and mode_token != "verify-resolutions":
        return {
            "status": "error",
            "reason": (
                f"empty diff for mode {mode_token!r} — nothing to review "
                "between the base and the current state (already committed? "
                "a committed bundle is cumulative's scope)"
            ),
        }
    # GATE AS DISPATCHER — do not spend a reviewer on a review the gate would
    # not require. `coverage_algebra.is_judgeable_path` already decides which
    # paths need coverage, and `coverage_verdict` already grants a FREE EDGE to
    # an interval holding none; until this check the predicate was consulted
    # only when GRADING coverage, so `check-cumulative-critic` could tell you a
    # round was unnecessary — but only after you had paid for it. Measured
    # 2026-08-06: 62 of 492 review facts (12.6%, ~5.2 opus-hours) covered
    # entirely non-judgeable intervals.
    #
    # THE SAFETY ARGUMENT: this refuses only what the gate would already pass.
    # Same predicate, same inputs, moved upstream of the cost — so nothing that
    # could not already merge becomes mergeable, and this is not a new escape
    # hatch. Do NOT re-key it on "looks like docs": `skills/`, `methodology/`,
    # `templates/` and root `CLAUDE.md` are judgeable `.md`, and a private
    # notion of "docs" is how a skip-gate and its gate drift apart.
    #
    # BOTH conjuncts are load-bearing. Without the first, reviews of real code
    # are refused. Without the second the gate DEADLOCKS: a `blocked` verdict's
    # only remedy is a verify-resolutions pass, and refusing that pass over a
    # free interval would leave findings raised on prose permanently
    # unresolvable, with no command that clears them.
    from . import coverage_algebra  # noqa: PLC0415 — lazy; keeps the import graph flat

    if (
        not force
        and not coverage_algebra.judgeable_files(files_changed)
        and not pending_actionable
    ):
        # Record the firing. The norm this control ships under ("a control
        # names the yield it expects and emits it observably") is what makes
        # this mandatory rather than nice: the yield argument above cites a
        # measurement taken BEFORE the guard existed, and only a record of
        # actual firings can ever falsify it — or answer the question that
        # retires the guard, "did it ever refuse a round that turned out to be
        # needed?". Sink ruling and its four reasons: `evidence.append_guard_refusal`.
        #
        # SOFT: the refusal is correct whether or not the record lands, so a
        # store failure must not turn a correct exit-3 into an error. Not
        # silent, though — a degraded record that vanishes leaves the yield
        # question looking answered at zero.
        recorded = evidence.append_guard_refusal(
            project_dir,
            "critic-dispatch-free-interval",
            {
                # Nested, not spread across the body's top level, because a
                # top-level base_tree/head_tree is the shape a coverage EDGE
                # has. Keeping the interval one level down means no reader that
                # walks bodies looking for edges can mistake a refusal for one.
                "interval": {"base_tree": base_tree, "head_tree": head_tree},
                "mode": mode_token,
                "free_files": list(files_changed),
                "scope": scope,
                "chunk": chunk,
                "branch": gitstate.current_branch(project_dir),
                "dispatch_commit": dispatch_commit,
            },
        )
        if recorded.get("status") != "appended":
            print(
                "critic-begin: the refusal is correct but was NOT recorded "
                f"({recorded.get('reason', 'unknown')}) — this firing is missing "
                "from `prawduct-hook evidence list --kind guard-refusal`, so read "
                "that query as a lower bound.",
                file=sys.stderr,
            )
        return {
            "status": "no-review-needed",
            "reason": (
                f"no judgeable file in {base_tree[:12]}..{head_tree[:12]} — the "
                "coverage gate already composes this interval as a free edge, so "
                "a review would record a fact nothing needs"
            ),
            "free_files": list(files_changed),
            "recorded": recorded.get("status") == "appended",
        }

    if files_reviewed is None:
        files_reviewed = list(files_changed)

    roster, roster_chosen_by = _derive_roster(mode_token, files_changed, prawduct_dir)
    review_id = mint_review_id()

    # Machine-verified record checks, computed HERE so the reviewers are told
    # the answers rather than re-deriving them (record-class findings were 57%
    # of one day's review output on 2026-07-29, and none of them needed
    # judgment). Advisory: the result rides the manifest for the builder, and
    # nothing downstream gates on it. A lint that cannot run reports itself
    # ``unchecked`` rather than empty — see ``record_lint``.
    from . import record_lint  # noqa: PLC0415 — lazy; keeps the import graph flat
    lint = record_lint.lint_records_safe(
        project_dir, prawduct_dir, files_changed, base_tree, head_tree, chunk, scope
    )

    # Answers already given about findings in these files, so a fresh review can
    # decline to re-litigate them. Dispositions have been facts for a while;
    # nothing put them where a REVIEWER could see one, so a cumulative
    # dispatched after an `--accept` handed its reviewers a diff and no memory.
    # Advisory like `record_lint` beside it: it rides the manifest, and nothing
    # downstream gates on it.
    from . import dispositions  # noqa: PLC0415 — lazy; keeps the import graph flat

    try:
        priors = dispositions.prior_dispositions(
            evidence.read_facts(project_dir), files_changed, scope=scope
        )
    except (OSError, ValueError, TypeError) as exc:  # pragma: no cover - defensive
        # A block that cannot be built must not cost a review its dispatch. Loud,
        # though: an empty block and an unbuilt one are different facts about the
        # world, and a reviewer told "nothing was dispositioned here" when the
        # join failed would be told something false. This catches an unexpected
        # shape; the two DEGRADED store states are returned rather than raised,
        # so `prior_dispositions` answers those itself, in the same words.
        priors = dispositions._unavailable(f"{type(exc).__name__}: {exc}")

    manifest = {
        "id": review_id,
        "mode": verbose,
        "mode_chosen_by": (chosen_by or "").strip() or "not-recorded",
        "roster": roster,
        "roster_chosen_by": roster_chosen_by,
        # Where each reviewer writes, resolved HERE so the filename shape has
        # exactly one home. Every instruction surface reads its role's entry
        # instead of composing the name, which is what keeps a change to the
        # shape (this one, and the next) out of four prose files.
        "rendezvous": _rendezvous(project_dir, prawduct_dir, roster, review_id),
        "commit_reviewed": dispatch_commit,
        "base_commit": base_commit,
        "base_tree": base_tree,
        "head_tree": head_tree,
        "head_commit": head_commit,
        "files_changed": files_changed,
        "files_reviewed": files_reviewed,
        "tier": tier,
        "scope": scope,
        "scope_chosen_by": scope_chosen_by,
        "chunk": chunk,
        "base_reviewed": base_reviewed,
        # Make the resolved target VISIBLE so a wrong-tree review is obvious
        # instead of silent (PDT-WT9K). ``branch`` is None on a detached HEAD.
        "worktree": str(project_dir),
        "branch": gitstate.current_branch(project_dir),
        "record_lint": lint,
        "prior_dispositions": priors,
        # Which seed `capture_tree` used for THIS dispatch. The stderr line a
        # degraded capture prints lives only in scrollback, and the question it
        # answers — did the fast seed engage, or is a slow capture still slow —
        # is asked after the fact, by someone verifying the fix on the machine
        # that reported the symptom. So it rides the durable record the dispatch
        # already writes. Advisory: nothing gates on it, and an older manifest
        # without the key is still valid.
        "seed": capture.get("seed"),
    }
    ok, reason = validate_manifest(manifest)
    if not ok:
        # A manifest this function derived failing its own validator is a bug
        # here — fail loudly rather than dispatch a review that can never
        # consolidate.
        return {"status": "error", "reason": f"internal error — derived manifest invalid: {reason}"}

    cleared = False
    archived: Path | None = None
    pdir = partials_dir(prawduct_dir)
    if pdir.is_dir():
        # A manifest still on disk here belongs to a review that never
        # consolidated (consolidate removes everything on success). Deleting
        # it would erase the only trace that review ran — archive first, then
        # sweep whatever archiving left behind.
        # No note appended for the archive: the CLI already renders
        # `archived_leftovers` as its own stdout line, and a note here printed
        # the same fact twice (once per channel).
        archived = _archive_leftovers(prawduct_dir)
        remove_partials(prawduct_dir)
        cleared = True
    # The same act for the derived view: the leftover partials are moved aside,
    # and the leftover FINDINGS say so rather than reading as this review's.
    # After the anchor read above (`_prior_review_fact` runs on the
    # verify-resolutions branch and needs the record as it stands), and after
    # the manifest validated — nothing is marked for a dispatch that fails.
    superseded = _mark_cache_superseded(prawduct_dir, review_id)
    pdir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path(prawduct_dir), json.dumps(manifest, indent=2))

    return {
        "status": "ok",
        "id": review_id,
        "roster": roster,
        "path": str(manifest_path(prawduct_dir)),
        "notes": notes,
        "cleared_leftovers": cleared,
        "archived_leftovers": str(archived) if archived else None,
        "superseded_findings": superseded,
        "manifest": manifest,
    }


# ---------------------------------------------------------------------------
# Schema validation — every validator returns (ok, reason) so the caller can
# name the specific defect. Fail-closed: a malformed record is NEVER treated as
# a complete review.
# ---------------------------------------------------------------------------


def _nonempty_str(val) -> bool:
    return isinstance(val, str) and bool(val.strip())


def _nonempty_str_list(val) -> bool:
    return isinstance(val, list) and bool(val) and all(_nonempty_str(v) for v in val)


def _str_list(val) -> bool:
    """A list — possibly empty — of non-empty strings."""
    return isinstance(val, list) and all(_nonempty_str(v) for v in val)


def validate_partial(data) -> tuple[bool, str]:
    """Validate a single reviewer partial.

    Schema: ``{role, goals, dispatch_id, commit_reviewed, model?,
    duration_seconds?, findings:[{name, goal, severity, recommendation, files?}],
    resolutions?:[{review_id, fid, disposition, rationale?}], summary}``.
    ``model``/``duration_seconds`` are nullable telemetry; everything else is
    load-bearing. ``severity`` must be one of the known vocabulary so a typo
    can't silently persist as a non-blocking finding. ``resolutions`` is the
    verify-resolutions judgment payload (D5): ``disposition`` is ``fixed`` or
    ``waived``, and ``waived`` REQUIRES a non-empty ``rationale`` (R7 — a
    waiver carries its justification).

    ``dispatch_id`` is the id of the review that dispatched this reviewer, and
    it is deliberately NOT named ``review_id``: ``resolutions[].review_id`` in
    this same record means the *prior* review whose finding is being
    dispositioned. Two referents under one token, in a record a model writes
    from prose, is the seam where an identifier degrades silently — so the two
    get different names, and this one matches the module's existing
    ``dispatch_commit``/``dispatch_age_minutes`` vocabulary.
    """
    if not isinstance(data, dict):
        return False, "partial is not a JSON object"
    if not _nonempty_str(data.get("role")):
        return False, "missing/empty 'role'"
    if not _nonempty_str(data.get("dispatch_id")):
        return False, (
            "missing/empty 'dispatch_id' — a partial must name the review that "
            "dispatched it (the manifest's 'id')"
        )
    goals = data.get("goals")
    if not (_nonempty_str(goals) or _nonempty_str_list(goals)):
        return False, "missing 'goals' (non-empty string or list)"
    if not _nonempty_str(data.get("commit_reviewed")):
        return False, "missing/empty 'commit_reviewed'"
    if not _nonempty_str(data.get("summary")):
        return False, "missing/empty 'summary'"
    model = data.get("model")
    if model is not None and not _nonempty_str(model):
        return False, "'model' must be a non-empty string or null"
    dur = data.get("duration_seconds")
    if dur is not None and (not isinstance(dur, (int, float)) or isinstance(dur, bool)):
        return False, "'duration_seconds' must be a number or null"
    findings = data.get("findings")
    if not isinstance(findings, list):
        return False, "'findings' must be a list"
    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            return False, f"finding[{idx}] is not an object"
        for field in ("name", "goal", "severity", "recommendation"):
            if not _nonempty_str(f.get(field)):
                return False, f"finding[{idx}] missing/empty '{field}'"
        if f["severity"] not in _SEVERITY_RANK:
            return False, (
                f"finding[{idx}] severity {f['severity']!r} not in "
                f"{sorted(_SEVERITY_RANK)}"
            )
        # ``files`` is optional attribution, normalized away downstream: a
        # blank/non-string element is dropped in ``merge_findings`` and an
        # all-blank list collapses to no ``files`` at all — exactly like ``[]``
        # or an omitted key. Reject only a value that is not a list; a single
        # malformed element must never fail-close the WHOLE consolidation over
        # optional attribution (a reviewer's ``files:[""]`` on a file-less
        # META-finding otherwise bricked every review).
        if "files" in f and not isinstance(f["files"], list):
            return False, f"finding[{idx}] 'files' must be a list"
    resolutions = data.get("resolutions")
    if resolutions is not None:
        if not isinstance(resolutions, list):
            return False, "'resolutions' must be a list"
        for idx, r in enumerate(resolutions):
            if not isinstance(r, dict):
                return False, f"resolution[{idx}] is not an object"
            for field in ("review_id", "fid"):
                if not _nonempty_str(r.get(field)):
                    return False, f"resolution[{idx}] missing/empty '{field}'"
            if r.get("disposition") not in _RESOLUTION_DISPOSITIONS:
                return False, (
                    f"resolution[{idx}] disposition {r.get('disposition')!r} "
                    f"not in {sorted(_RESOLUTION_DISPOSITIONS)}"
                )
            rationale = r.get("rationale")
            if rationale is not None and not _nonempty_str(rationale):
                return False, f"resolution[{idx}] 'rationale' must be a non-empty string or null"
            if r["disposition"] == "waived" and not _nonempty_str(rationale):
                # R7 — a waiver carries its justification. The requirement id
                # stays here; the message states the reason instead, because
                # an operator downstream cannot resolve "R7".
                return False, (
                    f"resolution[{idx}] disposition 'waived' requires a non-empty "
                    "'rationale' — a waived finding must record why it was waived"
                )
    return True, ""


def validate_manifest(data) -> tuple[bool, str]:
    """Validate the dispatch manifest (v3 shape — written by ``begin_review``
    only).

    Required: ``id``, verbose ``mode``, ``mode_chosen_by``, ``roster``,
    ``roster_chosen_by``, ``rendezvous`` (one ``{partial, started}`` entry per
    roster role — the resolved write paths, so no instruction surface has to
    spell the filename shape), ``commit_reviewed``, ``base_tree``, ``head_tree``,
    non-empty ``files_reviewed``, ``files_changed`` (a list, possibly empty —
    a same-tree verify-resolutions pass legitimately changes nothing).
    Nullable: ``base_commit``/``head_commit`` (a prior review of a dirty tree
    has no commit), ``tier``/``scope``/``scope_chosen_by``/``chunk``/``model``/
    ``base_reviewed``, ``worktree``/``branch`` (visibility fields; ``branch`` is
    None on a detached HEAD — PDT-WT9K).

    The v2 (model-written) manifest shape carries none of the v3 interval
    fields, so it fails here loudly — a stale cached skill hand-authoring a
    manifest can no longer produce something consolidation trusts (CRT-W2NV
    regression pin).
    """
    from . import gates  # noqa: PLC0415 — lazy; gates is heavy and one-way

    if not isinstance(data, dict):
        return False, "manifest is not a JSON object"
    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in gates._CRITIC_MODE_VALUES:
        return False, (
            f"'mode' must be a verbose persistence string "
            f"({sorted(gates._CRITIC_MODE_VALUES)}), got {mode!r}"
        )
    for req in ("id", "mode_chosen_by", "roster_chosen_by", "commit_reviewed",
                "base_tree", "head_tree"):
        if not _nonempty_str(data.get(req)):
            return False, f"missing/empty '{req}'"
    if not _nonempty_str_list(data.get("roster")):
        return False, "missing 'roster' (non-empty list of role names)"
    # The id and every role become filename components of the rendezvous paths.
    # Refused here rather than at the paths: a validator returns a verdict the
    # caller can name, while a raise inside path construction would turn a
    # malformed record into a crash on the session-end backstop's read.
    for label, value in [("id", data["id"])] + [
        ("roster entry", r) for r in data["roster"]
    ]:
        # The RAW value, not a stripped copy: what is checked has to be what
        # becomes the filename, or the check grades a string nothing writes.
        if not _path_component_safe(value):
            return False, (
                f"{label} {value!r} is not usable as a filename component "
                "(no '/', '\\' or '..')"
            )
    rendezvous = data.get("rendezvous")
    if not isinstance(rendezvous, dict):
        return False, (
            "missing 'rendezvous' (per-role partial/started paths). A manifest "
            "without it was written by a hook older than this one. If this is the "
            "PENDING review, the sequence is: reload the plugin (/reload-plugins, "
            "or restart the session), then `prawduct-hook critic-end` to abandon "
            "it, then dispatch again — a bare re-dispatch is refused while the "
            "marker is live, so the abandon step is not optional. If this is a "
            "RESTORED review, no dispatch can record it: a dispatch reviews the "
            "tree now, not what that review read"
        )
    if sorted(rendezvous) != sorted(data["roster"]):
        return False, (
            f"'rendezvous' covers {sorted(rendezvous)} but the roster is "
            f"{sorted(data['roster'])} — every role needs exactly one entry"
        )
    for role, entry in rendezvous.items():
        if not isinstance(entry, dict):
            return False, f"rendezvous[{role!r}] is not an object"
        for key in ("partial", "started"):
            if not _nonempty_str(entry.get(key)):
                return False, f"rendezvous[{role!r}] missing/empty {key!r}"
    if not _nonempty_str_list(data.get("files_reviewed")):
        return False, "missing 'files_reviewed' (non-empty list)"
    if not _str_list(data.get("files_changed")):
        return False, "'files_changed' must be a list of non-empty strings"
    for opt in ("base_commit", "head_commit", "tier", "scope", "scope_chosen_by",
                "chunk", "model", "base_reviewed", "worktree", "branch"):
        val = data.get(opt)
        if val is not None and not _nonempty_str(val):
            return False, f"'{opt}' must be a non-empty string or null"
    return True, ""


# ---------------------------------------------------------------------------
# Pending-state inspection — read-only, no git. The session-end backstop
# uses this to decide self-heal vs. block-naming-the-missing-reviewer without
# re-implementing the read.
# ---------------------------------------------------------------------------


#: The four ways the manifest file can present itself, as
#: :func:`manifest_condition` reports them. ``pending_state`` collapses the
#: middle two into its own ``"unreadable"`` — see that function for why the
#: collapse is right THERE and wrong in a message.
MANIFEST_ABSENT = "absent"
MANIFEST_CORRUPT = "corrupt"
MANIFEST_STALE_SCHEMA = "stale-schema"
MANIFEST_VALID = "valid"
#: The fifth value, and it lives HERE rather than at a call site. A caller whose
#: classify call raised needs a word for "could not tell", and the first cut let
#: ``cmd_stop`` invent one locally — re-opening in miniature the exact split this
#: module exists to close (a vocabulary is not shared by being mostly shared).
#: :func:`manifest_condition` never returns it; only a caller that caught an
#: exception does.
MANIFEST_UNKNOWN = "unknown"

#: A validation reason can be a paragraph. ``validate_manifest``'s
#: ``missing 'rendezvous'`` branch — the shape a pre-3.3.4 archive actually has —
#: runs ~700 characters and prescribes its OWN recovery sequence. Embedded
#: mid-sentence in an operator message that then gives a different remedy, that
#: is one disk with two recovery stories, which is the defect this module exists
#: to end, arriving through a borrowed string instead of a re-derived fact.
#: Message surfaces take :func:`short_detail`; logs and tests can have it whole.
_DETAIL_MAX_CHARS = 120


def short_detail(detail: str) -> str:
    """A message-safe one-clause form of a validation reason.

    Keeps the first sentence/clause and hard-caps the length, so a reason that
    carries its own embedded remedy cannot smuggle it into a surface that is
    about to name a different one. Returns ``""`` unchanged for no detail.
    """
    if not detail:
        return ""
    first = detail.split("\n", 1)[0].strip()
    # Cut at the first sentence end that is not a version dot ("v3.2.6").
    for end in (". ", "; "):
        head, sep, _rest = first.partition(end)
        if sep and len(head) >= 20:
            first = head
            break
    if len(first) > _DETAIL_MAX_CHARS:
        first = first[: _DETAIL_MAX_CHARS - 1].rstrip() + "…"
    return first


def anything_worth_keeping(prawduct_dir: Path) -> tuple[bool, str]:
    """Is there reviewer output here worth preserving, and the clause saying so.

    **The one home for the keep-or-discard VERDICT**, added because routing the
    *reading* through one place turned out not to route this (#676 follow-up).
    Five surfaces compose the shared reading; three were repointed at
    :func:`manifest_condition` and two kept a locally-authored tail — so a
    stale-schema manifest printed "any partials beside it are real reviewer
    output" and then, four lines later, "Nothing here is worth keeping". One
    message, both verdicts, discard last. The swept-marker variant is the worse
    of the two: the marker is gone, so that notice is the ONLY report the
    operator ever gets, and one told nothing was attached will not run
    ``critic-restore`` before the archive ring evicts the partials.

    A verdict authored beside a shared sentence is not shared by being adjacent
    to it. So this returns the verdict itself, and callers append the clause
    rather than composing their own.

    Two inputs, and the second is why hedging was not enough: the manifest's
    condition, and whether reviewer partials are actually on disk. A
    stale-schema manifest sitting ALONE has nothing to preserve, and a message
    promising a ``critic-restore`` handle there sends an operator looking for an
    archive with nothing in it (R-11).
    """
    condition, _detail, _manifest = manifest_condition(prawduct_dir)
    partials = [
        p for p in partials_dir(prawduct_dir).glob("*.json")
        if p.name != MANIFEST_NAME
    ] if partials_dir(prawduct_dir).is_dir() else []
    if not partials:
        return False, (
            "  No reviewer output is on disk — nothing here is worth keeping.\n"
        )
    if condition in (MANIFEST_STALE_SCHEMA, MANIFEST_CORRUPT):
        return True, (
            f"  {len(partials)} reviewer partial(s) ARE on disk and are real output. The next\n"
            "  dispatch archives them rather than deleting them, printing a\n"
            "  `critic-restore` handle as it goes — do not delete them by hand.\n"
        )
    return True, (
        f"  {len(partials)} reviewer partial(s) are on disk; the next dispatch archives\n"
        "  rather than deletes them, printing a `critic-restore` handle.\n"
    )


def manifest_condition(prawduct_dir: Path) -> tuple[str, str, dict | None]:
    """What the manifest FILE is — the one home for that question.

    Returns ``(condition, detail, manifest)`` where ``condition`` is one of
    :data:`MANIFEST_ABSENT`, :data:`MANIFEST_CORRUPT`,
    :data:`MANIFEST_STALE_SCHEMA`, :data:`MANIFEST_VALID`; ``detail`` is the
    parse or validation reason (empty for absent/valid); and ``manifest`` is the
    parsed object when there was one to parse (``None`` for absent/corrupt), so
    a caller that wants the stale record's own fields does not re-read the file.

    **Why this is separate from :func:`pending_state`.** For DECIDING, corrupt
    and stale-schema are the same answer — neither can be consolidated, so
    ``pending_state`` is right to return ``"unreadable"`` for both and callers
    are right to branch on it. For TELLING SOMEONE, they are not remotely the
    same, and three surfaces had each re-derived the distinction on their own:
    the Stop hook's abandoned-review backstop said "unreadable or
    schema-invalid" (accurate), while :func:`pending_roster_reading` — the
    surface that ``critic-begin``'s refusal prints — said "no readable dispatch
    manifest … never recorded what it was reviewing … nothing here is worth
    keeping", which for a stale-schema manifest is three false clauses in a row.
    It is readable JSON; it *did* record ``commit_reviewed`` and
    ``files_reviewed``, in the schema of the version that wrote it; and its
    partials are worth enough that ``_archive_leftovers`` deliberately archives
    rather than deletes them, naming ``critic-restore`` as it goes. A message
    telling an operator to discard what the mechanism beside it is carefully
    preserving is the contradiction this function exists to end.

    That divergence is exactly what :func:`pending_roster_reading`'s docstring
    already forbids ("must not differ in what they say the on-disk state IS"),
    and it had recurred anyway — because the shared thing was the *reading*, and
    a reading cannot be shared for a distinction nobody had computed. So the
    classification lives in one function underneath all of them, and every
    surface derives from it instead of from its own read of the file.

    **Not a liveness check and not a wedge.** Verified rather than assumed
    (2026-08-22, #676): a stale-schema manifest with no marker does NOT block
    dispatch — ``begin_review`` sees ``"unreadable"``, which is neither
    ``active`` nor ``"complete"``, archives the leftovers under a recoverable
    ``unmanifested-<ts>`` name and proceeds. What the source report experienced
    as a wedge was the MARKER, which expires on its own TTL and which
    ``critic-end`` clears.
    """
    mpath = manifest_path(prawduct_dir)
    if not mpath.is_file():
        return MANIFEST_ABSENT, "", None
    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, ValueError) as exc:
        # ValueError, not `json.JSONDecodeError` (#676 follow-up, R-7): a
        # manifest that is not decodable UTF-8 raises `UnicodeDecodeError` out
        # of `read_text()`, which the narrower clause let through — so a
        # refusal that called this tracebacked instead of refusing, at the one
        # moment the caller is trying to explain a broken file. JSONDecodeError
        # is itself a ValueError, so the wider clause is a superset, not a swap.
        return MANIFEST_CORRUPT, str(exc), None
    ok, reason = validate_manifest(manifest)
    if not ok:
        return MANIFEST_STALE_SCHEMA, reason, manifest
    return MANIFEST_VALID, "", manifest


def pending_state(prawduct_dir: Path) -> tuple[str, list[str]]:
    """Classify the on-disk consolidation state, purely by file presence.

    Returns ``(state, missing_roles)``:
      - ``("none", [])`` — no manifest: nothing pending.
      - ``("unreadable", [])`` — manifest present but not valid JSON/schema.
      - ``("incomplete", [roles])`` — manifest valid, some roster partials absent.
      - ``("complete", [])`` — manifest valid, every roster partial present on disk.

    "complete" means every partial FILE exists — it does NOT validate partial
    contents (that is :func:`consolidate`'s job). This is the cheap liveness
    read; the full fail-closed check happens at consolidation.

    **The ``"unreadable"`` collapse is deliberate and stays.** Corrupt JSON and a
    stale-schema record are one answer to the question this function is asked —
    *can this be consolidated?* — and every caller branches on that. The
    distinction they do NOT share is what to SAY about it, which lives in
    :func:`manifest_condition` (whose docstring holds the reasoning) and is
    consumed by the message surfaces. Widening this return vocabulary instead
    would have made four callers handle a case that changes none of their
    decisions.
    """
    condition, _detail, manifest = manifest_condition(prawduct_dir)
    if condition == MANIFEST_ABSENT:
        return "none", []
    if condition in (MANIFEST_CORRUPT, MANIFEST_STALE_SCHEMA):
        return "unreadable", []
    missing = [
        role
        for role in manifest["roster"]
        if not partial_path(prawduct_dir, role, manifest["id"]).is_file()
    ]
    if missing:
        return "incomplete", missing
    return "complete", []


def pending_roster_reading(prawduct_dir: Path) -> tuple[str, str]:
    """What a pending roster MEANS — the one home, for every surface that advises on one.

    Two functions compose advice from :func:`pending_state`: this module's
    :func:`active_dispatch_refusal` (a ``critic-begin`` that refuses) and the
    retained-marker notice in ``bin/prawduct-hook`` (a session boundary that
    kept a live marker). They should differ in what they tell the reader to DO
    — one is refusing a dispatch, the other is announcing a retention — and
    must not differ in what they say the on-disk state IS. They did: only one
    of them was taught the fact below, and the untaught one sits at the more
    dangerous surface.

    **The ``incomplete`` reading is why this is shared rather than duplicated.**
    A marker survives ``/clear`` while its review could still land
    (``lib/critic_marker`` states why: no session event proves a reviewer died).
    That makes this state reachable two ways — reviewers still writing, or a
    dispatcher that is gone — and only one of them is safe to act on. A message
    naming just the second reads as already-satisfied to someone who has *just*
    run ``/clear``, and the command it points at (``critic-end``) clears the
    marker, which lets the next dispatch archive partials that reviewers are
    still writing. So the reading carries both possibilities and the tell that
    separates them, and it carries them everywhere at once.

    **Being shared means being true at every surface, including the one that
    just acted.** ``critic_marker.boundary_sweep`` DOES release an expired
    marker whose roster is incomplete, and the notice reporting that release
    prints this same reading — so a flat "a ``/clear`` retains the marker"
    lands as "waiting is safe" directly above a paragraph explaining that the
    marker is gone. Every clause here names its condition for that reason. A
    new caller is a new place these sentences have to hold, and the check is to
    read the composed output as that surface's reader.

    Returns ``(state, reading)`` — deliberately NOT the ``missing`` role list.
    The reading already names the outstanding roles in prose, and a third
    element no caller consumed read as an obligation to use it; both call sites
    had bound it to ``_missing``. A caller that needs the roles programmatically
    should ask :func:`pending_state`, which is what this wraps.

    The reading is indented two spaces to match every caller's block, states
    only what is on disk, and deliberately names no command: the remedy is
    surface-specific and stays with the caller.

    **One ``state``, more than one reading (#676).** The returned ``state`` is
    still :func:`pending_state`'s four-value vocabulary, because that is what
    callers branch on — but ``"unreadable"`` covers two genuinely different
    disks and used to print one sentence that was false for one of them. A
    stale-schema manifest is readable and DID record what it was reviewing, so
    being told "no readable dispatch manifest" is simply wrong. The three cases
    now read differently and are classified in one place
    (:func:`manifest_condition`).

    **This describes the MANIFEST and nothing else.** It deliberately makes no
    keep-or-discard claim — that is :func:`anything_worth_keeping`, and the
    separation is load-bearing rather than tidy. The first repair had the
    stale-schema reading assert that partials beside it were real reviewer
    output; composed with a verdict computed from the actual disk, that produced
    "…printing a `critic-restore` handle" directly above "No reviewer output is
    on disk", which is the same self-contradiction one layer in. The manifest's
    condition and whether reviewer output exists are two independent facts, and
    a sentence that answers both from one of them will be wrong whenever they
    disagree — an orphaned partial set with no manifest is exactly that disk.
    ``test_no_composed_message_contradicts_itself`` composes every surface under
    every condition and is what caught it.
    """
    state, missing = pending_state(prawduct_dir)
    if state == "complete":
        reading = (
            "  On disk: every reviewer has reported. That review is FINISHED and needs\n"
            "  only consolidation.\n"
        )
    elif state == "incomplete":
        reading = (
            f"  On disk: still waiting on {', '.join(missing)}. Either those reviewers\n"
            "  are still running — consolidation fires as they finish, so wait — or the\n"
            "  session that dispatched them ended (a `/clear` keeps the marker while they\n"
            "  could still land, and releases it once the liveness window has passed).\n"
            "  If nothing lands, they are gone.\n"
        )
    else:
        # `state` is "none" (no manifest at all) or "unreadable" (corrupt or
        # stale-schema). Those are one decision and three different facts, so
        # the REMEDY stays shared while the sentence describing disk does not.
        # `manifest_condition` owns the distinction; see its docstring for the
        # three false clauses the single collapsed reading used to print.
        condition, detail, manifest = manifest_condition(prawduct_dir)
        if condition == MANIFEST_STALE_SCHEMA:
            # It parsed. Name what it still tells you, because that is what
            # decides whether the partials beside it are worth restoring —
            # and the archive step preserves them on exactly that bet.
            reviewed = manifest.get("commit_reviewed") if isinstance(manifest, dict) else None
            recorded = (
                f" It says it was reviewing {reviewed}."
                if isinstance(reviewed, str) and reviewed
                else ""
            )
            reading = (
                "  On disk: a dispatch manifest written by an OLDER PRAWDUCT — it parses,\n"
                f"  but not against this version's schema ({short_detail(detail)}).{recorded}\n"
                "  It cannot be consolidated.\n"
            )
        elif condition == MANIFEST_CORRUPT:
            reading = (
                f"  On disk: a dispatch manifest that is not valid JSON ({short_detail(detail)}) —\n"
                "  the write that produced it was interrupted. It cannot be consolidated.\n"
            )
        else:
            reading = (
                "  On disk: no dispatch manifest at all — a review set the marker but\n"
                "  never recorded what it was reviewing.\n"
            )
    return state, reading


def active_dispatch_refusal(
    prawduct_dir: Path, age_seconds: float | None, active: bool = True
) -> str:
    """The message a ``critic-begin`` prints when it refuses to displace a review
    that is still in flight.

    **Why the refusal exists.** ``critic-begin`` resets the partials directory
    (:func:`_archive_leftovers`; :func:`remove_partials` states why). That
    treatment is right for an *orphaned* leftover and catastrophic for a *live*
    review's: dispatching over one archives partials that may be complete,
    overwrites the manifest and re-stamps the marker, so a finished review —
    blocking findings included — leaves no fact and no ledger anchor until
    someone notices and restores it by name (``critic-restore``). Refusing costs
    one command; the alternative costs a whole review round.

    That second-order harm — a displaced review's straggler landing in the new
    review's directory and consolidating as it — is no longer possible, and this
    message no longer argues from it. A partial is keyed by review id and
    declares its ``dispatch_id``, so a straggler is named as foreign rather than
    merged. What survives is the first-order harm above, which is enough: this
    refusal exists to protect findings that have already been written.

    **This message is also the missing observability.** ``methodology/building.md``
    tells an agent whose review looks slow to "wait; if it fails, re-invoke", and
    nothing distinguished *in flight* from *dead* — so the guide's own failure
    path led into the destructive dispatch. The refusal is emitted at exactly the
    moment that judgment is being made, and answers it with the on-disk state
    rather than leaving it to a guess.
    """
    age_note = f"~{int(age_seconds // 60)}m ago" if age_seconds is not None else "recently"
    prior_id = "(id unavailable — no usable dispatch manifest)"
    try:
        prior_id = json.loads(manifest_path(prawduct_dir).read_text())["id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass
    # The READING is shared with the boundary retained-marker notice
    # (:func:`pending_roster_reading` says why); only the remedy below is local
    # to refusing a dispatch.
    state, situation = pending_roster_reading(prawduct_dir)
    if state == "complete":
        situation += (
            "  Dispatching now would discard it:\n"
            "    prawduct-hook critic-consolidate\n"
        )
    elif state == "incomplete":
        situation += "  If they are gone, that is `critic-end`, below.\n"

    # The remedy has to REACH the state that is refusing, and the two conditions
    # strand a caller differently. A live marker expires and `critic-end` clears
    # it. A complete roster with NO live marker does neither: consolidation
    # fail-closes without removing partials (its two `remove_partials` call sites
    # are `begin_review` — now behind this guard — and consolidate-on-success),
    # so a failed consolidate leaves a complete roster that `critic-end` cannot
    # touch and no TTL expires. Naming the marker's TTL there would be false, and
    # a refusal whose stated remedy does not work is worse than none.
    if active:
        escape = (
            "  If that review is genuinely dead, abandon it explicitly and re-dispatch:\n"
            "    prawduct-hook critic-end"
        )
        # "Wait it out" is only an escape where waiting reaches something. On a
        # COMPLETE roster this refusal does not turn on the marker at all — a
        # finished review is refused at any age — so naming the TTL there offers
        # a remedy that never arrives, and the situation above has already given
        # the one that does.
        if state != "complete":
            escape += (
                f"\n  The marker also stops blocking after "
                f"{critic_marker.CRITIC_ACTIVE_TTL_SECONDS // 60} minutes — though a `clear`"
                "\n  releases it only once nothing recoverable is attached to it."
            )
    else:
        escape = (
            "  No live marker — these partials are STRANDED, most likely by a\n"
            "  consolidation that failed (it leaves them in place so the fix can retry).\n"
            "  Consolidate them if the cause is fixable; `critic-end` will NOT clear this\n"
            "  state and nothing expires it. To discard them deliberately and dispatch\n"
            "  fresh — archiving first, never deleting outright:\n"
            "    prawduct-hook critic-discard\n"
            "  That archive is not a dead end: `prawduct-hook critic-restore <review-id>`\n"
            "  brings the discarded review back as itself, ready to consolidate."
        )
    opening = (
        f"refusing — a Critic review is already in flight in this "
        f"worktree ({prior_id}, dispatched {age_note}).\n"
        if active
        else f"refusing — a completed review's partials are still on disk ({prior_id}).\n"
    )
    # No "critic-begin:" prefix — the CLI renders this as `f"critic-begin: {reason}"`.
    return (
        opening
        + "  Dispatching now would archive its partials and overwrite its manifest, so\n"
        "  a finished review would leave no fact and no ledger anchor until someone\n"
        "  noticed and ran `prawduct-hook critic-restore` on it by name.\n"
        "\n"
        + situation
        + "\n"
        + escape
    )


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def merge_findings(partials: list[dict]) -> list[dict]:
    """Union every reviewer's findings into the fact-body shape,
    de-duplicated by ``(goal, name, files)`` keeping the highest severity,
    with sequential ``fid``s assigned in merge order (deterministic: roster
    order × each partial's findings order).

    Each partial finding ``{name, goal, severity, recommendation, files?}``
    maps to ``{fid, goal, severity, title, recommendation, files?}`` — the
    reviewer's ``name`` becomes the fact ``title`` (the field the coverage
    algebra surfaces for unresolved blockers; the derived cache renders it
    as the record ``summary``). The ``fid`` is what resolution facts join on
    (D5) — a blocking finding without one could never be resolved, so the
    writer always assigns them.
    """
    merged: dict[tuple, dict] = {}
    for partial in partials:
        for f in partial.get("findings", []):
            # Normalize optional attribution to non-empty string paths, so a
            # blank/non-string element collapses to no ``files`` exactly like
            # ``[]`` or an omitted key — the validator tolerates such elements
            # rather than fail-closing, and normalization happens here.
            files = [
                x for x in (f.get("files") or []) if isinstance(x, str) and x.strip()
            ]
            key = (f["goal"], f["name"], tuple(files))
            entry = {
                "goal": f["goal"],
                "severity": f["severity"],
                "title": f["name"],
                "recommendation": f["recommendation"],
            }
            if files:
                entry["files"] = files
            existing = merged.get(key)
            if existing is None or (
                _SEVERITY_RANK[f["severity"]] > _SEVERITY_RANK[existing["severity"]]
            ):
                merged[key] = entry
    findings = list(merged.values())
    for idx, entry in enumerate(findings, start=1):
        entry["fid"] = f"R-{idx}"
    return findings


# Words that carry no discriminating signal in a finding title. Deliberately
# short: over-stopping raises the similarity of unrelated titles, which costs
# precision in the one direction that matters.
_TITLE_NOISE = frozenset(
    """a about above after again against all also an and any are as at be been before
    below between but by can cannot could did do does down during else for from further
    had has have here how if in into is it its may might must never new no not now of
    on once one only or out over own same second should so than that the their then
    there this three through to too two under until up very was were what when where
    which while who with would""".split()
)

#: Title-word overlap above which two findings from DIFFERENT reviewers are
#: reported as probably one defect. Calibrated on this repo's 254 recorded
#: reviews: the true pair that prompted this sat at 0.44, and every pair
#: surfaced at 0.4 spot-checked as a genuine duplicate (23 pairs across 16 of
#: 209 reviews with findings, including one defect found by three reviewers).
#: Set low deliberately — the output is advisory, so a false positive costs a
#: hint while a miss costs a silently double-counted finding.
DUPLICATE_SIMILARITY = 0.4

#: The same bar, applied to the OVERLAP coefficient rather than Jaccard, and
#: only when the two findings cite the same files. Jaccard divides by the union,
#: so it is punished by length asymmetry: three reviewers meeting one defect
#: describe it at whatever length their goal calls for, and a terse title inside
#: a verbose one scores low while sharing every word it has. The observed
#: triplicate (R-1/R-5/R-11 on one branch — same file, same claim) reported as
#: `[]` for exactly that reason. Overlap coefficient — |A∩B| / min(|A|,|B|) — is
#: the length-insensitive form of the same question, and it is gated on
#: identical file attributions because that is the condition under which a
#: contained title is evidence of one defect rather than of two findings about
#: the same subsystem.
DUPLICATE_CONTAINMENT = 0.6

#: Significant words the SHORTER title must carry before containment may group.
#: Without it the rule is degenerate: a one- or two-word title ("Ordering") is
#: trivially contained in any title that happens to use the same word, so every
#: terse finding would join whichever neighbour shared a noun. Three is the
#: floor at which containment says something — the observed triplicate's
#: shortest title carries five.
DUPLICATE_MIN_WORDS = 3


def _title_words(title: str) -> frozenset:
    words = re.findall(r"[a-z0-9_]+", (title or "").lower())
    return frozenset(w for w in words if len(w) > 2 and w not in _TITLE_NOISE)


def likely_duplicate_groups(findings: list[dict]) -> list[list[str]]:
    """Groups of ``fid``s that probably describe ONE defect, so a finding count
    is not mistaken for a defect count.

    **Advisory only — nothing here merges, drops, or reorders a finding.**
    :func:`merge_findings` keys on ``(goal, name, files)``, and the
    coordinator's goal sets are *disjoint by construction* (each reviewer is
    told to review ONLY its goals), so two reviewers meeting the same defect
    always yield two findings that no exact key can collapse. Collapsing them
    would take fuzzy matching in the *write* path, and a fuzzily-dropped real
    finding is invisible in the output — strictly worse than over-counting. So
    this reports and the builder decides.

    Candidates must come from different goals (hence different reviewers) and
    have file attributions that are not disjoint. Two ways they then qualify,
    and the second exists because the first missed the case this was built for:

    - Jaccard over significant title words ≥ :data:`DUPLICATE_SIMILARITY`.
    - **Identical** file attributions and overlap coefficient ≥
      :data:`DUPLICATE_CONTAINMENT` — the length-insensitive test. Jaccard
      divides by the union, so a terse title wholly contained in a verbose one
      scores low while sharing every word it has, which is exactly how three
      reviewers describing one defect at three levels of detail reported as no
      group at all.

    Grouping is transitive, so one defect found by all three reviewers reports
    as a single group.
    """
    entries = [
        (
            f["fid"],
            f.get("goal"),
            frozenset(f.get("files") or []),
            _title_words(evidence.finding_title(f)),
        )
        for f in findings
        if isinstance(f, dict)
        and isinstance(f.get("fid"), str)
        and f["fid"].strip()
    ]
    parent = {fid: fid for fid, _goal, _files, _words in entries}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for i, (fid_a, goal_a, files_a, words_a) in enumerate(entries):
        for fid_b, goal_b, files_b, words_b in entries[i + 1 :]:
            if goal_a == goal_b:
                continue
            if files_a and files_b and not (files_a & files_b):
                continue
            if not words_a or not words_b:
                continue
            shared = len(words_a & words_b)
            jaccard = shared / len(words_a | words_b)
            containment = shared / min(len(words_a), len(words_b))
            same_files = bool(files_a) and files_a == files_b
            long_enough = min(len(words_a), len(words_b)) >= DUPLICATE_MIN_WORDS
            if jaccard >= DUPLICATE_SIMILARITY or (
                same_files and long_enough and containment >= DUPLICATE_CONTAINMENT
            ):
                root_a, root_b = find(fid_a), find(fid_b)
                if root_a != root_b:
                    parent[root_a] = root_b

    order = [fid for fid, _goal, _files, _words in entries]
    grouped: dict[str, list[str]] = {}
    for fid in order:
        grouped.setdefault(find(fid), []).append(fid)
    return sorted(
        (group for group in grouped.values() if len(group) > 1),
        key=lambda group: order.index(group[0]),
    )


def distinct_finding_count(findings: list[dict], groups: list[list[str]]) -> int:
    """``findings`` counted with each likely-duplicate group collapsed to one."""
    return len(findings) - sum(len(group) - 1 for group in groups)


def _render_duplicate_groups(findings: list[dict], groups: list[list[str]]) -> str:
    """Each likely-duplicate group as ONE defect line carrying N attributions.

    Reporting "2 likely-duplicate groups" and then leaving the builder to read
    three separately-worded findings does not save the second and third
    disposition — the count is a claim about the list, and the list is what gets
    worked. So the group gets a line of its own, with the shortest title as the
    defect (a terse title is the one the three reviewers agree on; the verbose
    ones carry each goal's framing) and every fid named after it.

    Presentation only. `merge_findings` still keys exactly, every finding
    survives in the fact and in `.critic-findings.json`, and each fid is printed
    — so a WRONG group costs a reader one confusing line and can never hide a
    finding. That asymmetry is what lets the grouping bar sit low.
    """
    if not groups:
        return ""
    by_fid = {
        f["fid"]: f
        for f in findings
        if isinstance(f, dict) and isinstance(f.get("fid"), str)
    }
    lines = [
        "",
        f"  {len(groups)} defect(s) below were each filed by more than one reviewer — "
        "dispose of the group once, not once per fid:",
    ]
    for group in groups:
        entries = [by_fid[fid] for fid in group if fid in by_fid]
        if not entries:
            continue
        lead = min(
            entries,
            key=lambda f: len(evidence.finding_title(f)),
        )
        title = evidence.finding_title(lead, "<no title>")
        # The severity is the group's MAXIMUM, never the lead's. The lead is
        # chosen for its wording (shortest = the claim the reviewers agree on),
        # and wording has nothing to do with severity — so a BLOCKING found by
        # one reviewer and noted by another would have printed as [NOTE] and
        # been dispositioned as one. A group is one defect; its severity is the
        # most severe reading any reviewer gave it.
        severity = max(
            (str(f.get("severity") or "").lower() for f in entries),
            key=lambda s: _SEVERITY_RANK.get(s, -1),
            default="",
        ).upper() or "?"
        goals = ", ".join(
            sorted({str(f.get("goal")) for f in entries if f.get("goal")})
        )
        lines.append(
            f"    - [{severity}] {title}  ({'+'.join(group)}"
            + (f"; goals: {goals}" if goals else "")
            + ")"
        )
    return "\n".join(lines)


def _severity_counts(findings: list[dict]) -> tuple[int, int, int]:
    blocking = sum(1 for f in findings if f["severity"] == "blocking")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    note = sum(1 for f in findings if f["severity"] == "note")
    return blocking, warning, note


def build_fact_body(manifest: dict, partials: list[dict]) -> dict:
    """Assemble the review fact body (design D4) from the manifest interval
    and the merged partials. The derived cache is rendered FROM this body
    (:func:`fact_to_cache_record`), so it carries everything the cache needs."""
    findings = merge_findings(partials)
    blocking, warning, note = _severity_counts(findings)
    # Parallel reviewers → wall-clock is the slowest, not the sum. None when no
    # reviewer reported a duration.
    durations = [
        p["duration_seconds"]
        for p in partials
        if isinstance(p.get("duration_seconds"), (int, float))
        and not isinstance(p.get("duration_seconds"), bool)
    ]
    return {
        "base_commit": manifest.get("base_commit"),
        "base_tree": manifest["base_tree"],
        "head_tree": manifest["head_tree"],
        "head_commit": manifest.get("head_commit"),
        "dispatch_commit": manifest["commit_reviewed"],
        "mode": manifest["mode"],
        "mode_chosen_by": manifest["mode_chosen_by"],
        "tier": manifest.get("tier"),
        "roster": [
            {"role": p["role"], "model": p.get("model")} for p in partials
        ],
        "files_reviewed": list(manifest["files_reviewed"]),
        "files_changed": list(manifest["files_changed"]),
        "findings": findings,
        "counts": {"blocking": blocking, "warning": warning, "note": note},
        "duration_seconds": max(durations) if durations else None,
        "scope": manifest.get("scope"),
        # How the scope was decided, carried so attribution is auditable rather
        # than merely asserted — a fact naming a plan should say whether the
        # dispatch named it or the branch did.
        "scope_chosen_by": manifest.get("scope_chosen_by"),
        "chunk": manifest.get("chunk"),
        "base_reviewed": manifest.get("base_reviewed"),
        # The record-lint control's YIELD, carried from the dispatch manifest
        # into the fact so it is queryable rather than printed and forgotten
        # (`nonfunctional-requirements.md` § Direction — a control born after
        # 2026-07-29 emits its yield at birth, or it can only ever be defended
        # on principle instead of retired on evidence). This is data ABOUT the
        # review, not a finding IN it: it never reaches `counts`, so it cannot
        # move a verdict, and no gate reads it.
        "record_lint": manifest.get("record_lint"),
    }


def fact_to_cache_record(fact: dict, price_sentence: "str | None" = None) -> dict:
    """Render the derived ``.critic-findings.json`` record from a review fact
    (D7: the cache is a code-regenerated VIEW of the latest fact — builders
    and briefings read it for content; no gate reads it). Carries the source
    ``fact_id`` so staleness is detectable and the verify-resolutions
    dispatch can locate its anchor fact.

    ``price_sentence`` rides through to :func:`next_action_line`. It is a
    parameter rather than a ledger read here because this function is a pure
    fact→record projection and the cache is written once per consolidation,
    where the caller already holds the prawduct dir."""
    body = fact.get("body") or {}
    findings = []
    for f in body.get("findings", []):
        entry = {
            "fid": f.get("fid"),
            "goal": f.get("goal"),
            "severity": f.get("severity"),
            "summary": f.get("title"),
            "recommendation": f.get("recommendation"),
        }
        if f.get("files"):
            entry["files"] = list(f["files"])
        findings.append(entry)
    counts = body.get("counts") or {}
    blocking = counts.get("blocking", 0)
    warning = counts.get("warning", 0)
    note = counts.get("note", 0)
    if blocking:
        verdict = "Blocking findings must be resolved before proceeding."
    else:
        verdict = "Changes ready to proceed."
    roster = body.get("roster") or []
    models = [r.get("model") for r in roster if r.get("model")]
    return {
        "timestamp": fact.get("ts"),
        "duration_seconds": body.get("duration_seconds"),
        "mode": body.get("mode"),
        "mode_chosen_by": body.get("mode_chosen_by"),
        "model": models[0] if models else None,
        "commit_reviewed": body.get("dispatch_commit"),
        "base_reviewed": body.get("base_reviewed"),
        "files_reviewed": list(body.get("files_reviewed") or []),
        "findings": findings,
        "summary": (
            f"{blocking} blocking, {warning} warning, {note} note "
            f"across {len(roster)} reviewer(s). {verdict}"
        ),
        "fact_id": fact.get("id"),
        # The builder's copy of the loop-termination rule, computed from the
        # counts just read. See `next_action_line` for why the findings file is
        # the carrier that had a reader and no message.
        "next_action": next_action_line(
            fact.get("id"), blocking, warning, note, price_sentence
        ),
        # Recomputed from the fact's own findings, so this advisory grouping
        # adds nothing to the persisted schema and keeps no model in the write
        # path. Additive key: `--json` readers tolerate unknown fields.
        "likely_duplicate_groups": likely_duplicate_groups(
            body.get("findings") or []
        ),
    }


# ---------------------------------------------------------------------------
# Consolidate — the command body
# ---------------------------------------------------------------------------


def _known_findings_index(store: dict) -> set[tuple[str, str]]:
    """Every ``(review_id, fid)`` recorded in the store — the existence check
    a resolution must pass before it may weaken a gate.

    The key set of the shared walk (``evidence.findings_index``), which the
    census consumer needs in its richer per-finding form. One walk, so the
    gate's notion of "recorded" and the census's cannot drift apart."""
    return set(evidence.findings_index(store))


def dispatch_age_minutes(review_id: str, *, now: datetime | None = None) -> float | None:
    """Minutes since the dispatch timestamp a ``begin_review`` id embeds
    (``rev-%Y%m%dT%H%M%SZ-<hex>``), or ``None`` when the id carries none
    (hand-written manifests). Clock skew can put the stamp in the future;
    clamp to 0 rather than report a negative age."""
    match = _REVIEW_ID_TS.match(review_id)
    if not match:
        return None
    try:
        dispatched = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dispatched).total_seconds() / 60.0)


def _incomplete_noop_message(missing: list[str], present: int, total: int,
                             review_id: str,
                             prawduct_dir: Path | None = None) -> str:
    """The incomplete no-op with a liveness verdict, not just a partial count.
    Zero partials shortly after dispatch is the NORMAL background-reviewer
    state — say so explicitly, or the caller infers reviewer death from
    silence and double-dispatches. The wait-side variants also direct a
    periodic progress readout, so a session that correctly decides to wait
    does not idle its prompt cache into expiry while doing so.

    Per-role liveness: each coordinator-dispatched reviewer writes the started
    marker :func:`started_path` names as its first action, so a missing role is judged by its
    OWN started-marker age when one exists — a reviewer that started late (e.g.
    resumed against a moved HEAD) is not declared dead by dispatch age. The
    past-grace advice fires only when EVERY missing role is past the grace
    window on its own effective age (marker age when present, dispatch age
    otherwise): one dead reviewer among live ones converges — the live roles
    report and leave ``missing``, and the dead one's age keeps growing."""
    age = dispatch_age_minutes(review_id)
    counts = f"{present}/{total} partials present"
    if age is not None:
        counts += f"; dispatched {age:.1f} min ago"
    started: dict[str, float | None] = {}
    if prawduct_dir is not None and total > 1:
        started = {
            role: started_age_minutes(prawduct_dir, role, review_id)
            for role in missing
        }

    def _label(role: str) -> str:
        s_age = started.get(role)
        return role if s_age is None else f"{role} (started {s_age:.1f} min ago)"

    line = (
        f"no-op: review incomplete — waiting on "
        f"{', '.join(_label(r) for r in missing)} ({counts})."
    )
    effective = [
        started.get(role) if started.get(role) is not None else age
        for role in missing
    ]
    past_grace = bool(effective) and all(
        e is not None and e > _INFLIGHT_GRACE_MINUTES for e in effective
    )
    if past_grace:
        line += (
            f" Every missing role is past the in-flight grace window"
            f" (~{_INFLIGHT_GRACE_MINUTES} min) on its own age"
            " — the reviewers may have died. Abandon this review with"
            " `prawduct-hook critic-end`, then re-dispatch."
        )
    elif total == 1:
        # Single-pass roster: the reviewer IS the dispatching fork and
        # consolidates itself — a SubagentStop trigger will never land it, so
        # the coordinator-roster story would be false here.
        line += (
            " The single-pass reviewer (the dispatching fork itself) writes its"
            " partial and consolidates when it finishes — reviews typically take"
            " 4-10 minutes; missing partials are the normal in-flight state, NOT"
            " evidence the reviewer died. Re-run this command later; if the fork"
            " already returned without consolidating, abandon with"
            " `prawduct-hook critic-end`, then re-dispatch."
        )
        line += _CACHE_WARM_DIRECTIVE
    else:
        line += (
            " Reviewers run in the BACKGROUND after the dispatching fork returns"
            " and typically take 4-10 minutes; missing partials are the normal"
            " in-flight state, NOT evidence the reviewers died. Do not"
            " re-dispatch — wait for the SubagentStop trigger to consolidate"
            " (or re-run this command later). A genuine re-dispatch requires"
            " `prawduct-hook critic-end` first."
        )
        line += _CACHE_WARM_DIRECTIVE
    if prawduct_dir is not None:
        line += _stray_partial_note(prawduct_dir, missing, review_id)
    return line


def _stray_partial_note(prawduct_dir: Path, missing: list[str],
                        review_id: str) -> str:
    """Name a partial that is on disk but not this review's, and say what to do.

    Without this, the two ways a reviewer's work goes uncounted are both
    invisible. A **straggler** from an abandoned review sits under that review's
    own name and is correctly ignored — but silence reads as "the reviewer never
    wrote anything", which is the death verdict that produced the double
    dispatch in the first place. A **legacy** partial at the pre-keyed
    ``<role>.json`` is worse: it means the skill that wrote it is older than
    this hook, the reviewer did its whole run, and the file will never be read.
    Accepting it instead would reopen the hole this keying closes, so the answer
    is to say so and name the remedy.

    Advice, so it fails soft: any read error yields no note rather than an
    exception on a message-building path.
    """
    pdir = partials_dir(prawduct_dir)
    try:
        names = {p.name for p in pdir.iterdir() if p.is_file()}
    except OSError:
        return ""
    legacy = [r for r in missing if f"{r}.json" in names]
    foreign: list[str] = []
    for role in missing:
        # `partial_path` owns the shape; asking it for the name this review
        # would use keeps this reader from becoming a second home for it.
        mine = partial_path(prawduct_dir, role, review_id).name
        for name in sorted(names):
            if (name.startswith(f"{role}.") and name.endswith(".json")
                    and name not in (f"{role}.json", mine)):
                foreign.append(name)
    note = ""
    if legacy:
        # The remedy has to REACH the state, and a bare "re-dispatch" does not:
        # this note is appended to a message whose roster branch has just said
        # "do not re-dispatch", and `critic-begin` refuses anyway while the
        # marker is live. So the sequence is stated in full, in order, and the
        # abandon step comes first.
        note += (
            f" NOTE: {', '.join(sorted(f'{r}.json' for r in legacy))} in that"
            " directory is a partial written to the path this hook used before"
            " reviews were keyed by id — the skill that wrote it is older than"
            " this hook, so its work cannot be read and waiting will not"
            " produce it. This one case overrides the wait advice above:"
            " reload the plugin (/reload-plugins, or restart the session),"
            " then `prawduct-hook critic-end` to abandon this review, then"
            " dispatch again."
        )
    if foreign:
        note += (
            f" NOTE: {', '.join(sorted(set(foreign)))} in that directory"
            " belongs to an earlier review, not this one — a straggler that is"
            " correctly ignored here. It is not evidence about whether this"
            " review's reviewers are alive."
        )
    return note


def _already_consolidated_note(prawduct_dir: Path) -> str:
    """What the "no pending manifest" no-op should add about the review that
    already landed.

    This branch is the COORDINATOR path's normal case, not an error: the
    SubagentStop trigger consolidated while the main agent was elsewhere, and
    CLAUDE.md tells that agent to run ``critic-consolidate`` before reading the
    findings precisely so it never reads a stale file. Bare "nothing to
    consolidate" answers a question it did not ask. Naming the review that IS
    recorded — and, when it has findings, how to fix them without buying extra
    rounds — is the answer to the question it did ask.

    Says "newest recorded", never "yours" — nothing here can tell whether the
    recorded review is the caller's or a bystander's. It CAN tell how old it is
    (:func:`dispatch_age_minutes` parses the same id shape sixty lines up), so it
    says: an unqualified "holds N findings" about a week-old review, followed by
    a disposition directive, would manufacture the very round this exists to
    prevent.

    **Absence of the note means "clean", so a failure must never render as
    absence** — that is the swallow-into-``""`` shape ``learnings.md`` warns
    about by name, and here it would report a truncated cache as a clean review
    to the one caller CLAUDE.md routes through this branch. Read/parse/shape
    failures therefore say so; only a genuinely finding-free cache is silent.
    Diagnostics stay advisory (``architecture.md``: advice fails soft — which
    says do not block, not do not report).
    """
    cache = prawduct_dir / ".critic-findings.json"
    if not cache.exists():
        return ""
    try:
        # ValueError covers JSONDecodeError AND the UnicodeDecodeError a
        # byte-truncated cache raises from read_text() — the case the "must not
        # crash an informational no-op" contract promises and a narrower
        # (OSError, JSONDecodeError) missed.
        record = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f" (`.prawduct/{cache.name}` exists but is unreadable: {exc} — not a clean-review signal.)"
    if not isinstance(record, dict) or not isinstance(record.get("findings"), list):
        return f" (`.prawduct/{cache.name}` is not a findings record — not a clean-review signal.)"
    findings = record["findings"]
    if not findings:
        return ""
    fact_id = record.get("fact_id") or "unknown"
    # DISPATCH age, from the id's own stamp — not the time the fact was
    # recorded, which is later by however long the review took (ten minutes on a
    # coordinator run). Labelled for what it is; the caller's question is "how
    # stale is this?", which the dispatch time answers just as well.
    age = dispatch_age_minutes(str(fact_id))
    age_note = f", dispatched {age:.0f} min ago" if age is not None else ""
    return (
        f" The newest recorded review ({fact_id}{age_note}) holds {len(findings)}"
        f" finding(s) — read `.prawduct/{cache.name}`; if they are already"
        " dispositioned, this is history, not work." + _BATCH_FIX_DIRECTIVE
    )


def consolidate(project_dir: Path) -> int:
    """Merge complete reviewer partials into evidence facts + the derived
    cache. Idempotent.

    Exit codes:
      - ``0`` + ``no-op:`` — nothing to do (no manifest, or roster incomplete —
        the message names the missing roles). The common in-flight case as
        reviewers finish one by one; the incomplete message also states the
        dispatch age and whether silence is still normal (wait) or past the
        grace window (critic-end + re-dispatch).
      - ``0`` + ``consolidated:`` — review fact appended (or already present),
        resolution facts appended, cache regenerated, ledger anchored, marker
        cleared, partials removed.
      - ``1`` — fail-closed: malformed manifest/partial, a partial reviewed a
        different commit than dispatched, off-protocol resolutions, a
        resolution referencing a finding the store doesn't hold, a store
        write failure, or a ledger failure. Nothing partial is persisted as
        complete; the manifest is left in place so the fix can retry (fact
        appends already made are healed by the id-idempotency probe).
    """
    from . import gates  # noqa: PLC0415 — lazy; gates is heavy

    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    mpath = manifest_path(prawduct_dir)
    if not mpath.is_file():
        print(
            "no-op: no pending review manifest — nothing to consolidate."
            + _already_consolidated_note(prawduct_dir)
        )
        return 0

    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"critic-consolidate: manifest unreadable ({exc})", file=sys.stderr)
        return 1
    ok, reason = validate_manifest(manifest)
    if not ok:
        print(f"critic-consolidate: invalid manifest — {reason}", file=sys.stderr)
        return 1

    roster = manifest["roster"]
    manifest_commit = manifest["commit_reviewed"]
    review_id = manifest["id"]
    is_verify = manifest["mode"] == _VERBOSE_VERIFY_RESOLUTIONS

    # Collect partials; missing roles → incomplete no-op (still in flight).
    partials: list[dict] = []
    missing: list[str] = []
    for role in roster:
        ppath = partial_path(prawduct_dir, role, review_id)
        if not ppath.is_file():
            missing.append(role)
            continue
        try:
            data = json.loads(ppath.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"critic-consolidate: partial {role!r} unreadable ({exc}) — "
                "fail-closed, not persisting a partial review as complete.",
                file=sys.stderr,
            )
            return 1
        valid, preason = validate_partial(data)
        if not valid:
            print(
                f"critic-consolidate: partial {role!r} invalid — {preason}. "
                "Fail-closed; not consolidating.",
                file=sys.stderr,
            )
            return 1
        if data["role"] != role:
            print(
                f"critic-consolidate: partial for {role!r} declares role "
                f"{data['role']!r} — roster mismatch, fail-closed.",
                file=sys.stderr,
            )
            return 1
        # Belt-and-braces against the commit binding being the ONLY one. The
        # keyed filename already stops a straggler from another review landing
        # here; this catches the case the name cannot — a reviewer handed the
        # wrong id in its dispatch prompt, writing to the right file with the
        # wrong review's identity. Stripped before comparing, because
        # surrounding whitespace normalizes identically and must not abort a
        # whole consolidation (the `files: []` lesson, same module): hard-fail
        # is for genuine ambiguity, which a different id is and a padded one
        # is not.
        if data["dispatch_id"].strip() != review_id.strip():
            print(
                f"critic-consolidate: reviewer {role!r} was dispatched by "
                f"{data['dispatch_id'].strip()} but this manifest is "
                f"{review_id} — the partial belongs to a different review, "
                "fail-closed.",
                file=sys.stderr,
            )
            return 1
        if data["commit_reviewed"] != manifest_commit:
            print(
                f"critic-consolidate: reviewer {role!r} reviewed "
                f"{data['commit_reviewed'][:12]} but dispatch was at "
                f"{manifest_commit[:12]} — inconsistent, re-review.",
                file=sys.stderr,
            )
            return 1
        partials.append(data)

    if missing:
        print(_incomplete_noop_message(
            missing, len(partials), len(roster), review_id, prawduct_dir))
        return 0

    # Resolutions may only arrive from a verify-resolutions dispatch — they
    # WEAKEN gates (they unblock findings), so off-protocol ones fail closed.
    resolutions: list[dict] = []
    seen_res: set[tuple[str, str]] = set()
    for partial in partials:
        entries = partial.get("resolutions") or []
        if entries and not is_verify:
            print(
                f"critic-consolidate: partial {partial['role']!r} carries "
                f"resolutions but the dispatch mode is {manifest['mode']!r} — "
                "only a verify-resolutions dispatch may resolve findings; "
                "fail-closed.",
                file=sys.stderr,
            )
            return 1
        for r in entries:
            key = (r["review_id"], r["fid"])
            if key not in seen_res:
                seen_res.add(key)
                resolutions.append(r)

    store = evidence.read_facts(project_dir)
    if store["status"] == "error":
        print(
            f"critic-consolidate: evidence store unreadable — {store['reason']}",
            file=sys.stderr,
        )
        return 1
    if resolutions:
        known = _known_findings_index(store)
        for r in resolutions:
            if (r["review_id"], r["fid"]) not in known:
                print(
                    f"critic-consolidate: resolution targets finding "
                    f"{r['fid']!r} of review {r['review_id']!r}, which the "
                    "evidence store does not hold — a resolution must "
                    "reference a recorded finding; fail-closed.",
                    file=sys.stderr,
                )
                return 1

    # All preconditions met — append the review fact (idempotent by id: the
    # CRT-4B7X double-consolidate race appends exactly one).
    already = any(
        f.get("id") == review_id for f in evidence.facts_of_kind(store, "review")
    )
    if not already:
        body = build_fact_body(manifest, partials)
        result = evidence.append_fact(project_dir, "review", review_id, body)
        if result["status"] != "appended":
            print(
                f"critic-consolidate: could not append review fact — "
                f"{result['reason']}",
                file=sys.stderr,
            )
            return 1

    # Resolution facts (D5) — deterministic ids so a retry appends nothing new.
    appended_resolutions = 0
    for r in resolutions:
        res_id = f"{review_id}:{r['review_id']}:{r['fid']}"
        if evidence.has_fact(project_dir, "resolution", res_id):
            continue
        res_body = {
            "finding": {"review_id": r["review_id"], "fid": r["fid"]},
            "disposition": r["disposition"],
            "verified_by": review_id,
            "at_tree": manifest["head_tree"],
            "rationale": r.get("rationale"),
        }
        result = evidence.append_fact(project_dir, "resolution", res_id, res_body)
        if result["status"] != "appended":
            print(
                f"critic-consolidate: could not append resolution fact — "
                f"{result['reason']}",
                file=sys.stderr,
            )
            return 1
        appended_resolutions += 1

    # Regenerate the derived cache FROM the stored fact (D7) — re-read so a
    # retry after a partial failure renders the original fact, not a new one.
    store = evidence.read_facts(project_dir)
    fact = next(
        (
            f
            for f in evidence.facts_of_kind(store, "review")
            if f.get("id") == review_id
        ),
        None,
    )
    if fact is None:
        print(
            "critic-consolidate: internal error — appended review fact "
            f"{review_id!r} not readable back from the store.",
            file=sys.stderr,
        )
        return 1
    # One ledger read per consolidation, shared by the cache record and the
    # relayed NEXT-ACTION line, so the two carriers of the same sentence cannot
    # quote different prices. Unavailable is a first-class answer here — the
    # formatter says so out loud rather than dropping the clause.
    from . import telemetry  # noqa: PLC0415 — lazy, matching this module's other lib imports

    price_sentence = telemetry.format_round_price(telemetry.round_price(prawduct_dir))

    record = fact_to_cache_record(fact, price_sentence)
    findings_path = prawduct_dir / ".critic-findings.json"
    atomic_write_text(findings_path, json.dumps(record, indent=2))

    # Belt-and-suspenders: the cache we just rendered must satisfy the schema
    # its readers trust. If it doesn't, that is a bug in fact_to_cache_record —
    # fail loudly rather than anchor an invalid record in the ledger.
    if not gates.validate_critic_findings(findings_path):
        print(
            "critic-consolidate: internal error — rendered cache record failed "
            "schema validation; not anchoring in the ledger.",
            file=sys.stderr,
        )
        return 1

    # Anchor in the governance ledger (telemetry + v2 gate continuity), once
    # per review. The fact append is idempotent by (kind, id), but this ledger
    # has neither key nor dedupe, and `review-stats` counts its lines — so a
    # second consolidation would double-count the review in the very instrument
    # review proportionality is measured with. Two paths reach one: a REPLAY
    # (this manifest and its partials re-materializing after success, or a
    # crash between the fact append and remove_partials), which the probe
    # closes; and an OVERLAP past the manifest check, which it only narrows —
    # read-then-write, no lock.
    if ledger.review_event_exists(prawduct_dir, review_id):
        print(
            f"critic-consolidate: {review_id} is already anchored in the "
            "ledger — not appending a second event.",
            file=sys.stderr,
        )
    else:
        models = [p.get("model") for p in partials if p.get("model")]
        argv = ["--event", "review.critic"]
        if manifest.get("scope"):
            argv += ["--scope", manifest["scope"]]
        if manifest.get("chunk"):
            argv += ["--chunk", manifest["chunk"]]
        if models:
            argv += ["--model", models[0]]
        rc = ledger.ledger_append(project_dir, argv)
        if rc != 0:
            print(
                "critic-consolidate: ledger append failed — leaving the manifest "
                "in place so consolidation can retry.",
                file=sys.stderr,
            )
            return 1

    # Persisted + anchored. Clear the critic-active marker and remove the
    # partials so a repeat call (or a straggler SubagentStop) is a clean no-op.
    critic_marker.clear_marker(prawduct_dir)
    remove_partials(prawduct_dir)

    fact_body = fact.get("body") or {}
    counts = fact_body.get("counts") or {}
    res_note = f", {appended_resolutions} resolution fact(s)" if resolutions else ""
    all_findings = fact_body.get("findings") or []
    groups = likely_duplicate_groups(all_findings)
    # A finding count is not a defect count: reviewers hold disjoint goals, so
    # two of them meeting one defect produce two findings that no exact merge
    # key can collapse. Say so here rather than let the raw count read as
    # thoroughness and drive disposition work that is partly duplicated.
    dupe_note = (
        f" (~{distinct_finding_count(all_findings, groups)} distinct; "
        f"{len(groups)} likely-duplicate group(s): "
        f"{'; '.join('+'.join(g) for g in groups)})"
        if groups
        else ""
    )
    # ...and then RENDER each group as one defect. The summary line above tells
    # the builder a number; what they act on is the list, and a list of three
    # separately-worded findings reads as three pieces of work no matter what
    # the count said. Every fid stays visible — this is a presentation of an
    # advisory grouping, never a merge, so nothing can be dropped by a wrong
    # group (the standing reason `merge_findings` refuses fuzzy keys in the
    # WRITE path).
    group_lines = _render_duplicate_groups(all_findings, groups)
    print(
        f"consolidated: {counts.get('blocking', 0)} blocking, "
        f"{counts.get('warning', 0)} warning, {counts.get('note', 0)} note"
        f"{dupe_note} "
        f"from {len(partials)} reviewer(s) → fact {review_id}{res_note} + "
        f"{findings_path.name} + ledger anchor; marker cleared."
        + group_lines
        # Only when there is something to fix — a clean pass that ended with a
        # fix strategy attached would read as work it does not have.
        + (_BATCH_FIX_DIRECTIVE if all_findings else "")
    )
    # The single-pass reviewer runs this command itself, so everything above
    # lands in the REVIEWER's context and dies there — the builder never sees a
    # word of it. This one line is the part that has to travel: both protocol
    # files tell the reviewer to relay `NEXT-ACTION:` verbatim as their closing line.
    # Code owns the wording so it cannot be paraphrased into something weaker,
    # and so it stays identical to the `next_action` the builder reads in
    # `.critic-findings.json` on the coordinator path.
    print(
        "NEXT-ACTION: "
        + next_action_line(
            review_id,
            counts.get("blocking", 0),
            counts.get("warning", 0),
            counts.get("note", 0),
            price_sentence,
        )
    )
    return 0


def remove_partials(prawduct_dir: Path) -> None:
    """Remove the manifest + every partial + the partials directory. Best-effort
    and idempotent — a missing file is fine (the point is that nothing pending
    remains). Public: ``critic-begin`` also calls this so every review starts
    from a clean partials dir — consolidate removes partials only on success, so
    a waived or stale-failed review leaves them behind.

    **The reason changed when partials gained review identity, and this is its
    one home.** It used to be a correctness requirement: a leftover partial at
    the same commit as a fresh dispatch would merge as if the new reviewer had
    written it. Keying by review id makes that impossible — a leftover is named
    as foreign, never merged. What remains is hygiene, and it is still worth
    doing: the directory stops accumulating debris no reader can use, and the
    archive stays the single place an unconsolidated review's trace lives."""
    pdir = partials_dir(prawduct_dir)
    if not pdir.is_dir():
        return
    # The LISTING is guarded, not only the per-child unlink. Both callers reach
    # here one line after `_archive_leftovers`, which degrades rather than
    # raising when this same directory cannot be read — so leaving this
    # `iterdir` bare re-raised the exception that function had just absorbed,
    # and did it AFTER its caller had printed that the partials were deleted but
    # BEFORE the marker was cleared. The operator was told the destructive thing
    # happened, and left in the wedged state anyway. Hygiene must never be the
    # step that strands someone.
    try:
        children = list(pdir.iterdir())
    except OSError:
        children = []
    for child in children:
        try:
            child.unlink()
        except OSError:
            pass
    try:
        pdir.rmdir()
    except OSError:
        pass
