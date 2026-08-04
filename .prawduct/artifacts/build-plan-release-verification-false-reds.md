---
artifact: build-plan
version: 2
scope: release-verification-false-reds
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "A command's posture follows what it produces; authority fails closed, advice fails soft → this plan is that norm applied to itself. `check-released` produces a verdict ABOUT A RELEASE, so a genuine failure must stay `failed` and exit 1 — nothing here softens a real finding. What changes is the antecedent: three paths currently reach `failed` from a state where the question was never answered. Fail-closed means failing on the answer, not on the absence of one."
      - "**No gate acquires a language-specific parser** (`architecture.md` § Direction, in-transition LNG-5W8R) → GOVERNS, and it reshaped this plan before any code was written. Its retroactivity list names this exact surface: `_VERSION_FILES` is a prawduct-layout table and `_version_from`'s `toml` branch is a hand-rolled parser for one language's manifest format — with the remedy **owner-ruled as product declaration rather than broader parsing (#576)**. The first draft of this plan had Chunk 01 making that TOML branch table-aware, which is broader parsing and would have been a silent departure. Restructured instead: R3 is satisfied by the SAME declaration that satisfies R2 — the product names the key path, so nothing infers which table — and no parsing sophistication is added. Surfaced by `/prawduct:learnings` at plan time, which is where a norm is supposed to bite."
      - "Python-implemented, never Python-specific → this is R2's whole point. `_VERSION_FILES` hardcodes prawduct's own layout and this module ships to every governed product, so a Python project using setuptools-scm — or any non-Python product with no `pyproject.toml` semantics at all — is graded against a layout it never claimed. Declaration replaces inference."
      - "Every fact has one home → the version files a product ships become a declared fact in `project-state.yaml`, read through `advisory_store.load_project_state` (the path `release_readiness.py` already uses). The module stops carrying a second, private opinion about which files those are."
      - "An independent reviewer never mutates the session it reviews → inapplicable. Nothing here touches the Critic lifecycle, the evidence store, or the critic-active window."
      - "Local-first: no network, no daemon in the governance runtime → conforms, and the boundary is already drawn correctly here. `check_github_release` is the one network call in this module, and the module docstring records why it is allowed: `check-released` is an operator/CI command, not a session gate. This plan adds no I/O and does not move that line."
      - "The plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms. Chunk 02 READS a new `project-state.yaml` key; it writes nothing. The declaration is authored by the product, not scaffolded by the plugin."
      - "Prawduct guides and reviews; it never implements → conforms. This is prawduct's own tooling, not product code; no best practice is implemented on a product's behalf."
      - "Goals and verification bind; prescribed method is advice → invoked in advance for Chunk 01. This plan prescribes an in-repo probe for `check_tag_on_main`; the GOAL is that a non-repository never yields `failed`. If the probe proves to be the wrong instrument (for example a stderr classification reads more precisely), the goal governs and the deviation is recorded rather than the prescription silently followed."
  - artifact: observability-strategy
    dispositions:
      - "Stable severity-prefix vocabulary; a dormant/degraded reader states dormancy → conforms and is the deliverable. Every new degraded path emits `unverified:` with a reason naming the real cause, never a bare skip. The existing `ERROR:`/`unverified:`/`ok:` prefixes are unchanged."
      - "Text emitted into a governed product names no prawduct-internal identifier → the new messages name the product's own config key and the real cause (`not a git repository`), never an issue number or requirement id."
      - "The governance ledger has a single writer (`ledger-append`) → inapplicable. `check-released` appends no ledger event; it prints a verdict and exits."
  - artifact: nonfunctional-requirements
    dispositions:
      - "Review wall-clock is a P0 constraint; reviewer payload is the lever → inapplicable. This plan touches no reviewer payload file — no protocol, no skill prose, no methodology guide. The one prose surface it adds (documenting the new project-state key) is product-facing configuration reference, which no review dispatch loads."
      - "State-file growth past its size threshold is an advisory, never a hard block → inapplicable. Nothing here writes to an accumulating state file; the new key is a small hand-authored declaration, and `check-released` appends nothing."
      - "A new control names the yield it expects AND emits it observably → conforms, and cheaply: the yield is the disappearance of `failed` verdicts from environments that could not ask the question, and `check-released --json` already emits per-check `state`, so a false red and an honest `unverifiable` are distinguishable in the payload without adding a field. No new telemetry is needed for this one, which is the contrast with the two DEPARTURES recorded on `review-loop-carriers`."
last_validated: 2026-08-04
---

## Requirements Confidence

**Level:** High

