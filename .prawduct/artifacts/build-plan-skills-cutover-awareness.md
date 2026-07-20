---
artifact: build-plan
version: 1
scope: skills-cutover-awareness
depends_on:
  - artifact: backlog-service-requirements
  - artifact: backlog-service-data-model
governed_by:
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms (every surface here is advice — Critic NOTEs, PR NOTE/WARNING, janitor findings, a session advisory; each degrades to a stated notice, none blocks)"
      - "Local-first, stdlib-only; no network, no daemon → conforms (the new probe reads `.prawduct/` state only; no adapter call, no `gh`)"
      - "An independent reviewer never mutates the session it reviews → conforms (the Critic precondition is a `Read` of `project-state.yaml`; the reviewer writes nothing it did not already write, and deliberately reaches no adapter — CRT-3X9D — so the no-execution boundary is preserved rather than widened)"
      - "The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the `.gitignore`/`.claude/settings*.json` it must reconcile → conforms (the advisory's id and dismissal land in the existing `.prawduct/` advisory store; no new path outside it is written)"
  - artifact: data-model
    dispositions:
      - "Two stores, two lifetimes → conforms (the advisory's id and any sticky dismissal ride the EXISTING per-clone, gitignored advisory store — the nags-and-caches side of the split. Corrected from an initial 'inapplicable/adds no persisted store': the plan mints no NEW format, but it does write per-clone state, and 'no new store' is not the same claim as 'no store')"
      - "Derived views are disposable and never authoritative — no gate reads a view → conforms (no gate reads backlog state at all; `hooks/gates.json` declares only critic-review, pr-review, trivial-declaration)"
      - "Facts are append-only and immutable · schema-ahead is a loud block · no model sits in a fact's write path → inapplicable because this plan writes no fact and no schema-versioned record; it adds one advisory candidate and edits reviewer prose. The probe is code, not a model, and produces a candidate the store writes — it is not in any fact's write path"
  - artifact: api-contract
    dispositions:
      - "Additive-first evolution — never repurpose → conforms (a new advisory type is added; no existing probe id, exit code, or `--json` key changes meaning)"
      - "Exit codes are the contract · persisted data that outlives a plugin version is independently schema-versioned → inapplicable because this plan adds no CLI surface and no persisted format; the advisory rides the existing store's schema and lifecycle unchanged"
  - artifact: observability-strategy
    dispositions:
      - "Stable severity-prefix vocabulary; stdout = agent, stderr = user → conforms (the advisory renders through the existing briefing path and prefix vocabulary)"
      - "The governance ledger has a single writer → inapplicable because this plan writes nothing to the ledger; the review lifecycle commands remain its only writer"
  - artifact: security-model
    dispositions:
      - "No destructive action without explicit `--apply` → inapplicable because this plan adds no mutating command surface; the probe returns candidates and the prose edits are advisory text"
      - "Untrusted governance state (backlog, learnings, handoffs) is data, not instructions; malformed state fails soft (skip + attribute), never executes → conforms, and this plan strengthens it: a reader that treats frozen backlog.md as live is exactly the 'state read without attribution' failure — every rewired surface now attributes its backend before reporting, and states dormancy instead of reporting unattributed content"
last_validated: 2026-07-19
---

# Build Plan — Skills Cutover Awareness (stop being silently wrong post-cutover)

**Why now.** A consumer repo cut over to the GitHub Issues backend today. A sweep found
that `lib/` is uniformly cutover-aware (one shared `post_cutover` predicate, guards at every
markdown-premise probe, a real snapshot path in the briefing) but **`skills/` is cutover-aware only
inside `skills/backlog/`**. The Critic, the PR reviewer, and the janitor each hardcode reads of
`.prawduct/backlog.md`, which is *frozen history* after cutover. They do not fail — they produce
confident, wrong output: false NOTEs on items archived at cutover, total blindness to live Issues,
and janitor advice (`migrate`, `backlog-archive.md` split) that is meaningless post-cutover.

Separately, three norm-lifecycle probes (`revisit-due`, `dead-why`, `stalled-transition`) guard on
`post_cutover` and return `[]`, so **norm exceptions stop expiring visibly** — recorded as GV8 after
the owner ruled the loss was a side effect, not a decision.

