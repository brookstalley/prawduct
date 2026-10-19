---
artifact: build-plan
version: 2
scope: backlog-file-path
branch: fix/backlog-file-path
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: one chunk, one boundary review; no review round, reviewer or mode is added"
      - "proportionality ratchets both ways; new controls emit their yield → conforms: the one new control (`foreign-target`) refuses with its own error code, so every firing is visible in the envelope; it adds no step to an in-repo filing"
      - "state-file growth is advisory only → inapplicable because no state file is touched"
      - "review rigor is stage-keyed → inapplicable because no review mechanism is touched"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable because no reviewer is touched"
      - "authority fails closed; advice fails soft → conforms: the own-target check refuses on an unresolved identity; lint stays advisory and now says so"
      - "the plugin writes nothing into a governed repo but its own state → conforms: nothing new is written locally"
      - "local-first governance, no third-party governance dependencies → conforms: no dependency added; identity is read from project-state and .git/config"
      - "prawduct guides and reviews; it never implements → inapplicable because no product code is touched"
      - "never specific to Python → inapplicable because the backlog adapter is language-neutral already and nothing here reads product code"
      - "goals and verification bind; prescribed method is advice → conforms: each item's acceptance is pinned by a red-verified test"
      - "every fact has one home → conforms: the identity rule lives in `upstream` beside `check_not_self`; the label-length rule in `check_enum`; label spelling in `provision.ensure_labels`'s `applied`"
partition: serial — one chunk; four small fixes on one command path
last_validated: 2026-10-17
lifecycle: completed
archived: 2026-10-19
released_in: v3.7.1
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan: the `backlog file` path (#217, #1004, #1005, #1006)

## Goals

**Response taken:** Proceed, citing #217, #1004, #1005 and #1006. The owner asked on 2026-10-17
for the most important backlog item plus whatever is worth doing at the same time; `/prawduct:backlog
pick` chose #217 (ready, S effort, L impact, security, release-gating since 2026-07-20) and bundled
the three ready S bugs on the same `file` path. Each item states its requirement and acceptance.

**Product.** `backlog file` is the zero-ceremony create, and is zero-ceremony only because it never
crosses an owner boundary (`documentation/backlog-service-upstream-filing.md` §1). Today it accepts
any `--repo`, under a pre-granted tool permission, writing as the user. After this change it writes
only to the running repo's own tracker; the three bugs make its failures and successes legible.

**Inferred decisions (for the boundary):**
- *Inferred:* #217's guard covers `file` only, as the item specifies. The id-addressed writes
  (`comment`, `update`, `status`, `link`) carry the same hazard, but their target resolves from the
  id inside `core` (redirects included), so a correct guard sits there, not in the CLI. Filed as a
  follow-up (#1013) rather than widened here.
- *Inferred:* #1005 is fixed by re-reading state, not by parsing `already_exists` out of the 422.
  The `gh` stderr shape is unverified offline and not ours; a fresh listing is the fact the caller
  needs. And rather than rely on GitHub matching label names case-insensitively on issue create
  (unverified), provisioning returns the existing spelling (`applied`) and every caller applies it.
- *Inferred:* #1004's check lives in `check_enum`, which both write paths call, and applies to every
  facet including `stage`. `import` builds labels without calling it; filed as #1014.

**Decisions made mid-build:**
- `update_item` ran its facet `check_enum` after the title/body PATCH, so making length a refusal
  would have left items half-updated. Moved into the pre-request validation block. Settled by
  "do it right": every other offline check in that function already sits there.
- `update`'s facet and tag swaps compared label names case-sensitively, so a case variant already
  on the issue would be removed as the "old" value. Now case-insensitive. Same rule as #1005.
- Boundary review (W1, O-2/O-3): reusing GitHub's spelling made the READ side matter, since
  decode matched facet prefixes case-sensitively and would drop a facet carried as
  `Source:Review`. One helper, `encode.facet_labels` (its rule later moved to `label_has_prefix`, below), owns the prefix match for decode,
  `is_prawduct_issue`, status reconciliation and both `update` swaps; closed-vocabulary values
  (`stage`, `status`) decode to their canonical spelling. Settled by "do it right" and the
  one-home norm. `id:` alias labels stay case-sensitive: prawduct mints them, and alias
  resolution in `ids` is outside this path.
- Cumulative review (R-2): three facet-prefix readers off the `file`/`update` path still matched
  on their own (`provision.facet_of`, `restructure`'s kind strip, `is_prawduct_issue`'s loop).
  The rule moved down a level to `encode.label_has_prefix`, which `facet_labels` and all three
  now call; it keeps `id:` exact. Cumulative review (R-1): tests asserting on all of the hook's
  stderr failed in agent worktrees on the linked-worktree NOTE; they now run through
  `tests/fixtures/hook_env.isolated_hook_run`. Settled by the coordinator: fix both in place.

## Chunk 01 — the four fixes

**Delivers:** `upstream.check_own_target` + the `_run_file` call (`foreign-target`); the
`check_enum` length rule and `update_item`'s pre-request facet check; case-insensitive
`_create_missing` with the refused-create re-list and `ProvisionResult.applied` threaded through
every apply site; `_emit(op=…)` printing `filed <id>: <url>`, the stdout flush, and the advisory
lint prefix. API contract (`file` row, `foreign-target` code), backlog SKILL.md's `--repo`
sentence, change-log, rolling release note, dev.5 bump.

**Acceptance:** #217 (a)–(c) and the unresolved and origin-only cases; #1004 refuse-naming-flag,
exactly-50 files, update refuses with no request; #1005 case variant reused on file and update, the
race counted as existing, a refused create for an absent label still fails, reconcile shares the
rule; #1006 filed line first with URL, `get` unaffected, outcome before lint under a buffered
stdout. Each red-verified by reinstating its defect.

**Done when:** acceptance passes, suite green, `/prawduct:critic` boundary review clean of blocking.

## Status

- [x] Chunk 01 — the four fixes
