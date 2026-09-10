---
artifact: build-plan
version: 2
scope: comment-content-norm
branch: feat/comment-content-norm
governed_by:
  - artifact: architecture
    dispositions:
      - "prawduct is written in Python and must never be specific to Python; no gate acquires a language-specific parser — suffix matching only → conforms, and this norm REDIRECTED the design. The judging mechanism is the Critic (model-read, no comment grammar for any language). No per-language comment lexer, prefix table or grammar enters the runtime. Recorded in full at 774-requirements.md § Governing norms."
      - "prawduct guides and reviews; it never implements; it never re-implements what a product's own tooling already does → conforms — no linter rule is authored, and a number, where one exists at all, comes from the product's own tooling."
      - "a language with no populated rules is reported as unchecked, never silently passed → conforms — Chunk 03's advisory says `unchecked` where no figure is available; it never renders zero."
      - "every fact has one home; every other mention is a reference → conforms — the norm statement has exactly one home (Chunk 01's methodology text); the preferences row is a POINTER row and the advisory cites rather than restates."
      - "goals and verification bind; prescribed method is advice → acknowledged — the call sites named in Deliverables are this plan's best guess; a builder who finds a better route takes it and records why."
      - "authority fails closed; advice fails soft → conforms — nothing here produces a verdict; the advisory informs and degrades to silence."
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state → conforms — Chunk 03 writes only an advisory-store nag and a committed answer scalar."
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk grants a reviewer a write."
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes: shared committed answers kept distinct from per-clone gitignored nags → conforms — Chunk 02's clearing answer is a committed project-state scalar; the nag state stays in the gitignored advisory store."
      - "derived views are disposable and never authoritative; no gate reads a view → conforms — no gate reads anything this plan writes."
      - "governance verdicts on the Critic data plane are computed from the append-only fact ledger, never from mutable model-written state → inapplicable because no chunk writes to the Critic data plane or introduces a verdict."
      - "facts are immutable and append-only; a state change is a new fact, never an edit in place → conforms — the only state this plan writes is one advisory answer scalar, set once; nothing edits a fact."
      - "a governance document reaches a terminal state; it is never deleted → conforms — this plan will be archived, not deleted. Note the one deletion this branch DOES make is not a governance document: the mis-pathed preferences file (bare .prawduct/, no artifacts/) was created and removed within this same chunk, never a live document any reader resolved."
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules → conforms, and was exercised — #774's supplied title ran 95 chars and the adapter refused it; it was rewritten to 53 rather than the rule being bypassed."
      - "a fact written by a newer schema than the reader is surfaced as a loud block → inapplicable because no chunk changes a fact schema."
      - "backlog_service_repo selects which backlog store is authoritative; .prawduct/backlog.md is frozen history once set → conforms — every backlog touch in this cycle went through /prawduct:backlog, which routed to the Issues backend; no chunk reads or writes the markdown file."
partition: serial — 02 and 03 both depend on 01's exact wording, and 04 verifies all three against the live repo
---

# Build Plan — A Norm for Comment Content

**Issue:** #774 · **Requirements:** `documentation/issues/774-requirements.md`

## Requirements Confidence

**High.** The owner confirmed the framework-floor / product-owned-layer split before any code, and
a pre-build re-read of `plugin/methodology/building.md` corrected the requirements' central claim: the floor **already
exists and already binds**. What is left is precisely scoped — one new norm on one axis, its home,
its reach, and its adoption path.

**The correction is recorded rather than absorbed** (`documentation/issues/774-requirements.md` § Problem, § Grounding
facts). It dissolved a whole chunk: the original Chunk 02 existed to make the floor citable in
review, and three protocol files already do that.

### Open assumptions

None outstanding. The one HIGH-impact assumption — the floor/layer split — was confirmed
2026-09-10. The `advisory` audit home recorded in the first draft was corrected to `janitor` on the
norms spec's own rule (an advisory home must name the mechanical hook its probe fires on; after the
locator redirect there is none).

## What I would do differently — the advisory position

Stated before the chunks because a plan handed over silently reads as endorsed.

**1. I nearly wrote a second copy of an existing rule, and the plan is shaped by having caught it.**
The first draft's Chunk 01 was "state the floor." The floor is stated at
`plugin/methodology/building.md:88` and enforced as a **deletion finding** in three review
protocols. Reading the build cycle before building — the one step CLAUDE.md calls the #1 governance
failure to skip — is what surfaced it. Chunk 01 now adds *reach*, not a rule, and R1a makes "no
second home" an acceptance criterion rather than a good intention.

