# Issue #774 — Governance: No Norm Governs Comment Content or Volume: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-09-10 · source: user
(observed live, PR #773) · issue: https://github.com/brookstalley/prawduct/issues/774`

Related: #772 (this norm's Migrate ref — remediation of prawduct's own files lives there, not
here); #348 (the Python-only dormancy class this must not repeat); #167 (the evidence that a norm
alone does not install); #422 (closed — prose-diet, adjacent surface).

## Problem

Comments in this codebase narrate how a function got here instead of what it does for its caller
and why it is non-obvious. The owner's report — 1000-word comments documenting a function's
history — is confirmed by measurement, and two of PR #773's three review warnings were this exact
pathology.

**The complaint names two different defects, and only one of them is unspecified.** *"Documenting a
function's history"* is **Axis A**, and a rule for it already exists on both sides of the review:
`plugin/methodology/building.md:88` tells the builder *"never narrate history — history's one home
is commits and the change-log, so a comment recounting it is a deletion, not a rewrite,"* and three
protocol files tell the reviewer the same thing as a **deletion finding**. Axis A is an adherence
gap, not a specification gap.

*"Rather than what it does and how to use it"* is **Axis B**: a doc-comment whose interface is
buried under present-tense design narration. **Nothing in the repo addresses Axis B**, and Axis B
is where the volume actually is.

## Grounding facts

Re-verified against the current tree (2026-09-10). Comment lines counted by SonarQube's
*significant* definition (a comment line with alphanumeric content; bare `#` and separator lines
excluded); docstring lines counted by AST span.

- **Plugin non-test `.py` is 6,410 comment + 16,135 docstring of 45,006 non-blank lines = 50%.**
  #772 measured 51% over 42,038 lines. The tree grew ~3,000 lines and the proportion held, so the
  disproportion is **not self-correcting** — it reproduces at the rate new code is written.
- **Docstrings are three quarters of it** (16,135 of 22,545). A norm scoped to `#` comments alone
  would miss most of the measured surface. This is why the target is comments *and* doc-comments.
- **Worst files:** `critic_marker.py` 80%, `install_reference_probes.py` 75%,
  `retired_state_probes.py` 71%, `hooks/digest.py` 71%, `gitattributes_probes.py` 70%. Largest in
  absolute terms: `buildplan_refs.py` — 1,558 comment+doc lines of 2,391.
- **Nine of the fifteen worst files are `*_probes.py`.** The pathology concentrates in one
  family's house style rather than spreading evenly, which matters for how #772 sequences its
  migration.
- **The Axis A rule exists in four places** — `plugin/methodology/building.md:88` (builder side),
  and `plugin/skills/critic/review-protocol.md:125`, `plugin/skills/critic/goals-1-3.md:104` and
  `plugin/skills/pr/review-protocol.md:94` (reviewer side, all three classing a history-narrating
  comment as a **deletion** finding). An earlier draft of this document claimed no rule existed;
  that claim was produced by a grep for length/volume vocabulary, which the rule's own wording does
  not use. **Corrected here rather than quietly** — the false claim would have justified writing a
  second copy of a rule that already has a home.
- **Enforcing Axis A perfectly would not move the 50%.** Counting id / chunk / review references in
  the worst files: `plan_index.py` (70% density) has **zero** and is fully compliant;
  `critic_marker.py` (80%) has five; `buildplan_refs.py` (65%) has sixty-seven, its worst case, out
  of 1,558 comment+doc lines. The density is **not** made of history narration.
- **What `critic_marker.py` actually does wrong is ordering.** Its module docstring opens with the
  CRT-3X9D incident narrative and reaches what the module provides in the third paragraph. The
  rationale is load-bearing and should survive; the interface should not be underneath it.
- `plugin/skills/critic/review-protocol.md`'s line-84 ceiling governs how harshly comment *drift*
  is scored — a third axis again, presuming a correct comment that went stale.
- **Ruff carries no comment rule**, and per `pyproject.toml` the ruff stanza is explicitly
  groundwork — not running, no CI job, 149 sites still carrying `prawduct:allow` pragmas ruff
  cannot read. A linter mechanism is unavailable in this repo today even if one existed.
