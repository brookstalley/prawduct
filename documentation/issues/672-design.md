# Issue #672 — Critic: Coverage Composes by Tree but Its Gates Key on Identity: Design

`status: draft · stage: design · area: critic · added: 2026-09-24 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/672`

Related: #334 (Half 1's *write* leg — cited by #672 itself as sharing its root; Grounding facts
below finds it likely already resolved by a later rewrite, not re-opened here); #536 (fixed the
`Superseded:` *message* — Half 1 asks to change the underlying *design* that message correctly
describes); #669 (adjacent, not overlapping, per #672's own dedup note); #895 (a **different**
defect in the same `diagnose_base_advance_transfer` function — condition 1's set-equality after a
stacked-branch parent merge — filed 2026-09-23 and explicitly bouncing the "diagnostic wording"
sub-item back to #672; this design claims that sub-item).

**No separate requirements doc exists for #672, and none is needed** — the issue's own body carries
the problem statement, two independently-measured incidents (~10 min each), three candidate
directions, and an explicit shared-root framing. That is what a requirements pass would otherwise
produce; this document verifies each candidate against the current tree, resolves which to build,
and specifies the change. (Same convention #712, #843, #669 and others state for themselves —
`documentation/issues/843-design.md` § opening.)

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-24):

- **Coverage composition genuinely is tree-keyed, which is the floor both halves stand on.**
  `coverage_algebra.review_edges` (`plugin/lib/coverage_algebra.py:358`) builds a graph whose nodes
  are git tree ids and whose edges are review facts connecting `base_tree → head_tree`; a verdict is
  reachability over that graph (`coverage_verdict`, called from `gates._merge_base_verdict`). Nothing
  about *which round* raised a finding enters this layer — only tree identity does. The issue's
  framing ("the layer beneath asks *same tree?*") is accurate and unchanged by anything below.

- **Half 1's mechanism, confirmed exactly as described.** A blocking finding is recorded under
  `(review_id, fid)` and resolved only by a resolution fact naming that exact pair —
  `coverage_algebra.resolution_index` (`:316`) and `unresolved_blocking` (`:339`) both key on it with
  no fallback. `critic_consolidate._prior_review_fact` (`:2165`) anchors a `verify-resolutions` pass
  to the **single most recent** fact via the derived cache's one `fact_id` pointer
  (`.critic-findings.json`), and `_mark_cache_superseded` (`:1953`) documents *why* the cache is a
  single slot rather than a list ("mark, never delete" — deleting would strand the anchor for an
  abandoned review). The consequence: once round *N+1* dispatches, round *N*'s fact can never again
  be the anchor of a future `verify-resolutions`, so any of round *N*'s blocking findings a later
  round discharged **under a different fid** (because every review mints its own `R-1`, `R-2`, …
  starting from 1) have no resolution fact matching `(N, R-k)` and read as permanently unresolved.
  `critic_consolidate.carried_blocking` (`:756`) is the function this surfaces through today, and its
  own docstring names the exact failure ("R-12 sits on a superseded round that no later
  verify-resolutions pass will name again"). `review-cycle.md:104` documents the resulting
  `Superseded:` state as the **designed** exception, not a bug — so this design is a proposal to
  change a ratified behavior, which is what #672 itself says it is doing.

- **The finding/resolution schema has no "rule" field, so the issue's own proposed subject
  ("file + rule + normalized title") needs adapting.** `.prawduct/artifacts/data-model.md:118-119`
  states a finding's actual fields: `fid`, `goal`, `severity`, `title`, `recommendation`, plus
  `files` (used by `dispositions.py:270-ish`, `cited = finding.get("files")`). No `category` or
  `rule` key exists anywhere in `plugin/lib` (`git grep '"category"'` — no hits outside this survey).
  `evidence.finding_title` (`:729`) is the one place three historical spellings of the same field
  (`title`/`summary`/`name`) are reconciled, so it is the correct read path for whichever field a
  subject key uses.

- **#334 appears to already be substantially resolved by a rewrite the issue predates, which
  matters because #672's own dedup note calls #334 Half 1's write-side sibling.** #334 (filed
  2026-08-01) describes `render-dispositions` composing over "the newest fact only". The current
  `plugin/lib/dispositions.py` module docstring (`:1-14`) states the fix in the past tense — *"So
  dispositions become facts and the census becomes a rendering of them"* — and `disposition_index`
  (`:166`), `prior_dispositions` (`:187`), and `census` (`:639`) all walk **every** disposition fact
  in the store, not a single derived view. This reads as #334 already shipped in substance (its
  three merged predecessors — CRT-2X7R, CRT-7P5J, CRT-3F7T — line up with exactly the write/read/
  render split its own body describes). **This design does not close #334** — that is a separate
  issue with its own acceptance criteria and its own re-triage — but it means Half 1's fix below
  should not assume #334's problem still exists at the disposition layer; the remaining gap is
  specifically the coverage/gate layer's `(review_id, fid)` keying, which #334 never touched.

