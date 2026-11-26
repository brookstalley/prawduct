"""Coverage algebra — pure composition over evidence facts (kernel v3, ch.02).

The one question every v3 review gate asks, as a pure function
(``kernel-v3-evidence-design.md`` D4–D6): *does composed review coverage span
tree A → tree B, with zero unresolved blocking findings on the way?* The PR
gate instantiates it as Q1 (merge-base tree → HEAD tree); the Stop-hook
Critic gate as Q2 (session baseline tree → working tree). Mode labels,
`extends_cumulative` chains, demotion special cases, and mtime freshness all
dissolve into this composition — that is the point of the module.

**Purity.** No I/O and no git in here: facts come in as the envelopes
``lib.evidence.read_facts`` returned, and tree-to-tree diffs are supplied by
the caller as ``diff_fn(tree_a, tree_b) -> list[str] | None`` (``None`` =
could not compute — never guessed). Tests inject a table; the gate layer
(chunk 04) injects ``git diff --name-only <a> <b>``.

**The one judgeability predicate.** ``is_judgeable_path`` is the single
answer to "does this file need review coverage?" — the question v2.3.3
answered three divergent ways (``cmd_stop``, ``coverage._pr_diff_is_doc_only``,
``_record_covers_head``), whose disagreement over the metadata boundary was
the CRT-5D8Q deadlock. It composes the two existing canonical sources:
``gitstate.METADATA_PREFIXES`` (framework/session metadata is never
judgeable) and ``buildplan_refs.protected_path_violation`` (a ``.md`` under
any path in the protected set that function owns IS
behavioral logic here — PR-5K8D — so protection overrides the doc carveout).

**Edges (D6).**

- A ``review`` fact contributes edge ``base_tree → head_tree``, valid iff
  every judgeable file it recorded as changed is in its reviewed set — a
  scoped review that saw less than its diff yields NO edge (stricter, never
  looser). A malformed body yields no edge for the same reason, and so does a
  release batch review (:data:`RELEASE_SPAN`), which only
  :func:`batch_review_covers` credits.
- The caller's ``diff_fn`` contributes **free edges**: an interval whose
  entire diff is non-judgeable needs no review (the doc-only allowance,
  computed — never stored). "No judgeable path differs" is equality of a
  value each tree has alone, so a caller that supplies ``key_fn`` (a tree →
  judgeable-content digest) gets the same relation from *n* keys instead of
  *n²* diffs; the pairwise form remains as the reference implementation.

**Verdict.** ``covered`` — a path exists using only free edges and facts
with zero unresolved blockers, AND no tree on that path still carries one;
``blocked`` — otherwise, with the surviving findings listed (fixing or
verifying resolutions unblocks without re-review); ``uncovered`` — no path
composes. Resolutions are ``resolution`` facts joined by (review id, finding
id) with disposition ``fixed`` or ``waived`` (D5).

**Findings are a property of nodes, not of edges (CRT-5H2D).** Connectivity
asks "which intervals has review spanned"; the blocker question asks "is the
code at this tree fit to ship". Answering both from the edge set let a
blocking finding recorded on a zero-length interval (``base_tree ==
head_tree``) gate nothing at all — the self-loop is not an edge, so it was
invisible to the phase whose job is to return ``blocked``, and an equal-trees
span short-circuited before the edges were even built. So the verdict sweeps
every review fact standing at a tree on the found path, self-loops included.
Scope is still the path: an abandoned state's findings don't haunt unrelated
coverage, because its tree is not a node the path stands on.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Callable, Iterable, Iterator

from . import buildplan_refs
from .gitstate import METADATA_PREFIXES, is_object_id

DiffFn = Callable[[str, str], "list[str] | None"]
#: A tree's key, or ``None`` for a tree that cannot be read. May also carry an
#: optional ``prime(trees)`` attribute that answers many trees in one call
#: before they are keyed one by one (``gates._tree_key_fn`` sets it); the
#: algebra calls it when present and works without it.
KeyFn = Callable[[str], "str | None"]

_RESOLVING_DISPOSITIONS = frozenset({"fixed", "waived"})

#: The fact kinds the coverage verdict reads. :func:`coverage_verdict` drops
#: every other kind at its entry, which is what makes it safe for
#: ``evidence.OBSERVATIONAL_KINDS`` (the kinds left out of the verdict memo's
#: key) to exist at all; the two sets must never overlap.
VERDICT_INPUT_KINDS = frozenset({"review", "resolution"})

#: The ``span`` a release batch review records (``critic-begin --span
#: release``): anchor tree → the base's HEAD tree, rating only the files of the
#: merges no boundary review read. Such a fact is never an edge
#: (:func:`review_edges`); only :func:`batch_review_covers` credits it, and its
#: blockers settle only a span ending at its head tree (:func:`_counts_at`), as
#: do those of the verify passes that verify it (:func:`is_release_scoped`).
RELEASE_SPAN = "release"


def is_release_batch(fact: dict) -> bool:
    """A review fact recorded by a release batch review (its ``span`` is
    :data:`RELEASE_SPAN`)."""
    body = fact.get("body") if isinstance(fact, dict) else None
    return isinstance(body, dict) and body.get("span") == RELEASE_SPAN


def is_release_scoped(reviews: "list[dict]", fact: dict) -> bool:
    """Is ``fact`` a review taken on the integration base for the release: the
    release batch review (:func:`is_release_batch`), or a ``verify-resolutions``
    pass whose recorded :data:`VERIFIES_KEY` chain reaches one? The batch fix
    tail's pass and the pass that clears a merged branch's blocker on the base
    both anchor there, so their blockers say the same thing the batch's do: the
    base at that tree is not fit to release.

    Only a recorded claim is followed (:func:`walk_links`): a pass linked by
    tree alone, or one whose claim does not resolve, is not release-scoped, so
    its blocker counts everywhere, the stricter reading. ``reviews`` is the
    store's review facts in store order."""
    for current in walk_links(reviews, fact):
        if is_release_batch(current):
            return True
        if (current.get("body") or {}).get(VERIFIES_KEY) is None:
            return False
    return False


def is_judgeable_path(path: str) -> bool:
    """True if a change to ``path`` needs review coverage.

    THE predicate (CRT-5D8Q fix): framework/session metadata is never
    judgeable; a ``.md`` file is judgeable only when governance-protected
    (fork-skill prose is behavioral logic); everything else — code, config,
    data — is judgeable. Deliberately no size or content inspection: paths
    classify, contents don't (do-not-reintroduce: content-hash freshness).

    **Ruled 2026-07-29, after building the exception and reverting it: content
    equivalence cannot relax this, and "the change is only a comment" is not a
    safe exception in THIS repo.** The attempt keyed Python by normalized AST so
    a comment- or docstring-only edit would stay a free edge and cost no review
    pass. It is unsound here for a repo-specific reason no amount of narrowing
    fixes: ``waivers.py`` defines the ``prawduct:allow`` **source-comment**
    pragma and ``compliance.py`` acts on it, so adding
    ``# prawduct:allow prawduct/broad-except -- looks fine`` to an existing
    ``except Exception:`` suppresses a compliance check while leaving the AST
    byte-identical — exactly where ``skills/critic/review-protocol.md`` Goal 3
    obliges a reviewer to judge that waiver. A second channel compounds it:
    tests assert over ``.py`` prose, so docstring edits can break them. AST
    equality proves the *parser* sees the same program, not that the *system*
    behaves the same, and here source is read as text. The failure direction is
    the fatal one — a wrongly granted free edge ships unreviewed code. Prior
    art and the standing item: ``COV-3M8Q``. The sound way to stop paying for
    behaviour-neutral edits is to make review *cheap*, not skippable.
    """
    if any(path.startswith(p) for p in METADATA_PREFIXES):
        return False
    if path.endswith(".md"):
        return buildplan_refs.protected_path_violation(path) is not None
    return True


def judgeable_files(paths: "list[str] | None") -> list[str]:
    """The judgeable subset of ``paths`` (order preserved, None-safe)."""
    return [p for p in (paths or []) if is_judgeable_path(p)]


#: Records ABOUT the work, as opposed to the work itself: governance state,
#: specs, plans, the change log, learnings, reflections. A review READS these
#: to judge by; it does not rate them.
#:
#: ``.claude/rules/learnings/`` is here because the v2 cutover moved the corpus
#: OUT of ``.prawduct/``. Leaving it out reclassified every rule file from
#: oracle to review subject silently -- the Records Pass stops shielding them
#: and they land in ``files_reviewed`` -- which is a change in what a review
#: RATES, made by relocating a file rather than by deciding anything.
RECORD_PREFIXES = (".prawduct/", ".claude/rules/learnings/")


