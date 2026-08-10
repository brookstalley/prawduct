---
artifact: build-plan
version: 1
scope: chunk-refs-gate
depends_on:
  - artifact: buildplan-chunk-refs-discovery
governed_by:
  - artifact: api-contract
    dispositions:
      - "Exit codes are the contract; message severity is a stable prefix vocabulary → conforms. Chunk 02 adds `warn-ref:` as a new severity prefix at exit 0; it does not repurpose an existing prefix or exit-code meaning. The blocking contract a caller binds to is unchanged: exit 1 still means 'a deliverable named by the chunk under review is missing', exit 0 still means 'nothing blocking'. What exit 0 gains is an additive advisory line on stderr, which a caller that ignores stderr never sees."
      - "Additive-first evolution: existing flag names, exit-code meanings and `--json` keys are never repurposed → conforms. No flag is renamed and no exit code changes meaning. Chunk 02 widens *what is inspected* from one chunk to all, which is a coverage change rather than a contract change, and the severity split is what keeps it so — refs outside the chunk under review can only ever produce advisory output."
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms, and this norm is the reason the owner's ruling is right rather than merely convenient. The gate produces a governance verdict for the chunk under review (authority → blocks on a missing deliverable) and merely informs about every other chunk (advice → a note). Option (i) from the discovery doc — block on every chunk — would have converted advice into authority for chunks nobody is working on, which is the failure this norm names. Recorded because the applicability is an interpretation, not a given."
      - "Authority fails closed — SECOND application, and it caught a violation in this plan's own Chunk 01 during the build. The originally-planned 'skip a ref that resolves nowhere, has no extension, and whose first segment is absent' rule made the gate go SILENT on ambiguous input, which is precisely the inverse of the norm, and it would have weakened reporting in every consuming product to absorb three tokens in this repo's own plan. Withdrawn and replaced with report-and-let-the-author-disambiguate; the withdrawal and its reasoning are preserved in the Chunk 01 body. The lesson worth carrying: a disposition asserting conformance is worth nothing if it is written before the code and never re-read against it."
      - "Local-first: governance coordination is process-spawn + files + git, no network, no third-party dependencies → conforms. Every change here is stdlib path arithmetic against the working tree; no new dependency, no network, no new persisted format."
      - "The plugin writes nothing into a governed repo except its own `.prawduct/` state … → inapplicable because this plan adds no write path. `verify-chunk-refs` is read-only and stays so."
  - artifact: observability-strategy
    dispositions:
      - "Severity prefixes are a stable vocabulary (`CRITICAL:`/`WARNING:`/`NOTE:`/…); stdout is agent-facing, stderr user-and-diagnostics → conforms with a recorded departure on spelling. This command already speaks a LOCAL prefix vocabulary — `ok:`, `missing-ref:`, `cannot-verify:` — none of which uses the global spellings. `warn-ref:` is chosen for consistency with the command's own three existing prefixes rather than the global set, because a caller greps this command's output, not the framework's. [DECISION: use the command-local prefix spelling `warn-ref:` rather than `WARNING:` | the norm's why is a *stable* vocabulary a caller can bind to; consistency within the surface a caller actually parses serves that better than consistency with prefixes this command has never emitted | user can override]. Advisory output goes to stderr with the other diagnostics."
      - "Text emitted into a governed product names no prawduct-internal identifier → conforms. Warn lines name the product's own chunk ids and file paths, which are the reader's own build plan, never a prawduct backlog or incident id."
  - artifact: nonfunctional-requirements
    dispositions:
      - "Run-count is the lever for review wall-clock → conforms, with the cost engineered out rather than accepted. Widening from one chunk to all multiplies section parsing by the chunk count, and `_parse_build_plan_chunk_refs` re-reads the plan file on every call — so the naive shape would be N file reads per gate run. Chunk 02 reads the plan once and walks the parsed content, keeping the gate at one read regardless of chunk count."
      - "State-file growth is an advisory warning that prompts compaction — never a hard block → cited as precedent, not as a governing constraint on this plan: it is the same advisory-not-blocking shape the warn tier adopts."