**2. I would cut Chunk 02 (the advisory) if forced to cut anything.** It touches a declared risk
surface (`plugin/bin/*hook*`, three reviewers at any size) and, after the norm redirect, it cannot
cite a density figure in a repo without its own tooling — so it fires naming the rule and the
ratification path, which is real but thin. I keep it because it is the *only* mechanism that
reaches an already-onboarded repo, which is the requirement the owner actually raised. If this plan
runs long, cut it and file it; do not cut Chunk 03's dogfood.

**3. The risk is Chunk 01's wording, and the failure mode is now the opposite of what I first
thought.** The danger is not that the norm deletes too much — Axis B asks for *ordering*, and
deletes nothing. It is that a norm about ordering gets restated in review as a norm about volume,
which #772 forbids and which the oversized-file advisory independently warns against. Chunk 01's
wording must be un-paraphrasable into a percentage.

## Chunks

### Chunk 01 — The Axis B norm, its home, and the floor's reach

**Type:** `doc-only`

**Critic mode:** final — override: the keystone. Both later chunks cite this wording, so its
coherence must settle before they build on it. Declared on its own line with a bare value because
`plugin/lib/critic_mode.py`'s parser anchors at line start and rejects a backticked value — a
mid-line or backticked declaration is read as absent, silently.

**Surfaces this touches** (enumerated up front — a project-wide concept cascades):
- `.prawduct/artifacts/project-preferences.md` — **the canonical file, which already exists** (58
  norm-index rows). The norm is **added** to it: one Code Style bullet, one norm block, one
  Enforcement row (mechanism `Critic`, audit home `Critic + janitor`), `migrate: #772`. Every
  pre-existing row and owner ruling is preserved.
  **Readers, which is what makes this the right path** — `norm_index_scaffold.PREFERENCES_REL`,
  `norm_probes._preferences_lines` (the module owning the pattern Chunk 02 mirrors), `briefing.py`,
  `init_product.py`. A first pass shipped this to the bare .prawduct/ path (no artifacts/), which nothing
  reads; deleted, not relocated (Critic `rev-20260910T155357Z-2ed219ba`).
- ~~`plugin/methodology/session-digest.md`~~ — **DESCOPED 2026-09-10, measured, owner decision
  required.** See *Blocked deliverable* below. Not silently dropped, and not squeezed in.

**Deliverables**
- The Axis B statement: a comment **or doc-comment** leads with what a reader needs in order to use
  or change the thing it documents; rationale, alternatives and recorded rulings follow, clearly
  separated; a reader who needs only the interface must not read the rationale to find it.
  Phrased as *what a reader needs* rather than *what it does for its caller* because D3 puts plain
  `#` blocks in scope and a caller-shaped predicate excludes them — including `pyproject.toml`'s
  ruff stanza, which this norm must leave intact.
- Its Why: the first reader almost always needs to *use* the thing, and rationale placed after it
  loses nothing.
- ~~Axis A's reach sentence in the digest~~ — descoped; see below.

**Blocked deliverable — the injected budget is full, and this was measured, not estimated.**

The digest is emitted as SessionStart `additionalContext`. Two independent budgets govern it, in
two test modules with no reference between them, and only the second binds here:

| Control | Limit | Current | Headroom |
|---|---|---|---|
| Harness character wall (`ADDITIONAL_CONTEXT_INLINE_LIMIT`) | 10,000 chars | 9,128 | 872 |
| Working char budget (reserve held for the next framework default) | 9,500 chars | 9,128 | 372 |
| **Injected token ceiling, framework shape** | **3,212** | **3,211** | **1** |
| **Injected token ceiling, product shape** | **2,096** | **2,095** | **1** |

The sentence was written, measured at +24 tokens, tightened to +18 by merging the id-decay and
history clauses into one rule (justified by re-derivation — `plugin/methodology/building.md` states
them as one sentence with three clauses), and **still does not fit in one token of headroom**. It
was reverted; the digest is byte-identical to `develop`.

**Why it was not paid for by trimming.** The one clearly trimmable candidate — the handoff bullet's
cold-cache rationale — turned out to have been *deliberately relocated into* the digest to fund an
earlier `plugin/methodology/building.md` trim. Cutting it would undo a recorded decision and delete
a why that no other injected surface carries. That is a quality regression dressed as a trim, which
is the exact failure the digest's own reserve comment names.

**Two honest routes, both the owner's to pick.** (a) Raise the injected ceilings by ~25 tokens by
owner ruling — the ceilings are policy and there is precedent for raising them; the 10,000-char
harness wall is untouched and has 872 chars free. (b) Run a proper relief pass, relocating a
relocatable section out of the injected set with a stated retrieval path.

