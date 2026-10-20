---
artifact: build-plan
version: 2
scope: change-log-fragments
branch: feature/change-log-fragments
depends_on:
  - artifact: documentation/issues/1012-requirements.md
  - artifact: documentation/issues/1012-design.md
governed_by:
  - artifact: data-model
    dispositions:
      - "Critic-data-plane verdicts come from the fact ledger → inapplicable because fragments are not Critic facts and no Critic verdict reads them"
      - "facts immutable and append-only → inapplicable because that norm's stated scope is the evidence store; the cut moves fragment content verbatim into the append-only archive and never edits archived history"
      - "derived views never authoritative → conforms: the cut renders the plugin/CHANGELOG.md section once, and no gate reads it (the banner is not a gate)"
      - "governance documents archived, never deleted → inapplicable because the norm covers .prawduct/artifacts/; fragments live in .prawduct/changes/, and the cut moves their content into the archive rather than discarding it"
      - "newer-schema facts block loudly → conforms: `schema: 1` is required and a higher value is refused (design, prior-art section)"
      - "two stores, two lifetimes → conforms: fragments are committed shared answers"
      - "backlog_service_repo selects the store → conforms: the merge-flow close reads `closes:` and routes through /prawduct:backlog"
  - artifact: architecture
    dispositions:
      - "local-first, stdlib-only governance runtime → conforms: Python stdlib only; changie and towncrier rejected (FRG8)"
      - "reviewer never mutates the session it reviews → inapplicable because no review path writes fragments"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; CLI subcommands internal → conforms: cut-change-log and migrate-change-log join the internal/unstable tier"
partition: serial — 02 and 03 both read through 01's module, 03's cut is tested against 02's pending_scopes, and 04 migrates with all three in place
last_validated: 2026-10-19
---

# Build Plan — Change-Log Fragments, Wave 1 (#1012)

## Goals

**Response taken:** Proceed citing a backlog item and its design: #1012, with
`documentation/issues/1012-requirements.md` and `1012-design.md`. The owner approved the fragment
direction on 2026-10-17. On 2026-10-19 the owner asked for changie.dev's one-file-per-scope model
and confirmed two design decisions: `type` is a closed set, and a reopened scope is a new fragment
carrying `reopens:`.

