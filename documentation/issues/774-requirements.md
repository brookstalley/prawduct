# Issue #774 — Governance: No Norm Governs Comment Content or Volume: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-09-11 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/774`

Related: #772 (the migration/remediation item this norm's Retroactivity line must name as its
tracking ref — no doc exists for #772 yet either, and this document does not author one); #348
(the Python-only failure class this item's "reach" decision exists to avoid repeating); #167 (why
a norm alone, unenforced structurally, does not install itself — cited, not restated); #422
(closed, adjacent — durable-prose consistency, out of scope here per the issue's own scope-out).

The issue records six "Owner decisions (ruled 2026-09-10 — do not re-litigate)." This document
does not reopen them; it grounds each against the current tree, surfaces two decisions the issue
did not make but design cannot proceed without, and turns the result into numbered requirements.

## Problem

No norm anywhere in this repo — verified by the same grep the issue reports — states what a
comment or doc-comment is for, or where change-history narration belongs instead. The absence is
not enforcement drift; nothing was ever specified, so there is nothing for a reviewer to cite. The
repo's own instance of the artifact that would hold such a norm, `.prawduct/project-preferences.md`,
does not exist at all. Compounding: the plugin's existing Critic drift check already scores
comment/docstring *wording* staleness (a description whose subject moved) — a different axis from
content (what a comment should say) and volume (how much of the file is comment), so a fix here
must add a norm without duplicating or being confused with that existing check.

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-11):

- **`.prawduct/project-preferences.md` does not exist in this repo.** `git show
  <develop>:.prawduct/project-preferences.md` fails with "path does not exist" — confirms the
  issue's claim exactly, and confirms acceptance criterion 2 ("`.prawduct/project-preferences.md`
  authored for this repo") is authoring a file from scratch, not editing one.
- **The locator's language reach has one existing classifier to extend, not duplicate.**
  `plugin/lib/compliance.py:29-44`'s `_is_source_file` recognizes 12 extensions (`.py .js .ts .jsx
  .tsx .go .rs .java .rb .swift .kt .cs .c .cpp .h`), excludes test-named files and anything under
  `.prawduct/`. The issue's own acceptance criterion says "the ~15 languages `compliance.py::
  _is_source_file` already recognizes" — the count is 12, not ~15; a small factual correction to
  carry into design, not a reason to build a second classifier. This is the same function named as
  the reuse target in the issue's own `refs:` list.
- **The Enforcement table's shape and pointer-row convention are ratified, not proposed.**
  `plugin/docs/norms.md:307` (`## Enforcement — who checks what, when`) defines the per-preference
  table `| Preference / norm | Mechanism | Enforcement artifact | Audit home | Why |`, three
  mechanisms (Linter / Test / Critic), and a pointer-row shape (`norm lives in <artifact> §
  Direction`) for when the norm is stated elsewhere. `plugin/templates/project-preferences.md`'s own
  false-confidence guardrail — "if a generated test would pass on conforming code but couldn't
  reliably catch a real violation... prefer Critic over a weak test" — is the concrete textual
  source for the issue's Decision 2 ("prefer Critic over a weak test"): comment *content*
  ("interface + non-obvious why") is judgment-required, so Mechanism = Critic is not a new idea,
  it is this template's existing rule applied to a new row.
- **The Migrate retroactivity shape is exact, not paraphrased.** `plugin/docs/norms.md:148-172`
  (`### Birth — capture and retroactivity`) states Migrate as: existing violations become sized
  backlog work, **and the norm is born `Status: in-transition` with the migration item as its
  tracking ref** — which is precisely what the issue's Decision 6 asks for, #772 named as that ref.
  No new retroactivity mechanics need designing; this document only needs to state the norm's
  Retroactivity line points at #772.
- **The one-shot invitation the issue wants "reused" has one concrete precedent, not a documented
  pattern separate from its code.** `plugin/lib/norm_probes.py:1204-1253`
  (`probe_norm_registry_unratified`) fires when a strategy-class artifact exists and either no
  `## Direction` entry is ratified anywhere, or the Enforcement table lacks norm columns; it is
  gated on the shared-state key `RATIFIED_FACT = "norm_registry_ratified"`
  (`norm_probes.py:166`), registered via `register_probe(FEATURE, "norm-registry-unratified", ...)`
  (`norm_probes.py:1325`). `plugin/docs/norms.md:376-395` (`## Adoption — existing products`)
  documents this probe's day-one behavior and the on-demand `/prawduct:doctor` ratification flow,
  including "no norms to ratify" as a valid, advisory-clearing answer. This is the "one-shot
  pattern" the issue's Decision 4 names — a second, independently-gated probe function following
  the same shape, not a call into the existing one (see Decision D4 below for why the existing
  key cannot be reused directly).