**My recommendation is (c): decline it.** Axis A is already enforced where it bites — three review
protocols class a history-narrating comment as a **deletion** finding, and that is what caught both
PR #773 violations. The digest addition would cost every session forever to move a rule from
read-before-building to always-injected, when the reviewer already catches it. The measurement
above is the argument; the decision is not mine.

**Done when**
1. **`plugin/methodology/building.md` line 88 is unchanged** and no text anywhere restates it —
   verified by diff.
2. The Axis B wording cannot be paraphrased into a line count or percentage. Read it back
   adversarially and rewrite if it can.
3. Read the wording against `plugin/lib/coverage_algebra.py`'s `is_judgeable_path` docstring and
   `pyproject.toml`'s ruff stanza: both must survive **at full length**, relocated below the
   interface at most. A wording that shortens either is wrong.
4. Every token and character budget is green with **no ceiling raised** — satisfied by the digest
   being byte-identical to `develop`.
5. The norm is in `.prawduct/artifacts/project-preferences.md`, its norm index is **+1 row and
   otherwise unchanged**, and no preferences file exists at any other path. `norm-index-scaffold`
   reporting `ok` does **not** discharge this — it graded the pre-existing file and passed
   vacuously while the deliverable sat at an unread path.
6. `/prawduct:critic` passes with no blocking findings.
7. Tick this chunk's Status box.

### Chunk 02 — The one-shot ratification invitation

**Type:** `code`

**Critic mode:** chunk

The only mechanism that reaches an already-onboarded repo. Fires once, never recurs.

**Deliverables**
- One probe on the `norm-registry-unratified` pattern (`plugin/lib/norm_probes.py`), registered at
  the runtime composition root (`plugin/bin/prawduct-hook`), not at import time.
- Fires once per repo; clears on a **committed** answer so a teammate's ratification clears it for
  everyone on next sync; dismissal is a recorded decision.
- Names the rule and the ratification path. Where no density figure exists — every repo without its
  own comment tooling — it says so rather than rendering zero.

**Done when**
1. **No per-language comment grammar, prefix table or lexer appears in the diff.** The measurement
   script that produced this work's evidence stays in the scratchpad. This is the norm redirect's
   enforcement point, checked by inspection of the diff.
2. The probe fires once, clears on the committed answer, and does not recur — tested, not asserted.
3. Registration is at the composition root, keeping `advisory_store` feature-agnostic.
4. `/prawduct:critic` passes with no blocking findings.
5. Tick this chunk's Status box.

### Chunk 03 — Dogfood: prawduct adopts its own norm

**Type:** `cumulative-final`

Critic mode is left to inference, which derives `cumulative` from the Type. No override is
declared — and the field is deliberately not written here even as a comment, since any bolded
`Critic mode:` line carrying a non-mode word would parse as an unrecognized mode.

The adoption path is unproven until this repo has walked it, and the norm is unproven until it has
been applied to something.

**Deliverables**
- Prawduct ratifies Axis B against itself through the `/prawduct:doctor` Norm Ratification Flow,
  recording `norm_registry_ratified` in `.prawduct/project-state.yaml`.
- **One worked example**: `plugin/lib/critic_marker.py`'s module docstring reordered interface-first.
  Its rationale is load-bearing and is **kept in full** — only its position changes. One file, as
  proof the norm is applicable; remediation remains #772's and is not started here.
- #772 updated to carry the Migrate relationship, so the retroactivity line names a live item.
- Change-log entry under `scope=comment-content-norm`, deliberately **untagged by `release=`** —
  that absence is the release-pending state.

**Done when**
1. The flow ran against this repo and the outcome is recorded, **including anywhere the flow could
   not do what this plan assumed** — that finding is the dogfood's real product.
2. `plugin/lib/critic_marker.py` reads interface-first and its docstring is no shorter than it was. Verify the
   line count did not drop; a reduction means rationale was cut, which this chunk forbids.
3. #772 carries the relationship and the norm names it.
4. Commit the chunk, then run `/prawduct:critic cumulative` once.
5. Tick this chunk's Status box — the last tick disarms the Stop gates.

## Governance checkpoints

1. **After Chunk 01** — the wording review. Both later chunks cite this text, and the specific
   failure to check for is a norm about ordering that reads as a norm about volume.
2. **After Chunk 03** — the trajectory review: did the adoption path work on a real repo, and did
   the floor/product-layer split hold under contact or collapse into one of the pure answers?

## Status

- [ ] Chunk 01 — The Axis B norm, its home, and the floor's reach
- [ ] Chunk 02 — The one-shot ratification invitation
- [ ] Chunk 03 — Dogfood: prawduct adopts its own norm