last_validated: 2026-07-29
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — `verify-chunk-refs`: see the right chunk, and only real deliverables

Covers **BLD-ZQ2V** and **BLD-5R7K**. Requirements, measurements and the owner
ruling are in `.prawduct/artifacts/buildplan-chunk-refs-discovery.md`; this plan
does not restate them.

**Not part of v3.2.0.** `active_build_plan` stays pointed at
`build-plan-v3.2.0-golive.md` per the gitflow plan-lifecycle rule. This work
lands on the same branch for convenience (that branch already carries adjacent
governance fixes, e.g. `67fe565`), but it is **not** in the release scope the
2026-07-28 narrowing set, and Chunk 09's change-log flip must not sweep it up.
If the owner wants v3.2.0 to ship with a working ref gate, that is a scope
decision to take explicitly — see § Open assumptions.

## Requirements Confidence

**Level:** High.

- **Problem:** `verify-chunk-refs` verifies one file reference for an entire
  release and reports green (measured: Chunk 01 has 1 ref; 49 others uninspected).
- **Success:** the gate inspects every chunk, blocks on the one under review,
  warns on the rest, and reports zero false positives on the real plan.
- **Out of scope:** listed in the discovery doc § 5, unchanged.

**Open assumptions:**

- `[ASSUMPTION: full-plan verification is acceptable on other products' build plans | MED impact | user can veto]`
  — carried forward from discovery § 6. The warn/block split is the mitigation:
  a product with stale refs in closed chunks gets warnings, not a wall.
- `[ASSUMPTION: this plan is NOT added to v3.2.0's release scope | MED impact | user can override]`
  — the release narrowing deferred governance-machinery work, and this is
  governance machinery even though most of it is deletion. Shipping it in
  v3.2.0 would need an explicit scope call, not a silent inclusion.

## Status

- [x] Chunk 01: stop the two false-positive classes — the gate's blast radius, before it can fire
- [ ] Chunk 02: verify every chunk; block on the one under review, warn on the rest
- [ ] Chunk 03: BLD-5R7K — announce the degraded reading, document the precondition

**Ordering is load-bearing, not stylistic.** Chunk 01 must land before Chunk 02.
Chunk 02 alone would convert a silent gate into one blocking 21 refs across
seven chunks (discovery § 3). Chunk 01 alone is a safe no-op improvement — it
can only ever turn a *would-be* false positive into a pass, and today the gate
inspects a chunk that has none.

---

### Chunk 01: stop the two false-positive classes

**Goal:** Make `_verify_chunk_refs` stop reporting two classes of non-defect —
plugin-relative shorthand, and tokens that name no file anywhere — so that
widening coverage in Chunk 02 is safe.

**Covers:** BLD-ZQ2V parts (a) and (b).
**Depends on:** —  ·  **Type:** code  ·  **Critic mode:** chunk

**Design decision — a change to `_looks_like_file_path` is a change to two
gates.** `plugin/lib/risk.py:55` imports it and applies it at `:117` to
`boundary-patterns.md` tokens, so editing it changes which contract surfaces
risk assessment sees — a different module, a different job, no test linking
them. Found by grepping the predicate's *callers*, which is this branch's own
Chunk 05c lesson applied before the fact rather than after.

That does not make the predicate untouchable; it makes the test for touching it
sharper. **A rule belongs there when it is true of the token's shape for every
consumer, and nowhere else otherwise.** The `#` rule qualifies — an issue
reference or anchor is not a file path in *any* caller's world — so it lands
there and is pinned at both consumers. Repo-slug discrimination does not: it
needs to know what resolves in a particular repo, which is context, not shape.
The first instinct was to encode that context as a shape heuristic anyway; the
withdrawal note above is what came of testing it against the governing norm.

**Done when:**