- **Half 2's condition 2 is already scoped to judgeable files only, which is exactly what
  direction 3 asks for — but this predates #672 and cannot be confirmed sound from reading alone.**
  `coverage.diagnose_base_advance_transfer` (`:484`) computes `required = judgeable_files(branch_diff)`
  from condition 1, then diffs every candidate endpoint against the required span's endpoint
  **pathspec-limited to `paths = sorted(required)`** (the `_survivors` closure). A conflict-resolution
  edit confined to a non-judgeable file (`plugin/CHANGELOG.md` — a plain `.md`, not
  governance-protected, so `is_judgeable_path` at `:79` returns `False` for it) is outside that
  pathspec and should not by itself break condition 2 as the function reads *today*. The function
  existed before #672 was filed (`f0c19460`, 2026-08-13, five days before the 2026-08-18 incident),
  so I cannot tell from git history alone whether the judgeable-only scoping was present at
  observation time or has since been refined — and the function has been touched as recently as
  2026-09-22 (`dd76523f`). **Treat "does a non-judgeable-only conflict still deny the transfer" as
  unverified, not as fixed** — Decision 4 below makes the live check the first step of the build
  rather than assuming either answer.

- **A worse, currently-live version of the "diagnostic wording" gap exists independent of both
  named candidates, and it is the one thing in this item I can confirm end to end from the code
  alone.** `transfer_remedy` (`gates.py:2097`) — the function that renders *any* explanation of a
  denied transfer — is called from exactly two sites: `session_review_verdict`
  (`gates.py:1481`, the Stop-gate/briefing path, call at `:1655`) and `_cumulative_critic_verdict`
  (`gates.py:2575`, the PR gate, call at `:2697`). **Both call it only when
  `classify_transfer(transfer) == "unavailable"`** (a degraded check — git could not compute a
  diff). When `diagnose_base_advance_transfer` instead returns `None` outright — conditions 1 or 2
  failed cleanly, which is exactly the shape a byte-different conflict-resolution produces —
  `classify_transfer` (`:459`) returns `"absent"`, and **neither call site prints anything about the
  transfer at all.** The operator sees only the generic `uncovered` / "run a full cumulative"
  remedy, with no indication a transfer was attempted or why it declined. This is strictly worse
  than the "could not run" wording #672 flagged (that wording at least names that a check ran) and
  is a different failure from the one #895's evidence describes ("a degraded candidate steals the
  explanation for a denial that content mismatch already caused" — #895's own scope-out explicitly
  leaves that half to #672). Fixing the silent-`absent` case is cheap, self-contained, and not gated
  on either open verification above.

## Decisions

**1. Shared-root framing: adopt "match by subject, bounded by lineage" for Half 1; treat Half 2 as
"probably already correct, confirm before building."** The two candidate directions in the issue are
not symmetric in how settled they are — Half 1's gap is fully reproducible by reading (no fallback
match exists anywhere in the resolution-index code path); Half 2's gap may already be closed by code
that landed for unrelated reasons. Building both as if equally open would mean shipping dead code for
half this item. Decision 4 makes the live check for Half 2 the first build step rather than a
requirements question.

**2. Subject key: `(frozenset(finding.get("files") or []), normalize(finding_title(finding)))`.**
`normalize` = casefold, collapse internal whitespace to one space, strip a trailing sentence-ending
punctuation mark. No stemming, no fuzzy matching — two titles that are reworded between rounds (a
real possibility; a reviewer re-describing the same defect in fresher prose) will **not** match, and
that is the right failure direction for something that clears a BLOCKING finding without a human
disposition: a false negative costs a round that was already going to happen (today's behavior,
unchanged); a false positive silently un-blocks a live defect. Titles are free text with no schema
constraint (`data-model.md:118`), so no stronger normalization can be justified without inventing a
constraint the reviewer contract does not impose today — that is a separate item (tightening the
`title` field itself), not this one's to open.

