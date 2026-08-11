---
artifact: architecture
version: 1
depends_on:
  - artifact: product-brief   # vision lives in README.md + CLAUDE.md
  - artifact: data-model
last_validated: null
---

# System Architecture

<!-- Triggered by classification.structural.multi_process_distributed (monolith-with-workers).
     Describes the intended process topology, communication channels, concurrency model, and
     persistence boundaries. Written toward the design we want to hold — where the current code
     has not fully arrived, the text says so. -->

## Design Intent

Prawduct's architecture serves one goal: **govern an AI coding session without ever trusting the
governed party to certify itself.** Everything below follows from that. Five invariants express
what we want to be true.

1. **Code owns the data plane; the model supplies judgment as content.** Every file a gate trusts
   is written by deterministic code. A reviewer's judgment enters only as *content inside a
   validated partial*, which code checks against a code-written manifest before it becomes a fact.
   The line between "what a reviewer claimed" and "what the ledger attests" is code, always.

2. **An independent reviewer never mutates the session it reviews.** This is the load-bearing
   governance invariant. It is enforced at the *mutation site* (the session-reset command refuses to
   run while a review is active), not merely by restricting a reviewer's tools — because a
   dispatched subagent does not inherit the coordinator's tool restrictions.

3. **Local-first, no network, no daemon — in governance.** Coordination is process-spawn +
   atomically-written files + the git object database. There is no socket, port, or long-running
   server. This is a deliberate constraint: a governance layer that required infrastructure would
   not survive contact with "I just want to code." The **principal** network surface is the
   **opt-in** backlog backend (`backlog_service_repo`), which reaches GitHub Issues through the
   `gh` CLI; it is off by default, degrades to the markdown backend, and no gate or review verdict
   depends on it. It is not the only one — the full list, including one call that does run on a
   hook path, is enumerated in `security-model.md` and `project-state.yaml`'s `egress_boundary`.
   Kept as a pointer rather than a second copy, so the two cannot drift.

4. **Coordination is decoupled, idempotent, and fail-closed.** The processes that produce a review
   (coordinator, reviewers, consolidator) are never all alive at once; they communicate through
   files and reconverge through idempotent operations keyed by identity fixed at dispatch. When
   state is incomplete or ambiguous, the system blocks (fail-closed on *authority*), while probes
   that merely inform never block (fail-soft on *advice* — see the Failure Model).

5. **The plugin writes nothing into a repo it governs, except its own version marker and the
   guidance it injects.** All mutable state lives under the product's `.prawduct/` (per-worktree) or
   the clone's shared evidence store (inside `.git`). Governance code and methodology ship in the
   plugin and stay there. This is what lets a repo commit only a tiny install reference.

## Direction

<!-- Ratified norms (2026-07-17). The descriptive Design Intent above motivates these; the entries
     below are their binding form. See docs/norms.md. -->

- **An independent reviewer never mutates the session it reviews — enforced at the mutation site, not by tool-restriction alone.**
  Why: a dispatched subagent does not inherit the coordinator's tool limits, so the invariant must be enforced where mutation happens; this is the load-bearing governance guarantee — without it the reviewed party could quietly rewrite what it is being judged on.
  Status: steady-state. Mechanism: `prawduct-hook clear` refuses while a review is active (`critic-begin` … `critic-consolidate`/`critic-end`).
- **Authority fails closed; advice fails soft.**
  Why: anything that produces or consumes a governance *verdict* blocks on incomplete, malformed, or ambiguous state (so governance means something), while anything that merely *informs* degrades to a note (so governance stays bearable) — the split is also an abuse-resistance property: you cannot make a gate pass by feeding it garbage, garbage makes it block.
  Status: steady-state.
  Rulings: none live. **[[regen-views-is-advice]] retired 2026-08-08 — subject removed, recorded here rather than deleted (GD4).** That ruling reconciled this norm against `data-model.md`'s *derived views are never authoritative* for exactly one command, `regen-views`, by giving a view *writer* the fail-soft posture. The derived views are gone and so is the command, so the collision has no case to decide. **The category-level generalisation it produced is kept and promoted out of the ruling, because it never depended on that command:** *a command's failure posture follows what it produces* — this norm's why is that a verdict must not be satisfiable by feeding it garbage, which reaches a command only where a verdict exists to corrupt. Nothing that emits no verdict can attach the fail-closed half. A future view writer needs no new ruling; it inherits that sentence.
- **Local-first: *governance* coordination is process-spawn + atomically-written files + the git object database — no network, no daemon, and the governance runtime carries no third-party dependencies (dev/test tooling excepted). An opt-in backlog backend may take a network surface, provided it stays off by default, degrades to the markdown backend, and carries no governance verdict.**
  Why: a governance layer that *required* infrastructure would not survive contact with "I just want to code," and a zero-dependency stdlib runtime shrinks the supply-chain surface to prawduct's own code plus git. Both rationales survive this amendment intact, because the network surface is opt-in per product (`backlog_service_repo` unset ⇒ the markdown backend) and confined to backlog storage: a product that never opts in runs exactly the substrate this norm has always described, and no gate, evidence fact, or review verdict crosses the network.
  Status: steady-state.
  Amended: 2026-07-21, owner decision at the backlog-service cutover. The original entry declared that any future network surface would be "a characteristic flip, not a quiet addition" — this is that decision, taken deliberately rather than by accretion. Scope narrows from "no network anywhere" to "no network in governance; opt-in network for backlog storage." The dependency is the `gh` CLI, recorded in `project-state.yaml` `design_decisions.infrastructure_dependencies`. No structural characteristic flips: `gh` owns the credential (`~/.config/gh`) and the adapter never manages a token, so `handles_sensitive_data` stays absent.
