"""Critic mode inference — picks the right ``/critic`` mode from git +
build-plan state so the builder doesn't have to declare it at every chunk.

Explicit ``$ARGUMENTS`` always wins (the per-invocation override path).
Below it sits the **plan-level override**: when the active build plan's
CURRENT chunk declares a valid ``**Critic mode:**`` field, that mode is
honored as a successive override (rationale ``"plan-override: <mode>"``).
"Current" is the first open chunk, read through
:func:`lib.plan_status.current_chunks` (via :func:`binding_progress`), the one
walker of chunk progress, which this module consumes rather than reimplements:
a chunk is done when a review fact naming it certifies it, not when a box is
ticked (#1051). Re-deriving "current" here is what let the original defect
reach three consumers (CRT-7B4M). The methodology has always called this field
a "successive override," and this is where it is read (CRT-3M8Q). Only when neither override fires
does :func:`infer_mode` walk four inference rules in precedence order and
return the first that fires:

  1. ``verify-resolutions`` — prior ``.critic-findings.json`` has
     BLOCKING/WARNING findings + ``commit_reviewed`` anchor resolves **and is
     an ancestor of HEAD** + uncommitted diff is non-empty AND its judgeable
     subset is within prior ``files_reviewed`` (the review's subject set,
     which is re-narrowed here because it is not already judgeable-only —
     the eligibility classifier admits behaviour-governing prose into a
     subject set). Signal: builder is in the middle of fixing findings from
     the last review.
  1b. ``verify-resolutions`` (post-cumulative fix, CRT-4J8W) — tree clean,
     prior record is a ``cumulative`` review, and the committed delta since
     its ``commit_reviewed`` holds ≥1 judgeable file under the widening
     threshold. Signal: builder committed a fix after the cumulative; a
     verify pass reviews the delta instead of re-paying a full bundle
     review. (The v2 multi-link chain arm — a verify record carrying an
     ``extends_cumulative`` anchor — died in the kernel-v3 cutover: no
     writer emits the field, and the gates compose facts by tree, so the
     recommendation no longer needs to propagate anchors.)
  2. ``cumulative`` — working tree is clean (no uncommitted code) AND
     branch is ≥2 commits ahead of the detected base branch AND no
     ``cumulative``-mode findings file exists for current HEAD. Signal:
     builder has shipped chunks and is at the ``/pr create`` precondition
     point. **Not mid-plan** (the branch's own plan still owes a later
     review): there a clean tree means the builder committed the chunk
     before reviewing it, which is inner-stage work, so the answer is
     ``chunk`` over the unreviewed interval — from the covered frontier, or
     the merge-base when no blocker-free reviewed state is behind HEAD — or ``deferred``
     when nothing is unreviewed or a short plan defers
     (:func:`_mid_plan_answer`). The stage is keyed on cycle position, not
     commit order (``nonfunctional-requirements.md`` § Direction, the ruling
     beneath the stage-keyed rigor norm).
  2b. ``deferred`` (#292, the short-plan deferral) — the branch's plan has
     ≤ :data:`SHORT_PLAN_MAX_CHUNKS` chunks, no chunk declares a
     ``Critic mode:``, the branch is not the base itself, nothing it has
     changed is a risk surface, and code is in flight. No review is
     dispatched: the boundary review at the last chunk is every chunk's
     review, and the rationale gives :func:`short_plan_next_step` — tick each
     earlier chunk at commit, or (on the last chunk) commit and run the
     ``cumulative`` that is that chunk's review. Sits below rules 1–2 so a fix-in-progress or a committed bundle
     still gets the review it is owed; pre-empts only the inner-stage
     answers of rules 3–4. Predicate: :func:`short_plan_deferral`.
  3. ``final`` — active build plan with exactly one open chunk left (and
     no unreadable entry standing in for another) AND uncommitted work is
     present (the builder is on the last chunk),
     OR no build plan + uncommitted diff has ≥5 files (medium+
     non-chunked work).
  4. ``cumulative`` when the tree is clean and a committed bundle is
     dispatchable, since a ``chunk``/``final`` interval ends at the working
     tree and, with nothing unreviewed behind HEAD, would be empty (and
     ``critic-begin`` answers an empty interval without a review) — except mid-plan, which answers as rule 2 does; otherwise ``chunk`` —
     grounded on the plan when one exists, and the bare default when none
     does. ``final`` is never a default: the stage-keyed rigor norm
     (`nonfunctional-requirements.md` § Direction) says unsure defaults to the
     inner-stage review of whatever interval exists, and the boundary is
     never inferred away. The size escalator in rule 3 (no plan, 5+ files →
     ``final``) is untouched: ``final`` there is still an inner-stage review,
     rated on the inner BLOCKING set, and it fires on a signal rather than on
     the absence of one.

The plan rule 4 grounds on is **this checkout's binding** (``lib.work_unit``):
the plan that claims the branch, or none. A legacy-window binding — a repo
whose plans declare no branch, governed through the pointer or the
conventional path — still grounds it, and the rationale, which is what lands
in ``mode_chosen_by``, says the relation is assumed rather than shown.

Deviation from build-plan rule 2: the spec reads "branch ahead of base by
≥2 commits AND no cumulative-mode record exists for the current HEAD"
with no working-tree-clean guard. Implemented WITH the clean-tree guard
so the rule doesn't over-fire mid-chunk-3-of-5 (which would silently
demote ``chunk``-mode reviews to 4-10 min ``cumulative`` runs at every
commit). The user-feedback motivation for the whole proportionality
thread was reducing review latency for small fixes — over-firing
cumulative would undo that. The guard preserves the spec's intent (run
cumulative when about to PR) without the cost.

Pure-ish: takes ``project_dir``, reads files under it, runs ``git``
subprocesses against it. Deterministic given fixed git state. Imports only
from the stdlib + light lib siblings (``coverage``, ``gitstate``,
``buildplan_refs``, ``plan_status``, ``work_unit``) — never ``bin/prawduct-hook``, and never ``lib.gates``
(keeping gates out of this module's import graph is why the chain-anchor
helper below is a deliberate, test-pinned mirror rather than an import).
The metadata/build-plan helpers once re-implemented here moved to their
canonical homes in ``gitstate``/``buildplan_refs`` (STH-2K8R); this module
consumes them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from . import buildplan_refs, coverage_algebra, gitstate, plan_status, risk, work_unit
from .coverage import _resolve_base_branch

# Verbose-string mode constant — used to recognize prior findings'
# ``mode`` field. Must stay in lockstep with ``lib.gates``'s
# ``_CRITIC_MODE_*`` constants and ``critic_consolidate``'s
# ``MODE_TOKEN_TO_VERBOSE``. (Persisted form is verbose; caller-side
# short tokens are what we return / accept as ``args``.)
_MODE_CUMULATIVE_VERBOSE = "cumulative (bundle review, ready for merge)"

# Short-token caller-side mode names — what ``$ARGUMENTS`` carries and
# what :func:`infer_mode` returns as the first element of its tuple. The
# same token set is accepted in the build plan's per-chunk
# ``**Critic mode:**`` field (the plan-level override).
_VALID_ARG_MODES = frozenset({
    "chunk",
    "final",
    "cumulative",
    "verify-resolutions",
})

# The chunk field this module reads, built from the shared field grammar in
# ``buildplan_refs`` — the same factories the ``**Type:**`` reader uses. Hand
# copying the shape into a second module is how the two delimiter sets came to
# disagree about ``<br>``, with nothing to tell anyone they had.
#
# Why the field is searched mid-line at all: authors compose chunk headers
# (``**Type:** code · **Critic mode:** final``) and backtick the value
# (``**Critic mode:** `chunk` ``); an anchored read finds neither, and finding
# nothing is indistinguishable from a chunk that declares no mode — a
# plan-mandated `final` runs as an inferred `chunk` with no one told. That
# silent demotion is the one thing this field's reader exists to prevent.
_BUILD_PLAN_CRITIC_MODE_RE = buildplan_refs.field_token_re("Critic mode")

# The same field carrying something no mode token can be read out of —
# ``**Critic mode:** (inferred — `chunk`)``, say. Silence is not available
# there: it would say "this chunk declares no mode", and the author wrote one.
#
# Read only from FIELD POSITION, where binding is not, and that asymmetry is the
# whole point. Binding is bounded twice over — only a VALID mode wins, and only
# from a declaration position rather than a sentence mentioning the field.
# REPORTING gets neither bound's benefit: it speaks about a value it could NOT
# read, so it cannot check the value, and position is a heuristic. A note firing
# on a Description line is one its reader learns to skip — and then skips on the
# chunk that needed it. A mid-line unparseable value therefore goes unreported;
# that is the silence this field had before, kept only where speaking would cost
# more. Blank stays silent too: a field with nothing after it carries no intent
# to contradict.
_BUILD_PLAN_CRITIC_MODE_FIELD_RE = buildplan_refs.field_value_re("Critic mode")


def _unrecognized_mode_note(token: str, line_num: int | None = None) -> str:
    """The one line an ignored ``Critic mode:`` value earns.

    Fail-open-to-inference is correct and is NOT changing: a typo'd mode must
    not block a review, and nothing is skipped — inference runs and a mode is
    chosen. What was missing is that the ignore never said so. Absent and blank
    stay silent because they carry no intent to contradict; a value someone
    typed does, and swallowing it let an author believe a mode was pinned when
    it was not, discover otherwise from surprising behaviour, and file that as a
    defect against prawduct.

    The ``Type:`` hint is the specific trap worth naming: ``cumulative-final``
    is a valid ``Type:`` and reads like a mode, so an author reaching for
    "cumulative, and it's the final one" reaches for the field that takes
    ``cumulative``. Naming the right field lands the correction where the
    confusion actually is. The membership test reads
    ``buildplan_refs._BUILD_PLAN_ALLOWED_TYPES`` rather than a copy, so a Type
    added later keeps routing authors correctly.
    """
    where = f" (plan line {line_num})" if line_num is not None else ""
    note = (
        f"NOTE: chunk's `Critic mode:`{where} is {token!r}, which is not one of "
        f"{', '.join(sorted(_VALID_ARG_MODES))}. Ignoring it and inferring the "
        "mode instead — nothing was skipped."
    )
    if token in buildplan_refs._BUILD_PLAN_ALLOWED_TYPES:
        note += (
            f" {token!r} IS a valid `Type:` value — if that was the intent it "
            "belongs in that field, which is an orthogonal axis."
        )
    return note


#: The two modes whose interval ENDS at the working tree — where it starts is
#: `critic_consolidate.working_tree_interval_base`'s answer — and therefore the
#: only two an explicit token can name into an empty review. The clean-tree
#: redirect below sends them to `cumulative` at the boundary; mid-plan it asks
#: the interval owner first (:func:`_mid_plan_answer`), because there the
#: unreviewed commits are inner-stage work and a `chunk` interval can reach them.
#: `cumulative` reviews the committed bundle and `verify-resolutions` the delta
#: since a prior review fact; neither goes empty because the working tree is clean.
_WORKING_TREE_MODES = frozenset({"chunk", "final"})


def infer_mode(
    project_dir: Path | str,
    args: str | None = None,
) -> tuple[str, str]:
    """Infer the right ``/critic`` mode for the current project state.

    Parameters
    ----------
    project_dir : Path | str
        Project root (contains ``.prawduct/``). Coerced to ``Path``.
    args : str | None
        The ``$ARGUMENTS`` string passed to ``/critic``. When non-empty
        and parseable as one of the recognized mode tokens, that token
        wins (rationale ``"explicit-args"``) — except where its interval
        is provably empty, see below. Empty / None / unrecognized →
        trigger inference.

    Returns
    -------
    (mode, rationale) : tuple[str, str]
        ``mode`` is the short-token form (``chunk`` / ``final`` /
        ``cumulative`` / ``verify-resolutions``). ``rationale`` is a
        human-readable string suitable both for stdout reporting and the
        ``mode_chosen_by`` field in ``.critic-findings.json``.
    """
    project_dir = Path(project_dir)
    prawduct_dir = project_dir / ".prawduct"

    if args is not None:
        stripped = args.strip()
        if stripped:
            token = stripped.split()[0]
            if token in _VALID_ARG_MODES:
                return _explicit_mode(token, prawduct_dir, project_dir)


    # Resolve chunk progress ONCE, through the one owner of the question.
    # Re-deriving "which chunk is current" locally is what let the original
    # defect reach three consumers (CRT-7B4M), so this module asks rather than
    # re-derives — that discipline outlives the second reading it was written
    # for.
    # Which plan this branch is building: the checkout's work-unit binding, the
    # one answer the gates and the review record share. Rule 4 used to ground
    # `chunk` on whatever `active_build_plan` named, so a branch with no plan of
    # its own inherited an unrelated one's chunk count. An unbound checkout has
    # no plan here and grounds on none; a legacy-window binding is the plan, and
    # rule 4 says how it was reached rather than presenting it as a claim.
    plan = work_unit.resolve(project_dir)
    # The fact store is read ONCE per inference and threaded: `progress` carries
    # the read (:attr:`PlanProgress.facts`) and every helper below reuses it
    # rather than re-reading a store the Stop hook may hold thousands of lines of.
    from . import evidence  # noqa: PLC0415 — lazy, as this module's other lib imports are

    progress = binding_progress(project_dir, plan, facts=evidence.read_facts(project_dir))
    total = progress.total
    current_chunk_id = progress.current_id

    # Plan-level override: the CURRENT chunk may declare a ``**Critic mode:**``
    # field. Honor it here (above inference, below explicit args) so a
    # plan-mandated ``final`` is no longer silently demoted to the inferred
    # ``chunk`` (CRT-3M8Q). "Current" is the first open chunk above, so the
    # override reads the chunk actually in progress, not always Chunk 01
    # (CRT-7B4M). Only a recognized token overrides; an absent / blank /
    # unrecognized field falls through to ordinary inference.
    plan_read = (
        _critic_mode_for_chunk(prawduct_dir, current_chunk_id, plan.plan_path)
        if current_chunk_id is not None
        else ChunkModeRead(None, None)
    )
    if plan_read.mode is not None:
        return plan_read.mode, f"plan-override: {plan_read.mode}"

    # An unreadable plan escalates rather than falling through. Rule 4 would
    # answer `chunk` — the narrowest mode there is — on the strength of a plan
    # nobody could parse, and "unsure defaults cheap" is about the ABSENCE of a
    # signal; a plan that exists and cannot be read is a signal, like rule 3's
    # last-chunk and size signals, that the builder's declared state and the
    # tree disagree. The reason travels with it, so the rationale names the
    # plan instead of reporting a confident `chunk`.
    if plan_read.unreadable:
        return "final", f"rule-0 final (plan unreadable): {plan_read.unreadable}"

    # A value was typed into `Critic mode:` and matched nothing. Inference
    # proceeds — documented, correct, and not changing — but the ignore says so
    # once. Unlike its escalating sibling above, this changes no verdict.
    if plan_read.unrecognized:
        print(
            _unrecognized_mode_note(
                plan_read.unrecognized, plan_read.unrecognized_line
            ),
            file=sys.stderr,
        )

    # A later review on this plan will start from the last reviewed state and
    # cover whatever is uncovered since, so the rules below that would buy a
    # round for it now — a verify pass over a non-blocking fix, a cumulative
    # over a clean tree mid-plan — answer `deferred` instead. Asked lazily,
    # only when one of those rules fires, because it walks history.
    def _extension(clean_tree: bool = False):
        owed = extension_deferral_owed(project_dir, prawduct_dir, plan, progress)
        if owed is None:
            return None
        kind, why = owed
        # On a clean tree the owed boundary `cumulative` is the review to run
        # now, not one to defer to.
        return None if clean_tree and kind == OWED_BOUNDARY else why

    if _rule_verify_resolutions_fires(prawduct_dir, project_dir):
        ext = _extension()
        if ext:
            return MODE_DEFERRED, f"extension-deferred (fix in progress): {ext}"
        return "verify-resolutions", (
            "rule-1 verify-resolutions: prior findings have actionable "
            "(BLOCKING/WARNING) entries with a resolvable commit_reviewed "
            "anchor, and the current uncommitted diff is a non-empty "
            "subset of prior files_reviewed (builder is mid-fix)"
        )

    postfix_reason = _rule_postfix_fix_fires(prawduct_dir, project_dir)
    if postfix_reason:
        return "verify-resolutions", (
            f"rule-1b verify-resolutions (post-cumulative fix): {postfix_reason}"
        )

    cumulative_reason = _rule_cumulative_fires(prawduct_dir, project_dir)
    if cumulative_reason:
        ext = _extension(clean_tree=True)
        if ext:
            return MODE_DEFERRED, f"extension-deferred (mid-plan, clean tree): {ext}"
        mid = _mid_plan_answer(project_dir, prawduct_dir, plan, progress, "rule-2")
        if mid:
            return mid
        return "cumulative", f"rule-2 cumulative: {cumulative_reason}"

    # Short-plan deferral (#292), between rules 2 and 3. Rules 1, 1b and 2 are
    # untouched above it on purpose: a builder mid-fix on findings a prior
    # review DID record still gets `verify-resolutions`, and a clean tree with
    # a bundle still gets `cumulative` — the boundary review is what the
    # deferral defers TO, so nothing here may pre-empt it. What it pre-empts is
    # rules 3 and 4, the two that would infer an inner-stage review of the
    # uncommitted diff: on a short plan touching no risk surface that review
    # is the round the owner traded away, and inferring it would spend it.
    # Only a tree with code in flight is deferred — a record-only diff has no
    # chunk work to defer, and falls through to rule 4's honest answer.
    # Inference's reading of the deferral (`read_built=True`): a box-free short
    # plan's committed chunks are `built`, so its last chunk is visible here.
    deferral = short_plan_deferral(project_dir, prawduct_dir, plan, progress, read_built=True)
    if deferral.defers and _get_uncommitted_code_files(project_dir):
        return MODE_DEFERRED, _deferral_rationale(project_dir, deferral, plan)

    final_reason = _rule_final_fires(project_dir, progress)
    if final_reason:
        # A `Type: cumulative-final` last chunk's review IS the boundary
        # `cumulative` (planning.md), which reviews the committed bundle — so a
        # `final` of the uncommitted chunk first re-pays 4-10 minutes the
        # cumulative re-derives, and any fix it prompts then buys a verify pass
        # the cumulative would have covered too. Measured on consumers: every
        # cumulative-final plan inspected ran final → verify → cumulative.
        if boundary_cumulative_still_owed(project_dir, prawduct_dir, plan, progress):
            return MODE_DEFERRED, (
                f"cumulative-final deferral: {final_reason}, and the chunk declares "
                f"`Type: cumulative-final`; {LAST_CHUNK_BOUNDARY_STEP}. An explicit "
                "`/prawduct:critic final` still reviews the uncommitted chunk first. "
                f"Grounded on {_plan_relation_note(project_dir, plan)}"
            )
        return "final", f"rule-3 final: {final_reason}"

    # Rule 4: the default when nothing else fired is the INNER-STAGE review of
    # whatever interval exists (the stage-keyed rigor norm). `chunk` and
    # `final` both end at the captured working tree and start where
    # `critic_consolidate.working_tree_interval_base` says: HEAD's tree, the
    # covered frontier behind it, or — with no reviewed state behind HEAD and
    # nothing judgeable uncommitted — the merge-base. With nothing unreviewed behind HEAD on a
    # clean tree their interval is EMPTY and `critic-begin` answers it without a review,
    # but only after the round-trip. A mode that cannot review anything is not
    # the answer to "what should I run", whichever rule matched. At the
    # boundary `cumulative` is the mode whose interval is committed, and it is
    # what the refusal message named as the remedy — so a clean tree with a
    # dispatchable bundle answers `cumulative`. Mid-plan it does not: the stage
    # is keyed on where in the cycle the review sits, not on whether the builder
    # committed first, so the redirect asks :func:`_mid_plan_answer` before
    # sending an inner-stage review to the boundary. Everything else answers
    # `chunk`. A plan grounds the choice when one exists; without one, `chunk`
    # is still the answer, because a planless diff is an uncommitted interval
    # and the cheap review of it is the default. `final` is never the
    # fall-through: it used to be, on the belief that more review is the safe
    # failure direction, and the norm retired that belief — an inner-stage
    # review run at boundary rigor is a defect priced in minutes and rounds.
    if _working_tree_is_empty(project_dir):
        redirect = _clean_tree_redirect(prawduct_dir, project_dir)
        if redirect:
            mid = _mid_plan_answer(
                project_dir, prawduct_dir, plan, progress, "rule-4", deferral=deferral
            )
            if mid:
                return mid
            return "cumulative", f"rule-4 cumulative: {redirect}"
    if total > 0:
        return "chunk", (
            f"rule-4 chunk: {_plan_relation_note(project_dir, plan)}, prior chunks "
            "committed, no fix-in-progress signal, no cumulative precondition"
        )
    return "chunk", (
        "rule-4 chunk: no active build plan and no other rule fired — unsure "
        "defaults to the inner-stage review of whatever interval exists"
    )


def _explicit_mode(
    token: str, prawduct_dir: Path, project_dir: Path
) -> tuple[str, str]:
    """Answer a named mode, redirecting only the two whose interval can be empty.

    An explicit token is an operator instruction and the ladder does not
    second-guess it: `cumulative` and `verify-resolutions` come back exactly as
    typed, and so do `chunk` and `final` in every case but one.

    That case is the defect (#684). `chunk` and `final` share an interval
    ending at the working tree, so on a clean tree with nothing unreviewed
    behind HEAD it is EMPTY and `critic-begin`
    refuses — after the operator has spent the dispatch. Rule 4 already declines
    to *infer* a mode that cannot review anything (:func:`_clean_tree_redirect`),
    but the explicit-args return sat above the whole ladder, so naming the mode
    was the one way to reach the refusal the redirect exists to prevent.

    **Redirect, not refuse, and say whose token moved.** `cumulative` is not a
    downgrade of `final` here — it is the mode whose interval can SEE work that
    is already committed, which is the demotion property the SKILL states for
    every other refusal. The rationale therefore carries the original token, so
    `mode_chosen_by` — a durable field of the review fact — records that the
    operator asked for `final` and what moved it, rather than claiming the
    operator chose `cumulative`. "Never silently downgrade" forbids the silence;
    this is the opposite of silent.

    **Only where the redirect works.** :func:`_clean_tree_redirect` returns ""
    when `cumulative` would refuse in its own way (no resolvable base, nothing
    committed beyond it, or a fresh cumulative record already covering HEAD).
    Then the token stands and the operator gets the honest empty-interval
    refusal instead of a redirect to a second one — the same rule rule 4 keeps.

    **Nor mid-plan, where the interval is not empty.** A clean tree mid-plan
    still holds unreviewed commits when the builder committed the chunk before
    reviewing it, and the ``chunk``/``final`` interval reaches them — from the
    covered frontier, or from the merge-base when no blocker-free reviewed
    state is behind HEAD. Sending that review to ``cumulative`` would price an
    inner-stage review at boundary rigor, so the token stands and the rationale
    says why. When mid-plan nothing is unreviewed, the token stands too, and
    ``critic-begin`` answers the empty interval with exit 3 (no review needed),
    because the last review already covers HEAD. Both answers come from
    :func:`_mid_plan_verdict`, the owner inference also asks.
    """
    if token in _WORKING_TREE_MODES and _working_tree_is_empty(project_dir):
        redirect = _clean_tree_redirect(prawduct_dir, project_dir)
        if redirect:
            plan = work_unit.resolve(project_dir)
            progress = binding_progress(project_dir, plan)
            verdict = _mid_plan_verdict(project_dir, plan, progress, prawduct_dir)
            if verdict is not None and verdict[0] != _MID_PLAN_UNREACHABLE:
                kind, start = verdict
                if kind == _MID_PLAN_NOTHING_UNREVIEWED:
                    return token, (
                        f"explicit-args {token} (mid-plan, nothing unreviewed): "
                        f"{_mid_plan_note(project_dir, plan, progress)}; the last review already "
                        "covers HEAD, so this interval is empty and `critic-begin` "
                        "answers no review needed; a whole-branch `cumulative` is not owed mid-plan"
                    )
                return token, (
                    f"explicit-args {token} (mid-plan, not redirected): "
                    f"{_mid_plan_note(project_dir, plan, progress)}; {_interval_note(start)}"
                )
            return "cumulative", f"explicit-args {token} redirected: {redirect}"
    return token, "explicit-args"


def _clean_tree_redirect(prawduct_dir: Path, project_dir: Path) -> str:
    """Rationale for answering ``cumulative`` on a clean tree, or ``""``.

    ``chunk`` and ``final`` both end at the working tree, so on a clean tree
    their interval is empty unless unreviewed commits sit behind HEAD, and
    ``critic-begin`` answers an empty interval without a review. Recommending one
    anyway costs a round-trip and names no remedy the caller didn't already have.
    This answers the BOUNDARY half only: both callers ask the mid-plan owner,
    :func:`_mid_plan_verdict`, before taking the redirect, because mid-plan those
    commits are inner-stage work the ``chunk`` interval can reach.

    The caller gates this on :func:`_working_tree_is_empty`, NOT on
    :func:`_get_uncommitted_code_files` — those answer different questions, and
    the difference is exactly a record-only work cycle. That helper drops every
    path under ``.prawduct/``, while the interval comes from ``capture_tree``,
    which stages everything tracked; so uncommitted plan and change-log edits DO
    make the interval non-empty. Redirecting them to ``cumulative`` would
    note-and-exclude the records just written and stamp "working tree is clean"
    into ``mode_chosen_by`` — a durable field of the review fact — over a dirty
    tree.

    **What such a dispatch then does changed on 2026-08-06, and this distinction
    survived it.** A record-only interval is non-empty but holds nothing
    *judgeable*, so ``critic-begin`` now answers exit 3 (no review needed) rather
    than reviewing it. The reason to keep the two helpers apart is therefore no
    longer "those edits get reviewed" — it is that the two refusals are different
    answers and only one of them is true here: an empty interval is "there is
    nothing here", while a record-only interval is "there is something here and
    the gate does not need it reviewed". Redirecting the second to ``cumulative``
    would still stamp a false claim into a durable field, and would still name a
    remedy the caller does not need.

    **Only redirects when the redirect works.** ``cumulative`` needs a resolvable
    base and at least one commit beyond it, or it refuses in its own way; and a
    fresh cumulative record already covering HEAD means the bundle review was
    just run, so re-recommending it is the noise rule 2 declines to make. When
    none of that holds there is genuinely nothing dispatchable, and the caller
    keeps the inner-stage answer (``chunk``) with its honest refusal rather
    than a redirect to a second refusal.
    """
    base_branch, _ = _resolve_base_branch(project_dir)
    if not base_branch:
        return ""
    commits_ahead = buildplan_refs._commits_ahead_of_base(project_dir, base_branch)
    if commits_ahead < 1:
        return ""
    if _fresh_cumulative_covers_head(prawduct_dir, project_dir):
        return ""
    return (
        "working tree is clean, so chunk/final would dispatch an empty "
        f"interval; branch is {commits_ahead} commit(s) ahead of {base_branch} "
        "and no cumulative record covers current HEAD — the committed bundle "
        "is cumulative's scope"
    )


def _fresh_cumulative_covers_head(prawduct_dir: Path, project_dir: Path) -> bool:
    """True when the derived cache records a ``cumulative`` review of this exact
    HEAD — i.e. the bundle review has already been run and re-recommending it
    would be noise.

    One home for the question: rule 2 skips on it, and rule 4's clean-tree
    redirect must not undo that skip by routing to the mode rule 2 just declined.
    """
    head_sha = gitstate._git_head_sha(project_dir)
    findings_path = prawduct_dir / ".critic-findings.json"
    if not head_sha or not findings_path.is_file():
        return False
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return (
        data.get("commit_reviewed") == head_sha
        and data.get("mode") == _MODE_CUMULATIVE_VERBOSE
    )


class PlanProgress(NamedTuple):
    """The bound plan's progress, as :mod:`lib.plan_status` answers it.

    One walk (:func:`plan_status.chunk_states`) read four ways, so no helper
    here counts boxes or re-derives "done":

    - ``states`` — the walk itself, plan order, synthetic entries included;
    - ``open_ids`` — :func:`plan_status.current_chunks`: the open chunk ids,
      synthetic entries (an unreadable plan ``?``, a rejected heading
      ``?L<n>``) left out, so ``current_id`` is always a real chunk or ``None``;
    - ``total`` / ``complete`` — every entry, and those ``done`` or
      ``dropped``. ``total - complete`` is the open count WITH synthetic
      entries, so a plan that cannot be fully read never reads as fewer chunks
      left than it may have (authority fails closed). The two names are kept
      because the Stop hook reads ``total - complete`` and that arithmetic
      still means "chunks not done or dropped";
    - ``finished`` — :func:`plan_status.is_finished`, the only "finished"
      answer; never ``not open_ids``, which a synthetic entry makes false;
    - ``facts`` — the ``evidence.read_facts`` result the walk read, so the
      helpers handed this progress reuse that one read (:func:`_facts_for`)
      instead of reading the store again. ``None`` when nothing was read.
    """

    total: int
    complete: int
    current_id: "str | None"
    open_ids: tuple = ()
    states: "dict | None" = None
    finished: bool = True
    facts: "dict | None" = None

    @property
    def open_count(self) -> int:
        """Entries not done or dropped, synthetic ones included."""
        return self.total - self.complete

    @property
    def unreadable_open(self) -> bool:
        """Whether an open entry stands for something that could not be read."""
        return self.open_count > len(self.open_ids)


#: The progress of a checkout with no plan: no chunks, nothing current.
NO_PLAN_PROGRESS = PlanProgress(0, 0, None, (), {}, True)


def progress_of(
    plan_path: "Path | None", facts: object, *, repo_dir: Path
) -> PlanProgress:
    """:class:`PlanProgress` for ``plan_path`` against ``facts`` (a
    ``read_facts`` result) — one :func:`plan_status.chunk_states` walk."""
    store = facts if isinstance(facts, dict) else None
    if plan_path is None:
        return NO_PLAN_PROGRESS._replace(facts=store)
    states = plan_status.chunk_states(Path(plan_path), facts, repo_dir=repo_dir)
    open_ids = tuple(
        plan_status.current_chunks(Path(plan_path), facts, repo_dir=repo_dir, states=states)
    )
    return PlanProgress(
        total=len(states),
        complete=sum(1 for s in states.values() if s.state != "open"),
        current_id=open_ids[0] if open_ids else None,
        open_ids=open_ids,
        states=states,
        finished=plan_status.is_finished(
            Path(plan_path), facts, repo_dir=repo_dir, states=states
        ),
        facts=store,
    )


def binding_progress(project_dir: Path, binding, facts: "dict | None" = None) -> PlanProgress:
    """The bound plan's chunk progress, or none at all for a checkout with no plan.

    Read from :mod:`lib.plan_status` over the clone's fact store — the review
    and resolution facts certify chunks, and an unmigrated plan's ticked
    ``## Status`` boxes read as imports in memory there, not here. Only the
    binding's plan is ever read, so an unbound or broken checkout is never
    answered about a plan its binding refused.

    ``facts`` is the caller's ``evidence.read_facts`` result when it holds one;
    otherwise the store is read here — once, and only when a plan is bound. The
    read rides the returned :attr:`PlanProgress.facts` so the helpers it is
    handed to do not read again.
    """
    if binding.plan_path is None:
        return NO_PLAN_PROGRESS._replace(facts=facts)
    return progress_of(
        binding.plan_path, _facts_for(project_dir, None, facts), repo_dir=Path(project_dir)
    )


def _facts_for(project_dir: Path, progress, facts: "dict | None" = None) -> dict:
    """The fact-store read a helper works from: ``facts`` when the caller passed
    one, else the read ``progress`` carries (:attr:`PlanProgress.facts`), else
    one ``evidence.read_facts`` now — the default for a caller holding neither."""
    if facts is not None:
        return facts
    carried = getattr(progress, "facts", None)
    if carried is not None:
        return carried
    from . import evidence  # noqa: PLC0415 — lazy, as this module's other lib imports are

    return evidence.read_facts(project_dir)


def _plan_chunk_ids(plan_path: "Path | None", repo_dir: Path) -> "list[str] | None":
    """Every chunk id the plan declares, plan order; ``None`` when the plan
    cannot be read whole — the file itself, or any chunk heading the parser
    rejects (a synthetic entry), since then the list may be missing a chunk
    and "the last chunk" or "no chunk declares a mode" would be guesses.

    The roster comes from :func:`plan_status.chunk_states` walked over no
    facts: that is the plan's chunk list with no verdicts, which costs no git
    (no fact can need the reachability probe).
    """
    if plan_path is None or not Path(plan_path).is_file():
        return None
    states = plan_status.chunk_states(Path(plan_path), {"facts": []}, repo_dir=repo_dir)
    if any(s.synthetic for s in states.values()):
        return None
    return list(states)


def plan_rel(project_dir: Path, binding) -> "str | None":
    """The bound plan's path relative to the repo root, for a rationale; ``None``
    when nothing is bound (``work_unit.repo_rel`` is the display rule)."""
    if binding is None or binding.plan_path is None:
        return None
    return work_unit.repo_rel(binding.plan_path, project_dir)


def _plan_relation_note(project_dir: Path, plan) -> str:
    """How rule 4's grounding plan was reached — a claim, or the legacy window.

    A plan that claims this branch is its subject with nothing assumed. A
    legacy-window binding (the pointer or the conventional path, in a repo
    whose plans declare no branch) still governs, but nothing shows the plan
    and the branch are related, so the rationale says which route answered —
    it lands in ``mode_chosen_by``, the record a reader can find it in
    (`nonfunctional-requirements.md` § Direction: a control emits its yield
    observably or it can only be defended on principle).
    """
    rel = plan_rel(project_dir, plan) or "(unresolved)"
    if plan.is_claim:
        return f"build plan {rel}, which claims this branch"
    if plan.is_legacy:
        route = "`active_build_plan`" if plan.case == "legacy-pointer" else "the conventional path"
        return (
            f"build plan {rel}, reached through {route} and assumed related — "
            "it declares no `branch:`, so nothing confirms it is this branch's"
        )
    return f"no build plan ({plan.reason or plan.state})"


# ---------------------------------------------------------------------------
# Mid-plan: the stage is keyed on cycle position, not on commit order
# ---------------------------------------------------------------------------


def _mid_plan_start(project_dir: Path, plan, progress, deferral=None) -> "dict | None":
    """Where the ``chunk`` interval would start, when the branch is mid-plan.

    ``None`` when it is not mid-plan, which is three conditions, all required:

    - **the plan claims this branch** (``Binding.is_claim``). A plan
      reached through the legacy window is *assumed* related, and a branch
      whose plan cannot be shown keeps rule 2's boundary answer — the boundary
      is never inferred away on an assumption;
    - **a later review is owed** (:func:`later_review_owed`: two or more
      chunks open). With exactly one open chunk and a clean tree the
      boundary review is the answer. Chunk states cannot show whether the last
      chunk is BUILT, only that it is open, so :func:`short_plan_next_step`
      tells the builder to build it before asking for review;
    - **a deferring short plan is not at its boundary** (``deferral``, the
      :func:`short_plan_deferral` answer the caller holds): a short plan's
      earlier chunks are committed and left open for the boundary review to
      name, so "two or more open" says nothing there; its ``last_chunk`` —
      one chunk neither done, dropped nor built — is the boundary.

    Mid-plan, the answer is the interval owner's
    (``critic_consolidate.working_tree_interval_base``), asked with the same
    inputs ``critic-begin`` will capture, so the mode named here and the
    interval that mode then reviews cannot disagree. ``None`` too when HEAD
    cannot be read: an unreadable state keeps today's answer.
    """
    if not plan.is_claim or not later_review_owed(progress):
        return None
    if deferral is not None and deferral.defers and deferral.last_chunk:
        return None
    head_commit = gitstate._git_head_sha(project_dir)
    head_tree = _head_tree(project_dir)
    if not head_commit or not head_tree:
        return None
    from . import critic_consolidate  # noqa: PLC0415 — lazy; it imports this module lazily too

    return critic_consolidate.working_tree_interval_base(
        project_dir, head_commit, head_tree, read=getattr(progress, "facts", None)
    )


def _reaches_committed_work(start: dict) -> bool:
    """Whether a ``chunk`` interval starting at ``start`` covers unreviewed commits."""
    from . import critic_consolidate  # noqa: PLC0415 — lazy, as above

    return start["origin"] in (
        critic_consolidate.BASE_AT_FRONTIER,
        critic_consolidate.BASE_AT_MERGE_BASE,
    )


def _mid_plan_note(project_dir: Path, plan, progress) -> str:
    """Why this state is inner-stage, in the words ``mode_chosen_by`` records."""
    left = progress.open_count
    return (
        f"{left} chunk(s) of {plan_rel(project_dir, plan)} are open, so this is mid-plan and the "
        "review is inner-stage (the stage is keyed on where in the cycle the "
        "review sits, not on whether the builder committed first)"
    )


def _interval_note(start: dict) -> str:
    """Which interval the ``chunk`` review will capture, named from its start."""
    from . import critic_consolidate  # noqa: PLC0415 — lazy, as above

    if start["origin"] == critic_consolidate.BASE_AT_MERGE_BASE:
        return (
            f"{critic_consolidate.merge_base_start_reason(start.get('absent'))}, so "
            f"the interval runs from the merge-base ({start['commit'][:12]}) to the "
            "working tree"
        )
    return (
        f"the interval runs from the last reviewed state ({start['commit'][:12]}) "
        "to the working tree, so it covers the commits since"
    )


#: The mid-plan verdicts :func:`_mid_plan_verdict` returns.
_MID_PLAN_REVIEW = "review"
_MID_PLAN_NOTHING_UNREVIEWED = "nothing-unreviewed"
_MID_PLAN_UNREACHABLE = "unreachable"


def _mid_plan_verdict(
    project_dir: Path, plan, progress, prawduct_dir: "Path | None" = None, deferral=None
) -> "tuple[str, dict] | None":
    """The one owner of the mid-plan question, for every caller that asks it.

    ``None`` when the branch is not mid-plan. Otherwise ``(verdict, start)``
    with ``start`` the interval owner's answer, and the verdict one of:
    :data:`_MID_PLAN_NOTHING_UNREVIEWED` when the covered frontier is HEAD;
    :data:`_MID_PLAN_REVIEW` when the interval reaches unreviewed commits;
    :data:`_MID_PLAN_UNREACHABLE` when it cannot reach them (no reviewed state
    behind HEAD with judgeable work uncommitted, or a frontier that could not be
    looked for). Unreachable is still mid-plan, so a short plan's deferral still
    applies to it; only the ``chunk`` answer does not. Inference (:func:`_mid_plan_answer`) and an explicit token
    (:func:`_explicit_mode`) both map this verdict. Neither re-derives it,
    because a second derivation is how an explicit `chunk` reached a mid-plan
    `cumulative` in the state inference answers `deferred`. ``deferral`` is the
    caller's :func:`short_plan_deferral` answer; without one it is asked here
    (inference's reading, ``read_built=True``) when ``prawduct_dir`` is given
    and the cheap mid-plan conditions hold.
    """
    if (
        deferral is None
        and prawduct_dir is not None
        and plan.is_claim
        and later_review_owed(progress)
    ):
        deferral = short_plan_deferral(project_dir, prawduct_dir, plan, progress, read_built=True)
    start = _mid_plan_start(project_dir, plan, progress, deferral)
    if start is None:
        return None
    from . import critic_consolidate  # noqa: PLC0415 — lazy, as above

    if start["origin"] == critic_consolidate.BASE_AT_HEAD_COVERED:
        return _MID_PLAN_NOTHING_UNREVIEWED, start
    if _reaches_committed_work(start):
        return _MID_PLAN_REVIEW, start
    return _MID_PLAN_UNREACHABLE, start


def _mid_plan_answer(
    project_dir: Path, prawduct_dir: Path, plan, progress, rule: str, deferral=None
) -> "tuple[str, str] | None":
    """The mid-plan answer where a clean tree would otherwise infer ``cumulative``.

    Asked by rule 2 and by rule 4's clean-tree redirect, after
    :func:`extension_deferral` has declined. ``None`` keeps the caller's
    ``cumulative``: the branch is not mid-plan, or the interval could not reach
    the committed work (no reviewed state behind HEAD with judgeable work
    uncommitted, or a frontier that could not be looked for).

    Mid-plan it answers one of:

    - ``deferred`` when the plan is short and defers per-chunk review
      (:func:`short_plan_deferral`) — the boundary review covers every chunk,
      and a clean tree changes nothing about that trade;
    - ``deferred`` when nothing committed is unreviewed (the covered frontier
      is HEAD): the last review already covers HEAD, so no review is owed now;
    - ``chunk`` over the unreviewed interval otherwise, from the covered
      frontier or, when no blocker-free reviewed state is behind HEAD, the
      merge-base (the rationale names which of the three reasons applies).

    ``deferral`` is the caller's :func:`short_plan_deferral` answer, when it
    holds one, so the short plan's ``built`` walk runs once per inference.
    """
    if not plan.is_claim or not later_review_owed(progress):
        return None
    if deferral is None:
        deferral = short_plan_deferral(project_dir, prawduct_dir, plan, progress, read_built=True)
    verdict = _mid_plan_verdict(project_dir, plan, progress, prawduct_dir, deferral)
    if verdict is None:
        return None
    if deferral.defers:
        return MODE_DEFERRED, _deferral_rationale(project_dir, deferral, plan)
    kind, start = verdict
    note = _mid_plan_note(project_dir, plan, progress)
    if kind == _MID_PLAN_UNREACHABLE:
        return None
    if kind == _MID_PLAN_NOTHING_UNREVIEWED:
        return MODE_DEFERRED, (
            f"mid-plan deferred (nothing unreviewed): {note}; the last review "
            "already covers HEAD, so no review is owed now — build the next chunk "
            "and review it before committing"
        )
    return "chunk", f"{rule} mid-plan chunk: {note}; {_interval_note(start)}"


# ---------------------------------------------------------------------------
# Rule predicates
# ---------------------------------------------------------------------------


def _rule_verify_resolutions_fires(
    prawduct_dir: Path, project_dir: Path
) -> bool:
    """Rule 1: prior findings + anchor resolves + diff ⊆ prior scope."""
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return False
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    commit_reviewed = data.get("commit_reviewed")
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return False

    findings = data.get("findings")
    if not isinstance(findings, list):
        return False
    actionable = [
        f for f in findings
        if isinstance(f, dict) and f.get("severity") in ("blocking", "warning")
    ]
    if not actionable:
        return False

    prior_files = data.get("files_reviewed")
    if not isinstance(prior_files, list) or not prior_files:
        return False
    prior_set = {f for f in prior_files if isinstance(f, str) and f.strip()}
    if not prior_set:
        return False

    # Resolving is not enough: a sibling branch's anchor resolves in the shared
    # object store, and the delta from it would span the divergence.
    if not _commit_resolves(project_dir, commit_reviewed):
        return False
    if not _commit_is_ancestor(project_dir, commit_reviewed):
        return False

    diff_files = _get_uncommitted_code_files(project_dir)
    if not diff_files:
        return False

    # Subset check: every uncommitted JUDGEABLE file must be in the prior
    # review's surface. Even one such file outside scope means the builder added
    # new work alongside the fix — that's a chunk/final case, not a verify pass.
    # The dispatch side enforces the same "diff ⊆ scope" contract in
    # ``critic_consolidate.begin_review``, whose verify arm anchors on
    # ``_prior_review_fact`` and refuses once ``_scope_widened`` trips.
    #
    # BOTH sides re-narrowed to the coverage-priced subset, and neither call
    # is redundant. `files_reviewed` is the SUBJECT set, which since the
    # eligibility classifier admits deliverables and behaviour-governing prose
    # (`README.md`, `docs/*.md`) — so it is NOT already judgeable-only, and
    # reading it as though it were is what makes the prior-side call look like a
    # no-op to delete. Dropping either inflates a count and LOOSENS the bound,
    # which fails open: a re-review that should have fallen back to a full one
    # proceeds as a partial. The diff side is narrowed for the mirror reason —
    # comparing a raw diff against a priced set would fail the subset the moment
    # a fix touched a README, sending the cheap prose-plus-code fix this
    # framework steers toward into a full round instead of a verify pass.
    # `critic_consolidate._scope_widened` computes the identical bound and says
    # the same thing; two implementations of one threshold have to agree.
    return set(coverage_algebra.judgeable_files(sorted(diff_files))).issubset(
        set(coverage_algebra.judgeable_files(sorted(prior_set)))
    )


def _cumulative_anchor(data: dict) -> str | None:
    """Return the prior ``cumulative`` review's ``commit_reviewed`` when
    ``data`` is one, else ``None`` — the only record kind rule 1b extends.

    The v2 multi-link arm (a ``verify-resolutions`` record carrying an
    ``extends_cumulative`` anchor) was deleted in the kernel-v3 chunk-06
    vestige sweep: nothing writes the field since the cutover, and the
    gates compose review FACTS by tree, so mode inference no longer needs
    to propagate anchors through the single-slot cache. Stays-deleted
    guards live in ``tests/test_critic_mode_inference.py``.
    """
    commit_reviewed = data.get("commit_reviewed")
    if not isinstance(commit_reviewed, str) or not commit_reviewed.strip():
        return None
    if data.get("mode") == _MODE_CUMULATIVE_VERBOSE:
        return commit_reviewed
    return None


def _rule_postfix_fix_fires(prawduct_dir: Path, project_dir: Path) -> str:
    """Rule 1b (CRT-4J8W): a committed fix after a cumulative review.

    Fires when the working tree is clean, the prior record is a
    ``cumulative`` review (see :func:`_cumulative_anchor`), its
    ``commit_reviewed`` resolves, and the committed delta since it holds at
    least one judgeable file while staying under the verify-resolutions
    widening threshold, measured on the judgeable subset of both sides —
    mirroring ``critic_consolidate._scope_widened`` exactly, so the rule never
    recommends a mode that would immediately demote. Without
    this rule the canonical no-args ``/prawduct:critic`` after a
    post-cumulative fix falls through to rule 2 and recommends a FULL
    bundle re-review — the run-count treadmill this rule exists to kill
    (under v3 either recommendation records a fact the gates compose;
    the verify pass is simply the delta-cost one). A delta holding no
    **judgeable** file, or an empty one, does not fire: the existing coverage
    still spans HEAD, so no review is needed at all. Judgeable is
    :func:`coverage_algebra.is_judgeable_path`, NOT a ``.md`` suffix test —
    governance-protected prose is judgeable and does fire, which is the case
    this docstring used to get wrong along with the code below it.

    Returns a rationale string when the rule fires, ``""`` otherwise.
    """
    if _get_uncommitted_code_files(project_dir):
        return ""
    findings_path = prawduct_dir / ".critic-findings.json"
    if not findings_path.is_file():
        return ""
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return ""
    anchor = _cumulative_anchor(data)
    if anchor is None:
        return ""
    commit_reviewed = data["commit_reviewed"]  # non-empty str when anchor is not None
    if not _commit_resolves(project_dir, commit_reviewed):
        return ""
    # Same reason as rule 1: an anchor off this lineage yields a cross-branch
    # delta, and `_committed_files_since` below would take exactly that diff.
    if not _commit_is_ancestor(project_dir, commit_reviewed):
        return ""
    prior_files = data.get("files_reviewed")
    if not isinstance(prior_files, list) or not prior_files:
        return ""
    prior_set = {f for f in prior_files if isinstance(f, str) and f.strip()}
    if not prior_set:
        return ""
    delta = {
        f for f in _committed_files_since(project_dir, commit_reviewed)
        if not gitstate._is_metadata_path(f)
    }
    # THE predicate again (CRT-5D8Q). This was a FIFTH bare-suffix classifier,
    # found by the class scan the change-log-gate fix triggered — the same
    # `.endswith(".md")` shape, and wrong in the same direction: governance-
    # protected prose (the set `buildplan_refs.protected_path_violation` owns)
    # IS judgeable, so a committed delta of only skill prose used to suppress the
    # verify-resolutions suggestion as though nothing reviewable had landed.
    judgeable_delta = coverage_algebra.judgeable_files(sorted(delta))
    if not judgeable_delta:
        return ""
    # BOTH sides through the predicate, matching `critic_consolidate`'s
    # `_scope_widened`. `files_reviewed` is the subject set only on facts written
    # since that narrowing shipped; every older one carries its whole diff, and
    # this reader meets both. Narrowing the delta alone would measure a subject
    # count against a raw one on exactly those older records — the same
    # like-for-unlike comparison the narrowing itself introduced, inverted.
    judgeable_prior = coverage_algebra.judgeable_files(sorted(prior_set))
    if len(judgeable_delta) > 2 * len(judgeable_prior) + 5:
        return ""
    return (
        f"committed delta of {len(judgeable_delta)} coverage-priced file(s) "
        f"since the prior cumulative review ({commit_reviewed[:12]}); a verify "
        "pass extends the cumulative's vouching to HEAD at delta-review cost"
    )


def _rule_cumulative_fires(
    prawduct_dir: Path, project_dir: Path
) -> str:
    """Rule 2: no code in flight + ≥2 commits ahead + no fresh cumulative record.

    Returns rationale string when the rule fires, empty string otherwise.
    """
    # No CODE in flight — deliberately the metadata-stripped predicate, not the
    # strict :func:`_working_tree_is_empty` that rule 4's redirect uses. The two
    # ask different questions and the difference is load-bearing in opposite
    # directions: rule 4 asks "would a working-tree mode have anything to
    # review", where uncommitted records ARE content; rule 2 asks "is the
    # builder mid-work", where they are not. Tightening this one would mean a
    # builder with an uncommitted change-log entry — the normal state just
    # before a PR — could never be recommended the bundle review the PR gate
    # wants. See the module docstring's deviation note for why the guard exists.
    if _get_uncommitted_code_files(project_dir):
        return ""

    base_branch, _ = _resolve_base_branch(project_dir)
    if not base_branch:
        return ""

    commits_ahead = buildplan_refs._commits_ahead_of_base(project_dir, base_branch)
    if commits_ahead < 2:
        return ""

    # Skip if a cumulative-mode record already covers current HEAD —
    # re-recommending the bundle review the builder just ran is noise.
    # (The v2 chain-record arm — verify-resolutions + extends_cumulative —
    # died in the kernel-v3 chunk-06 vestige sweep: nothing writes the
    # field, so a record carrying it is v2-era state the gates ignore.)
    if _fresh_cumulative_covers_head(prawduct_dir, project_dir):
        return ""

    return (
        f"branch is {commits_ahead} commits ahead of {base_branch}, "
        "working tree clean, no fresh cumulative-mode record for "
        "current HEAD"
    )


def _rule_final_fires(project_dir: Path, progress: PlanProgress) -> str:
    """Rule 3: last chunk in progress, or no-plan medium+ work.

    Takes the :class:`PlanProgress` :func:`infer_mode` resolved. "Last chunk"
    is exactly one open chunk AND nothing synthetic open beside it: an
    unreadable plan or a rejected heading may stand for a chunk still to
    build, so it keeps the plan mid-plan (rule 4's ``chunk``) rather than
    letting the boundary-adjacent ``final`` read it as the end. Returns a
    rationale string when the rule fires, ``""`` otherwise.
    """
    total = progress.total
    if total > 0:
        # Active build plan.
        if (
            len(progress.open_ids) == 1
            and progress.open_count == 1
            and _get_uncommitted_code_files(project_dir)
        ):
            return (
                f"last open chunk ({progress.current_id}) of {total}-chunk plan is "
                f"in progress ({progress.complete} done or dropped, current chunk "
                "has uncommitted work)"
            )
        return ""

    # No active plan — fall back to size-based final for medium+ work.
    diff_files = _get_uncommitted_code_files(project_dir)
    if len(diff_files) >= 5:
        return (
            f"no build plan, session diff has {len(diff_files)} changed "
            "files (medium+ work — full review warranted)"
        )
    return ""


# ---------------------------------------------------------------------------
# Short-plan deferral (#292) — a short plan owes one boundary review
# ---------------------------------------------------------------------------

#: The answer :func:`infer_mode` gives when no review is owed NOW: the plan is
#: short, nothing it changed is a risk surface, and the boundary review at the
#: last chunk covers every chunk. Output-only — never accepted as an argument
#: or a plan field (it is not in :data:`_VALID_ARG_MODES`), because "run the
#: deferred review" is not a mode anyone runs; the skill reads it and dispatches
#: nothing. It is a fifth token rather than a non-zero exit because the skill
#: reads a non-zero exit as inference FAILING and falls back to ``chunk`` —
#: the exact review this answer exists to withhold.
MODE_DEFERRED = "deferred"

#: Upper bound on the chunk count of a plan that defers its per-chunk reviews.
#: #292's proposed bound, carried by the review-stages plan as an owner-vetoable
#: assumption; the evidence is chunk-mode yield (about one actionable finding
#: per seven chunk reviews) against the assessment's small-scope medians (five
#: rounds and twenty minutes for a scope of five files or fewer).
SHORT_PLAN_MAX_CHUNKS = 3


class ShortPlanDeferral(NamedTuple):
    """Whether the branch's plan defers per-chunk review to the boundary.

    ``reason`` is prose in the product's terms, fit for a rationale string or
    a gate message, and is filled in BOTH directions: why the plan defers, or
    which condition failed. ``last_chunk`` is whether the chunk the branch's
    uncommitted work belongs to is the plan's last — the boundary review is
    that chunk's review, so its readers (the Stop gate, the rationale) say
    something different there. It is "exactly one chunk not done or dropped",
    read by :func:`plan_status.chunk_states` against the plan AS COMMITTED AT
    HEAD (:func:`_progress_at_head`), falling back to the working tree only
    when the plan is not at HEAD: a tick made and not yet committed belongs to
    the chunk just finished, and counting it would call chunk N-1's Stop the
    last chunk's and block for a boundary review one chunk early — which chunk
    N would then owe again, two `cumulative` runs where the plan promised one.
    The facts are the same in both readings; only the plan text differs.

    With ``read_built=True`` (inference and the Stop gate both pass it) a chunk
    that is ``built`` (:func:`plan_status.built_chunks` — committed on the
    branch) does not count either: that IS the short plan's "committed, review
    deferred to the boundary" state (``1050-design.md`` § 3), and with no box to
    tick it is the only way a box-free plan's last chunk can be seen. It may
    only ARM ``last_chunk`` — make the Stop gate block for the boundary review —
    never clear it (:func:`short_plan_deferral`).
    """

    defers: bool
    reason: str
    last_chunk: bool
    total: int
    #: The open chunks' labels (``"Chunk 01"``), filled only when the plan
    #: defers — the one case whose next step names them.
    unticked: tuple = ()


def _progress_at_head(
    project_dir: Path, plan_path: "Path | None", facts: dict
) -> "PlanProgress | None":
    """:class:`PlanProgress` of the plan AS COMMITTED AT HEAD, or ``None``.

    The same walk (:func:`plan_status.chunk_states`) over the same facts, of the
    plan text at a different tree: HEAD's copy is written to a scratch file and
    walked there, with git run in ``project_dir``. ``None`` when the plan is
    not at HEAD (a new plan, or ``.prawduct/`` not tracked), when git cannot
    run, or when the path is outside the repo — the caller falls back to the
    working-tree reading, which is the only one there is in that case.
    ``facts`` is the caller's ``read_facts`` result — the store is not re-read.
    """
    import tempfile  # noqa: PLC0415 — only this reader needs a scratch file

    if plan_path is None:
        return None
    toplevel = gitstate._git_toplevel(project_dir)
    if toplevel is None:
        return None
    try:
        rel = Path(plan_path).resolve().relative_to(toplevel.resolve())
    except ValueError:
        return None
    rc, text, _err = gitstate._git_text(project_dir, "show", f"HEAD:{rel.as_posix()}")
    if rc != 0:
        return None
    with tempfile.TemporaryDirectory(prefix="prawduct-plan-at-head-") as scratch:
        copy = Path(scratch) / Path(plan_path).name
        try:
            copy.write_text(text, encoding="utf-8")
        except OSError:
            return None
        return progress_of(copy, facts, repo_dir=Path(project_dir))


def short_plan_deferral(
    project_dir: Path,
    prawduct_dir: Path,
    plan,
    progress,
    *,
    facts: "dict | None" = None,
    read_built: bool = False,
) -> ShortPlanDeferral:
    """Does this branch's plan owe one boundary review instead of one per chunk?

    A plan defers when ALL of these hold, checked cheapest-first and each
    named in ``reason`` when it fails:

    - it has between 1 and :data:`SHORT_PLAN_MAX_CHUNKS` chunks and is not
      finished (:func:`plan_status.is_finished`);
    - no chunk declares a ``Critic mode:`` — a declaration on ANY chunk is the
      plan opting out, and the existing override then governs that chunk as it
      always has;
    - the branch is not the base branch itself — on the base there is no
      merge-base…HEAD interval, so the "boundary review" the deferral names
      could never run and every chunk would be deferred to nothing;
    - no path the branch has changed (committed since the merge-base, or in
      the working tree) is a risk surface, by the SAME predicate the roster
      and ``classify-diff-risk`` use (:func:`lib.risk.paths_touch_risk_surface`
      — declared ``risk_surfaces:`` when present, else the derived defaults
      plus the product's contract paths). A second definition of "risk
      surface" for this one consumer would be a second home for the fact.

    The risk test is evaluated against the TREE, not against anything the plan
    declares about its chunks: a chunk cannot be known to touch a surface until
    it is built, so eligibility is re-asked at every inference and every Stop,
    and flips off the moment a later chunk lands on a surface — that chunk then
    owes its review like any other.

    Fails closed at every degradation: a plan that cannot be read, a base that
    does not resolve, a detached HEAD, a git listing that fails, and an
    unparseable ``risk_surfaces:`` all answer "does not defer", so per-chunk
    review stands wherever the predicate could not be evaluated. ``plan`` is
    the checkout's ``work_unit.Binding`` and ``progress`` a
    :class:`PlanProgress` (:func:`binding_progress`) — the caller resolves both
    once, through the single owners, and passes them in. ``facts`` is the
    caller's store read (default: the one ``progress`` carries).

    ``read_built`` asks :func:`plan_status.built_chunks` for ``last_chunk`` —
    the one place chunk progress walks git history, and only for a plan within
    :data:`SHORT_PLAN_MAX_CHUNKS`. Inference and the Stop gate both pass it.
    **A git-derived signal may ARM a gate, never disarm one** (coordinator
    ruling 2026-10-25; DV3's incident was git switching gates off early): so
    ``built`` can only turn the reading's "not the last chunk" (the gate warns,
    deferring) into "the last chunk" (the gate blocks for the boundary review),
    never the reverse. It is OR-ed onto the facts-and-boxes answer, it never
    reaches ``defers``, and a chunk the facts or boxes call done stays done.
    """
    total = progress.total
    if total == 0:
        return ShortPlanDeferral(False, "no build plan", False, 0)
    if progress.finished:
        return ShortPlanDeferral(
            False,
            f"every chunk of the {total}-chunk plan is done or dropped — nothing left to defer",
            False,
            total,
        )
    committed = _progress_at_head(
        project_dir, plan.plan_path, _facts_for(project_dir, progress, facts)
    )
    reading = committed if committed is not None else progress
    # The facts-and-boxes answer first; `built` may only add to it (see above).
    open_entries = [k for k, s in (reading.states or {}).items() if s.state == "open"]
    last_chunk = len(open_entries) == 1
    if not last_chunk and read_built and total <= SHORT_PLAN_MAX_CHUNKS:
        built = {
            buildplan_refs._normalize_chunk_id(c)
            for c in plan_status.built_chunks(Path(plan.plan_path), Path(project_dir))
        }
        left = [
            chunk_id
            for chunk_id in open_entries
            if (reading.states[chunk_id].synthetic
                or buildplan_refs._normalize_chunk_id(chunk_id) not in built)
        ]
        # One left is the last chunk; none left while the plan is unfinished
        # means every open chunk is already built, which is the boundary too.
        last_chunk = len(left) == 1 or (bool(built) and not left)
    return _short_plan_shape(
        project_dir, prawduct_dir, plan, total, last_chunk, progress.open_ids
    )


def _short_plan_shape(
    project_dir: Path,
    prawduct_dir: Path,
    plan,
    total: int,
    last_chunk: bool,
    open_ids: tuple,
) -> ShortPlanDeferral:
    """The short-plan conditions that are about the plan's SHAPE and the
    branch, not about how far it has got — :func:`short_plan_deferral`'s
    checks after its progress ones, also asked by :func:`review_owed_after`
    when the review just recorded finished the plan (a short plan's boundary
    ``cumulative`` is still owed then, and nothing about progress can say so).
    """
    if total > SHORT_PLAN_MAX_CHUNKS:
        return ShortPlanDeferral(
            False,
            f"the plan has {total} chunks (a short plan has at most "
            f"{SHORT_PLAN_MAX_CHUNKS})",
            last_chunk,
            total,
        )
    declared = _declared_chunk_modes(prawduct_dir, plan.plan_path)
    if declared is None:
        return ShortPlanDeferral(
            False, "the build plan could not be read", last_chunk, total
        )
    if declared:
        chunk_id, mode = declared[0]
        return ShortPlanDeferral(
            False,
            f"Chunk {chunk_id} declares Critic mode: {mode} — the plan opted out "
            "of the deferral",
            last_chunk,
            total,
        )
    branch = gitstate.current_branch(project_dir)
    if not branch:
        return ShortPlanDeferral(
            False, "HEAD is detached, so there is no branch to defer along", last_chunk, total
        )
    base_branch, base_reason = _resolve_base_branch(project_dir)
    if not base_branch:
        return ShortPlanDeferral(
            False,
            f"no base branch resolves ({base_reason}), so there is no boundary "
            "review to defer to",
            last_chunk,
            total,
        )
    if base_branch == branch or base_branch.endswith("/" + branch):
        return ShortPlanDeferral(
            False,
            f"the work is on the base branch {branch} itself, where the boundary "
            "review has no interval to cover",
            last_chunk,
            total,
        )
    paths = risk._review_scope_paths(project_dir, base_branch)
    if paths is None:
        return ShortPlanDeferral(
            False,
            "git could not list the paths this branch changed, so whether a "
            "risk surface was touched is unknown",
            last_chunk,
            total,
        )
    touched, why = risk.paths_touch_risk_surface(prawduct_dir, paths)
    if touched:
        return ShortPlanDeferral(
            False, f"a changed path is a risk surface — {why}", last_chunk, total
        )
    return ShortPlanDeferral(
        True,
        f"the plan has {total} chunk(s) and nothing {branch} has changed since "
        f"{base_branch} is a risk surface ({why})",
        last_chunk,
        total,
        _unticked_labels(open_ids),
    )


def later_review_owed(progress) -> bool:
    """Whether the branch's plan still owes a review AFTER the one just done.

    Two or more chunks not done or dropped (:attr:`PlanProgress.open_count`,
    synthetic entries included), not one. Asked where nothing says which chunk
    the work in flight belongs to — the mid-plan clean-tree answer
    (:func:`_mid_plan_start`), and :func:`review_owed_after` when the newest
    review's chunks were not certified by its own chain. There a lone open
    chunk is ambiguous: it may be the chunk under review, or the one chunk
    left, built or not. Reading it as "owed" would defer a fix that no later
    review will ever cover, so the ambiguous case keeps the round — the cost of
    the conservative reading is at most one round, never an unreviewed fix.
    When the chain DID certify the reviewed chunks they are no longer open, so
    every open chunk is a later one; :func:`review_owed_after` asks
    :attr:`PlanProgress.open_count` ``>= 1`` there instead.
    """
    return progress.total - progress.complete >= 2


def declares_boundary_cumulative(prawduct_dir: Path, plan) -> bool:
    """Whether the plan's LAST chunk declares ``Type: cumulative-final``.

    That chunk's review is the one boundary ``cumulative`` (planning.md), so a
    ``final`` before it re-pays what the cumulative re-derives, and a fix made
    after an earlier review rides it. ``False`` whenever the plan or the chunk's
    field cannot be read: this only ever relaxes a gate or withholds a round,
    and a predicate that could not run must do neither. "Last" is the plan's
    last chunk as :func:`plan_status.chunk_states` walks it.
    """
    if plan is None or plan.plan_path is None or not Path(plan.plan_path).is_file():
        return False
    ids = _plan_chunk_ids(Path(plan.plan_path), Path(prawduct_dir).parent)
    if not ids:
        return False
    chunk_type, _error = buildplan_refs._parse_build_plan_chunk_type(
        prawduct_dir, ids[-1], Path(plan.plan_path)
    )
    return chunk_type == "cumulative-final"


#: The two answers :func:`review_owed_after` gives: a later CHUNK's review
#: starts from the newest committed state a review covers, while the boundary
#: ``cumulative`` spans the branch from the merge-base. Both cover a fix committed before them, but
#: the advice names the review that will, so the two stay distinguishable.
OWED_LATER_CHUNK = "later-chunk"
OWED_BOUNDARY = "boundary"


def review_owed_after(
    project_dir: Path, prawduct_dir: Path, plan, progress, chain: list[dict]
) -> "tuple[str, str] | None":
    """Which review the branch's plan still owes after the newest one, and why.

    The one owner of "a later review will cover this", read by the Stop gate's
    extension deferral, inference and the review close. ``chain`` is the review
    chain the newest review stands on (:func:`review_chain`). Returns
    ``(kind, reason)`` or ``None``:

    - nothing is owed once a ``cumulative`` is on the chain
      (:func:`boundary_review_on_chain`): it spans every chunk built so far, so
      no later chunk review is coming to carry anything;
    - when the chain's own facts certified every chunk it names
      (:func:`chain_certified_chunks`), those chunks are done, so every chunk
      still open is a LATER one: :data:`OWED_LATER_CHUNK` when one or more is
      open, and when none is (this review finished the plan)
      :data:`OWED_BOUNDARY` if the plan's boundary is a ``cumulative`` that has
      not run — the last chunk declares ``Type: cumulative-final``, or the plan
      has a short plan's shape (:func:`_short_plan_shape`);
    - otherwise nothing says the reviewed chunk is closed, so the ambiguous
      reading stands: :data:`OWED_LATER_CHUNK` when two or more chunks are
      open (:func:`later_review_owed`), and with exactly one open,
      :data:`OWED_BOUNDARY` on the same two conditions (the short plan through
      :func:`short_plan_deferral`). The lone open chunk is ambiguous for a
      chunk review (under review, or still to build), but not here: whichever
      it is, the cumulative is still owed, and nothing short of it discharges
      it.

    ``None`` on any read failure, through the predicates it composes.
    """
    if progress.total <= 0 or boundary_review_on_chain(chain):
        return None
    left = progress.open_count
    where = plan_rel(project_dir, plan) or "the plan"
    if chain_certified_chunks(progress, chain) is not None:
        if left >= 1:
            return OWED_LATER_CHUNK, (
                f"{left} more chunk(s) of {where} follow, so a later review is owed"
            )
        if declares_boundary_cumulative(prawduct_dir, plan):
            return OWED_BOUNDARY, _BOUNDARY_CUMULATIVE_FINAL_WHY
        shape = _short_plan_shape(project_dir, prawduct_dir, plan, progress.total, True, ())
        if shape.defers:
            return OWED_BOUNDARY, (
                f"the plan is short ({shape.reason}), so the boundary `cumulative` is "
                "every chunk's review and has not run yet"
            )
        return None
    if later_review_owed(progress):
        return OWED_LATER_CHUNK, (
            f"{left - 1} more chunk(s) of {where} follow, so a later review is owed"
        )
    if left != 1:
        return None
    if declares_boundary_cumulative(prawduct_dir, plan):
        return OWED_BOUNDARY, _BOUNDARY_CUMULATIVE_FINAL_WHY
    deferral = short_plan_deferral(project_dir, prawduct_dir, plan, progress)
    if deferral.defers:
        return OWED_BOUNDARY, (
            f"the plan is short ({deferral.reason}), so the boundary `cumulative` is "
            "every chunk's review and has not run yet"
        )
    return None


_BOUNDARY_CUMULATIVE_FINAL_WHY = (
    "the plan's last chunk is `Type: cumulative-final`, so its review is the "
    "boundary `cumulative`, which has not run yet"
)


def chain_named_chunks(chain: list[dict]) -> list[str]:
    """The chunk ids the NEWEST fact on ``chain`` that names any names, as it
    spells them — so a chunk-less ``verify-resolutions`` pass inherits the
    chunk review it verifies. ``[]`` when no fact on the chain names a chunk.
    The one inheritance rule, read by :func:`chain_certified_chunks` and by
    ``critic_consolidate``'s ``verify-resolutions`` proposal."""
    for fact in chain:
        ids = plan_status.fact_chunks(fact.get("body") or {})
        if ids:
            return ids
    return []


def chain_certified_chunks(progress: PlanProgress, chain: list[dict]) -> "tuple | None":
    """The chunks ``chain`` reviewed, when its own facts certified every one; else ``None``.

    The reviewed chunks are those the NEWEST fact on the chain that names any
    names (:func:`plan_status.fact_chunks`, the one reader of the field), so a
    chunk-less ``verify-resolutions`` pass inherits the chunk review it
    verifies — and an earlier chunk's review further back on the chain does
    not widen the set. They are certified BY THE CHAIN when
    :func:`plan_status.chunk_states` reads each as ``done`` with ``fact_id`` a
    fact on the chain — not an import (a ticked box or a ``chunk-imported``
    fact: a box ticked after its review is the builder saying they moved on),
    and not a review elsewhere. ``None`` when the chain names nothing, names a
    chunk the plan does not have, or any named chunk is open, dropped,
    imported or certified off the chain: then nothing shows the reviewed work
    closed, and callers keep the ambiguous reading. Plan order.
    """
    named = list(
        dict.fromkeys(buildplan_refs._normalize_chunk_id(c) for c in chain_named_chunks(chain))
    )
    if not named or not progress.states:
        return None
    chain_ids = {f.get("id") for f in chain}
    by_norm = {
        buildplan_refs._normalize_chunk_id(k): (k, s)
        for k, s in progress.states.items()
        if not s.synthetic
    }
    certified: list[str] = []
    for norm in named:
        entry = by_norm.get(norm)
        if entry is None:
            return None
        chunk_id, state = entry
        if state.state != "done" or state.imported or state.fact_id not in chain_ids:
            return None
        certified.append(chunk_id)
    order = list(progress.states)
    return tuple(sorted(certified, key=order.index))


def boundary_cumulative_still_owed(
    project_dir: Path, prawduct_dir: Path, plan, progress, *, facts: "dict | None" = None
) -> bool:
    """Whether a ``Type: cumulative-final`` last chunk's boundary ``cumulative``
    has yet to run on this branch: exactly one chunk is left open (the last
    one, under way) and no ``cumulative`` stands on the newest review's chain —
    so once that cumulative stands, a later edit gets a ``verify-resolutions``
    delta, not a second full cumulative.

    Asked directly rather than through :func:`review_owed_after`, which answers
    what is owed AFTER the newest review: when that review certified an earlier
    chunk, the one open chunk is a later chunk to it, while here it is the
    chunk whose review is the boundary."""
    if progress.open_count != 1 or not declares_boundary_cumulative(prawduct_dir, plan):
        return False
    read = _facts_for(project_dir, progress, facts)
    newest = _newest_branch_review(project_dir, read)
    chain: list[dict] = []
    if newest is not None:
        chain = review_chain(read.get("facts") or [], newest)
    return not boundary_review_on_chain(chain)


def _newest_branch_review(project_dir: Path, facts: "dict | None" = None) -> "dict | None":
    """The most recent ``review`` fact recorded on the checked-out branch, or ``None``.

    Read from the clone-wide store and filtered by the ``actor.branch`` each fact
    carries, so a sibling worktree's reviews of another branch never answer for
    this one. Its tree need not be committed: a review of uncommitted work is
    exactly the case where the tree it judged exists nowhere in the history.
    ``facts`` is the caller's ``read_facts`` result; read here when absent.
    """
    branch = gitstate.current_branch(project_dir)
    if not branch:
        return None
    read = _facts_for(project_dir, None, facts)
    if read.get("status") == "error":
        return None
    reviews = [
        f for f in read.get("facts") or []
        if f.get("kind") == "review" and (f.get("actor") or {}).get("branch") == branch
    ]
    # The store is append-only, so its order IS the recording order; `ts` has
    # one-second resolution and two reviews can share it. Position breaks the
    # tie — a timestamp alone picks arbitrarily between same-second reviews.
    return reviews[-1] if reviews else None


def review_chain(facts: list[dict], newest: dict) -> list[dict]:
    """Every review fact on the chain ``newest`` stands on, newest first.

    The chain is structural: each review's ``base_tree`` is the ``head_tree`` of
    the review before it (the link ``critic_consolidate.carried_blocking`` reads
    one hop of). EVERY review standing at a linked tree is included, not only
    the newest there, because a second review of an unchanged tree must not hide
    the first; the walk steps back through the newest of them. Walked to the
    end, because a chain can be several passes long.
    """
    reviews = [f for f in facts if f.get("kind") == "review"]
    # Append order is recording order (the store is append-only); `ts` has
    # one-second resolution, so it cannot order two reviews in the same second.
    position = {f.get("id"): i for i, f in enumerate(reviews)}
    chain: list[dict] = []
    seen: set[str] = set()
    current: "dict | None" = newest
    while current is not None and current.get("id") not in seen:
        seen.add(current.get("id"))
        chain.append(current)
        base = (current.get("body") or {}).get("base_tree")
        here = position.get(current.get("id"), len(reviews))
        earlier = [
            f for f in reviews
            if f.get("id") not in seen and (f.get("body") or {}).get("head_tree") == base
            and position[f.get("id")] < here
        ]
        for other in earlier[:-1]:
            seen.add(other.get("id"))
            chain.append(other)
        current = earlier[-1] if earlier else None
    return chain


def _open_blocker_on_chain(facts: list[dict], chain: list[dict]) -> bool:
    """Whether any review on ``chain`` still holds an unresolved blocker.

    A ``verify-resolutions`` pass records resolutions for the findings it names
    and does not copy forward the ones it leaves open, so the newest review can
    be clean while one it stands on is not. An open blocker anywhere on the
    chain also blocks the gates, whose composed path stands on the same trees.
    """
    resolved = coverage_algebra.resolution_index(facts)
    return any(coverage_algebra.unresolved_blocking(f, resolved) for f in chain)


def boundary_review_on_chain(chain: list[dict]) -> bool:
    """Whether a ``cumulative`` sits on ``chain`` — the builder is at the boundary.

    A ``cumulative`` spans every chunk built so far and names every chunk open
    at its dispatch (``plan_status.propose_chunks``), so after one an open chunk
    cannot say whether it is still to be built or was left out of that set; on
    a plan with ``## Status`` boxes, a box awaiting its tick reads the same as
    one still to build. The review's mode can: a ``cumulative`` is the
    end-of-plan or pre-PR review, so no later chunk review is coming to carry
    anything, and nothing may defer.
    """
    return any(
        str((f.get("body") or {}).get("mode", "")).startswith("cumulative") for f in chain
    )


def extension_deferral(
    project_dir: Path, prawduct_dir: Path, plan, progress, *, facts: "dict | None" = None
) -> "str | None":
    """Why the next review will cover this state, or ``None`` when it will not.

    :func:`extension_deferral_owed`'s reason without its kind — for the Stop
    gate and ``cost-of-commit``, which defer either way.
    """
    owed = extension_deferral_owed(project_dir, prawduct_dir, plan, progress, facts=facts)
    return owed[1] if owed else None


def extension_deferral_owed(
    project_dir: Path, prawduct_dir: Path, plan, progress, *, facts: "dict | None" = None
) -> "tuple[str, str] | None":
    """``(kind, reason)`` when the next review will cover this state, else ``None``.

    ``facts`` is the caller's ``read_facts`` result (default: the read
    ``progress`` carries, else one read here), handed on to
    ``gates.covered_frontier`` (``read=``).

    ``kind`` is :func:`review_owed_after`'s. Inference needs it: on a clean
    tree the boundary ``cumulative`` is not a review to defer TO, it is the
    review to run now, so only a later chunk's review defers there.

    A review of the uncovered work since the last reviewed tree is not owed NOW
    only when ALL of these hold — each is the answer to a way the deferral can
    skip a review that is owed:

    1. **The pending work is a fix to the reviewed chunks, not a chunk nobody
       reviewed.** Otherwise deferring it would skip that chunk's review rather
       than carry a fix. The reviewed chunks are those the newest review on
       the branch (:func:`_newest_branch_review`) names, inherited along the
       chain it stands on (:func:`review_chain`), so a ``verify-resolutions``
       pass that names none carries the chunk review it verifies — set
       membership through :func:`plan_status.fact_chunks`, never a
       Status-derived id (record-lint's graded chunk is the first-open reading
       ``progress.current_id`` is, so it would match a parked chunk nobody
       reviewed, #911). A chain naming no chunk defers nothing. Which shape
       answers depends on what can certify the plan:

       - **(1a) the chain certified them** (:func:`chain_certified_chunks`):
         every reviewed chunk is ``done`` by a fact on the chain, AND the work
         since the newest review's tree touches no OPEN chunk's Deliverables
         (:func:`plan_status.propose_chunks` in ``chunk`` mode over those
         paths is empty). A review closes its chunks the moment it records,
         so no tick marks "the builder moved on"; the observable stands in for
         the stored one (``hook-surface.md``: observable beats stored).
         **Fail-open, accepted (coordinator, 2026-10-25):** a chunk whose
         Deliverables name no path-shaped token can never be proposed, so new
         work on it reads as a fix and defers. That widens the next review's
         interval and loses no coverage, because the later review still
         starts at the covered frontier (condition 4) and spans this work.
       - **(1b) nothing on the plan can certify them** (a legacy-window
         binding: the plan declares no ``branch:``, so review facts complete
         nothing and only boxes and imports do): the reviewed chunk is the
         CURRENT one, still open — the reading this predicate had before
         facts certified chunks.
    2. **No open blocker on the chain it stands on**
       (:func:`_open_blocker_on_chain`). Checked on the facts, not on the
       committed history: a review of uncommitted work leaves its tree nowhere
       a history walk can find, so a blocker it raised is invisible to
       :func:`gates.covered_frontier`. And not on the newest fact alone: a
       verify pass does not copy forward a blocker it left open. Blockers clear
       only through ``verify-resolutions``. Nor a ``cumulative`` on that chain
       (:func:`boundary_review_on_chain`): after the boundary review, no later
       chunk review is coming.
    3. **A later review is owed** (:func:`review_owed_after`). Under (1a) one
       or more open chunks, since the reviewed ones are closed; under (1b) two
       or more, "this reviewed chunk, and at least one after it". When none is
       left, the plan's boundary ``cumulative`` is owed when the last chunk
       declares ``Type: cumulative-final`` or the plan is short — and it spans
       the branch from the merge-base, so it covers a fix committed before it.
    4. **A covered frontier exists** (``gates.covered_frontier``), so that later
       ``chunk``/``final`` review has a reviewed state to start from and covers
       everything after it. The boundary ``cumulative`` needs none: its interval
       starts at the merge-base.

    ``None`` on any failure, so a predicate that could not run never relaxes
    anything.
    """
    if progress.total <= 0:
        return None
    read = _facts_for(project_dir, progress, facts)
    newest = _newest_branch_review(project_dir, read)
    if newest is None:
        return None
    from . import gates  # noqa: PLC0415 — lazy; gates is heavy and one-way

    fact_list = read.get("facts") or []
    chain = review_chain(fact_list, newest)
    reviewed = chain_certified_chunks(progress, chain)
    if reviewed is not None:
        pending = _paths_since_tree((newest.get("body") or {}).get("head_tree"), project_dir)
        if pending is None or plan_status.propose_chunks(
            Path(plan.plan_path), read, pending, "chunk", repo_dir=Path(project_dir)
        ):
            return None
        label = ", ".join(reviewed)
    else:
        if not getattr(plan, "is_legacy", False) or progress.current_id is None:
            return None
        named = next(
            (ids for ids in (plan_status.fact_chunks(f.get("body") or {}) for f in chain) if ids),
            [],
        )
        current = buildplan_refs._normalize_chunk_id(str(progress.current_id))
        if current not in {buildplan_refs._normalize_chunk_id(c) for c in named}:
            return None
        label = progress.current_id
    if _open_blocker_on_chain(fact_list, chain):
        return None
    owed = review_owed_after(project_dir, prawduct_dir, plan, progress, chain)
    if owed is None:
        return None
    kind, why = owed
    if kind == OWED_BOUNDARY:
        return kind, (
            f"chunk {label} was reviewed with no open blocker and {why}. "
            "That review spans the branch from the merge-base, so it covers this work "
            "too. Commit, then run `/prawduct:critic` when the chunk is done — it infers "
            "the cumulative"
        )
    frontier = gates.covered_frontier(project_dir, read=read)
    if frontier is None:
        return None
    return kind, (
        f"chunk {label} was reviewed with no open blocker and {why}, and it "
        f"starts from the newest committed state a review covers ({frontier['commit'][:12]})"
        " — it covers this "
        "work too. Commit and carry on"
    )


def _paths_since_tree(tree: object, project_dir: Path) -> "set[str] | None":
    """Every path that differs between ``tree`` and the working tree, untracked
    files included; ``None`` when ``tree`` is not an object id or git fails.

    The work since a review: what :func:`extension_deferral_owed` asks the
    plan's Deliverables about. ``None`` defers nothing.
    """
    if not gitstate.is_object_id(tree):
        return None
    rc, changed, _err = gitstate._git_text(project_dir, "diff", "--name-only", str(tree), "--")
    if rc != 0:
        return None
    rc, untracked, _err = gitstate._git_text(
        project_dir, "ls-files", "--others", "--exclude-standard"
    )
    if rc != 0:
        return None
    return {
        line.strip()
        for line in (changed + "\n" + untracked).splitlines()
        if line.strip()
    }


def _declared_chunk_modes(
    prawduct_dir: Path, plan_path: Path | None
) -> "list[tuple[str, str]] | None":
    """Every ``(chunk_id, mode)`` a plan's chunks declare, in plan order;
    ``None`` when the plan (or one of its chunk sections) cannot be read.

    Reads each chunk through :func:`_critic_mode_for_chunk`, the one reader of
    the field, so a declaration counts here exactly when it would count as an
    override there — an unrecognized value is ignored in both places.
    """
    # The roster comes back finished from its one owner (`plan_status`);
    # walking the plan here would be re-deriving the chunk list privately
    # (BLD-7K3Q).
    ids = _plan_chunk_ids(plan_path, Path(prawduct_dir).parent)
    if ids is None:
        return None
    found: list[tuple[str, str]] = []
    for chunk_id in ids:
        read = _critic_mode_for_chunk(prawduct_dir, chunk_id, plan_path)
        if read.unreadable:
            return None
        if read.mode is not None:
            found.append((chunk_id, read.mode))
    return found


def _unticked_labels(open_ids) -> tuple:
    """The open chunks (:attr:`PlanProgress.open_ids`, from
    :func:`plan_status.current_chunks`) as ``"Chunk NN"`` labels."""
    return tuple(f"Chunk {chunk_id}" for chunk_id in open_ids)


#: What a builder does on a plan's last chunk when that chunk's review IS the
#: boundary ``cumulative`` — a short plan's, or a ``Type: cumulative-final``
#: chunk's. One statement, because inference, the Stop gate and the short-plan
#: rationale all say it, and a second wording is how two of them came to
#: disagree about whether a ``final`` runs first.
LAST_CHUNK_BOUNDARY_STEP = (
    "this is the last chunk and the boundary review is its review: "
    "commit it, then `/prawduct:critic` infers `cumulative`, which is "
    "this chunk's review and the PR gate's evidence — no separate `final`"
)


#: The short-plan deferral knows one boundary, the plan's last chunk, because
#: it assumes one PR per plan. A chunk that ships as its own PR is a boundary
#: too, and the existing declaration already handles it (#999): any
#: `Critic mode:` turns the deferral off, and the current chunk's declaration
#: is what inference honours. One wording, read by the inference rationale and
#: the Stop gate's non-final warning.
SHORT_PLAN_OWN_PR_NOTE = (
    "If this branch opens a PR before the plan's last chunk, that PR is a "
    "boundary: run `/prawduct:critic cumulative`, and declare "
    "`Critic mode: cumulative` on chunks that ship as their own PR"
)


def short_plan_next_step(deferral: ShortPlanDeferral) -> str:
    """What a builder on a deferring short plan does next — the ONE statement.

    The inference rationale and both Stop-gate messages (the non-final warning
    and the last-chunk block) compose this, so the rule cannot be stated two
    ways. The rule: an earlier chunk's review is the boundary ``cumulative``,
    so the chunk is COMMITTED and left for it — nothing is ticked, because the
    boundary review names every chunk still open (``plan_status``:
    ``propose_chunks`` in ``cumulative`` mode) and its fact closes them all.
    Inference sees a committed chunk as ``built`` (:func:`short_plan_deferral`,
    ``read_built``) when its subject names it or its diff touches the chunk's
    Deliverables paths — hence "naming it in the subject" — so the boundary is
    inferred as soon as one chunk is left
    neither done nor committed on a clean tree, whether or not that last chunk
    is built — so the text says to build it first.
    """
    if deferral.last_chunk:
        return LAST_CHUNK_BOUNDARY_STEP
    named = (
        f" (open now: {', '.join(deferral.unticked)})" if deferral.unticked else ""
    )
    return (
        "commit this chunk, naming it in the subject (`… (Chunk <id>)`) — a "
        f"deferred chunk's review is the boundary's, so it waits for none{named}. "
        "Then build the last chunk before asking for review: `/prawduct:critic` "
        "infers the boundary `cumulative` once one chunk is left uncommitted and "
        "the tree is clean, and that review names every chunk still open and "
        "closes them together"
    )


def _deferral_rationale(project_dir: Path, deferral: ShortPlanDeferral, plan) -> str:
    """The ``mode_chosen_by``-shaped sentence for a :data:`MODE_DEFERRED` answer.

    The next step is :func:`short_plan_next_step`'s, the one statement the
    Stop gate composes too. The rationale adds the way back to a per-chunk
    review, because a deferral the reader cannot decline is a gate, and this
    is advice.
    """
    return (
        f"short-plan deferral: no per-chunk review is owed — {deferral.reason}; "
        f"{short_plan_next_step(deferral)}. {SHORT_PLAN_OWN_PR_NOTE}. "
        "An explicit mode (`/prawduct:critic chunk`) or a "
        "`Critic mode:` field on any chunk restores per-chunk review. "
        f"Grounded on {_plan_relation_note(project_dir, plan)}"
    )


# ---------------------------------------------------------------------------
# Internal helpers — git + build-plan parsing
# ---------------------------------------------------------------------------


def _working_tree_is_empty(project_dir: Path) -> bool:
    """True when the working tree holds NO uncommitted change at all.

    The honest predicate for "a working-tree-scoped mode has nothing to review":
    it counts metadata too, because ``capture_tree`` — which derives the actual
    interval — stages everything tracked and does not strip ``.prawduct/``.
    :func:`_get_uncommitted_code_files` answers the narrower "is there *code* in
    flight", which the size-based rules want and this does not.

    Fails toward NOT empty: any git failure returns False, so an unreadable
    state keeps the caller on the inner-stage answer rather than redirecting
    to the boundary on a tree it could not read. The guard covers the *raise*
    class too — an absent binary or the timeout — because a docstring promising a return value while
    the call propagates is a promise the code does not keep.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    return not proc.stdout.strip()


def _head_tree(project_dir: Path) -> str | None:
    """``HEAD^{tree}``, or ``None`` when it cannot be read (fails toward no answer)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    tree = proc.stdout.strip()
    return tree if proc.returncode == 0 and tree else None


def _get_uncommitted_code_files(project_dir: Path) -> set[str]:
    """Return uncommitted-change file paths (vs HEAD), minus metadata.

    Includes modifications, staged changes, untracked files. Rename
    targets are returned (porcelain ``XY <old> -> <new>``). Uses
    ``--untracked-files=all`` so a new directory expands to per-file
    entries rather than collapsing to ``?? subdir/`` (the default
    ``--untracked-files=normal`` undercounts new directories — caught
    by ``test_wins_for_no_plan_medium_plus_work``). The ``-uall`` flag is
    why this keeps its own ``git status`` call instead of
    ``gitstate.git_status_output``; line parsing (quoted paths, renames)
    is ``gitstate.parse_porcelain_line``.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return set()
    files: set[str] = set()
    for line in proc.stdout.splitlines():
        parsed = gitstate.parse_porcelain_line(line)
        if parsed is None:
            continue
        path = parsed[2]
        if not gitstate._is_metadata_path(path):
            files.add(path)
    return files


def _committed_files_since(project_dir: Path, sha: str) -> set[str]:
    """Files changed in ``<sha>..HEAD`` (committed delta). ``set()`` on failure."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{sha}..HEAD"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _commit_resolves(project_dir: Path, sha: str) -> bool:
    """True iff ``sha`` resolves to a commit in this repo.

    Necessary but NOT sufficient for an anchor — see :func:`_commit_is_ancestor`.
    Worktrees of one clone share an object store, so this succeeds for any object
    in it, a sibling branch's tip included.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode == 0


def _commit_is_ancestor(project_dir: Path, sha: str) -> bool:
    """True iff ``sha`` is an ancestor of HEAD — i.e. on *this* lineage.

    The guard :func:`_commit_resolves` is not. A record left by a sibling branch
    survives a branch switch in the single-slot ``.critic-findings.json``, and
    its anchor still resolves in the shared object store — so resolution alone
    let a verify-resolutions dispatch latch onto a cross-branch anchor and diff
    across the divergence, reviewing phantom changes this branch never made.

    **Fails closed.** Only exit 0 is an ancestor; exit 1 (genuinely not one) and
    any other failure — git missing, timeout, a malformed SHA — all return False,
    so an anchor that cannot be *placed* is never trusted. The mirror shape is
    ``coverage.py``'s and ``briefing.py``'s, which run the same plumbing command.
    """
    try:
        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


# `_commits_ahead_of_base` / `_committed_chunk_ids` moved to lib/buildplan_refs.py
# (a third mover, `_git_aware_progress`, was not moved but DELETED — the
# git-derived second reading of chunk progress is retired, so a reader following
# this pointer would grep for a function that exists nowhere) — they answer "which chunk is current," which is
# build-plan parsing, and keeping the derivation here made it reachable
# only by this module's consumer (the defect recurred at two others: BLD-7K3Q,
# SCN-4H9T). This module now reaches it through `plan_status` (via
# `binding_progress`), the one walker of chunk progress (#1051).


class ChunkModeRead(NamedTuple):
    """What reading a chunk's ``**Critic mode:**`` field found.

    Two fields because ``None`` alone cannot carry the difference that matters:
    *this chunk declares no mode* and *this plan could not be read* both mean
    "no override", but only the second means inference is working from a plan it
    cannot trust. Collapsing them sends an unreadable plan down rule 4 to
    ``chunk`` with a rationale that never mentions the plan — the silent
    demotion CRT-3M8Q exists to prevent, arriving by a different door.

    ``unreadable`` is prose naming why, for the rationale string; ``None`` when
    the plan read fine.
    """

    mode: str | None
    unreadable: str | None
    #: The value found where a mode was expected, when no mode could be read
    #: out of it. A THIRD state, for the same reason ``unreadable`` is a second:
    #: absent and blank carry no intent to contradict, but a value someone typed
    #: does. It must not escalate the way ``unreadable`` does — a typo'd mode is
    #: no reason to spend a heavier review, and inference proceeding is correct
    #: — so it changes no verdict and earns only a line saying it was ignored.
    unrecognized: str | None = None
    #: Which line of the plan carried it, so the note can point at it rather
    #: than describe it. Set together with ``unrecognized``, never alone.
    unrecognized_line: int | None = None


def _critic_mode_for_chunk(
    prawduct_dir: Path, chunk_id: str | None, plan_path: Path | None = None
) -> ChunkModeRead:
    """Return ``chunk_id``'s declared mode and whether its plan could be read.

    Finds that chunk's ``### Chunk <id>:`` detail section and reads its
    ``**Critic mode:** <value>`` field, wherever on its line it sits and
    whether or not its value is backticked. Returns the short-token value
    only when it is one of the recognized modes; anything else falls through
    to inference rather than honoring a typo as a mode override — the same
    fail-open posture the methodology's "optional field" contract implies.

    What "anything else" carries differs, and the third field is why. An absent
    or blank value yields ``ChunkModeRead(None, None)`` and says nothing. A
    value someone typed that no mode can be read out of — a typo, or prose
    where a token belongs — yields ``ChunkModeRead(None, None, <value>)``, and
    the caller notes it: inference proceeds either way, but only one of the two
    is an author being quietly overruled. The whole section is scanned, so a
    real declaration always beats an unhonorable value above it.

    ``chunk_id`` is resolved by the caller: the first open chunk
    (:attr:`PlanProgress.current_id`, from :func:`plan_status.current_chunks`
    — CRT-7B4M). Section discovery is
    the shared ``buildplan_refs._chunk_section_lines`` walker: name-anchored
    on ``### Chunk <id>:`` with leading-zero tolerance, fenced code blocks
    skipped, stop at the next sibling chunk or top-level section. A plan carrying a chunk heading that walker cannot read yields
    ``ChunkModeRead(None, <reason>)`` instead, and the caller escalates on it.
    """
    if chunk_id is None:
        return ChunkModeRead(None, None)

    # ``plan_path`` is the plan the chunk id came from — `infer_mode`'s bound
    # plan — and nothing else is consulted: reading a different plan here than
    # that one is how a chunk's declared mode gets read off the wrong file.
    if plan_path is None or not plan_path.is_file():
        # No plan at all is not an unreadable plan: rule 4 already grounds its
        # choice on the plan's absence and says so, so there is nothing here that
        # inference does not already know.
        return ChunkModeRead(None, None)
    try:
        # Explicit UTF-8 with the same except-set as every other build-plan
        # reader. `infer_mode` reads the plan TWICE — here and through
        # `plan_status.chunk_states` — so a locale codec here made
        # one function disagree with itself about whether the plan decodes.
        # `UnicodeDecodeError` is a `ValueError`, so a bare `except OSError`
        # let it escape past a caller that has no guard.
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ChunkModeRead(None, f"{plan_path.name} could not be read ({exc})")

    section = buildplan_refs._chunk_section_lines(content, chunk_id)
    # The same gate the deliverable and `Type:` readers apply. Reading the field
    # anyway is not safe: a section whose end was never detected runs on into the
    # next chunk, so the first `**Critic mode:**` in it can belong to a different
    # one — and this field OVERRIDES inference, so a `chunk` picked up from a
    # neighbour silently downgrades a plan-mandated `final`.
    #
    # But declining is not safe either, which is why the gap is REPORTED rather
    # than swallowed. A bare `None` here means "no override", and inference then
    # walks down to rule 4 and picks `chunk` — narrower than the `final` the
    # unreadable plan might have mandated, with a rationale that never says the
    # plan could not be read. That is CRT-3M8Q's silent demotion arriving through
    # the gate meant to prevent it. The caller escalates instead.
    # Only the UNTRUSTWORTHY half escalates. `chunk_section_gap` also refuses a
    # chunk that simply has no detail section in a plan that reads perfectly —
    # an ordinary shape (a Status roster whose later chunks are not written up
    # yet), where the plan states no mode and inference is exactly right to
    # proceed. Escalating that would turn every not-yet-detailed chunk into a
    # `final`. What must not proceed silently is a plan carrying a heading
    # nothing can parse, because then the field this function did not find may
    # exist under it, and the section that did resolve may not be its own.
    unparsed = buildplan_refs.unparsed_chunk_heading_reason(section)
    if unparsed:
        return ChunkModeRead(None, unparsed)
    if buildplan_refs.chunk_section_gap(chunk_id, section):
        return ChunkModeRead(None, None)
    # The whole section is scanned, and a valid token anywhere in it beats
    # anything unhonorable found above it. Returning on first sight is what an
    # unanchored read cannot afford: the marker appears in prose too — a
    # Description line discussing the field is indistinguishable from a line
    # declaring it — so first-sight would let a sentence *about* the field
    # suppress the declaration below it. That is a lost declaration reported as
    # a typo, which is the silent demotion this reader exists to prevent
    # wearing a note that misdirects the author away from it.
    unhonored: str | None = None
    unhonored_line: int | None = None
    for line_num, line in section.lines:
        for match in buildplan_refs.iter_field_declarations(
            line, _BUILD_PLAN_CRITIC_MODE_RE
        ):
            if match.group(1) in _VALID_ARG_MODES:
                return ChunkModeRead(match.group(1), None)
        if unhonored is not None:
            continue
        # Nothing bound, and this line puts the field in field position with a
        # value after it. Reported for the reason a typo'd mode is: the author
        # declared an intent, it is not being honored, and the only way they
        # learn that today is by noticing the review came out shallower than
        # they asked for. The VERBATIM value is what carries, truncated only
        # where it stops being a value — a paraphrase they cannot grep for is
        # a note that costs them the search it was supposed to save.
        declared = _BUILD_PLAN_CRITIC_MODE_FIELD_RE.search(line)
        if declared:
            unhonored = declared.group(1)[: buildplan_refs.FIELD_VALUE_QUOTE_LIMIT]
            unhonored_line = line_num
    return ChunkModeRead(None, None, unhonored, unhonored_line)
