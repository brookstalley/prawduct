# Backlog — prawduct

<!-- Structured backlog (format v2). Managed via the /backlog skill.
     Each item: an ID line + a backticked metadata bar + optional free-form body.
     Sections: ## Open (pickable) · ## Promoted (in an active build plan) · ## Archive (shipped/dropped).
     Items move between sections only via explicit `/backlog update` calls. -->

## Open

- **[MET-8K4R]** Should prawduct ship PROCESS norms as ratifiable defaults, not only product norms? The plugin's own rules bind every governed repo on installation with no lifecycle — no exception path, no expiry, no erosion probe, no amend-tell
  `effort: M · impact: L · area: methodology · kind: question · source: user · added: 2026-07-27 · reviewed: 2026-07-27 · status: open · stage: research · related: MET-6Q3D, GOV-7Q4N, GOV-6N4W, GOV-EXI2, GOV-4X9M, JNT-8E3P · refs: plugin/docs/norms.md (§ Where Norms Live — all three homes are product-owned; § Adoption — "no auto-ratification"; § Exceptions expire; § Deliberate Non-Design — the no-new-file-class constraint), plugin/skills/doctor/SKILL.md § Norm Ratification Flow (the existing candidate-triage / bulk-confirm surface the sketch reuses), .prawduct/artifacts/architecture.md:182 ("The one model-owned session file" — the handoff-pair contract that surfaced this, currently descriptive prose), .prawduct/artifacts/architecture.md:172 (persistence table — "read-only; never placed into a repo"; the ruling's supporting finding), .prawduct/artifacts/architecture.md:59 ("Authority fails closed; advice fails soft" — a product ## Direction norm that the ruling reclassifies as constitutional; risk 1), plugin/templates/project-preferences.md:65 (§ Enforcement — "the product's norm index"; why preferences are a subset of norms, not a parallel kind), plugin/docs/principles.md, plugin/methodology/ (building.md, discovery.md, planning.md, reflection.md — the shipped rules with no lifecycle)`

  **Raised by the owner 2026-07-27 during the session-handoff-continuity build (Chunk 03). They asked the question rather than ruling, so nothing is decided.** *(Superseded in part — the owner ruled later the same day; see **OWNER RULING — 2026-07-27** at the foot of this item. The store question is settled; the constitutional-vs-default test is not.)*

  **The observation.** The norm lifecycle (`plugin/docs/norms.md`) is deliberately *product-scoped*: all three homes for a norm (project-preferences rows, `## Direction` sections, project-state classification) are product-owned, and binding force comes from the owner's declaration — "no auto-ratification." But the plugin **also** ships rules that bind every governed repo on installation: the methodology guides, the principles, the hook gates. Those have **no lifecycle at all** — no way to record a bounded exception, no expiry, no erosion probe, no amend-tell. A product either complies or silently does not, which is precisely the silent departure the Authority Rule says is never available.

  **Two parallel binding systems, and only one has a lifecycle.**

  **How it surfaced.** The handoff-pair contract — who may write which session file (`.handoff-notes.md` vs `.session-handoff.md`) — is norm-shaped, binds every governed repo's PROCESS, and currently lives as descriptive prose in this repo's `architecture.md`. It has no home in the norm system because the norm system has no place for a *plugin-shipped* norm.

  **Sketch of a resolution worth evaluating — not a decision.** The plugin ships process norms as **candidates** (a `## Direction` section in a plugin doc), and `/prawduct:doctor`'s existing ratification flow — which already reads artifacts, proposes candidates, triages the decision-worthy ones and bulk-confirms the obvious — offers them alongside the product's own. A product that ratifies gets the rule in its own Enforcement table with the full lifecycle; one that does not still gets today's advisory methodology guidance. This preserves "no auto-ratification" and adds no new file class — `norms.md` § Deliberate Non-Design forbids both.

  **THE ACTUAL DESIGN WORK is a split the spec does not currently have:** which process rules are **CONSTITUTIONAL** (bind on installation, no exception path — "never write Critic findings yourself" is fraud, not a preference) versus **DEFAULT** (shipped as candidates, product-ratifiable). Drawing that line is discovery-shaped, not a chunk. (user — owner)

  ---

  **=== OWNER RULING — 2026-07-27 ===** *Everything above this line is the question as originally raised. Everything below is decided by the owner, except where marked **STILL OPEN**. Status/stage/kind deliberately unchanged: the item stays `stage: research` because the constitutional-vs-default test is not yet ruled.*

  **RULED — two stores, not one.** A single norm data store cannot govern both consuming products and prawduct itself: you would have to merge prawduct norm updates *into* consumer repos, and parse consumer norms during prawduct updates. So — **separate terminology and separate storage**, even though the two are conceptually the same thing. Prawduct ships **only constitutional, inviolable norms**; anything that may legitimately vary by user or project belongs in the product's own `project-preferences`. Prawduct must therefore be very opinionated about exactly two things: **(1)** inviolable principles, and **(2)** **suggested defaults** that are *hoisted* into a consuming project's preferences/norms at onboard, where the user may adjust them.

  **Supporting finding — stronger than the merge-pain argument.** `architecture.md`'s persistence table (`.prawduct/artifacts/architecture.md:172`) says the plugin is *"read-only; never placed into a repo."* A shipped **mutable** norm store therefore has only two possible shapes, and both are dead on arrival:
  - **Read-only in the plugin** → a product cannot record an exception against it, so the norm *lifecycle* (exception, expiry, erosion probe, amend-tell) is dead — which is precisely the gap this item was filed about; or
  - **Copied into the repo at install** → that **is** the file-sync engine retired in M4 / v2.0.3 (`MANAGED_FILES` survives only so migration can delete committed framework copies).

  One store re-litigates the v2.0 transition. Cite this finding in the design rather than re-deriving it.

  **STILL OPEN — the constitutional-vs-default test.** Proposed 2026-07-27, **not yet ruled.** A rule is **CONSTITUTIONAL** if either:
  - **(a)** the shipped code already enforces it unconditionally, so a product *cannot* depart even if it wants to — calling it a preference would be a lie; or
  - **(b)** departing makes the framework's **output dishonest**, rather than merely different.

  Everything else is a **DEFAULT** (shipped as a candidate, hoisted at onboard, product-adjustable).

  Worked, as evidence the test actually discriminates:
  - *An independent reviewer never mutates the session it reviews* — passes **(a)**: `prawduct-hook clear` refuses while a review is active.
  - *Never write Critic findings yourself* — fails (a), passes **(b)** decisively.
  - *The handoff-pair **contract*** — passes **(a)**: the generator overwrites regardless of preference. But the *practice* of writing handoff notes at chunk close fails both limbs and is a **default**. The same surface splits across the line — which is exactly why it felt slippery when the question was raised.
  - *Never weaken a test* — fails (a), passes **(b)**: green stops meaning "behaviour preserved."
  - *Merge strategy, branching model, reflection cadence* — fail both ⇒ defaults.

  **Corollary worth keeping:** a rule *believed* constitutional that fails both limbs must either get its enforcing mechanism built, or be demoted to a default. That is the "quietly becomes aspirational" failure one level up from this item.

  **ANSWERED — preferences vs. norms are NOT duplicative, and should NOT be split terminologically.** `project-preferences.md` § Enforcement already declares itself *"the product's **norm index**"* (`plugin/templates/project-preferences.md:65`), and `docs/norms.md` § Where Norms Live lists preferences rows as one of the three homes a norm can occupy. Preferences are therefore a **subset** of norms, split by **subject** (code / architecture / identity), not by kind. **Methodology sits in none of the three homes — that hole is this item.** Under the ruling the load-bearing axis becomes **constitutional vs. product**, which cuts *across* preferences and norms; a second terminological axis would yield four quadrants with two of them empty.

  **Recommended shape (design input, not a ruling).** Keep **one index and one store** on the product side, and add a **third sub-table — hoisted process defaults** — populated by `/prawduct:doctor` from the plugin's candidate set. Separately: the blur the owner noticed in the Enforcement table has a *different source* than the constitutional/default distinction — that table is a **registry** in its top half (rows state the rule inline) and an **index** in its bottom half (rows are pointers). Same table, two jobs.

  **RISKS TO CLOSE BEFORE BUILDING.**
  1. **Prawduct is its own first consumer, and the one place the two stores overlap.** `architecture.md:59` today carries *"Authority fails closed; advice fails soft"* as a **product** `## Direction` norm — but under this ruling it is **constitutional**. Prawduct would become the first product whose norm store can drift from the constitution it ships. This must be a **rule, not a habit**: a constitutional rule is authored **once** in the plugin, and every artifact — prawduct's own included — **cites** it rather than restating it.
  2. **Hoist-at-install is one-shot.** Products onboarded at different plugin versions get different defaults, and neither re-hoists. That is *correct* for defaults (once adopted they are the product's to own), but it means a **bad** default can never be fixed retroactively — only re-offered via `doctor`. Design that re-offer path in deliberately, rather than discovering it after the first bad default ships. (owner ruling — 2026-07-27)

- **[MET-6Q3D]** Correctness must never depend on a user-invoked command — audit every remedy that routes through `/prawduct:doctor`, and write the always-run-surfaces rule down where the next mechanism's author will hit it
  `effort: S · impact: M · area: methodology · kind: task · source: user · added: 2026-07-27 · reviewed: 2026-07-27 · status: open · stage: ready · related: MET-8K4R, GOV-9K2T · refs: plugin/bin/prawduct-hook:3063 (the live instance — coverage-status' norm-ratification fix line), plugin/docs/norms.md:354-377 (§ Adoption — "binding force comes from the owner having declared a direction; ratification records it, never creates it"; "Day one, automatically"), plugin/docs/norms.md:288 (§ Enforcement — who checks what, when; candidate home for the rule), plugin/docs/doctor-vs-janitor.md (the other candidate home — already describes who checks what and when), plugin/skills/doctor/SKILL.md`

  **Owner ruling — 2026-07-27.** `/prawduct:doctor` is a **repair path, not a workflow step**: it is what people run when something is obviously broken, and it is not part of the normal loop. Therefore any mechanism whose **absence** produces a wrong answer must live on a surface that runs **unconditionally**; user-invoked commands may only **REPAIR** or **REPORT**.

  **The always-run surfaces are exactly:** SessionStart (banner, digest, `clear --session-start`, `build-index`), UserPromptSubmit, Stop, SubagentStop. Everything else is opt-in.

  **Live instance, not hypothetical.** `prawduct-hook coverage-status` emits `fix = "ratify the product's norms via /prawduct:doctor"` (`plugin/bin/prawduct-hook:3063`), so the norm-ratification remedy is routed through a command nobody runs.

  **Why this is an audit rather than a bug.** Whether that routing is acceptable turns on a distinction worth making explicit rather than assuming — and the answer looks like **yes**. `docs/norms.md` § Adoption states that binding is automatic ("Day one, automatically: reviewers apply the normative/descriptive test to unmarked prose… the amend tell needs no markers at all") and that ratification exists for **lifecycle and visibility**, not for binding force. So the shipped design already keeps doctor out of the correctness path; the advisory's remedy line is about making an *already-binding* norm visible, and the wording may simply need to say so.

  **The work.**
  1. **Audit** every surface that names `/prawduct:doctor` as a remedy and classify each as *correctness-critical* or *visibility-only*.
  2. **Reword** any that read as correctness-critical, so the consequence of never running doctor is stated honestly.
  3. **Write the rule down** where the NEXT mechanism's author will hit it — the natural home is `docs/norms.md` § Enforcement or the doctor-vs-janitor split doc, since both already describe who checks what and when.

  **Why file this rather than capture it as a learning.** It has a concrete near-term consumer. The constitutional-vs-default work (**MET-8K4R**) proposed hoisting suggested defaults into a product's preferences via doctor's ratification flow; the owner's objection is what killed that shape, and the rule needs to be written down before it is re-proposed. A learning would not be read at the moment someone designs the next hoist. (user — owner ruling)

- **[COV-3M8Q]** Doc-only fast-path can't see a provably behavior-preserving code change (docstring/comment-only .py) — keys on .md extension alone
  `effort: M · impact: M · area: governance/gates · kind: question · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: research · related: COV-2P7F, COV-4H7N, COV-6T3P, PR-5K8D · refs: plugin/lib/coverage_algebra.py:59-72 (is_judgeable_path — the extension/prefix-only classifier and its do-not-reintroduce docstring), plugin/lib/coverage.py (cmd_check_pr_doc_only), .prawduct/learnings.md (#258 — separate the rejected direction from the rejected primitive; #91 — language-agnosticism)`

  **Observed live 2026-07-21** on `feature/backlog-service-relayout`. A branch whose entire delta was (a) a markdown reorder and (b) a docstring-only edit to a `.py` file demanded a fresh full review cycle: `check-pr-doc-only` classified it not-doc-only, and the cumulative Critic gate exited 1 / uncovered. The `.py` change was *proven* — not asserted — behavior-preserving: the file's AST is identical before and after once docstrings are stripped. So the review cycle was spent on a delta with a mechanical proof that no behavior moved.

  The gap: `is_judgeable_path` (`plugin/lib/coverage_algebra.py:59-72`) classifies on **extension and prefix only** — metadata prefixes are exempt, `.md` is exempt unless governance-protected, and *everything else is judgeable unconditionally*. There is no notion of a code change that is provably inert. `check-pr-doc-only` inherits this.

  **This runs straight into a deliberate design constraint, which is why the stage is `research`, not `ready`.** That same docstring says: "Deliberately no size or content inspection: paths classify, contents don't (do-not-reintroduce: content-hash freshness)." Content-hashing was rejected twice (v1.3.8 fingerprint, v2.1.8 `git_sha`). Learning #258 gives the test for re-proposing: separate the rejected *direction* from the rejected *primitive*. Here both legs are live questions:

  1. **Primitive** — an AST-equivalence proof is content inspection, exactly what the ban names. But it is not a *hash*: it is a semantic equivalence check with a well-defined meaning, and its failure mode is the opposite of a hash's (a hash false-STALEs on churn; this can only false-*pass*). Whether the ban covers it needs an explicit ruling, not an assumption.
  2. **Direction** — the safe-direction-only property that unblocked tree-anchoring does NOT transfer. Tree-anchoring could only move stale→current. This moves judgeable→non-judgeable, i.e. it *removes* review coverage. A bug in the equivalence check ships unreviewed code. That is the unsafe direction, so it needs a stronger correctness argument than the tree-anchoring precedent did.

  Two further constraints any design must answer:
  - **Language-agnosticism** (learning #91): AST-strip-and-compare is Python-only. A carveout that works solely for `.py` re-creates the ecosystem-gating problem `--from-counts` was built to fix. Either the primitive generalizes (comment/docstring-token stripping per language, opt-in per repo) or the carveout is explicitly scoped and that scope is documented as a known limit.
  - **Non-hermetic tests** (COV-4H7N): the standing counterexample to "this file can't change outcomes". A docstring is a weaker case than `.prawduct/` state — a test would have to assert on `__doc__` — but the class is the same and must be ruled on, not waved past.

  **Relationship to the existing family** — this is a *different axis*, not a duplicate. COV-2P7F / the `.prawduct/`-umbrella item / PR-5K8D all argue about which *paths* belong on which side of a path-based classifier. This one asks whether a *content-level proof* may ever override a path classification at all. Answering "no, deliberately" is a legitimate and cheap outcome — and if so, record the rationale in `is_judgeable_path`'s docstring so the next person hitting the treadmill finds the decision instead of re-deriving it.

  Governance-protected (`plugin/lib/coverage_algebra.py`, gates) → full Critic + PR review if it ever leaves `research`. (user — observed live)

- **[BLD-6P8T]** Nothing verifies that intra-repo path references RESOLVE — the packaging test pins where files may LIVE and is blind to references pointing at paths that no longer exist
  `effort: M · impact: L · area: governance · kind: feature · source: reflection · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: DOC-2R7M, GOV-4H7T, GOV-3P8K, JNT-4R2M, GOV-6J3P, ONB-3F9P, BKL-8V3D · refs: tests/test_plugin_packaging.py:182 (`NOT_DISTRIBUTED_DIRS` — the location-only guard this complements), .prawduct/learnings.md:216 ("Relocating a source file: sweep every READER of the old path" — recurrence 3 at :220 names this item), plugin/skills/backlog/SKILL.md (an `allowed-tools:` grant that broke), f62cae1 (the five-skill fix), DOC-2R7M (the durable-artifact half of the same sweep)`

  **Structural enforcement earned by a third recurrence, filed from reflection.** Nothing in the suite verifies that intra-repo path references *resolve*. `tests/test_plugin_packaging.py` pins where files may **live** (`NOT_DISTRIBUTED_DIRS`) and is blind to references pointing at paths that no longer exist. The `plugin/` relocation therefore shipped `bin/prawduct-hook` in five skills' instruction prose **and** in their `allowed-tools:` permission grants; the full suite was green throughout, because no test executes skill front-matter. The Critic caught it as BLOCKING.

  This is the **third occurrence** of the confirmed learning at `.prawduct/learnings.md:216` ("Relocating a source file: sweep every READER of the old path"), which per `methodology/reflection.md` Learning Lifecycle promotes it from a rule to structural enforcement.

  **Proposed shape, to be confirmed at design.** A test that extracts repo-relative path-shaped tokens from the surfaces that fail silently — `allowed-tools:` grants in `plugin/skills/**/*.md` front-matter, fenced/inline commands in skill and methodology prose, and `.prawduct/artifacts/**.md` — and asserts each resolves against the tree, with a **named-exception allowlist** for intentionally-absent paths: a path a skill tells the USER to create; product-side paths like `.prawduct/backlog.md` that exist only in a consuming repo; and illustrative examples. The allowlist must be small and reasoned or the test becomes ceremony.

  **Named risk:** a naive implementation will drown in false positives from prose that mentions paths illustratively. Scoping the extraction to **command position and front-matter** is what makes it high-signal — `docs/norms.md` Deliberate Non-Design warns that a probe which misfires trains its reader to ignore the one real catch.

  Sibling: **DOC-2R7M** is the durable-artifact half of the same sweep (the stale references this test would have caught in `.prawduct/artifacts/**`). (reflection)

- **[BKL-7Q4M]** Safe upstream filing — a private consuming repo must be able to file a prawduct bug into prawduct's PUBLIC repo without leaking its own content; the missing design is CONTENT MINIMIZATION, not auth
  `effort: L · impact: L · area: backlog-service · kind: feature · source: user · added: 2026-07-21 · reviewed: 2026-07-23 · status: open · stage: ready · related: BKL-9XQ2, BKL-0QR1, BKL-2Q7F, BKL-8V3D, BKL-5N9W, BKL-6M4T, ONB-3F9P, MET-6T4K · refs: .prawduct/artifacts/security-model.md (§ Direction — the norm this item tracks), tests/preferences/test_no_upstream_content_egress.py (the interim enforcement mechanism), documentation/backlog-service-security-model.md (§1 auth by target owner, §4 cross-owner cache scoping, §5 XP2 untrusted-until-triaged, §6 PV3/PV4 abuse prevention), .prawduct/artifacts/build-plan-backlog-service.md:687 (W3 roadmap row — `file-upstream`, XP1/XP2 public/foreign identity plane), plugin/skills/report-bug/SKILL.md, plugin/lib/backlog/transport.py:34-58 (`scrub_secrets` — the existing denylist redaction precedent), documentation/backlog-service-requirements.md (Upstream bug reporting — XP4–XP7, the settled content-minimization requirements), documentation/backlog-service-upstream-filing.md (the complete, owner-approved design — the buildable spec)`

  **RELEASE BLOCKER for 3.2.0 — stated by the owner 2026-07-21.**

  **This is the tracking item for a live norm exception.** `.prawduct/artifacts/security-model.md` § Direction carries the norm *"A governed product's content never leaves that product's own repository and owner. The backlog adapter reaches exactly the repo named in `backlog_service_repo`; the upstream bug channel is filesystem-local. Any cross-owner or public-plane filing surface is an owner decision, never an increment."* That norm moves from `Status: steady-state` to **`Status: in-transition`** and cites **BKL-7Q4M** literally as its tracking item. The capability described here is *blocked by that norm today* and is unbuilt; the norm's interim enforcement — `tests/preferences/test_no_upstream_content_egress.py`, which fails if a `file-upstream` surface appears anywhere in the plugin or if prawduct's own tracker reaches the backlog adapter — stays live until this item's requirements are settled and a design deliberately supersedes it.

  **`stage: ready` as of 2026-07-23 — the design is complete and owner-approved, so this is now buildable.** This was a security design before it was code (Principle 6): requirements settled as the content-minimization / upstream-filing requirements **XP4–XP7** in `documentation/backlog-service-requirements.md`, and the design that settles the outbound-payload shape against them is now written and signed off in `documentation/backlog-service-upstream-filing.md`. Route it into implementation via the normal build cycle (`/prawduct:methodology building`), designing against that doc rather than a re-drafted model.

  **The design surface that already exists — reconcile with it, do not re-invent it.** `documentation/backlog-service-security-model.md` already covers the public-submission plane: **§1** (auth by target owner), **§5** (XP2 — arriving reports are *untrusted until triaged*, enforced by GitHub's non-collaborator permissions), **§6** (PV3/PV4 abuse prevention), **§4** (cross-owner cache scoping). `.prawduct/artifacts/build-plan-backlog-service.md:687` sizes the capability as roadmap wave **W3** (`file-upstream`, XP1/XP2 public/foreign identity plane). Any requirements pass starts by reading those, not by drafting a parallel model.

  **What that existing design does NOT appear to cover — and what the owner's concern is actually about — is CONTENT MINIMIZATION rather than auth.** The written surface answers *who may file where* and *how much to trust what arrives*. The owner's question is the orthogonal one: **exactly which fields cross the boundary**, how repo paths / code excerpts / learnings prose / product names get redacted or omitted, and whether the owner **sees and approves the verbatim outbound payload** before it is sent. Auth being correct does not make the payload minimal.

  **The questions settled during requirements (XP4–XP7) — now the inputs the design answers to:**
  1. **Minimum field set** — what is the smallest set of fields a *useful* upstream report needs? (A report the maintainer cannot act on is not a win for having leaked less.)
  2. **Redaction strategy** — **allowlist** the fields that may cross vs. **denylist** patterns that may not. Note the existing precedent is a *denylist*: `scrub_secrets` (`plugin/lib/backlog/transport.py:34-58`) is a regex denylist backstop for credentials in `gh` output. Whether that shape generalizes to *repo content* (where the sensitive material is arbitrary prose and paths, not a token with a recognizable form) is precisely the open question — an allowlist is the structurally safer default and should have to be argued *out of*, not *into*.
  3. **Owner preview-and-consent** — is preview-and-consent **mandatory per report**? Is the shape a dry-run/`--apply` pair, consistent with the standing norm *"No destructive action without an explicit `--apply` step"*? (Cross-check BKL-8V3D: `adapter-mode.md` already *claims* an `--apply`/dry-run contract that `lib/backlog/` does not implement — do not design against a contract that does not exist yet.)
  4. **Filer identity** — anonymous vs. authenticated. Interacts with BKL-9XQ2's refinement: the adapter **inherits the session's GitHub auth** (PRD O5), so an authenticated filing is attributed to the user personally, permanently, in someone else's public project. Anonymity trades that away for the abuse surface §6/PV3 exists to handle (PV3 is itself gated on MET-6T4K).
  5. **Relation to the filesystem-local `incoming-bugs/` drop-box** — the safe path that *works today* whenever a local prawduct checkout is reachable. What does this capability replace, what does it complement, and what remains the fallback when no checkout is reachable? MG5 ties drop-box retirement to a live upstream path (BKL-0QR1), so this question is a sequencing dependency, not a footnote.

  **Relationship to BKL-9XQ2 — deliberately separate, cross-linked, not merged.** BKL-9XQ2 (`stage: ready`) is the broad "upstream filing is critically underspecified" item: consent-at-install (1a), consent-at-file (1b), agency/attribution, the adapter-vs-prose binding site, label taxonomy. **This item is narrower and downstream of it:** it is specifically the *content-minimization / outbound-payload* leg, and it is the item the § Direction norm cites. If a requirements pass ends up folding the two, do it explicitly via `dedup` — do not let either quietly absorb the other, because the norm's citation must keep resolving. (user — owner, 3.2.0 release blocker)

- **[BKL-3N8Q]** Relationship/timeline foreign-API shapes are fake-verified only — `list_blocked_by` fails silently, so `pick` reports a blocked item as ready with a confident "no open blockers"
  `effort: M · impact: L · area: backlog-service · kind: bug · source: critic · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: BKL-9J3F, BKL-2K8V, BKL-6M4T, BKL-4H8P, BKL-6X5D · refs: lib/backlog/transport.py:166/217/222 (protocol) and :334/459/476 (the `gh` implementations of `list_blocked_by` / `list_sub_issues` / `list_timeline`), lib/backlog/query.py:180 (`blockers = transport.list_blocked_by(...)`), lib/backlog/query.py:368-369 (the "no open blockers" readiness string), tests/fakes/fake_github.py:52-59 (`blocked_by` / `sub_issues` / `timeline` — the only shapes these three are checked against), .prawduct/artifacts/build-plan-backlog-service.md (the unrun `verify-api` step / L5 smoke set), .prawduct/project-state.yaml `design_decisions.infrastructure_dependencies.integration_test_strategy` (cites THIS id), documentation/backlog-service-api-contract.md`

  **Stable id — do not renumber.** `.prawduct/project-state.yaml` records this item by id inside
  `design_decisions.infrastructure_dependencies.integration_test_strategy` ("tracked as BKL-3N8Q").
  A dedup merge or migrate that changes the id dangles that reference; if this item is ever
  superseded, update the design decision in the same commit.

  Filed by the backlog-service relayout Critic review (rev-20260721T161120Z-c06da7f6).

  Three foreign-API surfaces — `list_blocked_by`, `list_sub_issues`, `list_timeline` in
  `lib/backlog/transport.py` — are exercised **only** against `tests/fakes/fake_github.py`. The
  offline suite therefore proves the adapter agrees with *our model of* GitHub's relationship and
  timeline payloads, not with GitHub. The build plan's `verify-api` step (the one that would check
  the real shapes) has not been run; it is queued in the L5 smoke set and deferred by owner decision
  to an owner-run session. So the fake is currently the *only* oracle for all three.

  **The `blocked_by` leg is the dangerous one because it fails silently.** `query.pick` reads
  blockers via `transport.list_blocked_by` (`query.py:180`) and, finding none, emits a readiness
  verdict that literally asserts `"no open blockers"` (`query.py:368-369`). A shape mismatch — a
  renamed field, a moved nesting level, a paginated envelope the parser doesn't unwrap — yields
  `[]`, which is indistinguishable from *genuinely unblocked*. The failure mode is not an error the
  operator sees; it is `pick` confidently handing the agent a **blocked** item and stating, as fact,
  that nothing blocks it. That is the one output class where a silent empty is worse than a raise:
  the framework's own requirements-precede-code routing runs off it.

  `list_sub_issues` and `list_timeline` share the fake-only exposure but degrade visibly (a missing
  child or a thin audit trail), so they rank below the blocker path.

  Fix-shape (not yet designed): (a) run `verify-api` against a live repo and pin the observed shapes;
  (b) make the three decoders **distinguish "no rows" from "did not understand the payload"** —
  an unrecognized envelope must raise or return an explicit unknown, never `[]`; (c) have `pick`
  refuse to assert "no open blockers" on an unknown-blocker result, degrading to an
  unknown-blocker-state readiness string instead. (b) is the load-bearing half: it converts a silent
  wrong answer into a loud one, and it is worth doing even before the live verification lands.

- **[BKL-4C9P]** `migration-scrub.md` step 5 says cutover retires a "backlog trio" — it is a quartet, and the omitted probe is the one that sent the operator to that runbook
  `effort: S · impact: M · area: backlog-service · kind: bug · source: critic · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: BKL-6J2X, BKL-2Q7F, BKL-8V3D, BKL-8W2M, BKL-6M4T · refs: skills/backlog/migration-scrub.md:203-204 (step 5 — "the backlog trio `legacy-backlog-format` / `legacy-section-schema` / `backlog-overdue-grooming`"), lib/backlog_probes.py:240 (`probe_migration_required`) and :262 (its `post_cutover(state)` early return), lib/backlog_probes.py:367-376 (`register` — six probes), documentation/post-sync-advisory-spec.md:366-375 ("the four markdown probes above", naming `backlog-service-migration-required`), documentation/backlog-service-api-contract.md:113-118 (§2.4 — "the seven markdown-premise advisory probes retire on the same switch — the backlog quartet")`

  Filed by the backlog-service relayout Critic review (rev-20260721T161120Z-c06da7f6).

  `skills/backlog/migration-scrub.md:203-204` tells the operator that setting `backlog_service_repo`
  retires "the backlog **trio** `legacy-backlog-format` / `legacy-section-schema` /
  `backlog-overdue-grooming` AND the norm trio". Both governing specs say otherwise, and they agree
  with each other and with the code:

  - `documentation/backlog-service-api-contract.md:113` (§2.4) — "the **seven** markdown-premise
    advisory probes retire on the same switch — the backlog **quartet** (`legacy-backlog-format`,
    `backlog-service-migration-required`, `legacy-section-schema`, `backlog-overdue-grooming`)".
  - `documentation/post-sync-advisory-spec.md:366-375` (§8.2) — "the **four** markdown probes above",
    naming `backlog-service-migration-required` among them.
  - `lib/backlog_probes.py:262` — `probe_migration_required` early-returns on
    `post_cutover(state)`, i.e. it is in fact guarded by the same switch.

  So the runbook is the only surface with the wrong count, and the probe it drops is
  `backlog-service-migration-required` — **the advisory whose `recommended_action` is what routed the
  operator into this runbook in the first place** (`migration-scrub.md:9-14` states that coupling
  from the other side). An operator reading step 5 is left unable to answer the obvious question
  "does the nudge that sent me here stop after I finish?" — and the natural wrong inference is that
  it keeps firing forever, which invites a second, unnecessary scrub run.

  Fix: correct step 5 to "backlog quartet", name the fourth probe explicitly, and state that the
  migration-required advisory is self-clearing at cutover. Doc-only; no code change. Worth a
  coherence check on any other prose surface that counts these probes while the fix is in hand.

- **[GOV-5R8T]** Concerns-registry row "Backend declaration before a governance read" cites Discovery and Builder coverage that no methodology file has ever carried
  `effort: S · impact: M · area: governance · kind: bug · source: critic · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: BLD-4Q8W, GOV-4H7T, BKL-3W6K · refs: .prawduct/cross-cutting-concerns.md:42 (the "Backend declaration before a governance read" row — the Discovery cell and the Builder cell), methodology/discovery.md (no such text), methodology/building.md (no such text; `git log -S` finds no commit that ever added it), skills/critic/review-protocol.md (Goal 1/4 — the row's claimed Critic coverage), documentation/backlog-service-api-contract.md §2.4 (`backlog_service_repo`), .prawduct/artifacts/build-plan-backlog-service.md`

  Filed by the backlog-service relayout Critic review (rev-20260721T161120Z-c06da7f6).

  `.prawduct/cross-cutting-concerns.md:42` claims pipeline coverage for this concern at two stages:
  a **Discovery** cell ("which store is system of record is a structural fact recorded in
  `project-state.yaml` (`backlog_service_repo`), not inferred per reader", attributed to
  `discovery.md`) and a **Builder** cell ("a reader declares the backend it read before it reports;
  **repoint** a reader that consumes the item view as-is, declare **dormant** one that derives a
  verdict from it", attributed to `building.md`). Neither file contains that text, and
  `git log -S` over the phrasing finds **no commit that ever added it** — this is not drift from a
  deleted rule, it is coverage that was recorded without ever being written.

  Why it matters more than a stale cell: the registry is the artifact a reviewer consults to decide
  whether a concern is *already handled upstream*. A row asserting Discovery + Builder coverage
  reads as "two stages catch this before it reaches me", so the one stage that genuinely could
  catch it (Critic judgment) is the only real coverage while the matrix reports three. The row's own
  ⚠️ note already flags that every *enforcement* surface it names is absent from `main` at v3.1.1;
  the methodology cells are a separate and older defect, since those surfaces at least exist on the
  feature branch.

  **Recurrence, not a one-off.** BLD-4Q8W is the identical failure on row :36 (the Build-plan
  ref-drift row claimed `building.md` instructs builders to run `verify-chunk-refs`; `methodology/`
  mentions it nowhere). Two rows, same mechanism: a registry cell asserting methodology coverage
  that was never authored. Fix-shape should therefore be two-part — (a) correct the row (either write
  the methodology rules or record the absence, matching how :36 was resolved), and (b) sweep the
  remaining rows for methodology-attributed cells whose text does not exist in the cited file, since
  a hand-maintained matrix has no mechanism that would have caught either instance.

- **[BKL-8W2M]** No declared terminal-markdown state — `backlog-service-migration-required` warns forever in products that will never host on GitHub
  `effort: M · impact: M · area: backlog-service · kind: feature · source: critic · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: requirements · related: BKL-6J2X, BKL-4C9P, BKL-3W6K, BKL-2Q7F · refs: lib/backlog_probes.py:240-262 (`probe_migration_required` — resolution is `post_cutover` only), lib/backlog_probes.py:370-372 (unconditional registration), lib/backlog_probes.py:106 (`post_cutover` — the single shared resolution predicate), skills/backlog/migration-scrub.md (the `recommended_action` target — requires `gh` and a GitHub owner/repo), documentation/backlog-service-requirements.md (GV7), documentation/post-sync-advisory-spec.md §8.2 (probe resolution conditions)`

  Filed by the backlog-service relayout Critic review (rev-20260721T161120Z-c06da7f6).

  `probe_migration_required` registers unconditionally (`backlog_probes.py:370-372`) and its **only**
  resolution condition is `post_cutover(state)` — i.e. `backlog_service_repo` being set. There is no
  third state. A product that is deliberately staying on the markdown backlog forever — no GitHub
  remote, self-hosted git, an air-gapped or non-GitHub forge, or simply a small product whose owner
  does not want an Issues tracker — has **no way to resolve the advisory**, because the only exit is
  migrating to the thing it will never adopt. It gets a `warn`-priority nudge at every session start,
  in perpetuity, recommending `/prawduct:backlog scrub`, a runbook that requires `gh` and a GitHub
  `owner/repo` it does not have.

  This is distinct from BKL-6J2X, which holds the same advisory out of v3.2.0 because the migration
  path is *unproven*. That is a release-timing hold on a path that will eventually be right for those
  repos. **This** item is the permanent case: repos for which the path will never be right, and for
  which "hold the advisory" is not a fix because the advisory returns the moment the hold lifts. Both
  need answering; only one is release-gating.

  `stage: requirements` is deliberate — the fix is a **product decision** before it is code. The open
  questions: is terminal-markdown a first-class supported state or an unsupported edge? If
  first-class, how is it declared (an explicit `backlog_backend: markdown` scalar, a
  `backlog_service_repo: none` sentinel, a dismissal that survives, or inference from the absence of
  a GitHub remote)? Does declaring it also silence the rest of the migration-shaped surface, or only
  this probe? And does the same declaration mean anything to `backlog-checks-dormant`, which exists
  precisely to name checks with no Issues-backend path? Note that plain advisory *dismissal* is
  probably not the answer — a permanent architectural fact deserves a recorded, shared, committed
  state, not a per-user dismissal that every fresh clone re-nags about.

- **[DOC-7K4V]** `artifacts/api-contract.md` never describes the `prawduct-hook backlog` surface, though the build plan declares it an Exposed API
  `effort: S · impact: M · area: docs · kind: debt · source: critic · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: CRT-4Q7K, TPL-8H3M, BKL-9XQ2, BKL-2D8N · refs: .prawduct/artifacts/api-contract.md (zero mentions of `backlog` — the gap), .prawduct/artifacts/build-plan-backlog-service.md (the `**Exposed API:**` declaration), lib/backlog/cli.py:33 (the op set), skills/backlog/adapter-mode.md (the error-envelope + exit-class contract the model reads instead), documentation/backlog-service-api-contract.md (the feature-local contract that exists but is not the product's api-contract artifact)`

  Filed by the backlog-service relayout Critic review (rev-20260721T161120Z-c06da7f6).

  The backlog-service build plan declares `prawduct-hook backlog` an **Exposed API** — the marker
  whose whole purpose is to route the chunk through the versioning / error-model review. The
  product's own API contract artifact, `.prawduct/artifacts/api-contract.md`, does not mention the
  surface at all: not the op set, not the envelope, not the exit classes, not the compatibility
  promise.

  The surface is not *undocumented* — `documentation/backlog-service-api-contract.md` and
  `skills/backlog/adapter-mode.md` both describe it in detail. The defect is that the artifact a
  reader is told is the product's API source of truth omits an API the product exposes, so the two
  disagree by omission and there is no pointer between them. A consumer (or a future Critic run)
  reading `api-contract.md` to answer "what does prawduct expose, and under what compatibility
  promise?" gets a confidently incomplete answer.

  Cheapest sufficient fix is probably not a full re-authoring: add a section to `api-contract.md`
  covering the `prawduct-hook backlog` surface at the level the artifact uses for its other entries,
  with the versioning/error-model statements stated there and the operational detail **referenced**
  into `documentation/backlog-service-api-contract.md` rather than duplicated (duplication here is a
  second drift source, cf. BKL-2D8N). Worth checking in the same pass whether any *other*
  `**Exposed API:**` declaration in a shipped chunk is likewise missing from the artifact — the gap
  suggests nothing links the declaration to the artifact.

- **[CRT-6R3W]** Critic should sweep by the RULE that generates a pattern, not by the instances it happened to see — instance-enumeration still misses sites the rule catches
  `effort: M · impact: L · area: critic · kind: feature · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: research · related: CRT-4X2N, TST-9M4X, CRT-8Q6R, CRT-5M9J · refs: skills/critic/review-protocol.md (finding content / Output Format), skills/critic/SKILL.md, .prawduct/learnings.md ("verify at the quantifier" — CRT-8Q6R Correction 4)`

  Relayed by the user 2026-07-21 from an agent using prawduct in another repo. **Capture, not a design** — `stage: research` is deliberate; route through discovery before any implementation.

  **Relayed verbatim from the reporting agent** (the self-diagnosis is the valuable part — preserve it):

  > That last verify pass caught three problems in the commit whose own message said "generalise the fix":
  >
  > - The %r sweep I described as complete was short by four sites — including the two success-path log lines one line below the ones I fixed.
  > - My surrogate test was vacuous. It asserted only the 401, which %s also returns, because logging.Handler.emit swallows the encode error. The only revert signal was an xdist crash attributable to no test.
  > - My null parametrize case never reached the guard — httpx sends an empty body for json=None, so it passed via the JSON-decode path instead.
  >
  > That's four rounds now where I declared a sweep done and the sweep wasn't. The pattern is consistent enough to name plainly: I keep fixing the instances a reviewer hands me instead of the rule that generates them. This round I applied the rule — anything carrying request-body, path, or external-API text logs with %r — which caught two more sites (mcp_token.py, entities.py) that no review had named.

  **Why this is strictly stronger than [CRT-4X2N], and must not be deduped into it.** CRT-4X2N says the reviewer should grep tree-wide and enumerate every INSTANCE of a pattern. This report shows that is still not enough. The agent applied an instance sweep and was short by four sites, including two success-path log lines ONE LINE BELOW the ones it had just fixed — proximity that no reasonable "did you check nearby" heuristic would have missed, yet an instance-shaped search did. What finally converged was articulating the **generating rule** ("anything carrying request-body, path, or external-API text logs with %r") and sweeping by that rule, which surfaced two files no review round had ever named.

  The distinction to design against: an *instance* is a string you can grep; a *rule* is a predicate over code that names the class. Grepping the string finds textual matches of what you already saw. Applying the predicate finds sites that instantiate the class in forms you had not seen — which is exactly where the residue lives.

  **Actor question, which is the open design issue.** CRT-4X2N argued the reviewer is the right actor because the reviewer holds the pattern. This report complicates that: the reporting agent was the FIXER, and it was the fixer who eventually derived the rule, after four rounds. So the candidates are (a) reviewer states the generating rule in the finding, not just the sites; (b) fixer is required to state the rule before claiming a sweep complete; (c) both, with the reviewer's rule as a hypothesis the fixer must confirm or widen. Do not pick this by inference — it wants a real design pass. Note the failure recurred FOUR times under existing guidance, which is evidence that adding prose to one actor's protocol is the intervention most likely to fail again.

  **Cost signal.** Four rounds on one defect class, and per CRT-4X2N each fix commit reopens the cumulative-Critic coverage gap and forces another delta review — so rule-vs-instance is a direct multiplier on review cost, not a quality nicety.

  Sibling item from the same report, covering the test-discrimination half: **[TST-9M4X]**. (user — relayed external agent feedback)

- **[TST-9M4X]** Nothing verifies that a regression test actually discriminates — a test can pass identically on fixed and unfixed code, or never reach the guard it claims to cover
  `effort: M · impact: L · area: tests · kind: feature · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: research · related: CRT-6R3W, CRT-4X2N, COV-4M2J, CRT-5M9J · refs: methodology/building.md (Verify — acceptance criteria / test evidence), skills/critic/review-protocol.md (review goals), bin/prawduct-hook (test-evidence record), lib/gates.py (test-evidence freshness), bin/test-reference-verify (the coverage floor that counts a test as covering a change)`

  Relayed by the user 2026-07-21 from an agent using prawduct in another repo — same source report as **[CRT-6R3W]**, distinct defect class. **Capture, not a design** — `stage: research` is deliberate.

  Two of the three problems in the report behind CRT-6R3W are not about sweeps at all — they are about tests that looked like coverage and were not:

  1. **Vacuous assertion.** "My surrogate test was vacuous. It asserted only the 401, which %s also returns, because logging.Handler.emit swallows the encode error. The only revert signal was an xdist crash attributable to no test." The test passed on the FIXED code and would have passed on the UNFIXED code — it could not distinguish them. Root cause is domain-specific (`logging.Handler.emit` swallows the encode error, so the observable outcome is identical either way), but the class is general.

  2. **Test never reached the code under test.** "My null parametrize case never reached the guard — httpx sends an empty body for json=None, so it passed via the JSON-decode path instead." A green parametrize case that exercised a different branch entirely, and reported success.

  **The class:** a test whose pass/fail carries no information about the property it claims to pin. Both instances were GREEN. Neither the test suite, the test-evidence machinery, nor the Critic surfaced either one — they were caught only by the agent's own later verify pass, and one of them was caught by a *crash* rather than a signal.

  **Why prawduct should care.** Principle 1 says tests are contracts. A vacuous test is a contract that binds nothing while reporting that it does — and it is worse than no test, because it consumes the coverage slot and terminates the search. Test evidence that counts a vacuous test as coverage is confidently wrong in the framework's own defined sense.

  **Candidate directions (NOT a design — the point of `stage: research`).** (a) Require a regression test to be shown failing against the pre-fix state before it counts as evidence — the red-then-green discipline, made checkable rather than assumed. (b) A Critic review goal that asks of each new test "would this fail on the unfixed code, and does it reach the guarded path?" (c) Mutation-style spot checks on the specific guard a fix introduces. Each has real cost and (a) interacts with how test evidence is currently captured, so this wants a proper look at what is affordable — see Principle 11, proportional effort. Do not build against this item without a discovery pass first.

  Same shape as [CRT-5M9J] one layer down: that item asks "does this capability trace to a requirement and is it reachable end-to-end?"; this asks the same reachability question of the *test* that vouches for it. (user — relayed external agent feedback)

- **[VWS-4T9P]** regen-views plan-discovery globs `artifacts/` NON-RECURSIVELY (two sites), so repos that organize build plans in subdirectories fail closed forever — and one sibling parser silently no-ops on a plausible authoring variant
  `effort: M · impact: L · area: views · kind: bug · source: report-bug · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: VWS-2W6H, VWS-2F9K, TST-6K3D, BLD-5J8N, VWS-7N3K · refs: lib/views.py:549 AND lib/views.py:614 (both `sorted(artifacts_dir.glob("*.md"))` — non-recursive; the upstream report named only :549, there are TWO sites), lib/views.py:532 (build_scope_to_plan_map), lib/views.py:649 (scope→plan diagnostic, fatal for the whole run), lib/views.py:49 (CHUNK_LINE_RE), lib/buildplan_refs.py:291 (_chunk_section_lines — NOTE: report said :251; the function is at :291), lib/critic_mode.py (the `**Critic mode:**` reader that folds onto the same walk), bin/prawduct-hook (cmd_regen_views fatal-diagnostics block), incoming-bugs/regen-views-cannot-see-build-plans-in-subdirectories.md`

  Upstream report from the **hallucinote** product against prawduct v3.1.0 (filed 2026-07-20). Primary defect re-verified live on `main` 2026-07-21.

  **Primary defect (live).** `build_scope_to_plan_map` iterates `sorted(artifacts_dir.glob("*.md"))` — non-recursive, directory not configurable. A repo that organizes plans as `.prawduct/artifacts/plans/<id>/build-plan.md` is invisible to it. **There are two such glob sites, not one** (`lib/views.py:549` and `lib/views.py:614`) — confirmed by reading the tree; the upstream report named only the first, so a fix that patches one site leaves the other. The scope→plan diagnostic then appends a validation error for any release-pending scope absent from the map, and the caller treats validation errors as fatal for the WHOLE run — so release-notes and scope-rollup regeneration, which have no dependency on the plan roster, are skipped too. All-or-nothing.

  The failure is silent in effect: the error names a scope tag, so it reads as "you tagged the change-log wrong," not "your plans are in a directory I don't scan." In the reporting repo (48 plans under `plans/<id>/`) `release-notes.md` was missing SIX whole version sections and `scope_rollups` had 34 keys instead of 62 — drift accumulated with no signal at any point. On a branch with no scope-tagged entry, `regen-views --check` reports "up to date," so the drift stays invisible until one appears.

  **Contributing factor worth checking across onboarded repos:** the reporting repo had `.prawduct/artifacts/build-plan.md` GITIGNORED until `prawduct-hook update-gitignore` un-ignored it. Plans plausibly drifted into `plans/` *because* the canonical path was ignored — so repos onboarded before that contract change may all be in this state.

  **Parser-variant sub-claims — one live, one already fixed (verified on `main` 2026-07-21, do not re-fix blind).**
  (a) LIVE: `CHUNK_LINE_RE` (`lib/views.py:49`) pins `\s+Chunk\s+(?P<id>[A-Za-z0-9_-]+):` — requires the colon, no tolerance for surrounding `**` or an em-dash — so `- [x] **Chunk A** — …` never matches and those checkboxes can never flip. **Substantially overlaps [VWS-2F9K]**, which already covers the em-dash/colon-less form for this same regex; the genuinely NEW facet here is the **bolded** (`**Chunk A**`) variant. Fix them together — do not fix one and leave the other.
  (b) ALREADY FIXED UPSTREAM OF THIS FILING: the report claims `_chunk_section_lines` matches only `startswith("### Chunk ")` plus a colon. **Not true of current `main`** — `_chunk_section_lines` (`lib/buildplan_refs.py:291`) is the canonical walk and matches via `_CHUNK_HEADING_RE` (`^#{2,3}\s+Chunk\s+(\w+)` + `_CHUNK_ID_SEP = \s*(?:[:—–(-]|$)`), accepting both `##`/`###` and any of `: — – ( -` or end-of-line, with leading-zero tolerance (broadened by BLD-5J8N). So `## Chunk A — …` parses, and the `**Critic mode:**` reader that folds onto this walk is NOT inert. The reporter was presumably on an older tree. Retained here as a negative result so the next person doesn't re-open it. (Sibling test-replica drift on this same matcher is [TST-6K3D].)

  Fix shape: (1) recursive plan discovery (or a configurable plan root) applied to **both** glob sites; (2) decouple view regeneration so one unresolvable scope doesn't block unrelated views — note [VWS-7N3K] already shipped the analogous decoupling for the null-plan abort, so follow that precedent; (3) broaden `CHUNK_LINE_RE` to tolerate the bolded/em-dash authoring variants — or reject them loudly — jointly with VWS-2F9K. The unifying defect is that each check quietly does nothing instead of complaining. Governance-protected code path → full Critic + PR review.

  **Fleet survey, 2026-07-21 (measured, not estimated).** Surveyed all 23 onboarded repos under `/Users/brookstalley/source/`. Structural exposure — build plans below the top level of `.prawduct/artifacts/`, counted via `find … -mindepth 2 -name '*.md' -exec grep -l '^artifact: build-plan'`: `discodon`, `discodon-brooks2`, `discodon-research-sources`, `wt-discodon-backlog` — **16 nested build plans each**; `hallucinote` — **5 nested**, 1 top-level; all other onboarded repos — 0 nested.

  **Nobody is blocked today, but both clear results are clear for contingent reasons — this is latent, not resolved.** `hallucinote`: `regen-views --check` passes ONLY because the single scope-tagged change-log entry resolves to `artifacts/build-plan-highroi-sweep.md`, which they hand-moved to top level as the workaround; five nested plans remain, and the next change-log entry whose scope resolves to one of those five re-blocks them. The discodon family: not blocked ONLY because `views_enabled` is unset in `project-state.yaml`, so `regen-views` no-ops entirely ("Views disabled").

  **THE TRAP — enabling views is currently a landmine for the largest consumer.** discodon carries 16 nested build plans and 47 nested artifact files. The moment `views_enabled: true` is set, `regen-views` fails closed on the whole repo, and — because one unresolvable scope aborts the entire run — release-notes and scope-rollup regeneration die with it, neither of which depends on the plan roster. Anything that flips that flag walks them straight into it: a `/prawduct:doctor` repair, a future advisory recommending views, or a user following the hint in the error message the tool itself prints ("set views_enabled: true in project-state.yaml"). **prawduct's own tooling currently recommends the action that triggers the bug.** That is an argument for fixing this BEFORE any work that encourages view enablement, and for fix-shape step (2) — decouple view regeneration so one unresolvable scope can't block unrelated views — being the load-bearing half rather than a nice-to-have.

  **Distribution note relevant to urgency.** All consumers install via `{"source": "github", "repo": "brookstalley/prawduct", "ref": "main"}` with `autoUpdate: true` — they track the `main` BRANCH, not a tag. A fix merged to `main` reaches every consumer on next update with no version bump required, so this does not need a release to ship; it needs a merge.

  Note vs **[VWS-2W6H]**: RELATED BUT DISTINCT — that item is about design artifacts masquerading as build plans (an `artifact: build-plan` frontmatter filter); this one is about plans being invisible to the glob entirely. Both touch `build_scope_to_plan_map`; fixing either does not fix the other. Cross-linked deliberately, not merged. (report-bug — hallucinote upstream)

- **[CRT-7P5J]** Session handoff reports resolved Critic findings as outstanding — it reads the derived view instead of composing over resolution facts, contradicting the kernel-v3 invariant
  `effort: S · impact: M · area: critic · kind: bug · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: CRT-4X2N, CRT-2Q6D, CRT-6D2N, GOV-9T2K, GOV-4H7T · refs: lib/briefing.py:804 (`_summarize_critic_findings` — reads `.critic-findings.json` raw), lib/briefing.py:886 (the call site in `generate_session_handoff`), lib/briefing.py:518 (the briefing line that surfaces the handoff to the next session), lib/core.py:87 (`.prawduct/.session-handoff.md` in the session-file set), CLAUDE.md ("gates read the evidence store, not this" / "no gate reads the view — gates compose over facts"), `<git-common-dir>/prawduct/evidence.jsonl` (where resolution facts land), tests/test_plugin_packaging.py:218-229 (the resolutions the handoff failed to reflect)`

  **Observed live at the start of this session (2026-07-21).** `.prawduct/.session-handoff.md` reported "0 blocking, 4 warning, 2 note … Changes ready to proceed" and then enumerated three WARNING lines about the plugin-root guard (first-path-segment comparison; working-tree vs tracked "ships" side; R-5's surviving symlink instruction). All three had in fact been **resolved before v3.1.1 shipped** — `tests/test_plugin_packaging.py:218-229` carries the fixes with an explicit `(Critic verify-resolutions, 2026-07-21.)` annotation at exactly the points the warnings named, and the module docstring's symlink text is rationale for why symlinks were REJECTED, not a surviving instruction. The handoff recorded the findings and never recorded their resolutions.

  **Cost, concretely.** This is the first artifact a new session reads (`lib/briefing.py:518` tells it to). The session acted on it, told the user three warnings were unfiled and at risk of being lost, and recommended filing them — a wrong recommendation that took a code-verification round to retract. The failure mode is a fresh session confidently re-opening closed work, which is the exact "confidently wrong context" class the framework exists to prevent.

  **Root cause — verified by reading the source.** `_summarize_critic_findings` (`lib/briefing.py:804`) opens `.critic-findings.json`, pulls `data["findings"]`, buckets by `severity`, and prints every blocking plus the first three warnings. There is **no resolution composition anywhere in the path** — it never consults the evidence store. Under kernel v3 the review fact and the resolution facts are separate appends to `<git-common-dir>/prawduct/evidence.jsonl`, and `.critic-findings.json` is a *derived view of the latest review fact*. So a `verify-resolutions` pass that records resolutions does not change what the handoff prints.

  **Why this is a design violation, not just a missing feature.** CLAUDE.md states the kernel-v3 invariant twice — "gates read the evidence store, not this" and "no gate reads the view — gates compose over facts." The handoff generator is a consumer that reads the derived view instead of composing over facts. It is arguably not a "gate," which is precisely the loophole: the invariant was stated for gates and this consumer sits outside that word while having the same correctness requirement. Worth checking whether OTHER non-gate consumers read `.critic-findings.json` the same way — this is a pattern-shaped defect and should be swept tree-wide, not fixed at the one site (see **[CRT-4X2N]**, same lesson).

  **Fix shape.** Compose resolution facts over the review fact before summarizing: suppress or mark-resolved any finding carrying a resolution, and make the counts reflect the composed state. Secondary: the summary line and the enumerated findings disagreed with each other ("ready to proceed" above three WARNING lines) — whatever the composition does, those two must be derived from the same computation. A regression test should pin the case: review records N warnings → verify-resolutions resolves them → handoff shows zero outstanding. Governance-protected (`lib/`, Critic data plane) → full Critic + PR review. (user — observed live 2026-07-21)

- **[CRT-4X2N]** Pattern-shaped Critic findings report only the first site, multiplying fix→re-review rounds
  `effort: S · impact: M · area: critic · kind: fix · source: report-bug · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: CRT-6R3W, CRT-8Q6R, CRT-5M9J · refs: skills/critic/review-protocol.md (finding content / Output Format), .prawduct/learnings.md ("verify at the quantifier" — CRT-8Q6R Correction 4), incoming-bugs/pattern-shaped-critic-findings-should-enumerate-every-instance-tree-wide.md`

  Upstream report from the **hallucinote** product against prawduct v3.1.0 (filed 2026-07-20).

  When a Critic finding is an instance of a REPEATED pattern — the same claim, term, or value across several files — the reviewer reports the site it happened to be looking at and stops. The fixer corrects that site; the next round finds the same pattern in the next file; repeat. Not a false-positive problem — every round was a legitimate catch. The reviewer holds the pattern and could enumerate it in one pass, but isn't asked to.

  This interacts badly with the cumulative-Critic gate: because coverage must span to HEAD, every fix commit reopens the gap and needs another delta review. Partial enumeration multiplies directly into review rounds. Observed: one 15-commit bundle spent THREE rounds on TWO defects — a false claim surfaced in a SKILL.md then in a module docstring; a wrong release attribution surfaced in change-log tag lines, then change-log prose, then a build plan Status block, then that plan's Verification strategy section (leaving the file half-fixed and self-contradicting in between), then a backlog archive closure note. A single `git grep` per pattern produced the complete list in seconds.

  Root cause (inferred, not traced): `review-protocol.md` asks for findings anchored to a site (`file:line`), right for one-off defects, but says nothing about a finding whose SHAPE is "this claim recurs." Nothing instructs the reviewer to search beyond the file under inspection, so scope follows attention rather than the pattern.

  Key insight worth preserving: the fixer-side discipline already exists as a learning in the reporting repo ("pattern sweeps are tree-wide or they don't count"). It fired and they still got it wrong twice. That is evidence the guidance is aimed at the WRONG ACTOR — the reviewer is the one holding the pattern and can collapse N rounds into 1; telling the fixer to sweep leaves them inferring what the pattern is.

  Fix shape: in `review-protocol.md`, when a finding is a repeated claim/term/value rather than a one-off, require the reviewer to grep tree-wide and enumerate every instance in the finding body. TWO CAVEATS belong in the same text or this does harm: (1) make it CONDITIONAL — trigger on pattern-shaped findings only; a blanket "always grep tree-wide" adds cost and noise to genuinely local findings. (2) require CLASSIFICATION, not a dump — most hits in the reported greps were LEGITIMATE and must not be touched (correction narratives deliberately quoting old wording, archived backlog items recording superseded history, tests deliberately pinning old behavior). An unclassified dump moves triage onto the fixer and invites over-correction of text that is supposed to say that. Mark each hit needs-fix vs legitimate. Cheap partial version if the full change is too invasive: one checklist line in the reviewer's finding template.

  Note this pairs with prawduct's own "verify at the quantifier" learning (CRT-8Q6R Correction 4) — same underlying shape, opposite actor. (report-bug — hallucinote upstream)

  **STRENGTHENED — do not fix this item without reading [CRT-6R3W] (filed 2026-07-21, same day).** A second external report shows instance enumeration is *necessary but not sufficient*: an agent ran exactly the tree-wide instance sweep this item prescribes and was still short by four sites, including two log lines one line below the ones it had just fixed. What converged was sweeping by the **generating rule** (the predicate that names the class) rather than by the instances. CRT-6R3W also reopens the actor question this item settled by inference (reviewer-side) — its report's rule came from the FIXER, after four rounds. Treat this item as the enumeration half of a larger problem; CRT-6R3W carries the rule-vs-instance design question and is deliberately **not** merged into this one.

- **[REL-5W2J]** `docs/release-process.md` omits `pyproject.toml`, `CHANGELOG.md`, and clearing `active_build_plan`
  `effort: S · impact: M · area: docs · kind: fix · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: REL-3M7K, REL-7D4X, GOV-4H7T · refs: docs/release-process.md, pyproject.toml (version — stale at 3.0.3), CHANGELOG.md, hooks/banner.py (the version-delta banner reader), .prawduct/project-state.yaml (`active_build_plan`), .prawduct/runbooks/cut-and-publish-a-plugin-release.md`

  Three release-prep steps are absent from the process doc and get rediscovered every release. `pyproject.toml` carries a version and is stale at `3.0.3` — it missed v3.0.4, v3.0.5 and v3.1.0. `CHANGELOG.md` is what the version-delta banner actually reads (`hooks/banner.py`) and is named nowhere (that half is REL-3M7K, already open — cross-link rather than duplicate). `.prawduct/project-state.yaml`'s `active_build_plan` wants clearing at release or the shipped tree misdirects every session opening against it. All three were found by *deriving* `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` from the runbook guide, not by reading the process doc. v3.1.1 patches the instances; the source stays wrong. (user — v3.1.1 release fold-in)

- **[REL-7D4X]** Release runbook prescribes a positional change-log sweep, which drops entries that merged below the boundary
  `effort: S · impact: M · area: docs · kind: fix · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: REL-2N8K, REL-5W2J, REL-9F2T · refs: .prawduct/runbooks/cut-and-publish-a-plugin-release.md (Phase 1 steps 2–3; `last_verified: null`), .prawduct/artifacts/release-plan-v3.1.1-hotfix.md, .prawduct/change-log.md, docs/release-process.md`

  `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` Phase 1 steps 2–3 say to find the topmost tag line carrying `release=` and flip everything *above* it. That is the exact method `release-plan-v3.1.1-hotfix.md` proves wrong: `2026-07-14: Stale remote-base diagnostics` sits below the v3.1.0 boundary and is genuinely unreleased, so a positional sweep silently drops it. The sound test is per-candidate — an entry is release-pending iff it carries no `release=` tag AND its code is absent from the prior release's tree. Same root cause as REL-2N8K. The runbook is otherwise sound and was used for v3.1.1; it is also `last_verified: null`. (user — v3.1.1 release fold-in)

- **[GOV-6J3P]** `skills/runbook/SKILL.md` grants `Bash(prawduct-hook backlog *)` it never uses
  `effort: S · impact: S · area: governance · kind: fix · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: BKL-5N9W, JNT-4R2M, CRT-2M5P, GOV-4H7T · refs: skills/runbook/SKILL.md:6 (allowed-tools — both invocation forms), skills/runbook/SKILL.md:214 (the only backlog use — `/prawduct:backlog add`), skills/backlog/SKILL.md:7 (the grant the slash-command invocation carries instead)`

  The frontmatter grants both `Bash(prawduct-hook backlog *)` and `Bash(python3 bin/prawduct-hook backlog *)`, but the skill's only backlog use is "File it with `/prawduct:backlog add`" (line 214) — a slash-command invocation that loads the backlog skill with its own `allowed-tools` and needs no Bash grant from this file. On `develop` the grant resolves so it is not a live defect, but it is an unnecessary wildcard grant of the same shape as one of the five v3.2.0 blockers. v3.1.1 strips it as a partial take; removing it at source stops the re-patch every release. (user — v3.1.1 release fold-in)

- **[CRT-6D2N]** `critic-begin` anchors verify-resolutions to committed HEAD whenever *any* commit landed since the prior review — so a clean commit delta over a dirty tree exits 1 with "nothing to verify" and leaves judgeable uncommitted work unreviewed
  `effort: S · impact: M · area: critic · kind: bug · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: open · stage: ready · related: CRT-7H2W, CRT-4J8W, CRT-8H3R · refs: lib/critic_consolidate.py (`begin_review` — the verify-resolutions intent-aware anchor branch keyed on `critic_mode._committed_files_since`, and the `not delta and not actionable` "nothing to verify" refusal a few lines below it; ~:324-338 and ~:382-389 as of 2026-07-20, anchored by symbol because the fix moves both), lib/critic_mode.py (`_committed_files_since`), tests/test_critic_consolidate.py, bin/prawduct-hook (critic-begin), skills/critic/SKILL.md`

  **Observed live 2026-07-20** on branch `fix/archive-scope-preservation-claim`: a 97-line unreviewed rewrite of `.prawduct/artifacts/release-plan-v3.1.1-hotfix.md` sat in the working tree while `prawduct-hook critic-begin --mode verify-resolutions` exited 1 with `nothing to verify: the prior review has no blocking/warning findings and nothing changed since`. The refusal reads as "everything is reviewed"; it actually means "everything I chose to look at is reviewed."

  **Mechanism — CONFIRMED 2026-07-20** (second live occurrence during Critic review `rev-20260720T225910Z-8d517755`; the earlier reading below was filed as inference and now matches the code as read). The root cause is a **commit-set vs tree-set mismatch**. The CRT-7H2W intent detector (`lib/critic_consolidate.py`, `begin_review` — `~:326` as of 2026-07-20, anchored by symbol `critic_mode._committed_files_since`) decides the head anchor from a **commit-set** diff (`<prior_commit>..HEAD`). When the prior review fact carries `head_commit: null` (a dirty-tree anchor), `prior_commit` falls back to `dispatch_commit`; a later commit that merely **materializes the already-reviewed tree** still makes `committed_since` non-empty, so the anchor moves to committed HEAD. But the prior `head_tree` equals that commit's `HEAD^{tree}`, so `delta = tree_diff(base_tree, head_tree)` computes **empty** — and the `not delta and not actionable` guard (`~:382`) refuses with a factually wrong *"nothing changed since"* while real judgeable work sits uncommitted. This is exactly the flow `skills/critic/review-cycle.md:70` documents as *"a review of the dirty working tree **vouches for the subsequent commit** when the commit is made verbatim"* — the vouching commit is precisely what trips the detector. **Fix shape (now specific, matching option (a) below): detect intent by TREE inequality — prior `head_tree` != capture `head_tree` — not by the commit set.** Impact stays bounded (the SKILL's fallback to another mode works), but the stderr message misleads a builder into believing the tree is reviewed. Observed twice on branch `fix/archive-scope-preservation-claim` (2026-07-20).

  **Mechanism as originally filed (2026-07-20, the inference now confirmed above).** CRT-7H2W made the verify-resolutions head anchor intent-aware: if `_committed_files_since(project_dir, prior_commit)` is non-empty, anchor `head_tree = capture["head_tree"]` (committed HEAD, the PR-gate target) and *note-and-exclude* the dirty working tree; otherwise keep the working-tree anchor (the Stop-hook target). The scope is then `delta = tree_diff(base_tree, head_tree)` — committed content only — and the refusal guard tests exactly that `delta` plus the prior review's actionable count. The two sides use **different notions of "changed"**: the branch keys on a *commit-log* delta, the guard on a *tree* delta. They disagree in the case that bites — the prior review anchored to a dirty working tree (`head_commit = None`, so `prior_commit` falls back to `dispatch_commit`), the builder then *commits that already-reviewed content* (commit-log delta non-empty, tree delta empty), and new judgeable work lands in the working tree afterwards. The anchor branch excludes the new WIP by design, the guard then sees an empty committed delta and no prior findings, and `critic-begin` refuses — the excluded WIP is never in anyone's scope.

  **Why it matters.** The failure is silent in the direction that loses governance: exit 1 with a message a builder reasonably reads as "nothing left to review", on a tree that carries unreviewed judgeable changes. It is the mirror of the case CRT-7H2W fixed (there the PR gate read `uncovered` after a *successful* verify-resolutions; here the review never runs at all).

  **Fix-shape (menu — (a) is now the confirmed shape after the second occurrence; still a judgement call, not a mechanical edit).** (a) Key the anchor branch on the *tree* delta rather than `_committed_files_since`, so "commits that changed nothing since the reviewed tree" falls through to the working-tree anchor and the WIP is reviewed (preserves CRT-7H2W's PR-gate intent, which only applies when committed content actually differs, and preserves CRT-4J8W dirty-tree verify). (b) Keep the branch and teach the guard about what the branch excluded: refuse only when there is no committed delta *and* no judgeable uncommitted file; otherwise fall through, or return a message naming the excluded WIP and the required action (commit it, or re-dispatch at a mode that covers it). (c) At minimum, make the refusal message non-misleading — "nothing changed since" must not be emitted while judgeable uncommitted files exist. (a) and (c) are compatible and probably both wanted. Add a regression test pinning the clean-commit-delta-over-dirty-tree case. Governance-protected (`lib/critic_consolidate.py`, the Critic data plane) → full Critic + PR review. (user — observed live)

- **[CRT-3F7M]** Critic coordinator dispatches reviewer subagents from a skill fork; they die with the fork, leaving a valid manifest and zero partials — the review hangs silently forever
  `effort: M · impact: L · area: critic · source: critic · added: 2026-07-20 · reviewed: 2026-07-23 · status: open · stage: research · related: CRT-4V8P, ENV-7C4K, CRT-7Q2T, CRT-5N3F, STH-7W9K, CRT-8Q6R · refs: skills/critic/SKILL.md:57 (coordinator dispatch — "dispatch the three critic-reviewer subagents … and STOP"), skills/critic/review-protocol.md (Coordinator Pattern), lib/critic_consolidate.py (partial/manifest contract), bin/prawduct-hook (critic-begin, critic-consolidate, critic-end, clear)`

  Observed 2026-07-20 on branch `fix/archive-scope-preservation-claim`. `/prawduct:critic` (`context: fork`) ran `critic-begin`, wrote a **valid** `.prawduct/.critic-partials/manifest.json`, reported "three reviewers dispatched", and returned. No reviewer subagent ever wrote a partial: `prawduct-hook critic-consolidate` reported `no-op: review incomplete — waiting on correctness, design, sustainability (0/3 partials present)` indefinitely, and `TaskList` showed no running tasks — so the subagents did not survive the fork's return. The critic-active marker stays set meanwhile, which also blocks the session-mutating `prawduct-hook clear`.

  **Recovery that worked:** re-dispatch the same three roster roles as subagents from the MAIN agent (which persists) against the *existing* manifest, each writing its own `<role>.json`. Consolidation then merged normally and produced a correct review (2 blocking, 8 warning, 13 note — all findings real). So the data plane is sound; only the dispatch lifetime is broken.

  **Why this matters more than the wasted time:** the failure is **silent** and is indistinguishable from a slow review. A cumulative review legitimately takes 4–10 minutes, so an agent that waits patiently is doing the right thing and will still wait forever. Worst case, a builder gives up waiting and proceeds unreviewed — the governance gate is bypassed by a timeout, not by a decision.

  **Candidate fixes (as originally filed — (b) has since landed, see the 2026-07-20 update below):** (a) dispatch the roster from the persisting main agent rather than from the fork — note this cuts against `skills/critic/SKILL.md:57`'s explicit "once the reviewers are dispatched you are done; there is no resume-to-aggregate"; (b) have `critic-begin` record a dispatch deadline so `critic-consolidate` can report "reviewers never reported" instead of "waiting" — turns a silent hang into a loud failure without changing the dispatch model; (c) have the coordinator await its subagents before returning.

  **Needs verification** that this is reproducible rather than incidental to this session — hence `stage: research`. Same silent-failure family as ENV-7C4K (stale `prawduct-hook` on PATH → `critic-begin` silently wrote no manifest; here the manifest is fine and the *reviewers* are missing). Related to CRT-4V8P (mode inference returned `chunk` for a clean tree in the same invocation). Governance-protected (Critic dispatch path) → full Critic + PR review. (critic)

  **Update 2026-07-20 (branch `fix/archive-scope-preservation-claim`) — partial fix shipped + evidence revision.**
  - **Candidate fix (b) landed:** `critic-consolidate`'s incomplete no-op now parses the dispatch timestamp from the review id and renders a **liveness verdict** — inside a 15-minute grace window it says wait; past it, it says `critic-end` + re-dispatch — with roster-accurate wording for single-pass vs coordinator reviews. The hang is no longer silent; the underlying dispatch-lifetime question stays open.
  - **New evidence (2026-07-20 hallucinote transcripts):** at least one "reviewers died with the fork" report was a **misdiagnosis** — the reviewers survived the fork's end, ran 7–9 minutes, and completed; the parent session inferred death from 0/3 partials at ~2.5 minutes and double-dispatched. The title's death claim is therefore unconfirmed for that instance; fix (b)'s 15-minute grace window exists precisely to prevent this premature-death inference.
  - **Remaining (why this stays open at `stage: research`):** root-cause whether reviewer subagents can *genuinely* die with the fork (dispatch-lifetime semantics), and reproduce the originally filed hang.

  **Update 2026-07-23 — field corroboration of candidate fix (c)/(a).**
  A separate agent working a ~25-file (coordinator-mode) cumulative diff independently reported using a "sync workaround so it aggregates findings before ending the turn" — i.e. it awaited the reviewer subagents and consolidated in-turn rather than the sanctioned dispatch-and-STOP. That is candidate fix (c) ("have the coordinator await its subagents before returning") reinvented in the field, and it maps to (a) as well (re-couple persistence to the review). Two takeaways:
  - The field is routinely deviating from the documented "STOP, no resume-to-aggregate" protocol (`skills/critic/SKILL.md:57`, `skills/critic/review-protocol.md:150-162`) to get results. When agents work around the sanctioned path to make the Critic produce output, the sanctioned path is the defect (Principle 16 — fix the system).
  - The recurring "Critic ends without producing results" reports trace to the async decoupling regardless of whether reviewers literally die with the fork: even when they survive, the coordinator's turn ends at 0/3 partials and findings only land minutes later via the SubagentStop trigger (advisory, `bin/prawduct-hook:956-1004`) or the session-end backstop — so from the caller's seat the Critic "ran and nothing came back."

  **Proposed repro (resolves the `stage: research` blocker — does await-in-fork hold?):** from the `context: fork` coordinator, dispatch the three critic-reviewer subagents with `run_in_background: false`; confirm the fork blocks until all three partials land, then runs `critic-consolidate` in-turn. Validate across a *genuine* 7–9 min cumulative review, not just a fast one — the 2026-07-20 update already showed the "died with the fork" premise was at least once a misdiagnosis (reviewers survived 7–9 min; the parent double-dispatched at ~2.5 min). If the fork reliably awaits, candidate (c)/(a) become the primary path and the async SubagentStop trigger + session-end backstop become the fallback. This is the empirical question that has kept the item at `stage: research`; the field report is fresh evidence it can be answered.

  **Cross-link CRT-8Q6R:** the cache-warm / "stay audible while waiting" stopgap (`_CACHE_WARM_DIRECTIVE`, hardcoded 4-min interval in `lib/critic_consolidate.py`) exists *only because the wait is async*; a synchronous coordinator await largely obviates that stopgap and its TTL guessing. (CRT-8Q6R already lists CRT-3F7M as related, so the back-link exists.)

  (Source: user-directed, from an owner session reviewing field reports.)

- **[CRT-8Q6R]** Critic wait-side cache-warm directive hardcodes a 4-minute readout interval against an *assumed* 5-minute prompt-cache TTL — a stopgap that is wasteful on 1-hour-TTL sessions and silently wrong if the default changes
  `effort: S · impact: M · area: critic · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: open · stage: research · related: CRT-3F7M · revisit: v3.2.0 release · refs: lib/critic_consolidate.py (_CACHE_WARM_DIRECTIVE, _CACHE_WARM_INTERVAL_MINUTES, _incomplete_noop_message, dispatch_age_minutes, _INFLIGHT_GRACE_MINUTES rationale block), tests/test_critic_consolidate.py (test_wait_side_directs_a_periodic_readout, test_review_cycle_prose_matches_the_code_cadence), skills/critic/review-cycle.md (§ Prep work before invoking cumulative), methodology/building.md (§ The Critic takes time), skills/critic/SKILL.md, .prawduct/artifacts/release-plan-v3.1.1-hotfix.md, .prawduct/artifacts/project-preferences.md`

  **Requirement (the durable part, which outlives the stopgap):** a session waiting on in-flight background critic reviewers must not idle *silently*. An idle session issues no requests; its prompt cache expires; the next turn re-reads the whole prefix. Observed as token replay on early-adopter and owner sessions, 2026-07-20.

  **Stopgap as implemented (targeted for v3.1.1 — not yet released):** `_CACHE_WARM_DIRECTIVE` in `lib/critic_consolidate.py`, appended to the incomplete-consolidate no-op message (`_incomplete_noop_message`), telling a waiting session to stay audible at least every `_CACHE_WARM_INTERVAL_MINUTES` (= 4) minutes — sized to stay inside an *assumed* 5-minute prompt-cache TTL. The same wait-side advice appears in the operator-facing guides — carried by the same commit, not a later one: `skills/critic/review-cycle.md` (§ Prep work before invoking cumulative) states the 4-minute cadence as prose; `methodology/building.md` (§ The Critic takes time) carries the don't-go-silent rationale without a numeric literal.

  **Why it is a stopgap, not a fix.** The cache TTL is **not observable from inside a hook**. Anthropic offers both 5-minute and 1-hour prompt-cache TTLs, so a hardcoded 4-minute interval is (a) wasteful on a 1-hour-TTL session — it burns readouts to defend a cache that was never at risk — and (b) silently wrong if the effective default changes, with no signal at the call site. The number is a guess dressed as a constant.

  **Candidate fixes at revisit (v3.2.0):**
  - make the interval a `project-preferences.md` knob (explicit, per-product, no inference);
  - derive it from something observable rather than assuming a TTL;
  - **drop it entirely** if the harness already handles cache retention for idle sessions — check this first, since it would retire the directive rather than tune it.

  **State as committed (verified 2026-07-20).** The stopgap **is implemented and committed** on branch `fix/archive-scope-preservation-claim`, targeted for the v3.1.1 hotfix (`.prawduct/artifacts/release-plan-v3.1.1-hotfix.md`). The commit `fix(critic): tell a waiting session to stay audible, not just to stop re-dispatching` (`b4617e0` as of 2026-07-20 — a short SHA on an unpushed branch, so expect it to move; the message is the durable handle) is the **single commit carrying all three surfaces** — `lib/critic_consolidate.py` (`_CACHE_WARM_DIRECTIVE`, `_CACHE_WARM_INTERVAL_MINUTES`), `methodology/building.md`, and `skills/critic/review-cycle.md` — together with this backlog item. **Follow-up, enumerated per-file over `b4617e0..HEAD` (re-verified 2026-07-20):** `methodology/building.md` — none; `skills/critic/review-cycle.md` — none; `lib/critic_consolidate.py` — **one**, `8b0bea1` (`fix(critic): resolve Critic warnings, and plan the v3.1.1 hotfix`, +28/−5), the `mint_review_id` extraction, which **did not touch the cache-warm directive block** (`_CACHE_WARM_DIRECTIVE` appears in that diff only as a hunk-header context anchor). Not "no follow-up on any of them" — that blanket phrasing was itself Correction 4's defect. So this item is the **revisit record for a live stopgap**, not an open question about whether it landed — and the phrasing is "targeted for v3.1.1," not "shipped in v3.1.1," because v3.1.1 does not exist yet.

  (Correction 1: an earlier draft of this paragraph asserted the directive was absent from the tree and that no commit mentioned a cache-warm interval. That was true of the parent tree the filing text was drafted against and **false as committed**. Corrected after Critic review `rev-20260720T203947Z-6a88b71d`, where all three reviewers flagged it.)

  (Correction 2 — the one worth recording, from `rev-20260720T205656Z-d302f7af`: the fix for Correction 1 introduced a *new* false claim in its place. It said "a follow-up commit carried the wait-side advice into `methodology/building.md` and `skills/critic/review-cycle.md`." No such commit exists — `git log <stay-audible-commit>..HEAD` on those two paths is empty, and `git log origin/develop..HEAD` on them returns only that one commit (`b4617e0` at the time of writing; resolve it by message, since an unpushed branch's SHAs are provisional). This is the **fourth** instance on branch `fix/archive-scope-preservation-claim` of a claim that was true when drafted and false when committed, and it occurred **inside the correction written to fix the third**. The lesson is not "verify before filing" — that was already the lesson from instances 1–3. It is that *correcting a claim is authoring a claim*, and a correction inherits the full verification burden of the thing it replaces; a correction drafted from recollection of what "must have happened" reproduces the exact failure it is fixing.)

  (Correction 4 — root cause of the run, from `rev-20260720T212124Z-9827ad5a`, which counts this as the **eighth** instance on this branch: *correcting a claim is authoring a claim* has not stopped it, because the failure is narrower than "unverified claim." **The recurring shape is a claim whose quantifier is broader than what was actually verified** — "no follow-up commit on **any** of them", "**every** one of them", "**six** steps", "also catches a **second** site": the narrow fact gets checked, the broad claim gets written. The operative rule is **verify at the quantifier** — when a claim says *no / every / all / only / none / N*, the check must **enumerate the quantified set**, not confirm one instance. Aggravating factor, visible in this very finding: the false sentence was an **untouched sentence inside an edited paragraph**, which reads as freshly vouched-for when nothing re-checked it — editing a paragraph does not re-verify the sentences you left alone.)

  **The cadence is pinned by a test, so a bump costs two edits.** `tests/test_critic_consolidate.py` asserts `_CACHE_WARM_INTERVAL_MINUTES < 5` and that both wait-side message variants interpolate it (`test_wait_side_directs_a_periodic_readout`), and separately binds `skills/critic/review-cycle.md`'s bare prose literal to the constant (`test_review_cycle_prose_matches_the_code_cadence`). Changing the interval therefore requires updating **both** the constant and the guide, or the suite fails — the guard that keeps the operator-facing prose from quietly contradicting the tool when this item is revisited.

  Sits on the same wait-side surface as **CRT-3F7M** (the incomplete-consolidate no-op) but is a distinct concern: CRT-3F7M is about *inferring reviewer death from silence*; this is about *what the waiting session should do with the silence*. Do not merge — one is a liveness verdict, the other a cache-retention directive. (user)

- **[CRT-4V8P]** `infer-critic-mode` returns `chunk` for a clean working tree — rule 4 fires on an unrelated active build plan and produces an empty-diff refusal
  `effort: S · impact: M · area: critic · source: critic · added: 2026-07-20 · status: open · stage: ready · related: GOV-8N4V, CRT-6J4P, CRT-8H3R, WT-7M4K · refs: lib/critic_mode.py:197-210 (rule 4), lib/critic_mode.py:111 (infer_mode), bin/prawduct-hook (infer-critic-mode, critic-begin), skills/critic/SKILL.md`

  On a standalone fix branch with all work committed, `prawduct-hook infer-critic-mode` returned `chunk` via rule 4 ("active build plan, prior chunks committed"), but rule 4 fired on an **unrelated** active build plan (`artifacts/build-plan-backlog-skill-repoint.md`, retained-by-rule pending release) while the branch had no build plan at all. Because the tree was clean, `chunk`'s interval (HEAD tree → working tree) was empty and `critic-begin --mode chunk` correctly refused with exit 1, naming the remedy: a committed bundle is cumulative's scope.

  Observed 2026-07-20 on `fix/archive-scope-preservation-claim`; the critic skill recovered by falling back to `cumulative` and recorded `mode_chosen_by` accordingly, so this is a **wasted round-trip rather than a wrong review**. The fail-closed refusal worked as designed; this item is about not requiring the fallback.

  **Fix shape (cheap):** have the inference check for a non-empty interval before returning a working-tree-scoped mode — a clean tree cannot be reviewed by `chunk`, regardless of which rule matched. Rule 4's `if total > 0` (`lib/critic_mode.py:202`) grounds the choice in a plan's chunk count but never checks that anything is actually reviewable in the working tree.

  **Secondary:** rule 4 keying on `active_build_plan` should confirm the plan is actually related to the branch's changes (same "unbounded pointer" family as CRT-6J4P / CRT-8H3R, which bound rule 1b's anchor to branch/plan scope — consider one pass). Distinct from GOV-8N4V, which is the inverse failure (a *set* pointer going unresolved → fail-safe `final`). Governance-protected (`lib/critic_mode.py`) → full Critic + PR review. (critic)

- **[OBS-7M4D]** Purge prawduct-internal ids from operator-emitted text (hook stdout/stderr, CLI usage, advisory evidence)
  `effort: S · impact: M · area: observability · source: builder · added: 2026-07-19 · reviewed: 2026-07-20 · status: open · stage: ready · related: GOV-3P8K · refs: .prawduct/artifacts/observability-strategy.md (§ Direction — the norm), docs/norms.md (§ Exceptions expire / in-transition), bin/prawduct-hook (cmd_clear critic-active refusal message — "CRT-3X9D"), lib/backlog/cli.py (_HELP usage string — the reconcile-labels "GV6" and import "MG6" lines), lib/critic_consolidate.py (validate_partial — the waived-disposition error "non-empty 'rationale' (R7)")`

  Tracking item for the `## Direction` norm born in `observability-strategy.md` (skills-cutover-awareness Chunk 04): *text emitted into a governed product names no prawduct-internal identifier*. The norm is born `Status: in-transition` because a sweep at birth found sites beyond the changeset's scope.

  Fixed at birth (in scope for that chunk):
  - the three dormancy NOTE copies (`skills/critic/review-cycle.md`, `skills/pr/review-protocol.md`, `skills/janitor/SKILL.md`) — dropped `GV8`
  - `skills/backlog/adapter-mode.md` find NOTE — dropped `W2`
  - `lib/backlog_probes.py` (`probe_checks_dormant` advisory evidence) — dropped the check labels `C-B1`-`C-B4` and `R-1`/`R-2`; the enumeration now derives from a `DORMANT_CHECKS` list of plain-language names

  **Inventory corrected after the Chunk 04 cumulative Critic (finding R-10).** `lib/backlog_probes.py` is **no longer in this item's scope**. Its evidence string was written by the *same changeset that birthed the norm*, so the norm's own interim rule — *"emitted text a changeset writes or edits complies"* — already required fixing it; deferring it here would have made the birthing changeset the norm's first exception. It was fixed at birth (see the list above).

  **Ruling on the debatable case** (previously flagged in this item as unresolved): internal check labels **do** count as internal ids for this norm, because an operator downstream can resolve `R-2` no better than `GV8`.

  Remaining inventory — **four sites**. Anchored by *symbol*, not line number: the original line-number anchors had all rotted within a day (Critic review `rev-20260720T203947Z-6a88b71d` — `critic_consolidate.py:500`, filed as the `R7` string, now points at an unrelated severity check).
  - `bin/prawduct-hook` — `cmd_clear`'s critic-active refusal message names `CRT-3X9D`
  - `lib/backlog/cli.py` — the `_HELP` usage string's `reconcile-labels` line names `GV6`
  - `lib/backlog/cli.py` — the `_HELP` usage string's `import` line names `MG6`
  - `lib/critic_consolidate.py` — `validate_partial`'s waived-disposition error names `R7`

  **Two sites left the inventory (verified 2026-07-20):** the `--archive-scope open` warnings in `cli.py`'s `_run_restructure_preview` and `migrate.py`'s `import_backlog` both used to end "…they remain in the source markdown + MG2 export." Commit `0191f1e` rewrote both to drop the export promise, and the `MG2` id went with it — the norm's interim rule (*emitted text a changeset edits complies*) applied, so the rewrite had to leave them clean. Neither copy names an internal id today.

  Each fix is replacing the id with the plain-language reason it stood for; the id stays in the adjacent comment/docstring, which the norm permits. The sweep heuristic (id-shaped tokens inside string literals) is not exhaustive — prefixes are open-ended — so closing this item means running the sweep AND recording that ongoing enforcement is the Critic's judgment, not a regex.

- **[JNT-4R2M]** `skills/janitor/SKILL.md` instructs `prawduct-hook review-stats` but its `allowed-tools` carries no `prawduct-hook` grant — the call is unrunnable in a plugin-governed product repo
  `effort: S · impact: M · area: janitor · kind: bug · source: critic · added: 2026-07-19 · reviewed: 2026-07-19 · status: open · stage: ready · related: ONB-3F9P, JNT-5K3W · refs: skills/janitor/SKILL.md:5 (allowed-tools), skills/janitor/SKILL.md:182 (the review-stats instruction), skills/backlog/SKILL.md:7 (the dual-form grant precedent), docs/governance-telemetry.md`

  Surfaced by the Chunk 03 Critic review of `skills-cutover-awareness`. `skills/janitor/SKILL.md:182` instructs *"Run `prawduct-hook review-stats` for the project's review cost / actionable-finding history"*, but the frontmatter at `skills/janitor/SKILL.md:5` carries no grant covering `review-stats`.

  **Evidence corrected at the PR review (2026-07-20).** This item originally read "grants only `Bash(git *), Bash(npm *), Bash(python3 *), Read, Write, Edit, Glob, Grep, Agent` — no `prawduct-hook` grant of any form." Chunk 04 of the same bundle that filed this item added `Bash(prawduct-hook backlog *)` and `Bash(python3 bin/prawduct-hook backlog *)` to that exact line, so the quoted inventory described a tree that no longer exists. **The defect is unchanged and still open** — the grant is scoped to `backlog`, and `review-stats` remains ungranted in both forms — but it is now a *missing subcommand* gap, not a missing-grant-entirely gap.

  **Scope the claim precisely** (per the Chunk 03 `verify-resolutions` note). The bare `prawduct-hook review-stats` form is unrunnable **in a plugin-governed product repo**, where the hook is only reachable as `prawduct-hook`. It is *not* unrunnable in this self-hosted checkout: janitor holds `Bash(python3 *)`, so `python3 bin/prawduct-hook review-stats` is already permitted here. **That is exactly why the gap stayed invisible while dogfooding** — every janitor run in this repo could reach the hook by the self-hosted path, so nothing ever failed locally to expose the missing grant.

  Verified as an outlier, not a design position: **every** sibling skill that instructs a hook call carries the matching scoped grant — advisory (`advisory*`), backlog (`backlog *`), critic (nine subcommand grants), doctor (five), migrate (`migrate-plugin*`), onboard (`init-product *`), pr (seven), repo-disable (`repo-disable *`). The only other grant-less skills (learnings, methodology, ping, report-bug) instruct **no** hook calls at all. Janitor is the sole skill that instructs a hook subcommand it holds no grant for — since Chunk 04 it *does* carry the two `backlog` grants, which makes the omission narrower and more clearly an oversight: the same line was edited without `review-stats` being noticed.

  Fix-shape: grant **both invocation forms** on the `allowed-tools` line — `Bash(prawduct-hook review-stats*)` **and** `Bash(python3 bin/prawduct-hook review-stats*)` — scoped to the subcommands the janitor actually instructs (audit the file for any others before landing). `skills/backlog/SKILL.md:7` is the house precedent and grants both forms (`Bash(prawduct-hook backlog *)`, `Bash(python3 bin/prawduct-hook backlog *)`) precisely to cover the installed-plugin and self-hosted invocations; mirror that. **Landing only the bare form recreates half the gap** — it fixes the product repo and leaves the self-hosted path ungranted. Same class as the `skills/doctor/SKILL.md` grant gap tracked under **ONB-3F9P** and the earlier BKL-3W6K finding that the backlog skill lacked Bash entirely; if ONB-3F9P is worked first, fold this in with it. Governance-protected (`skills/`) → full Critic + PR review. (critic — skills-cutover-awareness)

- **[TST-6K3D]** Build-plan chunk-heading test replica has drifted from the production matcher — the guard rejects headings production parses fine
  `effort: S · impact: M · area: tests · kind: bug · source: critic · added: 2026-07-19 · status: open · stage: ready · related: BLD-7P3K, BLD-5J8N, VWS-2F9K, CRT-3T6V · refs: tests/test_build_plan_resolution.py:264 (_parseable_body_chunk_ids), lib/buildplan_refs.py:82 (_CHUNK_HEADING_RE, _CHUNK_ID_SEP)`

  Found by the Chunk 01 `verify-resolutions` pass on `feature/skills-cutover-awareness`. The guard test `_parseable_body_chunk_ids` (`tests/test_build_plan_resolution.py:264`) documents itself as replicating "the matcher the production parsers use" and requires **three-hash + a colon** (`### Chunk N:`). The only production matcher — `lib/buildplan_refs.py:82` `_CHUNK_HEADING_RE = re.compile(r"^#{2,3}\s+Chunk\s+(\w+)" + _CHUNK_ID_SEP)` with `_CHUNK_ID_SEP = r"\s*(?:[:—–(-]|$)"` — accepts **both `##` and `###`** and **any of `: — – ( -`** or end-of-line (broadened by BLD-5J8N for the `## Chunk N (ID) — Name` research-plan form).

  Consequence: a plan heading production parses fine is rejected by the guard, and the docstring's claim is **false** — the test is a stale second implementation of a contract it no longer mirrors, which is exactly the drift class BLD-7P3K created it to prevent.

  **Decide deliberately which contract is authoritative.** If the stricter `### Chunk NN:` convention is intended as the *authored* standard (a style guard, not a parser replica), say so in the docstring and stop calling it a replica. If not, widen the test to match production. **Do NOT narrow `_CHUNK_ID_SEP` to match the stale test** — that would re-break the em-dash form BLD-5J8N deliberately enabled. Sibling drift of the same broadening lives in VWS-2F9K (`lib/views.py CHUNK_LINE_RE` never widened). (critic)

- **[BKL-4H8P]** Adapter error envelope says `retryable: true` but supplies no retry budget — a forked skill burned 23 attempts over 5+ minutes on GitHub 503s
  `effort: S · impact: M · area: backlog · kind: bug · source: user · added: 2026-07-19 · status: open · stage: ready · related: BKL-9T3K, BKL-2D8N, BKL-3W6K, BKL-3K9N, BKL-6M4T · refs: skills/backlog/adapter-mode.md (§"Reading the result — envelope + exit code", the exit-class table + error discipline), lib/backlog/transport.py (classification, no retry loop), lib/backlog/migrate.py (bounded importer backoff), lib/backlog/core.py:296 (post-create settle retry), documentation/backlog-service-requirements.md (G2)`

  Observed live in the samsung-frame-art-loader Phase 1 dogfood (2026-07-19), not hypothesized. Against a run of GitHub **503s**, a forked `/prawduct:backlog` model retried **23 times over 5+ minutes** before giving up. The envelope told it the error was retryable and nothing told it when to stop.

  **The adapter itself is well-behaved** — `transport.py` classifies the failure and returns **immediately**, with no retry loop for single ops (the only retry logic in `lib/backlog` is `migrate.py`'s bounded importer backoff and the narrow post-create settle retry at `core.py:296`), and measured op latency was **1.55–1.77s**. The defect is in the **prose contract**: `adapter-mode.md` documents `retryable` in the error envelope with **no max attempts, no wall-clock deadline, and no give-up-and-report rule**, so the model supplied its own unbounded loop.

  Fix: state an explicit **retry budget** in `skills/backlog/adapter-mode.md` alongside the exit-class table — e.g. at most N attempts and/or a T-second ceiling on `retryable: true`, with exponential spacing, then **stop and report the failure to the user** (never silently keep trying). Cheap, doc-only, governance-protected (`skills/`) → full Critic + PR review.

  This is effectively a **G2 violation at the seam**: G2 says a backend failure must never hang and must degrade cleanly. The adapter honors G2; the adapter + prose + model *system* did not — the never-block guarantee is only as strong as the weakest layer that reads it. Same doc-gap-not-code-defect class as BKL-9T3K (`prawduct:` block ownership) and BKL-2D8N (`--help`), all from the same dogfood. (user — samsung-frame-art-loader Phase 1 dogfood)

- **[BKL-4R7V]** Citation surfaces must recognize `owner/repo#number`, not just `[PFX-XXXX]` — post-cutover item references are invisible to every reader
  `effort: M · impact: M · area: backlog · source: user · added: 2026-07-19 · status: open · stage: ready · related: BLD-5V8F, BLD-3M7K, BKL-5D2C, BKL-6M4T · refs: documentation/backlog-service-requirements.md (GV9 — parent requirement; GV8 for the resolve half), lib/norm_probes.py:144 (_BACKLOG_ID_RE), lib/buildplan_refs.py (_parse_build_plan_chunk_refs — the deferred backlog-ref verification), skills/critic/review-protocol.md (Backlog check C-B4), skills/pr/review-protocol.md (R-2), .prawduct/change-log.md + backlog metadata (closes: / closed-by:)`

  Surfaced by the samsung-frame-art-loader Phase 1 dogfood (2026-07-19). Parent requirement is **GV9** in `documentation/backlog-service-requirements.md` — "item references survive the identifier change." After cutover the canonical id is `owner/repo#number`, but every citation-consuming surface in prawduct still recognizes only the markdown-era `[PFX-XXXX]` spelling, so a post-cutover reference is not mis-read — it is **not seen at all**, the same silent degradation GV7/GV8 exist to prevent.

  Concrete break (verified in source, not inferred): `lib/norm_probes.py:144` `_BACKLOG_ID_RE = re.compile(r"\b[A-Z]{2,4}-[A-Z0-9]{4}\b")` is PFX-only. The same PFX-only assumption sits behind the **Critic backlog check C-B4**, the **PR reviewer R-2** check, the `closes:` / `closed-by:` fields in both `.prawduct/change-log.md` entries and backlog item metadata bars, and the deferred **backlog-id verification** half of `lib/buildplan_refs.py` (tracked by BLD-5V8F, whose deferral note — "this project's backlog has no formal IDs" — is now doubly obsolete).

  **Recognition is additive: never narrow the PFX matching.** Both spellings must be accepted indefinitely — archived markdown items keep their PFX ids, `id:PFX` alias labels persist on migrated issues, and pre-cutover documents are not rewritten. This is a widening of every id regex/parser, not a replacement.

  Sequencing: **parsing/recognition can ship earlier** (pure syntax — widen the regexes, thread both spellings through the citation surfaces). **Resolving `#N` to a live status** is a backlog *read* and therefore lands with the W1 cache under GV8, alongside the other post-cutover readers. Split accordingly rather than blocking the cheap half on the expensive one.

  Dedup note: distinct from **BLD-3M7K**, which wants `owner/repo#number` tokens *excluded* from `verify-chunk-refs`' file-path heuristic. The two are complementary and should land coherently — BLD-3M7K stops the token being misread as a path; this item makes it read as a backlog id. (user — samsung-frame-art-loader Phase 1 dogfood)

- **[BKL-7H2M]** The issue standard contradicts itself on the body budget — §2 says ~120 visible words, §4 and the linter say 150, and §2's own per-section budgets already sum past both
  `effort: S · impact: M · area: backlog · source: user · added: 2026-07-19 · status: open · stage: ready · related: BKL-3T7X, BKL-4C6P, BKL-8N5K, BKL-6M4T · refs: documentation/backlog-service-issue-standard.md (§2 body templates + per-section budgets, §4 linter thresholds), lib/backlog/issuefmt.py:75 (BODY_MAX_WORDS = 150), lib/backlog/issuefmt.py:294 (body-too-long finding)`

  Surfaced by the samsung-frame-art-loader Phase 1 dogfood (2026-07-19). `documentation/backlog-service-issue-standard.md` states two different body budgets: **§2 says ~120 visible words**, while **§4 and the implementation agree on 150** (`lib/backlog/issuefmt.py:75` `BODY_MAX_WORDS = 150`, emitted at :294 as the `body-too-long` finding). Worse, §2's own **per-section** budgets sum to roughly **143–155 words before any Evidence section at all** — so an author who follows §2's section-by-section guidance exactly can produce a fully conforming task issue that still trips `body-too-long`. The standard is unsatisfiable at its own stated limits.

  Fix: reconcile to **one number**, propagated to all three homes (§2 prose, §2 per-section budgets, §4 threshold) with `issuefmt.BODY_MAX_WORDS` as the single implementation constant. Decide deliberately whether the per-section budgets shrink to fit the total or the total rises to accommodate them + Evidence.

  **Timing is the impact multiplier:** resolve this *before* the MG6 migration restructure pre-pass (BKL-8N5K) rewrites bodies at scale. Restructuring ~200 items against a self-contradictory budget bakes the contradiction into every migrated issue and makes the linter noisy from day one on an irreversible run. (user — samsung-frame-art-loader Phase 1 dogfood)

- **[BKL-9T3K]** `adapter-mode.md` must explicitly forbid the skill authoring a `prawduct:` block — the block is adapter-owned
  `effort: S · impact: M · area: backlog · source: user · added: 2026-07-19 · status: open · stage: ready · related: BKL-3W6K, DOC-4K9M, BKL-6M4T · refs: skills/backlog/adapter-mode.md, lib/backlog/encode.py (the prawduct: block writer/parser)`

  Observed live during the samsung-frame-art-loader Phase 1 dogfood (2026-07-19), not hypothesized. Filing an item through the post-cutover adapter path, the **skill hand-wrote a `prawduct:` block into the issue body**. The adapter then appended **its own** block, detected the duplicate, and **warned + discarded** the skill-authored one; the skill self-corrected with a follow-up `update`. Outcome was benign this time, but the round-trip is pure waste and the failure mode is only benign because the adapter happens to warn — a future body-composition path that merges rather than discards would silently produce a corrupt or ambiguous block.

  Root cause is a documentation gap, not a code defect: `skills/backlog/adapter-mode.md` never states the ownership boundary, so the skill inferred it should compose the full body including the machine block. **The `prawduct:` block is adapter-owned** — the skill supplies title, prose body, and facets as adapter arguments; the adapter alone serializes the block.

  Fix: add an explicit prohibition to `adapter-mode.md` (near the body/`file` guidance) — "never author, edit, or reproduce a `prawduct:` block; pass facets as adapter arguments and let the adapter serialize it." Governance-protected (`skills/`) → full Critic + PR review. (user — samsung-frame-art-loader Phase 1 dogfood)

- **[BKL-2D8N]** `prawduct-hook backlog <subcommand> --help` exits 2 "unknown flag" instead of printing usage
  `effort: S · impact: S · area: backlog · source: user · added: 2026-07-19 · status: open · stage: ready · related: BKL-3W6K, BKL-6M4T · refs: lib/backlog/cli.py (per-subcommand argument parsing), skills/backlog/adapter-mode.md`

  Surfaced by the samsung-frame-art-loader Phase 1 dogfood (2026-07-19). Every `prawduct-hook backlog` subcommand **rejects `--help`** with exit **2, "unknown flag"** rather than printing its usage. Small but real friction: `--help` is the universal discovery affordance, and an agent (or operator) probing an adapter op's flag set gets an error that reads like a malformed invocation instead of documentation. It also means the *only* source of truth for a subcommand's flags is `adapter-mode.md` plus the source — exactly the coupling that drifts.

  Fix: accept `--help` on each subcommand and print usage (flags, envelope shape, exit classes) at exit 0. Cheap, self-documenting, and it makes the adapter surface discoverable without opening `lib/backlog/cli.py`. (user — samsung-frame-art-loader Phase 1 dogfood)

- **[JNT-5K3W]** Janitor should SURFACE orphaned `prawduct`-namespace labels with zero issues — never auto-delete them
  `effort: S · impact: S · area: janitor · source: user · added: 2026-07-19 · status: open · stage: ready · related: JNT-7T1W, BKL-6M4T · refs: skills/janitor/SKILL.md (Backlog Health step), lib/backlog/provision.py:61,145 (PROV-1 — create-only, existing labels never modified), documentation/backlog-service-requirements.md (GV6 — label taxonomy provisioning + coexistence)`

  Surfaced by the samsung-frame-art-loader Phase 1 dogfood (2026-07-19). `prawduct-hook backlog update --area …` (and the other facet mutators) **provision** namespaced labels on demand but **never garbage-collect** them. Over time a repo accumulates `area:*` / `kind:*` / `stage:*` labels with **zero issues** — typos, renamed areas, abandoned facet values — cluttering the label picker and the GitHub UI for humans filing by hand.

  **This must SURFACE for human deletion, never auto-delete.** `lib/backlog/provision.py` is deliberately **create-only (PROV-1: existing labels are never modified)** precisely so the taxonomy **coexists** with labels that humans and other tools own (GV6). An automatic GC would violate that coexistence guarantee the first time it met a zero-issue label some other workflow owns — and label deletion is not recoverable through the adapter.

  Fix-shape: a janitor Backlog Health sub-check that lists `prawduct`-namespace labels (only the namespaces prawduct provisions — never a bare label) whose issue count is zero, framed as *"candidates for deletion — delete in the GitHub UI if you agree."* Read-only; no adapter write path. (user — samsung-frame-art-loader Phase 1 dogfood)

- **[ONB-3F9P]** `/prawduct:onboard` and `/prawduct:doctor` never provision the backlog surface or the label taxonomy — GV5/GV6 have no implementation
  `effort: M · impact: M · area: onboard · source: user · added: 2026-07-19 · status: open · stage: ready · related: DOC-7H2K, BKL-1V8J, JNT-5K3W, BKL-6M4T · refs: documentation/backlog-service-requirements.md (GV5 zero-cost provisioning, GV6 label-taxonomy provisioning + coexistence), skills/onboard/SKILL.md:6 (allowed-tools — only Bash(prawduct-hook init-product *)), skills/doctor/SKILL.md:6 (allowed-tools — no Bash(prawduct-hook backlog *) grant), lib/backlog/provision.py (reconcile-labels)`

  Surfaced by the samsung-frame-art-loader Phase 1 dogfood (2026-07-19). **GV5** ("zero-cost provisioning: `/prawduct:onboard` — and `doctor` — provisions a project's backlog surface") and **GV6** ("adoption provisions and reconciles the label taxonomy and coexists with a repo's existing labels") are written requirements with **no implementation on either skill**:

  - `skills/onboard/SKILL.md` has **no `backlog_service_repo` step and no label-provisioning step**, and `prawduct-hook init-product` has **no flag** to set the backlog repo or seed the taxonomy. A newly onboarded repo therefore has no backlog surface decision recorded and no labels.
  - `skills/doctor/SKILL.md` carries `allowed-tools` with **no `Bash(prawduct-hook backlog *)` grant** (verified at `skills/doctor/SKILL.md:6`), so it is **structurally incapable** of running `reconcile-labels` — the exact repair GV6 assigns to it. Same class of gap as BKL-3W6K's finding that the backlog skill lacked Bash entirely.

  **This is a missing explicit taxonomy step, not a broken backlog.** The adapter **self-creates labels on write**, so a cutover repo does eventually acquire its taxonomy — lazily, in whatever order items happen to be filed, with no up-front provisioning and no reconcile path when a human deletes a base label. The requirement is for provisioning to be an *explicit, verifiable adoption step*, not an emergent side effect of the first write.

  Fix-shape: (1) an `init-product` flag (or onboard prompt) recording `backlog_service_repo` when a product adopts the Issues backend; (2) an onboard step invoking the adapter's label provisioning; (3) add `Bash(prawduct-hook backlog *)` to the doctor `allowed-tools` and a doctor step running `reconcile-labels` as a repair. Pairs naturally with JNT-5K3W (the janitor's orphan-label surfacing) — provision on adoption, reconcile in doctor, surface orphans in janitor. Governance-protected (`skills/`) → full Critic + PR review. (user — samsung-frame-art-loader Phase 1 dogfood)
- **[BKL-9XQ2]** Consuming repos filing issues against prawduct — consent, evidence/PII & label taxonomy (requirements + design settled; buildable)
  `effort: L · impact: L · area: backlog-service · source: user · added: 2026-07-20 · reviewed: 2026-07-23 · status: open · stage: ready · related: BKL-7Q4M (the content-minimization leg — the § Direction norm's tracking item), BKL-0QR1, BKL-3T7X, BKL-7F3D, MET-6T4K, BKL-2Q7F, BKL-8V3D, BKL-5N9W, BKL-6J2X · refs: documentation/backlog-service-security-model.md#6-abuse-prevention--public-submission-pv3pv4, documentation/backlog-service-api-contract.md, artifacts/build-plan-backlog-service.md (Chunk 06 / MG5; W3 roadmap row — XP1/XP2), skills/report-bug/SKILL.md, artifacts/project-preferences.md, lib/backlog/cli.py:181-191 (file --repo), lib/backlog/ids.py:136-151 (parse_repo — shape-only), skills/backlog/SKILL.md:7 (allowed-tools wildcard), documentation/backlog-service-prd.md:258 (O5 — adapter inherits the session's GitHub auth), documentation/backlog-service-prd.md:217 (MG1 — GitHub has no ordinary issue-delete and never reuses numbers), skills/onboard/SKILL.md (NOT a consent surface — consent-at-install resolved 2026-07-23 as not-required), documentation/backlog-service-requirements.md (Upstream bug reporting — XP4–XP7; all upstream-filing legs settled as requirements; consent-at-install resolved 2026-07-23 as not-required), documentation/backlog-service-upstream-filing.md (the complete, owner-approved design — the buildable spec)`

  **REQUIREMENTS SETTLED, DESIGN COMPLETE AND OWNER-APPROVED — BUILDABLE; RELEASE GATE STILL STANDS.** Owner flagged this 2026-07-20 as critically important to prawduct's future. All upstream-filing requirements are settled as **XP4–XP7** in `documentation/backlog-service-requirements.md` (already in `refs:`): content-minimization (**XP4**), per-report consent (**XP5**), label-less filing (**XP6**), and adapter invariants (**XP7**). Consent-at-install / disclosure (leg 1a below) is resolved by **owner decision 2026-07-23 as NOT required** — there is no install-time opt-in; per-report consent is the whole mechanism. `stage: ready` reflects that: requirements are complete and the design that settles them is written and owner-approved in `documentation/backlog-service-upstream-filing.md`, so the item is buildable via the normal build cycle (Principle 6; `/prawduct:methodology building`). The release gate stated in the escalation below (THIS GATES RELEASE) still stands.

  The upstream-filing path — a *consuming* repo filing an issue against prawduct's own tracker — is underspecified in three named ways:

  **(1) User approval is default-required.** *(REFRAMED and split in two by the owner refinement of 2026-07-20 — read that block below before designing to this paragraph; the paragraph stands as written, but it conflates two distinct consent obligations and it under-frames the risk as confidentiality.)* Filing anything upstream from a consumer's repo must be user-approved by default. Needs a config preference mirroring the existing PR-merge-policy pattern in `project-preferences.md` (a stated workflow decision, read at a decision point, strictly adhered to), with **three** states: `always-file` / `ask-user` / `never-file`, **default = `ask-user`**, user-settable, and honored without exception. The unattended path matters here — Security §1a says no human is present, which is exactly when `ask-user` must mean "don't file," never "file anyway."

  **(2) Evidence and data exfiltration.** What evidence (if any) rides along with an upstream issue, and how prawduct *guarantees* a consuming repo never files proprietary code, secrets, or PII into a public prawduct issue. This interacts directly with (1) — approval is the human check, but a human approving a body they didn't read is not a control. Owner is explicitly unsure how to define the policy and asked for a **research/planning spike, not a guess**. Prior art to start from, not to assume sufficient: Security §4 (structured/allowlist-first credential scrub) and §3 (data privacy, local artifact sensitivity); neither was written for the consumer→public-prawduct-repo direction, where the *repo contents themselves* are the sensitive material.

  **(3) Label taxonomy for arriving issues.** Issues arriving from consuming repos need a taxonomy. Likely shape: prawduct defines it once and consumers adhere — but unresolved, and it must reconcile with the namespaced `<facet>:value` labels the adapter already models (`encode.py`, `provision.py`) and with GV6's coexistence/drift reconcile.

  Anchors into the existing requirement family: **XP1** (file upstream directly), **XP2** (provenance) / **XP3** (descoped), **PV3/PV4** (public-submission abuse handling — Security §6), **MG5** (retire the `incoming-bugs/` drop-box only in lockstep with a replacement), **GV6** (label-taxonomy provisioning).

  **Sequencing risk — this discovery gates a retirement.** MG5 ties drop-box retirement to a live upstream filing path, so (1)–(3) must be settled before a consumer starts filing upstream. See BKL-0QR1's owner sign-off: the minimal same-repo replacement (fixed-target public issue-create, `untriaged-upstream` label) is a *subset* of XP1 and rides Chunk 06; the cross-owner/foreign-identity/private-target surface stays W3. The three concerns above apply to **both** — the same-repo subset already sends a consumer's bug body into a public repo, so (2) in particular is live at Chunk 06, not deferrable to W3.

  ---

  **ESCALATION — owner, 2026-07-20: THIS GATES RELEASE.** No longer capture-only in priority (in *activity* it is now `stage: ready` — all upstream-filing requirements are settled as XP4–XP7; consent-at-install (leg 1a) resolved 2026-07-23 as not-required; the design is complete and owner-approved in `documentation/backlog-service-upstream-filing.md`, so the item is buildable). The sharp case: **private** repos consuming prawduct have never been able to file upstream at all. Post-migration their own items land in their own private Issues (fine) — but the same repos may file bug reports **up** into prawduct's **public** repo. A leak path that has never existed becomes possible for the first time, and it must be settled before release and before anybody migrates.

  **Mechanism — verified in code 2026-07-20** (recorded so the gate is enforceable rather than vague):

  - **`report-bug` cannot leak today.** `skills/report-bug/SKILL.md` is a plain gitignored **file write** into a local `incoming-bugs/` drop-box, active only when a local prawduct checkout is reachable; otherwise it captures into the product's **own** backlog. No `--repo`, no network. Confirmed by grep — the skill carries no `--repo` and no `backlog_service_repo` reference.
  - **But the capability already exists and is merely *uninstructed*, not *prevented*.** `skills/backlog/SKILL.md:7` grants `Bash(prawduct-hook backlog *)` (**wildcard**), and `backlog file --repo owner/repo` accepts **any** owner/repo: `_run_file` (`lib/backlog/cli.py:181-191`) passes the flag straight to `ids.parse_repo` (`lib/backlog/ids.py:136-151`), which validates **shape only** (`owner/repo`, two clean segments) — no allowlist, no owner constraint, no same-repo check. Any repo with the plugin can already file into `brookstalley/prawduct`. The only thing stopping it is that nothing tells it to. *(Correction to the reported citation: `cli.py:228` is the `get` owner-default path; the `file` path is `cli.py:189`. The unconstrained-owner finding holds at every one of the ten `parse_repo` call sites — none of them constrain the owner.)*
  - **That "guard" is exactly what Chunk 06 / MG5 removes** — retiring the drop-box replaces the file write with an *instructed* public-issue-create.

  **Consequence for the design (structural, changes where the policy must bind):** the three-state policy from sub-concern (1) must bind at the **adapter — the data plane** (refuse, or prompt, on a foreign-owner `--repo`), **not in skill prose**. Skill prose is the very thing being rewritten when the drop-box retires, so a prose-only guard is deleted by the same change that creates the risk. This mirrors the framework's standing MG4/G1 split: the model is in the decision, never in the data plane. Whether the wildcard `Bash(prawduct-hook backlog *)` grant should also narrow is a live sub-question, but a tools-allowlist narrowing is **not** a substitute for the adapter guard — permissions bound *who may call*, not *where the call may send*.

  **Scoping correction — so the gate does not over-block.** A consumer migrating its **own** backlog to its **own** Issues does **not** enable upstream filing; that is a different code path. The trigger is **Chunk 06's MG5 leg** (drop-box retirement / upstream-filing replacement), which is **not built** — `artifacts/build-plan-backlog-service.md:121` still carries Chunk 06 as `- [ ]`. Therefore:
  - **BLOCK:** Chunk 06's MG5 leg, and the release that carries it.
  - **DO NOT BLOCK:** a consumer backlog migration (its own repo → its own Issues), or the non-MG5 legs of Chunk 06.

  ---

  **REFINEMENT — owner, 2026-07-20: the consent problem is NOT limited to private repos, and "confidentiality / leak" understates it.** This *reframes sub-concern (1)* and corrects the framing of the escalation above (which reached for the **private**-repo case as the sharp one). Both stand as history; this is the framing to design against.

  **The public-repo risk is AGENCY AND ATTRIBUTION, not secrecy.** The adapter **inherits the session's GitHub auth** (PRD **O5**, RESOLVED 2026-07-16 — `documentation/backlog-service-prd.md:258`), so an upstream issue is filed **as the user**, under their own GitHub identity, in **someone else's public project**. The user's name is on it whether or not the content is sensitive. An agent doing that unasked is the problem *even when nothing confidential is disclosed*. A scrub that perfectly redacts secrets does not address this at all.

  **Permanence raises the consent bar rather than lowering it.** GitHub has **no ordinary issue-delete** (only a destructive admin action) and **never reuses numbers** (PRD `:217`, verified 2026-07-16). A mis-filed public issue **cannot be cleanly withdrawn** — it can only be *closed*: still public, still attributed, permanently. "It's public anyway, so it's low-stakes" inverts the actual risk.

  **This refinement had split consent into TWO obligations (1a, 1b) — the owner's 2026-07-23 decision resolves (1a) away, so only (1b) survives** (sub-concern (1) originally conflated the two):

  - **(1a) CONSENT-AT-INSTALL / DISCLOSURE — RESOLVED 2026-07-23 as NOT REQUIRED (owner decision).** There is **no** install-time opt-in and **no** separate onboarding disclosure surface. Per-report consent (1b) is the whole mechanism; the owner rejected any onboarding-time obligation. *(Superseded — kept as history: the earlier position that users must **understand at onboarding that prawduct can file upstream at all**, an obligation a per-file prompt supposedly could not satisfy, with likely surfaces `/prawduct:onboard` / the committed install reference / `project-preferences.md`. That obligation no longer exists.)*
  - **(1b) CONSENT-AT-FILE — the settled mechanism (XP5).** The three-state per-report preference from the original sub-concern (1): `always-file` / `ask-user` / `never-file`, **default `ask-user`**, honored without exception. `always-file` is **standing consent** — no one-time informed opt-in is required (the owner rejected that on 2026-07-23; a user who sets `always-file` has granted the authorization). With (1a) resolved away, this per-report consent is the entire consent mechanism.

  **DEFAULT POSITION: `ask` regardless of repo visibility.** **Public is NOT the safe-by-default case** — it is the case where the act is permanent, attributed, and visible to third parties. **Do not special-case public repos as consent-free** (a tempting simplification precisely because the MG5 replacement targets a public repo and needs no new auth).

  **Unchanged by this refinement:** the structural finding above still holds in full — the policy must bind at the **adapter (data plane)**, never in skill prose, since the prose is what the drop-box retirement rewrites.

- **[BKL-2Q7F]** `migration-scrub.md` never selects, creates, or provisions the target repo — `--repo <owner/repo>` is an unbound placeholder in six commands across four steps, and `provision` appears in no skill file
  `effort: M · impact: L · area: backlog · kind: bug · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: open · stage: ready · related: BKL-9XQ2, BKL-8V3D, BKL-5N9W, BKL-6J2X, ONB-3F9P, BKL-6M4T · refs: skills/backlog/migration-scrub.md — the six unbound `--repo <owner/repo>` placeholders, anchored by step + op rather than line number: step 0 `export`, step 1 `list`, step 3 `import` / `merge` / `status`, step 4 `counts` (verified against the tree 2026-07-20), skills/backlog/migration-scrub.md (Steps 0–5 — no repo-selection step), skills/backlog/SKILL.md:7 (allowed-tools wildcard), lib/backlog/cli.py:33,141 (the `provision` op), lib/backlog/ids.py:136-151 (parse_repo — shape-only), lib/backlog/provision.py (label taxonomy), .prawduct/artifacts/release-plan-backlog-service-golive.md (Chunk 06 ship list), artifacts/build-plan-backlog-service.md (Chunk 06 / MG4)`

  **Release-gating for v3.2.0.** Found 2026-07-20 while scoping the v3.1.1 hotfix; verified in-file the same day.

  **Anchored by step + op, not by line number (re-anchored 2026-07-20, `rev-20260720T205656Z-d302f7af`).** This item originally cited `migration-scrub.md:34,38,154,161,165,176`. Those anchors were invalidated by **the same commit that filed this item** — the Critic-warning-resolution commit that also plans the v3.1.1 hotfix (`fix(critic): resolve Critic warnings, and plan the v3.1.1 hotfix`) — whose step-2c rewrite of `migration-scrub.md` inserted ~11 net lines above them (17 added / 6 removed); the placeholders now sit at 34, 38, 165, 172, 176, 187. Rather than restate the new numbers (which the fix for this very item will move again, since the fix inserts a repo-selection step at the top of the runbook), the refs now name **step + op**. Same reason OBS-7M4D and CRT-8Q6R were re-anchored: a line number in a backlog item is a claim about a file the item exists to change, so it is stale the moment the work starts. The count (six) and the step/op mapping were re-verified against the tree, not carried over from either prior number set.

  (Correction 3 — the citation above is named by commit *message*, not SHA, and here is why it moved. The paragraph originally cited that commit as `510b8b7`. **That SHA is unreachable**: `git branch -a --contains 510b8b7` returns nothing. It was orphaned by a `git commit --amend` that rewrote it as `8b0bea1` — identical tree, message rewritten to add the release-plan provenance. The reflog dates the sequence precisely: `510b8b7` committed 14:56:23, amended to `8b0bea1` at 15:08:29, and the correction commit carrying the `510b8b7` citation landed at 15:08:47 — **eighteen seconds after its own reference was orphaned**. This is the **fifth** instance on branch `fix/archive-scope-preservation-claim` of a claim that was true when drafted and false when committed, and the first **caused by the branch's own remediation**: the amend that invalidated the SHA was part of the same correction pass that recorded it. The structural lesson is narrower than instances 1–4's *correcting a claim is authoring a claim*: **a short SHA on an unpushed branch is an ephemeral reference by construction.** This branch has no upstream, so every SHA on it is provisional — an amend or rebase rewrites it. (Corrected 2026-07-20, `rev-20260720T212124Z-9827ad5a`: this paragraph originally predicted that `8b0bea1` "will itself dangle the moment this branch merges." That is **wrong under this project's configured merge strategy** — `.prawduct/artifacts/project-preferences.md:48` sets *merge commit* (`gh pr merge --merge`, "do not squash"), which preserves the commit on `develop`. The dangle-on-merge risk applies only to squash- or rebase-merge; the amend/rebase-on-branch risk that orphaned `510b8b7` is real regardless.) Prefer naming a commit by its message or its role; use a SHA only where a runnable command needs one, and expect it to rot.)

  **The gap.** `skills/backlog/migration-scrub.md` is the runbook an owner follows to move a markdown backlog onto GitHub Issues. It has **no step that selects, creates, or provisions the target repo.** `--repo <owner/repo>` appears as a bare placeholder in six instructions (`export` step 0, `list` step 1, `import` step 3, `merge` step 3, `status` step 3, `counts` step 4) with nothing upstream that binds it. The `provision` op — which installs the label taxonomy and is a real subcommand (`lib/backlog/cli.py:33`, dispatched at `:141`) — appears in **no skill file at all** (grep over `skills/` returns only `provisional_id` in `adapter-mode.md`). So the runbook tells the model to migrate into a repo it was never told how to choose, against a taxonomy it was never told to install.

  **Why this is severe rather than cosmetic — three failures compose.** (a) The placeholder is unbound, so the natural inference is the current repo's git remote. (b) `skills/backlog/SKILL.md:7` grants `Bash(prawduct-hook backlog *)` — a **wildcard** over every adapter op including `import` (see BKL-5N9W). (c) `--repo` is **shape-validated only**: `ids.parse_repo` (`lib/backlog/ids.py:136-151`) checks two clean segments and nothing else — no allowlist, no owner constraint, no same-repo check, at any of its ten call sites (established in BKL-9XQ2). Together: a scrub run can write **100–250 real issues into a real repo** that nobody confirmed, and GitHub has no ordinary issue-delete and never reuses numbers (PRD `:217`) — so the mistake is not cleanly reversible.

  **Scope note — this is a distinct blast radius from BKL-9XQ2.** BKL-9XQ2's scoping correction explicitly says a consumer migrating *its own* backlog to *its own* Issues is not blocked, because that path does not enable upstream filing. That correction stands: this item is **not** an upstream-filing leak. It is the *same* own-repo migration path failing for a different reason — the target is never pinned, so "its own Issues" is an assumption the runbook never checks.

  Fix-shape (needs design, not just prose): (1) an explicit **target-repo selection + owner confirmation** step at the top of the runbook, recorded to `backlog_service_repo` before any adapter call; (2) a **provisioning** step invoking `provision` for the label taxonomy (this is the scrub-side sibling of ONB-3F9P's onboard/doctor gap — resolve them together so provisioning has exactly one owner per entry path); (3) every subsequent step reads the *bound* repo rather than re-templating a placeholder. Consider whether the durable guard belongs at the adapter (refuse a `--repo` that does not match a recorded `backlog_service_repo` without explicit confirmation) — same structural argument BKL-9XQ2 makes: a prose-only guard sits in the file being rewritten. Governance-protected (`skills/`) → full Critic + PR review.

- **[BKL-8V3D]** `adapter-mode.md:96` promises the model an `--apply`/dry-run safety contract that does not exist — zero occurrences in `lib/backlog/`
  `effort: S · impact: L · area: backlog · kind: bug · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: open · stage: ready · related: BKL-2Q7F, BKL-5N9W, BKL-6J2X, BKL-9XQ2, BKL-4Z7M, BKL-6M4T · refs: skills/backlog/adapter-mode.md:96 (the false claim), lib/backlog/ (grep for `--apply`/`--dry-run`/`dry_run` → 0 hits), lib/backlog/cli.py, lib/backlog/migrate.py, .prawduct/artifacts/release-plan-backlog-service-golive.md (Chunk 06 ship list)`

  **Release-gating for v3.2.0.** Found 2026-07-20 while scoping the v3.1.1 hotfix.

  `skills/backlog/adapter-mode.md:96` tells the model, in its Write-operations section, that "mutations follow the adapter's own `--apply`/dry-run and crash-safety contracts (you never invent a mutation path)." **`--apply`, `--dry-run` and `dry_run` have zero occurrences anywhere in `lib/backlog/`** (verified by grep 2026-07-20). The reassurance is fabricated: there is no dry-run mode to fall back on, and the sentence's practical effect is to lower the model's caution at exactly the moment it is about to make an irreversible GitHub write.

  **This is the same defect class as the `--archive-scope open` backup claim just fixed** (see BKL-4Z7M and the `fix/archive-scope-preservation-claim` branch): prose asserting a safety property the code does not implement, read by an agent that has no cheap way to falsify it. That class is worth naming as a recurring failure mode — *false-reassuring claim in an instruction surface* — because both instances were found by reading the code against the prose, not by any test.

  **Compounding:** this sits directly on the migration path. A model running the scrub (BKL-2Q7F) with a wildcard adapter grant (BKL-5N9W) and an unbound `--repo` is *told* it is protected by a dry-run contract that isn't there.

  Fix-shape — two legitimate resolutions, pick deliberately: (a) **delete the claim** and replace it with what is actually true (mutations are immediate and, for issue creation, not cleanly reversible — MG1); or (b) **build** a real preview/`--dry-run` path on the mutating ops and keep the sentence. (a) is the correct v3.2.0 fix; (b) is a candidate follow-on. Do not paper over it by softening the wording while leaving a safety implication. Also worth a guard: a test that pins instruction-surface claims about adapter flags to flags the CLI actually parses. Governance-protected (`skills/`) → full Critic + PR review.

- **[BKL-5N9W]** `skills/backlog/SKILL.md` pairs `disable-model-invocation: false` with a wildcard `Bash(prawduct-hook backlog *)` grant — narrow it to the ops the skill drives
  `effort: S · impact: L · area: backlog · kind: task · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: open · stage: ready · related: BKL-2Q7F, BKL-8V3D, BKL-6J2X, BKL-9XQ2, BKL-3W6K, ONB-3F9P, JNT-4R2M · refs: skills/backlog/SKILL.md:5 (disable-model-invocation: false), skills/backlog/SKILL.md:7 (the wildcard grant, both invocation forms), lib/backlog/cli.py:33 (the op set — includes import/merge/provision/reconcile-labels), skills/backlog/adapter-mode.md (the ops the skill actually drives), skills/backlog/migration-scrub.md (scrub ops), CRT-2M5P (the read-only-git precedent for narrowing a wildcard grant)`

  **Release-gating for v3.2.0.** Found 2026-07-20 while scoping the v3.1.1 hotfix.

  `skills/backlog/SKILL.md` carries `disable-model-invocation: false` (the model may invoke this skill on its own initiative) **and**, since BKL-3W6K, its first-ever Bash grant — `Bash(prawduct-hook backlog *)` plus the `python3 bin/…` self-hosted form. That grant is a **wildcard over the entire adapter op set** (`lib/backlog/cli.py:33`), which includes the high-consequence ops the everyday skill never needs: `import` (bulk-creates 100–250 issues), `merge`, `provision`, `reconcile-labels`. The everyday path (`add`/`list`/`pick`/`update`/`find`) needs `file`, `list`, `get`, `pick`, `update`, `status`, `claim`, `unclaim`, `counts` — a much smaller set.

  Narrow the grant to the ops the skill actually drives, in **both** invocation forms (the dual-form rule from JNT-4R2M — landing only the bare form leaves the self-hosted path ungranted). Decide explicitly where the scrub's ops (`import`/`merge`/`provision`) live: they belong to the one-shot, owner-confirmed migration, so either scope them to a separate surface or gate them behind the confirmation step BKL-2Q7F adds. Precedent for this shape is CRT-2M5P (the Critic's `Bash(git *)` → explicit read-only verb list) — including its caveat that a skill `allowed-tools` list may be a no-prompt allow-list rather than a hard cap (CRT-9V4T), so **this narrowing is defense-in-depth, not the primary guard**. Per BKL-9XQ2's structural finding, a tools-allowlist narrowing is **not** a substitute for an adapter-side target guard: permissions bound *who may call*, not *where the call may send*. Pin the resulting list with a metadata test. Governance-protected (`skills/`) → full Critic + PR review.

- **[BKL-6J2X]** Hold the `backlog-service-migration-required` advisory — a `warn` that fires in every un-migrated repo and routes the whole fleet into an unproven migration path
  `effort: S · impact: L · area: backlog · kind: task · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: open · stage: ready · related: BKL-2Q7F, BKL-8V3D, BKL-5N9W, BKL-9XQ2, BKL-6M4T · refs: lib/backlog_probes.py:277-291 (the advisory — type, recommended_action `/prawduct:backlog scrub`, priority `warn`), lib/backlog_probes.py:371 (registration), skills/backlog/migration-scrub.md:9-14 (the runbook's own statement that this advisory is what routes repos here), documentation/backlog-service-requirements.md (GV7), .prawduct/artifacts/release-plan-backlog-service-golive.md (Chunk 06 ship list)`

  **Release-gating for v3.2.0 — this is the amplifier that turns the other three into a fleet-wide event.**

  `probe_migration_required` (`lib/backlog_probes.py:277`) emits a **`warn`** advisory in **every** repo that has a structured `.prawduct/backlog.md` with pending items and no `backlog_service_repo` — i.e. every un-migrated consumer, every session — with `recommended_action: "/prawduct:backlog scrub"`. `migration-scrub.md:9-14` confirms the coupling from the other side ("The session-start `backlog-service-migration-required` advisory (GV7) is what nudges an un-migrated repo here").

  So on the day v3.2.0 ships, every consuming repo is told at session start to run the scrub — and the scrub is the runbook with no target-repo selection or provisioning step (BKL-2Q7F), citing a safety contract that does not exist (BKL-8V3D), under a wildcard adapter grant (BKL-5N9W). Individually those are three defects in one runbook; combined with a fleet-wide `warn` they are an **automated route from every repo into an irreversible, unpinned bulk write**.

  Requirement: **the advisory must not ship until the migration path is owner-ready and proven.** Concretely — do not enable it in a release until (i) BKL-2Q7F, BKL-8V3D, BKL-5N9W are resolved, and (ii) the path has been proven on at least one real end-to-end run (prawduct's own migration, BKL-6M4T, is the natural proof case). Options for v3.2.0, in preference order: (a) hold the advisory out of the release (keep the probe, don't register/emit it); (b) demote to `info` **and** rewrite `recommended_action` so it does not name a runnable command until the path is ready. Note the ordering constraint: prawduct's own migration is itself gated on part (b) of BKL-6X5D, so the proof run is not immediately available — plan for (a). Whatever is chosen, record it as a release-plan decision rather than leaving the probe's default to decide.

- **[CRT-2Q6D]** Dangling docstring reference — `lib/critic_mode.py:261` still cites `_verify_resolutions_gate_check`, deleted in the kernel-v3 cutover
  `effort: S · impact: S · area: critic · source: critic · added: 2026-07-19 · status: open · stage: ready · related: CRT-8H3R, CRT-5D8Q · refs: lib/critic_mode.py:261`

  Found during the 2026-07-19 stale-branch salvage sweep (verified against develop, not inferred). The docstring at `lib/critic_mode.py:261` names `_verify_resolutions_gate_check` as its mirror; that function was DELETED in the kernel-v3 cutover and is asserted-absent by a stays-deleted pin (`tests/test_cumulative_gate.py:419-431`). Pure documentation drift — no behavior depends on it — but it points a reader at machinery that no longer exists, in the exact function (rule 1) that CRT-8H3R will edit. Fix-shape: repoint the docstring at the surviving mechanism (composed tree-keyed coverage via `lib/coverage_algebra.coverage_verdict`, or `critic_consolidate._prior_review_fact`), or drop the mirror clause. Cheapest to land as a rider on CRT-8H3R rather than standalone. (critic — salvage sweep)

- **[PR-4V2N]** `skills/pr/SKILL.md:47` self-contradicts on which steps a doc-only PR skips — Step 1c is both skipped and reached
  `effort: S · impact: M · area: pr · source: critic · added: 2026-07-19 · status: open · stage: ready · related: COV-2P7F, PR-7T2K · refs: skills/pr/SKILL.md:47 (doc-only exit-0 branch), skills/pr/SKILL.md:59 (Step 1c change-log STOP), lib/coverage.py:272`

  Found during the 2026-07-19 stale-branch salvage sweep. On a `check-pr-doc-only` exit 0, `skills/pr/SKILL.md:47` tells the agent to "Skip Steps 2, 2b, 3, and 4" — a list that does NOT include Step 1c — and then to "jump straight to Step 5", which DOES skip 1c. The two halves of one sentence disagree, so whether a doc-only PR actually runs the change-log entry gate depends on which half the model happens to follow. Behavioral, not cosmetic: Step 1c is a STOP, and it is exactly the gate COV-2P7F shows is broken for `.prawduct/`-only branches — so this ambiguity decides whether that defect is even reachable, and makes the failure non-deterministic across runs. Fix-shape: state one rule (either "skip 2, 2b, 3, 4 and run 1c" or "jump to Step 5"), and make the skip-list and the jump target agree. Resolve alongside the COV-2P7F one-liner — together they make doc-only PR behavior deterministic. Governance-protected (skills/pr) → full Critic + PR review. (critic — salvage sweep)

- **[STH-2N6J]** VERIFY INTENT: `session_changes_all_non_judgeable` returns False for a metadata-ONLY session, so the reflection-gate label loses its doc-only carveout
  `effort: S · impact: S · area: stop-hook · source: critic · added: 2026-07-19 · status: open · stage: research · related: COV-6T3P, COV-2P7F · refs: lib/gates.py:514-533 (session_changes_all_non_judgeable, the `if not non_metadata: return False` early exit), bin/prawduct-hook:1135 (reflection-gate label)`

  **Flagged during the 2026-07-19 salvage sweep, NOT asserted as a defect — the point of this item is to determine intent before anyone "fixes" it.** `gates.session_changes_all_non_judgeable` (`lib/gates.py:514-533`) returns False when EVERY session-changed file is metadata, via the `if not non_metadata: return False` early exit. Read literally that is inverted: a session that changed only metadata is the *most* doc-only session possible, yet it does not get the doc-only carveout. The Critic gate itself is unaffected (`session_review_verdict` composes free edges independently), but the reflection-gate label at `bin/prawduct-hook:1135` inherits the result. The early exit may well be deliberate — "no non-metadata files at all" can reasonably mean "nothing to reason about, don't claim a carveout" — which is why this is `stage: research`: read the function's history and its callers, decide whether the early exit is intentional, and then either document the intent in the docstring (likely outcome) or file the behavior change. Do not change behavior before answering that. (critic — salvage sweep)

- **[STH-7W9K]** Skill/subagent forks silently write `.prawduct/` state to the launch dir instead of a mid-session-entered worktree (cross-worktree pollution)
  `effort: M · impact: L · area: worktree · source: user · added: 2026-07-16 · reviewed: 2026-07-19 · status: open · stage: requirements · related: CRT-6W2N, STH-4K7N, STH-3R8K, CRT-3X9D · refs: bin/prawduct-hook (get_project_dir), lib/gitstate.py (resolve_project_dir), skills (fork skills that mutate .prawduct/ — backlog/advisory/operator-verification), methodology/building.md (mid-cycle worktree-entry edge), .prawduct/learnings.md (companion rule — "A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir …")`

  Recurring pain in both dogfooding and adopter projects. When a session ENTERS a git worktree mid-session (harness `EnterWorktree`, not launched there), a `/prawduct:*` skill invoked as a fork resolves the project dir to the LAUNCH directory (`CLAUDE_PROJECT_DIR`), not the session's active worktree — and silently writes `.prawduct/` state to the wrong working copy. Observed 2026-07-16: while building in a worktree, `/prawduct:backlog add` filed the new item into the PRIMARY checkout's `.prawduct/backlog.md` (a *different* active worktree, mid-build on another branch), reporting success. Main-loop `prawduct-hook` calls from the same session resolved CORRECTLY to the worktree (STH-4K7N's cwd-based `resolve_project_dir` works because the Bash tool's cwd is the worktree); the FORK did not — its cwd/`CLAUDE_PROJECT_DIR` is pinned to the launch dir, so it never reaches the worktree branch of the resolver.

  Impact: (a) state lands on the wrong branch and misses the intended PR; (b) CROSS-WORKTREE POLLUTION — the write dirties another active worktree's WIP, corrupting that branch's diff / Critic / PR; (c) SILENT — the skill reports success against the wrong path, no error; (d) hits adopters who mandate worktrees, not just this repo. Distinct from CRT-6W2N (its reconciliation assumes a session run *entirely* inside one worktree — this is the mid-session-ENTRY + FORK gap) and STH-4K7N (which fixed the main-loop resolver via cwd, but forks don't inherit the worktree cwd).

  Adopter corroboration (discodon, 2026-07-15 — SCH-2QW9 dedup note): same class, independently hit in a product repo. Item `ENT-T8QN` was filed into the `engine-drift-identity` worktree's `backlog.md` (branch `fix/engine-drift-event-metadata`) and diverged from `main` as a near-duplicate of the canonical `SCH-2QW9`; reconciliation required manually REVERTING that worktree's `backlog.md` ("so main solely owns the backlog") and hand-merging its material into the main-branch item — the same revert+relocate workaround the dogfooding evidence above describes. This generalizes the root cause beyond the fork-resolution bug: `.prawduct/backlog.md` is a per-working-copy file, so ANY worktree activity (a fork mis-targeting it, or a session legitimately filing into a worktree that then diverges from main) produces split/misplaced backlog state that only manual reconciliation resolves. Implication: the fix needs a coherent worktree-backlog OWNERSHIP story (e.g. main solely owns the backlog with a defined port/merge path, or a backlog store that isn't a per-working-copy flat file), not just the fork-resolution guard. This ownership question is the same tension the backlog-service (GitHub Issues backend) is being built to resolve — a single server-side backlog store sidesteps per-worktree divergence entirely; capture that as a motivating data point for the service.

  Fix-shape (menu, needs a design pass — which leg prawduct owns vs. the harness): (1) skill forks that mutate `.prawduct/` must be told the session's active worktree — thread an explicit project dir (env or `--project-dir`) from the main agent into the skill's `prawduct-hook` calls rather than re-resolving from a pinned launch dir; (2) a write-time GUARD — a `.prawduct/`-mutating hook command detects when its resolved project dir belongs to a different worktree than the session's active one and refuses/warns loudly instead of writing silently (generalizes the critic-session-guard invariant CRT-3X9D: a fork must not mutate a different worktree's state); (3) harness-side, `EnterWorktree` should update the project dir for subsequently-spawned forks (likely upstream Claude Code, noted not-purely-a-prawduct-bug, cf. CRT-6W2N's gitflow base-ref note); (4) document the safe pattern prominently — LAUNCH (or `/clear`) the session in the worktree so the project dir is the worktree from the start (building.md notes this edge for SessionStart markers but not the fork WRITE-pollution consequence). Governance-protected (hooks/skills/state resolution) → full Critic + PR review. (user report — surfaced during backlog-service worktree dogfooding)

  **Salvage note (2026-07-19).** This item was itself stranded by the very defect it describes: it was filed on branch `worktree-backlog-service-plan`, whose worktree was later removed, so it never reached this checkout. Re-filed here verbatim with its original id. Filing it also RESOLVES A DANGLING REFERENCE: `.prawduct/learnings.md` already carries the companion durable rule ("A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir, not a worktree the session ENTERED mid-session…") and closes with "Full detail + fix-shape in [[backlog]] STH-7W9K" — a pointer that had no target in this repo until now. Verified 2026-07-19 against `.prawduct/learnings.md`.

- **[VWS-2W6H]** regen-views plan-discovery mis-classifies scope-tagged design artifacts as build plans
  `effort: S · impact: M · area: views · kind: bug · source: builder · added: 2026-07-16 · reviewed: 2026-07-21 · status: open · stage: ready · related: REL-3B7Q, VWS-4T9P · refs: lib/views.py:532 (build_scope_to_plan_map), lib/views.py:588 (diagnose_scope_plan_coverage), lib/views.py:658 (validate_chunk_roster), lib/views.py:1023 (_plan_status_results), bin/prawduct-hook:2508-2520 (cmd_regen_views fatal-diagnostics block)`

  ROOT DEFECT (unchanged and live): `build_scope_to_plan_map`, `diagnose_scope_plan_coverage`, and `validate_chunk_roster` in lib/views.py all glob `artifacts/*.md` and treat ANY file whose frontmatter declares a `scope:` as a build plan. There is no `artifact: build-plan` filter. Design artifacts (data-model, api-contract, security-model, api-notes) legitimately carry `scope:` for traceability — as the backlog-service Chunk 01 artifacts do — and are therefore indistinguishable from plans to plan-discovery. Fix: filter plan-discovery to files whose frontmatter declares `artifact: build-plan`.

  BEHAVIOR AS OF 2026-07-19 (re-verified in code; the original filing described only the first mode, and a later triage note wrongly claimed the loud error had been replaced by a silent pick — BOTH modes are live, on different inputs):

  1. LOUD (design artifact declares the SAME scope as its build plan — the originally-observed case). `diagnose_scope_plan_coverage` (lib/views.py:588) scans the glob unconditionally and emits `duplicate scope=… also declares it (keeping …); one plan is malformed.` `cmd_regen_views` (bin/prawduct-hook:2508-2520) treats that diagnostic as FATAL — prints `ERROR:`, `return 2`, "no views written" — so the whole regen aborts and Status derivation is disabled for the branch. This is still exactly what happens; the original item text remains accurate for this input.

  2. SILENT (design artifact's scope is NOT duplicated by a real plan — e.g. the actual build plan has no frontmatter `scope:`, or is retired/absent). `build_scope_to_plan_map` (lib/views.py:532) now dedupes by "first by sorted filename wins", silently, so a design artifact can also outrank the real plan by name alone (`api-contract-backlog-service.md` sorts before `build-plan-backlog-service.md`). With no duplicate to trip the fatal diagnostic, the map silently binds the scope to a NON-plan file and three things go wrong quietly: `diagnose_scope_plan_coverage`'s "unreleased scope with no plan file" check is FALSELY SATISFIED (the design artifact stands in for the missing plan); `validate_chunk_roster` (lib/views.py:658) reads that file's `## Status` section, finds an empty roster, and emits misdirected "these IDs will never flip a checkbox" errors naming the wrong file; and `_plan_status_results` (lib/views.py:1050) selects the design artifact as a plan to regenerate. Both modes have the same one-line fix (the `artifact: build-plan` filter). (builder — backlog-service Chunk 02; re-verified 2026-07-19)

- **[BLD-9H2M]** `verify-chunk-refs` never detects a SOFT-WRAPPED `new` qualifier — the regex is applied per line, so `… new\n  \`path\`` is not exempted and the created file reports as a missing ref
  `effort: S · impact: M · area: build-plan · kind: bug · source: builder · added: 2026-07-19 · reviewed: 2026-07-19 · status: open · stage: ready · related: BLD-8R3T, BLD-5N7C, BLD-6T4R, BLD-4V7Q, BLD-3M7K, BLD-4K7P, BLD-2R9X, BLD-8F2Q, BLD-5J8N, BLD-4Q8W · refs: lib/buildplan_refs.py (_BUILD_PLAN_NEW_QUALIFIER_RE, the forward_refs comprehension in _parse_build_plan_chunk_refs), .prawduct/artifacts/build-plan-backlog-service.md (chunk 01 Deliverables), skills/critic/review-protocol.md (Build-plan ref drift goal), .prawduct/cross-cutting-concerns.md`

  Third variant in the `verify-chunk-refs` false-positive family, surfaced during the
  `verify-chunk-refs-token-fixes` corpus check (2026-07-19) and deliberately filed rather than
  fixed — out of scope for both BLD-4V7Q and BLD-6T4R, which shipped in that same change.

  `_BUILD_PLAN_NEW_QUALIFIER_RE` (`\bnew\s+\`([^\`\s]+)\``) has an `\s+` that *could* span a
  newline, but it is matched against ONE LINE AT A TIME — the `forward_refs` comprehension in
  `_parse_build_plan_chunk_refs` iterates `section_lines` and calls `.finditer(section_line)`. So a
  declaration that soft-wraps between the word `new` and its backticked path is never collected
  into the forward-ref set at all. BLD-6T4R widened the exemption's REACH (line-local → chunk-scoped
  per path); this is the separate problem that the declaration is never RECOGNIZED, so widening the
  reach cannot help — nothing gets into the set to widen. (A fourth variant, **BLD-8R3T**, concerns
  that same widened exemption in the opposite direction: it never expires when the chunk closes.)

  Live instance: `.prawduct/artifacts/build-plan-backlog-service.md` chunk 01 Deliverables wraps
  twice — line 345 ends in `new` with `` `lib/backlog/encode.py` `` opening line 346, which itself
  ends in `new` with `` `lib/backlog/provision.py` `` opening line 347. Both are files the chunk
  CREATES, and both are existence-checked and reported `missing-ref` whenever they aren't yet on
  disk. Same false-negative-habituation risk as the rest of the family: a checker that cries wolf on
  correctly-authored plans trains reviewers to dismiss it — and this checker IS a gate, so that
  habituation has teeth (see the urgency note below).

  Fix-shape: collect the `new` qualifier over the JOINED chunk-section text (or with an explicit
  next-line lookahead) instead of per line, then feed the results through `_ref_path_part` exactly
  as the current comprehension does — the exemption set is already chunk-scoped and per-path, so
  only the collection pass changes. Guard the widening: `\s+` across a newline must not let a
  sentence that merely ENDS in the word "new" capture the first backticked token of the next line
  (constrain to a single newline plus indent, or require the match to stay inside one list item).
  **Urgency correction (2026-07-19).** This item's first draft inherited BLD-6T4R's "low urgency —
  `verify-chunk-refs` is not wired into any gate" line. That claim is **stale and wrong**, verified
  against the tree today: `skills/critic/review-protocol.md:71` makes it a Critic goal — "run
  `prawduct-hook verify-chunk-refs` — both `missing-ref:` (deliverable absent) and `cannot-verify:`
  (gate couldn't run) exits are **BLOCKING**" — and `.prawduct/cross-cutting-concerns.md:36` records
  it as the Goal-2 build-plan-ref-drift gate. `skills/critic/SKILL.md` allow-lists the command so the
  Critic fork can run it. It is not wired into a *hook* directly, but a BLOCKING Critic goal IS a
  gate with teeth: the stop hook refuses session end while blocking findings are unresolved, so a
  false `missing-ref:` on a correctly-authored plan blocks the chunk AND the session until someone
  dismisses it — which is precisely the false-negative habituation this whole family is about. Urgency accordingly is **not** low; the live instance
  below fires on an in-flight plan. (Note `.prawduct/cross-cutting-concerns.md:36` also claimed
  `building.md: builder runs verify-chunk-refs before marking chunk done`, but `methodology/` carries
  no such instruction — a separate doc-drift, since corrected in that cell. Whether building.md
  *should* carry the step is now tracked as **BLD-4Q8W**, not by this item.)
  (builder — verify-chunk-refs-token-fixes)

- **[BLD-8R3T]** `verify-chunk-refs`' chunk-scoped `new` exemption never expires — it is unconditional on chunk completion, so a SHIPPED chunk's declared-new deliverable is never existence-checked
  `effort: S · impact: M · area: build-plan · kind: bug · source: critic · added: 2026-07-19 · reviewed: 2026-07-26 · status: open · stage: ready · related: BLD-5N7C, BLD-9H2M, BLD-6T4R, BLD-4V7Q, BLD-7K3Q, CRT-7B4M · refs: lib/buildplan_refs.py (the forward_refs set in _parse_build_plan_chunk_refs, _BUILD_PLAN_NEW_QUALIFIER_RE, _ref_path_part), lib/buildplan_refs.py:301 (resolve_chunk_progress — the ONE progress answer) + :218 (_git_aware_progress — the git-derived completion signal), lib/gates.py:744 (_has_active_build_plan_file — the deliberate checkbox precedent), .prawduct/change-log.md (2026-07-19 "verify-chunk-refs stops flagging path:line citations…"), skills/critic/review-protocol.md (Build-plan ref drift goal)`

  Contract gap in BLD-6T4R's shipped fix, surfaced by the Critic on that change's change-log draft
  and deliberately filed rather than folded in. The `new` qualifier means *"this chunk will CREATE
  this file"* — a forward reference, correctly exempt from the existence check **while the chunk is
  being built**. The shipped exemption is per-path and per-chunk but **unconditional with respect to
  chunk completion**: once a chunk is `[x]` in the plan's `## Status`, the promise has come due, and a
  declared-new deliverable that is still absent from disk is a REAL signal — the chunk shipped
  without its deliverable, or the plan text has drifted off a rename. The exemption silences that
  signal permanently.

  Concrete cost, already paid: the corpus verification for BLD-6T4R found exactly two such refs
  (`lib/backlog.py` and `methodology/agent-stance.md`, both in `[x]` chunks, neither on disk). They
  were TRUE positives, caught only incidentally because those chunks happened to re-reference the
  path — the very re-reference BLD-6T4R's fix suppresses. Post-fix, nothing surfaces them. Filed
  separately as **BLD-5N7C**; this item is the systemic leg, that one the two instances.

  Fix-shape: gate the forward-ref exemption on the chunk still being OPEN. `lib/buildplan_refs.py`
  already parses the plan's `## Status` checkbox roster (`lib/views.py` `CHUNK_LINE_RE` and the
  chunk-item primitives), so the checked/unchecked state of the chunk under verification is
  reachable — apply the `forward_refs` set only when the chunk is unchecked, and existence-check
  `new`-declared paths normally once it is checked. Watch two edges before building: (a) checkboxes
  are a DERIVED view that stays `[ ]` on a feature branch until release (see the backlog-rework
  plan's own Status comment and CRT-7B4M), so "unchecked" is not reliably "in flight" mid-branch —
  fail toward the exemption there rather than manufacturing false positives on the branch that is
  legitimately creating the file; (b) BLD-9H2M must land first or alongside, since a soft-wrapped
  `new` never enters the set at all, and re-arming the check on closed chunks would turn that
  false-negative into a false POSITIVE on correctly-authored plans. Governance-protected
  (`lib/buildplan_refs.py` feeds a BLOCKING Critic goal) → full Critic + PR review.

  **Trigger surface is wider than "declared deliverable" (2026-07-19, critic R-4 on
  `verify-chunk-refs-token-fixes`).** The framing above says the exemption covers a chunk's *declared*
  deliverable. The code is looser: `_BUILD_PLAN_NEW_QUALIFIER_RE` (`lib/buildplan_refs.py:207`,
  `` \bnew\s+`([^`\s]+)` ``) matches the word `new` before ANY backticked path anywhere in the chunk
  section, adjectival prose included — "the new `lib/foo.py` guard", "a new `path` helper" — not just
  "creates a new X" declarations. Under the retired line-local rule an incidental adjective cost one
  occurrence; chunk-scoped AND never-expiring, it can silence every reference to a genuinely-drifted
  path for the life of the plan. Scanning every `.prawduct/artifacts/*build-plan*.md` for
  `` (a|the|to|into|and) new `<path>` `` found only two hits, both genuine creation declarations
  (`lib/backlog/migrate.py`, `skills/migrate/`) — so this is a widened trigger surface, not a live
  defect today. Fold it into the fix rather than gating on chunk state alone: constrain the qualifier's
  SHAPE at the same time (e.g. require the match to sit inside a Deliverables list item), so the
  re-armed check keys off declarations instead of any prose use of the word.

  **Sibling NOTE disposition — three-level `path:line:col:extra` (same review, critic R-5).**
  Considered and left unfiled by design; the record lives in **BLD-4V7Q**'s archive note, which owns
  `_BUILD_PLAN_LINE_SUFFIX_RE`. Summary: the suffix regex is `$`-anchored over at most two
  numeric groups, so `lib/foo.py:1:2:3` still half-strips to `lib/foo.py:1`; no corpus instance exists
  and no citation convention here uses three levels, so it stays a near-miss rather than an open item.
  Noted here only because the two findings arrived together — this item does not carry that work.

  **PREMISE MAY HAVE SHIFTED — re-derive the fix-shape before building (2026-07-26, Chunk 02 Critic
  cross-check C-B3 on `session-handoff-continuity`).** Status deliberately unchanged; this is an
  annotation, not a reopen or a resolution. This item's whole behaviour — the `new` exemption is
  unconditional on chunk completion — was written when "complete" meant exactly one thing: the
  `## Status` checkbox. It no longer does. **BLD-7K3Q** shipped in `session-handoff-continuity`
  Chunk 02 and changed how "which chunk is current" and "which chunks are complete" are derived for
  `verify-chunk-refs` itself: every consumer now resolves through
  `lib/buildplan_refs.py:301 resolve_chunk_progress`, which prefers a **git-derived** reading
  (`:218 _git_aware_progress`) on a `views_enabled` branch that is ahead of its base — there a chunk
  counts complete when its box is `[x]` **OR** its id appears in a commit subject since base. So a
  chunk can read as complete on the branch long before the release flips its box.

  What this does to the fix-shape above: the fix-shape says "apply the `forward_refs` set only when
  the chunk is unchecked," and its edge (a) fails toward the exemption precisely *because*
  checkboxes stay `[ ]` mid-branch. That edge is no longer the only reading available — the
  git-derived signal is exactly the "is this chunk actually done on this branch" answer edge (a)
  lacked. Whoever picks this up should **re-derive against `resolve_chunk_progress`, not against
  "first unchecked box,"** and decide *deliberately* which completion the exemption expires on:
  the git-derived completion (exemption dies when the chunk's commit lands), the checkbox
  completion (exemption dies only at release), or neither. That is a judgment call with a live
  precedent worth reading first: `lib/gates.py:744 _has_active_build_plan_file` deliberately kept
  the **checkbox** reading and documents why — a chunk's last commit lands BEFORE its Critic pass
  and its reflection, so routing that gate through the git signal switched the blocking gates off
  during the complete-but-unmerged window. The same "committed ≠ finished" asymmetry may or may not
  apply to a deliverable's existence check (a declared-new file arguably *does* exist by the time
  its chunk is committed) — that difference is the actual decision, and it should be made on
  purpose rather than inherited.

  Raised by the Chunk 02 Critic's C-B3 cross-check, which noted five open `area:build-plan` items
  sit on this same gate surface (BLD-9H2M, BLD-8R3T, BLD-5N7C, BLD-4Q8W, BLD-5V8F) and found this
  one to be the only member whose premise actually moved. The others are unaffected by Chunk 02.
  (critic — session-handoff-continuity Chunk 02)

  (critic — verify-chunk-refs-token-fixes)

- **[BLD-5N7C]** Two stale shipped-deliverable paths in closed chunks — `lib/backlog.py` and `methodology/agent-stance.md` are declared `new` in `[x]` chunks but no longer exist
  `effort: S · impact: S · area: build-plan · kind: task · source: critic · added: 2026-07-19 · reviewed: 2026-07-19 · status: open · stage: ready · related: BLD-8R3T, BLD-6T4R · refs: .prawduct/artifacts/build-plan-backlog-rework.md (Chunk 01 Deliverables, and the Status/Context lines naming lib/backlog.py), .prawduct/artifacts/build-plan-rigor-and-stance.md (Chunk 02, ~:98/:112/:114/:117), .prawduct/change-log.md (2026-07-19 verify-chunk-refs entry)`

  The two concrete instances of **BLD-8R3T**'s systemic gap. Both were flagged `missing-ref` by
  `verify-chunk-refs` before BLD-6T4R shipped and are silenced by its chunk-scoped exemption now.
  They are **TRUE positives, not false ones** — the checker was right; the plan text is stale.
  (The change-log entry's first draft had this backwards and was corrected by the Critic; the
  archived BLD-6T4R note has been corrected to match.)

  1. `lib/backlog.py` — declared `new` in `build-plan-backlog-rework.md` Chunk 01 ("Parser
     substrate"), chunk `[x]`. The file WAS built and shipped there; it was later restructured into
     the `lib/backlog/` package by backlog-service Chunk 01 (`51f529d`, the commit that deletes it).
     The plan still names the flat module in its Deliverables, its `## Status` checkbox line, its
     Context paragraph, and Chunks 02/03/04's references.
  2. `methodology/agent-stance.md` — declared `new` in `build-plan-rigor-and-stance.md` Chunk 02,
     chunk `[x]`. Also genuinely written and shipped (`66e2fb0`, released `a930f98`/v2.0.7), then
     FOLDED into the digest + methodology guides by prose-diet Chunk 03 (`b4d569e`, released
     `10012cf`/v2.3.0). The plan still cross-references it from Deliverables
     and from the `docs/principles.md` / `skills/methodology/SKILL.md` / presence-test steps.

     *(Retracted 2026-07-19 — this bullet previously warned that "the change-log entry says 'no
     agent-stance doc was written' … it was written and later folded." No change-log entry has ever
     said that: the phrase appears nowhere in `.prawduct/change-log.md`, and `git log -S` over that
     file's whole history returns no commit that added or removed it. The 2026-07-19 entry in fact
     states the opposite and correct thing — both paths were "genuinely built, then restructured
     away," the stance doc "folded into the digest by prose-diet Chunk 03." The warning was aimed at
     a draft that the Critic had already corrected before it landed, so it sent a reader to fix text
     that was already right. Dropped rather than kept-with-a-note because a pointer at nonexistent
     text is pure misdirection; the shipped-and-later-folded fact it was defending is stated plainly
     above.)*

  So neither is a delivery failure — both are shipped plans whose deliverable paths were later
  renamed or folded, leaving the historical plan pointing at files that no longer exist. Fix-shape
  (decide which, don't do both): annotate each stale path in place with its successor — e.g.
  `lib/backlog.py` *(later restructured into `lib/backlog/`; see backlog-service Chunk 01)* — which
  keeps the plan honest as a historical record AND clears the check; or, if the project prefers
  shipped plans to be immutable history, close this by making BLD-8R3T's gate skip closed chunks
  entirely, in which case this item is a doc-accuracy nicety rather than a checker concern. Prefer
  the annotation: a reader following a shipped plan to a dead path has no signal today. Ordering:
  worth landing BEFORE BLD-8R3T re-arms the check, so re-arming does not immediately fire on two
  known-stale paths. Docs-only, no code. (critic — verify-chunk-refs-token-fixes)

- **[BLD-4Q8W]** Should `methodology/building.md` instruct builders to run `verify-chunk-refs` before marking a chunk done? — the concerns registry claimed that step; `methodology/` never carried it
  `effort: S · impact: M · area: build-plan · kind: question · source: builder · added: 2026-07-19 · status: open · stage: requirements · related: BLD-9H2M, BLD-8R3T, BLD-6T4R · refs: .prawduct/cross-cutting-concerns.md:36 (Build-plan ref drift row, builder-stage cell), methodology/building.md (chunk "Done when" / verify steps), skills/critic/review-protocol.md:71 (the BLOCKING Critic goal), bin/prawduct-hook (verify-chunk-refs)`

  Surfaced while correcting BLD-9H2M's urgency note (2026-07-19). `.prawduct/cross-cutting-concerns.md:36`
  claimed, in the builder-stage cell of the Build-plan ref drift row, that
  `building.md: builder runs verify-chunk-refs before marking chunk done`. That was **never true** —
  `methodology/` mentions `verify-chunk-refs` nowhere; the gate is Critic-run only. The registry cell
  has since been corrected to record the absence, and it names this item as the open question. So the
  *drift* is fixed; what remains is the **decision** the drift papered over.

  The question: is a builder-stage run the right coverage, or is Critic-only correct by design?
  Arguments each way, both real —
  - **For adding it.** The Critic exit is BLOCKING, so a `missing-ref:` found at review time bounces a
    chunk that was already declared done, and the stop hook then holds the session until it is
    resolved. Catching it at the builder's own "Done when" step is cheaper and shortens the loop —
    the same shift-left rationale the registry's other builder-stage cells carry.
  - **Against.** It duplicates a check the Critic already runs unconditionally, adds a step to every
    chunk for a defect class that is rare per chunk, and cuts against Independent Review (Principle 14)
    — a builder self-certifying the check the reviewer exists to run. Note also that this whole family
    (BLD-9H2M, BLD-8R3T, BLD-2R9X, BLD-3M7K, BLD-4K7P, …) is a standing stream of FALSE positives;
    putting a cry-wolf checker in the builder's hands is a habituation risk in the place where
    habituation is least recoverable.

  Not directly buildable — `stage: requirements` because the deliverable is a decision plus (if yes) a
  one-paragraph methodology edit and a registry-cell update, not code. Settle it before BLD-9H2M /
  BLD-8R3T change the checker's false-positive profile, since that profile is the main argument
  against. Whatever is decided, `.prawduct/cross-cutting-concerns.md:36` must end up matching reality
  — it is the cell that lied for the life of the row. (builder — verify-chunk-refs-token-fixes)

- **[ENV-7C4K]** `prawduct-hook` on PATH resolves to the installed plugin cache (stale version) inside framework-repo worktrees — Critic `critic-begin` silently wrote no kernel-v3 manifest until re-dispatched with repo-local `bin/prawduct-hook`
  `effort: S · impact: M · area: environments · source: reflection · added: 2026-07-16 · status: open · stage: ready · reviewed: 2026-07-19 · related: ENV-2W7K, CRT-6W2N · refs: bin/prawduct-hook, skills/critic/SKILL.md (critic-begin dispatch + SubagentStop critic-consolidate), CLAUDE.md (Critic data-plane commands)`

  Observed 2026-07-16 during the backlog-service Chunk 01 Critic run in a framework-repo
  worktree: bare `prawduct-hook` on PATH resolved to the *installed plugin cache* binary (2.3.3)
  while the worktree carries the repo-local `bin/prawduct-hook` (3.0.4 lineage). The Critic
  coordinator's `critic-begin` ran the stale binary and silently wrote no kernel-v3 dispatch
  manifest — no error, no manifest, wrong-version semantics — until the coordinator was
  re-dispatched with `bin/prawduct-hook` explicitly. Dogfooding-specific hazard: product repos
  legitimately run the plugin-cache binary; the skew bites only in the framework repo, where the
  checkout is a newer lineage than the installed plugin. Fix-shape (either or both): (a) skills/
  docs invoked inside the framework repo prefer the repo-local binary — resolve
  `bin/prawduct-hook` at the repo root ahead of PATH; (b) fail loudly on version skew — the
  invoked binary compares its self-reported version against the repo's expected lineage and
  refuses to proceed silently. A silent no-op in the review data plane is the worst failure mode
  here; loud beats clever. (reflection)

  **Recurrence — second data-plane path (observed 2026-07-16, backlog-service Chunk 01
  final review).** The same stale-binary no-op bites a *second* Critic data-plane write,
  not just `critic-begin`: the `SubagentStop`-triggered `critic-consolidate` ALSO silently
  no-ops. Bare `prawduct-hook` on the *hook's* PATH resolves to the stale 2.3.3 plugin
  cache, so the SubagentStop consolidate runs the wrong-version binary and leaves the
  review un-persisted — until a manual repo-local `./bin/prawduct-hook critic-consolidate`
  lands the fact. Consequence for the fix: it must cover BOTH data-plane writes —
  `critic-begin` (manifest write) AND the SubagentStop `critic-consolidate` — any fix
  touching only `critic-begin` is incomplete. This makes fix-shape (a) (repo-local binary
  resolution) or (b) (loud version-skew failure) need to apply on the hook invocation path
  too, not just skill/doc invocations. (reflection)

- **[CRT-3T6V]** verify-chunk-refs `cannot-verify:` vs `missing-ref:` exit-message differentiation + critic-begin bare-repo sibling-worktree guard lack direct pytest coverage
  `effort: S · impact: S · area: critic · kind: test-gap · source: critic · added: 2026-07-18 · status: open · stage: ready · related: BLD-5J8N, CRT-6W2N · refs: bin/prawduct-hook (cmd_verify_chunk_refs, cmd_critic_begin)`

  Two behaviors were manually CLI-verified during discodon-upstream-defects but have no regression test. (1) `cmd_verify_chunk_refs` differentiates its `cannot-verify:` exit message from its `missing-ref:` exit message — the distinction is untested, so a regression that collapsed the two would pass CI. (2) `cmd_critic_begin`'s bare-repo sibling-worktree `.get('branch', '?')` guard (the fallback when a sibling worktree has no branch, e.g. a detached/bare checkout) has no test exercising the missing-branch path. Both surfaces are in `bin/prawduct-hook`; add pytest coverage pinning each. Related: BLD-5J8N (chunk-HEADER parser family in cmd_verify_chunk_refs), CRT-6W2N / its Chunk 04 PDT-WT9K (the critic-begin worktree-guard work). Filed from /critic.

- **[VWS-2F9K]** regen-views `CHUNK_LINE_RE` + the `chunks=`→Status-line match still require the colon `Status` form after BLD-5J8N broadened the em-dash form elsewhere — checkboxes silently fail to flip at merge
  `effort: S · impact: M · area: views · kind: bug · source: builder · added: 2026-07-18 · reviewed: 2026-07-21 · status: open · stage: ready · related: BLD-5J8N, GOV-8N4V, VWS-4T9P · refs: lib/views.py (CHUNK_LINE_RE, collect_shipped_chunks), .prawduct/learnings-detail.md (colon-form learning)`

  After BLD-5J8N broadened `verify-chunk-refs` + `infer-critic-mode` to accept the `## Chunk N (ID) — Name` / em-dash header form, `CHUNK_LINE_RE` (lib/views.py) and the `chunks=` tag → Status-line match were NOT broadened — they still require the colon `Status` form. Consequence: a build plan whose `## Status` checkbox LINES use the em-dash/colon-less form can pass the Goal-2 + mode-inference gates yet silently fail to flip its checkboxes at merge (partial/no flip). Also the `chunks=` tag → Status-line match is literal (no leading-zero tolerance — `Chunk 1` != `Chunk 01`). Fix-shape: broaden `CHUNK_LINE_RE` to the same separator set as `buildplan_refs._CHUNK_ITEM_RE`, and decide zero-padding-tolerant matching for `chunks=`.

- **[BKL-2K8V]** pick latency ~12.4s at 209-issue scale — flat across candidates (not N+1) but 6x the NFR <2s floor; dominated by the gh-subprocess full-scan
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-17 · status: open · stage: design · related: BKL-6M4T`

  Settled live by SPIKE-S2 (2026-07-17 dry-run, ~209-issue throwaway repo). pick_latency_ms_by_candidates measured {1: 12528, 3: 12390, 5: 12380} — i.e. ~12.4s and FLAT across 1/3/5 candidates. Two reads: (a) GOOD — the ready-work fan-out is NOT N+1 (no growth with candidate count), consistent with a batched/cheap fan-out; (b) BAD — the absolute floor is ~6x the NFR <2s target, dominated by the FIXED cost of query._all_issues fetching every open issue across paginated `gh` subprocess calls (subprocess spawn + REST round-trips), not the per-candidate blocker fan-out. This SETTLES the NFR §4 PROBE-LAT open question (previously target-grade, S2-to-measure): the <2s floor is NOT met on the `gh`-subprocess path at ~200-issue scale. Resolution: the <2s floor requires the raw-HTTP/GraphQL fast-path (roadmap W1) or a scoped candidate query that avoids the full-issue-scan — not the current `gh` REST-over-subprocess path. Record the measured number into NFR §4 and re-state pick's <2s as W1-gated (or scoped-query-gated), not slice-native. Caveat (honest confidence): measured under light concurrent read load (a 4-min progress poll) and on one machine/one API-latency sample; the ~12s magnitude and flatness are robust, the exact ms is one sample.

- **[BKL-9J3F]** CC5 decoder gaps: close-as-duplicate redirect read only from block not timeline; deleted soft-facet/body-block decode silently to None
  `effort: M · impact: M · area: backlog-service · source: critic · added: 2026-07-17 · status: open · stage: design · related: BKL-4W7H, BKL-5R2K`

  Lower-priority decoder gaps found in the same CC5 trace as BKL-4W7H (captured there "so not lost"; now filed as their own item since BKL-4W7H shipped). (1) ENC-6: close-as-duplicate redirect (superseded_by) is read only from the block, never the timeline (encode.py "not yet implemented"; decode_item never calls list_timeline) → a human "close as duplicate" in the GitHub UI silently drops superseded_by (compounds with BKL-5R2K). (2) A deleted soft-facet label (e.g. impact:high) decodes to None with NO warning. (3) ENC-5(c) missing-stage advisory is unimplemented. (4) A wholesale body-block deletion yields an empty Block with no warning (silently loses id_aliases/superseded_by/claimed_at). Theme: several human-UI edits degrade silently where the decoder should warn.

- **[BKL-6X5D]** Archive window never quantified (binary `{all,open}` is the only shipped lever); Pacer doesn't meter 900 REST pts/min for the create+close archive stretch — part (b) is a **v3.2.0 release blocker** gating prawduct's own migration (A1 chose `--archive-scope all`)
  `effort: S · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-20 · status: open · stage: design · related: BKL-6M4T · refs: backlog-service-prd.md#89, backlog-service-nfr.md, .prawduct/artifacts/migration-scrub-decisions.md (decision 5 — A1 = `all`), .prawduct/artifacts/release-plan-backlog-service-golive.md (item 8 / C7-before-C4)`

  Pre-sign-off rate-budget trace. (a) Doc-coherence: PRD §8.9 and requirements ~§228 credit the "recent-shipped archive window" as "the lever that keeps the write-burst inside the ~500/hr budget," and §9 attributes the fit to the scrub — circular, and neither quantifies the window (no N-months, no formula). But the Pacer is what GUARANTEES the ceiling (it sleeps to stay at 500/hr regardless of volume); the window is a throughput/noise lever, not a ceiling lever. Latent for the 204-item dogfood (204<500, so the lever isn't even needed — never stated). Fix: re-attribute (Pacer=ceiling via pace-across-time; window=throughput/noise) and quantify the window as a throughput target; reconcile the §8.9↔§9 circular reference. (b) Pacer 900 pts/min gap (inferred arithmetic, medium): the Pacer's docstring assumes a "pure-create workload" so the 80/min content cap binds before the 900 REST-pts/min burst — but the archive import is create+close (2 writes/archive item, migrate.py:453-455), so during the archive stretch points/min ≈ 80×5 + 80×5 + reads > 900. Mitigated INCIDENTALLY by gh-subprocess latency (not designed-in; breaks with the raw-HTTP fast-path D2/W1). Fix: meter total REST points (5/write,1/read) against 900/min in the Pacer, or explicitly document the reliance on transport latency + S3 confirmation. Minor doc-vs-code: the scrub runbook suggests importing archive items already-closed to avoid create-then-close churn, but create_issue has no state field — the importer always creates-open-then-reconciles, so that optimization is unbuilt (drives the 2-writes/archive-item cost).

  **Progress (2026-07-18, owner-feedback pass):** the binary `--archive-scope {all,open}` lever now SHIPS (MG4b — `lib/backlog/{cli,migrate}.py`, honored by import + restructure-preview + the scrub runbook step 2c), and the **requirements** attribution is corrected (Pacer = ceiling via pace-across-time; the window = write-*volume*/throughput lever, not the rate ceiling), matched in migration-scrub.md + change-log. Open *as of that date*: the same re-attribution in **PRD §8.9** + the §8.9↔§9 circular reference; the window **quantification** (N-months / a throughput formula); and **part (b)** — the Pacer metering total REST points (5/write, 1/read) against 900/min for the create+close archive stretch. (Superseded by the 2026-07-20 note below — the first two of those are now closed.)

  **Part (a) CLOSED 2026-07-20** (change-log 2026-07-20, "`--archive-scope` becomes discoverable…"). Both doc-coherence legs are done. The **re-attribution** — Pacer = ceiling by pacing creates across the clock whatever the volume; archive scope = write-*volume* lever that shortens the run but does not keep it compliant — is corrected in **six documentation surfaces** (plus `apply_archive_scope`'s docstring, which taught the same mis-attribution in code): **requirements** ~§228, **PRD §8.9**, **PRD §9/NF3**, **PRD §11/S3** (:249), **NFR §3.3** (:146, the workload table's Migration-import row), and **NFR §9** (:287, the measurement-plan row). Those six took **four rounds** to surface: 2026-07-18 (requirements, owner-feedback pass); 2026-07-20 (PRD §8.9 + the docstring in the changeset, with the chunk Critic's R-3 catching **§9/NF3**, §8.9's sibling copy); then the verify-resolutions Critic's R-1 catching **NFR §3.3 + PRD §11/S3** — the two the *previous* version of this note had already declared covered under an "every surface" claim; then a *second* verify-resolutions R-1 catching **NFR §9** (:287), which read "migration burst fits after scrub." That sixth is the sharpest data point in the sequence: it was returned by the *very grep this note publishes as the pre-claim check*, in the same revision that published it — the recipe was written down and not run. The count is deliberately **not** framed as exhaustive: six is the count actually swept, not a proof that no seventh surface exists. The falsifying query, if this needs re-asserting: `grep -rn 'scrub' documentation/*.md | grep -i '500\|rate\|budget\|fit\|trim'` — run it *before* claiming coverage, not after. NFR §9 was load-bearing rather than incidental prose (it is a table of proof obligations, so its wording steers what S2 measures), so its fix is not just a re-wording: the row now states the **S2 obligation** as proving the **Pacer** holds the burst inside the content cap **measured with the scrub's volume reduction disabled (`--archive-scope all`)** — so the run proves pacing rather than a small input — and adds the open **create-then-close 900 pts/min** question (only creates are paced) as an explicit S2 target, i.e. part (b) below now has a named prover. And the **§8.9↔§9 circular reference** dissolves as a consequence: §8.9 now credits the Pacer and cites §9 for the budget, §9 credits the Pacer and cites NFR §3 — neither defers to the other for the ceiling. §8.9 also stopped describing the unbuilt "recent-shipped window" as the current lever (the shipped lever is the binary `--archive-scope {all,open}`, MG4b, now also in `--help` with a parity+orphan test guarding it).

  **Still open — and part (b) now GATES prawduct's own v3.2.0 migration (updated 2026-07-20, source: critic).** Remaining: (i) the window **quantification** (an N-months / throughput formula between the `{all,open}` poles — still the adopter-scale refinement, unbuilt, and still deferred: nothing below changes its status); and (ii) **part (b)**, the Pacer metering *total* REST points (5/write, 1/read) against 900/min. Part (b) was filed "not gating the dogfood," and that held only while prawduct's own run was assumed to be `--archive-scope open`. Owner decision **A1 (2026-07-20)** chose **`--archive-scope all`** for prawduct's own migration (`.prawduct/artifacts/migration-scrub-decisions.md` decision 5), which falsifies that premise: prawduct's run **is** an `all`-scope run, so part (b) is a **firm v3.2.0 release blocker — item 8 on the ship list**, no longer conditional (`.prawduct/artifacts/release-plan-backlog-service-golive.md`, item 8 / C7). **Ordering — proposed, owner sign-off owed (separate call from the gating):** the recommendation is that it land **before the bulk import (C4)**, so the irreversible migration runs fully metered instead of being part (b)'s own proof case. That ordering is **decision 6** in `.prawduct/artifacts/migration-scrub-decisions.md`, explicitly *builder-proposed with owner sign-off owed* — it does **not** follow mechanically from A1 (decision 5, which **is** owner-confirmed and is what makes part (b) a blocker at all), so it must not ride in on A1's authority. If the owner declines the ordering, **part (b) runs beside the migration instead** (C4's blocked-by drops C7) — and it **remains a v3.2.0 release blocker either way**. Only the sequencing is unratified; the gating status is firm.

  The escalation to **gating** rests on a **structural** argument that needs no item count. Under `--archive-scope all`, each archived item costs a **create *and* a close**, while `pacer.before_create()` is annotated "the only paced call" (`lib/backlog/migrate.py:787`) — so the archive stretch runs create-then-close with **only half of it metered**, which is exactly the >900 REST pts/min window part (b) describes. That holds at 317 items and at 389 alike: the ratio, not the volume, is what breaches the burst ceiling. Its only mitigation today is *incidental* `gh`-subprocess latency, explicitly "not designed-in" — and forfeited by the raw-HTTP fast-path (D2/W1). New scope: **gating for any `--archive-scope all` migration — which, since A1, includes prawduct's own**; only under `--archive-scope open` is there no archive stretch and the gap stays theoretical, and no run in the v3.2.0 release takes that path. Impact raised S→M accordingly. Part (b) now has a **named prover**: NFR §9 (:287) makes it an S2 obligation — measure the burst with `--archive-scope all` (volume reduction disabled, so the run proves the Pacer and not a small input) and answer whether the create-then-close archive stretch breaches 900 pts/min.

  **Why no count carries this decision (2026-07-20).** An earlier revision of this note justified the escalation with "383 open + 124 archive = **507 paced creates**, past the hourly cap." That evidence is withdrawn: the number is not stable enough to carry a gating decision. The PR reviewer challenged it against the 317-open figure still standing in four documents, and on checking, **discodon's four checkouts report 384 / 389 / 349 / 319 open**, with the *canonical* checkout reading **383 then 384 twenty minutes apart**. There is no citable "discodon open count" — which is itself a live instance of the **stale-views-across-checkouts** pain (#2) this project exists to kill. Counts may illustrate the run length; they must not be the load-bearing evidence. The gating status stands on the structural argument above.

  **Do not sweep the 317 figures to a new number** (follow-up for whoever next touches those docs). The "discodon is ~317 open (~435 with archive)" figure at `backlog-service-nfr.md:146` and `:256`, `backlog-service-prd.md:57`, `:246` and `:249`, `backlog-service-requirements.md:47` and `:460`, and `backlog-service-test-specifications.md:710` is a **2026-07-13/14 planning-era figure of unverified current accuracy**. Any single replacement number would inherit exactly the same instability, so the correct fix is to **mark them planning-era** (e.g. "~317 as of the 2026-07-13 planning pass") rather than re-count — and to keep any downstream reasoning (pacing, S2 targets, fan-out cost) anchored on structure rather than on the figure.

- **[BKL-6M4T]** Complete backlog-service Chunk 06 live migration (deferred)
  `effort: L · impact: M · area: backlog-service · source: builder · added: 2026-07-17 · reviewed: 2026-07-19 · status: open · stage: ready · related: BKL-5R2K, DOC-4K9M · refs: artifacts/build-plan-backlog-service.md, VRF-006`

  Offline deliverables (scrub runbook, MIG-5 test, SPIKE-S2 script) landed 2026-07-17; the live, owner-in-the-loop remainder is deferred to a post-sign-off session: run SPIKE-S2 on a throwaway repo, run the real prawduct-first migration (scrub → import), repoint briefing/gates to the adapter, retire `lib/backlog/legacy.py` + the `incoming-bugs/` drop-box, then the single cumulative-critic that gates the slice PR. Blocked on design sign-off + a chosen target repo.

  Pre-PR cleanup (2026-07-17 cumulative-Critic warning): strip 9 dangling build-plan chunk-number refs from shipped source before the slice PR (they resolve to nothing once /prawduct:pr deletes the build plan; durable ids like CC1/CRASH-2/DM7 already sit alongside). Locations: lib/backlog/transport.py:322,456,476; migrate.py:12,22,247,326,574; query.py:18. Also reconcile the two follow-up bodies (BKL-7Q2N/BKL-9J3F) that narrate BKL-4W7H as "shipped" once the slice actually merges. UPDATE 2026-07-18 (cumulative-Critic R-6, resolved in the slice PR): the chunk-ref strip leg is DONE — all chunk-number refs removed from lib/backlog source. The BKL-7Q2N/BKL-9J3F body reconcile still pends the slice merge.

  Owner checkpoint 2026-07-18 — live run HELD; scrub dispositions (5 merges + 13 drops), restructure scope (open survivors only), and MIG-M4-REMOVE (import as-is) all owner-approved and recorded in artifacts/migration-scrub-decisions.md. The migration session executes against that artifact; re-confirm only sign-off + source drift.

  Cutover checklist addition 2026-07-18 (cumulative-Critic R-7 — artifact cascade): at cutover, update `.prawduct/artifacts/architecture.md` — add the `lib/backlog` subsystem component, the `gh` runtime dependency, the clone-shared `backlog-counts.json` store, the briefing/gate repoint, and the drop-box replacement per MG5 — and note the `gh` runtime dependency in project-preferences.md's dependency inventory (rationale home stays PRD O5).

- **[BKL-0QR1]** Chunk 06 retires incoming-bugs/ drop-box before its XP1 replacement exists (upstream-channel sequencing gap)
  `effort: S · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-20 · status: open · stage: ready · related: BKL-6M4T, BKL-9XQ2 · accepted-by: @brooks`

  PRD §8.9 and build-plan Chunk 06 (deliverables list, artifacts/build-plan-backlog-service.md:507) retire the incoming-bugs/ drop-box, justified by 'XP1 becomes the upstream path.' But XP1 (file-upstream, cross-repo filing into the target owner's issues) is roadmap W3 — post-slice, not built (no cmd_upstream/file_upstream in lib/). Executing Chunk 06 literally removes the only working upstream delivery channel before its replacement exists. Interim is degraded-not-lost (the report-bug skill falls back to local capture in the consumer's own backlog when no inbox is reachable), but consumers can no longer deliver a prawduct bug upstream at all until W3. Resolution options for owner sign-off: (a) hold the drop-box retirement in Chunk 06 until XP1/W3 lands; or (b) explicitly accept the local-capture interim and reconcile §8.9 wording with the roadmap sequencing so the plan no longer assumes XP1 is available at retirement time. Surfaced 2026-07-17 during pre-sign-off scenario tracing (scenario 1: consuming repo files a prawduct bug that should land in a prawduct GH issue). Related: VRF-006, BKL-6M4T (Chunk 06 live migration).

  ---
  RESOLVED 2026-07-17 (owner sign-off) → option (c): retire the drop-box IN LOCKSTEP with a minimal same-repo replacement, never before it — neither (a) hold nor (b) accept-interim. Rationale: today's `incoming-bugs/` drop-box is inert unless a prawduct checkout is reachable on the same machine (local dogfooding only); plugin-only consumers already take report-bug's local-capture + canonical-tracker fallback. The 1:1 replacement is a fixed-target, public-repo issue-create — report-bug files an `untriaged-upstream`-labeled issue into prawduct's own PUBLIC repo via the adapter's create path, and the `untriaged-upstream-reports` advisory counts labeled issues instead of `incoming-bugs/*.md`. This needs no new auth (any authenticated user may open an issue on a public repo), so it is a SUBSET of XP1, not full XP1 — the cross-owner/foreign-identity/private-target/XP2 surface explicitly stays W3. Recorded as PRD §8.9/MG5; Chunk 06 rescoped (description, deliverables, acceptance) to include it. Closes when Chunk 06 ships (execution tracked by BKL-6M4T).

  ---
  **GATED 2026-07-20 by BKL-9XQ2 (owner escalation — release-gating).** The MG5 replacement resolved above is the *first* path by which a consuming repo — including a **private** one — sends a bug body into prawduct's **public** repo. BKL-9XQ2's three concerns (approval policy, evidence/exfiltration, label taxonomy) must be settled before this leg is built, and its structural finding applies directly to the replacement's shape: the guard must bind at the **adapter/data plane**, not in `report-bug` prose — because retiring the drop-box *is* the prose rewrite. Do not execute the MG5 leg (or ship a release carrying it) until BKL-9XQ2 clears. The non-MG5 legs of Chunk 06, and any consumer's own-repo backlog migration, are **not** blocked by this.

- **[BKL-3T7X]** GitHub issue titles need a "scannable handle, detail in body" standard — for net-new `file` and for migration (via the scrub, NOT the data plane)
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: open · stage: ready · related: BKL-6M4T, BKL-0QR1`

  Surfaced 2026-07-17 by eyeballing SPIKE-S2's live dry-run output: the migrated issue titles (taken verbatim from backlog item titles) are simultaneously too verbose AND under-informative — run-on em-dash detail-dumps that don't read as GitHub issue titles (e.g. "v3 session-gate advisory surfaces are coarser than the blocking gate — briefing collapses error/schema-ahead verdicts; Gate 2.5 synthesis advisory reads the clone-global latest review fact"). Root cause: the markdown backlog format conflates title with a one-line-carries-everything summary; GitHub issues want title=scannable handle, body=detail. The importer + `file` both pass item.title through verbatim.

  Two application points of ONE convention (title = imperative/noun handle, ~<=70 chars, no em-dash detail-dumps; full context in the body):
  (1) NET-NEW (`file` / cmd_file / `/prawduct:backlog add`): establish the title standard and apply it on creation; add a SOFT LINT that warns on over-long / detail-dump titles. Items are usually model-written, so convention+lint carries most of it. No fidelity concern (new content).
  (2) MIGRATION: do NOT auto-rewrite titles in the importer's data plane — that violates MG1 verbatim-fidelity AND MIG-5/G1 "no model in the migration data plane," on an irreversible run. Deterministic truncation is rejected (cuts mid-clause → less informative, fails the bar). Instead fold a TITLE-CLEANUP pass into the MG4 scrub (Chunk 06): model PROPOSES a clean title → owner CONFIRMS/edits → deterministic import writes the confirmed title. Same owner-confirmed pattern the scrub already uses for dispositions. Preserve fidelity by stashing the ORIGINAL title in the body (or an `original_title:` block field) whenever the scrub changes it, so nothing is lost.

  Design homes when built: PRD §8.9 (scrub gains the title-cleanup disposition) + Data Model (title convention + optional original_title block field) + the `file`/`add` skill (convention + lint). This is a design-stage requirement (requirements-precede-code); do not code before it's written into the PRD/data-model. Blast radius: touches the MG4 scrub scope in Chunk 06 and the item-creation path.

  ---
  DESIGNED 2026-07-17. Standard written: documentation/backlog-service-issue-standard.md (web-researched, current-GitHub-verified + owner-decided). Key facts: the LABEL half is ALREADY built (adapter models kind/area/effort/impact/source + stage/status as namespaced <facet>:value labels, encode.py:70 / provision.py:30) — no redesign. NEW work = title convention (<=72, `area: summary`, atomic), body templates (bug + task, section+word budgets, progressive disclosure), a WARN-only linter, and issue application at two homes (programmatic `file`/migration = serializer + linter; consumer UI filing = YAML Issue Forms). Owner decision on MIGRATION scope (irreversible run): retitle + restructure BODIES + assign kind:, PRESERVE originals verbatim (original_title/original_body block fields + MG2 export), NO auto-split (flag non-atomic for manual scrub-time split → keeps 1 PFX = 1 issue); one LLM pre-pass in the MG4 scrub, before the data plane (MIG-5). Recorded as PRD §8.9/MG6. This revises MG1: bodies restructured-to-standard (not byte-verbatim), original preserved.

  Build breakdown (implement against the standard doc): (1) `file` serializer applies title+section contract + assigns kind:; (2) WARN-only linter (thresholds in the standard §4); (3) migration restructure pre-pass folds into Chunk 06 / MG6 (with original_* preservation); (4) ship YAML Issue Forms in .github/ISSUE_TEMPLATE for consumer UI filers; (5) populate kind: (under-used today). Consider splitting into per-deliverable build items when planned. Decomposed 2026-07-17 into build items BKL-2H9W (net-new `file` path), BKL-4C6P (WARN linter), BKL-7F3D (YAML Issue Forms), BKL-8N5K (MG6 migration pre-pass).

- **[BKL-7F3D]** Ship YAML Issue Forms (.github/ISSUE_TEMPLATE) for consumer UI filers
  `effort: S · impact: M · area: backlog-service · source: user · added: 2026-07-17 · status: open · stage: ready · related: BKL-3T7X · refs: documentation/backlog-service-issue-standard.md`

  Ship YAML Issue Forms (one per variant: bug, task/feature) enforcing the standard §2 sections at CREATION for humans filing via the GitHub UI. Required textareas = the hard section list; dropdowns pin kind/area/stage/impact; labels: auto-applies defaults (provision already creates the labels). NOTE: issue Forms only gate UI-created issues — prawduct's own `file` is programmatic (governed by items BKL-2H9W+BKL-4C6P). This is the consumer-facing enforcement home. Markdown templates only as a fallback for repos that won't adopt forms.

- **[SEC-8R3K]** Document the GitHub Actions workflow env-wiring required by the backlog SEC-5 guard (`PRAWDUCT_PR_HEAD_REPO`, `PRAWDUCT_ACTOR_AUTHORIZED`)
  `effort: S · impact: S · area: security · source: critic · added: 2026-07-17 · status: open · stage: ready · refs: artifacts/build-plan-backlog-service.md`

  The backlog SEC-5 guard reads two workflow-surfaced signals via `context.is_untrusted_trigger` / `actor_authorized`: `PRAWDUCT_PR_HEAD_REPO` (fork-PR detection) and `PRAWDUCT_ACTOR_AUTHORIZED` (the collaborator authorization check). These must be wired in the GitHub Actions workflow. Absent that wiring, the fork-PR defense-in-depth layer is inert — safe by construction (fork PRs get a read-only token) but the flag itself won't fire. Document the required env-wiring so the layer is actually engaged. Land alongside the Chunk-06 briefing / Actions wiring. Filed from Chunk 04 Critic NOTE.
- **[LRN-9K2P]** Modernize ~28 legacy terse learnings.md headings to self-contained "When X, do Y because Z" rule form
  `effort: S · impact: S · area: memory/learnings · source: critic · added: 2026-07-17 · status: open · stage: ready · related: LRN-7M4D · refs: .prawduct/learnings.md, .prawduct/learnings-detail.md, methodology/reflection.md`

  The 2026-07-17 learnings.md compaction reduced the file to header-only rules (narrative moved to learnings-detail.md). ~1/3 of the headings are legacy terse topic-labels (e.g. "Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo") that state the rule but not the inline *why*. Since the SessionStart briefing now surfaces headings only, their actionable why isn't visible without opening learnings-detail.md — still reachable via `/prawduct:learnings`, so **NOT a regression** (the briefing was headers-only before too).

  Fix: reword the terse headings to carry rule + why in one line, matching the dominant "When X, do Y because Z" format the intro + `methodology/reflection.md` now describe. Surfaced by the Critic design + sustainability reviewers (NOTE, rev-20260717T192532Z). (critic)

- **[COV-4H7N]** Doc-only/state-only PR silently breaks a repo-coupled (non-hermetic) test — check-pr-doc-only AND test-status both assume non-code files can't change test outcomes
  `effort: M · impact: M · area: governance/gates · source: builder · added: 2026-07-17 · status: open · stage: design · related: COV-2P7F, COV-6T3P, COV-8R2K · refs: lib/coverage.py (cmd_check_pr_doc_only — doc-only fast-path), lib/coverage_algebra.py (is_judgeable_path), bin/prawduct-hook (test-status / cmd_test_evidence), tests/test_norm_probes.py (TestSilentAgainstThisRepo)`

  A doc-only/state-only change can break a live-state-coupled test with **no gate catching it**. Concrete: PR #125 (norm-registry ratification) changed only `.prawduct/*.md` + `project-state.yaml`, so `check-pr-doc-only` reported doc-only (skipped Critic + PR review + suite) AND `test-status` reported "current" (treats `project-state.yaml` as non-judgeable) — but `tests/test_norm_probes.py::TestSilentAgainstThisRepo` reads the **live** `project-state.yaml`, so ratifying the registry silently broke it on develop; only caught on the next unrelated branch's suite run.

  **Root cause:** both the doc-only fast-path and test-status's judgeable-path classifier assume non-code files can't change test outcomes — but repo-coupled (**non-hermetic**) tests read committed state/docs, so a `.prawduct/*` edit CAN flip a test red.

  **Possible fixes** (design pending — pick and reconcile with COV-2P7F): (a) test-status/doc-only should treat `project-state.yaml` (and any file a non-hermetic test reads) as judgeable; (b) doc-only PRs should still run the suite when repo-coupled tests exist; (c) narrow/inventory the non-hermetic tests so the assumption becomes true.

  **Tension to resolve — this is a hard constraint on COV-2P7F.** COV-2P7F pushes the *opposite* direction (treat `.prawduct/**` as governance-only so a metadata edit escapes full gates). This item is the counterexample proving a *blanket* `.prawduct/**` exemption is unsound while non-hermetic tests exist: exempting `project-state.yaml` from the suite is exactly what let #125 break silently. Any COV-2P7F design must account for this — the safe exemption is narrower than "all of `.prawduct/**`", or fix (b)/(c) must land first. Also related: COV-6T3P (the `is_judgeable_path` predicate that classifies these paths) and COV-8R2K (coverage floor on non-code config). Stage: design — the problem/root cause are clear; which of (a)/(b)/(c) and how it reconciles with COV-2P7F is the open decision. Governance-protected (lib/gates, lib/coverage, hooks) → full Critic + PR review. (builder — finding this session)

- **[GOV-8R3F]** Janitor Step-3 Reconcile surfaces candidates flat (single confirm-or-correct block); apply the shipped doctor surface-by-exception taxonomy
  `effort: M · impact: M · area: governance · source: reflection · added: 2026-07-17 · reviewed: 2026-07-17 · status: open · stage: ready · related: GOV-6N4W, GOV-4X9M, JNT-8E3P · refs: skills/janitor/SKILL.md (Step-3 Reconcile — the residual), skills/doctor/SKILL.md (steps 2-3, shipped clear-to-ratify/needs-a-ruling taxonomy — reuse precedent), docs/norms.md (§ Adoption)`

  The **doctor** Norm Ratification Flow shipped the surface-by-exception fix this cycle (`skills/doctor/SKILL.md` steps 2-3 + `docs/norms.md` § Adoption): a **clear-to-ratify vs. needs-a-ruling** taxonomy, a ban on flat-dumping ~6+ candidates, and an explicit bulk-confirm guard. That fixed the doctor's original failure mode — at scale, a one-block dump of every candidate becomes a wall-of-text the owner skims and rubber-stamps (the "blanket 'looks good' that never engages the forks" failure ratification exists to prevent — Principle 6; the GOV-4X9M "approval on the divergences, not the document" concern).

  **Residual (this item):** the sibling **janitor Step-3 Reconcile** (`skills/janitor/SKILL.md`) still presents its candidates as a flat "single confirm-or-correct block" and carries the identical failure mode — it needs the same treatment.

  Fix-shape: **reuse the shipped doctor taxonomy** — don't design a competing one. Apply the same clear-to-ratify / needs-a-ruling split to the janitor's Reconcile step: foreground only the candidates that need a decision (the doctor taxonomy already encodes which — ambiguous classification, high-stakes/security-relevant, `in-transition`, Type-2 sub-optimal-norm risk), collapse the clearly-safe ones into a bulk **confirm-in-summary** affordance, and honor the ~6-item flat-dump ban. Exception criterion, surfacing shape, and bulk-confirm guard are all already designed and proven in the doctor precedent — this is a port, not a fresh design.

  Guard: surface-by-exception must **never silently ratify** the un-surfaced candidates — the collapsed set still gets an explicit bulk confirm (owner sees the count and can expand), matching the doctor's shipped guard, because auto-binding a norm the owner didn't engage is a norm-birth decision made by default (`docs/norms.md` § No auto-ratification).

  Stage: ready — the fix-shape is proven by the shipped doctor precedent, so there is no open design question; the work is porting the existing clear-to-ratify/needs-a-ruling taxonomy onto the janitor's Step-3 Reconcile. Governance-protected (`skills/`) → full Critic + PR review.

- **[GOV-4X9M]** Backfill-as-discovery: interview-driven strategy-artifact authoring with just-in-time nudges + layered opt-outs
  `effort: L · impact: L · area: governance · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: open · stage: requirements · related: GOV-EXI2, GOV-5K3M`

  **Problem.** Prawduct nudges products to author strategy-class artifacts (the structural-coverage chain), but authoring is a *solo agent task* that (a) tends to codify current practice as if it were intended design, and (b) cannot know the owner's actual intent — intent lives in the owner's head, not the repo. Good outcomes today depend on a human steering the agent manually (observed live while authoring prawduct's own 7 artifacts, 2026-07-17). The Critic currently *rewards* the failure mode: the cumulative review praised the artifacts for being 'accurate to prawduct's actual system' — accuracy-to-current-code is the wrong success metric for a document meant to lead development.

  **Direction — treat backfill as retroactive discovery (an interview), not solo documentation.** Reuse/generalize the existing new-product discovery flow rather than building a second one.
  - **Elicit the mode, don't presume it:** first fork is 'draft a first pass from what's built, or come at it from first principles?' — plus 'capture current state (maintenance) vs. set direction'. Surface the true depth of what's missing (many owners *want* to know), framed as information+options, not alarm. Depth-gauged like discovery.
  - **Stance:** backfilled artifacts state *intended design* (the target you'd defend to a skeptic) and flag divergences from current code as explicit owner decisions/backlog items — never silently enshrine a dubious current practice. Promote memory feedback_artifacts_express_intent into methodology (planning.md + one line per template + advisory/scaffold text).
  - **Critic objective flip:** add a check so a purely-descriptive strategy artifact that rubber-stamps current behavior is a finding; accuracy-to-code alone is insufficient.

  **Primary trigger — just-in-time, stakes-calibrated nudge.** When requested work would benefit from a missing/thin doc ('you asked to add logging but there's no observability-strategy'), propose addressing it first. Detection is LLM judgment (not a mechanical gate), likely built on the work-model tripwire / jurisdiction+coverage machinery (absence of an expected governing artifact for the work area). Calibrate to stakes (security-model before auth = gold; observability before a copy tweak = noise). Applies to doc states 1 (nonexistent) and 2 (stale); state 2 deferred.

  **Layered opt-outs (a way-of-thinking, NOT a formal state machine):**
  - Decline-once ('later') -> stay state 1, continue; RE-SURFACE relevance-triggered (same work area recurs), not calendar-triggered; judgment backs off on repeated decline. DEFAULT for ambiguity — never auto-write a 'not relevant' stub the owner didn't decide (Principle 6).
  - Decline-this-doc ('not needed because X') -> author the (not relevant — X) stub = state 3, a recorded decision whose expiry is the app's characteristics; a structural-characteristic flip re-opens it (existing norms.md machinery) — so capture the assumption richly.
  - Decline-everything ('I just want to code without docs') -> recorded, reversible, SCOPED project-preferences posture (suppresses proactive nudges; on-demand /prawduct:doctor still answers).

  **Secondary (test, don't design): strengthen the advisory + agent behavior** to proactively surface/triage advisories in the agent's first response. Constraint: the agent never gets the first turn, so this can only ride the first response. Genuinely uncertain whether it helps or annoys — empirical, needs anti-annoyance tuning; not designed up front.

  **Out of scope (now):** state-2 stale-doc detection; forcing anything (advisories only advise); a second discovery flow; designing the advisory tuning.

  **Open questions:** detection heuristic + its home (extend work-model tripwire?); re-surfacing judgment mechanics; opt-out granularity; how the interview reuses discovery machinery; whether prawduct's own 7 artifacts get re-derived via the flow once it exists; does first-response proactive surfacing actually work.

  **Doc-state lens (thinking tool):** 1 nonexistent · 2 stale · 3 exists-with-(not relevant)-opt-out · 4 good. Nudge 1 (now) and 2 (later).

  **Provenance:** design conversation 2026-07-17 following the solo authoring of prawduct's 7 strategy-class artifacts (GOV-5K3M). Relates to GOV-EXI2 (reactive systems can't detect missing things), the structural-coverage chain, and memory feedback_artifacts_express_intent / feedback_advisor_first.

  ---
  ## Design refinements (conversation 2026-07-17, continued)

  **Templates & interview-guidance homing:**
  - VERIFIED: 6/7 strategy-class templates exist; `templates/architecture.md` is MISSING = GOV-2T6K, now a HARD DEPENDENCY (can't prompt authors to write an architecture spec with no scaffold).
  - Templates carry GENERATION guidance only, no elicitation guidance — correct. Two kinds of meta: templates = deliverable-meta (stack-agnostic scaffold of what to produce); interview guidance = process-meta (how to elicit). Different homes.
  - Interview TECHNIQUE is universal -> the shared discovery core (one central home). Interview TARGETING is artifact-specific but THIN -> extend discovery.md's existing '## Surface X' pattern to cover all 7 artifacts (today missing explicit data-model/security/architecture elicitation sections). NOT in templates; NO per-artifact interview files. Optional one-line pointer in each template -> discovery elicitation section (co-location without duplication).
  - Artifact-specific targeting = the distinctive high-leverage question + where owners under-specify (e.g. data-model: consumers' future queries / persisted-format lock-in; security: threat model, interview MORE directively because owners under-claim; NFR: real target numbers, 'what breaks at 10x?'; api-contract: internal-vs-external consumers; architecture: cross-process failure modes).

  **Divergence-approval = norm birth + retroactivity (reuse docs/norms.md wholesale, don't invent):**
  - WHAT divergences: material gaps between the OWNER-RATIFIED intended design (the artifact's Direction = proportionate best-practice-for-this-project, pinned in the interview) and current code. Baseline is owner-ratified, which dissolves the 'can't pre-define best practices' problem. Proportionate to stakes; err toward surfacing (miss >> annoy).
  - REVISIT: yes, via the existing norm lifecycle — new divergences caught by the Critic (departure from Direction = BLOCKING); baseline decay/erosion/stall caught by janitor Norm Health + advisories; evolving best-practice = norm amendment (recorded decision). Feed the lifecycle, don't rebuild it.
  - 'Accept current divergences + document best practice as goal + backlog to align' = the norms.md MIGRATE retroactivity outcome: intended-design norm born Status:in-transition, divergences -> sized backlog item(s), the item WIRED as the norm's tracking ref so stall-detection prevents 'align later' rotting into 'never'. The three dispositions map to the three retroactivity outcomes: accept-and-align=Migrate / permanently-fine-here=Grandfather / old-and-new-coexist=Contain.

  **Backlog as the responsible-deferral primitive:** every 'not now' in the flow (skip-doc-for-now, accept-divergences, defer-a-question) becomes a one-tap backlog item — agent drafts it, owner just affirms. This is the durable, re-surfacing record that makes 'later' honest. GUARD (from the pressure test): a deferral item must hang off an in-transition norm as its tracking ref, else backlog becomes a graveyard.

  **The interview collapses Layer 1 + Layer 2:** the divergence/retroactivity machinery only has teeth if the intended design is a RATIFIED Direction norm, and ratification needs the owner present. Solo authoring can't ratify -> toothless descriptions (proven live: prawduct's own 7 artifacts, authored solo this session, have no Direction sections and engage none of this machinery). The interview produces Layer 1 + Layer 2 together (owner declares intent = ratification, retroactivity decided same sitting). Allow 'not ready to bind yet' -> descriptive + defer ratification as a backlog item; default toward collapsing.

  **Pressure-test findings (red-teamed for false negatives; priority: miss-a-gap >> annoy — LLM deference gives non-annoyance for free):**
  1. Extend the just-in-time nudge to LAYER 0 ('you're adding payments but I don't know what this product IS yet') — highest value, since the whole chain is downstream of recorded characteristics. Biggest hole: a user who skips discovery gets zero governance.
  2. VALIDATE opt-outs against recorded/detected characteristics — a '(not relevant — tiny utility)' security stub on a product with handles_sensitive_data is a detectable CONTRADICTION -> challenge/block, don't accept at face value. Single highest-leverage tightening.
  3. Bias toward surfacing/insisting; default-when-uncertain = surface not defer; present full stakes, don't soft-pedal.
  4. Approval on the DIVERGENCES not the document; blanket 'looks good' that never engages the flagged forks is not ratification; Critic objective-flip (descriptive rubber-stamp = finding) applies to interview output.
  5. Keep mechanical gates (advisory + Critic/PR) as judgment-INDEPENDENT backstops for detection misses; opt-outs suppress proactive nudges ONLY, never the gates.
  6. Characteristic-DRIFT detection (re-detect from ongoing work; the work-model tripwire on payments/auth/PII terms is a proto-signal) is what makes n/a stubs self-expiring in practice.
  7. Durable opt-out must be visible/attributed/reversible and repo-scoped-with-care (team: one dev's opt-out shouldn't silently gag the team's gates).

  ---
  ## Divergence model — Type 1 / Type 2 correction (conversation 2026-07-17, continued)

  **CORRECTION to the divergence model (supersedes the single-divergence framing above):** there are THREE things, not two — (a) best practice = the agent's expert recommendation; (b) the ratified norm = what the owner binds; (c) the code. 'Divergence' splits into two gaps with OPPOSITE handling:
  - **TYPE 1 — code below norm (b vs c):** documented goal is genuinely best practice, code lags. Approval = ratify the good norm + accept the code must be updated (norm-birth + MIGRATE retroactivity, backlog the alignment). The CODE is wrong. [This is the case the earlier 'divergence-approval = norm birth + retroactivity' section covers.]
  - **TYPE 2 — norm below best practice (a vs b):** the owner wants to enshrine a sub-optimal practice AS the norm ('never use comments', 'plaintext HTTP credentials'). The NORM is wrong. Approval = the OPPOSITE of accept — clarify/validate/challenge so the owner chooses it eyes-open. This is the 'docs normalize mistakes' fear at the norm layer, where it gets the framework's authority.

  This PUNCTURES the earlier claim that 'owner-ratified intended design IS the definition of best-practice, which dissolves the definition problem' — owner-ratification can enshrine garbage. Expertise (a) is a SEPARATE input from ratification (b); the interview is where they meet and the agent must not let (b) silently drop below (a).

  **Type 2 mechanics (mostly reuse existing machinery):**
  - Severity gradient: stylistic/defensible ('never use comments') -> challenge gently, defer gracefully (Principle 23, owner owns the product), ratify if insisted; genuine harm, esp. harm to THIRD PARTIES ('plaintext credentials' exposes the app's users) -> challenge hard, refuse to frame as recommended, record starkly.
  - The required `why` (norms.md) is the Type-2 detector: a norm whose why doesn't survive scrutiny is the trip signal to challenge; a whyless/weak-why bad norm isn't quietly ratified.
  - Ratify-against-advice is a LABELED decision, never laundered: recorded as 'adopted against recommendation: <agent objection>', never relabeled 'best practice'. The honest label is the point.
  - Critic's Type-2 role is ANTI-LAUNDERING not veto: it can't override a recorded owner decision (Principle 23) but must verify a sub-optimal norm is honestly labeled as an override, not dressed as recommended practice.

  **Net:** 'approval on divergences' is TWO approvals — Type 1 = 'hold the code to this good bar' (align code); Type 2 = 'confirm you're lowering the bar on purpose' (raise the bar, or record the lowering honestly). Type 2 is where 'docs should be more strident than the code' has the most force.

  ---
  ## Type 2 handling — no-veto correction (conversation 2026-07-17, continued)

  **CORRECTION to Type 2 handling — the agent has NO VETO over a norm (supersedes 'refuse to frame as recommended' / 'challenge hard, refuse' language above):** Every best practice is a DEFEASIBLE HEURISTIC, and the developer holds context the agent cannot see. Literally every SE best practice is the wrong choice in some rare, legitimate case (e.g. plaintext credentials to an ancient microcontroller on an airgapped bus is correct, not a mistake). So the terminus is ALWAYS ratify — warn, explain, then defer (Principle 23 in full).

  Corrected Type 2 flow:
  1. Surface the general best practice + its reasoning (stays strident; the warning does NOT get softer).
  2. ELICIT the why (the part previously under-weighted) — don't pre-judge the norm bad; ask. The why often reveals the 'wrong' practice is right in this context, i.e. it's the context the agent was missing.
  3. Ratify — ALWAYS. The honesty of the RECORD scales to how the why holds up, not whether the agent agrees:
     - why resolves the concern -> recorded as a legitimate context-specific decision (NOT 'against advice' — the agent was working from partial context).
     - no adequate why for a genuinely risky choice -> still ratified (developer owns it), agent's unresolved concern noted honestly on the record.

  The ONLY thing the agent ever declines is to LAUNDER (call something 'best practice' when it isn't, or omit the concern from the record). It never declines to ratify. Honest labeling != refusal.

  This softens the earlier 'harm to third parties raises the bar' -> it raises WARNING INTENSITY and why-elicitation rigor, never the outcome toward refusal (the agent can't reliably assess third-party harm from partial context). Critic anti-laundering role holds but the LABEL REFLECTS THE WHY: a legitimate airgapped decision reads as a decision, not a warning banner; the Critic checks the why EXISTS and the choice is RECORDED, not that it agrees.

  Candidate framework principle worth elevating: 'the agent is advisory on norm content, never a gate; every best practice is defeasible.' Strident warning + graceful deferral + honest record.

  ---
  **Note (2026-07-17):** the `templates/architecture.md` hard dependency (flagged under "Templates & interview-guidance homing" above) is satisfied — GOV-2T6K shipped 2026-07-17 (`closed-by: architecture-template`). All 7/7 strategy-class authoring templates now exist; this item is no longer blocked on scaffolding.

- **[GOV-4M7K]** coverage-status layer-0 report should share the ambient nudge's product-work gate
  `effort: S · impact: S · area: governance · source: critic · added: 2026-07-16 · status: open · stage: ready · refs: bin/prawduct-hook (cmd_coverage_status), lib/gitstate.py (_has_product_definition_work), skills/doctor/SKILL.md #11`

  Critic NOTE (structural-coverage cumulative, R-2). cmd_coverage_status in bin/prawduct-hook computes layer-0-active purely from 'not structural_characteristics_recorded', WITHOUT the _has_product_definition_work gate that the ambient layer-0 briefing nudge (also in cmd_clear) applies. Consequence: on a freshly-onboarded empty repo (no code, no docs/) the doctor 'coverage-status' report says layer 0 is active / coverage degraded, while the ambient session-briefing advisory correctly stays SILENT (and doctor Health Check #6 also gates on product work). The doctor report is thus slightly more eager than the nudge it claims to mirror ('reads the SAME expectation table'). Fix: gate the coverage-status layer-0 determination on _has_product_definition_work too, so the report and the ambient nudge agree on a fresh repo. Bounded, cosmetic (a report line, no wrong behavior). refs: bin/prawduct-hook (cmd_coverage_status), lib/gitstate.py (_has_product_definition_work), skills/doctor/SKILL.md #11.

- **[GOV-6N4W]** UserPromptSubmit "norm-shaped prompt" classifier — detect norm-birth phrasing at prompt time and nudge capture
  `effort: M · impact: M · area: governance · source: builder · added: 2026-07-16 · status: open · stage: idea · related: GOV-7Q4N, WMK-4Q9T, WMK-1P4Q · refs: .prawduct/artifacts/build-plan-norm-lifecycle.md (Out of scope + Chunk 6), docs/norms.md`

  Deferred follow-up filed from the norm-lifecycle build plan (declared out of scope there; Chunk 6 directs this filing). Detect norm-birth phrasing in user prompts at UserPromptSubmit time — "we should always X", "from now on Y", "never Z again" — and nudge capture into the norm registry (Direction section + preferences row) so a norm is born recorded instead of ambient. Deferred for precision risk per the work-model review history: the work-model prompt-term tripwire (WMK-4Q9T) shows prompt-time classifiers misfire on ordinary prose and desensitize the very nudge they power — a norm-shaped classifier must clear that bar before it ships. Idea-stage: needs a design pass on the detection signal (phrase patterns vs. heavier classification), its false-positive posture, and usage evidence from shipped v1 norm capture (advisory probes + janitor Norm Health + doctor ratification) that prompt-time detection adds value over capture-at-reflection. Governance-protected (hooks) → full Critic + PR review. (builder)

- **[JNT-8E3P]** Erosion metrics automation — compute the janitor Norm Health sweep's distance-from-norm measurements instead of hand-deriving them
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-07-16 · status: open · stage: idea · related: GOV-7Q4N · refs: skills/janitor/SKILL.md (Norm Health theme), docs/norms.md (§ Trajectory), .prawduct/project-state.yaml (norm_health:)`

  Deferred follow-up filed from the norm-lifecycle build plan (Chunk 6 directive). v1's Norm Health sweep measures erosion by hand: the janitor searches for violation sites per norm and manually records the point-in-time measurement (date + per-norm distance, e.g. "3 violation sites, 2 open exceptions") under `norm_health:` in `project-state.yaml` so the next sweep sees the trend. Automate the measurement: violation-site counting and trending computed by code (per-norm search signal → counts → trend deltas against the recorded `norm_health:` history) so the sweep's erosion numbers are derived rather than hand-counted — cheaper sweeps, comparable numbers across runs, and the trajectory failure the theme exists to catch (many individually-defensible exceptions summing to a dead norm) becomes mechanical. Idea-stage: needs a design pass on how a norm declares its machine-checkable violation signal (e.g. a search pattern on its Enforcement row) — most norms carry prose-only constraints, so v1 automation likely scopes to norms that can declare one, with the manual path remaining for the rest. (builder)

- **[GOV-3P8K]** Deterministic tripwire for the ephemeral-ref firewall — grep/hook check that auto-flags ephemeral build identifiers leaking into committed code comments / durable specs
  `effort: M · impact: S · area: gates · source: critic · added: 2026-07-14 · status: open · stage: idea · refs: skills/critic/review-protocol.md (Goal 4 — Coherence, ephemeral-ref check), docs/principles.md (Principle 13 durable-artifact clause), .prawduct/cross-cutting-concerns.md (Durable-artifact self-containment row — "Deterministic grep tripwire deliberately deferred")`

  Deferred follow-up from the ephemeral-ref-firewall change (2026-07-14). A deterministic grep/hook check that scans committed code comments and durable product specs for ephemeral build identifiers (chunk NN, build-plan / work-cycle names) and flags leaks automatically, complementing the Critic Goal 4 check that shipped in ephemeral-ref-firewall.

  Deliberately DEFERRED, case-law-first — build only if the rule + Critic prove insufficient in practice (the cross-cutting-concerns registry row already records this deferral).

  Design challenge: false positives on "chunk" as an ordinary word (chunked data, memory chunk) and on the blessed bookkeeping exemption (change-log `chunks=`, backlog `closed-by:`, operator-verification). Any deterministic scanner has to separate a real ephemeral-build-ref leak from these legitimate uses.

  Idea-stage: needs a design pass on the detection signal and its false-positive posture before it is buildable. Governance-protected (gates / skills/critic) → full Critic + PR review. (critic)

- **[COV-2P7F]** NARROWED: route the change-log entry gate through `judgeable_files` — the last `.endswith(".md")` classifier in the gate surface (was: unify the governance-metadata predicate across ALL PR fast-paths)
  `effort: S · impact: M · area: coverage · source: user · added: 2026-07-09 · reviewed: 2026-07-19 · status: open · stage: ready · related: CRT-5D8Q, COV-5H3N, COV-8R2K, PR-5K8D, COV-4H7N, REL-6C3W · refs: lib/coverage.py:272 (check_change_log_entry non_md filter), lib/coverage_algebra.py (judgeable_files / is_judgeable_path), bin/prawduct-hook:3796-3797 (dispatch), skills/pr/SKILL.md:59 (Step 1c STOP), tests/test_change_log_entry_gate.py, incoming-bugs/archive/2026-06-13-governance-metadata-fix-triggers-full-code-pr-gates.md`

  Triaged from incoming bug incoming-bugs/archive/2026-06-13-governance-metadata-fix-triggers-full-code-pr-gates.md (hallucinote, prawduct v2.1.4). "Docs" is defined as `.md`-only across the fast-paths, but governance STATE lives in `.prawduct/*.yaml` too — so editing the governance metadata that DRIVES the gates is treated as editing the product the gates protect. A `.prawduct/`-only maintenance branch (e.g. a one-line active_build_plan pointer fix in project-state.yaml + some `.prawduct/*.md`) fails check-pr-doc-only (not-doc-only on any non-.md file), re-stales the cumulative critic (the "docs changed since review" allowance is .md-only), requires a change-log entry, and forces a full test re-run + a second Critic pass — all disproportionate to a metadata edit.

  This is the UMBRELLA requirement none of our existing scattered items state as one: (1) treat a branch whose entire diff is under `.prawduct/` (state yaml, backlog, change-log, learnings, plans) as governance-only in check-pr-doc-only and the cumulative-critic "changed since" allowance — qualify it for a doc-only / sibling "governance-only" fast-path and don't re-stale a cumulative; (2) don't require a change-log entry for a `.prawduct/`-only branch; guard: keep skills/, methodology/, templates/, root CLAUDE.md classified as code (behavioral logic), exactly as the existing doc-only bound list already does. Related existing items: the metadata-exemption-boundary item (CRT-5D8Q — the two gate helpers _record_covers_head vs _compute_verify_resolutions_scope disagree on the `.prawduct/` boundary), COV-5H3N (gitflow base), and the coverage-floor-on-config item (COV-8R2K); PR-5K8D is the inverse (exclude skills/ from doc-only, i.e. keep governance CONTENT classified as code). This item is the consolidating parent; the boundary item (CRT-5D8Q) is a specific sub-fix. Governance-protected (lib/gates.py, hooks) → full Critic + PR review.

  Cross-reference (2026-07-14): the tree-validated test-evidence freshness work (v3.0.3, `lib/gates.py` `_test_evidence_tree_valid`) is now a NEW consumer of the canonical `is_judgeable_path` / `coverage_algebra.judgeable_files` predicate. It does NOT advance this item's scope — the PR doc-only fast-paths and the cumulative-critic "changed since" allowance are untouched — but it widens the blast radius of any change to that predicate: the freshness gate now also classifies paths through it. Any change made under this item to `is_judgeable_path`/`judgeable_files` must account for the freshness gate as a downstream consumer.

  **SCOPE NARROWED 2026-07-19 (salvage annotation) — VERDICT: PARTIAL, most of the umbrella is
  already done.** Verified against develop's current code with live gate execution, captured before
  the stale branch `feature/gate-exemption-boundary` was deleted (work preserved at tag
  `archive/gate-exemption-boundary`; the relevant commit for THIS item is `955bc2a` on
  `archive/gate-friction-batch`). Sub-requirements (1a) and (1b) of the umbrella above are **FIXED
  by kernel-v3** — treat the paragraphs above as history, not as remaining scope:
  - (1a) `check-pr-doc-only` routes through `coverage_algebra.judgeable_files`
    (`lib/coverage.py:216`). Empirically: a branch changing only `.prawduct/backlog.md` +
    `.prawduct/project-state.yaml` → `doc-only: 2 file(s) in main...HEAD, none judgeable`, rc=0.
  - (1b) the cumulative-critic staleness concept is gone entirely; a wholly-non-judgeable interval
    is a free edge (`lib/coverage_algebra.py:180-189`). Empirically, on a `.prawduct/`-only branch
    with ZERO review facts: `satisfied: (0 review fact(s) + 1 free edge(s))`, rc=0. Adding one
    `.py` flips it to `uncovered`, rc=1 — so the exemption does not over-exempt.

  **STILL BROKEN — the change-log entry gate, and that is now this item's whole scope.**
  `lib/coverage.py:272`: `non_md = [f for f in files if not f.endswith(".md")]` — the only
  remaining behavioral `.endswith(".md")` classifier in the gate surface. Reproduced on develop: a
  `.prawduct/`-only branch → rc=1, `no-entry: branch changes code
  (.prawduct/project-state.yaml) but .prawduct/change-log.md is untouched`. **The two gates now
  openly contradict each other on the same diff** — doc-only says "none judgeable", change-log says
  "branch changes code". The wiring is live: `bin/prawduct-hook:3796-3797` dispatches it;
  `skills/pr/SKILL.md:59` Step 1c makes it a STOP.

  **FOLD IN — the inverse gap (newly found 2026-07-19, not in the item's original text).** A branch
  changing only `skills/pr/SKILL.md` → `check-pr-doc-only` rc=1 (`not-doc-only: review-needing
  files: skills/pr/SKILL.md`) but `check-change-log-entry` rc=0 (`doc-only: all 1 changed file(s)
  are .md — no entry required`). Behavioral skill-prose changes can therefore merge with NO
  change-log entry — a REL-6C3W-class hole that the change-log gate exists to close. The same
  one-line fix closes this direction too, which is why it belongs here rather than in a new item.

  **Residual work is ONE LINE, not a port of `955bc2a`.** Change `lib/coverage.py:272` to use
  `coverage_algebra.judgeable_files(files)`. Do NOT port the branch's helpers (`is_doc_or_metadata`,
  `is_nonbehavioral_path`) — they are semantically identical to develop's `is_judgeable_path`
  negated (verified across `.prawduct/*.yaml|md`, `.claude/settings.json`, `skills/*.md`,
  `methodology/*.md`, `CLAUDE.md`, `docs/*.md`, `lib/*.py`), so porting them would re-introduce the
  duplicate predicate CRT-5D8Q was created to kill. The branch's other three call sites are already
  fixed or deleted on develop.

  *Test pointers.* develop's `tests/test_change_log_entry_gate.py` has NO `.prawduct/`-only case and
  NO `skills/*.md` case — the gap is untested in both directions; `955bc2a` adds both. Existing
  predicate pins that already hold and must keep holding: `tests/test_coverage_algebra.py:69-90`,
  `tests/test_cumulative_gate.py:250`, `tests/test_session_critic_gate.py:186`.

  *Constraint carried forward.* COV-4H7N's tension note (a blanket `.prawduct/**` exemption is
  unsound while non-hermetic tests exist) applied to the umbrella's (1a)/(1b) legs, which have
  already shipped; it does not constrain this one-liner (the change-log gate does not decide whether
  the suite runs). Resolve that tension against COV-4H7N's own scope, not here. Stage advanced
  design→ready: the fix, its blast radius, and its tests are all determined. Resolve alongside
  PR-4V2N (the `skills/pr/SKILL.md:47` step-skip ambiguity that decides whether a `.prawduct/`-only
  PR even reaches this gate).

- **[STH-4B7Q]** check-operator-verification gate reportedly throws ModuleNotFoundError (needs repro)
  `effort: S · impact: M · area: stop-hook · source: user · added: 2026-07-09 · status: open · stage: idea · related: STH-2J9F, STH-8M3V`

  hallucinote reported (recorded 2026-07-04, incidents May–June) that the check-operator-verification gate hook throws ModuleNotFoundError across 6+ PRs, and that the failures were never escalated upstream (carved around instead of fixed). Needs-verification: a quick check of bin/prawduct-hook's lazy `from lib import ...` pattern did not confirm the exact failing import path or whether this reproduces on current v2.3.0 (the operator-verification surface was reworked in v2.0.0 Chunk 13, so this may be stale or environment-specific — e.g. a broken/partial install where lib/ is unresolvable). Stage: idea pending a clean repro. Fix-shape (if confirmed): correct the import path / fail loud with an actionable install-repair message rather than an opaque ModuleNotFoundError. Source: hallucinote reflection sweep 2026-07-09. (user)

- **[BKL-7M4Q]** `/prawduct:backlog` mutation is not crash-safe or idempotent — partial file mutation on mid-run crash + duplicate paragraphs emitted
  `effort: M · impact: M · area: backlog · source: critic · added: 2026-07-09 · status: open · stage: ready · related: STH-9T4F, STH-8M3V · refs: skills/backlog/SKILL.md, .prawduct/backlog.md`

  The forked /prawduct:backlog skill mutates backlog.md non-atomically. Two corroborating incidents in hallucinote: (a) the skill died on an API socket error mid-run and left a PARTIAL file mutation — data corruption, not a clean rollback; (b) a Critic (2026-07-07) found a DUPLICATED paragraph the skill had emitted (non-idempotent write). Impact: a mid-run crash or retry can corrupt or duplicate backlog entries — the very tool meant to be the safe mutation path for the backlog is itself unsafe. Fix-shape: make backlog mutations transactional and idempotent — parse the file to a model, transform by item id, assert no duplicate ids / no dropped items, then write atomically (temp file + rename). Governance-protected (skill) → full Critic + PR review. (critic)

- **[PR-7T2K]** PR gates validate local HEAD, not the pushed origin/<branch> that squash-merge uses — post-push commits silently dropped
  `effort: M · impact: M · area: pr · source: user · added: 2026-07-09 · status: open · stage: ready · related: PR-2H8N, WT-7M4K, COV-7K4N · reviewed: 2026-07-19 · refs: lib/gates.py (no check_branch_pushed exists), skills/pr/SKILL.md (Merge Flow), lib/gitstate.py (current_branch, _git_head_sha)`

  The PR gates (change-log entry, cumulative-critic, evidence) validate the LOCAL commits, but `gh pr merge --squash` squashes what's on origin/<branch>. A commit made after the last push — very often the change-log entry the gate itself just forced the builder to add — never reaches origin, so the squash-merge silently drops it and the merged result is missing content the gates confirmed present. Reported by hallucinote (~June). Fix-shape: /prawduct:pr (or a PR gate) should assert `git rev-parse origin/<branch>` == local HEAD (branch fully pushed) before allowing merge, and fail loud with "unpushed commits — push before merging" otherwise. Governance-protected → full Critic + PR review.

  Reviewed 2026-07-17 (ambient-merge-commit-default Critic C-B3): remains valid — the unpushed-commit hazard survives the squash→merge-commit flip, since a merge commit still merges what's on origin/<branch>, so post-push local commits are still silently dropped.

  **Salvage annotation (2026-07-19) — VERDICT: STILL-PRESENT.** Captured before the stale branch
  `feature/gate-friction-batch` was deleted; its work is preserved at tag
  `archive/gate-friction-batch` (restore with `git branch feature/gate-friction-batch
  archive/gate-friction-batch`), relevant commit `4c8cfe9`. `check-branch-pushed` **does not exist
  as a subcommand at all** — tree-wide `git grep "branch.pushed|branch_pushed"` returns zero hits
  across `bin/`, `lib/`, `skills/`, `tests/`. The usage strings (`bin/prawduct-hook:3511`, `:3517`)
  and the dispatch table (`:3775`) carry no such gate; `lib/gates.py:874` exposes only
  `check_cumulative_critic` as a public `check_*`. Merge Flow has no push assertion:
  `skills/pr/SKILL.md:131-143` — step 1 `gh pr checks`, step 2 conflicts, step 3 evidence file
  exists, **step 4 (`:138`) merges directly**. Nothing compares local HEAD to `origin/<branch>`; no
  ahead/behind probe and no `gh pr view`/`headRefOid` check anywhere in the PR path. The one
  adjacent surface is entry ROUTING, not a gate: `skills/pr/SKILL.md:29` routes "new local commits
  not pushed" to Update, but that table is evaluated once at invocation (`:18-27`) — a commit
  created AFTER routing (exactly the change-log/bookkeeping commit Create-flow Step 1d (`:70-72`)
  forces) is never re-checked before the merge.

  *Salvageable fix-shape.* Add `lib/gates.py::check_branch_pushed(project_dir)` — read the current
  branch, require `git rev-parse HEAD` == `git rev-parse --verify origin/<branch>^{commit}`. Exit 0
  with `pushed:`; otherwise exit 1 with a DIRECTION-AWARE stderr reason derived from
  `git rev-list --count origin/<b>..HEAD` and `HEAD..origin/<b>`: `diverged` /
  `local-behind-remote` / `unpushed-commits`, plus `branch-not-pushed`, `detached-head`,
  `git-unavailable`/`git-failed`. Fail CLOSED on every uncertainty — a merge that silently drops
  commits is worse than a false block. Wire `cmd_check_branch_pushed` + usage + dispatch in
  `bin/prawduct-hook`, and add it to `skills/pr/SKILL.md` Merge Flow as a hard step BEFORE the
  merge: "on non-zero, `git push` and re-run — do not proceed."

  *Port caveats (three, all mechanical).* (1) develop's `lib/gates.py` does NOT import
  `subprocess` (imports at `:40-45` are `json, sys, Path` + `buildplan_refs, coverage,
  coverage_algebra, evidence, gitstate`) — add the import, or home the body in `lib/gitstate.py` /
  `lib/coverage.py` which already shell out. (2) Prefer the existing helpers
  `gitstate.current_branch()` (`lib/gitstate.py:137`) and `gitstate._git_head_sha()` (`:406`) over
  raw calls. (3) All the branch's stderr text and SKILL wording say "squash-merges
  `origin/<branch>`" — reword for the merge-commit default (`skills/pr/SKILL.md:138`); the hazard
  statement itself is unchanged. Merge-Flow numbering also differs (develop's flow is 1-7); insert
  before develop's current step 4.

  *Test pointers (on the archive tag).* New `tests/test_check_branch_pushed.py` (135 lines, real
  bare-origin remote fixture) — `test_fully_pushed_passes`, `test_unpushed_commit_fails`,
  `test_local_behind_remote_fails`, `test_diverged_fails`, `test_branch_never_pushed_fails`,
  `test_detached_head_fails`. Does not exist on develop.

- **[COV-4M2J]** Coverage floor is Python-only — `bin/test-reference-verify` symbol-grep can't reference non-Python (JS/TS/Go/…) changed files; bring-your-own-verifier via `--merge-into` is the only escape
  `effort: L · impact: M · area: coverage · source: builder · added: 2026-06-26 · status: open · stage: requirements · related: COV-3R9K, COV-8R2K, TST-2H9P · refs: bin/test-reference-verify (symbol-grep floor), lib/coverage.py (changed-files derivation), bin/prawduct-hook (verify-coverage, test-evidence record F4a overlay), skills/critic/review-cycle.md (Goal 1 F4b)`

  Split from COV-3R9K during the test-evidence-single-run work (build-plan-test-evidence-single-run.md, Chunk 03 — the user's "add `--from-counts`, backlog the floor" choice). COV-3R9K closed the RUN-half of the test-evidence double-run; this is the residual coverage-FLOOR gap.

  The F4a coverage floor — `bin/test-reference-verify`'s symbol-grep that populates `changes_referenced` — only understands Python symbols. On a polyglot or non-Python repo (vitest JS/TS, Go, Rust, embedded), changed source files yield an empty/honest `changes_referenced` half (no false regression today because `coverage_required` defaults OFF), but there is NO working coverage floor for those languages — the framework's "the tests actually referenced the changed code" guarantee is Python-only. Current escape: bring-your-own-verifier — a product writes its own reference output and feeds it via `bin/test-reference-verify --merge-into` (the same seam TST-2H9P exposed for monorepo tests-dir). The residual is a language-agnostic / pluggable coverage floor so non-Python products get the guarantee without hand-rolling a verifier.

  Needs a requirements/design pass (stage: requirements). Open question is the plug-point: a declared per-language verifier command (project-state knob) vs a built-in multi-language symbol grep vs ingesting native coverage-tool output (lcov / cobertura). Adjacent to COV-8R2K (make the floor file-type/language-aware for non-executable files) — both are "make the floor smarter about what it's inspecting." effort/impact are preliminary (sized at the split; confirm during design). Governance-protected (bin/, lib/) → full Critic + PR review. (builder)

- **[CRT-4Q7K]** Coded auto-detect variant of the `**Exposed API:**` Critic trigger — fire the versioning/error-model Goal-2 check on API-exposing chunks even when the author didn't declare it
  `effort: M · impact: M · area: critic/governance · source: user · added: 2026-06-24 · status: open · stage: idea · related: SEC-4Q7H, GOV-9K2T · refs: .prawduct/cross-cutting-concerns.md (Known Gaps), templates/api-contract.md, skills/critic/review-cycle.md (Goal 2)`

  Deferred follow-up from the api-design feature (cross-cutting-concerns.md Known Gaps). Today the API versioning / error-model Goal-2 Critic check fires only when a chunk author declares `**Exposed API:** <name>` in the build plan — an opt-in trigger mirroring the existing Foreign-API convention. A stronger guarantee would AUTO-DETECT API-exposing chunks from boundary-patterns globs / code (the surfaces a chunk actually touches) so an undeclared chunk still gets the versioning/error-model check, closing the "author forgot to declare it" hole. ENHANCEMENT, not a gap in shipped coverage — the opt-in path works; this hardens it against omission. Idea-stage: needs a design pass on the detection signal (boundary-patterns globs vs diff inspection) and its false-positive posture before it's buildable. Governance-protected (skills/critic) → full Critic + PR review. (user)

- **[TPL-8H3M]** Standalone error-model artifact/template — extract the error-envelope decision from api-contract.md if error-model design grows
  `effort: M · impact: M · area: templates/artifacts · source: user · added: 2026-06-24 · status: open · stage: idea · related: CRT-4Q7K · refs: .prawduct/cross-cutting-concerns.md (Known Gaps), templates/api-contract.md, .prawduct/project-state.yaml (design_decisions.api_error_model_approach)`

  Deferred follow-up from the api-design feature (cross-cutting-concerns.md Known Gaps). Today the error-model decision lives INSIDE templates/api-contract.md plus the `design_decisions.api_error_model_approach` project-state block. A DEDICATED error-model template/artifact may be wanted if error-envelope design grows in importance (richer error taxonomies, machine-readable problem-details, per-surface error contracts). ENHANCEMENT, not a gap in shipped coverage — the embedded form covers today's needs; extract only when the design surface earns its own artifact. Idea-stage: the trigger is "does error-model design grow?" — re-derive the requirement (what the standalone artifact must capture beyond the embedded block) before any template work. (user)

- **[DOC-5T8N]** Self-document the build-plan Status "derived view" behavior in templates/build-plan.md to prevent hand-editing confusion
  `effort: S · impact: S · area: templates/docs · source: user · added: 2026-06-24 · status: open · stage: idea · related: VWS-4D8J, CRT-3D9K, CRT-4Q7K, TPL-8H3M · refs: templates/build-plan.md, lib/views.py (extract_status_section, regenerate_status_section), .prawduct/change-log.md`

  Sibling to the named-but-dropped / derived-view learnings from api-design. Problem: when project-state has `views_enabled: true`, a build-plan `## Status` block is a DERIVED view of change-log `status=shipped|merged` tags (regen-views flips checkboxes at merge/release), so `[ ]` on a feature branch is correct, not a forgotten update — but nothing in the plan doc itself says so, and a session that "fixes" the checkboxes by hand has its edits silently overwritten by regen-views (happened during the api-design build: hand-flipped chunks 01/02 to `[x]`, regen-views reset them).

  Fix-shape: add a short explanatory HTML comment to templates/build-plan.md explaining that when `views_enabled` the Status is derived (don't hand-edit; flip via change-log status tags + regen-views; checkboxes track merge/release, dev-progress lives in the Context line). Make it conditional-aware — a repo WITHOUT `views_enabled` hand-maintains the checkboxes.

  Placement nuance (verified against lib/views.py): put the comment ABOVE the `## Status` heading (or in the template's top comment block), NOT inside the Status section body — `extract_status_section` (lib/views.py) spans from the `## Status` line to the next `## ` H2 and `regenerate_status_section` rewrites that block, so a comment placed inside it would be clobbered.

  Idea-stage: a small DX self-documentation fix, but confirm the exact comment text and placement against the current views.py extraction bounds before writing. (user)

- **[SEC-4Q7H]** Audit auth/authz as a holistic cross-cutting concern — confirm coherent pipeline coverage across ALL surfaces, not fragmented per-surface
  `effort: M · impact: M · area: governance/security · source: user · added: 2026-06-24 · status: open · stage: research · refs: .prawduct/cross-cutting-concerns.md (Security + Data-privacy rows), build-plan-api-design.md, skills/critic/review-cycle.md (Goal 1 auth completeness), templates/ (security-model artifact)`

  Surfaced during the api-design cross-cutting work (build-plan-api-design.md), where API auth was deliberately NOT duplicated into the API-design concern because auth belongs to the Security pipeline (Security + Data-privacy rows in cross-cutting-concerns.md; Critic Goal-1 auth completeness; security-model artifact). This audit verifies that placement is sound: trace auth/authz across the FULL pipeline (discovery structural detection → security-model artifact → builder guidance → Critic checks) and confirm it is treated coherently across ALL surfaces (API, human-interface, multi-party, unattended) rather than ad-hoc per surface.

  Look specifically for: object-level authorization / BOLA (OWASP API Top 10 #1) coverage; session vs token models; multi-party trust-boundary enforcement; and whether the security-model template prompts auth decisions strongly enough.

  Outcome: either confirm coverage is sound or identify the gaps (likely a follow-on to the api-design work). Research-stage — this is an audit/investigation, not yet a buildable task; route to discovery to advance the stage. (user)

- **[COV-5H3N]** resolve-base ignores origin/HEAD and defaults to main on gitflow repos — silent wrong-base inflates review scope and misroutes PR bookkeeping + build-plan lifecycle
  `effort: M · impact: M · area: coverage · source: user · added: 2026-06-22 · status: open · stage: design · related: PR-2H8N, REL-7P3X, MIG-6B0R · refs: lib/coverage.py (_resolve_base_branch, _DEFAULT_BASE_CANDIDATES), lib/migrate_plugin.py, skills/onboard, incoming-bugs/archive/resolve-base-ignores-origin-head-defaults-to-main-on-gitflow-repos.md · reviewed: 2026-07-10`

  When base_branch: is unset in project-state.yaml, _resolve_base_branch falls back to the hardcoded candidate list (origin/main, main, HEAD~1) and returns the first that resolves — even when the repo's declared default branch (origin/HEAD) is develop. The wrong base flows into the cumulative-Critic base, PR-reviewer base, coverage diff, classify-diff-risk, and the stamp-merged guard, so a 2-commit feature off develop is reviewed/gated as the entire develop..main promotion range, and stamp-merged refuses on develop ("integration base is main"), and Merge-Flow step 8 can take the build-plan-DELETE branch for a release-pending merge. Reported v2.1.4 from Discodon; every gitflow consumer hits it on its first PR unless they know the base_branch knob. THIS repo masks it (base_branch: develop is set). Fix-shape (either alone closes most of the gap; both is best): (1) make the default branch-aware — consult `git symbolic-ref --short refs/remotes/origin/HEAD` before the hardcoded list, prefer it when it resolves and isn't main-family (trunk repos with origin/HEAD=main unaffected); optionally warn instead of silently picking main when both a main-family branch and a non-main origin/HEAD exist. (2) set base_branch: at onboarding/migration time when origin/HEAD is non-main, so freshly-migrated gitflow repos start correct. Governance-protected (lib/) → full Critic + PR review.

  **Note 2026-07-10 (single-pr-bookkeeping):** the stamp-merged branch-guard consequence above
  is retired — no flow calls stamp-merged anymore (it is deprecated-but-callable only; hard
  removal tracked as REL-4Q9V). But the item is now MORE load-bearing, not less:
  `/prawduct:pr` create-flow Step 1d branches trunk-vs-gitflow on resolve-base, so a wrong
  default base silently misroutes the PR's change-log bookkeeping (statusless-until-release vs
  shipped-in-PR), on top of the review-scope inflation.

- **[COV-8R2K]** verify-coverage records BLOCKING missing-coverage for non-executable files — prose .md docs AND non-code config (YAML) — forcing waivers or token reference-tests on otherwise-clean chunks
  `effort: M · impact: M · area: coverage · source: user · added: 2026-06-22 · reviewed: 2026-07-19 · status: open · stage: design · related: TST-4K2P, COV-4M2J, CRT-5D8Q · refs: bin/prawduct-hook (verify-coverage), lib/coverage.py, lib/coverage_algebra.py (is_judgeable_path), skills/critic/review-protocol.md (Goal 1 rule F4b), incoming-bugs/archive/verify-coverage-records-blocking-missing-coverage-for-prose-docs.md, incoming-bugs/archive/check-pr-trivial-passes-feature-clusters-that-only-touch-existing-files.md`

  The symbol-grep coverage floor is applied to non-executable files the same as code. Two corroborating reports: (a) a chunk whose deliverables legitimately include a prose .md always produces an unsoftenable BLOCKING missing-coverage (Goal 1 F4b: "a missing-coverage line is recorded BLOCKING per file, never softened"), even though prose can't be executed; (b) a branch editing a YAML/config file with no test symbols (e.g. .prawduct/project-state.yaml) is flagged missing-coverage and verify-coverage exits 1 on an otherwise-clean branch (the "config-file-accounting gap" products already note in their own learnings). A doc-ONLY-chunk skip already exists; this is the MIXED-chunk and non-code-config version. Fix-shape: make the floor file-type/language-aware — exempt (or downgrade to NOTE) files under a docs-path policy (configurable allowlist, e.g. **/README.md, docs/**, *.md) and non-code config, or scope the floor to runner-executable languages only. Governance-protected → full Critic + PR review.

  **Salvage annotation (2026-07-19) — VERDICT: STILL-PRESENT, confirmed by executing develop's own
  suite.** Captured before the stale branch `feature/gate-fidelity` was deleted; its work is
  preserved at tag `archive/gate-fidelity` (restore with `git branch feature/gate-fidelity
  archive/gate-fidelity`), relevant commit `ae697a6`. `lib/gates.py:1067-1074` (inside
  `gates.verify_coverage`, `lib/gates.py:986`) — the bucket split is byte-identical to the branch's pre-image (`skipped` = files
  in `changes_unjudged` or absent from disk; `missing` = everything else not in
  `changes_referenced`). **No file-type test anywhere in the path.** kernel-v3 rewrote the
  *review-coverage* gates — a different mechanism — and did not touch this one. Executed
  confirmation: `tests/test_verify_coverage_gate.py:186-206`
  (`TestLegacyEvidenceCompat.test_evidence_without_unjudged_field_keeps_old_behavior`) writes
  `NOTES.md` and asserts rc==1 with `missing-coverage: NOTES.md`; ran on develop → 6 passed. A
  prose `.md` provably still produces a BLOCKING missing-coverage today. The protocol half is also
  unfixed: `skills/critic/review-protocol.md:65` still says missing-coverage lines are "BLOCKING
  per missing file … must not be softened."

  *Reachability (why it looks dormant but isn't).* `bin/test-reference-verify:239-242` routes
  non-Python files into `changes_unjudged`, which the gate skips — so a freshly-run STOCK verifier
  masks the symptom. The defect is reachable whenever `changes_unjudged` doesn't align with the
  gate's recomputed `changed` set: stale evidence (tests run, then a doc/YAML edited before
  `verify-coverage`), product-authored evidence, legacy evidence lacking the field, or a
  `coverage_level: executed` verifier. `lib/coverage.py:150-176` recomputes `changed` at gate time
  independently of when the evidence was written — that's the misalignment window. Dormant in THIS
  repo (`coverage_required: false`, `.prawduct/project-state.yaml:338`); live for any product that
  opts in.

  *Salvageable fix-shape.* Add `is_non_executable_path(path, *, exempt_globs=())` to
  `lib/coverage.py` — True when the suffix is in `{.md,.yaml,.yml,.json,.toml,.ini,.cfg,.txt}` or
  the repo-relative path fnmatches an exempt glob — plus `coverage_exempt_globs(project_dir)`
  reading an optional `coverage_exempt_paths:` list from project-state.yaml (escape hatch for paths
  whose extension looks executable but isn't). In `verify_coverage`, compute a third bucket
  `nonexec` from the would-be-missing files, subtract it from `missing`, and print
  `note: N non-executable file(s) … reported, not gated`. `unjudged`/deleted keep precedence; the
  `ok:` count subtracts `nonexec` too; an uncovered `.py` still BLOCKS. Also soften
  `skills/critic/review-protocol.md` Goal-1 F4b to informational for non-executable files. **Also
  needed:** the branch promoted `_read_list_yaml_key` from `lib/risk.py` to `lib/core.py` as
  `read_list_yaml_key` — still private on develop at `lib/risk.py:66`.

  **DESIGN NOTE — do not port blindly.** The branch invented its extension set independently of
  `coverage_algebra.is_judgeable_path` (`lib/coverage_algebra.py:59-72`), which kernel-v3
  established as THE one judgeability predicate. Re-landing a SECOND file-classification set is
  exactly the divergence CRT-5D8Q was created to kill. Express the exemption in terms of, or
  alongside, `is_judgeable_path` rather than as a fresh suffix frozenset. This is the load-bearing
  constraint on the fix-shape above.

  *Test pointers (on the archive tag).* `TestNonExecutableFilesAreExempt`
  (`test_md_only_change_passes_as_note`, `test_yaml_only_change_passes`,
  `test_mixed_change_only_executable_blocks` — the true-positive guard,
  `test_override_glob_exempts_extra_path`); `TestNonExecutableClassifier`
  (`test_known_non_executable_extensions`, `test_executable_paths_are_not_exempt_by_default`,
  `test_override_glob_exempts_matching_path`, `test_exempt_globs_reads_block_list`); plus the
  re-anchored legacy-compat test (`NOTES.md` → `src/legacy.py`).

- **[STH-6T9W]** Stop critic-review gate counts untracked operator-authored non-code files as chunk-diff scope — no Critic mode can satisfy it, forcing a waiver on a clean, fully-reviewed tree
  `effort: M · impact: S · area: stop-hook · source: user · added: 2026-06-22 · reviewed: 2026-07-19 · status: open · stage: design · related: STH-3W7F, STH-7K2A, COV-8R2K, CRT-5D8Q · refs: lib/coverage_algebra.py (is_judgeable_path), lib/evidence.py (capture_tree), lib/critic_mode.py (mode-inference subset check), lib/gates.py (session_review_verdict), incoming-bugs/archive/stop-gate-counts-untracked-operator-notes-as-chunk-diff.md`

  An untracked operator-dropped non-code file (e.g. a note placed in incoming-bugs/) is counted into the chunk-diff scope, growing it beyond what the verify-resolutions findings cover; the suggested remedy (re-run /critic chunk) can't produce a schema-valid empty-scope record (validate_critic_findings requires non-empty files_reviewed), so a waiver becomes the only exit — on a session whose code was already fully reviewed and merged. Trains waiver-reaching: when the framework's cleanest sessions end in waivers, waivers stop signaling anything. Distinct root cause from STH-3W7F (background work) and STH-7K2A (loop-counter). Fix-shape: exclude untracked non-code files outside source/test/governance roots from the chunk-diff scope; and/or allow a schema-valid scope:empty findings record. Governance-protected → full Critic + PR review.

  **Salvage annotation (2026-07-19) — VERDICT: PARTIAL. The reported HARM is eliminated; a much
  milder root cause survives.** Captured before the stale branch `feature/gate-fidelity` was
  deleted; its work is preserved at tag `archive/gate-fidelity` (restore with
  `git branch feature/gate-fidelity archive/gate-fidelity`), relevant commit `e6e9434`.
  Impact downgraded M→S accordingly.

  *What the kernel-v3 rewrite removed.* Both scope sites named above are DELETED and pinned as such
  (`tests/test_cumulative_gate.py:411-431`, `:433-435`). The gate is now composed coverage
  (`lib/gates.py:555-632` → `lib/coverage_algebra.py:197-266`, invoked from
  `bin/prawduct-hook:1393-1400`) — no scope-subset check, nothing the operator can fail. **The
  waiver-wedge is gone:** `lib/critic_consolidate.py:350-351` sets
  `files_reviewed = list(files_changed)`, so CODE derives the reviewed set from the manifest's
  diff and the model never authors it; a noise-only interval yields non-empty `files_changed`, so
  `validate_critic_findings`'s non-empty requirement (`lib/gates.py:408-410`) can no longer block.
  **The exact reported repro no longer fires at all:** the report was a `.md` dropped into
  `incoming-bugs/`, and `is_judgeable_path` returns False for non-protected `.md`
  (`lib/coverage_algebra.py:70-71`), so that interval is a free edge.

  *What survives (the milder root cause).* `is_judgeable_path` (`lib/coverage_algebra.py:68-72`)
  classifies ANY non-metadata non-`.md` path as judgeable, with no tracked/untracked distinction
  (verified by execution: `note.txt` → True, `scratch.json` → True, `tmp/data.yaml` → True). And
  `evidence.capture_tree` (`lib/evidence.py:367-405`) runs `git add -A` in a temp index, so
  untracked non-ignored files ARE inside the target tree. Dropping a `note.txt` therefore changes
  the tree SHA → the interval contains a judgeable file → not a free edge →
  `session_review_verdict` returns `uncovered` → the stop hook blocks
  (`bin/prawduct-hook:1413`+). The operator must dispatch a real Critic review whose entire subject
  is a stray note. Secondary: untracked noise inflates `delta`, and `_scope_widened`
  (`lib/critic_consolidate.py:100`) can push a legitimate verify-resolutions pass into a forced
  full re-review. Tertiary: `lib/critic_mode.py:254-263` still does a diff⊆scope subset check over
  `_get_uncommitted_code_files` (`:419-449`, includes untracked, filters only metadata) — mode
  inference only, not a gate, so a stray note silently downgrades the recommended mode.

  *Branch fix-shape (recorded for reference — DOES NOT still apply).* Three helpers in
  `lib/gates.py`: `_untracked_files` (`git ls-files --others --exclude-standard`, empty set on any
  git failure = fail closed); `_tracked_work_roots` (top-level dirs holding ≥1 tracked file,
  derived from `git ls-files` rather than hardcoded, so it adapts to any product layout); and
  `_is_untracked_noncode_noise(rel_path, work_roots)` (False if the first segment is a work root;
  else True when the suffix is not in `gitstate._PRODUCT_CODE_SUFFIXES`). Deliberately narrow —
  tracked files, code files anywhere, and non-code files UNDER a work root all stay in scope.
  **Why it can't be ported:** both call sites it patched no longer exist, and
  `_PRODUCT_CODE_SUFFIXES` is a SECOND judgeability opinion — precisely what kernel-v3
  consolidated away (see CRT-5D8Q). Only the branch's TEST corpus transfers cheaply.

  *Landing options today (pick one during design).* (a) Teach `is_judgeable_path` about
  untracked-non-code-outside-work-roots — but it is deliberately a pure path function with no git
  access, so the untracked fact must be INJECTED by the caller. (b) Exclude such files at
  `evidence.capture_tree` so they never enter the tree SHA — cleanest, but it changes what a review
  fact attests. (c) **WONTFIX** — a legitimate outcome now that the harm is "run one extra review"
  rather than "waiver or nothing"; the original waiver-training argument no longer applies.

  *Test pointers (on the archive tag).*
  `tests/test_cumulative_gate.py::test_scope_excludes_untracked_noncode_noise`;
  `tests/test_session_critic_gate.py::test_untracked_noncode_note_does_not_inflate_scope`,
  `::test_untracked_code_file_still_counts`,
  `::test_untracked_noncode_under_work_root_still_counts` (the over-exclusion guard), and
  `TestUntrackedNoncodeNoisePredicate`.

- **[WMK-4Q9T]** Work-model term tripwire flags ordinary English words and file-path fragments as ungoverned terms — desensitizes the one tripwire meant to catch real undocumented requirements
  `effort: S · impact: M · area: work-model · source: user · added: 2026-06-22 · status: open · stage: design · related: WMK-7D3R, WMK-1P4Q, GOV-7T2M, GOV-4C7X · refs: UserPromptSubmit hook (work-model term extraction), lib/work_model_index.py, incoming-bugs/archive/work-model-term-tripwire-flags-ordinary-prose-words.md · reviewed: 2026-07-16`

  The prompt-term extractor treats common adjectives/adverbs/verbs and singularized file-path fragments (e.g. "incoming-bug" from incoming-bugs/) as candidate domain terms, firing the "terms not found in any governing artifact" tripwire on most natural-language prompts. Noise PERSISTS as of 2026-06-22 — it fired on THIS very session's prompt ("urgent, wrap-up, awaiting, model-id, fold, single-owner, ceiling, cross-linked…"). Pure noise today, but desensitizes tripwire #1 (requirements-precede-code). WMK-7D3R is the staleness/rebuild sibling and explicitly says probe PRECISION was "separate, covered by the review-fixes plan Chunk 2" — verify whether that precision pass shipped before sizing; the 2026-06-11 Scriob repros + this session's recurrence show the noise is live regardless (so file NEW; if review-fixes Chunk 2 shipped a partial fix, this is the incomplete-fix follow-up). Fix-shape: stoplist/POS-filter to nouns; don't tokenize path-like strings; scope firing to build-intent prompts or recurring terms.

  **Narrowed 2026-07-02 (partial supersession by GOV-7T2M, shipped closed-by=gate-noise):** two
  of the noise classes are now fixed — maintenance verbs (refactor/rename/redesign/rework/
  remove/replace) split into MAINTENANCE_VERBS so review/cleanup prompts are no longer
  requirement-shaped at the single-orphan threshold, and the `docs/`/`methodology/` corpus globs
  are recursive so doc-subdir vocabulary no longer reads as orphaned. (Review-fixes Chunk 2's
  precision pass — the common-English frequency floor, lib/common_words.py — had also shipped;
  the 2026-06-22 recurrence was on top of it.) **Remaining scope:** path-like tokenization —
  `_WORD` (`[A-Za-z][A-Za-z'-]*`, lib/work_model_index.py:71) still extracts hyphenated
  path/compound fragments ("incoming-bug" from incoming-bugs/, "wrap-up", "model-id",
  "cross-linked") as orphan candidates — plus the optional POS/noun-filter and
  build-intent-scoping legs if the tokenizer fix alone doesn't quiet it. Effort re-sized M→S
  to match the narrowed scope.

  **Owner decision 2026-07-12 (kernel-redesign discovery) — resolution is DELETION, not a
  precision fix.** The work-model term tripwire will be deleted outright (the prompt-term
  extractor plus the work-model index machinery behind it), superseding the remaining fix-shape
  legs above (path-tokenization fix, POS/noun-filter, build-intent scoping — all moot).
  Requirements-precede-code enforcement moves to a review-time scope-check question instead
  (cf. CRT-5M9J). Subsumed by the governance kernel redesign program GOV-4C7X, which carries
  the deletion; this item stays open until the deletion actually ships, then archive it
  `closed-by:` the shipping kernel-redesign plan scope.

  **Re-checked 2026-07-16** (Critic C-B3, norm-lifecycle Chunk 2): still accurate and unresolved.
  Not implicated in the norm-lifecycle work — the jurisdiction subcommand bypasses the cached
  index, so it is unaffected by this item's noise classes.

- **[BKL-8T3W]** Backlog-accuracy structural enforcement — surface cross-session "shipped-but-not-removed" Open items (and stale-by-age) so a ready item isn't rebuilt
  `effort: M · impact: M · area: governance/backlog-tooling · source: user · added: 2026-06-21 · status: open · stage: requirements · related: BLD-4K7P · refs: incoming-bugs/archive/backlog-accuracy-stale-check-hook-plus-closed-but-not-removed-critic-goal.md, skills/critic/review-cycle.md, skills/pr/review-protocol.md, lib/backlog_probes.py`

  ENHANCEMENT (not a defect), needs a design pass before build — file at stage=requirements. Recurring
  drift: a `stage: ready` Open item (or its headline sub-claim) is shipped by OTHER, already-merged
  work and never reconciled, so the next picker rebuilds shipped work or does archaeology. Evidence: 3
  ready items in one Hallucinote session were 60–100% already shipped. Upstream report from
  Hallucinote/puzzles.

  Three CONSTRAINTS for whoever builds this (the review already mapped the overlap — scope to the
  DELTA, don't rebuild):
  1. Most of the proposal already exists — EXTEND, don't duplicate: the Critic's Backlog
     Reconciliation (skills/critic/review-cycle.md:137, final+cumulative) already does the SEMANTIC
     "this session's changes resolve an open item → NOTE archive"; the PR reviewer's R-2
     (skills/pr/review-protocol.md:58, WARNING) already flags a diff referencing closes:/closed-by: PFX
     while the item is still open; lib/backlog_probes.py's backlog-overdue-grooming advisory + the
     /prawduct:backlog summary already do age/stale. The proposed (b) Critic "closed-but-not-removed"
     goal is NOT the inverse of (a) — it largely duplicates review-cycle.md:137.
  2. The genuine UNCOVERED gap is CROSS-SESSION drift: an item resolved by work that merged on a PRIOR
     branch/session — the per-session Critic reconciliation structurally can't catch it. A
     periodic/briefing-level scan of all Open items vs recently-merged work (the report's part (a)(2))
     is the real value. Keep it ADVISORY (briefing/NOTE), never blocking.
  3. The proposed keyword/headline-grep matching is the WEAK part — high false-positive risk, the exact
     BLD-4K7P over-matching family. Prefer high-precision signals (an item's named files/functions from
     its refs/body), NOT headline keywords. The existing SEMANTIC reviewer check is more precise than
     grep for this. Consider a cheaper high-ROI partial first: a `pick`-time "this ready item may
     already be shipped — grep the code/changelog first" nudge, which catches the drift at the moment it
     costs money.

  related: BLD-4K7P (keyword-grep over-match lesson), backlog-overdue-grooming probe. (user — upstream
  report from Hallucinote/puzzles)

- **[REL-3M7K]** Release-prep must add the root CHANGELOG.md headline and gate on a green suite before tagging
  `effort: S · impact: L · area: governance/release · source: builder · added: 2026-06-21 · status: open · stage: ready · related: REL-9F2T · refs: CHANGELOG.md, hooks/banner.py (parse_changelog), skills/pr/SKILL.md, .prawduct/release-notes.md · reviewed: 2026-07-14`

  Root cause found 2026-06-21 during the hook-cli-robustness baseline check: v2.1.6 was tagged +
  version-bumped (81b28fe) but its consumer-facing root CHANGELOG.md headline was never added — the
  prep commit updated .prawduct/release-notes.md and .prawduct/change-log.md but missed root
  CHANGELOG.md. That left develop RED on
  tests/test_plugin_version_banner.py::test_changelog_has_current_version_entry (PLUGIN_VERSION 2.1.6
  absent from CHANGELOG.md) since the release, i.e. v2.1.6 shipped on a red suite.

  Two gaps: (a) release-prep updates the .prawduct views but not root CHANGELOG.md, so the
  consumer-facing headline is hand-step-only and was forgotten; (b) the release tagged without a
  green full suite, or CI does not gate tagging. Symptom already repaired (headline added in
  024bf53, sourced from release-notes.md v2.1.6 block).

  Fix-shape: wire the CHANGELOG.md headline into the /prawduct:pr release-promotion / release-prep
  flow (or generate it from the release= change-log tag like release-notes.md is), and make
  release-prep refuse to bump/tag on a non-green suite. (builder)

  Recurrence log:
  - v3.0.4 (2026-07-14): recurred (3rd+ occurrence). release-prep(v3.0.4) (3ebf914) again bumped the
    version + regenerated .prawduct/release-notes.md/change-log.md but omitted the consumer-facing root
    CHANGELOG.md headline; it had to be backfilled out-of-band in bc23ef5 ("fix(changelog): backfill the
    missing v3.0.4 headline (release-prep miss)"). Identical failure mode to the v2.1.6 root-cause find
    above — the headline remains a forgettable hand step because the fix is still unbuilt. Recurrence at
    this cadence is why impact was raised M→L on 2026-07-14: the cost of not fixing (releases shipping
    with a missing/late headline, and the CHANGELOG-current-version test flapping) now clearly exceeds
    the small effort of wiring the headline into release-prep. (reflection)

- **[STH-3K7M]** Capture `git branch --show-current` once on the SessionStart (clear) hot path
  `effort: S · impact: S · area: stop-hook · source: builder · added: 2026-06-21 · status: open · stage: ready · related: STH-6Q9D · refs: lib/briefing.py (_get_current_branch and its callers)`

  `_get_current_branch` (lib/briefing.py) is invoked redundantly on the SessionStart (clear) hot
  path — measured 4× during STH-6Q9D. The redundancy spans three separate briefing functions:
  `staleness_scan` (~L160), `assemble_session_briefing` (~L455), and `_parse_wip` (~L246
  auto-detect). So "capture once" is a cross-function thread (compute in `cmd_clear` or the briefing
  entry and pass the branch down), unlike STH-6Q9D's three local targets — which is why it was left
  out of that chunk. Same fan-out theme as STH-6Q9D (shipped hot-path-git-batching). (builder)

- **[CRT-7Q2T]** Critic's no-test-execution rule is not structurally enforced for coordinator-dispatched subagents
  `effort: M · impact: M · area: governance/critic · source: reflection · added: 2026-06-10 · status: open · stage: design · related: CRT-3X9D, CRT-8D2W, CRT-9V4T · refs: skills/critic/SKILL.md (Structural Constraints), bin/prawduct-hook (critic-begin/critic-end) · reviewed: 2026-06-10`

  During the 2026-06-10 gate-soundness cumulative review, a coordinator-pattern subagent ran the
  affected test files directly (217 passed, reported in the review summary) despite the SKILL prose
  instruction and the pure-allow tool list — which doesn't bind Agent-dispatched subagents. Same gap
  class as CRT-3X9D, whose critic-begin marker guards only `prawduct-hook clear`. The review
  conclusion was unaffected, but the boundary exists so reviews can't mutate or depend on session
  state. Fix-shape: extend the critic-active marker enforcement (or subagent tool restriction) to
  test/build execution, or have the coordinator pass an enforced `allowed-tools` to Agent
  dispatches. Priority P2. (reflection)

- **[TEL-7A4X]** Cross-project review-telemetry aggregation — aggregate and review review-cost/value stats across all Prawduct-governed products
  `effort: M · impact: L · area: governance/telemetry · source: user · added: 2026-06-10 · status: open · stage: requirements · refs: build-plan-review-proportionality.md · reviewed: 2026-06-10`

  Builds on the per-project foundation in `build-plan-review-proportionality.md` (chunk 02 ledger
  `.prawduct/.critic-reviews.jsonl` with schema_version/model fields; chunk 03 `prawduct-hook
  review-stats --json` stable machine shape with top-level schema_version/project/generated_at —
  that JSON contract is the integration point). Fix-shape sketch (requirements still open): an
  aggregator that scans known product directories (the same discovery the "reviewing product
  feedback" CLAUDE.md route uses for learnings.md), collects each repo's `review-stats --json`, and
  renders a cross-project view: review wall-clock and actionable-finding rate by mode/model/project,
  so proportionality tuning (e.g. which products' chunk reviews yield nothing, where escalation
  pays) is evidence-driven framework-wide. Open requirements: where the aggregate view lives (skill
  vs doc vs janitor section), product opt-in/privacy posture (ledgers are gitignored local state),
  and whether product plugin versions skew comparability. **Blocked until review-proportionality
  chunks 02–03 ship.** User request 2026-06-10 ("grab a backlog to enable telemetry aggregation and
  review across projects"). (user)

  Groom 2026-06-10: UNBLOCKED — review-proportionality chunks 02 and 03 both shipped in v2.1.0
  (change-log `release=v2.1.0 | status=shipped`), so the `review-stats --json` integration point
  exists. Next step is the open requirements (where the view lives, opt-in posture, version skew),
  not code.

- **[TEL-2B6K]** Governance ledger phase 2 — record gate-block + probe-fire events and finding dispositions
  `effort: M · impact: M · area: governance/telemetry · source: builder · added: 2026-06-10 · status: open · stage: design · related: TEL-7A4X · refs: lib/ledger.py, lib/telemetry.py, lib/gates.py · reviewed: 2026-06-10`

  The v2.1.0 ledger records review.critic/review.pr only; proportionality tuning cannot answer "how
  often did each gate block?", "which probes fire and where?", or "were findings acted on or
  ignored?" (actionable-rate is currently severity-presence, not disposition). Phase 2: (a)
  `gate.blocked` / `probe.fired` event kinds (the schema already reserves unknown-kind
  forward-compat; consumers skip unknowns); (b) a lightweight finding-disposition record at
  resolution time feeding an honest actionable-rate. Design questions: where dispositions get
  captured (verify-resolutions already walks findings — a natural hook), and volume control for
  gate events. Feeds TEL-7A4X cross-project aggregation. (builder)

- **[CRT-5Q8W]** Skill prose clarity micro-fixes from the 2026-06-09 review (critic protocol wording, designer-handoff note, backlog pick defaults, framework-checks example)
  `effort: S · impact: S · area: critic · source: builder · added: 2026-06-09 · status: open · stage: ready · closes: PR-3J6W · related: PR-3J6W, CRT-6F2N, MET-3Q8V · refs: skills/critic/review-protocol.md, skills/critic/review-cycle.md, skills/critic/framework-checks.md, skills/critic/SKILL.md, skills/backlog/SKILL.md, skills/pr/SKILL.md · reviewed: 2026-07-03`

  Batch of small wording fixes from the skills review agent, none changing behavior: (1) critic
  review-protocol.md 'Decide checks from signals below' is vague — state that the resolved MODE
  determines which goals apply, with a pointer to review-cycle.md. (2) ~~critic SKILL.md Getting
  Started: add a one-line note that Type: designer-handoff chunks exit early without a findings
  file, so an agent that skips the protocol read still knows the special case.~~ **Resolved** by
  review-fixes ch.3's CRT-6F2N fix (2026-06-10, feature/review-fixes). (3) review-cycle.md
  learnings cross-check: note that if a later learning revokes/softens the original, the latest
  learning wins (currently assumes learnings are infallible). (4) framework-checks.md Check 7: add
  a concrete avoid/prefer example for 'strengthening the dynamic generation system'. (5) backlog
  SKILL pick: document the combined effect of missing effort/impact defaults (2/2 = 1.0 score)
  explicitly; drop the stale Q6 label. (builder)

  2026-06-10: sub-item (2) resolved by review-fixes ch.3's CRT-6F2N fix; sub-items (1), (3), (4),
  (5) remain open.

  2026-06-10 (merged from PR-3J6W residual): the audit verified PR-3J6W sub-items 1-3 are resolved
  (release-promotion guard now sits pre-routing via REL-8K3M; Step 2 names its re-check loop; Step
  1b made imperative in #89). The surviving piece joins this batch as sub-item (6): decide
  PR-review evidence-file retention — archive to .prawduct/.pr-reviews-archive/ vs document why
  deletion is intended. Full original body preserved on the archived PR-3J6W.

  2026-07-03 post-prose-diet check (branch feature/prose-diet; chunks 02-03 rewrote
  review-protocol/review-cycle/framework-checks): the diet compressed and merged the
  surrounding text but ABSORBED NONE of the open sub-items — all of (1), (3), (4), (5), (6)
  still apply, at slightly shifted locations. (1) "Decide checks from signals below" survives
  verbatim as activation step 6 (review-protocol.md:12); the Modes block above it does map
  mode→goals with a review-cycle.md pointer, so the residual fix narrows to making step 6
  reference that mapping. (3) the Learnings Cross-Check (now in review-cycle.md, "Learnings
  Cross-Check") still assumes learnings are infallible — no latest-learning-wins note. (4)
  framework-checks.md Check 7: the diet merged the Test/Plan-level-generality bullets into one
  but added no concrete avoid/prefer example for "strengthening the dynamic generation system".
  (5) backlog SKILL pick: the diet only repointed the discovery/planning routes to
  /prawduct:methodology; the score line documents missing→2 ("unknown-middle") but not the
  combined 2/2 = 1.0 effect, and the stale "(Q6)" label remains. (6) untouched.

- **[MET-5C2H]** Holistic context/token-budget audit — manage what fills the context window, don't dodge ceilings
  `effort: M · impact: L · area: methodology · source: user · added: 2026-06-08 · status: open · stage: research`

  The per-file token-budget tests (`building.md` <4850, critic `review-protocol.md` <3120) are proxies for
  context-window cost, but they (a) don't measure the *whole* always-loaded surface (session digest +
  product CLAUDE.md anchor + whatever methodology gets read on demand per work cycle), and (b) invite a
  "we hit a ceiling, put the tokens in a file with headroom" reflex that optimizes the wrong thing —
  content lands in a less-natural home to dodge a budget instead of asking whether the budget should rise.
  Surfaced during backlog-rework Chunk 05 (placing C-B checks in `review-cycle.md`): there the file *was*
  the natural home, but the heuristic itself is a smell. **Research-stage** — investigate before designing:
  enumerate every always-on / per-cycle context surface and its size; estimate per-token ROI (is every
  existing token earning its place?); decide whether budgets should be holistic (a total always-on ceiling)
  rather than per-file; and only raise a per-file budget when every existing token is high-ROI. Output: a
  recommendation + (likely) a revised budget model. Then it can advance to `design`/`ready`. (user)

  — 2026-06-22: the critic-protocol-budget bump (review-protocol.md ceiling 3120→3350; change-log + PR #103) is a data point for this audit — a per-file ceiling raised AFTER a lean-audit (file at 3116/3120, every token load-bearing, relocating the one movable block would fragment the instructions), i.e. the reasoned posture this item asks for, not a ceiling-dodge. Does not close this (the broad holistic budget audit remains open).

- **[ADR-7X2M]** Adversarial review agent (4th review-agent role) — RFC: systematic edge-case / attack-surface generation
  `effort: L · impact: M · area: methodology · source: user · added: 2026-06-06 · status: open · stage: requirements · related: CRT-9V4T, PRR-4M9T, JAN-4F7M · reviewed: 2026-06-10`

  RFC for a FOURTH independent review agent alongside Critic / PR-reviewer / Janitor, with the
  opposite goal — make the code *break*, not work: systematic edge-case / attack-surface generation.
  **Opt-in per project (default disabled).** Defense-in-depth via THREE independent attack-surface
  identification points: (1) **Planning** — build-plan chunks declare an `attack_surfaces:` field (an
  empty list is a valid declaration; the field itself is required); (2) **Builder** — verifies the
  actual surfaces touched at chunk-end and prompts the user for an opt-in adversarial pass when the
  diff matches the surface taxonomy; (3) **Critic Goal 8** — independent diff inspection backstop
  (WARNING on an undeclared touched surface, or a declared-but-undispositioned surface). Plus a
  pre-release `/adversarial --sweep-since-last-release` sweep.

  **NOTE — needs rework, not a merge:** the original RFC targeted the pre-2.0 `agents/` +
  `templates/critic-review.md` layout (both since removed). A real implementation must be reworked
  onto the current plugin `skills/` architecture; treat as **new feature work**, not a merge. Full
  original design is preserved verbatim at git tag `rfc/adversarial-review` (commit `967b861`).
  Author: Jason-Vaughan. Type: feature/methodology, size: medium-large. (user)


- **[PR-2H8N]** Key the `/pr` release-promotion guard off `resolve-base` instead of hardcoded branch names
  `effort: S · impact: S · area: pr · source: critic · added: 2026-06-06 · status: open · stage: ready · related: REL-8K3M · reviewed: 2026-07-17`

  REL-8K3M's release-promotion guard in `skills/pr/SKILL.md` hardcodes `develop`/`main`/`master` to
  recognize a release/integration context. The skill's own merge-flow (step 7) already distinguishes
  trunk-vs-gitflow generically via `prawduct-hook resolve-base`. A repo with a custom `base_branch`
  name (or an unusual release-surface name) would slip past the guard. Kept a NOTE during REL-8K3M
  because the guard is judgment-admitting prose an LLM can generalize, the doc reference is already
  present, and REL-8K3M targets prawduct's own gitflow case. Fix-shape: have the guard compare the
  current branch to `resolve-base`'s output (the integration base) and to the release surface, rather
  than a fixed name list. Filed from the REL-8K3M cumulative Critic NOTE on 2026-06-06. (critic)

  Reviewed 2026-07-17 (ambient-merge-commit-default Critic C-B3): remains valid and unaffected by the squash→merge-commit default flip — the guard-keying gap is independent of merge strategy.

- **[WMK-1P4Q]** Work-model parent-map injection (B2) + optional `vocabulary:` frontmatter convention
  `effort: M · impact: M · area: hooks · source: critic · added: 2026-06-06 · status: open · stage: idea · related: WMK-7D3R · refs: docs/work-model-spec.md, docs/work-model-enforcement.md · reviewed: 2026-06-10`

  Deferred from the work-model build (confidence-gated). A SessionStart hook would inject a compact,
  capped "parent map" (governing docs + 1-line scope) as ambient awareness, complementing the shipped
  *active* UserPromptSubmit nudge. Deferred because its value over the active nudge is medium-confidence
  and it adds ambient per-session tokens (review NOTE-7) — earn with usage evidence (false-positive /
  miss data from the live nudge). Also document the optional `vocabulary:`/`governs:` frontmatter
  convention in artifact templates (the lib already supports it; auto-extract is the default). See
  `docs/work-model-spec.md` Part C and `docs/work-model-enforcement.md`.

- **[LRN-3F8K]** Reconcile the dangling sentinel on the "Framework ownership follows the write strategy" learning
  `effort: S · impact: S · area: learnings · source: critic · added: 2026-06-04 · status: open · stage: design · refs: .prawduct/learnings.md · reviewed: 2026-06-10`

  `audit-learnings` reports an error: the learning "Framework ownership follows the write strategy,
  not just registry membership" carries `sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip`,
  but `tests/test_prawduct_sync.py` was deleted with the file-sync engine in M4 (v2.0.3) — so the
  sentinel is dangling and the audit flags it as a failing sentinel (which blocks the learning's
  retirement). Pre-existing (M4-era); surfaced by the rigor-and-stance cumulative Critic as outside
  that bundle, flagged rather than fixed inline (Scope Discipline). Fix-shape: decide whether the
  write-strategy-ownership contract still has a live equivalent test (repoint the sentinel to it), or
  the learning has outlived its mechanism (drop the sentinel annotation / retire the learning) — a
  one-line annotation fix once decided. Filed from the v2.0.7 release audit. (critic)

- **[STN-6K3D]** (Optional) Ship a non-forced `output-styles/` style power users can voluntarily select
  `effort: S · impact: S · area: agent-stance · source: builder · added: 2026-06-04 · status: open · stage: ready · reviewed: 2026-06-10`

  rigor-and-stance Chunk 02 placed the agent stance in the always-on session digest because a
  `force-for-plugin` output style HARD-OVERRIDES (clobbers) a consumer's own output style and does not
  compose — disqualifying for unconditional, composable governance (verified against the Claude Code
  output-styles docs, 2026-06-04). A *non-forced* output style is a separate, safe nice-to-have: ship
  `output-styles/<name>.md` (no `force-for-plugin`) so power users can OPT IN to the prawduct voice via
  `/config` without clobbering their own style. Low priority — the digest already delivers the stance
  unconditionally; this is pure ergonomics. Filed from the rigor-and-stance cumulative Critic
  (Complete Delivery — the plan deferred this). (builder)

- **[STH-4D2X]** Decide whether the trivial/doc-only file-set gate should also protect a consumer's own `.claude/skills/`
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-06-03 · status: open · stage: requirements · related: STH-1W5N · reviewed: 2026-06-10`

  The waiver-pragma branch (W2-C1) fixed `_classify_trivial_change` to bound `skills/` (the framework
  repo's own skill definitions) instead of the deleted `agents/`. Open question it surfaced: in a
  CONSUMER repo, a product's own skills live at `.claude/skills/` (not top-level `skills/`), and
  `_is_metadata_path` no longer excuses them (M4 made `.claude/skills/` count as gated code). Should
  editing `.claude/skills/foo/SKILL.md` in a `Type: trivial`/doc-only chunk trip the catastrophic-
  blast-radius bound? A product skill is important but arguably not "governs all future work"
  catastrophic the way the framework's own `skills/`/`methodology/`/`templates/` are. Changing it
  affects every consumer, so it needs a deliberate decision + test, not a silent add. Filed from the
  2.0-rock-solid pass, 2026-06-03. (builder)

- **[CRT-9V4T]** Verify (or harden) interactive enforcement of the Critic fork-skill's `allowed-tools` cap
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-01 · status: open · stage: research · related: CRT-7Q2T · reviewed: 2026-06-10`

  Surfaced during v2.0.0 Chunk 4 empirical verification. The Critic's structural "no pytest / read-only git" guarantee rests on a `context: fork` skill with a pure-allow `allowed-tools` list (pytest unmatchable). `test_critic_skill_metadata.py` pins the *list shape* (no allow pattern matches pytest), and CLAUDE.md calls the constraint "structural, not behavioral." But a Chunk-4 probe found that under headless `claude -p`, a fork-skill with `allowed-tools: Read, Bash(git status *)` still ran a NON-allow-listed `echo` (marker printed) — i.e. headless `-p` did not enforce the allow-list as a hard cap. This does NOT prove a hole: the real Critic runs **interactively** (forked from a `/critic` invocation), where the cap is designed to apply, and the probe couldn't exercise that path. But it means the interactive enforcement is **assumed, not hermetically verified**, and the "structural" claim is only as strong as that assumption. Pre-existing — affects today's file-sync Critic identically; Chunk 4 introduced no regression (frontmatter byte-identical). Relates to memory `feedback_critic_no_test_execution` and learning CRT-2M5P. Fix-shapes: (a) an interactive-mode verification (manual or scripted) that confirms a forked `/critic` is actually denied a non-allow-listed Bash command — establishes whether the cap is structural or merely prompt-suppression; (b) if (a) shows it's not a hard cap, add a belt-and-suspenders **PreToolUse guard hook** in the plugin `hooks/hooks.json` that blocks pytest/`git checkout`/tree-mutation specifically when the calling agent is the critic (needs the hook to be able to scope to the subagent — itself unverified); (c) at minimum, soften the "structural, not behavioral" wording in CLAUDE.md to match what's actually verified. Open question: does Claude Code treat skill `allowed-tools` as a hard deny-cap in interactive mode, or as a no-prompt allow-list with a separate ask-fallback for unlisted tools? Resolve (a) before relying further on the claim. Filed from Chunk 4 verification on 2026-06-01. (builder)

- **[STH-7K2A]** Stop-hook structural loop-detection counter (defense-in-depth on top of v1.5.2's discoverability fix)
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-23 · status: open · stage: design · closes: v1.5.2 discoverability half · related: STH-3W7F · reviewed: 2026-06-10`

  v1.5.2 (2026-05-23) shipped the discoverability piece: all four blocker stderr messages now name `.gates-waived`, the JSON shape, and `build-governance.md` so agents stuck in unsatisfiable gate states can declare a waiver. The structural piece is still open. Pathology: even with the escape hatch named in the blocker text, an agent can in principle ignore it and continue re-firing the same gate. Defense-in-depth fix-shape: track stop-hook fire count per session in a new `.prawduct/.stop-fire-count` file recording `{count, blocker_signature, ts}`. On the Nth (e.g., 3rd) consecutive fire with the same signature and no progress (no new Critic findings, no new waiver, no diff change since last fire), either (a) escalate the blocker text to name the loop explicitly and force-surface the waiver mechanism above the existing prose, or (b) auto-downgrade to advisory (stderr-only) on the assumption that the agent has seen the gate and made an informed call. (a) is conservative; (b) is firmer about not burning tokens. Auto-clear on session start. Open design questions: per-blocker counter or session-wide? what counts as "progress" (any diff change or only changes that materially address the gate)? should the counter persist if the blocker signature changes mid-session? Filed from v1.5.2 release (2026-05-23) as the deferred structural half of the original infinite-loop bug; the original "discoverability" half is shipped and the backlog entry closes against v1.5.2's change-log entry. (reflection)

- **[MIG-6B0R]** Recommend gitflow as the default git strategy + strip prawduct artifacts on deploy-to-main
  `effort: L · impact: M · area: migration · source: builder · added: 2026-05-19 · status: open · stage: requirements · reviewed: 2026-06-10`

  Two coupled proposals:
  1. **Recommend gitflow** (`develop` for ongoing work, `main` as the deployed/released branch, feature/release/hotfix branches off `develop`) as the prawduct-recommended workflow. Captured in `project-preferences.md` (or a new `methodology/git-strategy.md`) with rationale: prawduct's session-artifacts churn pattern fits gitflow's "develop is mutable, main is immutable releases" split much better than trunk-based flow, where every session-edit lands on the deployable branch.
  2. **In gitflow repos, strip prawduct artifacts from `main` when promoting `develop` → `main`** (or when pushing directly to `main`). Filter scope:
     - **Strip:** `.prawduct/` contents — `backlog.md`, `build-plan.md`, `artifacts/`, `learnings.md`, `learnings-detail.md`, `change-log.md`, `.session-*`, `.critic-findings.json`, `.test-evidence.json`, etc. (governance bookkeeping, not deployment payload).
     - **Strip:** prawduct-owned hooks/skills — `bin/prawduct-hook`, `.claude/skills/{critic,pr,janitor,learnings,prawduct-doctor}/SKILL.md`, framework-managed `.claude/settings.json` hook entries.
     - **Keep:** `docs/` and `documentation/` (real product documentation, not governance artifacts).
     - **Keep:** project-owned skills/hooks (anything in `.claude/skills/` that's NOT in the prawduct-managed set — user-authored skills stay).
  Fix-shape: probably a `prawduct-doctor deploy-to-main` (or `prawduct-deploy`) subcommand that performs a filtered merge/squash — strips the listed paths from a temp index, commits the cleaned tree to `main`, leaves `develop` intact. Alternative: a git pre-receive hook recipe in `methodology/git-strategy.md` that products copy into their own remote. Need to decide which paths are framework-canonical (centralizable in `core.py`'s MANAGED_FILES + a new `DEPLOY_STRIP_PATHS` set) vs. project-configurable. Open question: does the filter run on every push to main, or only on explicit `prawduct-doctor deploy` invocations? Filed from user request on 2026-05-19. (builder)

  Groom 2026-06-10: premise partially obsoleted — the strip-list names file-sync-era files
  (bin/prawduct-hook, framework-managed skills in product repos) that plugin-governed products no
  longer commit. The residual want (keep governance bookkeeping like .prawduct/ state off a
  deployed main) may still be real; re-derive the requirement against the plugin-era reality
  before any design. Stays stage: requirements.

- **[BLD-5V8F]** F3: extend `verify-chunk-refs` beyond file paths
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-18 · status: open · stage: requirements · related: BLD-2R9X, BLD-8F2Q · reviewed: 2026-06-10`

  v1.4 Chunk 02 (F3) shipped file-path verification only; the original plan also called for symbol (function/class names) and backlog-ID verification. Deferred during build because (a) symbols in prose are often approximate (`parse_func` vs implementation's `_parse_func`) so strict grep produces false positives requiring fuzzy match; (b) this project's backlog has no formal IDs (bullet titles, not e.g. `BL-123`), so the check would be inert here and need per-project ID convention. Add when a project surfaces a concrete need: define matching rules (substring grep across configured source roots for symbols; project-preferences `backlog_id_pattern` regex for backlog refs) and extend `_parse_build_plan_chunk_refs` to return `symbols` and `backlog_refs` lists alongside `file_paths`. Note: this project now HAS formal backlog IDs (`[PFX-XXXX]`) post-migration, so the backlog-ID half is newly actionable. Filed from /critic NOTE on 2026-05-18. (critic)

- **[MET-9K4R]** Workflow-values schema/validator
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-01 · status: open · stage: design · reviewed: 2026-06-10`

  Workflow preferences (`Branching: direct`, `PR creation: wait_for_user`, `PR merge: wait_for_user`) are read by `building.md` and `/pr` but have no allowed-vocabulary or shape check. A typo or unknown value would silently default. Candidate: small Critic checklist line ("Workflow values must be one of X / Y / Z") OR a tiny config-presence test. Low priority — current values are stable. (critic, 2026-05-01)

- **[CRT-6T1V]** Critic check: test helpers duplicating production logic
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · stage: design · reviewed: 2026-06-10`

  Cross-product reflection audit (Apr 16) surfaced a recurring drift hazard in discodon: test files re-implement production calculations (LogQL builders, SDK result parsing) rather than importing the shared helper, so tests keep passing while production drifts. Evidence: discodon/reflections.md §2026-04-14 "Pattern worth keeping". Candidate: extend Goal 1 or Goal 7 in skills/critic/review-protocol.md — when a test performs a calculation/parsing operation that exists in production, flag as WARNING unless the test is deliberately testing the helper itself. Needs design work on detection heuristic (string-matching is noisy; AST match is heavier). (reflection)

- **[CRT-1B6Q]** Critic check: stateful objects in shared_kwargs need lifecycle cleanup
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-15 · status: open · stage: design · reviewed: 2026-06-10`

  Discodon's multi-tool coordinator pattern passes stateful objects (PendingVoiceSlot, prior voice_getter closures) via `shared_kwargs` to multiple tools. Critic caught lifecycle bugs (missed_intro false-positives when idle) only after complex state interactions emerged. Evidence: discodon/reflections.md §2026-04-15 V0.5-5. Candidate: extend Goal 6 (The System Can Be Understood) — when an object with enter/exit/close methods is shared across tools, verify owner tool's stop() drains/closes it. Generalizes beyond discodon's specific pattern to any DI/coordinator framework. (reflection)

- **[CRT-5N3F]** Critic false positives from fork-context limits
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · stage: research · reviewed: 2026-06-10`

  Discodon archive (Feb–Apr 2026) has 4 confirmed cases where Critic misread code: Mar 24 shutdown event closure, Mar 25 eval doc merge (3 of 4 prior findings false), Mar 28 ARIA A1/A2 missed an existing `model_config = ConfigDict(str_strip_whitespace=False)` override, plus branch-switching confusion. Root cause: `context: fork` can't see overrides spanning files / inheritance / closures. Investigate whether Critic's research phase needs a wider read budget for inheritance chains, or whether prompt engineering can compensate. (reflection)

- **[CRT-8D2W]** Critic-in-worktree as structural fix for session-file conflicts
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-03-25 · status: open · stage: requirements · reviewed: 2026-06-10 · related: CRT-3X9D`

  v1.3.3 gitignored build-plan.md and v1.3.4 added `_untrack_session_files()`, but the user explicitly suggested running Critic in a separate worktree to avoid touching session files in the active tree at all. Mar 25 discodon avatar_description session captured this when branch-switching during Critic review caused merge conflicts on `.session-handoff.md` and backlog. Worth designing as a follow-up to the gitignore approach. (reflection)

  **Premise partially obsoleted — reassessed 2026-06-10:** the original motivation rested in part on
  the build plan being a *gitignored* session file; gate-soundness ch.3 (feature/gate-soundness) made build
  plans **tracked**, so that half of the conflict surface is gone. The residual rationale is
  narrower: the remaining gitignored session files (`.session-handoff.md`, `.critic-findings.json`,
  `.session-reflected`, …) plus the broader isolation argument — an independent reviewer should not
  be able to mutate the session tree at all (the same invariant CRT-3X9D enforces at the mutation
  site via the critic-begin/critic-end guard). Before any design work, re-derive the requirement
  against the current tracked-build-plan + critic-session-guard reality; the worktree approach may
  now be redundant defense-in-depth rather than a structural fix. (critic, gate-soundness cumulative
  review note)

- **[TST-4P8H]** Flaky tests under parallel execution (xdist)
  `effort: M · impact: M · area: tests · source: builder · added: 2026-04-16 · status: open · stage: research · reviewed: 2026-06-10`

  Re-validated 2026-06-03: 5 of the 6 originally-named tests were removed with the file-sync engine (M4) — only `TestStopPrReviewGate::test_stop_clean_without_pr` survives. The narrow open question is whether that surviving subprocess-heavy test (and peers) still flake under `-n10`. The depth_cap test creates 111 git subprocess commits in a loop — when 9 other xdist workers are simultaneously doing similar subprocess-heavy work, the system runs out of fork resources / hits IO contention and the test times out. Passes 100% of the time when run in isolation or with reduced parallelism. Root cause likely race conditions in the subprocess-based hook tests sharing process-level state or temp dir contention. (builder)

  Groom 2026-06-10 (audit refresh): no active flakes; conftest now auto-groups by directory under
  xdist and the heavy git suites (test_governance_ledger, test_cumulative_gate) use sterile-HOME
  isolation. New evidence in the same family: test_audit_learnings hit a pytest-timeout worker
  crash under full-suite xdist (2026-06-10, worked around by pointing at a tmp repo). Item narrowed
  to: give the residual heavy tests explicit timeouts or a dedicated xdist group; close when the
  suite runs clean at -n10 repeatedly.

- **[STH-7B5N]** Session lock file for concurrent session detection
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-04-16 · status: open · stage: ready · reviewed: 2026-06-10`

  Advisory lock file in product-hook clear/stop to warn when another Claude session is active on the same project. Agreed on non-blocking approach with staleness timeout (~4 hours). (builder)

- **[BLD-7W2J]** Single-slot `active_build_plan` vs parallel in-flight plans
  `effort: M · impact: M · area: governance/planning · source: critic · added: 2026-06-10 · status: open · stage: idea · related: REL-4T8N · refs: lib/core.py (resolve_build_plan_path), methodology/planning.md`

  Two concurrent feature branches (feature/review-fixes → `build-plan-review-fixes.md`,
  feature/gate-soundness → `build-plan-gate-soundness.md`) each set the one `active_build_plan`
  pointer in `project-state.yaml`, guaranteeing a same-line merge conflict on develop — after which
  one plan is invisible to pointer-resolved governance (stop hook, `infer-critic-mode`,
  `verify-chunk-refs`) until repointed. planning.md's new "Plan lifecycle on gitflow" paragraph
  covers only the *serial* release-pending case; gate-soundness ch.3 (tracked plans) + scope-named
  files make parallel plans more likely. Design work needed: model multi-plan state (e.g. a plan
  list, or per-branch resolution) or document the parallel-branch convention. Related: REL-4T8N
  solved the *release-side* multi-plan problem (regen-views enumerates change-log scopes instead of
  the pointer) but the in-flight pointer remains single-slot. Filed from fable test-reviewer NOTE on
  the gate-soundness bundle, 2026-06-10. (critic)

- **[MET-7R4J]** Methodology/CLAUDE.md redundancy and prompt-quality pass — hard rules stated 4-6x across always-loaded surfaces
  `effort: S · impact: M · area: methodology · source: builder · added: 2026-06-09 · status: open · stage: ready · related: MET-5C2H, MET-3Q8V · refs: CLAUDE.md, docs/principles.md, methodology/building.md, methodology/planning.md, methodology/session-digest.md · reviewed: 2026-07-03`

  From the 2026-06-09 framework review (methodology-as-prompts agent). For Opus/Fable-class models, restating a rule with varied phrasing creates interference, not reinforcement. (1) Consolidate to one canonical statement + cross-refs: Tests Are Contracts appears 6x (CLAUDE.md, principles.md, agent-stance.md, building.md 2x, session-digest.md); the mid-build-requirement rule has 8+ phrasings; the Critic mandate appears 6x with escalating emphasis. (2) Remove emphasis escalation: CLAUDE.md 'STOP. Read this before writing ANY code' caps — prompt-rot pattern that also misstates Critic timing (Critic runs after code). (3) Compress planning.md Foreign API Verification (~40 lines to ~15: rule + when-to-apply + one worked example; move match mechanics to the Critic protocol). (4) Add one sentence to building.md Before You Build: re-review the plan's Open assumptions as code reveals new facts (assumptions are recorded at plan time but never checkpointed mid-build). Note: digest-vs-CLAUDE.md duplication is handled separately by the review-fixes plan Chunk 4 (slim framework-repo digest); this item is the within-file redundancy pass. Token-budget guardrail tests on methodology files will need adjusting downward, not up. (builder)

  2026-07-03 superseded-check (prose-diet cumulative Critic reconciliation, branch
  feature/prose-diet — MET-3Q8V's own note said prose-diet "largely supersedes" this item).
  What prose-diet DELIVERED: sub-item (1) largely — `methodology/agent-stance.md` deleted
  (one whole duplicate surface gone), building.md's Tests-Are-Contracts restatements removed
  (now 0 in-file; canonical lives in principles.md + CLAUDE.md list + digest), and the
  mid-build-requirement phrasings compressed by the D1-D6 reconcile; sub-item (3) fully —
  planning.md Foreign API Verification is now ~17 lines (rule + when-to-apply + pointer to the
  filled template example). RESIDUE still open, now the whole of this item: sub-item (2) —
  CLAUDE.md's "**STOP. Read this before writing ANY code**" emphasis-escalation caps survive
  verbatim (line ~94), still misstating Critic timing; sub-item (4) — building.md still has no
  mid-build open-assumptions re-review sentence (assumptions recorded at plan time, never
  checkpointed). Effort trimmed M→S to match the residue.

- **[JNT-9R2K]** Janitor SKILL: move the investigation-theme taxonomy to a companion reference file; close the Step 2.5 to Step 7 backlog loop
  `effort: S · impact: S · area: janitor · source: builder · added: 2026-06-09 · status: open · stage: ready · refs: skills/janitor/SKILL.md · reviewed: 2026-06-10`

  From the 2026-06-09 framework review (skills agent). (1) The nine investigation themes (~100 lines, ~50% of the skill) read once per janitor run — move theme details to a bundled companion file (the pattern the Critic already uses with review-protocol.md etc.) and keep SKILL.md as dispatcher + process. (2) Clarify that Step 2.5 Backlog Health emits read-only NOTE findings and Step 7 Reconcile is where those findings drive /prawduct:backlog update calls — the linkage is currently implicit. (3) Reframe the 'fresh eyes' line toward pattern-detection + infer-and-confirm, and say what to do when the user cannot confirm a preference divergence (file a backlog item rather than resolving unilaterally). (builder)

- **[WMK-7D3R]** Work-model index never rebuilds on artifact deletion — retired vocabulary lingers
  `effort: S · impact: S · area: work-model · source: builder · added: 2026-06-09 · status: open · stage: design · related: WMK-1P4Q, GOV-7T2M · refs: bin/prawduct-hook, lib/work_model_index.py · reviewed: 2026-07-16`

  From the 2026-06-09 framework review. The staleness check (bin/prawduct-hook, build-index path) compares
  remaining artifact mtimes to the index mtime, so deleting an artifact never triggers a rebuild and its
  vocabulary lingers between sessions. Mostly masked by build-index force=True at SessionStart — decide
  whether to fix (include the artifact file-set in the staleness fingerprint) or document the SessionStart
  rebuild as the intended guarantee. Note: probe precision (false positives on common English) is separate,
  covered by the review-fixes plan Chunk 2. (builder)

  **Re-checked 2026-07-02** at GOV-7T2M ship (gate-noise): still open, content unchanged in kind —
  gate-noise widened the corpus (`docs/`/`methodology/` now recursive in
  `_work_model_corpus_paths`) but did not touch the mtime-only staleness check, so the
  deletion-doesn't-rebuild gap now spans a strictly larger file-set (marginally more relevant,
  same fix-shape: file-set in the staleness fingerprint, or document SessionStart force-rebuild
  as the guarantee). The probe-precision thread this item pointed sideways at continued in
  GOV-7T2M/WMK-4Q9T.

  **Re-checked 2026-07-16** (Critic C-B3, norm-lifecycle Chunk 2): still accurate and unresolved.
  Not implicated in the norm-lifecycle work — the jurisdiction subcommand bypasses the cached
  index, so the mtime-only staleness gap doesn't affect it.

- **[CRT-6J4P]** Mode-inference rule 1b chains across work-cycle/bundle boundaries — prior bundle's cumulative vouches for a new plan's first chunk
  `effort: S · impact: S · area: governance/critic · source: reflection · added: 2026-06-10 · status: open · stage: design · related: CRT-8W3F, CRT-4J8W, CRT-7B4M, CRT-2N7V, CRT-8H3R · refs: lib/critic_mode.py (_rule_postfix_fix_fires, _cumulative_anchor), skills/critic/SKILL.md · reviewed: 2026-07-19`

  Observed 2026-06-10: on a brand-new branch/plan (feature/do-next, first chunk), inference picked
  verify-resolutions extending the PREVIOUS released bundle's cumulative (3c4b627,
  changelog-lifecycle v2.1.1) instead of chunk mode. Commit-coverage keeps the record sound, but
  cross-bundle chaining is surprising; consider bounding rule-1b to the current branch/merge-base or
  active plan scope. (reflection)

  **kernel-v3 refresh (2026-07-13, chunk-06 cumulative review batch).** Still live in v3, with a
  smaller blast radius. The v2 multi-link chain arm (`extends_cumulative`) died in the cutover,
  but rule 1b (`_rule_postfix_fix_fires` / `_cumulative_anchor` in `lib/critic_mode.py`) still
  anchors to whatever cumulative record sits in the single-slot `.critic-findings.json` derived
  view, with no branch/merge-base/plan bound — so a prior bundle's cumulative can still vouch a
  verify-resolutions recommendation for a new plan's first chunk. Under v3 the consequence is
  proportionality only (a verify pass over a surprising cross-bundle delta): the gates compose
  tree-keyed facts, so coverage stays sound whichever mode gets recommended. Fix shape: bound
  rule 1b to the current branch/merge-base or active plan scope — same ancestor-guard family as
  CRT-8H3R; consider fixing both in one pass.

  **Salvage annotation (2026-07-19) — VERDICT: STILL-PRESENT, and the deleted branch never
  actually covered this item.** ⚠️ **Correction to the record.** Commit `af8350f` on
  `feature/gate-fidelity` (preserved at tag `archive/gate-fidelity`) has a message claiming it
  addresses "vouching across bundle boundaries (CRT-6J4P)". **It does not.** The filed observation
  above is a *same-lineage* cross-bundle chain: on a brand-new branch/plan, inference extended the
  previously RELEASED bundle's cumulative. Once that bundle merged to develop and the new branch
  was cut, its `commit_reviewed` IS an ancestor of HEAD, so `git merge-base --is-ancestor` returns
  0 and rule 1b still fires. The branch's ancestor guard closes only the sibling-BRANCH sub-case,
  which is CRT-8H3R's territory, not this one. Do not treat this item as "fixed on a branch
  somewhere" — and do not treat the CRT-8H3R fix as closing it.

  *Evidence the defect is live on develop.* `lib/critic_mode.py:285-337` gates rule 1b on exactly
  four things — clean tree (`:304`), slot record mode is cumulative (`:313`), anchor resolves
  (`:317`), and a non-`.md` file in the committed delta (`:329`) under
  `len(delta) > 2*len(prior)+5` (`:331`). No branch bound, no merge-base bound, no active-plan
  bound. `_resolve_base_branch` IS imported (`lib/critic_mode.py:75`) but used only by rule 2
  (`:352`) and `_committed_chunk_ids` (`:540`) — never by rule 1b. That is precisely the absence
  this item's fix-shape names. `critic_consolidate.fact_to_cache_record` (`:684-728`) overwrites
  the single slot unconditionally, so a previous bundle's cumulative survives a `git switch` and a
  new plan.

  *Residual work is NEW DESIGN, not a port.* Nothing on the archive tag implements it and no
  branch test covers the filed case. Two candidate shapes: require the anchor to be at or after
  `merge-base(_resolve_base_branch(project_dir), HEAD)`; or require the record's `files_reviewed`
  to intersect the active build plan's scope. Stays `stage: design`.

- **[CRT-8H3R]** Mode inference can latch a verify-resolutions dispatch onto a sibling branch's anchor after a branch switch — require anchors to be ancestors of HEAD
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-21 · status: open · stage: ready · related: CRT-6J4P · refs: lib/critic_mode.py (infer_mode rules 1/1b, _commit_resolves, _cumulative_anchor), lib/critic_consolidate.py (_prior_review_fact) · reviewed: 2026-07-19`

  If SessionStart recorded branch A but the work is on a divergent branch B, mode-inference can chain
  verify-resolutions to A's anchor SHAs; compute-verify-resolutions-scope only demotes when an anchor
  SHA does NOT resolve, so a SHA that still resolves on the sibling branch (not an ancestor of HEAD)
  passes the guard and yields a cross-branch two-way diff full of phantom findings (surfaced live this
  session on feature/hot-path-git-batching, anchors f208ad2/f92a4be from sibling
  feature/hook-cli-robustness). Fix shape: add an is-ancestor check on commit_reviewed (git merge-base
  --is-ancestor <anchor> HEAD) — if the anchor isn't an ancestor of HEAD, demote to cumulative/final
  instead of computing a divergent delta. Surfaced + self-flagged by the Critic during STH-6Q9D.
  (critic)

  Second live occurrence + soundness escalation (2026-07-03, prose-diet chunk-01 Critic WARNING): a
  stale single-slot `.critic-findings.json` left by sibling branch feature/gate-exemption-boundary
  latched verify-resolutions onto a cross-branch delta while reviewing feature/prose-diet. Both
  `commit_reviewed` and `extends_cumulative` SHAs must be required to be ANCESTORS OF HEAD (mere
  object-resolution is insufficient) — and the stakes are worse than phantom findings: if the reviewer
  records the chain anchor, `check-cumulative-critic` could spuriously accept a Goals-1-3 review as
  cumulative coverage for an unrelated branch's PR. Fail closed: non-ancestor anchor → demote to
  chunk/final. (critic, chunk-01 prose-diet review)

  **kernel-v3 refresh (2026-07-13, chunk-06 cumulative review batch) — the paragraphs above
  describe v2 mechanisms; read them as history.** The SOUNDNESS half is structurally resolved:
  `compute-verify-resolutions-scope`, `extends_cumulative` chains, and mode-label gate
  acceptance were all deleted in the v3 cutover — gates compose tree-keyed review facts
  (`lib/coverage_algebra.coverage_verdict`), so a sibling branch's review can no longer
  spuriously satisfy `check-cumulative-critic` for this branch's PR (its tree edges don't chain
  base→HEAD; the gate fails closed). What SURVIVES is the dispatch-side half: `infer_mode`
  rules 1/1b (`lib/critic_mode.py`) and `critic-begin`'s prior-fact anchor
  (`critic_consolidate._prior_review_fact`, resolved via the single-slot
  `.critic-findings.json` derived view) still check only that the anchor RESOLVES
  (`_commit_resolves`), not that it is an ancestor of HEAD — after an in-tree branch switch, a
  sibling branch's record can still latch a verify-resolutions dispatch onto a cross-branch
  delta (phantom findings, a wasted review pass). Fix shape unchanged from the original: run
  `git merge-base --is-ancestor <anchor> HEAD` on the rule-1/1b anchor and in
  `_prior_review_fact`; non-ancestor → demote to chunk/final. Consequence is now
  proportionality/noise, not gate soundness — impact downgraded M→S accordingly. Sibling fix:
  CRT-6J4P (bound rule 1b to branch/plan scope) — consider one pass for both.

  **Salvage annotation (2026-07-19) — VERDICT: STILL-PRESENT (dispatch side only).** Captured
  before the stale branch `feature/gate-fidelity` was deleted; its work is preserved at tag
  `archive/gate-fidelity` (restore with `git branch feature/gate-fidelity
  archive/gate-fidelity`), relevant commit `af8350f`. Verified against develop's current code, not
  inferred. The soundness half is confirmed gone (`lib/gates.py:928-930` composes tree-keyed
  edges; a sibling edge cannot complete the BFS in `coverage_algebra._find_path`;
  `.critic-findings.json` is never read by a gate — pinned at
  `tests/test_cumulative_gate.py:412-417`). The dispatch/noise half is intact and unguarded:
  `lib/critic_mode.py:251` (rule 1) and `:317` (rule 1b) accept the anchor on `_commit_resolves`
  alone; `_commit_resolves` (`:466-475`) is just `git rev-parse --verify <sha>^{commit}`, which
  succeeds for ANY object in the shared store including a sibling tip; `_committed_files_since`
  (`:452-463`) then takes the two-way diff `<sha>..HEAD` spanning the divergence (the
  phantom-finding surface, reused at `lib/critic_consolidate.py:266-269`). Zero occurrences of
  `is-ancestor`/`is_ancestor` anywhere under `lib/` or `bin/`.

  *Salvageable fix-shape (re-implementable without the branch).* Add
  `_commit_is_ancestor(project_dir, sha)` = `git merge-base --is-ancestor <sha> HEAD`, True only
  on exit 0 (fail closed — exit 1 AND any other failure demote). Call it immediately after each
  `_commit_resolves` check; a non-ancestor anchor returns False/"" so inference falls through to
  cumulative/final. Insert points on develop: `lib/critic_mode.py:252` and `:318`. **Port caveat:**
  the branch also patched `gates._compute_verify_resolutions_scope`, which was DELETED in the v3
  cutover and is asserted-absent by a stays-deleted pin (`tests/test_cumulative_gate.py:419-431`) —
  porting it would break the pin. Redirect that half to `critic_consolidate._prior_review_fact`
  (`lib/critic_consolidate.py:137`) or the verify arm of `begin_review` (`:239-250`), checking the
  fact body's `head_commit`/`dispatch_commit` for ancestry and returning the existing
  `{"status": "error", "reason": ...}` shape.

  *Test pointers.* `tests/test_critic_mode_inference.py::TestRule1VerifyResolutions::test_does_not_fire_when_anchor_is_non_ancestor`
  and `::TestRule1bPostfixChain::test_does_not_fire_when_anchor_is_non_ancestor` port cleanly, with
  develop renames: class `TestRule1bPostfixChain` → `TestRule1bPostCumulativeFix`
  (`tests/test_critic_mode_inference.py:353`), function `_rule_postfix_chain_fires` →
  `_rule_postfix_fix_fires`. Both assert `_commit_resolves(...) is True` AND
  `_commit_is_ancestor(...) is False` before asserting the demote — i.e. they prove the OLD guard
  would have passed, so the new guard is load-bearing. **Keep that pattern.** The branch's two
  `tests/test_cumulative_gate.py` tests are dead code against develop.

- **[CRT-9L2F]** Post-release live verification: explicit /prawduct:critic mode argument honored end-to-end (follow-up to CRT-2N7V, gate-hardening ch.03)
  `effort: S · impact: M · area: governance/critic · source: builder · added: 2026-06-10 · status: open · stage: ready · related: CRT-2N7V, CRT-3M8Q · refs: skills/critic/SKILL.md, lib/critic_mode.py`

  After the gate-hardening bundle ships in a release (so the installed plugin carries the rewritten
  SKILL.md step 1), invoke the Critic via the Skill tool with an explicit mode that DIFFERS from
  what inference would pick, and confirm .critic-findings.json records mode_chosen_by:
  "explicit-args". Context: the bundle's own cumulative (2026-06-10) was invoked with explicit args
  and still recorded rule-2 inference — third observation; undetermined whether the edited skill
  even ran (framework-repo skill source ambiguity: marketplace v2.1.2 clone vs working tree).
  Known facts: $ARGUMENTS substitution is broken for Skill-tool→fork (anthropics/claude-code#34164,
  closed not-planned); args demonstrably reach OTHER fork skills (backlog, learnings — same
  session); the helper layer (prawduct-hook infer-critic-mode <token>) is unit-proven. If
  launch-message delivery doesn't reach the Critic fork, escalate to a file-based mode request
  (invoker writes the requested mode to a .prawduct dotfile; helper reads + deletes it). (builder)

- **[REL-5K8M]** Heavier-mechanism option for reviewer-model churn — single-source tier→model registry + drift check
  `effort: M · impact: M · area: governance/release · source: builder · added: 2026-06-12 · status: open · stage: idea · refs: .prawduct/artifacts/build-plan-reviewer-model-fallback.md, documentation/research/open-6-model-tier-registry.md`

  **Paused 2026-07-14 (v3.0.1):** reviewer-model tiering was removed (emergency patch — reviewers
  run on the session model; change-log `reviewer-session-model`). There is currently no tier→model
  mapping to single-source, so this item is inert until tiering is restored — fold it into the
  restore work rather than grooming it standalone. Kept open (not superseded) because the restore
  is planned.

  Deferred from reviewer-model-fallback (2026-06-12). The v2.1.5 fix handled model withdrawal (Fable
  temporarily pulled) with prose-only ordered fallback chains — the user chose the lightest mechanism.
  If model churn recurs or the prose-driven resolution proves error-prone, consider the heavier
  mechanism that was considered and declined for proportionality: a single source-of-truth tier→model
  registry (one place to edit on a lineup change) plus a `/prawduct:doctor` or `/prawduct:janitor`
  drift check that flags when a named alias in the registry is past a known retirement date.

  Honest constraint recorded in `build-plan-reviewer-model-fallback.md`: a Python hook cannot see the
  harness's live valid-model set, so any check is refresh-cadence/advisory-based, not an automated
  availability probe. Related: `documentation/research/open-6-model-tier-registry.md` is a separate
  surface (the Critic classifying a *product's* models), not this reviewer-dispatch registry. Type:
  enhancement, low priority. (builder)

- **[TEL-6P2D]** review-stats windowing + zero-yield pruning-candidate flag + a documented pruning protocol (no auto-cut)
  `effort: S · impact: M · area: telemetry · source: user · added: 2026-06-22 · status: open · stage: design · related: TEL-4M9X, CRT-9R4K, CRT-5T8N · refs: lib/telemetry.py, methodology/building.md`

  Problem: We want to retire/lighten review legs that demonstrably catch nothing, WITHOUT guessing.
  Today review-stats has no window and no "this leg looks unproductive" signal, and there is no written
  protocol for how a cut is justified/approved. The 2026-06-22 data (post-A1) is too thin per bucket
  (1–8 reviews) to act on, so the immediate need is to accumulate clean data and stand up the decision
  machinery.

  Approach:
  - Add `review-stats --since=<window>` (time-based e.g. 30d AND/OR last-N reviews) so trailing-window
    yield is readable, not just all-time.
  - Flag any (role × mode [× code-path]) leg with ≥N reviews and 0 actionable (B/W) findings over the
    window as a HUMAN-REVIEWED pruning candidate — surfaced in the report, NEVER auto-applied.
  - Write the pruning protocol into methodology: a review leg may be lightened/retired only when (a) ≥N
    reviews in window, (b) 0 actionable yield, (c) a human signs off, AND (d) it ships with a regression
    test proving a non-eligible case still gets the full review (the trivial-fast-path lesson: a
    skip-gate needs the MOST adversarial coverage).
  - Name the PR reviewer (pr-scoped) as the standing WATCH-TARGET: as of 2026-06-22 it is the lowest
    yield-per-run (9 reviews, ~1 actionable, ~46 min wall-clock total), BUT its low yield is confounded
    — its job includes confirming the Critic was right + release-readiness, where an empty result is
    partly success. Do NOT cut it on current data; instrument and watch.

  Assurance: preserved by construction — every cut is gated behind data + human sign-off + a regression
  test; the flag is advisory only.

  Open design decisions: threshold N (proposal ≥10 reviews/0 actionable before flagging); window
  semantics (time vs count — recommend both, default time); whether to break the flag down by
  code-path/scope (a leg may be productive on governance diffs, dead on docs). Depends on A1 (clean
  model dimension). Feeds C (the data that would justify deferring per-chunk reviews on short plans).
  (user)

- **[CRT-9R4K]** Extend cumulative-final to short plans — defer per-chunk Critic reviews into one end-of-plan cumulative
  `effort: M · impact: M · area: building · source: user · added: 2026-06-22 · status: open · stage: requirements · related: TEL-6P2D · refs: methodology/building.md, skills/critic/review-protocol.md, lib/critic_mode.py`

  Opportunity: For a multi-chunk feature every chunk gets its own opus fork Critic review, then the
  cumulative re-reviews all of them (the deliberate local-vs-integration redundancy). For SHORT plans
  this is the biggest avoidable wall-clock: N per-chunk runs a single end-of-plan cumulative would
  cover. The 2026-06-22 chunk-mode yield is low (~1 actionable across 7 reviews) — MILD supporting
  evidence only; early-detection value is not captured by finding-count, so this is a judgment call,
  not a data verdict.

  Tradeoff (USER owns it — Principle 23): deferring per-chunk reviews trades EARLY detection for a
  bigger blast radius — a flaw introduced in chunk 1 surfaces only at end-of-plan, costing more rework
  to unwind. Eligibility bounds that risk.

  Requirements to pin FIRST (C0 — why this is stage:requirements, not ready):
  - Decide the acceptable-tradeoff bounds: under what plan shape is deferring early detection
    acceptable? Proposal: chunk-count ≤ 3 AND risk tier = standard AND NEVER escalate-tier
    (governance/contract-path scope always gets per-chunk review). User to confirm/adjust.
  - Confirm composition with the existing cumulative-final Type (today: commit last chunk, run
    cumulative once = chunk review + PR record). C generalizes that to cover ALL chunks of a short
    eligible plan, not just the last.

  Design (C1, after requirements): eligibility predicate in lib/critic_mode.py + the build cycle in
  methodology/building.md (eligible short plan marks intermediate chunks "review deferred to
  end-of-plan cumulative"); resolve how a deferred plan interacts with the stop-hook Critic gate and
  session boundaries (a plan spanning sessions cannot defer past a session end without a gate record).

  Guardrail (C2 — MANDATORY, load-bearing): ship with a regression test proving a NON-eligible plan
  (4+ chunks OR escalate-tier) STILL gets per-chunk reviews. The retired PR trivial-fast-path failed
  precisely because it shipped with zero adversarial coverage — a skip-gate needs the MOST adversarial
  coverage.

  Assurance: preserved only if the eligibility predicate + C2 regression test hold and the bounded
  early-detection loss is explicitly accepted by the user. Gated behind A's accumulated data OR an
  explicit user accept-the-tradeoff decision. (user)

- **[BLD-3M7K]** `verify-chunk-refs` over-matches git-ref tokens (origin/-prefixed and branch-like slash tokens) in build-plan prose, producing false missing-ref positives
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-21 · reviewed: 2026-07-19 · status: open · stage: idea · related: BLD-4K7P, BLD-2R9X, BLD-8F2Q, BLD-6T4R · refs: lib/buildplan_refs.py (_looks_like_file_path)`

  Follow-up to BLD-4K7P. Surfaced 2026-06-21 by the hook-cli-robustness cumulative Critic: the
  plan's own prose backticked `origin/develop` and `origin/` while describing the REL-7P3X fix;
  `_looks_like_file_path` treats any backticked slash-token without `<>`/`://`/glob as a file path,
  so git refs flag as missing. Same false-positive family the BLD-4K7P fix (placeholders, URLs,
  gitignored) does NOT cover, and PR #99's cumulative saw it too. Workaround in place: de-backtick
  git refs in plan prose (the gate correctly checks file paths; a git ref isn't one). Open question:
  a general fix is hard — branch-like tokens (feature/x) are indistinguishable from real paths
  (feature/x), so an origin/-prefix-only heuristic risks false-negatives on real missing paths.
  Decide whether the narrow origin/ exclusion is worth it or the convention (don't backtick git
  refs) suffices. (critic)

<!-- Fix program from the framework efficiency review (owner-accepted 2026-07-02).
     Parent requirement doc: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md
     READ IT IN FULL before planning any item below — it carries the evidence these one-liners cannot.
     Waves: 1 = P0 (kill recurring taxes), 2 = P1 (outcome gaps), 3 = P2 (weaker-model scaffolding).
     Each wave item ships as its own small 1-2 chunk plan on its own branch — NOT one monolithic plan. -->

- **[CRT-5M9J]** Wave 2: scope check in review — mandated question: does this capability trace to a documented requirement, and is it reachable/consumed end-to-end?
  `effort: S · impact: M · area: critic/pr-protocols · source: user · added: 2026-07-02 · status: open · stage: ready · related: ADR-7X2M · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Underspecified #2), skills/critic/review-protocol.md, skills/pr/review-protocol.md`

  P1. The metallm blind spot, documented 4x: every reviewer checks work AS SCOPED, never whether
  the requirement should EXIST or was ever built (scriob shipped 697 commits with an unversioned
  API on an unchallenged one-word deferral). Fix costs a paragraph: one mandated question in the
  cumulative and PR protocols pressure-testing scope and end-to-end reachability. (user)

- **[ENV-2W7K]** Wave 2: environments plan — worktree story, gitflow base detection, non-Python coverage floor goes silent, document --from-counts as the paved non-pytest path
  `effort: L · impact: L · area: environments · source: user · added: 2026-07-02 · reviewed: 2026-07-18 · status: open · stage: design · related: CRT-6W2N, STH-4K7N, CRT-8D2W, COV-5H3N, COV-4M2J, TST-2H9P · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Underspecified #1)`

  P1. The framework assumes repo-root Python, single checkout, main-based — violated by engine/
  subdirs (scriob), .NET/Swift (cordyceps/trenchant), worktrees (incoming bug 2026-06-20:
  "following one prawduct rule forces you off-protocol on another"), devcontainers (discodon),
  gitflow (silent wrong-base on every first PR). Scope: a supported worktree story; gitflow base
  detection that doesn't require knowing `base_branch:` exists; non-Python coverage floor goes
  SILENT (not noisy) for languages it can't see; document `--from-counts` as the paved non-pytest
  path. Owner's rule: the worktree piece needs a short design note FIRST, confirmed with the
  owner, before building. Umbrella over CRT-6W2N/STH-4K7N/COV-5H3N — dedup/`closes:` when
  planned. (user)

  Reconcile 2026-07-18 (worktree leg DELIVERED, item stays OPEN): the worktree-story piece of this umbrella is now shipped and is tracked by the now-shipped CRT-6W2N — a documented/owned worktree workflow (STH-4K7N Chunk 02, PR #107) plus the observable stop-path redirect signal (STH-3R8K) and SessionStart worktree-awareness (worktree enumeration/orientation in the briefing, `lib/briefing.py:379-428`, `:495-509`). A future picker should NOT re-plan the worktree piece.

  **Attribution correction 2026-07-19 (salvage sweep N1).** The reconcile line above originally credited the SessionStart worktree-awareness leg to **BRF-6K2D** — that is wrong and is now corrected in place. What actually landed is the briefing's worktree enumeration/orientation (`lib/briefing.py:379-428`, `:495-509`), which is unrelated to BRF-6K2D. BRF-6K2D is the merge-awareness of the "delete the plan" nudge (`lib/briefing.py:146-170`), and its own surface is verified UNTOUCHED on develop — it remains fully OPEN. The same mis-credit appears in CRT-6W2N's archived entry (its `closed-by:` and body); left as archived history there, corrected here, and flagged in CRT-6W2N's body so a reader of either lands on the truth. ENV-2W7K's remaining OPEN scope therefore narrows to its three other legs: (1) gitflow base detection that doesn't require knowing `base_branch:` exists; (2) the non-Python coverage floor going SILENT (not noisy) for languages it can't see; and (3) documenting `--from-counts` as the paved non-pytest path. The umbrella line above still holds for STH-4K7N/COV-5H3N; only the CRT-6W2N (worktree) leg is closed.

- **[LRN-7M4D]** Wave 2: memory convergence — learnings + learnings-detail durable, .session-reflected ephemeral, retire per-repo reflections.md accumulation (design note first)
  `effort: M · impact: M · area: memory/learnings · source: user · added: 2026-07-02 · status: open · stage: design · related: MET-6W3J · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Underspecified #5)`

  P1. The memory triple-track: reflections.md is write-heavy/read-never (discodon: 7,645 lines,
  nothing retrieves from it); metallm's reflection loop froze while learnings thrived. Converge:
  learnings + learnings-detail as the durable pair; .session-reflected ephemeral (distilled or
  discarded at session end); retire per-repo reflections.md accumulation. Owner flagged this
  convergence directly. Changes the onboarded-repo contract, so it needs a migrate path — write
  the short design note FIRST and confirm with the owner before building. (user)

- **[MET-8J5R]** Wave 2: plan-shape guidance in planning.md — one plan per scope tag; split heterogeneous work; a plan that won't ship in ~3 sessions is a program; planner pushes back on monolithic requests
  `effort: S · impact: M · area: methodology/planning · source: user · added: 2026-07-02 · status: open · stage: ready · related: BLD-7W2J · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (finding 6a, Wave 2), methodology/planning.md, methodology/building.md`

  P1 (finding 6a). building.md's size ladder reads as an instruction to build ONE big chunked
  plan; long-lived-plan frictions sat in learnings for weeks without flowing back into
  planning.md (a Close the Learning Loop failure). Add mechanical heuristics: one plan per scope
  tag; split when change types differ; a plan that won't ship within ~3 sessions is a program →
  backlog items + per-wave plans; the planner must push back on monolithic-plan requests. This
  fix program's own wave structure is the worked example. (user)

- **[DOC-3V7T]** Wave 2: persistence contract for review/research artifacts — first-class home (.prawduct/artifacts/ + naming convention), backlog items link their parent artifact, pick surfaces it
  `effort: S · impact: M · area: artifacts/convention · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-8J5R · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (finding 6b, Wave 2)`

  P1 (finding 6b). Rich review/research output has no first-class home — cross-session surfaces
  (build-plan Context line, backlog one-liners, .session-handoff.md) are all thin; the efficiency
  review itself had to hand-roll the workaround (write an artifact, link every item to it).
  Deliverable is likely just a convention + template + one line in planning.md: artifacts live in
  .prawduct/artifacts/ with a naming convention; backlog items `refs:` their parent artifact;
  `pick` surfaces the linked artifact. Avoid building machinery. (user)

- **[STN-4W7R]** Wave 2: advisor-first stance made structural — digest stance-block tone rewrite (rides with MET-3Q8V) + advisory obligations attached to existing checkpoints
  `effort: M · impact: M · area: agent-stance · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-3Q8V, MET-8J5R · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Advisor-first stance, Wave 2), methodology/session-digest.md, methodology/planning.md, methodology/discovery.md, CLAUDE.md (Before Building) · reviewed: 2026-07-03`

  P1. Owner directive 2026-07-02: lean into prawduct's role as advisor/expert rather than merely
  an implementor of whatever the user asks for. Two parts: (a) TONE — when Plan C (MET-3Q8V
  prose-diet) rewrites the digest, reframe the stance block from a trait list into a lead
  position: the agent's first duty on any substantive ask is the expert take (risks,
  stronger/simpler alternative, recommendation), compliance second. (b) STRUCTURE — attach
  advisory obligations to checkpoints models already hit, because tone exhortations decay on
  weaker models: plan creation (plan-shape pushback, MET-8J5R), backlog pick ("is this still
  worth doing?"), discovery start (what the user hasn't thought of — already present), and the
  Before-Building check gains an explicit "should this be built as asked?" line. Advisorship
  that lives only in adjectives will not survive under context pressure; advisorship attached to
  gates will. Parent: framework-efficiency-review-2026-07-02.md "Advisor-first stance" section. (user)

  2026-07-03 (prose-diet cumulative Critic reconciliation, branch feature/prose-diet): part (a)
  DELIVERED on that branch — chunk 03 rewrote the digest stance block in
  `methodology/session-digest.md` (~239 words) from trait list to expert-take-leads framing,
  keeping the checkable bars; slim digest synced. Also this branch deleted
  `methodology/agent-stance.md` (folded by MET-3Q8V), so the stance's sole operational surface
  is now `methodology/session-digest.md` — refs repointed accordingly. Part (b) (advisory
  obligations attached to existing checkpoints: plan creation, backlog pick, discovery start,
  Before-Building line) remains open and is now the whole of this item.

- **[MET-2X6F]** Wave 3: weaker-model scaffolding — filled example chunk, domain-concern checklist seeded by structural characteristics, root-cause stopping rule, 3-4-file size tiebreak, red-baseline protocol
  `effort: M · impact: M · area: methodology/templates · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-3Q8V, BLD-8N4W · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 3, Underspecified #4), templates/build-plan.md, methodology/discovery.md:100, methodology/building.md · reviewed: 2026-07-03`

  P2. Judgment offloads with no weaker-model scaffolding: "detect domain concerns dynamically, no
  hardcoded lists"; no root-cause stopping rule; the 3-4-file size-classification dead zone; no
  red-baseline protocol; zero filled examples in the build-plan template. Note: the filled
  example chunk may already land in Wave 1 Plan C (MET-3Q8V) — check before duplicating work. (user)

  2026-07-03 (prose-diet cumulative Critic reconciliation): the "filled example chunk"
  deliverable LANDED in prose-diet chunk 01 — `templates/build-plan.md` is now a fully-filled
  Pantry example (1,197 words), so Wave 3 must NOT redo it. The rest of the item still stands:
  domain-concern checklist seeded by structural characteristics, root-cause stopping rule,
  3-4-file size tiebreak, and red-baseline protocol remain undelivered (4 of 5 deliverables
  open). Item stays open at effort M — the template piece was the smallest of the five.

- **[BLD-8N4W]** Wave 3: subagent-output verification rule in building.md — a subagent's "Done" on a removal is a claim to verify
  `effort: S · impact: M · area: methodology/building · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-2X6F · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 3, Underspecified #4), methodology/building.md`

  P2. Actual weak-model failures cluster in SUBAGENT quality: premature "Done", over-broad
  allowlists, 5-15% inventory undercounts (discodon learnings — already a learning there; this
  closes the loop into methodology). Add the verification rule to building.md. (user)

- **[STH-5D8J]** Wave 3: trivial gate — add a waiver key + product-relative blast radius, or retire it
  `effort: S · impact: S · area: stop-hook · source: user · added: 2026-07-02 · status: open · stage: design · related: STH-4D2X · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 3, Overbuilt #5)`

  P2. The trivial gate hard-codes prawduct's own dir names as blast radius in product repos and
  has no waiver key (KNOWN_WAIVER_KEYS lacks "trivial"). Decision needed (patch vs retire): its
  sibling trivial fast-path already proved fileset-as-detector unsound (built 2026-05-22, fully
  retired 2026-06-08) — the third-rework-is-a-deletion-signal lens (MET-9W2P) applies. (user)

- **[MET-9W2P]** Wave 3: principle amendment proposal — the third rework of a mechanism is a deletion signal, not a patch signal
  `effort: S · impact: M · area: principles · source: user · added: 2026-07-02 · status: open · stage: idea · related: STH-5D8J · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Structural diagnosis, Wave 3), docs/principles.md`

  P2. Supported 3x in the evidence: freshness fingerprint, trivial fast-path, stop hook (reworked
  6+ times, never stabilized). Pattern: gate misfires → suppression layer added → suppression
  layer accretes its own bugs and learnings. Draft the amendment (Principle 19 — Evolving
  Principles is the vehicle) and confirm wording with the owner. (user)

- **[REL-4Q9V]** Vocabulary shrink for the change-log lifecycle — hard-remove `status=merged` and the deprecated stamp-merged machinery; one scope identifier (future major)
  `effort: M · impact: M · area: governance/change-log · source: builder · added: 2026-07-02 · status: open · stage: design · related: VWS-6R4T, REL-9F2T · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan B "consider shrinking"), .prawduct/artifacts/build-plan-changelog-fail-loud.md (descope assumption + rationale) · reviewed: 2026-07-10`

  Deletion-over-patching candidate. Descoped from the changelog-fail-loud plan (VWS-6R4T) per
  that plan's HIGH-impact assumption. Blocked on the owner confirming the shrink is wanted once
  fail-loud validation ships — validation removes the P0 urgency. Cascade surfaces:
  `docs/release-process.md`, `stamp_merged` in `lib/views.py`, several learnings. (planning)

  **Delivery note 2026-07-10 (feature/single-pr-bookkeeping) — lifecycle half shipped; item
  stays open, narrowed to the hard-removal half.** Statusless-until-release is now the
  documented + code-supported lifecycle: `collect_release_pending_scopes` enumerates statusless
  tagged scopes; the `/prawduct:pr` merge-flow stamp step is removed (merge-flow step 6 no
  longer exists — cascade list above updated accordingly); create-flow Step 1d establishes "the
  PR carries its own bookkeeping"; `docs/release-process.md` + the template are rewritten.
  Remaining scope (deferred to a future major): drop `merged` from `VALID_STATUS_VALUES`,
  delete `stamp_merged`/`cmd_stamp_merged` (currently deprecated-but-callable with a stderr
  notice), and the "one scope identifier" vocabulary consolidation.

- **[CRT-6Q2N]** critic-consolidate's ledger anchor lacks an idempotency guard — retry in the ledger-append→remove_partials crash window lands a duplicate `review.critic` line
  `effort: S · impact: S · area: governance/critic · source: critic · added: 2026-07-13 · status: open · stage: ready · related: CRT-4B7X · refs: .prawduct/artifacts/build-plan-kernel-evidence-store.md, .prawduct/.governance-ledger.jsonl`

  The review-fact and resolution-fact appends are id-idempotent, but the ledger anchor is not: a
  retry after the crash window between ledger-append and remove_partials (or a re-materialized
  same-id manifest) lands a duplicate `review.critic` ledger line for the same review id. Benign
  today — check-cumulative-critic reads the newest qualifying event and the store fact stays
  single — but worth a guard keyed on the dispatch id. Surfaced by the Critic (NOTE),
  kernel-evidence-store chunk 03, 2026-07-13. Sibling of CRT-4B7X (same duplicate-ledger-line
  symptom via concurrent SubagentStop firings); a dispatch-id-keyed guard likely fixes both —
  merge candidates at next triage. (critic)

- **[GOV-2R8W]** Session Critic gate's firing guard is porcelain-based — a fully-committed session skips the Q2 composition verdict at session end
  `effort: S · impact: M · area: governance/kernel · source: critic · added: 2026-07-13 · status: open · stage: design · related: GOV-4C7X, CRT-6Q2N · refs: lib/gitstate.py (git_has_session_changes), bin/prawduct-hook (session Critic gate), .prawduct/artifacts/kernel-v3-evidence-design.md (Q2), .prawduct/artifacts/build-plan-kernel-evidence-store.md`

  From the kernel-v3 chunk 04 Critic review (final mode, 2026-07-13, NOTE). The v3 session-end
  Critic gate's firing guard is still porcelain-based (`git_has_session_changes`), so a session
  that committed all its work reaches session end with a clean porcelain and never gets the Q2
  composition verdict ("do recorded reviews cover the session's tree span?"). v2-parity
  jurisdiction — the PR gate still covers the branch — but the documented Q2 span is wider than
  the firing guard. Fix-shape: align the guard with the tree-span question (fire when the
  session's tree span is non-empty, not only when porcelain is dirty). Candidate for chunk 06
  of the kernel-evidence-store plan or a later constituent plan of GOV-4C7X. Governance-protected
  (gates/hooks) → full Critic + PR review. (critic)

- **[GOV-6H4P]** v3 session-gate advisory surfaces are coarser than the blocking gate — briefing collapses error/schema-ahead verdicts; Gate 2.5 synthesis advisory reads the clone-global latest review fact
  `effort: S · impact: S · area: governance/kernel · source: critic · added: 2026-07-13 · status: open · stage: ready · related: GOV-2R8W, GOV-4C7X · refs: lib/briefing.py (_check_previous_session_gates), bin/prawduct-hook (Gate 2.5)`

  From the kernel-v3 chunk 04 Critic review (final mode, 2026-07-13, NOTE). Two advisory-only
  coarseness gaps in the v3 session-gate surfaces: (a) `briefing._check_previous_session_gates`
  collapses error/schema-ahead verdicts into "Critic review not recorded", hiding the
  update-plugin remedy from the session-start advisory; (b) Gate 2.5's synthesis advisory reads
  the clone-global latest review fact, so another worktree's review can steer this session's
  advisory. Both are advisory-only — the blocking gate is unaffected. Fix-shape: differentiate
  the verdicts on the briefing surface, and key the synthesis advisory's fact read to the
  session's worktree/branch. Governance-protected → full Critic + PR review. (critic)

- **[GOV-4C7X]** Governance kernel redesign (v3) — SHA-keyed evidence store + coverage-algebra gates + deterministic Critic data plane
  `effort: L · impact: L · area: governance/kernel · source: user · added: 2026-07-12 · status: promoted · stage: design · related: CRT-5D8Q, GOV-7T2M, WMK-4Q9T, MIG-6B0R, CRT-9K7T · refs: .prawduct/artifacts/kernel-redesign-discovery.md, .prawduct/artifacts/kernel-inventory-2026-07-12.md, .prawduct/artifacts/build-plan-kernel-evidence-store.md, .prawduct/artifacts/kernel-v3-evidence-design.md · reviewed: 2026-07-12`

  PROGRAM-level item (true effort is XL — a program of small shippable plans; recorded `L`, the
  metadata-bar scale ceiling). Owner-approved re-architecture per the discovery artifact (owner
  decisions 2026-07-12). Concerns: evidence model (C1), deterministic data plane (C2), fail-loud
  invariant (C3), gate posture recalibration (C4), per-repo SHA-keyed store (C5),
  upstream-feedback pull path (C6), schema versioning (C7), branch-role-aware gates including
  the MIG-6B0R strip-on-promotion (C8). Subsumes the Wave 2 MECHANISM items of
  framework-efficiency-review-2026-07-02 (CRT-5M9J scope-check question, STH-8R3Q
  outcome-checking Stop gate, ENV-2W7K environments plan, CRT-3F6W reviewer-dedup deletion —
  reconcile/close those against this program as its constituent plans ship; they stay open until
  then). Also carries WMK-4Q9T's owner-decided tripwire deletion (extractor + index machinery
  removed; requirements-precede-code becomes a review-time scope-check question). External
  drivers: discodon upstream reports CRT-8F3K (local counterpart CRT-9K7T, shipped
  critic-persistence-redesign), CRT-W2NV, CRT-J4PM. Delivery posture: breaking release + doctor
  migration; opus-level model floor assumed. (user)

  **Promoted 2026-07-12** — first constituent plan authored:
  `artifacts/build-plan-kernel-evidence-store.md` (C1 evidence store + C2 review data plane,
  6 chunks, `feature/kernel-v3-evidence-store`); design note
  `artifacts/kernel-v3-evidence-design.md`. This program item stays the umbrella; later plans
  (test evidence, PR facts, C8 promotion gate, C6 feedback pull, §4.3 deletions) will be carved
  as their predecessors ship.

- **[CRT-7V4N]** Harden evidence-store tree SHAs before they reach git subprocess args — shape-validate hex-SHA form
  `effort: S · impact: S · area: critic/evidence · source: critic · added: 2026-07-13 · status: open · stage: ready · related: CRT-2K9F · refs: lib/evidence.py (tree_diff, read_facts), lib/gates.py (composition gates), lib/coverage_algebra.py (review_edges)`

  From the chunk-06 cumulative review (kernel-evidence-store bundle f64c22c..69f63a2). Tree SHAs
  read back from evidence-store facts are passed to the git CLI (`evidence.tree_diff` →
  `git diff` argv, and the gate paths feeding it) without shape validation — a corrupted or
  hand-edited fact could inject an arbitrary token into a subprocess argument vector. argv is
  list-form (no shell), so the exposure is git option injection / confusing failures rather than
  shell injection — hardening, not an active hole. Fix: validate each SHA at the read/compose
  boundary against `^([0-9a-f]{40}|[0-9a-f]{64})$` (the review note's `{40,64}` range tightened
  to the two real lengths, SHA-256-ready); treat a non-conforming SHA like any malformed fact —
  it weakens coverage (yields no edge), never crashes the gate. (critic)

- **[CRT-2W8J]** Coordinator roster threshold counts non-judgeable files — a metadata-heavy 5-file diff dispatches a full coordinator
  `effort: S · impact: M · area: critic · source: critic · added: 2026-07-13 · status: open · stage: ready · refs: lib/critic_consolidate.py (_derive_roster, COORDINATOR_FILE_THRESHOLD), lib/coverage_algebra.py (judgeable_files)`

  From the chunk-06 cumulative review (kernel-evidence-store bundle f64c22c..69f63a2).
  `critic_consolidate._derive_roster` promotes a `final`/`cumulative` dispatch to the full
  coordinator roster at n >= 5 counted over the RAW changed-file list, so a metadata-heavy diff
  (e.g. 4 `.prawduct/` files + 1 code file) pays a multi-subagent coordinator review for one
  judgeable file. Proportionality fix: count `coverage_algebra.judgeable_files(files_changed)`
  instead — the same single predicate the gates already compose over, so dispatch cost tracks
  what actually needs review coverage. While in there, check whether
  `critic_mode._rule_final_fires`' no-plan >=5 heuristic wants the same treatment (its file
  source already strips metadata — verify, don't assume). (critic)

- **[COV-6T3P]** is_judgeable_path hard-codes ".md = not judgeable unless governance-protected" — markdown-centric products never gate their core work
  `effort: M · impact: M · area: gates/coverage · source: critic · added: 2026-07-13 · status: open · stage: requirements · related: COV-2P7F · refs: lib/coverage_algebra.py (is_judgeable_path), lib/coverage.py (doc-only fast-path)`

  From the chunk-06 cumulative review (kernel-evidence-store bundle f64c22c..69f63a2). The v3
  single judgeability predicate (`coverage_algebra.is_judgeable_path`) enshrines ".md changes
  don't need review coverage unless governance-protected" — right for code products, wrong for a
  product whose PRODUCT IS the markdown (docs sites, content repos): their core work would never
  require review coverage. Proposal: a project-preferences knob widening judgeability (e.g. a
  boolean or per-path globs). NEEDS OWNER INPUT on semantics before design: binary vs
  path-scoped, interaction with the PR doc-only fast-path, and whether flipping the knob
  retroactively stales existing composed coverage. Filed at stage=requirements — not buildable
  as written. (critic)

- **[MET-6T4K]** Assign-to-agent (GitHub issue→PR autopilot) bypasses the governed build cycle — needs gate + retro-governance path
  `effort: L · impact: L · area: methodology · source: user · added: 2026-07-14 · status: open · stage: research · related: BKL-5D2C · refs: documentation/backlog-service-requirements.md (Assign-to-agent subsection), docs/principles.md (P6, P22) · reviewed: 2026-07-14`

  Surfaced 2026-07-14 during owner review of documentation/backlog-service-requirements.md (draft v3). Becomes live the moment prawduct adopts GitHub Issues as the backlog backend.

  Tension: off-the-shelf "assign issue to a Claude agent" flows — `@claude` via the official `anthropics/claude-code-action`, or org-enabled assign-to-agent — take a GitHub issue and open a PR unattended. That path bypasses the prawduct build cycle entirely: no stage/requirements gate (Principle 6), no Critic, no reflection. It is safe only for `stage: ready`, well-scoped items, and even then human/CI still gates the merge (the agent cannot self-approve — some independent-review posture survives, but not the Critic specifically). This is a governance-is-structural (Principle 22) hole: a fast lane that skips the gates silently is the "governance optional" failure mode. Note the assignee-as-claim half of the same feature is GOOD (native issue assignment = the CC3 claim + CC4 attribution primitive) — this item is only about the autonomous-execution half.

  Candidate mitigations (to evaluate — this is the research work):
  1. Assignment-time gate (prevention): only `stage: ready` items with a linked requirement (`refs:`) may be assigned to the agent; a CI check un-assigns/comments otherwise. Principle 6 relocated to the assignment boundary.
  2. Cycle-in-CI (integration): the action spawns a prawduct-GOVERNED Claude session (plugin installed in CI), running plan -> /prawduct:critic -> reflect and gating the PR on the kernel-v3 evidence store, instead of raw code. Answers "can it use the build cycle?" = yes. Limits to verify: (a) discovery is interactive, so a CI agent cannot confirm requirements with the owner — under-specified items must never be auto-assigned (reinforces #1); (b) Stop-hook enforcement assumes an interactive session boundary, so CI must invoke the gates explicitly; (c) confirm the Critic evidence-store gating actually runs headless in GitHub Actions (kernel v3 was built worktree/CI-friendly — verify end-to-end).
  3. Retro-governance / onboard out-of-compliance PR (likely keystone — GENERALIZES): a PR-boundary reconciliation that detects any PR lacking cycle evidence (no Critic review fact spanning the diff, no parent requirement, no reflection) and runs the cycle AGAINST the existing diff retroactively — attach/reconstruct the parent requirement, run the Critic over the diff, capture reflection, record the facts — before merge is allowed. Covers not just the agent autopilot but ALL out-of-band PRs (a human who hand-coded, an external/anonymous contributor's fork — and draft v3 just widened the doc to invite third-party/anonymous filing, which raises out-of-band PR volume). Slots under GV3 (traceability + reconciliation), which already exists in the doc.

  Open questions: which mitigation(s) to build; does retro-governance warrant its own capability/backlog item; can headless Critic evidence-store gating run in GitHub Actions (verify); how to represent a PR's "compliance status" (label? check? evidence fact?).

  refs: documentation/backlog-service-requirements.md (## Assign-to-agent subsection), GV3, Principle 6, Principle 22.

  Owner note (2026-07-14): retro-governance (mitigation #3) is a large topic in its own right and warrants its OWN doc/spec later — not just a sub-item of the backlog-service work. It also reaches beyond out-of-band PRs into ONBOARDING EXISTING REPOS: bringing a pre-existing, ungoverned repo under prawduct is the same retroactive-cycle problem at repo scale (reconstruct/attach requirements, run the cycle against existing code, record the facts). Parked for now — do NOT design yet; this item only references it. Resolves the earlier open question ("does retro-governance warrant its own capability/backlog item") = yes, its own doc, later.

- **[REL-3B7Q]** Release tooling: support planless scopes in regen-views (first-class `chunks=none` / `plan=none` sentinel)
  `effort: M · impact: M · area: release-tooling · source: reflection · added: 2026-07-14 · status: open · stage: design · related: REL-4T8N, REL-9F2T, VWS-6R4T, VWS-7N3K · refs: lib/views.py`

  A change-log entry for proportionally-planless work (`chunks=n/a`, no build plan) blocks `regen-views`: `diagnose_scope_plan_coverage` (lib/views.py) fails closed on any unreleased scope that doesn't resolve to a build-plan file. First hit by the gitignore-drift-advisory scope at v3.0.0 release-prep; worked around by folding its scope into kernel-evidence-store.

  Desired: a first-class sentinel (e.g. `chunks=none` / `plan=none`) that the release validator recognizes and skips scope→plan resolution for, so proportional planless work can carry its own scope and release-notes line without a fabricated build plan. Distinct from the sibling no-plan fail-closed cases already shipped (VWS-7N3K: regen aborts when NO plan resolves at all; VWS-6R4T: fail-loud roster validation of every change-log tag) — this is about a legitimate *per-scope* planless entry that the roster/coverage validator must accept as intentionally planless rather than reject.

- **[COV-9B4T]** Reconsider cumulative/PR base resolution to prefer the nearer of local/remote integration branch when local is ahead AND an ancestor of HEAD
  `effort: M · impact: M · area: coverage · source: reflection · added: 2026-07-14 · status: open · stage: design · related: COV-7K4N, COV-5H3N, ENV-2W7K · refs: lib/coverage.py (_resolve_base_branch), lib/gates.py (check_cumulative_critic)`

  This is fix-shape #3 from COV-7K4N (a deferred spike), deferred at that item's close. Reconsider base resolution to prefer the nearer of local <b> / origin/<b> when local <b> is ahead of origin/<b> AND an ancestor of HEAD — this would eliminate the false-`uncovered` at its root (rather than only diagnosing it, which fix-shapes #1+#2 now do). Trades against the deliberate "stable remote-tracking merge-base" design (origin/<b> preferred for stability) and is load-bearing across EVERY gate that resolves a base (PR, doc-only, cumulative-critic), so it is a spike, not a quick change. Governance-protected (lib/gates.py, lib/coverage.py) → would need full Critic + PR review. Now lower urgency because COV-7K4N's diagnostic hint (gate) + unpromoted-release-prep advisory already convert the wrong/expensive remedy into the right cheap one and nudge before the gate is hit.

- **[GOV-8N4V]** `infer-critic-mode` misses a set `active_build_plan` — fail-safes to `final` and verify-chunk-refs sees "no current chunk" despite a resolvable pointer and a declared chunk mode
  `effort: S · impact: M · area: governance · source: critic · added: 2026-07-16 · status: open · stage: ready · related: BLD-5J8N, BLD-7W2J · refs: lib/critic_mode.py, bin/prawduct-hook (infer-critic-mode, verify-chunk-refs), .prawduct/artifacts/build-plan-norm-lifecycle.md · reviewed: 2026-07-18`

  Observed 2026-07-16 during norm-lifecycle Chunk 2's review on feature/norm-lifecycle: `prawduct-hook infer-critic-mode` reported "no active build plan and no other rule fired — fail-safe to final" and verify-chunk-refs saw "no current chunk", even though project-state.yaml `active_build_plan: artifacts/build-plan-norm-lifecycle.md` was set and the plan's Chunk 2 declares `Critic mode: chunk`. Failed SAFE here (final ⊇ chunk — a broader review than required), but the same current-chunk/plan derivation feeds the stop-hook gate, so the miss is not confined to mode choice. Likely the derivation doesn't resolve the pointer, or expects a different Status-section shape than the plan uses. Overlap check before fixing separately: BLD-5J8N is the chunk-HEADER regex leg of cmd_verify_chunk_refs ("## Chunk NN — Title" h2/em-dash style exits "chunk not found") — if build-plan-norm-lifecycle.md uses that header style, this may be the same parser gap surfacing at the plan/current-chunk derivation layer; verify against both readers before fixing either alone. BLD-7W2J is the single-slot pointer design (different failure: pointer repointed between parallel plans, not a set pointer going unresolved). Governance-protected (lib/critic_mode.py, bin/prawduct-hook) → full Critic + PR review. (critic)

  Partially advanced 2026-07-18 by discodon-upstream-defects Chunk 02 (BLD-5J8N): the shared lib/buildplan_refs.py chunk parsers were broadened to accept the `## Chunk N (ID) — Name` form, which fixes the chunk-HEADER-regex facet of this item (infer-critic-mode and verify-chunk-refs share those primitives). The remaining facet — a set `active_build_plan` pointer going unresolved / the Status-shape derivation when the pointer resolves but the current-chunk still reads empty — is NOT addressed here and remains OPEN; verify against build-plan-norm-lifecycle.md's actual heading form to confirm whether the parser fix fully closed it.

- **[BKL-6W9R]** transport: _api_paged page-cap trip is silent truncation — fail loud (or warn) at _PAGED_MAX_PAGES
  `effort: S · impact: S · area: backlog-service · kind: task · source: critic · added: 2026-07-17 · reviewed: 2026-07-18 · status: open · stage: ready · related: BKL-2V6N`

  Critic note (sustainability, 2026-07-18 review of the BKL-2V6N fix): when _api_paged hits _PAGED_MAX_PAGES (100 pages x per_page), it returns the collected prefix indistinguishably from completion — the same silent-truncation class BKL-5T3J exists to kill, though reachable only at 10k+ entries per endpoint (labels/timeline/sub-issues). Fix direction: on cap trip, either raise TransportError(unavailable, 'result truncated at N pages') or surface a warning through the envelope so callers (export especially — the MG2 backup) can distinguish truncated from complete. Compare query._all_issues, which at least logs a diag line on its cap. Not migration-gating (prawduct scale is ~220).

  Update 2026-07-18 (cumulative-Critic R-4): PARTIAL fix landed in the slice PR — core.iter_alias_issues is now bounded (_ALIAS_SCAN_MAX_PAGES=100, diag line on cap trip, tested). Remaining direction folded in from the same finding: extract ONE shared issue-list paginator to replace the four near-identical loops (transport._api_paged / query._all_issues / migrate._scan_all / core.iter_alias_issues) and converge their bounds and cap-trip loudness — one place to fail loud instead of four divergent caps.
- **[WT-7M4K]** Squash-merged worktree branch leaves a stale merge-base — SessionStart, `infer-critic-mode`/cumulative-Critic, and `pr create` over-count already-merged commits and re-review shipped code
  `effort: L · impact: M · area: worktree · source: user · added: 2026-07-17 · reviewed: 2026-07-18 · status: open · stage: design · related: CRT-6W2N, PR-7T2K, BRF-6K2D · refs: incoming-bugs/archive/squash-merged-branch-left-stale-gates-review-merged-code-and-pr-would-replay.md, skills/pr/SKILL.md (merge-commit default ~:138; post-merge hygiene; create pre-flight gate), bin/prawduct-hook (infer-critic-mode), skills/critic (cumulative interval), Stop/SessionStart briefing (worktree enumeration)`

  **Update — merge-strategy leg handled (`pr-merge-commit-default`):** the `/pr` default flipped squash→merge-commit. A merge-commit merge keeps the branch's commits reachable from the base, so a reused worktree branch's merge-base stays correct and no gate silently re-reviews already-merged work — this dissolves the primary (default-path) failure mode. **This item stays open, rescoped to the residual:** defense-in-depth for what the default flip doesn't cover — a product that *overrides* back to squash (fix ideas #2/#3 merge-base staleness guards still apply there), and the general "a reused branch is behind the base after *any* merge" hygiene gap (fix ideas #1 detection, #4 post-merge hygiene, #5 docs nudge). Severity drops from medium-high to medium.

  Triaged from upstream bug report (discodon, prawduct v3.0.4, reported 2026-07-17). `/prawduct:pr` merges with the **squash** strategy by default (`skills/pr/SKILL.md:138`). After a squash-merge, a long-lived *worktree's* local feature branch still holds its original *granular* commits: their content is now on `origin/develop` under one squash SHA, but their commit **identities** are not — so the merge-base between the stale branch and `origin/develop` sits *before* the squash. Every prawduct surface that reasons about "what's new on this branch" via merge-base then over-counts already-merged work:
  - `infer-critic-mode` picks `cumulative` and computes its interval as `merge-base(origin/develop, HEAD)..HEAD`, spending a full 4–10 min review re-reviewing shipped code and raising coherence findings about **already-merged artifacts** (facts about `develop`'s shipped state, not defects in the new work) that bury the real new-work findings.
  - `/prawduct:pr create` would replay all N already-merged commits onto a develop that already has their squashed equivalent → conflicts or duplicate history.
  - The `SessionStart` briefing enumerates the worktree/branch but does **not** detect that its content is already present upstream as a squash, so nothing warns operator or agent.

  Observed concretely: worktree `wt-discodon-backlog` on `fix/obs-a9rd-debug-rounds` (already merged as squash #1493) read as **17 commits ahead** — 15 stale pre-squash commits + 2 genuinely-new. Caught only because the human operator *remembered* the prior merge; with no such memory an agent proceeds to `/prawduct:pr`, re-commits already-merged docs, and hits the wall at merge time (expensive) or lands duplicate history. Root cause: squash-merge erases the identity link the gates rely on to bound "new work," and there is **no post-merge step** that prunes/flags the stale branch.

  **Fix menu (ranked by leverage in the report — several ship independently):**
  1. *(cheapest, highest-signal, effectively `stage: ready` on its own)* SessionStart per-worktree "already-merged?" flag: `gh pr list --state merged --head <branch> -L1` → if a merged PR exists for this head, annotate the worktree "⚠ already merged as #NNNN — rebase onto origin/develop or start a fresh branch." Fallback when `gh` unavailable: empty `git diff origin/develop...HEAD` net-diff + non-empty `git log origin/develop..HEAD` (prefer this over `git cherry` — squash patch-ids don't match the individual commits').
  2. `infer-critic-mode`/`cumulative` interval: detect a stale merge-base (net diff largely already-upstream, or a merged PR for the head) and refuse to silently review merged code — pick the mode against the rebased interval; at minimum the ahead-count message reads "N ahead, K already merged upstream."
  3. `/prawduct:pr create` pre-flight staleness gate: verify the branch rebases cleanly onto `origin/<base>` and its net diff isn't already merged; refuse (or offer auto-rebase/reset-onto-develop) when squash-stale — last line of defense before conflict-time.
  4. Post-merge hygiene (attacks the root): after a squash-merge, `/prawduct:pr` offers to delete the merged local branch / prune its worktree / rename `shipped/<name>`; a `/prawduct:janitor` or `/prawduct:doctor` check lists worktrees whose branches are already merged.
  5. Docs nudge in the building guide's worktree section: after a branch squash-merges, reset onto `origin/<base>` before building the next increment (the failure mode is reusing a squash-merged branch for the follow-on).

  **Distinctness (cross-linked, not duplicates):** PR-7T2K is the *inverse* squash hazard (gates validate local HEAD but squash merges origin/<branch>, so post-push commits are dropped). CRT-6W2N is the general "no supported worktree workflow" gap (this item is a specific squash-staleness hazard within it). BRF-6K2D is the same missing branch/merge-awareness reasoning in the briefing's "delete the plan" nudge (its mirror: branch *not* merged but nudge says done; here branch *is* merged but gates say not). Governance-protected (`skills/pr`, `bin/prawduct-hook`, Stop/SessionStart hooks) → full Critic + PR review.

  `stage: design` — the problem/requirement is clear (detect a squash-stale worktree branch *before* wasting a cumulative review + PR attempt), but the approach across the five surfaces is an open design choice (which surfaces get the guard, gh-vs-git detection, whether to auto-rebase, where post-merge hygiene lives). Fix #1 is the cheapest ready-to-slice sub-fix. Route to `/prawduct:methodology planning`.

- **[DOC-8L3F]** CLAUDE.md project content exceeds the ~150-line guidance (191 lines) — diet pass needed
  `effort: S · impact: S · area: docs · source: critic · added: 2026-07-17 · status: open · stage: ready · related: MET-7R4J · refs: CLAUDE.md, methodology/building.md (~150-line guidance, :83), skills/critic/review-protocol.md (CLAUDE.md size warning, :97) · reviewed: 2026-07-17`

  Critic WARNING from the ambient-merge-commit-default review: CLAUDE.md is at 191 lines against the ~150-line guidance ("CLAUDE.md is instructions, not documentation" — methodology/building.md:83; the Critic's review protocol warns above ~150). Needs a diet pass — move architecture/reference content to docs/ or .prawduct/artifacts/, compress redundant instruction. Overlaps MET-7R4J (methodology/CLAUDE.md redundancy and prompt-quality pass) — consider running the diet together with that consolidation; kept separate because MET-7R4J targets cross-file rule interference while this is the CLAUDE.md line-count budget itself. (critic)

  2026-07-17 (retrieval-over-generation Critic C-B3): assessed — that cycle added one necessary roster line to CLAUDE.md (Principle 24; roster completeness beats the diet), leaving the count at ~190-191 lines. The diet pass remains this item's job; MET-7R4J stays the consolidation vehicle. (critic)

- **[TST-8C4V]** Guard test binding the `lib/coverage_probes.py` expectation table to `templates/` scaffold existence
  `effort: S · impact: S · area: tests · source: critic · added: 2026-07-17 · status: open · stage: ready · related: GOV-2T6K · refs: lib/coverage_probes.py (TRIGGERED_ARTIFACTS / expectation table), templates/`

  From the architecture-template review (the work that closed GOV-2T6K): add a guard test asserting every expected artifact in the `lib/coverage_probes.py` expectation table has a corresponding authoring template under `templates/` — prevents a future expected artifact entering the table with no authoring template (the exact gap GOV-2T6K just closed for `architecture`). Note the coverage-scaffold stub is deliberately template-independent, so the test asserts **authoring-path parity**, not coverage correctness — coverage functions end-to-end with or without a template; what the test protects is the human-facing authoring starting point. (critic)

- **[TST-5N2Q]** mixed JUnit/non-JUnit polyglot cannot combine `test_commands` with `--from-counts`
  `effort: M · impact: S · area: test-evidence · source: critic · added: 2026-07-17 · status: open · stage: design · related: TST-6F2R, ENV-2W7K, COV-3R9K · refs: bin/prawduct-hook (test-evidence record — test_commands aggregation, --from-counts on-ramp)`

  From the test-evidence-environments review (the work that shipped TST-6F2R's multi-environment `test_commands` list): a product with one environment whose toolchain cannot emit JUnit is excluded from the declared-list form — the aggregated record has no way to accept a counts-only source alongside the JUnit-capable environments. Today's escape is a wrapper script, or repeated `--from-junit` for the JUnit halves plus nothing for the counts half. Design question: should `--from-counts` compose as one more aggregated source (i.e. a counts entry participating in the same multi-environment aggregation) rather than remaining an exclusive whole-record mode? Touches ENV-2W7K's "document --from-counts as the paved non-pytest path" — if composition ships, that documentation should describe the composed form. (critic)

- **[SCN-7K4B]** Session-continuity machinery is chunk-granular only — multi-plan programs have no home in project-state/handoff/briefing, so "what's next" collapses to a flat backlog count when a chunk closes
  `effort: M · impact: M · area: session-continuity · source: reflection · added: 2026-07-02 · reviewed: 2026-07-19 · status: open · stage: design · related: STN-4W7R, MET-3Q8V, MET-8J5R, DOC-3V7T · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md, .prawduct/project-state.yaml (active_build_plan), lib/briefing.py, methodology/building.md (chunk close-out)`

  Multi-plan programs (e.g. the efficiency-review 3-wave fix program) have no home in
  project-state/handoff/briefing — continuity machinery is chunk-granular only, so when a chunk
  closes "what's next" collapses to a flat backlog count. Observed 2026-07-02: agent proposed
  generic next steps despite Wave 1 Plan C (MET-3Q8V, P0, stage:ready) being the planned next
  item; parent artifact framework-efficiency-review-2026-07-02.md says "future sessions read it
  first" but nothing routes sessions to it. Same class as STN-4W7R's thesis: context that depends
  on the agent remembering decays; context attached to checkpoints survives.

  Fix-shape sketch: an `active_program` pointer (parent artifact + ordered plan roster) in
  project-state.yaml; briefing surfaces "Program: X — next: item" when the active build plan is
  complete; handoff template gains a Program-context line; chunk close-out gains an
  update-program-pointer step.

  Overlap notes (kept separate, cross-linked): MET-8J5R defines when a plan IS a program
  (planning guidance); DOC-3V7T gives the parent artifact a home and has `pick` surface it. This
  item is the third leg — the routing/state machinery that carries the program across sessions.
  Related: STN-4W7R, MET-3Q8V. (reflection)

  Salvage note (2026-07-19): recovered verbatim from `feature/gate-exemption-boundary` (cc285bb),
  where it was filed 2026-07-02 and never reached develop's backlog — an orphaned item, not a
  re-file. Still-open verified on develop: a search for `active_program` across `lib/` and
  `project-state.yaml` returns nothing, so none of the fix-shape has landed. If that branch later
  merges it carries the SAME id — resolve the conflict, don't create a second item.

- **[TST-6H2Q]** `test_pr_reviewer.py::TestStopPrReviewGate` stop-gate "blocks" tests flake under xdist cross-FILE pollution
  `effort: M · impact: M · area: test-isolation · source: builder · added: 2026-07-09 · reviewed: 2026-07-19 · status: open · stage: ready · related: TST-4P8H`

  Two tests — `test_stop_with_pr_no_evidence_blocks` and `test_stop_with_pr_and_evidence_missing_findings_blocks` — fail intermittently in the full parallel suite (`python3 -m pytest -q`; config uses `-n` + `--dist loadfile`) but PASS deterministically in isolation and when `test_pr_reviewer.py` runs as a whole file (31 passed). So it is cross-FILE pollution: some earlier test on the same xdist worker leaks global state that makes the stop-gate's "blocks" assertions fail (the gate stops blocking). Suspected culprit class: a test that writes to / operates on the REAL repo-root `.prawduct/` instead of a `tmp_path` (note `test_project_dir_resolution.py::test_get_project_dir_self_check_this_checkout` chdirs to ROOT), leaking a `.gates-waived`/findings/project_dir state that redirects the gate. Pre-existing on develop (reproduced on a tree that is develop + only a backlog.md edit); nondeterministic.

  Fix-shape: find the polluting test (bisect files paired with `test_pr_reviewer` under one worker), make it operate on `tmp_path` / restore global state, add isolation. NOTE: surfaced during gate-friction-batch baseline; NOT introduced by that work. Distinct from TST-4P8H (which is subprocess resource/timeout contention on the same test family) — this is state leakage, a different root cause.

  Salvage note (2026-07-19): recovered verbatim from `feature/gate-friction-batch` (aec6d3e), where
  it was filed 2026-07-09 and never reached develop's backlog. Structural preconditions re-verified
  on develop — both named tests still exist (`tests/test_pr_reviewer.py:99`, `:223`) and the
  suspected root-chdir test still exists (`tests/test_project_dir_resolution.py:193`) — but the
  FLAKE itself was NOT re-reproduced during salvage (that needs repeated full-suite `-n` runs).
  Confirm reproduction before sizing the fix. Kept separate from TST-4P8H per the distinctness
  argument above (state leakage vs. subprocess/timeout contention); cross-linked, not merged.

- **[BKL-4Z7M]** Under `--archive-scope open`, a migrated repo's skipped archive stays out of post-cutover `list` and add-time dedup until someone re-runs
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-20 · status: open · stage: design · related: BKL-6X5D, BKL-3W6K, BKL-6M4T, BKL-8V3D · refs: skills/backlog/SKILL.md:17 (frozen-history routing), skills/backlog/SKILL.md:81 (`find` W2-deferred post-cutover), skills/backlog/adapter-mode.md:145 (adapter's `find` NOTE → `list` filters), skills/backlog/migration-scrub.md (step 2c decision + step 3 tradeoff note), lib/backlog/migrate.py:466 (apply_archive_scope), .prawduct/artifacts/migration-scrub-decisions.md:20 (A1 — prawduct chose `all`), documentation/backlog-service-prd.md:218 · reviewed: 2026-07-20`

  After cutover (`backlog_service_repo` set), `skills/backlog/SKILL.md` treats `.prawduct/backlog.md`
  as frozen history and forbids reading it for live state. Items excluded by `--archive-scope open`
  are therefore not on the service at all. The archive-scope-specific cost lands on the operations
  that **do** work post-cutover: `list` (with `--area=`/`--status=`/`--stage=`/`--kind=` filters)
  silently omits the un-backfilled archive, and add-time dedup — which scans the live backlog —
  misses it too. So a duplicate of a previously-*dropped* item can be re-filed with no signal that
  the project already considered and rejected it.

  **Not a `find` claim.** PR #134 established that post-cutover full-text `find` is W2-deferred for
  *every* item, archived or not — the adapter returns a `NOTE:` pointing at `list` filters
  (`skills/backlog/adapter-mode.md:145`, `skills/backlog/SKILL.md:81`). Archive scope is not what
  puts items outside `find`; `find` simply does not work on the Issues backend yet. The two gaps are
  **additive, not overlapping**: when W2 search lands it will search the live backlog, which still
  won't contain the skipped archive — so W2 **inherits** this gap rather than fixing it.

  **This is recoverable, not data loss (verified 2026-07-20).** `open` *defers* the archive rather
  than discarding it: a repo migrated with `--archive-scope open` can be re-run later with
  `--archive-scope all`, and the already-migrated items are skipped rather than duplicated. The skip
  authority is the permanent `id:PFX` alias label written **atomically in the create**
  (`lib/backlog/migrate.py` — find-or-create skip-if-exists, then reconcile status), not any local
  progress record. Guarded by a test:
  `tests/test_backlog_migrate.py::TestArchiveScope::test_open_then_all_backfills_the_archive_without_duplicating`.
  So the severity here is **discoverability/latency**, not permanence.

  The item is still real: post-cutover `list` and add-time dedup silently omit the archive until
  someone re-runs, and **nothing surfaces that state to the user** — a repo can sit indefinitely
  with an un-backfilled archive and no signal that a one-command backfill is available.

  prawduct itself is unaffected (A1 decided `all` on 2026-07-20), so this is **adopter-facing**.
  Discovered 2026-07-20 while correcting ten claim sites across seven files that wrongly claimed
  the skipped set lives in the MG2 export (the export dumps the migrated repo *post-import*, so by
  construction it never contains what the import excluded). The docs are now truthful about the
  consequence; this item is the product gap behind them.

  Possible shapes, none chosen — cheapest first: **surface the state** (have the adapter or the
  session briefing detect that a repo was migrated with `open` and still has an un-backfilled
  archive, and point at the `--archive-scope all` re-run); export the source markdown to a durable
  artifact at step 0; teach `find` an explicit opt-in archive-history read; or accept and document.
  Related to BKL-6X5D (the quantified recent-shipped window between the `open`/`all` poles — same
  lever, different consequence: that item is the rate/volume budget, this one is post-cutover
  reachability).

- **[GOV-9T2K]** Upgrading consumers keep the old version's plugin cache directory, including prawduct's internal state
  `effort: S · impact: L · area: governance/plugin-runtime · kind: fix · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: open · stage: ready · related: GOV-4H7T, ENV-7C4K · refs: .claude-plugin/marketplace.json (`"source": "./plugin"` — the GOV-4H7T fix), .prawduct/change-log.md (v3.1.1 packaging entry, which cites this id), plugin/skills/doctor/SKILL.md (candidate surface for option (c))`

  Plugin caches are version-keyed at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`. Verified 2026-07-21 by installing v3.1.0 into an isolated `CLAUDE_CONFIG_DIR`, advancing the source repo to v3.1.1, and running `claude plugin marketplace update` + `claude plugin update`: the active plugin correctly becomes the clean 3.1.1 tree (109 files, no `.prawduct/`), but the `3.1.0/` directory is **retained on disk** with all 314 files including prawduct's backlog, learnings, change-log, build plans and test suite. `claude plugin prune` does not remove it ("Nothing to prune (no auto-installed plugins at user scope)").

  Consequence: GOV-4H7T's fix is complete for what *loads* but partial for what is *on disk*. A model globbing broadly under `~/.claude/plugins/cache/` in a consuming repo can still reach prawduct's internal state from the stale directory. The condition is pre-existing — v3.1.0 is what put it there — and v3.1.1 stops adding to it rather than cleaning it up, which is why this is filed rather than treated as a v3.1.1 blocker.

  Open questions for whoever picks this up: (a) does Claude Code prune old version directories on any schedule, or is retention indefinite? (b) is there a supported hook or manifest field for post-update cleanup, or is the only remedy documentation telling operators to delete the directory? (c) should the v3.1.1 release note or `/prawduct:doctor` surface the stale-cache condition and offer the delete, since doctor already checks install conformance and is the natural place a consumer would learn about it? Option (c) is probably the cheapest real improvement. (user)

  **Measured 2026-07-21 on a real multi-profile machine, and it is worse than the item first assumed.** Plugin caches are per *config directory*, not per machine. A maintainer running several Claude Code profiles (multiple Anthropic accounts, devcontainer variants) carries an independent cache set in each. Observed: **four config dirs (`~/.claude`, `~/.claude-second`, `~/.claude-devcontainer`, `~/.claude-second-devcontainer`), 16 version directories, ~90 MB total**, with each pre-v3.1.1 copy still holding prawduct's `.prawduct/`, `tests/` and `documentation/` — the exact contamination v3.1.1 removes. The owner confirms multiple agents and multiple accounts on the machine is their normal working setup, so this is a routine configuration rather than an edge case.

  Two consequences. First, the remediation is not a single `rm` — a consumer following per-profile guidance must repeat it for every profile, and will not necessarily know how many they have. Second, and more important: it strengthens option (c) from the original three. `/prawduct:doctor` already checks install conformance and is the one surface a consumer would plausibly run; a check that globs `~/.claude*/plugins/cache/<plugin>/` and reports version directories below the running version — with the delete command — converts an invisible accumulation into a one-line actionable report. That is cheap, needs no upstream mechanism, and works regardless of whether Claude Code ever prunes on its own. Recommend scoping (c) first and treating (a) and (b) as research that may never be needed.

  Impact raised M → L on that basis: not tidiness, but ~90 MB of another product's requirements and documentation sitting readable in every profile of a routine developer setup, which is the harm GOV-4H7T was raised to eliminate.

  Note: v3.1.1's shipped CHANGELOG now states `~/.claude*/plugins/cache/prawduct/` with the `du` command and the measured scale, so consumers get the manual remedy today; this item is the durable fix.

- **[BKL-8Q3D]** `/prawduct:backlog update stage=X` flips the metadata field but leaves stage-DESCRIBING body prose stale, contradicting the new stage and misrouting pick
  `effort: S · impact: M · area: backlog · kind: debt · source: reflection · added: 2026-07-23 · reviewed: 2026-07-23 · status: open · stage: research · related: BKL-7Q4M, BKL-9XQ2 · refs: plugin/skills/backlog/SKILL.md (### update — the mutation site that flips `stage:` without reconciling body prose), .prawduct/learnings.md:109 (reconcile a mechanism's retained self-descriptions in the same change or the prose reads as false), .prawduct/learnings.md:47 (stale-prose / falsification-query family — a replacement sentence gets the same falsification query the original needed)`

  **Filed from reflection — the backlog skill's own `update` mutation site has the very stale-prose failure the skill exists to prevent elsewhere.** Advancing an item's stage via `/prawduct:backlog update stage=X` changes the `stage:` **metadata field** but does NOT reconcile the item's **body prose** that describes or justifies the *old* stage — e.g. "`stage: requirements` is deliberate and load-bearing", "do NOT route this into implementation via `pick`", "route through discovery", "open questions to settle below". After the field flips, that prose contradicts the new stage and would **misroute `pick`**: an item now at `stage: design` whose body still says "do not route into implementation, see /prawduct:methodology discovery" sends a reader who trusts the prose over the field back to discovery.

  **Evidence — 2026-07-23 consolidation session.** Advancing BKL-7Q4M and BKL-9XQ2 (with a design→requirements→design correction mid-flight) left stale stage-describing prose in ~5 body spots (opening block, escalation block, sub-concern blocks, cross-references, a `refs:` annotation), caught only incrementally across ~3 extra backlog passes plus a Critic warning (stale-prose-after-status-change). The skill flips one field, but a stage change semantically ripples through the prose.

  **Fix-shape (needs design — hence `stage: research`, not `ready`).** When `update` changes `stage`, detect stage-describing body prose (a small set of stage-referencing phrases — "stage: <name> is deliberate", "do NOT route … via pick", "route through discovery/planning", "open questions to settle") and prompt to reconcile it; at minimum warn "body prose references the old stage — reconcile it". This is the pattern-sweep / stale-prose-after-status-change learnings operationalized at the skill's own mutation site.

  Relates to the documented stale-prose-after-status-change learnings: `.prawduct/learnings.md:109` (when you change a mechanism, reconcile its retained self-descriptions in the same change or the prose reads as false) and `:47` (a replacement sentence gets the same falsification query the original needed). (reflection)

- **[SCN-2M6P]** The handoff preservation net catches a REPLACED `.session-handoff.md` but not an APPENDED one — the marker is still present, so appended model text is silently overwritten
  `effort: M · impact: S · area: session-continuity · kind: bug · source: critic · added: 2026-07-26 · reviewed: 2026-07-26 · status: open · stage: ready · related: SCN-4H9T, CRT-7P5J, SCN-7K4B · refs: plugin/lib/briefing.py:922-931 (`HANDOFF_MARKER` / `HANDOFF_MARKER_PREFIX` — the machine marker and its "do not hand-edit" redirect), plugin/lib/briefing.py:985-1010 (`_read_unmarked_handoff` — the rescue, keyed on marker ABSENCE), plugin/lib/briefing.py:1031 (every generated handoff opens with the marker), plugin/lib/briefing.py:1049 (the "had no machine marker, so it was preserved" note), plugin/lib/briefing.py:935 (`HANDOFF_NOTES_NAME` — the documented forward channel), plugin/bin/prawduct-hook:540 (consume-and-clear of `.handoff-notes.md`), .prawduct/artifacts/build-plan-session-handoff-continuity.md (Chunk 01 built the net; Chunk 03 is the affordance mitigation) · revisit: after the Chunk 01 governance checkpoint reports whether the unmarked-handoff rescue fires in practice`

  **Known gap, deliberately left open at build time — not an oversight.** `generate_session_handoff` stamps `HANDOFF_MARKER` on every handoff it writes, and `_read_unmarked_handoff` rescues a `.session-handoff.md` that **lacks** the marker (model- or human-authored) by folding its body into the new handoff. The net is keyed on marker *absence*, so it catches an agent who **replaces** the file.

  **It does not catch an agent who APPENDS** to a marked, machine-generated handoff. The marker is still the first body line, so the file reads as machine-written, the rescue returns `""`, and the appended text is overwritten and lost — the same silent-context-loss failure mode SCN-4H9T was filed for, surviving in a narrower shape.

  **Why it wasn't closed.** Detection requires retaining a copy or content hash of what the machine generated, to diff the on-disk file against at the next `/clear`. That was judged disproportionate for a case the marker text explicitly redirects ("Do not hand-edit … forward notes go in `.prawduct/.handoff-notes.md`"), and it drags in the content-hash-freshness question this repo has ruled on before (cf. COV-3M8Q's discussion of the do-not-reintroduce constraint) — so it is a design question, not a mechanical patch, despite the item being well-understood.

  **What ships instead.** Chunk 03 is *affordance* work — documenting the notes channel in `building.md` / `reflection.md` / the session digests so agents reach for `.handoff-notes.md` rather than the handoff file. That is mitigation, not detection: it lowers the rate, it does not close the hole.

  **Impact is rated S conditionally, and the condition is written into `revisit:`.** The residual case is narrow *because* the affordance work is in flight. If the Chunk 01 governance checkpoint shows the unmarked-handoff rescue firing at all in practice, that is evidence agents still reach for the wrong file despite the redirect — which raises this to a real detection requirement and the impact with it. Re-rate on that evidence rather than on intuition.

  Filed from the Chunk 01 Critic review (note severity) on `feature/session-handoff-continuity`, whose only other home would be a build plan deleted at release. Governance-protected (`plugin/lib/`, session-continuity machinery) → full Critic + PR review. (critic)

- **[SCN-8T4R]** The session-file registry is a replicated contract surface with no `boundary-patterns.md` entry — four sites edited in lockstep, only two held together by a test
  `effort: M · impact: M · area: session-continuity · kind: tech-debt · source: critic · added: 2026-07-26 · reviewed: 2026-07-26 · status: open · stage: ready · related: SCN-4H9T, STH-8M3V · refs: plugin/lib/core.py:76 (`GITIGNORE_ENTRIES` — site 1), plugin/bin/prawduct-hook:415 (`_SESSION_GITIGNORED_PATHS` — site 2, the untrack set), .gitignore:3-43 (this repo's own copy — site 3), plugin/bin/prawduct-hook (site 4 — the session-file deletion loop in `cmd_clear`, the `for name in (".session-reflected", …)` loop — symbol-anchored deliberately: this ref was drafted as `:690` and was already stale one commit later), tests/test_build_plan_resolution.py:208-228 (the sites-1↔2 parity test — the ONLY guard), .prawduct/artifacts/boundary-patterns.md (where the entry is missing), plugin/bin/prawduct-hook:291 and plugin/hooks/banner.py:29 (comments that name the 1↔2 mirror but not the full set)`

  **Adding one session file requires editing at least four places in lockstep:**
  1. `core.GITIGNORE_ENTRIES` (`plugin/lib/core.py:76`) — the canonical set
  2. the hook's `_SESSION_GITIGNORED_PATHS` (`plugin/bin/prawduct-hook:415`) — the untrack set used by `_untrack_session_files`
  3. this repo's own `.gitignore`
  4. the session-file deletion loop in `cmd_clear` (`plugin/bin/prawduct-hook`, the `for name in (".session-reflected", …)` loop)

  **Only sites 1 and 2 are guarded** — `tests/test_build_plan_resolution.py:208-228` asserts the mirror parity (with an explicit `__pycache__` carve-out). Sites 3 and 4 can silently fall out of sync: a new session file that misses site 3 gets committed by accident, and one that misses site 4 survives `/clear` and leaks state into the next session.

  **`boundary-patterns.md` does not record this as a contract surface at all** (verified — it contains no session-file, gitignore, or registry entry). So nothing tells the next author that a fourth site exists or which ones are guarded. The two in-code comments that mention the pattern (`prawduct-hook:291`, `hooks/banner.py:29`) name only the 1↔2 mirror, which actively *understates* the fan-out to a reader who finds them.

  **Surfaced concretely** during `session-handoff-continuity` Chunk 01 when adding `.prawduct/.handoff-notes.md` — it had to be threaded through all four sites by hand.

  **Fix direction, two legs.** (a) Record it in `boundary-patterns.md` as a replicated registry, naming all four sites and which parity test covers which — cheap, and it is the leg that stops the next author guessing. (b) Consider whether sites 2–4 can be *derived* from `GITIGNORE_ENTRIES` rather than kept in sync by hand; the existing `__pycache__` carve-out in the parity test is the shape of the divergence any derivation has to model, so this leg needs a look at the real differences before committing to it. Leg (a) is worth doing even if leg (b) is rejected.

  Filed from the Chunk 01 Critic review (note severity) on `feature/session-handoff-continuity`. Governance-protected (`plugin/lib/`, `plugin/bin/`) → full Critic + PR review. (critic)

- **[STH-4P2R]** A `views_enabled` repo's SessionStart re-resolves git-derived chunk progress 3× per `/clear` — 12–16 git subprocesses answering one question — memoize the resolution per process
  `effort: S · impact: M · area: performance · kind: debt · source: critic · added: 2026-07-26 · status: open · stage: ready · related: STH-3K7M, STH-6Q9D, BLD-7K3Q, SCN-4H9T · refs: plugin/lib/buildplan_refs.py:287 (`resolve_chunk_progress`), plugin/lib/buildplan_refs.py:200 (`_git_aware_progress`), plugin/lib/briefing.py:152 (`staleness_scan`), plugin/lib/briefing.py:440 (`_get_active_work`), plugin/lib/briefing.py:542 (`assemble_session_briefing`), plugin/lib/briefing.py:1141 (`generate_session_handoff`), .prawduct/artifacts/build-plan-hot-path-git-batching.md (the standing concern that sets the posture), tests/test_hot_path_git_batching.py`

  **Origin.** `session-handoff-continuity` Chunk 02 routed every build-plan progress consumer through `buildplan_refs.resolve_chunk_progress`. On a `views_enabled` repo ahead of its base, that path runs `_resolve_base_branch` + `git rev-list --count` + `git log --format=%s` — roughly 4 git invocations per resolution, on a code path that previously ran **none**.

  **The cost.** One `/clear` reaches `_parse_build_plan_status` from three places: `staleness_scan`, `assemble_session_briefing` (via `_get_active_work`), and `generate_session_handoff` (via `_get_active_work`). That is ~3 resolutions × ~4 git invocations = **12–16 subprocesses per SessionStart**, all answering the identical question "which chunk is current." `assemble_session_briefing` already dedupes *its own* two calls; the cross-function repetition is what remains.

  **Deliberately not fixed in Chunk 02.** The Critic recommended a backlog item over a scope expansion rather than growing the chunk — this is that item, not an oversight.

  **Posture is already established, don't relitigate it.** This repo carries a standing hot-path-git-batching concern (`.prawduct/artifacts/build-plan-hot-path-git-batching.md`, pinned by `tests/test_hot_path_git_batching.py`): **batch or memoize, do not cache-with-invalidation.**

  **Fix-shape (two options, both mechanical).**
  1. A per-process memo of the git-derived progress keyed on the resolved project dir, with an **explicit reset hook for tests** (a process-lifetime memo without a reset is a test-isolation bug waiting to happen).
  2. Thread one resolved `ChunkProgress` through `cmd_clear`'s consumers, so the resolution happens once at the entry and is passed down.

  **The gate path does not pay this** — `_has_active_build_plan_file` (`plugin/lib/gates.py:744`) was deliberately kept on the cheap checkbox reading, so this is a SessionStart-briefing/handoff cost only.

  **Cluster note (do these together).** **STH-3K7M** is the *same fix on the same hot path* for a different value — `_get_current_branch` invoked 4× across `staleness_scan` / `assemble_session_briefing` / `_parse_wip`, with the identical "cross-function thread, unlike a local batch" rationale. Whoever picks either should sweep both: one "resolve the session's git context once at the `cmd_clear` entry and pass it down" change closes both items. **STH-6Q9D** (shipped, `hot-path-git-batching`) is the precedent that set the posture; **BLD-7K3Q** (shipped, `closed-by: session-handoff-continuity`) is the correctness fix that made the git-derived path load-bearing and therefore introduced this cost.

  Filed from the Chunk 02 Critic review on `feature/session-handoff-continuity`. Governance-protected (`plugin/lib/`, SessionStart hot path) → full Critic + PR review. (critic)

- **[ROB-7T2N]** Sweep explicit encoding across the ~67 remaining bare `read_text()` calls in the plugin runtime, or pin the rule repo-wide
  `effort: M · impact: M · area: robustness · kind: debt · source: critic · added: 2026-07-26 · status: open · stage: ready · related: STH-8M3V, STH-9T4F, TST-3E8V · refs: tests/preferences/test_build_plan_decoding.py (the build-plan pin — both axes, two mechanisms, vacuity guard), tests/test_handoff_parser_correctness.py::TestNonUtf8PlanDegrades (the behavioral half — asserts the designed degradation actually runs), plugin/lib/buildplan_refs.py (the swept module + docstring stating the rule), plugin/lib/views.py (swept + designed degradations), plugin/lib/critic_mode.py, plugin/lib/ledger.py (_scope_from_plan — folded onto the canonical frontmatter reader), plugin/bin/prawduct-hook · reviewed: 2026-07-26`

  **Origin.** `session-handoff-continuity` Chunk 02 found the same class **three review rounds running**: a file read that decodes with the *operator's locale*, so two readers of the SAME file can disagree by construction about whether it parses. The rest of the runtime was deliberately left alone as scope creep; this item is that deferral, not an oversight.

  **Status of the build-plan slice — a dated verification, NOT a standing claim of closure (verified 2026-07-26 at `7d03b56`).** Build-plan reads are fixed and pinned in `tests/preferences/test_build_plan_decoding.py` (the home this item itself recommended; the pin previously lived at `tests/test_handoff_parser_correctness.py::test_every_build_plan_read_names_its_encoding`, **which no longer exists** — do not grep for it). The pin checks **both** axes plus a vacuity guard:
  - `test_every_build_plan_read_names_utf8` — the codec axis.
  - `test_every_guarded_build_plan_read_catches_unicode_decode_error` — the except-set axis. As of 2026-07-26 every build-plan read the pin sees passes both axes. Phrase it that way and no stronger: an earlier revision of this item said "this half is now closed for build-plan reads," and that sentence was **false when written**. Still open at the time: `plugin/lib/views.py::diagnose_scope_plan_coverage` — a line-for-line twin of `build_scope_to_plan_map` sixty-eight lines above it (same `artifacts/*.md` glob, same `_parse_build_plan_frontmatter_scope` consumer) still caught `OSError` alone, and was *worse*-guarded than its twin: `prawduct-hook` calls it bare with no global handler and it had no designed degradation, so one non-UTF-8 file under `artifacts/` tracebacked out of `regen-views`, across a boundary whose recorded error model forbids an internal stack trace crossing it. Fixed at `7d03b56`.
  - `test_the_pin_has_something_to_check` — vacuity guard (≥12 matches), so a rename can't silently empty coverage.

  **Do not hand-count the swept sites — ask the pin.** The earlier revision of this item enumerated "`plugin/lib/views.py` (×2)", which was wrong in both directions: there are **four** widened sites in that module and it omitted the one that was still unwidened. Run the pin's collector (`_plan_reads()` in `tests/preferences/test_build_plan_decoding.py`) for the current, mechanically-derived list of file/line/function/guard. A hand-count in this item will drift again.

  **There is no skip list.** The earlier revision named `buildplan_refs._parse_build_plan_status` "the one skip." That is retired, and the framing was wrong anyway. The except-set test scopes itself to reads that are *guarded at all* (an unguarded read is a deliberate let-it-propagate choice the pin does not second-guess) and accepts a broad `except Exception`. That site's guard sits 74 lines below it, and the rebuilt pin walks to the enclosing `try` however far away it is — so it passes **on its merits**, not by exemption. No site is exempted.

  **What the instrument actually is (the old description is stale — this is the one to trust).** The pin no longer keys on the `plan_path.read_text(` local-name idiom at all. It is AST-based, in two mechanisms, each covering the other's blind spot:
  1. **File-scoped and exhaustive** over `plugin/lib/buildplan_refs.py` and `plugin/lib/views.py` — the modules whose job *is* the build plan, so **every** `read_text` in them counts regardless of what the local is called. No naming convention left to drift from.
  2. **AST data-flow** for readers outside those modules — any read whose content is passed to a build-plan parser (the `PLAN_PARSERS` set). Catches `critic_mode` and `ledger` without dragging in their unrelated JSON reads (those are this item's territory).

  It sees **16 reads** as of 2026-07-26 where the idiom saw **12** (the rebuild commit's message says 15; the number moves, which is exactly why it is derived by running the collector and not maintained here). The sweeper does **not** need to widen the detector to AST — that is done. The open design question is only how to extend the rule, or a rule of its shape, to the remaining ~67 general runtime reads.

  **A third hand-rolled frontmatter parser fell out of closing the data-flow gap — expect more of these.** `ledger._scope_from_plan` parsed the plan's frontmatter **inline**, which is precisely why the pin could not see it (it never called `views._parse_build_plan_frontmatter_scope`, so there was no data-flow edge to follow). It also **could not read a comment-header plan**: it required `---` on line 1, and 16 of this repo's 48 plans open with an HTML comment first (the other 32, including the plan this branch is executing, open with `---`) — counts as of 2026-07-27, and re-derive them before relying on them: `for f in .prawduct/artifacts/build-plan*.md; do head -1 "$f"; done | sort | uniq -c`. That divergence is real in principle and **zero in practice here** — on all 16 the frontmatter `scope:` is byte-identical to the filename stem, which was the inline copy's fallback, so it produced the canonical answer on every file in the repo. An earlier version of this paragraph claimed "every real build-plan" opens with a comment header AND an observable disagreement; both were false and neither was checked before being written. The verifiable driver is the data-flow one above, which needs no corroboration. Folded onto the canonical reader at `7d03b56`. The lesson for the ~67-site sweep: an inline re-implementation is invisible to a data-flow detector *and* is where the disagreement lives.

  **The deferred sweep should EXTEND that file, not re-derive the rule.** The two-axis framing, the reachability argument (PEP 538/540 narrow the "fails to decode" risk; the real risk is *disagreement*), and why each of the two mechanisms exists are already written down there. Note the pin deliberately does **not** treat every `read_text` under `plugin/` as a build-plan read — that would sweep every unrelated file read in the runtime, which is this item's own territory and a different risk profile, and would make the rule mean something else.

  **The surface.** `grep -rn "read_text()" plugin/lib plugin/bin` returns **67 sites** (verified 2026-07-26) reading `learnings.md`, gitignore, `project-state.yaml`, `VERSION`, findings JSON, evidence JSONL, templates and more.

  **Two facets, both worth deciding deliberately rather than by default.**
  1. **The codec.** Which of these files can contain non-ASCII authored by a model or a human? `learnings.md`, `project-state.yaml`, artifacts and templates certainly can. JSON reads are lower risk since `json.loads` handles its own encoding rules — but the *read* still happens first.
  2. **The except-set (the sharper half).** `UnicodeDecodeError` is a **`ValueError`, NOT an `OSError`**, so every `except OSError` wrapped around a `read_text` lets it escape. The build-plan case escaped past an unguarded caller in `bin/prawduct-hook` as a **traceback rather than a degradation**.

  **Fix-shape options (the embedded decision — make it, don't relitigate the problem).** Either (a) sweep all sites and add a repo-wide pin in `tests/preferences/` that every `read_text` under `plugin/` names an encoding; or (b) scope the pin to files a model or a human authors and record *why* the rest are exempt. **Prefer whichever is enforceable** — the reason this class recurred is that it was a **convention, not a pin**.

  **Prior art in the same family.** STH-8M3V (shipped) already noted that `gitstate._get_session_changed_files` lacks the `(UnicodeDecodeError, OSError)` guard its siblings have — the same except-set gap, spotted a month earlier and never generalized. TST-3E8V (shipped) is the sibling widen-the-except fix. That two-for-two history is the argument for the repo-wide pin over another one-site patch. `tests/preferences/test_no_upstream_content_egress.py` is the local precedent for a preference-pin of this shape.

  Filed from the Chunk 02 Critic review on `feature/session-handoff-continuity`. Governance-protected (`plugin/lib/`, `plugin/bin/`) → full Critic + PR review. (critic)

- **[SCN-6V3D]** Git-derived chunk progress degrades to the known-wrong checkbox reading silently — `ChunkProgress.git_derived` records which reading answered and no production caller reads it
  `effort: S · impact: S · area: session-continuity · kind: bug · source: critic · added: 2026-07-27 · reviewed: 2026-07-27 · status: open · stage: ready · related: SCN-4H9T, STH-4P2R, BLD-7K3Q, BLD-8R3T, CRT-7B4M · refs: plugin/lib/buildplan_refs.py:230 (`_git_aware_progress` — the six `return None` paths), plugin/lib/buildplan_refs.py:309 (`ChunkProgress` — the `git_derived` field and the docstring that states this gap honestly), plugin/lib/buildplan_refs.py:335 (`resolve_chunk_progress` — the ONE progress answer, and two more `git_derived=False` returns), plugin/lib/buildplan_refs.py:362 (`_resolve_chunk_progress_from` — where the fallback is chosen), tests/test_handoff_parser_correctness.py:227 (`assert progress.git_derived is True` — the only reader), .prawduct/learnings.md:329 ("Advice fails soft" is not "advice fails silent" — the rule this instantiates), plugin/lib/gates.py:744 (`_has_active_build_plan_file` — the deliberate checkbox-reading precedent)`

  **The gap.** `_git_aware_progress` returns `None` — falling back to the checkbox reading — for several distinct reasons: `views_enabled` unset, no base branch resolves, HEAD not ahead of base, no chunk id appears in a commit since base, and any `OSError`/`SubprocessError` from git. (There is a sixth, `total <= 0`; it is inert, since with no Status items both readings are empty.) The `views_enabled`-unset case is normal and correct. The rest are **degradations**, and on a `views_enabled` repo mid-branch the checkbox reading is the one **known** to be wrong — every box reads unchecked until release, which is the entire reason the git derivation exists. Nothing announces it.

  **The discarded signal.** `ChunkProgress.git_derived` records which reading answered. It is asserted by `tests/test_handoff_parser_correctness.py:227` and read by **no production caller** — so the information needed to report *why* is computed and thrown away. Note `resolve_chunk_progress` also returns `git_derived=False` on its two early exits (no plan file, unreadable plan); those carry `has_status_items=False`, so a reporting surface can distinguish "no plan" from "plan read, git path bailed" without new plumbing.

  **Why this is a defect and not a nit.** It is an instance of this repo's own ratified rule — *"advice fails soft" is not "advice fails silent": a degraded advisory path must still name its consequence* (`.prawduct/learnings.md:329`, filed from Chunk 01 of this same branch). The consequence here is a handoff/briefing that reports the wrong current chunk with full confidence.

  **The fix is NOT a diagnostic at the failure point.** `_git_aware_progress` runs on the SessionStart/Stop hot path, most `git_derived=False` answers are perfectly normal, and a notice on every session is the noise pattern the orphan-term hook already taught us to avoid. The work is **picking the surface that should report** — a deliberately-invoked diagnostic one. Candidates worth *evaluating* rather than a decision already made:
  - `prawduct-hook handoff preview` — a human ran it precisely to ask what the machine thinks.
  - `verify-chunk-refs` — already prints a per-chunk verdict.
  - the session briefing's Resume line.

  **Narrow it to the case that actually matters:** `views_enabled` is true **AND** the git path bailed. That is the only combination where the fallback is known-wrong rather than merely unused; reporting the `views_enabled`-unset case would be pure noise.

  Surfaced by the `session-handoff-continuity` Chunk 03 cumulative Critic (2026-07-27, warning). The `ChunkProgress` docstring was corrected in `90397b6` to state the gap honestly instead of claiming a capability — **this item is what makes the word "tracked" in that docstring true.** Governance-protected (`plugin/lib/`, SessionStart hot path) → full Critic + PR review. (critic)

- **[SCN-5B8Q]** SessionStart treats `resume` as a work boundary — `clear --session-start` destroys in-flight session state on a *continuation*, and re-anchoring the session base silently narrows the session-end Critic gate's own jurisdiction
  `effort: S · impact: M · area: session-continuity · kind: bug · source: user · added: 2026-07-27 · reviewed: 2026-07-27 · status: open · stage: ready · related: SCN-4H9T, SCN-2M6P, SCN-8T4R, CRT-3X9D · refs: plugin/hooks/hooks.json:25 (the `startup|resume|clear` matcher on `clear --session-start` — the single line that forces the coupling), plugin/hooks/hooks.json:5/:15/:35 (banner, digest, build-index — all `startup|resume|clear|compact`, which is why a compacted session gets those three but no briefing), plugin/bin/prawduct-hook:584 (`cmd_clear` — the one entry point doing both jobs), plugin/bin/prawduct-hook:620-645 (critic-active marker sweep vs. refusal), plugin/bin/prawduct-hook:647-656 (`_check_previous_session_gates` warning), plugin/bin/prawduct-hook:658-669 (`_untrack_session_files`), plugin/bin/prawduct-hook:671-696 + :540 (`generate_session_handoff` + `_consume_handoff_notes` — MUTATING), plugin/bin/prawduct-hook:698-709 (`.session-reflected` → `reflections.md` archive — MUTATING), plugin/bin/prawduct-hook:715 (the session-file deletion loop — MUTATING), plugin/bin/prawduct-hook:729-736 (`.session-start` recapture — MUTATING), plugin/bin/prawduct-hook:800-812 (advisory probe refresh — read-only), plugin/bin/prawduct-hook:818-826 (`.session-git-baseline` recapture — MUTATING), plugin/bin/prawduct-hook:840-857 (`.session-base-tree` recapture — MUTATING, the Critic-gate anchor), plugin/bin/prawduct-hook:864 (`assemble_session_briefing` — read-only), plugin/lib/gates.py:484 (`_read_session_base_tree`), plugin/lib/gates.py:556-585 (the Stop-hook Critic gate — composes coverage from the session base tree to the working tree), plugin/lib/gates.py:514 (`session_changes_all_non_judgeable` — the baseline-relative gate-skip predicate), plugin/lib/gitstate.py:230 (`git_has_session_changes`), plugin/lib/gitstate.py:447 (`_get_session_changed_files`)`

  The `clear --session-start` hook is registered with matcher `startup|resume|clear` (`plugin/hooks/hooks.json:25`), and `cmd_clear` is a full boundary reset. So `claude --resume` / `--continue` — a session **continuation**, where the transcript is restored and nothing was lost — runs the same destructive path as a real boundary.

  **Reproduced end-to-end in a scratch repo, not inferred.** After a simulated resume: `.prawduct/.handoff-notes.md` was DELETED (consumed into a handoff for a session still running); `.prawduct/.session-reflected` was archived to `reflections.md` and DELETED mid-session; `.session-git-baseline` and `.session-start` were recaptured; and `.session-handoff.md` was written describing a session that had not ended.

  **THE CONTINUITY HALF ABOVE IS THIS ITEM'S PRIMARY JUSTIFICATION.** It was reproduced end-to-end and no part of it is affected by the correction below. The governance half is real but *smaller than this item originally claimed*; the correction is recorded in full rather than quietly edited away.

  **The anchor anatomy (checked against the live tree while filing, 2026-07-27 — this part stands).** The porcelain baseline (`.session-git-baseline`) is only half the anchor, and the smaller half — it feeds `git_has_session_changes` / `_get_session_changed_files` (`plugin/lib/gitstate.py:230`, `:447`) and through them `session_changes_all_non_judgeable` (`plugin/lib/gates.py:514`), the predicate that decides a session's changes are all non-judgeable and the gates may be skipped. The **load-bearing** anchor is `.session-base-tree` — the `HEAD^{tree}` SHA `cmd_clear` records at session start and the deletion loop at `:715` removes on every fire. The Stop-hook Critic gate's whole question is *"does composed review coverage span this session's base tree → the current working tree"* (`plugin/lib/gates.py:556-585`). Re-recording that marker at the resume point moves the base forward.

  **WHAT THAT ACTUALLY COSTS — undocumented narrowing, not an exploitable hole.** On resume the session-end gate silently narrows *its own jurisdiction* to `resume-point → working tree`. Nothing reports the narrowing, and it is not among the degradations `session_review_verdict`'s docstring carefully enumerates: that docstring covers a **missing** marker (jurisdiction shrinks to uncommitted work), not a silently **re-anchored** one. So the weaker end-of-session check is invisible to the person relying on it. That is the whole of the governance defect — worth fixing alongside the continuity half, not worth calling a hole.

  **CORRECTION (owner challenge, 2026-07-27, accepted — `impact` lowered L → M).** This item previously claimed re-anchoring "blinds the Critic gate" and put "every commit made before the resume outside the gate's jurisdiction by construction"; the filing-time verification note amplified it. Overstated, on two counts each re-verified in code:
  - `session_review_verdict` **already documents the committed-but-unreviewed case as a deliberate degradation** — *"A commit made without review leaves a gap no dispatchable review can span from the session base (chunk/final reviews anchor at HEAD's tree); composed coverage of merge-base → working tree is the PR gate's own bar — strictly stronger evidence about the current state — so requiring an unsatisfiable base instead would only train waivers"* (`plugin/lib/gates.py:582-588`). That merge-base fallback is **unaffected** by a re-anchored marker: it fires whenever the marker-based verdict fails to compose (`gates.py:623-630`), so a resume cannot defeat it. It equally does not *rescue* the narrowed case — when the narrow span composes clean, the fallback is never consulted — which is exactly why the residue is undocumented narrowing rather than a hole.
  - `check_cumulative_critic` (`plugin/lib/gates.py:885`) **independently requires composed coverage of `merge-base(base_branch, HEAD)` → `HEAD` before any PR is created.** Unreviewed pre-resume commits are therefore caught at the **merge** boundary regardless; the session gate was never the last line of defence.

  **The owner's framing, preserved because it is the correct one:** per-chunk review facts **compose over trees**, which is exactly why the framework does not re-review the cumulative stack on every commit — demanding session-base coverage that no dispatchable review can produce would only train waivers, which is precisely what the fallback exists to prevent.

  **ROOT CAUSE:** `cmd_clear` does two categorically different jobs under one entry point.
  - **READ-ONLY ORIENTATION** — render the session briefing (`:864`), refresh advisories (`:800-812`), sweep a stale `.critic-active` marker (`:620-645`), untrack accidentally-committed session files (`:658-669`), warn on the previous session's unmet gates (`:647-656`).
  - **MUTATING BOUNDARY WORK** — generate `.session-handoff.md` (`:671-696`), consume and delete `.handoff-notes.md` (`:540`), archive and delete `.session-reflected` (`:698-709`), reset the git baseline (`:818-826`) and `.session-base-tree` (`:840-857`) and `.session-start` (`:729-736`), delete `.gates-waived` (`:715`).

  `resume` needs the first column and must not get the second; the matcher forces both.

  **PROPOSED FIX (owner-reviewed shape, not yet ruled):** keep one entry point and split by matcher — `startup|clear` gets `clear --session-start` (both columns), `resume|compact` gets a new read-only `clear --brief-only` (first column only). No stdin parsing, no new entry point: the matcher already carries the one fact needed.

  **REJECTED ALTERNATIVE, recorded so nobody re-proposes it.** Simply dropping `resume` from the matcher is a one-token diff that discards BOTH columns — no briefing on resume (you resume into a repo you believe is unchanged: new commits, new advisories, another worktree taken), no `.critic-active` sweep (so a crashed Critic leaves `clear` refusing until the 30-minute expiry — resume is currently what rescues you from that), no defensive untrack. The owner confirmed from repeated observation that the session briefing has substantial value, which settles it: the read-only half must keep firing.

  **INCIDENTAL GAP the fix closes:** `compact` is excluded from the `clear` hook entirely (it *is* on the banner/digest/build-index matchers at `hooks.json:5`/`:15`/`:35`), so a compacted session gets banner + digest + index but NO briefing — and compaction is the one source where context genuinely was just lost.

  Governance-protected (`plugin/hooks/`, `plugin/bin/prawduct-hook`, SessionStart/Stop gate machinery) → full Critic + PR review. (user — continuity half reproduced in a scratch repo; refs and the `.session-base-tree` anatomy verified against the working tree at filing time; the *severity* the filing note attached to that anatomy was overstated and was corrected 2026-07-27 against `gates.py` — see CORRECTION above)

## Promoted

- **[BKL-5D2C]** Move the backlog out of git to a centralized, agent-friendly issue-tracking service
  `effort: L · impact: L · area: backlog · source: user · added: 2026-07-13 · status: promoted · stage: ready · related: BKL-7M4Q, BKL-8T3W, BKL-3R8P · refs: documentation/backlog-service-requirements.md, artifacts/build-plan-backlog-service.md · reviewed: 2026-07-18`

  Umbrella requirement for replacing .prawduct/backlog.md (git-file backlog, LLM-mediated
  mutation) with a centralized backlog/issue service that is fast, non-blocking,
  concurrency-safe, and cross-project. Motivating pain (all observed): slow LLM-in-the-loop
  CRUD, non-atomic writes (BKL-7M4Q), merge conflicts from parallel humans+agents, git-coupled
  edits, drop-box upstream reporting. Requirements doc:
  documentation/backlog-service-requirements.md (draft v2 2026-07-13, evidence-sharpened;
  prior-art research complete — recommendation: adopt GitHub Issues as system of record + build
  a thin deterministic adapter in the plugin; awaiting owner review). stage:
  requirements — design starts after owner vets the doc's pushback and open questions. Related:
  BKL-7M4Q (crash-safe mutation — superseded by CC1 if this ships), BKL-8T3W (shipped-drift
  surfacing — becomes GV3 reconciliation), BKL-3R8P (dedup — becomes Q3/AU3), XP flow replaces
  skills/report-bug drop-box. (user)

  Promoted 2026-07-18 (cumulative-Critic sustainability note — stage/status were stale at requirements/open): the requirements doc was owner-vetted, design signed off, and the work is in active build under artifacts/build-plan-backlog-service.md, with the Chunk 06 slice at the PR boundary. Advanced status open→promoted, stage requirements→ready to reflect the in-build state; the "awaiting owner review" narrative above is historical. Live-migration remainder tracked by BKL-6M4T; closes when the backlog-service slice ships.

- **[BKL-4W7H]** id:PFX alias not self-healing — PFX read-resolution unwired + alias-drift breaks import idempotency (CC5)
  `effort: M · impact: L · area: backlog-service · source: user · added: 2026-07-17 · status: promoted · stage: design · related: BKL-5R2K, BKL-6M4T, BKL-0QR1 · reviewed: 2026-07-17`

  Pre-sign-off CC5 trace, verified in code. Three compounding gaps around the id:PFX alias (load-bearing for MG1 "existing IDs stay valid forever"):
  (1) No read path resolves a PFX ref. is_pfx/alias_label/resolve_redirect/_find_by_key are wired NOWHERE in lib/backlog/{core,query,encode,cli}.py (grep: only a docstring mention). So post-migration `get BKL-0QR1` fails. Severity note (corrects an over-statement): it fails LOUD, not silent — normalize_id's repo-number form requires an all-digit suffix, and ZERO real prawduct IDs have numeric suffixes (all alphanumeric like BKL-0QR1), so it returns "unrecognized ID spelling", never silently resolves to a wrong issue. Still a gap: MG1's ID-validity promise is not met by the adapter read path.
  (2) reconcile-labels cannot restore a human-deleted per-issue alias. provision.reconcile is repo-taxonomy-only (ensures stage:*/status:* base label DEFINITIONS exist; never touches per-issue labels; never reads block id_aliases). Verified provision.py:139-157, base_labels 85-94.
  (3) Import idempotency has a single point of failure: the on-issue id:PFX label is the SOLE skip authority ("never the block", migrate.py:442-444); block id_aliases is written but never a fallback. Delete the label + re-run import → _find_by_key returns [] → duplicate issue; GitHub never reuses numbers → permanent duplicate. Requires the compound re-import-recovery scenario (medium likelihood, high/irreversible impact).
  Fix: wire PFX resolution into get/pick/link (label search + is_pfx short-circuit); make block id_aliases a fallback skip-authority in _find_by_key AND/OR have reconcile re-derive a missing id:PFX from the block; add a test that deletes an id:PFX label then re-imports and asserts no duplicate. Pre-migration must-fix (MG1 critical path).
  Also (lower-priority CC5 decoder gaps found in the same trace, capture so not lost): ENC-6 close-as-duplicate redirect is read only from the block, never the timeline (encode.py:405 "not yet implemented"; decode_item never calls list_timeline) → a human "close as duplicate" silently drops superseded_by (compounds with BKL-5R2K); a deleted soft-facet label (e.g. impact:high) decodes to None with NO warning; ENC-5(c) missing-stage advisory is unimplemented; a wholesale body-block deletion yields an empty Block with no warning (silently loses id_aliases/superseded_by/claimed_at). [Spun off into BKL-9J3F.]

  Promoted 2026-07-17: Offline code + tests landed 2026-07-17 (commit 8ecd02e, cumulative-Critic 0 blocking). core.resolve_ref wires PFX→canonical alias resolution into get/link; migrate._find_by_key gains a block-id_aliases fallback skip-authority (_AliasIndex) that self-heals a human-deleted id:PFX label so a re-import can't duplicate; reconcile-labels re-derives deleted aliases. In-flight under the Chunk 06 slice (BKL-6M4T) — closes when the slice merges. Follow-ups spun off: BKL-7Q2N (mutator-side PFX resolution), BKL-9J3F (CC5 decoder gaps).

## Archive

- **[SCN-4H9T]** Session handoff destroys model-authored context and mislabels active work — `/clear` overwrites `.session-handoff.md`, and the parser has no done-predicate, no `views_enabled` awareness, and truncates Context
  `effort: M · impact: L · area: session-continuity · kind: bug · source: user · added: 2026-07-26 · status: shipped · stage: ready · reviewed: 2026-07-27 · closed-by: session-handoff-continuity · related: CRT-7P5J, SCN-7K4B, BRF-6K2D, BLD-7K3Q, CRT-7B4M · refs: .prawduct/artifacts/build-plan-session-handoff-continuity.md (the governing plan — settles the ownership question that held this at `stage: design`), plugin/lib/briefing.py:921 (`generate_session_handoff`), plugin/lib/briefing.py:993-999 (the unconditional `atomic_write_text` behind the `len(sections) > 2` guard), plugin/lib/briefing.py:355 (`_get_active_work`), plugin/lib/briefing.py:87 (`staleness_scan` — where the done-predicate DOES exist), plugin/lib/briefing.py:227 (`_parse_wip`), plugin/lib/buildplan_refs.py:144 (`_parse_build_plan_status`), plugin/lib/buildplan_refs.py:188 (`current_chunk` = first `- [ ]`), plugin/methodology/building.md:120 (the sole sentence documenting machine ownership), plugin/methodology/reflection.md:63 ("Complete handoff"), .prawduct/learnings-detail.md:852 ("Session-end signals must come AFTER handoff")`

  **Upstream of discodon STH-9FYI** (filed 2026-07-25, never triaged here). Five confirmed defects in one function, verified by running the parser against the prawduct repo's own live plan.

  **(1) `/clear` UNCONDITIONALLY OVERWRITES a model-authored handoff.** `generate_session_handoff` ends in a bare `atomic_write_text` of `.session-handoff.md` — no read, no merge. The only guard is `if len(sections) > 2`, so a model-written handoff survives ONLY when the machine has nothing to say: preserved when it matters least, clobbered in every session with real work. Intermittent, therefore unlearnable.

  **(2) NO FORWARD CHANNEL EXISTS.** All five sources (active-work, `.session-reflected`, critic findings, changed files, commits) are backward-looking machine state. `.session-reflected` is doctrinally backward (what happened, root cause). Meanwhile `methodology/reflection.md:63` tells the model to "Complete handoff", which reads as an action on the file, while the sole sentence documenting machine ownership is `methodology/building.md:120`. The framework instructs the model to do a thing then silently overwrites it. Learnings already carry the rule ("Session-end signals must come AFTER handoff", `learnings-detail.md:852`) with no mechanism to satisfy it.

  **(3) NO DONE-PREDICATE.** `staleness_scan` (`briefing.py:87`, the done-conclusion at ~`:150-157`) correctly concludes "all chunks complete — delete the plan"; `_get_active_work` (`briefing.py:355`, ~`:354-359`) reads the IDENTICAL parse and applies no predicate, so a finished plan is stamped **Task** for the next session.

  **(4) `views_enabled` REPOS ARE SYSTEMATICALLY WRONG** (not in the discodon report). `current_chunk` = first `- [ ]` (`buildplan_refs.py:188`). Where Status is a derived view that only flips at release, this reports the FIRST chunk as current forever. Verified live: prawduct's own plan returned "Chunk 01" with three chunks complete and committed.

  **(5) WIP SECTION SILENTLY VANISHES + CONTEXT TRUNCATED** (not in the discodon report). `description` requires a `# Build Plan` H1; a frontmatter-style plan has none, so `_get_active_work` falls through to `_parse_wip`, returns empty, and the handoff OMITS the work section entirely (verified: returned `{}` on a live 4-chunk plan; briefing reads "Work: none active"). Separately, `context` = `removeprefix` on ONE physical line, so the multi-paragraph Context block — which `building.md` calls "the cross-session handoff" — is truncated at the first newline, and the loop has no `break` so multiple Context lines silently last-wins.

  **Severity: continuity is destroyed silently while the model reports success.**

  **Shipped 2026-07-27 by `session-handoff-continuity` — all five legs closed, across three chunks.**
  - legs **(1)** unconditional overwrite and **(2)** no forward channel — the mechanism half — shipped in **Chunk 01** (commit `5e5b178`): `.prawduct/.handoff-notes.md` is the model-owned forward channel, the generator emits it first behind a machine marker, and an unmarked (hand-authored) handoff is folded in rather than overwritten;
  - legs **(3)** no done-predicate, **(4)** `views_enabled` current-chunk, and **(5)** vanishing work section + truncated Context shipped in **Chunk 02** (commit `d43f1b1`) — leg (4) closed by the shared `_git_aware_progress` sweep, not a local patch (see the BLD-7K3Q overlap note below);
  - the remaining half of leg (2) — the **affordance** work this item deliberately stayed open for — shipped in **Chunk 03** (commit `c85bf79`): `building.md`'s chunk-close write-the-notes step and its two-files-two-owners paragraph, the `reflection.md:63` "Complete handoff" disambiguation, both digests naming the channel, plus two runtime pieces (an *advisory* false-success note when a session did work and left no forward note, and `handoff preview`, which renders what the next session would receive without writing or consuming). Nothing added here can block `/clear`.

  Held open through Chunk 03 on purpose: the bug report's own diagnosis was that the *affordance*, not just the mechanism, is what caused agents to write the wrong file, so closing on the mechanism alone would have closed this item on half of its own analysis.

  **Note the channel shape shipped as an assumption, not an owner ruling.** The plan recorded "a NEW model-owned file consumed into the generated handoff" as a HIGH-impact vetoable assumption, and its "what would raise confidence" was exactly that ruling. It was never overridden and the work built on it — worth knowing if the two-file design is ever revisited.

  Chunks 04 (**CRT-7P5J**) and 05 (**SCN-7K4B**) of the same plan belong to those items, not to this one.

  **The `refs:` line above is pre-fix** — it records the code sites as found and is deliberately left intact as the defect record. It no longer points at the cited code: `plugin/lib/briefing.py:921`, `:993-999` and `:355`, and `plugin/lib/buildplan_refs.py:144` and `:188`, have all moved or been rewritten by Chunks 01–02 (`_git_aware_progress` now lives in `plugin/lib/buildplan_refs.py:200`, applied from `:322`).

  **Stage history.** *Filed* `stage: design`, not `ready`, because the five legs were not uniformly buildable: legs **(3)**, **(4)** and **(5)** are mechanical fixes with obvious shapes (apply `staleness_scan`'s existing done-predicate in `_get_active_work`; adopt the git-derived current-chunk path; relax the H1 requirement and make Context multi-line), while legs **(1)** and **(2)** shared one unsettled design question — **who owns `.session-handoff.md`, and by what contract does model-authored forward-looking content survive a machine regeneration?** The filing note asked that a build plan either settle that contract first or split (3)/(4)/(5) out as a separate mechanical chunk.

  **Advanced to `stage: ready` 2026-07-26.** `.prawduct/artifacts/build-plan-session-handoff-continuity.md` does both: it answers the ownership question (a **new model-owned notes file** consumed into the generated handoff, so the generator keeps sole ownership of `.session-handoff.md` and the two-owners-one-file bug is designed out) in Chunk 01, and it splits the mechanical legs into Chunk 02. That made it buildable; the one caveat carried into the build — the channel shape being a vetoable assumption rather than an owner ruling — is recorded above, and it was never ruled on.

  **Overlap notes (filed as distinct; cross-linked, not merged).**
  - **BLD-7K3Q** and **CRT-7B4M** were the *same root cause* as leg (4) — `buildplan_refs._parse_build_plan_status` treating the first unchecked box as current on a `views_enabled` branch — at two other consumers (`verify-chunk-refs` and `infer-critic-mode`). **Resolved as prescribed:** BLD-7K3Q is archived `status: shipped · closed-by: session-handoff-continuity`, fixed as the shared sweep it called for (`_git_aware_progress` moved into `buildplan_refs` and applied from `_parse_build_plan_status`), and **leg (4) closed by that same fix** rather than by a third local patch. No sweep remains outstanding here.
  - **BRF-6K2D** is the adjacent half of leg (3): it makes `staleness_scan`'s delete-nudge merge-aware. This item points the other way — `_get_active_work` doesn't apply the predicate `staleness_scan` already has. Both touch the same two functions and are cheaper done together.
  - **CRT-7P5J** is a third correctness defect in the *same* `generate_session_handoff` output (it reads the derived critic-findings view instead of composing over resolution facts). Not a duplicate — different source, different fix — but it is the fourth known way this one function emits wrong context, which is itself an argument for treating the handoff generator as one body of work.
  - **SCN-7K4B** is the granularity axis of the same machinery (chunk-granular continuity has no home for multi-plan programs). Complementary, not overlapping.

  Governance-protected (`plugin/lib/`, session-continuity machinery) → full Critic + PR review. (user — verified against the live repo)

- **[BRF-6K2D]** Session-briefing "delete the plan" nudge isn't merge-aware — fires on develop while the plan's feature branch is unmerged
  `effort: S · impact: M · area: briefing · source: reflection · added: 2026-07-09 · reviewed: 2026-07-26 · status: shipped · stage: ready · closed-by: session-handoff-continuity · related: STH-3K7M, STH-3R8K, DOC-5T8N, WT-7M4K, COV-7K4N · refs: lib/briefing.py (staleness_scan, _get_other_branch_wip, _get_current_branch), lib/coverage.py (_resolve_base_branch), skills/pr/SKILL.md:142 (the live workaround)`

  The session-briefing / stale-plan nudge recommends deleting build-plan.md when all its chunks are checked complete. But build-plan.md is gitignored/session-local and persists across branch switches, so the nudge can fire while the session is on `develop` even though the plan's feature branch is still unmerged with no PR open. Following it would orphan live, unshipped work. Reported by discodon (2026-06-11, pre-2.3.0). Fix-shape: make the staleness check branch/merge-aware — before recommending deletion, confirm the plan's feature-branch commits are actually reachable from the integration branch (or its PR merged), e.g. `git merge-base --is-ancestor <plan-branch-tip> <base>`; otherwise say "plan complete but branch not yet merged — keep until merged" rather than "delete". Source: discodon reflection sweep 2026-07-09.

  **Salvage annotation (2026-07-19) — VERDICT: STILL-PRESENT; the branch fix still applies
  near-mechanically.** Captured before the stale branch `feature/gate-friction-batch` was deleted;
  its work is preserved at tag `archive/gate-friction-batch` (restore with
  `git branch feature/gate-friction-batch archive/gate-friction-batch`), relevant commit `d7a632f`.
  `lib/briefing.py:146-170` is the stale-plan scan; both nudges fire unconditionally on plan state
  alone — `:154-159` ("has all chunks complete — if work is done, delete the plan") and `:160-168`
  (the no-Status fallback). Nothing between `:151` and `:168` consults branch, base, or merge
  state. `git grep "delete the plan"` hits only `lib/briefing.py:158` and `:167`. No
  `_plan_work_possibly_unmerged` or equivalent exists; `lib/briefing.py:40` imports only
  `buildplan_refs, gates, gitstate` — `coverage` (which owns `_resolve_base_branch`) is not
  imported. The defect is currently documented as a LIVE WORKAROUND rather than fixed:
  `skills/pr/SKILL.md:142` — "A non-blocking 'consider deleting idle plan' advisory may surface …
  ignore it until the release ships." Treated as unshipped as recently as 2026-07-19
  (`.prawduct/change-log.md:167-168`).

  *Salvageable fix-shape.* Add
  `lib/briefing.py::_plan_work_possibly_unmerged(project_dir, prawduct_dir) -> (bool, reason)` with
  two independent sufficient signals: (1) foreign-branch WIP — `_get_other_branch_wip` non-empty (a
  session-local plan surviving a switch onto the base branch, the exact repro); (2) feature branch
  ahead of base — resolve base via `coverage._resolve_base_branch`, and if `current_branch != base`
  run `git merge-base --is-ancestor HEAD <base>`, where rc 1 means unmerged. Fail toward
  `(False, "")` on every uncertainty, so the change only ADDS a keep-recommendation on positive
  evidence and never silently suppresses a legitimate delete nudge. In `staleness_scan`, branch
  both findings: when unmerged, emit "… has all chunks complete but <reason> — keep the plan until
  it merges (deleting now would orphan unshipped work)". All inside the existing best-effort
  try/except.

  *Still applies? Yes.* Every dependency survives with the same shape: `_get_other_branch_wip`
  (`lib/briefing.py:431`), `_get_current_branch` (`:219`), `_parse_wip` (used at `:163`),
  `coverage._resolve_base_branch` (`lib/coverage.py:56`), target try/except (`:150`, `:169`).
  Adding `coverage` to briefing's imports is safe — nothing under `lib/` imports `briefing`, so no
  cycle. Two carry-over caveats: (a) the branch's import line imported `backlog`, which develop has
  restructured to `from .backlog import legacy as backlog` (`:41`) — **don't clobber it**;
  (b) `_resolve_base_branch` prefers `origin/<b>` and can be stale (see COV-7K4N) — for this nudge
  the stale case errs toward "keep", the safe direction, but leave a comment saying so.

  *Test pointers (on the archive tag).* New `tests/test_briefing_merge_aware_plan.py` (105 lines,
  real git fixtures) — `test_on_base_branch_merged_says_delete`,
  `test_feature_branch_unmerged_says_keep`, `test_foreign_branch_wip_says_keep`. Develop's `tests/`
  has only `test_briefing_extraction.py` and `test_briefing_functions.py`.

  **Shipped 2026-07-26 by Chunk 02 of `session-handoff-continuity`** (commit `d43f1b1`) — landed
  with the done-predicate work exactly as the build plan prescribed
  (`.prawduct/artifacts/build-plan-session-handoff-continuity.md:255`, acceptance item 6), because
  it is the adjacent half of the same two functions. Delivered along the salvaged fix-shape above:
  `plugin/lib/briefing.py::_plan_work_possibly_unmerged` (`:57`) with the two independent
  sufficient signals — foreign-branch WIP via `_get_other_branch_wip`, and
  `git merge-base --is-ancestor HEAD <base>` with the base resolved through `_resolve_base_branch`
  — wired into both nudges in `staleness_scan` (`:221`, `:240`), inside the existing best-effort
  try/except. Both carry-over caveats were honored: the restructured `backlog` import was not
  clobbered, and the stale-`origin/<base>` case (COV-7K4N) errs toward "keep" with a comment
  saying so. Signal 2 fails toward `(False, "")` on every uncertainty, so the change can only ADD
  a keep-recommendation and never silently suppress a legitimate delete nudge. Coverage landed as
  `TestDeleteNudgeIsMergeAware` (4 tests) in `tests/test_handoff_parser_correctness.py` rather
  than the salvage note's proposed `test_briefing_merge_aware_plan.py` — including
  `test_merged_branch_still_gets_the_delete_nudge`, which pins the direction the fix must not
  break. Change-log entry: `.prawduct/change-log.md:45`.

  **One leg explicitly descoped, not silently dropped.** The `refs:` line lists
  `skills/pr/SKILL.md:142 (the live workaround)`, and that note still stands — correctly. It
  describes the *release-pending* window (work already merged to `develop`, awaiting the batched
  `develop→main` release), where `current_branch == base`, so `_plan_work_possibly_unmerged`
  returns `(False, "")` and the delete nudge still fires by design while `/prawduct:pr` says
  RETAIN the plan for `regen-views`. That is a **different trigger** from this item's
  unmerged-feature-branch repro and was never in its fix-shape. If the residual advisory noise in
  that window is worth removing, it needs its own item (the signal would be "plan's scope tag has
  a release-pending change-log entry"), not a reopen of this one.

- **[BLD-7K3Q]** `verify-chunk-refs` grades the WRONG chunk on a `views_enabled` branch — it reads the first *unchecked* Status item, but checkboxes only flip at release
  `effort: M · impact: M · area: build-plan · kind: bug · source: critic · added: 2026-07-19 · reviewed: 2026-07-26 · status: shipped · stage: ready · closed-by: session-handoff-continuity · related: BLD-8R3T, BLD-9H2M, VWS-2F9K, CRT-3T6V, SCN-4H9T, CRT-7B4M · refs: lib/buildplan_refs.py:188 (_parse_build_plan_status — "Current chunk = first unchecked item"), lib/buildplan_refs.py:606 (_current_chunk_id_from_status), lib/critic_mode.py:151-158 + :520 (_git_aware_progress — the git-derived path, CRT-7B4M), lib/views.py:1237 (is_views_enabled)`

  Surfaced by the Chunk 03 Critic review of `skills-cutover-awareness`. `verify-chunk-refs` resolves "which chunk is current" from the build-plan `## Status` checkboxes: `lib/buildplan_refs.py:188` takes the first `- [ ]` item, and `:606` `_current_chunk_id_from_status` extracts its id. On a `views_enabled` repo the Status checkboxes are a **derived view** that only flips at release, so on a feature branch *every* chunk stays unchecked and Chunk 01 remains "current" for the entire branch.

  Consequence: chunks 02..N are never ref-verified while the gate reports success. It fails **silently and green** — the worst shape for a gate whose whole job is catching drift.

  Observed live on this branch: `verify-chunk-refs` returned `ok: chunk 01` while `infer-critic-mode` correctly resolved Chunk 03.

  Fix-shape: `lib/critic_mode.py` already solved exactly this (CRT-7B4M) — `_git_aware_progress` (`:520`) derives `(complete, current_chunk_id)` from commits against the base when `views_enabled` is set, falling back to `buildplan_refs._current_chunk_id_from_status` otherwise (`:151-158`). Give `buildplan_refs` the same git-derived path so the two agree on "current chunk" by construction. Note the current import direction — `critic_mode` imports `buildplan_refs`, not the reverse — so the shared derivation needs a home that doesn't create a cycle (extract into `buildplan_refs` and have `critic_mode` call it, per the STH-2K8R canonical-homes note in `lib/critic_mode.py:62`). Sibling non-broadening drift lives in **VWS-2F9K**. Governance-protected (gate logic) → full Critic + PR review. (critic — skills-cutover-awareness)

  **Shipped 2026-07-26 by Chunk 02 of `session-handoff-continuity`** (commit `d43f1b1`), as the build plan prescribed — `.prawduct/artifacts/build-plan-session-handoff-continuity.md` names this item as closing with that chunk. Fixed as a **sweep, not a local patch**, exactly along the fix-shape above: `_git_aware_progress` moved out of `lib/critic_mode.py` into `plugin/lib/buildplan_refs.py` (now `:200`) beside the rest of the Status parsing, and `_parse_build_plan_status` applies it (`:322`), so `verify-chunk-refs`, mode inference, the session handoff and the stop-hook gate are correct by construction rather than each carrying their own derivation. Four functions now take `project_dir` instead of `prawduct_dir` — resolving "current" reads git, so the call sites say so. The same root cause at the handoff consumer was leg (4) of **SCN-4H9T**; **CRT-7B4M** was the first, single-consumer fix this sweep generalised. Regression coverage for the failing case (all boxes `[ ]`, chunks committed) is in `tests/test_build_plan_resolution.py`. Note the `refs:` line above records the *pre-fix* code sites as filed — the live homes are `plugin/lib/buildplan_refs.py`.

- **[DOC-2R7M]** Post-relayout stale references in durable PLANNING artifacts — the release plan names `lib/backlog/**` at the pre-relayout path and points v3.2.0 at the wrong branch; the repoint build plan instructs `python3 bin/prawduct-hook`, which no longer exists
  `effort: S · impact: M · area: docs · kind: bug · source: critic · added: 2026-07-21 · reviewed: 2026-07-23 · status: shipped · stage: ready · closed-by: feature/backlog-service-relayout · related: DOC-7K4V, DOC-2W9P, BKL-3W6K, BKL-6M4T, BLD-6P8T · refs: .prawduct/artifacts/release-plan-backlog-service-golive.md (lines 26, 38, 84, 117, 187 — the five `lib/backlog/**` mentions; lines 22–39 — the branch guidance), .prawduct/artifacts/build-plan-backlog-skill-repoint.md (lines 46, 86, 118, 136 — `python3 bin/prawduct-hook backlog …`), plugin/bin/prawduct-hook (the post-relocation path)`

  Filed by the verify-resolutions pass `rev-20260721T165755Z-c3371605` — finding **R-20**'s durable-prose half.

  **This is the durable-artifact remainder of the same relayout sweep that fixed the five shipped skills in commit `f62cae1`.** The *shipped* surface is clean; this is the *planning* surface, which the sweep did not reach.

  **Two concrete defects, both verified against the tree (2026-07-21):**

  1. `.prawduct/artifacts/release-plan-backlog-service-golive.md` names `lib/backlog/**` **five times** at the pre-relayout path (`:26`, `:38`, `:84`, `:117`, `:187`) — after the relocation the tree carries `plugin/lib/backlog/`. It also points v3.2.0 work at the wrong branch: its "First: the code is not on `develop` any more" section (`:22–39`) instructs resuming on top of `feature/backlog-service`, but the work is now on **`feature/backlog-service-relayout`**, heading for `develop`.
  2. `.prawduct/artifacts/build-plan-backlog-skill-repoint.md` still instructs `python3 bin/prawduct-hook backlog …` (`:46`, `:86`, `:118`, `:136`). After the relocation that path is `plugin/bin/prawduct-hook`; `bin/prawduct-hook` does not exist, so **the command cannot run as written** — a reader following the verification steps gets a `No such file or directory`, not a hint.

  **Why this is a bug and not mere aging.** Both are durable artifacts a future session reads as *current instruction* — the release plan is what a v3.2.0 resumption navigates by, and the build plan's steps are meant to be executed. Stale paths here mislead an agent into the wrong branch or a failing command, rather than simply reading as history. Compare **DOC-2W9P** (shipped): the same class of stale-path defect in `documentation/` design specs, which was correctly treated as low-impact *because* those are an internal design archive. These two are not.

  Fix shape: repoint the five `lib/backlog/**` mentions to `plugin/lib/backlog/**`, correct the branch guidance to `feature/backlog-service-relayout` → `develop`, and repoint the four `bin/prawduct-hook` invocations to `plugin/bin/prawduct-hook`. Check for other post-relayout stragglers in `.prawduct/artifacts/` while in there — the shipped-skill sweep and this one together suggest the relocation had no artifact-surface pass at all. (critic — verify-resolutions R-20)

- **[GOV-4H7T]** Plugin ships `source: ./` with no packaging boundary — every repo-local file reaches consumer caches
  `effort: L · impact: L · area: governance/plugin-runtime · kind: feature · source: user · added: 2026-07-21 · reviewed: 2026-07-21 · status: shipped · stage: ready · closed-by: plugin-packaging-boundary · related: GOV-6J3P, REL-5W2J · refs: .claude-plugin/marketplace.json:13 (`"source"` — was `"./"`, now `"./plugin"`), plugin/, documentation/, tests/test_plugin_packaging.py, docs/release-process.md, docs/principles.md (Principle 10 — Clean Deployment)`

  `.claude-plugin/marketplace.json` declares `"source": "./"`, so whatever is in the repo tree lands in every consumer's plugin cache. During v3.1.1 construction, two `.claude/workflows/*.js` research scripts had to be held out of the release by hand under Principle 10 (dev tooling never reaches production). Hand-holding does not scale and does not survive the next contributor — there is no ignore/packaging boundary, so repo-local files are shipped-by-default and the only defence is someone noticing during a release. Wanted: a declared package manifest or ignore list so dev scaffolding stops shipping. (user — v3.1.1 release fold-in)

  **Requirement stated by the owner 2026-07-21:** "we explicitly do not want product's internal requirements and documentation landing in the plugin cache — it's not secret but it would be confusing to models working on consuming projects." This is the governing requirement, not just a tidiness preference: the harm is *model confusion in consuming products*, which makes it a correctness concern for every downstream session, not a hygiene nice-to-have. (Impact raised M→L on this basis.)

  **Mechanism settled 2026-07-21 (verified against official Claude Code plugin docs + marketplace schema — do not re-derive).** There is NO exclusion mechanism: no `exclude`/`files` field in `plugin.json` or `marketplace.json`, no `.claudeignore`, no npm-style ignore semantics. Installing a marketplace plugin copies the **entire source directory** to `~/.claude/plugins/cache` unfiltered. `.gitignore` cannot solve this — it controls what git tracks, and `source: "./"` collapses "tracked" and "distributed" into one question.

  **The supported fix is the `git-subdir` source type**, which sparse-clones only a named subdirectory: `"source": {"source": "git-subdir", "url": "https://github.com/brookstalley/prawduct.git", "path": "<dist>"}`. That requires the plugin root (`.claude-plugin/`, `skills/`, `hooks/`, `lib/`, `bin/`, `methodology/`, `templates/`, `docs/`, `agents/`) to live at that subdirectory, with `.prawduct/`, `tests/`, and `documentation/` outside it. Symlinks *within* a marketplace are dereferenced and their target content copied, so a hybrid layout is possible. Alternatives: a CI build step publishing a curated tarball/branch, or a separate distribution repo.

  **Scale of what ships today** (measured at v3.1.1, ~6.7 MB total): `.prawduct/` 3.0 MB (backlog 580K, change-log 520K, learnings-detail 180K, every build plan and release plan), `tests/` 1.5 MB, `documentation/` 408 KB — roughly 4.9 MB of internal-only material, none of it gitignorable. Pre-existing since v2.0.0 plugin distribution; v3.1.1 did not worsen it (raw research transcripts were moved under the ignored `research/**/raw/` and `.claude/workflows/` was ignored).

  **Design decision needed before build:** curated-subtree-in-repo (`git-subdir`) vs CI-built artifact vs separate dist repo. Each changes the release runbook, `${CLAUDE_PLUGIN_ROOT}` resolution, and the develop→main promotion mechanics, so this is a design item, not a mechanical fix. Deliberately NOT blocking v3.1.1 — the condition is unchanged in kind from what consumers already have.

  **Stage/effort corrected 2026-07-21:** `stage: ready` → `stage: design` (the three-way layout choice above is an unrecorded decision; `ready` would route this straight into implementation with the design question open — Principle 6). `effort: M` → `L` on the same evidence: relocating the plugin root touches the release runbook, `${CLAUDE_PLUGIN_ROOT}` resolution, and the develop→main promotion mechanics. Next step is `/prawduct:methodology planning`, not a build.

  **Shipped in v3.1.1 (plugin-packaging-boundary).** The plugin root moved to a real `plugin/` directory and `marketplace.json` `source` is now `"./plugin"`. `docs/` was curated by audience, moving nine internal files to `documentation/`. Verified by a real install from a fresh clone into an isolated `CLAUDE_CONFIG_DIR`: **109 tracked files / 1.7 MB**, down from 203 / ~6.7 MB, with `.prawduct/`, `tests/`, `documentation/`, `CLAUDE.md`, `pyproject.toml` and `.claude/` all absent, and the installed plugin executing correctly. Pinned by `tests/test_plugin_packaging.py`, mutation-tested against three regressions including symlink reintroduction.

  **Not symlinks — and this is the load-bearing finding.** A symlink farm was built and verified working on macOS, then verified **BROKEN** under `core.symlinks=false`, where every entry clones as a few-byte text stub and the plugin installs inert. The files were moved for real instead. (Note this supersedes the "symlinks are dereferenced, so a hybrid layout is possible" claim recorded in the mechanism paragraph above — true for marketplace copying, false for the clone that precedes it.)

  **Note for the record — the design question was settled by testing, not deliberation.** This item was routed to `stage: design` for a three-way choice (curated-subtree via `git-subdir` vs CI-built artifact vs separate dist repo). `git-subdir` was researched as *the* supported mechanism, but a plain relative path to a curated subdirectory turned out to be sufficient and simpler; the symlink-vs-move question was likewise settled by a `core.symlinks=false` clone rather than by argument. Cheapest-check-that-could-change-the-decision (Principle 24) beat the deliberation it was staged for.

- **[MET-7B3X]** Runbook authoring capability — guide, template, and `/prawduct:runbook` skill
  `effort: L · impact: L · area: methodology · kind: feature · source: user · added: 2026-07-20 · reviewed: 2026-07-20 · status: shipped · stage: ready · closed-by: runbook-authoring · refs: docs/runbook-authoring.md, templates/runbook.md, skills/runbook/SKILL.md, skills/methodology/SKILL.md (registration), templates/operational-spec.md, templates/observability-strategy.md, templates/unattended-operation/failure-recovery-spec.md, .prawduct/research/runbook-authoring/CHECKPOINT.md`

  This is the **retroactive parent requirement** for work delivered 2026-07-20 (Principle 6 — never silently *invent* a requirement). The gap was detected and named during the work, in `.prawduct/research/runbook-authoring/CHECKPOINT.md` synthesis decision 5, and is filed here at close-out rather than left implicit.

  **The gap.** Three prawduct artifacts point users at runbooks — `templates/operational-spec.md` ("High-risk: runbooks, escalation procedures"), `templates/observability-strategy.md` (its "What You Get" scenarios are effectively runbook triggers), and `templates/unattended-operation/failure-recovery-spec.md` ("## Recovery Procedures") — but **nothing in the framework said how to write one.** Owner reported that prawduct users frequently need runbooks and that generated quality was "between bad and abysmal."

  **Delivered.** `docs/runbook-authoring.md` (canonical rules + evidence appendix); `templates/runbook.md` (the blank, cross-linked section-by-section into the rules); `skills/runbook/SKILL.md` (`/prawduct:runbook` — survey, new, review, list); and registration from the methodology skill and the three templates above.

  **Note for the record.** Research provenance and resume instructions live in `.prawduct/research/runbook-authoring/CHECKPOINT.md`. Four gap searches — regulated environments, machine-vs-human audiences, irreversible-ops beyond what was recovered, and empirical evidence for runbook field sets — died on a session limit and **remain open**; the guide marks those areas honestly rather than filling them with convention. Worth a follow-on item if anyone wants them closed. (user)

- **[BRF-7Q4M]** SessionStart banner has no provenance marker — an operator can't tell whether the local `--plugin-dir` checkout or the marketplace copy is loaded
  `effort: S · impact: M · area: governance/plugin-runtime · kind: feature · source: user · added: 2026-07-19 · reviewed: 2026-07-19 · status: shipped · stage: ready · closed-by: banner-load-provenance · refs: hooks/banner.py (identity line), tests/test_plugin_version_banner.py`

  **PROBLEM** (observed 2026-07-19, live): the banner prints only `═══ Prawduct v3.1.0 (plugin) ═══`. `develop` and `main` BOTH read 3.1.0 — VERSION/plugin.json only bump at release-prep, and develop carries ~380 unreleased commits under the last released label — so the version string cannot discriminate. An operator testing unreleased work in a sibling repo via `claude <target> --plugin-dir ../prawduct` has no way to tell whether the local develop checkout loaded or the marketplace copy of main did. Sharpened by a real precedence hazard: a target repo that commits `enabledPlugins: {"prawduct@prawduct": true}` (what `init-product` scaffolds) force-enables the marketplace plugin, and per Claude Code's documented precedence `--plugin-dir` cannot override a settings-managed force-enable — so the dev load may silently lose with no visible signal.

  **SUCCESS**: the identity banner carries provenance when, and only when, the plugin is loaded from a local checkout — e.g. `═══ Prawduct v3.1.0 (plugin · develop@24e4210) ═══`, with a dirty marker when the checkout has uncommitted tracked changes. Managed/marketplace installs keep the current banner byte-for-byte. The presence of the provenance segment is itself the discriminator: if you see it, `--plugin-dir` won.

  **DESIGN CONSTRAINT discovered by measurement (do not skip this)**: the git calls cost ~66ms (rev-parse) + ~77ms (dirty check) = ~143ms, and marketplace installs DO contain a `.git` dir (`~/.claude/plugins/marketplaces/prawduct/.git`, currently on main) — so naive git-detection would bill every real user ~143ms on the SessionStart hot path for a dev-only diagnostic. The free discriminator is a pure path comparison: a managed install lives under `~/.claude/plugins/` (honor `CLAUDE_CONFIG_DIR` when set); a `--plugin-dir` checkout does not. Gate all git work behind that check so managed installs pay zero.

  **Scope**: `hooks/banner.py` identity line + tests. **OUT of scope**: bumping VERSION/plugin.json (that is release-prep and would redden `test_version_mirrors_VERSION_file`, `test_version_is_semver`, `test_changelog_has_current_version_entry`), changing the release process, changing marketplace precedence behavior.

  Filed as the parent requirement for work being built immediately in this session; to be marked shipped on the branch that lands it. (user)

  **Shipped 2026-07-19 (banner-load-provenance).** All SUCCESS criteria implemented, tested (15 cases, real git fixtures) and verified live against both load shapes plus end-to-end from a sibling repo under `--plugin-dir`. Landed on develop across commit a96456c (feature) and the Critic-resolution follow-ups. Managed installs keep a byte-identical banner; the path gate keeps the git subprocess off the SessionStart hot path for ordinary users. Archived per the shipped→Archive convention.

- **[COV-7K4N]** check-cumulative-critic false-`uncovered` with a misleading remedy when origin/<base> is stale (feature built on unpushed local integration commits)
  `effort: S · impact: M · area: coverage · source: reflection · added: 2026-07-14 · reviewed: 2026-07-19 · status: shipped · stage: design · closed-by: stale-remote-base-diagnostics · related: COV-5H3N, ENV-2W7K, PR-2H8N, PR-7T2K, COV-9B4T · refs: lib/coverage.py (_resolve_base_branch prefers origin/<b> for a "stable remote-tracking merge-base"), lib/gates.py (check_cumulative_critic uncovered path), docs/release-process.md`

  When `base_branch: develop` is set, `_resolve_base_branch` resolves the base to `origin/develop` by design. If local develop is ahead of origin/develop (release-prep or a merge committed locally but not pushed) and a feature is built on top of that ahead-state, check-cumulative-critic anchors merge-base to the STALE origin/develop and demands one composed review path spanning the whole unshipped range — dragging already-reviewed, already-shipped work into the required span — so it reports `uncovered` even though every commit in the span has a clean Critic fact (blocking=0). The stderr remedy ("run /prawduct:critic cumulative") is then both WRONG and expensive (~4-10 min; it re-reviews the whole promotion delta for zero added signal). Observed live during the v3.0.3 release: origin/develop sat at v3.0.1 while local develop carried an unpushed, never-promoted release-prep(v3.0.2) — a "phantom release." The actual fix was `git push origin develop` to reconcile the base, after which the gate re-composed and passed (2 review facts + 1 free edge). Root cause upstream: a release-prep(vX) that stops before promotion+push leaves develop, the version files, and origin/develop out of sync across sessions.

  FIX-SHAPE (menu; recommend 1 near-term, 2 follow-up, 3 deferred spike):
  (1) Diagnostic hint on the uncovered path — if base is origin/<b>, local <b> exists, is an ancestor of HEAD, and is ahead of origin/<b>, append "origin/<b> is N commit(s) behind local <b>; try `git push origin <b>` and re-check before a full review." Cheap, text-only, converts the wrong remedy into the right one.
  (2) Root-cause session-start advisory (observable-state pattern, cf. the gitignore-drift probe): nudge when local develop is ahead of origin/develop with an unpromoted release-prep(vX). Self-resolves once develop is pushed/promoted.
  (3) [deferred spike] Reconsider base resolution to prefer the nearer of local/remote integration branch when local is ahead AND an ancestor of HEAD — would eliminate the false-uncovered but trades against the deliberate "stable remote-tracking merge-base" design and is load-bearing across every gate (PR, doc-only, cumulative). Governance-protected (lib/gates.py, lib/coverage.py) → full Critic + PR review.

  Dedup note (2026-07-14): distinct facet from COV-5H3N — that item is the *wrong-default-to-main* case when `base_branch:` is UNSET; this is the *stale-remote* case when `base_branch: develop` IS set and origin/develop trails local. Both live in `_resolve_base_branch`; keep separate, cross-linked. Adjacent to PR-7T2K (local-vs-origin divergence breaking a gate, but on the feature branch's push-state at merge, not the base branch) and umbrella'd by ENV-2W7K (gitflow base detection, Wave 2).

  **Shipped 2026-07-14 (stale-remote-base-diagnostics).** Fix-shapes #1 (uncovered-path diagnostic hint on the gate) and #2 (session-start unpromoted-release-prep advisory) both landed this session; fix-shape #3 (base-resolution reconsideration) was deferred and re-filed as COV-9B4T to keep the decision trackable. Archived per the shipped→Archive convention.

- **[DOC-8N4F]** Change-log template's `status=` vocabulary contradicts views.py flip semantics — scaffolded header misleads gitflow repos about when Status checkboxes flip
  `effort: S · impact: M · area: change-log/templates · source: report-bug · added: 2026-07-02 · reviewed: 2026-07-19 · status: shipped · stage: ready · closed-by: single-pr-bookkeeping · related: REL-4Q9V, DOC-5T8N, VWS-6R4T · refs: templates/change-log.md, lib/views.py (VALID_STATUS_VALUES, ChangeLogEntry.shipped_chunks, stamp_merged), incoming-bugs/archive/change-log-template-says-merged-flips-status-checkboxes-but-views-py-only-flips-shipped.md`

  Upstream bug report from scriob (arch-refactor build, prawduct v2.2.3). Reported symptom: their
  scaffolded change-log header claims "Both `merged` and `shipped` flip the build-plan `## Status`
  checkboxes", while `lib/views.py` deliberately flips only `status=shipped` — so in a gitflow repo
  where develop runs far ahead of main, every merged-but-unreleased chunk reads `- [ ]` and the
  surrounding guidance (commit messages, plan Context lines, a Critic WARN) told the builder the
  box should already be checked.

  Triage verification (2026-07-02, framework tree + 2.2.3 plugin cache): the CURRENT
  `templates/change-log.md` does NOT contain the quoted "Both merged and shipped" text — it says
  checkboxes flip from `status=shipped` (correct). The reporter's header is a product-side stale
  scaffold/hand-evolved variant. But the template has a REAL vocabulary bug of its own: it lists
  `status - shipped | in-progress | deferred` while `VALID_STATUS_VALUES` is `{shipped, merged}` —
  it omits the recognized intermediate `merged` entirely and documents two values that are invalid,
  which post-VWS-6R4T (changelog-fail-loud) now error loudly for any product following the
  template's own guidance. Same defect class as reported (template contradicts views.py semantics),
  different wrong text.

  Fix-shape: align `templates/change-log.md` line ~30 to the real vocabulary — document
  `shipped | merged` (statusless = feature-branch), state explicitly that only `shipped` flips a
  checkbox and `merged` is the release-pending intermediate that does NOT flip, per the views.py
  docstring. Interaction with REL-4Q9V: if the vocabulary shrink ships (drop `merged` +
  stamp-merged), the template update lands as part of that cascade instead — coordinate rather
  than double-fix. The report's usability suggestion (surface merged-pending in the Status view,
  e.g. a `(merged)` annotation, so plans can distinguish "not built" from "merged, awaiting
  release") is feature-shaped — route it into REL-4Q9V's design rather than this doc fix.
  Downstream note: scriob's own scaffolded header needs its product-side correction regardless
  (scaffolded files don't re-sync). (report-bug)

  **Salvaged already-shipped (2026-07-19).** Recovered from the unmerged branch
  `feature/gate-exemption-boundary` (cc285bb), where it was filed 2026-07-02 as `status: open` and
  never reached develop's backlog. Re-verified on develop before filing: the fix-shape above LANDED
  independently in `single-pr-bookkeeping` (de2d6bd, PR #118, released v2.3.2) —
  `templates/change-log.md` now documents `status - shipped | merged (legacy)`, states that a
  statusless tagged entry is the release-pending state, and that any other value is a fatal
  regen-views error; `VALID_STATUS_VALUES` in `lib/views.py:197` is `{shipped, merged}`, matching.
  The invalid `in-progress | deferred` vocabulary is gone. Filed directly to Archive rather than as
  an open item — salvaging it as open would have re-opened finished work. The item's two deferred
  hand-offs remain live elsewhere and are NOT closed by this: the vocabulary shrink is REL-4Q9V
  (still open), and the reporter's product-side scaffold correction is scriob's, not ours.

- **[BLD-4V7Q]** verify-chunk-refs flags a false missing-ref on a backticked code-location token carrying a `:line` / `:line-range` suffix (`path:line`)
  `effort: S · impact: S · area: critic · kind: bug · source: critic · added: 2026-07-18 · reviewed: 2026-07-19 · status: shipped · stage: ready · related: BLD-8F2Q, BLD-5J8N, BLD-3M7K, BLD-4K7P, BLD-6T4R, BLD-9H2M · refs: lib/buildplan_refs.py (_ref_path_part, _BUILD_PLAN_LINE_SUFFIX_RE, _parse_build_plan_chunk_refs), tests/test_build_plan_resolution.py · closed-by: verify-chunk-refs-token-fixes`

  **Shipped 2026-07-19 (verify-chunk-refs-token-fixes)** — fixed in `lib/buildplan_refs.py` alongside its sibling `BLD-6T4R`; both variants live in `_parse_build_plan_chunk_refs`'s token loop. A new helper `_ref_path_part` reduces a backticked ref token to the path that gets existence-checked, dropping BOTH suffix forms: `::symbol` (the pre-existing BLD-8F2Q carveout, now routed through the same helper) and `:line` / `:line-range` via `_BUILD_PLAN_LINE_SUFFIX_RE` (`:\d+(?::\d+)?(?:-\d+)?$`). Order is load-bearing and documented: the `::` split runs FIRST so a digit-tailed symbol (`lib/foo.py::rule42`) is discarded with the symbol half rather than mistaken for a line number. The stored `ref` is now the reduced path, so a genuine missing-ref message names the file rather than the citation. 12 regression tests added; suite 2408 passed / 6 skipped. Verified against the real plan corpus (every chunk of every `.prawduct/artifacts/*build-plan*.md` parsed under pre- and post-fix parsers), not fixtures alone.

  **Record correction (2026-07-19).** Two details above were wrong as first written and are fixed in
  place; both were verified against the tree and the ship commit `9865132`, not re-derived from memory.
  (a) The regex was quoted as `:\d+(?:-\d+)?$`, dropping the `(?::\d+)?` alternative — so the note
  understated the fix, which also covers the editor-style `path:line:col` form (`lib/foo.py:12:34`).
  The pattern shipped with that alternative from the start; only the note was short. (b) The counts
  read "11 regression tests added; suite 2407 passed / 6 skipped." The commit adds **12** test
  functions to `tests/test_build_plan_resolution.py` (7 for this item's suffix handling, 5 for its
  sibling `BLD-6T4R`'s exemption reach) and the suite stands at **2408 passed / 6 skipped** — which is
  what the 2026-07-19 change-log entry recorded and what `pytest` reports on `develop` today. This
  archive note was the outlier, not the change-log.

  **Disposition — three-level `path:line:col:extra` half-strip (2026-07-19, critic R-5 on
  `verify-chunk-refs-token-fixes`; NOTE severity, "backlog or ignore").** Considered and deliberately
  left; recorded here rather than filed, so the dismissal is visible instead of silent.
  `_BUILD_PLAN_LINE_SUFFIX_RE` is `$`-anchored and consumes at most two numeric groups, so a
  three-level token like `lib/foo.py:1:2:3` reduces to `lib/foo.py:1` — still a false missing-ref, and
  reported under a half-stripped name that reads like a real path (the same shape as the two-level case
  this item fixed, one level deeper). Left because: no instance exists anywhere in the
  `.prawduct/artifacts/*build-plan*.md` corpus, and no citation convention used in this repo (grep,
  editor `path:line:col`, `path:line-range`, `path::symbol`) produces three numeric levels — so it is a
  near-miss, not a live defect, and widening the regex would add surface without a demonstrated payer.
  If one ever appears, the cheapest close is substituting to a fixed point (loop the `re.sub`, or make
  the pattern `(?::\d+)+(?:-\d+)?$`) plus one case alongside `test_line_and_column_suffix_stripped`.
  Cross-referenced from BLD-8R3T, which carries the companion NOTE from the same review.

  `_parse_build_plan_chunk_refs` strips a `::symbol` suffix (the BLD-8F2Q carveout) but NOT a single `:line` / `:line-range` suffix, so a backticked code-location citation like `lib/critic_mode.py:452` or `lib/foo.py:5-8` is existence-checked literally as the whole `path:line` token and reported `missing-ref`. Same false-negative-habituation class BLD-5J8N just fixed at the chunk-HEADER layer, but here in the ref-TOKEN family (siblings: BLD-2R9X glob, BLD-8F2Q path::symbol, BLD-4K7P inline-code/URL, BLD-3M7K git-ref). Fix-shape: strip a trailing `:<digits>` or `:<digits>-<digits>` from a backticked path token before the existence check, mirroring the `::symbol` carveout, in `_parse_build_plan_chunk_refs` / `_looks_like_file_path`. Filed from /critic.

- **[BLD-6T4R]** `verify-chunk-refs` forward-ref (`new`) exclusion is line-local, not chunk-scoped — a file declared `new` on a chunk's Deliverables line flags as missing when re-referenced elsewhere in the same chunk
  `effort: S · impact: M · area: build-plan · source: critic · added: 2026-07-16 · reviewed: 2026-07-19 · status: shipped · stage: ready · related: BLD-8R3T, BLD-5N7C, BLD-3M7K, BLD-4K7P, BLD-5J8N, BLD-4V7Q, BLD-9H2M · refs: lib/buildplan_refs.py (_parse_build_plan_chunk_refs forward_refs set, _BUILD_PLAN_NEW_QUALIFIER_RE, _ref_path_part), tests/test_build_plan_resolution.py · closed-by: verify-chunk-refs-token-fixes`

  **Shipped 2026-07-19 (verify-chunk-refs-token-fixes)** — the offset-keyed per-line `excluded_spans` exclusion is gone. `_parse_build_plan_chunk_refs` now collects every `new \`path\`` qualifier across ALL lines of the chunk section into a per-path `forward_refs` set BEFORE the token loop, normalized through the same `_ref_path_part` helper as the tokens — so a `new` declaration on a Deliverables line also exempts a later `path:42` citation of that same path (the two fixes compose). The exemption stays per-path and per-chunk: one `new` declaration does not silence other missing refs in the section and does not leak into sibling chunks. Corpus verification (all `.prawduct/artifacts/*build-plan*.md`) showed five plans change. A THIRD variant found during that corpus check was filed rather than fixed: **BLD-9H2M** (soft-wrapped `new` qualifier undetected — the regex is per-line).

  **Correction (2026-07-19) — two dropped refs were TRUE positives, not false ones.** The sentence
  above originally read that two of the dropped refs "were live false positives on `new`-declared
  paths absent from disk — `lib/backlog.py` in `build-plan-backlog-rework` and
  `methodology/agent-stance.md` in `build-plan-rigor-and-stance`." That is backwards, and the same
  error was caught by the Critic in the change-log entry's first draft. Both paths sit in chunks
  marked `[x]` shipped and **neither file exists**, so `verify-chunk-refs` was reporting real drift;
  it surfaced them only incidentally, because those chunks happened to re-reference the path — the
  exact re-reference this item's fix suppresses. The fix is still correct for its own scope (a
  forward reference inside a chunk being BUILT must not flag), but it is unconditional with respect
  to chunk completion, so a shipped chunk's declared-new deliverable is now never existence-checked.
  That contract gap is filed as **BLD-8R3T**; the two stale plan paths as **BLD-5N7C**. Accepted
  knowingly at ship time — recorded in the 2026-07-19 change-log entry, not discovered later.

  **Urgency correction (2026-07-19).** The original filing's closing "Low urgency — verify-chunk-refs
  is not wired into any gate" (preserved verbatim below as filed) is **stale and wrong**, and it
  propagated into BLD-9H2M before being caught. `skills/critic/review-protocol.md:71` makes it a
  Critic goal with both `missing-ref:` and `cannot-verify:` exits **BLOCKING**, and
  `.prawduct/cross-cutting-concerns.md:36` records it as the Goal-2 build-plan-ref-drift gate. Not
  hook-enforced, but a BLOCKING Critic goal is a gate. Do not re-derive urgency from that line.

  A file declared with the `new` qualifier on a chunk's Deliverables line (`new \`path\``) is still
  flagged as a missing ref when the same path is re-referenced WITHOUT the prefix elsewhere in the
  same chunk section (e.g. a Done-when step). The exclusion keys on the token's start offset — only
  the exact `new \`path\`` occurrence is exempt — so it is line-local, not chunk-scoped. Observed
  2026-07-16 during the backlog-service plan review (Critic NOTE on
  `.prawduct/artifacts/build-plan-backlog-service.md` ~line 167: `api-notes-github-issues.md`
  declared `new` on Deliverables, re-referenced in a Done-when step). Distinct variant within the
  verify-chunk-refs false-positive family: BLD-3M7K is token CLASSIFICATION (git-ref/branch-like
  prose tokens misread as paths); this is the forward-ref exclusion's SCOPE. Fix direction: once a
  path is declared `new` anywhere in a chunk section, exempt all same-chunk re-references of that
  path. Low urgency — verify-chunk-refs is not wired into any gate. (critic)

  Variant log (2026-07-16, backlog-service final-mode Critic review): `verify-chunk-refs` exit 1
  on `.prawduct/artifacts/build-plan-backlog-service.md` line 144 — backticked ID-grammar prose
  tokens (`owner/repo#number`, `repo/number`) parsed as plan-referenced file paths and flagged
  missing. Strictly this is the token-CLASSIFICATION facet (BLD-3M7K's `_looks_like_file_path`
  over-match, same family as branch-like slash tokens), logged here as this session's
  verify-chunk-refs FP record. **This facet is NOT closed by this item's fix** — it remains open
  under BLD-3M7K. Same fix-the-classification rule applies: never demote the check
  to a warning — fix what it classifies as a path (ID-grammar tokens with `#`, and slash tokens
  that are format grammar rather than repo paths, should be excluded from the path heuristic).

  Re-verified 2026-07-19: still live as written. `lib/buildplan_refs.py:346-360` recomputes
  `excluded_spans` per LINE inside the section loop and exempts a token only via
  `any(start == match.start(1) for start, _ in excluded_spans)` — an exact start-offset match
  against spans from that same line. Nothing carries the `new` declaration across lines within
  the chunk. Salvaged from branch `worktree-backlog-service-plan` (worktree removed before merge).

- **[DOC-4K9M]** VRF-007's operator checklist asks the operator to verify a step the skill cannot do (`--if-updated-at` round-trip), contradicting its own pre-verification note
  `effort: S · impact: M · area: operator-verification · source: critic · added: 2026-07-19 · reviewed: 2026-07-19 · status: shipped · stage: ready · related: BKL-3W6K, BKL-6M4T · refs: .prawduct/operator-verification.md (VRF-007, Verify step 3 :245-247 vs Pre-verified note :225-230), skills/backlog/adapter-mode.md (update <id> section), .prawduct/artifacts/build-plan-backlog-skill-repoint.md · closed-by: worktree-salvage`

  **Shipped 2026-07-19 (worktree-salvage)** — fixed in place rather than deferred, owner-approved. `.prawduct/operator-verification.md` VRF-007 "Verify" step 3 was reworded to drop the unimplementable `--if-updated-at` round-trip and instead verify a **normal-path** field round-trip: a title/stage/area edit made via `update` is reflected by a following `get`/`list`. A parenthetical was added recording that the `--if-updated-at` guard is deliberately NOT exercised, because the `get` envelope exposes no `updated_at`. This was chosen over the alternative fix-shape ("keep the clause but annotate it") so the checklist contains no unreachable instructions and a future reader cannot silently re-add the step. The checklist and the "Pre-verified (adapter loop, 2026-07-19)" note now state the same thing.

  **Caveat — the reworded step is itself UNVERIFIED.** The rewording resolves the doc contradiction; it does not prove the normal-path round-trip actually works. That remains unproven until the Phase 1 sibling-session dogfood (**BKL-6M4T**) actually executes VRF-007. If the round-trip fails there, that is a product defect to raise fresh — not a regression of this item.

  Doc-coherence defect, re-raised twice by the Critic. Inherited from the merged backlog-skill-repoint work (BKL-3W6K) — **not** introduced by the branch on which it was found.

  The contradiction is internal to one document. `.prawduct/operator-verification.md` VRF-007 step 3 of the "Verify" checklist still read "a field change round-trips via `--if-updated-at`", but the **same** entry's "Pre-verified (adapter loop, 2026-07-19)" paragraph ~15 lines above records that this exact step was DROPPED as unimplementable: "the `get` envelope does not expose `updated_at`, so the update guidance dropped the unimplementable get-then-`--if-updated-at` step." `skills/backlog/adapter-mode.md` (the `update <id>` section) agrees — the `--if-updated-at` optimistic-concurrency guard "is only usable when a caller already holds that timestamp from elsewhere; the skill's normal path omits it." Consequence (now removed): an operator draining VRF-007 during Phase 1 (the sibling-repo dogfood) was blocked on a step that cannot be performed through the skill, with no in-document signal that the block was a doc bug rather than a product defect.

  Drains with, or before, VRF-007 itself (Phase 1 of the migration program, execution tracked by BKL-6M4T). (critic)

- **[BKL-3W6K]** /prawduct:backlog skill is markdown-only — repoint it onto the GitHub-Issues adapter when backlog_service_repo is set
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-19 · reviewed: 2026-07-19 · status: shipped · stage: ready · related: BKL-6M4T, BKL-8P2R, BKL-5D2C · refs: .prawduct/artifacts/build-plan-backlog-skill-repoint.md · closed-by: backlog-skill-repoint`

  GATING deliverable for the GH-Issues migration (owner-scoped 2026-07-19). The backlog-service program built the adapter (lib/backlog, Chunks 01-06) and the migration/import, and Chunk 06 repointed the BRIEFING + advisory probes onto backlog_service_repo — but the everyday /prawduct:backlog SKILL was never repointed. skills/backlog/SKILL.md has allowed-tools: Read, Edit, Write, Grep, Glob (NO Bash), so it structurally cannot call prawduct-hook backlog; every subcommand (summary/add/find/list/update/pick/dedup) reads/writes .prawduct/backlog.md in place. Only 'scrub' (the one-shot migration) drives the adapter. Consequence: after a cutover (backlog_service_repo set, markdown frozen), /prawduct:backlog pick/add/list/update would still operate on the FROZEN markdown, not the Issues that are now system-of-record. This is unplanned work — the roadmap waves (W1 cache/sync, W2 search/dedup, Wv verify, W3 cross-project) all WIDEN the adapter; none repoints the skill. Fix-shape: make the skill dual-mode — markdown when backlog_service_repo unset (unchanged for pre-cutover consumers), adapter-driven (prawduct-hook backlog <op> --repo <resolved> --json, parse envelope, branch on exit class) when set; add Bash (scoped to the adapter) to allowed-tools; map add->file, list->list, pick->pick, update->status/update, claims->claim/unclaim, dedup->merge. Open design fork: find/dedup need search, which is W2-unbuilt — post-cutover find degrades (documented). Gates Phase 1 (sibling dogfood) of the migration program. related: BKL-6M4T (prawduct self-cutover), BKL-8P2R (briefing/probe repoint that stopped short of the skill), BKL-5D2C (parent: Issues as system-of-record).

- **[CRT-6W2N]** Governance gates + Critic/PR skills have no supported git-worktree workflow — the learned "run Critic/PR from the primary session" workaround breaks across working copies, forcing every worktree work cycle off-protocol
  `effort: L · impact: M · area: worktree · source: user · added: 2026-06-22 · status: shipped · stage: requirements · related: STH-4K7N, CRT-8D2W, CRT-2K9F, REL-7P3X · refs: lib/gates.py, bin/prawduct-hook (infer-critic-mode, check-cumulative-critic, test-evidence), skills/critic, skills/pr, Stop hook, incoming-bugs/archive/governance-gates-and-critic-pr-skills-dont-compose-with-git-worktrees.md · reviewed: 2026-07-18 · closed-by: feature/worktree-compat (STH-4K7N Chunk 02, PR #107) + STH-3R8K + BRF-6K2D + PDT-WT9K (PR #132)`

  Host repos increasingly MANDATE worktrees for WIP (stable primary checkout served live as a --plugin-dir MCP source), but prawduct has no documented worktree story, so sessions abandon the formal machinery (review via an independent Agent, PR/merge via raw gh), silently skipping the cumulative-Critic record the framework otherwise requires. IMPORTANT reconciliation (verified 2026-06-22 in this framework repo): state-file resolution is NOT actually ambiguous — get_project_dir() deterministically uses the session's CLAUDE_PROJECT_DIR, so a session run ENTIRELY inside one worktree reads/writes that worktree's .prawduct/ consistently and the gates ARE satisfiable in place (empirically confirmed: check-cumulative-critic resolved the worktree's own .critic-findings.json; gitignored runtime files isolate per-worktree). The real gap is therefore (a) NO documented supported worktree workflow, so host repos invented the "run Critic/PR from the PRIMARY session against worktree WIP" rule — and THAT genuinely breaks because the primary's .prawduct/ is a different working copy than the worktree's; and (b) the harness EnterWorktree defaults new worktrees off origin/<default-branch>=main (wrong on gitflow — belongs upstream with the harness, noted not-a-prawduct-bug). Fix-shape (remediation menu): (1) document/own a supported worktree workflow in the methodology — drive the full cycle (code→critic→pr→reflection) from inside the worktree (this WORKS today); (2) worktree-capable critic/pr skills that detect the worktree and review merge-base(base)..HEAD writing the normal record; (3) at minimum, methodology guidance so repos stop reinventing the workaround as private memory. Distinct from CRT-8D2W (inverse: run the Critic in ITS OWN worktree for session-isolation) and CRT-2K9F (worktrees SIDESTEP the single-slot clobber). Adjacent to the gitflow base-resolution item (base resolution vs gate/skill composition). Governance-protected → full Critic + PR review.

  Dedup/reconcile 2026-06-22 (vs STH-4K7N, shipped v2.1.8 / scope=worktree-compat): the
  CODE-RESOLUTION leg this item leans on ("a session run entirely inside one worktree reads/writes
  that worktree's .prawduct/ consistently") is now HARDENED, not merely assumed — STH-4K7N shipped
  `lib.gitstate.resolve_project_dir` so `get_project_dir` follows the session into its worktree
  (`git rev-parse --show-toplevel` of cwd, preferred over the `CLAUDE_PROJECT_DIR` pin only when cwd
  is a same-repo worktree, failing open on git error). That closes the narrow `.prawduct/`-resolution
  defect (STH-4K7N's "Full fix approved"). It does NOT close THIS item: CRT-6W2N's remaining,
  genuinely-open want is the DOCUMENTATION/METHODOLOGY leg — a documented, supported worktree
  workflow (fix-shape 1 & 3) plus optional worktree-capable critic/pr skills (fix-shape 2) — so host
  repos stop reinventing the "run from the primary session" workaround as private memory. Kept OPEN
  at stage:requirements, scoped now to that doc/methodology + skill leg; `related: STH-4K7N` records
  the shipped code dependency it builds on. NOT archived (not a true duplicate — STH-4K7N was the
  code fix, this is the workflow/docs).

  Shipped 2026-07-18 (reconcile-as-shipped; closed-by: feature/worktree-compat (STH-4K7N Chunk 02, PR #107) + STH-3R8K + BRF-6K2D). All three of CRT-6W2N's own fix-shapes are delivered. Fix-shapes 1 & 3 (documented/owned worktree workflow in the methodology + guidance so repos stop reinventing the "review in primary, merge with raw gh" workaround) shipped as STH-4K7N Chunk 02 in PR #107 (commit 796719d, merged 2026-06-22): the "Working in a git worktree" subsection at methodology/building.md:15 plus the worktree notes in skills/critic/SKILL.md:32 and skills/pr/SKILL.md:15. Fix-shape 2 (worktree-capable critic/pr skills reviewing in place, merge-base(base)..HEAD, writing the normal record) is delivered by STH-4K7N Chunk 01's resolve_project_dir resolver plus the already-relative skills — empirically confirmed because the worktree-compat build plan itself ran /prawduct:critic cumulative over merge-base...HEAD FROM a worktree and unblocked /prawduct:pr create, and dogfooded again THIS session (a linked worktree on develop, common-dir shared with primary; last session STH-3R8K ran its full governed close-out — Critic final clean + commit 1637c4a — in place here). Reinforced by STH-3R8K (observable stop-path signal for the silent worktree redirect) and BRF-6K2D (SessionStart worktree-awareness, live in this session's briefing). ROOT CAUSE of the false-open: the 2026-06-22 reconciliation split PR #107 into "code shipped / docs open," missing that Chunk 02 of that same PR shipped the docs — the shipped-but-not-removed drift BKL-8T3W targets. VRF-001 (operator-verification.md) marked verified via this session's dogfood.

  **Attribution correction 2026-07-19 (salvage sweep N1) — archived entry, corrected not rewritten.** Every reference to **BRF-6K2D** above (in `closed-by:` and in "Reinforced by … BRF-6K2D (SessionStart worktree-awareness)") is a MIS-CREDIT. What actually landed is the briefing's worktree enumeration/orientation (`lib/briefing.py:379-428`, `:495-509`); BRF-6K2D is the merge-awareness of the "delete the plan" nudge (`lib/briefing.py:146-170`), whose surface is verified UNTOUCHED on develop. BRF-6K2D remains OPEN and did not contribute to closing CRT-6W2N. The historical text is left intact above; read it through this correction.

  Merge reconciliation 2026-07-19 (develop integration): the discodon-upstream-defects branch (PR #132, merged to origin/develop in parallel with this session) shipped PDT-WT9K as its Chunk 04 and, unaware of this reconciliation, left CRT-6W2N OPEN with a partial-progress note asserting "the broader [documented worktree] gap remains OPEN." That assertion is superseded here: PDT-WT9K (critic-begin now surfaces the resolved worktree/branch/base, lists sibling worktrees, and refuses when the shell's git repo differs from the resolved review tree — commits eb83a68/85c1654) is ADDITIONAL delivery of fix-shape 2 (worktree-capable critic skills), not evidence the docs leg is missing; the docs leg (fix-shapes 1 & 3) was already verified shipped in STH-4K7N Chunk 02 above. Net: CRT-6W2N stays archived-as-shipped, now closed-by also PDT-WT9K.

- **[STH-3R8K]** Surface a one-line signal when `get_project_dir` redirects `.prawduct/` resolution to a worktree toplevel
  `effort: S · impact: S · area: stop-hook · source: critic · added: 2026-06-20 · reviewed: 2026-07-18 · status: shipped · stage: ready · related: STH-4K7N · closed-by: stop-worktree-redirect-note · refs: bin/prawduct-hook, hooks/digest.py, hooks/banner.py`

  Surface a one-line signal when `get_project_dir` redirects `.prawduct/` resolution away from
  `CLAUDE_PROJECT_DIR` to a worktree toplevel. Today the worktree redirect (STH-4K7N) is silent: the
  load-bearing assumption that a hook process runs with the worktree as its cwd fails safe (toward
  more gating) but invisibly. A brief stderr/briefing note on the Stop path ("operating on worktree
  <path> for branch <b>") when toplevel != `CLAUDE_PROJECT_DIR` would make the redirect observable
  and aid debugging if the assumption is ever false. (critic)

  Shipped 2026-07-18 (closed-by: stop-worktree-redirect-note). Delivered: cmd_stop now emits a one-line stderr signal ("WORKTREE: .prawduct/ state resolved to worktree <path> for branch <b>, not CLAUDE_PROJECT_DIR (<env>) — the Stop gates read THIS worktree (STH-4K7N)") whenever get_project_dir() redirected .prawduct/ resolution to a worktree toplevel differing from CLAUDE_PROJECT_DIR. New reusable lib/gitstate.py current_branch() probe supplies the branch label; new _worktree_redirect_note() helper in bin/prawduct-hook computes it (silent when env unset or equal — no noise on the single-checkout / launched-in-worktree path). 7 tests added in tests/test_project_dir_resolution.py; full suite green (2371 passed); Critic final-mode clean (0/0/1). DELIBERATE SCOPE DECISION (not a silent drop of the refs' digest.py/banner.py mention): the SessionStart digest/banner surface was scoped OUT — (a) SessionStart runs in the launch dir and provably cannot observe a mid-cycle worktree move (the highest-risk case), so the Stop path is the load-bearing surface the critic named; (b) BRF-6K2D already emits SessionStart worktree-awareness, so a second SessionStart line would duplicate it. The Critic independently validated Stop-path as the correct surface.

- **[CRT-4T7M]** critic-consolidate fail-closes the WHOLE consolidation on a finding whose `files` has a blank/non-string element (`files: [""]`) — `_str_list` rejects it, unlike the already-tolerated empty-list case
  `effort: S · impact: M · area: critic · kind: bug · source: user · added: 2026-07-18 · status: shipped · stage: ready · closed-by: discodon-upstream-defects · related: CRT-9K7T, CRT-7H2W, BLD-5J8N · refs: lib/critic_consolidate.py:429-430, lib/critic_consolidate.py:757, lib/critic_consolidate.py (_str_list :374) · reviewed: 2026-07-18`

  Upstream defect reported by discodon (their id **CRT-M3F8**; kept in prose per the local upstream-id cross-link convention — this repo maps discodon ids to a distinct local id rather than adopting them, so the local id is **CRT-4T7M**). The empty-list `files: []` case is already tolerated (the comment at `validate_partial` :423-428; `_str_list([])` → True and `merge_findings` only keeps truthy files), but a blank/non-string ELEMENT (`files: [""]`) still trips `_str_list` at `lib/critic_consolidate.py:429-430` — `_nonempty_str("")` is False → `all(...)` False → `not _str_list([""])` True → `validate_partial` returns False — and the whole consolidation fail-closes at `:757` (`return 1`, "Fail-closed; not consolidating."). A single reviewer emitting `files: [""]` on a META-finding aborts the entire critic run. Verified against current code 2026-07-18 (identical in 3.0.5/3.1.0); the initial upstream triage pass wrongly called this fixed because it only tested `[]`, not `[""]`. Fix: normalize blank/non-string elements out instead of fail-closing — validator rejects `files` only when it is not a list; `merge_findings` drops falsy/blank elements so `[""]` → `[]` (the same normalization already applied to `[]`); optionally tighten the reviewer prompt to omit `files` for non-file-specific findings. Governance-protected code (`lib/critic_consolidate.py`, pinned by `tests/test_critic_consolidate.py`) → feature-branch + full Critic + PR. Related family: CRT-9K7T, CRT-7H2W, BLD-5J8N. (user, via discodon upstream report)

- **[BLD-5J8N]** verify-chunk-refs can't parse the "## Chunk NN — Title" header style — false "chunk not found" exits habituate reviewers to dismiss a real-BLOCKING-shaped signal
  `effort: S · impact: M · area: critic · source: user · added: 2026-06-22 · status: shipped · stage: ready · closed-by: discodon-upstream-defects · related: BLD-4K7P, BLD-7P3K · refs: bin/prawduct-hook (cmd_verify_chunk_refs), templates/build-plan.md, incoming-bugs/archive/verify-chunk-refs-cant-parse-house-chunk-header-style.md · reviewed: 2026-07-18`

  The chunk-header regex only matches the template's "### Chunk 01: [Name]" form; plans using "## Chunk 01 — title" (h2, em-dash) exit 1 "chunk not found" even though the chunk exists, so reviewers learn to hand-wave the exit — and a real missing-deliverable BLOCKING can then hide behind the dismissed exit (false-negative habituation). Distinct from the verify-chunk-refs ref-TOKEN-extraction family (BLD-2R9X glob, BLD-8F2Q path::symbol, BLD-4K7P <>/URL tokens, BLD-5V8F symbol/backlog-ref) — this is the chunk-HEADER detection regex (which chunks exist at all). Fix-shape: loosen header regex to ^#{2,3}\s+Chunk\s+(\w+)\s*[:—–-]; and/or distinguish "cannot parse" from "ref missing" in the exit contract. Same cmd_verify_chunk_refs surface as BLD-4K7P — could ride in one pass. Governance-protected → full Critic + PR review.

- **[CRT-7H2W]** `/prawduct:critic verify-resolutions` anchors its head to the WORKING tree while the cumulative/PR gate targets the COMMITTED HEAD tree — a dirty tree with judgeable uncommitted files leaves check-cumulative-critic `uncovered` after verify-resolutions reports success
  `effort: M · impact: M · area: critic · source: user · added: 2026-07-14 · status: shipped · stage: ready · closed-by: discodon-upstream-defects · related: CRT-9K7T, CRT-5D8Q, COV-7K4N, CRT-8H3R · refs: lib/critic_consolidate.py:239-297, lib/gates.py:911-980, lib/coverage_algebra.py, lib/critic_mode.py:452, lib/gitstate.py:161 · reviewed: 2026-07-18`

  **Upstream defect** reported by the discodon product (their backlog id CRT-T9RX, local-capture fallback; canonical tracker https://github.com/brookstalley/prawduct/issues). Confirmed in prawduct's own source on branch develop, 2026-07-14.

  **Symptom.** After a `cumulative` review, the builder commits a fix and runs `/prawduct:critic verify-resolutions`, which reports success and records resolution facts — but `prawduct-hook check-cumulative-critic` still reports `uncovered` (exit 1). The only (undocumented) remedy is `git stash` the WIP so working==committed, then re-run verify-resolutions. Observed live on PR #1472 (feature/research-latency→develop): cumulative anchored committed tree 9d32e1bc3185; after a post-cumulative commit (with .devcontainer/* + an artifact .md + backlog.md still uncommitted) verify-resolutions anchored working tree 1aefcf85; the gate wanted committed HEAD 89c9a3bf023b → no path composes → uncovered.

  **Root cause (exact sites, verified in code).**
  - verify-resolutions records `head_tree = capture["tree"]` — the WORKING tree, WIP included — at `lib/critic_consolidate.py:251`.
  - cumulative records `head_tree = capture["head_tree"]` — the COMMITTED HEAD tree — at `lib/critic_consolidate.py:232` (explicit comment: "the committed state, not the dirty tree"; notes-and-excludes WIP at :234-238).
  - `check-cumulative-critic` targets `HEAD^{tree}` (committed) at `lib/gates.py:923`, then calls `coverage_algebra.coverage_verdict(facts, merge_base_tree, HEAD^{tree}, ...)` at :928.
  - So verify-resolutions' review EDGE terminates at the working-tree node, which is not the target the PR gate asks about → composition finds no path → `uncovered`.

  This is the two-target design stated in `lib/coverage_algebra.py:5-8`: the PR gate is Q1 (merge-base tree → HEAD tree) and the Stop-hook Critic gate is Q2 (session baseline tree → WORKING tree, confirmed at `lib/gates.py:604` where `target = capture["tree"]`). verify-resolutions' single head anchor can serve only one of them once the working tree diverges from committed HEAD — today it serves Q2 and breaks Q1.

  **Mechanism refinement — it is NOT "any dirty tree" (this narrows severity and explains the intermittency).** The coverage algebra has a free-edge bridge (`lib/coverage_algebra.py:180-189` and `:301-315`): it probes a free edge from the working-tree node back to committed HEAD, and that edge qualifies IFF the uncommitted delta is entirely non-judgeable. Since `METADATA_PREFIXES = ('.prawduct/', '.claude/settings.json')` (`lib/gitstate.py:161`), uncommitted `.prawduct/*` docs compose SILENTLY via the free edge and the bug never shows. What actually breaks PR #1472 is the `.devcontainer/*` files — plain config, judgeable (`is_judgeable_path` at `coverage_algebra.py:59` returns True: not metadata-prefixed, not a protected .md) — so the free edge fails and the gate goes uncovered. Trigger, precisely: verify-resolutions on a dirty tree that contains uncommitted CODE/CONFIG (judgeable) while closing a COMMITTED delta. Docs-only WIP hides it; a stray config file exposes it.

  **Distinct from the CRT/COV family (cross-link, do not merge).** CRT-8F3K = coordinator writeback never lands. CRT-J4PM = roster/mode-label gate rejection. CRT-K7VF = accepts a FOREIGN-lineage cumulative (base/lineage). CRT-5D8Q = metadata-exemption boundary disagreement (shipped — is_judgeable_path unified it). COV-7K4N = false-uncovered from a stale origin/<base> (base anchor). CRT-8H3R = mode inference latches a sibling-branch anchor (base/lineage). THIS item is a HEAD-anchor mismatch inside a single valid lineage — a different axis than every one of those.

  **Recommended fix — layered pair.**
  1. STRUCTURAL (the real fix): make verify-resolutions' head anchor intent-aware in `lib/critic_consolidate.py` (the else-branch at :239-290). Branch on whether a COMMITTED delta exists since the prior review's `commit_reviewed` (there is already `_committed_files_since` in `lib/critic_mode.py:452`): (a) committed delta exists → builder committed the fix (PR-gate / post-commit case) → anchor `head_tree = capture["head_tree"]`, `head_commit = dispatch_commit`, note-and-exclude WIP exactly like cumulative at :232-238 → edge `prior_head → committed HEAD` → PR gate composes with no stash dance; (b) no committed delta, dirty subset of prior `files_reviewed` (the fix-in-progress signal mode-inference rule-1 keys on) → keep `head_tree = capture["tree"]` (working) → Stop-hook gate composes, and the PR gate legitimately can't pass until the fix is committed (correct). This resolves the irreducible two-target tension by reading intent from git state instead of forcing one anchor, and it PRESERVES CRT-4J8W's dirty-tree-verify capability (the thing :251 was designed to enable). Sound: the reviewer then reviews `prior_head..committed-HEAD` and vouches for exactly what ships.
  2. CHEAP DIAGNOSTIC (ship regardless, mirrors COV-7K4N's stale-base hint): extend `check-cumulative-critic`'s `uncovered` remedy text (`lib/gates.py:969-979`) with a dirty-tree branch, and have verify-resolutions emit a WARNING at record time when it anchors to a dirty working tree carrying judgeable WIP ("anchored to working tree X; the cumulative/PR gate targets committed HEAD Y — if you're closing a committed delta, stash or commit the WIP and re-run"). This alone removes the worst part: reported-success-then-silently-uncovered with an undocumented stash remedy.

  **Rejected:** the reporter's "tolerate/normalize the working-tree anchor in composition" — that would wave UNREVIEWED judgeable uncommitted changes through the gate (an unsound integrity hole). Do not.

  **Governance.** Touches governance-protected code (`lib/critic_consolidate.py`, `lib/gates.py`, possibly `lib/coverage_algebra.py`) with existing pinning tests (`tests/test_critic_consolidate.py:340-345` pins the current dirty-tree/no-head_commit verify behavior — will need updating). → feature-branch + full Critic + PR.

  Cross-link note (triage, 2026-07-14): the upstream distinctness IDs above are discodon-side ids. Local mapping — CRT-8F3K → local counterpart **CRT-9K7T** (forked coordinator never writes findings); CRT-J4PM and CRT-K7VF have **no local backlog item** (upstream-only report ids, kept in the prose for the distinctness argument). Confirmed DISTINCT from all local family members (CRT-9K7T, CRT-5D8Q, COV-7K4N, CRT-8H3R) — cross-linked in `related:`, not merged. (user)

- **[BKL-9V2W]** migrate.import_items: resumable error envelope (TransportError path) drops accrued warnings[] — alias self-heal audit lines lost and never re-emitted on resume
  `effort: S · impact: S · area: backlog-service · kind: bug · source: critic · added: 2026-07-18 · reviewed: 2026-07-18 · status: shipped · stage: ready · related: BKL-6M4T, BKL-3K9N · closed-by: fix/import-resumable-warnings`

  Cumulative-Critic correctness reviewer NOTE (rev-20260718T144940Z): migrate.import_items' resumable mid-run error envelope (TransportError path) carries created/skipped/collisions but drops the accrued warnings[] — an alias self-heal audit line emitted by an already-completed record is lost, and it is never re-emitted on the re-run because the restored label makes the skip take the fast path. The live-migration audit trail should not lose these. Fix direction: include warnings in the error envelope, or re-emit them on resume. Same lost-audit-warning class as the known minor limitation recorded on BKL-3K9N (429-retry path); this is the TransportError-resume path.

  Shipped 2026-07-18 (closed-by: fix/import-resumable-warnings).

- **[BKL-5R2K]** Wire the merge/transfer redirect-follow (`ids.resolve_redirect` / `migrate.resolve`) into a real get/pick consumer
  `effort: S · impact: S · area: backlog-service · source: critic · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · refs: artifacts/build-plan-backlog-service.md · closed-by: Chunk-06`

  `get`/`pick` should auto-follow a `superseded_by` redirect to the survivor. The redirect-follow primitives (`ids.resolve_redirect` / `migrate.resolve`) were built and tested in backlog-service Chunk 05 but have no production consumer yet — the decoded item surfaces `superseded_by` so callers can follow the redirect manually today. Filed from Chunk 05 Critic R-5 note.

  Shipped 2026-07-18 (closed-by: Chunk-06). core.resolve_survivor (hoisted from migrate.resolve, which delegates) wires the redirect-follow into real consumers: get returns the merged-away item with resolves_to + a warning (chain-following, cycle-safe fail-open at the last resolvable node; ERR-6-netted with a diag, degrades to no enrichment); pick excludes an open-but-redirected item (the CRASH-2 window); CLI human mode prints the superseded_by -> survivor breadcrumb. The ENC-6 timeline-redirect sibling stays tracked in BKL-9J3F.

- **[BKL-5T3J]** transport: client-side PR filtering breaks len(batch)<per_page pagination terminators — export/counts/alias-self-heal silently truncate in PR-bearing repos
  `effort: M · impact: L · area: backlog-service · kind: bug · source: critic · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · related: BKL-6M4T, BKL-2V6N · closed-by: Chunk-06`

  Holistic pre-migration review (Fable, 2026-07-18), BLOCKING-BEFORE-MIGRATION. transport.list_issues (transport.py:310-317) fetches one raw page then drops pull_request entries CLIENT-SIDE; every pagination loop that terminates on len(batch) < per_page — query._all_issues (query.py:320), core.iter_alias_issues (core.py:858), migrate._scan_all (migrate.py:850) — sees the FILTERED length and stops early. brookstalley/prawduct has 127+ PRs interleaved in the issues list, so post-import: export (the MG2 backup for the irreversible run) silently dumps a handful of the 217 items; counts/refresh-counts report garbage (and the BKL-8P2R briefing repoint would ship on that broken read); worst, iter_alias_issues feeds the _AliasIndex re-import fallback and reconcile-labels alias restore — a truncated view can turn the exact deleted-label+resume scenario the self-heal exists for into a PERMANENT duplicate issue. A fully-PR page also filters to empty, tripping the documented page-until-empty contract (query.py:72-75). pick mostly escapes (server-side stage:ready label filter). Invisible to the L1 fake and the PR-free spike repo. Fix: transport returns raw pages (terminate loops on raw length) and PR-filtering moves to the decode layer — is_prawduct_issue already excludes PRs (no prawduct marker); keep an explicit pull_request guard in _find_by_key/_numbers_for_alias since labels CAN sit on PRs. Live-verify read-only against the real repo. Gates BKL-6M4T.

  Shipped 2026-07-18 (closed-by: Chunk-06). transport.list_issues returns raw pages (PRs included, marked by pull_request); every len(batch)<per_page terminator now reads raw length; PRs leave the pipeline at encode.is_pull_request/is_prawduct_issue with explicit guards on the label-keyed lookups (_find_by_key, _numbers_for_alias, iter_alias_issues); list gains has_more derived from the raw page (the page-until-empty leg) with per_page clamped 1..100. Live-verified read-only against brookstalley/prawduct: 128 raw entries / 122 PRs walked over 2 pages; the old filtered terminator demonstrably stopped at page 1 seeing 4 of 128.

- **[BKL-2V6N]** transport: gh --paginate multi-document JSON breaks list_labels/list_timeline/list_sub_issues past one page
  `effort: M · impact: L · area: backlog-service · kind: bug · source: critic · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · related: BKL-6M4T, BKL-6W9R · closed-by: Chunk-06`

  Holistic pre-migration review (Fable, 2026-07-18), BLOCKING-BEFORE-MIGRATION. transport.list_labels (transport.py:494-498) uses gh api --paginate without --slurp; gh emits each page as a SEPARATE JSON document, and _api (transport.py:590-602) does a single json.loads -> JSONDecodeError -> TransportError(unavailable) once the result exceeds one page (~30 labels default page size). The import provisions labels per record (migrate.py:727-729 -> provision.ensure_labels -> list_labels), and the migration mints 216 id:PFX alias labels — so the real run dies ~8-12 records in and EVERY resume fails at its first create, permanently. Post-migration, file/update/set-status/provision/reconcile-labels are equally dead. Same latent defect in list_timeline and list_sub_issues (transport.py:457-459, 477-480) — export breaks per-item once an issue accrues >1 timeline page. Invisible to the L1 fake (bypasses gh) and to the small-repo live spike (single page). Fix: --slurp + flatten, or an explicit per_page/page loop like list_issues; MUST be live-verified read-only against a >30-label repo (brookstalley/prawduct qualifies) before the migration. Gates BKL-6M4T.

  Shipped 2026-07-18 (closed-by: Chunk-06). transport._api_paged (explicit per_page/page loop, raw short-page terminator, bounded at 100 pages, injectable per_page) replaces gh --paginate in list_labels/list_timeline/list_sub_issues. Live-verified read-only against brookstalley/prawduct (9 labels walked at per_page=3, set-identical with the single-page read). Silent-cap follow-up filed as BKL-6W9R.

- **[BKL-8P2R]** Chunk 06 briefing/gate repoint must use snapshot.read + detached refresh (never sync counts); fix 30s timeout default; add real-slowness never-block test (G2)
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: design · related: BKL-6M4T · closed-by: Chunk-06`

  Pre-sign-off G2 trace, verified in code. The adapter's never-block floor is solid (4 failure modes slow/auth/offline/429 → clean non-hanging envelope; snapshot cache with visible age; spawn_refresh detached). BUT the consumer prawduct actually needs is UNBUILT: briefing.py:40,675 still parses backlog.md (bare "N pending", no age); gates.py doesn't read counts via the adapter; spawn_refresh has NO caller anywhere (grep). The repoint is deferred to Chunk 06. Risk: the count path paginates (query.py _MAX_PAGES=100) at the transport's 30.0s default timeout (transport.py:252) while NFR §6 specifies "a few s" — so if Chunk 06 wires the briefing to a SYNCHRONOUS counts() instead of snapshot.read + detached spawn_refresh, a slow backend blocks 30s×pages (≈120s typical). Requirements for Chunk 06: (a) wire briefing/gate to snapshot.read + spawn_refresh, never inline counts(); (b) lower/scope the timeout on the briefing path toward the NFR's "few s"; (c) surface the snapshot age in the briefing; (d) add a never-block test that injects ACTUAL slowness (a stalling transport) asserting wall-clock ≤ T — current TestNeverBlock cases inject an instant error (fake raises immediately), so the classic hang case is untested (rests on stdlib-timeout trust).

  Shipped 2026-07-18 (closed-by: Chunk-06). Residuals recorded per the Critic: (1) the "gate" leg was vacuous — gates.py has no backlog-count consumer, so the repoint's real consumers are the briefing + the advisory probes (no-op resolution, not unfinished work); (2) requirement (d)'s never-block test pins fire-and-forget structurally (a child whose wait() raises + a wall-clock bound) rather than injecting a stalling transport — the transport is not reachable on the briefing path at all, which is the stronger guarantee; (3) the live-session repoint leg now reduces to writing backlog_service_repo per runbook step 5.

- **[BKL-2H9W]** `file` creation path applies the issue-structure standard (title + body sections + kind:)
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · related: BKL-3T7X, BKL-6M4T · refs: documentation/backlog-service-issue-standard.md · closed-by: issue-standard`

  Implement the issue standard (documentation/backlog-service-issue-standard.md §1–2) on the net-new creation path (`file` / cmd_file → create_issue). Emit a <=72-char `area:`-prefixed atomic title and a template-structured body (bug: Problem/Repro/Actual/Expected/Evidence; task: Problem/Change/Acceptance `- [ ]`/Scope-out) honoring the §2 per-section word budgets + progressive disclosure (fences/<details>). Assign a `kind:` label (bug/feature/task/chore/spike) — under-populated today. Items are usually model-authored, so this is the shared title/body composer + authoring guidance; the linter (sibling BKL-4C6P) guards it. No fidelity concern (new content).

  Shipped 2026-07-17 (closed-by: issue-standard): the `file` creation path now applies the issue standard §1/§2 — lib/backlog/issuefmt.py (normalize_title area-prefix + render_body section composer) wired into core.file_item, with a kind:/area: authoring contract. Correction: despite the auto-added promotion note, this was NOT part of build-plan-backlog-service.md (the migration slice) — it was built directly from the design parent documentation/backlog-service-issue-standard.md, hence closed-by: issue-standard. Built, tested (offline fake-transport; suite 2215 passing), Critic-reviewed (0 blocking), and documented (api-contract §3, issue-standard §4) this session on branch feature/backlog-prd-owner-feedback.

- **[BKL-4C6P]** WARN-only issue linter implementing the standard §4 thresholds
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · related: BKL-3T7X · refs: documentation/backlog-service-issue-standard.md · closed-by: issue-standard`

  Build a WARN-only linter for the issue standard §4: title >72 / <15 / placeholder, title joining >=2 claims (non-atomic), missing or empty required section, >~150 visible words, unwrapped evidence >30 lines, no kind:/area:, >~6 labels, acceptance prose without `- [ ]`. NEVER blocks (prawduct never-block posture; this path was never a blocking gate — distinct from the "don't demote blocking→warning" rule). Wired into `file` (warn on create) and reusable as an audit over migrated issues (migration runs it audit-only).

  Shipped 2026-07-17 (closed-by: issue-standard): the WARN-only §4 linter (issuefmt.lint), wired into `file` (findings ride in the envelope's `lint` field, never block) and reusable as a migration audit. Correction: despite the auto-added promotion note, this was NOT part of build-plan-backlog-service.md (the migration slice) — it was built directly from the design parent documentation/backlog-service-issue-standard.md, hence closed-by: issue-standard. Built, tested (offline fake-transport; suite 2215 passing), Critic-reviewed (0 blocking), and documented (api-contract §3, issue-standard §4) this session on branch feature/backlog-prd-owner-feedback.

- **[BKL-7Q2N]** PFX alias read-resolution not wired into the other single-id mutators (status/update/comment/claim/unclaim/merge)
  `effort: S · impact: L · area: backlog-service · source: builder · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: design · related: BKL-4W7H · closed-by: Chunk-06`

  BKL-4W7H wired core.resolve_ref (PFX→canonical via the id:PFX alias label, against --repo) into get and link/unlink only (the plan's named read-path consumers). The other single-id commands still call ids.normalize_id directly, so `status BKL-0QR1 --to shipped`, `update BKL-0QR1 ...`, `comment`, `claim`, `unclaim` (core) and `merge` source/target (migrate) still fail "unrecognized ID spelling" on a bare PFX — an incoherence vs MG1 "existing IDs stay valid forever." Fix is mechanical: route each through core.resolve_ref (already built) + thread default_repo from --repo (generalize cli._default_owner to also return the repo). Deferred from BKL-4W7H to keep that fix in the plan's named scope.

  Shipped 2026-07-17 (closed-by: Chunk-06): the single-id mutators (status/update/comment/claim/unclaim) plus merge source/target now resolve a bare PFX through core.resolve_ref + a threaded default_repo (MG1). Built, tested (fake-transport, offline), and Critic-reviewed clean (Goals 1-3, 0 blocking/warn) this session as a Chunk 06 must-fix ahead of the live migration (BKL-6M4T). Shipped straight from design (folded into the signed-off Chunk 06 DoD; body pre-scoped + verified in code during pre-sign-off) without a separate ready stage. (closed-by recorded as the Chunk-06 scope handle, not the caller-supplied commit SHA 857587d — a bare commit SHA can't be recorded as a closed-by ref.)

- **[BKL-3K9N]** Importer has no Retry-After/backoff — a mid-import 429 hard-stops the irreversible migration; immediate re-run re-hits the secondary window
  `effort: S · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: design · related: BKL-6M4T · closed-by: Chunk-06`

  Pre-sign-off rate-budget trace, verified in code. The Pacer proactively paces creates at 80/min + 500/hr (the correct SECONDARY content-creation limit — design did NOT budget against the wrong 5k/hr primary limit; credit). But there is NO reactive rate-limit handling: transport maps 403/429 → TransportError("rate_limited") carrying only {operation,returncode,http_status} — Retry-After is never parsed; grep confirms no retry-after/backoff/exponential anywhere in lib/. On a 429 mid-import, import_items returns a resumable envelope (graceful stop, not crash), but the run aborts and recovery is a fresh top-level re-run that re-hits the same unelapsed secondary window. Realistically reachable during the irreversible run: Chunk 06 repoints briefing/gates to read through the SAME O5 user token during the migration → shared-bucket contention can trip a 429 even though the Pacer avoids it proactively. Fix: on rate_limited inside import_items, parse+honor Retry-After (thread through TransportError.details) or a bounded exponential backoff, then CONTINUE the same run (pause-resume, not hard-stop). Low urgency for the 204-item dogfood in isolation; load-bearing for larger discodon/adopter migrations governed by the same one-shot importer.

  Shipped 2026-07-17 (closed-by: Chunk-06): RateLimitBackoff pauses-and-resumes a mid-import 429 within the same run (honoring Retry-After or a bounded exponential backoff), bounded so a persistent limit stays resumable; the transport now threads a parsed Retry-After into the rate_limited details. Built, tested (fake-transport, offline), and Critic-reviewed clean (Goals 1-3, 0 blocking/warn) this session as a Chunk 06 must-fix ahead of the live migration (BKL-6M4T). Shipped straight from design (folded into the signed-off Chunk 06 DoD; body pre-scoped + verified in code during pre-sign-off) without a separate ready stage. Known minor limitation: a 429 landing between an alias self-heal restore and the reconcile within one record drops that run's "restored missing alias label" audit warning on the successful retry (the restore itself is correct and idempotent).

- **[BKL-8N5K]** MG6 migration restructure pre-pass — restructure to standard, preserve originals, no auto-split (Chunk 06)
  `effort: M · impact: M · area: backlog-service · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · related: BKL-3T7X, BKL-6M4T · refs: documentation/backlog-service-issue-standard.md · closed-by: Chunk-06`

  Implement PRD §8.9/MG6 — the single LLM pre-pass in the MG4 scrub (Chunk 06), BEFORE the deterministic import (no model in the data plane, MIG-5). Per item: propose a <=72 area-title + template body + kind:; PRESERVE the original verbatim (original_title/original_body block fields + the MG2 export); backfill kind: for existing items. NO auto-split — flag non-atomic (multi-claim) items for owner MANUAL split (keeps 1 PFX = 1 issue). Owner reviews the restructured set in AGGREGATE (representative sample + full before/after diff artifact), approves the batch — not per-item HITL. Revises MG1: bodies restructured-to-standard, original preserved (IDs/sections still verbatim). This is a Chunk 06 deliverable (folds into BKL-6M4T's live migration); tracked here as the discrete MG6 build unit.

  Plan-coherence to fold when this is built (surfaced by the issue-standard Critic 2026-07-17, fact rev-20260717T235511Z): build-plan-backlog-service.md has NOT absorbed the issue-standard §5 MG1 revision ('bodies restructured to standard; original preserved verbatim') or this MG6 restructure pre-pass. Reconcile on build: Chunk 05 MIG-1 still says 'verbatim … fidelity'; the Chunk 06 MG4 scrub names no restructure pre-pass; and the SPIKE-S2 settled fact reads 'preserved verbatim'. render_body (lib/backlog/issuefmt.py) is the shared composer to reuse; issuefmt.lint is the audit-only pass to run over restructured items.

  Shipped 2026-07-17 (closed-by: Chunk-06): the MG6 restructure pre-pass shipped as part of the Chunk 06 slice (folds into BKL-6M4T's live migration).
- **[TST-6F2R]** `test-evidence record` with no declared test_command falls back to sys.executable pytest — venv-isolated projects record a catastrophic false-red
  `effort: M · impact: M · area: test-evidence · source: user · added: 2026-07-13 · status: shipped · stage: ready · closed-by: test-evidence-environments · related: TST-3E8V, TST-6V2N, TST-7M3K · refs: bin/prawduct-hook (cmd_test_evidence run fallback, ~line 1903), incoming-bugs/archive/test-evidence-record-persists-false-red-when-test-command-undeclared.md · reviewed: 2026-07-17`

  Upstream bug from discodon (incoming-bugs/test-evidence-record-persists-false-red-when-test-command-undeclared.md, severity medium). When project-state.yaml declares no `test_command`, `test-evidence record` falls back to running `sys.executable -m pytest` — the HOOK's interpreter, not the project's venv. In venv-isolated projects (pipenv/poetry/conda), collection fails wholesale on ModuleNotFoundError and the record persists a catastrophic false-red (discodon: 0 passed / 5074 failed, all collection-level import errors) to `.prawduct/.test-evidence.json`, polluting test-status. Verified in the current tree at bin/prawduct-hook:1903-1907 (the report's ~1787-1792 line refs have drifted).

  Fix direction per the report: fail loud — refuse to record (or exit 2 with a clear "wrong interpreter?" message) when collection-level import failure dominates the run (a suite where ~everything dies at collection is a launch-environment error, not a red suite) — and/or require an explicit `test_command` instead of guessing the interpreter (make the sys.executable fallback opt-in). Same code region as TST-3E8V (launch-failure handling) and the TST-6V2N-born writer; TST-7M3K/TST-4K2P shipped the surrounding record semantics. Governance-protected (test-status gate input) → full Critic + PR review. (user — upstream report from discodon)

  Promoted 2026-07-17 for the 3.1.0 release line.

  Shipped 2026-07-17 (closed-by: test-evidence-environments): delivered the false-red guard (refuse-to-persist with migration guidance), the fallback deprecation nudge, and the multi-environment `test_commands` list the owner's 3.1.0 scope ruling required (polyglot products: one command per environment, aggregated into one record); prawduct now dogfoods a declared test_command.

- **[MET-4V8Q]** Retrieval-over-generation methodology incorporation — new Judgment principle + building/discovery/digest surfaces
  `effort: M · impact: M · area: methodology · source: user · added: 2026-07-17 · status: shipped · stage: requirements · closed-by: retrieval-over-generation · refs: docs/principles.md, methodology/building.md, methodology/discovery.md, hooks/digest.py · reviewed: 2026-07-17`

  From the discodon learning artifact (product-learning feedback; the artifact lives in the discodon repo): incorporate retrieval-over-generation into the methodology as a new Judgment principle, carried onto the building, discovery, and session-digest surfaces. Slated for the 3.1.0 release line. Requirements-stage: recover the source learning artifact from discodon and draft the principle text plus the exact surface changes before design/build. (user — from discodon learning artifact)

  Shipped 2026-07-17 (closed-by: retrieval-over-generation). Requirement grounded by the user's directive plus the discodon source artifact; delivered as Principle 24 with building/discovery/digest/onboard surface changes and learnings capture.

- **[GOV-2T6K]** `templates/architecture.md` authoring template is missing — a product triggered into an architecture spec has nothing to start from
  `effort: S · impact: S · area: governance · source: builder · added: 2026-07-16 · status: shipped · stage: ready · closed-by: architecture-template · refs: templates/, lib/coverage_probes.py (TRIGGERED_ARTIFACTS) · reviewed: 2026-07-17`

  `architecture` is one of the seven strategy-class artifacts (the characteristic-triggered arm fired by `multi_process_distributed`; the sibling triggered artifact `api-contract` ships a template, and every universal strategy-class artifact has one), but `templates/architecture.md` does not exist. So a product that records `multi_process_distributed` and runs `/prawduct:methodology planning` to author its architecture spec has no template to start from — every other strategy-class artifact hands the author a scaffold, this one does not.

  Scope is an additive authoring-template gap, NOT a hole in the shipped coverage mechanism: the `coverage-scaffold` helper drops a neutral, template-independent stub, and a stub satisfies the strategy-artifact-missing probe, so coverage still functions end-to-end. What's missing is the human-facing starting-point document for writing a real architecture spec.

  Fix-shape: add `templates/architecture.md` matching the structure/tone of the other strategy-class templates (`api-contract.md`, `security-model.md`, `data-model.md`, …), including the `(not relevant to this project — <reason>)` stub affordance the coverage mechanism recognizes. Discovered during structural-coverage Chunk 04; also recorded in `.prawduct/cross-cutting-concerns.md` Known Gaps. (builder)

  Promoted 2026-07-17 for the 3.1.0 release line.

  Shipped 2026-07-17 (closed-by: architecture-template): `templates/architecture.md` authored on the closing branch, matching the structure/tone of the other strategy-class templates and including the `(not relevant to this project — <reason>)` stub affordance.

- **[PR-8W3D]** Ambient merge-commit default — carry the `/pr` squash→merge-commit flip onto the ambient guidance surfaces (CLAUDE.md, session digest, pr-skill, templates)
  `effort: S · impact: M · area: pr · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: ready · closed-by: ambient-merge-commit-default · related: WT-7M4K · refs: CLAUDE.md, hooks/digest.py, skills/pr/SKILL.md, templates/project-preferences.md (PR merge strategy row ~:46)`

  The `pr-merge-commit-default` scope flipped `/prawduct:pr`'s merge default squash→merge-commit (recorded in WT-7M4K's update note: a merge commit keeps the branch's commits reachable from the base, so merge-bases stay correct and gates don't re-review already-merged work). This item is the *ambient* leg: merges performed outside the `/pr` flow — an agent running `git merge` directly, release promotions, product sessions following CLAUDE.md/digest guidance — have no stated merge-strategy default, so an ambient squash/fast-forward can reintroduce the stale-merge-base hazard the `/pr` flip dissolved. Deliver the same merge-commit default on the ambient guidance surfaces: CLAUDE.md conventions, the always-injected session digest (hooks/digest.py), any remaining squash-era language in skills/pr/SKILL.md, and the templates (templates/project-preferences.md:46 already documents the merge-commit default for the `/pr` merge — align the ambient-merge guidance with it). Distinct from WT-7M4K's residual, which is detection/hygiene for branches already squash-stale; this is the default itself on non-/pr surfaces. (user)

- **[WT-8Q3N]** SessionStart briefing enumerates sibling worktrees (branch @ path), misdirecting the agent into working in the WRONG worktree/directory
  `effort: M · impact: H · area: briefing · source: user · added: 2026-07-17 · reviewed: 2026-07-17 · status: shipped · stage: requirements · closed-by: fix/briefing-worktree-noise · related: CRT-6W2N, STH-4K7N, STH-3R8K, WT-7M4K, GOV-6H4P, STH-7B5N · refs: lib/briefing.py (_detect_worktrees + worktree-awareness block ~499-516)`

  ROOT CAUSE (corrected per owner, 2026-07-17): This is NOT a session-lock problem and NOT two agents contending for the same directory. It is: the SessionStart briefing surfaces NOISE about sibling worktrees, the agent gets confused, and it goes and works in the WRONG directory. Remove the noise and the agent stays in its own worktree.

  Clean, common repro (owner's words):
  1. user clones repo in D1
  2. user creates a worktree in D2
  3. user starts claude in D1 and sets it to work
  4. user starts another claude in D2 and sets it to work
  5. D1's claude goes and starts working in D2  <-- the failure

  Observed live 2026-07-17: a fresh session launched in the main checkout (D1, develop) read the briefing's enumerated worktree list, saw uncommitted Chunk 04 work in the prd-owner-feedback worktree (D2), judged it adoptable, EnterWorktree'd into D2, and began verifying/reviewing it — while D2 had its own live session actively doing that same work. No collision LOCK is needed to prevent this; the agent should simply never have been pointed at D2.

  The offending code (lib/briefing.py ~509-516): the worktree-awareness block prints one orientation line ("hook is operating on <branch> at <path>. Other worktrees are NOT visible to gates this session.") and then a `for` loop that enumerates every SIBLING worktree as `- <branch> @ <path>`. That enumeration is the noise: it hands the agent a menu of other directories that contain live work, which reads as "here is more work you could pick up." The block was originally added for a gate-SCOPING reason (avoid the discodon "gate fired on the wrong tree" confusion), but its net effect is to MISDIRECT the agent into the wrong worktree.

  FIX-SHAPE (minimal, and it is genuinely minimal — resist re-expanding this into a lock/heartbeat design; the owner has ruled that out):
  - Drop the sibling enumeration (the `for w in worktrees` loop appending `- branch @ path`). Do not advertise other worktrees' branches or paths in the briefing.
  - Keep the POSITIVE orientation the block was meant to give: "You are working in worktree <path> (branch <branch>); gates see only THIS worktree." Optionally add a firm "Other worktrees are separate sessions — do not read or modify them," WITHOUT naming or pathing them (nothing to wander toward).
  - Sibling worktrees remain discoverable on demand (`git worktree list`) if the user actually asks — always-on enumeration is not needed to preserve that.
  - Re-verify the original gate-scoping intent is still served by the orientation line alone (it is — the "gates see only this tree" caveat does not require listing the siblings).

  SEPARATE, secondary concern (do NOT bundle into this fix): the evidence store is clone-shared by design (lib/evidence.py store_path -> git_common_dir), so a worktree's own legitimate Critic reviews still land in the main clone's .git/prawduct/evidence.jsonl. That is a by-design sharing decision, tracked on the advisory surface by GOV-6H4P; it is a cleanliness question, not the wrong-directory failure this item is about. Keep it linked, not merged.

  Process lesson (candidate for learnings.md): "uncommitted work visible in a sibling worktree is NOT yours to adopt — a session works only in the worktree it launched in." Left as a lesson note here; capture separately on a branch off develop.

  Filing note: this rewrite supersedes the original (concurrency/collision/heartbeat) framing per the owner's 2026-07-17 correction. Dropped STH-7B5N from related: (it was the session-lock item — no longer the right direction for THIS item).

  Shipped 2026-07-17 (closed-by: fix/briefing-worktree-noise): PRIMARY fix implemented on branch fix/briefing-worktree-noise — lib/briefing.py drops the sibling-worktree enumeration and rewrites the orientation line to scope the agent to THIS worktree only (positive orientation + original gate-scoping intent preserved); tests/test_briefing_functions.py adds a regression guard; a durable learnings.md rule was added. SCOPE: this closes ONLY the misdirecting-enumeration fix. The SECONDARY belt-and-suspenders liveness DETECTION stays open under STH-7B5N, and the clone-shared evidence cleanliness question stays open under GOV-6H4P — both intentionally NOT closed by this item (kept in related:).

- **[GOV-5K3M]** Author prawduct's 7 strategy-class artifacts (close the layer-1 coverage nudge)
  `effort: M · impact: M · area: governance · source: builder · added: 2026-07-16 · status: shipped · stage: ready · closed-by: structural-coverage · related: GOV-2T6K, GOV-EXI2 · refs: .prawduct/artifacts/, lib/coverage_probes.py (TRIGGERED_ARTIFACTS), .prawduct/cross-cutting-concerns.md · reviewed: 2026-07-17`

  Recording classification.structural for prawduct (structural-coverage Chunk 05 dogfood) advanced the coverage chain to layer 1: prawduct now owes all seven strategy-class artifacts, currently all missing. Author each in .prawduct/artifacts/ as a real spec OR a deliberate '(not relevant — <reason>)' stub (existence satisfies coverage). The set: data-model.md, security-model.md, nonfunctional-requirements.md, operational-spec.md, observability-strategy.md (universal); api-contract.md (triggered by exposes_programmatic_interface — document the bin/prawduct-hook CLI + JSON contracts, versioning/deprecation/error-model decisions); architecture.md (triggered by multi_process_distributed — process topology of the Critic coordinator/reviewer fan-out + shared tree-keyed evidence store). This is the deferred symptom-fix, correctly downstream of the system-fix (the coverage chain itself). NOTE: authoring architecture.md is missing its authoring template — see GOV-2T6K (templates/architecture.md). prawduct-hook coverage-scaffold --apply drops neutral stubs for all seven in one act as a starting point.

  Shipped 2026-07-17 (closed-by: structural-coverage): all seven strategy-class artifacts now exist under `.prawduct/artifacts/` (api-contract.md, architecture.md, data-model.md, nonfunctional-requirements.md, observability-strategy.md, operational-spec.md, security-model.md), closing the layer-1 coverage nudge.

- **[GOV-5D2W]** Advisory `show` reconstructs evidence with an empty probe registry — probe re-run silently no-ops for every probe family
  `effort: S · impact: S · area: governance · source: critic · added: 2026-07-16 · status: shipped · stage: ready · closed-by: structural-coverage · related: GOV-6H4P · refs: lib/advisory_cmd.py, lib/probe_families.py, bin/prawduct-hook, tests/test_advisory_cmd.py · reviewed: 2026-07-16`

  Probe registration lives only in cmd_clear (bin/prawduct-hook ~line 690), so lib/advisory_cmd.show_advisory's probe re-run reconstructs evidence against an empty probe registry and silently no-ops for every probe family. Pre-existing graceful degradation surfaced by the norm-lifecycle Chunk 3 Critic review (fact rev-20260716T173555Z-10a0f433, NOTE). Fix shape: a shared register-all-probes helper both call sites use. (critic)

  Shipped 2026-07-16 (closed-by: structural-coverage): resolved by structural-coverage Chunk 04 — exactly the item's fix-shape. Created `lib/probe_families.py` with `register_all()` as the shared probe-registration helper, and wired both `bin/prawduct-hook` cmd_clear and `lib/advisory_cmd.show_advisory` to it, so `advisory show` reconstruction now registers the full probe roster before re-running probes (previously it scanned an empty registry and no-op'd for every family). Regression test: `tests/test_advisory_cmd.py::test_show_self_registers_probe_roster_for_reconstruction`.

- **[GOV-EXI2]** `norm-registry-unratified` advisory adoption blind spot — Enforcement-table-lacks-norm-columns disjunct never fires without strategy-class artifacts
  `effort: M · impact: M · area: governance/advisory · source: user · added: 2026-07-16 · status: shipped · stage: design · closed-by: structural-coverage · related: GOV-7Q4N, GOV-6N4W · refs: lib/norm_probes.py (norm-registry-unratified probe), docs/norms.md (§ Adoption, § Enforcement), .prawduct/.governance-ledger.jsonl (Chunk 3 review R-1) · reviewed: 2026-07-16`

  The `norm-registry-unratified` advisory requires strategy-class artifacts to exist before firing, so a product whose norms live only in project-preferences.md (Enforcement table) + learnings — with no strategy-class artifacts — never gets the ratification nudge. Prawduct itself is in this blind spot: its own norm registry is unratified and the advisory stays silent. The disjunct that would catch it ("Enforcement table lacks norm columns") was deliberately deferred in Chunk 3 (Critic finding R-1) to hit the norm-lifecycle build's "zero advisories against this repo" acceptance criterion.

  Fix-shape: make the "Enforcement-table-lacks-norm-columns" disjunct fire independently of strategy-class artifacts, relying on the one-shot + shared-answer + clears-on-ratify-or-record-none mechanism (already built) to keep the broad nudge tolerable rather than narrowing the trigger.

  Design question to resolve: false-nag posture on mass upgrade — every pre-norm product would fire once on adoption day; confirm the one-shot/shared-state clearing makes that acceptable (it was designed to) vs. the narrowing that traded away the signal.

  Governance-protected (probes/hooks) → full Critic + PR review. (user)

  Shipped 2026-07-16 (closed-by: structural-coverage): resolved by design — the structural-coverage staging chain closes the blind spot upstream rather than by ungating layer 2. Layer 1 (strategy-artifact-missing) now nudges a product with no strategy-class artifacts to author them (a `(not relevant — …)` stub counts and still creates the file); once any strategy artifact exists — even an all-stub set — layer 2 (norm-registry-unratified) fires the ratification nudge as before. So a product whose norms live only in preferences + learnings is reached transitively (layer 1 → files exist → layer 2), and layer 2's artifact-existence gate becomes correct staging instead of a blind spot. The original ungate-arm-(b) fix-shape is deliberately NOT taken (the DECISION line in build-plan-structural-coverage.md Requirements Confidence). Recorded in docs/norms.md § Enforcement (structural-coverage staging table).

- **[GOV-7Q4N]** Norm lifecycle — treat governing-artifact statements as binding norms with a full lifecycle
  `effort: L · impact: L · area: governance · source: user · added: 2026-07-16 · status: shipped · stage: ready · closed-by: norm-lifecycle · related: MET-3P7B, GOV-3P8K · refs: build-plan-norm-lifecycle.md, docs/norms.md · reviewed: 2026-07-16`

  Treat normative statements in governing artifacts as **binding norms** with a full lifecycle: birth/retroactivity, jurisdiction, rulings, exceptions with expiry, transitions, and erosion/decay health. Origin: discodon incident — async-tool work built a bespoke telemetry system parallel to the declared OTel substrate, and **every governance layer laundered the divergence** (Critic Goal 6, PR review, and doc-freshness each resolved the mismatch by syncing the strategy artifact to the code, i.e. the norm was rewritten to match the violation instead of the violation being flagged). Root cause: prawduct's coherence model is one-directional — artifacts track code — with no concept of normative statements that *bind* code. Design complete: build plan at `.prawduct/artifacts/build-plan-norm-lifecycle.md` (being authored the same session as this filing, 2026-07-16 — confirm the plan file landed before promoting). Adjacent-not-duplicate: MET-3P7B (assign an enforcement mechanism per preference — a norm-enforcement sibling at methodology level), GOV-3P8K (deterministic tripwire for durable-artifact coherence). (user)

  Promoted 2026-07-16: plan-landed caveat confirmed — `.prawduct/artifacts/build-plan-norm-lifecycle.md` exists and `project-state.yaml` `active_build_plan` points to it. In active build on `feature/norm-lifecycle` (Chunk 1 complete).

  Shipped 2026-07-16: all six chunks of `build-plan-norm-lifecycle.md` built on `feature/norm-lifecycle` (Chunks 1–6, `d8d1ef6`…`f78bb73` "time-domain sweeps + adoption path"); closing cumulative Critic review passed with 0 blocking findings. Archived on the branch so it ships in the closing PR. Supersedes the earlier "stays promoted" disposition, which predated Chunks 5–6 landing.

- **[MET-3P7B]** Lift "assign a mechanism per preference" pattern into methodology
  `effort: M · impact: M · area: methodology · source: critic · added: 2026-05-01 · status: shipped · stage: research · closed-by: norm-lifecycle · related: GOV-7Q4N · refs: docs/norms.md (§ Birth, § Enforcement), templates/project-preferences.md (§ Enforcement) · reviewed: 2026-07-16`

  The Enforcement section added to `project-preferences.md` (and the template, 2026-05-01) encodes a methodology insight: every preference must be assigned to Linter / Test / Critic when it's captured, with a false-confidence guardrail that escalates weak tests to Critic. Currently lives only in the artifact + template. Candidate: weave into `methodology/discovery.md` (when capturing preferences) and `methodology/planning.md` (when designing test specs). Validate the pattern against 2-3 more preferences first before promoting. (critic)

  Closed 2026-07-16 by the norm-lifecycle bundle (GOV-7Q4N), which subsumes the ask at a stronger level than the item's candidates: `docs/norms.md` § Birth makes an Enforcement-table row — mechanism assigned and existing-or-filed, audit home per the Audit-home rule — a requirement of norm *capture* itself; the preferences Enforcement table is designated the product's norm index and gained Audit home/Why columns (template); and `methodology/discovery.md` ("A norm surfaced"), `methodology/planning.md` (Governing Artifacts / `governed_by:` reconciliation), and `methodology/building.md` all route norm capture through `docs/norms.md`. The false-confidence guardrail (weak test → escalate to Critic) remains in the template's Enforcement section — now on the mandatory capture path, its point of use — consistent with norms.md § Deliberate Non-Design keeping per-mechanism guidance in the table. The "validate against 2-3 more preferences" precondition is moot: the pattern was validated by generalizing it to all norms. Residual: none. (This repo's own artifact table predates the new columns; the designed upgrade route is the Chunk 6 adoption path — `norm-registry-unratified` advisory + `/prawduct:doctor` ratification — tracked by that machinery, not this item.)

- **[CRT-2K9F]** PR-gate ledger fallback should select the newest record that covers HEAD — interleaved Critic→PR cycles silently invalidate the earlier branch
  `effort: S · impact: M · area: critic · source: user · added: 2026-06-22 · status: shipped · stage: design · closed-by: kernel-evidence-store · related: CRT-8W3F, CRT-4J8W, CRT-7M2D · refs: lib/gates.py (compute_pr_gate, _pr_gate_record_qualifies, _evaluate_pr_gate_record, _ledger_fallback_record — all deleted in the v3 cutover), .prawduct/.critic-findings.json (no longer read by any gate) · reviewed: 2026-07-13`

  Observed live 2026-06-22 while shipping the review-streamlining track (PRs #101/#102/#103). The cumulative-Critic PR gate (lib/gates.py compute_pr_gate) reads the single-slot .prawduct/.critic-findings.json. When two branches' Critic→PR cycles interleave (run branch X's Critic, then branch Y's Critic, then go to PR branch X), Y's Critic has overwritten the single slot with a record that IS the right KIND (a clean cumulative) but covers Y's HEAD, not X's. compute_pr_gate only falls back to the governance ledger when the slot record is the WRONG KIND (_pr_gate_record_qualifies false); a right-kind-but-wrong-HEAD record goes straight to _evaluate_pr_gate_record, fails the coverage check, and exits 1 — it never consults the ledger, where X's own still-valid qualifying record was appended. This session it forced a needless re-run of budget's Critic after B's Critic clobbered budget's slot.

  Fix-shape: when the slot record fails (wrong kind OR fails HEAD-coverage/chain-scope), fall back to the ledger AND make _ledger_fallback_record select the newest qualifying record whose commit_reviewed COVERS THE CURRENT HEAD (CRT-7M2D coverage semantics), not merely the newest session-fresh qualifying record. The CRT-8W3F session-freshness bound stays.

  Workaround today: finish one branch's full Critic→PR cycle before starting the next branch's Critic.

  Assurance: must not loosen the gate — a record that covers HEAD and is clean is exactly as strong as the slot record would have been; this only stops a sibling branch's clean record from masking this branch's. Governance-protected file (lib/gates.py + skills/) → full Critic + PR review.

  Related: CRT-8W3F (ledger-fallback freshness bound, shipped), CRT-4J8W (verify-resolutions chain record, shipped), CRT-7M2D (covers-HEAD semantics). (user)

  Worktree corollary (verified 2026-06-22): the clobber is strictly a within-ONE-working-tree problem. Each git worktree has its own gitignored .prawduct/.critic-findings.json (and .session-start, .governance-ledger.jsonl), so running each branch's Critic->PR cycle in a separate worktree sidesteps the clobber entirely — no shared single slot to overwrite. That makes worktrees an available workaround and lowers this item's urgency; the in-tree fix below still matters for users who switch branches within one tree.

  **Resolved by design, kernel-v3 evidence store (gate cutover ch.04 + vestige sweep ch.06),
  2026-07-13.** The single-slot clobber premise is gone: review facts append to the shared,
  tree-keyed evidence store (`<git-common-dir>/prawduct/evidence.jsonl`) and the PR gate answers
  by composition (`lib/gates.py` → `lib/coverage_algebra.coverage_verdict`, merge-base tree →
  HEAD tree, zero unresolved blocking findings). No gate reads the single-slot
  `.critic-findings.json` any more, and the ledger fallback this item's fix-shape targeted was
  deleted outright with stays-deleted guards — the chunk-06 cumulative review verified the
  deletion. Interleaved branch Critic→PR cycles each compose their own facts, so branch Y's
  review can no longer mask or invalidate branch X's. Archived on
  `feature/kernel-v3-evidence-store` per the ship-in-PR convention (chunk-06 cumulative review,
  bundle f64c22c..69f63a2).

- **[STH-8R3Q]** Wave 2: outcome-checking Critic Stop gate — findings file must show zero unresolved blocking findings, not merely valid schema
  `effort: S · impact: M · area: stop-hook/gates · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: kernel-evidence-store · related: STH-4F7C · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Overbuilt #5), lib/gates.py (session_review_verdict — replaced critic_findings_satisfy_session_gate in the v3 cutover) · reviewed: 2026-07-13`

  P1. The Critic Stop gate accepts any schema-valid fresh findings file EVEN WITH unresolved
  blocking findings — it enforces a proxy (file exists, schema valid), not the outcome (blockers
  resolved). Make `critic_findings_satisfy_session_gate` check disposition of blocking findings.
  Gate edit governs the editing session — small blast radius, own branch. (user)

  **Resolved, kernel-v3 evidence store (gate cutover ch.04), 2026-07-13.** The Stop-hook Critic
  gate now outcome-checks exactly as this item demanded: `cmd_stop` calls
  `lib/gates.session_review_verdict` → `coverage_algebra.coverage_verdict`, which passes only
  when composed review coverage spans session base tree → current working tree with ZERO
  unresolved blocking findings. The schema-valid-file proxy
  (`critic_findings_satisfy_session_gate`) is deleted — no gate reads `.critic-findings.json`.
  Verified by the chunk-06 cumulative review (bundle f64c22c..69f63a2). Archived on
  `feature/kernel-v3-evidence-store` per the ship-in-PR convention.

- **[CRT-3F6W]** Wave 2: reviewer-dedup deletion — keep both reviewers; PR reviewer becomes a fresh full-scope release review; delete the record-audit protocol, extends_cumulative chain, and don't-re-scan scoping prose
  `effort: M · impact: M · area: critic/pr-protocols · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: kernel-evidence-store · related: CRT-5T8N, CRT-6J4P, CRT-8H3R, CRT-9R4K · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Overbuilt #4), skills/pr/review-protocol.md · reviewed: 2026-07-13`

  P1. Independence is load-bearing — two reviewers stay (PR reviewer independently caught bugs
  the Critic missed at least twice). What goes is the ~2k words of OVERLAP machinery that exists
  only to deduplicate two overlapping scopes: the "Critic Record — Evidence, Not Truth" audit
  protocol, the extends_cumulative chain, verify-resolutions scope math, and the "don't re-scan"
  scoping prose. The PR review becomes a simple fresh full-scope release review. Prefer deletion
  over patching. Supersedes CRT-5T8N's single-owner question — candidate `closes:` at dedup. (user)

  **Resolved by the kernel-v3 cutover (chunks 04–06), 2026-07-13 — the deletion targets are
  dead; the re-review prescription was superseded.** Every piece of overlap machinery this item
  ordered deleted is gone: the "Critic Record — Evidence, Not Truth" record-audit protocol no
  longer appears in `skills/pr/review-protocol.md`, and `extends_cumulative` chains +
  verify-resolutions scope math were deleted from `lib/gates.py`/`lib/critic_mode.py` with
  stays-deleted guards. Both reviewers remain, as this item required. One deliberate delta from
  the prescription: the PR reviewer did NOT become a fresh full-scope re-review — v3 made that
  unnecessary, because `check-cumulative-critic` structurally verifies composed coverage over
  the actual trees before the reviewer is dispatched, so it stays release-readiness-scoped. The
  two surviving "don't re-scan" notes (learnings cross-check, backlog-reconciliation R-1) are
  deliberate single-owner scoping, not dedup machinery. CRT-5T8N's single-owner question is
  answered by this design (each check has exactly one owner) — assess it at next triage rather
  than via the `closes:` this item anticipated. Archived on `feature/kernel-v3-evidence-store`
  per the ship-in-PR convention (chunk-06 cumulative review, bundle f64c22c..69f63a2).

- **[CRT-5D8Q]** PR-gate coverage vs verify-resolutions scope disagree on the metadata exemption — deadlock when the ledger fallback window has lapsed
  `effort: S · impact: M · area: governance/critic-gate · source: critic · added: 2026-07-02 · status: shipped · stage: ready · closed-by: kernel-evidence-store ch.04 · reviewed: 2026-07-13 · related: CRT-8H3R, CRT-2K9F, CRT-4J8W, STH-6T9W, GOV-4C7X · refs: lib/gates.py (_record_covers_head L972, _compute_verify_resolutions_scope L447), tests/scenarios/test_kernel_v3_gate_cutover.py`

  The two gate helpers draw the `.prawduct/` metadata-exemption boundary differently. `_record_covers_head` exempts only `.md` files, so a routine post-cumulative `.prawduct/*.yaml` change (e.g. repointing `active_build_plan`) marks the cumulative record stale. But `_compute_verify_resolutions_scope` exempts ALL `.prawduct/` metadata, so the demanded verify-resolutions pass returns "no-actionable-findings" and the SKILL's literal demotion to `final` yields a non-gate-qualifying record — deadlock when the ledger fallback window has lapsed. Fix-shape: make the two helpers agree on the metadata-exemption boundary. Observed live 2026-07-02 on feature/changelog-fail-loud (Critic hand-anchored a chain record to route around it). Governance-protected (lib/gates.py) → full Critic + PR review. (critic)

  **Resolved by design, kernel-v3 chunk 04 (gate cutover), 2026-07-13.** The v3 gates use ONE
  judgeability predicate, so the split `_record_covers_head` / `_compute_verify_resolutions_scope`
  boundary disagreement that produced the deadlock no longer exists; scenario-pinned in
  `tests/scenarios/test_kernel_v3_gate_cutover.py`. Archived on `feature/kernel-v3-evidence-store`
  per the ship-in-PR convention (chunk 04 Critic review, final mode).

- **[CRT-4B7X]** critic-consolidate concurrency — two near-simultaneous SubagentStop firings each write a `review.critic` ledger line (duplicate telemetry)
  `effort: S · impact: S · area: critic · source: critic · added: 2026-07-09 · status: shipped · stage: ready · closed-by: kernel-evidence-store ch.03 · reviewed: 2026-07-13 · related: CRT-9K7T, TEL-2B6K, CRT-6Q2N · refs: .prawduct/.governance-ledger.jsonl`

  Two near-simultaneous SubagentStop firings can both pass the completeness check and each write a `review.critic` ledger line — a duplicate telemetry entry. Correctness and gates are unaffected (the findings file is single-slot and check-cumulative reads newest-first); only review-stats double-counts. Fix-shape: a lightweight lock / rename-guard around the consolidate merge so exactly one firing wins. Surfaced by the critic-persistence-redesign cumulative review (NOTE). (critic)

  **Resolved by design, kernel-v3 chunk 03 (deterministic dispatch), 2026-07-13.** The v3
  `critic-consolidate` appends the review fact idempotently by dispatch id and the readers
  dedupe at read time, so concurrent SubagentStop firings can no longer double-land the store
  fact — the race this item describes is dead (chunk 03 commit: "the CRT-4B7X store race dies").
  Residual: the ledger anchor LINE itself still lacks a dispatch-id idempotency guard; that
  narrower symptom is carried by the open sibling CRT-6Q2N. Archived on
  `feature/kernel-v3-evidence-store` per the ship-in-PR convention (chunk 04 review follow-up).

- **[CRT-9K7T]** Forked `/prawduct:critic` coordinator never writes `.critic-findings.json` and leaves a stale `.critic-active` marker
  `effort: M · impact: M · area: critic · source: critic · added: 2026-07-09 · status: shipped · stage: ready · closed-by: critic-persistence-redesign · reviewed: 2026-07-09 · related: CRT-7Q2T, CRT-2K9F, STH-6T9W, CRT-6F2N · refs: skills/critic/SKILL.md, .prawduct/.critic-findings.json, .prawduct/.critic-active`

  In forked/coordinator mode (final + verify-resolutions, 3-subagent pattern), the reviewer subagents complete and return full reviews via task-notifications, but the coordinator never writes the consolidated `.prawduct/.critic-findings.json` (it stays frozen at a prior review's timestamp), and `.critic-active` is left present with a now-dead pid (must `rm -f` before the next run). Impact: stop-hook / cumulative-critic gates read a stale/foreign record, so they cannot confirm a review ran for the current changeset even though it did and all findings were resolved; the builder cannot sanctioned-ly write the file themselves, forcing a manual gate waiver every time. Observed 4x in one session on prawduct plugin v2.3.0 (discodon, filed there as CRT-8F3K, area prawduct-upstream). A related variant seen in cordyceps (2026-07-02): the forked coordinator returns BEFORE its background reviewers finish, so a network drop + re-invoke spawns a duplicate reviewer fleet (wasted cost) and aggregation only completes via a manual "aggregation-only" re-invoke. Fix-shape: make the coordinator reliably write the consolidated findings file and clear `.critic-active` on completion; consider an idempotent/resume-aggregation coordinator that reattaches to in-flight reviewers instead of re-spawning. Governance-protected → full Critic + PR review. Cross-repo (2 consumers), post-2.3.0. (critic)

- **[MET-3Q8V]** Wave 1 Plan C: prose-diet — single-source the mode/type matrix, strip the build-plan template to a filled example, fold agent-stance + delegator skills, reconcile the 5 contradictions
  `effort: L · impact: L · area: methodology/prose · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: prose-diet · reviewed: 2026-07-04 · related: MET-7R4J, MET-5C2H, CRT-5Q8W · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan C, Overbuilt #3), .prawduct/artifacts/build-plan-prose-diet.md, methodology/planning.md:97-137, templates/build-plan.md:222-281, methodology/building.md:284`

  P0. Target: halve the ~31k-token governance cycle load. Moves: single-source the mode×type
  matrix (methodology only; template gets a pointer); strip build-plan template (2,774 words,
  zero filled examples) to a FILLED example + brief comments; fold agent-stance.md into the
  digest; fold the 4 one-line delegator skills (building/discovery/planning/reflection) into
  /prawduct:methodology; delete implementation narration (hook internals, bug IDs,
  withdrawn-model chains, the parser-bug narrative at build-plan.md:22-29) from files weaker
  models parse; de-Fable-ese compressed sentences; reconcile the 5 documented cross-doc
  contradictions (listed in the artifact). Largely supersedes MET-7R4J. (user)

  Promoted 2026-07-02: build plan authored at .prawduct/artifacts/build-plan-prose-diet.md
  (branch feature/prose-diet, 3 chunks). The plan pre-delivers STN-4W7R part (a) (advisor-first
  digest stance rewrite, chunk 03) and MET-2X6F's filled-example-chunk (chunk 01) — those items
  get updated at close-out, not now. MET-7R4J supersession check is a chunk 03 close-out step.

- **[VWS-6R4T]** Wave 1 Plan B: changelog-fail-loud — regen-views validates every change-log tag against the plan roster and errors loudly; tolerant chunk-ID matching
  `effort: M · impact: L · area: change-log/views · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: changelog-fail-loud · related: REL-9F2T, REL-2N8K, REL-6C3W, VWS-4D8J, VWS-7N3K, BLD-5J8N, REL-4Q9V · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan B, Overbuilt #2), .prawduct/artifacts/build-plan-changelog-fail-loud.md · reviewed: 2026-07-02`

  P0. The literal-string tag DSL fails partially and SILENTLY (~12 of 71 learnings, duplicate
  incoming bugs, broke for trenchant's entire lifespan). Fix: validate every tag (`scope=`,
  `chunks=`, `status=`) against the plan roster at write/check time — no silent partial flips;
  tolerant chunk-ID matching (zero-padding, separator variants). Consider shrinking the
  vocabulary: one scope identifier; statusless-until-release as the only lifecycle. Overlaps the
  REL-9F2T silent-drop family and VWS-4D8J/VWS-7N3K — dedup pass should fold or `closes:` those
  once this is planned. Prefer deletion over patching. (user)

  — 2026-07-02: claimed by @brooks; build plan authored at
  `.prawduct/artifacts/build-plan-changelog-fail-loud.md` (branch `feature/changelog-fail-loud`).
  The "consider shrinking the vocabulary" clause is DESCOPED from that plan per the plan's
  HIGH-impact assumption (owner asked 2026-07-02, AFK, recommendation applied) — the shrink now
  lives as its own item, [REL-4Q9V].

  **Shipped 2026-07-02** on `feature/changelog-fail-loud` (chunk 01 built and Critic-cleared,
  aaaf39a): fail-loud roster validation + tolerant chunk-ID matching + `regen-views --check`
  shipped. The vocabulary-shrink clause lives on as [REL-4Q9V].

- **[GOV-7T2M]** Wave 1 Plan A: gate-noise — freshness = `test-status` exit code only (both review protocols) + work-model tripwire verb/corpus fix
  `effort: S · impact: L · area: gates · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: gate-noise · related: WMK-4Q9T, WMK-7D3R · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan A), .prawduct/artifacts/build-plan-gate-noise.md, skills/critic/review-protocol.md, skills/pr/review-protocol.md, lib/work_model_index.py:120-126, bin/prawduct-hook:2661-2675 · reviewed: 2026-07-02`

  P0. (1) One line in BOTH review protocols: test-evidence freshness is the `test-status` exit
  code; reviewers must never infer staleness from anything else (session-timestamp is the settled
  freshness answer — this closes the residual "reviewer eyeballs staleness" gap). (2) Tripwire:
  drop refactor/rename/redesign/rework/remove/replace from REQUIREMENT_VERBS and include doc
  subdirectories in the corpus glob (fired on the owner's own review prompt twice). Largely
  supersedes WMK-4Q9T — candidate for a `closes:` merge at dedup. High-confidence; proceed to
  planning without re-running discovery. (user)

  **Promoted 2026-07-02:** build plan active at `.prawduct/artifacts/build-plan-gate-noise.md`
  on `feature/gate-noise`. Deliverable (1) (protocol freshness lines) verified already shipped
  in PR #104 — the plan descopes it; remaining scope is the tripwire verb split + recursive
  doc corpus.

  **Shipped 2026-07-02** on `feature/gate-noise` (chunk 01, cumulative Critic clean):
  MAINTENANCE_VERBS split out of REQUIREMENT_VERBS (still orphan-exempt via _DIRECTIVE_VERBS)
  + `docs/`/`methodology/` corpus globs made recursive. Deliverable (1) was descoped — already
  shipped in PR #104 (2026-06-22, TST-4K2P: skills/critic/review-protocol.md:41,
  skills/pr/review-protocol.md:56). Dedup resolution: WMK-4Q9T is NOT closed by this — the
  supersession is partial (requirement-shape misfire + doc-subdir recall fixed here; the
  path-fragment tokenization leg remains) — WMK-4Q9T stays open, narrowed to the residual.

- **[COV-3R9K]** test-evidence double-run after a no-op commit — RUN-half closed (retired "record-after-commit" habit + `--from-counts`/`--no-rerun`); the original F4a-scope-shift diagnosis was a MISDIAGNOSIS
  `effort: M · impact: M · area: coverage · source: user · added: 2026-06-26 · status: shipped · stage: requirements · closed-by: test-evidence-single-run · related: TST-4K2P, TST-7M3K, COV-8R2K, COV-4M2J · refs: methodology/building.md, bin/prawduct-hook, .prawduct/artifacts/build-plan-test-evidence-single-run.md · reviewed: 2026-06-26`

  **RESOLVED — reframed 2026-06-26 with the VERIFIED diagnosis (closed-by=test-evidence-single-run; ships in this branch's PR, merged-pending like the rest of the bundle).** A multi-agent investigation (consumer map of every `.test-evidence.json`/`changes_referenced` reader, empirical `git diff` traces in throwaway repos, TST-4K2P/TST-7M3K history, three adversarial verifiers) corrected the original triage: the RUN-half is closed by docs + two new on-ramps, the coverage-FLOOR language gap is split out (COV-4M2J), and the originally-blamed F4a scope-shift was a MISDIAGNOSIS.

  **Verified diagnosis (replaces the original F4a framing in the upstream report below):**
  - The double-RUN is NOT gate-forced. Freshness is session-scoped (`lib/gates.py:tests_are_current`: `timestamp >= .session-start` AND `failed==0`, with NO `git_sha`/HEAD/tree-hash since TST-4K2P), and `changes_referenced` is produced by `git diff --name-only <base>` (base→working-tree, content-based), commit-invariant on a real base branch.
  - The reported `git diff base...HEAD` membership-shift was a MISDIAGNOSIS: the changed-file producers use two-arg `git diff <base>` (base→working-tree), not three-dot `base...HEAD`, so a no-op commit does not shift the set on a real base. (The only genuine no-op-commit shift is the HEAD~1 *fallback* base on repos with no `main`/`base_branch:` — advisory, addressed in resolution item 3.)
  - Root cause: a retired "record AFTER the final commit / evidence SHA must equal HEAD" habit (declared obsolete at learnings.md:270-272), not a code defect.

  **RESOLUTION — shipped in build-plan-test-evidence-single-run (scope=test-evidence-single-run):**
  1. `methodology/building.md` now prescribes record-ONCE-at-Verify and states that a commit (even a no-op) does not stale session-scoped evidence — kills the habit at its documentation source; propagates to every consumer via the plugin.
  2. The stale "Stopgap … record test-evidence as the LAST step, after committing" wording in the TST-4K2P content-hash item is marked SUPERSEDED (survives only as a quoted-obsolete reference).
  3. Suggested fix #2 (`--no-rerun`/`--restamp`) shipped as the sanctioned cheap COVERAGE-half refresh — reuse prior counts, re-stamp the timestamp, re-overlay F4a against the current tree, no suite run (covers the real surviving F4a shifts: a rename or a force-added gitignored path on a fixed base). Plus a HEAD~1-fallback-base stderr advisory naming the `base_branch:` knob.
  4. The agnosticism gap surfaced during design (the recorder was JUnit-coupled) is closed by a NEW `--from-counts passed=N failed=M skipped=K` on-ramp so non-JUnit / embedded / bespoke toolchains record evidence without faking a JUnit report.

  (Suggested fix #3 `--from-junit` was already shipped in TST-7M3K / v2.1.8 — the prior triage noted this.)

  **NOT done — deliberately rejected (pre-v1.4 + TST-4K2P):** content-/tree-hash freshness (suggested fix #1) and any `git_sha`/HEAD/commit-position field. Both were removed pre-v1.4 for chronic false positives and TST-4K2P explicitly rejected re-adding them; freshness stays session-scoped (timestamp).

  **Split out → COV-4M2J:** the Python-only coverage FLOOR (`bin/test-reference-verify` symbol-grep is Python-only; bring-your-own-verifier via `--merge-into` is the current escape for other languages) is the remaining residual.

  --- Original upstream report (scriob, prawduct 2.2.1, gitflow, per-component venvs: engine+server pytest, frontend vitest; source: incoming-bugs/test-evidence-redundant-rerun-after-noop-commit.md, archived) ---

  SYMPTOM: To satisfy the documented discipline that test-evidence must "vouch for HEAD," the operator records evidence, commits the chunk (which packages the exact same tree just tested), then must record evidence AGAIN — a second full multi-component suite run (~3-4 min) with byte-identical inputs and identical outputs. `record` always re-runs the suite; there is no "tree didn't change, just restamp" path. One chunk paid ~7 min of test time, half pure duplicate. Severity: medium (waste + trains operator to distrust a green test-status).

  COMPONENTS: `prawduct-hook test-evidence record` + `lib/coverage.py` (changed_files / reference-verify) + the methodology learning "Record test-evidence AFTER the chunk's final commit — the evidence SHA must equal HEAD". `.prawduct/.test-evidence.json` stores timestamp + changes_referenced + counts but NO git_sha at top level — nothing in the file even names the commit it's supposed to match.

  ROOT CAUSE (reporter: inferred, partially traced): `lib/coverage.py` derives the changed-file set from `git diff <base>...HEAD` (base = origin/main / main / HEAD~1) unioned with untracked files; this feeds `changes_referenced`, which `bin/test-reference-verify` later checks. The diff membership shifts the moment you commit (a modified file moves from "working-tree vs HEAD" into "in HEAD vs base"), so pre-commit evidence references a differently-scoped set than the post-commit gate recomputes — hence the re-record rule. The only refresh mechanism is a full re-run; no content-/tree-hash short-circuit, no restamp.

  SUGGESTED FIXES (any one removes the duplicate run): (1) Validate evidence by source/tree-content hash, not commit position — stamp the recording with the tree hash, have the gate compare that so a no-op commit needs no re-record (most principled; also lets methodology drop the "record AFTER final commit" rule entirely). (2) Add a restamp path: `test-evidence record --restamp`/`--no-rerun` that updates only HEAD/metadata association iff the tracked+test-file content hash matches the last recording. (3) Expose `--from-junit` in the multi-component recorder so an already-completed pytest/vitest run can be ingested instead of re-run. (4) Short-circuit `record` when the tree hash equals the last recording's. (user — upstream report from scriob)

- **[STH-3W7F]** Stop gate blocks session end while a tracked background workflow/task is still producing the diff
  `effort: M · impact: M · area: stop-hook · source: user · added: 2026-06-04 · status: shipped · stage: ready · closed-by: stop-gate-defer · related: STH-7K2A · reviewed: 2026-06-25`

  Filed by a Hallucinote session (`incoming-bugs/stop-gate-blocks-on-in-flight-background-work.md`) and
  **confirmed firsthand** in the roi-batch-2 session: the `critic-review` + `reflection` Stop gates fire
  on "tracked files changed, no Critic/reflection yet" with NO awareness of in-flight background work.
  While a background `Workflow`/`Task` is still generating the diff, ending the turn (the natural thing
  while awaiting an async run) trips the block, and every subsequent yield re-fires it until the job
  completes (roi-batch-2 absorbed ~15 block-loops over the ~12-min HOOK lane). The two available
  outcomes both misfit: SPIN (absorb a block every turn) or WAIVE — but `.gates-waived` means "cannot be
  satisfied THIS session" (`docs/waivers.md`), which is FALSE here (the gate WILL be satisfied minutes
  later), so waiving overloads the semantics and pollutes the archive with a "can't satisfy" reason for
  work that was satisfied. Distinct from [STH-7K2A] (a same-signature loop COUNTER that escalates/
  downgrades after N fires): this is about *deferral when a live tracked job exists*, not loop-counting —
  though a unified design could cover both. Remediation options (from the report): (1) background-aware
  deferral — before blocking, the Stop hook checks for a live tracked background job (workflow run dir /
  task registry) and DEFERS, re-running the gate on the next Stop after completion; (2) a first-class
  `.gates-deferred` state (reason + expected-completion) distinct from a waiver, so the archive records
  "deferred pending async run"; (3) minimal — sanction an in-flight-work waiver reason-prefix in
  `docs/waivers.md` to stop the semantic overload. Open design problem: the Stop hook is a subprocess and
  has no guaranteed handle on "is a Workflow still running" — the detection signal (a live workflow run
  dir under the session dir?) is harness-version-dependent and needs verification before (1) is viable;
  (3) is the cheap, safe floor. Filed 2026-06-04. (user)

  **DESIGN + safe floor shipped (evidence-deferral, 2026-06-04 — chunk 02).** Investigation
  corrected the framing: the report's option (3) "sanction an in-flight WAIVER" is actually WRONG —
  waiving the Critic gate while background work is in flight would SKIP the Critic the completed
  work still needs (the waiver persists the session, auto-clears next). So the agent is NOT forced
  to choose between two bad options: SPIN is the *correct* behavior (wait, then run the Critic when
  the job lands); the only real defect is the NOISE of repeated harmless blocks during a legitimate
  wait. Shipped floor: `methodology/building.md` Gate-waivers now states "in-flight background work
  is NOT a waiver case — wait, don't waive," so the semantic-overload temptation is removed.
  Detection finding (rules out option 1 for now): the Stop hook (`prawduct-hook stop`) does NOT read
  stdin, so it has no `transcript_path`/`session_id`; even if it did, inspecting
  `subagents/workflows/*/journal.jsonl` can't distinguish a LIVE run from a CRASHED one (`started >
  result` matches both; the journal persists after completion) — harness-version-dependent, unsafe
  to build. Recommended REAL fix (option 2, refined): a SELF-DECLARED `.prawduct/.gates-deferred`
  file (the AGENT knows it launched background work; the hook can't detect it) that the Stop hook
  honors to defer the gate EXACTLY ONCE, then auto-rearms (clears itself on the deferred fire) — so
  it quiets the wait WITHOUT ever permanently skipping the Critic (the next Stop re-checks normally;
  the harness's pending-background-work keeps the session alive across the deferred fire). Distinct
  archive semantics from a waiver ("deferred pending async run," not "unsatisfiable"). This needs a
  Stop-hook code change + a guard test that a deferred gate re-arms; deferred from the doc-floor
  chunk on proportionality. Could unify with [STH-7K2A] (both quiet a re-firing gate). (builder)

  Groom 2026-06-10: design is done and the floor shipped — the remaining work is just the
  `.gates-deferred` one-shot deferral (Stop-hook code + re-arm guard test). Effort dropped L → M;
  stage advanced to ready.

  RESOLUTION (2026-06-25, closed-by=stop-gate-defer): the remaining `.gates-deferred` one-shot
  deferral — the code fix left pending after the 2026-06-04 floor+design (chunk 02) — shipped, so the
  item is fully delivered and archived. The earlier `partial:` metadata note ("floor+design shipped
  via #60 (code fix pending)") is superseded by this completion; the floor+design history above is
  preserved verbatim.

- **[VWS-7N3K]** regen-views aborts the entire regen (release-notes + scope_rollups never written) when no build plan resolves; YAML-null pointer reads as the string "null"
  `effort: M · impact: H · area: views · source: report-bug · added: 2026-06-24 · status: shipped · stage: ready · closed-by: regen-views-null-plan · related: STH-5P2W, REL-4T8N, BLD-4Q9X · refs: lib/core.py (read_str_yaml_key, resolve_build_plan_path), lib/views.py (_plan_status_results, plan_regen), bin/prawduct-hook (inline _read_str_yaml_key / _resolve_build_plan_path mirrors + regen-views handler), incoming-bugs/archive/regen-views-aborts-whole-regen-when-no-build-plan-resolves.md, incoming-bugs/archive/regen-views-aborts-when-active-build-plan-is-yaml-null.md · reviewed: 2026-06-24`

  On a clean release boundary — change-log carries `status=shipped | release=vX` entries but no build plan resolves and `active_build_plan` is `null`/unset — `prawduct-hook regen-views` raises `FileNotFoundError: build-plan not found at .prawduct/null` and exits 2 BEFORE regenerating `release-notes.md` or the `scope_rollups` block. Those two views depend on NO build plan, yet a missing/absent plan aborts the whole command, blocking `docs/release-process.md` step 3 on a clean release; the consumer-facing release-notes silently goes stale. Two independent, complementary layers:

  (1) NULL LITERAL NOT NORMALIZED (originating). The column-0 pointer reader `read_str_yaml_key` (lib/core.py ~145-166) maps only EMPTY to None (`return value or None`); the truthy string `"null"` survives, so `resolve_build_plan_path` (lib/core.py ~221-226) returns `.prawduct/null` (a path that never exists). The codebase already handles this elsewhere — `_parse_build_plan_frontmatter_scope` (lib/views.py ~353) does `if not value or value.lower() in ("null","~")` — the pointer reader just doesn't mirror it. The inline `_read_str_yaml_key`/`_resolve_build_plan_path` mirror in bin/prawduct-hook has the same gap, which is why the SessionStart briefing emits the spurious `active_build_plan points at a MISSING file: 'null' resolved to .prawduct/null` warning (the STH-5P2W loud guard mis-firing on an explicit YAML-null opt-out).

  (2) ZERO-PLAN RESOLUTION ABORTS THE WHOLE REGEN. `_plan_status_results` (lib/views.py ~876-922) builds plan_paths from (a) scope-tagged release-pending plans and (b) the active_build_plan pointer plan; when BOTH are empty it enters the back-compat single-plan branch and `raise FileNotFoundError(...)`. `plan_regen` (lib/views.py ~994) calls it FIRST, before the release-notes (~997) and scope-rollups steps, so the exception takes down views that have nothing to do with build plans; bin/prawduct-hook's regen-views handler catches FileNotFoundError and exits 2 (~1559-1567). This back-compat contract predates REL-4T8N's multi-scope model, under which "no plans to update" is a legitimate clean-release state, not an error. NOTE: fixing only layer 1 is insufficient — a normalized None pointer falls back to DEFAULT_BUILD_PLAN_REL (artifacts/build-plan.md), also absent in these repos, so _plan_status_results still raises. BOTH layers need addressing.

  FIX-SHAPE (two complementary changes; either alone is a real improvement):
  - Normalize the YAML null literal at the pointer reader: treat `null`/`~` as None in read_str_yaml_key (or at minimum in resolve_build_plan_path + the bin/prawduct-hook inline mirror, kept in parity), the same way _parse_build_plan_frontmatter_scope already does. Makes `active_build_plan: null` behave like absent/empty, silences the spurious briefing warning, makes "no active plan" expressible in canonical YAML. WATCH the parity test pinning read_str_yaml_key semantics — this is a value-normalization change, not a parse change.
  - Make the status view degrade gracefully: when plan_paths is empty, _plan_status_results returns an empty/noop result (or plan_regen isolates the status step) so plan-independent release-notes + scope_rollups still regenerate. The hard FileNotFoundError back-compat contract should fire only when a plan is genuinely EXPECTED (an explicitly-pinned but missing active_build_plan), not when the project opted out of an active plan / has no resolvable plan — gate it on views_enabled + an explicitly-pinned-but-missing pointer, not on the absence of any plan.

  EVIDENCE: Reported twice from the Hallucinote repo (gitflow on develop, views_enabled, build plans without `scope:` frontmatter, no default artifacts/build-plan.md): first at prawduct v2.1.8 during the v1.6.0 release (severity medium, worked around by temporarily pointing active_build_plan at an already-shipped plan, running regen-views, then restoring null); again at v2.2.0 cutting v1.6.1 (severity escalated to high, worked around by invoking lib.views.build_release_notes_view + build_scope_view directly and writing their byte-identical outputs, skipping only the status step). Root cause traced and verified against source both times. ALSO LIVE IN THE FRAMEWORK REPO ITSELF — this session's SessionStart briefing fired the exact `'null' resolved to .prawduct/null` warning. Both incoming reports archived under incoming-bugs/archive/. Deduped from two upstream report-bug filings of the same two-layer defect (recurred across the v1.6.0 and v1.6.1 releases). (report-bug)

  RESOLUTION (2026-06-24, closed-by=regen-views-null-plan, branch fix/regen-views-null-plan-resolution): both layers landed. (1) `read_str_yaml_key` + the bin/prawduct-hook inline mirror normalize the YAML `null`/`~` literal to None. (2) `_plan_status_results` returns a no-op instead of raising when no plan resolves and the pointer is unset/null, while still raising for an explicitly-pinned-but-missing pointer. 14 new/updated tests; full suite 1449 passed, 1 skipped; dogfooded on this repo (regen-views now exits 0 with active_build_plan: null).

- **[GOV-9K2T]** Review the doctor vs janitor scope boundary — clarify the responsibility split and eliminate apparent overlap
  `effort: M · impact: M · area: governance/tooling · source: user · added: 2026-06-24 · status: shipped · stage: research · closed-by: doctor-janitor · refs: skills/doctor/SKILL.md, skills/janitor/SKILL.md, .prawduct/cross-cutting-concerns.md · reviewed: 2026-06-24`

  Surfaced during the api-design cross-cutting work, where the new API-versioning concern landed in BOTH a `/prawduct:doctor` check (#9) and a `/prawduct:janitor` theme — exposing that the line between the two skills is fuzzy. Both are framed as "health check": doctor = "health-check, repair, and maintain an already-onboarded Prawduct repo"; janitor = "periodic codebase maintenance — systematic health check across VCS hygiene, code quality, docs, tests, deps, controllability."

  Hypothesis to confirm or redraw: doctor = prawduct GOVERNANCE/install health (is this repo correctly set up and governed — install reference, distribution, anchor, core state, discovery captured, gitignore contract); janitor = the product's OWN codebase craft health (is the code/docs/tests well-maintained).

  Audit for: (1) duplicated/overlapping checks across the two skills; (2) a clear rule for which skill a new concern belongs to (or legitimately both, and why); (3) whether the API check should stay in both or consolidate. Research-stage — investigation/audit, not yet a buildable task; route to discovery to advance the stage. (user)

<!-- Bundle: test-evidence cluster — shipped in v2.1.8 (scope=test-evidence, #104).
     Shared surface: `prawduct-hook test-evidence record` (bin/prawduct-hook).
     TST-4K2P is the spine (content-based freshness identity); TST-7M3K folds in
     double-execution (--from-junit); TST-2H9P folds in configurable --tests-dir.
     Governance-protected (bin/, lib/, skills/) → full Critic + PR review. -->

- **[TST-4K2P]** Make test-evidence freshness content-based, not commit-SHA-based — a pre-commit record must not read as stale
  `effort: M · impact: L · area: test-evidence · source: user · added: 2026-06-22 · status: shipped · stage: design · related: TST-6V2N, TST-7M3K, TST-2H9P · refs: bin/prawduct-hook, lib/gates.py, skills/pr/review-protocol.md, skills/critic/review-cycle.md · closed-by: test-evidence · reviewed: 2026-06-22`

  **URGENT** (user: "a huge pain for all users", "a constant annoyance" — flagged 2026-06-22). High impact: affects every product using the prawduct PR/review flow.

  **Bundle spine** (picked 2026-06-22 with TST-7M3K + TST-2H9P → one design + build plan): the content-hash *scope decision* this item must make ("which files are test-relevant inputs") is the same question TST-2H9P answers for --tests-dir, and the runner-ownership choice in TST-7M3K decides *when* the hash is computed. Design all three in one pass.

  Problem: `prawduct-hook test-evidence record` stamps `git_sha` = HEAD at record time, but it tests the WORKING TREE (HEAD + uncommitted edits). So the natural flow "edit → run suite → record → commit" stamps the PRE-commit SHA; after committing, the stamp lags HEAD. Consumers that read the stamp then judge the evidence stale even though its CONTENT tested exactly what's shipping — the PR reviewer flagged this as a WARNING on PR #101 ("evidence ran against a tree without the fix"; false — the tree had the fix, uncommitted), and it recurs on every branch unless you remember to record AFTER committing (hit twice in the 2026-06-22 session: A1 and the critic-protocol-budget bump). The mismatch is structural, not user error.

  Proposed direction (user): judge freshness by CONTENT, independent of commit status — stamp a hash of the test-relevant file contents instead of (or alongside) `git_sha`. Then "edit → record → commit" stays current (the commit doesn't change content), and an amend/rebase/cherry-pick doesn't falsely invalidate.

  KEY design decision (why stage:design, not ready): the hash MUST be scoped to test-relevant inputs (source + tests + test config), NOT the whole tree — a naive whole-tree content hash would invalidate evidence on every `.md` edit and destroy the CRT-7M2D docs-only allowance (a doc tweak after a clean review currently rides free, and SHOULD). Options for the scope: all tracked non-`.md` non-metadata files; a declared `tests_dirs:`/source glob; or language-native coverage inputs. Decide the scope, then content-hash that set.

  Consumers to reconcile (all currently key off git_sha / commit-coverage): `test-status` (the reader), the PR-reviewer Merge-Hygiene freshness check (`skills/pr/review-protocol.md`), the Critic Goal-1 test-status check, and the cumulative-gate's HEAD-covering + CRT-7M2D docs-only-since logic in `lib/gates.py` (git_sha-based — reconcile content-freshness with the gate's commit-coverage requirement; they answer different questions).

  ~~Stopgap until shipped: record test-evidence as the LAST step, after committing, on a clean tree.~~ **SUPERSEDED (TST-4K2P, v2.1.8 + test-evidence-single-run, v2.2.3):** `git_sha` was retired and freshness is session-scoped timestamp-only, so a commit (even a no-op) does not stale evidence — record ONCE at Verify, never re-record after committing (see methodology/building.md and learnings.md:270-272). Surfaced by TEL-4M9X (A1) and critic-protocol-budget; part of the review-streamlining track.

  Cross-product corroboration + digest-mechanism suggestion (from upstream report test-evidence-git-sha-pins-parent-commit-when-tree-is-dirty.md, Scriob/halcyon, v-2026-06): a SECOND product independently hit this — record stamps git_sha=HEAD-at-record-time but tests the working tree, so in the natural 'run suite (dirty) → commit' order the stamp carries the PARENT sha (~50s wasted re-run, surfaced as a procedurally-correct-but-substantively-false Critic freshness WARNING). Concrete digest mechanism the report proposes for the content-hash: `git stash create`-style working-tree tree hash, OR a hash of (`git diff HEAD` + HEAD sha) — either makes the natural test→commit order first-class without a post-commit re-run. Corroborates the two 2026-06-22 Hallucinote hits this item already records.

- **[TST-7M3K]** test-evidence record re-runs the full suite the builder just ran — every stamp point pays for the suite twice
  `effort: M · impact: M · area: test-evidence · source: user · added: 2026-06-22 · status: shipped · stage: design · related: TST-4K2P, TST-6V2N, TST-2H9P · refs: bin/prawduct-hook (test-evidence record), methodology/building.md (Verify), incoming-bugs/archive/test-evidence-record-reruns-the-suite-the-builder-just-ran.md · closed-by: test-evidence · reviewed: 2026-06-22`

  **Bundled with TST-4K2P (spine) + TST-2H9P** (picked 2026-06-22 → one design + build plan): this is the runner-ownership leg — whether `record` runs the suite itself, accepts `--from-junit`, or `--reuse-last` determines *when* TST-4K2P's content hash is computed and which run produced the evidence.

  The build cycle says "run the suite, then record," but `test-evidence record` executes the entire suite itself rather than accepting the builder's run, so every stamp point triggers two back-to-back full-suite runs (~5 min/feature in Hallucinote). Pure wall-clock waste that scales with suite size × stamp frequency; a gate that costs double its necessary price trains the corner-cutting it exists to prevent. Distinct from TST-6V2N (created the record WRITER) and TST-4K2P (freshness IDENTITY, sha-vs-content) — this is record's double EXECUTION. Fix-shape (reporter ranks option 2): (1) record --from-junit <file> parses a runner-native junitxml the builder already produced; (2) record becomes the canonical runner (builder doesn't run separately); (3) --reuse-last. Pairs naturally with TST-4K2P's content-hash design — could be designed in one pass. Governance-protected → full Critic + PR review.

- **[TST-2H9P]** test-evidence record (F4a overlay) defaults --tests-dir to repo-root tests/ — breaks engine-subdir / monorepo layouts, writing empty changes_referenced/tests_executed halves
  `effort: S · impact: S · area: test-evidence · source: user · added: 2026-06-22 · status: shipped · stage: design · related: TST-4K2P, TST-7M3K, TST-6V2N · refs: bin/prawduct-hook (test-evidence record, bin/test-reference-verify --merge-into --tests-dir), incoming-bugs/archive/check-pr-trivial-passes-feature-clusters-that-only-touch-existing-files.md · closed-by: test-evidence · reviewed: 2026-06-22`

  **Bundled with TST-4K2P (spine) + TST-7M3K** (picked 2026-06-22 → one design + build plan): the configurable --tests-dir / source-scope this item needs is the SAME "which files are test-relevant inputs" decision TST-4K2P's content-hash scope must make — design the layout knob once and both consume it.

  Secondary finding harvested from the check-pr-trivial report (Scriob, polyglot monorepo with the engine in engine/). The test-evidence record F4a overlay step (bin/test-reference-verify --merge-into) defaults --tests-dir to repo-root tests/; with tests in engine/tests it writes an EMPTY changes_referenced/tests_executed half → false verify-coverage missing-coverage and a cumulative-Critic BLOCKING. This is the next layer after TST-6V2N ("reader without a writer" — the writer now exists but assumes repo-root tests). Worked around in-repo with a wrapper passing --tests-dir engine/tests, but the hook itself can't be told the tests dir. Fix-shape: make tests-dir configurable (a project-state.yaml knob, e.g. tests_dir:) and/or auto-detect from the layout; thread it through record's overlay. Governance-protected → full Critic + PR review.

- **[STH-5R2Q]** Flag-only `prawduct-hook` subcommands silently ignore unknown positional arguments
  `effort: S · impact: M · area: governance/cli · source: builder · added: 2026-06-10 · status: shipped · stage: ready · refs: bin/prawduct-hook · related: STH-9V4K · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  `prawduct-hook audit-learnings` (and any flag-only subcommand) silently ignores unknown positional
  arguments; this hid a test bug where `tmp_path` was passed positionally and the real repo was audited
  instead (found 2026-06-10 during review-proportionality ch.04). Tighten flag-only subcommand arg
  parsing to reject unknowns, matching ledger-append/review-stats/classify-diff-risk fail-closed arg
  handling. (builder)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[TST-3E8V]** `cmd_test_evidence` catches only FileNotFoundError for a declared test_command — widen to OSError
  `effort: S · impact: S · area: tests/runtime · source: critic · added: 2026-06-10 · status: shipped · stage: ready · refs: bin/prawduct-hook (cmd_test_evidence), tests/test_plugin_runtime.py (TestTestEvidenceKnobs) · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  `cmd_test_evidence` wraps the declared `test_command` launch in `except FileNotFoundError` only,
  so a *missing* executable gets the clean exit-2 path but a *non-executable* target raises
  PermissionError and tracebacks instead. Fix-shape: widen the except to `OSError`
  (FileNotFoundError and PermissionError are both subclasses) so any OS-level launch failure takes
  the same clean exit-2 path; add a non-executable-target case alongside the existing
  `TestTestEvidenceKnobs` coverage. Filed from the cumulative Critic NOTE on the gate-soundness
  bundle, 2026-06-10. (critic)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[REL-7P3X]** stamp-merged branch guard rejects origin/-prefixed base_branch configs
  `effort: S · impact: S · area: governance/release · source: critic · added: 2026-06-10 · status: shipped · stage: ready · refs: bin/prawduct-hook · related: PR-2H8N · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  cmd_stamp_merged (bin/prawduct-hook) compares the raw `base_branch` value from project-state.yaml
  to `git rev-parse --abbrev-ref HEAD` output; works for bare `develop` (this repo) but
  project-state.yaml's own comment calls `origin/develop` "preferred", and an origin/-prefixed value
  would make stamp-merged refuse permanently while resolve-base normalizes fine. Fix-shape: strip a
  leading `origin/` from the configured value before comparing (the guard compares local branch names
  by design — deliberate divergence from `_resolve_base_branch` is on record in the 2026-06-10
  chunk-02 Critic findings). Source: PR #90 reviewer NOTE (fable, escalate tier), same family as
  PR-2H8N. (critic)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[STH-9T4F]** Convert the two remaining non-atomic .prawduct state writes to core.atomic_write_text
  `effort: S · impact: S · area: stop-hook · source: builder · added: 2026-06-10 · status: shipped · stage: ready · related: STH-8M3V · refs: lib/critic_marker.py, lib/operator_verification.py, lib/core.py · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  Convert the two remaining non-atomic .prawduct state writes to core.atomic_write_text:
  lib/critic_marker.py:75 (critic-active marker payload) and lib/operator_verification.py:251
  (operator-verification queue rewrite). Found during STH-8M3V (gate-hardening ch.02), which
  converted the four audited sites and added the shared helper; these two were out of that item's
  groomed scope. Same rationale: readers fail open, torn writes misfire governance silently.
  (builder)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[BLD-4K7P]** `verify-chunk-refs` over-matches inline-code/prose tokens in build-plan chunk sections, producing false "missing-ref" positives
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-20 · status: shipped · stage: ready · related: BLD-2R9X, BLD-8F2Q, BLD-5V8F · refs: bin/prawduct-hook (cmd_verify_chunk_refs / _parse_build_plan_chunk_refs) · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  The Goal-2 ref-drift check (`cmd_verify_chunk_refs` / `_parse_build_plan_chunk_refs`) extracts
  backticked paths from a chunk's section and asserts they exist on disk. It misparses tokens that
  are NOT deliverables: env-var names (`PRAWDUCT_BUG_INBOX`), write-target templates with angle
  brackets (`<inbox>/<kebab-slug>.md`), URLs (`https://...`), and intentionally-gitignored paths
  (`.prawduct/.bug-inbox`). Surfaced during the upstream-bug-reporting cumulative review (HEAD
  befbcb8) — 4 false missing-ref lines, all adjudicated NOT blocking by the Critic. Fix-shape:
  tighten the extractor to skip non-path-shaped tokens (contains `<>` or `://`, or matches a
  known-gitignored managed entry), so the `new`-prefix convention is only needed for genuinely
  created files. Also a candidate learning: a ref-existence heuristic over backticked spans must
  exclude placeholder/templated/gitignored tokens or it cries wolf on legitimate plans. Same
  parser family as the shipped BLD-2R9X (glob metacharacters) and BLD-8F2Q (`path::symbol`); this
  covers token classes those two fixes don't reach. (critic)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[STH-6Q9D]** Batch git subprocess fan-out on SessionStart/Stop hot paths
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: shipped · stage: ready · refs: bin/prawduct-hook, lib/gitstate.py · closed-by: hot-path-git-batching · reviewed: 2026-06-22`

  From the 2026-06-09 framework review. cmd_clear runs ~20+ serial subprocesses (~940ms here; 5-10s
  risk on monorepos): _untrack_session_files issues 1 + up to 14 git ls-files --error-unmatch calls
  every session start (replace with one batched 'git ls-files -- <paths>'); 'git status --porcelain'
  is re-run 4-5x per clear and >=3x per stop (capture once per invocation and pass down);
  _has_product_code (lib/gitstate.py) walks the full tree via rglob including node_modules/.git
  before filtering (use pruned os.walk or git ls-files). (builder)

  Groom 2026-06-10: partial fix landed in v2.1.0 (#89 removed the no-change-session `gh pr list`).
  Remaining hot-path cost per the audit: _untrack_session_files (up to 15 git ls-files + 15 git rm
  --cached per SessionStart, bin/prawduct-hook ~L291-339 — batch into one ls-files + one rm),
  repeated `git status --porcelain` per clear/stop (capture once, pass down), and _has_product_code
  rglob walking node_modules before filtering (lib/gitstate.py ~L219-227). Still stage: ready.

  Shipped 2026-06-22 in v2.1.8, scope=hot-path-git-batching (#106).

- **[STH-4K7N]** Governance gates + critic/pr skills don't compose with git worktrees — hooks resolve `.prawduct/` to the launch dir, agent side to the session worktree
  `effort: M · impact: M · area: stop-hook · source: user · added: 2026-06-20 · status: shipped · stage: ready · related: CRT-8D2W · refs: bin/prawduct-hook, hooks/digest.py, hooks/banner.py, incoming-bugs/governance-gates-and-critic-pr-skills-dont-compose-with-git-worktrees.md · closed-by: worktree-compat · reviewed: 2026-06-22`

  Hooks resolve `.prawduct/` to the launch dir (`CLAUDE_PROJECT_DIR`) while the agent side resolves
  to the session worktree (cwd), so worktree-written reflection/critic/cumulative records are
  invisible to the Stop + cumulative-critic gates (false blocks), forcing every worktree work cycle
  off-protocol. Full fix approved: worktree-aware `get_project_dir()` resolution (stdin cwd →
  `os.getcwd()` → `CLAUDE_PROJECT_DIR` via `git rev-parse --show-toplevel`) in `bin/prawduct-hook` +
  `hooks/digest.py` + `hooks/banner.py`, empirical hook-cwd confirmation + regression tests, and
  methodology guidance to run critic/pr from the worktree. (user)

  Shipped 2026-06-22 in v2.1.8, scope=worktree-compat (#107). `lib.gitstate.resolve_project_dir`
  makes the project dir follow the session into its worktree (`git rev-parse --show-toplevel` of cwd,
  preferred over the `CLAUDE_PROJECT_DIR` pin only when cwd is a worktree of the same repo, failing
  open on any git error); `get_project_dir` delegates to it across `bin/prawduct-hook` +
  `hooks/digest.py` + `hooks/banner.py`. The broader "no documented supported worktree workflow"
  remediation (the methodology/documentation leg) remains open under CRT-6W2N, which was reframed
  2026-06-22 to the docs/methodology gap once the code-resolution leg was confirmed sound.

- **[CRT-5T8N]** Single-owner the Learnings Cross-Check & Backlog Reconciliation shared by the cumulative-Critic and the PR reviewer
  `effort: S · impact: S · area: critic · source: user · added: 2026-06-22 · status: shipped · stage: ready · related: TEL-6P2D · refs: skills/critic/review-protocol.md, skills/pr/review-protocol.md · closed-by: single-owner-shared-checks · reviewed: 2026-06-22`

  Problem: After the consume-and-audit redesign (PR reviewer audits the Critic record instead of
  re-deriving code soundness), two checklist items are still performed by BOTH the cumulative/final
  Critic and the PR reviewer: (1) Learnings Cross-Check (both scan learnings.md) and (2) Backlog
  Reconciliation (Critic does it; PR reviewer does a data-consistency variant). This duplicates prompt
  scope across two agents. It saves prompt tokens/focus, NOT wall-clock (no review run is removed) — a
  tidy, not a needle-mover; scope accordingly.

  Approach:
  - B0 (validate FIRST — Principle 15): diff the two protocols' checklists and confirm the overlap is
    TRUE duplication, not complementary work. Specifically check whether the PR reviewer's
    release-coherence/data-consistency check (change-log ↔ version ↔ backlog) catches something the
    Critic's reconciliation does not. Do NOT dedup complementary checks. If complementary, close B as
    "no-op, confirmed complementary."
  - B1: assign single ownership for the genuinely-duplicated parts — Critic owns the Learnings
    Cross-Check and the substantive Backlog Reconciliation; the PR reviewer cites the Critic's result /
    does only the thin release-coherence delta. Edit skills/critic/review-protocol.md and
    skills/pr/review-protocol.md to state the single owner explicitly.

  Assurance: must NOT drop any check — only relocate it to exactly one owner.
  Acceptance: each of the two checks has exactly one named owner across the two protocols; nothing
  silently dropped; the PR reviewer protocol explicitly references the Critic's result for the
  relocated checks. Governance-protected files (skills/) → full Critic + PR review. (user)

  Shipped 2026-06-22 on branch feature/single-owner-shared-checks: scoped the PR reviewer's
  Learnings Cross-Check + Backlog R-1 to the consumed Critic record; R-2 stays unconditional;
  review-cycle.md names final/cumulative as owner; 2 guard tests; cumulative Critic clean, PR
  reviewer clean. Archived on-branch per the ship-in-PR contract so it rides in the closing PR.
  closed-by is the branch/feature scope name (a pre-commit handle, not a SHA).

- **[TEL-4M9X]** Normalize model-id strings in the governance ledger so review-stats can analyze the model dimension
  `effort: S · impact: M · area: telemetry · source: user · added: 2026-06-22 · status: shipped · stage: ready · related: TEL-6P2D · refs: lib/telemetry.py, .prawduct/.governance-ledger.jsonl, .prawduct/artifacts/reviewer-model-ab-2026-06-10.md · closed-by: telemetry-model-id-normalization · reviewed: 2026-06-22`

  Problem: `review-stats` aggregates by `role × model × mode`, but the SAME model is recorded under
  several id strings — `opus`, `claude-opus-4-8`, and `claude-opus-4-8[1m]` are all the same model,
  while `fable`/`sonnet` are genuinely different. This fragments the model dimension into noise. The
  2026-06-22 review-stats run split critic-opus reviews across three buckets (1 + 6 + others), making
  per-model yield unreadable — which defeats the exact A/B question the telemetry was built to answer
  (see reviewer-model-ab artifact).

  Approach:
  - Canonicalize the model-id at the aggregation key in lib/telemetry.py (read-time fold) AND at
    write-time where the review.* ledger event is created, so new events are clean and the existing 41
    immutable events still aggregate correctly without rewriting the append-only ledger.
  - Collapse opus aliases (`opus`, `claude-opus-4-8`, `claude-opus-4-8[1m]`) → one canonical `opus`
    family label; keep `fable`, `sonnet`, `haiku` distinct; unknown id → passthrough.
  - Put the mapping in ONE shared helper so future model ids are a one-line add.

  Assurance impact: pure measurement/observability fix — changes no gate behavior and adds no review
  runs. Zero assurance risk.

  Acceptance:
  - review-stats shows opus variants collapsed to one bucket per (role, mode); fable stays separate.
  - The historical 41 events aggregate correctly with NO rewrite of the ledger file.
  - Unit test covers the canonicalization map (opus aliases→opus; fable→fable; unknown→passthrough).

  Open decision: normalize the aggregation key only vs. add a persisted `model_family` field —
  recommend aggregation-key normalization + shared helper (lighter; preserves the raw string). This is
  the FIRST deliverable of the evidence-driven-pruning track and must land before any per-model or
  per-leg pruning can be data-justified. Being started immediately (will be promoted on a feature
  branch off develop). (user)

  Shipped 2026-06-22 on branch feature/telemetry-model-id-normalization (lib/telemetry.py
  `_canonical_model` fold + 4 tests + docs/governance-telemetry.md + change-log entry; full suite 1355
  passed). Archived on the branch per the ship-in-PR contract so it rides in the closing PR.

- **[BKL-9K4T]** Reconcile the `closed-by:` contract with non-chunk/bare-commit work — define a stable on-branch handle and warn on the amend-dangle footgun
  `effort: S · impact: S · area: backlog · source: user · added: 2026-06-21 · status: shipped · stage: ready · related: REL-7P3X, PR-2H8N · refs: incoming-bugs/archive/backlog-closed-by-cannot-reference-its-own-commit.md, skills/backlog/SKILL.md, templates/backlog.md · closed-by: backlog-closed-by-handle · reviewed: 2026-06-21`

  Upstream report (puzzles repo via Hallucinote, prawduct v2.1.5;
  `incoming-bugs/archive/backlog-closed-by-cannot-reference-its-own-commit.md`). The `closed-by:` field is
  contracted as `<chunk-id|tag>` — an identifier that exists **before** the commit (backlog SKILL.md
  item-shape contract, the `update … closed-by=<change-log tag or chunk id>` step, and the
  `templates/backlog.md` legend line, reported as SKILL :30/:61 + template :45 in v2.1.5). That holds
  for chunked/released work, but prawduct also legitimately ships **non-chunk** items (refactors,
  chores, debt paydown) whose only stable "what shipped this" handle is the commit SHA — and a bare
  SHA is a footgun: a `git commit --amend` that folds `backlog.md` into the ship commit rewrites the
  SHA (dangling ref), and a commit cannot contain its own final SHA (chicken-and-egg), so recording
  `closed-by` correctly forces an extra "fix closed-by ref" commit.

  Fix-shape (reconcile the contract with the v2.1.6 on-branch ship rule, reported at :14): define the
  on-branch `closed-by` handle as the **branch/scope name** (or a change-log `date-slug` heading,
  which also exists before the commit) — never a bare SHA and never a PR# (assigned post-push, also
  unstable for an in-commit handle). Update the three contract sites (SKILL item-shape line, the
  `update … closed-by` step, the template legend) consistently, and have the `update <ID>
  closed-by=<bare-sha>` path **warn** about the amend-dangle and recommend the stable handle instead.
  Dedup note: distinct from REL-7P3X / PR-2H8N (release/PR-merge guard mechanics) — this is the
  `closed-by` provenance contract, not the merge flow. (user — upstream report)

- **[STH-2K8R]** `lib/critic_mode` could consume `lib/buildplan_refs` directly instead of mirroring its build-plan helpers
  `effort: S · impact: S · area: refactor · source: builder · added: 2026-06-07 · status: shipped · stage: ready · closes: CRT-3D9K · related: STH-9V4K, BLD-6Q1N · closed-by: PR #93 / v2.1.4 (bf0c889) · reviewed: 2026-06-10`

  `lib/critic_mode.py` carries independent re-implementations of `_current_chunk_id_from_status`,
  the chunk-`Type:` parser, and `_is_metadata_path` (and references `_parse_build_plan_status`),
  whose stated rationale is "no dependency on `bin/prawduct-hook` — re-implemented to stay importable
  from the slash-command shim" (critic_mode.py docstring ~L46). STH-9V4K ch.2–3 moved those helpers
  into `lib/gitstate` + `lib/buildplan_refs`, which `critic_mode` *already* imports siblings from
  (`from .core import resolve_build_plan_path`). So the mirror's reason-to-exist is now gone:
  `critic_mode` could `from .buildplan_refs import _current_chunk_id_from_status` (etc.) and
  `from .gitstate import _is_metadata_path`, deleting the duplicate bodies + their manual-sync
  docstrings. Defer until the decomposition (ch.4–7) lands so the lib surface is stable. NOT a
  behavior-preserving move (it changes critic_mode's structure + collapses a parity relationship),
  so it needs its own tests + Critic pass — kept out of ch.3 for scope discipline. Filed from the
  ch.3 buildplan_refs extraction on 2026-06-07. (builder)

  Critic note (review-fixes Chunk 1, 2026-06-09): lib/critic_mode.py contains a third porcelain
  parser that near-duplicates the new shared gitstate.parse_porcelain_line (quoted paths, renames);
  fold it onto the shared helper when consolidating this item's lib/critic_mode mirrors.

  Groom 2026-06-10: UNBLOCKED — the defer-until condition ("until the decomposition (ch.4–7) lands")
  is satisfied: STH-9V4K shipped in v2.0.14 (archived). The lib surface is stable; this is now
  directly actionable.

  — merged from CRT-3D9K (2026-06-10) — this item's consolidation closes CRT-3D9K by construction
  (CRT-3D9K's own text says so); CRT-3D9K's full original body is preserved on its archived entry.
  Audit 2026-06-10 confirmed critic_mode still carries its own _current_chunk_id_from_status
  (~L640), _count_build_plan_chunks (~L744, duplicate of lib/gates.py ~L633 — the BLD-6Q1N pair),
  and an inline porcelain parse in _get_uncommitted_code_files (~L462-474) that does NOT use
  gitstate.parse_porcelain_line despite importing gitstate. One consolidation pass closes STH-2K8R +
  CRT-3D9K + the porcelain remnant; do BLD-6Q1N in the same pass.

  Promoted 2026-06-10 into `artifacts/build-plan-critic-mode-consolidation.md` (branch
  `feature/critic-mode-consolidation`) — one consolidation chunk covering STH-2K8R + BLD-6Q1N.

  Shipped 2026-06-10 in v2.1.4 (PR #93, commit bf0c889, squash-merged to develop). Carries
  `closes: CRT-3D9K` (already archived) — CRT-3D9K's closure rides this anchor: the consolidation
  that closed it by construction shipped in PR #93 / v2.1.4.

- **[BLD-6Q1N]** Extract `_iter_status_section_items` shared parser for build-plan Status
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-08 · status: shipped · stage: ready · refs: lib/gates.py, lib/critic_mode.py, lib/buildplan_refs.py · related: STH-2K8R · closed-by: PR #93 / v2.1.4 (bf0c889) · reviewed: 2026-06-10`

  `_count_build_plan_chunks` (bin/prawduct-hook lines ~2073-2113, added v1.3.13) duplicates the Status-section parsing skeleton of `_parse_build_plan_status` (lines ~1021-1099): same `## Status` detection, same HTML-comment skip, same exit on next `## ` heading. Two callers is borderline; if a third caller appears (e.g., a future stop-hook check that needs chunk metadata), extract to `_iter_status_section_items(prawduct_dir) -> Iterator[StatusItem]` and refactor both call sites. Filed from /critic NOTE on 2026-05-08. (critic)

  Groom 2026-06-10 — refs refreshed post hook-decomposition (STH-9V4K, v2.0.14) and the premise is
  now STRONGER: `_count_build_plan_chunks` exists as near-duplicate copies in BOTH `lib/gates.py`
  (~L633) and `lib/critic_mode.py` (~L744), alongside `_parse_build_plan_status` in
  `lib/buildplan_refs.py` (~L31). The third-caller threshold the item set is effectively met;
  natural home for the shared iterator is lib/buildplan_refs. Overlaps the STH-2K8R consolidation —
  consider doing both in one pass.

  Promoted 2026-06-10 into `artifacts/build-plan-critic-mode-consolidation.md` (branch
  `feature/critic-mode-consolidation`) — one consolidation chunk covering STH-2K8R + BLD-6Q1N.

  Shipped 2026-06-10 in v2.1.4 (PR #93, commit bf0c889, squash-merged to develop) — one
  consolidation chunk with STH-2K8R.

- **[STH-4F7C]** Extract the duplicated Critic-freshness gate (cmd_stop vs briefing) to lib/gates.py — copies have already diverged
  `effort: S · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: shipped · stage: ready · related: STH-9V4K, STH-6B4R, STH-2K8R · refs: bin/prawduct-hook, lib/briefing.py, lib/gates.py · closed-by: feature/gate-hardening ch.01 (04f571a) · reviewed: 2026-06-10`

  From the 2026-06-09 framework review. The mtime-vs-session-start freshness check is duplicated
  nearly verbatim (including the same STH-6B4R comment block) in cmd_stop (bin/prawduct-hook) and
  briefing._check_previous_session_gates (lib/briefing.py). Unlike the hook's intentional inline
  mirrors, this pair has no parity test and has already diverged: cmd_stop gained the
  verify-resolutions scope check; the briefing copy did not. The briefing copy lives in lib/
  already, so the import-light hot-path rationale does not apply — extract to lib/gates.py and add
  a parity/regression test. (builder)

  Groom 2026-06-10 (audit): divergence re-confirmed and sharpened — cmd_stop runs the
  verify-resolutions scope check (bin/prawduct-hook ~L787-812) but
  lib/briefing._check_previous_session_gates (~L906-934) does not, so the session-start advisory
  can report a stale verify-resolutions record as satisfying. Still stage: ready.

  Shipped 2026-06-10 on feature/gate-hardening (chunk 01, commit 04f571a): shared session
  Critic-freshness gate extracted, advisory gains the scope check. Gate-hardening bundle, delivered
  and Critic-approved this session.

- **[STH-8M3V]** Atomic writes for .prawduct state files + guard unguarded hot-path I/O in cmd_clear
  `effort: S · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: shipped · stage: ready · related: STH-6Q9D, ADV-9K2T, STH-9T4F · refs: bin/prawduct-hook, lib/advisory_store.py, lib/gitstate.py, lib/briefing.py · closed-by: feature/gate-hardening ch.02 (cd644be) · reviewed: 2026-06-10`

  From the 2026-06-09 framework review. Only .test-evidence.json gets tmp + os.replace;
  .advisories.json (lib/advisory_store.py), .work-model-index.json, .session-start,
  .session-git-baseline, and .session-handoff.md are plain write_text — two concurrent sessions on
  the same repo (worktrees) can tear them. Readers fail open, so blast radius is a misfired gate,
  not a crash — still worth one shared atomic_write_text helper. Same pass: three unguarded I/O
  sites in cmd_clear (session-file unlink loop, .session-start write, baseline write) can traceback
  the SessionStart hook on an OSError, unlike the meticulously best-effort code around them;
  gitstate's _get_session_changed_files also lacks the (UnicodeDecodeError, OSError) guard its
  siblings have. (builder)

  Groom 2026-06-10 (audit): the unatomic set confirmed — .session-start + .session-git-baseline
  (bin/prawduct-hook ~L468, 563), .session-handoff.md (lib/briefing.py ~L868), .advisories.json
  (lib/advisory_store.py ~L333), and .gates-waived. One shared atomic_write_text helper covers all.
  Still stage: ready.

  Shipped 2026-06-10 on feature/gate-hardening (chunk 02, commit cd644be): atomic .prawduct state
  writes via shared helper + cmd_clear OSError resilience. Two out-of-scope sites spun off as
  STH-9T4F. Gate-hardening bundle, delivered and Critic-approved this session.

- **[CRT-2N7V]** /prawduct:critic explicit mode argument not honored — mode_chosen_by records inference rationale instead of explicit-args
  `effort: S · impact: M · area: governance/critic · source: builder · added: 2026-06-10 · status: shipped · stage: ready · related: CRT-3M8Q, CRT-7B4M, CRT-6J4P, CRT-9L2F · refs: skills/critic/SKILL.md · closed-by: feature/gate-hardening ch.03 (b5f0c2c) · reviewed: 2026-06-10`

  Observed 2026-06-10 on feature/do-next chunk 01: invoked the skill with args "chunk" but the
  forked Critic ran rule-1b verify-resolutions and recorded mode_chosen_by as the verbatim inference
  string, not "explicit-args" as skills/critic/SKILL.md documents. The $ARGUMENTS override path
  appears not to reach or not to be honored by the forked skill. Review validity was unaffected
  (superset scope) but the documented override contract is broken; investigate whether Skill-tool
  args reach $ARGUMENTS in forked execution. Possible regression/recurrence of CRT-3M8Q (shipped
  v2.0-era, closed-by #58), which fixed the same Skill-tool-args-don't-thread-to-$ARGUMENTS gap —
  verify whether that fix covers explicit args or only the plan-field override. (builder)

  Shipped 2026-06-10 on feature/gate-hardening (chunk 03, commit b5f0c2c): explicit mode arg now
  forwarded to infer-critic-mode; the skill never self-parses $ARGUMENTS. Post-release end-to-end
  verification tracked as CRT-9L2F. Gate-hardening bundle, delivered and Critic-approved this
  session.

- **[CRT-8W3F]** PR-gate ledger fallback accepts an arbitrarily old cumulative — no freshness/session check
  `effort: S · impact: M · area: governance/gates · source: critic · added: 2026-06-10 · status: shipped · stage: ready · related: CRT-4J8W, CRT-7M2D · refs: lib/gates.py (_ledger_fallback_record ~L1094-1121) · closed-by: feature/do-next ch.01 (59258bd) · reviewed: 2026-06-10`

  When the latest `.critic-findings.json` is wrong-mode (e.g. a chunk review overwrote the
  cumulative), check_cumulative_critic falls back to the NEWEST qualifying `review.critic` ledger
  event with no timestamp or session-freshness check — only commit-coverage. A days-old cumulative
  from prior work can satisfy the PR gate if only `.md` changed since, where the findings-file path
  would have demanded freshness. Fix-shape: require the ledger record's `ts >=` session start
  (mirroring the findings-file freshness model) or a bounded age, fail closed. Found by the
  2026-06-10 governance audit of the new v2.1.0 chain-gate code. Priority: do-next (gate soundness,
  S effort). (critic)

  Shipped 2026-06-10 on feature/do-next (scope=do-next, chunk 01, commit 59258bd); cumulative
  Critic passed with 0 blocking. Ledger fallback now requires envelope `ts >= .session-start`,
  failing closed on a missing marker or ts-less events.

- **[STH-5P2W]** Loud guard when a set active_build_plan pointer resolves to no file
  `effort: S · impact: M · area: stop-hook · source: critic · added: 2026-06-09 · status: shipped · stage: ready · related: REL-4T8N · refs: lib/core.py, bin/prawduct-hook, templates/project-state.yaml · closed-by: feature/do-next ch.02 (a5305c0) · reviewed: 2026-06-10`

  From review-fixes Chunk 1 Critic (2026-06-09). The active_build_plan pointer is
  .prawduct/-relative; a repo-relative value (the natural way to write it) mis-resolves and the
  resolvers (lib/core.py resolve_build_plan_path + the hook's inline mirror) silently fall back to
  the default plan path — disabling the Critic gate, plan-aware mode inference, and
  verify-chunk-refs with no signal. Happened live: the review-fixes planning commit shipped the
  mis-resolving form and the gates were blind for one work cycle until the Critic caught it.
  Fix-shape: when the pointer is SET but resolves to a nonexistent file, warn loudly in the session
  briefing (and/or accept repo-relative forms by stripping a leading .prawduct/) + test.
  Escape-hatches-create-silent-failures shape. (critic)

  Groom 2026-06-10 (audit): scope widened — besides the loud briefing warning + accepting
  repo-relative pointers, also document the `active_build_plan` field in
  templates/project-state.yaml: it is currently undocumented in the template a new product copies,
  and the audit found no schema guidance anywhere a product would look. Do-next priority.

  Shipped 2026-06-10 on feature/do-next (scope=do-next, chunk 02, commit a5305c0); cumulative
  Critic passed with 0 blocking. Repo-relative pointer now accepted (leading-prefix strip in both
  parity-pinned resolvers), loud briefing guard added for a set-but-missing pointer, and
  active_build_plan documented in templates/project-state.yaml.

- **[MET-6W3J]** learnings.md compaction: restore When-X-do-Y-because-Z brevity, move narrative to learnings-detail.md, add a size nudge
  `effort: M · impact: M · area: methodology · source: builder · added: 2026-06-09 · status: shipped · stage: ready · related: MET-5C2H, MET-7R4J · refs: .prawduct/learnings.md, .prawduct/learnings-detail.md · closed-by: feature/do-next ch.03 (b5439e1) · reviewed: 2026-06-10`

  From the 2026-06-09 framework review. learnings.md is ~28k tokens for 23 entries — individual
  entries run 300-600 words, drifting from the file's own stated format (rule in learnings.md, full
  context in learnings-detail.md). Every /prawduct:learnings lookup and Critic learnings cross-check
  pays this. Fix-shape: (1) compact each entry to the When/do/because rule plus a pointer into
  learnings-detail.md (move the narrative there — never delete it); (2) add a mechanical size check
  per this repo's own 'growing files need structural nudges to prune' learning (e.g. session-start
  warn when learnings.md exceeds a threshold, like the existing project-state.yaml 40KB warning).
  (builder)

  Groom 2026-06-10 (audit): learnings.md is now ~80KB on disk and growing; every
  /prawduct:learnings lookup and Critic learnings cross-check pays it. Do-next priority among the
  context-economy items.

  Shipped 2026-06-10 on feature/do-next (scope=do-next, chunk 03, commit b5439e1); cumulative
  Critic passed with 0 blocking. learnings.md 79.5KB → 32.3KB: 48 of 58 entries compacted,
  narratives moved verbatim to learnings-detail.md, navigation by same-heading convention; briefing
  size nudge added at 40KB. Drive-by fix: the briefing "Learnings (N rules)" line counted only
  bullets and reported 0 on entry-format files — now counts `##` entries.

- **[REL-9F2T]** Change-log lifecycle hardening — close the silent-drop family (statusless entries, missing entries, multi-tag entries, orphaned scopes)
  `effort: M · impact: L · area: governance/change-log · source: reflection · added: 2026-06-10 · status: shipped · stage: ready · closes: REL-2N8K, REL-6C3W, VWS-4D8J · related: VWS-3K7P, REL-4T8N, CRT-7B4M · refs: lib/views.py, skills/pr/SKILL.md, docs/release-process.md, .prawduct/artifacts/build-plan-changelog-lifecycle.md · closed-by: v2.1.1 · reviewed: 2026-06-10`

  The change-log state machine (statusless → merged → shipped) is broken at three transitions, all
  silent, all observed live: (a) the /prawduct:pr merge flow is documented to stamp `status=merged`
  but never does, so most entries reach release-prep statusless, and docs/release-process.md step 3
  literally says flip "`status=merged`" → statusless entries silently dropped (v2.0.14: 8 of 10)
  [REL-2N8K]; (b) a code-changing branch can merge with NO entry at all and nothing flags it
  (CRT-7B4M/#82, reconstructed at the v2.0.16 release) [REL-6C3W]; (c) lib/views.py
  parse_change_log stops at the FIRST `prawduct:` tag line per entry section, silently dropping
  later ones (v2.1.0 live: the reviewer-model-tiering chunks=02 tag nearly shipped unflipped)
  [VWS-4D8J]; (d) NEW from the 2026-06-10 audit: diagnose_scope_plan_coverage validates the
  scope=→plan mapping only for `status=merged` entries, so a statusless entry with a bad `scope=`
  is undetected until release. Fix as one scope: stamp `status=merged` in the /prawduct:pr merge
  step + reword release-process step 3 to "every unreleased entry, statusless OR merged"; add a
  release-prep/merge probe for code-changing diffs with no new entry; warn (or union) on multiple
  tag lines per entry; extend scope validation to statusless entries. Priority: do-next — this is
  the top release-integrity hole. Merged 2026-06-10 from REL-2N8K + REL-6C3W + VWS-4D8J; the three
  original bodies are preserved verbatim on the archived items. (reflection)

  Promoted 2026-06-10 — build plan authored at
  .prawduct/artifacts/build-plan-changelog-lifecycle.md (3 chunks: multi-tag-line union+warning,
  stamp-merged + statusless scope validation, missing-entry probe at PR create); branch
  feature/changelog-lifecycle.

  — Shipped 2026-06-10 as v2.1.1: all three chunks shipped (PR #90 squash-merged to develop as
  c7015e9). Closes the silent-drop family REL-2N8K, REL-6C3W, VWS-4D8J per the `closes:` field —
  all three already archived (dropped, merged into this item) at the 2026-06-10 groom.

- **[REL-2N8K]** Release-prep silently drops statusless change-log entries — step 3 only flips `status=merged`
  `effort: S · impact: M · area: methodology · source: builder · added: 2026-06-08 · status: dropped · stage: design · related: REL-4T8N, REL-6C3W, VWS-4D8J, REL-9F2T · reviewed: 2026-06-10`

  `docs/release-process.md` step 3 instructs the release author to flip entries "from `status=merged`
  to `status=shipped`." But the documented two-state lifecycle (set `status=merged` at the
  feature→develop merge) is manual and the `/prawduct:pr` merge flow never applies it, so most entries
  arrive at release-prep **statusless**. A literal reading of step 3 flips only the `status=merged`
  entries and silently omits every statusless one — and since `regen-views` acts only on
  `status ∈ {shipped, merged}`, those scopes' build-plan `## Status` checkboxes never flip and they
  vanish from `release-notes.md` + `scope_rollups`, with no warning. At v2.0.14, 8 of 10 unreleased
  entries were statusless (hook-decomp ch.1–7 + critic-session-guard); the release was correct only
  because the author enumerated ALL entries above the prior `release=` boundary by hand. Two fix
  options: (a) reword step 3 to "flip every unreleased entry — statusless OR `status=merged` — to
  `status=shipped`," and/or (b) make the `/prawduct:pr` feature→develop merge reliably stamp
  `status=merged` on the merged entry so the lifecycle the learnings describe actually holds. Either
  closes the silent-omission hole. (builder, from the v2.0.14 release)

  — Dropped 2026-06-10 (groom): merged into [REL-9F2T] "Change-log lifecycle hardening," which
  carries this as silent-drop transition (a). Body preserved here verbatim.

- **[REL-6C3W]** Flag a code-changing branch that merges with no change-log entry
  `effort: M · impact: M · area: release/change-log · source: reflection · added: 2026-06-08 · status: dropped · stage: design · related: REL-2N8K, REL-9F2T · refs: docs/release-process.md · reviewed: 2026-06-10`

  A non-doc-only feature branch can merge to develop with NO `.prawduct/change-log.md` entry at all,
  and nothing flags it — CRT-7B4M (#82) did exactly this, and it only surfaced at the v2.0.16
  release-prep, where the entry had to be reconstructed from the build plan to ship release-notes /
  flip the plan's Status / clear the pointer. This is a worse sibling of REL-2N8K (statusless entries
  silently dropped at release): there the entry exists but lacks a status; here there's no entry.
  Candidate fix: a PR/merge gate (parallel to check-pr-doc-only/trivial) or a release-prep probe that
  flags when `merge-base...HEAD` is not doc-only/trivial yet adds no new change-log entry. Filed from
  the v2.0.16 release (2026-06-08). (reflection)

  — Dropped 2026-06-10 (groom): merged into [REL-9F2T] "Change-log lifecycle hardening," which
  carries this as silent-drop transition (b). Body preserved here verbatim.

- **[VWS-4D8J]** regen-views silently honors only the FIRST `<!-- prawduct: ... -->` tag line when an entry section carries several
  `effort: S · impact: M · area: governance/views · source: reflection · added: 2026-06-10 · status: dropped · stage: ready · related: REL-2N8K, VWS-3K7P, REL-9F2T · refs: lib/views.py, .prawduct/change-log.md · reviewed: 2026-06-10`

  Observed live at the v2.1.0 release (2026-06-10): the reviewer-model-tiering change-log entry had
  two `<!-- prawduct: ... -->` tag lines under one `##` header (chunks=01 and chunks=02);
  regen-views flipped only chunk 01 and the only signal was the per-scope rollup count printing
  "1 chunk(s)". Same silent-drop family as REL-2N8K (statusless entries) and the shipped VWS-3K7P
  (status-value typos). Fix-shape: lib/views.py warns on stderr when an entry section contains more
  than one prawduct: tag comment (suggesting a merged chunks= list), or unions the chunk lists.
  (reflection)

  — Dropped 2026-06-10 (groom): merged into [REL-9F2T] "Change-log lifecycle hardening," which
  carries this as silent-drop transition (c). Body preserved here verbatim.

- **[CRT-3D9K]** `bin/prawduct-hook` stop-gate chunk resolution has the same views-branch blindness CRT-7B4M fixed in inference
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-08 · status: dropped · stage: requirements · related: CRT-7B4M, STH-2K8R · reviewed: 2026-06-10`

  CRT-7B4M fixed `lib/critic_mode.py` so Critic-mode inference derives the current chunk from git
  on a `views_enabled` feature branch (where the build-plan Status checkboxes are a derived view
  that never flips until release). But `bin/prawduct-hook`'s stop-gate still resolves the current
  chunk via the non-git-aware `_current_chunk_id_from_status` mirror (for chunk-`Type:` detection —
  e.g. the trivial-rationale gate), so on a feature branch it reads Chunk 01's `Type:`, not the
  chunk actually in progress. This was an explicit, user-vetoable scope boundary in the
  critic-mode-branch-fix build plan (ASSUMPTION 2); it fails safe (worst case: the gate checks the
  wrong chunk's Type, defaulting toward stricter review), so it's filed rather than fixed in that
  PR. Fix-shape: give the hook's chunk resolver the same git-aware path (or — per STH-2K8R —
  consolidate the mirrored helpers into `lib/` and have both the hook and inference consume one
  implementation, which would close this by construction). Surfaced by the CRT-7B4M cumulative
  Critic (2026-06-08). (critic)

  — Dropped 2026-06-10 (groom): merged into [STH-2K8R], whose consolidation closes this by
  construction (this item's own fix-shape says so). Body preserved here verbatim.

- **[PR-3J6W]** PR skill control-flow clarity: pre-flight guard placement, named retry entry points, Step 1b addressee, evidence retention
  `effort: S · impact: M · area: pr · source: builder · added: 2026-06-09 · status: dropped · stage: ready · related: PR-5K8D, PR-2H8N, CRT-5Q8W · refs: skills/pr/SKILL.md, skills/pr/review-protocol.md · reviewed: 2026-06-10`

  From the 2026-06-09 framework review (skills agent). (1) The release-promotion guard sits
  mid-prose after the Context Detection heading but must fire before routing — extract it as an
  explicit Pre-flight section before the routing table. (2) The three sequential STOPs (steps 2,
  2b, 3) never name their retry entry point; an agent may re-run Step 1 after fixing a Step 3
  block — add 'fix, re-run THIS gate, continue' to each. (3) Step 1b's doc-only fast-path
  instruction reads as if addressed to the Critic; rephrase as imperative to the skill executor.
  (4) Decide evidence-file retention: 'delete the evidence file with the branch' loses the audit
  trail if a PR is reverted — archive to .prawduct/.pr-reviews-archive/ or document why deletion
  is intended. Note: the doc-only fileset bug itself (skills/ treated as docs) is PR-5K8D,
  promoted into the review-fixes plan Chunk 3 — this item is the prose/control-flow cleanup only.
  (builder)

  — Dropped 2026-06-10 (groom): sub-items 1-3 verified resolved by the audit (release-promotion
  guard pre-routing via REL-8K3M; Step 2 names its re-check loop; Step 1b made imperative in #89).
  The residual sub-item 4 (evidence-file retention) merged into [CRT-5Q8W] as its sub-item (6).
  Body preserved here verbatim.

- **[CRT-1F7N]** Re-enable cumulative inference mid-build by recording per-HEAD cumulative records
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-22 · status: dropped · stage: research · reviewed: 2026-06-10`

  Chunk 03's rule 2 (cumulative) added a clean-tree guard so it doesn't over-fire mid-chunk-N. Side effect: even after the user commits chunk N, rule 2 still doesn't fire because the helper has no record that cumulative was already run for THIS HEAD — but in practice cumulative IS expensive and the user typically only wants it pre-PR. The current behavior matches the proportionality intent, but loses some signal: if the user committed and is about to PR, inference doesn't surface "you should run cumulative" — it returns `chunk` (or `final` if last chunk). Fix-shape: when the working tree is clean AND ≥2 commits ahead, return `cumulative` even though it'd take 4-10 min — the cleanness is the signal the user has stopped editing and is about to merge. Risk: false-positives on chunk boundaries where the user clean-committed but isn't about to PR. Validate against a few real chunk boundaries before changing. Filed from Chunk 03 work on 2026-05-22. (builder)

  — Dropped 2026-06-10 (groom): superseded — the /pr Step 2 gate now tells the user exactly when a
  cumulative is needed, and CRT-4J8W's chain removed the treadmill cost the mid-build inference
  nudge was meant to manage.

- **[CRT-2H8K]** `.critic-findings.json` cumulative-state file
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-05 · status: dropped · stage: idea · reviewed: 2026-06-10`

  Would let `final` reviews focus on emergent cross-chunk concerns by remembering what each `chunk` review already covered. Useful but not necessary for proportionality MVP (v1.3.13). Revisit if `final` reviews still feel slow after live use. Filed during proportional-Critic build plan as out-of-scope. (builder)

  — Dropped 2026-06-10 (groom): superseded by the v2.1.0 governance ledger, which records what each
  review covered; revisit only if final reviews still feel slow in practice.

- **[CRT-SHADOW]** (Optional) Recreate an A/B "shadow Critic" as a plugin variant
  `effort: M · impact: S · area: critic · source: builder · added: 2026-06-02 · status: dropped · stage: idea · reviewed: 2026-06-10`

  Chunk 13 retired the `critic-test` shadow skill (owner decision 2026-06-02). It was a framework-only experimental twin of `/critic` that wrote to `.critic-test-findings.json` (non-gating) for A/B-testing review-strategy changes. It was deliberately never ported to the plugin (Chunk 3), it read the now-deleted `agents/` tree, and its comparison baseline — the production Critic — now lives in the plugin. If A/B review-strategy testing is wanted again, recreate it as a **plugin** skill (`skills/critic-test/`) that forks against the plugin's bundled `skills/critic/review-protocol.md`, rather than maintaining divergent copies of the protocol. Low priority — only build if a concrete review-strategy experiment needs it. (builder)

  — Dropped 2026-06-10 (groom): superseded — the reviewer-model A/B
  (reviewer-model-ab-2026-06-10.md) was run without a shadow skill, and the ledger now provides the
  evidence base a shadow Critic was meant to supply.

<!-- v1.7.0 deferred scope — the backlog feature shipped its lean core (the /backlog skill + the single
     legacy-backlog-format probe). The items below are real requirements scope (backlog-system-requirements.md,
     post-sync-advisory-spec.md §8.2) held back on proportionality grounds: low-risk internal markdown tool,
     no current consumer. Add each when a real product needs it. Filed from the v1.7.0 release chunk (2026-05-29).
     (Comment moved to Archive with BKL-4N6X at the 2026-06-10 groom — its sibling items were already archived.) -->

- **[BKL-4N6X]** `/backlog dismiss-advisory` per-feature alias
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: dropped · stage: ready · reviewed: 2026-06-10`

  Requirements §8.2. A convenience alias that forwards to the existing unified `/prawduct-advisory dismiss`. The unified command already works, so this is pure ergonomics — deferred until the alias's discoverability is worth the extra surface. (builder)

  — Dropped 2026-06-10 (groom): pure ergonomics alias with no demand since filing; the requirement
  stays recorded in backlog-system-requirements.md §8.2 — re-file if a product asks.

- **[SYN-6J0R]** WIP tracking goes stale when branches merge piecemeal
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-03-23 · status: dropped · stage: design · reviewed: 2026-06-10`

  Mar 23 discodon doc audit found 3 WIP branches were already merged into develop via other PRs but project-state.yaml still listed them in-progress. No mechanism reflects branch completion back to project-state.yaml when PRs merge. Consider git-based detection (branch existence on remote) or a post-merge sync step. (reflection)

  — Dropped 2026-06-10 (groom): premise stale — project-state.yaml no longer carries a WIP-branch
  list (work is tracked via active_build_plan + change-log scopes); the discodon-era mechanism it
  referenced is gone.

- **[DOC-9J4B]** F8: add Foreign-API example to hallucinote product repo
  `effort: S · impact: S · area: docs · source: critic · added: 2026-05-18 · status: dropped · stage: ready · reviewed: 2026-06-10`

  v1.4 Chunk 04 (F8) acceptance criterion called for "at least one product-repo example added (hallucinote's Ableton Live MCP work is the obvious reference)." The Ableton-MCP example was shipped as a worked illustration inside the framework (planning.md "Foreign API Verification" section + templates/build-plan.md inline example), satisfying the spirit but not the literal product-repo touch. Defer the hallucinote-side update — `**Foreign API:** ableton-live-mcp` on the relevant build-plan chunk + `verify-api` step in Done-when — to the next hallucinote session. Filed from /critic NOTE on 2026-05-18. (critic)

  — Dropped 2026-06-10 (groom): the remaining work is entirely in the hallucinote repo — re-file in
  hallucinote's backlog at the next hallucinote session.

- **[STH-9V4K]** `bin/prawduct-hook` decomposition
  `effort: L · impact: M · area: stop-hook · source: janitor · added: 2026-04-16 · status: shipped · closed-by: hook-decomp ch.1–7 (v2.0.14) · reviewed: 2026-06-10 · related: STH-2K8R`

  Split the hook monolith into logical modules. **Implementation complete (2026-06-07):** all 7 chunks built + Critic-clean, one module per PR in dependency order — ch.1 lazy `lib/__init__` (enabling), ch.2 `lib/gitstate` (#74), ch.3 `lib/buildplan_refs` (#75), ch.4 `lib/compliance` (#76), ch.5 `lib/coverage` (#77), ch.6 `lib/gates` (#78), ch.7 `lib/briefing` (the SessionStart surface — final). The hook went from **4,942 → 1,911 lines (−61%)** and is now a thin dispatcher (bootstrap + parity-pinned inline mirrors + lazy `lib` accessors + `cmd_*` wrappers + `cmd_clear`/`cmd_stop`/`main`). An AST call-graph drove the leaf-first order; the briefing↔gates↔coverage↔buildplan_refs cycle was broken by reassigning `_parse_build_plan_status` to buildplan_refs. **Remaining: the develop→main release** that flips the build-plan checkboxes `[x]` (`status=shipped` change-log tags + regen-views) — close this item then. Enabled follow-up still open: STH-2K8R (critic_mode mirror consolidation). (janitor)

  — Shipped 2026-06-08 in v2.0.14: all 7 hook-decomp change-log entries carry `release=v2.0.14 |
  status=shipped`, so the develop→main release this item was held open for has happened. Plan was
  `build-plan-hook-decomposition.md`. Archived at the 2026-06-10 groom; follow-up STH-2K8R remains
  open (now unblocked).

- **[CRT-3X9D]** Critic's no-execution constraint doesn't prevent session-mutating `prawduct-hook clear`
  `effort: S · impact: M · area: critic · source: builder · added: 2026-06-07 · status: shipped · closed-by: critic-session-guard ch.1 (v2.0.14) · reviewed: 2026-06-10 · related: STH-9V4K, CRT-7Q2T`

  The Critic skill is documented (CLAUDE.md, review-protocol) to run with restricted `allowed-tools` so
  it "cannot run test suites, builds, or executables" — review is code-analysis only. During the
  STH-9V4K ch.7 `cumulative` review the Critic nonetheless ran `prawduct-hook clear` (as a "read-only
  smoke") AND `pytest` once against the real project dir. `clear` is NOT read-only: it archived +
  deleted the builder's `.session-reflected`, rewrote `.session-start` (making fresh test evidence read
  "stale"), and recaptured the git baseline — clobbering live session governance state mid-review. The
  builder had to restore the reflection and re-record evidence. Root cause: the tool restriction must
  not actually be enforced for `prawduct-hook <subcmd>` (and pytest) the way the docs imply, OR the
  Critic agent has Bash latitude it shouldn't. Fix options: tighten the Critic's `allowed-tools` so it
  genuinely cannot invoke `prawduct-hook`/`pytest`, or make the Critic's smoke run against a temp copy /
  with a guard env var that disables session-file mutation. Either way, an independent reviewer must
  never be able to mutate the session it's reviewing. (builder)

  — Shipped 2026-06-08 in v2.0.14 (`scope=critic-session-guard`, built on branch
  fix/critic-session-guard-CRT-3X9D, plan build-plan-critic-session-guard.md): the invariant is
  enforced at the mutation site — `prawduct-hook critic-begin`/`critic-end` markers make the
  session-mutating `clear` refuse to run while a review is active (now documented in CLAUDE.md).
  Residual gap — coordinator-dispatched subagents' Bash latitude is not bound by the marker — is
  tracked separately as CRT-7Q2T. Archived at the 2026-06-10 groom.

- **[BLD-2R9X]** `verify-chunk-refs` over-matches glob paths (`*.md`) written as prose in a build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-06-05 · status: shipped · closed-by: #73 (v2.0.14) · reviewed: 2026-06-10 · related: BLD-8F2Q, BLD-5V8F`

  **Resolved on branch.** `_looks_like_file_path` (`bin/prawduct-hook`, the single semantic gate the
  chunk-ref parser consults) now returns False for any backticked token carrying a shell-glob
  metacharacter (`*`, `?`, `[`) — a literal source path never contains one, so a glob written in prose
  (e.g. a Tests bullet's `docs/requirements/*.md`) is skipped instead of reported `missing-ref`. Same
  parser family as the shipped BLD-8F2Q (`path::symbol`); symbol/backlog-ref verification stays
  deferred (BLD-5V8F). 4 regression tests in
  `tests/test_build_plan_resolution.py::TestVerifyChunkRefsGlobPaths` (each glob char + the per-token
  case where a real path on the same line is still captured). Statusless change-log entry on-branch;
  flips to `merged` at develop-merge, `shipped` at release, then this item archives.

  — Shipped 2026-06-08 in v2.0.14 (change-log "verify-chunk-refs skips glob patterns written as
  prose", merged via #73, `release=v2.0.14 | status=shipped`). Archived at the 2026-06-10 groom.

- **[REL-8K3M]** `/pr` cumulative-Critic gate false-positives (benign exit-1) on a develop→main RELEASE promotion
  `effort: S · impact: S · area: release · source: reflection · added: 2026-06-06 · status: shipped · closed-by: v2.0.14 · reviewed: 2026-06-10 · related: CRT-7M2D, PR-2H8N`

  **Resolved on branch (fix-shape a+b, no gate-logic change).** `skills/pr/SKILL.md` gained a
  release-promotion guard (on `develop`/`main` → redirect to `docs/release-process.md`, don't run the
  feature-PR gates); `docs/release-process.md` gained a "`/prawduct:pr` is not the release vehicle"
  section explaining the benign `check-cumulative-critic` exit-1 is neither a gate to re-satisfy (the
  CRT-7M2D treadmill) nor a waiver case. Fix-shape (c) — broadening the CRT-7M2D allowance to version/
  derived-view files — was rejected (weakens a correct global gate to patch a context-misuse). 2 guard
  tests in `tests/test_pr_reviewer.py::TestPrReviewSkillContent`. Change-log entry is statusless
  on-branch (avoids the regen-views typo-guard); gains `status=merged` at feature→develop merge and
  `status=shipped` at the develop→main release, then this item archives.

  Original report: the `/prawduct:pr` Step 2 gate is feature→develop shaped and exit-1'd during the
  v2.0.13 release because release-prep touches non-`.md` version files (version strings +
  `regen-views`-regenerated `scope_rollups`) outside CRT-7M2D's docs-only allowance. (reflection)

  — Shipped 2026-06-08 in v2.0.14 (change-log "/prawduct:pr redirects a release promotion to the
  release process (REL-8K3M)", `release=v2.0.14 | status=shipped`). Follow-up PR-2H8N (key the guard
  off `resolve-base` instead of hardcoded branch names) remains open. Archived at the 2026-06-10
  groom.

- **[CRT-4J8W]** P0 — review-phase wall clock: accept a cumulative + verify-resolutions CHAIN at the PR gate
  `effort: M · impact: L · area: governance/gates · source: user · added: 2026-06-10 · status: shipped · closed-by: gate-soundness ch.05 (commits 9618c2b + 78fadaf) · reviewed: 2026-06-10 · stage: ready · related: CRT-7M2D · refs: lib/gates.py (check_cumulative_critic), skills/critic/SKILL.md, skills/critic/review-protocol.md, tests/test_cumulative_gate.py`

  User escalation 2026-06-10: review phase ran 30+ min wall clock for ~5 min of work. Two cost
  drivers: unit cost per review (fixed same day — reviewers default to model opus, ~4x faster per
  the reviewer-model-ab-2026-06-10.md experiment) and the **re-review treadmill**: every non-.md fix
  after a cumulative review re-stales `check-cumulative-critic` and costs a FULL bundle re-review
  even when only 2 files changed. Structural fix (the option deferred in gate-soundness ch.4 as
  "build if it recurs" — it recurred the same session):
  1. When `/prawduct:critic verify-resolutions` runs while the existing `.critic-findings.json` is a
     clean cumulative record, embed an `extends_cumulative: {commit_reviewed: <X>}` anchor in the
     new record.
  2. `check_cumulative_critic` accepts EITHER a HEAD-covering cumulative record (today's rule) OR a
     chain: `mode=verify-resolutions`, 0 blocking, `commit_reviewed==HEAD`, `extends_cumulative`
     present, AND files changed in `X..HEAD` ⊆ the record's `files_reviewed` (fail closed on any
     gap, same as today).

  Soundness argument: cumulative@X vouches for the bundle; a clean delta review whose scope covers
  `X..HEAD` extends that vouching to HEAD — same shape as the existing doc-only allowance, with
  scope verification. Surfaces: `lib/gates.py` (`check_cumulative_critic` + findings schema optional
  field), `skills/critic/SKILL.md` + `review-protocol.md` (record the anchor),
  `tests/test_cumulative_gate.py` (chain accept/reject cases incl. scope-gap fail-closed),
  `methodology/building.md` + `skills/pr/SKILL.md` sequencing prose (update: the fix-after-cumulative
  path becomes a cheap delta review, not a full re-run). Priority P0. Related: CRT-7M2D (the
  coverage-not-mtime gate this extends — archived/shipped). (user)

  — Shipped 2026-06-10 — Built as gate-soundness chunk 05 (commits 9618c2b + 78fadaf). Dogfooded on
  its own PR bundle: the chain record satisfied `check-cumulative-critic` live.
- **[CRT-6F2N]** `critic-begin` runs before the designer-handoff skip, so a designer-handoff chunk leaves the marker set
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-08 · status: shipped · closed-by: review-fixes-ch3 · reviewed: 2026-06-09 · related: CRT-3X9D`

  Critic SKILL.md step 1 runs `prawduct-hook critic-begin` right after mode resolution, but a
  `Type: designer-handoff` chunk exits clean *before* step 8 (`critic-end`), so the
  `.prawduct/.critic-active` marker is left set on that path. Benign — the marker self-corrects
  three ways (30-min TTL, session-start sweep, explicit override) — and rare, but ideally
  `critic-begin` should run only after the designer-handoff skip is ruled out (move the
  `critic-begin` call below the skip, or pair the skip with a `critic-end`). Surfaced as a NOTE in
  the CRT-3X9D cumulative review. (critic, 2026-06-08)

- **[PR-5K8D]** check-pr-doc-only should exclude skills/ (and methodology/templates) — align with `_classify_trivial_change`'s bounds
  `effort: S · impact: M · area: pr/governance · source: reflection · added: 2026-06-08 · status: shipped · closed-by: review-fixes-ch3 · reviewed: 2026-06-09 · related: PR-9T4M · refs: skills/pr/SKILL.md, lib/buildplan_refs.py, lib/coverage.py`

  The two PR fast-path classifiers disagreed on skill files. On the backlog-legend-refresh PR (#83),
  `check-pr-doc-only` returned exit 0 (all 4 files `.md` → "gates may be skipped"), which per the
  `/pr` Step 1b instruction would skip the independent PR reviewer entirely — but `check-pr-trivial`
  correctly returned "not-trivial: skill-file-edited: skills/backlog/SKILL.md. Full review required."
  A fork-skill's SKILL.md IS behavior/logic (per the existing learning "when a feature's logic lives
  in a context:fork skill, lib/ holds DATA not LOGIC"), so an extension-only doc-only classification
  under-reads a behavioral skill change and can skip review.

  Re-anchored 2026-06-08 (branch fix/retire-pr-trivial-fast-path): `check-pr-trivial` /
  `_pr_diff_is_trivial` were DELETED when the PR-boundary trivial fast-path was retired (see
  PR-9T4M). The original fix-shape pointed at `check-pr-trivial` as the model to copy; that
  classifier is gone. The canonical exclusion bounds still live in `lib/buildplan_refs.py`
  (`_classify_trivial_change` / `_TRIVIAL_PROTECTED_PATHS` — `{skills/, methodology/, templates/,
  CLAUDE.md}`), now consumed only by the chunk-level `_is_trivial_fileset_eligible` gate
  (`lib/gates.py`). This item is now MORE relevant, not less: with the trivial fast-path retired,
  `check-pr-doc-only` (`lib/coverage.py`, hook `cmd_check_pr_doc_only`) is the ONLY remaining
  PR-boundary gate-skip path, and it still under-reads behavioral `skills/*.md` changes. Candidate
  fix (re-anchored): align `check-pr-doc-only`'s fileset bounds with `_classify_trivial_change` —
  exclude `skills/`, `methodology/`, `templates/`, and `CLAUDE.md` from the doc-only fast-path so a
  behavioral-prose change still gets the reviewer; consume the shared `_TRIVIAL_PROTECTED_PATHS`
  rather than re-listing the bounds. refs: skills/pr/SKILL.md (Step 1b/1c), lib/coverage.py
  (check_pr_doc_only), lib/buildplan_refs.py (_classify_trivial_change). Filed from the v2.0.16
  release (2026-06-08). (reflection)

- **[PR-9T4M]** Trivial PR fast-path treats `bin/` + `lib/` (core runtime) as fileset-eligible — a core-runtime change can skip cumulative-Critic + reviewer
  `effort: S · impact: M · area: pr · source: builder · added: 2026-06-06 · status: shipped · closed-by: retire-pr-trivial-fast-path · reviewed: 2026-06-08 · related: STH-1W5N, BLD-2R9X`

  `_TRIVIAL_PROTECTED_PATHS` (`bin/prawduct-hook`) bounds the `Type: trivial` / `check-pr-trivial`
  fast-path to `{skills/, methodology/, templates/, CLAUDE.md}` — the governance *content* surfaces.
  It does NOT include `bin/` or `lib/`, which hold the framework's executable runtime — including
  `bin/prawduct-hook` itself (the ~4,369-line hook that *implements every gate*) and the `lib/`
  modules. Consequence (observed firsthand merging BLD-2R9X, a `bin/prawduct-hook` bugfix):
  `check-pr-trivial` returned exit 0 (`all fileset-eligible`), so the `/prawduct:pr` fast-path would
  have skipped BOTH the cumulative-Critic gate AND the independent reviewer for a change to the core
  gate-runtime. I declined the fast-path manually and ran the full review, but the next contributor
  may not. A bug in `bin/prawduct-hook`/`lib/` can break gating itself, so it is arguably *more*
  catastrophic-blast-radius than a `templates/` edit, not less. Fix-shape: add `("bin/", False,
  "runtime-edited")` and `("lib/", False, "runtime-edited")` to `_TRIVIAL_PROTECTED_PATHS` (single
  source of truth — both the stop-hook `_is_trivial_fileset_eligible` and the PR-boundary
  `_pr_diff_is_trivial` consume it), with tests in `tests/test_trivial_fileset_gate.py`. Open
  question: is a doc/comment-only edit to a `bin/`/`lib/` file (no logic change) worth exempting, or
  keep the bound coarse (any `bin/`/`lib/` touch → full review)? Coarse is safer and simpler. Filed
  from the BLD-2R9X merge on 2026-06-06. (builder)

  — Resolved 2026-06-08 (branch fix/retire-pr-trivial-fast-path) — Closed by retiring the entire
  PR-boundary trivial fast-path (`check-pr-trivial` / `_pr_diff_is_trivial` removed) rather than the
  narrower proposed fix (adding `bin/`/`lib/` to `_TRIVIAL_PROTECTED_PATHS`). With the whole
  PR-boundary fast-path gone, there is no longer any path where fileset-eligibility skips BOTH review
  gates — retiring the unsound predicate supersedes the narrower patch. Note: the chunk-level
  `Type: trivial` fileset bounds still omit `bin/`/`lib/`, but `Type: trivial` does NOT skip the
  Critic gate at the chunk level, so no gate-skip risk remains there.

- **[CRT-7B4M]** infer-critic-mode pins to Chunk 01 on a feature branch with views_enabled (derived checkboxes never flip)
  `effort: S · impact: S · area: critic · source: builder · added: 2026-06-08 · status: shipped · closed-by: critic-mode-branch-fix · reviewed: 2026-06-08 · stage: requirements`

  On a feature branch with views_enabled, build-plan ## Status checkboxes are a derived view that only flips at release, so they stay [ ] for every chunk during branch development. prawduct-hook infer-critic-mode reads the first unchecked [ ] as the current chunk → always resolves to Chunk 01, so a multi-chunk plan's later chunks all inherit Chunk 01's declared Critic mode (final, in backlog-rework) regardless of the chunk's own declared mode. Observed across all 10 backlog-rework chunks: passing an explicit /prawduct:critic <mode> arg was the workaround. Not harmful (final is the safe direction) but it makes per-chunk Critic-mode declarations inert on a branch and the mode_chosen_by rationale misleading. Research-stage: investigate whether inference should consult git-committed-chunk-count or the plan's own chunk ordering rather than the derived checkboxes. Surfaced during backlog-rework (2026-06-08).

- **[BKL-2F7K]** Ship the three remaining §8.2 backlog probes (`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`)
  `effort: L · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 06) · reviewed: 2026-06-08`

  v1.7.0 shipped only `legacy-backlog-format` (the first production probe). The other three §8.2 probes are deferred — no product today has an external backlog file, an old-section-schema backlog, or a stale-grooming signal worth nagging. Build when one does. Each registers against the v1.6.0 advisory infrastructure via `register_probe("backlog", …)` in a new `lib/` probe module via `lib/advisory_store.register_probe` (the file-sync `tools/lib/backlog_probes.py` was deleted in M4) and resolves off a `project-state.yaml` fact: `external-backlog-detected` → `backlog_external_imports` (set by `/backlog import`); `legacy-section-schema` → reuse `backlog_format_version: 2` (migration folds the old `## Active`/`## Queue` headings); `backlog-overdue-grooming` → `backlog_last_groomed_at` + the 90-day window (spec §8.2). Tune the >5-item / >20-item / 90-day thresholds against a real product's backlog before shipping. (builder)

- **[BKL-3R8P]** `/backlog dedup` — surface and merge near-duplicate items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 04) · reviewed: 2026-06-08`

  Requirements §4.3. A subcommand that finds candidate duplicate items (title/area/keyword overlap) and proposes merges, preserving both bodies. Not on the path to the §1 user-facing test ("pick a high-value item in 30 min"), so deferred from lean core. The `add` subcommand already does inline dedup-on-create; this is the after-the-fact sweep. (builder)

- **[BKL-5H9M]** `/backlog import <path>` — convert an external TODO/BACKLOG file into structured items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 08) · reviewed: 2026-06-08`

  Requirements §4.3/§8.4. Resolves the `external-backlog-detected` probe ([BKL-2F7K]) by writing `backlog_external_imports` to `project-state.yaml`. Heuristically converts each bullet/list item in the named file into a `[PFX-XXXX]` entry (`source: user`, `status: open`, area inferred), always confirming before writing. Deferred with its probe — this repo has no external file to import. Build alongside [BKL-2F7K]'s `external-backlog-detected`. (builder)

- **[BKL-1V8J]** prawduct-doctor setup-time external-backlog report
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 08) · reviewed: 2026-06-08`

  Requirements/advisory-spec §8.3. At setup/health-check time, `prawduct-doctor` reports any external backlog files (`TODO.md`, `BACKLOG.md`) found in repo root + `.github/`. Redundant with the `external-backlog-detected` probe ([BKL-2F7K]); deferred with it — build both together or decide one supersedes the other. (builder)

- **[BKL-6L3Q]** Build-plan hygiene-step guidance in `templates/build-plan.md` + `methodology/building.md`
  `effort: S · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 09) · reviewed: 2026-06-08`

  Requirements §5.3, decision D9. Document the backlog-hygiene step (at chunk close, review open items in the chunk's area and update status explicitly — the framework never infers status from plans/change-logs, per D4) in the build-plan template's Done-when prose and in `methodology/building.md`. Cheap, but no probe or check depends on it in lean core, so filed rather than shipped. The v1.7.0 plan already dogfoods the step informally (chunk close-out includes "backlog hygiene"); this makes it a documented standard. (builder)

- **[CRT-3K9P]** The four backlog Critic checks C-B1–C-B4
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 05) · reviewed: 2026-06-08`

  Requirements §7. Four soft NOTE-level Critic checks for backlog hygiene (e.g. C-B3: a chunk touches an area with open backlog items but its Done-when has no backlog-hygiene step). Decision D1 made them NOTE-level; deferred because adding governance friction to *every* product's Critic run before there's evidence of need is the least proportional piece of the feature (success criterion S6 watches for fatigue). Build when backlog-hygiene drift actually shows up in reviews. (builder)

- **[JNT-7T1W]** Janitor Step 2.5 — Backlog Triage (incl. Q2 archive-split)
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 07) · reviewed: 2026-06-08`

  Requirements §6. Add a backlog-triage step to the janitor: flag stale `status: open` items (`reviewed`/`added` >90d), surface neglected `## Promoted` items whose owning chunk shipped, and — the Q2 decision — when `## Archive` exceeds ~200 entries, propose splitting it to `backlog-archive.md` (with `/backlog find` spanning both files). Deferred from lean core; build when a product's backlog is large enough that grooming friction is real. (builder)

- **[CRT-7M2D]** Cumulative-Critic gate judges commit-coverage, not mtime-recency
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-04 · status: shipped · closed-by: #65 (v2.0.9) · related: STH-6B4R`

  `check-cumulative-critic` now passes iff the cumulative record covers HEAD (`commit_reviewed == HEAD`,
  or only `.md` changed since), instead of judging mtime vs `.session-start` — closing the false-pass
  (a stale record passing over real code changes) AND the post-review re-run treadmill (inert doc fixes
  no longer force a full cumulative re-run). New `tests/test_cumulative_gate.py` (8 real-git tests; the
  gate previously had none); doc wording swept "fresh" → "HEAD-covering". Dogfooded on its own PR #65
  (doc-only post-review fixes stayed covered, no re-run). Shipped v2.0.9. (builder)

- **[REL-4T8N]** Release tooling: handle MULTIPLE release-pending plans (regen-views per scope) instead of a single `active_build_plan` pointer
  `effort: M · impact: M · area: release · source: builder · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  The release model assumed ~one release-pending plan between `develop→main` releases: `regen-views`
  resolved THE plan via the single `active_build_plan` pointer. Batched sub-releases stack up (v2.0.5
  shipped four scopes), so the release had to point the pointer at each plan in turn and `regen-views`
  per scope — 4× tedious, easy to miss one. It also surfaced a SECOND symptom: the derived
  `release-notes.md` rendered only one entry per `release=` tag, mis-aggregating all scopes of a
  release under one heading with a union'd chunk list.

  **Resolved #62 (v2.0.6):** Chunk 01 (REL-4T8N-A) — `regen-views` now enumerates every change-log
  `scope=` (status ∈ {shipped, merged}), resolves each to its build-plan file via frontmatter `scope:`
  (`build_scope_to_plan_map`), and regenerates every release-pending plan in one pass (per-plan scope
  re-detection → no cross-scope leakage; single-plan back-compat preserved; also fixed a latent
  can't-run exit-2 state). Chunk 02 (REL-4T8N-B) — `release-notes.md` renders each distinct scope as
  its own `### ` sub-section (group-by-scope; same-scope collapses; single sub-release stays flat). The
  open "scope→file" question was answered by the existing frontmatter parser. (builder)

- **[BLD-8F2Q]** `verify-chunk-refs` misreads `path::symbol` backtick tokens as missing file paths
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  The chunk-ref parser (`bin/prawduct-hook` `cmd_verify_chunk_refs` / `_parse_build_plan_chunk_refs`)
  captured a whole backtick token like `lib/views.py::is_views_enabled`, saw the `/`, and treated the
  entire `module.py::symbol` string as a (missing) file path → false-positive exit 1 even though the
  file exists. **Resolved #62 (v2.0.6):** the parser splits on `::` and existence-checks only the
  pre-`::` path (stored as the ref); symbol verification stays deferred (BLD-5V8F). The `new ` forward-
  ref exclusion still composes; 6 net-new tests. (critic)

- **[PR-7Q3M]** Condition PR-skill merge-flow step 7 (build-plan deletion) on whether the develop-merge is itself the release
  `effort: M · impact: M · area: pr · source: user · added: 2026-06-02 · status: shipped · closed-by: #62 (v2.0.6) · related: BLD-3X9M`

  Under the v2.0 gitflow batched-release model, release-bound work merges feature→develop ahead of the
  develop→main release, where the release runs `regen-views` ON the build plan. Deleting the plan +
  clearing `active_build_plan` at develop-merge time left the release nothing to regenerate; step 7 also
  hardcoded `artifacts/build-plan.md`. **Resolved #62 (v2.0.6):** step 7 branches on `prawduct-hook
  resolve-base` — base = release surface (`main` family) → delete the plan (resolved via the pointer,
  not a hardcoded path) + clear the pointer; base = `develop` (release-pending) → RETAIN both until the
  release. Dogfooded on this very PR's merge (base=develop → retained). (user)

- **[TST-9K4W]** Structural tests scan `.claude/worktrees/` — leftover/in-flight workflow worktrees fail the suite
  `effort: S · impact: S · area: tests · source: builder · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  `test_test_location::test_all_test_files_live_under_tests_directory` and
  `test_plugin_methodology_digest::test_source_is_one_canonical_copy` globbed the whole repo tree, so a
  worktree-isolated workflow's leftover `.claude/worktrees/wf_*/` checkout (duplicate test/methodology
  copies) failed both. **Resolved #62 (v2.0.6):** both collectors prune the `.claude/` path component
  (and take a `root` param for testability); regression tests via synthetic worktree trees + a real-tree
  simulation. Layer-2 `norecursedirs` was deliberately skipped (collection is already scoped by
  `testpaths=["tests"]`). (builder)

- **[BLD-7P3K]** Guard test: assert the active build plan's chunk headings parse (fail loud on heading-format drift)
  `effort: S · impact: M · area: build-plan · source: critic · added: 2026-06-04 · status: shipped · closed-by: #61 (v2.0.5) — shipped test-only; runtime-check-for-any-product variant not pursued · related: VWS-3K7P`

  Recommended by `learnings.md` ("Build-plan chunk headings must use `### Chunk N:` colon form") AND
  twice by the roi-batch-2 cumulative Critic after the build plan itself shipped with `#### Chunk NN:`
  (four-hash, under a `### Lane` grouping level) — which silently defeated the `### Chunk ` parsers
  (`verify-chunk-refs`, `_parse_build_plan_chunk_type`, `lib/critic_mode.py` plan-override) for the
  WHOLE plan. The degradation is silent: chunk-type fail-closes to `code`, refs stop verifying, and
  nothing errors. Fix-shape: a test (or a `regen-views`/stop-hook check) that resolves the active
  build plan via `resolve_build_plan_path` and asserts its `## Status` chunk IDs each map to a
  parseable `### Chunk <id>:` heading — so a depth/format mismatch fails LOUDLY instead of degrading.
  Open question: test-only (pins the framework's own plan) vs. a runtime check that fires for any
  product's active plan. Filed from roi-batch-2 Critic NOTE on 2026-06-04. (critic)

- **[SYN-9C4T]** Extract shared `read_bool_yaml_key(state_path, key)` from `lib/views.py::is_views_enabled` and `bin/prawduct-hook::_read_bool_yaml_key`
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-06-03`

  Both perform the same column-0 boolean scan against `project-state.yaml`, intentionally duplicated to keep the hook flat (one inline ~10-line helper vs. a new lib import). Move to `lib/core.py::read_bool_yaml_key(path, key) -> bool` and call from both sites. **Now more actionable (re-verified 2026-06-03):** the file-sync `product-hook` named in the original NOTE was deleted in M4; the duplicate survives in the plugin runtime as `bin/prawduct-hook::_read_bool_yaml_key` (line ~3331, comment says "kept parallel to is_views_enabled in lib/views.py") against `lib/views.py::is_views_enabled` (line ~651). The third caller the original NOTE said would tip this to extraction is already here — `_read_bool_yaml_key` now also reads `coverage_required` (bin/prawduct-hook ~3464). Filed from /critic chunk NOTE on 2026-05-19 (Chunk 09); paths refreshed post-M4. (critic)

- **[TST-5W1J]** Cache test-file contents in `bin/test-reference-verify` to drop O(N*T) re-reads
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-19 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  `_has_reference` re-opens every test file once per changed file. Sub-second on framework scale (~20 test files × small chunk diffs) but a stronger verifier or larger product would feel it. Fix-shape: discover_tests reads all test contents into a dict once, then `_has_reference` runs substring across the cached text. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 08). (critic)

- **[PRR-4M9T]** Trim PR-reviewer goals to remove Critic overlap
  `effort: S · impact: S · area: pr-reviewer · source: builder · added: 2026-05-05 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  PR reviewer Goals 1, 2, 4, 5, 6 in `skills/pr/review-protocol.md` overlap with Critic. Now that the layering is explicit (Critic-chunk = local; Critic-final = synthesis; PR reviewer = release readiness), PR reviewer goals could be trimmed to release-specific concerns (narrative, scope, merge hygiene, simplification). Filed during proportional-Critic build plan as out-of-scope. (builder)

- **[CRT-4W8M]** Critic check: byte-exact assertions for "no behavior change" refactors
  `effort: S · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  When a refactor's explicit bar is "no behavior change," substring-level test assertions are insufficient. Discodon graph_ops refactor (Apr 16) had two silent text drifts (double-prefix, error message wrapper) that substring assertions missed and Critic caught only by reading the code. Evidence: discodon/reflections.md §2026-04-16 graph_ops. Candidate: add to skills/critic/review-protocol.md for Refactor work type — "If the chunk claims no behavior change, are output assertions exact-match (not substring/contains)? If not, flag WARNING." (reflection)

- **[MET-7H2D]** Testing guidance: multi-hop edge-case tests
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-04-08 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  When a data structure or state machine's correctness depends on what happens on the NEXT invocation (accumulator, coordinator, cursor, stateful retry), tests that only check post-state miss multi-hop bugs. Discodon has repeatedly shipped bugs caught only by the next cycle (Apr 8 accumulator, Apr 15 V0.5-7a timestamp collision under prune). Evidence: discodon/reflections.md §2026-04-08 "What I'd do differently". Candidate: add a bullet to methodology/building.md §Test Discipline — "When tested behavior depends on subsequent invocations (next cycle, next call, next prune), exercise at least one additional step beyond the immediate post-state." Broadly applicable; no detection heuristic needed. (reflection)

- **[TST-6V2N]** test-evidence freshness gate reads `.test-evidence.json` but the plugin ships no command to WRITE it
  `effort: M · impact: M · area: tests · source: user · added: 2026-06-04 · status: shipped · closed-by: #60 (72c4081, develop) · related: TST-5W1J · reviewed: 2026-06-04`

  Filed by a Hallucinote session (`incoming-bugs/test-evidence-gate-reads-a-file-the-plugin-doesnt-write.md`)
  and **confirmed firsthand** in roi-batch-2: the plugin has a READER (`cmd_test_status` freshness check +
  the cumulative-Critic staleness flag + `cmd_validate_evidence` schema check) but NO command that RUNS the
  suite and PRODUCES `.test-evidence.json` (timestamp + `git_sha` + passed/failed/skipped/duration + the
  F4a fields). `bin/test-reference-verify` writes only the F4a half (`changes_referenced`/`coverage_level`)
  via `--merge-into`; nothing writes the pytest half. Under the retired file-sync model `product-hook`
  wrote it; post-plugin-migration it's a reader without a writer. roi-batch-2 had to hand-author the
  passed/failed/git_sha/timestamp JSON and manually merge F4a — exactly the friction the prior roi-batch
  handoff flagged ("no automated test-evidence writer is wired up"). Hallucinote improvises with a local
  `tools/stamp_evidence_sha.py` shim; every product repo reinvents this. Worse, the gate's `git_sha` check
  is satisfiable by a post-commit stamp over STALE counts — nothing ties the recorded counts to a real run.
  Fix-shape: add a `prawduct-hook test-evidence record [-- <pytest args>]` subcommand that runs (or wraps)
  the suite, captures real `passed/failed/skipped/duration`, stamps `git_sha = HEAD` + ISO timestamp, calls
  `test-reference-verify --merge-into` for the F4a half, and writes atomically — so the freshness gate
  judges output the plugin itself produced + ties counts to an actual run. Watch the pytest-count parse
  (no native JSON without a plugin; parse the summary line or use exit-code + `--json-report`). Until then,
  ship the sha-stamp+schema as a documented helper so repos don't each reinvent it. Filed 2026-06-04. (user)

- **[VWS-3K7P]** Validate change-log `status=` values + reconcile views.py docstring
  `effort: M · impact: M · area: views · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/views.py parse_tag_line accepts ANY status= string; only `status=shipped` flips checkboxes, so a typo (e.g. `status=shippd`) silently never flips and emits no warning — a real release-process footgun. Also the views.py module docstring (~line 19) lists status values as `shipped|in-progress|deferred` but the actual convention (docs/release-process.md, learnings.md, roi-batch entry) uses `merged` for the release-pending intermediate; in-progress/deferred are not emitted today. Fix-shape: add a pure `validate_status_values(entries) -> list[str]` helper in views.py recognizing {shipped, merged} (warn on others) and have bin/prawduct-hook cmd_regen_views print the warnings; sync the docstring to {shipped, merged}; never change the flip rule (only shipped flips). + tests. The DOC half (defining the enum in release-process.md) already shipped in a28ccaa; this is the code half. (janitor)

- **[STH-2J9F]** regen-views returns exit 0 on ImportError (silent degradation)
  `effort: S · impact: M · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  bin/prawduct-hook cmd_regen_views (~line 3673-3683) catches `from lib import views` ImportError, prints a NOTE, and returns 0 — but it is a state-mutating command, and other mutating commands (accept-operator-verification, verify-operator-verification) return 1 on ImportError per the honest-failure pattern. A user on a broken install sees exit 0 and assumes views regenerated. Fix-shape: return 1 for ImportError, keep 0 for the disabled-by-config path. + test. (janitor)

- **[STH-6B4R]** Gate freshness timestamp comparison is lexicographic / tie-ambiguous
  `effort: M · impact: M · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  The stop-hook Critic gate (bin/prawduct-hook ~2579-2594) and check-cumulative-critic (~3616-3627) compare ISO-8601 string mtimes (`.session-start` vs findings mtime). Same-second ties are ambiguous and the precision contract is undocumented/untested. Fix-shape: format both sides to identical %Y-%m-%dT%H:%M:%SZ precision and TEST the tie case (findings_mtime == session_start must be rejected as not-fresh), or switch to numeric epoch seconds. Document the tie-breaking rule. (janitor)

- **[TST-7Q3D]** Stop-gate regression coverage gaps (verify-resolutions, trivial-fileset, waiver unknown-key)
  `effort: M · impact: M · area: tests · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  TestPluginStopGate is missing three regression cases: (a) verify-resolutions mode out-of-scope file blocking — findings with files_reviewed=[a.py], diff modifies [a.py,b.py] -> assert exit 2 out-of-scope (bin/prawduct-hook ~2198); (b) Type: trivial chunk modifying files outside the allowed bounds -> assert exit 2 fileset reason (~2536-2564); (c) gate-waiver unknown key -> assert stderr diagnostic WITHOUT blocking (~2438-2447). All test-only, no runtime change. (janitor)

- **[TST-4H8M]** Unit coverage for migrate `_collapse_blank_runs` edge cases
  `effort: S · impact: S · area: tests · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/migrate_plugin.py _collapse_blank_runs (~264-273, added by MIG-8C3V) has no dedicated unit tests for 3/4/5/7+ consecutive newlines, only-newlines, empty string, or while-loop convergence (e.g. `a\n\n\nb\n\n\nc` -> `a\n\nb\n\nc`). Currently only covered indirectly via the end-to-end migrate test. Add a TestCollapseBlankRuns class. (janitor)

- **[VWS-8M2Q]** Harden lib/views.py tag/frontmatter parsers (quote-in-chunk-id, unclosed HTML comment)
  `effort: S · impact: S · area: views · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  Two low-impact parser corners in lib/views.py: (a) chunk IDs from parse_tag_line are quoted verbatim into scope_rollups YAML (~368-384) without escaping — a chunk id containing a quote (malformed tag) produces unparseable YAML; CHUNK_LINE_RE guards the build-plan file but not tag-line input. (b) _parse_build_plan_frontmatter_scope (~165-170) silently treats an UNCLOSED HTML comment block as missing frontmatter (returns (False,None)) rather than flagging it; the v1.5.1 R5 'explicit malformed-frontmatter test' was never added. Fix-shape: validate/escape chunk IDs (or yaml.safe_dump); raise or explicitly document unclosed-comment leniency + add the malformed-frontmatter test. (janitor)

- **[ADV-9K2T]** advisory_store read/write failures degrade silently (no corruption surfacing)
  `effort: M · impact: M · area: advisory · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/advisory_store.py best-effort read/write falls back to safe defaults on any failure, so a corrupted `.advisories.json` is silently reset with no signal — the user never learns their advisory state was lost. Fix-shape: on a parse/read failure, drop a `.advisories.json.corrupt` sentinel (or log) so corruption is surfaced on next session start for user-initiated recovery, instead of silently swallowed. (janitor)

- **[STH-1W5N]** Centralize the trivial-change protected-path bounds into a documented constant
  `effort: S · impact: S · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · related: STH-4D2X · reviewed: 2026-06-04`

  The Type: trivial / doc-only fileset bounds (skills/, methodology/, templates/, CLAUDE.md, test deletions, new files) are enforced inline in bin/prawduct-hook (~3120-3180) with no central spec. Extract to a documented module-level `_TRIVIAL_PROTECTED_PATHS` frozenset (lib/core.py or bin/prawduct-hook) with a rationale per path, referenced from all call sites. Relates to STH-4D2X (the `.claude/skills/` bound question). (janitor)

- **[TST-1D5W]** Tighten `_validate_evidence_schema` against bool-as-int
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-05 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  Python's `bool` is a subclass of `int`, so `{"passed": True}` slips through `isinstance(v, int)` in the test-evidence validator. No real test runner emits booleans for these fields, so impact is theoretical, but the loophole is real. If addressed: add `or isinstance(v, bool)` exclusion to the type check (with a comment), and add a `TestValidateEvidenceSchema::test_bool_rejected_for_int_field` case. Filed from /critic NOTE on 2026-05-05. (critic)

- **[CRT-3M8Q]** `/critic` ignores the build plan's per-chunk `Critic mode:` override — Skill-tool args don't thread to `$ARGUMENTS`, so a plan-mandated `final` silently runs as inferred `chunk`
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-06-01 · status: shipped · closed-by: #58 (befd69b, develop) · related: CRT-1F7N · reviewed: 2026-06-04`

  The `/critic` skill ignores the build plan's per-chunk `**Critic mode:**` field, and Skill-tool args don't thread to its `$ARGUMENTS`, so a plan-mandated `final` override silently runs as inferred `chunk` mode. Discovered in v2.0.0 Chunk 9 (a destructive cutover whose plan overrode the mode to `final`): the independent Critic ran clean goals 1-3 twice but goals 4-7 were never run by the agent (`mode_chosen_by: rule-4`, not `explicit-args`). The methodology already says the per-chunk `Critic mode:` should be a "successive override," but the skill doesn't read it and the Skill-tool args never reach the forked skill, so the override is inert. Fix-shape: (a) have the `/critic` skill read the active build plan's per-chunk `**Critic mode:**` field as an override (matching the methodology's "successive override" intent), and/or (b) fix Skill-tool args reaching the forked skill's `$ARGUMENTS`. Type: process/governance. Priority: medium. Filed from v2.0.0 Chunk 9 reflection on 2026-06-01. (reflection)

- **[BLD-4Q9X]** `scope: null` in build-plan frontmatter does not suppress change-log inference
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-23 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Surfaced by v1.5.1 Chunk 05 cumulative Critic. The template ships `scope: null` as the documented opt-out form, and `_parse_build_plan_frontmatter_scope` correctly returns `None` for null literals. But `_detect_active_scope` then treats "key present with null" identically to "key absent" — it falls through to change-log inference, picking up the most-recent `scope=` tag. Result: a product with a tagged release in change-log.md (e.g. `scope=v1.5`) plus a fresh `scope: null` build-plan with new chunks 01/02/03 will see `regen-views` flip those chunks to `[x]` because v1.5's tagged entries claim chunks 01/02/03. Author's explicit-null intent ("don't filter") is overridden silently. Fix-shape: distinguish "key absent" from "key present with null/empty" in `_parse_build_plan_frontmatter_scope` (return a sentinel or change to `tuple[bool, str | None]`); have `_detect_active_scope` skip inference when key was explicitly null. Doesn't bite the framework's own v1.5.1 plan (sets `scope: v1.5.1` explicitly). Filed from /critic cumulative WARNING on 2026-05-23 (v1.5.1 Chunk 05). (critic)

- **[TST-2R7H]** Add fixture coverage for `cumulative-final`/`cleanup` Type fall-through to default gate
  `effort: S · impact: M · area: tests · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Code analysis confirms only `designer-handoff` skips the Critic gate; the other Type values (`code`, `doc-only`, `cleanup`, `cumulative-final`) all fall through to the default gate path. But no dedicated test fixture pins this — `TestDesignerHandoffSkipsCriticGate` only covers the explicit skip branch. A refactor that accidentally broadens the skip list (e.g. `if chunk_type in {"designer-handoff", "doc-only"}`) would silently regress. Fix-shape: add a parametrized `TestNonHandoffTypesFallThroughToGate` covering the four fall-through Types. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MIG-8C3V]** migrate's CLAUDE.md transform leaves a double blank line at the top of the migrated file
  `effort: S · impact: S · area: migration · source: user · added: 2026-06-02 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  When `apply_claude_anchor` strips the framework generator comments via `_drop_generator_comments` (`lib/migrate_plugin.py`), it removes the comment lines but leaves the blank line that preceded them adjacent to the blank line that followed, producing two consecutive blank lines between the H1 title and the first product section. Cosmetic only (markdown collapses it on render), zero semantic impact, but it's a wart in a diff meant to be pristine. Found during the v2.0.0 1.x→2.x migration acceptance test against ../discodon (2026-06-02). Fix: collapse 3+ consecutive newlines to 2 in the assembled CLAUDE.md, or drop blank lines left adjacent to removed generator comments. Low priority / trivial. (user)

- **[MET-4K8Z]** 8-surface cascade pattern — anticipate token-budget pressure in chunk plans
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Chunk 05's source-of-truth guardrail threading touched 8 surfaces (product-claude / Critic SKILL / 2 critic-review / 2 pr-review / methodology / build-plan template). Same pattern Requirements Precede Code (v1.3.15) hit. When a chunk introduces a project-wide structural concept, the plan should enumerate the surface count up front so token-budget bumps (and the aggressive trim that precedes them) are anticipated, not discovered. Worth promoting to methodology after one more datapoint; until then, captured as observation. Filed from Chunk 05 reflection, 2026-05-18. (reflection)

- **[MET-1T5W]** Document the `new \`path\`` forward-ref convention in methodology prose
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `verify-chunk-refs` (F3) supports `new \`path/to/file\`` syntax to mark forward-references for not-yet-created files; this is implemented, tested, and documented inside `templates/build-plan.md`'s inline HTML comment, but not in `methodology/planning.md` prose. Authors who write plans without copying the template won't know the keyword exists and will get spurious BLOCKING ref-drift findings for chunks creating new files. Fix-shape: add a one-paragraph "Forward-references" note to planning.md near the build-plan-structure section. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-8N2C]** Tighten F8 worked-example numbering language for consistency
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `methodology/planning.md:118` describes the `verify-api` step as "the first item in its Done-when", while the worked example a few lines down uses "step 0" (`0. verify-api: ...`). Both true, but the terminology is inconsistent. Fix-shape: change line 118 to "prepended as step 0 in its Done-when (so existing step numbering is preserved across chunks with and without a foreign API)". One-line tweak. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-2D9K]** `methodology/planning.md` parallel section for the `Visual change:` build-plan field
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  F8 added a "Foreign API Verification" section to planning.md when introducing `**Foreign API:**`. F10 (Chunk 14) added `**Visual change:**` to the build-plan template with inline-comment guidance but no parallel planning.md section. The build-plan template's HTML comment is sufficient discoverability for v1.4.0; consider a v1.5 enhancement (~50 tokens) to align with the F8 precedent and pre-empt the asymmetry NOTE the Critic emitted. Filed from /critic Chunk 14 final review NOTE. (critic)

- **[DOC-2W9P]** Repoint stale `tools/lib/` example paths in `documentation/` design specs to plugin-native
  `effort: S · impact: S · area: docs · source: builder · added: 2026-06-03 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `documentation/post-sync-advisory-spec.md` (≈ lines 197/218/276/296/434/435) and
  `documentation/governance-tax-followups.md` §3 still illustrate the advisory/probe layout with
  retired file-sync paths (`tools/lib/probes/…`, `tools/product-hook`, `prawduct-setup.py`, `run_sync`).
  The spec is still the authoritative reference for `lib/advisory_store.py`, so the illustrative paths
  should point at `lib/advisory_store.py` / `hooks/hooks.json` / `bin/prawduct-hook`. Internal design
  archive, not user-facing — deferred from the 2.0-rock-solid pass Wave 2. (builder)

- **[ADV-3K7Q]** Namespace skill names in plugin advisory output (briefing recommended_action + dismiss hint)
  `effort: S · impact: S · area: advisory · source: critic · added: 2026-06-03 · status: shipped · closed-by: #53 (12e03b3, v2.0.3) · reviewed: 2026-06-03`

  Surfaced when the advisory-probe-at-SessionStart fix made post-sync advisories visible in plugin repos for the first time. The briefing rendered un-namespaced skill forms (`/backlog migrate`, `/prawduct-advisory dismiss`) where a plugin repo resolves `/prawduct:backlog` / `/prawduct:advisory`. info-priority/cosmetic; not a broken gate.

  **Shipped (#53 — `fix(plugin): namespace all agent-facing command forms in the plugin runtime`, commit `12e03b3`, in develop/v2.0.3):** the runtime gate-message + advisory-output sweep landed. `bin/prawduct-hook` now renders `/prawduct:advisory` (0 bare `/prawduct-advisory` remain) and `/prawduct:critic`/`/prawduct:pr` in every agent-facing gate; `lib/operator_verification.py`'s `/pr create` stragglers namespaced. Pinned by `TestPluginRuntimeNamespacing` (assert-absent source-scan) + strengthened stop-gate/divergence tests. The byte-parity-lock half (`backlog_probes` → `DIVERGED_MODULES`) is moot: `lib/backlog_probes.py` and its frozen `tools/lib/` twin were both deleted in M4 (v2.0.3, Chunk 3) along with the `legacy_backlog_format_probe`, so source #1 no longer exists. The stale standalone branch `origin/fix/advisory-namespace-backlog` (single commit, same title/SHA-content as #53) was superseded by the merged PR and can be deleted. (Triage 2026-06-03 — the "do not archive until merged" hold is satisfied: the work is in HEAD.)

- **[CRT-2M5P]** Critic skill `Bash(git *)` allowed-tools is too broad — permits state-mutating git verbs (checkout/stash/reset/branch)
  `effort: S · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Observed v1.5.1 Chunk 05 verify-resolutions: the Critic ran `git checkout d2b8af4` (mid-review!), corrupted the working tree to a detached HEAD state, and recovered via stash+pop. All my modified files survived but only because the Critic chose to restore them. The skill `allowed-tools` entry `Bash(git *)` permits every git subcommand including ones that mutate the working tree. Read-only verbs are sufficient for Critic's review purpose. Fix-shape: replace `Bash(git *)` with an explicit allow-list of read-only verbs — `Bash(git diff *)`, `Bash(git log *)`, `Bash(git status *)`, `Bash(git show *)`, `Bash(git ls-files *)`, `Bash(git rev-parse *)`, `Bash(git merge-base *)`, `Bash(git branch --show-current)`, `Bash(git for-each-ref *)`. Or, more concise, add a deny-list (subject to the same v1.5.1 Chunk 02 caveat that skill-frontmatter denies may not enforce). Filed from /critic verify-resolutions NOTE on 2026-05-23 (v1.5.1 Chunk 05). (critic)

  **Resolved (reduce-governance-tax Chunk E):** The Critic's `allowed-tools` now grants explicit read-only git verbs (diff/log/status/show/ls-files/rev-parse/merge-base/branch --show-current/for-each-ref) instead of the broad `Bash(git *)`, so a review can no longer run `git checkout`/`reset`/`stash` and corrupt the tree. Applied to `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`, and the `critic-test` shadow skill; pinned by `test_critic_skill_metadata.py::test_git_is_read_only`.

- **[CRT-8H3D]** v1.5.1 Chunk 02's `!Bash(pytest*)` deny patterns in skill `allowed-tools` do NOT structurally block pytest invocation
  `effort: M · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Confirmed by v1.5.1 Chunk 04 Critic WARNING: the Critic agent ran `python3 -m pytest` despite the four deny patterns in `.claude/skills/critic/SKILL.md` `allowed-tools`. The patterns appear to be documentation-only; Claude Code's skill `allowed-tools` field is allow-list semantics and the `!`-prefixed deny syntax is not honored there (or is overridden by project-level `settings.local.json` `permissions.allow: ["Bash(python3:*)"]`). Fix-shape options: (1) move deny patterns to `.claude/settings.json` `permissions.deny` (project-wide block — but would also block the *builder* from running pytest, which is wrong); (2) scope deny via a wrapper command or use a tool-namespace filter the harness actually enforces; (3) accept that the constraint is prose-and-allow-list only (the allow-list IS restrictive — `Bash(python3 tools/product-hook ...)` exact-strings shouldn't match pytest in pure-allow mode), and soften the v1.5.1 change-log / memory rule claim of "structurally enforced". Add a deliberate negative-path probe test before claiming structural enforcement. Filed from /critic chunk WARNING on 2026-05-23 (v1.5.1 Chunk 04). (critic)

  **Resolved (reduce-governance-tax Chunk E):** Structural enforcement is the PURE-ALLOW list (the `!Bash(...pytest*)` entries are documented as non-functional). Added the negative-path probe the item asked for: `test_critic_skill_metadata.py::test_no_allow_pattern_permits_pytest` asserts no allow pattern can match a pytest invocation. The skill comment already softens the 'structurally enforced' claim to name the allow-list as the real mechanism.

- **[SYN-2K9N]** Template drift advisory dismiss/acknowledge mechanism
  `effort: M · impact: M · area: sync · source: critic · added: 2026-04-16 · status: shipped · closed-by: reduce-governance-tax Chunk B · reviewed: 2026-05-30`

  **Resolved** by the template-drift fire-once fix (Chunk B of the governance-tax reduction): a drift advisory now surfaces exactly once per template change, then sync refreshes the stored template hash so it self-resolves — directly fixing the "nags every session" pathology. This is a cleaner fix than the proposed `dismissed_advisories` list / `/janitor dismiss` flow: place-once files are user-owned ("surface the change once, then it's yours"), so auto-resolving after one surfacing matches the semantics without new dismiss machinery. The user's place-once file is never overwritten. (critic)

- **[BLD-9R3K]** `infer-critic-mode` does not detect a build plan living in `.prawduct/artifacts/`
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-29 · status: shipped · closed-by: v1.6.0 Chunk 06 · reviewed: 2026-05-29`

  During v1.6.0 Chunk 02 the helper returned `rule-4 final: no active build plan ... fail-safe to thoroughness` even though `.prawduct/artifacts/v1.6.0-advisory-infrastructure-plan.md` is the active plan. **Resolved** by Chunk 06's `active_build_plan:` pointer (project-state.yaml) + the shared `core.resolve_build_plan_path` resolver, mirrored inline in product-hook and used by `infer-critic-mode`, `regen-views`, the stop-hook gates, `verify-chunk-refs`, and `check-pr-trivial`. The chosen shape is the explicit pointer (not the `*plan*.md` glob the original fix-shape proposed — a glob is ambiguous when multiple scope-named plans accumulate, which this repo demonstrates). Validated against both the framework repo (pointer → scope-named plan) and the back-compat default (no pointer → `build-plan.md`). Filed from /critic NOTE on 2026-05-29 (v1.6.0 Chunk 02); closed 2026-05-29 (v1.6.0 Chunk 06). (critic)

- **[JAN-4F7M]** Rewrite `skills/janitor/SKILL.md` "Template Currency" theme for plugin distribution
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-06-03 · status: shipped · closed-by: v2.0.3 · reviewed: 2026-07-17`

  The janitor skill's **Template Currency** investigation theme (and its Step 1 framework-health
  pre-check + Step 7 hash-update guidance) still teaches the file-sync maintenance workflow:
  comparing the consumer's place-once artifacts against `framework_source/templates/*` via
  `.prawduct/sync-manifest.json` `place_once_templates` stored hashes. Under plugin distribution a
  consumer carries no sync-manifest (init never creates it; `/prawduct:migrate` removes it) and has
  no `framework_source` checkout, so the whole theme is inert for migrated/plugin-native repos.
  Surfaced during M4 Chunk 4: `test_v5_templates.py::TestJanitorSkillTemplateCurrency` (which pinned
  this content via the now-deleted `templates/skill-janitor.md`) was DELETED rather than retargeted,
  precisely to avoid pinning stale guidance. Resolve: rework the theme for plugin-era maintenance —
  what does "is this product's tooling current with the plugin?" mean when governance ships from the
  plugin and updates via `autoUpdate`? — and add fresh `skills/janitor/SKILL.md` structural coverage
  to replace the deleted mirror test. Candidate to fold into M4 Chunk 5 (docs/residue) if cheap, else
  a standalone janitor-skill pass. Filed from M4 Chunk 4 on 2026-06-03. (builder)

  **Resolved (v2.0.3 pre-promotion, 2026-06-04):** reworked the Template Currency theme for plugin
  distribution — it now compares the product's artifacts against the read-only plugin templates at
  `${CLAUDE_PLUGIN_ROOT}/templates/` (no `sync-manifest.json`, no `framework_source`, no place-once
  hash store). The Step 1 framework-health pre-check now confirms the plugin runtime is reachable
  (`${CLAUDE_PLUGIN_ROOT}/templates/` readable) instead of asserting a sync-manifest exists; Step 7
  records resolved drift in `.prawduct/change-log.md` rather than recomputing template hashes.
  Structural coverage restored via `test_plugin_runtime.py::TestJanitorSkillPluginEra` (asserts no
  `sync-manifest`/`framework_source`/`place_once` residue + the plugin-root target). The same pass
  also cleaned the file-sync-era `_METADATA_PREFIXES` entries (`.claude/skills/`, `tools/product-hook`)
  from both mirrors (`bin/prawduct-hook` + `lib/critic_mode.py`) — a product's own `.claude/skills/`
  skill now counts as gated code, not excused metadata (`TestMetadataPathClassification`). Surfaced by
  the develop→main release-readiness review; folded into v2.0.3 rather than deferred. 652 passing. (builder)

- **[DOC-7H2K]** Port `/prawduct:doctor`'s remaining file-sync-coupled flows to the plugin model (Chunk 13)
  `effort: L · impact: M · area: doctor · source: builder · added: 2026-06-02 · status: shipped · closed-by: v2.0.0 Chunk 13 · reviewed: 2026-07-17`

  Surfaced during v2.0.0 Chunk 11 (dogfood + self-containment audit). The plugin's `skills/doctor/SKILL.md` is a thin wrapper over `python3 <framework>/tools/prawduct-setup.py` for nearly every flow: Onboard (`setup`), Health Check (`validate`), Migrate feature opt-ins (`migrate --enable-coverage|--enable-settings-layout|--enable-operator-verification`), and Audit Learnings (`audit-learnings`). In a migrated consumer there is no framework checkout, so all of these break — only the **Verify** flow was ported this chunk (new `prawduct-hook verify-operator-verification`, which operates purely on the consumer's `.prawduct/`). The rest were deliberately NOT ported because (a) `setup`/`validate` ARE the file-sync engine, which design §5 / Chunk 5 deliberately excludes from the plugin runtime — bundling them would re-introduce exactly what the architecture removes; and (b) the plugin onboarding model is "install the plugin + `/prawduct:migrate`", not a `setup` script. Resolve as part of Chunk 13 (remove file-sync + its name): rework the doctor skill to the plugin model — Onboard → install + `/prawduct:migrate`; Health Check → a plugin-native `prawduct-hook` validate/health read of the consumer's own `.prawduct/` (no framework path); coverage / operator-verification opt-ins → plugin-native `project-state.yaml` flag flips (need no sync); decide whether `--enable-settings-layout` (pure file-sync settings normalization) and `audit-learnings` survive in the plugin world. Also: `lib/operator_verification.py::run_verify_entry`'s "no queue" error hint still names the legacy `prawduct-setup migrate --enable-operator-verification` path — repoint once the plugin-native enable exists. And the legacy `agents/` tree ships inside the plugin and the loader picks it up as frontmatter-less agents (`claude plugin validate` warnings) — Chunk 13's grep-sweep across `agents/` should drop it. Filed from Chunk 11 dogfood on 2026-06-02. (builder)

  **Resolved (Chunk 13, 2026-06-02):** all four flows reworked off file-sync — Onboard → install + `/prawduct:migrate`; Health-Check → plugin-native Read/Glob of the consumer's own `.prawduct/`; opt-ins (F4/F10) → `project-state.yaml` flag flips (F5 settings-layout dropped as file-sync-only); Audit-Learnings → new plugin-native `prawduct-hook audit-learnings` (port of `lib/audit_learnings_cmd.py`). Operator-verification hint repointed off `prawduct-setup migrate`. The legacy `agents/` tree dropped (clears the 6 `claude plugin validate` frontmatter warnings). `/prawduct:doctor` `allowed-tools` tightened (broad `Bash(python3 *)` removed). Confirmed by the Chunk-13 Critic (NOTE 2). (builder)

- **[MIG-M4-REMOVE]** Permanently delete the file-sync engine + payload + shims (post-2.0.0 milestone M4)
  `effort: L · impact: M · area: distribution · source: builder · added: 2026-06-02 · status: shipped · closed-by: M4 (v2.0.3) · reviewed: 2026-06-03`

  The terminal step of the file-sync→plugin transition, deliberately deferred out of 2.0.0. Chunk 13 removes file-sync only from THIS repo's active path; the engine stays a **live service** for un-migrated external repos, because `tools/product-hook` + `tools/lib/*` are `MANAGED_FILES` synced into products and a product's own `try_sync()` calls back to this framework's `tools/prawduct-setup.py sync` every session (fail-soft: missing script ⇒ no crash, the sibling keeps governing on its last-synced version). **Blocked on:** marketplace live (Chunk 2) AND every local sibling migrated to the plugin (`/prawduct:migrate`). Inventory is the owner's — manual, "only this one machine"; no consumer census / deprecation advisory is being added (owner decision 2026-06-02, keep 1.x frozen). When unblocked: delete `templates/`, the 7 `.claude/skills/*` sync sources, `tools/product-hook`, `tools/lib/*` (sync modules), `tools/prawduct-setup.py`, and the `prawduct-{init,sync,migrate}.py` shims; finish the deep name-sweep across the (now-removed) `templates/`+`tools/` — *you can only remove a mechanism's name from a path once the mechanism has left it.* After M4, a stale un-migrated sibling fails-soft (silent no-update), an acceptable terminal contract because it was warned during M3. See build-plan Chunk 13 "Permanent-removal path (M1–M4)". **Cleanup rider (Chunk 13 Critic NOTE 1, 2026-06-02):** the plugin `lib/audit_learnings_cmd.py` is byte-parity-locked to `tools/lib/audit_learnings_cmd.py`, so its `run_audit_learnings` docstring still names the legacy `prawduct-setup audit-learnings` path (correct for the file-sync copy, stale for the plugin). When `tools/lib/` is deleted here, the parity lock dissolves — repoint that docstring to `prawduct-hook audit-learnings`. (builder)

  **Resolved (M4, v2.0.3, 2026-06-03):** the owner directive (2026-06-03, "we DO NOT need backwards compatibility … remove ANY cruft that exists only for back compat to pre-2.0") lifted the consumer-census block — the inventory is "only this one machine," all local siblings migrated. M4 (5 chunks on `feat/retire-filesync-engine-m4`) executed the full removal: Chunk 2 deleted `tools/` (product-hook, prawduct-setup.py, the 3 shims, `tools/lib/`), Chunk 4 deleted the file-sync templates (`product-claude`/`critic-review`/`pr-review`/`build-governance`/`product-settings.json`/`conftest.py` + the 7 `skill-*.md` sources) and slimmed `lib/core.py`, Chunk 5 removed the committed `.prawduct/` protocol-doc residue + swept the deep name-sweep across kept code/docs/templates. The `run_audit_learnings` docstring rider was discharged (repointed to `prawduct-hook audit-learnings`, Chunk 5). Deferred fragment: `[JAN-4F7M]` (the janitor skill's file-sync Template Currency theme). (builder)

- **[BLD-3X9M]** Resolve `status=shipped` semantic — per-chunk merge vs. tagged release
  `effort: S · impact: M · area: build-plan · source: builder · added: 2026-05-18 · status: shipped · closed-by: v2.0.0 Chunk 14 · reviewed: 2026-07-17`

  Chunk 05 dogfooding raised an open question: does `status=shipped` on a change-log tag line mean "merged to mainline" (per-chunk timing — Status flips `[x]` when the chunk commits) or "in a tagged release" (wave timing — Status flips when a release entry covers it)? Current state: Chunk 05 left `[ ]` pending Wave 2 release entry. The Critic check (mismatch → WARNING) is symmetric, so either interpretation is internally consistent once chosen. Decide before Wave 2 release; document the chosen semantic in `templates/change-log.md` schema doc. Filed from Chunk 05 work, 2026-05-18. (builder)

  **Resolved (v2.0.0 Chunk 14, 2026-06-02):** decided as **tagged-release / wave timing** — `status=shipped` means "in a tagged release" and flips Status `[x]` only at the `develop → main` release; `status=merged` is the develop-phase intermediate that does NOT flip checkboxes. Documented in `docs/release-process.md` (release checklist + "Why the checkboxes stay `[ ]` during development") and the v2.0.0 build-plan "Checkbox model" note. (Schema-doc home moved from `templates/change-log.md` to `docs/release-process.md` under the plugin model.)

- **[DOC-4B2W]** Namespace bare command forms in plugin-bundled teaching prose (`skills/critic/*.md`, `methodology/*.md`)
  `effort: M · impact: M · area: docs/governance · source: builder · added: 2026-06-03 · status: shipped · closed-by: M4 Chunk 1 (v2.0.3) · reviewed: 2026-06-03`

  **Resolved (M4 Chunk 1, v2.0.3, 2026-06-03):** swept the 6 plugin-only prose files (`methodology/{building,planning,reflection}.md`, `skills/critic/{review-cycle,review-protocol}.md`, `skills/pr/review-protocol.md`) → `/prawduct:*`; pinned by `TestPluginDocsNamespacing` (assert-absent source-scan over the skill vocabulary). Decision (point 3): conceptual short-names ARE namespaced in the teaching prose, since a plugin repo resolves `/prawduct:*`. File-path carve-outs (`.prawduct/critic-review.md`) and the built-in `/clear` preserved; the file-sync `tools/` copies that carried duplicated prose were deleted outright in Chunk 2 rather than kept on bare forms. (builder)

  The runtime gate-message sweep (#53) namespaced `bin/prawduct-hook` + `lib/` agent-facing OUTPUT, but the plugin-bundled PROSE an agent reads via `/prawduct:*` still carries ~34+ bare command forms — `skills/critic/review-cycle.md`, `skills/critic/review-protocol.md`, and `methodology/{building,planning,reflection}.md` say "run /critic", "/pr create", "/critic cumulative" etc. where a plugin repo resolves `/prawduct:critic`, `/prawduct:pr`. Same leak class as #53, larger + lower-severity surface (teaching prose, not gates; agents can often infer the mapping, and the SessionStart briefing already lists namespaced forms). This is the "entire leak class as a build plan" follow-up.

  Scope notes for the build plan: (1) sweep the whole FORM-FAMILY per the new learning — bare `/cmd`, hyphenated `/prawduct-advisory`, legacy `prawduct-setup` — one grep per spelling; (2) preserve carve-outs: file paths (`.prawduct/critic-review.md`, `agents/critic/SKILL.md`), the Claude Code built-in `/clear`, and prose like "critic/pr skills"; (3) DECISION REQUIRED — whether to namespace conceptual short-names in teaching guides at all, or keep `/critic` as the canonical short name with a one-time namespacing note (judgment call, raise with owner); (4) the frozen `tools/` copies of any duplicated prose stay bare; (5) pin with an assert-absent source-scan like `TestPluginRuntimeNamespacing`, extended to the docs surface. (builder)

- **[SYN-3D8K]** Align `enable_v1_4_views` detector/mutator on inline-comment forms
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: dropped · reviewed: 2026-05-29`

  Same pattern Chunk 10 fixed in `enable_v1_4_coverage`: `is_views_enabled`-style detection strips inline comments via `split('#', 1)`, but `enable_v1_4_views`'s flip uses exact `line.strip() == "views_enabled: false"`. A user line like `views_enabled: false  # opt-out` is detected as present-and-off but never flipped → silent no-op (manifest flag still set, file unchanged). Edge case (templates emit bare values), but the asymmetry will keep biting until both helpers use the same shape-aware match. Apply the Chunk-10 fix-shape: iterate lines, skip indented, compare comment-stripped value, re-attach inline comment on rewrite. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 10) — the views variant was left alone in-chunk to keep diff scope tight. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the enable_v1_4_views mutator/flip lived in the deleted sync engine; only the is_views_enabled reader survives and it isn't the buggy path.

- **[BLD-0G6V]** Backfill Done-when blocks on Chunks 05-14 of v1.4 build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  Chunks 00-04 each carry a Done-when block; Chunks 05-14 do not. Not a chunk-close blocker (chunk-mode Critic still fires on declared `**Critic mode:**`), but worth backfilling for consistency before Chunk 06 starts. Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — backfilling Done-when on the long-shipped v1.4 plan has no consumer.

- **[BLD-7A2E]** Capture pre-commit-regen scope-shift in Wave 2 retrospective / change-log
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  F1 plan line 234 promises "pre-commit regen of build-plan Status from work-log"; Chunk 05 shipped on-demand `regen-views` plus methodology docs that tell users to invoke manually (Chunk 06 plan note confirms this is deliberate as "ad-hoc regen between commits"). The deliverable line was flagged "high level — to be expanded before chunk starts" so this is not silent, but the Wave-2 release entry / retrospective should record the explicit decision: pre-commit hook (deferred to Chunk 07's migration tooling or Wave-3) vs. on-demand `regen-views` (shipped now). Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the v1.4 Wave-2 retrospective window is closed; the decision shipped.

- **[DOC-6P3Q]** v1.4 release-readiness: document the new `/pr create` gate before tagging
  `effort: S · impact: M · area: docs · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  F2 ships hard enforcement: `check-cumulative-critic` blocks `/pr create` without a fresh cumulative-mode findings file. Product owners who sync v1.4 without reading the change-log will hit the gate cold and read it as a regression. Before tagging v1.4 (after all waves merge): add a change-log entry naming the new gate, a `prawduct-doctor` migration prompt if relevant, and a Compatibility-Strategy line in the release notes (the cumulative gate is new structural enforcement, not a behavior tweak). Filed from /critic cumulative NOTE on 2026-05-18. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the 'before tagging v1.4' window is closed; the /pr cumulative gate shipped and is live.

- **[SYN-7L0D]** Remove dead `if rel_path in ("CLAUDE.md",)` lines in sync_cmd.py `template`-strategy branch
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-08 · status: dropped · reviewed: 2026-05-29`

  Two pre-existing branches (`force=True` overwrite + `current_hash != stored_hash` skip) emit a "re-read CLAUDE.md" note guarded by `if rel_path in ("CLAUDE.md",)`. CLAUDE.md uses `block_template`, not `template`, so it can never reach these branches. Dead since the strategy split. Remove or document. Filed from /critic chunk on 2026-05-08 — flagged after the same dead pattern was caught in the new stale-clean branch (already removed there). Two-line cleanup; defer until next sync_cmd.py touch. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the dead CLAUDE.md branch lived in the deleted sync_cmd.py.

- **[SYN-3F6P]** Sync: skip-summary line counts + `--diff` preview flag
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-05-08 · status: dropped · reviewed: 2026-05-29`

  When sync skips a file as "local edits," it gives no signal about the size or shape of the divergence — the user must `--force` blind or manually diff. Add to the skip note: `+N lines / -M lines vs current template`. Add a `--diff` flag that prints the unified diff(s) of would-be skips (or all would-be changes) without writing anything. For `block_template`, also note that content outside markers won't change. Lets users decide whether to force without a separate investigation. (reflection)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — pure file-sync `sync` UX (--diff/--force/skip-summary); the sync engine is gone.

- **[TST-8B3X]** Audit public-function coverage exemptions in `tests/preferences/test_public_function_coverage.py`
  `effort: M · impact: S · area: tests · source: builder · added: 2026-05-05 · status: dropped · reviewed: 2026-05-29`

  Four functions in `tools/lib/` are exercised transitively but never directly referenced as a function call (under the tightened detection that requires `Attribute.attr` or `Name` in `Call.func`): `core.py::log`, `core.py::load_json`, `migrate_cmd.py::strip_test_tracking`, `migrate_cmd.py::generate_sync_manifest`. For each, decide: (a) add a direct unit test class, or (b) rename to `_<name>` (private-by-convention) and remove from the exemption list. Rationale captured inline in `EXEMPT_FROM_DIRECT_COVERAGE`. (builder)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — two of the four named functions were in the deleted tools/lib/migrate_cmd.py and the exemption list referenced the old tree (a fresh public-function-coverage audit against lib/ can be re-filed if wanted).

- **[SYN-5G2J]** Extract `_git_run` helper for fw-dir git lookups
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-01 · status: dropped · reviewed: 2026-05-29`

  `_get_framework_head_commit`, `_get_template_last_change` (sync_cmd.py), and the inline `git log -1` inside `_compute_framework_freshness` (product-hook) share the same try/except + subprocess.run + timeout=10 + broad-except + None-on-failure pattern. Three is the minimum-viable case for extraction. If a fourth fw-dir git lookup gets added, factor into `tools/lib/core.py` as `_git_run(fw_dir, args, timeout=10) -> str | None`. Currently small and well-commented; not urgent. (critic, 2026-05-01)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the three _git_run call sites were framework-dir freshness probes in the deleted sync_cmd.py/product-hook.

- **[SYN-3T7B]** run_sync() decomposition
  `effort: M · impact: M · area: sync · source: janitor · added: 2026-04-16 · status: dropped · reviewed: 2026-05-29`

  Extract per-strategy logic (template, block_template, always_update, merge_settings) from 337-line function in sync_cmd.py. (janitor)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — run_sync() was the deleted sync_cmd.py dispatcher; no 2.0 analog.

- **[TST-1M6V]** Pre-existing timeout flakes in test_product_hook.py
  `effort: M · impact: S · area: tests · source: builder · added: 2026-04-16 · status: dropped · reviewed: 2026-05-29`

  `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` intermittently hit the 15s timeout. May need investigation into why the product-hook subprocess hangs in certain test configurations. (builder)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** both named tests were removed with the file-sync engine in M4 — `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` (manifest = file-sync) no longer exist.