- **The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile — `.gitignore`, `.claude/settings*.json`, and `CLAUDE.md`'s governance anchor — never framework files.**
  Why: least authority over the machine is what makes running the plugin a safe trust decision and what lets a governed repo commit only a tiny install reference; framework code stays in the plugin, read-only from the repo's perspective. The three reconciled files share one property that the carve-out turns on: each is the *product's own* file, which the plugin edits at a declared seam rather than authors wholesale — `CLAUDE.md` receives the thin `PRAWDUCT:ANCHOR` block and nothing else, exactly as `.gitignore` receives its managed section.
  Status: steady-state.
  Amended: 2026-07-30 — `CLAUDE.md` added to the enumeration. `[DECISION: name CLAUDE.md in the reconciled-files carve-out | the enumeration was incomplete at ratification, not permissive-by-omission: init_product.py has created-or-anchored CLAUDE.md and migrate_plugin.py has edited it in place (_EDIT_IN_PLACE) since before this norm was written, and the governance anchor is what makes plugin-based onboarding work at all. Leaving it unnamed meant the norm read as prohibiting the plugin's own installer, and the sibling 'never implements' norm named it while this one did not — a reader following the trust argument landed in the gap | user can veto/override]` This widens the written enumeration to match long-sanctioned behaviour; it authorizes no new write, and the "never framework files" limit is untouched.