**3. Lineage bound: subject-matching applies only inside `carried_blocking`'s existing anchor
relationship, never as a store-wide join.** `carried_blocking` already restricts its blocking-finding
survey to the one review fact whose `head_tree` equals `this` pass's `base_tree` (`:774-782`) —
precisely to avoid picking up a sibling worktree's unrelated review as "this branch's prior round."
The fix extends that same-anchor survey: after this verify pass's own resolution facts are read
(the ones it just wrote, or that already existed), compute the subject key of each and treat an
INHERITED blocker as resolved if its subject key matches ANY resolution recorded against a finding
on the anchor review's own resolved-lineage chain (the anchor and every fact between the anchor and
HEAD that the coverage graph already accepts as an edge — reusing `review_edges`/`coverage_verdict`'s
own reachability rather than inventing a second one). A finding whose subject is fixed on an
unrelated branch, in an unrelated worktree, or in a sibling PR never enters this survey, because
`carried_blocking`'s anchor selection already excludes it before subject-matching runs. This is
additive to the existing `(review_id, fid)` exact match, never a replacement — the exact match still
resolves the common case for free; subject-matching only widens what the *carried* set considers
answered.

**4. Half 2 build order: verify live before writing new code; ship the wording fix regardless.**
First build step is a fixture reproducing #672's own Half 2 scenario against current `develop`: two
branches sharing a base, one merges, the other syncs and resolves a conflict confined to a
non-judgeable file, then calls `diagnose_base_advance_transfer` directly. If it already returns
`{"status": "match"}`, direction 3 is done — ship the fixture as a permanent regression test and
close that half of the acceptance criteria with no production code change. If it still denies,
extend condition 2 with the tolerance direction 3 describes: a conflict-resolution commit whose own
diff against its two merge parents touches only non-judgeable paths does not count against blob
equality for the required (judgeable) span. Either branch of this decision ships the **silent-`absent`**
fix from Grounding facts unconditionally: both `session_review_verdict` and `_cumulative_critic_verdict`
render `transfer_remedy`-equivalent context whenever a transfer was **attempted** (required
non-empty, i.e. the branch's own diff has judgeable content) and did not grant — not only when it
is classified `unavailable`. The message for a clean `absent` denial says plainly that condition 1
or condition 2 did not hold (byte-identical requirement, not an availability problem), closing the
wording gap #895 bounced back without touching #895's own condition-1 relaxation.

**5. Do not touch #895's scope.** #895 is condition 1's set-equality after a base-advance transfer
(a stacked branch whose surplus files are exactly what the advance brought in) — a distinct root from
either half of this item. This design's Decision 4 changes only messaging and (conditionally)
condition 2's tolerance; it leaves condition 1 exactly as #895 will need to find it.

## What ships

1. `plugin/lib/coverage_algebra.py`: new `finding_subject(finding) -> tuple[frozenset[str], str]`
   (Decision 2), pure and colocated with `finding_title`'s reuse point; new
   `carried_blocking_with_subjects` — or an additive keyword on the existing `carried_blocking` — that
   accepts the calling pass's own newly-recorded resolution facts and resolves an inherited blocker
   whose subject matches one of them (Decision 3), reusing `review_edges`/`coverage_verdict` for the
   lineage bound rather than a new reachability computation.
2. `plugin/lib/critic_consolidate.py`: `carried_blocking`'s one call site (`:~4875`, inside
   `begin_review`) passes this pass's own resolution facts once they're read, so the subject-widened
   survey runs where the exact-match survey already runs today — no new call site.
3. `plugin/lib/coverage.py`: `diagnose_base_advance_transfer` gains the non-judgeable-conflict
   tolerance **only if** Decision 4's live check shows it is still needed; either way, its docstring
   gains the verified fixture as a cited example (Grounding facts' honesty rule: a docstring claim
   should point at the test that proves it, not just assert it).