**REVISED DURING BUILD (2026-07-29) — the original done-when 2 was withdrawn as
unsafe. It is preserved below with the reason, because the reason generalizes.**

> The withdrawn rule: *skip a ref when it resolves nowhere, has no file
> extension, and its first segment is not an entry in the repo* — the
> conjunction meant to separate `brookstalley/prawduct` from `plugin/lib`.
>
> **Why it was wrong: it makes authority fail open.** The governing norm
> (`architecture.md` § Direction) is *authority fails closed; advice fails
> soft* — a gate blocks on incomplete, malformed, or **ambiguous** state. That
> rule did the reverse: faced with a token it could not classify, it stayed
> silent. And the silence was not confined to this repo — every consuming
> product would lose reporting on stale extension-less directory refs
> (`oldmodule/handlers` after the module is deleted), a real class, to buy a
> cosmetic win on three tokens in prawduct's own plan. A recorded disposition
> claiming conformance while the code does the opposite is worse than no
> disposition.

1. **A second ref root, DECLARED by the repo.** A ref that does not resolve at
   the repo root but does resolve under a root the repo declares
   (`build_plan_ref_root:` in `project-state.yaml`) is not missing. Scope by
   the pattern, not the 17 sites.

   **Revised twice, and the second revision is the one that matters.** The
   plan's original form resolved against `project_dir / "plugin"`
   unconditionally; that was caught in build and narrowed to require a
   `plugin/.claude-plugin/plugin.json` marker. **The marker was still wrong** —
   raised by the owner, checking `../hallucinote`. A governed product that *is*
   a Claude Code plugin carries exactly that manifest, so the guard admits
   precisely the repos it was written to exclude. (hallucinote survives only
   because it puts `.claude-plugin` at its repo root rather than under
   `plugin/` — a layout accident, not the design working. A fleet survey found
   no live victim today, which is a fact about one machine, not a property.)

   The defect underneath both cuts is the same one this chunk already withdrew
   a rule for: **the gate inferring its own permission from filesystem shape.**
   A repo that ships a plugin, an extension, or a vendored tree has an ordinary
   layout, not a statement of intent. So the repo declares, the verifier never
   sniffs, and an absent key — every consuming product today — means the repo
   root is the only root. Fail-closed by default, and the affordance is
   available on purpose to any repo that wants it rather than taken silently by
   this one. A declared root that escapes the repo, is absent, or is not a
   directory is ignored, not honoured.
2. **Issue references and anchors are not file paths.** A token containing `#`
   (`owner/repo#12`, `docs/api#usage`) names a location in a tracker or
   document; no source file this verifier is asked about carries one. This is a
   genuine property of the token's *shape*, so it belongs in
   `_looks_like_file_path` and is correct for its other consumer — a contract
   surface with a `#` is not a path either.
3. **Everything else path-shaped stays checked, including bare `owner/repo`
   slugs.** The gate reports what it cannot resolve; the *author* disambiguates
   in the plan. Both escape hatches already exist: `<owner>/<repo>` for
   placeholders (angle-bracket carveout) and a URL or unbackticked prose for a
   real repository. Loud and occasionally inconvenient beats silent and
   weakening, for a gate.
4. The three offending prose sites in `build-plan-v3.2.0-golive.md` are
   corrected at source — they were backticking repo slugs as if they were
   paths, which is the actual defect.
5. Tests pin each edge, **including the absence of the withdrawn heuristic** so
   a later "simplification" cannot reintroduce it: plugin-relative file and
   directory refs resolve; an **unmarked** `plugin/` dir does *not* resolve
   (the consuming-product guard); root wins over plugin; absent-from-both still
   reports; `#` tokens excluded; a bare repo slug is still path-shaped and
   still reported; an extension-less ref under an absent directory is still
   reported.
6. `risk.py` shares `_looks_like_file_path`, so its behavior change is pinned
   at that consumer too (`tests/test_classify_diff_risk.py`) — a change to a
   gate's input set is a contract change, not a local edit.