**Why:** Three filed defects, each with a measured repro, all in one 325-line module
with an existing 425-line test file. The failure class is named by the module's own
docstrings ("a false red is worse than no check, because a false red is how a check gets
ignored") — this plan finishes an argument the code already makes about itself.

**Open assumptions / unknowns:** one, recorded and vetoable — R2 introduces a
`project-state.yaml` key, which is a persisted format and therefore lock-in. The shape is
designed in Chunk 02 rather than assumed here.

**What would raise confidence:** exercising `verify-release.yml` at the first promotion
(#581), which is structurally impossible before it and is explicitly out of scope.

## The problem, measured

`plugin/lib/release_verification.py` ships in v3.2.4 as a **new** capability
(`prawduct-hook check-released`). Three distinct paths make it state a confident
`not-released` verdict about a release it never actually assessed:

| # | Path | Measured behaviour |
|---|---|---|
| #579 | `check_tag_on_main` line 203 | `git rev-parse <tag>^{commit}` exits 128 for *absent tag* **and** for *not a git repository*. Run from any non-repo directory: `ERROR: tag-on-main: tag v3.2.4 does not resolve to a commit`, exit 1. |
| #576 | `check_version_files` + `_VERSION_FILES` | The tuple hardcodes prawduct's layout and this module ships to every governed product. A file that is *present but carries no literal `version =`* (setuptools-scm `dynamic`, a tooling-only `pyproject.toml`) is rated `failed`, not skipped. |
| #580 | `_version_from(kind="toml")` | Scans every line and returns the first key named `version` in any table. `[tool.myplugin] version="9.9.9"` above `[project] version="1.0.0"` returns **9.9.9** and reports a false mismatch. The inline comment calls the ordering a guarantee; TOML makes no such promise. |

**They are one defect, not three.** Each conflates *"I could not ask the question"* with
*"the answer is no"* — the same `unavailable`-vs-`None` distinction the
`review-loop-carriers` work just closed in `coverage.diagnose_fix_churn` and
`briefing._summarize_critic_findings`. The module already has the right vocabulary
(`UNVERIFIABLE`, `EXIT_UNVERIFIABLE`, `--allow-unverifiable`); these three paths do not
reach it.

**Why now rather than after the release.** v3.2.4 *introduces* this command, so there is
no installed base depending on current behaviour — this is the cheapest moment the fix
will ever be, with no migration and no compatibility question. Shipping it first means
the repair is v3.2.5 and every consumer who hits a false red in between learns to
distrust the check, which the module's own docstring names as the durable cost.

## Requirements

| Req | Source | This plan |
|---|---|---|
| R1 — a check that could not ask its question reports `unverifiable`, never `failed` | #579 | Chunk 01 |
| R2 — the files carrying a release version are **declared by the product**, not inferred; an undeclared layout cannot produce `failed` | #576 | Chunk 02 |
| R3 — no version read guesses which table/key holds the value; the product names it | #580 | Chunk 02 (with R2 — same mechanism) |

**Out of scope, deliberately:**
- **#581** — `verify-release.yml` has never executed and *cannot* before the promotion:
  GitHub registers a workflow only from the default branch (`main`), and this repo merges
  to `develop`. The first promotion is its test. Already an owner ruling.
- **#575** (sentinel-branch test coverage) and **#578** (timeout message quality) —
  follow-ups; neither is a false red.

## Verification Strategy

Every requirement is verified by driving the **real** failure path, never a monkeypatched
return — the producer-side lesson `review-loop-carriers` paid a BLOCKING finding for. R1
runs the check from a genuine non-repository directory; R3 reads the adversarial table ordering
from #580's repro **in both directions**, since one ordering alone cannot tell a key-path
descent from the positional scan it replaced; R2 builds a fixture product whose declared
and undeclared layouts differ. `tomllib` is **not available on the 3.10 floor**
(`requires-python >=3.10`, CI matrix runs 3.10). This paragraph originally concluded "so the
TOML fix is hand-rolled and must be tested on that floor" — the opposite of what shipped, and
corrected here rather than left to read as a dropped constraint. Hand-rolling is what LNG-5W8R
forbids, and honouring a declared key path would have meant *growing* that parser; the read
delegates to `tomllib` and reports **unverifiable** below 3.11, so the floor is exercised as a
degraded path rather than as a second parser.

## Status

- [ ] Chunk 01: A check that could not ask does not answer
- [ ] Chunk 02: The product declares which files carry its version

Context: Plan authored 2026-08-04 on `fix/release-verification-false-reds`, cut from
`develop` at `f864cbc` (immediately after `review-loop-carriers` merged as PR #588).
Blocks cutting v3.2.4: `release_verification` is new in that release, and Phase 0 of the
release runbook asks whether everything is *fit* to ship, not merely present.

## Build Chunks

### Chunk 01: A check that could not ask does not answer

- **Description:** Close the mechanical false-red in `check_tag_on_main` — the check
  misreading its own input rather than the release being broken — and, as a recorded
  addition, the misattributed *cause* in `check_version_files`. **An earlier draft said
  "the two mechanical false-reds", counting #580 here; LNG-5W8R moved that one to Chunk
  02 (see R3), and this line is corrected rather than left to read as a dropped
  deliverable.**
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/release_verification.py` — `check_tag_on_main` establishes that it is in a
    git repository *before* reading a non-zero `rev-parse` as an absent tag, mirroring the
    `origin/main` existence probe the same function already performs one branch down (the
    precedent is in-file, and its comment already states this rule). A non-repository, or
    git failing, reports `UNVERIFIABLE` naming the real cause; a genuinely absent tag stays
    `FAILED`.
  - `plugin/lib/release_verification.py` — `check_version_files`'s no-files branch
    names the real cause. **Not in the original deliverable list; added during the build
    and recorded here rather than left to be discovered.** It is a sibling of R1 rather
    than an instance of it: R1 is about the *state* (this path already returned
    `UNVERIFIABLE`), and what changed is the *reason* — outside a repository every
    `git show` fails per-file exactly as an absent path does, so all three files
    "skipped" and the branch reported a layout question, sending a product owner to
    inspect a layout that is fine. Traced to R1's parent norm rather than to R1: "advice
    fails soft" is not "advice fails silent" (`learnings.md`), which governs the reason a
    soft failure gives, not only its exit code.
  - **NOT in this chunk, and recorded so the omission is not read as a drop:** the
    table-blind TOML read (#580). The first draft fixed it here by making the parser
    table-aware; LNG-5W8R forbids exactly that, so it moves to Chunk 02 and is solved by
    declaration instead. R3's entry in the table above says so.
- **Tests:** R1 driven from a real non-repository directory (`tmp_path`), asserting
  `UNVERIFIABLE` and that the detail names the cause; a genuinely absent tag in a real repo
  still returns `FAILED`, so the fix does not soften a true finding.
- **Acceptance criteria:** `prawduct-hook check-released vX.Y.Z` from a non-repository
  directory reports `unverified`, not `not-released`, and a genuinely missing tag inside a
  real repository still reports `not-released`.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and the chunk recorded complete (tagged change-log entry + `regen-views`
     under `views_enabled` — not a hand-flipped checkbox)

### Chunk 02: The product declares which files carry its version — and where in them

- **Description:** Replace inference with declaration. `_VERSION_FILES` is prawduct's own
  layout applied to every governed product; a product that never claimed it is currently
  graded against it.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `.prawduct/project-state.yaml` schema — a `release_version_files:` declaration
    (path + format per entry). **Persisted format ⇒ lock-in** (`building.md` Decision
    Research), so the field shape is designed in this chunk against its future consumer
    queries, not improvised: the only consumer is `check_version_files`, and the only
    questions it asks are *which paths* and *how is each parsed*.
  - `plugin/lib/release_verification.py` — `check_version_files` reads the declaration from
    **the tag's own tree** (`git show <tag>:.prawduct/project-state.yaml`), through a
    minimal-YAML block reader in this module. **Corrected during the build, not silently
    deviated from** ("goals and verification bind; prescribed method is advice"): this line
    prescribed `advisory_store.load_project_state`, which parses only column-0 *scalars* from
    the **checkout** — so it could not have read a nested list at all, and reading the checkout
    would answer "which files carried this release's version" from whatever branch you happen to
    be standing on, the exact confusion this module was built to refuse. Owner-ruled at build
    time in favour of the tag's tree. The
    posture splits on provenance: a **declared** file that is present and unparseable is
    `FAILED` (the product said it carries the version), while under the **undeclared**
    fallback the built-in tuple is a *guess* and can only produce `OK` or `UNVERIFIABLE` —
    never `FAILED`. That split is the requirement; without it, declaration is cosmetic.
  - Doc surface for the new key wherever `project-state.yaml` fields are described.
- **Tests:** a declared layout that disagrees still fails; a declared file that is present
  and unparseable fails; an undeclared product whose `pyproject.toml` has no `[project]`
  version reports `unverifiable` rather than `failed` (#576's repro); **#580's exact repro
  — `[tool.myplugin] version="9.9.9"` above `[project] version="1.0.0"` — resolves to
  1.0.0 under a `key: project.version` declaration, and both orderings agree** (R3);
  prawduct's own repo keeps its current verdict either way.
- **Acceptance criteria:** a correctly-configured product using setuptools-scm, or a
  tooling-only `pyproject.toml`, no longer receives a `not-released` verdict; a product
  that declares its files still fails when they genuinely disagree.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then ONE `/prawduct:critic cumulative` — it is this chunk's review and the
     PR gate's evidence
  3. Chunk recorded complete (as Chunk 01 step 3)