def is_review_subject(path: str) -> bool:
    """True if a finding may be *about* ``path``.

    **This is not the complement of :func:`is_judgeable_path`, and implementing
    it as one is the defect it exists to close.** The two answer different
    questions. ``is_judgeable_path`` asks *does an edit here re-open the
    coverage gate?* — a cost question, whose answer excludes every ``.md`` that
    is not governance-protected. This asks *may a finding be about this file?*
    — an eligibility question. They coincided until the subject/oracle split
    gave the cost predicate a second job, and its exclusions were never
    re-vetted against the second one.

    Where the negation got it wrong, in this repo: a review subagent's own
    system prompt under ``agents/`` and the norm/principle/waiver references
    under a ``docs/`` tree are behaviour-governing prose that no finding could
    be about. The general case is sharper and no path list reaches it — for a
    governed product whose **deliverable is markdown** (a docs site, a spec
    repo, a prompt library) every product file is non-judgeable, so the whole
    product output would be read-but-never-rated for all seven goals.

    **Fails closed toward subject.** A path this cannot place is reviewable:
    over-inclusion costs reviewer attention, while under-inclusion ships an
    unrated deliverable, and only one of those is recoverable. That is the same
    direction ``protected_path_violation`` already states for its own bounds.
    """
    return not any(path.startswith(p) for p in RECORD_PREFIXES)


def review_subjects(paths: "list[str] | None") -> list[str]:
    """The subject subset of ``paths`` (order preserved, None-safe)."""
    return [p for p in (paths or []) if is_review_subject(p)]


#: Live repo state that a NON-HERMETIC test in this repo reads (COV-4H7N).
#:
#: A named inventory, deliberately not a ``.prawduct/**`` rule. These paths are
#: not judgeable — editing one needs no Critic review — but a change to one CAN
#: flip a test red, because a test reads the committed file rather than a
#: fixture. Observed: PR #125 changed only ``.prawduct/*.md`` plus
#: ``project-state.yaml``; ``check-pr-doc-only`` took the fast path (no Critic,
#: no PR review, no suite) and ``test-status`` read *current*, while
#: ``tests/test_norm_probes.py::TestSilentAgainstThisRepo`` reads the live
#: ``project-state.yaml`` — so ratifying the norm registry broke develop
#: silently, and only an unrelated branch's suite run found it.
#:
#: Membership rule, so this stays an inventory rather than a drift-collector:
#: a path belongs here when a repo-coupled test asserts a CONTENT property of
#: it AND the file is low-churn framework configuration.
#:
#: - ``project-state.yaml`` — ``test_norm_probes.TestSilentAgainstThisRepo``
#:   requires every norm-lifecycle probe to stay silent against it.
#: - ``cross-cutting-concerns.md`` — ``test_v5_methodology.TestCrossCuttingConcerns``
#:   pins named sections and references in it.
#:
#: **The residual, stated rather than implied.** ``backlog.md``,
#: ``change-log.md``, ``.claude/rules/learnings/**`` and ``artifacts/**`` are
#: ALSO read by repo-coupled tests (``test_backlog_parser`` pins an item id;
#: ``test_change_log`` pins the tagged/untagged split, the scope-to-plan join
#: and same-line duplicates; ``test_path_reference_resolution`` grades every
#: path a rule cites). They are held out on cost, not on principle: all
#: four are written as ordinary bookkeeping in nearly every session, and a
#: change-log entry is written LATE by construction because the PR gate demands
#: one — so suite-coupling them would tax every PR with a re-run after the
#: bookkeeping. The sound close for those is to make their tests hermetic
#: (COV-4H7N option c proper), not to widen this set.
TEST_COUPLED_STATE = frozenset(
    {
        ".prawduct/project-state.yaml",
        ".prawduct/cross-cutting-concerns.md",
    }
)


def affects_test_outcome(
    path: str,
    extra_prefixes: "tuple[str, ...]" = (),
    static_prefixes: "tuple[str, ...]" = (),
) -> bool:
    """True if a change to ``path`` can change what the test suite says.

    A superset of :func:`is_judgeable_path` except for declared static content
    (``static_prefixes`` below), and the distinction is the
    point. "Does this need review coverage?" and "can this flip a test red?"
    are different questions that the metadata boundary answers differently:
    framework state needs no reviewer, and a non-hermetic test still reads it.
    Conflating them is what let a state-only PR skip the suite AND read its
    stale evidence as current (COV-4H7N).

    Kept as a second function rather than a second rule inside
    :func:`is_judgeable_path` because review coverage must NOT widen here: the
    ``_BATCH_FIX_DIRECTIVE`` tells a builder that ``.prawduct/`` writes cost no
    new review between review rounds, and that promise stays true.

    ``extra_prefixes`` carries the half that CANNOT ship: path prefixes a repo
    declares its own non-hermetic tests read. **Prefixes, not a prose rule** —
    they are not restricted to ``.md``, so declaring a root couples every file
    under it. That is the fail-safe direction (a superset can only cost a suite
    run) and it keeps the clause one comparison rather than two (``core.suite_coupled_prefixes``,
    from ``project-state.yaml``). Which directories hold prose a test scans is a
    fact about one repo's layout — this repo's guards sweep ``documentation/``
    and ``plugin/`` markdown, and a design doc merged straight to ``develop``
    failing two of them while this predicate reported day-old evidence as
    *current* over the red tree. Baking those names in would make the rule inert
    for every product that names its directories differently and would tax every
    product that happens to match, so the names live where the layout does.
    Default ``()`` — a product that declares nothing behaves exactly as before.

    **A parameter rather than a wider default rule.** "Every ``.md``" was the
    obvious alternative and it silently overturns two priced decisions: the
    residual named under :data:`TEST_COUPLED_STATE` (bookkeeping held out on
    cost, whose sound close is hermetic tests) and the ``README.md`` /
    ``docs/notes.md`` line those tests pin. Both remain out at every call site.

    **Callers pass prefixes only where the question is FRESHNESS.** The
    doc-only PR fast path asks a review question and must not inherit them:
    widening it there would make a documentation-only PR buy a full Critic
    review, which nothing priced. Passing them is therefore a deliberate act
    at each site, not a default the predicate applies on its own.

    ``static_prefixes`` is the repo's static-content declaration, the one
    narrowing input: a judgeable file it covers cannot change what the suite
    says (:func:`is_static_content`). The freshness callers pass it beside
    ``extra_prefixes``, and a coupled path is never static, so the widening
    declaration always wins an overlap.
    """
    if path in TEST_COUPLED_STATE:
        return True
    if extra_prefixes and path.startswith(tuple(extra_prefixes)):
        return True
    if is_static_content(path, static_prefixes, extra_prefixes):
        return False
    return is_judgeable_path(path)


def suite_coupled_files(
    paths: "list[str] | None",
    extra_prefixes: "tuple[str, ...]" = (),
    static_prefixes: "tuple[str, ...]" = (),
) -> list[str]:
    """The subset of ``paths`` a test outcome can depend on (order preserved,
    None-safe) — :func:`affects_test_outcome` over :func:`judgeable_files`.

    Both declarations are forwarded unchanged; see that function for why the
    freshness callers pass them and the review callers must not."""
    return [
        p for p in (paths or []) if affects_test_outcome(p, extra_prefixes, static_prefixes)
    ]


def is_static_content(
    path: str,
    static_prefixes: "tuple[str, ...]",
    coupled_prefixes: "tuple[str, ...]",
) -> bool:
    """True if ``path`` is static content by this repo's declaration: a judgeable
    file nothing in the product executes, serves as code or parses, such as a
    stylesheet, a static example page or a design-value file kept with its
    documents. Both declarations are the ones in force for the judged tree
    (``coverage.suite_declarations``), and the coupling one is required so no
    caller can classify a path without the declaration that overrides this.

    Static content still needs review coverage. :func:`is_judgeable_path` is
    not asked to change, so a static file is reviewed, never rides the doc-only
    fast path, and still owes a change record. What the declaration buys is
    narrower: such a file cannot change what the suite says
    (:func:`affects_test_outcome`), no test can execute it
    (:func:`is_executable_path`), and it does not count toward the boundary
    review's volume escalator (``critic_consolidate._derive_roster``). The
    review still runs because one over static pages has found real defects
    (a design value contradicting an owner ruling, accessibility faults in
    reference markup); it just runs lighter.

    **Paths classify, and the declaration is the whole claim.** There is no
    extension table: a second suffix table beside the one predicate is the
    divergence :func:`is_executable_path` records as removed.

    Never static, whatever the declaration says:

    - a path under ``coupled_prefixes``,
      because a test reads it as data. The declaration that widens the suite's
      reach wins an overlap;
    - governance-protected prose (``buildplan_refs.protected_path_violation``),
      because an agent executes it. Its bounds match a path SEGMENT, so a
      declared file under any ``skills/`` or ``templates/`` directory stays
      judged in full; the safe direction;
    - a path that is not judgeable anyway (metadata, unprotected ``.md``),
      which already costs nothing. :data:`TEST_COUPLED_STATE` is metadata, so it
      is never static, and :func:`affects_test_outcome` asks it first in any
      case.
    """
    if not static_prefixes or not path.startswith(tuple(static_prefixes)):
        return False
    if coupled_prefixes and path.startswith(tuple(coupled_prefixes)):
        return False
    if buildplan_refs.protected_path_violation(path) is not None:
        return False
    return is_judgeable_path(path)


