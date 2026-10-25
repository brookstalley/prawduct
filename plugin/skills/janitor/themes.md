# Janitor — Investigation Themes

Companion to `SKILL.md`, read at the start of Step 2 (Survey). The skill is the dispatcher and the process; this file is the taxonomy.

These themes are universal starting points — they apply to any project regardless of domain, language, or technology. **They are not a checklist.** Adapt each theme to what you find in this specific codebase. A firmware project's "controllability" looks different from a web app's. A console game's "test fitness" looks different from a backend service's.

After investigating all themes, step back and ask: **what else has drifted, accumulated, or been overlooked that doesn't fit any theme?** The best janitor finding is often one nobody expected. Every project has its own maintenance needs shaped by its domain and history — discover them.

### Version Control Hygiene

Is the repository's history and branch structure clean and navigable?

- Branches that were merged but never deleted, and worktrees left behind (`prawduct-hook git-tidy` lists each with its proof; remove them with `--apply` on the owner's yes, not by hand)
- Branches with no activity within the staleness window (default: 14 days; see Arguments)
- Branches superseded by other work — started, then abandoned in favor of a different approach
- Orphaned work that was started but apparently abandoned with no resolution
- Files that should be ignored but aren't (build artifacts, editor files, secrets) — or vice versa. This is general gitignore hygiene; the prawduct gitignore *contract* (session-file entries, the retired `build-plan.md` entry) is `/prawduct:doctor` Health-Check #8 (`docs/doctor-vs-janitor.md`).

### Structural Clarity

Does the project's file organization reflect its architecture? Would a new contributor find things where they expect them?

- Source and test layout — intuitive, consistent, and conventional for this language and framework
- Module boundaries — do directory, package, or namespace boundaries match logical component boundaries?
- Configuration organization — scattered across the tree or collected sensibly?
- Dead directories — remnants of old features, experiments, or refactors that weren't cleaned up

### Code Health

Are the codebase's internal qualities sound? Would a domain expert reviewing this code find it unsurprising?

- Encapsulation — is internal state leaking across boundaries? Are there public APIs that should be private?
- Duplication — repeated logic that should be consolidated, or near-identical implementations that diverged
- Separation of concerns — are responsibilities clearly divided, or is business logic tangled with infrastructure?
- Coupling — are components appropriately independent? Can one module change without rippling?
- Complexity — is complexity proportionate to what the code actually does?
- Unmodeled state-based problems — anywhere the code moves through a discrete set of conditions (phases, modes, lifecycle stages, UI views, connection status, workflow steps) where the current condition governs what's valid, but the conditions aren't enumerated, valid/invalid transitions aren't named, and "what condition are we in" has to be reconstructed from flag combinations or order-dependent conditionals. Look for clusters of interdependent booleans that must stay in sync, phase/stage/mode variables whose transitions are scattered across call sites, and recovery paths that don't have a known-good condition to return to. Flag candidates for explicit modeling regardless of implementation shape (enum, class, protocol, reducer, type, schema, or doc all qualify) — the goal is to make the conditions, transitions, and invariants explicit, not to impose a particular mechanism.

### Artifact Fitness

Do all forms of documentation — comments, READMEs, specs, configs, generated docs, inline TODOs — describe the current system accurately?

- Stale documentation that no longer matches the code it describes
- Redundant documentation saying the same thing in multiple places (creating drift risk)
- Missing documentation where complexity or non-obvious behavior warrants explanation
- Orphaned docs describing removed or replaced features
- TODOs for work that was completed, or abandoned long enough to decide on

### Template Currency

Have product artifacts kept pace with framework template improvements?

When the session briefing shows template drift advisories, or when running a full survey, compare the product's artifacts against the current framework templates the plugin ships at `${CLAUDE_SKILL_DIR}/../../templates/`. The product's artifacts were created from these templates at onboarding; the plugin's templates evolve over time, so a product can fall behind.

- project-preferences.md — Are there new preference fields the product hasn't declared?
- conftest.py — Are there new test infrastructure patterns available?
- boundary-patterns.md — Are there new contract surface types to consider?
- test-specifications.md — Are there new testing strategies (e.g., property-based testing) in the template that this product's specs don't address? Compare by reading the plugin template directly at `${CLAUDE_SKILL_DIR}/../../templates/test-specifications.md`.

For each template (`${CLAUDE_SKILL_DIR}/../../templates/<file>`), compare it with the product's version and recommend the missing sections that fit this product's domain and structural characteristics; mark the rest "not applicable".

This is advisory, not mechanical — a CLI tool doesn't need property-based testing guidance just because the template now includes it. Use the product's structural characteristics and domain to judge relevance.

### Test Fitness

Are tests earning their maintenance cost? Do they catch real bugs and document real behavior?

- Behavioral coverage — are edge cases, error paths, and boundary conditions tested?
- Test quality — testing behavior (durable) or implementation details (brittle)?
- Test reliability — flaky tests or hidden dependencies on external state or ordering?
- Test organization — is the structure intuitive and navigable?
- Test speed — fast enough that developers (and agents) actually run them?

### Dependency Health

Are external dependencies current, justified, minimal, and secure?

- Unused dependencies — imported but not used, or listed but not imported
- Deprecated or unmaintained dependencies with no migration plan
- Known security vulnerabilities in current dependency versions
- Version constraints that are too tight (blocking updates) or too loose (risking breakage)

### API Design & Versioning Hygiene

If this product exposes an API — any programmatic surface others call (a network service, a library/SDK, an on-device/platform interface, or a CLI), not just HTTP/REST — is that contract designed to evolve without breaking its consumers?

- Versioning — is there a recorded versioning scheme and granularity (`design_decisions.api_versioning_approach`), or is the surface unversioned by unexamined default? (`/prawduct:doctor` check #9 flags a missing decision; the `api-versioning` advisory nudges ambiently.)
- Deprecation & compatibility — is there a sunset/deprecation policy and a breaking-change signal? Are changes additive (tolerant-reader, never remove or repurpose a field) so new versions stay rare?
- Error model — is the error envelope consistent across the surface (`design_decisions.api_error_model_approach`), or does each operation shape errors differently?
- Protocol semantics — the correctness conventions for whatever the surface actually is. For HTTP/REST: status codes, PUT vs PATCH, conditional requests / ETags, idempotency keys. For a library/SDK: semver discipline and stable signatures. For a CLI: stable flags, exit codes, and output contracts.
- Pagination, filtering, sorting, and payload/size limits — present and consistent wherever collections are returned?
- Wire conventions — the footguns: timestamps (ISO-8601/UTC), money (minor-units or decimal string, never float), casing, opaque IDs, string enums, null/optional semantics.
- Surface inventory & stability tiers — is the public contract distinguished from internal/admin surfaces, and are experimental/stable/deprecated tiers marked? (The OWASP API9 "improper inventory" failure mode.)
- Published contract — is there a maintained contract artifact (`templates/api-contract.md`) consumers can rely on, kept current with the code?

Survey, not gate — surface what's undecided or drifting. The recorded *decisions* (versioning, error model) are the only gated parts, and they live in the Critic and the `api-versioning` advisory, not here.

### Controllability

Can a developer — human or AI agent — control, debug, test, and observe the entire system effectively?

- Can the full system be built and run from a clean checkout with documented steps?
- Can individual components be tested in isolation?
- Are there development tools, scripts, or fixtures that are missing, broken, or undocumented?
- Can an agent exercise the system end-to-end for debugging and verification?
- Is there adequate observability (logs, metrics, debug output) for diagnosing problems during development?

### Obsolescence

Has past work left behind artifacts that no longer serve a purpose?

- Dead code — functions, classes, or modules that nothing calls
- Completed migrations — migration logic for transitions that finished
- Exhausted feature flags — flags for features that shipped or were abandoned
- Unnecessary backwards compatibility — shims, fallbacks, or adapters for versions nobody runs
- Resolved TODOs — comments marking work that was done but the marker wasn't removed
- Stale build plans — a plan in `.prawduct/artifacts/` whose work is over. Two shapes, and the second is the one that accumulates: **completed** (every chunk done or dropped) and **superseded** (work stopped, was descoped, or was absorbed elsewhere — a half-finished plan is never finished, so nothing else ever sweeps it and it sits in the live directory reading as active). Clean up: **archive, never delete** — `prawduct-hook archive-plan <path> --state completed|superseded`, which stamps the plan with what became of it and moves it into `archive/`. Its open chunks are left as they are; they record how the work ended. On gitflow, leave a merged-but-unreleased plan live until its release ships

### Norm Health

Are the product's declared norms (`## Direction` sections in `.prawduct/artifacts/*.md`, norm rows in the preferences Enforcement table — `/prawduct:methodology norms`) still holding, still justified, and still moving? This is the deep time-domain sweep the advisory probes cannot do: probes fire only on machine-readable hooks (dates, backlog-id literals, structural presence); this theme owns the judgment half. When the product has no ratified norms, note that and move on — ratification is `/prawduct:doctor`'s flow, not the janitor's.

- **Erosion — distance from each norm.** Measure global distance: violation sites (search for what the norm constrains), waiver pragmas and open exception items pointing at it, new code that quietly stopped following it. Point-in-time distance suffices on a first run; **record the measurement** so the next sweep sees the *trend* — many individually-defensible exceptions summing to a dead norm is exactly what no single diff review can see. Record shape: `norm_health:` in `project-state.yaml` is a list, one entry per sweep — `- date: <YYYY-MM-DD>` plus a `measurements:` map of norm handle → one-line distance (e.g. `"telemetry-substrate": "3 violation sites, 2 open exceptions"`). **Append** a new entry per sweep (the trend *is* the history — never overwrite), keep the last 3 entries and prune older ones (git holds the full history).
- **Decay — norms that outlived their why.** A norm whose why rests on completed/abandoned work or a dead condition (the migration shipped; the scale assumption broke). Backlog-id-citing whys fire mechanically (the `dead-why` advisory); *prose* whys are this sweep's judgment. Cross-reference the Obsolescence theme rather than duplicating it: Obsolescence finds the dead code and completed migrations; Norm Health asks whether a norm's rationale died with them.
- **Stalled transitions.** For each `Status: in-transition` norm: is the tracking item live and moving? Is the interim rule still serving new work, or are builders routing around it? (The `stalled-transition` advisory catches the mechanical unedited-past-window case; the sweep judges the rest.)
- **Event-bound exception triggers.** Walk each open exception item whose `revisit:` is a free-text trigger rather than a date ("when the collector export ships") and ask: has this fired? Dated `revisit:` clocks fire mechanically (`revisit-due` advisory); event triggers fire only here.
- **Registry hygiene needing judgment** — norm statements that drifted from what the team actually holds; Direction entries whose *descriptive* surroundings went stale. Structural integrity (whys present, mechanisms exist, tracking ids on in-transition entries) is `/prawduct:doctor`'s registry-integrity check, not this sweep (`docs/doctor-vs-janitor.md`).

Erosion and decay findings enter Reconcile with the explicit fork — **re-affirm the norm and schedule cleanup, or retire it** (see Step 3). **Stamp the sweep:** on completing this theme (even with zero findings), write `norm_health_last_run: <today>` (top-level scalar) in `project-state.yaml` — the committed fact that resolves the `norm-health-sweep-overdue` advisory, mirroring `backlog_last_groomed_at`.
