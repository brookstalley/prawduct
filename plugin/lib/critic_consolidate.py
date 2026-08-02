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
  D6 edge-validity check agree by construction), ``files_reviewed``, and
  telemetry/attribution (``tier``, ``scope``, ``chunk``).
- ``<role>.json`` — one partial per roster role, written by that reviewer.
  Carries the reviewer's findings, and — for a verify-resolutions dispatch
  only — its ``resolutions`` judgments (D5).

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
_BATCH_FIX_DIRECTIVE = (
    " Disposition them ALL in ONE pass — land every fix you are going to make in"
    " ONE commit, and accept or file the rest. Only unresolved BLOCKING findings"
    " gate anything; if that commit touches judgeable files, ONE"
    " `/prawduct:critic verify-resolutions` re-covers it. A fix-commit-verify"
    " cycle per finding multiplies 5-10 minute rounds, and each round reviews the"
    " prose the previous fix wrote. Free to write at any time (they do not move"
    " coverage): everything under `.prawduct/` — change-log, backlog,"
    " project-state, build plans, regen-views output — plus"
    " `.claude/settings.json` and `.md` files OUTSIDE `skills/`,"
    " `methodology/`, `templates/` and a root `CLAUDE.md`. Everything else"
    " moves the tree and must land BEFORE the verify pass: code, config, data,"
    " tests, and those governance-protected `.md` files (a comment-only edit to"
    " a code file counts)."
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
    " not — a diff read instead of the file it changed, and a finding whose"
    " second site is in a file this delta does not touch. Spend this on the"
    " finding you feel surest about: a rule you agree with and do not apply to"
    " the disposition actually in front of you has done nothing."
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


def partials_dir(prawduct_dir: Path) -> Path:
    return prawduct_dir / PARTIALS_DIRNAME


def manifest_path(prawduct_dir: Path) -> Path:
    return partials_dir(prawduct_dir) / MANIFEST_NAME


def partial_path(prawduct_dir: Path, role: str) -> Path:
    return partials_dir(prawduct_dir) / f"{role}.json"


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
) -> dict:
    """Derive and write the dispatch manifest for one review. All code.

    Returns ``{"status": "ok", "id", "roster", "path", "notes": [...],
    "cleared_leftovers": bool, "manifest": {...}}`` or ``{"status": "error",
    "reason", "kind"?}`` where ``kind == "scope-widened"`` tells the CLI to
    exit 2 (the skill's fall-back-to-final signal).

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
        scope = buildplan_refs.infer_scope_from_branch(project_dir, prawduct_dir)
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
        committed_differs = capture["head_tree"] != base_tree
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
                        "committed HEAD, so it will read `uncovered` until you commit "
                        "(or stash) the fix and re-run verify-resolutions"
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
            return {
                "status": "error",
                "kind": "scope-widened",
                "reason": (
                    f"scope-widened: {len(delta)} files changed since the prior "
                    f"review of {len(prior_files)} — a partial re-review would "
                    "mislead; run a full review"
                ),
            }
        prior_counts = prior_body.get("counts") or {}
        actionable = (prior_counts.get("blocking") or 0) + (
            prior_counts.get("warning") or 0
        )
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

    manifest = {
        "id": review_id,
        "mode": verbose,
        "mode_chosen_by": (chosen_by or "").strip() or "not-recorded",
        "roster": roster,
        "roster_chosen_by": roster_chosen_by,
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
    }
    ok, reason = validate_manifest(manifest)
    if not ok:
        # A manifest this function derived failing its own validator is a bug
        # here — fail loudly rather than dispatch a review that can never
        # consolidate.
        return {"status": "error", "reason": f"internal error — derived manifest invalid: {reason}"}

    cleared = False
    pdir = partials_dir(prawduct_dir)
    if pdir.is_dir():
        remove_partials(prawduct_dir)
        cleared = True
    pdir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path(prawduct_dir), json.dumps(manifest, indent=2))

    return {
        "status": "ok",
        "id": review_id,
        "roster": roster,
        "path": str(manifest_path(prawduct_dir)),
        "notes": notes,
        "cleared_leftovers": cleared,
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

    Schema: ``{role, goals, commit_reviewed, model?, duration_seconds?,
    findings:[{name, goal, severity, recommendation, files?}],
    resolutions?:[{review_id, fid, disposition, rationale?}], summary}``.
    ``model``/``duration_seconds`` are nullable telemetry; everything else is
    load-bearing. ``severity`` must be one of the known vocabulary so a typo
    can't silently persist as a non-blocking finding. ``resolutions`` is the
    verify-resolutions judgment payload (D5): ``disposition`` is ``fixed`` or
    ``waived``, and ``waived`` REQUIRES a non-empty ``rationale`` (R7 — a
    waiver carries its justification).
    """
    if not isinstance(data, dict):
        return False, "partial is not a JSON object"
    if not _nonempty_str(data.get("role")):
        return False, "missing/empty 'role'"
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
                return False, (
                    f"resolution[{idx}] disposition 'waived' requires a "
                    "non-empty 'rationale' (R7)"
                )
    return True, ""