def is_executable_path(
    path: str,
    static_prefixes: "tuple[str, ...]" = (),
    coupled_prefixes: "tuple[str, ...]" = (),
) -> bool:
    """True if a test could execute this path — the coverage floor's
    jurisdiction (COV-8R2K).

    The third question over the same boundary, and the narrowest of the three:
    :func:`is_judgeable_path` asks whether a change needs a reviewer,
    :func:`affects_test_outcome` whether it can change what the suite says, and
    this asks whether a test can *run* it — which is what the symbol-grep
    coverage floor is actually measuring when it demands a reference.

    Clauses on top of the judgeability answer, deliberately not a second
    suffix table: **no ``.md`` is executable**, protected or not. Governance
    protection makes fork-skill prose review-worthy, which is a different claim
    from testable — demanding an executing test for ``methodology/building.md``
    buys a token reference-test and nothing else. Re-landing an independent
    ``{.md,.yaml,.json,.toml,…}`` frozenset here is the exact divergence
    CRT-5D8Q was created to kill, so the exemption is expressed against the one
    predicate instead.

    **The residual.** A product-owned non-code config outside the metadata
    boundary (``config/app.yaml``, ``settings.toml``) is still executable by
    this reading and still gates. That is the conservative direction — a config
    file genuinely can be the subject of a test — and closing it properly needs
    the ``coverage_exempt_paths:`` knob COV-6T3P asks for, which is a question
    for the owner (binary vs path-scoped, and how it interacts with the
    doc-only fast path) rather than a default anyone should pick here. Declared
    static content (:func:`is_static_content`, given both declarations) is the
    path-scoped half for files nothing parses: it is not executable. A config
    the product reads is parsed, so it is not static by that declaration's own
    definition, and this residual stands for it.
    """
    if is_static_content(path, static_prefixes, coupled_prefixes):
        return False
    return is_judgeable_path(path) and not path.endswith(".md")


# ---------------------------------------------------------------------------
# Findings / resolutions join (D5)
# ---------------------------------------------------------------------------


def blocking_findings(review_fact: dict) -> list[dict]:
    """The BLOCKING findings a review fact carries (case-insensitive on
    severity; malformed findings entries are ignored — they cannot *satisfy*
    anything, and treating garbage as blocking would let a corrupt entry
    wedge a gate forever with nothing actionable to resolve)."""
    body = review_fact.get("body") or {}
    findings = body.get("findings")
    if not isinstance(findings, list):
        return []
    out = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        if isinstance(severity, str) and severity.strip().upper() == "BLOCKING":
            out.append(finding)
    return out


def resolution_index(facts: list[dict]) -> set[tuple[str, str]]:
    """(review id, finding id) pairs resolved by ``resolution`` facts with a
    recognized disposition. Unknown dispositions resolve nothing (fail toward
    stricter — escape hatches in classification create silent failures)."""
    resolved: set[tuple[str, str]] = set()
    for fact in facts:
        if fact.get("kind") != "resolution":
            continue
        body = fact.get("body") or {}
        target = body.get("finding") or {}
        review_id = target.get("review_id")
        fid = target.get("fid")
        disposition = body.get("disposition")
        if (
            isinstance(review_id, str)
            and isinstance(fid, str)
            and isinstance(disposition, str)
            and disposition in _RESOLVING_DISPOSITIONS
        ):
            resolved.add((review_id, fid))
    return resolved


def unresolved_blocking(review_fact: dict, resolved: set[tuple[str, str]]) -> list[dict]:
    """Blocking findings of ``review_fact`` not resolved by ``resolved``.
    A blocking finding without a usable ``fid`` can never be matched by a
    resolution fact, so it stays unresolved forever by construction — the
    writer (chunk 03) must always assign fids."""
    review_id = review_fact.get("id")
    out = []
    for finding in blocking_findings(review_fact):
        fid = finding.get("fid")
        if not isinstance(fid, str) or (review_id, fid) not in resolved:
            out.append(finding)
    return out


# ---------------------------------------------------------------------------
# The review link — which earlier review a review's interval starts from
# ---------------------------------------------------------------------------


def _store_position(reviews: list[dict], fact: dict) -> int:
    """``fact``'s index in ``reviews`` (store order) — by identity, else by
    fact id, else ``len(reviews)`` (a fact not yet in the store, as at
    dispatch, comes after every review it holds)."""
    for i, other in enumerate(reviews):
        if other is fact:
            return i
    fid = fact.get("id")
    if fid is not None:
        for i, other in enumerate(reviews):
            if other.get("id") == fid:
                return i
    return len(reviews)


#: The review-fact body key naming the review a ``verify-resolutions`` pass
#: anchored to — written by ``critic_consolidate`` from the dispatch's own
#: choice, read only through :func:`_resolve_claim`.
VERIFIES_KEY = "verifies"

#: The shape of a review id, ``rev-<UTC %Y%m%dT%H%M%SZ>-<8 hex>``: what
#: ``critic_consolidate.mint_review_id`` mints, and what :func:`_resolve_claim`
#: asks of an id no review carries. Defined here, in the pure layer both import;
#: the dispatch-age reader asks only the ``rev-<stamp>-`` prefix, so an id with
#: another suffix still has an age.
REVIEW_ID = re.compile(r"^rev-(\d{8}T\d{6}Z)-[0-9a-f]{8}\Z")


def _resolve_claim(
    reviews: list[dict], fact: dict
) -> "tuple[bool, dict | None, str | None]":
    """``(claimed, anchor, missing)`` for ``fact``'s recorded :data:`VERIFIES_KEY`.

    ``claimed`` is False when the body carries no such key (or null): a fact
    written before the field, or one that is not a verify pass — the tree link
    then decides. Otherwise ``anchor`` is the review in ``reviews`` with that
    id, standing at the pass's ``base_tree``, or ``None``; ``missing`` is the id
    when it has a review id's shape (:data:`REVIEW_ID`) and no review in
    ``reviews`` carries it, else ``None``. That is the one unresolved claim an
    ingest MIGHT repair, never one it will: the review may be another clone's
    not yet synced, or a fact this store dropped or could not read. A value of
    any other shape names no review anywhere, so it is unresolved and not
    missing. Shape is asked only when no review carries the id, since one the
    store holds is a review's id whatever its spelling.

    **A claim that does not resolve is no link, never a fallback to the tree.**
    The id is the dispatch's own choice, made because the tree alone cannot
    tell two reviews of one tree apart; when the named review is not in this
    store (not yet ingested from the clone that recorded it), the newest review
    at the tree is exactly the guess the field exists to stop making, so a
    reader would act on a review the pass did not verify. Every consumer reads
    "no link" in the safe direction: the Stop hook names the missing review and
    both repairs (sync it in, else run a ``final``), a chain ends at the pass
    (no chunk is inherited, no boundary review is credited), and a roll-call
    carries nothing it cannot name. The link resolves on its own once the
    review arrives.

    Unresolved too, though present: a value that is not a non-empty string, one
    naming the pass itself, and an anchor whose ``head_tree`` is not the pass's
    ``base_tree``. The dispatch takes the pass's base from its anchor's head,
    so a recorded pair that disagrees is a malformed record, and neither half
    says which review the interval started from.

    Looked up by id over the WHOLE store, not only what precedes the pass:
    ingest appends another clone's facts in note order, which can put a pass
    ahead of the review it verifies, and the id says which review it is
    wherever it sits. So store order does not end a walk over the link (a
    malformed store could name a cycle); :func:`walk_links` ends it."""
    body = fact.get("body") or {}
    claim = body.get(VERIFIES_KEY)
    if claim is None:
        return False, None, None
    if not isinstance(claim, str) or not claim or claim == fact.get("id"):
        return True, None, None
    for other in reviews:
        if other is not fact and other.get("id") == claim:
            if (other.get("body") or {}).get("head_tree") != body.get("base_tree"):
                return True, None, None
            return True, other, None
    return True, None, claim if REVIEW_ID.match(claim) else None