- **The preferences file exists, at `.prawduct/artifacts/project-preferences.md`** — 29KB, 58
  norm-index rows. **An earlier draft said it did not exist and that `/prawduct:doctor` Check #14
  was firing; both were false** (Critic `rev-20260910T155357Z-2ed219ba`). The bare
  `.prawduct/project-preferences.md` path this document had invented is read by nothing: every
  runtime reader — `norm_index_scaffold.PREFERENCES_REL`, `norm_probes._preferences_lines`,
  `briefing.py`, `init_product.py` — uses the `artifacts/` path. Chunk 01 initially shipped a file
  there, where it sat unread **and contradicted** the canonical one on ratified points (inverted
  Error handling to exception-based against a norm reading *"new code that raises within governance
  internals is a violation"*, flipped Branching from `direct`, dropped the 2026-08-19 owner ruling
  on parallelization). Deleted, not relocated. **Enumerate a file's readers, not the documents that
  describe it.**
- **This work draws the three-reviewer review at any size.** `risk_surfaces` in
  `project-state.yaml` lists `plugin/skills/` and `plugin/bin/*hook*`; the norm touches the first
  and the probe registration the second.

### Prior art

- **SonarQube `comment_lines_density = comment_lines / (lines + comment_lines)`** is the
  established language-agnostic formulation, implemented across ~30 languages. Two details worth
  copying: non-significant comment lines (empty, separators-only) do not count, and file-header
  license blocks are excluded — both are noise that would otherwise dominate small files.
- **"Revision history belongs in commit messages, not comments"** is settled convention across
  published style guides. This anchors the norm's *Why* in an external standard rather than in
  this repo's taste, which matters for a norm we intend to offer to other products.

## Decisions (owner, 2026-09-10)

| # | Fork | Ruling |
|---|---|---|
| D1 | Reach | Ships to **all governed products**, not prawduct-only |
| D2 | Mechanism | **Norm + Critic goal + locator**; the locator points, never grades — and per *Governing norms* it is not a prawduct-authored lexer |
| D3 | Target | **Comments and doc-comments together** |
| D4 | Day one | **One-shot ratification invitation** per repo, dismissible |
| D5 | Adoption | Probe ships instantly; **norm registry stays product-owned** |
| D6 | Retroactivity (prawduct) | **Migrate**, born `in-transition`, tracked by **#772** |
| D7 | Rule kind | **Narrow framework floor + product norm above it** (inferred — see below) |

**D1's rationale is a named failure class, not a preference.** #348 recorded
`_GREEN_IS_EVIDENCE_DIRECTIVE` firing off a Python-only signal and going silently dark in every
Swift/Go/TS/Rust/C# product — *"in a product whose owner has no way to observe that it was
supposed to fire."* Learning #91 generalizes it. A Python-only comment locator would be the same
defect with a new name.

**D2's rationale cuts against the obvious design.** The intuitive mechanism — a block-length
ceiling or comments-per-function ratio that fails a check — is ruled out twice over: #772's
acceptance says *"no line-count or percentage target adopted"*, and
`templates/project-preferences.md`'s false-confidence guardrail says *"if a generated test would
pass on conforming code but couldn't reliably catch a real violation (e.g., greppy heuristics for
semantic rules), prefer Critic over a weak test."* A comment-length ceiling is precisely a greppy
heuristic for a semantic rule. The number's only legitimate job is **locating** files for a
judge — never being the judge.

**D2's counterweight is #167.** A norm alone does not install: the reporter there wrote the
governing rule hours before committing two more violations of it. So the locator is not optional
decoration — it is what makes anyone look.

## The norm

Two axes, two different pieces of work. **Only Axis B needs a new rule.**

### Axis A — already specified; the gap is reach, not wording