- **No goal named "Norms" exists anywhere in the plugin.** A repo-wide search
  (`review-protocol.md`, `goals-1-3.md`, `framework-checks.md`, `plugin/docs/principles.md`) for
  "Goal 4" or "Norms" as a goal name returns nothing matching that pairing. `review-protocol.md`'s
  own goal list (`:34`, "Your goals, in priority order — you run all seven") names seven goals by
  their stated titles (`### 1. Nothing Is Broken` through `### 7. The Design Is Sound`); goal 4 is
  titled `Everything Is Coherent` (`:83`), not Norms. The **Normative authority** preamble
  (`:36-46`) — which precedes and governs all seven goals, not goal 4 specifically — states
  explicitly that a departure, unruled edge-work, normative change, or unrecorded norm birth is
  raised as a **Goal 3 BLOCKING** finding (`:40`), naming the `project-preferences.md` row or
  Direction statement departed from. So today, every normative departure — this one included, once
  the norm exists — is a Goal 3 finding, never a Goal 4 finding. The issue's acceptance criterion
  ("the norm reaches Critic review through Goal 4 (Norms) — no new goal invented") names a goal
  that does not exist under that description; see Decision D7.
- **Goal 4's existing Drift bullet already covers a related but distinct axis, and explicitly
  exempts norms from itself.** `review-protocol.md:84`: "comment, docstring and doc *wording*
  takes Severity Levels' prose ceiling... Norms are exempt — Normative authority above." This
  confirms two things at once: (a) comment/docstring *wording* staleness is Goal 4's territory
  today and this item must not duplicate it, and (b) Goal 4's own text already defers anything
  normative to the Normative-authority path (i.e., to Goal 3) — internally consistent with the
  previous finding, not a contradiction to resolve.
- **Neither of this item's own forward-declared artifacts exist yet.** The issue's `refs:` list
  names `documentation/issues/774-requirements.md` (this document) and
  `.prawduct/artifacts/build-plan-comment-content-norm.md`; neither existed anywhere in the repo
  before this session. This document is the first artifact against this issue.
- **#772, the Migrate tracking ref, has no design or requirements document of its own yet either.**
  Its retroactivity item being undesigned does not block this document: `norms.md`'s Birth section
  only requires the norm be born `in-transition` *pointing at* a tracking item, not that the
  tracking item already be designed.

## Decisions

Decisions 1–3, 5, 6 restate the issue's owner-ruled decisions, grounded; D4 sharpens Decision 4 with
one correction; D7–D9 are new, needed to unblock design, and were not ruled by the issue.

**1 (given). Reach is all governed products, not prawduct-only, and the locator extends
`compliance.py::_is_source_file` (12 recognized extensions, not ~15) rather than forking a second
per-language classifier.** Grounded above; the count correction carries into design and into
CCN-3 below.

**2 (given). Mechanism is a norm (Enforcement row, Mechanism = Critic) plus a density locator that
never itself passes or fails.** Grounded directly in the template's own false-confidence guardrail
and the Enforcement table shape at `norms.md:307`.

**3 (given). Target is comments and doc-comments together** (docstrings, JSDoc, `///`, `/** */`),
per the issue's own measurement showing docstrings are three-quarters of the counted volume.

**4 (sharpened). Day-one behavior is a new, independently-gated one-shot advisory, structurally
mirroring `probe_norm_registry_unratified` — but it MUST NOT be gated on the existing
`RATIFIED_FACT` key.** `RATIFIED_FACT` already means "the general norm registry has been ratified
(or declared empty) for this product." Wiring this norm's invitation to the same key would mean
dismissing the general norm-registry advisory silently also dismisses this one (and vice versa),
with no way to tell, from either shared-state fact alone, which decision was actually made. The
issue's acceptance criterion — "the one-shot invitation fires once, is dismissible, and dismissal
records a decision" — requires that decision be independently attributable. This document requires
a **second, dedicated shared-state key** (name deferred to design) alongside a second probe
function, following `probe_norm_registry_unratified`'s shape (own gate, own advisory candidate,
own registration) but answering its own question, not the registry's.

**5 (given). Adoption is per-product, owner-ratified via `/prawduct:doctor`; the framework never
decides which statements are norms on an owner's behalf.** Grounded in `norms.md:376-395`.