def missing_anchor(reviews: list[dict], fact: dict) -> "str | None":
    """The id ``fact`` recorded as the review it verifies, when it is shaped
    like a review id and no review in ``reviews`` carries it, else ``None``:
    the one unresolved claim a reader can name a possible repair for
    (:func:`_resolve_claim`).

    ``None`` too when ``fact`` has no usable ``base_tree``, whatever it names:
    :func:`linked_reviews` links such a pass to nothing even once its review
    arrives, so naming an ingest as the repair would promise a link that
    cannot form."""
    base = (fact.get("body") or {}).get("base_tree")
    if not isinstance(base, str) or not base:
        return None
    return _resolve_claim(reviews, fact)[2]


def linked_reviews(reviews: list[dict], fact: dict) -> list[dict]:
    """THE review-link rule: the reviews ``fact``'s interval starts from —
    every review recorded strictly BEFORE it (store order) whose ``head_tree``
    is its ``base_tree`` — oldest first, so ``[-1]`` is the one it links to
    (:func:`prior_review`).

    **A verify-resolutions pass that recorded its anchor links to that review
    alone.** Its body's :data:`VERIFIES_KEY` names the review the dispatch
    anchored to, and the tree cannot: two worktrees of one clone can review the
    same tree, in either order, and a fact's ``actor`` is trimmed when it
    travels, so no store-order or worktree filter can say which other reviews
    of that tree were this lineage's. The rest of the chain is reached by
    walking on from the anchor. A claim that does not resolve links to nothing
    (:func:`_resolve_claim` says why that, and not the tree, is the safe
    reading). A fact without the key — one written before it, or any other
    mode — links by tree as below.

    One rule for every reader that follows the link, because three copies of it
    had already drifted (identity by ``id()`` vs by fact id; every review at
    the tree vs the newest; the pass itself excluded or not). The walkers go
    through :func:`walk_links`, which owns stepping back along the link and
    ending the walk: ``gates._review_verified_passes_stand_on`` follows it back
    over verify passes to the review they stand for, ``critic_mode.review_chain``
    walks it back through every review at each linked tree, over only the
    reviews its ``bound`` leaves on this branch (#1224: a tree link knows no
    branch, so the walk is fed the branch's reviews rather than taught to stop), and
    ``plan_status._extended_reviews`` follows it to the review that records a
    commit. ``critic_consolidate.carried_blocking`` takes one hop of it, as a
    verify pass's anchor, through :func:`prior_review`.

    On the tree link, **strictly before** excludes the pass from its own
    anchor: a review cannot start from one recorded after it. It does not
    end a walk by itself, because a recorded anchor is found by id wherever
    it sits; :func:`walk_links` refuses to revisit a fact instead, so a loop
    that steps along this link by calling it repeatedly would have to repeat
    that guard. ``reviews`` is the store's review facts in store order (append order is
    recording order; ``ts`` has one-second resolution). ``fact`` need not be
    in it — a dispatch asks before its fact exists, and then every review
    counts as earlier. A ``base_tree`` that is not a non-empty string links to
    nothing, anchored or not: a missing tree must not match another fact's
    missing tree, and a pass whose interval cannot be placed is no link.
    """
    base = (fact.get("body") or {}).get("base_tree")
    if not isinstance(base, str) or not base:
        return []
    claimed, anchor, _missing = _resolve_claim(reviews, fact)
    if claimed:
        return [anchor] if anchor is not None else []
    here = _store_position(reviews, fact)
    return [
        f for f in reviews[:here]
        if f is not fact and (f.get("body") or {}).get("head_tree") == base
    ]


def prior_review(reviews: list[dict], fact: dict) -> "dict | None":
    """The review ``fact`` links to — the newest of :func:`linked_reviews` —
    or ``None`` when its interval starts at a tree no earlier review stands
    at, or it names an anchor this store does not hold.

    The one owner of "which review does this verify-resolutions pass verify":
    the review its recorded :data:`VERIFIES_KEY` names, else, for a fact from
    before that key, the newest earlier review at its ``base_tree``. A caller
    that holds the dispatch's choice before the pass is recorded asks with a
    probe carrying it (``critic_consolidate.carried_blocking``)."""
    linked = linked_reviews(reviews, fact)
    return linked[-1] if linked else None


def _walk_identity(fact: dict) -> object:
    """The key :func:`walk_links` asks "already visited?" of: the fact's id,
    else the object itself (by ``id()``) for a fact without a non-empty string
    id.

    The id, because it is the store's own identity: ``evidence.read_facts``
    keeps one fact per ``(kind, id)``, and the link rule finds a recorded
    anchor and a fact's own store position by id, so a copy of a stored fact
    (the envelope a consolidation just appended, an anchor read in another
    pass over the store) is the same review as the stored one and must end the
    walk as a revisit would. The object for an id-less fact, because ids that
    are absent must not collide: every hand-built probe without one is a
    different fact. Over what the store can hold the two readings agree,
    since every review fact there carries a unique non-empty id."""
    fid = fact.get("id")
    return fid if isinstance(fid, str) and fid else id(fact)


def walk_links(
    reviews: list[dict], fact: "dict | None", *, siblings: bool = False
) -> Iterator[dict]:
    """The facts on the line ``fact`` stands on, nearest first: ``fact``, the
    review it links to (:func:`prior_review`), the one that links to, and so
    on, each yielded once.

    The ONE owner of stepping back along the link and of ending the walk. A
    recorded anchor is found by id wherever it sits in the store
    (:func:`_resolve_claim`), so store order does not end a walk over a
    malformed store naming a cycle; this ends it, at a fact whose link is
    empty or whose linked review is already yielded, under one identity rule
    (:func:`_walk_identity`). A caller stops early by breaking out; the next
    link is computed only when the caller asks for the next fact.

    ``siblings`` also yields, after each spine fact, the OTHER reviews it links
    to (:func:`linked_reviews`' ``[:-1]``: the older reviews at the same tree)
    that are not yet yielded, then steps back through the newest. They are
    yielded but not walked themselves, and they count as visited: a walk ends
    where the review a fact links to is already on it, siblings included,
    because stepping on to it again would walk a line already walked.
    ``critic_mode.review_chain`` asks for them; the walkers that only follow
    the link to one review do not.

    ``reviews`` is the store's review facts in store order; ``fact`` need not
    be in it, and ``None`` yields nothing."""
    seen: "set[object]" = set()
    current = fact
    while current is not None and _walk_identity(current) not in seen:
        seen.add(_walk_identity(current))
        yield current
        linked = linked_reviews(reviews, current)
        if not linked or _walk_identity(linked[-1]) in seen:
            return
        if siblings:
            for other in linked[:-1]:
                if _walk_identity(other) not in seen:
                    seen.add(_walk_identity(other))
                    yield other
        current = linked[-1]


def reviews_linked_from(reviews: list[dict], root_tree: str) -> list[dict]:
    """Every review whose chain of links reaches back to ``root_tree``, in
    store order: one standing AT it, one starting from it, and — the link rule
    read forward — one starting from the ``head_tree`` of an earlier member.

    The tree relation :func:`linked_reviews` reads backward, from a root
    instead of from a review, so the two agree about which TREES link. A
    verify pass's recorded anchor is not consulted here: one that resolves
    stands at the pass's ``base_tree`` (:func:`_resolve_claim` refuses one that
    does not), so it names which review at a linked tree the pass verified,
    never another tree, and this answers membership
    (does a review's chain reach the root), not which review it verified.
    ``coverage.branch_review_ids`` bounds its empty-span fallback with it,
    over one worktree's reviews, where the anchor may have been recorded
    elsewhere."""
    if not isinstance(root_tree, str) or not root_tree:
        return []
    reached = {root_tree}
    out = []
    for fact in reviews:
        body = fact.get("body") or {}
        head = body.get("head_tree")
        base = body.get("base_tree")
        # A malformed or newer-schema body can carry a non-string tree; a set
        # lookup on an unhashable one would raise out of every gate reading this.
        if (isinstance(base, str) and base in reached) or head == root_tree:
            out.append(fact)
            if isinstance(head, str) and head:
                reached.add(head)
    return out


# ---------------------------------------------------------------------------
# Edges (D6)
# ---------------------------------------------------------------------------