**Product:** Every branch today edits two shared files (`.prawduct/change-log.md` and the rolling
`plugin/CHANGELOG.md` section). That costs merge conflicts (#1019 on 2026-10-19), a `merge=union`
driver that resurrects archived entries (#857), hand-written tags nothing validates, and consumer
notes written in bulk at the cut (16 of 26 scopes at v3.7.1). Wave 1 moves prawduct itself onto one
validated file per scope. Wave 2, planned after this ships, rolls the format out to onboarded repos.

**Architecture:**
- One owner module, `change_fragments.py`; no other module parses a fragment.
- Every reader accepts both shapes (legacy log and fragments) for the whole window, so onboarded
  repos are unaffected by wave 1.
- `plugin/CHANGELOG.md` is written only by the cut.
- Must stay possible: wave 2's migration of onboarded repos, and #834 drafting the fragment from
  the PR body.

**Constraints:** Python stdlib only (owner, in #1012). Archived history is never rewritten.
Nothing may require a post-merge commit (`/prawduct:pr` Step 1d).

**Owner decisions, 2026-10-19:**
- The `## Consumer note` section is required, holding text or `none: <reason>`. The cut's dry run
  lists every `none:` with its reason, and the release-time digest-coverage advisory is retired for
  fragments.
- `closes:` is backend-neutral and holds backlog item IDs (via `lib/backlog/ids.py`). It is the
  single source for which items a change closes: the PR body's `Closes` lines are generated from
  it, and the Merge Flow closes those items from it.

**Tradeoffs accepted:**
- The rolling per-merge `-dev.N` version bumps stay. The cut makes most of their reason go away;
  revisit once wave 1 has run one release.
- `.gitattributes` keeps `merge=union` for the legacy log in this repo through wave 1, because
  `gitattributes_probes` still requires it until wave 2 gates the probe.

**Decisions made mid-build:** *(one line each, naming what settled it)*

**Level:** High. The design is grounded in the current tree (re-verified 2026-10-19), the July
proposal is reconciled, and every schema decision is the owner's.

## Status

- [ ] Chunk 01: Fragment format core — `change_fragments.py`, schema, template
- [ ] Chunk 02: Readers and the PR gate read fragments (dual-shape)
- [ ] Chunk 03: The cut — `cut-change-log`
- [ ] Chunk 04: Prawduct migrates onto fragments; docs and runbooks
Context: Plan written 2026-10-19 on `feature/change-log-fragments`; nothing built yet. The amended
requirements and design ride this branch. Next: Chunk 01.

## Verification Strategy

Each chunk is exercised as the release operator and the PR flow would use it, beyond the unit
tests. From 02 on, run `check-releasability` and `check-change-log-entry` against a scratch repo
holding fragments, legacy entries, and both. 03 merges two real branches that each add a fragment,
with no union driver, and dry-runs and applies a cut on a copy of this repo. 04 runs the
migration on this repo itself; the result must leave `check-releasability --release v3.7.2` naming
the same pending scopes as before.

## Build Chunks

### Chunk 01: Fragment format core — `change_fragments.py`, schema, template

- **Description:** The single owner of the fragment format. Parse frontmatter and body, validate
  against the D2 schema, and render a fragment as a legacy archive block and as consumer text.
  Every error code the design names gets a fixture that must be refused. Per core.md, a check
  never seen to fail proves nothing.
  A persisted format is a lock-in decision, so the schema answers these consumer queries and no
  others:
  - Which scopes are pending? (`check-releasability`)
  - Which plan does a scope belong to? (`plan-backfill`)
  - What is the consumer note for each scope in this release? (the cut)
  - Which backlog items does this change close? (PR Create Step 5, the Merge Flow)
  - Which scope does this one reopen? (`reopens`)
  - Was this written by a newer plugin? (`schema`)
  - Is the record well-formed? (Step 1c, `record_lint`)

  `type` has no reader today. It is kept by owner decision, rendered into the archive tag line.
- **Depends on:** none
- **Artifacts consumed:** `1012-design.md` D1, D2, D3, D5; `1012-requirements.md` FRG1–FRG3, FRG8
- **Deliverables:**
  - new `plugin/lib/change_fragments.py` (`parse_fragment`, `validate_fragment`, `load_pending`, `render_entry`, `render_consumer_section`)
  - new `plugin/templates/change-fragment.md`
  - The schema: `schema` (required, must be 1), `type` (closed set of seven), `scope` (equals the
    filename stem), `date`, `title`, optional `closes` and `reopens`, and a required
    `## Consumer note` section holding text or `none: <reason>`.
  - `RELEASE_VALUE_RE` and `RETIRED_TAG_KEYS` are imported from `change_log.py`, not copied.
- **Tests:** new `tests/test_change_fragments.py`. One refusal fixture per error code, each
  red-verified by removing the check. A round-trip test: `render_entry` output parses with the
  legacy `parse_change_log` to the same scope and title.
- **Acceptance criteria:** every D2/D3/D5 error code has a fixture that fails without its check;
  a valid fragment renders to a block the legacy archive parser accepts.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Readers and the PR gate read fragments (dual-shape)

- **Description:** `pending_scopes(root)` returns the union of legacy pending entries and
  fragments; a scope appearing in both is a hard error. Every consumer of the change record goes
  through it. The consumer set is enumerated by query, not taken from the design's list: a grep
  for `change-log.md`, `CHANGE_LOG_REL_PATH` and `parse_change_log` over `plugin/lib` and
  `plugin/bin` on 2026-10-19 found modules the design's D7 omits (`lifecycle_repair`,
  `coverage_algebra`, `onboarding_probes`, `oversized_state_probes`). Each is switched or
  recorded here as not reading pending state. The PR Step 1c probe accepts a branch that adds one
  valid fragment and surfaces validation errors as its refusal. PR Create Step 5 generates the
  body's `Closes` lines from the fragment's `closes:`, and the Merge Flow closes those items from
  it. `check-releasability`'s digest-coverage advisory stops applying to fragment-shaped scopes.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1012-design.md` D6 (readers), D7; FRG6
- **Deliverables:**
  - `pending_scopes` in `release_readiness.py`, used by every reader in the enumerated set
  - `check-change-log-entry` (in `coverage.py`) accepts and validates fragments
  - `record_lint` lints the fragment directory
  - `/prawduct:pr` Step 1c/1d, Create Step 5's `Closes` lines and the Merge Flow close step, rewritten for fragments
  - the Critic cross-check text for fragments
- **Tests:** the existing `release_readiness` and coverage tests pass unchanged against a
  legacy-only repo. New fixtures cover fragments-only, both shapes, the same scope in both
  (refused), and Step 1c refusing a malformed fragment.
- **Acceptance criteria:** `check-releasability` gives the same verdict on a repo whether a pending
  scope is a legacy entry or a fragment; Step 1c refuses each schema error by code.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The cut — `cut-change-log`

- **Description:** `prawduct-hook cut-change-log --release vX.Y.Z [--apply]` (D4). It validates
  everything first and writes nothing on any error. It renders archive blocks tagged
  `release=vX.Y.Z` into the month buckets (skipping on the `(date, scope)` key, so a re-run is
  safe), inserts consumer-note text under the open `-dev` section's headline, and removes the cut
  fragments, all as one staged transaction. It never writes a headline, and it refuses when the
  open section has none. Fragments a release plan classifies `withheld` stay pending. A trunk-base
  PR runs the same cut for a set of one.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `1012-design.md` D4; FRG4, FRG5
- **Deliverables:**
  - the `cut-change-log` subcommand, a dry run by default
  - a two-branch merge test with no union driver
  - withheld scopes are left pending
- **Tests:**
  - A real `git merge` of two branches, each adding a fragment, is clean.
  - Cut output is byte-identical to the legacy renderer on a fixture.
  - A failure injected after the archive write leaves a re-runnable state.
  - A re-run is a no-op.
  - Each refusal code (`no-headline`, a validation error, a released fragment found in the
    pending directory) has its own test.
- **Acceptance criteria:** a dry run then `--apply` on a copy of this repo with fragments produces
  the archive blocks and the `plugin/CHANGELOG.md` notes, and empties the directory except for
  withheld scopes.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Prawduct migrates onto fragments; docs and runbooks

- **Description:**
  - `prawduct-hook migrate-change-log` (D6) converts release-pending legacy entries into fragments,
    with its named refusals, and runs on this repo. This branch's own record becomes this repo's
    first fragment.
  - The release runbooks replace Phase 1 steps 1–3 and step 10's note-writing with the cut.
    `documentation/release-process.md`, the change-log template's grammar comment and the PR
    skill are brought into agreement.
  - Docs are swept by searching for the claim ("release-pending is the absence of `release=`",
    "append at the top"), not for the edited tokens.
  - `change-log-ledger-design.md` is archived as superseded by #1012.
- **Depends on:** Chunk 03
- **Artifacts consumed:** `1012-design.md` D6 (migration), build sketch chunk 5
- **Deliverables:**
  - the `migrate-change-log` subcommand
  - this repo's pending entries converted to new `.prawduct/changes/` fragments
  - the runbook, release-process, template and skill text updated
  - the July proposal archived as superseded
- **Tests:** the five fixtures in FRG7 (empty log, pending-only, mixed, `release=unreleased`
  refused, two tag lines refused); a second migration run is a no-op.
- **Acceptance criteria:** after migrating this repo, `check-releasability --release v3.7.2`
  names the same pending scopes it named before; a claim-search for the legacy rules returns only
  history.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review. The last chunk's cumulative
review makes the branch PR-ready.

- After chunk 01: confirm the schema with the owner before readers depend on it. A persisted
  format is a lock-in decision.
- After chunk 03: confirm a real two-branch merge and a dry-run cut before migrating this repo.
- After chunk 04 (cumulative): full-bundle review, then plan wave 2 (consumer rollout).
