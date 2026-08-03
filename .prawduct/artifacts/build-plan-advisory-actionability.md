---
artifact: build-plan
version: 2
scope: advisory-actionability
depends_on: []
governed_by:
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with a stdout/stderr channel split → conforms. The advisory block stays on stdout (the agent-facing channel) and introduces no new prefix; the `owner →` / `agent →` / `after →` labels are field labels inside an existing block, not severity tokens. The owner still learns by relay, which is the mechanism this artifact already assigns the job to"
      - "text emitted into a governed product names no prawduct-internal identifier → **binds every line of copy this plan writes.** Eighteen new `owner_action` strings land in downstream products' session briefings and get relayed verbatim into conversation. No check label, requirement id, or backlog id in any of them; the trace goes in the adjacent comment. This is the norm's stated weakness — enforcement is the reviewer's judgment, not a regex — so it is named here as a standing review instruction for every chunk, not just the copy chunk"
      - "the governance ledger has a single writer → inapplicable because no chunk writes a ledger event"
      - "relay covers every active advisory, verbosity scaled by priority → **conforms, and this plan is that amendment's implementation.** The amendment was recorded in the artifact (2026-08-03, owner decision) BEFORE this plan was written, not alongside the code that benefits from it — the ordering matters, because amending a governing artifact to match code already in the tree is the laundering tell this repo's Authority Rule names"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → **the organising constraint for Chunk 01.** Advisories are advice by construction (this spec's §2.1: they surface, they never gate), so every new failure mode degrades rather than blocks: an edge naming an unknown type is ignored, a cycle falls back to priority order, an absent `owner_action` renders a generic approval line. What fails soft must not fail *silent* (`learnings.md`) — the fallback line is visible copy, not an omitted line, so a probe that forgot the field reads as 'approval only' rather than vanishing"
      - "every fact has one home; every other mention is a reference to it → **binds Chunk 02.** The owner-facing consequence of an action (bulk write size, irreversibility, that a committed file gets edited) is a fact. Its home is the probe that computes it, not a copy in the skill prose, the spec, or the relay directive. The relay passes fields through; it does not restate what any given advisory costs"
      - "goals and verification bind; prescribed method is advice → conforms. The Deliverables lines below are pre-code guesses; the Acceptance criteria and these dispositions bind"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state … → conforms. The only write is `.prawduct/.advisories.json`, which is already this subsystem's own per-clone store"
      - "prawduct is written in Python and must never be specific to Python → conforms. Nothing here dispatches on the governed product's language; the advisory block renders identically in a Swift or Go product"
      - "prawduct guides and reviews; it never implements → conforms. Every chunk edits the framework's own runtime and instruction prose"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches the review-active mutation guard"
      - "local-first governance, no network, no third-party dependency in the runtime → inapplicable because no chunk adds a network call or a dependency"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways; a control added from 2026-07-29 names its expected yield and emits that yield observably → **binds Chunk 02, which adds one control** (the authoring lint in new `tests/test_advisory_actionability.py`). Its yield is directly countable without new machinery, because the control is a test and its yield is the set of construction sites it reddens. **Pre-build census: 18 `AdvisoryCandidate(` construction sites across 8 probe modules, of which 18 lack `owner_action` today** — that is the denominator. Expected yield after Chunk 02 is zero standing failures and one red suite per future probe authored without the field, which is the regression class it exists for. No new emission channel is built for a single test; the test IS the emission"
      - "SessionStart must be fast; no probe or gate on the hot path may block or noticeably delay session start → **binds Chunk 01.** The ordering pass is an in-memory stable sort over an active set capped at a handful of entries. No new subprocess, no new file read, no tree walk. Verified by inspection, not by benchmark — a micro-benchmark on a list of five would be ceremony"
      - "state-file growth is governed by mechanical thresholds → conforms with a named cost: two string fields per active advisory grow `.advisories.json` and the briefing block. Non-active entries keep the compact form (§3.4), which is where unbounded growth would actually come from, and the block-level dismissal hint (§5.1) pays back part of the briefing cost by removing one repeated line per advisory"
      - "review wall-clock is P0; cost = unit-cost × run-count → conforms. Three chunks, one review each, matched to three distinct surfaces: mechanism, copy, and the read-side surfaces. No prose is added to either budgeted reviewer payload file"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; existing flag names, exit-code meanings and `--json` keys are never repurposed → **the one norm this plan comes closest to departing from, and the reason it does not is worth stating.** `owner_action` and `prerequisite_of` are purely additive. `recommended_action` keeps its name while its *documented meaning narrows* from 'single primary action (a slash command or short instruction)' to 'the command the runtime executes'. That is a narrowing of the spec's language to match what every conforming value already was — not a repurposing, because no consumer's reading of an existing value changes. It does make four current values non-conforming (three prose instructions in `lib/norm_probes.py`, one explicit non-action in `lib/backlog_probes.py`), and **Chunk 02 discharges exactly those four** rather than leaving the narrowed contract aspirational. A rename was considered and rejected: `.advisories.json` is a live per-clone store across the fleet and a rename orphans every stored entry"
      - "exit codes are the contract; message severity is a stable prefix vocabulary; errors are attributed → conforms. No exit code or prefix changes; `prawduct-hook advisory list/show` gains fields in its output, not new statuses"
      - "whole-surface semantic versioning → conforms (additive minor change to an existing surface)"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → **binds Chunk 01's relay directive, and is the one genuinely new exposure here.** The directive tells the runtime to relay advisory text into conversation, and some probes interpolate product-derived values into that text (a discovered `TODO.md` path, a backlog item label, a branch name). Those values are data being reported, never instructions to follow, and the relay directive must say so — a file named to read like an instruction must not become one by passing through an advisory. Framework-authored field text is trusted; interpolated product values are quoted material"
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level → **conforms, and strengthens an existing guarantee.** The backlog-migration advisory routes to an irreversible bulk write of real GitHub issues. Today its briefing line names neither the irreversibility nor the volume, so approval, where it happens, is uninformed. Chunk 02's `owner_action` for that probe states the cost in the sentence the owner actually reads"
      - "a governed product's content never leaves its own repository and owner → conforms. Nothing here adds an outbound path; the relay moves text from stdout into the same session's conversation"
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes → conforms. Both new fields live in `.prawduct/.advisories.json` (gitignored, per-clone — the nag log). Neither is a resolution-condition fact, so neither belongs in the committed answer store; probes' resolution conditions are untouched"
      - "derived views are disposable and never authoritative; no gate reads a view to reach a verdict → conforms. The advisory block is a rendering, and no gate reads it. Advisories remain non-blocking (spec §9)"
      - "facts are immutable and append-only → inapplicable because no chunk writes a fact"
      - "a fact written by a newer schema is a loud block → inapplicable because no chunk changes the fact schema"
      - "governance verdicts computed from the append-only fact ledger → inapplicable because no chunk computes a governance verdict"
      - "`backlog_service_repo` selects the authoritative store → inapplicable because no chunk reads or writes the backlog store; the backlog probes' trigger and resolution conditions are unchanged"
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The problem was stated with two real reproductions (a hallucinote briefing and a discodon briefing), and both defects it names are confirmed in the source rather than inferred: `briefing.py` renders one untyped action field behind a hardcoded `→ Run` prefix, and `report-bug` triage is `info` while the backlog-migration nudge it must precede is `warn`, so the priority sort prints them in the wrong order in every product carrying both. Success is verifiable by rendering: the block states an owner action and an agent action for each advisory, in an order whose prerequisites come first. Scope is bounded to the advisory subsystem's write and render paths plus the probe roster's copy.

**Open assumptions / unknowns:**
- `[ASSUMPTION: relayed info advisories are one compact line each, not a collapsed group line ("3 info advisories: …") | LOW impact | user can override at Chunk 01]` — chosen because a group line reintroduces the defect being fixed (a count with no action) one level up.
- `[ASSUMPTION: the prerequisite edge is declared on the earlier advisory (`prerequisite_of`) rather than the later one (`blocked_by`) | LOW impact | user can override]` — confirmed with the owner via the option preview; recorded because the inverse is defensible and the choice is not derivable from the code.

**What would raise confidence:** N/A.

## Status

<!-- Derived view (`views_enabled: true`). Mark a chunk shipped by adding a change-log entry
     tagged scope=advisory-actionability / status=shipped, then run regen-views.
     Do NOT hand-flip the checkboxes. Stays [ ] on this branch until the release ships —
     a built chunk is recorded in Context below, not by its checkbox. -->

- [ ] Chunk 01: Two-audience schema, prerequisite ordering, and the rewritten relay — proven end to end on one probe
- [ ] Chunk 02: Owner actions across the whole probe roster, with the authoring lint that keeps them
- [ ] Chunk 03: The read-side surfaces — advisory CLI output and the skill
Context: Plan authored 2026-08-03 against `documentation/post-sync-advisory-spec.md` v0.3, which was amended first (schema §3.6, rendering §5, ordering §5.3, relay §5.4, authoring rules §7.2). The relay-scope change is a recorded amendment in `.prawduct/artifacts/observability-strategy.md` (owner decision, 2026-08-03) — that artifact previously ruled `warn`/`urgent` only.

**Chunk 01 built** on `feat/advisory-actionability` off `develop` at `596d761`. Suite green, with evidence recorded from the declared JUnit command (the count lives in `.test-evidence.json`, not restated here — a literal total in prose is the part that goes stale). The ordering algorithm changed once during the chunk and the reason is worth carrying forward: a ready-queue toposort was written first, and the fixture render of the four real advisories showed it demoting the `warn` below three unrelated `info` entries — one edge globally re-sorting the block. It is now a pull-up (each advisory emitted after its own prerequisites, otherwise in arrival order), pinned by `test_one_edge_does_not_demote_the_warn_below_unrelated_infos`. Next: Chunk 02 — 17 remaining `owner_action` sites and the four narrowed `recommended_action` values. Chunk 02's own rendered read-through will show the fallback line disappearing as each site lands; it is currently visible on three of the four fixture advisories and on this repo's live one, which is the intended interim state, not a defect.

## Scaffolding

No scaffolding. This is a change to an existing subsystem: `plugin/lib/advisory_store.py` (schema + write path), `plugin/lib/briefing.py` (render + relay), `plugin/lib/advisory_cmd.py` (CLI read side), and the eight probe modules under `plugin/lib/`. Tests run with `uv run pytest -q`.

**Why three chunks.** The surfaces fail differently and are worth separating for review: Chunk 01 is mechanism (a schema change, an ordering algorithm, and a directive rewrite — the part with failure modes), Chunk 02 is 18 sites of owner-facing copy governed by the no-internal-identifiers norm (the part where a reviewer reads prose, not logic), and Chunk 03 is two read-side surfaces that must not drift from the new fields. Merging 01 and 02 would put an algorithm and 18 English sentences under one review pass, where the prose reliably gets skimmed.

### Verification Strategy

Tests cover rendering and ordering, but they cannot tell us the copy actually helps — that is the whole point of the change. So each chunk ends with a rendered-block read-through: assemble a briefing against a fixture store carrying the real advisories from the two reported products (a `warn` backlog migration, an `info` gitignore drift, an `info` untriaged-reports, an `info` structural-coverage) and read the block as an owner would, checking that every entry answers "what do you need from me?" without naming a command for the owner to type. Chunk 01 additionally verifies against this repo's own live briefing, which currently carries one `info` advisory and, under the old rule, relayed nothing.

## Build Chunks

### Chunk 01: Two-audience schema, prerequisite ordering, and the rewritten relay

- **Description:** The thin vertical slice: a probe declares both actions and a prerequisite edge, the store persists them, the briefing orders and renders them, and the relay directive carries them into conversation. `upstream_probes.py` is the one probe converted here because it is the earlier half of the only live prerequisite edge — converting it proves the ordering path end to end rather than in a fixture.
- **Depends on:** none
- **Artifacts consumed:** `documentation/post-sync-advisory-spec.md` §3.3, §3.6, §5, §5.3, §5.4
- **Deliverables:**
  - `plugin/lib/advisory_store.py` — `owner_action: str = ""` and `prerequisite_of: tuple[str, ...] = ()` on `AdvisoryCandidate`; both carried through the write path onto the stored advisory.
  - `plugin/lib/briefing.py` — the `owner →` / `agent →` / `after →` rendering with the `owner_action`-absent fallback; the dismissal hint moved to one per block; a stable prerequisite-ordering pass over the active set that fails soft on unknown types and cycles; `ADVISORY_RELAY_TEXT` rewritten to the four rules of §5.4 plus the interpolated-values-are-data constraint; `_RELAY_PRIORITIES` retired in favour of relaying any active advisory.
  - `plugin/lib/upstream_probes.py` — `owner_action` and `prerequisite_of=("backlog:backlog-service-migration-required",)`.
  - `tests/test_briefing_functions.py` — ordering (including the `info`-before-`warn` inversion), fail-soft on unknown edge and cycle, the absent-`owner_action` fallback, and relay presence for an `info`-only active set. The existing relay tests assert the old `warn`/`urgent`-only rule and are updated to the amended rule, not deleted.
- **Tests:** unit — ordering pass (prerequisite ahead of higher-priority dependent; unknown type inert; cycle falls back to priority order); rendering (both action lines present; fallback line present when `owner_action` is empty; one dismissal hint per block); relay (present for `info`-only, present for `warn`).
- **Acceptance criteria:** `uv run pytest -q` passes. A briefing assembled over a fixture store containing the untriaged-reports and backlog-migration advisories renders triage first with the migration annotated `after →`, despite the migration outranking it on priority. This repo's own session briefing carries the relay directive for its single `info` advisory.
- **Critic mode:** final
  <!-- Override: inference picks `chunk` mid-plan, but this chunk lands the schema and the
       ordering algorithm that Chunks 02 and 03 both build on, and it rewrites a directive
       that ships into every governed product. Coherence is worth the full pass now. -->
- **Visual change:** yes — the advisory block and the relayed conversational form are read by owners, and legibility is the deliverable; a test cannot speak to it.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Rendered-block read-through per the Verification Strategy
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: Owner actions across the probe roster, with the lint that keeps them

- **Description:** Author `owner_action` at the remaining 17 construction sites, and narrow the four `recommended_action` values that currently hold prose or a non-action. Add the authoring lint so the next probe cannot ship without both. This chunk is mostly English, and it is governed by the no-internal-identifiers norm at every site.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/post-sync-advisory-spec.md` §7.2 (the four owner-action shapes and the three authoring rules)
- **Deliverables:**
  - `owner_action` at every remaining site: `plugin/lib/backlog_probes.py` (6), `plugin/lib/norm_probes.py` (5), `plugin/lib/coverage_probes.py` (2), `plugin/lib/api_versioning_probes.py`, `plugin/lib/gitignore_probes.py`, `plugin/lib/install_reference_probes.py`, `plugin/lib/stale_base_probes.py` (1 each).
  - The four narrowed `recommended_action` values — three prose instructions in `plugin/lib/norm_probes.py`, and the explicit non-action in `plugin/lib/backlog_probes.py` whose action text currently renders as `→ Run no action needed`.
  - Named copy targets, because these are the advisories that prompted the work: the structural-coverage advisory gains an owner action that offers the "not relevant — one-line stub is a valid answer" route instead of only listing absent files; the gitignore advisory stops asking a person to run `prawduct-hook`; the backlog-migration advisory states the volume and the irreversibility of the write it authorises.
  - new `tests/test_advisory_actionability.py` — sweeps every `AdvisoryCandidate(` construction under `plugin/lib/*_probes.py`: `owner_action` present and non-empty; no slash command, `prawduct-hook`, or shell invocation inside it; `recommended_action` either empty or a single command token. Plus **every declared `prerequisite_of` key resolves against the registered probe roster** — an edge naming a `<feature>:<type>` no probe registers is inert by design (it fails soft at render time), which means a typo in one is silent forever unless something checks it here. This sweep is the cheap home for that check: the roster is already imported to run the other assertions.
- **Tests:** the authoring lint above (the control this chunk adds); plus a regression that the backlog-migration owner action names both the irreversibility and the volume, since that is the security-model disposition's discharge and a copy edit could quietly drop it.
- **Acceptance criteria:** `uv run pytest -q` passes with the lint green over all 18 sites. Every advisory this repo and a fixture product can raise renders an owner line that answers "what do you need from me?" and contains no command for the owner to type.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Rendered-block read-through per the Verification Strategy
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: The read-side surfaces — advisory CLI and skill

- **Description:** The two surfaces that read advisories outside the briefing, so they do not drift from the new fields: `prawduct-hook advisory list/show` output, and the skill prose that tells the runtime how to work the subsystem.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `documentation/post-sync-advisory-spec.md` §5.1, §6.1
- **Deliverables:**
  - `plugin/lib/advisory_cmd.py` — `show` prints both actions with their audiences; `list` carries the owner action, since a bare summary list is the same "here is a problem, no route out" shape being fixed everywhere else.
  - `plugin/skills/advisory/SKILL.md` — the two-audience model, and the rule that the skill never hands the owner a command to type.
- **Tests:** unit — `show` and `list` output carry both fields, including the fallback line for a stored advisory written without `owner_action`.
- **Acceptance criteria:** `uv run pytest -q` passes; `prawduct-hook advisory list` and `show <id>` against this repo's live store render both audiences.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