def review_edges(facts: list[dict]) -> list[dict]:
    """Valid edges from ``review`` facts:
    ``{"src", "dst", "fact"}``. Validity — the fact recorded both trees as
    full-length git object ids, every judgeable changed file is within its
    reviewed set, and it is not a release batch review (:func:`is_release_batch`);
    anything less yields no edge (a partial or malformed fact must weaken
    coverage, never strengthen it).

    The tree ids are shape-checked here rather than trusted because facts are
    read back from a plain file on disk: a corrupted or hand-edited one can
    carry any string, and these values become git argv downstream. Rejecting
    the edge is the same direction as every other malformedness in this
    function — it costs coverage, so it can only ever demand more review.

    Rejection here is **silent by construction**: this module is pure (no I/O,
    see the module docstring), so it has no channel to attribute on. The
    attribution belongs to the layer that owns the store, and
    ``evidence.tree_diff``/``tree_entries`` emit it when the same malformed id
    reaches the git boundary — see ``evidence._attribute_bad_tree``."""
    edges = []
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        src = body.get("base_tree")
        dst = body.get("head_tree")
        files_changed = body.get("files_changed")
        files_reviewed = body.get("files_reviewed")
        if not (
            is_object_id(src)
            and is_object_id(dst)
            and isinstance(files_changed, list)
            and isinstance(files_reviewed, list)
        ):
            continue
        reviewed = {f for f in files_reviewed if isinstance(f, str)}
        changed = [f for f in files_changed if isinstance(f, str)]
        if any(f not in reviewed for f in judgeable_files(changed)):
            continue  # under-reviewed interval — not an edge
        if is_release_batch(fact):
            # A release batch review is never an edge, even when its subject
            # happens to be every judgeable file: its subject was chosen by the
            # release classification, not by the interval, and what credits it
            # is `batch_review_covers`, which is relax-only. Its findings still
            # stand at its trees (`_unresolved_at_nodes`), for a span ending at its
            # head tree (`_counts_at`), so it can block, never cover.
            continue
        if src == dst:
            # Degenerate interval: contributes nothing to *connectivity* that
            # the node does not already give. It still carries findings, and
            # those are swept by `_unresolved_at_nodes` at verdict time —
            # CRT-5H2D, where dropping the edge dropped the payload with it.
            continue
        edges.append({"src": src, "dst": dst, "fact": fact})
    return edges


def _free_edge_files(diff_fn: DiffFn, src: str, dst: str) -> "list[str] | None":
    """The interval's diff when it qualifies as a free edge (entirely
    non-judgeable), else ``None``. A ``diff_fn`` failure (``None``) is never
    a free edge — unknown diffs don't get free passes."""
    files = diff_fn(src, dst)
    if files is None:
        return None
    if judgeable_files(files):
        return None
    return files


def _free_classes(nodes: "set[str]", key_fn: KeyFn) -> dict[str, list[str]]:
    """Free-edge adjacency derived from per-tree keys instead of pairwise
    probing — the linear form of the same relation.

    A free edge ``a → b`` exists iff the interval's diff holds no judgeable
    path, i.e. iff ``a`` and ``b`` agree on every judgeable ``(path, blob)``.
    That is equality of a value each tree has on its own, so a caller that
    can key a tree by its judgeable content turns *n²* diffs into *n* keys:
    equal keys ⇒ mutually free-connected, and each key class is a clique.

    A tree whose key cannot be computed (``None`` — unreadable object, git
    failure) joins no class and so gets no free edge, matching
    :func:`_free_edge_files`'s refusal to grant one on a failed diff. Speed
    must never buy a free pass; the fast path fails in the same direction as
    the slow one.
    """
    # A key function may answer many trees in one call first (the production
    # one resolves trees git no longer holds); optional, so any callable works.
    prime = getattr(key_fn, "prime", None)
    if prime is not None:
        prime(sorted(nodes))
    classes: dict[str, list[str]] = {}
    for node in nodes:
        key = key_fn(node)
        if key is None:
            continue
        classes.setdefault(key, []).append(node)
    adjacency: dict[str, list[str]] = {}
    for members in classes.values():
        if len(members) < 2:
            continue
        for member in members:
            adjacency[member] = [o for o in members if o != member]
    return adjacency


class _EvidenceGraph:
    """The one graph composed coverage is searched over: review edges plus free
    edges among the trees the evidence mentions and the span's two endpoints.

    Every search builds it here — :func:`_find_path` for the single path
    :func:`coverage_verdict` settles, :func:`_reach` for the closures
    :func:`excused_gap_verdict` composes across one gap. The excused-gap verdict
    is relax-only because it uses no edge the coverage verdict would not; that
    holds by construction only while both read the same graph, so neither
    builds its own. Free edges between trees outside the node set are left out
    because nothing connects such trees to anything.

    Free edges come from ``key_fn`` when one is supplied (:func:`_free_classes`
    — *n* keys, the form every gate uses) and from pairwise ``diff_fn`` probing
    otherwise (*n²* diffs, the reference implementation the injected-table
    tests exercise). Both decide "no judgeable path differs", one per tree and
    one per pair.
    """

    def __init__(
        self,
        edges: list[dict],
        start: str,
        end: str,
        diff_fn: DiffFn,
        key_fn: "KeyFn | None",
    ) -> None:
        self.nodes = {start, end}
        self._out: dict[str, list[dict]] = {}
        self._in: dict[str, list[dict]] = {}
        for edge in edges:
            self.nodes.add(edge["src"])
            self.nodes.add(edge["dst"])
            step = {
                "kind": "review",
                "id": edge["fact"].get("id"),
                "src": edge["src"],
                "dst": edge["dst"],
            }
            self._out.setdefault(edge["src"], []).append(step)
            self._in.setdefault(edge["dst"], []).append(step)
        self._diff_fn = diff_fn
        self._free = _free_classes(self.nodes, key_fn) if key_fn is not None else None

    def steps_from(
        self, node: str, *, reverse: bool, skip: Callable[[str], bool]
    ) -> "Iterator[tuple[str, dict]]":
        """Each tree one evidence step from ``node`` — after it when ``reverse``
        is False, before it when True — with that step in forward orientation
        (``src`` precedes ``dst``). Review steps first, then free steps.

        ``skip`` is asked lazily, per candidate, and only spares the pairwise
        probe a diff for a tree the caller has already reached; a caller still
        re-checks every yielded tree, so ``skip`` cannot change what is reached.
        """
        for step in (self._in if reverse else self._out).get(node, ()):
            yield (step["src"] if reverse else step["dst"]), step
        if self._free is not None:
            for other in self._free.get(node, ()):
                src, dst = (other, node) if reverse else (node, other)
                yield other, {"kind": "free", "src": src, "dst": dst}
            return
        for other in self.nodes:
            if other == node or skip(other):
                continue
            src, dst = (other, node) if reverse else (node, other)
            files = _free_edge_files(self._diff_fn, src, dst)
            if files is not None:
                yield other, {"kind": "free", "src": src, "dst": dst, "files": files}


def _attribute_free_steps(path: list[dict], diff_fn: DiffFn) -> list[dict]:
    """Fill in the ``files`` a ``free`` step reports, for the steps on a
    *found* path only.

    Key-derived free edges know an interval is free without having listed
    its files, and the verdict's path carries that list for attribution. The
    diff is therefore deferred to here — O(path length) calls rather than one
    per candidate examined, which is the whole point of the key form. An
    unavailable diff degrades to ``[]``: the key already established the
    interval is free, so attribution detail may be missing but the verdict
    may not change.
    """
    for step in path:
        if step.get("kind") == "free" and "files" not in step:
            step["files"] = diff_fn(step["src"], step["dst"]) or []
    return path


# ---------------------------------------------------------------------------
# The verdict (Q1/Q2)
# ---------------------------------------------------------------------------


def _path_nodes(base_tree: str, path: list[dict]) -> set[str]:
    """Every tree the composed ``path`` stands at — the base plus each step's
    endpoints. ``path == []`` (the degenerate span) still yields ``{base}``,
    which is what makes the equal-trees short-circuit answerable."""
    nodes = {base_tree}
    for step in path:
        for end in (step.get("src"), step.get("dst")):
            if isinstance(end, str) and end:
                nodes.add(end)
    return nodes


def _facts_at_nodes(facts: list[dict], nodes: "set[str]") -> list[dict]:
    """Review facts recorded *at* one of ``nodes`` — head_tree lands there.

    Edge validity is deliberately NOT required. A fact whose reviewed set was
    narrower than its diff yields no edge (it cannot vouch for an interval),
    but the blocking findings it *did* record are real and must still weigh;
    validity gates what evidence proves, never what it accuses. Self-loops
    (``base_tree == head_tree``) land here too, which is the whole point:
    ``review_edges`` drops them for connectivity, so this is where their
    payload re-enters (CRT-5H2D).
    """
    out = []
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        head = body.get("head_tree")
        if isinstance(head, str) and head in nodes:
            out.append(fact)
    return out