- **Prawduct is written in Python and must never be specific to Python. Gates and canaries dispatch per *file* by language, never per repo; no gate may assume the governed product shares the runtime's language; and a language with no populated rules is reported as *unchecked*, never silently passed.**
  Why: the runtime's implementation language is an accident of the framework, not a property of the products it governs — those are Swift, Rust, C#, C, TypeScript and Python, and they are **routinely polyglot inside one repo** (a large Python service with a TypeScript frontend is the common shape, not the exception), which is what makes a repo-level language flag wrong at the file level and per-file dispatch the only correct granularity. The fail-open clause carries equal weight: a language with no rules currently yields the same output as a language that passed, so Python-specificity is invisible to exactly the person who would otherwise catch it — visibility is what keeps this norm from decaying into aspiration. Scope note: the framework's own `lib/` may of course be Python; this norm governs what gates *assume about the code they inspect*.
  Status: in-transition — LNG-5W8R tracks the migration. Interim rule: new gate code delegates first (below); where prawduct must classify a file itself, it dispatches from a per-suffix table and reports an unknown suffix as **unchecked** rather than passing it. No gate acquires a language-specific parser — suffix matching only. A parser per language, and a syntax-pattern table per language, are both the complexity ratchet this norm exists to prevent.
  Decision: `[DECISION: adopt per-file language dispatch as binding, with an unpopulated language reported unchecked rather than passed | the norm's why is that governed products are Swift/Rust/C#/C/TS and routinely polyglot, so a repo-level language assumption is wrong at the file level; the unchecked clause is what stops the norm decaying, since a silent no-op and a clean pass are indistinguishable at the output | user can veto/override]` Owner decision, 2026-07-29, stated directly ("we cannot let prawduct drift into being python-specific, even if we use python to drive the framework").
  Retroactivity: migrate: LNG-5W8R — inventory 2026-07-29, **partial by declaration, not exhaustive**. Confirmed compliant: `gates.py`, `coverage_algebra.py` (no language literals; path-based). Confirmed violating: `compliance.py` (`_is_test_file`, `_is_dependency_file`, `_check_broad_exceptions`); `plugin/bin/test-reference-verify` (`_PY_SYMBOL_RE`, `_is_python_file` — and it feeds `verify-coverage`, a **BLOCKING** Goal 1 check that therefore passes silently on Swift/Rust/C#, the most serious instance found); `gitstate.py` `_PRODUCT_CODE_SUFFIXES` (12 suffixes, missing `.cs`, fails open rather than reporting unchecked); ~~`release_verification.py`~~ — **discharged 2026-08-04**, both grounds, before the module's first release. `_VERSION_FILES` was a prawduct-layout table and `_version_from`'s `toml` branch a hand-rolled parser for one language's manifest format — the "no gate acquires a language-specific parser" clause exactly. Products now declare `release_version_files:` (path + format + key path), which is the remedy as owner-ruled — **declaration** rather than broader parsing — and the TOML read **delegates to stdlib `tomllib`** per this norm's own interim rule ("new gate code delegates first"), so the parser was deleted rather than taught about tables. The layout table survives only as an explicitly-labelled fallback *guess* that cannot produce a failure. Kept in this list, struck rather than removed: the enumeration is the migration's record, and a reader checking whether a named site was ever addressed needs the answer, not a gap. Completing this enumeration is LNG-5W8R's first acceptance criterion — an earlier revision of this line claimed `compliance.py` held *every* violation, which was false, and no reader should treat this list as closed until that sweep runs.
- **Prawduct guides and reviews; it never implements. It writes no product code, no config, and no tooling — a best practice enters as a *requirement* captured at discovery, Claude Code implements it, and the Critic blocks on a requirement that went unimplemented. The same line one level down: prawduct never re-implements what a product's own tooling already does. A bare-except check belongs to ruff or clippy, not to a prawduct gate.**
  Why: the framework's whole leverage is judgment about *what should be true*, delivered through artifacts and review. The moment it authors the thing it judges, it is both builder and reviewer and the independence that makes its verdicts worth anything is gone — the same reason the reviewer may not mutate the session it reviews, applied to the framework as a whole. The tooling corollary is that error one level down: a check prawduct writes to duplicate a linter is a worse version, maintained by non-specialists, that must be re-derived for every language the framework meets — while the ecosystem's own tool is both better and language-agnostic for free (prawduct never needs to know Swift's syntax because SwiftLint does). **The enforcement chain needs no new machinery downstream of discovery**: the Enforcement table already assigns each preference to Test/Linter/Critic, and an unimplemented requirement is already a blocking Goal 2 finding, so an iOS product whose requirements name SwiftLint and which ships without `.swiftlint.yml` is caught today. What *is* missing sits upstream, in discovery itself: `discovery.md` captures "testing, tooling, code style" preferences generally but never asks, per ecosystem present, which checker is standard — and with no captured requirement there is nothing for Goal 2 to enforce. LNG-5W8R carries that one gap.
  Scope: this norm governs prawduct-the-framework's relationship to the products it governs. Prawduct-the-product — this repo — is a product like any other and is built normally; writing Python here is not a departure. Owner ruling, 2026-07-29: conflating the two is a category error, and it is pre-decided at the category level so the next reader does not re-derive it.
  Status: in-transition — LNG-5W8R retires the two `compliance.py` checks that violate the corollary, and configures ruff for prawduct itself first so nothing is lost. Interim rule: a new check that duplicates an existing linter rule is not written — capture the toolchain standard as a requirement instead.
  Decision: `[DECISION: prawduct never writes product code, config or tooling; best practices are enforced as requirements through review, and prawduct never re-implements a rule an ecosystem's own tooling owns | the norm's why is that authoring what it judges makes prawduct both builder and reviewer, collapsing the independence its verdicts rest on — the same reason a reviewer may not mutate the session it reviews; the tooling corollary is that error one level down, and it is what the per-language ratchet grows from | user can veto/override]` Owner decision, 2026-07-29, stated directly ("Prawduct is *never* responsible for writing code… it's a framework that helps guide Claude Code to build better applications"), rejecting a provisioning design drafted earlier the same session.
  Retroactivity: migrate: LNG-5W8R — violating sites are `compliance.py` checks 1 and 3 (a re-implemented linter rule, and a re-implemented coverage judgment Goal 1 already owns). Explicitly **not** violations, because they are prawduct's own state and reconciled config rather than product code: everything the reconciled-files carve-out above enumerates, `CLAUDE.md` included — `init_product.py` creates-or-anchors it and `migrate_plugin.py` edits it in place (`_EDIT_IN_PLACE`). That carve-out is the enumeration's one home and this line stopped restating it on 2026-08-02: two enumerations in one document is the shape that let the 2026-07-30 amendment land in the norm and miss its copies elsewhere.

- **Goals and verification bind; prescribed method is advice.** A governing artifact says what must be true and how it will be checked, and those bind. Where it also prescribes *how* — a chunk's `Deliverables`, a named call site or file, a skill's ordering of steps — that is the author's best guess, made before the code was read, and a builder who finds a better route **takes it and records why** rather than conforming to a guess. Verification structure is not method and is untouched by this: independent review, mutation-proof, mechanical enumeration, and the gates all bind exactly as before, because they constrain the *output contract* rather than the route to it. Neither are the load-bearing invariants stated elsewhere in this section — reviewer non-mutation, authority-fails-closed, least-authority writes — which state what must be true, not how to get there.
  Why: the framework's leverage is accumulated judgment — learnings, artifacts, ratified norms — delivered to a model capable of reasoning from it, not a script for that model to execute. A method prescription written before the code was read carries the full authority of a spec while being a guess, and the builder standing at the call site routinely holds better information than the plan's author did. **Measured, not asserted:** on `learnings-firing` (2026-07-31), three chunk-level prescriptions were wrong — a delivery site that was structurally inert, a test file that does not exist, and a deliverable that was decorative because the constant it named was dead code — while every goal-level statement (Problem, Success, acceptance criteria) held. Faithful conformance would have produced strictly worse work in all three. The converse held in the same session, which is why the split is not simply "fewer constraints": mutation-proving caught two tests the builder was confident about and wrong about, and the mechanical `governed-by-gap` enumeration found 22 gaps across 8 plans. **A constraint earns its keep when it catches what the builder is structurally blind to; it costs more than it is worth when it prescribes a route the builder can derive better in context.**
  Scope: applies to prawduct's own artifacts and skills *and* to the products it governs — the owner's call was to loosen globally rather than gate it behind a preference, on the reasoning that a capable model working to goals beats one following a procedure, and that where the bet is wrong the cost is a recoverable miss rather than a silent one. It does **not** license skipping verification, dropping a requirement, or departing from a norm without the recorded decision this document already requires: a better route is still a route to the same stated goal, and Principle 2 (Complete Delivery) is unchanged.
  Status: in-transition — GOV-4T9P tracks the sweep.
  Decision: `[DECISION: prescribed method in governing artifacts is advisory; goals, acceptance criteria and verification structure bind | the framework's leverage is accumulated judgment delivered to a capable reasoner, not a script — and a prescription authored before the code was read has spec authority with guess reliability, which this session demonstrated three times in one plan; the carve-out for verification structure is what keeps this from being "fewer constraints," since the same session showed mechanical checks catching what judgment missed | user can veto/override]` Owner decision, 2026-07-31, stated directly ("I think it's ok for you to change specs unilaterally… if the change proves positive, it's a win. if it's negative, we learn… we may be over-constraining models here… models usually get better results working to goals versus prescriptive processes").
  Retroactivity: migrate: GOV-4T9P — **partial by declaration, not exhaustive.** Most existing prescriptive text needs no edit, because this norm changes how a prescription is *read* rather than forbidding it from existing. What does need migrating is text that asserts method as *binding*, where a reader cannot tell advice from authority. Confirmed sites, and both need care because neither holds the normative line a sweeper would grep for. **`templates/build-plan.md`** — `Deliverables:` appears *only* inside the three worked-example chunks (`:118`, `:131`, `:148`); there is no separate field definition, so **the example is the spec**, and the edit is to the example phrasing plus its surrounding guidance. **`methodology/planning.md`** — contains no literal `Deliverables:` string at all; it teaches the concept at `:57` and in the "Good chunks are" block at `:77-83`, which is where the contract phrasing is actually learned. A sweep that greps the field name will conclude both files are clean and skip the place the phrasing propagates from. Note also that neither file *was itself wrong*: the three failures were in a plan written from them, and the migration target is the phrasing authors copy, not a defect in the template. Explicitly **not** violations, and not to be relaxed by a later reader working from this line: `methodology/building.md`'s read-this-first instruction (knowledge delivery, not method), every `## Direction` invariant in this file, the Critic and PR gates, and the commit/merge conventions in `CLAUDE.md`. Completing the enumeration is GOV-4T9P's first acceptance criterion; this list is not closed.

- **Every fact has one home; every other mention is a reference to it.** A fact is anything checkable that can change — a number, a behaviour claim, a path, a rule statement, a schema. Its home is the place closest to the mechanism that owns it. Elsewhere: cite the symbol, the heading, or the command that yields it. Never restate it. **If changing a fact requires editing N places, N−1 of them are already wrong** — the only question is when someone notices. **A fact is the whole predicate, not a token inside it:** sharing a constant shares *syntax*; sharing the constant AND the reader that feeds it is what shares the *definition*.
  Why: coherence findings are the largest category the Critic produces and nearly all of them are one fact, copied, drifting — 9 of 23 on the changeset that prompted this norm. Correcting every copy is the wrong repair: it restores agreement and preserves the duplication that will break it again. The norm reframes the review question from *"do these agree?"* to *"why are there two?"*, and the fix from *update both* to *delete one*. This repo had already invented the rule four times for four fact types without stating it once — `LAST_MEASURED_TOKENS` ("do not keep a prose copy of a figure a mechanism can own"), `record_lint`'s `suite-total-claim`, learning 322 ("cite the command, never the digits"), and the `governed_by:` pointer table ("the statement lives in each artifact; this table is the index"). `data-model.md`'s **derived views never authoritative** is this same rule scoped to the evidence store; this is its general form.
  Scope: prawduct's own artifacts, code, comments and tests, *and* the products it governs. Not a ban on repetition for emphasis — a ban on a second **authoritative** statement. Quoting a fact and naming its home is a reference; restating it so a reader could act on the copy alone is a second home. **An index entry is a name, not a copy** — the `project-preferences.md` norm table carries a short title per norm and points at the artifact, which is a handle; the first draft of this norm's own row instead paraphrased the whole statement, which was a second home, caught on the day it shipped and shortened to a title. That is the line: a reader who can act on your text without following the pointer is holding a copy. **The granularity clause binds, and it is the harder half, because importing a symbol LOOKS like compliance.** Worked counter-example (2026-08-11): `record_lint._norm_field_re` imported `norm_probes._FIELD_MARKER_RE` *specifically* so two definitions of a norm entry could not drift, and its docstring asserted they "cannot drift apart on an edit". They drifted on the first edit — one module stripped blockquote markers before matching and the other walked raw text, so the byte-identical regex answered **differently on identical input**, and a quoted registry counted N entries in one module and 0 in the other. The shared symbol read as proof of agreement, which makes this failure worse than two frank copies: nobody re-checks a fact with one home. **So the test is not "did I import it" but "does the shared thing include the INPUT"** — a caller sharing a matcher must also share the normalization that feeds it, or move both behind one handle that returns them together.
  Status: in-transition — GOV-2R8K tracks the sweep.
  Decision: `[DECISION: one home per fact, everything else by reference | 40% of one review's findings were copies drifting, and the repair I applied (correct all four copies) preserved the defect; the rule already existed four times for four fact types, which is the upleveling failure this plan is about | user can veto/override]` Owner decision, 2026-07-31 ("we should have one source of truth for any fact, everything else by reference. we should enforce that on consuming repos").
  Decision: `[DECISION: a fact is the whole predicate — sharing a constant shares syntax, sharing the constant AND the reader that feeds it shares the definition | the norm was FOLLOWED (one home, imported symbol) and still produced two answers, because a token-level reading satisfies its letter; the shared symbol then reads as proof of agreement, so nobody re-checks it | user can veto/override]` Owner amendment, 2026-08-11 (#643), on the branch whose own code the stricter reading had already been fixed to (`b0a96583`) — the norm tightened against the code, not the code blessed by the norm. Case that produced it: [[one-home-is-the-predicate-not-the-token]].
  **This DOES forbid something previously permitted**, and the earlier draft of this line wrongly claimed otherwise. Sharing a constant while leaving its input unshared satisfied the norm as written and does not now; #643's own problem statement says so ("any product following the norm as written will share a constant and believe the job is done"), and this branch is the proof. The patch-release argument does not rest on the amendment being toothless — it rests on the amendment being small and its only known violating site being already fixed.
  Retroactivity: migrate: GOV-2R8K — **not yet enumerated.** **A THIRD KIND, added 2026-08-11 with the granularity amendment and stated here rather than discovered mid-pass (#342's own practice):** a *shared symbol with an unshared reader* — two call sites importing one constant but normalizing their input differently. No duplicate-text sweep can see it, because there is no duplicated text; the enumeration below and the two kinds #342 already carves out are all copy-shaped. Known site: `record_lint._norm_field_re` / `norm_probes._FIELD_MARKER_RE`, fixed in `b0a96583`. Known duplications from the review that prompted this: the restamp claim (4 copies), "sentinel tracker" (2), the empty-pointer promise (3), `changes_referenced`-means-judged-code (3). Enumerating the rest is the item's first acceptance criterion.

## Process Topology — "monolith with workers"

The **monolith** is a single long-lived Claude Code session. The **workers** are short-lived: hook
processes the harness spawns on lifecycle events, and reviewer subagents the session dispatches.

```
Claude Code harness (external)
  │  fires lifecycle hooks (python3, one process per event); backgrounds Agent subagents
  ├─ SessionStart  → identity/version banner · guidance digest (injected as context)
  │                → briefing (every source) · session reset (boundary sources only)
  ├─ Stop          → governance gates (Critic coverage + reflection) + consolidation backstop
  └─ SubagentStop  → (scoped to critic-reviewer) consolidate when all reviewers reported
  │
  ▼
Main Claude session  (the monolith / coordinator of work)
  │  invokes /prawduct:critic → forked context (own tool allow-list)
  ▼
Critic coordinator  (forked skill context)
  │  small change  → reviews itself, single-pass
  │  risk surface / 12+ judgeable → dispatches worker subagents, then STOPS
  ▼
critic-reviewer subagents (parallel workers, read-only + Write-partial only)
  │  each writes exactly one partial findings file
  ▼
critic-consolidate  (deterministic code — not a process of its own)
      runs from whichever trigger fires first: SubagentStop, the single-pass fork inline,
      or the Stop-hook backstop — all idempotent
```

The coordinator and reviewers are separate agent contexts; the hooks are separate OS processes.
`critic-consolidate` is code run inside whichever process invokes it.

## The Critic Data Plane

The flagship multi-process flow, and the clearest expression of invariant 1.

- **`critic-begin` (code).** Captures the working tree into the shared git object DB via a
  *temporary* index (never touching the session's real index or working tree), derives the review
  interval and reviewer roster from git + mode in code, and writes the dispatch manifest and the
  active-review marker. The manifest is the contract: it names the exact tree interval and roster a
  review will attest. It also carries `record_lint` — the deterministic record checks (`lib/record_lint.py`)
  answered here so no reviewer re-derives them. Those checks are **advice**: they never gate, they
  never reach a review's severity counts, and their per-check counts ride into the review fact so the
  control's own yield is a query rather than an argument. Cost is proportional to the diff, not the
  repo: line-scoped checks read one `git diff --unified=0` over the changed records and see only
  added lines.
- **Reviewers write partials (model judgment as content).** Single-pass: the fork writes one
  partial. Coordinator: each worker writes exactly the two paths the manifest's `rendezvous`
  records for its role — its started marker and its partial — and nothing else. Every partial is
  schema-validated, and declares the `dispatch_id` of the review that dispatched it, so a
  straggler from an abandoned review cannot satisfy a roster it never reviewed.
- **`critic-consolidate` (code).** Reads the manifest, collects the partials, and **fails closed**
  on any gap (missing role, wrong reviewed-commit, malformed partial → no fact). On success it
  appends the review fact (and any resolution facts) to the evidence store, regenerates the derived
  findings view, anchors a telemetry event, clears the marker, and removes the partials.
- **A review that never consolidates is archived, not deleted — and the archive is addressable.**
  A dispatch sweeping leftovers, and `critic-discard` clearing a stranded roster, both move the
  manifest + partials to `.prawduct/.critic-partials-archive/<review-id>/` (newest three kept).
  `critic-restore <review-id>` copies a set back so it consolidates **as itself**. That inverse is
  only sound because partials carry review identity: the recovery it replaces copied one review's
  partials into another's directory, which succeeded precisely because a partial was bound to a
  commit rather than to a review, and therefore recorded findings under the wrong review's id.
  Restoring the manifest alongside the partials is what makes the round trip lossless.

**Why consolidation is decoupled from dispatch.** The harness backgrounds dispatched subagents, so
the coordinator cannot reliably resume to aggregate. Instead, consolidation runs from three
independent triggers — the per-reviewer `SubagentStop` hook, the single-pass fork
inline, and the Stop-hook backstop — so the review lands regardless of which fires. **"Exactly once"
holds for the review *fact*, not for every output:** the fact is idempotent by `(kind, id)`, while the
governance-ledger anchor is replay-closed by `ledger.review_event_exists` and merely overlap-narrowed
(read-then-write, no lock). A concurrent overlap can still anchor twice — observed live 2026-07-29 —
and mandating concurrent coordinator dispatch made that path more reachable, not less. Residual:
CRT-8L3Q.

## Worktree & Distribution Model

"**Tree-keyed**" carries two distinct meanings; both are intentional.

- **Facts are keyed by git *tree SHA*, not by branch or commit.** A verbatim commit preserves its
  tree, so a review recorded before commit still vouches for the eventual commit from any checkout.
  Gates answer coverage by *composition over trees*: a squash-merge (same tree) stays covered, a
  rebase or amend (new tree) correctly opens a coverage gap. This is what makes governance survive
  normal git workflows instead of fighting them.
- **The evidence store is shared across all worktrees of a clone**, because it lives inside the
  shared `.git` common dir. Every worktree appends to and reads the same log, so review coverage
  composes across worktrees — while unrelated clones are isolated by construction.

**Session/gate state is per-worktree**, deliberately, so parallel worktree agents don't clobber each
other's session markers. The resolver pins governance reads and writes to the session's active
worktree. The split is the design: *shared* where coverage must compose (the evidence store),
*local* where sessions must stay isolated (session markers). Readers fail safe toward more gating
when the two disagree.

**Distribution.** Prawduct ships as a Claude Code plugin (skills, hooks, methodology, the
`prawduct-hook` CLI). A governed repo commits only an install *reference*; framework code lives in
the plugin root and is read-only from the repo's perspective. The one legacy exception — the 1.x
file-sync file registry — exists now only so migration can *remove* committed framework copies;
the plugin no longer places them.

## Concurrency Model

- **Races are avoided by construction wherever a design choice can avoid them.** Parallel reviewers
  each write a distinct partial file; a deterministic merge unions them. No *governance* state is a
  shared mutable file two writers contend on.
- **The one exception is the backlog cache, and it is a lock-based design on purpose.** The optional
  SQLite read-through store (`<git-common-dir>/prawduct/backlog-cache.sqlite3`) *is* a shared
  mutable file that several agents across several worktrees write concurrently, resolved by WAL plus
  a busy timeout rather than by partitioning. Construction cannot avoid it here: the store's value
  is that every worktree of a clone shares one cache, and a per-writer file would be a per-writer
  cache. It is safe to make the exception precisely because it holds **no governance verdict** — it
  is derived, gitignored, and rebuildable from the provider, so the worst outcome of a lost race is
  a re-fetch. A shared-mutable *authority* store would still be forbidden.
- **Idempotency absorbs the multi-trigger race.** The review's identity is fixed at dispatch, and
  every append is existence-guarded, so the three consolidation triggers collapse to exactly one
  fact — every repeat is a clean no-op.
- **Atomic writes everywhere.** All `.prawduct/` state files are written tmp-sibling-then-rename, so
  a reader sees old-or-new, never a torn prefix. Append-only stores use a single append-mode write
  syscall so concurrent whole-line appends from multiple worktrees interleave cleanly. Read paths
  self-heal a torn tail line rather than trusting it.
- **In-flight vs. abandoned.** When the Stop gate sees an active-review marker, it distinguishes
  "reviewers still running" (defer) from "review abandoned" (self-heal or block) by consulting the
  harness's background-task state — and fails closed on any ambiguity.

## Persistence Boundaries

| Tier | Where | Holds | Sharing |
|------|-------|-------|---------|
| Ledger (source of truth) | `<git-common-dir>/prawduct/` (inside `.git`) | evidence facts | shared by all worktrees of a clone; never committed |
| Derived cache (never truth) | `<git-common-dir>/prawduct/` (inside `.git`) | the optional backlog read-through store and the briefing-counts snapshot — **the same directory as the ledger above, and a different tier**: the provider is the home of every fact here, nothing originates, and a drop-and-rebuild is the mechanical proof of it. Discarded on any schema mismatch rather than migrated | shared by all worktrees of a clone; never committed |
| Session/gate state | `.prawduct/.*` (gitignored) | markers, partials, caches, session baselines, advisories | per-worktree |
| Committed product state | `.prawduct/` (tracked) | project-state, learnings, artifacts, change log, build plan — **and `backlog.md` only while a product is pre-cutover** | shared via git, owned by the product |
| Backlog, post-cutover | GitHub Issues on `backlog_service_repo` | the live backlog, reached through the `gh` CLI (channel 5) | owned by the target repo; `.prawduct/backlog.md` becomes **frozen history** and is no longer read as live state |
| Plugin (distributed) | `plugin/` in the prawduct repo; the plugin root once installed | skills, hooks, methodology, CLI, templates | read-only; never placed into a repo |
| Framework docs (this repo) | `documentation/` (tracked) | long-form requirements, PRDs, research, and the migration guide — human-facing working docs, framework-repo only (distinct from the plugin-bundled `docs/` reference) | committed to the framework repo |
| Upstream bug intake (this repo) | `incoming-bugs/` (tracked) | bug reports products file upstream about prawduct itself, via `/prawduct:report-bug`; triaged into the backlog, then archived under `incoming-bugs/archive/` | committed to the framework repo |
| CI (this repo) | `.github/workflows/` (tracked) | the suite on every push and pull request; `check-released` on a tag push, and on the `workflow_dispatch` the release runbooks issue — which is the route that fires on the release path, since the tag is created through the Releases API and so emits no push. Framework-repo only — it governs prawduct's own code, is never copied into a governed product, and never publishes a release | committed to the framework repo |

### What counts as a session boundary

Session/gate state is scoped to a *session*, so the definition of where one ends is load-bearing for
every gate that reads it. Claude Code fires `SessionStart` with five sources, and they divide on one
question — **was the transcript restored?**

| | Sources | What the hook does |
|---|---|---|
| **Boundary** | `startup`, `clear` | orientation **+** the reset (generate the handoff, consume the forward notes, archive the reflection, delete `.gates-waived`, re-capture the three session anchors) **+** the two boundary-dependent readers below |
| **Continuation** | `resume`, `compact`, `fork` | orientation **only**: briefing, advisories, session-file untracking, the state-size and preferences checks, the subagent briefing |

Statements sort into **three** categories, not two — the middle one is the easy mistake:

1. **Destructive boundary acts** — they delete or overwrite session-scoped evidence.
2. **Boundary-dependent readers** — they destroy nothing, but *interpret* session state as belonging
   to a session that has **finished**. Two qualify: the critic-active marker sweep (it deletes a
   marker on the theory that its writer's process is gone) and the previous-session gate check (it
   reads `.session-reflected`/`.gates-waived`/the change baseline and reports them as a completed
   session's record). Both are boundary-only. However read-only such a statement looks, it is not
   orientation — and sorting purely on "does it destroy evidence" puts it in the wrong column, which
   is exactly what the first cut of this split did.
3. **Orientation** — everything else: safe on every source, because it neither destroys session
   evidence nor assumes a boundary just happened.

The split is carried by the hooks.json matcher rather than by parsing the event payload, because the
matcher already carries the one fact needed. `--brief-only` selects the continuation path; it is
orthogonal to `--session-start`, which keeps meaning "a genuine hook invocation" (as opposed to a
reviewer subagent's bare `clear`, which the CRT-3X9D guard refuses). Note the ceiling on that
mechanism: `--brief-only` distinguishes continuation from boundary and **nothing finer**, so `resume`,
`compact` and `fork` are indistinguishable to the hook. Anything needing to tell them apart must split
the matcher further or read `source` from the event payload.

Two properties are easy to get backwards. First, a continuation must never re-capture an anchor **even
when one is missing**: stamping a resume-time clock onto a session that began earlier narrows the
Critic gate's jurisdiction, which is the defect the split exists to remove. An absent anchor already
fails closed, and failing closed is the safe direction. A third consequence follows from the same rule and is easy to miss: `.gates-waived` is deleted only at a boundary, so a declared waiver **outlives a continuation**. That is correct — a waiver is session-scoped and the session is continuing — but it means a waiver survives an unbounded number of resumes, which is a longer life than the pre-split behaviour gave it. Second, the marker sweep is **boundary-only**,
which is the opposite of the intuitive call: sweeping looks like a repair, and a crashed Critic's
marker does wedge an operator. But the premise that licenses deleting someone else's marker — an
in-flight review dies with the process that dispatched it — holds only for a session that *ended*.
`compact` fires mid-session in-process, and `fork`'s parent is frequently still running, so a marker
seen there is likely **live**; sweeping it would disarm both this norm's enforcement and the Stop
hook's abandoned-review backstop, which keys on the marker's presence. Sweeping a live marker is a
silent governance failure; leaving a dead one costs the 30-minute TTL, with `--force` and `rm` as loud
overrides. A crashed Critic is rescued by the next real boundary.

`fork` is the source most easily overlooked (it postdates the other four and was missing from this
plan's first draft). It restores the transcript *and* allocates a new session id, so the parent
session is frequently still running — making it the source where a boundary reset would destroy a
**live** session's evidence rather than a finished one's.

### The two model-owned session files

Session/gate state is machine-written by default — the model reads it, code writes it. Models do
write into `.prawduct/` elsewhere (reviewer subagents emit their own review partials), but those are
inputs to a machine consolidation step. Two files are different: they are narrative, and the machine
cannot synthesize them — `.session-reflected` (backward — what happened) and `.handoff-notes.md`
(forward — what the next session needs to know). The handoff pair's contract, which is the lock-in
that matters more than either file's format:

| | `.handoff-notes.md` | `.session-handoff.md` |
|---|---|---|
| Writer | the model, any time | the machine, at a session **boundary** only (`startup` / `clear` — never on a continuation) |
| Reader | the handoff generator, and nothing else | the next session (via the briefing pointer) |
| Lifetime | until *delivered*, then cleared (see below) | until the next boundary regenerates it |
| Scope | per-worktree, like every session file | per-worktree |

Consumption is transactional and keys on **delivery, not on the handoff having been written**: a
note is cleared only once its text is in the handoff, so one that was unreadable — or lost to a
failed write — survives for the next `/clear`. (Gating on "a handoff was written" is the near-miss:
it is true whenever any *other* section had content, so an unreadable note would be deleted
undelivered.) Notes get no archive of their own — their text is carried verbatim into the handoff,
which is where it is read. A generated handoff carries a machine marker; a `.session-handoff.md`
lacking it was hand-authored, and is folded into the new handoff rather than overwritten. Advice
fails soft applies throughout: none of this can block `/clear` — but every failure names its
consequence, because silent degradation is the bug this pair exists to fix. Failures split by
audience: housekeeping goes to stderr (the operator's), while "a note was left for you and did not
arrive" goes to stdout, which is the channel the incoming agent reads.

**What "survives" actually means, stated honestly** — the three survival paths differ, and only one
of them self-clears:

- *Delivered but not unlinked* — the text IS in the handoff; the stale copy is consumed on the next
  `/clear`. One hop, bounded.
- *Undelivered* (the handoff write failed) — the note is kept and persists until some later `/clear`
  writes successfully. Its text is in no handoff meanwhile.
- *Unreadable* — kept, and **unbounded**: nothing clears it until a human fixes or removes the file,
  and its text never reaches any handoff.

The last two are announced on stdout every session, which is what keeps them from being silent, but
neither is bounded by the mechanism and neither is visible *in the handoff*. Preferring an
unbounded, announced failure over an automatic deletion is the deliberate trade — this channel
exists because deleting an agent's note is the loss that matters — but the bound is the operator's
to close, not the code's.

**Both sides of the boundary can see the channel's state.** The failure this pair exists to fix was
silent in both directions, so two surfaces make it visible, and neither is a gate. *Forward:* when a
session did work and left no note — and left no hand-authored handoff to rescue either — the
generated handoff says so, in the position the note would have occupied, because a file listing a
session's commits and nothing else reads as a complete account of it. It is deliberately not raised
when a note exists but could not be *read*: that is the machine's failure, has its own notice at the
consumption site, and blaming the agent for it would contradict that notice. *Backward:* `handoff
preview` renders through the same function `/clear` does and stops there, so checking what the next
session would receive is no longer the same act as replacing what is there. The asymmetry is real
and worth stating: the absence signal reaches the incoming agent, who cannot act on it. What reaches
the agent who still could — the chunk-close step, the digest line, the preview — is all advisory
too, by the same norm.

**Known gap in the marker scheme:** it recognises a handoff that was *replaced* (no marker), not one
that was *appended to* (marker still present) — that text is still overwritten. Closing it needs a
retained copy or hash to diff against, judged disproportionate against a marker that already
redirects the writer. Tracked as SCN-2M6P; revisit if the net is observed firing at all, since that
is evidence agents still reach for the wrong file.

## Communication Channels

Four are local, and they are the only channels governance uses. A fifth exists only when a product
opts into the backlog service:

1. **CLI invocation + JSON on stdin/stdout** — the harness passes event payloads to `prawduct-hook`
   on stdin; skills and the Critic fork reach the data plane by invoking `prawduct-hook`
   subcommands. This channel also carries **behavioural directives**, not just data: a command whose
   output an agent reads at a decision point may state the rule that applies there
   (`critic_consolidate._CACHE_WARM_DIRECTIVE`, `_BATCH_FIX_DIRECTIVE`). The move is
   deliberate — a guide is read hours earlier if at all, and on the Critic's coordinator path the
   reviewing fork returns no findings summary, so this is the only surface the builder is guaranteed
   to meet. It is also *unbudgeted*, which is the bound worth stating: relocating instruction text
   out of a measured methodology file into a runtime string is legitimate when the string fires at
   the moment the rule applies, and is budget laundering when it does not. Directives here are
   advisory (they never block) and carry no prawduct-internal ids, per
   `observability-strategy.md`.
2. **Files as the shared bus** — the dispatch manifest, per-role partials, evidence store, findings
   view, and session markers let the decoupled coordinator, reviewers, and consolidator communicate
   without ever being alive simultaneously.
3. **Hook stdout injected as session context** — SessionStart hooks print the briefing and inject
   guidance; this is the harness→model channel.
4. **The git object database as a side channel** — tree objects written to the shared ODB, then
   referenced by SHA, are the substrate that makes tree-keying work across worktrees.
5. **`gh` subprocess → GitHub Issues REST** — *opt-in only*, present when `backlog_service_repo` is
   set. Sole egress lives in `lib/backlog/transport.py`; the counts cache under
   `<git-common-dir>/prawduct/` is a disposable, network-independent read-through of channel 2, never
   an authority. This opt-in is the only network surface a *governance verdict* depends on — but
   it is **not** the only network call the runtime makes: `cmd_stop` runs `gh pr list` on the Stop
   hook regardless of `backlog_service_repo`. The earlier phrasing here ("absent this opt-in,
   prawduct makes no network call") was simply false, and survived because nothing tested it.
   `security-model.md` enumerates all three sites; this section deliberately keeps no second copy.

   **One non-governance egress, added 2026-08-04.** `prawduct-hook check-released` shells to
   `gh` to ask whether a Release exists. It is an operator/CI command: it never runs on a
   session hot path, is never invoked by a hook, and produces no session governance verdict —
   so the local-first norm, whose subject is the governance runtime, does not reach it. It is
   named here rather than left to be discovered, because "prawduct makes no network call" was
   flatly true before this and is now true only with a qualifier. When `gh` cannot answer, the
   command reports *unverifiable* and exits 3 rather than guessing in either direction.

## Failure Model

The architecture holds two failure postures on purpose, and keeps them apart:

- **Authority fails closed.** Anything that produces or consumes a governance *verdict* blocks when
  state is incomplete, malformed, or ambiguous — a missing reviewer partial, an unreadable marker, a
  newer-than-known schema. A gate that cannot be sure prefers to block.
- **Advice fails soft.** Anything that merely *informs* — the SessionStart briefing, advisory
  probes, version banner — must never block session start or interrupt work. A probe that errors is
  swallowed with attribution, not raised. (See `observability-strategy.md` for how failures surface,
  and `nonfunctional-requirements.md` for the wall-clock budget this posture protects.)

The distinction is the whole ballgame: gates are strict so governance means something; probes are
gentle so governance is bearable.