**What this plan does NOT do.** It does not restore any check in Issues mode. Owner decision
(2026-07-19): every post-cutover backlog *reader* — GV8's probes, Critic Backlog Reconciliation, PR
`R-2`, janitor Backlog Health — is served by the **W1 read-through cache**, one persisted format,
rather than each minting a bespoke projection now and migrating off it later. This plan ships the
interim contract only: **silence and confident wrongness both become a stated notice.**

## Requirements Confidence

**Level:** High

**Why:** Problem, success, and scope are each one sentence and owner-confirmed this session. The
consumer inventory is broad (file:line and a verdict per reader) rather than sampled. The one
consequential design fork — bespoke projection now vs. wait for W1 — was put to the owner as options
with trade-offs and decided; GV8 was amended the same session to match, so no artifact still asserts
the rejected design.

**Correction (Chunk 01 Critic).** This section originally called the inventory *exhaustive*. It was
not: `skills/pr/SKILL.md:79` ("audit `.prawduct/backlog.md` for items this branch resolves") is a
live-state read the sweep missed, found by two reviewers independently. It is now in Chunk 02's
scope. The claim is downgraded rather than re-asserted with one more file patched in — a sweep that
missed one reader may have missed another, and Chunk 04's re-greppable check is what actually closes
that, not the adjective.

**Correction 2 (`verify-resolutions`) — the chunk-heading root cause was wrong.** Commit `922af15`
rewrote this plan's headings `## Chunk NN — ` → `### Chunk NN: ` and recorded that the em-dash form
"defeats the parsers." **It does not.** `lib/buildplan_refs.py:82` is the only production chunk-heading
matcher and accepts both depths and `[:—–(-]` — its own comment records that the em-dash case was
fixed precisely so it would not silently disable ref verification. What actually rejected the heading
was `tests/test_build_plan_resolution.py:264`, whose docstring claims to *"replicate the matcher the
production parsers use"* and then demands three-hash **plus a colon**. The replica has drifted from
what it mirrors. The headings stay in the stricter form (it satisfies both, and costs nothing), but
the belief is corrected here so no one later "fixes" `_CHUNK_ID_SEP` by narrowing it to match a stale
test. The drifted guard is filed separately.

**Open assumptions / unknowns:**
- [ASSUMPTION: one **consolidated** advisory naming all dormant checks, rather than one signal per
  dormant check | MED impact | owner can split it — seven separate nags per session is the failure
  mode this avoids, but it does trade per-check precision for one line]
- [ASSUMPTION: the advisory is `info` priority, not `warn` | LOW impact | it reports an accepted,
  time-boxed interim state with a known resolution (W1), which is the `info` shape; `warn` is for
  signal-loss risk the reader must act on]
- [ASSUMPTION: restricted reviewers can reach `.prawduct/project-state.yaml` with `Read` and need no
  new tool grant | LOW impact | verified against `agents/critic-reviewer.md` grants (`Read, Glob,
  Grep, Bash(git *), Write`); confirmed at Chunk 01 before the prose depends on it]

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Consolidated dormant-checks advisory + Critic surfaces (keystone) — built 2026-07-19,
      commit 590a8f4. `backlog-checks-dormant` probe (`info`, dismissible) fires post-cutover naming
      all seven dormant checks; the backend precondition landed in both `review-cycle.md` and
      `review-protocol.md`. Done-when 3 confirmed: `agents/critic-reviewer.md`'s `Read` grant reaches
      `.prawduct/project-state.yaml` — no new tool grant, the assumption held. Critic bundle pass
      0 blocking / 8 warning / 11 note → verify-resolutions 0/3/1; fixes in 922af15, abb4b20;
      change-log + regenerated views in 2b93295.
- [x] Chunk 02: PR reviewer R-1 / R-2 — built 2026-07-19, commit ef34dfc. Re-typed `doc-only` → `code`
      at build (`tests/test_pr_reviewer.py` pinned the old behavior). Critic chunk 0/1/2 →
      verify-resolutions 0/0/1.
- [x] Chunk 03: Janitor Backlog Health — built 2026-07-19, commit ad8d8d9. All seven checks emit one
      "unavailable" line rather than the section being omitted (an absent section reads as a clean
      bill of health); Step 1's overlap read repointed to `/prawduct:backlog list`. Critic chunk 0/1/2
      → verify-resolutions 0/1/1 → 0/0/3.