**Verification:** the discovery doc's probe, re-run — 21 missing → **0**, with
chunk-scoping still in place and **no fail-open rule anywhere in the path**. The
three that the mechanical fixes deliberately do *not* absorb were fixed as
prose. Suite 2781 passed / 7 skipped (was 2768; +13).

---

### Chunk 02: verify every chunk; block on the one under review, warn on the rest

**Goal:** Remove the chunk-scoping that let the gate inspect a chunk nobody was
working on, and introduce the severity split the owner ruled on.

**Covers:** BLD-ZQ2V part (1), per the 2026-07-29 ruling (discovery § 6).
**Depends on:** Chunk 01  ·  **Type:** code  ·  **Critic mode:** chunk

**Done when:**

1. `cmd_verify_chunk_refs` with no explicit chunk verifies **every** chunk in
   the plan, not just the resolved current one.
2. Missing refs in the chunk under review print `missing-ref:` and exit **1** —
   unchanged behavior, unchanged prefix.
3. Missing refs in any other chunk print a new `warn-ref:` line on stderr and do
   **not** affect the exit code. New prefix, additive; extends the existing
   `missing-ref:` / `cannot-verify:` vocabulary rather than inventing a
   mechanism. **The line names its consequence, not just the path** — advice
   fails soft, which is not the same as failing silent (learnings.md); a reader
   must be able to tell that this ref will block once that chunk comes under
   review, or the warning manufactures the false success it exists to prevent.
3b. **The plan is read once.** `_parse_build_plan_chunk_refs` re-reads the plan
   file per call, so verifying N chunks the naive way is N reads per gate run.
   Walk the already-read content instead. Any new build-plan read introduced
   here decodes UTF-8 and guards the same except-set as the existing readers —
   the project-preferences convention pinned by
   `tests/preferences/test_build_plan_decoding.py`, which is file-scoped over
   the owning modules and has "lost every one" of five review rounds as an
   unpinned convention. Prefer adding no new read at all.
4. An explicit `chunk_id` argument (or `PRAWDUCT_VERIFY_CHUNK_ID`) keeps today's
   single-chunk behavior — the existing seam stays the way to grade one chunk,
   and is what the tests drive.
5. The `ok:` summary reports what was actually verified (chunk count and ref
   count), so a green run is legible rather than merely silent.
6. Tests pin: a missing ref in the current chunk blocks; the same ref in another
   chunk warns at exit 0; explicit-chunk mode is unchanged; the `new`-qualifier
   forward-ref exemption still suppresses in both severities.

**Verification:** run against `build-plan-v3.2.0-golive.md` — expect exit 0,
zero `missing-ref:`, zero `warn-ref:` (Chunk 01 having removed all 21). Then
break one path in the current chunk and one in another chunk, and confirm the
severities land on the right side.

---

### Chunk 03: BLD-5R7K — announce the degraded reading, document the precondition

**Goal:** Stop `resolve_chunk_progress` degrading silently, and write down the
commit convention it depends on.

**Covers:** BLD-5R7K.
**Depends on:** Chunk 02  ·  **Type:** code + doc  ·  **Critic mode:** chunk
**Splittable:** 03a (runtime announcement) / 03b (documentation).

**03a — announce.** `verify-chunk-refs` is the deliberately-invoked surface
BLD-5R7K names as the likely home; Chunk 02 has just made it the surface that
reports on the whole plan, which makes it the right one. When
`ChunkProgress.git_derived` is `False` on a repo where the git reading was
expected, emit one advisory line naming the degradation. Non-blocking — this is
advice, not authority.