def _verify_anchor_id(facts: list[dict], nodes: "set[str]") -> "str | None":
    """The review fact at one of ``nodes`` that a verify-resolutions pass would
    anchor to: the most recently appended one. ``None`` when no review fact
    stands at any node on the path.

    This is what makes a blocking finding *reachable*. A verify pass reviews
    the delta from one prior fact and records resolutions against that fact
    alone, so a blocker carried by any OTHER fact on the path is superseded:
    no verify pass will anchor to it again. Superseded is not stranded: since
    #334 a verify pass's roll-call NAMES every blocker this module's verdict
    counts when composing to the tree it anchors on
    (``critic_consolidate.carried_blocking`` over :func:`blockers_counted`),
    so a superseded blocker that composition still counts clears through
    verify-resolutions; only one it does not count needs a review spanning the
    whole interval (``gates.blocking_remedy_lines``).

    Two deliberate choices, because both directions of error are wrong advice:

    - **Appended order, not the derived findings cache.** The dispatcher finds
      its anchor through that cache's pointer, but no gate may read it (D7),
      and it is per-worktree while facts are the shared truth. The store is
      append-only and :func:`evidence.read_facts` preserves that order, so the
      last review fact IS the newest one.
    - **Restricted to the path's nodes, not the whole store.** The store is
      shared by every worktree of the clone, so a sibling's newer review would
      otherwise make a perfectly reachable finding look stranded. A fact
      standing at a tree on this path is on this interval's lineage by
      construction — and every review *step* on the path is such a fact, since
      a step's ``dst`` IS its fact's ``head_tree``, so this is a superset of
      the path-step reading rather than a different one.

    **The residual, stated rather than implied.** This PREDICTS the anchor a
    future verify pass will choose, by the newest review at the path's trees;
    it is a *proxy* for the dispatcher's choice, not the same value. A pass
    already recorded names its anchor (:data:`VERIFIES_KEY`, read through
    :func:`prior_review`), but the pass this advice is about has not been
    dispatched, and the dispatcher picks its anchor from this worktree's
    findings cache pointer or this branch's newest review. So the two can
    differ: when a sibling worktree reviews the same tree later, its review is
    the newest here, this branch's own blocker at that tree reads superseded,
    and the remedy prescribes a review spanning the interval where a verify
    pass would clear it; and should the cache point at a fact that is not on
    the composed path, an on-path blocker reads reachable and the message
    prescribes a verify pass that will demote rather than clear it. Nothing
    here can detect either: reading the cache to check is the very thing D7
    forbids a gate to do. It stays a proxy because the failure is soft (the
    verdict never moves, only the advice).
    """
    newest = None
    for fact in _facts_at_nodes(facts, nodes):
        newest = fact.get("id")
    return newest


def _counts_at(fact: dict, target: "str | None", reviews: "Callable[[], list[dict]]") -> bool:
    """Does ``fact``'s blocker settle a span ending at ``target``?

    Every fact's does, except a release-scoped review's (:func:`is_release_scoped`:
    the release batch review, or a verify pass verifying it) when the span ends
    anywhere but the tree it reviewed. Such a review is taken on the integration
    base, and its blocker says the base there is not fit to RELEASE: it is owed
    by the release check (:func:`batch_review_blockers` and :func:`entry_blockers`,
    which count it always) and by the base at that tree, where the verify pass
    that clears it composes to (its roll-call composes merge-base tree → the
    tree it anchors on, which is this one). A feature branch forked at that tree
    stands on it as its merge-base and ends at its own tip, so it is not held
    for code it never touched.

    ``target`` ``None`` counts every fact: the release check's settlement.
    ``reviews`` gives the store's review facts, asked only for a fact that
    could be release-scoped, since following a claim reads the store."""
    if target is None:
        return True
    body = fact.get("body") or {}
    if body.get("head_tree") == target:
        return True
    if not is_release_batch(fact) and body.get(VERIFIES_KEY) is None:
        return True
    return not is_release_scoped(reviews(), fact)


def _unresolved_at_nodes(
    facts: list[dict], resolved: set[tuple[str, str]], nodes: "set[str]",
    target: "str | None" = None, *, at_nodes: "list[dict] | None" = None,
) -> list[dict]:
    """Every unresolved blocking finding recorded at a tree on the path, of the
    facts whose blockers settle a span ending at ``target`` (:func:`_counts_at`).
    ``at_nodes`` is :func:`_facts_at_nodes`' answer when the caller already
    holds it (a :class:`Settlement`'s index), in store order.

    This is the composition-side answer to CRT-5H2D. Connectivity and findings
    were previously answered by one edge set, and that conflation is what let a
    blocker on a zero-length interval gate nothing: ``review_edges`` drops the
    self-loop before either search phase runs, and ``coverage_verdict``
    short-circuits an equal-trees span before the edges are built at all. Both
    doors close by asking the findings question of the *nodes* the verdict
    stands on rather than of the edges it traversed.

    The widening is deliberate and load-bearing beyond self-loops: a blocker
    recorded at a tree the path passes through counts even when the path
    routed around its edge (over a free edge, or over a second review of the
    same interval). A blocking finding says "the code at this tree is not fit
    to ship"; a *different* fact reaching the same tree does not make that
    untrue. Clearing it takes a resolution fact — ``fixed`` or ``waived`` — or
    a spanning review that never stands at the tree in question. This is
    strictly stricter than the pre-CRT-5H2D reading, which is the only safe
    direction for a gate that had been reporting ``satisfied`` while the store
    held an unresolved blocker.
    """
    at = _facts_at_nodes(facts, nodes) if at_nodes is None else at_nodes
    if target is not None:
        memo: "list[list[dict]]" = []

        def reviews() -> "list[dict]":
            if not memo:
                memo.append([f for f in facts if f.get("kind") == "review"])
            return memo[0]

        at = [f for f in at if _counts_at(f, target, reviews)]
    anchor = _verify_anchor_id(at, nodes)
    entries = []
    for fact in at:
        for finding in unresolved_blocking(fact, resolved):
            entry = {
                "review_id": fact.get("id"),
                "superseded": fact.get("id") != anchor,
            }
            entry.update(
                {
                    k: finding.get(k)
                    for k in ("fid", "severity", "title", "files")
                    if k in finding
                }
            )
            entries.append(entry)
    return entries


def coverage_verdict(
    facts: list[dict],
    base_tree: str,
    target_tree: str,
    diff_fn: DiffFn,
    key_fn: "KeyFn | None" = None,
) -> dict:
    """Does composed coverage span ``base_tree → target_tree`` with zero
    unresolved blocking findings?

    Returns::

        {"status": "covered",   "path": [step, ...]}
      | {"status": "blocked",   "path": [step, ...], "unresolved": [
            {"review_id", "fid", "title", "superseded", ...}, ...]}
      | {"status": "uncovered", "reason": str}

    Path steps are ``{"kind": "review", "id", "src", "dst"}`` or
    ``{"kind": "free", "src", "dst", "files"}`` — enough for a gate message
    to attribute exactly which evidence vouched for what.

    Search is two-phase: first over blocker-free facts + free edges; then over
    all valid edges; neither = ``uncovered``. A path found by either phase is
    then settled by :func:`_unresolved_at_nodes` — ``covered`` only if no tree
    it stands on still carries an unresolved blocker, ``blocked`` otherwise
    (fix/verify them and the same evidence passes, no re-review). The equal-
    trees span skips the search but not the settlement: it has one node, and a
    node can carry findings (CRT-5H2D).

    Each unresolved entry carries ``superseded``: True when its fact is not the
    one a verify-resolutions pass would anchor to (:func:`_verify_anchor_id`).
    That alone no longer means only a spanning review can clear it: a verify
    pass's roll-call names every blocker this verdict counts at its anchor's
    tree (:func:`blockers_counted`, #334), so a superseded entry is stranded
    only when that composition does not count it
    (``gates.blocking_remedy_lines`` asks). The verdict itself is unaffected —
    a blocker blocks either way.

    A release-scoped review's blocker (the release batch review's, or a verify
    pass's verifying it: :func:`is_release_scoped`) settles only a span ending
    at the tree it reviewed (:func:`_counts_at`): it gates the release check and
    the base, never a branch built on top of that tree.

    A blocker the verdict does NOT list is not open, whatever its resolution
    facts say: one recorded at a tree no composed path stands on (a clean
    spanning review routed around it) gates nothing. :func:`blockers_counted`
    is the one reading of that answer for every surface that reports open
    blockers, so none of them can count one the gate has stopped counting.
    """
    if not isinstance(base_tree, str) or not base_tree:
        return {"status": "uncovered", "reason": "no base tree to compose from"}
    if not isinstance(target_tree, str) or not target_tree:
        return {"status": "uncovered", "reason": "no target tree to compose to"}
    # Only the kinds this module reads get past here. Every helper below also
    # filters by kind, but a filter written some other way later would not be
    # visible to `evidence.OBSERVATIONAL_KINDS` — the kinds the verdict memo's
    # key leaves out — so the guarantee that those kinds cannot move a verdict
    # is made once, at the door, rather than by each helper remembering to.
    facts = [f for f in facts if f.get("kind") in VERDICT_INPUT_KINDS]
    resolved = resolution_index(facts)

    def _settle(path: list[dict]) -> dict:
        """``covered`` unless a tree on ``path`` still carries a blocker."""
        unresolved = _unresolved_at_nodes(
            facts, resolved, _path_nodes(base_tree, path), target_tree
        )
        if unresolved:
            return {"status": "blocked", "path": path, "unresolved": unresolved}
        return {"status": "covered", "path": path}

    if base_tree == target_tree:
        # A zero-length span still has a node, and a node can carry findings.
        return _settle([])

    edges = review_edges(facts)
    clean_edges = [
        e for e in edges if not unresolved_blocking(e["fact"], resolved)
    ]

    path = _find_path(clean_edges, base_tree, target_tree, diff_fn, key_fn)
    if path is not None:
        return _settle(path)

    path = _find_path(edges, base_tree, target_tree, diff_fn, key_fn)
    if path is not None:
        settled = _settle(path)
        if settled["status"] == "covered":
            # Unreachable by construction — this phase only finds a path the
            # clean-edge phase could not, so it used an edge whose fact carries
            # an unresolved blocker, and that fact stands at a node on the
            # path. Kept explicit rather than asserted: a search that somehow
            # disagreed must not be reported as coverage the first phase
            # already refused.
            return {"status": "blocked", "path": path, "unresolved": []}
        return settled

    return {
        "status": "uncovered",
        "reason": (
            f"no evidence path composes from {base_tree[:12]} to "
            f"{target_tree[:12]} — a review at the current tree closes the gap"
        ),
    }