**6 (given). This repo's own retroactivity is Migrate, born `Status: in-transition`, with #772 as
the tracking ref.** Grounded in `norms.md:148-159`.

**7 (new). The norm's violations route through Goal 3 ("Nothing Is Unintended"), the goal the
current Normative-authority preamble actually assigns to every normative departure — not "Goal 4
(Norms)," which names a goal that does not exist under that description anywhere in the plugin.**
The issue's acceptance criterion is stale against the current protocol text (Goal 4 is titled
"Everything Is Coherent" and is about drift, not norms). Requirement CCN-6 below adopts the goal
the mechanism actually has today and requires the design pass to correct the wording gap — in the
issue, in `review-protocol.md`, or in both — rather than silently building against a goal number
that does not exist. This is exactly the kind of citation a requirements pass exists to catch
before a design or build spends time reconciling it under pressure.

**8 (new). The locator is a distinct signal from Goal 4's existing Drift bullet, and does not
modify it.** Goal 4's Drift check already scores comment/docstring *wording* staleness and
explicitly exempts norms from itself (`review-protocol.md:84`, "Norms are exempt — Normative
authority above"). This item's locator answers a different question (how much of a file is
comment/doc-comment, and does its content read as interface-plus-why or as narrated history) and
feeds Goal 3's normative check once the norm exists; it must not be merged into, or mistaken for,
Goal 4's drift scoring.

**9 (new). The locator's queryable form (a `prawduct-hook` subcommand, an advisory-candidate
payload, or both) is deferred to design.** The issue requires the locator "point at the worst
files so a reviewer looks," which needs some concrete surface a reviewer or the one-shot advisory
can read; this document requires that surface exist and be queryable ahead of a review, without
picking its shape.

## Requirements

MUST unless marked SHOULD. Prefix `CCN` (Comment Content Norm), scoped to this item alone.

- **CCN-1** A `## Direction` entry (or a preferences-table pointer row per `norms.md`'s pointer-row
  convention) MUST state the norm — comments and doc-comments govern interface and non-obvious
  why; change history belongs in `change-log.md` and build plans, the durable homes this repo
  already has — carrying its Why, `Status: in-transition`, and a Retroactivity line naming #772
  (Decisions 1, 3, 6).
- **CCN-2** `.prawduct/project-preferences.md`, authored fresh for this repo (Grounding facts: it
  does not exist), MUST carry one Enforcement-table row for this norm: Mechanism = Critic, Audit
  home = advisory, Enforcement artifact naming the locator (CCN-3), Why = the norm's stated
  rationale (Decision 2).
- **CCN-3** A density locator MUST compute the SonarQube-style ratio the issue's own Prior Art
  section cites (`comment_lines / (lines + comment_lines)`, doc-comments folded in per Decision 3)
  across every file `compliance.py::_is_source_file` recognizes today (12 extensions — Grounding
  facts), extending that shared classifier rather than forking a second one (Decision 1).
- **CCN-4** The locator MUST NOT pass or fail on any threshold; its only output is a ranked pointer
  at the worst-N files by this ratio, for a reviewer to read (Decision 2) — no line-count or
  percentage target is adopted anywhere in the shipped mechanism, inherited from #772.
- **CCN-5** A second one-shot advisory, structurally mirroring `probe_norm_registry_unratified`
  (own probe function, own registration, own `AdvisoryCandidate`), MUST fire once per repo as a
  ratification invitation, gated on a **dedicated** shared-state key distinct from `RATIFIED_FACT`
  (Decision 4) — the exact firing condition (what counts as "day one" for this probe) is deferred
  to design, but MUST NOT collapse onto the general norm-registry gate.
- **CCN-6** Findings against this norm MUST be raised as Goal 3 findings under the
  Normative-authority path the protocol already defines (Decision 7) — this item MUST NOT invent a
  new Critic goal, and design MUST reconcile the issue's "Goal 4 (Norms)" wording against
  `review-protocol.md`'s actual goal titles before build.
- **CCN-7** The locator (CCN-3/CCN-4) MUST remain distinct from Goal 4's existing comment/docstring
  wording-drift check (`review-protocol.md:84`) — this item ships no change to that check (Decision
  8).
- **CCN-8** The locator's output MUST be queryable by a reviewer (or by CCN-5's advisory) ahead of,
  and independent from, any single review invocation; its exact interface is a design-stage
  decision (Decision 9).
- **CCN-9** This item's scope ends at norm + locator + one-shot invitation; it authors no
  remediation of existing files and no design for #772 itself (see Scope-out).