`building.md:88` is read **on demand**, and only by a builder about to write code against a plan.
The always-injected digest carries only the *id-decay* half of the rule (*"durable prose never
rides on a value that changes under it"*), not the *history* half. So the rule that would have
caught two of PR #773's three warnings is in a file that session had no reason to open.

**The work here is one sentence of reach**, extending the digest's existing bullet — not a new
rule, and explicitly not a second home for an existing one.

### Axis B — the new norm

**Statement.** A comment or doc-comment **leads with what a reader needs in order to use or change
the thing it documents.** Design rationale, alternatives weighed, and recorded rulings follow it,
clearly separated. A reader who needs only the interface must not have to read the rationale to
find it.

**Phrased as *what a reader needs*, not *what it does for its caller*, deliberately.** D3 rules
comments and doc-comments both in scope, and a caller-shaped predicate silently excludes plain `#`
blocks — including `pyproject.toml`'s ruff stanza, one of the two comments this norm is required to
leave intact. The reader's first question generalizes where "its caller" does not: for a callable
it is the signature; for that stanza it is "is this gating yet?", which it already answers in its
opening sentence.

**This is a rule about ordering and separation, not about volume**, and that is deliberate on three
counts. It does not ask anyone to delete rationale, so it does not collide with the oversized-file
advisory's warning that recorded reasoning *"is the methodology working"* and is not the thing to
cut. It cannot be satisfied by a line count, so it cannot decay into the percentage target #772
forbids. And it leaves every do-not-reintroduce comment intact — `is_judgeable_path`'s ruling and
`pyproject.toml`'s ruff stanza both keep their full length, and simply sit below the interface.

**Why.** A comment's first reader is almost always someone who needs to *call* the thing, not
someone deciding whether to change its design. Making that reader page through a design essay to
find the signature taxes the common case to serve the rare one — and it is the concrete form of the
owner's report, which named history and interface in the same breath. Rationale placed *after* the
interface loses nothing: the reader who needs it reads on.

**Mechanism:** Critic (Goal 4 — Norms). Judgment-required by construction: no linter can tell an
interface paragraph from a rationale paragraph, which is also why this is language-agnostic for
free. **Audit home:** janitor — and this is a **correction to an earlier draft**, which said
`advisory`. `docs/norms.md` requires an advisory-homed norm to name the mechanical hook its probe
fires on, and after the locator redirect there is no such hook. A norm claiming an audit home it
has no mechanism for is the aspirational failure this repo names by name.

**Status:** `in-transition` for prawduct. **Retroactivity:** `migrate: #772`.

## Governing norms — and the one that redirected this design

Reconciled against `.prawduct/artifacts/architecture.md` § Direction before any code, per
`methodology/planning.md` "Governing Artifacts".

**1. "Prawduct is written in Python and must never be specific to Python."** `Status:
in-transition` (LNG-5W8R), with a live interim rule: *"where prawduct must classify a file itself,
it dispatches from a per-suffix table and reports an unknown suffix as **unchecked** rather than
passing it. No gate acquires a language-specific parser — suffix matching only. **A parser per
language, and a syntax-pattern table per language, are both the complexity ratchet this norm exists
to prevent.**"* A bounded Stopgap extends the interim rule to 2026-12-01 (owner ruling #732).

**2. "Prawduct guides and reviews; it never implements."** *"prawduct never re-implements what a
product's own tooling already does… a check prawduct writes to duplicate a linter is a worse
version, maintained by non-specialists, that must be re-derived for every language the framework
meets — while the ecosystem's own tool is both better and language-agnostic for free."*

`[DECISION: the density locator is NOT a prawduct-authored per-language comment lexer; the judging
mechanism is the Critic, and any number comes from the product's own tooling or is reported absent
| a comment-lexing table keyed by suffix IS the "syntax-pattern table per language" norm 1's
interim rule names as the ratchet it exists to prevent, and it is simultaneously the linter
re-implementation norm 2 forbids. This is not a close call on either norm, and the repo has already
paid for the lesson: `compliance.py`'s per-language broad-except regex table is the same shape, and
`pyproject.toml` records that it is being retired precisely because it "re-derived, per language,
rules a linter already implements — and failed open on every language it did not know." Building a
second one while deleting the first would be the laundering tell | user can veto/override]`

**What this costs, stated honestly.** The one-shot invitation (D4) was specified to cite the
repo's density figure, and in a repo with no comment-density tooling there will be no figure to
cite. The invitation still fires — it just names the rule and the ratification path rather than a
percentage. Prawduct's own repo is the exception, not the template: the 50% figure in *Grounding
facts* was produced by a throwaway measurement script for this document, and **that script is
evidence, not a deliverable** — it must not be promoted into the runtime, which is exactly how the
banned lexer would enter through the back door.

**Third norm, satisfied — with its home corrected.** *"Every fact has one home."* An earlier draft
put the norm statement's home at "the methodology floor." That was left over from when Chunk 01 was
to author methodology text, and it is wrong for Axis B: Axis B is the **product-owned layer**, so
its home is the preferences file's norm block and the Enforcement row points at it. Methodology is
Axis A's home, and Axis A is restated nowhere. Two axes, two homes, no fact in two places.

## Requirements

**R1 — The Axis B norm is captured with full anatomy.** Statement, Why, scope, Status,
Retroactivity, and an Enforcement row assigning mechanism (`Critic`) and audit home (`janitor` —
there is no mechanical hook, and claiming `advisory` without one is the aspirational failure). Per
`docs/norms.md` § Birth, a norm adopted over existing code requires a retroactivity decision with
one of three honest outcomes; ours is Migrate, and Migrate obliges `Status: in-transition` naming
the tracking item.

**R1a — Axis A gains no second home, and its reach change is BLOCKED pending an owner ruling.** The
rule already lives at `plugin/methodology/building.md` and in three review protocols; restating it
anywhere is the duplication the `every fact has one home` norm forbids, and writing a second copy
was the concrete risk this document's corrected grep created.

The proposed reach change — one sentence extending the digest's durable-prose bullet — was written,
measured and reverted: the injected token ceilings have **one token of headroom** in each session
shape (framework 3211/3212, product 2095/2096), and the tightest wording costs 18. The measurement,
the two funding routes, and the recommendation to decline are recorded in the build plan under
Chunk 01 *Blocked deliverable*. **Descoped explicitly, not dropped** — the requirement stands
unmet until the owner rules.

**R2 — The norm lands in the canonical preferences file, additively.** That file is
`.prawduct/artifacts/project-preferences.md`, it already exists with a ~58-row norm index, and the
requirement is that the norm is **added** — one Code Style bullet, one norm block, one Enforcement
row — with every pre-existing row and owner ruling preserved. The path is not cosmetic:
`PREFERENCES_REL` decides whether a norm is visible to `norm-index-scaffold`, to the
`norm-registry-unratified` probe Chunk 02 must mirror, and to Chunk 03's `norm_registry_ratified`.

**R3 — The rule ships in two layers, and the floor is already shipped.** The **floor** is Axis A —
change history goes to the change-log and the build plan, not into comments. It binds every
governed product today, with no ratification, exactly as the owner confirmed it should; the work
against it is reach (R1a), not authorship. The **product-owned layer** is Axis B — interface
before rationale — offered and ratified per product, each owner making their own retroactivity
call. The layer boundary is itself a requirement: a product must be able to comply with the floor
while declining the layer above it.

**R4 — The judging mechanism carries no per-language syntax knowledge.** Two ratified norms in
`architecture.md` § Direction forbid the obvious implementation, and they are why the locator is
not a lexer (see *Governing norms* below). The mechanism that reads comment content must be one
that is language-agnostic **by construction**, not by enumeration — the Critic, which reads source
with a model and needs no comment grammar for any language. Where a *number* is wanted, it comes
from the product's own tooling if it has any, and is otherwise absent — never from a
prawduct-authored per-language comment lexer.

**R4a — Absence is reported, never passed.** Where no density figure is available for a file or a
language, the surface says `unchecked`. A silent zero is the #348 defect and the norm's fail-open
clause names it explicitly: *"a language with no rules currently yields the same output as a
language that passed, so Python-specificity is invisible to exactly the person who would otherwise
catch it."*

**R5 — One shot, dismissible, and the dismissal is a decision.** The advisory fires once per repo
on the `norm-registry-unratified` pattern (`plugin/lib/norm_probes.py:1230`), clears on a
committed shared-state answer so a teammate's ratification clears it for everyone, and does not
recur.

**R6 — Nothing here returns a verdict on a number.** No pass, no fail, no threshold that gates
anything. This is a requirement on the *interface*, not only on the current configuration — a
surface that returns a boolean invites a gate to be built on it later.

**R7 — Prawduct's own retroactivity is executed, not merely declared.** #772 is updated to become
the named migration item, and prawduct ratifies this norm against itself through the doctor flow —
the dogfood pass that proves the adoption path works before other products meet it.

## Decision — the rule splits into a framework floor and a product-owned layer

**Confirmed by the owner, 2026-09-10.** Recorded first as an assumption when the question went
unanswered; affirmed before any code was written. What the confirmation did *not* anticipate — and
what the corrected grep then showed — is that the floor it endorses **already exists and already
binds**. The split holds; only the work under it moved.

**The question this resolves.** Doctor's Norm Ratification Flow proposes candidates by reading *the
product's own* artifacts — norms the owner already declared, which ratification merely records. It
has no mechanism for "prawduct suggests you adopt this," and § Adoption is emphatic: *"What the
framework must never do is decide which unmarked statements are norms on the owner's behalf."*

**Why the split rather than either pure answer.** Prawduct already ships binding craft rules that
no owner ratifies — *"Tests are contracts. Fix the code, never weaken the test."* binds every
governed product on upgrade. So the framework plainly may declare craft rules; the live question is
*which* ones, and the answer tracks how contestable the rule is:

- **The floor is not contestable.** "Revision history belongs in commit messages, not comments" is
  settled convention across published style guides, and this repo already has two durable homes for
  history that no product lacks. Shipping it as methodology claims no more authority than the
  tests-are-contracts rule does, and it installs on upgrade — which is what #167 says a rule needs.
- **Everything above it is contestable.** How dense is too dense, whether every public function
  owes a doc-comment, whether module headers carry design narrative — these vary legitimately by
  language, team and domain. A framework that dictated them would be declaring taste, and a product
  disagreeing would have to depart from methodology rather than simply decline a norm.

**What this buys structurally.** It removes the new-capability requirement from the critical path:
the floor needs no ratification flow change at all, so no "framework-offered candidate" concept has
to be invented, built and reviewed on a risk surface before anything installs. The product-owned
layer then rides the *existing* flow unchanged — a product ratifies its own density norm the same
way it ratifies any other, from its own declared direction.

**Two routes considered and rejected for the existing-repo case.** Shipping the norm as a filled
row in `templates/project-preferences.md` fails twice: the table ships empty by design, and
`init-product` copies templates only into destinations that do not exist — so a template fix
reaches new onboards and nothing else. That is the precise mechanism behind doctor Check #14's
leftover-scaffold finding, and it is the migration failure this item exists to avoid.

## Acceptance

- [ ] The Axis B norm is stated with full anatomy (statement, Why, scope, Status, Retroactivity)
      and an Enforcement row naming mechanism `Critic` and audit home `janitor`
- [ ] Axis A gains **no** second copy — the diff adds reach (one digest sentence) and no restatement
- [ ] The stated norm demonstrably preserves the do-not-reintroduce comments named above — checked
      against `is_judgeable_path`'s docstring and the `pyproject.toml` ruff stanza specifically,
      both of which must survive at full length, relocated below the interface at most
- [ ] The norm is in `.prawduct/artifacts/project-preferences.md` — the path `PREFERENCES_REL`
      names — with its pre-existing rows and rulings intact (norm-index row count strictly +1)
- [ ] No second preferences file exists at any other path
- [ ] No per-language comment grammar, prefix table, or lexer ships in the runtime — verified by
      inspection of the diff, and the measurement script used for this document stays out of it
- [ ] Where no density figure is available the surface says `unchecked`, never zero and never clean
- [ ] `critic_marker.py` reads interface-first when the norm is applied to it — the worked example
      that proves the norm is applicable rather than merely stated
- [ ] The advisory fires once, clears on a committed answer, and does not recur
- [ ] A product can comply with the methodology floor while declining the product-owned
      layer above it — verified, not asserted
- [ ] No threshold in the shipped code gates, blocks, or fails anything
- [ ] #772 carries the Migrate relationship and this norm names it as tracking ref
- [ ] Prawduct has ratified the norm against itself via the doctor flow

## Scope-out

- **Remediating existing files is #772**, not this item. This item ends when the norm exists, is
  enforceable, and prawduct has adopted it — the 50% comes down on #772's schedule, riding commits
  that open those files for other reasons.
- **Durable prose in `plugin/methodology/` and `documentation/`** is out of scope (#422 worked that surface
  and has shipped).
- **No linter rule.** Ruff is not running in this repo (`pyproject.toml`), and a cross-language
  linter mechanism is out of proportion to the outcome.
- **No change to `review-protocol.md`'s prose severity ceiling.** Adjacent axis; leave it.

## Evidence / references

- `plugin/docs/norms.md` — § Birth (retroactivity: Migrate / Contain / Grandfather, and the
  forbidden mixture), § Adoption (probe ships instantly, registry is product-owned), § Anatomy
- `plugin/templates/project-preferences.md` — Enforcement mechanism table, the rule for adding a
  preference, the false-confidence guardrail
- `plugin/skills/doctor/SKILL.md` — Norm Ratification Flow; Health Check #14 (absent preferences)
- `plugin/lib/norm_probes.py:1230` — `norm-registry-unratified`, the one-shot pattern to mirror
- `plugin/lib/compliance.py:34` — `_is_source_file`, the existing 15-extension language set
- `plugin/skills/critic/review-protocol.md:84` — the prose severity ceiling (different axis)
- `pyproject.toml` — the ruff stanza; why a linter mechanism is unavailable
- #772, #348, #167, #422; learning #91 (language-agnosticism)
- SonarQube metric definitions — `comment_lines_density`