def blockers_counted(verdict: dict) -> "list[dict] | None":
    """The unresolved blocking findings a :func:`coverage_verdict` result
    COUNTS — the gate's own answer to "is this blocker still open", read off
    the verdict rather than re-derived.

    A blocker is open when a resolution fact has not lifted it AND it stands at
    a tree the composed path stands on (:func:`_unresolved_at_nodes`). The first
    half alone is the tempting second predicate, and it is wrong after a clean
    spanning review: the path routes around the round that raised the blocker,
    the gate passes, and a surface asking only "is there a resolution fact"
    keeps reporting it open — a manufactured round, a false NOT DONE.

    ``[]`` for ``covered``; the listed entries for ``blocked`` (shape:
    ``review_id``, ``fid``, ``title``, ``superseded``, …); ``None`` for
    ``uncovered`` or anything else — no path composes, so the verdict counts no
    blocker and cannot say which one a path would. ``None`` is "unknown", never
    "none open": each caller picks its own degraded posture."""
    status = verdict.get("status") if isinstance(verdict, dict) else None
    if status == "covered":
        return []
    if status == "blocked":
        return [dict(e) for e in verdict.get("unresolved") or []]
    return None


#: The most (forward-reached, backward-reached) tree pairs :func:`excused_gap_verdict`
#: diffs per search phase. A cost bound, not a condition: pairs past it are not
#: asked, which can only leave a span uncovered that a wider search would have
#: excused — never excuse one.
EXCUSED_GAP_MAX_PAIRS = 32


def _reach(
    edges: list[dict],
    start: str,
    other_end: str,
    diff_fn: DiffFn,
    key_fn: "KeyFn | None",
    *,
    reverse: bool,
) -> dict[str, list[dict]]:
    """Every tree composed evidence connects to ``start``, with the steps that
    connect it, in forward order: ``start → node`` when ``reverse`` is False,
    ``node → start`` when it is True. The graph :func:`_find_path` searches —
    one :class:`_EvidenceGraph`, so the two cannot disagree on an edge — asked
    as a closure instead of a single path. A key-form free step carries no
    ``files`` here; the caller attributes the one path it returns."""
    graph = _EvidenceGraph(edges, start, other_end, diff_fn, key_fn)
    reached: dict[str, list[dict]] = {start: []}
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        for to, step in graph.steps_from(node, reverse=reverse, skip=reached.__contains__):
            if to in reached:
                continue
            reached[to] = [step] + reached[node] if reverse else reached[node] + [step]
            queue.append(to)
    return reached


def excused_gap_verdict(
    facts: list[dict],
    base_tree: str,
    target_tree: str,
    diff_fn: DiffFn,
    key_fn: "KeyFn | None",
    excused: Callable[[list[str]], bool],
    *,
    max_pairs: int = EXCUSED_GAP_MAX_PAIRS,
) -> dict:
    """Does composed coverage span ``base_tree → target_tree`` EXCEPT for one
    interval whose judgeable files the caller excuses?

    The question :func:`coverage_verdict` cannot ask: it composes by tree, so a
    span reads ``uncovered`` whenever any interval on it lacks review, whoever
    wrote that interval. A caller that knows some files are not the subject of
    its gate (the Stop gate: files a sync brought in that this session did not
    author) needs the composition with one hole allowed — evidence from the base
    forward to a tree ``f``, evidence from a tree ``r`` forward to the target,
    and the interval ``f → r`` whose judgeable diff ``excused`` accepts.

    **Only relaxes, never covers more than the evidence does.** Every review
    edge and free edge used is one :func:`coverage_verdict` would use; the gap
    is the only interval no evidence spans, and ``excused`` sees its full
    judgeable diff — a file changed both inside and outside the excused set is
    in that diff and is the caller's to refuse. A diff that cannot be computed
    is never excused. Blockers settle exactly as in :func:`coverage_verdict`:
    every review fact standing at a tree on the composed path, the gap's two
    endpoints included, still blocks.

    Search mirrors :func:`coverage_verdict`'s two phases — blocker-free edges
    first, then all valid edges — so a gap reachable only through a blocked
    review settles as ``blocked`` (the blocker is still owed) rather than as
    ``uncovered``. Pairs are tried longest-evidence first and capped at
    ``max_pairs`` per phase (:data:`EXCUSED_GAP_MAX_PAIRS`).

    Returns::

        {"status": "covered", "path": [..., {"kind": "gap", "src", "dst",
         "files"}, ...], "gap": {"src", "dst", "files"}}
      | {"status": "blocked", "path", "unresolved", "gap"}
      | {"status": "uncovered", "gap": {"src", "dst", "files"} | None,
         "capped": True}   # ``capped`` present only when the cap cut a phase

    The ``path`` steps other than the gap have :func:`coverage_verdict`'s shape,
    a free step's ``files`` included in both free-edge forms: a returned path is
    a found path, attributed by :func:`_attribute_free_steps` as that one is.

    For ``uncovered``, ``gap`` is the smallest unexcused interval found (the one
    whose files a message should name), or ``None`` when no pair could be
    diffed; ``capped`` says pairs went unasked, so a caller can tell "nothing
    excusable" from "the search stopped". Cost: two closures over the evidence graph plus at most
    ``max_pairs`` diffs per phase, the second phase's mostly answered by the
    caller's diff memo.
    """
    if not (isinstance(base_tree, str) and base_tree and isinstance(target_tree, str) and target_tree):
        return {"status": "uncovered", "gap": None}
    facts = [f for f in facts if f.get("kind") in VERDICT_INPUT_KINDS]
    resolved = resolution_index(facts)
    edges = review_edges(facts)
    clean_edges = [e for e in edges if not unresolved_blocking(e["fact"], resolved)]

    smallest: "dict | None" = None
    blocked: "dict | None" = None
    capped = False
    for phase_edges in (clean_edges, edges):
        forward = _reach(phase_edges, base_tree, target_tree, diff_fn, key_fn, reverse=False)
        backward = _reach(phase_edges, target_tree, base_tree, diff_fn, key_fn, reverse=True)
        candidates = sorted(
            ((f, r) for f in forward for r in backward if f != r),
            key=lambda p: (-(len(forward[p[0]]) + len(backward[p[1]])), p),
        )
        capped = capped or len(candidates) > max_pairs
        pairs = candidates[:max_pairs]
        for f, r in pairs:
            files = diff_fn(f, r)
            if files is None:
                continue
            judgeable = judgeable_files(files)
            gap = {"src": f, "dst": r, "files": judgeable}
            if not excused(judgeable):
                if smallest is None or len(judgeable) < len(smallest["files"]):
                    smallest = gap
                continue
            path = forward[f] + [{"kind": "gap", **gap}] + backward[r]
            unresolved = _unresolved_at_nodes(facts, resolved, _path_nodes(base_tree, path), target_tree)
            if not unresolved:
                return {
                    "status": "covered", "path": _attribute_free_steps(path, diff_fn),
                    "gap": gap,
                }
            if blocked is None:
                blocked = {
                    "status": "blocked", "path": _attribute_free_steps(path, diff_fn),
                    "unresolved": unresolved, "gap": gap,
                }
    if blocked is not None:
        return blocked
    uncovered: dict = {"status": "uncovered", "gap": smallest}
    if capped:
        uncovered["capped"] = True
    return uncovered