## Acceptance

- [ ] A Direction entry or pointer row exists stating the norm, its Why, `Status: in-transition`,
      and Retroactivity → #772.
- [ ] `.prawduct/project-preferences.md` exists for this repo with the norm's Enforcement row
      (Mechanism: Critic; Audit home: advisory).
- [ ] The locator runs across every language `_is_source_file` recognizes (12 extensions today),
      demonstrated on at least one non-Python file, using the shared classifier rather than a new
      one.
- [ ] The locator never fails a build or review on a number — it only ranks and points.
- [ ] The one-shot invitation fires once, is dismissible, records its own decision independent of
      the general norm-registry advisory's shared-state fact, and never fires again once answered.
- [ ] Findings against this norm are raised as Goal 3 findings — no new Critic goal exists, and the
      issue's "Goal 4 (Norms)" phrasing has been reconciled against actual goal titles before
      design proceeds.
- [ ] No line-count or percentage pass/fail threshold exists anywhere in the shipped mechanism.

## Scope-out (this item)

- Remediation of the plugin's own already-measured 50% comment+docstring proportion — #772's
  territory, and this norm's Migrate tracking ref.
- Any change to Goal 4's existing comment/docstring wording-drift check (`review-protocol.md:84`)
  — a different axis, untouched by this item (Decision 8).
- Durable prose in `plugin/methodology/` and `documentation/` — out per the issue's own scope-out,
  adjacent to the closed #422.
- The locator's exact queryable interface (Decision 9) and CCN-5's exact firing condition (Decision
  4/CCN-5) — both design-stage.
- Designing #772 itself — this document only requires that this norm's Retroactivity line name it.
- Whether a distinct "Norms" goal should be added to the seven-goal protocol — bigger than this one
  norm; this document only requires CCN-6 not invent one unilaterally to route this norm alone.

## Evidence / references

- `.prawduct/project-preferences.md` — absent from this repo; `git show <develop>:` confirms it
  does not exist. Issue acceptance criterion 2's target.
- `plugin/lib/compliance.py:29-44` — `_is_source_file`, the 12-extension classifier this item's
  locator must extend, its test-file and `.prawduct/`-path exclusions.
- `plugin/templates/project-preferences.md` — the Enforcement-table intro, mechanism table
  (Linter/Test/Critic), the false-confidence guardrail cited for Decision 2, and the "never leave a
  preference unassigned" rule.
- `plugin/docs/norms.md:111-145` (`## Anatomy of a Norm`) — the fields a Direction entry carries
  (Why/Status/Rulings/Retroactivity), relevant to CCN-1.
- `plugin/docs/norms.md:148-172` (`### Birth — capture and retroactivity`) — the three retroactivity
  outcomes and the exact Migrate shape (`Status: in-transition` + tracking ref) CCN-1/Decision 6
  rest on.
- `plugin/docs/norms.md:307` (`## Enforcement — who checks what, when`) — the Enforcement table's
  column shape and pointer-row convention.
- `plugin/docs/norms.md:376-395` (`## Adoption — existing products`) — the day-one one-shot pattern
  and on-demand `/prawduct:doctor` ratification flow this item's CCN-5 mirrors, and the "no norms to
  ratify" valid-outcome precedent CCN-5's dismissal-recording borrows.
- `plugin/lib/norm_probes.py:166` (`RATIFIED_FACT = "norm_registry_ratified"`) — the shared-state
  key Decision 4 requires this item NOT reuse directly.
- `plugin/lib/norm_probes.py:1204-1253` (`probe_norm_registry_unratified`) and `:1325`
  (`register_probe(..., "norm-registry-unratified", ...)`) — the concrete one-shot-probe precedent
  CCN-5 mirrors structurally.
- `plugin/skills/critic/review-protocol.md:34-46` — the seven-goal list and the Normative-authority
  preamble routing every normative departure to Goal 3, grounding Decision 7/CCN-6.
- `plugin/skills/critic/review-protocol.md:83-86` (`### 4. Everything Is Coherent`, Drift bullet at
  `:84`) — the existing comment/docstring *wording*-drift check this item must stay distinct from
  (Decision 8/CCN-7), and its own "Norms are exempt" line corroborating Decision 7.
- Issue #774's own Prior Art section — the SonarQube `comment_lines_density` formula this document
  cites for CCN-3 without independently re-deriving it.
- #772 — this norm's Retroactivity tracking ref; itself undesigned, which does not block this
  document (Grounding facts).