**03b — document.** The precondition (a `Chunk NN` commit subject **and** a
conventional-commit scope matching the plan's `scope:` frontmatter) is stated in
`plugin/templates/build-plan.md`, where a plan author meets it.

**Measured constraint, correcting the item.** BLD-5R7K says `building.md` "is at
4596 of a hard 4600." Both numbers have moved: the ceiling is now **4660**
(`tests/test_v5_methodology.py:146`) and the file measures **4651** by that
test's own estimator — **9 tokens of headroom**. So an addition there requires a
trim first, and 03b is correspondingly more expensive than "ready to write."
Prefer the template (1712 tokens, no ceiling test) and add to `building.md` only
if a reader genuinely needs it at commit time; if a trim is needed, that is an
editorial judgment call on governance-protected prose and belongs in its own
review, not bundled with a code chunk.

**Done when:** 03a emits the advisory and is pinned by a test; 03b states the
precondition in the build-plan template; any `building.md` change is either a
net-neutral trim-and-add or explicitly deferred back to BLD-5R7K with the
headroom measurement recorded.

## Explicit residual — this plan fixes ONE of three consumers, deliberately

`resolve_chunk_progress` answers "which chunk is current" for three consumers:
`verify-chunk-refs`, `critic_mode.infer_mode`, and the session handoff/briefing
(`prawduct-hook:1499` is a second `_current_chunk_id_from_status` call site, the
stop gate, distinct from the gate at `:2618`).

**Chunk 02 does not fix the wrong-question defect. It removes the question for
one consumer.** By verifying every chunk, `verify-chunk-refs` stops needing a
correct "current" for *scope*; it still uses it for *severity*, where a wrong
answer is cheap. The other two consumers keep asking "first incomplete" and
keep receiving Chunk 01 for this entire release — `infer_mode` will infer the
mode from a chunk shipped in a prior release, and the handoff will describe it
as the work in progress.

**The stop gate's use is worse than the other two, and was found while building
Chunk 01.** `prawduct-hook:1499` does not verify refs — it reads the resolved
chunk's declared **`Type:`**, which selects the `trivial` file-set bounds and the
`designer-handoff` review bypass. So for this entire release the stop hook has
been reading *Chunk 01's* Type to govern whatever chunk was actually built. Had
Chunk 01 declared `designer-handoff` — the one Type that bypasses Critic
enforcement entirely — every chunk of v3.2.0 would have shipped with the review
gate silently disabled.

It did not, because Chunk 01 declares `operator verification (no code change in
this chunk)`, which is not a recognized value, so the parser falls back to
`code` and the gate stayed armed. **The release was protected by a fail-safe
default and an unrecognized string, not by the mechanism working.** That is a
governance hole, and it upgrades this residual from "cheap severity mislabel" to
"a bypass Type on the wrong chunk disables review for a whole release."

This is recorded rather than fixed because fixing it is direction (1) — the
working-diff resolver the ruling made optional — and because scoping it in here
would exceed what was asked. It is **not** a silent drop (Principle 2). But it
is the strongest argument yet that the next fix must be structural: the severity
of a wrong answer is not uniform across the three consumers, and the worst of
them is not the one this plan touches.

**It is also the exact shape learnings.md warns about:** *"A fix lands at the
instance a review named; the defect lives in the class."* The cited instance is
literally this mechanism — CRT-7B4M shipped git-derived current-chunk for
`infer-critic-mode` alone, the identical defect then resurfaced at
`verify-chunk-refs` (BLD-7K3Q) and at the session handoff (SCN-4H9T): three
consumers, one root cause, fixed three times. The rule's conclusion is *sweep by
construction, not by enumeration — and when a class returns a third time, stop
sweeping and make it enforceable.*

By that rule the correct end state is **not** three more patches but one owner:
either `resolve_chunk_progress` answers "in progress" (not "first incomplete")
for everyone, or the two questions become separately named functions so a
consumer cannot get the wrong one by accident. **Filed as a follow-up on
BLD-ZQ2V rather than built here** — with the note that this is the class's
*fourth* appearance, which by the rule means the next fix should be structural,
not another consumer-local patch.

## Governance checkpoints

One, after Chunk 01 — it is the chunk that decides whether Chunk 02 is safe, and
its "no false positives remain" claim is the precondition for everything after.
The falsifying command is the discovery doc's probe; a non-zero residual stops
the plan.