class Settlement:
    """One store read's verdict-input facts (:data:`VERDICT_INPUT_KINDS`), their
    resolution index and their review facts by head tree, built once and handed
    to :func:`batch_review_blockers`, :func:`entry_blockers` and
    :func:`batch_review_covers` in place of the fact list. The release check
    asks those once per entry and per candidate review, and rebuilding the
    whole-store indices on every ask made its cost grow with the store, not the
    release (``boundary_coverage._Classifier`` builds one)."""

    def __init__(self, facts: "list[dict]"):
        self.facts = [f for f in facts if f.get("kind") in VERDICT_INPUT_KINDS]
        self.resolved = resolution_index(self.facts)
        self.ids = frozenset(f.get("id") for f in self.facts if f.get("id") is not None)
        self._by_head: "dict[str, list[tuple[int, dict]]]" = {}
        for i, fact in enumerate(self.facts):
            head = (fact.get("body") or {}).get("head_tree") if fact.get("kind") == "review" else None
            if isinstance(head, str):
                self._by_head.setdefault(head, []).append((i, fact))

    def at_nodes(self, nodes: "Iterable[str]") -> "list[dict]":
        """:func:`_facts_at_nodes` from the index: the review facts standing at
        ``nodes``, in store order."""
        found = [pair for node in set(nodes) for pair in self._by_head.get(node, ())]
        return [fact for _i, fact in sorted(found, key=lambda pair: pair[0])]


def _settled(facts: "list[dict] | Settlement") -> Settlement:
    return facts if isinstance(facts, Settlement) else Settlement(facts)


def batch_review_blockers(facts: "list[dict] | Settlement", review: dict,
                          entry_trees: "Iterable[str]" = ()) -> list[dict]:
    """The unresolved blocking findings standing at ``review``'s two trees, and
    at ``entry_trees`` (the trees of the commit a batch would credit and of
    every commit it brought onto the base), over every review and resolution
    fact (``review`` itself included, whether or not ``facts`` holds it). The
    settlement half of :func:`batch_review_covers`, shared with the release
    check's batch fix tail, which asks it of a review whose findings the tail
    fixed: a ``verify-resolutions`` pass's resolution facts are what clear them.

    Every fact standing at those trees counts, a release batch review's
    included: this is the release check's settlement, where a release batch
    review's blockers always gate (contrast :func:`_counts_at`). ``facts`` may
    be a :class:`Settlement` built once for many asks."""
    body = review.get("body") if isinstance(review, dict) else None
    if not isinstance(body, dict):
        return []
    settled = _settled(facts)
    nodes = {t for t in (body.get("base_tree"), body.get("head_tree"), *entry_trees)
             if isinstance(t, str) and t}
    at = settled.at_nodes(nodes)
    held = review.get("id") is not None and review.get("id") in settled.ids
    if not held and not any(f is review for f in at):
        # Not in the store yet: it stands at its own head tree, newest of all.
        at = at + [review] if body.get("head_tree") in nodes else at
    return _unresolved_at_nodes(settled.facts, settled.resolved, nodes, at_nodes=at)


def entry_blockers(facts: "list[dict] | Settlement", entry_trees: "Iterable[str]") -> list[dict]:
    """The unresolved blocking findings standing at ``entry_trees`` alone (the
    trees of a release entry and of every commit it brought onto the base), over
    every review and resolution fact, a release batch review's included.

    The blockers a release entry owes a resolution whatever review would credit
    it: :func:`batch_review_covers` refuses over them, and they are not the
    batch review's own, so a ``verify-resolutions`` pass anchored to that review
    names them only when it is told them (``critic_consolidate.release_owed_
    blockers``, its roll-call's second input on the integration base).
    ``facts`` may be a :class:`Settlement`."""
    nodes = {t for t in entry_trees if isinstance(t, str) and t}
    if not nodes:
        return []
    settled = _settled(facts)
    return _unresolved_at_nodes(settled.facts, settled.resolved, nodes,
                                at_nodes=settled.at_nodes(nodes))


def batch_review_covers(
    facts: "list[dict] | Settlement",
    review: dict,
    entry_files: "list[str] | None",
    *,
    brackets: bool,
    entry_trees: "Iterable[str] | None",
) -> dict:
    """Does one boundary-stage review ``review`` cover one release entry, a
    commit on the integration base whose changed files are ``entry_files``?

    The question :func:`coverage_verdict` cannot ask (design §3 of
    ``documentation/issues/1222-1223-design.md``): a release batch review rates
    only the files of the merges no boundary review read, so it is not an edge
    (:func:`review_edges`), and composition cannot credit it. This rule credits
    it for one entry at a time, when all three hold:

    1. ``brackets``: the review's base tree is at or before the entry's first
       parent on the base's first-parent line, and its head tree at or after the
       entry. A git question, so the caller answers it.
    2. Every judgeable file of the entry that still differs across the review's
       interval (is in its ``files_changed``) is in its ``files_reviewed``. A
       file the entry changed that is back to the interval's base content needs
       no reading. A review whose subject is every judgeable file it changed
       (any valid edge) meets this for every entry, which is wave 1's
       whole-edge batch rule as the special case.
    3. No unresolved blocking finding stands at the review's two trees, or at
       ``entry_trees`` (the trees of the commit and of every commit it brought
       onto the base: a merged branch's own), over every fact
       (:func:`batch_review_blockers`). A blocker on the merged branch is owed a
       resolution, and a clean review that outlives it does not clear it, so a
       merge that bypassed a blocked PR gate stays not covered until
       ``verify-resolutions`` records one. ``None`` (the caller could not read
       them) refuses, as unread entry files do.

    **Relax-only.** It reads facts and returns an answer about one entry; it adds
    no edge, and :func:`coverage_verdict` never calls it, so no gate verdict can
    move because a batch fact exists. Its caller may only turn a not-covered
    release entry into covered with it, never the reverse.

    The caller passes only boundary-stage reviews: stage is the consolidator's
    reading of a mode, which this pure module does not import.

    Returns ``{"status": "covered" | "blocked" | "not", "reason": str}``, with
    ``outside`` (the files the review did not rate) on condition 2's refusal and
    ``unresolved`` (as :func:`coverage_verdict` lists them) on ``blocked``.
    """
    body = review.get("body") if isinstance(review, dict) else None
    if not isinstance(body, dict) or review.get("kind") != "review":
        return {"status": "not", "reason": "not a review fact"}
    changed = body.get("files_changed")
    reviewed = body.get("files_reviewed")
    if not (
        is_object_id(body.get("base_tree"))
        and is_object_id(body.get("head_tree"))
        and isinstance(changed, list)
        and isinstance(reviewed, list)
    ):
        return {"status": "not", "reason": "the review's interval or file sets are malformed"}
    if not brackets:
        return {"status": "not", "reason": "the review's interval does not bracket the commit "
                                           "on the base's first-parent line"}
    if not isinstance(entry_files, list):
        # Unread is never "changed nothing": that would credit any commit.
        return {"status": "not", "reason": "the commit's changed files could not be read"}
    in_interval = {f for f in changed if isinstance(f, str)}
    rated = {f for f in reviewed if isinstance(f, str)}
    outside = [f for f in judgeable_files([f for f in entry_files if isinstance(f, str)])
               if f in in_interval and f not in rated]
    if outside:
        return {"status": "not", "outside": outside,
                "reason": f"the review did not rate {len(outside)} of the commit's judgeable "
                          f"file(s): {', '.join(outside)}"}
    if entry_trees is None:
        return {"status": "not", "reason": "the commit's own trees could not be read, so no "
                                           "blocker standing on them could be ruled out"}
    unresolved = batch_review_blockers(facts, review, entry_trees)
    if unresolved:
        named = ", ".join(f"{u.get('review_id')} {u.get('fid')}" for u in unresolved[:3])
        return {"status": "blocked", "unresolved": unresolved,
                "reason": f"{len(unresolved)} unresolved blocking finding(s) stand at the review's "
                          f"trees or the commit's own ({named}{' …' if len(unresolved) > 3 else ''})"}
    return {"status": "covered", "reason": "the review rated every judgeable file of the commit "
                                           "still changed across its interval, with no open blocker"}


def _find_path(
    edges: list[dict],
    src: str,
    dst: str,
    diff_fn: DiffFn,
    key_fn: "KeyFn | None" = None,
) -> "list[dict] | None":
    """BFS from ``src`` to ``dst`` over the :class:`_EvidenceGraph` — review
    edges plus free edges among the trees the evidence mentions and the two
    endpoints. Free steps on the returned path carry their ``files``, filled in
    for the found path only when the key form established them."""
    graph = _EvidenceGraph(edges, src, dst, diff_fn, key_fn)
    visited = {src}
    queue: deque[tuple[str, list[dict]]] = deque([(src, [])])
    while queue:
        node, path = queue.popleft()
        if node == dst:
            return _attribute_free_steps(path, diff_fn)
        for other, step in graph.steps_from(node, reverse=False, skip=visited.__contains__):
            if other in visited:
                continue
            visited.add(other)
            queue.append((other, path + [step]))
    return None