def validate_manifest(data) -> tuple[bool, str]:
    """Validate the dispatch manifest (v3 shape — written by ``begin_review``
    only).

    Required: ``id``, verbose ``mode``, ``mode_chosen_by``, ``roster``,
    ``roster_chosen_by``, ``commit_reviewed``, ``base_tree``, ``head_tree``,
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
    """
    mpath = manifest_path(prawduct_dir)
    if not mpath.is_file():
        return "none", []
    try:
        manifest = json.loads(mpath.read_text())
    except (OSError, json.JSONDecodeError):
        return "unreadable", []
    ok, _reason = validate_manifest(manifest)
    if not ok:
        return "unreadable", []
    missing = [
        role
        for role in manifest["roster"]
        if not partial_path(prawduct_dir, role).is_file()
    ]
    if missing:
        return "incomplete", missing
    return "complete", []


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

#: Jaccard overlap of significant title words above which two findings from
#: DIFFERENT reviewers are reported as probably one defect. Calibrated on this
#: repo's 254 recorded reviews: the true pair that prompted this sat at 0.44,
#: and every pair surfaced at 0.4 spot-checked as a genuine duplicate (23 pairs
#: across 16 of 209 reviews with findings, including one defect found by three
#: reviewers). Set low deliberately — the output is advisory, so a false
#: positive costs a hint while a miss costs a silently double-counted finding.
DUPLICATE_SIMILARITY = 0.4


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
    have file attributions that are not disjoint; then their significant title
    words must overlap by :data:`DUPLICATE_SIMILARITY`. Grouping is transitive,
    so one defect found by all three reviewers reports as a single group.
    """
    entries = [
        (
            f["fid"],
            f.get("goal"),
            frozenset(f.get("files") or []),
            _title_words(f.get("title") or f.get("summary")),
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
            if len(words_a & words_b) / len(words_a | words_b) >= DUPLICATE_SIMILARITY:
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


def fact_to_cache_record(fact: dict) -> dict:
    """Render the derived ``.critic-findings.json`` record from a review fact
    (D7: the cache is a code-regenerated VIEW of the latest fact — builders
    and briefings read it for content; no gate reads it). Carries the source
    ``fact_id`` so staleness is detectable and the verify-resolutions
    dispatch can locate its anchor fact."""
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
                             review_id: str) -> str:
    """The incomplete no-op with a liveness verdict, not just a partial count.
    Zero partials shortly after dispatch is the NORMAL background-reviewer
    state — say so explicitly, or the caller infers reviewer death from
    silence and double-dispatches. The wait-side variants also direct a
    periodic progress readout, so a session that correctly decides to wait
    does not idle its prompt cache into expiry while doing so."""
    age = dispatch_age_minutes(review_id)
    counts = f"{present}/{total} partials present"
    if age is not None:
        counts += f"; dispatched {age:.1f} min ago"
    line = f"no-op: review incomplete — waiting on {', '.join(missing)} ({counts})."
    if age is not None and age > _INFLIGHT_GRACE_MINUTES:
        line += (
            f" That is past the in-flight grace window (~{_INFLIGHT_GRACE_MINUTES} min)"
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
    return line


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
        ppath = partial_path(prawduct_dir, role)
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
        print(_incomplete_noop_message(missing, len(partials), len(roster), review_id))
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
    record = fact_to_cache_record(fact)
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
    print(
        f"consolidated: {counts.get('blocking', 0)} blocking, "
        f"{counts.get('warning', 0)} warning, {counts.get('note', 0)} note"
        f"{dupe_note} "
        f"from {len(partials)} reviewer(s) → fact {review_id}{res_note} + "
        f"{findings_path.name} + ledger anchor; marker cleared."
        # Only when there is something to fix — a clean pass that ended with a
        # fix strategy attached would read as work it does not have.
        + (_BATCH_FIX_DIRECTIVE if all_findings else "")
    )
    return 0


def remove_partials(prawduct_dir: Path) -> None:
    """Remove the manifest + every partial + the partials directory. Best-effort
    and idempotent — a missing file is fine (the point is that nothing pending
    remains). Public: ``critic-begin`` also calls this so every review starts
    from a clean partials dir — consolidate removes partials only on success,
    so a waived or stale-failed review leaves them behind, and a leftover
    partial at the same commit as a fresh dispatch would otherwise merge as if
    the new reviewer had written it."""
    pdir = partials_dir(prawduct_dir)
    if not pdir.is_dir():
        return
    for child in pdir.iterdir():
        try:
            child.unlink()
        except OSError:
            pass
    try:
        pdir.rmdir()
    except OSError:
        pass