4. `plugin/lib/gates.py`: `session_review_verdict` (`:1481`) and `_cumulative_critic_verdict`
   (`:2575`) render transfer context on `"absent"` with a non-empty attempted span, not only on
   `"unavailable"` (Decision 4). `transfer_remedy` (`:2097`) gains a branch for the clean-denial case,
   naming condition 1/2 by their actual content ("the branch's own diff was not byte-identical to a
   prior covered span" / "no prior covered span shares this branch's exact judgeable file set") —
   the same two-sentence shape `blocking_remedy_lines` (`:2139`) already uses for its own three-case
   structure, so the messaging idiom stays one shape across both gates rather than acquiring a second.
5. `review-cycle.md:104` is amended: the `Superseded:` sentence changes from "clears only through a
   spanning `cumulative`" to "clears through a spanning `cumulative`, **or** through a later
   `verify-resolutions` pass whose own fix matches the blocker's subject" — the ratified-behavior
   change Decision 1 commits to.

## Acceptance criteria — how each is met

- **A defect raised in round N, re-raised under a new fid in round N+1, and fixed there, no longer
  requires a full `cumulative` to clear round N's copy** — Decisions 2/3, `finding_subject` +
  `carried_blocking`'s lineage-bounded subject match.
- **A subject match never crosses branch, worktree, or PR boundaries** — Decision 3, inherited
  unchanged from `carried_blocking`'s existing anchor restriction; the fix widens what counts as
  resolved *within* that boundary, never the boundary itself.
- **The base-advance transfer's tolerance for a non-judgeable-only conflict is either already true
  (regression-tested) or made true** — Decision 4, live-checked before any production code is written.
- **A denied transfer always says why, including the `absent`/no-degraded-reason case that renders
  nothing today** — Decision 4 / What ships #4, closing the sub-item #895 explicitly left to this
  issue.
- **No change to #895's condition 1 or #334's disposition/census layer** — Decision 5 and Grounding
  facts' #334 finding; both are named, neither is edited.

## Scope-out (this item)

- **#895's condition-1 relaxation** (stacked branch, parent merge, surplus-file superset case).
  Different root; #895 is its own item and this design leaves condition 1 untouched (Decision 5).
- **Re-triaging or closing #334.** Grounding facts records the evidence that it is likely already
  resolved in substance, for the next person who opens it — this item does not carry the authority
  to close someone else's issue on a read-through, and #334 has its own acceptance criteria (the
  session-handoff composition leg in particular) this design has not verified.
- **Tightening the `title` field's schema** (stemming, structured rule ids, etc.) to make subject
  matching more forgiving than exact-normalized-string. Decision 2's conservative normalization is a
  deliberate choice, not a placeholder for a follow-on — loosening it is a new proposal with its own
  false-positive analysis, not a natural extension of this one.
- **A store-wide "same subject anywhere" index.** Decision 3 is bounded to the anchor lineage on
  purpose; a global subject index is a different (and much riskier) feature this item does not ask
  for and the issue's own text does not request.

## Evidence / references

- `plugin/lib/coverage_algebra.py:358` (`review_edges`), `:316` (`resolution_index`), `:339`
  (`unresolved_blocking`), `:297` (`blocking_findings`), `:79` (`is_judgeable_path`), `:113`
  (`judgeable_files`) — the tree-keyed base layer and the exact-match resolution layer this design
  extends.
- `plugin/lib/critic_consolidate.py:756` (`carried_blocking`), `:2165` (`_prior_review_fact`),
  `:1953` (`_mark_cache_superseded`) — Half 1's mechanism, confirmed as described in Grounding facts.
- `plugin/lib/coverage.py:459` (`classify_transfer`), `:484` (`diagnose_base_advance_transfer`) —
  Half 2's mechanism and the already-judgeable-scoped condition 2.
- `plugin/lib/gates.py:1481` (`session_review_verdict`, call at `:1655`), `:2575`
  (`_cumulative_critic_verdict`, call at `:2697`), `:2097` (`transfer_remedy`), `:2139`
  (`blocking_remedy_lines`) — the two call sites that render (or, today, silently don't render)
  transfer context, and the message-shape precedent Decision 4/What-ships-#4 follows.
- `plugin/lib/dispositions.py:1-14` (module docstring), `:166` (`disposition_index`), `:187`
  (`prior_dispositions`), `:639` (`census`) — the fact-composed rewrite that appears to already
  answer #334.
- `.prawduct/artifacts/data-model.md:109-144` — the finding/resolution/disposition fact schema this
  design's subject key and lineage bound are built against.
- `plugin/lib/evidence.py:664` (`findings_index`), `:729` (`finding_title`) — the field-aliasing
  reconciliation `finding_subject` reuses rather than re-deriving.
- `plugin/skills/critic/review-cycle.md:104` — the ratified `Superseded:` behavior this design
  proposes to amend (Decision 1, What ships #5).
- `plugin/skills/pr/SKILL.md:51` — Step 1's own statement that a conflict resolution denies the
  transfer outright, the operator-facing description this design's Decision 4 makes accurate for the
  `absent` case rather than leaving it to mean "and you will not be told why."
- Issue #672's own body (2026-08-18) — both measured incidents, the three candidate directions, and
  the dedup notes against #536/#334/#669 this document resolves or defers.
- Issue #895 (2026-09-23) — the sibling condition-1 defect in the same function, and its own
  scope-out line bouncing "denial-message wording (#672 'Diagnostic wording')" back to this item,
  which What ships #4 claims.