- [x] Chunk 04: Name-and-prose coherence sweep — built 2026-07-19, commit 2a0b1cf. The two deferred
      adjudications became `## Direction` norms with owners and enforcement rows, because in each case
      the defect was *no owner*, not a wrong rule. The no-internal-ids norm is born `Status:
      in-transition` tracking **OBS-7M4D** — four in-scope sites fixed here, seven residual outside
      the changeset, and the sweep heuristic recorded as non-exhaustive (id prefixes are open-ended).
      Cumulative pass (the plan's single cumulative and the `/prawduct:pr create` gate) 0 blocking /
      9 warning / 13 note, resolved over a six-round verify-resolutions chain ending 0/0/0 at 35b9a14;
      fixes in 4b20d99, 7429444, 762d703, f221981, 7e68cd7, 35b9a14.

**Not closed by the build:** VRF-008 remains `pending`. The behavioral proof for all four chunks is a
live dogfood in a cut-over repo (`backlog_service_repo` set) — this repo is pre-cutover, so there is
nothing local to run it against. `operator_verification_required: false`, so the PR gate does not
block; the feature merges with the verification outstanding, deliberately and on the record.

---

### Chunk 01: Consolidated dormant-checks advisory + Critic surfaces (keystone)

**Type:** code
**Critic mode:** final *(override: this chunk lands the architectural keystone — the "how a reader
declares itself dormant" contract that Chunks 02–04 all copy; coherence matters before they build on it)*

**Delivers.** One advisory that names every backlog check dormant on the Issues backend, plus the
first two consumers rewired to it.

1. **New probe** in `lib/backlog_probes.py`: fires only when `post_cutover(state)` is true; evidence
   names the dormant checks; `recommended_action` points at the W1 resolution; `info` priority;
   dismissible like any advisory. Registered in `register()` alongside the existing five.
2. **`skills/critic/review-cycle.md`** — Backlog Reconciliation and C-B1–C-B4 gain a backend
   precondition: read `backlog_service_repo` from `.prawduct/project-state.yaml`; when set, **skip
   the walk** and emit a single NOTE stating the check is unavailable on the Issues backend. The
   reviewer must not open `.prawduct/backlog.md` for live state in that mode.
3. **`skills/critic/review-protocol.md:133`** — the same rule at the file the reviewer subagents
   actually load. Both files carry it; neither points at the other for the rule itself.

**Structural note.** The precondition is deliberately a `Read` of project state, not an adapter
call: `agents/critic-reviewer.md` grants no `Bash(prawduct-hook backlog *)` by design (no-execution
structural, CRT-3X9D). `lib/` holds the data, the fork skill holds no logic that needs a shell.

**Done when:**
1. Probe fires post-cutover, stays silent pre-cutover, and is covered by tests in both states.
2. A repo-coupled test asserts the probe does **not** fire against this repo (pre-cutover) — the
   zero-fire bar is met by this repo genuinely being out of the target state, never by narrowing the
   trigger.
3. `Read` reachability of `.prawduct/project-state.yaml` from `agents/critic-reviewer.md` grants is
   confirmed before the prose depends on it.
4. Full suite green; `prawduct-hook test-evidence record`.
5. `/prawduct:critic` — resolve blocking findings.

### Chunk 02: PR reviewer R-1 / R-2

**Type:** code *(re-typed at build from `doc-only`: `tests/test_pr_reviewer.py` asserted "R-2 stays
unconditional", which GV8 makes false. The assertion still passed on a substring of the new prose —
a test that keeps passing while its stated contract inverts is worse than a failing one, so it was
rewritten to scope "always" to the markdown backend and to pin the new precondition.)*
**Critic mode:** chunk

`skills/pr/review-protocol.md:49-51`. **R-2 is the highest-risk reader in the inventory**: it is
marked *"always run — the Critic does not do this check,"* so it is the sole owner of the
change-log-says-`closes:`-but-item-is-open consistency check, and post-cutover it resolves
`PFX-XXXX` against frozen markdown — silently passing or dangling. **R-1** is written against
`## Open`/`## Promoted` *sections*, which `adapter-mode.md:110` states do not exist post-cutover.

Both gain the Chunk 01 precondition. R-2's dormancy is called out explicitly in its own text, because
a reader who knows R-1 is deferred to the Critic may reasonably assume R-2 is covered somewhere else.
It is not.

**Also in scope — `skills/pr/SKILL.md:79`** ("audit `.prawduct/backlog.md` for items this branch
resolves", in the prep-while-Critic-runs step). Missed by the original sweep and added here after the
Chunk 01 Critic; it is a third live-state read in the PR path, distinct from R-1 and R-2.

**Deviation, recorded (build):** this third reader is **repointed, not declared dormant.** R-1/R-2
are reviewer checks that parse backlog structure, so post-cutover they have nothing to parse; the
SKILL.md step is a *builder* action, and `/prawduct:backlog list` is already backend-routed
(`skills/backlog/adapter-mode.md:78` maps it onto `prawduct-hook backlog list`). Declaring dormancy
there would retire a step that still works. The dormancy contract applies to readers with no live
path — not to every surface that happens to name the file.

**Done when:** no PR-path reader treats `.prawduct/backlog.md` as live state — R-1/R-2 state dormancy
post-cutover, the SKILL.md prep step routes through the backend-routed skill; no prose still names
markdown sections as the resolution surface; `/prawduct:critic`.

### Chunk 03: Janitor Backlog Health

**Type:** doc-only
**Critic mode:** chunk

`skills/janitor/SKILL.md` — Step 1 Orient (`:174`), the Step 2.5 Backlog Health block (`:197-207`,
all seven checks), and the Step 7 (Close) reconcile target (`:278`). All seven checks are markdown-shaped
(group by `area:`, dedup by overlap, staleness via `reviewed`/`added`, unstaged `stage:`, `## Promoted`
neglect, legacy-item count, `## Archive` growth).

Two of them are not merely stale post-cutover but **actively wrong advice**: check 6 proposes
`/prawduct:backlog migrate` and check 7 proposes a `backlog-archive.md` split — both meaningless once
Issues is system of record. The block states dormancy as a whole rather than per-check; the fix path
(`/prawduct:backlog`) stays correct and is already backend-routed.

**Sharpened at build — the repoint-vs-dormant discriminator.** Chunk 02's rule ("dormancy is for
readers with **no live path**") under-determined this chunk: `/prawduct:backlog list` *can*
approximate two of the seven Health checks (area clusters, stale items), so "has a live path" alone
would have argued for restoring them — the bespoke per-reader projection the owner decision rejected.
The sharper test, found by treating Step 1 and Step 2.5 as the same question and getting different
answers: **repoint a reader that consumes the item view as-is; declare dormant a reader that derives
a verdict from it.** Step 1's overlap read consumes; the Health checks judge. Recorded here rather
than only in the janitor leaf, because Chunks 02–04 all turn on it.

**Done when:** the Backlog Health block states dormancy post-cutover; Step 1 (Orient) and Step 7
(Close) no longer name `backlog.md` as the live-state or reconcile surface; `/prawduct:critic`.

### Chunk 04: Name-and-prose coherence sweep

**Type:** cumulative-final
**Critic mode:** cumulative

The residue the inventory found — each one prose that *describes* markdown-only behavior
unconditionally. Per the standing learning, a behavior change is not done until every artifact
describing it is updated, and removing a mechanism requires removing its name too.

- `skills/backlog/SKILL.md:25` — the Archive-split (Q2) rule sits in the shared preamble *above* the
  routing block, so it reads as applying in both modes. *(The plan also asked to add archive-split to
  `adapter-mode.md`'s not-applicable list "which currently omits it" — **struck**, verified done at
  Chunk 03 review: `f8c5dce` added it on the prior plan and it reads at `adapter-mode.md:157`. The
  `skills/backlog/SKILL.md:25` half is still live.)*
- `skills/backlog/SKILL.md:63` — `find` "across all sections (and `backlog-archive.md`)" stated
  unconditionally in the same preamble.
- `lib/upstream_probes.py:54-60` — advisory text says "not yet triaged into `.prawduct/backlog.md`";
  prose-only (no parse), so it is misleading rather than broken. Make it backend-neutral.
- Verify no remaining surface outside `skills/backlog/` names `backlog.md` as *live* state.
- **Adjudicate: do internal ids belong in the dormancy NOTE?** (Chunk 02 Critic.) The NOTE that
  Chunks 01–03 all copy ends "(GV8; restored with the read-through cache)", while
  `tests/test_backlog_probes.py:288` asserts `GV8`/`W1` must **not** appear in the advisory's
  `recommended_action` — reasoning that prawduct's internal ids mean nothing in a downstream
  product's briefing. A reviewer finding may legitimately carry a trace pointer an advisory should
  not, but the two conventions currently contradict with nothing deciding between them. Rule one way,
  apply it to every copy of the NOTE, and pin the copies together so they cannot drift apart.
- **Adjudicate: may a reader open `.prawduct/backlog.md` directly pre-cutover?** (Chunk 03 Critic.)
  The repoint rule now has two divergent copies: `skills/pr/SKILL.md:79` says **never** read the file
  directly, `skills/janitor/SKILL.md:176` explicitly permits it on the markdown backend. Both are
  defensible — the janitor wants full bodies, the PR path wants a filtered view — but nothing owns
  the rule, so the next reader copies whichever it happens to open. Rule once, apply to both, and
  fold into the same pin as the bullet above: the two copies-drift risks are one job.

**Rulings, recorded (build).** Both adjudications became `## Direction` norms rather than a decision
buried in a leaf file — "nothing owns the rule" was the defect in each case, and only a norm with an
enforcement row has an owner.

1. **Internal ids → `observability-strategy.md`: emitted text names none.** Ruled for the test's
   reasoning (an operator downstream cannot resolve `GV8`), against the reviewer-finding side. The
   NOTE now ends "they return when the backlog read-through cache lands" — the id replaced by what it
   stood for, so dropping it costs no information. Born `Status: in-transition` tracking **OBS-7M4D**:
   the birth sweep found seven further emitted sites outside this changeset, and a norm that claims a
   clean inventory it does not have is worse than one that names its debt. The sweep heuristic
   (id-shaped tokens in string literals) is not exhaustive — prefixes are open-ended — so the durable
   enforcement is recorded as the Critic's judgment, not a regex.
2. **Direct reads → `data-model.md`: gated on `backlog_service_repo`, not banned.** A blanket ban was
   the tidier rule and was rejected: it would retire the janitor's full-body overlap read with no live
   replacement, which is the bespoke per-reader projection the owner decision already rejected. The
   risk being guarded is reading *frozen* history as live, and that risk exists only on one side of
   the gate — so the gate is the rule. `skills/pr/SKILL.md`'s absolute wording was the copy that
   diverged and is corrected; both readers now state the gate inline per Chunk 01's contract.

**Also fixed, unplanned — the drain condition didn't cover the janitor.** The Verification Strategy
below requires all three live runs, but VRF-008 drained on a Critic run plus `/prawduct:pr create`
only, and Chunk 03 never added a janitor step. That is the Chunk 02 finding recurring one chunk
later: *the artifact was verified, the loop that drains it was not.* VRF-008 gains steps 8-11 and a
three-way drain condition.

**Done when:** the sweep is complete and re-greppable; suite green; commit; then
`/prawduct:critic cumulative` **once** — this chunk's review is the plan's single cumulative pass and
the `/prawduct:pr create` gate.

---

## Verification Strategy

Tests cover the probe (fires/silent/zero-fire-against-this-repo). The prose changes have no unit
tests — skills are prose a model executes. The behavioral proof is a **live dogfood in the cut-over
sibling repo**: run `/prawduct:critic`, `/prawduct:pr create`, and `/prawduct:janitor` there and
confirm each states dormancy rather than reporting frozen-history findings. All three are needed —
a Critic run never dispatches the PR reviewer, so it leaves R-1/R-2 (Chunk 02) unexercised while
looking like coverage. This mirrors the VRF-007 lesson — a read-then-consume
handoff between prose and CLI survives clean multi-reviewer review and still fails live — so it is
enqueued as an operator-verification entry, not asserted from the diff.

## Governance Checkpoints

1. **After Chunk 01** — the dormancy contract is the keystone; confirm Chunks 02–04 can copy it
   verbatim before they do.
2. **At Chunk 04** — cumulative review over the full bundle, which is also the PR gate.
